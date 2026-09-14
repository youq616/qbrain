#pragma once
#include "qbrain/memory/session_memory.hpp"

namespace qbrain::memory {
// Source-scoped, caller-attested claims. Values are COMPLETE user quotes, not
// inferred triples. Each thread needs its own Brain/Database connection.
class FactStore {
 public:
  FactStore(Brain& brain, std::string source);
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
  // Literal active-quote recall. Every item includes all valid direct explicit
  // counterclaims. No transitive expansion, semantic inference or winner.
  Json recall(const std::string& query, const std::string& predicate = "",
              int limit = 10, int max_bytes = 8192);
  // Internal integration entry: empty queries select recent active facts.
  // Prompt callers must not pass empty terms as a substitute for an empty query.
  Json recall_for_hook(const std::vector<std::string>& queries, int limit = 10,
                       int max_bytes = 8192);
 private:
  Json recall_queries(const std::vector<std::string>& queries, const std::string& predicate,
                      int limit, int max_bytes);
  void validate() const;
  Brain& brain_;
  std::string source_;
};
}  // namespace qbrain::memory
