#pragma once
#include "qbrain/core/brain.hpp"
#include "qbrain/core/types.hpp"
#include <optional>
#include <string>
#include <vector>

namespace qbrain::search {

// Numeric per-call observations, not process-memory or semantic-quality metrics.
struct RetrievalDiagnostics {
  std::size_t chunks_scanned = 0;
  std::size_t valid_chunks = 0;
  std::size_t invalid_chunks = 0;
  std::size_t peak_retained_pages = 0;
  std::size_t backlink_candidates = 0;
  std::size_t backlink_queries = 0;
};

struct HybridOpts {
  int limit = 10;
  int rrf_k = 60;
  bool use_vector = true;
  std::string source_id;  // empty = all
  std::string mode;       // conservative | balanced | tokenmax (N3)
  bool rerank = false;    // explicit override; tokenmax enables by default
  bool rerank_llm = false;
  const Config* config = nullptr;  // needed for LLM rerank; optional
  int* candidate_budget_out = nullptr;  // test hook
  int* pre_autocut_count_out = nullptr; // test hook
  RetrievalDiagnostics* diagnostics = nullptr; // optional; no memory text
  // Absent: active configured model. Explicit empty: no vector lane, not wildcard.
  // Raw C++ callers can name the model that produced their supplied query vector.
  std::optional<std::string> embedding_model;
};

std::vector<SearchHit> fts_search(Brain& brain, const std::string& query, int limit,
                                  const std::string& source_id = {});
// Low-level raw API: empty expected_model retains legacy unfiltered behavior.
// Production hybrid search always supplies a validated, nonempty model.
std::vector<SearchHit> vector_search(Brain& brain, const std::vector<float>& qemb, int limit,
                                     const std::string& source_id = {},
                                     RetrievalDiagnostics* diagnostics = nullptr,
                                     const std::string& expected_model = {});
std::vector<SearchHit> hybrid_search(Brain& brain, const std::string& query,
                                     const std::vector<float>* qemb,
                                     const HybridOpts& opts);

}  // namespace qbrain::search
