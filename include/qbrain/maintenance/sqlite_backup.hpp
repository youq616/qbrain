#pragma once
// N48M: explicit, local SQLite-only administration; no Brain/registry initialization.
#include "qbrain/util/hash.hpp"
#include "qbrain/util/strict_json.hpp"
#include <sqlite3.h>
#include <nlohmann/json.hpp>
#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <fcntl.h>
#include <unistd.h>
#endif

namespace qbrain::maintenance::backup {
namespace fs = std::filesystem;
using Json = nlohmann::json;
inline constexpr std::uintmax_t database_cap = 256ULL * 1024 * 1024;
inline constexpr std::size_t manifest_cap = 8192;
struct Error : std::runtime_error { using std::runtime_error::runtime_error; };
inline void need(bool ok, const char* code) { if (!ok) throw Error(code); }
inline std::string utf8(const fs::path& p) {
  const auto s = p.u8string(); return {s.begin(), s.end()};
}
inline bool hex_digest(const std::string& s) {
  return s.size() == 64 && std::all_of(s.begin(), s.end(), [](char c) {
    return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
  });
}
inline fs::path path(const std::string& text) {
  need(!text.empty() && text.size() <= 4096 && text.find('\0') == std::string::npos, "backup_path");
  need(text != ":memory:" && text.rfind("file:", 0) != 0, "backup_path");
  auto p = fs::u8path(text);
  for (const auto& part : p) need(part != "..", "backup_parent_path");
#ifdef _WIN32
  // Local drive files only, not device names, alternate streams or UNC resources.
  const auto root = utf8(p.root_name());
  need(root.empty() || (root.size() == 2 && root[1] == ':' &&
       ((root[0] >= 'a' && root[0] <= 'z') || (root[0] >= 'A' && root[0] <= 'Z'))), "backup_path");
  for (const auto& part : p.relative_path()) {
    const auto s = utf8(part);
    need(s == "." || (s.find_first_of(":<>\"|?*") == std::string::npos &&
         !s.empty() && s.back() != '.' && s.back() != ' '), "backup_path");
  }
#endif
  return fs::absolute(p).lexically_normal();
}
inline void regular_path(const fs::path& p, bool directory = false) {
  fs::path current;
  for (const auto& part : p) {
    current /= part;
    const auto s = fs::symlink_status(current);
    need(fs::exists(s) && !fs::is_symlink(s), "backup_link_or_missing");
#ifdef _WIN32
    const auto attributes = GetFileAttributesW(current.c_str());
    need(attributes != INVALID_FILE_ATTRIBUTES && !(attributes & FILE_ATTRIBUTE_REPARSE_POINT), "backup_link_or_missing");
#endif
  }
  need(directory ? fs::is_directory(p) : fs::is_regular_file(p), "backup_file_type");
  if (!directory) need(fs::hard_link_count(p) == 1, "backup_hard_link");
}
inline void new_directory(const fs::path& p) {
  regular_path(p.parent_path(), true);
  need(!fs::exists(fs::symlink_status(p)), "backup_output_exists");
  need(fs::create_directory(p), "backup_output_exists");
#ifndef _WIN32
  fs::permissions(p, fs::perms::owner_all, fs::perm_options::replace);
#endif
}
inline void external_output(const fs::path& source, const fs::path& out) {
  for (auto p = out.parent_path(); !p.empty(); p = p.parent_path()) {
    need(!fs::equivalent(source, p), "backup_output_inside_source");
    if (p == p.root_path()) break;
  }
}
inline std::string read(const fs::path& p, std::uintmax_t cap) {
  regular_path(p);
  const auto size = fs::file_size(p);
  const auto time = fs::last_write_time(p);
  need(size <= cap, "backup_size_limit");
  std::ifstream in(p, std::ios::binary);
  need(bool(in), "backup_read");
  std::string data(static_cast<std::size_t>(size), '\0');
  in.read(data.data(), static_cast<std::streamsize>(data.size()));
  need(static_cast<std::size_t>(in.gcount()) == data.size() && in.peek() == EOF && !in.bad(), "backup_read");
  need(fs::file_size(p) == size && fs::last_write_time(p) == time, "backup_source_changed");
  return data;
}
// CREATE_NEW / O_EXCL prevents overwriting even an unexpected existing output file.
inline void write_new(const fs::path& p, const std::string& bytes) {
#ifdef _WIN32
  HANDLE h = CreateFileW(p.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW,
                         FILE_ATTRIBUTE_NORMAL, nullptr);
  need(h != INVALID_HANDLE_VALUE, "backup_write");
  std::size_t offset = 0; bool ok = true;
  while (offset < bytes.size()) {
    DWORD n = 0;
    const auto count = static_cast<DWORD>((std::min)(bytes.size() - offset, std::size_t(1048576)));
    if (!WriteFile(h, bytes.data() + offset, count, &n, nullptr) || n == 0) { ok = false; break; }
    offset += n;
  }
  ok = FlushFileBuffers(h) && ok;
  const bool closed = CloseHandle(h) != 0;
#else
  int h = ::open(p.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
  need(h >= 0, "backup_write");
  std::size_t offset = 0; bool ok = true;
  while (offset < bytes.size()) {
    const auto n = ::write(h, bytes.data() + offset, bytes.size() - offset);
    if (n < 0 && errno == EINTR) continue;
    if (n <= 0) { ok = false; break; }
    offset += static_cast<std::size_t>(n);
  }
  ok = (::fsync(h) == 0) && ok;
  const bool closed = ::close(h) == 0;
#endif
  need(ok && closed, "backup_write");
}
struct Budget {
  std::chrono::steady_clock::time_point end;
  explicit Budget(int ms) : end(std::chrono::steady_clock::now() + std::chrono::milliseconds(ms)) {
    need(ms >= 100 && ms <= 120000, "backup_timeout_range");
  }
  bool expired() const { return std::chrono::steady_clock::now() >= end; }
  void check() const { need(!expired(), "backup_timeout"); }
  static int progress(void* p) { return static_cast<Budget*>(p)->expired() ? 1 : 0; }
  static int busy(void* p, int) {
    if (static_cast<Budget*>(p)->expired()) return 0;
    sqlite3_sleep(5); return 1;
  }
};
struct Db {
  sqlite3* db = nullptr;
  Budget& budget;
  Db(const fs::path& p, bool writable, Budget& b) : budget(b) {
    const int flags = (writable ? SQLITE_OPEN_READWRITE : SQLITE_OPEN_READONLY) |
                      SQLITE_OPEN_NOMUTEX | SQLITE_OPEN_NOFOLLOW;
    int rc = sqlite3_open_v2(utf8(p).c_str(), &db, flags, nullptr);
    if (rc != SQLITE_OK) { sqlite3_close(db); db = nullptr; throw Error("backup_open"); }
    sqlite3_busy_handler(db, Budget::busy, &budget);
    sqlite3_progress_handler(db, 1000, Budget::progress, &budget);
    sqlite3_db_config(db, SQLITE_DBCONFIG_DEFENSIVE, 1, nullptr);
    sqlite3_db_config(db, SQLITE_DBCONFIG_TRUSTED_SCHEMA, 0, nullptr);
    sqlite3_limit(db, SQLITE_LIMIT_LENGTH, static_cast<int>(database_cap));
  }
  Db(const Db&) = delete; Db& operator=(const Db&) = delete;
  ~Db() { if (db) sqlite3_close_v2(db); }
  void check(int rc) {
    budget.check();
    need(rc == SQLITE_OK || rc == SQLITE_ROW || rc == SQLITE_DONE, "backup_sqlite");
  }
  void exec(const char* sql) { check(sqlite3_exec(db, sql, nullptr, nullptr, nullptr)); }
  std::string scalar(const char* sql) {
    sqlite3_stmt* stmt = nullptr;
    const int prepared = sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr);
    if (prepared != SQLITE_OK) { sqlite3_finalize(stmt); check(prepared); }
    struct Guard { sqlite3_stmt* s; ~Guard() { sqlite3_finalize(s); } } guard{stmt};
    int rc = sqlite3_step(stmt); check(rc); need(rc == SQLITE_ROW, "backup_sqlite_shape");
    const auto* text = sqlite3_column_text(stmt, 0);
    need(text != nullptr && sqlite3_column_bytes(stmt, 0) <= 128, "backup_sqlite_shape");
    std::string value(reinterpret_cast<const char*>(text), static_cast<std::size_t>(sqlite3_column_bytes(stmt, 0)));
    rc = sqlite3_step(stmt); check(rc); need(rc == SQLITE_DONE, "backup_sqlite_shape");
    return value;
  }
  void close() {
    const auto rc = sqlite3_close(db);
    if (rc == SQLITE_OK) db = nullptr; // Null before deadline checks can throw.
    check(rc);
  }
};
inline int schema_version(Db& db) {
  need(db.scalar("SELECT count(*) FROM sqlite_schema WHERE type='table' AND name IN ('schema_version','pages','sources')") == "3", "backup_not_qbrain");
  const auto version = db.scalar("SELECT coalesce(max(version),0) FROM schema_version");
  need(version.size() <= 2 && !version.empty() && std::all_of(version.begin(), version.end(), [](char c){return c >= '0' && c <= '9';}), "backup_schema_version");
  const auto n = std::stoi(version);
  need(n >= 1 && n <= 13, "backup_schema_version");
  return n;
}
inline int validate(Db& db) {
  const auto version = schema_version(db);
  need(db.scalar("PRAGMA integrity_check(1)") == "ok", "backup_integrity");
  need(db.scalar("SELECT count(*) FROM pragma_foreign_key_check") == "0", "backup_foreign_keys");
  return version;
}
inline void sidecars(const fs::path& p) {
  for (const char* suffix : {"-wal", "-shm", "-journal"}) {
    auto name = p; name += suffix;
    if (fs::exists(fs::symlink_status(name))) regular_path(name);
  }
}
inline void inventory(const fs::path& p) {
  regular_path(p, true);
  std::set<std::string> names;
  for (const auto& entry : fs::directory_iterator(p)) { regular_path(entry.path()); names.insert(utf8(entry.path().filename())); }
  need(names == std::set<std::string>{"snapshot.sqlite3", "manifest.json"}, "backup_inventory");
}
inline Json manifest(const std::string& image, int version) {
  return {{"schema", "qbrain-sqlite-backup-v1"}, {"engine", "sqlite"}, {"database", "snapshot.sqlite3"},
    {"database_bytes", image.size()}, {"database_sha256", util::sha256_hex(image)},
    {"qbrain_schema_version", version}, {"scope", "database_only_all_sources"}, {"encrypted", false},
    {"sqlite_integrity_checked", true}, {"foreign_keys_checked", true}, {"source_authenticated", false}};
}
inline std::string encode(const Json& j) { return j.dump() + "\n"; }
inline Json result(const char* status, const Json& m, const std::string& manifest_hash) {
  return {{"schema", "qbrain-backup-result-v1"}, {"result", status}, {"manifest_sha256", manifest_hash},
    {"database_sha256", m.at("database_sha256")}, {"database_bytes", m.at("database_bytes")},
    {"qbrain_schema_version", m.at("qbrain_schema_version")}, {"scope", "database_only_all_sources"},
    {"encrypted", false}, {"registry_changed", false}, {"source_authenticated", false},
    {"application_semantics_verified", false}, {"provider_requests_sent", 0}};
}
inline Json create(const fs::path& input, const fs::path& output, int timeout = 10000) {
  Budget budget(timeout);
  regular_path(input); sidecars(input);
  need(fs::file_size(input) > 0 && fs::file_size(input) <= database_cap, "backup_size_limit");
  Db source(input, false, budget);
  source.exec("BEGIN");
  (void)schema_version(source);  // Establish the read snapshot before checking size/copying.
  const auto pages = std::stoull(source.scalar("PRAGMA page_count"));
  const auto size = std::stoull(source.scalar("PRAGMA page_size"));
  need(size >= 512 && size <= 65536 && pages > 0 && pages <= database_cap / size, "backup_size_limit");
  new_directory(output);
  const auto file = output / "snapshot.sqlite3";
  write_new(file, ""); // Reserve only our new database file; SQLite cannot overwrite another file.
  Db dest(file, true, budget);
  sqlite3_backup* handle = sqlite3_backup_init(dest.db, "main", source.db, "main");
  need(handle != nullptr, "backup_init");
  int rc = SQLITE_OK;
  do {
    if (budget.expired()) break;
    rc = sqlite3_backup_step(handle, 256);
    if (rc == SQLITE_BUSY || rc == SQLITE_LOCKED) sqlite3_sleep(5);
  } while (rc == SQLITE_OK || rc == SQLITE_BUSY || rc == SQLITE_LOCKED);
  const auto finished = sqlite3_backup_finish(handle);
  budget.check();
  need(rc == SQLITE_DONE && finished == SQLITE_OK, "backup_copy");
  source.exec("ROLLBACK"); source.close();
  need(dest.scalar("PRAGMA journal_mode=DELETE") == "delete", "backup_journal_mode");
  dest.exec("PRAGMA synchronous=FULL");
  const auto version = validate(dest);
  dest.close();
  const auto image = read(file, database_cap);
  need(image.size() >= 100 && image[18] == 1 && image[19] == 1, "backup_journal_mode");
  const auto m = manifest(image, version); const auto raw = encode(m);
  budget.check();
  write_new(output / "manifest.json", raw); // Acceptance marker LAST; failures never fabricate success.
  inventory(output);
  return result("CREATED", m, util::sha256_hex(raw));
}
struct Verified { Json meta; std::string raw_manifest, image; };
inline Verified load(const fs::path& folder, const std::string& expected, Budget& budget) {
  need(hex_digest(expected), "backup_expected_digest");
  inventory(folder);
  const auto raw = read(folder / "manifest.json", manifest_cap);
  need(util::sha256_hex(raw) == expected, "backup_manifest_digest");
  Json m;
  try { m = util::parse_unique_json(raw, manifest_cap, 8); }
  catch (...) { throw Error("backup_manifest_json"); }
  const auto file = folder / "snapshot.sqlite3";
  // No backup sidecars are accepted. A live or WAL-mode file is not a sealed snapshot.
  auto image = read(file, database_cap);
  need(image.size() >= 100 && image[18] == 1 && image[19] == 1, "backup_journal_mode");
  need(m.is_object() && m.contains("database_bytes") && m["database_bytes"].is_number_unsigned() &&
       m.contains("database_sha256") && m["database_sha256"].is_string(), "backup_manifest_content");
  need(m["database_bytes"] == image.size() && m["database_sha256"] == util::sha256_hex(image), "backup_database_digest");
  Db db(file, false, budget); db.exec("BEGIN");
  const auto version = validate(db);
  need(raw == encode(manifest(image, version)), "backup_manifest_content");
  need(read(file, database_cap) == image, "backup_source_changed");
  need(read(folder / "manifest.json", manifest_cap) == raw, "backup_source_changed");
  inventory(folder); db.exec("ROLLBACK"); db.close(); budget.check();
  return {std::move(m), raw, std::move(image)};
}
inline Json verify(const fs::path& folder, const std::string& expected, int timeout = 10000) {
  Budget budget(timeout); const auto verified = load(folder, expected, budget);
  return result("VERIFIED", verified.meta, expected);
}
inline Json restore(const fs::path& folder, const std::string& expected, const fs::path& output, int timeout = 10000) {
  Budget budget(timeout);
  regular_path(output.parent_path(), true); external_output(folder, output);
  need(!fs::exists(fs::symlink_status(output)), "backup_output_exists");
  const auto verified = load(folder, expected, budget);
  new_directory(output);
  const auto file = output / "brain.db";
  write_new(file, verified.image);
  { Db db(file, false, budget); need(validate(db) == verified.meta["qbrain_schema_version"].get<int>(), "backup_restore_schema"); db.close(); }
  need(read(file, database_cap) == verified.image, "backup_restore_changed");
  auto r = result("RESTORED_TO_NEW_DIRECTORY", verified.meta, expected);
  r["database"] = "brain.db";
  budget.check(); write_new(output / "RESTORE.json", encode(r));
  return r;
}
inline int command(const std::vector<std::string>& args) {
  try {
    need(!args.empty(), "backup_arguments");
    const auto& action = args[0];
    need(action == "create" || action == "verify" || action == "restore", "backup_arguments");
    std::map<std::string, std::string> options;
    for (std::size_t i = 1; i < args.size(); i += 2) {
      need(i + 1 < args.size() && !args[i + 1].empty(), "backup_arguments");
      need(options.emplace(args[i], args[i + 1]).second, "backup_arguments");
    }
    int timeout = 10000;
    if (options.count("--timeout-ms")) {
      const auto value = options.at("--timeout-ms");
      need(value.size() <= 6 && std::all_of(value.begin(), value.end(), [](char c){return c >= '0' && c <= '9';}), "backup_timeout_range");
      timeout = std::stoi(value); options.erase("--timeout-ms");
    }
    Budget checked(timeout);
    std::set<std::string> names; for (const auto& [k, v] : options) { (void)v; names.insert(k); }
    Json r;
    if (action == "create") {
      need(names == std::set<std::string>{"--database", "--output"}, "backup_arguments");
      r = create(path(options.at("--database")), path(options.at("--output")), timeout);
    } else {
      auto required = std::set<std::string>{"--backup", "--expect-sha256"};
      if (action == "restore") required.insert("--output");
      need(names == required, "backup_arguments");
      const auto folder = path(options.at("--backup")); const auto digest = options.at("--expect-sha256");
      r = action == "verify" ? verify(folder, digest, timeout) : restore(folder, digest, path(options.at("--output")), timeout);
    }
    std::cout << encode(r); return 0;
  } catch (const Error& e) { std::cout << encode(Json{{"error", {{"code", e.what()}}}}); }
  catch (...) { std::cout << "{\"error\":{\"code\":\"backup_local_failure\"}}\n"; }
  return 2;
}
} // namespace qbrain::maintenance::backup
