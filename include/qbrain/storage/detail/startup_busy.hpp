#pragma once
#include <sqlite3.h>
#include <algorithm>
#include <chrono>
#include <stdexcept>

namespace qbrain::storage::detail {
// Used only on a newly opened connection, before any caller installs a handler.
// One deadline covers all setup statements; normal operation reverts to fail-fast.
// It bounds lock waiting, not total filesystem work or OS scheduling latency.
class StartupBusyWait {
  using Clock = std::chrono::steady_clock;
  sqlite3* db_;
  Clock::time_point deadline_;
  static int wait(void* context, int) noexcept {
    auto& self = *static_cast<StartupBusyWait*>(context);
    const auto now = Clock::now();
    if (now >= self.deadline_) return 0;
    const auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(
        self.deadline_ - now).count();
    sqlite3_sleep(static_cast<int>(std::clamp<decltype(remaining)>(remaining, 1, 10)));
    return Clock::now() < self.deadline_ ? 1 : 0;
  }
 public:
  explicit StartupBusyWait(sqlite3* db) : db_(db),
      deadline_(Clock::now() + std::chrono::milliseconds(2500)) {
    if (sqlite3_busy_handler(db_, wait, this) != SQLITE_OK)
      throw std::runtime_error("Cannot set SQLite startup busy handler");
  }
  StartupBusyWait(const StartupBusyWait&) = delete;
  StartupBusyWait& operator=(const StartupBusyWait&) = delete;
  ~StartupBusyWait() { sqlite3_busy_handler(db_, nullptr, nullptr); }
};
}  // namespace qbrain::storage::detail
