#pragma once
#include <nlohmann/json.hpp>
#include <cstddef>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace qbrain::util {
// Fixed diagnostics only: never include an untrusted key/value in an exception.
enum class JsonInputFailure { duplicate_key, depth_limit, byte_limit, raw_nul };
class JsonInputError final : public std::runtime_error {
 public:
  explicit JsonInputError(JsonInputFailure failure)
      : std::runtime_error("json_input_rejected"), failure_(failure) {}
  JsonInputFailure failure() const noexcept { return failure_; }
 private:
  JsonInputFailure failure_;
};

// Validate raw input before a map can overwrite repeated decoded object keys.
// max_depth is the vendored parser callback depth (including keys/values), not
// a budget for string contents. Distinct sibling objects have distinct key sets.
inline nlohmann::json parse_unique_json(std::string_view raw, std::size_t max_bytes,
                                        int max_depth) {
  if (raw.size() > max_bytes) throw JsonInputError(JsonInputFailure::byte_limit);
  // Some parser paths interpret raw NUL as end-of-input. Escaped \\u0000 remains
  // legal JSON string content and participates in full-length key comparison.
  if (raw.find('\0') != std::string_view::npos)
    throw JsonInputError(JsonInputFailure::raw_nul);
  std::vector<std::set<std::string>> objects;
  using J = nlohmann::json;
  return J::parse(raw.begin(), raw.end(), [&](int depth, J::parse_event_t event, J& value) {
    if (depth > max_depth) throw JsonInputError(JsonInputFailure::depth_limit);
    if (event == J::parse_event_t::object_start) objects.emplace_back();
    else if (event == J::parse_event_t::key) {
      if (objects.empty() || !objects.back().insert(value.get<std::string>()).second)
        throw JsonInputError(JsonInputFailure::duplicate_key);
    } else if (event == J::parse_event_t::object_end) {
      if (objects.empty()) throw JsonInputError(JsonInputFailure::depth_limit);
      objects.pop_back();
    }
    // Never use false to reject: the library may silently discard that value.
    return true;
  });
}
}  // namespace qbrain::util
