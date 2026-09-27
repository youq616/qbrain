#pragma once
// N48N: audit a pinned backup's canonical full-text index, never repair it.
#include "qbrain/maintenance/sqlite_backup.hpp"
#include <cstring>
#include <memory>

namespace qbrain::maintenance::search_audit {
namespace b = backup;
using Json = b::Json;

// Only whitespace/case OUTSIDE quoted literals is normalized. In particular,
// content='pa ges' must never be accepted as content='pages'.
inline std::string normalized_sql(const std::string& sql) {
  std::string out;
  char quote = 0;
  for (std::size_t i = 0; i < sql.size(); ++i) {
    char c = sql[i];
    if (quote) {
      out.push_back(c);
      if (c == quote) {
        if (i + 1 < sql.size() && sql[i + 1] == quote) out.push_back(sql[++i]);
        else quote = 0;
      }
    } else if (c == '\'' || c == '"' || c == '`' || c == '[') {
      quote = c == '[' ? ']' : c;
      out.push_back(c);
    } else if (c != ' ' && c != '\n' && c != '\r' && c != '\t' && c != '\f') {
      out.push_back(c >= 'A' && c <= 'Z' ? static_cast<char>(c + ('a' - 'A')) : c);
    }
  }
  return out;
}
inline const std::map<std::string, std::string>& expected_definitions() {
  static const std::map<std::string, std::string> definitions = {
    {"pages_fts", "CREATE VIRTUAL TABLE pages_fts USING fts5(slug,title,body,content='pages',content_rowid='id',tokenize='unicode61')"},
    {"pages_ai", "CREATE TRIGGER pages_ai AFTER INSERT ON pages BEGIN INSERT INTO pages_fts(rowid,slug,title,body) VALUES(new.id,new.slug,new.title,new.body); END"},
    {"pages_ad", "CREATE TRIGGER pages_ad AFTER DELETE ON pages BEGIN INSERT INTO pages_fts(pages_fts,rowid,slug,title,body) VALUES('delete',old.id,old.slug,old.title,old.body); END"},
    {"pages_au", "CREATE TRIGGER pages_au AFTER UPDATE ON pages BEGIN INSERT INTO pages_fts(pages_fts,rowid,slug,title,body) VALUES('delete',old.id,old.slug,old.title,old.body); INSERT INTO pages_fts(rowid,slug,title,body) VALUES(new.id,new.slug,new.title,new.body); END"}
  };
  return definitions;
}
inline bool canonical(b::Db& db, const std::string& name) {
  sqlite3_stmt* stmt = nullptr;
  const auto rc = sqlite3_prepare_v2(db.db, "SELECT sql FROM sqlite_schema WHERE name=?1", -1, &stmt, nullptr);
  struct Guard { sqlite3_stmt* p; ~Guard() { sqlite3_finalize(p); } } guard{stmt};
  db.check(rc);
  db.check(sqlite3_bind_text(stmt, 1, name.c_str(), -1, SQLITE_TRANSIENT));
  const auto step = sqlite3_step(stmt); db.check(step);
  if (step == SQLITE_DONE) return false;
  const auto* text = sqlite3_column_text(stmt, 0);
  const auto size = sqlite3_column_bytes(stmt, 0);
  if (text == nullptr || size > 8192) return false;
  const std::string sql(reinterpret_cast<const char*>(text), static_cast<std::size_t>(size));
  const auto end = sqlite3_step(stmt); db.check(end);
  return end == SQLITE_DONE && normalized_sql(sql) == normalized_sql(expected_definitions().at(name));
}
struct SqliteFree { void operator()(unsigned char* p) const { sqlite3_free(p); } };
struct MemoryImage {
  // Declared before db: connection destruction MUST precede buffer destruction.
  std::unique_ptr<unsigned char, SqliteFree> buffer;
  b::Db db;
  MemoryImage(const std::string& image, b::Budget& budget)
      : buffer(static_cast<unsigned char*>(sqlite3_malloc64(image.size() + 65568))),
        db(std::filesystem::path(":memory:"), true, budget) {
    b::need(buffer != nullptr, "search_audit_memory");
    std::memcpy(buffer.get(), image.data(), image.size());
    std::memset(buffer.get() + image.size(), 0, 65568);
    // Caller owns fixed-capacity buffer; SQLite neither frees nor reallocates it.
    db.check(sqlite3_deserialize(db.db, "main", buffer.get(),
             static_cast<sqlite3_int64>(image.size()),
             static_cast<sqlite3_int64>(image.size() + 65568), 0));
    db.check(sqlite3_db_config(db.db, SQLITE_DBCONFIG_ENABLE_TRIGGER, 0, nullptr));
    db.check(sqlite3_extended_result_codes(db.db, 1));
    db.exec("PRAGMA temp_store=MEMORY");
  }
  MemoryImage(const MemoryImage&) = delete;
  MemoryImage& operator=(const MemoryImage&) = delete;
};
inline Json audit(const std::filesystem::path& folder, const std::string& expected,
                  int timeout = 10000) {
  b::Budget budget(timeout);
  const auto verified = b::load(folder, expected, budget);
  MemoryImage memory(verified.image, budget);
  auto& db = memory.db;
  Json report = {
    {"schema", "qbrain-backup-search-audit-v1"}, {"result", "UNSUPPORTED"},
    {"manifest_sha256", expected}, {"database_sha256", verified.meta.at("database_sha256")},
    {"database_bytes", verified.meta.at("database_bytes")},
    {"qbrain_schema_version", verified.meta.at("qbrain_schema_version")},
    {"scope", "canonical_pages_fts_all_sources"}, {"index", "pages_fts"},
    {"backup_verified", true}, {"fts_content_consistent", nullptr},
    {"maintenance_triggers_verified", nullptr}, {"pages_checked", nullptr},
    {"issues", Json::array()}, {"input_modified", false}, {"repair_performed", false},
    {"registry_changed", false}, {"provider_requests_sent", 0},
    {"application_semantics_verified", false}, {"source_authenticated", false}
  };
  const bool layout = db.scalar("SELECT count(*) FROM pragma_table_list WHERE schema='main' AND name='pages' AND type='table' AND wr=0") == "1" &&
      db.scalar("SELECT count(*) FROM pragma_table_xinfo('pages') WHERE (name='id' AND type='INTEGER' AND pk=1 AND hidden=0) OR (name IN ('slug','title','body') AND type='TEXT' AND hidden=0)") == "4";
  if (!layout || !canonical(db, "pages_fts")) {
    report["issues"].push_back("unsupported_search_schema");
    db.close(); return report;
  }
  bool triggers = true;
  for (const auto& name : {"pages_ai", "pages_ad", "pages_au"}) {
    if (!canonical(db, name)) {
      triggers = false;
      report["issues"].push_back(std::string("noncanonical_") + name);
    }
  }
  // Unexpected extra triggers are not covered by the canonical maintenance claim.
  if (db.scalar("SELECT count(*) FROM sqlite_schema WHERE type='trigger' AND tbl_name='pages' COLLATE NOCASE AND name NOT IN ('pages_ai','pages_ad','pages_au')") != "0") {
    triggers = false; report["issues"].push_back("additional_pages_triggers");
  }
  report["maintenance_triggers_verified"] = triggers;
  report["pages_checked"] = std::stoull(db.scalar("SELECT count(*) FROM pages"));
  // COUNT(*) on external-content pages_fts does NOT validate the index. Rank=1 does.
  const auto rc = sqlite3_exec(db.db,
      "INSERT INTO pages_fts(pages_fts,rank) VALUES('integrity-check',1)", nullptr, nullptr, nullptr);
  const auto extended = sqlite3_extended_errcode(db.db);
  budget.check();
  if (rc == SQLITE_OK) report["fts_content_consistent"] = true;
  else if (extended == SQLITE_CORRUPT_VTAB) {
    report["fts_content_consistent"] = false;
    report["issues"].push_back("fts_index_content_mismatch_or_corruption");
  } else throw b::Error("search_audit_sqlite");
  report["result"] = triggers && report["fts_content_consistent"].get<bool>() ? "PASS" : "FAIL";
  db.close(); budget.check();
  return report;
}
inline int command(const std::vector<std::string>& args) {
  try {
    b::need(!args.empty() && args[0] == "audit-search", "search_audit_arguments");
    std::map<std::string, std::string> options;
    for (std::size_t i = 1; i < args.size(); i += 2) {
      b::need(i + 1 < args.size() && !args[i + 1].empty(), "search_audit_arguments");
      b::need(options.emplace(args[i], args[i + 1]).second, "search_audit_arguments");
    }
    int timeout = 10000;
    if (options.count("--timeout-ms")) {
      const auto& value = options.at("--timeout-ms");
      b::need(value.size() <= 6 && std::all_of(value.begin(), value.end(), [](char c) { return c >= '0' && c <= '9'; }), "backup_timeout_range");
      timeout = std::stoi(value); options.erase("--timeout-ms");
    }
    b::Budget checked(timeout);
    b::need(options.size() == 2 && options.count("--backup") && options.count("--expect-sha256"), "search_audit_arguments");
    const auto report = audit(b::path(options.at("--backup")), options.at("--expect-sha256"), timeout);
    std::cout << b::encode(report);
    return report["result"] == "PASS" ? 0 : (report["result"] == "FAIL" ? 1 : 2);
  } catch (const b::Error& e) { std::cout << b::encode(Json{{"error", {{"code", e.what()}}}}); }
  catch (...) { std::cout << "{\"error\":{\"code\":\"search_audit_local_failure\"}}\n"; }
  return 2;
}
} // namespace qbrain::maintenance::search_audit
