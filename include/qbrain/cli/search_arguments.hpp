#pragma once

#include "qbrain/util/string_util.hpp"
#include <charconv>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace qbrain::cli {

// Search-only grammar. Parsing is pure and must finish before opening a brain.
struct SearchArguments {
  std::string query;
  std::map<std::string, std::string> values;
  std::set<std::string> flags;

  std::string value(const std::string& key, const std::string& fallback = {}) const {
    const auto it = values.find(key);
    return it == values.end() ? fallback : it->second;
  }
  std::vector<std::string> brain_args() const {
    return values.count("--brain") ? std::vector<std::string>{"--brain", value("--brain")}
                                    : std::vector<std::string>{};
  }
};

inline SearchArguments parse_search_arguments(const std::vector<std::string>& args) {
  const std::set<std::string> value_keys = {"--brain", "--limit", "--mode", "--query"};
  const std::set<std::string> flag_keys = {"--json", "--no-vector", "--rerank", "--rerank-llm"};
  SearchArguments out;
  std::set<std::string> seen;
  bool literal = false, has_positional = false;
  std::string positional;
  for (std::size_t i = 0; i < args.size(); ++i) {
    const auto& arg = args[i];
    if (!literal && arg == "--") { literal = true; continue; }
    if (literal || arg.rfind("--", 0) != 0) {
      has_positional = true;
      // Preserve the legacy positional join, including empty argv elements.
      if (!positional.empty()) positional.push_back(' ');
      positional += arg;
      continue;
    }
    const auto eq = arg.find('=');
    const auto key = arg.substr(0, eq);
    if (!value_keys.count(key) && !flag_keys.count(key))
      throw std::invalid_argument("invalid_search_argument");
    if (!seen.insert(key).second) throw std::invalid_argument("duplicate_search_argument");
    if (flag_keys.count(key)) {
      if (eq != std::string::npos) throw std::invalid_argument("invalid_search_argument");
      out.flags.insert(key);
      continue;
    }
    std::string value;
    if (eq != std::string::npos) value = arg.substr(eq + 1);
    else {
      // --query always consumes one literal argv, even "--" or a switch name.
      // For other values, use --key=VALUE to represent a leading -- literally.
      if (i + 1 == args.size() ||
          (key != "--query" && args[i + 1].rfind("--", 0) == 0))
        throw std::invalid_argument("missing_search_value");
      value = args[++i];
    }
    out.values.emplace(key, std::move(value));
  }
  if (out.values.count("--query")) {
    if (has_positional) throw std::invalid_argument("mixed_search_query");
    out.query = out.value("--query");
  } else out.query = util::trim(positional);
  if (util::trim(out.query).empty()) throw std::invalid_argument("search_query_required");

  const auto limit = out.value("--limit");
  if (!limit.empty()) {
    // Empty retains the old configuration default. Other values must fit int;
    // range clamping (including zero/negative values) stays in the search op.
    const char* first = limit.data();
    const char* last = first + limit.size();
    if (*first == '+') ++first;
    int number = 0;
    const auto parsed = std::from_chars(first, last, number);
    if (first == last || (limit[0] == '+' && *first == '-') ||
        parsed.ec != std::errc{} || parsed.ptr != last)
      throw std::invalid_argument("invalid_search_limit");
  }
  const auto mode = out.value("--mode");
  if (!mode.empty() && mode != "balanced" && mode != "conservative" && mode != "tokenmax")
    throw std::invalid_argument("invalid_search_mode");
  return out;
}

}  // namespace qbrain::cli
