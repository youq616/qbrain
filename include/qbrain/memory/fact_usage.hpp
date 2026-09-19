#pragma once
// Route-local SQLite use receipts. Reuses FactStore's public complete-evidence
// validator; no use side effects are inserted into the original fact/Hook paths.
#include "qbrain/memory/fact_store.hpp"
#include "qbrain/util/hash.hpp"
#include <algorithm>
#include <chrono>
#include <random>

namespace qbrain::memory {
namespace usage_detail {
using DB=storage::Database;
inline void require(bool condition,const char* code){if(!condition)throw Error(code);}
inline int64_t clock_now(){return std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count();}
inline void identifier(const std::string& id){
  require(id.size()==64 && std::all_of(id.begin(),id.end(),[](unsigned char c){
    return (c>='0' && c<='9') || (c>='a' && c<='f');}),"fact_invalid_id");
}
inline void keys(const Json& p,std::initializer_list<const char*> allowed){
  require(p.is_object(),"fact_invalid_payload");
  for(auto it=p.begin();it!=p.end();++it){bool found=false;
    for(auto key:allowed)if(it.key()==key)found=true;
    require(found,"fact_unexpected_argument");}
}
inline std::string field(const Json& p,const char* name){
  require(p.contains(name) && p[name].is_string(),"fact_invalid_field");return p[name].get<std::string>();
}
inline int64_t revision(const Json& p){
  require(p.contains("expected_revision") && p["expected_revision"].is_number_integer() &&
    p["expected_revision"]>=1 && p["expected_revision"]<INT32_MAX,"fact_invalid_revision");
  return p["expected_revision"].get<int64_t>();
}
inline bool exists(DB& db,const char* name,const char* type="table"){
  auto s=db.prepare("SELECT 1 FROM sqlite_master WHERE type=? AND name=?");
  s.bind_text(1,type);s.bind_text(2,name);return s.step();
}
struct ReadSnapshot {
  DB::Statement pin;
  explicit ReadSnapshot(DB& db):pin(db.prepare("SELECT COUNT(*) FROM sqlite_master")){
    require(pin.step(),"fact_snapshot_unavailable");}
};
struct Tx {
  DB& db;bool done=false;int old_timeout=0;
  explicit Tx(DB& d):db(d){
    {auto s=db.prepare("PRAGMA busy_timeout");if(s.step())old_timeout=int(s.column_int(0));}
    db.exec("PRAGMA busy_timeout=2500");
    try{db.exec("BEGIN IMMEDIATE");}catch(...){db.exec("PRAGMA busy_timeout="+std::to_string(old_timeout));throw;}
  }
  void commit(){db.exec("COMMIT");done=true;}
  ~Tx(){if(!done){try{db.exec("ROLLBACK");}catch(...){}}
    try{db.exec("PRAGMA busy_timeout="+std::to_string(old_timeout));}catch(...){}}
};
inline bool archive_ready(DB& db){
  if(!exists(db,"memory_fact_lifecycle_module")){
    require(!exists(db,"memory_fact_archive"),"fact_lifecycle_schema_conflict");return false;}
  auto s=db.prepare("SELECT version FROM memory_fact_lifecycle_module");
  require(s.step() && s.column_int(0)==1 && !s.step(),"fact_lifecycle_version_unsupported");
  require(exists(db,"memory_fact_archive"),"fact_lifecycle_schema_incomplete");return true;
}
inline bool is_archived(DB& db,const std::string& source,const std::string& id){
  auto s=db.prepare("SELECT archived_at,typeof(archived_at) FROM memory_fact_archive WHERE source_id=? AND fact_id=?");
  s.bind_text(1,source);s.bind_text(2,id);if(!s.step())return false;
  require(s.column_text(1)=="integer" && !s.column_is_null(0) && s.column_int(0)>=0,"fact_lifecycle_invalid_metadata");return true;
}
// Optional explicit-use module. No quote, session, provider or client data is
// stored here. The caller's report is never evidence of external consumption.
constexpr int max_use_receipts = 4096;
inline bool usage_ready(DB& db) {
  if (!exists(db,"memory_fact_usage_module")) {
    require(!exists(db,"memory_fact_usage"),"fact_usage_schema_conflict");
    return false;
  }
  auto v=db.prepare("SELECT version,typeof(version) FROM memory_fact_usage_module");
  require(v.step() && v.column_text(1)=="integer" && v.column_int(0)==1 && !v.step(),
          "fact_usage_version_unsupported");
  require(exists(db,"memory_fact_usage") && exists(db,"idx_memory_fact_usage_fact","index"),
          "fact_usage_schema_incomplete");
  auto cols=db.prepare("SELECT usage_id,source_id,fact_id,fact_revision,reported_at,withdrawn_at FROM memory_fact_usage LIMIT 0");
  cols.step();
  return true;
}
inline void usage_foreign_keys(DB& db) {
  auto s=db.prepare("PRAGMA foreign_keys");
  require(s.step() && s.column_int(0)==1,"fact_usage_foreign_keys_required");
}
inline void initialize_usage(DB& db) {
  {
    ReadSnapshot snapshot(db);
    if (usage_ready(db)) return;
    require(exists(db,"memory_fact_module"),"fact_not_found");
    const auto path=db.backend_file_path();
    if (!path.empty()) {
      std::random_device rng;std::string entropy;
      for(int i=0;i<8;++i)entropy+=std::to_string(rng())+":";
      require(db.backup_to(path+".pre-usage-v1-"+util::sha256_hex(entropy)+".bak"),"fact_usage_backup_failed");
    }
  }
  Tx tx(db);
  usage_foreign_keys(db);
  if(!usage_ready(db))db.exec(R"SQL(
CREATE TABLE memory_fact_usage_module(version INTEGER PRIMARY KEY CHECK(version=1));
INSERT INTO memory_fact_usage_module VALUES(1);
CREATE TABLE memory_fact_usage(
 source_id TEXT NOT NULL, usage_id TEXT NOT NULL,
 fact_id TEXT NOT NULL, fact_revision INTEGER NOT NULL CHECK(fact_revision>=1 AND fact_revision<=2147483647),
 reported_at INTEGER NOT NULL CHECK(reported_at>=0),
 withdrawn_at INTEGER CHECK(withdrawn_at IS NULL OR withdrawn_at>=reported_at),
 PRIMARY KEY(source_id,usage_id),
 FOREIGN KEY(fact_id,source_id) REFERENCES memory_facts(fact_id,source_id) ON DELETE CASCADE);
CREATE INDEX idx_memory_fact_usage_fact ON memory_fact_usage(source_id,fact_id,usage_id);
)SQL");
  tx.commit();
}
inline Json usage_flags() {
  return {{"origin","caller_reported"},{"host_consumption_verified",false},
          {"fact_truth_verified",false},{"provider_calls",0}};
}
inline Json usable_fact(Brain& brain,const std::string& source,const std::string& id) {
  auto result=FactStore(brain,source).read(id,"",true,1,32768);
  require(!result["truncated"].get<bool>(),"fact_usage_evidence_limit");
  require(result["items"].size()==1,"fact_not_found");
  auto f=result["items"][0];
  require(f["status"]=="active","fact_state_conflict");
  return f;
}
inline void check_reportable(Brain& brain,const std::string& source,const std::string& id,int64_t rev) {
  auto f=usable_fact(brain,source,id);
  require(f["revision"]==rev,"fact_revision_conflict");
  auto& db=brain.db();
  require(!archive_ready(db) || !is_archived(db,source,id),"fact_usage_archived");
}
struct UsageRow { std::string fact; int64_t rev,at,withdrawn;bool revoked; };
inline UsageRow usage_row(DB::Statement& row) {
  UsageRow r{row.column_text(0),row.column_int(1),row.column_int(2),row.column_int(3),!row.column_is_null(3)};
  identifier(r.fact);
  require(row.column_text(4)=="integer" && r.rev>=1 && r.rev<=INT32_MAX &&
      row.column_text(5)=="integer" && r.at>=0 &&
      ((!r.revoked && row.column_text(6)=="null") ||
       (r.revoked && row.column_text(6)=="integer" && r.withdrawn>=r.at)),"fact_usage_invalid_metadata");
  return r;
}
inline constexpr const char* usage_columns="fact_id,fact_revision,reported_at,withdrawn_at,typeof(fact_revision),typeof(reported_at),typeof(withdrawn_at)";

} // namespace usage_detail
class FactUsageStore {
 public:
  FactUsageStore(Brain& brain,std::string source):brain_(brain),source_(std::move(source)){validate();}
  Json report_use(const Json& payload);
  Json revoke_use(const Json& payload);
  Json usage(const std::string& fact_id);
 private:
  void validate() const { FactStore checked(brain_,source_); }
  Brain& brain_;
  std::string source_;
};
inline Json FactUsageStore::report_use(const Json& p) {
  using namespace usage_detail;validate();keys(p,{"fact_id","usage_id","expected_revision"});
  const auto id=field(p,"fact_id"),uid=field(p,"usage_id");
  identifier(id);identifier(uid);const auto rev=revision(p);auto& db=brain_.db();
  // Reject invalid claims without initializing the optional module. Repeat all
  // fact checks under the writer lock after any separate schema preparation.
  { ReadSnapshot snapshot(db);usage_foreign_keys(db);check_reportable(brain_,source_,id,rev); }
  initialize_usage(db);
  Tx tx(db);usage_foreign_keys(db);check_reportable(brain_,source_,id,rev);
  bool duplicate=false;int64_t at=clock_now();
  {
    auto row=db.prepare(std::string("SELECT ")+usage_columns+" FROM memory_fact_usage WHERE source_id=? AND usage_id=?");
    row.bind_text(1,source_);row.bind_text(2,uid);
    if(row.step()) {
      const auto old=usage_row(row);
      require(old.fact==id && old.rev==rev,"fact_usage_id_conflict");
      require(!old.revoked,"fact_usage_withdrawn");
      duplicate=true;at=old.at;
    }
  }
  if(!duplicate) {
    auto count=db.prepare("SELECT COUNT(*) FROM memory_fact_usage WHERE source_id=? AND fact_id=?");
    count.bind_text(1,source_);count.bind_text(2,id);
    require(count.step() && count.column_int(0)<max_use_receipts,"fact_usage_capacity");
    auto ins=db.prepare("INSERT INTO memory_fact_usage(source_id,usage_id,fact_id,fact_revision,reported_at) VALUES(?,?,?,?,?)");
    ins.bind_text(1,source_);ins.bind_text(2,uid);ins.bind_text(3,id);ins.bind_int(4,rev);ins.bind_int(5,at);ins.step_done();
  }
  auto out=usage_flags();out.update({{"status","reported"},{"source_id",source_},{"fact_id",id},
      {"usage_id",uid},{"fact_revision",rev},{"reported_at",at},{"duplicate",duplicate}});
  tx.commit();return out;
}
inline Json FactUsageStore::revoke_use(const Json& p) {
  using namespace usage_detail;validate();keys(p,{"fact_id","usage_id"});
  const auto id=field(p,"fact_id"),uid=field(p,"usage_id");identifier(id);identifier(uid);
  auto& db=brain_.db();
  { ReadSnapshot snapshot(db);require(usage_ready(db),"fact_usage_not_found"); }
  Tx tx(db);usage_foreign_keys(db);require(usage_ready(db),"fact_usage_not_found");
  UsageRow found;
  {
    auto row=db.prepare(std::string("SELECT ")+usage_columns+" FROM memory_fact_usage WHERE source_id=? AND usage_id=? AND fact_id=?");
    row.bind_text(1,source_);row.bind_text(2,uid);row.bind_text(3,id);
    require(row.step(),"fact_usage_not_found");found=usage_row(row);
  }
  const auto at=found.revoked?found.withdrawn:std::max(clock_now(),found.at);
  if(!found.revoked) {
    auto update=db.prepare("UPDATE memory_fact_usage SET withdrawn_at=? WHERE source_id=? AND usage_id=? AND fact_id=? AND withdrawn_at IS NULL");
    update.bind_int(1,at);update.bind_text(2,source_);update.bind_text(3,uid);update.bind_text(4,id);update.step_done();
    require(db.changes()==1,"fact_usage_write_conflict");
  }
  auto out=usage_flags();out.update({{"status","withdrawn"},{"source_id",source_},{"fact_id",id},
      {"usage_id",uid},{"fact_revision",found.rev},{"withdrawn_at",at},{"duplicate",found.revoked}});
  tx.commit();return out;
}
inline Json FactUsageStore::usage(const std::string& id) {
  using namespace usage_detail;validate();identifier(id);auto& db=brain_.db();ReadSnapshot snapshot(db);
  auto fact=usable_fact(brain_,source_,id);const auto rev=fact["revision"].get<int64_t>();
  const bool initialized=usage_ready(db),archived=archive_ready(db) && is_archived(db,source_,id);
  int current=0,historical=0,withdrawn=0,total=0;Json latest=nullptr;
  if(initialized) {
    auto rows=db.prepare(std::string("SELECT ")+usage_columns+",usage_id FROM memory_fact_usage WHERE source_id=? AND fact_id=? ORDER BY usage_id LIMIT 4097");
    rows.bind_text(1,source_);rows.bind_text(2,id);
    while(rows.step()) {
      require(++total<=max_use_receipts,"fact_usage_invalid_metadata");
      const auto row=usage_row(rows);identifier(rows.column_text(7));
      require(row.rev<=rev,"fact_usage_invalid_metadata");
      if(row.revoked)++withdrawn;
      else if(row.rev==rev){++current;if(latest.is_null() || row.at>latest.get<int64_t>())latest=row.at;}
      else ++historical;
    }
  }
  auto out=usage_flags();out.update({{"view","usage"},{"source_id",source_},{"fact_id",id},
      {"fact_revision",rev},{"initialized",initialized},{"archived",archived},
      {"current_revision_use_count",current},{"other_revision_use_count",historical},
      {"withdrawn_count",withdrawn},{"stored_receipts",total},{"receipt_capacity",max_use_receipts},
      {"last_current_revision_use_at",latest}});
  return out;
}

} // namespace qbrain::memory
