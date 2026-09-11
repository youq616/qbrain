#include "qbrain/codeintel/astlite.hpp"
#include <nlohmann/json.hpp>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
using namespace qbrain::codeintel::astlite;
namespace fs = std::filesystem;

static std::string read(const fs::path& path) {
  std::ifstream input(path, std::ios::binary);
  if (!input) throw std::runtime_error("fixture missing: " + path.string());
  std::ostringstream out;
  out << input.rdbuf();
  return out.str();
}
static std::string lf_copy(const std::string& body) {
  std::string out;
  for (std::size_t i = 0; i < body.size(); ++i) {
    if (body[i] == '\r' && i + 1 < body.size() && body[i + 1] == '\n') continue;
    out += body[i];
  }
  return out;
}
static std::string crlf_copy(const std::string& body) {
  std::string out;
  for (char c : lf_copy(body)) {
    if (c == '\n') out += '\r';
    out += c;
  }
  return out;
}
int main(int argc, char** argv) {
  try {
    if (argc != 2) throw std::runtime_error("fixture directory required");
    int checks = 0;
    for (const std::string stem : {"cpp_traps", "ts_traps"}) {
      const bool cpp = stem == "cpp_traps";
      const fs::path root(argv[1]);
      const auto raw = read(root / (stem + (cpp ? ".cpp" : ".ts")));
      const auto golden = nlohmann::json::parse(read(root / (stem + ".json")));
      for (const auto& body : {lf_copy(raw), crlf_copy(raw)}) {
        const auto first = to_json(parse_content(body, cpp ? Language::Cpp : Language::TypeScript));
        if (nlohmann::json::parse(first) != golden)
          throw std::runtime_error(stem + " newline golden mismatch");
        if (first != to_json(parse_content(body, cpp ? Language::Cpp : Language::TypeScript)))
          throw std::runtime_error(stem + " nondeterministic parse");
        checks += 2;
      }
    }
    for (const std::string text : {std::string(), std::string("#"),
                                   std::string("#define X \\\r"),
                                   std::string("#define X \\\r\n")}) {
      (void)parse_content(text, Language::Cpp);
      ++checks;
    }
    std::cout << "PASS newline parity, unchanged goldens and bounded EOF: " << checks << " checks\n";
    return 0;
  } catch (const std::exception& e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
