// Dedicated diagnostic driver: numeric lifetimes only; never provider data.
#include "qbrain/ai/http_client.hpp"
#include "qbrain/ai/detail/http_diagnostics.hpp"
#include <nlohmann/json.hpp>
#include <chrono>
#include <iostream>
#include <thread>
#include <string>
#ifdef _WIN32
#include <windows.h>
#endif
using J = nlohmann::json;
int main() {
#ifndef _WIN32
  std::cerr << "Native Windows required\n"; return 2;
#else
  try {
    std::string line;
    while (std::getline(std::cin, line)) {
      if (line.size() > 16384) throw std::runtime_error("command too large");
      const auto command = J::parse(line);
      const int count = command.value("count", 32);
      if (count < 0 || count > 128) throw std::runtime_error("invalid batch size");
      int timeout_count = 0;
      for (int n = 0; n < count; ++n) {
        auto result = qbrain::ai::http_post_json(command.at("base").get<std::string>(),
            "/stall", "synthetic-token", "{}", 40, 1024);
        if (result.failure == qbrain::ai::HttpFailure::timeout && result.status == 0 && result.body.empty())
          ++timeout_count;
      }
      // Same observation points as the original fixture. No retries for green.
      std::this_thread::sleep_for(std::chrono::milliseconds(250));
      DWORD early = 0, settled = 0;
      if (!GetProcessHandleCount(GetCurrentProcess(), &early)) throw std::runtime_error("handle count");
      std::this_thread::sleep_for(std::chrono::milliseconds(1750));
      if (!GetProcessHandleCount(GetCurrentProcess(), &settled)) throw std::runtime_error("handle count");
      const auto d = qbrain::ai::detail::http_diagnostics();
      std::cout << J({{"timeout_count",timeout_count},{"requested",count},
        {"handles_at_250ms",early},{"handles_at_2000ms",settled},
        {"opened",d.handles_opened},{"closed",d.handles_closed},{"close_errors",d.close_errors},
        {"states_created",d.states_created},{"states_destroyed",d.states_destroyed},
        {"final_callbacks",d.final_callbacks},{"callbacks_without_parents",d.callbacks_without_parents}}).dump() << std::endl;
    }
    return 0;
  } catch (...) { std::cerr << "Lifecycle probe failed\n"; return 1; }
#endif
}
