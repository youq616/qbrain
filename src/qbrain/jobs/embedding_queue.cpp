#include "qbrain/jobs/embedding_queue.hpp"
#include "qbrain/jobs/detail/busy_wait.hpp"
#include "qbrain/ai/embed.hpp"
#include "qbrain/ai/embedding_policy.hpp"
#include "qbrain/ai/http_client.hpp"
#include "qbrain/search/vector.hpp"
#include "qbrain/util/time_util.hpp"
#include "qbrain/util/utf8_display.hpp"
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <limits>
#include <optional>
#include <random>
#include <stdexcept>
#include <nlohmann/json.hpp>

namespace qbrain::jobs {
namespace {
using J = nlohmann::json;
using Database = storage::Database;
constexpr int kLeaseSeconds = 180; // renewed for each bounded, 60-second HTTP call
constexpr std::size_t kResponseValueBudget =
    (ai::HTTP_DEFAULT_RESPONSE_BYTES - 65536) / 32;
struct Stop { const char* outcome; const char* message; bool cancelled = false; };
struct LostClaim {};

// Short transactions only; no provider call occurs while an instance is active.
class Transaction {
  detail::ScopedQueueBusyWait busy_;
  Database& db_;
  bool active_ = true;
 public:
  explicit Transaction(Database& db) : busy_(db), db_(db) {
    db_.exec(db_.backend_kind() == storage::BackendKind::sqlite ? "BEGIN IMMEDIATE" : "BEGIN");
    try {
      // Unlike SQLite, PG BEGIN alone does not exclude competing writers. The
      // short table locks also fence rechunk inserts/deletes not updating pages.
      // This conservative PG path is not a PostgreSQL performance/parity claim.
      if (db_.backend_kind() == storage::BackendKind::postgres)
        db_.exec("LOCK TABLE pages, content_chunks IN SHARE ROW EXCLUSIVE MODE");
    } catch (...) { db_.exec("ROLLBACK"); throw; }
  }
  ~Transaction() {
    if (active_) { try { db_.exec("ROLLBACK"); } catch (...) {} }
  }
  void commit() { db_.exec("COMMIT"); active_ = false; }
};

struct PageSnapshot {
  std::string source, slug, hash, updated;
  int64_t count = 0, max_id = 0;
  bool operator==(const PageSnapshot&) const = default;
};
PageSnapshot page_snapshot(Database& db, int64_t page_id) {
  auto st = db.prepare(
      "SELECT p.source_id,p.slug,COALESCE(p.content_hash,''),p.updated_at,"
      "(SELECT COUNT(*) FROM content_chunks WHERE page_id=p.id),"
      "(SELECT COALESCE(MAX(id),0) FROM content_chunks WHERE page_id=p.id) "
      "FROM pages p WHERE p.id=? AND p.deleted_at IS NULL");
  st.bind_int(1, page_id);
  if (!st.step()) throw Stop{"deleted", "embedding target is deleted or missing", true};
  return {st.column_text(0),st.column_text(1),st.column_text(2),st.column_text(3),
          st.column_int(4),st.column_int(5)};
}
void check_snapshot(Database& db, int64_t page_id, const PageSnapshot& expected) {
  if (!(page_snapshot(db, page_id) == expected))
    throw Stop{"stale", "embedding target changed; retry explicitly"};
}
void fence(Database& db, const Job& job) {
  auto st = db.prepare("UPDATE jobs SET lock_until=?,updated_at=? WHERE id=? "
      "AND type='embed' AND status='active' AND lock_token=? AND attempts=? AND lock_until>?");
  const auto now = util::utc_now();
  st.bind_text(1, util::utc_now_offset(kLeaseSeconds)); st.bind_text(2, now);
  st.bind_int(3, job.id); st.bind_text(4, job.lock_token);
  st.bind_int(5, job.attempts); st.bind_text(6, now); st.step_done();
  if (db.changes() != 1) throw LostClaim{};
}
void record(Database& db, const Job& job, int64_t chunks, int64_t batches,
            const char* status, const char* outcome, const char* error = nullptr) {
  J progress = {{"chunks",chunks},{"batches",batches},{"outcome",outcome}};
  if (error) progress["error"] = error;
  const bool active = std::string_view(status) == "active";
  std::string sql = "UPDATE jobs SET status=?,result_json=?,error_text=?,updated_at=?";
  if (!active) sql += ",lock_token=NULL,lock_until=NULL";
  sql += " WHERE id=? AND status='active' AND lock_token=? AND attempts=? AND lock_until>?";
  auto st = db.prepare(sql); st.bind_text(1,status); st.bind_text(2,progress.dump());
  if (error) st.bind_text(3,error); else st.bind_null(3);
  const auto now = util::utc_now(); st.bind_text(4,now); st.bind_int(5,job.id);
  st.bind_text(6,job.lock_token); st.bind_int(7,job.attempts); st.bind_text(8,now);
  st.step_done(); if (db.changes()!=1) throw LostClaim{};
}

std::size_t json_text_bytes(std::string_view text) {
  if (!util::valid_utf8(text)) throw Stop{"invalid_input", "embedding input is not valid UTF-8"};
  std::size_t count = 2; // quotes, ensure_ascii=false as in embed_texts
  for (unsigned char c : text) {
    const std::size_t bytes = c=='"' || c=='\\' || c=='\b' || c=='\f' ||
        c=='\n' || c=='\r' || c=='\t' ? 2 : c<0x20 ? 6 : 1;
    if (bytes > ai::HTTP_MAX_REQUEST_BYTES-count)
      throw Stop{"invalid_input", "embedding input exceeds request byte limit"};
    count += bytes;
  }
  return count;
}
struct Pending { int64_t id, index; std::string text; };
std::vector<Pending> next_batch(Database& db, int64_t page_id, int64_t after,
                                const Config& cfg) {
  const auto width = ai::embedding_mock_enabled() ? std::size_t(3) :
      cfg.embedding_dimensions > 0 ? static_cast<std::size_t>(cfg.embedding_dimensions) : ai::EMBED_MAX_DIMENSIONS;
  const auto count = std::min(ai::EMBED_MAX_BATCH,
      std::min(ai::EMBED_MAX_VALUES, kResponseValueBudget)/width);
  J envelope = {{"model",cfg.embedding_model},{"input",J::array()},{"encoding_format","float"}};
  if (cfg.embedding_dimensions>0) envelope["dimensions"] = cfg.embedding_dimensions;
  std::size_t bytes = envelope.dump().size();
  const char* length = db.backend_kind()==storage::BackendKind::sqlite ?
      "length(CAST(text AS BLOB))" : "octet_length(text)";
  std::string sql = "SELECT id,chunk_index,"+std::string(length)+",text FROM content_chunks "
      "WHERE page_id=? AND id>? AND (embedding IS NULL OR length(embedding)=0) ORDER BY id LIMIT ?";
  auto st=db.prepare(sql); st.bind_int(1,page_id);st.bind_int(2,after);
  st.bind_int(3,static_cast<int64_t>(count));
  std::vector<Pending> out;
  while (st.step()) {
    if (st.column_int(2)<0 || st.column_int(2)>static_cast<int64_t>(ai::HTTP_MAX_REQUEST_BYTES))
      throw Stop{"invalid_input","embedding input exceeds request byte limit"};
    Pending p{st.column_int(0),st.column_int(1),st.column_text(3)};
    const auto size=json_text_bytes(p.text)+(out.empty()?0:1);
    if (size > ai::HTTP_MAX_REQUEST_BYTES-bytes) {
      if (out.empty()) throw Stop{"invalid_input","embedding input exceeds request byte limit"};
      break; // leave this row for the next batch, never truncate or skip it
    }
    bytes+=size; out.push_back(std::move(p));
  }
  return out;
}
void validate_result(const ai::EmbedResult& r, std::size_t count, const Config& cfg) {
  if (!r.ok) throw Stop{"provider_error","embedding provider request failed"};
  if (r.vectors.size()!=count || r.model!=ai::active_embedding_model(cfg))
    throw Stop{"provider_error","invalid embedding batch result"};
  std::size_t total=0, width=0;
  for (const auto& v:r.vectors) {
    if (v.empty() || v.size()>ai::EMBED_MAX_DIMENSIONS || v.size()>ai::EMBED_MAX_VALUES-total ||
        (width && width!=v.size()) ||
        (!ai::embedding_mock_enabled() && cfg.embedding_dimensions>0 &&
         v.size()!=static_cast<std::size_t>(cfg.embedding_dimensions)) ||
        !std::all_of(v.begin(),v.end(),[](float f){return std::isfinite(f);}) ||
        std::none_of(v.begin(),v.end(),[](float f){return f!=0;}))
      throw Stop{"provider_error","invalid embedding batch result"};
    total+=v.size();width=v.size();
  }
}
void apply_batch(Database& db, int64_t page_id, const std::vector<Pending>& batch,
                 const ai::EmbedResult& r) {
  auto st=db.prepare("UPDATE content_chunks SET embedding=?,dim=?,model=? "
      "WHERE id=? AND page_id=? AND chunk_index=? AND text=? "
      "AND (embedding IS NULL OR length(embedding)=0)");
  for (std::size_t i=0;i<batch.size();++i) {
    const auto blob=search::pack_f32(r.vectors[i]);
    st.reset();st.clear_bindings();st.bind_blob(1,blob.data(),static_cast<int>(blob.size()));
    st.bind_int(2,static_cast<int64_t>(r.vectors[i].size()));st.bind_text(3,r.model);
    st.bind_int(4,batch[i].id);st.bind_int(5,page_id);st.bind_int(6,batch[i].index);
    st.bind_text(7,batch[i].text);st.step_done();
    if (db.changes()!=1) throw Stop{"stale","embedding chunk changed; retry explicitly"};
  }
}
int bounded_count(int64_t count) {return static_cast<int>(std::min<int64_t>(count,std::numeric_limits<int>::max()));}
} // namespace

std::string new_embedding_claim_token() {
  static std::atomic<std::uint64_t> sequence{0};
  std::random_device random;
  return "embed-"+std::to_string(random())+"-"+std::to_string(random())+"-"+
      std::to_string(std::chrono::steady_clock::now().time_since_epoch().count())+"-"+
      std::to_string(sequence.fetch_add(1));
}

int execute_embedding_job(Brain& brain, const Job& job) {
  auto& db=brain.db(); int64_t persisted=0,batches=0,page_id=0,cursor=0;
  std::optional<PageSnapshot> expected;
  const Config cfg=brain.config(); // one request/model configuration for this attempt
  auto fail=[&](const char* status,const char* outcome,const char* message) {
    try {
      Transaction tx(db); fence(db,job);
      record(db,job,persisted,batches,status,outcome,message);tx.commit();
    } catch (const LostClaim&) { /* cancellation/reassignment belongs to the new owner */ }
  };
  try {
    auto payload=J::parse(job.payload_json);
    if (!payload.is_object() || !payload.contains("page_id") ||
        !payload["page_id"].is_number_integer() || payload["page_id"]<=0 ||
        payload["page_id"]>std::numeric_limits<int64_t>::max())
      throw Stop{"invalid_input","invalid embedding job payload"};
    page_id=payload["page_id"].get<int64_t>();
    if (!ai::valid_embedding_model(cfg.embedding_model) || cfg.embedding_dimensions<0 ||
        static_cast<std::size_t>(cfg.embedding_dimensions)>ai::EMBED_MAX_DIMENSIONS)
      throw Stop{"invalid_input","invalid embedding configuration"};
    for (;;) {
      std::vector<Pending> batch;
      {
        Transaction tx(db); fence(db,job);
        if (!expected) expected=page_snapshot(db,page_id);
        else check_snapshot(db,page_id,*expected);
        batch=next_batch(db,page_id,cursor,cfg);
        if (batch.empty()) {
          // Do not call a page complete if a concurrent edit invalidated an
          // already committed vector without changing its chunk identity.
          auto st=db.prepare("SELECT 1 FROM content_chunks WHERE page_id=? "
              "AND (embedding IS NULL OR length(embedding)=0) LIMIT 1");
          st.bind_int(1,page_id);
          if (st.step()) throw Stop{"stale","embedding work changed; retry explicitly"};
          record(db,job,persisted,batches,"completed","completed");tx.commit();break;
        }
        tx.commit();
      }
      std::vector<std::string> texts; texts.reserve(batch.size());
      for (const auto& p:batch) texts.push_back(p.text);
      // No live statement or transaction holds a read snapshot/write lock here.
      const auto response=ai::embed_texts(cfg,texts);
      validate_result(response,batch.size(),cfg);
      {
        Transaction tx(db);fence(db,job);check_snapshot(db,page_id,*expected);
        apply_batch(db,page_id,batch,response);
        record(db,job,persisted+static_cast<int64_t>(batch.size()),batches+1,"active","partial");
        tx.commit();
      }
      persisted+=static_cast<int64_t>(batch.size());++batches;cursor=batch.back().id;
    }
  } catch (const LostClaim&) {
    // Old work must not revive paused/cancelled/expired/reassigned jobs.
  } catch (const Stop& stop) {
    fail(stop.cancelled?"cancelled":"failed",stop.outcome,stop.message);
  } catch (const std::exception&) {
    // SQL/JSON/provider errors may contain text or keys. Do not echo them.
    fail("failed","execution_error","embedding execution failed");
  }
  return bounded_count(persisted);
}

int drain_embedding_jobs(Brain& brain,int max_jobs) {
  int64_t count=0;
  for (int n=0;n<max_jobs;++n) {
    std::string queue;
    {
      auto st=brain.db().prepare("SELECT queue FROM jobs WHERE type='embed' AND "
          "(status='waiting' OR (status='active' AND lock_until IS NOT NULL AND lock_until<?)) "
          "ORDER BY priority ASC,id ASC LIMIT 1");
      st.bind_text(1,util::utc_now());if (!st.step()) break;queue=st.column_text(0);
    }
    auto job=claim_job(brain,new_embedding_claim_token(),kLeaseSeconds*1000,queue,{"embed"});
    if (!job) continue; // a competing worker won; never run an unclaimed row
    count+=execute_embedding_job(brain,*job);
  }
  return bounded_count(count);
}
} // namespace qbrain::jobs
