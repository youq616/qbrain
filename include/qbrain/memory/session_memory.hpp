#pragma once
#include "qbrain/ai/chat.hpp"
#include "qbrain/core/brain.hpp"
#include <functional>
#include <nlohmann/json.hpp>
#include <stdexcept>

namespace qbrain::memory {
using Json = nlohmann::json;
struct Error : std::runtime_error { using std::runtime_error::runtime_error; };
using Provider = std::function<ai::ChatResult(const std::vector<ai::ChatMessage>&, int)>;
inline constexpr std::size_t max_payload_bytes = 262144;
Json capture(Brain&, const std::string& source, const Json& payload, bool manual = false);
Json extract(Brain&, const std::string& source, const std::string& event_id,
             const std::string& method = "local", const Provider& provider = {});
Json read(Brain&, const std::string& source, const std::string& query = "",
          int limit = 10, int max_bytes = 8192, const std::string& event_id = "");
Json drain(Brain&, const std::string& source, const std::string& method = "local", int limit = 8);
Json forget(Brain&, const std::string& source, const std::string& event_id);
// Pure validation seam shared by runtime and adversarial provider tests.
Json validate_candidates(const Json& messages, const Json& candidates, const std::string& mode);
bool contains_sensitive_material(const std::string& text);
}
