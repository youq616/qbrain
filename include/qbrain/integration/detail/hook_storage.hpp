#pragma once
// Internal Hook admission; no schema initialization, DSN echo or SQLite fallback.
#include "qbrain/core/brain.hpp"
#include "qbrain/storage/pg_backend.hpp"
namespace qbrain::integration::detail {

inline void open_existing_postgres(Brain& brain, const std::string& dsn) {
#if defined(QBRAIN_WITH_PG)
  if (brain.is_open()) throw std::runtime_error("hook_connection_already_open");
  auto& db_=brain.db();
  db_.adopt_backend(storage::make_pg_backend(dsn));
  try {
    // This connection belongs to the Hook; ordinary CLI connections are unchanged.
    db_.exec("SET statement_timeout = 2500");
    auto scope = db_.prepare("SELECT pg_catalog.current_schema(),"
        "pg_catalog.current_setting('server_encoding'),"
        "pg_catalog.current_setting('client_encoding'),"
        "pg_catalog.current_setting('session_replication_role')");
    if (!scope.step() || scope.column_text(0) != "public" ||
        scope.column_text(1) != "UTF8" || scope.column_text(2) != "UTF8" ||
        scope.column_text(3) != "origin") throw std::runtime_error("hook_pg_schema_context");
    auto names = db_.prepare("SELECT count(*) FROM (VALUES ('schema_version'),('sources'),('pages'),('config')) n(name) "
        "WHERE pg_catalog.to_regclass('public.' || name) IS NULL OR "
        "pg_catalog.to_regclass(name) IS DISTINCT FROM pg_catalog.to_regclass('public.' || name)");
    if (!names.step() || names.column_int(0) != 0) throw std::runtime_error("hook_pg_uninitialized");
    auto version = db_.prepare("SELECT COALESCE(MAX(version),0) FROM public.schema_version");
    if (!version.step() || version.column_int(0) != 13) throw std::runtime_error("hook_pg_schema_version");
    // No pg_ensure_schema, migration, source registration or local-directory writes.
    brain.load_config();
  } catch (...) { db_.close(); throw; }
#else
  (void)dsn;
  throw std::runtime_error("hook_pg_build_unsupported");
#endif
}

}
