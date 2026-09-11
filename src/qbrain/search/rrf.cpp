#include "qbrain/search/rrf.hpp"
#include "qbrain/search/result_identity.hpp"
#include <cmath>
#include <limits>
#include <unordered_set>
#include <algorithm>
#include <unordered_map>

namespace qbrain::search {

std::vector<SearchHit> rrf_fusion_weighted(const std::vector<std::vector<SearchHit>>& lists,
                                           const std::vector<double>& weights, int k) {
  struct Acc {
    SearchHit hit;
    double score = 0;
  };
  // Avoid zero/negative denominators from malformed configuration.
  k = std::max(k, 0);
  std::unordered_map<std::string, Acc> map;
  for (size_t li = 0; li < lists.size(); ++li) {
    double w = (li < weights.size()) ? weights[li] : 1.0;
    if (!std::isfinite(w) || w <= 0) continue;
    std::unordered_set<std::string> seen;
    const auto& list = lists[li];
    for (size_t rank = 0; rank < list.size(); ++rank) {
      const auto& h = list[rank];
      if (h.page_id <= 0 && h.slug.empty()) continue;
      const auto key = result_identity(h);
      if (!seen.insert(key).second) continue;  // no duplicate votes in one list
      auto [it, inserted] = map.try_emplace(key);
      auto& a = it->second;
      if (inserted) a.hit = h;
      // Reject inconsistent identity metadata rather than fusing stale rows.
      if (a.hit.slug != h.slug || a.hit.source_id != h.source_id) continue;
      const auto contribution = w / (static_cast<double>(k) + static_cast<double>(rank + 1));
      const auto maximum = std::numeric_limits<double>::max();
      a.score = contribution > maximum - a.score ? maximum : a.score + contribution;
      if (h.fts_rank > 0 && (a.hit.fts_rank == 0 || h.fts_rank < a.hit.fts_rank))
        a.hit.fts_rank = h.fts_rank;
      if (h.vector_rank > 0 && (a.hit.vector_rank == 0 || h.vector_rank < a.hit.vector_rank))
        a.hit.vector_rank = h.vector_rank;
      if (a.hit.snippet.empty() && !h.snippet.empty()) a.hit.snippet = h.snippet;
      if (a.hit.title.empty() && !h.title.empty()) a.hit.title = h.title;
    }
  }
  std::vector<SearchHit> out;
  out.reserve(map.size());
  for (auto& [_, a] : map) {
    a.hit.score = a.score;
    out.push_back(std::move(a.hit));
  }
  std::sort(out.begin(), out.end(),
            [](const SearchHit& x, const SearchHit& y) {
              return x.score != y.score ? x.score > y.score : result_identity_less(x, y);
            });
  return out;
}

std::vector<SearchHit> rrf_fusion(const std::vector<std::vector<SearchHit>>& lists, int k) {
  return rrf_fusion_weighted(lists, {}, k);
}

}  // namespace qbrain::search
