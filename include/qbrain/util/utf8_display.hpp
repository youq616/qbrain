#pragma once
#include <algorithm>
#include <cstddef>
#include <string>
#include <string_view>

namespace qbrain::util {
// Strict scalar-value validation: overlong encodings, surrogates and values
// above U+10FFFF are rejected. This is byte safety, not grapheme segmentation.
inline std::size_t utf8_scalar_size(std::string_view s, std::size_t i) noexcept {
  if (i >= s.size()) return 0;
  const auto b = [&](std::size_t n) { return static_cast<unsigned char>(s[i + n]); };
  const auto cont = [](unsigned char c) { return c >= 0x80 && c <= 0xBF; };
  const auto first = b(0);
  const auto left = s.size() - i;
  if (first <= 0x7F) return 1;
  if (first >= 0xC2 && first <= 0xDF)
    return left >= 2 && cont(b(1)) ? 2 : 0;
  if (first >= 0xE0 && first <= 0xEF) {
    if (left < 3 || !cont(b(1)) || !cont(b(2))) return 0;
    if (first == 0xE0 && b(1) < 0xA0) return 0;
    if (first == 0xED && b(1) > 0x9F) return 0;
    return 3;
  }
  if (first >= 0xF0 && first <= 0xF4) {
    if (left < 4 || !cont(b(1)) || !cont(b(2)) || !cont(b(3))) return 0;
    if (first == 0xF0 && b(1) < 0x90) return 0;
    if (first == 0xF4 && b(1) > 0x8F) return 0;
    return 4;
  }
  return 0;
}

inline bool valid_utf8(std::string_view s) noexcept {
  for (std::size_t i = 0; i < s.size();) {
    const auto n = utf8_scalar_size(s, i);
    if (!n) return false;
    i += n;
  }
  return true;
}

// A bounded DISPLAY COPY only. Invalid bytes become U+FFFD one byte at a time;
// stored originals are untouched. The optional marker is inside max_bytes.
// A byte budget is not a token count or an exact-tokenizer promise.
inline std::string utf8_excerpt(std::string_view s, std::size_t max_bytes,
                                bool mark_truncated = false) {
  constexpr std::string_view replacement = "\xEF\xBF\xBD";
  constexpr std::string_view marker = "[truncated]";
  std::string out;
  out.reserve(std::min(s.size(), max_bytes));
  std::size_t i = 0;
  while (i < s.size()) {
    const auto n = utf8_scalar_size(s, i);
    const auto unit = n ? n : replacement.size();
    if (unit > max_bytes - out.size()) break;
    if (n) out.append(s.data() + i, n);
    else out.append(replacement);
    i += n ? n : 1;
  }
  if (mark_truncated && i < s.size() && marker.size() <= max_bytes) {
    while (!out.empty() && out.size() > max_bytes - marker.size()) {
      auto start = out.size() - 1;
      while (start > 0 && (static_cast<unsigned char>(out[start]) & 0xC0) == 0x80)
        --start;
      out.resize(start);
    }
    out.append(marker);
  }
  return out;
}
}  // namespace qbrain::util
