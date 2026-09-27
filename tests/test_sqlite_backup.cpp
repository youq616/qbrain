#include "qbrain/maintenance/sqlite_backup.hpp"
#include <functional>
#include <thread>
#include <atomic>
using namespace qbrain::maintenance;
namespace b = qbrain::maintenance::backup;
using J = b::Json;
namespace fs = std::filesystem;
namespace {
int checks = 0;
void check(bool condition, const char* label) { if (!condition) throw std::runtime_error(label); ++checks; }
void rejects(const std::function<void()>& action, const char* code = nullptr) {
  try { action(); } catch (const b::Error& e) {
    check(code == nullptr || std::string(e.what()) == code, e.what()); return;
  } catch (const fs::filesystem_error&) { check(code == nullptr, "unexpected filesystem exception"); return; }
  throw std::runtime_error("rejection expected");
}
struct Connection {
  sqlite3* p = nullptr;
  explicit Connection(const fs::path& file) {
    if (sqlite3_open(b::utf8(file).c_str(), &p) != SQLITE_OK) throw std::runtime_error("fixture open");
  }
  ~Connection() { if (p) sqlite3_close(p); }
  void sql(const char* text) { if (sqlite3_exec(p, text, nullptr, nullptr, nullptr) != SQLITE_OK) throw std::runtime_error(sqlite3_errmsg(p)); }
  long long number(const char* sql) {
    sqlite3_stmt* st = nullptr;
    if (sqlite3_prepare_v2(p, sql, -1, &st, nullptr) != SQLITE_OK) throw std::runtime_error("fixture prepare");
    const int rc = sqlite3_step(st); long long n = rc == SQLITE_ROW ? sqlite3_column_int64(st, 0) : -1;
    sqlite3_finalize(st); if (rc != SQLITE_ROW) throw std::runtime_error("fixture query"); return n;
  }
};
void init(Connection& c) {
  c.sql("CREATE TABLE schema_version(version INTEGER PRIMARY KEY);INSERT INTO schema_version VALUES(13);"
        "CREATE TABLE sources(id TEXT PRIMARY KEY);INSERT INTO sources VALUES('main');"
        "CREATE TABLE pages(id INTEGER PRIMARY KEY,slug TEXT,body BLOB,source_id TEXT REFERENCES sources(id));"
        "INSERT INTO pages VALUES(1,'test',X'0001FF','main');"
        "CREATE VIRTUAL TABLE search USING fts5(body);INSERT INTO search VALUES('wal snapshot unicode');");
}
struct Temp {
  fs::path root;
  Temp() {
    root = fs::temp_directory_path() / fs::u8path("qbrain-backup-\xe4\xb8\xad-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    fs::create_directory(root);
  }
  ~Temp() { std::error_code e; fs::remove_all(root, e); }
};
}
int main() {
  try {
    Temp temp; const auto root = temp.root;
    const auto live = root / "live.db";
    Connection source(live); init(source);
    source.sql("PRAGMA journal_mode=WAL;PRAGMA wal_autocheckpoint=0;"
               "INSERT INTO pages VALUES(2,'COMMITTED-PRIVATE',X'00AB00','main');");
    check(fs::file_size(fs::u8path(b::utf8(live) + "-wal")) > 0, "actual WAL exists");
    const auto before_main = b::read(live, b::database_cap);
    const auto before_wal = b::read(fs::u8path(b::utf8(live) + "-wal"), b::database_cap);
    source.sql("BEGIN IMMEDIATE;INSERT INTO pages VALUES(3,'UNCOMMITTED',X'01','main');");
    auto report = b::create(live, root / "backup");
    const std::string digest = report.at("manifest_sha256");
    check(report["result"] == "CREATED", "create report");
    check(b::read(live, b::database_cap) == before_main, "source main unchanged");
    check(b::read(fs::u8path(b::utf8(live) + "-wal"), b::database_cap) == before_wal, "source WAL unchanged");
    source.sql("ROLLBACK");
    const auto manifest_raw = b::read(root / "backup/manifest.json", b::manifest_cap);
    const auto image = b::read(root / "backup/snapshot.sqlite3", b::database_cap);
    check(qbrain::util::sha256_hex(manifest_raw) == digest, "external digest");
    check(image[18] == 1 && image[19] == 1, "self-contained rollback journal");
    check(report.dump().find("PRIVATE") == std::string::npos && report.dump().find(b::utf8(root)) == std::string::npos, "body/path-free result");
    check(b::verify(root / "backup", digest)["result"] == "VERIFIED", "verify");
    check(b::read(root / "backup/snapshot.sqlite3", b::database_cap) == image, "verify unchanged database");
    check(b::read(root / "backup/manifest.json", b::manifest_cap) == manifest_raw, "verify unchanged manifest");
    auto restored = b::restore(root / "backup", digest, root / "recovered");
    check(restored["result"] == "RESTORED_TO_NEW_DIRECTORY", "restore result");
    check(b::read(root / "recovered/brain.db", b::database_cap) == image, "restored bytes exact");
    { Connection db(root / "recovered/brain.db");
      check(db.number("SELECT count(*) FROM pages") == 2, "committed only");
      check(db.number("SELECT count(*) FROM search WHERE search MATCH 'snapshot'") == 1, "FTS remains usable");
      check(db.number("SELECT hex(body)='00AB00' FROM pages WHERE id=2") == 1, "BLOB including NUL exact"); }
    rejects([&]{ b::create(live, root / "backup"); }, "backup_output_exists");
    rejects([&]{ b::restore(root / "backup", digest, root / "recovered"); }, "backup_output_exists");
    rejects([&]{ b::restore(root / "backup", digest, root / "backup/nested"); }, "backup_output_inside_source");
    rejects([&]{ b::verify(root / "backup", std::string(64,'a')); }, "backup_manifest_digest");
    for (const auto& value : {"", "abc", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"})
      rejects([&]{ b::verify(root / "backup", value); }, "backup_expected_digest");
    for (int ms : {0, 99, 120001}) rejects([&]{ b::create(live, root / "invalid-time", ms); }, "backup_timeout_range");
    for (const auto& value : {"", "../other.db", "file:memory?mode=memory"}) {
      rejects([&]{ b::create(b::path(value), root / "invalid-path"); });
    }
    rejects([&]{ b::path(std::string("abc\0def", 7)); }, "backup_path");
    check(!fs::exists(root / "invalid-path"), "invalid input makes no output");
    { b::Budget budget(100); b::Db db(root / "backup/snapshot.sqlite3", false, budget);
      budget.end = std::chrono::steady_clock::now();
      rejects([&]{ db.close(); }, "backup_timeout");
      check(db.db == nullptr, "closed handle cleared even when deadline check throws"); }
    // Corrupted/rehashed manifests cannot bypass the externally pinned digest.
    auto clone = [&](const char* name) {
      auto target = root / name; fs::create_directory(target);
      b::write_new(target / "snapshot.sqlite3", image); b::write_new(target / "manifest.json", manifest_raw); return target;
    };
    auto bad = clone("extra"); b::write_new(bad / "extra", "private");
    rejects([&]{ b::verify(bad, digest); }, "backup_inventory");
    bad = clone("missing"); fs::remove(bad / "snapshot.sqlite3");
    rejects([&]{ b::verify(bad, digest); }, "backup_inventory");
    bad = clone("changed");
    { std::fstream f(bad / "snapshot.sqlite3", std::ios::binary|std::ios::in|std::ios::out); f.seekp(72); f.put('\x7f'); }
    rejects([&]{ b::verify(bad, digest); }, "backup_database_digest");
    for (const char* name : {"extra-field", "bool-size", "wrong-version", "changed-database", "encrypted", "wrong-scope"}) {
      bad = clone(name); auto m = J::parse(manifest_raw);
      if (std::string(name) == "extra-field") m["extra"] = "secret";
      else if (std::string(name) == "bool-size") m["database_bytes"] = true;
      else if (std::string(name) == "wrong-version") m["qbrain_schema_version"] = 12;
      else if (std::string(name) == "changed-database") m["database"] = "../live.db";
      else if (std::string(name) == "encrypted") m["encrypted"] = true;
      else m["scope"] = "full_brain";
      fs::remove(bad / "manifest.json"); auto raw = b::encode(m); b::write_new(bad / "manifest.json", raw);
      rejects([&]{ b::verify(bad, digest); }, "backup_manifest_digest");
      rejects([&]{ b::verify(bad, qbrain::util::sha256_hex(raw)); }, "backup_manifest_content");
    }
    bad = clone("duplicate"); auto raw = std::string("{\"schema\":\"bad\",") + manifest_raw.substr(1);
    fs::remove(bad / "manifest.json"); b::write_new(bad / "manifest.json", raw);
    rejects([&]{ b::verify(bad, qbrain::util::sha256_hex(raw)); }, "backup_manifest_json");
    bad = clone("oversized"); fs::remove(bad / "manifest.json"); b::write_new(bad / "manifest.json", std::string(8193, ' '));
    rejects([&]{ b::verify(bad, digest); }, "backup_size_limit");
    // Integrity checks reject logical FK violations; partial work has no acceptance marker.
    { Connection invalid(root / "fk.db"); init(invalid); invalid.sql("INSERT INTO pages VALUES(2,'bad',NULL,'missing');");
      rejects([&]{ b::create(root / "fk.db", root / "fk-out"); }, "backup_foreign_keys");
      check(!fs::exists(root / "fk-out/manifest.json"), "no success marker after failed verification"); }
    { Connection invalid(root / "version.db"); init(invalid);
      for (int n : {0, 14}) { invalid.sql(("UPDATE schema_version SET version=" + std::to_string(n)).c_str());
        rejects([&]{ b::create(root / "version.db", root / "version-out"); }, "backup_schema_version"); }
      check(!fs::exists(root / "version-out"), "unsupported schema before output"); }
    { Connection invalid(root / "unrelated.db"); invalid.sql("CREATE TABLE something(a)");
      rejects([&]{ b::create(root / "unrelated.db", root / "unrelated-out"); }, "backup_not_qbrain"); }
    b::write_new(root / "not-sqlite", "not a sqlite database");
    rejects([&]{ b::create(root / "not-sqlite", root / "garbage-out"); }, "backup_sqlite");
    // An exclusive rollback-journal writer cannot produce a falsely completed snapshot.
    { Connection locked(root / "locked.db"); init(locked); locked.sql("BEGIN EXCLUSIVE;");
      const auto start = std::chrono::steady_clock::now();
      rejects([&]{ b::create(root / "locked.db", root / "lock-out", 100); }, "backup_timeout");
      check(std::chrono::steady_clock::now() - start < std::chrono::seconds(5), "busy deadline finite");
      locked.sql("ROLLBACK;"); check(!fs::exists(root / "lock-out"), "lock rejection no output"); }
#ifndef _WIN32
    fs::create_symlink(live, root / "link.db");
    rejects([&]{ b::create(root / "link.db", root / "link-out"); }, "backup_link_or_missing");
    fs::create_hard_link(live, root / "hard.db");
    rejects([&]{ b::create(live, root / "hard-out"); }, "backup_hard_link"); fs::remove(root / "hard.db");
    fs::create_directory_symlink(root / "backup", root / "link-dir");
    rejects([&]{ b::verify(root / "link-dir", digest); }, "backup_link_or_missing");
#endif
    std::cout << J{{"schema","qbrain-sqlite-backup-direct-v1"},{"passed",checks},{"failed",0}}.dump() << '\n';
    return 0;
  } catch (const std::exception& e) { std::cerr << "FAIL after " << checks << ": " << e.what() << '\n'; return 1; }
}
