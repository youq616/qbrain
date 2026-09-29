#pragma once
#include "qbrain/memory/session_memory.hpp"
namespace qbrain::memory::detail {
// Internal composition only, never exposed through CLI/MCP. Requires a live,
// module-owned PG fact READ ONLY REPEATABLE READ snapshot on this connection.
Json read_in_fact_snapshot(Brain&, const std::string& source,
                          const std::string& query, int limit, int budget);
}
