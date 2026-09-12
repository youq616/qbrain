#pragma once
#include "qbrain/ai/embed.hpp"
#include "qbrain/ai/embedding_policy.hpp"
#include "qbrain/ai/http_client.hpp"
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <unordered_set>
#include <nlohmann/json.hpp>

namespace qbrain::ai::detail {
// Shared production parser for text and image endpoints. All allocations based
// on indices are bounded by the request count, never by a provider-supplied index.
inline EmbedResult parse_embedding_response(std::string_view body,
    const std::string& requested_model, std::size_t expected_count,
    int expected_dimensions = 0,
    std::size_t byte_limit = HTTP_DEFAULT_RESPONSE_BYTES) {
  auto fail = [&] {
    EmbedResult result;
    result.error = "invalid embedding response";
    return result; // No partial vectors, model label, or raw parser/body text.
  };
  if (!valid_embedding_model(requested_model) || expected_count == 0 ||
      expected_count > EMBED_MAX_BATCH || expected_dimensions < 0 ||
      static_cast<std::size_t>(expected_dimensions) > EMBED_MAX_DIMENSIONS ||
      body.empty() || body.size() > byte_limit) return fail();
  try {
    using J = nlohmann::json;
    std::vector<std::unordered_set<std::string>> object_keys;
    std::size_t events = 0;
    auto callback = [&](int depth, J::parse_event_t event, J& value) {
      if (depth > 16 || ++events > EMBED_MAX_VALUES * 2 + 65536)
        throw std::runtime_error("embedding structure limit");
      if (event == J::parse_event_t::object_start) object_keys.emplace_back();
      else if (event == J::parse_event_t::object_end) object_keys.pop_back();
      else if (event == J::parse_event_t::key &&
               !object_keys.back().insert(value.get<std::string>()).second)
        throw std::runtime_error("duplicate embedding key");
      return true;
    };
    const auto payload = J::parse(body.begin(), body.end(), callback);
    if (!payload.is_object() || !payload.contains("data") ||
        !payload["data"].is_array() || payload["data"].size() != expected_count)
      return fail();
    if (payload.contains("model") &&
        (!payload["model"].is_string() || payload["model"] != requested_model))
      return fail();
    std::vector<std::vector<float>> vectors(expected_count);
    std::vector<bool> seen(expected_count, false);
    std::size_t width = static_cast<std::size_t>(expected_dimensions), total = 0;
    for (const auto& item : payload["data"]) {
      if (!item.is_object() || !item.contains("index") ||
          !item["index"].is_number_integer() || !item.contains("embedding") ||
          !item["embedding"].is_array()) return fail();
      const auto& index = item["index"];
      std::uint64_t position;
      if (index.is_number_unsigned()) position = index.get<std::uint64_t>();
      else {
        const auto signed_index = index.get<std::int64_t>();
        if (signed_index < 0) return fail();
        position = static_cast<std::uint64_t>(signed_index);
      }
      if (position >= expected_count || seen[static_cast<std::size_t>(position)]) return fail();
      const auto& values = item["embedding"];
      if (values.empty() || values.size() > EMBED_MAX_DIMENSIONS ||
          values.size() > EMBED_MAX_VALUES - total) return fail();
      total += values.size();
      if (width == 0) width = values.size();
      if (values.size() != width) return fail();
      auto& vector = vectors[static_cast<std::size_t>(position)];
      vector.reserve(width);
      bool nonzero = false;
      for (const auto& value : values) {
        if (!value.is_number()) return fail();
        const double number = value.get<double>();
        if (!std::isfinite(number) ||
            std::abs(number) > static_cast<double>(std::numeric_limits<float>::max()))
          return fail();
        const float element = static_cast<float>(number);
        if (!std::isfinite(element)) return fail();
        nonzero = nonzero || element != 0.0f;
        vector.push_back(element);
      }
      if (!nonzero) return fail();
      seen[static_cast<std::size_t>(position)] = true;
    }
    EmbedResult result;
    result.ok = true;
    result.model = requested_model;
    result.vectors = std::move(vectors);
    return result;
  } catch (const std::exception&) {
    return fail();
  }
}
}  // namespace qbrain::ai::detail
