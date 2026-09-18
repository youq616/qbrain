#pragma once
#include <cctype>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace qbrain::cli {

// Pure search-only parser: callers must never rescan the original argv.
struct SearchArguments {
  std::string query;
  std::map<std::string, std::string> values;
  std::set<std::string> flags;
};

inline SearchArguments parse_search_arguments(const std::vector<std::string>& args) {
  SearchArguments out;
  const std::set<std::string> value_options = {"--brain", "--limit", "--mode", "--query"};
  const std::set<std::string> flag_options = {"--json", "--no-vector", "--rerank", "--rerank-llm"};
  std::set<std::string> seen;
  bool literal = false, has_positional = false;
  std::string positional;
  for (std::size_t i = 0; i < args.size(); ++i) {
    const auto& token = args[i];
    if (!literal && token == "--") { literal = true; continue; }
    if (!literal && token.rfind("--", 0) == 0) {
      const auto equal = token.find('=');
      const auto key = token.substr(0, equal);
      if (!value_options.count(key) && !flag_options.count(key))
        throw std::invalid_argument("unknown_search_option: use --query or -- for literal text");
      if (!seen.insert(key).second) throw std::invalid_argument("duplicate_search_option");
      if (flag_options.count(key)) {
        if (equal != std::string::npos) throw std::invalid_argument("search_flag_has_value");
        out.flags.insert(key);
      } else if (equal != std::string::npos) {
        out.values.emplace(key, token.substr(equal + 1));
      } else {
        if (i + 1 == args.size() || (key != "--query" && args[i + 1].rfind("--", 0) == 0))
          throw std::invalid_argument("search_option_value_required: use --name=value for option-shaped values");
        out.values.emplace(key, args[++i]);
      }
    } else {
      has_positional = true;
      // Preserve the existing positional joining, including explicit empty argv.
      if (!positional.empty()) positional.push_back(' ');
      positional += token;
    }
  }
  if (out.values.count("--query")) {
    if (has_positional) throw std::invalid_argument("mixed_search_query_forms");
    out.query = out.values.at("--query");
  } else {
    const auto first = positional.find_first_not_of(" \t\n\r\f\v");
    if (first != std::string::npos)
      out.query = positional.substr(first, positional.find_last_not_of(" \t\n\r\f\v") - first + 1);
  }
  return out;
}

}  // namespace qbrain::cli
