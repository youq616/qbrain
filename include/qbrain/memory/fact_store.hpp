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
 private:
  void validate() const;
  Brain& brain_;
  std::string source_;
};
}  // namespace qbrain::memory
