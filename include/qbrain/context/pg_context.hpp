#pragma once
// N48P PostgreSQL dialect/lifetime for existing layered context; no raw PG handles.
#include "qbrain/context/context.hpp"
#include <map>
#include "qbrain/context/pg_directory_policy.hpp"

namespace qbrain::context::pg {
using DB = storage::Database;
inline bool enabled(DB& db) { return db.backend_kind() == storage::BackendKind::postgres; }
inline void need(bool condition, const char* code) { if (!condition) throw memory::Error(code); }
inline void namespace_check(DB& db) {
  auto s = db.prepare("SELECT pg_catalog.current_schema(),pg_catalog.current_setting('server_encoding'),"
                      "pg_catalog.current_setting('session_replication_role')");
  need(s.step() && s.column_text(0)=="public" && s.column_text(1)=="UTF8" && s.column_text(2)=="origin",
       "context_pg_schema_context");
  auto names = db.prepare("SELECT count(*) FROM (VALUES ('sources'),('pages'),('config'),"
    "('context_module'),('context_cache')) AS n(name) WHERE pg_catalog.to_regclass(name) IS DISTINCT FROM "
    "pg_catalog.to_regclass('public.' || name)");
  need(names.step() && names.column_int(0)==0, "context_pg_schema_context");
}
inline void idle(DB& db) { need(!db.transaction_active(), "context_transaction_active"); }
struct ReadSnapshot {
  DB& db; bool owned=false;
  explicit ReadSnapshot(DB& d):db(d) {
    if (!enabled(db)) return;
    idle(db);
    db.exec("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY"); owned=true;
    try { namespace_check(db); } catch (...) { finish(); throw; }
  }
  void finish() { if (owned) { db.exec("ROLLBACK"); owned=false; } }
  ~ReadSnapshot() { if (owned) try { db.exec("ROLLBACK"); } catch (...) {} }
  ReadSnapshot(const ReadSnapshot&)=delete;
  ReadSnapshot& operator=(const ReadSnapshot&)=delete;
};
inline void begin_write(DB& db) {
  idle(db); namespace_check(db);
  db.exec("BEGIN ISOLATION LEVEL READ COMMITTED");
  try {
    db.exec("SET LOCAL lock_timeout='2500ms'");
    // Same global order as N48O; never held across external model execution.
    db.exec("LOCK TABLE public.sources, public.pages, public.config IN SHARE ROW EXCLUSIVE MODE");
    namespace_check(db);
  } catch (...) { try { db.exec("ROLLBACK"); } catch (...) {} throw; }
}
inline constexpr const char* trigger_body=R"SQL(
BEGIN
 IF TG_OP = 'TRUNCATE' THEN
  UPDATE public.context_cache SET dirty=1,l0='',l1='',refs_json='[]';
 ELSIF TG_OP = 'INSERT' THEN
  UPDATE public.context_cache SET dirty=1,l0='',l1='',refs_json='[]' WHERE source_id=NEW.source_id;
 ELSIF TG_OP = 'DELETE' THEN
  UPDATE public.context_cache SET dirty=1,l0='',l1='',refs_json='[]' WHERE source_id=OLD.source_id;
 ELSE
  UPDATE public.context_cache SET dirty=1,l0='',l1='',refs_json='[]'
   WHERE source_id=OLD.source_id OR source_id=NEW.source_id;
 END IF;
 RETURN NULL;
END;
)SQL";
enum class CachePolicy { absent, source_v1, directory_v2 };
inline CachePolicy cache_policy(DB& db) {
  auto tables=db.prepare("SELECT c.relname,c.relkind FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n "
    "ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname IN ('context_module','context_cache')");
  std::map<std::string,std::string> relations;
  while(tables.step()) relations.emplace(tables.column_text(0),tables.column_text(1));
  auto functions=db.prepare("SELECT p.oid,p.prosrc,p.prosecdef,p.pronargs,p.prorettype='pg_catalog.trigger'::regtype,"
    "l.lanname,pg_catalog.array_to_string(p.proconfig,','),p.proisstrict,p.provolatile,p.proparallel,p.proleakproof,p.prokind FROM pg_catalog.pg_proc p "
    "JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace JOIN pg_catalog.pg_language l ON l.oid=p.prolang "
    "WHERE n.nspname='public' AND p.proname='qbrain_context_invalidate_v1'");
  const bool has_function=functions.step();
  auto triggers=db.prepare("SELECT t.tgname,t.tgtype,t.tgenabled,t.tgfoid,t.tgnargs,t.tgqual IS NULL,"
    "t.tgattr::text,t.tgconstraint FROM pg_catalog.pg_trigger t "
    "WHERE t.tgrelid='public.pages'::regclass AND NOT t.tgisinternal "
    "AND t.tgname IN ('ctx_page_insert','ctx_page_update','ctx_page_delete','ctx_page_truncate')");
  if(relations.empty()) {
    need(!has_function && !triggers.step(),"context_schema_conflict"); return CachePolicy::absent;
  }
  need(relations==std::map<std::string,std::string>{{"context_module","r"},{"context_cache","r"}},
       "context_schema_version_unsupported");
  const std::map<std::string,std::string> expected={
    {"context_module.version","bigint"},{"context_cache.source_id","text"},{"context_cache.uri","text"},
    {"context_cache.signature","text"},{"context_cache.l0","text"},{"context_cache.l1","text"},
    {"context_cache.refs_json","text"},{"context_cache.page_count","bigint"},{"context_cache.method","text"},
    {"context_cache.dirty","bigint"},{"context_cache.partial","bigint"}};
  std::map<std::string,std::string> columns;
  auto cols=db.prepare("SELECT c.relname,a.attname,pg_catalog.format_type(a.atttypid,a.atttypmod),a.attnotnull "
    "FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
    "JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid WHERE n.nspname='public' AND a.attnum>0 "
    "AND NOT a.attisdropped AND c.relname IN ('context_module','context_cache')");
  while(cols.step()) {
    need(cols.column_text(3)=="t","context_schema_version_unsupported");
    columns.emplace(cols.column_text(0)+"."+cols.column_text(1),cols.column_text(2));
  }
  need(columns==expected,"context_schema_version_unsupported");
  auto v=db.prepare("SELECT version FROM public.context_module");
  need(v.step() && v.column_int(0)==1 && !v.step(),"context_schema_version_unsupported");
  const bool legacy=has_function && functions.column_text(1)==trigger_body;
  const bool scoped=has_function && functions.column_text(1)==directory_policy::body();
  need(has_function && (legacy || scoped) && functions.column_text(2)=="f" &&
       functions.column_int(3)==0 && functions.column_text(4)=="t" && functions.column_text(5)=="plpgsql" &&
       functions.column_text(6)=="search_path=pg_catalog" && functions.column_text(7)=="f" &&
       functions.column_text(8)=="v" && functions.column_text(9)=="u" &&
       functions.column_text(10)=="f" && functions.column_text(11)=="f", "context_schema_incomplete");
  const auto function_id=functions.column_int(0);
  need(!functions.step(),"context_schema_incomplete");
  std::map<std::string,int64_t> actual_triggers;
  while(triggers.step()) {
    need(triggers.column_text(2)=="O" && triggers.column_int(3)==function_id && triggers.column_int(4)==0 &&
         triggers.column_text(5)=="t" && triggers.column_text(6).empty() && triggers.column_int(7)==0,
         "context_schema_incomplete");
    actual_triggers.emplace(triggers.column_text(0),triggers.column_int(1));
  }
  need(actual_triggers==std::map<std::string,int64_t>{{"ctx_page_insert",5},{"ctx_page_update",17},
       {"ctx_page_delete",9},{"ctx_page_truncate",32}},"context_schema_incomplete");
  // Do not alter the behavior of extra caller-owned trigger dependents during upgrade.
  auto users=db.prepare("SELECT count(*) FROM pg_catalog.pg_trigger WHERE tgfoid=?::oid");
  users.bind_int(1,function_id);
  need(users.step() && users.column_int(0)==4,"context_schema_incomplete");
  return legacy ? CachePolicy::source_v1 : CachePolicy::directory_v2;
}
inline bool ready(DB& db) { return cache_policy(db)!=CachePolicy::absent; }
inline void initialize_locked(DB& db) {
  // Called only after begin_write + source/evidence/consent revalidation.
  need(enabled(db) && db.transaction_active(),"context_transaction_required");
  namespace_check(db);
  const auto policy=cache_policy(db);
  if(policy==CachePolicy::directory_v2) return;
  const auto install=[](DB& target,bool replace) {
    target.exec(std::string(replace?"CREATE OR REPLACE FUNCTION ":"CREATE FUNCTION ")+
      "public.qbrain_context_invalidate_v1() RETURNS trigger LANGUAGE plpgsql "
      "VOLATILE CALLED ON NULL INPUT SECURITY INVOKER PARALLEL UNSAFE SET search_path=pg_catalog AS $qbrain$"+
      directory_policy::body()+"$qbrain$");
  };
  if(policy==CachePolicy::source_v1) {
    // All names/flags/dependents were checked under the caller's publication locks.
    // Replacement preserves OID, owner and ACL; neither triggers nor unknown objects are dropped.
    install(db,true);
    db.exec("UPDATE public.context_cache SET dirty=1,l0='',l1='',refs_json='[]'");
    return;
  }
  db.exec(R"SQL(
CREATE TABLE public.context_module(version BIGINT PRIMARY KEY CHECK(version=1));
INSERT INTO public.context_module VALUES(1);
CREATE TABLE public.context_cache(
 source_id TEXT COLLATE "C" NOT NULL REFERENCES public.sources(id) ON DELETE CASCADE,
 uri TEXT COLLATE "C" NOT NULL, signature TEXT NOT NULL, l0 TEXT NOT NULL, l1 TEXT NOT NULL,
 refs_json TEXT NOT NULL,page_count BIGINT NOT NULL CHECK(page_count BETWEEN 0 AND 256),
 method TEXT NOT NULL CHECK(method IN ('extractive','model')),
 dirty BIGINT NOT NULL DEFAULT 0 CHECK(dirty IN (0,1)),
 partial BIGINT NOT NULL DEFAULT 0 CHECK(partial IN (0,1)), PRIMARY KEY(source_id,uri));
)SQL");
  install(db,false);
  for(const auto& item:std::map<std::string,std::string>{{"insert","INSERT"},{"update","UPDATE"},{"delete","DELETE"},{"truncate","TRUNCATE"}})
    db.exec("CREATE TRIGGER ctx_page_"+item.first+" AFTER "+item.second+" ON public.pages FOR EACH "+
            (item.first=="truncate"?"STATEMENT":"ROW")+" EXECUTE FUNCTION public.qbrain_context_invalidate_v1()");
}
} // namespace qbrain::context::pg
