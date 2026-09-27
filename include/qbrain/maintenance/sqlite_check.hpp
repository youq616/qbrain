#pragma once
// N48N: explicit local diagnostics. All deep checks run on a private RAM snapshot.
#include "qbrain/maintenance/sqlite_backup.hpp"
#include "qbrain/storage/schema_sql.hpp"
#include <memory>
#include <optional>
#include <utility>

namespace qbrain::maintenance::check {
namespace b = qbrain::maintenance::backup;
using Json = nlohmann::json;
namespace fs = std::filesystem;
struct SqlError { int code; };

// No error messages from SQLite or the filesystem are included in public reports.
class Memory {
 public:
  sqlite3* db = nullptr;
  b::Budget& budget;
  explicit Memory(b::Budget& value) : budget(value) {
    int rc = sqlite3_open_v2(":memory:", &db,
        SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_NOMUTEX, nullptr);
    if (rc != SQLITE_OK) { sqlite3_close(db); db = nullptr; throw SqlError{rc}; }
    try {
      sqlite3_extended_result_codes(db, 1);
      sqlite3_progress_handler(db, 1000, b::Budget::progress, &budget);
      sqlite3_busy_handler(db, b::Budget::busy, &budget);
      for (int flag : {SQLITE_DBCONFIG_DEFENSIVE, SQLITE_DBCONFIG_TRUSTED_SCHEMA,
                       SQLITE_DBCONFIG_ENABLE_TRIGGER, SQLITE_DBCONFIG_ENABLE_VIEW})
        test(sqlite3_db_config(db, flag, flag == SQLITE_DBCONFIG_DEFENSIVE ? 1 : 0, nullptr));
      sqlite3_limit(db, SQLITE_LIMIT_LENGTH, static_cast<int>(b::database_cap));
      sqlite3_limit(db, SQLITE_LIMIT_SQL_LENGTH, 1048576);
      exec("PRAGMA temp_store=MEMORY");
      exec("PRAGMA mmap_size=0");
      exec("PRAGMA cell_size_check=ON");
    } catch (...) { sqlite3_close_v2(db); db = nullptr; throw; }
  }
  Memory(const Memory&) = delete;
  Memory& operator=(const Memory&) = delete;
  ~Memory() { if (db) sqlite3_close_v2(db); }
  void test(int rc) {
    budget.check();
    if (rc != SQLITE_OK && rc != SQLITE_ROW && rc != SQLITE_DONE) throw SqlError{rc};
  }
  void exec(const std::string& sql) { test(sqlite3_exec(db, sql.c_str(), nullptr, nullptr, nullptr)); }
};
class Statement {
  Memory& owner;
 public:
  sqlite3_stmt* stmt = nullptr;
  Statement(Memory& db, const char* sql, const std::vector<std::string>& args = {}) : owner(db) {
    try {
      owner.test(sqlite3_prepare_v2(db.db, sql, -1, &stmt, nullptr));
      int i = 1;
      for (const auto& value : args)
        owner.test(sqlite3_bind_text(stmt, i++, value.c_str(), static_cast<int>(value.size()), SQLITE_TRANSIENT));
    } catch (...) { sqlite3_finalize(stmt); stmt = nullptr; throw; }
  }
  Statement(const Statement&) = delete;
  Statement& operator=(const Statement&) = delete;
  ~Statement() { sqlite3_finalize(stmt); }
  bool next() { int rc = sqlite3_step(stmt); owner.test(rc); return rc == SQLITE_ROW; }
  std::string text(int column = 0) {
    if (sqlite3_column_type(stmt, column) != SQLITE_TEXT || sqlite3_column_bytes(stmt, column) > 65536)
      throw SqlError{SQLITE_MISMATCH};
    const auto* value = sqlite3_column_text(stmt, column);
    if (!value) throw SqlError{SQLITE_NOMEM};
    return {reinterpret_cast<const char*>(value), static_cast<std::size_t>(sqlite3_column_bytes(stmt, column))};
  }
  sqlite3_int64 integer(int column = 0) {
    if (sqlite3_column_type(stmt, column) != SQLITE_INTEGER) throw SqlError{SQLITE_MISMATCH};
    return sqlite3_column_int64(stmt, column);
  }
};
inline sqlite3_int64 number(Memory& db, const char* sql, const std::vector<std::string>& args = {}) {
  Statement s(db, sql, args);
  if (!s.next()) throw SqlError{SQLITE_MISMATCH};
  auto result = s.integer();
  if (s.next()) throw SqlError{SQLITE_MISMATCH};
  return result;
}
inline std::optional<std::string> definition(Memory& db, const std::string& name, const std::string& type) {
  Statement s(db, "SELECT sql FROM main.sqlite_schema WHERE name=? AND type=?", {name, type});
  if (!s.next()) return std::nullopt;
  auto value = s.text();
  if (s.next()) return std::nullopt;
  return value;
}

// Token boundaries and string-literal bytes are retained. This is intentionally
// conservative: equivalent but noncanonical SQL can require manual review.
inline std::vector<std::string> sql_tokens(const std::string& sql) {
  std::vector<std::string> out;
  auto word = [](unsigned char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
           (c >= '0' && c <= '9') || c == '_' || c == '$' || c >= 128;
  };
  for (std::size_t i = 0; i < sql.size();) {
    const unsigned char c = static_cast<unsigned char>(sql[i]);
    if (c == ' ' || c == '\t' || c == '\r' || c == '\n' || c == '\f') { ++i; continue; }
    if (i + 1 < sql.size() && sql[i] == '-' && sql[i+1] == '-') {
      i = sql.find('\n', i+2); if (i == std::string::npos) break; continue;
    }
    if (i + 1 < sql.size() && sql[i] == '/' && sql[i+1] == '*') {
      auto end = sql.find("*/", i+2);
      if (end == std::string::npos) return {"INVALID_UNCLOSED_COMMENT"};
      i = end+2; continue;
    }
    const auto begin = i++;
    if (c == '\'' || c == '"' || c == '`' || c == '[') {
      const char closing = c == '[' ? ']' : static_cast<char>(c);
      bool ended = false;
      while (i < sql.size()) {
        if (sql[i++] == closing) {
          if (c != '[' && i < sql.size() && sql[i] == closing) { ++i; continue; }
          ended = true; break;
        }
      }
      if (!ended) return {"INVALID_UNCLOSED_QUOTE"};
      out.push_back(sql.substr(begin, i-begin));
    } else if (word(c)) {
      while (i < sql.size() && word(static_cast<unsigned char>(sql[i]))) ++i;
      auto token = sql.substr(begin, i-begin);
      for (char& v : token) if (v >= 'A' && v <= 'Z') v = static_cast<char>(v-'A'+'a');
      out.push_back(std::move(token));
    } else { out.push_back(sql.substr(begin, 1)); }
  }
  if (!out.empty() && out.back() == ";") out.pop_back();
  return out;
}
inline bool canonical(Memory& actual, Memory& reference, const char* name, const char* type) {
  const auto want = definition(reference, name, type);
  if (!want) throw SqlError{SQLITE_INTERNAL};
  const auto got = definition(actual, name, type);
  return got && sql_tokens(*got) == sql_tokens(*want);
}
inline std::vector<std::string> core_inventory(Memory& db) {
  std::vector<std::string> issues;
  // The known v13 inventory, not a claim of complete DDL/business equivalence.
  const std::map<std::string, std::vector<std::string>> tables = {
    {"schema_version", {"version"}}, {"sources", {"id"}},
    {"pages", {"id", "source_id", "slug", "title", "body", "deleted_at", "source_kind", "ingested_via", "ingested_at"}},
    {"content_chunks", {"page_id"}}, {"tags", {"page_id"}}, {"page_versions", {"page_id"}},
    {"links", {}}, {"config", {}}, {"jobs", {"lock_token", "error_text", "parent_id", "depth"}},
    {"ingest_log", {"source_id"}}, {"job_messages", {"job_id"}},
    {"facts", {"entity_slug"}}, {"takes", {"entity_slug"}}, {"file_index", {"path"}}, {"raw_data", {"key"}}
  };
  for (const auto& [table, columns] : tables) {
    if (number(db, "SELECT count(*) FROM pragma_table_list WHERE schema='main' AND name=? AND type='table'", {table}) != 1) {
      issues.push_back("missing_or_nonordinary_table:" + table); continue;
    }
    for (const auto& column : columns)
      if (number(db, "SELECT count(*) FROM pragma_table_xinfo(?) WHERE name=? AND hidden=0", {table, column}) != 1)
        issues.push_back("missing_column:" + table + "." + column);
  }
  const std::map<std::string, std::string> indexes = {
    {"idx_pages_type","pages"}, {"idx_pages_updated","pages"}, {"idx_pages_source","pages"},
    {"idx_pages_source_slug","pages"}, {"idx_chunks_page","content_chunks"}, {"idx_chunks_missing_emb","content_chunks"},
    {"idx_links_from","links"}, {"idx_links_to","links"}, {"idx_jobs_claim","jobs"}, {"idx_jobs_status","jobs"},
    {"idx_ingest_log_source_created","ingest_log"}, {"idx_job_messages_job","job_messages"},
    {"idx_page_versions_page","page_versions"}, {"idx_facts_entity","facts"},
    {"idx_takes_entity","takes"}, {"idx_takes_body","takes"}, {"idx_file_index_name","file_index"},
    {"idx_raw_data_key","raw_data"}, {"idx_jobs_parent","jobs"}
  };
  for (const auto& [index, table] : indexes)
    if (number(db, "SELECT count(*) FROM main.sqlite_schema WHERE name=? AND tbl_name=? AND type='index'", {index, table}) != 1)
      issues.push_back("missing_index:" + index);
  if (issues.empty()) {
    if (number(db, "SELECT count(*) FROM schema_version WHERE typeof(version)!='integer' OR version<1 OR version>13") != 0 ||
        number(db, "SELECT coalesce(max(version),0) FROM schema_version") != 13 ||
        number(db, "SELECT count(*)-count(DISTINCT version) FROM schema_version") != 0)
      issues.push_back("unsupported_schema_version");
  }
  return issues;
}
inline std::vector<std::string> page_relations(Memory& db) {
  std::vector<std::string> issues;
  if (number(db, "SELECT count(*) FROM pages p WHERE p.source_id IS NULL OR NOT EXISTS(SELECT 1 FROM sources s WHERE s.id=p.source_id)") != 0)
    issues.push_back("page_source_orphans");
  for (const auto* table : {"content_chunks", "tags", "page_versions"}) {
    const auto sql = std::string("SELECT count(*) FROM ") + table +
      " c WHERE c.page_id IS NULL OR NOT EXISTS(SELECT 1 FROM pages p WHERE p.id=c.page_id)";
    if (number(db, sql.c_str()) != 0) issues.push_back(std::string("page_child_orphans:") + table);
  }
  if (number(db, "SELECT count(*) FROM (SELECT source_id,slug FROM pages GROUP BY source_id,slug HAVING count(*)>1)") != 0)
    issues.push_back("duplicate_source_slug");
  return issues;
}
inline Json empty_report() {
  Json r = {{"schema", "qbrain-database-check-v1"}, {"result", "ERROR"},
    {"scope", "sqlite_storage_and_pages_fts"}, {"snapshot", "private_memory_committed_transaction"},
    {"source_open_mode", "read_only"}, {"source_repaired", false}, {"registry_changed", false},
    {"provider_requests_sent", 0}, {"all_application_invariants_verified", false},
    {"source_authenticated", false}, {"sqlite_bookkeeping_may_create_sidecars", true}, {"checks", Json::array()}};
  for (const char* id : {"sqlite_integrity", "foreign_keys", "core_inventory", "page_relations",
                         "fts_definition", "fts_triggers", "fts_content"})
    r["checks"].push_back({{"id", id}, {"status", "NOT_RUN"}, {"issues", Json::array()}});
  return r;
}
inline std::string translate(const std::string& code) {
  return code.rfind("backup_", 0) == 0 ? "database_" + code.substr(7) : "database_local_failure";
}
inline Json inspect(const fs::path& input, int timeout = 10000) {
  Json report = empty_report();
  try {
    b::Budget budget(timeout);
    b::regular_path(input); b::sidecars(input);
    b::need(fs::file_size(input) > 0 && fs::file_size(input) <= b::database_cap, "backup_size_limit");
    Memory image(budget);
    {
      b::Db source(input, false, budget);
      b::need(sqlite3_db_readonly(source.db, "main") == 1, "backup_read_only");
      for (int flag : {SQLITE_DBCONFIG_ENABLE_TRIGGER, SQLITE_DBCONFIG_ENABLE_VIEW})
        source.check(sqlite3_db_config(source.db, flag, 0, nullptr));
      source.exec("PRAGMA query_only=ON;PRAGMA mmap_size=0;PRAGMA temp_store=MEMORY;PRAGMA cell_size_check=ON;BEGIN");
      (void)source.scalar("SELECT count(*) FROM sqlite_schema"); // Pin before size/copy.
      const auto pages = std::stoull(source.scalar("PRAGMA page_count"));
      const auto size = std::stoull(source.scalar("PRAGMA page_size"));
      b::need(size >= 512 && size <= 65536 && (size & (size-1)) == 0 && pages > 0 && pages <= b::database_cap / size, "backup_size_limit");
      image.exec("PRAGMA page_size=" + std::to_string(size));
      image.exec("PRAGMA max_page_count=" + std::to_string(b::database_cap / size));
      sqlite3_backup* raw = sqlite3_backup_init(image.db, "main", source.db, "main");
      b::need(raw != nullptr, "backup_snapshot_init");
      std::unique_ptr<sqlite3_backup, decltype(&sqlite3_backup_finish)> handle(raw, sqlite3_backup_finish);
      int rc = SQLITE_OK;
      do {
        budget.check(); rc = sqlite3_backup_step(handle.get(), 128);
        if (rc == SQLITE_BUSY || rc == SQLITE_LOCKED) sqlite3_sleep(5);
      } while (rc == SQLITE_OK || rc == SQLITE_BUSY || rc == SQLITE_LOCKED);
      const auto finished = sqlite3_backup_finish(handle.release());
      budget.check(); b::need(rc == SQLITE_DONE && finished == SQLITE_OK, "backup_snapshot_copy");
      source.exec("ROLLBACK"); source.close(); // Release live source before expensive checks.
      report["snapshot_bytes"] = pages * size;
    }
    auto run = [&](std::size_t index, auto operation) {
      std::vector<std::string> issues;
      try { issues = operation(); }
      catch (const SqlError& e) {
        const int code = e.code & 255;
        if (code != SQLITE_CORRUPT && code != SQLITE_NOTADB && code != SQLITE_MISMATCH) throw;
        issues.push_back("invalid_database_structure");
      }
      budget.check();
      report["checks"][index]["issues"] = issues;
      report["checks"][index]["status"] = issues.empty() ? "PASS" : "FAIL";
      return issues.empty();
    };
    const auto intact = run(0, [&] {
      Statement s(image, "PRAGMA integrity_check(1)");
      const bool ok = s.next() && s.text() == "ok" && !s.next();
      return ok ? std::vector<std::string>{} : std::vector<std::string>{"sqlite_integrity_failed"};
    });
    if (intact) {
      run(1, [&] { return number(image, "SELECT count(*) FROM pragma_foreign_key_check") == 0 ?
        std::vector<std::string>{} : std::vector<std::string>{"foreign_key_violations"}; });
      const bool core = run(2, [&] { return core_inventory(image); });
      if (core) run(3, [&] { return page_relations(image); });
      Memory reference(budget);
      reference.exec(qbrain::storage::kCanonicalSchemaSql);
      const bool layout = run(4, [&] { return canonical(image, reference, "pages_fts", "table") ?
        std::vector<std::string>{} : std::vector<std::string>{"noncanonical_pages_fts"}; });
      run(5, [&] {
        std::vector<std::string> issues;
        for (const char* name : {"pages_ai", "pages_ad", "pages_au"})
          if (!canonical(image, reference, name, "trigger")) issues.push_back(std::string("noncanonical_trigger:") + name);
        return issues;
      });
      if (core && layout) run(6, [&] {
        // This INSERT is exclusively on the disposable memory image, never source.
        image.exec("INSERT INTO pages_fts(pages_fts,rank) VALUES('integrity-check',1)");
        return std::vector<std::string>{};
      });
    }
    budget.check();
    bool passed = true;
    for (const auto& check : report["checks"]) if (check["status"] != "PASS") passed = false;
    report["result"] = passed ? "CHECK_PASSED" : "CHECK_FAILED";
  } catch (const b::Error& e) { report["error"] = {{"code", translate(e.what())}}; }
    catch (const SqlError& e) { report["error"] = {{"code", "database_sqlite_failure"}, {"sqlite_code", e.code}}; }
    catch (...) { report["error"] = {{"code", "database_local_failure"}}; }
  return report;
}
inline int command(const std::vector<std::string>& args) {
  Json report;
  try {
    b::need(!args.empty() && args[0] == "check" && args.size() <= 5 && args.size() % 2 == 1, "backup_arguments");
    std::map<std::string, std::string> options;
    for (std::size_t i = 1; i < args.size(); i += 2) {
      b::need((args[i] == "--database" || args[i] == "--timeout-ms") && !args[i+1].empty() &&
              options.emplace(args[i], args[i+1]).second, "backup_arguments");
    }
    b::need(options.count("--database") == 1, "backup_arguments");
    int timeout = 10000;
    if (options.count("--timeout-ms")) {
      const auto& value = options.at("--timeout-ms");
      b::need(value.size() <= 6 && std::all_of(value.begin(), value.end(), [](char c) { return c >= '0' && c <= '9'; }), "backup_timeout_range");
      timeout = std::stoi(value);
    }
    report = inspect(b::path(options.at("--database")), timeout);
  } catch (const b::Error& e) { report = empty_report(); report["error"] = {{"code", translate(e.what())}}; }
    catch (...) { report = empty_report(); report["error"] = {{"code", "database_local_failure"}}; }
  std::cout << report.dump() << '\n';
  return report["result"] == "CHECK_PASSED" ? 0 : (report["result"] == "CHECK_FAILED" ? 1 : 2);
}
} // namespace qbrain::maintenance::check
