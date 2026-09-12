#pragma once
#include "qbrain/core/types.hpp"
#include <algorithm>
#include <cstdlib>
#include <string>
#include <string_view>

namespace qbrain::ai {
inline constexpr std::size_t EMBED_MAX_BATCH = 2048;
inline constexpr std::size_t EMBED_MAX_DIMENSIONS = 16384;
inline constexpr std::size_t EMBED_MAX_VALUES = 1024 * 1024;
inline bool valid_embedding_model(std::string_view model) {
  return !model.empty() && model.size() <= 256 &&
      std::all_of(model.begin(), model.end(), [](unsigned char c) {
        return c > 0x20 && c < 0x7f;
      });
}
inline bool embedding_mock_enabled() {
  const char* value = std::getenv("QBRAIN_EMBED_MOCK");
  return value && (std::string_view(value) == "1" || std::string_view(value) == "true");
}
// The wire parser requires any returned model label to match the request.
// This label is not an attestation of provider endpoint or model weights.
inline std::string active_embedding_model(const Config& cfg) {
  return embedding_mock_enabled() ? "mock-embedding" : cfg.embedding_model;
}
}  // namespace qbrain::ai
