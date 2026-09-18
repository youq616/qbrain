#include "qbrain/cli/search_arguments.hpp"
#include <algorithm>
#include <iostream>
#include <utility>

using qbrain::cli::parse_search_arguments;
static int checks = 0;
static void check(bool ok, const char* message) {
  ++checks;
  if (!ok) throw std::runtime_error(message);
}
static void rejected(std::vector<std::string> args, const std::string& code) {
  try { (void)parse_search_arguments(args); }
  catch (const std::invalid_argument& e) { check(std::string(e.what()).find(code) == 0, "wrong rejection"); return; }
  check(false, "accepted invalid arguments");
}
int main() {
  try {
    const std::vector<std::string> literals = {"--brain", "--json", "--no-vector", "--rerank", "--rerank-llm", "--mode", "--limit", "--", "--query", "--unknown=value", "中文 😀", "  raw\ttext  "};
    for (const auto& text : literals) {
      for (const bool attached : {false, true}) {
        std::vector<std::string> argv = {"--brain", "intended", "--no-vector"};
        if (attached) argv.push_back("--query=" + text);
        else { argv.push_back("--query"); argv.push_back(text); }
        const auto p = parse_search_arguments(argv);
        check(p.query == text, "explicit literal changed");
        check(p.values.at("--brain") == "intended", "brain retargeted");
        check(p.flags == std::set<std::string>{"--no-vector"}, "data toggled flags");
      }
    }
    auto p = parse_search_arguments({"--brain", "intended", "--", "--brain", "shadow", "--json", "--mode", "tokenmax", "--rerank-llm"});
    check(p.query == "--brain shadow --json --mode tokenmax --rerank-llm", "delimiter lost data");
    check(p.flags.empty() && p.values.size() == 1 && p.values.at("--brain") == "intended", "delimiter flags leak");
    p = parse_search_arguments({"--brain=--json", "--query=x=y", "--mode=conservative", "--limit=2"});
    check(p.values.at("--brain") == "--json" && p.query == "x=y" && p.flags.empty(), "attached value corrupted");
    check(p.values.at("--limit") == "2" && p.values.at("--mode") == "conservative", "attached option lost");
    p = parse_search_arguments({"  first", "--json", "second  ", "--mode", "balanced"});
    check(p.query == "first second" && p.flags.count("--json"), "positional compatibility");
    check(parse_search_arguments({"-x", "-", "--no-vector"}).query == "-x -", "short tokens should be positional");
    check(parse_search_arguments({"--query=", "--json"}).query.empty(), "explicit empty changed");
    check(parse_search_arguments({"--brain", "", "--query", "x"}).values.at("--brain").empty(), "empty brain not retained");
    const std::vector<std::pair<std::vector<std::string>, std::string>> bad = {
      {{"--brain", "--no-vector", "needle"}, "search_option_value_required"},
      {{"--limit", "--", "needle"}, "search_option_value_required"},
      {{"--mode"}, "search_option_value_required"}, {{"--query"}, "search_option_value_required"},
      {{"--bad"}, "unknown_search_option"}, {{"--source", "x"}, "unknown_search_option"},
      {{"--brain sentinel"}, "unknown_search_option"}, {{"--json=true", "x"}, "search_flag_has_value"},
      {{"--no-vector=false", "x"}, "search_flag_has_value"},
      {{"--query=x", "--query", "y"}, "duplicate_search_option"},
      {{"--brain=x", "--brain", "y", "x"}, "duplicate_search_option"},
      {{"--rerank", "--rerank", "x"}, "duplicate_search_option"},
      {{"--query=x", "y"}, "mixed_search_query_forms"},
      {{"x", "--query=y"}, "mixed_search_query_forms"},
      {{"--query=x", "--", "y"}, "mixed_search_query_forms"},
      {{"--query=x", ""}, "mixed_search_query_forms"}
    };
    for (const auto& [args, code] : bad) rejected(args, code);
    // All orderings of five actual option groups must yield the same exact parse.
    std::vector<int> order = {0, 1, 2, 3, 4};
    const std::vector<std::vector<std::string>> groups = {{"--query", "--brain"}, {"--brain", "intended"}, {"--mode", "conservative"}, {"--json"}, {"--no-vector"}};
    do {
      std::vector<std::string> argv;
      for (const auto i : order) argv.insert(argv.end(), groups[i].begin(), groups[i].end());
      p = parse_search_arguments(argv);
      check(p.query == "--brain" && p.values.at("--brain") == "intended" && p.values.at("--mode") == "conservative" && p.flags == std::set<std::string>{"--json", "--no-vector"}, "permutation changed settings");
    } while (std::next_permutation(order.begin(), order.end()));
    std::cout << "SEARCH_ARGUMENTS_PASS checks=" << checks << "\n";
  } catch (const std::exception& e) { std::cerr << "SEARCH_ARGUMENTS_FAIL " << e.what() << "\n"; return 1; }
}
