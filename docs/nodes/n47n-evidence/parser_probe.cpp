// Separate review adapter: exercise the production parser, not a second parser.
#include "qbrain/cli/search_arguments.hpp"
#include <nlohmann/json.hpp>
#include <iostream>
#include <string>
int main() {
  std::string line;
  while (std::getline(std::cin, line)) {
    try {
      const auto argv = nlohmann::json::parse(line).get<std::vector<std::string>>();
      const auto parsed = qbrain::cli::parse_search_arguments(argv);
      std::cout << nlohmann::json({{"query",parsed.query},{"values",parsed.values},
          {"flags",parsed.flags},{"brain_args",parsed.brain_args()}}).dump() << '\n';
    } catch (const std::invalid_argument& e) {
      std::cout << nlohmann::json({{"error",e.what()}}).dump() << '\n';
    } catch (const std::exception& e) {
      std::cerr << "probe adapter error: " << e.what() << '\n';
      return 2;
    }
  }
  return std::cin.bad() ? 2 : 0;
}
