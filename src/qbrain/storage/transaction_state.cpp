#include "qbrain/storage/database.hpp"
#include "qbrain/storage/pg_backend.hpp"
#include <stdexcept>

namespace qbrain::storage {
// One compiled definition: PG macros need not propagate to unrelated libraries.
// The raw connection is inspected only inside storage, never returned to memory.
bool Database::transaction_active() const {
  if (!is_open()) return false;
  if (backend_kind() == BackendKind::sqlite)
    return sqlite3_get_autocommit(handle()) == 0;
#ifdef QBRAIN_WITH_PG
  if (auto* pg = pg_conn_of(*backend_))
    return PQtransactionStatus(pg) != PQTRANS_IDLE;
#endif
  throw std::runtime_error("transaction state unavailable");
}
} // namespace qbrain::storage
