#pragma once
// N48T: only owned SQLite cache triggers are upgraded, during summary publication.
// PostgreSQL deliberately retains its separately qualified source-wide policy.
#include "qbrain/context/context.hpp"
#include <array>
#include <map>
#include <string>

namespace qbrain::context::sqlite_cache {
using DB = storage::Database;
enum class Policy { absent, source_v1, directory_v2 };

inline const std::array<std::string, 3>& legacy_triggers() {
  static const std::array<std::string, 3> sql = {
    "CREATE TRIGGER ctx_page_insert AFTER INSERT ON pages BEGIN\n UPDATE context_cache SET dirty=1,l0='',l1='',refs_json='[]' WHERE source_id=NEW.source_id; END",
    "CREATE TRIGGER ctx_page_update AFTER UPDATE ON pages BEGIN\n UPDATE context_cache SET dirty=1,l0='',l1='',refs_json='[]' WHERE source_id=NEW.source_id OR source_id=OLD.source_id; END",
    "CREATE TRIGGER ctx_page_delete AFTER DELETE ON pages BEGIN\n UPDATE context_cache SET dirty=1,l0='',l1='',refs_json='[]' WHERE source_id=OLD.source_id; END"
  };
  return sql;
}

inline std::string member(const std::string& row) {
  // uri is a validated directory ending in '/'. instr is literal and case-sensitive;
  // do not use LIKE: '_' and case differences are real path components.
  return "context_cache.source_id=" + row + ".source_id AND instr('qbrain://' || " +
    row + ".source_id || '/' || CASE WHEN " + row + ".type='session_fragment' THEN 'memories' WHEN " +
    row + ".type='skill' THEN 'skills' ELSE 'resources' END || '/' || " + row + ".slug,context_cache.uri)=1";
}

inline const std::array<std::string, 3>& directory_triggers() {
  static const auto sql = [] {
    const std::string erase = "UPDATE context_cache SET dirty=1,l0='',l1='',refs_json='[]' WHERE ";
    // SQLite REPLACE may delete a conflicting row without firing DELETE triggers.
    // Observe those victims BEFORE mutation, not just the new row's namespace.
    const std::string victims = erase + "EXISTS(SELECT 1 FROM pages AS displaced WHERE "
      "(displaced.id=NEW.id OR (displaced.source_id=NEW.source_id AND displaced.slug=NEW.slug)) AND (" +
      member("displaced") + ")); ";
    return std::array<std::string, 3>{
      "CREATE TRIGGER ctx_page_insert BEFORE INSERT ON pages BEGIN " + victims + erase + member("NEW") + "; END",
      "CREATE TRIGGER ctx_page_update BEFORE UPDATE ON pages BEGIN " + victims + erase + "(" + member("OLD") + ") OR (" + member("NEW") + "); END",
      "CREATE TRIGGER ctx_page_delete AFTER DELETE ON pages BEGIN " + erase + member("OLD") + "; END"
    };
  }();
  return sql;
}

inline constexpr const char* cache_table = R"SQL(CREATE TABLE context_cache(source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,uri TEXT NOT NULL,
 signature TEXT NOT NULL,l0 TEXT NOT NULL,l1 TEXT NOT NULL,refs_json TEXT NOT NULL,page_count INTEGER NOT NULL,
 method TEXT NOT NULL,dirty INTEGER NOT NULL DEFAULT 0,partial INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(source_id,uri)))SQL";

inline std::string trim_ddl(std::string sql) {
  // Do not erase internal whitespace or quoted bytes; only SQLite's optional final
  // semicolon and external whitespace may differ from the owned statement.
  const auto first = sql.find_first_not_of(" \t\r\n");
  if (first == std::string::npos) return "";
  sql.erase(0, first);
  while (!sql.empty() && (sql.back() == ';' || sql.back() == ' ' || sql.back() == '\t' ||
                         sql.back() == '\r' || sql.back() == '\n')) sql.pop_back();
  return sql;
}

