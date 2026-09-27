#include "qbrain/maintenance/sqlite_check.hpp"
#include "qbrain/storage/database.hpp"
#include <functional>
namespace c = qbrain::maintenance::check;
namespace b = qbrain::maintenance::backup;
namespace fs = std::filesystem;
using qbrain::storage::Database;
int checks = 0;
void require(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
  ++checks;
}
struct Temp {
  fs::path root = fs::temp_directory_path() / fs::u8path("qbrain-check-\xe4\xb8\xad-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
  Temp() { fs::create_directory(root); }
  ~Temp() { std::error_code e; fs::remove_all(root, e); }
};
int main() {
  try {
    require(c::sql_tokens("SELECT a, 'two words' /* x */ FROM t;") == c::sql_tokens("select a,'two words'\nfrom t"), "format normalization");
    require(c::sql_tokens("SELECT a b") != c::sql_tokens("SELECT ab"), "word boundaries retained");
    require(c::sql_tokens("SELECT 'two words'") != c::sql_tokens("SELECT 'twowords'"), "literal spaces retained");
    require(c::sql_tokens("SELECT 'A'") != c::sql_tokens("SELECT 'a'"), "literal case retained");
    require(c::sql_tokens("SELECT 'a''b'") != c::sql_tokens("SELECT 'ab'"), "escaped quotes retained");
    require(c::sql_tokens("select a --last line") == c::sql_tokens("select a"), "line comments");
    require(c::sql_tokens("select \"a b\"") != c::sql_tokens("select \"ab\""), "quoted identifiers retained");
    Temp temp;
    const auto path = temp.root / "real.db";
    Database db; db.open(b::utf8(path)); qbrain::storage::apply_migrations(db);
    db.exec("PRAGMA wal_autocheckpoint=0;INSERT INTO pages(source_id,slug,title,body) VALUES('default','probe','Title','PRIVATE body words');");
    auto before = b::read(path, b::database_cap);
    const auto wal = fs::u8path(b::utf8(path) + "-wal");
    auto wal_before = b::read(wal, b::database_cap);
    auto good = c::inspect(path);
    require(good["result"] == "CHECK_PASSED", good.dump().c_str());
    require(good["checks"].size() == 7, "seven checks");
    for (const auto& check : good["checks"]) require(check["status"] == "PASS", "all checks execute");
    require(b::read(path, b::database_cap) == before, "main bytes unchanged");
    require(b::read(wal, b::database_cap) == wal_before, "WAL bytes unchanged");
    require(good.dump().find("PRIVATE") == std::string::npos && good.dump().find(b::utf8(path)) == std::string::npos, "content/path privacy");
    db.exec("BEGIN IMMEDIATE;DROP TRIGGER pages_au;UPDATE pages SET body='UNCOMMITTED';");
    require(c::inspect(path)["result"] == "CHECK_PASSED", "uncommitted changes excluded");
    db.exec("ROLLBACK;DROP TRIGGER pages_au;UPDATE pages SET body='STALE_INDEX';");
    auto bad = c::inspect(path);
    require(bad["result"] == "CHECK_FAILED", "stale index rejected");
    require(bad["checks"][0]["status"] == "PASS", "ordinary integrity misses stale index control");
    require(bad["checks"][5]["status"] == "FAIL", "missing trigger rejected");
    require(bad["checks"][6]["status"] == "FAIL", "external content checked");
    db.exec("INSERT INTO pages_fts(pages_fts) VALUES('rebuild');");
    require(c::inspect(path)["checks"][6]["status"] == "PASS", "repaired fixture content only");
    require(c::inspect(path)["result"] == "CHECK_FAILED", "missing trigger still fails");
    for (int ms : {0, 99, 120001}) require(c::inspect(path, ms)["error"]["code"] == "database_timeout_range", "invalid budget");
    db.close();
    { b::Budget budget(10000); c::Memory image(budget); image.exec("CREATE TABLE x(v INTEGER)");
      budget.end = std::chrono::steady_clock::now();
      bool timeout = false;
      try { image.exec("SELECT 1"); } catch (const b::Error& e) { timeout = std::string(e.what()) == "backup_timeout"; }
      require(timeout, "expired memory budget"); }
    { b::Budget budget(10000); c::Memory image(budget), reference(budget);
      reference.exec(qbrain::storage::kCanonicalSchemaSql);
      image.exec("CREATE TABLE pages_fts(pages_fts TEXT,rank INTEGER)");
      require(!c::canonical(image, reference, "pages_fts", "table"), "ordinary-table impersonation");
      image.exec("CREATE VIEW sources AS SELECT 1 AS id");
      auto issues = c::core_inventory(image);
      require(std::find(issues.begin(),issues.end(),"missing_or_nonordinary_table:sources") != issues.end(), "views not trusted core"); }
    require(c::inspect(temp.root / "absent.db")["result"] == "ERROR", "missing input is error");
    require(!fs::exists(temp.root / "absent.db"), "missing input not created");
    std::cout << c::Json{{"passed",true},{"checks",checks}}.dump() << '\n';
    return 0;
  } catch (const std::exception& e) { std::cerr << e.what() << '\n'; }
    catch (const c::SqlError& e) { std::cerr << "SQLite direct error " << e.code << '\n'; }
  return 1;
}
