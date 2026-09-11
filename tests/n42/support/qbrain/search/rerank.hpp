#pragma once
// TEST ADAPTER: no provider calls; reranking is intentionally not certified here.
#include "qbrain/core/types.hpp"
#include <string>
#include <vector>
namespace qbrain::search {
struct RerankerOpts {bool enabled=false;int top_n_in=0;bool use_llm=false;};
inline std::vector<SearchHit> apply_reranker(const Config&,const std::string&,
  std::vector<SearchHit> hits,const RerankerOpts&){return hits;}
}
