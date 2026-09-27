#include "qbrain/maintenance/sqlite_search_audit.hpp"
#include "qbrain/storage/schema_sql.hpp"
#include <functional>
using namespace qbrain::maintenance;
namespace b = qbrain::maintenance::backup;
namespace a = qbrain::maintenance::search_audit;
namespace fs = std::filesystem;
namespace {
int checks = 0;
void check(bool c, const char* label) { if (!c) throw std::runtime_error(label); ++checks; }
void reject(const std::function<void()>& f, const char* code) {
  try { f(); } catch(const b::Error& e) { check(std::string(e.what()) == code, e.what()); return; }
  throw std::runtime_error("expected rejection");
}
struct Temp {
  fs::path root = fs::temp_directory_path() / fs::u8path("qbrain-search-audit-中-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
  Temp() { fs::create_directory(root); }
  ~Temp() { std::error_code ec; fs::remove_all(root, ec); }
};
void sql(sqlite3* p, const std::string& text) {
  if (sqlite3_exec(p,text.c_str(),nullptr,nullptr,nullptr) != SQLITE_OK) throw std::runtime_error(sqlite3_errmsg(p));
}
}
int main() {
  try {
    Temp t;
    int sequence = 0;
    const std::string canonical = qbrain::storage::kCanonicalSchemaSql;
    auto scenario = [&](const std::string& mutation, const char* result, bool consistent, bool supported = true) {
      const auto root = t.root / std::to_string(sequence++); fs::create_directory(root);
      const auto live = root / "live.db"; b::write_new(live, "");
      { b::Budget budget(10000); b::Db db(live,true,budget);
        // The application enables its own FTS maintenance triggers during writes.
        db.exec("PRAGMA trusted_schema=ON");
        sql(db.db, canonical);
        sql(db.db, "INSERT INTO pages(slug,title,body) VALUES('private-slug','private-title','alpha beta');");
        sql(db.db, mutation); db.close(); }
      auto created = b::create(live, root / "backup");
      const std::string pin = created.at("manifest_sha256");
      const auto image = b::read(root / "backup/snapshot.sqlite3", b::database_cap);
      const auto manifest = b::read(root / "backup/manifest.json", b::manifest_cap);
      check(b::verify(root / "backup", pin)["result"] == "VERIFIED", "structural verify succeeds");
      const auto report = a::audit(root / "backup", pin);
      check(report["result"] == result, report.dump().c_str());
      if (supported) check(report["fts_content_consistent"] == consistent, "FTS result");
      else check(report["fts_content_consistent"].is_null(), "unsupported is unknown");
      check(report["application_semantics_verified"] == false && report["input_modified"] == false, "bounded claims");
      check(report.dump().find("private-") == std::string::npos && report.dump().find(b::utf8(root)) == std::string::npos, "no private output");
      check(b::read(root / "backup/snapshot.sqlite3", b::database_cap) == image && b::read(root / "backup/manifest.json", b::manifest_cap) == manifest, "input unchanged");
      b::inventory(root / "backup");
    };
    scenario("", "PASS", true);
    scenario("DELETE FROM pages;", "PASS", true);
    scenario("UPDATE pages SET deleted_at='2026-01-01';", "PASS", true);
    scenario("INSERT INTO sources(id) VALUES('other');INSERT INTO pages(source_id,slug,title,body) VALUES('other','private-slug','中文','unicode café alpha');", "PASS", true);
    scenario("INSERT INTO pages_fts(pages_fts) VALUES('delete-all');", "FAIL", false);
    scenario("DROP TRIGGER pages_au;UPDATE pages SET body='changed';" + a::expected_definitions().at("pages_au") + ";", "FAIL", false);
    scenario("INSERT INTO pages_fts(rowid,slug,title,body) VALUES(999,'ghost','ghost','ghost');", "FAIL", false);
    scenario("DROP TRIGGER pages_ai;", "FAIL", true);
    scenario("DROP TRIGGER pages_ad;", "FAIL", true);
    scenario("DROP TRIGGER pages_au;CREATE TRIGGER pages_au AFTER UPDATE ON pages BEGIN SELECT 1; END;", "FAIL", true);
    scenario("CREATE TRIGGER extra AFTER UPDATE ON pages BEGIN SELECT 1; END;", "FAIL", true);
    scenario("DROP TABLE pages_fts;CREATE VIRTUAL TABLE pages_fts USING fts5(slug,title,body,content='pages',content_rowid='id',tokenize='porter');", "UNSUPPORTED", false, false);
    check(a::normalized_sql("SELECT 'pa ges'") != a::normalized_sql("SELECT 'pages'"), "quoted whitespace preserved");
    check(a::normalized_sql("A 'it''s X'\nB") == "a'it''s X'b", "doubled quote preserved");
    check(a::normalized_sql("SELECT [pa ges]") != a::normalized_sql("SELECT [pages]"), "quoted identifier preserved");
    // Resource lifetime and a deadline failure after sqlite3_close succeeds.
    { b::Budget budget(100); b::Db db(fs::path(":memory:"),true,budget);
      budget.end = std::chrono::steady_clock::now();
      reject([&]{db.close();}, "backup_timeout");
      check(db.db == nullptr, "closed handle null on timeout"); }
    reject([&]{ a::audit(t.root,"abc"); }, "backup_expected_digest");
    reject([&]{ a::audit(t.root,std::string(64,'0'),99); }, "backup_timeout_range");
    std::cout << b::encode(b::Json{{"schema","qbrain-search-audit-direct-v1"},{"checks",checks},{"scenarios",sequence},{"result","PASS"}});
    return 0;
  } catch(const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
