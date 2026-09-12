#include "qbrain/ai/embed.hpp"
#include "qbrain/ai/http_client.hpp"
#include "qbrain/ai/detail/embedding_response.hpp"
#include "qbrain/util/utf8_display.hpp"
#include "qbrain/core/brain.hpp"
#include "qbrain/util/hash.hpp"
#include <nlohmann/json.hpp>
#include <algorithm>
#include <cstdlib>
#include <string_view>

using json = nlohmann::json;

namespace qbrain::ai {

namespace {

// ---- N33 D3: image embedding provider contract ----

constexpr int kImageEmbedTimeoutMs = 30000;           // shared monotonic network deadline
constexpr size_t kImageMaxResponseBytes = 2u * 1024 * 1024;  // response <= 2 MiB
constexpr size_t kImageMaxInputBytes = 32u * 1024 * 1024;    // 32 MiB input cap
constexpr size_t kImageMockHashPrefix = 4096;         // hash first 4 KiB only
constexpr size_t kImageMockVectorDims = 64;           // deterministic mock width
constexpr size_t kImageMaxErrorChars = 200;           // redacted error cap

std::string base64_encode(std::string_view in) {
  static const char kTable[] =
      "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  std::string out;
  out.reserve(((in.size() + 2) / 3) * 4);
  size_t i = 0;
  for (; i + 2 < in.size(); i += 3) {
    const unsigned char b0 = static_cast<unsigned char>(in[i]);
    const unsigned char b1 = static_cast<unsigned char>(in[i + 1]);
    const unsigned char b2 = static_cast<unsigned char>(in[i + 2]);
    out.push_back(kTable[b0 >> 2]);
    out.push_back(kTable[((b0 & 0x03) << 4) | (b1 >> 4)]);
    out.push_back(kTable[((b1 & 0x0F) << 2) | (b2 >> 6)]);
    out.push_back(kTable[b2 & 0x3F]);
  }
  if (i + 1 == in.size()) {
    const unsigned char b0 = static_cast<unsigned char>(in[i]);
    out.push_back(kTable[b0 >> 2]);
    out.push_back(kTable[(b0 & 0x03) << 4]);
    out.push_back('=');
    out.push_back('=');
  } else if (i + 2 == in.size()) {
    const unsigned char b0 = static_cast<unsigned char>(in[i]);
    const unsigned char b1 = static_cast<unsigned char>(in[i + 1]);
    out.push_back(kTable[b0 >> 2]);
    out.push_back(kTable[((b0 & 0x03) << 4) | (b1 >> 4)]);
    out.push_back(kTable[(b1 & 0x0F) << 2]);
    out.push_back('=');
  }
  return out;
}

void replace_all(std::string& text, const std::string& needle, const std::string& replacement) {
  if (needle.empty()) return;
  size_t pos = 0;
  while ((pos = text.find(needle, pos)) != std::string::npos) {
    text.replace(pos, needle.size(), replacement);
    pos += replacement.size();
  }
}

bool is_scheme_char(char c) {
  return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') ||
         c == '+' || c == '-' || c == '.';
}

// N33 D3 credential isolation: strip the configured base URLs, all resolved
// credential material, and any residual URL-looking span, then truncate.
std::string redact_provider_error(std::string message, const Config& cfg,
                                  const std::string& api_key) {
  for (const std::string* secret : {&api_key, &cfg.embedding_api_key, &cfg.chat_api_key}) {
    if (!secret->empty()) replace_all(message, *secret, "[redacted]");
  }
  for (const std::string* url : {&cfg.embedding_base_url, &cfg.chat_base_url}) {
    if (!url->empty()) replace_all(message, *url, "[redacted]");
  }
  // Generic URL scrub: anything scheme://... up to the next delimiter.
  size_t pos = 0;
  while ((pos = message.find("://", pos)) != std::string::npos) {
    size_t start = pos;
    while (start > 0 && is_scheme_char(message[start - 1])) --start;
    size_t end = pos + 3;
    while (end < message.size() && message[end] != ' ' && message[end] != '"' &&
           message[end] != '\'' && message[end] != '<' && message[end] != '>' &&
           message[end] != ')' && message[end] != ']' && message[end] != '}' &&
           message[end] != '\n' && message[end] != '\r' && message[end] != '\t') {
      ++end;
    }
    message.replace(start, end - start, "[redacted]");
    pos = start + std::string("[redacted]").size();
  }
  if (message.size() > kImageMaxErrorChars) message.resize(kImageMaxErrorChars);
  return message;
}

// Deterministic mock vector: hash of the first 4 KiB -> 64-bit seed ->
// splitmix64 stream -> fixed 64 dims. Same content = identical vector.
std::vector<float> mock_image_vector(std::string_view bytes) {
  const size_t n = std::min(bytes.size(), kImageMockHashPrefix);
  const std::string hex = util::sha256_hex(std::string_view(bytes.data(), n));
  uint64_t seed = 0;
  for (size_t i = 0; i < 16 && i < hex.size(); ++i) {
    seed = (seed << 4) | static_cast<uint64_t>(hex[i] <= '9' ? hex[i] - '0'
                                                             : (hex[i] | 0x20) - 'a' + 10);
  }
  std::vector<float> v;
  v.reserve(kImageMockVectorDims);
  uint64_t s = seed;
  for (size_t i = 0; i < kImageMockVectorDims; ++i) {
    s += 0x9E3779B97F4A7C15ULL;
    uint64_t z = s;
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    z = z ^ (z >> 31);
    const double unit = static_cast<double>(z >> 40) / 16777215.0;  // [0,1]
    v.push_back(static_cast<float>(unit * 2.0 - 1.0));              // [-1,1]
  }
  return v;
}

}  // namespace

EmbedResult embed_texts(const Config& cfg, const std::vector<std::string>& texts) {
  EmbedResult r;
  r.model = cfg.embedding_model;
  if (texts.empty()) {
    r.ok = true;
    return r;
  }
  if (const char* mock = std::getenv("QBRAIN_EMBED_MOCK")) {
    if (std::string(mock) == "1" || std::string(mock) == "true") {
      r.ok = true;
      r.model = "mock-embedding";
      r.vectors.reserve(texts.size());
      for (size_t i = 0; i < texts.size(); ++i) {
        float base = static_cast<float>((texts[i].size() % 17) + 1);
        r.vectors.push_back({base, 1.0f, static_cast<float>(i + 1)});
      }
      return r;
    }
  }
  if (texts.size() > detail::EMBED_MAX_BATCH || cfg.embedding_dimensions < 0 ||
      static_cast<std::size_t>(cfg.embedding_dimensions) > detail::EMBED_MAX_DIMENSIONS ||
      cfg.embedding_model.empty() || cfg.embedding_model.size() > 1024 ||
      !util::valid_utf8(cfg.embedding_model)) {
    r.error = "invalid embedding request configuration";
    return r;
  }
  if (cfg.embedding_dimensions > 0 &&
      texts.size() > detail::EMBED_MAX_COMPONENTS / static_cast<std::size_t>(cfg.embedding_dimensions)) {
    r.error = "embedding request exceeds component limit";
    return r;
  }
  for (const auto& text : texts) {
    if (text.empty() || text.size() > HTTP_MAX_REQUEST_BYTES || !util::valid_utf8(text)) {
      r.error = "invalid embedding text input";
      return r;
    }
  }
  auto key = resolve_api_key(cfg, false);
  if (key.empty()) {
    r.error = "missing embedding API key";
    return r;
  }
  std::string encoded;
  try {
    json body = {{"model", cfg.embedding_model}, {"input", json::array()},
                 {"encoding_format", "float"}};
    if (cfg.embedding_dimensions > 0) body["dimensions"] = cfg.embedding_dimensions;
    std::size_t bytes = body.dump().size();
    for (std::size_t i = 0; i < texts.size(); ++i) {
      if (i) ++bytes; // comma between array entries
      if (bytes > HTTP_MAX_REQUEST_BYTES) {
        r.error = "embedding request exceeds byte limit";
        return r;
      }
      const auto extra = detail::json_string_bytes(texts[i], HTTP_MAX_REQUEST_BYTES - bytes);
      if (extra > HTTP_MAX_REQUEST_BYTES - bytes) {
        r.error = "embedding request exceeds byte limit";
        return r;
      }
      bytes += extra;
    }
    body["input"] = texts;
    encoded = body.dump();
  } catch (const std::exception&) {
    r.error = "embedding request could not be encoded";
    return r;
  }
  const auto resp = http_post_json(cfg.embedding_base_url, "/embeddings", key, encoded);
  if (resp.failure != HttpFailure::none || resp.status < 200 || resp.status >= 300) {
    r.error = resp.error.empty() ? "embedding HTTP request failed" : resp.error;
    return r;
  }
  auto parsed = detail::parse_embedding_response(resp.body, texts.size(), cfg.embedding_dimensions);
  if (!parsed.ok) {
    r.error = std::move(parsed.error);
    return r;
  }
  r.vectors = std::move(parsed.vectors);
  r.ok = true;
  return r;
}

ImageEmbedResult embed_image(const Config& cfg, std::string_view image_bytes) {
  ImageEmbedResult r;
  r.model = cfg.embedding_model;
  auto degrade = [&](const std::string& message, bool no_credentials) {
    r.ok = false;
    r.vector.clear();
    r.unavailable = true;
    r.no_credentials = no_credentials;
    r.error = redact_provider_error(message, cfg, resolve_api_key(cfg, false));
    return r;
  };
  if (image_bytes.empty()) return degrade("empty image input", false);
  if (image_bytes.size() > kImageMaxInputBytes) {
    return degrade("image exceeds size limit", false);
  }
  if (const char* mock = std::getenv("QBRAIN_EMBED_MOCK")) {
    if (std::string(mock) == "1" || std::string(mock) == "true") {
      r.ok = true;
      r.mock = true;
      r.model = "mock-image-embedding";
      r.vector = mock_image_vector(image_bytes);
      return r;
    }
  }
  const std::string key = resolve_api_key(cfg, false);
  if (key.empty()) return degrade("no provider credentials", true);
  // Local magic sniff only to label the data URL; no image_meta dependency.
  std::string mime = "image/png";
  if (image_bytes.size() >= 3 && static_cast<unsigned char>(image_bytes[0]) == 0xFF &&
      static_cast<unsigned char>(image_bytes[1]) == 0xD8 &&
      static_cast<unsigned char>(image_bytes[2]) == 0xFF) {
    mime = "image/jpeg";
  }
  if (cfg.embedding_model.empty() || cfg.embedding_model.size() > 1024 ||
      !util::valid_utf8(cfg.embedding_model))
    return degrade("invalid embedding request configuration", false);
  std::string encoded;
  try {
    const std::string prefix = "data:" + mime + ";base64,";
    json body = {{"model", cfg.embedding_model}, {"encoding_format", "float"},
                 {"input", json::array({json{{"type", "image_url"},
                                           {"image_url", {{"url", prefix}}}}})}};
    const auto header_bytes = body.dump().size();
    const auto base64_bytes = ((image_bytes.size() + 2) / 3) * 4;
    if (header_bytes > HTTP_MAX_REQUEST_BYTES ||
        base64_bytes > HTTP_MAX_REQUEST_BYTES - header_bytes)
      return degrade("embedding request exceeds byte limit", false);
    body["input"][0]["image_url"]["url"] = prefix + base64_encode(image_bytes);
    encoded = body.dump();
  } catch (const std::exception&) {
    return degrade("embedding request could not be encoded", false);
  }
  const auto resp = http_post_json(cfg.embedding_base_url, "/embeddings", key, encoded,
                                   kImageEmbedTimeoutMs, kImageMaxResponseBytes);
  if (resp.failure != HttpFailure::none || resp.status < 200 || resp.status >= 300)
    return degrade(resp.error.empty() ? "embedding HTTP request failed" : resp.error, false);
  // Some image gateways omit the single item's index; accept only that legacy
  // omission, never a supplied out-of-range index or a multi-item response.
  auto parsed = detail::parse_embedding_response(resp.body, 1, 0, true, kImageMaxResponseBytes);
  if (!parsed.ok) return degrade(parsed.error, false);
  r.vector = std::move(parsed.vectors.front());
  r.ok = true;
  return r;
}

}  // namespace qbrain::ai
