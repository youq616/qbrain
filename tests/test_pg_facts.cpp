// N48Q: actual optional PostgreSQL service + unchanged SQLite semantic contracts.
#include "qbrain/memory/fact_store.hpp"
#include "qbrain/memory/fact_usage.hpp"
#include "qbrain/memory/fact_usage_batch.hpp"
#include "qbrain/memory/fact_usage_read.hpp"
#include "qbrain/memory/pg_fact_storage.hpp"
#include "qbrain/util/hash.hpp"
#include <atomic>
#include <barrier>
#include <chrono>
#include <cstdlib>
#include <future>
#include <iostream>
#include <thread>
using namespace qbrain;
using J=nlohmann::json;
namespace {
J checks=J::array();std::string backend,dsn;
void check(bool ok,const std::string& name){checks.push_back({{"name",backend+":"+name},{"passed",ok}});if(!ok)throw std::runtime_error(name);}
template<class F>void reject(F f,const std::string& code){
  try{f();}catch(const memory::Error& e){check(std::string(e.what())==code,"reject:"+code);return;}
  throw std::runtime_error("expected rejection:"+code);
}
std::string scalar(Brain& b,const std::string& sql){auto s=b.db().prepare(sql);if(!s.step())throw std::runtime_error("missing scalar");return s.column_text(0);}
int64_t count(Brain& b,const std::string& table){auto s=b.db().prepare("SELECT count(*) FROM "+table);if(!s.step())throw std::runtime_error("missing count");return s.column_int(0);}
bool pg(Brain& b){return memory::pg_fact::enabled(b.db());}
std::string hash(const std::string& s){return util::sha256_hex(s);}
std::unique_ptr<Brain> worker(){auto b=std::make_unique<Brain>();b->open_pg(dsn);return b;}
void reset(Brain& b){
  if(pg(b)){
    check(scalar(b,"SELECT current_database()") == "qbrain_n48q_native","disposable DB");
    b.db().exec("DROP TABLE IF EXISTS public.memory_fact_usage,public.memory_fact_usage_module,public.memory_fact_archive,public.memory_fact_lifecycle_module,"
      "public.memory_fact_relations,public.memory_fact_evidence,public.memory_facts,public.memory_fact_module CASCADE;"
      "DROP FUNCTION IF EXISTS public.qbrain_fact_evidence_gc_v1() CASCADE;"
      "DROP TABLE IF EXISTS public.memory_attempts,public.memory_items,public.memory_events,public.memory_module CASCADE");
  }else{
    b.db().exec("DROP TABLE IF EXISTS memory_fact_usage;DROP TABLE IF EXISTS memory_fact_usage_module;DROP TABLE IF EXISTS memory_fact_archive;"
      "DROP TABLE IF EXISTS memory_fact_lifecycle_module;DROP TABLE IF EXISTS memory_fact_relations;DROP TABLE IF EXISTS memory_fact_evidence;"
      "DROP TABLE IF EXISTS memory_facts;DROP TABLE IF EXISTS memory_fact_module;DROP TABLE IF EXISTS memory_attempts;DROP TABLE IF EXISTS memory_items;"
      "DROP TABLE IF EXISTS memory_events;DROP TABLE IF EXISTS memory_module");
  }
  b.db().exec("DELETE FROM pages;DELETE FROM config");b.ensure_source("alpha");b.ensure_source("beta");
  b.save_config_value("embed.auto","false",false);b.save_config_value("memory.writeback","salient",false);
}
struct Seed{std::string event,item,quote;};
Seed seed(Brain& b,const std::string& frag,const std::string& quote="I prefer Windows C++ 中文😀; not Python.",const std::string& source="alpha"){
  const auto payload=J{{"session_id","n48q-synthetic"},{"fragment_id",frag},{"messages",J::array({{{"role","user"},{"content",quote}},{{"role","assistant"},{"content","I prefer FAKE_ASSISTANT."}}})}};
  auto event=memory::capture(b,source,payload,true).at("event_id").get<std::string>();
  auto extracted=memory::extract(b,source,event);
  check(extracted["item_count"]==1,"only explicit user extracted");
  auto s=b.db().prepare("SELECT item_id FROM memory_items WHERE event_id=?");s.bind_text(1,event);
  check(s.step(),"support exists");return {event,s.column_text(0),quote};
}
J make(memory::FactStore& store,const Seed& s,const std::string& pred="tool.preference"){return store.create({{"predicate",pred},{"item_id",s.item}});}
J get(memory::FactStore& store,const J& f){const auto r=store.read(f.at("fact_id"),"",true,1,32768);check(r["items"].size()==1,"one supported fact");return r["items"][0];}
J use(const J& f,const std::string& uid,int64_t revision=1){return {{"fact_id",f["fact_id"]},{"usage_id",hash(uid)},{"expected_revision",revision}};}
J shared(Brain& b){
  reset(b);memory::FactStore store(b,"alpha"),other(b,"beta");
  check(store.read()["initialized"]==false,"read lazy facts");
  check(store.recall("Windows")["items"].empty(),"empty recall");
  check(!memory::pg_fact::enabled(b.db()) || !memory::pg_fact::exists(b.db(),"memory_fact_module"),"PG no read DDL");
  const auto a=seed(b,"first"),a2=seed(b,"second",a.quote),different=seed(b,"opposite","I prefer Linux, not Windows. 中文"),foreign=seed(b,"foreign",a.quote,"beta");
  auto f=make(store,a);check(f["revision"]==1 && !f["duplicate"].get<bool>(),"create revision");
  const auto expected=hash(J::array({"qbrain-fact-v1","alpha","user","tool.preference",a.quote,a.item}).dump());
  check(f["fact_id"]==expected,"independent fact identity");
  auto full=get(store,f);check(full["object"]==a.quote && full["confidence"].is_null() && full["truth_status"]=="caller_attested_user_statement","no invented confidence or shortened quote");
  check(full["evidence"][0]["event_id"]==a.event && full["evidence"][0]["item_id"]==a.item,"exact support binding");
  check(make(store,a)["duplicate"]==true && count(b,"memory_facts")==1,"create idempotence");
  reject([&]{make(other,a);},"fact_evidence_unavailable");
  reject([&]{store.create({{"predicate","p"},{"item_id",a.item},{"subject","assistant"}});},"fact_invalid_subject");
  check(other.read(expected)["items"].empty(),"source mismatch empty");
  check(store.attach({{"fact_id",expected},{"item_id",a2.item}})["revision"]==2,"attach independent support");
  check(store.attach({{"fact_id",expected},{"item_id",a2.item}})["duplicate"]==true,"attach idempotence");
  reject([&]{store.attach({{"fact_id",expected},{"item_id",different.item}});},"fact_quote_mismatch");
  reject([&]{store.attach({{"fact_id",expected},{"item_id",foreign.item}});},"fact_evidence_unavailable");
  auto g=make(store,different);check(store.read()["items"].size()==2,"different quote does not supersede automatically");
  auto conflict=store.contradict({{"fact_id",expected},{"other_id",g["fact_id"]}});
  check(conflict["resolution"]=="unresolved" && count(b,"memory_fact_relations")==1,"explicit symmetric contradiction");
  check(store.contradict({{"fact_id",g["fact_id"]},{"other_id",expected}})["duplicate"]==true,"symmetric repeat");
  check(store.conflicts()["items"].size()==1,"complete supported conflict pair");
  reject([&]{store.supersede({{"fact_id",expected},{"replacement_id",g["fact_id"]},{"expected_revision",1}});},"fact_revision_conflict");
  check(store.supersede({{"fact_id",expected},{"replacement_id",g["fact_id"]},{"expected_revision",3}})["revision"]==4,"exact revision supersession");
  check(store.read()["items"].size()==1 && get(store,f)["status"]=="superseded","history not revived");
  check(make(store,a)["status"]=="superseded","replay cannot revive superseded");
  check(store.retract({{"fact_id",g["fact_id"]},{"expected_revision",2}})["status"]=="retracted","explicit retraction");
  check(store.read()["items"].empty() && store.conflicts()["items"].empty(),"retired pair not recalled");
  check(store.retract({{"fact_id",g["fact_id"]},{"expected_revision",3}})["duplicate"]==true,"retraction idempotence");
  check(store.promote_event(a.event)["counts"]["skipped_retired"]==1,"promotion retirement veto");

  // Fresh active assertion, receipts, archive/restore and full-set snapshot binding.
  const auto live=seed(b,"active","I prefer CASE Café Ä --brain literal data 中文😀."),live2=seed(b,"active2",live.quote);
  auto h=make(store,live,"locale.preference");const std::string id=h["fact_id"];
  for(const auto& item:std::vector<std::pair<std::string,int>>{{"case",1},{"café",1},{"CAFÉ",0},{"ä",0},{"Ä",1},{"--brain",1},{"%' OR 1=1",0}})
    check(store.recall(item.first,"locale.preference")["items"].size()==std::size_t(item.second),"ASCII literal:"+item.first);
  memory::FactUsageStore usage(b,"alpha");
  check(usage.usage(id)["initialized"]==false,"receipt read no DDL");
  auto u=use(h,"use-one");check(usage.report_use(u)["duplicate"]==false,"first receipt");
  check(usage.report_use(u)["duplicate"]==true,"receipt idempotent");
  const auto before=usage.usage(id);check(before["current_revision_use_count"]==1 && before["host_consumption_verified"]==false,"reported not verified use");
  auto paged=memory::read_usage_receipts(b,"alpha",id,"all","","",1,2048);
  check(paged["items"].size()==1 && paged["items"][0]["state"]=="current","typed full-set receipt page");
  auto attached=store.attach({{"fact_id",id},{"item_id",live2.item}});check(attached["revision"]==2,"support bumps revision");
  check(usage.usage(id)["other_revision_use_count"]==1 && usage.usage(id)["current_revision_use_count"]==0,"old receipt historical");
  reject([&]{memory::read_usage_receipts(b,"alpha",id,"all",hash("use-one"),paged["snapshot"],1,2048);},"fact_usage_snapshot_conflict");
  reject([&]{usage.report_use(u);},"fact_revision_conflict");
  usage.report_use(use(h,"use-two",2));
  check(usage.revoke_use({{"fact_id",id},{"usage_id",hash("use-one")}})["duplicate"]==false,"withdraw historical receipt");
  check(usage.revoke_use({{"fact_id",id},{"usage_id",hash("use-one")}})["duplicate"]==true,"withdraw idempotent");
  auto archived=store.archive({{"fact_id",id},{"expected_revision",2}});check(archived["revision"]==3 && archived["archived"]==true,"archive exact revision");
  check(store.recall("CASE","locale.preference")["items"].empty(),"archived excluded");
  reject([&]{usage.report_use(use(h,"use-three",3));},"fact_usage_archived");
  auto restored=store.restore({{"fact_id",id},{"expected_revision",3}});check(restored["revision"]==4 && restored["archived"]==false,"restore supported fact");
  check(usage.usage(id)["withdrawn_count"]==1 && usage.usage(id)["other_revision_use_count"]==1,"receipts not reset by restore");
  auto requested=J{{"operation","report"},{"items",J::array({use(h,"batch-one",4),use(h,"batch-two",4)})}};
  auto preview=memory::usage_batch(b,"alpha",requested);check(preview["would_change"]==2 && preview["applied"]==false,"read-only receipt batch preview");
  requested["snapshot"]=preview["snapshot"];
  auto applied=memory::usage_batch(b,"alpha",requested,true);check(applied["changed"]==2 && applied["atomic"]==true,"atomic receipt batch");
  reject([&]{memory::usage_batch(b,"alpha",requested,true);},"fact_usage_batch_snapshot_conflict");
  check(usage.usage(id)["stored_receipts"]==4 && usage.usage(id)["current_revision_use_count"]==2,"correct receipt aggregate");
  const auto receipt_snapshot=memory::read_usage_receipts(b,"alpha",id);
  check(receipt_snapshot["matched_receipts"]==4 && receipt_snapshot["items"].size()==4,"complete receipt list");
  auto operations=J{{"operation","archive"},{"items",J::array({{{"fact_id",id},{"expected_revision",4}}})}};
  auto preview_archive=store.lifecycle_batch(operations);check(preview_archive["counts"]["change"]==1 && preview_archive["applied"]==false,"lifecycle preview");
  check(store.lifecycle_batch(operations,true)["counts"]["change"]==1,"atomic lifecycle apply");
  check(store.lifecycle(id)["items"].size()==1,"supported lifecycle read");
  check(store.lifecycle_candidates("restore")["items"].size()==1,"restore discovery");
  // Loss of one support changes surviving revision, never an inferred new fact.
  memory::forget(b,"alpha",live.event);auto remaining=get(store,h);
  check(remaining["revision"]==6 && remaining["evidence_count"]==1,"one support forgotten, surviving revision advanced");
  check(usage.usage(id)["stored_receipts"]==4,"receipt history preserved while support survives");
  memory::forget(b,"alpha",live2.event);
  check(store.read(id,"",true)["items"].empty(),"no orphan text in history");
  auto c=b.db().prepare("SELECT count(*) FROM memory_fact_usage WHERE fact_id=?");c.bind_text(1,id);check(c.step() && c.column_int(0)==0,"receipts cascade after last support");
  check(count(b,"memory_fact_archive")==0,"archive cascade after last support");
  const auto replay=memory::capture(b,"alpha",{{"session_id","n48q-synthetic"},{"fragment_id","active"},{"messages",J::array({{{"role","user"},{"content",live.quote}},{{"role","assistant"},{"content","I prefer FAKE_ASSISTANT."}}})}},true);
  check(replay["status"]=="forgotten","forgotten source replay blocked");
  // A bound original body altered behind the API cannot be published as evidence.
  auto update=b.db().prepare("UPDATE memory_items SET quote='I prefer FORGED' WHERE item_id=?");update.bind_text(1,a.item);update.step_done();
  // The other independent support remains valid, so only that reference is returned.
  check(get(store,f)["evidence_count"]==1,"forged support excluded independently");
  J observed={{"fact_id",expected},{"quote",full["object"]},{"confidence",full["confidence"]},
    {"first_support",full["evidence"][0]["item_id"]},{"retired_status",get(store,f)["status"]},
    {"last_support_removed",store.read(id,"",true)["items"].empty()},
    {"receipt_count_before_forget",receipt_snapshot["matched_receipts"]}};
  return observed;
}
void postgres_only(Brain& b){
  reset(b);auto e=seed(b,"pg-races"),e2=seed(b,"pg-races-second",e.quote);
  memory::FactStore store(b,"alpha");
  // Several distinct connections initialize and create the same assertion once.
  std::barrier start(4);std::atomic<int> created{0},duplicated{0},failed{0};std::vector<std::thread> threads;
  for(int i=0;i<4;++i)threads.emplace_back([&]{bool joined=false;try{auto w=worker();memory::FactStore s(*w,"alpha");joined=true;start.arrive_and_wait();auto f=make(s,e);if(f["duplicate"].get<bool>())++duplicated;else ++created;}catch(...){if(!joined)start.arrive_and_drop();++failed;}});
  for(auto& t:threads)t.join();
  check(created==1 && duplicated==3 && failed==0 && count(b,"memory_facts")==1,"concurrent initializer/idempotent create");
  auto f=make(store,e);const std::string id=f["fact_id"];
  check(memory::pg_fact::ready(b.db()),"canonical schema recognized");
  for(const auto* name:{"sources","pages","config","memory_module","memory_events","memory_items","memory_attempts",
      "memory_fact_module","memory_facts","memory_fact_evidence","memory_fact_relations",
      "memory_fact_lifecycle_module","memory_fact_archive","memory_fact_usage_module","memory_fact_usage"}){
    b.db().exec(std::string("CREATE TEMP TABLE ")+name+"(poison TEXT)");
    reject([&]{store.read();},"fact_pg_schema_context");
    b.db().exec(std::string("DROP TABLE pg_temp.")+name);
    check(!b.db().transaction_active(),"scope cleanup after name refusal");
  }
  b.db().exec("BEGIN");reject([&]{store.read();},"fact_transaction_active");check(b.db().transaction_active(),"caller transaction retained");b.db().exec("ROLLBACK");
  b.db().exec("BEGIN");try{b.db().exec("SELECT 1/0");}catch(...){}
  reject([&]{store.read();},"fact_transaction_active");check(b.db().transaction_active(),"failed caller transaction retained");b.db().exec("ROLLBACK");
  b.db().exec("SET client_encoding='SQL_ASCII'");reject([&]{store.read();},"fact_pg_schema_context");b.db().exec("SET client_encoding='UTF8'");
  b.db().exec("ALTER TABLE public.memory_fact_evidence DISABLE TRIGGER memory_fact_last_evidence");
  reject([&]{store.read();},"fact_schema_incomplete");
  b.db().exec("ALTER TABLE public.memory_fact_evidence ENABLE TRIGGER memory_fact_last_evidence");
  b.db().exec("ALTER FUNCTION public.qbrain_fact_evidence_gc_v1() SECURITY DEFINER");
  reject([&]{store.read();},"fact_schema_incomplete");
  b.db().exec("ALTER FUNCTION public.qbrain_fact_evidence_gc_v1() SECURITY INVOKER");
  b.db().exec("DROP INDEX public.idx_memory_facts_source;CREATE INDEX idx_memory_facts_source ON public.memory_facts(fact_id)");
  reject([&]{store.read();},"fact_schema_incomplete");
  b.db().exec("DROP INDEX public.idx_memory_facts_source;CREATE INDEX idx_memory_facts_source ON public.memory_facts(source_id,status,predicate,created_at,fact_id)");
  b.db().exec("ALTER TABLE public.memory_facts ALTER COLUMN object TYPE TEXT COLLATE \"POSIX\"");
  reject([&]{store.read();},"fact_schema_incomplete");
  b.db().exec("ALTER TABLE public.memory_facts ALTER COLUMN object TYPE TEXT COLLATE \"C\"");
  check(store.read()["items"].size()==1,"schema recovery fixture restored");
  // Internally owned read composes evidence/use checks, while another connection commits.
  {
    memory::pg_fact::ReadScope snapshot(b.db());
    auto first=store.read();check(first["items"].size()==1,"snapshot sees current fact");
    auto w=worker();memory::FactStore second(*w,"alpha");
    second.retract({{"fact_id",id},{"expected_revision",1}});
    check(store.read()==first,"read snapshot excludes concurrent committed retirement");
    reject([&]{store.retract({{"fact_id",id},{"expected_revision",1}});},"fact_transaction_active");
  }
  check(store.read()["items"].empty(),"new read sees retirement");
  // New active supported fact exercises receipt initialization from competing connections.
  auto e3=seed(b,"use-race","I decided to keep an exact Unicode 原话😀.");auto g=make(store,e3);
  created=0;duplicated=0;failed=0;threads.clear();std::barrier use_start(4);
  for(int i=0;i<4;++i)threads.emplace_back([&]{bool joined=false;try{auto w=worker();memory::FactUsageStore u(*w,"alpha");joined=true;use_start.arrive_and_wait();auto x=u.report_use(use(g,"race-receipt"));if(x["duplicate"].get<bool>())++duplicated;else ++created;}catch(...){if(!joined)use_start.arrive_and_drop();++failed;}});
  for(auto& t:threads)t.join();
  check(created==1 && duplicated==3 && failed==0,"concurrent identical receipts only one insert");
  memory::FactUsageStore u(b,"alpha");check(u.usage(g["fact_id"])["stored_receipts"]==1,"one actual stored receipt");
  // Metadata corruption must not be normalized into an empty/valid receipt set.
  b.db().exec("ALTER TABLE public.memory_fact_usage ALTER COLUMN reported_at TYPE NUMERIC");
  reject([&]{u.usage(g["fact_id"]);},"fact_usage_schema_incomplete");
  b.db().exec("ALTER TABLE public.memory_fact_usage ALTER COLUMN reported_at TYPE BIGINT");
  check(u.usage(g["fact_id"])["stored_receipts"]==1,"typed schema restored");
  // Explicit raw TRUNCATE is not a public API, but must not leave a copy of orphaned facts.
  b.db().exec("TRUNCATE public.memory_fact_evidence");
  check(count(b,"memory_facts")==0 && count(b,"memory_fact_usage")==0 && count(b,"memory_fact_relations")==0,"truncate support garbage-collects copies and receipts");
  check(store.read()["items"].empty(),"post-truncate read consistent");
  check(!b.db().transaction_active() && !memory::pg_fact::owned(b.db()),"no transaction leaked");
}
}
int main(int argc,char** argv){
  try{
    const bool only=argc==2 && std::string(argv[1])=="--sqlite-only";
    if(argc>1 && !only)throw std::runtime_error("unsupported test option");
    backend="sqlite";Brain s;s.open_at(":memory:");const auto sqlite=shared(s);const auto sqlite_count=checks.size();
    J postgres=nullptr;
    if(!only){
      const char* authorization=std::getenv("QBRAIN_PG_FACT_TEST_DISPOSABLE"),*connection=std::getenv("QBRAIN_PG_FACT_TEST_DSN");
      if(!authorization || std::string(authorization)!="1" || !connection || !*connection)throw std::runtime_error("explicit disposable PG service required");
      dsn=connection;backend="postgres";auto b=worker();postgres=shared(*b);
      check(postgres==sqlite,"cross-backend deterministic observed semantics");postgres_only(*b);
    }
    std::cout<<J{{"schema","qbrain-n48q-native-v1"},{"passed",true},{"sqlite_checks",sqlite_count},
      {"postgres_executed",!only},{"checks",checks},{"check_count",checks.size()},{"observations",{{"sqlite",sqlite},{"postgres",postgres}}}}.dump()<<'\n';return 0;
  }catch(const std::exception& e){std::cout<<J{{"schema","qbrain-n48q-native-v1"},{"passed",false},{"checks",checks},{"error",e.what()}}.dump()<<'\n';return 1;}
}
