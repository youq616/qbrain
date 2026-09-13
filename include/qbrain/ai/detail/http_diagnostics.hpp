#pragma once
// Standalone test instrumentation only; not a runtime flag or public MCP tool.
#ifdef QBRAIN_HTTP_DIAGNOSTICS
#include <cstdint>
namespace qbrain::ai::detail {
struct HttpDiagnostics {
  std::uint64_t handles_opened, handles_closed, close_errors;
  std::uint64_t states_created, states_destroyed, final_callbacks;
  std::uint64_t callbacks_without_parents;
};
HttpDiagnostics http_diagnostics() noexcept;
}
#endif
