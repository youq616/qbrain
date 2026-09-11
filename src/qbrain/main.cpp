#include "qbrain/cli/app.hpp"
#ifdef _WIN32
#include "qbrain/util/paths.hpp"
#include <fcntl.h>
#include <io.h>
#include <cstdio>
#include <iostream>
#include <vector>
int wmain(int argc, wchar_t** argv) {
  try {
    std::vector<std::string> values; values.reserve(argc);
    for (int i=0; i<argc; ++i) values.push_back(qbrain::util::wide_to_utf8(argv[i]));
    std::vector<char*> utf8; utf8.reserve(argc+1);
    for (auto& value : values) utf8.push_back(value.data());
    utf8.push_back(nullptr);
    // The protocols are UTF-8 bytes, not CRT locale text (also preserve CRLF payloads).
    if (_setmode(_fileno(stdin), _O_BINARY) == -1 || _setmode(_fileno(stdout), _O_BINARY) == -1)
      return 2;
    return qbrain::cli::run(argc, utf8.data());
  } catch (...) { std::cerr << "invalid native Unicode command line\n"; return 2; }
}
#else
int main(int argc, char** argv) { return qbrain::cli::run(argc, argv); }
#endif
