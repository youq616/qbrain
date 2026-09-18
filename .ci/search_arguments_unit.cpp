#include "qbrain/cli/search_arguments.hpp"
#include <algorithm>
#include <iostream>

using qbrain::cli::parse_search_arguments;
int checks = 0;
void need(bool ok) { ++checks; if (!ok) throw std::runtime_error("check " + std::to_string(checks)); }
void rejects(std::vector<std::string> a, const std::string& code) {
  try { (void)parse_search_arguments(a); }
  catch (const std::invalid_argument& e) { need(e.what() == code); return; }
  need(false);
}
int main() {
  try {
    for (const auto& q : {"--", "--brain", "--json", "--mode", "--rerank", "--rerank-llm", "--no-vector", "--limit", "--query", "--brain=decoy", "  literal\t\r\n", "中文😀"}) {
      for (int form = 0; form < 3; ++form) {
        auto a = form == 0 ? std::vector<std::string>{"--query", q} :
                 form == 1 ? std::vector<std::string>{std::string("--query=")+q} :
                             std::vector<std::string>{"--", q};
        a.insert(a.begin(), {"--brain", "intended", "--limit", "3", "--json"});
        auto r = parse_search_arguments(a);
        need(r.query == (form == 2 ? qbrain::util::trim(q) : q));
        need(r.value("--brain") == "intended");
        need(r.value("--limit") == "3");
        need(r.flags == std::set<std::string>{"--json"});
        need(r.brain_args() == std::vector<std::string>({"--brain", "intended"}));
      }
    }
    for (const auto& limit : {"", "0", "-1", "+1", "0005", "100", "101", "2147483647", "-2147483648"})
      need(parse_search_arguments({"q", "--limit", limit}).value("--limit") == limit);
    for (const auto& limit : {"+", "-", "+-1", " 5", "5 ", "1x", "1.0", "2147483648", "-2147483649", "99999999999999999999"})
      rejects({"q", "--limit", limit}, "invalid_search_limit");
    for (const auto& mode : {"", "balanced", "conservative", "tokenmax"})
      need(parse_search_arguments({"q", "--mode", mode}).value("--mode") == mode);
    rejects({"q", "--mode", "typo"}, "invalid_search_mode");
    for (const auto& opt : {"--brain", "--limit", "--mode", "--query"}) {
      rejects({"q", opt}, "missing_search_value");
      if (std::string(opt) != "--query") rejects({"q", opt, "--json"}, "missing_search_value");
    }
    for (const auto& opt : {"--brain", "--limit", "--mode", "--query"})
      rejects({opt, "x", std::string(opt)+"=y"}, "duplicate_search_argument");
    for (const auto& opt : {"--json", "--no-vector", "--rerank", "--rerank-llm"}) {
      rejects({"q", opt, opt}, "duplicate_search_argument");
      rejects({"q", std::string(opt)+"=true"}, "invalid_search_argument");
    }
    for (const auto& opt : {"--bogus", "--bogus=1", "--source", "--brain sentinelneedle"})
      rejects({"q", opt}, "invalid_search_argument");
    for (auto a : {std::vector<std::string>{}, {"--"}, {"--query", ""}, {"\t\r\n"}, {"--query= "}})
      rejects(a, "search_query_required");
    rejects({"x", "--query", "y"}, "mixed_search_query");
    rejects({"--query", "x", "--", "y"}, "mixed_search_query");
    need(parse_search_arguments({"--brain=--json", "q"}).brain_args() == std::vector<std::string>({"--brain", "--json"}));
    need(parse_search_arguments({"--query", "--"}).query == "--");
    need(parse_search_arguments({"--", "--", "--json"}).query == "-- --json");
    need(parse_search_arguments({"hello", "", "--json", "world"}).query == "hello  world");
    need(parse_search_arguments({"  hello ", "--json", "world  "}).query == "hello  world");
    need(parse_search_arguments({"-h"}).query == "-h");
    need(parse_search_arguments({"q"}).brain_args().empty());
    std::vector<std::vector<std::string>> groups={{"--query","--brain"},{"--brain","intended"},{"--limit","2"},{"--json"},{"--mode","conservative"}};
    std::vector<int> order={0,1,2,3,4};
    do {
      std::vector<std::string> a;
      for(int k:order) a.insert(a.end(),groups[k].begin(),groups[k].end());
      auto r=parse_search_arguments(a);
      need(r.query=="--brain" && r.value("--brain")=="intended" && r.value("--limit")=="2" && r.flags==std::set<std::string>{"--json"});
    } while(std::next_permutation(order.begin(),order.end()));
    std::cout << "SEARCH_ARGUMENTS_UNIT_PASS checks=" << checks << "\n";
    return 0;
  } catch(const std::exception& e) { std::cerr << e.what() << "\n"; return 1; }
}
