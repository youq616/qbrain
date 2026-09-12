#pragma once
#include "qbrain/search/result_identity.hpp"
#include <algorithm>
#include <cmath>
#include <iterator>
#include <set>
#include <unordered_map>
#include <utility>
#include <vector>

namespace qbrain::search::detail {
// Exact best-chunk-per-page Top-K for one statement snapshot. No scan ordering
// required. The worst retained rank only improves: an evicted page's old chunk
// cannot qualify later, but a new better chunk can re-enter normally.
class ExactPageTopK {
  struct Better {
    bool operator()(const SearchHit& a, const SearchHit& b) const {
      return a.score != b.score ? a.score > b.score : result_identity_less(a, b);
    }
  };
  using Ordered = std::set<SearchHit, Better>;
  std::size_t limit_;
  Ordered ordered_;
  std::unordered_map<std::string, Ordered::iterator> by_page_;

 public:
  explicit ExactPageTopK(int limit) : limit_(std::clamp(limit, 1, 500)) {}
  ExactPageTopK(const ExactPageTopK&) = delete;
  ExactPageTopK& operator=(const ExactPageTopK&) = delete;

  bool below_threshold(double score) const {
    // Equality still needs both deterministic page and same-page snippet ties.
    return ordered_.size() == limit_ && score < ordered_.rbegin()->score;
  }
  void consider(SearchHit hit) {
    if (!std::isfinite(hit.score) || below_threshold(hit.score)) return;
    const auto key = result_identity(hit);
    const auto found = by_page_.find(key);
    if (found != by_page_.end()) {
      const auto& previous = *found->second;
      if (hit.score < previous.score ||
          (hit.score == previous.score && hit.snippet >= previous.snippet)) return;
      ordered_.erase(found->second);
      by_page_.erase(found);
    } else if (ordered_.size() == limit_) {
      const auto worst = std::prev(ordered_.end());
      if (!Better{}(hit, *worst)) return;
      by_page_.erase(result_identity(*worst));
      ordered_.erase(worst);
    }
    const auto [position, inserted] = ordered_.insert(std::move(hit));
    if (inserted) by_page_.emplace(key, position);
  }
  std::size_t size() const noexcept { return ordered_.size(); }
  std::vector<SearchHit> results() const {
    std::vector<SearchHit> out(ordered_.begin(), ordered_.end());
    int rank = 1;
    for (auto& hit : out) hit.vector_rank = static_cast<double>(rank++);
    return out;
  }
};
}  // namespace qbrain::search::detail
