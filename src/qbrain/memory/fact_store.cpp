#include "qbrain/memory/fact_store.hpp"
#include "qbrain/util/hash.hpp"
#include "qbrain/util/utf8_display.hpp"
#include <algorithm>
#include <chrono>
#include <limits>
#include <random>
#include <set>
#include <unordered_map>

namespace qbrain::memory {
namespace {
using DB = storage::Database;
constexpr int max_evidence = 16, max_relations = 32, max_candidates = 100;
int64_t clock_now() {
  return std::chrono::duration_cast<std::chrono::seconds>(
      std::chrono::system_clock::now().time_since_epoch()).count();
}
void require(bool condition, const char* code) { if (!condition) throw Error(code); }
void keys(const Json& value, std::initializer_list<const char*> allowed) {
  require(value.is_object(), "fact_invalid_payload");
  for (auto it = value.begin(); it != value.end(); ++it) {
    bool found = false;
    for (const auto* name : allowed) if (it.key() == name) found = true;
    require(found, "fact_unexpected_argument");
  }
}
std::string field(const Json& value, const char* name) {
  require(value.contains(name) && value[name].is_string(), "fact_invalid_field");
  return value[name].get<std::string>();
}
void identifier(const std::string& id) {
  require(id.size() == 64 && std::all_of(id.begin(), id.end(), [](unsigned char c) {
    return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
  }), "fact_invalid_id");
}
void predicate_check(const std::string& p) {
  require(!p.empty() && p.size() <= 64 && p[0] >= 'a' && p[0] <= 'z' &&
      std::all_of(p.begin(), p.end(), [](unsigned char c) {
        return (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') ||
               c == '_' || c == '.' || c == '-';
      }), "fact_invalid_predicate");
  require(!contains_sensitive_material(p), "sensitive_material_rejected");
}
int64_t revision(const Json& p) {
  require(p.contains("expected_revision") && p["expected_revision"].is_number_integer() &&
      p["expected_revision"] >= 1 && p["expected_revision"] < INT32_MAX, "fact_invalid_revision");
  return p["expected_revision"].get<int64_t>();
}
struct Tx {
  DB& db; bool done = false; int old_timeout = 0;
  explicit Tx(DB& d) : db(d) {
    { auto s = db.prepare("PRAGMA busy_timeout"); if (s.step()) old_timeout = int(s.column_int(0)); }
    db.exec("PRAGMA busy_timeout=2500");
    try { db.exec("BEGIN IMMEDIATE"); }
    catch (...) { db.exec("PRAGMA busy_timeout=" + std::to_string(old_timeout)); throw; }
  }
  void commit() { db.exec("COMMIT"); done = true; }
  ~Tx() {
    if (!done) { try { db.exec("ROLLBACK"); } catch (...) {} }
    try { db.exec("PRAGMA busy_timeout=" + std::to_string(old_timeout)); } catch (...) {}
  }
};
bool exists(DB& db, const char* name, const char* type = "table") {
  auto s = db.prepare("SELECT 1 FROM sqlite_master WHERE type=? AND name=?");
  s.bind_text(1, type); s.bind_text(2, name); return s.step();
}
bool ready(DB& db) {
  if (!exists(db, "memory_fact_module")) {
    require(!exists(db, "memory_facts") && !exists(db, "memory_fact_evidence") &&
        !exists(db, "memory_fact_relations"), "fact_schema_conflict");
    return false;
  }
  { auto s = db.prepare("SELECT version FROM memory_fact_module");
    require(s.step() && s.column_int(0) == 1 && !s.step(), "fact_schema_version_unsupported"); }
  for (const auto* name : {"memory_facts", "memory_fact_evidence", "memory_fact_relations"})
    require(exists(db, name), "fact_schema_incomplete");
  require(exists(db, "memory_fact_last_evidence", "trigger"), "fact_schema_incomplete");
  return true;
}
void initialize(DB& db) {
  if (ready(db)) return;
  const auto path = db.backend_file_path();
  if (!path.empty()) {
    std::random_device rng; std::string entropy;
    for (int i = 0; i < 8; ++i) entropy += std::to_string(rng()) + ":";
    require(db.backup_to(path + ".pre-facts-v1-" + util::sha256_hex(entropy) + ".bak"),
            "fact_backup_failed");
  }
  Tx tx(db);
  if (!ready(db)) {
    db.exec(R"SQL(
CREATE TABLE memory_fact_module(version INTEGER PRIMARY KEY CHECK(version=1));
INSERT INTO memory_fact_module VALUES(1);
CREATE TABLE memory_facts(
 fact_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
 subject TEXT NOT NULL CHECK(subject='user'), predicate TEXT NOT NULL, object TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','superseded','retracted')),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>=1 AND revision<=2147483647),
 created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL, UNIQUE(fact_id,source_id));
CREATE TABLE memory_fact_evidence(
 fact_id TEXT NOT NULL, source_id TEXT NOT NULL,
 item_id TEXT NOT NULL REFERENCES memory_items(item_id) ON DELETE CASCADE,
 quote_hash TEXT NOT NULL, payload_hash TEXT NOT NULL, created_at INTEGER NOT NULL,
 PRIMARY KEY(fact_id,item_id),
 FOREIGN KEY(fact_id,source_id) REFERENCES memory_facts(fact_id,source_id) ON DELETE CASCADE);
CREATE TABLE memory_fact_relations(
 source_id TEXT NOT NULL, from_id TEXT NOT NULL, to_id TEXT NOT NULL,
 relation TEXT NOT NULL CHECK(relation IN ('superseded_by','contradicts')),
 created_at INTEGER NOT NULL, CHECK(from_id<>to_id),
 PRIMARY KEY(from_id,to_id,relation),
 FOREIGN KEY(from_id,source_id) REFERENCES memory_facts(fact_id,source_id) ON DELETE CASCADE,
 FOREIGN KEY(to_id,source_id) REFERENCES memory_facts(fact_id,source_id) ON DELETE CASCADE);
CREATE INDEX idx_memory_facts_source ON memory_facts(source_id,status,predicate,created_at,fact_id);
CREATE INDEX idx_memory_fact_evidence_item ON memory_fact_evidence(item_id);
CREATE INDEX idx_memory_fact_relations_to ON memory_fact_relations(to_id);
CREATE TRIGGER memory_fact_last_evidence AFTER DELETE ON memory_fact_evidence
BEGIN
 UPDATE memory_facts SET revision=MIN(revision+1,2147483647),
  updated_at=MAX(updated_at,CAST(strftime('%s','now') AS INTEGER))
  WHERE fact_id=OLD.fact_id AND source_id=OLD.source_id
  AND EXISTS(SELECT 1 FROM memory_fact_evidence WHERE fact_id=OLD.fact_id);
 DELETE FROM memory_facts WHERE fact_id=OLD.fact_id AND source_id=OLD.source_id
  AND NOT EXISTS(SELECT 1 FROM memory_fact_evidence WHERE fact_id=OLD.fact_id);
END;
)SQL");
  }
  tx.commit();
}
// Keep a read statement at SQLITE_ROW to pin schema detection and later reads
// in one implicit SQLite snapshot. Do not issue BEGIN/ROLLBACK: existing read
// APIs support authorizers that deny transaction-control SQL. Finalizing this
// statement releases only its own read, never the caller's transaction.
struct ReadSnapshot {
  DB::Statement pin;
  explicit ReadSnapshot(DB& db) : pin(db.prepare("SELECT COUNT(*) FROM sqlite_master")) {
    require(pin.step(), "fact_snapshot_unavailable");
  }
  ReadSnapshot(const ReadSnapshot&) = delete;
  ReadSnapshot& operator=(const ReadSnapshot&) = delete;
};
bool archive_ready(DB& db) {
  if (!exists(db,"memory_fact_lifecycle_module")) {
    require(!exists(db,"memory_fact_archive"),"fact_lifecycle_schema_conflict");
    return false;
  }
  auto version=db.prepare("SELECT version FROM memory_fact_lifecycle_module");
  require(version.step() && version.column_int(0)==1 && !version.step(),
          "fact_lifecycle_version_unsupported");
  require(exists(db,"memory_fact_archive"),"fact_lifecycle_schema_incomplete");
  // Validate the required columns even when there are no archived rows.
  auto columns=db.prepare("SELECT fact_id,source_id,archived_at FROM memory_fact_archive LIMIT 0");
  columns.step();
  return true;
}
void initialize_archive(DB& db) {
  {
  ReadSnapshot snapshot(db);
  if (archive_ready(db)) return;
  require(ready(db),"fact_not_found");
  const auto path=db.backend_file_path();
  if (!path.empty()) {
    std::random_device rng; std::string entropy;
    for (int n=0;n<8;++n) entropy+=std::to_string(rng())+":";
    require(db.backup_to(path+".pre-lifecycle-v1-"+util::sha256_hex(entropy)+".bak"),
            "fact_lifecycle_backup_failed");
  }
  } // Release the pinned pre-migration backup snapshot before taking a writer lock.
  Tx tx(db);
  if (!archive_ready(db)) db.exec(R"SQL(
CREATE TABLE memory_fact_lifecycle_module(version INTEGER PRIMARY KEY CHECK(version=1));
INSERT INTO memory_fact_lifecycle_module VALUES(1);
CREATE TABLE memory_fact_archive(
 fact_id TEXT PRIMARY KEY, source_id TEXT NOT NULL,
 archived_at INTEGER NOT NULL CHECK(archived_at>=0),
 FOREIGN KEY(fact_id,source_id) REFERENCES memory_facts(fact_id,source_id) ON DELETE CASCADE);
CREATE INDEX idx_memory_fact_archive_source ON memory_fact_archive(source_id,fact_id);
)SQL");
  tx.commit();
}
bool is_archived(DB& db,const std::string& source,const std::string& id) {
  auto row=db.prepare("SELECT archived_at,typeof(archived_at) FROM memory_fact_archive WHERE source_id=? AND fact_id=?");
  row.bind_text(1,source);row.bind_text(2,id);
  if (!row.step()) return false;
  require(row.column_text(1)=="integer" && !row.column_is_null(0) && row.column_int(0)>=0,
          "fact_lifecycle_invalid_metadata");
  return true;
}
struct Evidence {
  std::string item, event, quote, hash;
  Json reference;
};
struct ReadWork {
  int checks = 0;
  std::size_t bytes = 0;
  std::unordered_map<std::string,Evidence> cache;
};
Evidence evidence(DB& db, const std::string& source, const std::string& item, int64_t at, ReadWork* work = nullptr) {
  if (work) {
    if (auto it = work->cache.find(item); it != work->cache.end()) return it->second;
    require(++work->checks <= 512, "fact_read_work_limit");
  }
  identifier(item);
  if (!exists(db, "memory_module") || !exists(db, "memory_items") || !exists(db, "memory_events"))
    throw Error("fact_evidence_unavailable");
  { auto version = db.prepare("SELECT version FROM memory_module");
    require(version.step() && version.column_int(0)==1 && !version.step(), "fact_evidence_unavailable"); }
  auto s = db.prepare(
      "SELECT m.event_id,m.category,m.quote,m.message_index,m.expires_at,e.status,e.payload_hash,"
      "e.page_hash,e.expires_at,e.session_id,e.fragment_id,e.method,p.slug,p.body,p.content_hash,p.deleted_at "
      "FROM memory_items m JOIN memory_events e ON e.event_id=m.event_id "
      "JOIN pages p ON p.id=e.page_id AND p.source_id=e.source_id WHERE m.item_id=? AND e.source_id=? "
      "AND length(CAST(m.quote AS BLOB))<=4096 AND length(CAST(p.body AS BLOB))<=262144");
  s.bind_text(1, item); s.bind_text(2, source);
  require(s.step(), "fact_evidence_unavailable");
  const auto event = s.column_text(0), category = s.column_text(1), quote = s.column_text(2);
  const auto index = s.column_int(3), expiry = s.column_int(4), event_expiry = s.column_int(8);
  const auto hash = s.column_text(6), body = s.column_text(13);
  if (work) { work->bytes += body.size(); require(work->bytes <= 8*1024*1024, "fact_read_work_limit"); }
  require(s.column_text(5) == "extracted" && s.column_is_null(15) && expiry == event_expiry &&
      expiry >= 0 && (!expiry || expiry > at) && s.column_text(14) == s.column_text(7) &&
      !quote.empty() && quote.size() <= 4096 && util::valid_utf8(quote) &&
      body.size() <= max_payload_bytes && util::sha256_hex(body) == hash,
      "fact_evidence_unavailable");
  require(!contains_sensitive_material(quote), "fact_evidence_unavailable");
  require(event == util::sha256_hex(Json::array({"qbrain-memory-v1",source,
      s.column_text(9),s.column_text(10),hash}).dump()), "fact_evidence_unavailable");
  Json payload;
  try {
    payload = Json::parse(body, [](int depth, Json::parse_event_t, Json&) {
      if (depth > 8) throw Error("fact_evidence_unavailable");
      return true;
    });
    require(payload.is_object() && payload.contains("messages") && payload["messages"].is_array() &&
        payload.contains("expires_at") && payload["expires_at"].is_number_integer() &&
        payload["expires_at"] == event_expiry && index >= 0 &&
        static_cast<std::size_t>(index) < payload["messages"].size(), "fact_evidence_unavailable");
    const auto& message = payload["messages"][static_cast<std::size_t>(index)];
    require(message.is_object() && message.value("role", "") == "user" &&
        message.at("content") == quote, "fact_evidence_unavailable");
  } catch (...) { throw Error("fact_evidence_unavailable"); }
  const std::set<std::string> categories = {"preference","decision","commitment","event","lesson","fact"};
  require(categories.count(category) && item == util::sha256_hex(event +
      Json({{"message_index",index},{"category",category},{"quote",quote}}).dump()), "fact_evidence_unavailable");
  Evidence result{item,event,quote,hash,{{"item_id",item},{"event_id",event},{"source_id",source},
      {"session_id",s.column_text(9)},{"message_index",index},{"category",category},
      {"expires_at",expiry},{"method",s.column_text(11)},{"evidence_slug",s.column_text(12)}}};
  if (work) work->cache.emplace(item,result);
  return result;
}
Json load(DB& db, const std::string& source, const std::string& id, int64_t at, ReadWork* work = nullptr) {
  auto s = db.prepare("SELECT subject,predicate,object,status,revision,created_at,updated_at "
                      "FROM memory_facts WHERE source_id=? AND fact_id=?");
  s.bind_text(1,source); s.bind_text(2,id);
  if (!s.step()) return nullptr;
  Json out = {{"fact_id",id},{"source_id",source},{"subject",s.column_text(0)},
      {"predicate",s.column_text(1)},{"object",s.column_text(2)},{"status",s.column_text(3)},
      {"revision",s.column_int(4)},{"created_at",s.column_int(5)},{"updated_at",s.column_int(6)},
      {"confidence",nullptr},{"truth_status","caller_attested_user_statement"},
      {"untrusted_data",true},{"evidence",Json::array()}};
  auto refs = db.prepare("SELECT item_id,quote_hash,payload_hash FROM memory_fact_evidence "
                         "WHERE fact_id=? AND source_id=? ORDER BY item_id LIMIT 17");
  refs.bind_text(1,id); refs.bind_text(2,source);
  int count = 0;
  while (refs.step()) {
    require(++count <= max_evidence, "fact_evidence_limit");
    try {
      auto e = evidence(db,source,refs.column_text(0),at,work);
      if (e.quote != out["object"].get_ref<const std::string&>() || util::sha256_hex(e.quote) != refs.column_text(1) ||
          e.hash != refs.column_text(2)) continue;
      out["evidence"].push_back(e.reference);
    } catch (const Error& e) {
      if (std::string(e.what()) != "fact_evidence_unavailable") throw;
    }
  }
  if (out["evidence"].empty()) return nullptr; // Never publish orphaned or stale text.
  out["evidence_count"] = out["evidence"].size();
  return out;
}
// Shared strict N47F age semantics; this is support creation age, not usage,
// confirmation, truth or an automatic maintenance policy.
Json support_age(DB& db, const Json& fact, int64_t at, int days) {
  int64_t newest=0;bool anomaly=false,unknown=false;
  for(const auto& support:fact["evidence"]) {
    auto time=db.prepare("SELECT created_at,typeof(created_at) FROM memory_items WHERE item_id=?");
    time.bind_text(1,support["item_id"].get_ref<const std::string&>());
    require(time.step(),"fact_evidence_unavailable");
    const auto value=time.column_int(0);
    if(time.column_text(1)!="integer" || time.column_is_null(0) || value<=0)unknown=true;
    else if(value>at)anomaly=true;
    else newest=std::max(newest,value);
  }
  Json age=nullptr,created=nullptr;std::string state="unknown";
  if(anomaly)state="clock_anomaly";
  else if(!unknown && newest>0) {
    age=at-newest;created=newest;
    state=at-newest>=int64_t(days)*86400?"stale":"fresh";
  }
  return {{"age_state",state},{"age_seconds",age},{"latest_valid_support_created_at",created}};
}
Json need(DB& db, const std::string& source, const std::string& id, int64_t at) {
  require(ready(db), "fact_not_found");
  auto f = load(db,source,id,at); require(!f.is_null(), "fact_not_found"); return f;
}
void insert_evidence(DB& db, const std::string& source, const std::string& id, const Evidence& e, int64_t at) {
  auto s = db.prepare("INSERT INTO memory_fact_evidence(fact_id,source_id,item_id,quote_hash,payload_hash,created_at) "
                      "VALUES(?,?,?,?,?,?)");
  s.bind_text(1,id); s.bind_text(2,source); s.bind_text(3,e.item);
  s.bind_text(4,util::sha256_hex(e.quote)); s.bind_text(5,e.hash); s.bind_int(6,at); s.step_done();
}
void advance(DB& db, const std::string& source, const std::string& id, int64_t rev,
             const std::string& status, int64_t at) {
  require(rev > 0 && rev < INT32_MAX, "fact_invalid_revision");
  auto s = db.prepare("UPDATE memory_facts SET status=?,revision=revision+1,updated_at=? "
                      "WHERE source_id=? AND fact_id=? AND revision=?");
  s.bind_text(1,status); s.bind_int(2,at); s.bind_text(3,source); s.bind_text(4,id); s.bind_int(5,rev);
  s.step_done(); require(db.changes() == 1, "fact_revision_conflict");
}
bool has_relation(DB& db, const std::string& source, const std::string& a,
                  const std::string& b, const std::string& kind) {
  auto s = db.prepare("SELECT 1 FROM memory_fact_relations WHERE source_id=? AND from_id=? AND to_id=? AND relation=?");
  s.bind_text(1,source); s.bind_text(2,a); s.bind_text(3,b); s.bind_text(4,kind); return s.step();
}
void link(DB& db, const std::string& source, const std::string& a,
          const std::string& b, const std::string& kind, int64_t at) {
  for (const auto& id : {a,b}) {
    auto n = db.prepare("SELECT COUNT(*) FROM memory_fact_relations WHERE source_id=? AND (from_id=? OR to_id=?)");
    n.bind_text(1,source); n.bind_text(2,id); n.bind_text(3,id);
    require(n.step() && n.column_int(0) < max_relations, "fact_relation_limit");
  }
  auto s = db.prepare("INSERT INTO memory_fact_relations(source_id,from_id,to_id,relation,created_at) VALUES(?,?,?,?,?)");
  s.bind_text(1,source); s.bind_text(2,a); s.bind_text(3,b); s.bind_text(4,kind); s.bind_int(5,at); s.step_done();
}
void compatible(const Json& a, const Json& b) {
  require(a["fact_id"] != b["fact_id"] && a["source_id"] == b["source_id"] &&
      a["subject"] == b["subject"] && a["predicate"] == b["predicate"] && a["object"] != b["object"],
      "fact_incompatible_relation");
}
Json receipt(const Json& fact, bool duplicate = false) {
  return {{"fact_id",fact["fact_id"]},{"source_id",fact["source_id"]},
          {"status",fact["status"]},{"revision",fact["revision"]},{"duplicate",duplicate}};
}
}  // namespace

FactStore::FactStore(Brain& brain, std::string source) : brain_(brain), source_(std::move(source)) { validate(); }
void FactStore::validate() const {
  require(brain_.db().backend_kind() == storage::BackendKind::sqlite, "fact_backend_unsupported");
  const auto canonical = Brain::canonical_source_id(source_);
  require(canonical && *canonical == source_ && brain_.source_exists(source_), "invalid_source");
  auto s = brain_.db().prepare("PRAGMA foreign_keys");
  require(s.step() && s.column_int(0) == 1, "fact_foreign_keys_required");
}


namespace {
// Promotion may add a CURRENT independent support to a still-active assertion
// whose original supports have all genuinely expired. Historical validation is
// eligibility only: it is never returned as live evidence, does not change old
// expiry, and never repairs tampered/deleted/partially invalid backing records.
Json promotion_target(DB& db,const std::string& source,const std::string& id,int64_t at) {
  auto live=load(db,source,id,at);
  if(!live.is_null())return live;
  const auto historical=load(db,source,id,0);
  require(!historical.is_null() && historical["status"]=="active","fact_not_found");
  auto count=db.prepare("SELECT COUNT(*) FROM memory_fact_evidence WHERE source_id=? AND fact_id=?");
  count.bind_text(1,source);count.bind_text(2,id);
  require(count.step() && count.column_int(0)>=1 && count.column_int(0)<=max_evidence &&
      historical["evidence_count"]==count.column_int(0),"fact_not_found");
  for(const auto& support:historical["evidence"]) {
    const auto expiry=support["expires_at"].get<int64_t>();
    require(expiry>0 && expiry<=at,"fact_not_found");
  }
  return historical;
}
std::vector<Evidence> promotion_evidence(DB& db,const std::string& source,
                                        const std::string& id,int64_t at) {
  if(!exists(db,"memory_module") || !exists(db,"memory_events") || !exists(db,"memory_items"))
    throw Error("fact_event_unavailable");
  auto state=db.prepare("SELECT e.status,e.method,e.expires_at,e.payload_hash,e.page_hash,"
      "e.session_id,e.fragment_id,p.body,p.content_hash,p.deleted_at "
      "FROM memory_events e JOIN pages p ON p.id=e.page_id AND p.source_id=e.source_id "
      "WHERE e.source_id=? AND e.event_id=? AND length(CAST(p.body AS BLOB))<=262144");
  state.bind_text(1,source);state.bind_text(2,id);
  require(state.step(),"fact_event_unavailable");
  const auto status=state.column_text(0),body=state.column_text(7),hash=state.column_text(3);
  const auto expiry=state.column_int(2);
  require(state.column_text(1)=="explicit-markers-v1","fact_local_extraction_required");
  require((status=="extracted"||status=="no_matches") && state.column_is_null(9) &&
      expiry>=0 && (!expiry||expiry>at) && hash==util::sha256_hex(body) &&
      state.column_text(4)==state.column_text(8) &&
      id==util::sha256_hex(Json::array({"qbrain-memory-v1",source,state.column_text(5),
                                     state.column_text(6),hash}).dump()),"fact_event_unavailable");
  // Validate the bounded payload even when it contains no extracted items.
  try {
    auto p=Json::parse(body,[](int depth,Json::parse_event_t,Json&){
      if(depth>8)throw Error("fact_event_unavailable");return true;});
    require(p.is_object() && p.contains("messages") && p["messages"].is_array() &&
        p.contains("expires_at") && p["expires_at"].is_number_integer() && p["expires_at"]==expiry,
        "fact_event_unavailable");
  } catch(...) {throw Error("fact_event_unavailable");}
  auto items=db.prepare("SELECT item_id FROM memory_items WHERE event_id=? ORDER BY message_index,item_id LIMIT 33");
  items.bind_text(1,id);std::vector<Evidence> result;ReadWork work;
  while(items.step()) {
    require(result.size()<32,"fact_promotion_item_limit");
    result.push_back(evidence(db,source,items.column_text(0),at,&work));
  }
  require((status=="no_matches")==result.empty(),"fact_event_unavailable");
  return result;
}
}

Json FactStore::promote_event(const std::string& event_id) {
  validate();identifier(event_id);auto& db=brain_.db();
  require(sqlite3_get_autocommit(db.handle())!=0,"fact_transaction_active");
  auto preflight=promotion_evidence(db,source_,event_id,clock_now());
  Json out={{"source_id",source_},{"event_id",event_id},{"method","local_category_promotion"},
      {"model_inference",false},{"items",Json::array()},
      {"counts",{{"total",0},{"created",0},{"attached",0},{"duplicate",0},
                  {"skipped_retired",0},{"skipped_limit",0}}}};
  if(preflight.empty())return out; // Valid no-match event never initializes facts.
  // Same preparatory semantics as create: a backup/schema may remain if the
  // subsequent fact batch rolls back. No evidence mutation occurs outside tx.
  initialize(db);Tx tx(db);require(ready(db),"fact_schema_incomplete");
  const auto at=clock_now();const auto pending=promotion_evidence(db,source_,event_id,at);
  for(const auto& e:pending) {
    const auto pred="memory."+e.reference.at("category").get<std::string>();predicate_check(pred);
    Json row={{"item_id",e.item},{"predicate",pred}};std::string outcome;
    // Any explicitly retired equal quote is a conservative automatic-write veto.
    // Manual create/attach semantics and other predicates remain unchanged.
    auto retired=db.prepare("SELECT fact_id,revision,status FROM memory_facts "
        "WHERE source_id=? AND object=? AND status IN ('retracted','superseded') "
        "ORDER BY created_at,fact_id LIMIT 1");
    retired.bind_text(1,source_);retired.bind_text(2,e.quote);
    if(retired.step()) {
      identifier(retired.column_text(0));
      row["fact_id"]=retired.column_text(0);row["revision"]=retired.column_int(1);
      row["status"]=retired.column_text(2);outcome="skipped_retired";
    } else {
      // Prefer an existing attachment to keep replay idempotent even if another
      // same-quote fact was explicitly inserted later with an earlier timestamp.
      auto prior=db.prepare("SELECT f.fact_id FROM memory_facts f WHERE f.source_id=? "
          "AND f.subject='user' AND f.predicate=? AND f.object=? AND f.status='active' "
          "ORDER BY EXISTS(SELECT 1 FROM memory_fact_evidence e WHERE e.fact_id=f.fact_id "
          "AND e.source_id=f.source_id AND e.item_id=?) DESC,f.created_at,f.fact_id LIMIT 1");
      prior.bind_text(1,source_);prior.bind_text(2,pred);prior.bind_text(3,e.quote);prior.bind_text(4,e.item);
      if(prior.step()) {
        const auto id=prior.column_text(0);identifier(id);
        auto f=promotion_target(db,source_,id,at);
        auto attached=db.prepare("SELECT 1 FROM memory_fact_evidence WHERE source_id=? AND fact_id=? AND item_id=?");
        attached.bind_text(1,source_);attached.bind_text(2,id);attached.bind_text(3,e.item);
        if(attached.step())outcome="duplicate";
        else {
          auto count=db.prepare("SELECT COUNT(*) FROM memory_fact_evidence WHERE source_id=? AND fact_id=?");
          count.bind_text(1,source_);count.bind_text(2,id);require(count.step(),"fact_not_found");
          if(count.column_int(0)>=max_evidence)outcome="skipped_limit";
          else {
            insert_evidence(db,source_,id,e,at);
            advance(db,source_,id,f["revision"].get<int64_t>(),"active",at);
            f=need(db,source_,id,at);outcome="attached";
          }
        }
        row.update(receipt(f));
      } else {
        const auto id=util::sha256_hex(Json::array({"qbrain-fact-v1",source_,"user",pred,e.quote,e.item}).dump());
        auto s=db.prepare("INSERT INTO memory_facts(fact_id,source_id,subject,predicate,object,created_at,updated_at) "
                          "VALUES(?,?,'user',?,?,?,?)");
        s.bind_text(1,id);s.bind_text(2,source_);s.bind_text(3,pred);s.bind_text(4,e.quote);
        s.bind_int(5,at);s.bind_int(6,at);s.step_done();insert_evidence(db,source_,id,e,at);
        row.update(receipt(need(db,source_,id,at)));outcome="created";
      }
    }
    row.erase("duplicate");row["outcome"]=outcome;out["items"].push_back(std::move(row));
    out["counts"][outcome]=out["counts"][outcome].get<int>()+1;
    out["counts"]["total"]=out["counts"]["total"].get<int>()+1;
  }
  require(out.dump().size()<=32768,"fact_promotion_output_limit");tx.commit();return out;
}

Json FactStore::create(const Json& p) {
  validate();
  keys(p,{"predicate","item_id","subject"});
  const auto pred = field(p,"predicate"), item = field(p,"item_id");
  predicate_check(pred); identifier(item);
  if (p.contains("subject")) require(field(p,"subject") == "user", "fact_invalid_subject");
  auto& db = brain_.db(); (void)evidence(db,source_,item,clock_now());
  initialize(db); Tx tx(db); const auto at = clock_now();
  const auto e = evidence(db,source_,item,at);
  const auto id = util::sha256_hex(Json::array({"qbrain-fact-v1",source_,"user",pred,e.quote,item}).dump());
  if (auto old = load(db,source_,id,at); !old.is_null()) {
    tx.commit(); return receipt(old,true); // Explicit retraction/supersession never resets.
  }
  auto s = db.prepare("INSERT INTO memory_facts(fact_id,source_id,subject,predicate,object,created_at,updated_at) "
                      "VALUES(?,?,'user',?,?,?,?)");
  s.bind_text(1,id); s.bind_text(2,source_); s.bind_text(3,pred); s.bind_text(4,e.quote);
  s.bind_int(5,at); s.bind_int(6,at); s.step_done();
  insert_evidence(db,source_,id,e,at);
  const auto out = receipt(need(db,source_,id,at)); tx.commit(); return out;
}

Json FactStore::attach(const Json& p) {
  validate();
  keys(p,{"fact_id","item_id"}); const auto id = field(p,"fact_id"), item = field(p,"item_id");
  identifier(id); identifier(item); auto& db = brain_.db();
  require(ready(db), "fact_not_found"); Tx tx(db); const auto at = clock_now();
  auto f = need(db,source_,id,at); require(f["status"] != "retracted", "fact_state_conflict");
  const auto e = evidence(db,source_,item,at);
  require(e.quote == f["object"].get_ref<const std::string&>(), "fact_quote_mismatch");
  { auto s = db.prepare("SELECT 1 FROM memory_fact_evidence WHERE fact_id=? AND item_id=?");
    s.bind_text(1,id); s.bind_text(2,item);
    if (s.step()) { tx.commit(); return receipt(f,true); } }
  { auto s = db.prepare("SELECT COUNT(*) FROM memory_fact_evidence WHERE fact_id=?"); s.bind_text(1,id);
    require(s.step() && s.column_int(0) < max_evidence, "fact_evidence_limit"); }
  insert_evidence(db,source_,id,e,at);
  advance(db,source_,id,f["revision"].get<int64_t>(),f["status"].get<std::string>(),at);
  auto out = receipt(need(db,source_,id,at)); tx.commit(); return out;
}

Json FactStore::retract(const Json& p) {
  validate();
  keys(p,{"fact_id","expected_revision"}); const auto id = field(p,"fact_id");
  identifier(id); const auto rev = revision(p); auto& db = brain_.db();
  require(ready(db), "fact_not_found"); Tx tx(db); const auto at = clock_now(); auto f = need(db,source_,id,at);
  require(f["revision"] == rev, "fact_revision_conflict");
  if (f["status"] == "retracted") { tx.commit(); return receipt(f,true); }
  advance(db,source_,id,rev,"retracted",at);
  auto out = receipt(need(db,source_,id,at)); tx.commit(); return out;
}

Json FactStore::supersede(const Json& p) {
  validate();
  keys(p,{"fact_id","replacement_id","expected_revision"});
  const auto id = field(p,"fact_id"), replacement = field(p,"replacement_id");
  identifier(id); identifier(replacement); const auto rev = revision(p); auto& db = brain_.db();
  require(ready(db), "fact_not_found"); Tx tx(db); const auto at = clock_now();
  auto f = need(db,source_,id,at), next = need(db,source_,replacement,at); compatible(f,next);
  require(f["revision"] == rev, "fact_revision_conflict");
  require(f["status"] == "active" && next["status"] == "active", "fact_state_conflict");
  link(db,source_,id,replacement,"superseded_by",at);
  advance(db,source_,id,rev,"superseded",at);
  auto out = receipt(need(db,source_,id,at)); out["replacement_id"] = replacement; tx.commit(); return out;
}

Json FactStore::contradict(const Json& p) {
  validate();
  keys(p,{"fact_id","other_id"}); auto a = field(p,"fact_id"), b = field(p,"other_id");
  identifier(a); identifier(b); auto& db = brain_.db(); require(ready(db), "fact_not_found");
  Tx tx(db); const auto at = clock_now(); auto first = need(db,source_,a,at), second = need(db,source_,b,at);
  compatible(first,second);
  require(first["status"] == "active" && second["status"] == "active", "fact_state_conflict");
  if (b < a) std::swap(a,b); // One symmetric assertion, never an inferred contradiction.
  const bool duplicate = has_relation(db,source_,a,b,"contradicts");
  if (!duplicate) {
    link(db,source_,a,b,"contradicts",at);
    for (const auto& f : {first,second})
      advance(db,source_,f["fact_id"].get<std::string>(),f["revision"].get<int64_t>(),"active",at);
  }
  tx.commit(); return {{"source_id",source_},{"from_id",a},{"to_id",b},
                      {"relation","contradicts"},{"duplicate",duplicate},{"resolution","unresolved"}};
}

Json FactStore::read(const std::string& id, const std::string& pred, bool history, int limit, int budget) {
  validate();
  if (!id.empty()) identifier(id);
  if (!pred.empty()) predicate_check(pred);
  require(limit >= 1 && limit <= 50 && budget >= 512 && budget <= 32768, "invalid_read_budget");
  auto& db = brain_.db();
  Json out = {{"source_id",source_},{"items",Json::array()},{"untrusted_data",true},
      {"truth_status","caller_attested_user_statement"},{"truncated",false},
      {"candidate_limit",max_candidates},{"initialized",ready(db)}};
  if (!out["initialized"].get<bool>()) return out;
  std::string sql = "SELECT fact_id FROM memory_facts WHERE source_id=?";
  if (!id.empty()) sql += " AND fact_id=?";
  if (!pred.empty()) sql += " AND predicate=?";
  if (!history) sql += " AND status='active'";
  sql += " ORDER BY created_at DESC,fact_id LIMIT 101";
  auto s = db.prepare(sql); int parameter = 1; s.bind_text(parameter++,source_);
  if (!id.empty()) s.bind_text(parameter++,id);
  if (!pred.empty()) s.bind_text(parameter++,pred);
  const auto at = clock_now(); int scanned = 0; ReadWork work;
  // Keep this SELECT alive so child evidence/edge reads share its SQLite snapshot.
  try { while (s.step()) {
    if (++scanned > max_candidates) { out["truncated"] = true; break; }
    auto f = load(db,source_,s.column_text(0),at,&work); if (f.is_null()) continue;
    f["relations"] = Json::array();
    auto edges = db.prepare("SELECT from_id,to_id,relation FROM memory_fact_relations "
        "WHERE source_id=? AND (from_id=? OR to_id=?) ORDER BY relation,from_id,to_id LIMIT 33");
    edges.bind_text(1,source_); edges.bind_text(2,s.column_text(0)); edges.bind_text(3,s.column_text(0));
    int n = 0;
    while (edges.step()) {
      require(++n <= max_relations, "fact_relation_limit");
      const bool outgoing = edges.column_text(0) == s.column_text(0);
      const auto other = edges.column_text(outgoing ? 1 : 0);
      const auto target = load(db,source_,other,at,&work);
      if (target.is_null()) continue;
      f["relations"].push_back({{"relation",edges.column_text(2)},{"direction",outgoing?"outgoing":"incoming"},
                                {"other_fact_id",other},{"other_status",target["status"]}});
    }
    if (out["items"].size() >= static_cast<std::size_t>(limit)) { out["truncated"] = true; break; }
    out["items"].push_back(f);
    if (out.dump().size() + 32 > static_cast<std::size_t>(budget)) {
      out["items"].erase(out["items"].end()-1); out["truncated"] = true;
    }
  }
  } catch (const Error& e) {
    if (std::string(e.what()) != "fact_read_work_limit") throw;
    out["truncated"] = true; out["work_limited"] = true;
  }
  return out;
}

Json FactStore::conflicts(const std::string& id, const std::string& pred, int limit, int budget) {
  validate();
  if (!id.empty()) identifier(id);
  if (!pred.empty()) predicate_check(pred);
  require(limit >= 1 && limit <= 50 && budget >= 512 && budget <= 32768, "invalid_read_budget");
  auto& db = brain_.db();
  Json out = {{"source_id",source_},{"view","conflicts"},{"items",Json::array()},
      {"untrusted_data",true},{"semantics","explicit_contradictions_only"},
      {"truncated",false},{"work_limited",false},{"candidate_limit",max_candidates},
      {"initialized",ready(db)}};
  if (!out["initialized"].get<bool>()) return out;
  // The write API stores each symmetric assertion once, in canonical ID order.
  // Filter endpoint metadata before loading quote text. No inferred edges and
  // no traversal to another source, even if the stored relation is malformed.
  std::string sql =
      "SELECT r.from_id,r.to_id,r.created_at FROM memory_fact_relations r "
      "JOIN memory_facts a ON a.fact_id=r.from_id AND a.source_id=r.source_id "
      "JOIN memory_facts b ON b.fact_id=r.to_id AND b.source_id=r.source_id "
      "WHERE r.source_id=? AND r.relation='contradicts' "
      "AND r.from_id COLLATE BINARY < r.to_id COLLATE BINARY "
      "AND a.status='active' AND b.status='active' "
      "AND a.subject='user' AND b.subject='user' AND a.predicate=b.predicate "
      "AND a.object<>b.object "
      "AND length(CAST(a.object AS BLOB)) BETWEEN 1 AND 4096 "
      "AND length(CAST(b.object AS BLOB)) BETWEEN 1 AND 4096";
  if (!id.empty()) sql += " AND (r.from_id=? OR r.to_id=?)";
  if (!pred.empty()) sql += " AND a.predicate=?";
  sql += " ORDER BY r.from_id COLLATE BINARY,r.to_id COLLATE BINARY LIMIT 101";
  auto rows = db.prepare(sql);
  int parameter = 1; rows.bind_text(parameter++,source_);
  if (!id.empty()) { rows.bind_text(parameter++,id); rows.bind_text(parameter++,id); }
  if (!pred.empty()) rows.bind_text(parameter++,pred);
  ReadWork work; const auto at = clock_now(); int scanned = 0;
  // Keep this SELECT at SQLITE_ROW while both nested loads execute. WAL writers
  // can commit, but neither endpoint switches to a newer snapshot mid-pair.
  // All caches are call-local; the next invocation observes committed changes.
  try {
    while (rows.step()) {
      if (++scanned > max_candidates) { out["truncated"] = true; break; }
      const auto from = rows.column_text(0), to = rows.column_text(1);
      identifier(from); identifier(to);
      auto first = load(db,source_,from,at,&work);
      if (first.is_null()) continue;
      auto second = load(db,source_,to,at,&work);
      if (second.is_null()) continue;
      compatible(first,second);
      if (first["status"]!="active" || second["status"]!="active") continue;
      if (out["items"].size() >= static_cast<std::size_t>(limit)) {
        out["truncated"] = true; break;
      }
      out["items"].push_back({{"from_id",from},{"to_id",to},{"relation","contradicts"},
          {"resolution","unresolved"},{"created_at",rows.column_int(2)},
          {"facts",Json::array({std::move(first),std::move(second)})}});
      if (out.dump().size() > static_cast<std::size_t>(budget)) {
        // Do not show only the convenient side or shorten its evidence. Stop
        // after the first non-fitting complete pair; ordering is a stable prefix.
        out["items"].erase(out["items"].end()-1); out["truncated"] = true; break;
      }
    }
  } catch (const Error& error) {
    if (std::string(error.what()) != "fact_read_work_limit") throw;
    out["truncated"] = true; out["work_limited"] = true;
  }
  return out;
}

Json FactStore::recall(const std::string& query, const std::string& pred, int limit, int budget,
                       const std::string& match) {
  // Validate the COMPLETE input before splitting: token boundaries must not
  // defeat sensitive-input checks or hide bytes outside the aggregate term cap.
  validate();
  require(match == "literal" || match == "all_terms" || match == "any_terms", "fact_invalid_match");
  require(!query.empty() && query.size() <= 1024 && query.find('\0') == std::string::npos &&
      util::valid_utf8(query) && query.find_first_not_of(" \t\r\n") != std::string::npos,
      "fact_invalid_query");
  require(!contains_sensitive_material(query), "sensitive_material_rejected");
  if (match == "literal") return recall_queries({query}, pred, limit, budget);
  std::vector<std::string> terms;
  for (std::size_t start = query.find_first_not_of(" \t\r\n"); start != std::string::npos;) {
    const auto end = query.find_first_of(" \t\r\n", start);
    terms.push_back(query.substr(start, end == std::string::npos ? end : end - start));
    require(terms.size() <= 8, "fact_invalid_query"); // duplicates still count
    if (end == std::string::npos) break;
    start = query.find_first_not_of(" \t\r\n", end);
  }
  return recall_queries(terms, pred, limit, budget, match);
}

Json FactStore::recall_for_hook(const std::vector<std::string>& queries, int limit, int budget) {
  return recall_queries(queries, "", limit, budget);
}

Json FactStore::recall_queries(const std::vector<std::string>& queries, const std::string& pred,
                              int limit, int budget, const std::string& match) {
  validate();
  require(match.empty() || match == "all_terms" || match == "any_terms", "fact_invalid_match");
  require(queries.size() <= 8, "fact_invalid_query");
  std::size_t query_bytes = 0;
  for (const auto& query : queries) {
    require(!query.empty() && query.size() <= 1024 && query.find('\0') == std::string::npos &&
        util::valid_utf8(query) && query.find_first_not_of(" \t\r\n") != std::string::npos,
        "fact_invalid_query");
    require(!contains_sensitive_material(query), "sensitive_material_rejected");
    query_bytes += query.size();
  }
  require(query_bytes <= 1024, "fact_invalid_query");
  if (!pred.empty()) predicate_check(pred);
  require(limit >= 1 && limit <= 50 && budget >= 512 && budget <= 32768, "invalid_read_budget");
  auto& db = brain_.db();
  ReadSnapshot snapshot(db);
  const bool has_archive = archive_ready(db);
  Json out = {{"source_id",source_},{"view","recall"},{"items",Json::array()},
      {"untrusted_data",true},{"match_mode",match.empty() ? (queries.empty()?"recent_active":(queries.size()==1?"literal_substring":"any_literal_term")) : match},
      {"conflict_scope","direct_active_assertions"},{"neighbors_recursively_expanded",false},
      {"order","created_desc_id"},{"truncated",false},{"work_limited",false},
      {"candidate_limit",max_candidates},{"initialized",ready(db)}};
  if (!out["initialized"].get<bool>()) return out;
  // Filter BEFORE the candidate cap; older matching facts must not disappear
  // merely because 100 unrelated facts were written more recently.
  std::string sql = "SELECT fact_id FROM memory_facts WHERE source_id=? "
      "AND status='active' AND subject='user' "
      "AND length(CAST(object AS BLOB)) BETWEEN 1 AND 4096";
  if (has_archive) sql += " AND NOT EXISTS(SELECT 1 FROM memory_fact_archive ar "
      "WHERE ar.fact_id=memory_facts.fact_id AND ar.source_id=memory_facts.source_id)";
  if (!queries.empty()) {
    sql += " AND (";
    for (std::size_t i=0;i<queries.size();++i)
      sql += (i ? (match == "all_terms" ? " AND " : " OR ") : "") +
          std::string("instr(lower(object),lower(?))>0");
    sql += ")";
  }
  if (!pred.empty()) sql += " AND predicate=?";
  sql += " ORDER BY created_at DESC,fact_id COLLATE BINARY LIMIT 101";
  auto rows = db.prepare(sql);
  int parameter=1; rows.bind_text(parameter++,source_);
  for (const auto& query : queries) rows.bind_text(parameter++,query);
  if (!pred.empty()) rows.bind_text(parameter,pred);
  const auto at = clock_now(); ReadWork work; int scanned = 0;
  // rows stays at SQLITE_ROW throughout nested loads, including counterclaims.
  // ReadWork is shared inside this call only. Never publish the current item
  // until all direct counter-evidence has been checked and fits the byte budget.
  try {
    while (rows.step()) {
      if (++scanned > max_candidates) { out["truncated"] = true; break; }
      const auto id = rows.column_text(0); identifier(id);
      auto anchor = load(db,source_,id,at,&work);
      if (anchor.is_null() || anchor["status"] != "active") continue;
      Json item = {{"match_fact_id",id},{"facts",Json::array({std::move(anchor)})},
          {"contradictions",Json::array()},{"conflict_state","no_live_recorded_conflict"}};
      // The query selects only this anchor, not the counterclaims: a valid
      // contradiction must remain visible even when its quote does not match.
      auto edges = db.prepare(
          "SELECT r.from_id,r.to_id,r.created_at FROM memory_fact_relations r "
          "WHERE r.source_id=? AND r.relation='contradicts' AND (r.from_id=? OR r.to_id=?) "
          "ORDER BY r.from_id COLLATE BINARY,r.to_id COLLATE BINARY LIMIT 33");
      edges.bind_text(1,source_); edges.bind_text(2,id); edges.bind_text(3,id);
      int n = 0;
      while (edges.step()) {
        require(++n <= max_relations, "fact_relation_limit");
        const auto from = edges.column_text(0), to = edges.column_text(1);
        identifier(from); identifier(to);
        if (from >= to) continue; // invalid/noncanonical stored edge, not inferred evidence
        const auto other_id = from == id ? to : from;
        // Reject oversized/cross-predicate stored values before materializing
        // them. The public write API is bounded, but a damaged DB may not be.
        auto eligible = db.prepare("SELECT 1 FROM memory_facts WHERE source_id=? AND fact_id=? "
            "AND status='active' AND subject='user' AND predicate=? "
            "AND length(CAST(object AS BLOB)) BETWEEN 1 AND 4096");
        eligible.bind_text(1,source_); eligible.bind_text(2,other_id);
        eligible.bind_text(3,item["facts"][0]["predicate"].get_ref<const std::string&>());
        if (!eligible.step()) continue;
        auto other = load(db,source_,other_id,at,&work);
        if (other.is_null() || other["status"] != "active") continue;
        const auto& first = item["facts"][0];
        if (other["subject"] != "user" || other["predicate"] != first["predicate"] ||
            other["object"] == first["object"]) continue;
        item["facts"].push_back(std::move(other));
        item["contradictions"].push_back({{"from_id",from},{"to_id",to},
            {"relation","contradicts"},{"resolution","unresolved"},{"created_at",edges.column_int(2)}});
      }
      if (!item["contradictions"].empty()) item["conflict_state"] = "recorded_conflict";
      if (out["items"].size() >= static_cast<std::size_t>(limit)) {
        out["truncated"] = true; break;
      }
      out["items"].push_back(std::move(item));
      if (out.dump().size() > static_cast<std::size_t>(budget)) {
        out["items"].erase(out["items"].end()-1); out["truncated"] = true; break;
      }
    }
  } catch (const Error& error) {
    if (std::string(error.what()) != "fact_read_work_limit") throw;
    out["truncated"] = true; out["work_limited"] = true;
  }
  return out;
}

Json FactStore::archive(const Json& p) { return set_archived(p,true); }
Json FactStore::restore(const Json& p) { return set_archived(p,false); }
Json FactStore::set_archived(const Json& p,bool desired) {
  validate(); keys(p,{"fact_id","expected_revision"});
  const auto id=field(p,"fact_id");identifier(id);const auto expected=revision(p);
  auto& db=brain_.db();
  require(sqlite3_get_autocommit(db.handle())!=0,"fact_transaction_active");
  // Reject invalid operations before any backup or lazy schema change.
  { ReadSnapshot snapshot(db);
    const auto f=need(db,source_,id,clock_now());
    require(f["status"]=="active","fact_state_conflict");
    require(f["revision"]==expected,"fact_revision_conflict");
    (void)archive_ready(db);
  }
  if (desired) initialize_archive(db);
  Tx tx(db);
  const auto at=clock_now();auto f=need(db,source_,id,at);
  require(f["status"]=="active","fact_state_conflict");
  require(f["revision"]==expected,"fact_revision_conflict");
  const bool initialized=archive_ready(db);
  const bool current=initialized && is_archived(db,source_,id);
  if (current==desired) {
    tx.commit();auto out=receipt(f,true);out["archived"]=desired;return out;
  }
  if (desired) {
    auto insert=db.prepare("INSERT INTO memory_fact_archive(fact_id,source_id,archived_at) VALUES(?,?,?)");
    insert.bind_text(1,id);insert.bind_text(2,source_);insert.bind_int(3,at);insert.step_done();
  } else {
    auto erase=db.prepare("DELETE FROM memory_fact_archive WHERE source_id=? AND fact_id=?");
    erase.bind_text(1,source_);erase.bind_text(2,id);erase.step_done();
    require(db.changes()==1,"fact_revision_conflict");
  }
  advance(db,source_,id,expected,"active",at);
  tx.commit();f["revision"]=expected+1;
  auto out=receipt(f);out["archived"]=desired;return out;
}

Json FactStore::lifecycle_batch(const Json& p, bool apply) {
  validate(); keys(p,{"operation","items"});
  const auto operation=field(p,"operation");
  require(operation=="archive" || operation=="restore","fact_batch_invalid_operation");
  require(p.contains("items") && p["items"].is_array() && !p["items"].empty() &&
          p["items"].size()<=32,"fact_batch_invalid_size");
  require(p.dump().size()<=8192,"fact_batch_payload_limit");
  const bool desired=operation=="archive";
  struct Selection { std::string id; int64_t expected; };
  std::vector<Selection> selection; std::set<std::string> unique;
  for(const auto& item:p["items"]) {
    keys(item,{"fact_id","expected_revision"});
    auto id=field(item,"fact_id");identifier(id);
    require(unique.insert(id).second,"fact_batch_duplicate_id");
    selection.push_back({std::move(id),revision(item)});
  }
  auto& db=brain_.db();
  if(apply)require(sqlite3_get_autocommit(db.handle())!=0,"fact_transaction_active");
  // Receipts contain only metadata, not copied user quotes. A preview's after
  // values are predictions, not a reservation or proof that anything was applied.
  auto inspect=[&](int64_t at) {
    require(ready(db),"fact_not_found");const bool initialized=archive_ready(db);
    Json out={{"view","lifecycle_batch"},{"source_id",source_},{"operation",operation},
        {"result","PREVIEW"},{"applied",false},{"atomic",true},
        {"archive_initialized",initialized},{"schema_preparation_required",desired && !initialized},
        {"counts",{{"total",selection.size()},{"change",0},{"unchanged",0}}},
        {"items",Json::array()},{"untrusted_data",true}};
    ReadWork work;
    for(const auto& item:selection) {
      // Bound damaged stored values before load() materializes the quote.
      auto bound=db.prepare("SELECT 1 FROM memory_facts WHERE source_id=? AND fact_id=? "
          "AND subject='user' AND length(CAST(object AS BLOB)) BETWEEN 1 AND 4096");
      bound.bind_text(1,source_);bound.bind_text(2,item.id);
      require(bound.step(),"fact_not_found");
      auto f=load(db,source_,item.id,at,&work);
      require(!f.is_null(),"fact_not_found");
      require(f["status"]=="active","fact_state_conflict");
      require(f["revision"]==item.expected,"fact_revision_conflict");
      const bool before=initialized && is_archived(db,source_,item.id);
      const bool change=before!=desired;
      out["items"].push_back({{"fact_id",item.id},{"revision_before",item.expected},
          {"revision_after",item.expected+(change?1:0)},
          {"archived_before",before},{"archived_after",desired},{"change",change}});
      auto& count=out["counts"][change?"change":"unchanged"];count=count.get<int>()+1;
    }
    require(out.dump().size()<=32768,"fact_batch_output_limit");return out;
  };
  Json preflight;
  { ReadSnapshot snapshot(db);preflight=inspect(clock_now()); }
  if(!apply)return preflight;
  // Lazy schema preparation is separate, as in the single-item API. On a later
  // conflict an empty module/backup may remain; policy/revisions never half-apply.
  if(preflight["schema_preparation_required"].get<bool>())initialize_archive(db);
  Tx tx(db);const auto at=clock_now();auto out=inspect(at); // fresh work/cache + snapshot
  for(const auto& item:out["items"]) {
    if(!item["change"].get<bool>())continue;
    const auto& id=item["fact_id"].get_ref<const std::string&>();
    if(desired) {
      auto insert=db.prepare("INSERT INTO memory_fact_archive(fact_id,source_id,archived_at) VALUES(?,?,?)");
      insert.bind_text(1,id);insert.bind_text(2,source_);insert.bind_int(3,at);insert.step_done();
    } else {
      auto erase=db.prepare("DELETE FROM memory_fact_archive WHERE source_id=? AND fact_id=?");
      erase.bind_text(1,source_);erase.bind_text(2,id);erase.step_done();
      require(db.changes()==1,"fact_revision_conflict");
    }
    advance(db,source_,id,item["revision_before"].get<int64_t>(),"active",at);
  }
  out["result"]="APPLIED";out["applied"]=true;
  require(out.dump().size()<=32768,"fact_batch_output_limit");
  tx.commit();return out;
}

Json FactStore::lifecycle(const std::string& id,const std::string& pred,
                          int days,int limit,int budget) {
  validate();if(!id.empty())identifier(id);if(!pred.empty())predicate_check(pred);
  require(days>=1 && days<=36500,"fact_invalid_stale_days");
  require(limit>=1 && limit<=50 && budget>=512 && budget<=32768,"invalid_read_budget");
  auto& db=brain_.db();ReadSnapshot snapshot(db);
  const bool module=archive_ready(db);const auto at=clock_now();
  Json out={{"view","lifecycle"},{"source_id",source_},{"initialized",ready(db)},
      {"archive_initialized",module},{"age_basis","newest_valid_support_created_at"},
      {"stale_after_days",days},{"evaluated_at",at},{"age_is_advisory",true},
      {"usage_measured",false},{"truncated",false},{"work_limited",false},
      {"items",Json::array()},{"untrusted_data",true}};
  if(!out["initialized"].get<bool>())return out;
  std::string sql="SELECT fact_id FROM memory_facts WHERE source_id=? AND status='active' "
      "AND subject='user' AND length(CAST(object AS BLOB)) BETWEEN 1 AND 4096";
  if(!id.empty())sql+=" AND fact_id=?";
  if(!pred.empty())sql+=" AND predicate=?";
  sql+=" ORDER BY created_at DESC,fact_id COLLATE BINARY LIMIT 101";
  auto rows=db.prepare(sql);int i=1;rows.bind_text(i++,source_);
  if(!id.empty())rows.bind_text(i++,id);if(!pred.empty())rows.bind_text(i++,pred);
  ReadWork work;int scanned=0;
  try {
    while(rows.step()) {
      if(++scanned>max_candidates){out["truncated"]=true;break;}
      const auto fact_id=rows.column_text(0);identifier(fact_id);
      auto f=load(db,source_,fact_id,at,&work);if(f.is_null())continue;
      f["lifecycle"]=support_age(db,f,at,days);
      f["lifecycle"]["archived"]=module && is_archived(db,source_,fact_id);
      if(out["items"].size()>=static_cast<std::size_t>(limit)) {out["truncated"]=true;break;}
      out["items"].push_back(std::move(f));
      if(out.dump().size()>static_cast<std::size_t>(budget)) {
        out["items"].erase(out["items"].end()-1);out["truncated"]=true;break;
      }
    }
  } catch(const Error& e) {
    if(std::string(e.what())!="fact_read_work_limit")throw;
    out["truncated"]=true;out["work_limited"]=true;
  }
  return out;
}

Json FactStore::lifecycle_candidates(const std::string& operation,const std::string& pred,
                                      int days,const std::string& after,int limit,int budget) {
  validate();
  require(operation=="archive" || operation=="restore","fact_batch_invalid_operation");
  if(!pred.empty())predicate_check(pred);if(!after.empty())identifier(after);
  require(days>=1 && days<=36500,"fact_invalid_stale_days");
  require(limit>=1 && limit<=32 && budget>=512 && budget<=32768,"invalid_read_budget");
  auto& db=brain_.db();ReadSnapshot snapshot(db);
  const bool initialized=ready(db),module=archive_ready(db);const auto at=clock_now();
  Json out={{"view","lifecycle_candidates"},{"source_id",source_},{"operation",operation},
      {"predicate",pred},{"stale_after_days",days},{"initialized",initialized},
      {"archive_initialized",module},{"age_is_advisory",true},{"evaluated_at",at},
      {"items",Json::array()},{"batch_payload",nullptr},{"scanned",0},
      {"next_after_id",nullptr},{"has_more",false},{"stop_reason","end"},
      {"progressed",false},{"untrusted_data",true}};
  // Reserve the largest continuation envelope before accepting a whole item.
  // This conservative allowance is metadata, not truncation of user evidence.
  auto fits=[&] {
    auto bound=out;bound["next_after_id"]=std::string(64,'f');
    bound["has_more"]=false;bound["stop_reason"]="evidence_budget";
    bound["scanned"]=100;bound["progressed"]=false;
    return bound.dump().size()<=static_cast<std::size_t>(budget);
  };
  require(fits(),"invalid_read_budget");
  if(!initialized || (operation=="restore" && !module))return out;
  std::string sql="SELECT f.fact_id FROM memory_facts f WHERE f.source_id=? "
      "AND f.status='active' AND f.subject='user' "
      "AND typeof(f.revision)='integer' AND f.revision>=1 AND f.revision<2147483647 "
      "AND length(CAST(f.object AS BLOB)) BETWEEN 1 AND 4096";
  if(!pred.empty())sql+=" AND f.predicate=?";
  if(!after.empty())sql+=" AND f.fact_id COLLATE BINARY>?";
  if(module)sql+=std::string(" AND ")+(operation=="archive"?"NOT ":"")+
      "EXISTS(SELECT 1 FROM memory_fact_archive a WHERE a.source_id=f.source_id AND a.fact_id=f.fact_id)";
  sql+=" ORDER BY f.fact_id COLLATE BINARY LIMIT 101";
  auto rows=db.prepare(sql);int parameter=1;rows.bind_text(parameter++,source_);
  if(!pred.empty())rows.bind_text(parameter++,pred);if(!after.empty())rows.bind_text(parameter++,after);
  ReadWork work;std::string consumed=after;int scanned=0;
  auto stop=[&](const char* reason) {
    out["has_more"]=true;out["next_after_id"]=consumed;out["stop_reason"]=reason;
  };
  try {
    while(rows.step()) {
      if(scanned>=max_candidates){stop("scan_limit");break;}
      if(out["items"].size()>=static_cast<std::size_t>(limit)){stop("result_limit");break;}
      const auto id=rows.column_text(0);identifier(id);
      auto fact=load(db,source_,id,at,&work);
      if(!fact.is_null()) {
        predicate_check(fact["predicate"].get_ref<const std::string&>());
        const bool archived=module && is_archived(db,source_,id);
        auto age=support_age(db,fact,at,days);
        if((operation=="archive" && !archived && age["age_state"]=="stale") ||
           (operation=="restore" && archived)) {
          Json item={{"fact_id",id},{"expected_revision",fact["revision"]},
              {"predicate",fact["predicate"]},{"archived",archived},{"age",std::move(age)}};
          const bool first=out["items"].empty();
          if(first)out["batch_payload"]={{"operation",operation},{"items",Json::array()}};
          out["items"].push_back(std::move(item));
          out["batch_payload"]["items"].push_back({{"fact_id",id},{"expected_revision",fact["revision"]}});
          if(!fits()) {
            out["items"].erase(out["items"].end()-1);
            out["batch_payload"]["items"].erase(out["batch_payload"]["items"].end()-1);
            if(first)out["batch_payload"]=nullptr;
            stop("output_budget");break; // Current row is not consumed.
          }
        }
      }
      ++scanned;consumed=id;
    }
  } catch(const Error& e) {
    if(std::string(e.what())!="fact_read_work_limit")throw;
    stop("evidence_budget"); // Retry the unfinished row with a fresh per-call work budget.
  }
  out["scanned"]=scanned;out["progressed"]=consumed!=after;
  require(out["batch_payload"].is_null() || out["batch_payload"].dump().size()<=8192,"fact_batch_payload_limit");
  require(out.dump().size()<=static_cast<std::size_t>(budget),"fact_batch_output_limit");
  return out;
}
}  // namespace qbrain::memory
