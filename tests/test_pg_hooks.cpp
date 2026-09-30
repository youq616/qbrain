#include "qbrain/integration/detail/hook_storage.hpp"
// N48R: actual backend composition, not proof that a signed-in host used output.
#include "qbrain/integration/detail/fact_context.hpp"
#include "qbrain/memory/detail/composed_read.hpp"
#include "qbrain/memory/fact_store.hpp"
#include "qbrain/memory/pg_fact_storage.hpp"
#include "qbrain/storage/pg_backend.hpp"
#include <cstdlib>
#include <iostream>
using namespace qbrain;
using J=nlohmann::json;
namespace {
int checks=0;std::string backend,dsn;
void need(bool ok,const char* label){if(!ok)throw std::runtime_error(label);++checks;}
template<class F> void rejects(F f,const char* code){try{f();}catch(const std::exception& e){need(std::string(e.what())==code,code);return;}throw std::runtime_error("expected rejection");}
std::string scalar(Brain& b,const char* query){auto s=b.db().prepare(query);need(s.step(),"scalar exists");return s.column_text(0);}
struct Seed {std::string event,item,quote;};
Seed seed(Brain& b,const char* frag,const char* quote,const char* source="alpha") {
 auto id=memory::capture(b,source,{{"session_id","n48r"},{"fragment_id",frag},{"messages",J::array({{{"role","user"},{"content",quote}},{{"role","assistant"},{"content","I prefer ASSISTANT_POISON"}}})}},true)["event_id"].get<std::string>();
 need(memory::extract(b,source,id)["item_count"]==1,"only user extracted");
 auto s=b.db().prepare("SELECT item_id FROM memory_items WHERE event_id=?");s.bind_text(1,id);need(s.step(),"support exists");return {id,s.column_text(0),quote};
}
J compose(Brain& b){return integration::detail::compose_fact_context(b,"alpha","SessionStart","",8192,8,{});}
J payload(const J& value){const auto text=value.at("output").at("hookSpecificOutput").at("additionalContext").get<std::string>();return J::parse(text.substr(text.find('\n')+1));}
void reset(Brain& b) {
 if(b.db().backend_kind()==storage::BackendKind::postgres){
  need(scalar(b,"SELECT current_database()") == "qbrain_n48r_native","disposable database");
  b.db().exec("DROP TABLE IF EXISTS public.memory_fact_usage,public.memory_fact_usage_module,public.memory_fact_archive,public.memory_fact_lifecycle_module,public.memory_fact_relations,public.memory_fact_evidence,public.memory_facts,public.memory_fact_module,public.memory_attempts,public.memory_items,public.memory_events,public.memory_module CASCADE; DROP FUNCTION IF EXISTS public.qbrain_fact_evidence_gc_v1() CASCADE");
 }
 b.db().exec("DELETE FROM pages;DELETE FROM config");b.ensure_source("alpha");b.ensure_source("beta");
 b.save_config_value("embed.auto","false",false);b.save_config_value("memory.writeback","salient",false);
}
void basic(Brain& b) {
 reset(b);need(compose(b)["output"].empty(),"empty clean composition");
 auto f=seed(b,"fact","I prefer needle PostgreSQL 中文😀.");
 auto m=seed(b,"ordinary","I prefer needle native Windows.");
 seed(b,"foreign","I prefer FOREIGN_POISON.","beta");
 memory::FactStore store(b,"alpha");auto fact=store.create({{"predicate","tool.preference"},{"item_id",f.item}});
 auto out=compose(b);auto p=payload(out);
 need(out["fact_group_count"]==1 && out["memory_count"]==1,"both lanes composed");
 need(p["memories"][0]["item_id"]==m.item,"no fact quote duplicate in legacy lane");
 need(p.dump().find("FOREIGN_POISON")==std::string::npos && p.dump().find("ASSISTANT_POISON")==std::string::npos,"source and role isolation");
 need(!b.db().transaction_active(),"Hook read scope closed");
 const auto seen=integration::detail::compose_fact_context(b,"alpha","UserPromptSubmit","needle",8192,8,{m.item});
 need(seen["memory_count"]==0 && seen["fact_group_count"]==1,"legacy dedup never suppresses explicit fact group");
 const auto small=integration::detail::compose_fact_context(b,"alpha","SessionStart","",512,1,{});
 need(small["output"].dump().size()<=512,"bounded payload");
 b.db().exec("BEGIN");
 rejects([&]{compose(b);},backend=="postgres"?"fact_transaction_active":"hook_transaction_active");
 need(b.db().transaction_active(),"caller transaction not committed");b.db().exec("ROLLBACK");
 store.retract({{"fact_id",fact["fact_id"]},{"expected_revision",1}});
 auto retired=compose(b);need(retired["fact_group_count"]==0 && retired["memory_count"]==1,"retired fact cannot reappear via raw lane");
 need(payload(retired)["memories"][0]["item_id"]==m.item,"ordinary lane retained");
 memory::forget(b,"alpha",m.event);need(compose(b)["output"].empty(),"forget and retract leave no injected text");
 rejects([&]{memory::detail::read_in_fact_snapshot(b,"alpha","",16,32768);},"memory_composed_snapshot_required");
 need(!b.db().transaction_active(),"private reader no implicit scope");
}
void pg_cases(Brain& b) {
 using namespace memory;
 auto raw=seed(b,"snapshot-raw","I prefer needle unchanged evidence.");
 const std::string database=scalar(b,"SELECT current_database()");
 {
  pg_fact::ReadScope scope(b.db());
  auto first=detail::read_in_fact_snapshot(b,"alpha","unchanged",16,32768);
  need(first["items"].size()==1,"owned snapshot reads legacy lane");
  rejects([&]{memory::read(b,"alpha");},"memory_transaction_active");
  rejects([&]{memory::forget(b,"alpha",raw.event);},"memory_transaction_active");
  rejects([&]{compose(b);},"fact_transaction_active");
  Brain other;integration::detail::open_existing_postgres(other,dsn);memory::forget(other,"alpha",raw.event);
  need(detail::read_in_fact_snapshot(b,"alpha","unchanged",16,32768)==first,"both observations see pinned committed snapshot");
  need(b.db().transaction_active(),"scope retained across refusal");
 }
 need(memory::read(b,"alpha","unchanged")["items"].empty(),"new observation sees committed forget");
 {
  pg_fact::WriteScope scope(b.db());
  rejects([&]{detail::read_in_fact_snapshot(b,"alpha","",16,32768);},"memory_composed_snapshot_required");
 }
 b.db().exec("BEGIN READ ONLY");
 rejects([&]{detail::read_in_fact_snapshot(b,"alpha","",16,32768);},"memory_composed_snapshot_required");
 need(b.db().transaction_active(),"arbitrary readonly caller not borrowed");b.db().exec("ROLLBACK");
 b.db().exec("BEGIN");try{b.db().exec("SELECT 1/0");}catch(...){}
 rejects([&]{compose(b);},"fact_transaction_active");need(b.db().transaction_active(),"failed caller transaction retained");b.db().exec("ROLLBACK");
 for(const auto* name:{"sources","pages","config","memory_items","memory_facts","memory_fact_evidence"}) {
  b.db().exec(std::string("CREATE TEMP TABLE ")+name+"(poison TEXT)");
  rejects([&]{compose(b);},"fact_pg_schema_context");
  need(!b.db().transaction_active(),"temp conflict no leaked scope");
  b.db().exec(std::string("DROP TABLE pg_temp.")+name);
 }
 Brain reopened;integration::detail::open_existing_postgres(reopened,dsn);
 need(scalar(reopened,"SHOW statement_timeout")=="2500ms","Hook-only statement budget");
 need(reopened.db().backend_file_path()==b.db().backend_file_path(),"effective connection identity stable");
 need(scalar(reopened,"SELECT current_database()")==database,"no server fallback");
 const char* empty=std::getenv("QBRAIN_PG_HOOK_EMPTY_DSN");need(empty && *empty,"empty database DSN required");
#if defined(QBRAIN_WITH_PG)
 storage::Database inspector;inspector.adopt_backend(storage::make_pg_backend(empty));
 {auto s=inspector.prepare("SELECT current_database(),(SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public')");need(s.step() && s.column_text(0)=="qbrain_n48r_empty" && s.column_int(1)==0,"dedicated empty PG");}
 Brain absent;rejects([&]{integration::detail::open_existing_postgres(absent,empty);},"hook_pg_uninitialized");
 need(!absent.is_open(),"failed opening closes connection");
 {auto s=inspector.prepare("SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public'");need(s.step()&&s.column_int(0)==0,"Hook opening creates no schema");}
#endif
}
}
int main(int argc,char** argv) {
 try {
  backend="sqlite";Brain sqlite;sqlite.open_at(":memory:");basic(sqlite);const int local=checks;
  const bool sqlite_only=argc==2 && std::string(argv[1])=="--sqlite-only";
  if(!sqlite_only) {
   const char* s=std::getenv("QBRAIN_PG_HOOK_DSN"),*guard=std::getenv("QBRAIN_PG_HOOK_TEST_DISPOSABLE");
   need(s&&*s&&guard&&std::string(guard)=="1","explicit disposable PG required");dsn=s;
   backend="postgres";Brain pg;pg.open_pg(dsn);basic(pg);pg_cases(pg);
  }
  std::cout<<J{{"schema","qbrain-pg-hook-direct-v1"},{"passed",true},{"checks",checks},{"sqlite_checks",local},{"postgres_executed",!sqlite_only}}.dump()<<'\n';return 0;
 }catch(const std::exception& e){std::cerr<<backend<<" failed after "<<checks<<": "<<e.what()<<'\n';return 1;}
}
