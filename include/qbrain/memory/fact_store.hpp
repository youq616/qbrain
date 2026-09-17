#pragma once
#include "qbrain/memory/session_memory.hpp"

namespace qbrain::memory {
// Source-scoped, caller-attested claims. Values are COMPLETE user quotes, not
// inferred triples. Each thread needs its own Brain/Database connection.
class FactStore {
 public:
  FactStore(Brain& brain, std::string source);
  // Explicit local extraction -> complete user-quote facts. Batch fact/evidence
  // writes are atomic; optional schema preparation is a separate operation.
  // Explicit recall policy, not fact retirement or deletion. Writes require
  // the current fact revision; restore never revives unsupported/retired facts.
  Json archive(const Json& payload);
  Json restore(const Json& payload);
  // Preview or atomically apply 1..32 selected archive/restore changes. The
  // apply decision is owned by the public route, never accepted from payload.
  Json lifecycle_batch(const Json& payload, bool apply = false);
  Json lifecycle(const std::string& fact_id = "", const std::string& predicate = "",
                 int stale_after_days = 180, int limit = 10, int max_bytes = 8192);
  // Read-only discovery for explicit N47G batches. after_id is a seek key, not
  // a lease or authorization. Each page is a fresh snapshot, metadata only.
  Json lifecycle_candidates(const std::string& operation, const std::string& predicate = "",
                            int stale_after_days = 180, const std::string& after_id = "",
                            int limit = 10, int max_bytes = 8192);
  Json promote_event(const std::string& event_id);
  Json create(const Json& payload);       // predicate, item_id; subject is user
  Json attach(const Json& payload);       // fact_id, item_id (exact same quote)
  Json retract(const Json& payload);      // fact_id, expected_revision
  Json supersede(const Json& payload);    // fact_id, replacement_id, expected_revision
  Json contradict(const Json& payload);   // fact_id, other_id (explicit assertion)
  Json read(const std::string& fact_id = "", const std::string& predicate = "",
            bool include_history = false, int limit = 10, int max_bytes = 8192);
  // Explicit, still-supported contradictions. Each returned pair is complete;
  // this neither infers conflict nor decides which claim is true.
  Json conflicts(const std::string& fact_id = "", const std::string& predicate = "",
                 int limit = 10, int max_bytes = 8192);
  // Explicit public literal/all_terms/any_terms active-quote recall. Terms are
  // ASCII whitespace-delimited literals; all_terms applies to one anchor only.
  // Every item retains its valid direct counterclaims, regardless of matching.
  Json recall(const std::string& query, const std::string& predicate = "",
              int limit = 10, int max_bytes = 8192, const std::string& match = "literal");
  // Internal integration entry: empty queries select recent active facts.
  // Prompt callers must not pass empty terms as a substitute for an empty query.
  Json recall_for_hook(const std::vector<std::string>& queries, int limit = 10,
                       int max_bytes = 8192);
 private:
  Json set_archived(const Json& payload, bool archived);
  Json recall_queries(const std::vector<std::string>& queries, const std::string& predicate,
                      int limit, int max_bytes, const std::string& match = "");
  void validate() const;
  Brain& brain_;
  std::string source_;
};
}  // namespace qbrain::memory
