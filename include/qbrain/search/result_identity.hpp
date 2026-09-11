#pragma once
#include "qbrain/core/types.hpp"
#include <string>
#include <tuple>

namespace qbrain::search {
// IDs are unique within one Brain; callers must not fuse different databases.
// Source/slug fallback serves id-less clients; length framing avoids delimiter
// collisions. Empty source means legacy/unknown, NOT authorization to default.
inline std::string result_identity(const SearchHit& hit) {
  if (hit.page_id > 0) return "id:" + std::to_string(hit.page_id);
  return "slug:" + std::to_string(hit.source_id.size()) + ":" + hit.source_id + hit.slug;
}
inline bool result_identity_less(const SearchHit& a, const SearchHit& b) noexcept {
  return std::tie(a.source_id, a.slug, a.page_id) < std::tie(b.source_id, b.slug, b.page_id);
}
}  // namespace qbrain::search