inline void idle(DB& db) {
  if (db.transaction_pending()) throw memory::Error("context_transaction_active");
}
inline void namespace_check(DB& db) {
  auto temp = db.prepare("SELECT 1 FROM temp.sqlite_master WHERE type IN ('table','view') AND "
    "name COLLATE NOCASE IN ('sources','pages','config','context_cache') LIMIT 1");
  if (temp.step()) throw memory::Error("context_sqlite_schema_context");
  auto core = db.prepare("SELECT count(*) FROM main.sqlite_master WHERE type='table' AND "
    "name COLLATE NOCASE IN ('sources','pages','config')");
  if (!core.step() || core.column_int(0)!=3) throw memory::Error("context_sqlite_schema_context");
}

inline Policy policy(DB& db) {
  if (db.backend_kind() != storage::BackendKind::sqlite) throw memory::Error("context_backend_unsupported");
  namespace_check(db);
  auto table = db.prepare("SELECT type,sql FROM main.sqlite_master WHERE name COLLATE NOCASE='context_cache'");
  const bool exists = table.step();
  if (exists && (table.column_text(0) != "table" || trim_ddl(table.column_text(1)) != cache_table))
    throw memory::Error("context_schema_version_unsupported");
  const std::array<std::string, 3> names = {"ctx_page_insert", "ctx_page_update", "ctx_page_delete"};
  std::map<std::string, std::string> found;
  auto rows = db.prepare("SELECT name,tbl_name,sql FROM main.sqlite_master WHERE type='trigger' "
                        "AND name COLLATE NOCASE IN ('ctx_page_insert','ctx_page_update','ctx_page_delete')");
  while (rows.step()) {
    if (rows.column_text(1) != "pages") throw memory::Error("context_schema_incomplete");
    found.emplace(rows.column_text(0), trim_ddl(rows.column_text(2)));
  }
  if (!exists) {
    if (!found.empty()) throw memory::Error("context_schema_conflict");
    return Policy::absent;
  }
  if (found.size() != names.size()) throw memory::Error("context_schema_incomplete");
  bool legacy = true, scoped = true;
  for (std::size_t i = 0; i != names.size(); ++i) {
    if (!found.count(names[i])) throw memory::Error("context_schema_incomplete");
    legacy = legacy && found.at(names[i]) == legacy_triggers()[i];
    scoped = scoped && found.at(names[i]) == directory_triggers()[i];
  }
  if (scoped) return Policy::directory_v2;
  if (legacy) return Policy::source_v1;
  throw memory::Error("context_schema_incomplete");
}

struct ReadSnapshot {
  DB& db; bool owned=false;
  explicit ReadSnapshot(DB& value):db(value) {
    if (db.backend_kind()!=storage::BackendKind::sqlite) return;
    idle(db);
    db.exec("BEGIN"); owned=true;
    try { (void)policy(db); }
    catch (...) { finish(); throw; }
  }
  void finish() { if (owned) { db.exec("ROLLBACK"); owned=false; } }
  ~ReadSnapshot() { if (owned) try { db.exec("ROLLBACK"); } catch (...) {} }
  ReadSnapshot(const ReadSnapshot&)=delete;
  ReadSnapshot& operator=(const ReadSnapshot&)=delete;
};

inline void initialize_locked(DB& db) {
  // Caller has BEGIN IMMEDIATE and has revalidated evidence and permission.
  // Never take over/commit an arbitrary caller transaction here.
  if (!db.transaction_active()) throw memory::Error("context_transaction_required");
  const auto current = policy(db);
  if (current == Policy::directory_v2) return;
  if (current == Policy::absent) db.exec(cache_table);
  else {
    for (const auto* name : {"ctx_page_insert", "ctx_page_update", "ctx_page_delete"})
      db.exec(std::string("DROP TRIGGER ") + name);
    // One-time legacy reset. Unknown/custom trigger layouts never reach this path.
    db.exec("UPDATE context_cache SET dirty=1,l0='',l1='',refs_json='[]'");
  }
  for (const auto& trigger : directory_triggers()) db.exec(trigger);
}
} // namespace qbrain::context::sqlite_cache
