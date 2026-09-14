#pragma once
#include "qbrain/core/brain.hpp"
#include <nlohmann/json.hpp>
#include <set>
#include <string>

namespace qbrain::integration::detail {
// Pure composition relative to an existing Brain: reads only. Caller controls
// opt-in and project identity. Output bytes include the complete Hook envelope.
nlohmann::json compose_fact_context(Brain& brain, const std::string& source,
    const std::string& event, const std::string& prompt, int budget, int limit,
    const std::set<std::string>& seen = {});
}
