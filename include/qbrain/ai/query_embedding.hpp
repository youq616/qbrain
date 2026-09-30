#pragma once
// Call only from an already authorized query path; never reuse query results/evidence.
#include "qbrain/core/brain.hpp"
#include "qbrain/ai/embedding_policy.hpp"
#include "qbrain/ai/embed.hpp"
#include "qbrain/util/hash.hpp"
#include <initializer_list>
#include <string_view>

namespace qbrain::ai {
namespace query_cache_detail {
inline std::string fingerprint(std::initializer_list<std::string_view> fields) {
  std::string bytes;
  for (const auto field : fields) {
    bytes += std::to_string(field.size()); bytes += ':';
    bytes.append(field.data(), field.size());
  }
  return util::sha256_hex(bytes);
}
} // namespace query_cache_detail
inline EmbedResult query_embedding(Brain& brain, const std::string& query,
                                   const std::string& resolved_source) {
  auto& cache = brain.query_embedding_cache();
  const Config config = brain.config();
  const auto invoke = [&] { return embed_texts(config, {query}); };
  // This database setting is observed on every eligible query, not cached as policy.
  if (brain.get_config_value("search.query_embedding_cache").value_or("") != "1")
    return cache.get_or_load(false, {}, invoke);
  const bool mock = embedding_mock_enabled();
  const std::string key = resolve_api_key(config, false);
  if (!valid_embedding_model(config.embedding_model) || config.embedding_dimensions < 0 ||
      std::size_t(config.embedding_dimensions) > EMBED_MAX_DIMENSIONS || query.size() > 262144 ||
      resolved_source.size() > 64 || config.embedding_provider.size() > 256 ||
      config.embedding_base_url.size() > 8192 || key.size() > 65536 || (!mock && key.empty()))
    return cache.get_or_load(false, {}, invoke);
  QueryEmbeddingCache::Identity id;
  const std::string dimensions = std::to_string(config.embedding_dimensions);
  id.policy = query_cache_detail::fingerprint({"qbrain-query-vector-v1", config.embedding_provider,
    config.embedding_base_url, config.embedding_model, dimensions, key, mock ? "1" : "0"});
  id.key = query_cache_detail::fingerprint({"qbrain-query-source-v1", resolved_source, query});
  id.model = mock ? "mock-embedding" : config.embedding_model;
  id.dimensions = mock ? 3 : config.embedding_dimensions;
  return cache.get_or_load(true, std::move(id), invoke);
}
} // namespace qbrain::ai
