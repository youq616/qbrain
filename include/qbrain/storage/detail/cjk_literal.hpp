#pragma once
#include "qbrain/util/utf8_display.hpp"
#include <cstdint>
#include <string_view>

namespace qbrain::storage::detail {
// A lexical-policy check, not word segmentation or Unicode normalization.
// Limit only the additional SQLite literal lane; leave the old FTS path intact.
inline bool cjk_literal_eligible(std::string_view query) noexcept {
  if (query.empty() || query.size() > 1024 || !util::valid_utf8(query)) return false;
  bool found = false;
  for (std::size_t i = 0; i < query.size();) {
    const auto width = util::utf8_scalar_size(query, i);
    const auto first = static_cast<unsigned char>(query[i]);
    std::uint32_t cp = first;
    if (width > 1) {
      cp = first & (width == 2 ? 0x1f : width == 3 ? 0x0f : 0x07);
      for (std::size_t j = 1; j < width; ++j)
        cp = (cp << 6) | (static_cast<unsigned char>(query[i+j]) & 0x3f);
    }
    if (cp < 0x20 || cp == 0x7f) return false;
    found = found || (cp >= 0x3400 && cp <= 0x4dbf) ||
      (cp >= 0x4e00 && cp <= 0x9fff) || (cp >= 0xf900 && cp <= 0xfaff) ||
      (cp >= 0x20000 && cp <= 0x2fa1f) || (cp >= 0x30000 && cp <= 0x323af) ||
      (cp >= 0x3040 && cp <= 0x30ff) || (cp >= 0x31f0 && cp <= 0x31ff) ||
      (cp >= 0xff66 && cp <= 0xff9f) || (cp >= 0x1100 && cp <= 0x11ff) ||
      (cp >= 0x3130 && cp <= 0x318f) || (cp >= 0xa960 && cp <= 0xa97f) ||
      (cp >= 0xac00 && cp <= 0xd7ff);
    i += width;
  }
  return found;
}
}  // namespace qbrain::storage::detail
