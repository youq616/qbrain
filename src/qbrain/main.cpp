#include "qbrain/cli/app.hpp"
#include "qbrain/accounting/token_cost.hpp"
#include "qbrain/accounting/provider_usage.hpp"
#include "qbrain/integration/mcp_probe.hpp"
#include "qbrain/integration/opencode_audit.hpp"

namespace {
// Dispatch the explicit isolated checker before registry/default-brain setup.
int dispatch(int argc,char** argv) {
  if(argc>1 && std::string(argv[1])=="cost") {
    std::vector<std::string> args;for(int i=2;i<argc;++i)args.emplace_back(argv[i]);
    if(!args.empty() && args[0]=="import") return qbrain::accounting::usage_import::command(args);
    return qbrain::accounting::command(args);
  }
  if(argc>1 && std::string(argv[1])=="mcp-check") {
    std::vector<std::string> args;for(int i=2;i<argc;++i)args.emplace_back(argv[i]);
    return qbrain::integration::probe::command(args);
  }
  if(argc>1 && std::string(argv[1])=="opencode") {
    std::vector<std::string> args;for(int i=2;i<argc;++i)args.emplace_back(argv[i]);
    if(!args.empty() && args[0]=="audit")
      return qbrain::integration::opencode::audit_command(args);
    return qbrain::integration::opencode::command(args);
  }
  const int result=qbrain::cli::run(argc,argv);
  if(argc==1 || (argc>1 && (std::string(argv[1])=="help" || std::string(argv[1])=="--help" || std::string(argv[1])=="-h")))
    std::cout<<"Additional command: mcp-check preview|run --binary PATH [--timeout-ms N]; run requires --approve-sha256.\n";
  if(argc==1 || (argc>1 && (std::string(argv[1])=="help" || std::string(argv[1])=="--help" || std::string(argv[1])=="-h")))
    std::cout<<"Additional command: opencode preview|install|status|audit|uninstall-preview|uninstall|recovery-preview|recover|reconcile-preview|reconcile --project PATH.\n";
  if(argc==1 || (argc>1 && (std::string(argv[1])=="help" || std::string(argv[1])=="--help" || std::string(argv[1])=="-h")))
    std::cout<<"Additional command: cost report|import (bounded JSON from stdin; no network or brain access).\n";
  return result;
}
}

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
    return dispatch(argc, utf8.data());
  } catch (...) { std::cerr << "invalid native Unicode command line\n"; return 2; }
}
#else
int main(int argc, char** argv) { return dispatch(argc, argv); }
#endif
