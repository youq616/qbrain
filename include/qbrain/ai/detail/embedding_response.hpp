#pragma once
#include "qbrain/ai/http_client.hpp"
#include <nlohmann/json.hpp>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <set>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace qbrain::ai::detail {
// Qbrain application bounds, not a statement of any provider's API limits.
inline constexpr std::size_t EMBED_MAX_BATCH = 2048;
inline constexpr std::size_t EMBED_MAX_DIMENSIONS = 32768;
inline constexpr std::size_t EMBED_MAX_COMPONENTS = 1048576;
inline constexpr std::size_t EMBED_MAX_PARSE_EVENTS = EMBED_MAX_COMPONENTS + 65536;
inline constexpr int EMBED_MAX_JSON_DEPTH = 16;

struct EmbeddingPayload {
  bool ok = false;
  std::vector<std::vector<float>> vectors;
  std::string error;
};

inline EmbeddingPayload embedding_failure(const char* message) {
  return {false, {}, message};
}

// No returned error contains response bytes or parser diagnostics. An output is
// published only after the whole batch passes, including its final element.
inline EmbeddingPayload parse_embedding_response(
    std::string_view body, std::size_t expected_count, int expected_dimensions = 0,
    bool allow_unindexed_single = false,
    std::size_t byte_limit = HTTP_DEFAULT_RESPONSE_BYTES) {
  if (!expected_count || expected_count > EMBED_MAX_BATCH || expected_dimensions < 0 ||
      static_cast<std::size_t>(expected_dimensions) > EMBED_MAX_DIMENSIONS ||
      !byte_limit || byte_limit > HTTP_DEFAULT_RESPONSE_BYTES)
    return embedding_failure("invalid embedding response contract");
  if (body.size() > byte_limit)
    return embedding_failure("embedding response exceeds byte limit");
  using J = nlohmann::json;
  struct ParseLimit {};
  try {
    std::size_t events = 0;
    std::array<std::set<std::string>, EMBED_MAX_JSON_DEPTH + 1> object_keys;
    auto guard = [&](int depth, J::parse_event_t event, J& parsed) {
      if (depth < 0 || depth > EMBED_MAX_JSON_DEPTH || ++events > EMBED_MAX_PARSE_EVENTS)
        throw ParseLimit{};
      // An object's key events are one level deeper than its start event.
      if (event == J::parse_event_t::object_start) object_keys[depth].clear();
      if (event == J::parse_event_t::key) {
        if (depth == 0) throw ParseLimit{};
        auto& keys = object_keys[depth - 1];
        if (keys.size() >= 128 || !keys.insert(parsed.get<std::string>()).second)
          throw ParseLimit{};
      }
      if (event == J::parse_event_t::object_end) object_keys[depth].clear();
      return true;
    };
    const J payload = J::parse(body.begin(), body.end(), guard);
    if (!payload.is_object() || !payload.contains("data") || !payload["data"].is_array() ||
        payload["data"].size() != expected_count)
      return embedding_failure("embedding response batch count mismatch");

    std::vector<std::vector<float>> vectors(expected_count);
    std::vector<bool> seen(expected_count, false);
    std::size_t dimensions = static_cast<std::size_t>(expected_dimensions), components = 0;
    for (const auto& item : payload["data"]) {
      if (!item.is_object()) return embedding_failure("embedding response invalid item");
      std::uint64_t index = 0;
      if (!item.contains("index")) {
        if (!allow_unindexed_single || expected_count != 1)
          return embedding_failure("embedding response missing index");
      } else {
        const auto& v = item["index"];
        if (v.is_number_unsigned()) index = v.get<std::uint64_t>();
        else if (v.is_number_integer()) {
          const auto signed_index = v.get<std::int64_t>();
          if (signed_index < 0) return embedding_failure("embedding response invalid index");
          index = static_cast<std::uint64_t>(signed_index);
        } else return embedding_failure("embedding response invalid index");
      }
      // Never resize or narrow according to a provider-controlled index.
      if (index >= expected_count || seen[static_cast<std::size_t>(index)])
        return embedding_failure("embedding response invalid or duplicate index");
      seen[static_cast<std::size_t>(index)] = true;
      if (!item.contains("embedding") || !item["embedding"].is_array())
        return embedding_failure("embedding response invalid vector");
      const auto& input = item["embedding"];
      if (input.empty() || input.size() > EMBED_MAX_DIMENSIONS ||
          input.size() > EMBED_MAX_COMPONENTS - components)
        return embedding_failure("embedding response vector size invalid");
      if (!dimensions) dimensions = input.size();
      if (input.size() != dimensions)
        return embedding_failure("embedding response dimensions mismatch");
      components += input.size();
      auto& vector = vectors[static_cast<std::size_t>(index)];
      vector.reserve(dimensions);
      bool nonzero = false;
      for (const auto& value : input) {
        if (!value.is_number()) return embedding_failure("embedding response nonnumeric component");
        const double number = value.get<double>();
        if (!std::isfinite(number) ||
            number > static_cast<double>(std::numeric_limits<float>::max()) ||
            number < -static_cast<double>(std::numeric_limits<float>::max()))
          return embedding_failure("embedding response component out of range");
        const float component = static_cast<float>(number);
        nonzero = nonzero || component != 0.0f;
        vector.push_back(component);
      }
      if (!nonzero) return embedding_failure("embedding response zero vector");
    }
    return {true, std::move(vectors), {}};
  } catch (const ParseLimit&) {
    return embedding_failure("embedding response JSON structure rejected");
  } catch (const std::exception&) {
    return embedding_failure("embedding response malformed JSON");
  }
}

// Exact default nlohmann JSON UTF-8 string length (including quotation marks).
// Saturate above the budget, never wrap. UTF-8 validity is checked by the caller.
inline std::size_t json_string_bytes(std::string_view text, std::size_t budget) {
  if (budget < 2) return budget + 1;
  std::size_t length = 2;
  for (unsigned char c : text) {
    const std::size_t bytes = c == '"' || c == '\\' || c == '\b' || c == '\f' ||
        c == '\n' || c == '\r' || c == '\t' ? 2 : c < 0x20 ? 6 : 1;
    if (bytes > budget - length) return budget + 1;
    length += bytes;
  }
  return length;
}
}  // namespace qbrain::ai::detail
