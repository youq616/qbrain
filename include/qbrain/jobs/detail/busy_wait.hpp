#pragma once
#include "qbrain/storage/database.hpp"
#include <algorithm>

namespace qbrain::jobs::detail {
// Existing SQLite connections default to immediate SQLITE_BUSY. Queue claims
// and short commit transactions tolerate transient competing writers without
// changing the caller's connection policy after the operation. PostgreSQL has
// its own backend lock timeout and never receives SQLite PRAGMAs.
class ScopedQueueBusyWait {
  storage::Database& db_;
  int previous_ = 0;
  bool changed_ = false;
 public:
  explicit ScopedQueueBusyWait(storage::Database& db) : db_(db) {
    if (db_.backend_kind() != storage::BackendKind::sqlite) return;
    {
      auto statement = db_.prepare("PRAGMA busy_timeout");
      if (statement.step()) previous_ = static_cast<int>(statement.column_int(0));
    }
    const int bounded = previous_ > 0 ? std::min(previous_, 2000) : 2000;
    if (bounded != previous_) {
      db_.exec("PRAGMA busy_timeout=" + std::to_string(bounded));
      changed_ = true;
    }
  }
  ScopedQueueBusyWait(const ScopedQueueBusyWait&) = delete;
  ScopedQueueBusyWait& operator=(const ScopedQueueBusyWait&) = delete;
  ~ScopedQueueBusyWait() {
    if (changed_) {
      try { db_.exec("PRAGMA busy_timeout=" + std::to_string(previous_)); }
      catch (...) { /* No exception may escape a transaction unwinder. */ }
    }
  }
};
} // namespace qbrain::jobs::detail
