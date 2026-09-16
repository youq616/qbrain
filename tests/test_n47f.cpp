#include "qbrain/memory/fact_store.hpp"
#include "qbrain/integration/detail/fact_context.hpp"
#include "qbrain/util/hash.hpp"
#include "qbrain/util/paths.hpp"
#include <atomic>
#include <barrier>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <thread>

namespace {
using namespace qbrain;
using J=nlohmann::json;
int checks=0; J scenarios=J::array();
void check(bool ok,const char* message){if(!ok)throw std::runtime_error(message);++checks;}
template<class F> void scenario(const char* name,F f){const int before=checks;f();scenarios.push_back({{"name",name},{"status","PASS"},{"assertions",checks-before}});}
template<class F> void denied(F f,const std::string& code=""){
  try{f();}catch(const std::exception& e){check(code.empty()||e.what()==code,"expected error code");return;}
  throw std::runtime_error("expected rejection");
}
int64_t scalar(Brain& b,const std::string& sql){auto s=b.db().prepare(sql);check(s.step(),"scalar row");return s.column_int(0);}
std::unique_ptr<Brain> fresh(){auto b=std::make_unique<Brain>();b->open_at(":memory:");b->ensure_source("alpha");b->ensure_source("beta");b->save_config_value("memory.writeback","all");return b;}
struct Seed{std::string id,event,item,quote;};
Seed seed(Brain& b,const std::string& tag,const std::string& quote="我偏好不用图形界面，而用命令行。😀",const std::string& source="alpha",int64_t expires=0){
  const std::string event=memory::capture(b,source,{{"session_id","lifecycle"},{"fragment_id",tag},{"expires_at",expires},{"messages",J::array({{{"role","user"},{"content",quote}}})}},true)["event_id"];
  memory::extract(b,source,event);
  const auto promoted=memory::FactStore(b,source).promote_event(event);
  check(promoted["items"].size()==1,"one actual promoted item");
  return {promoted["items"][0]["fact_id"],event,promoted["items"][0]["item_id"],quote};
}
J payload(const std::string& id,int64_t revision){return {{"fact_id",id},{"expected_revision",revision}};}
J fact(memory::FactStore& s,const Seed& f,bool history=false){auto r=s.read(f.id,"",history);check(r["items"].size()==1,"valid fact readable");return r["items"][0];}
int64_t rev(memory::FactStore& s,const Seed& f){return fact(s,f,true)["revision"];}
std::filesystem::path unique_dir(){auto p=std::filesystem::temp_directory_path()/("qbrain-lifecycle-"+util::sha256_hex(std::to_string(std::chrono::steady_clock::now().time_since_epoch().count())).substr(0,20));std::filesystem::create_directory(p);return p;}
void simple(){
 scenario("fresh lifecycle reads and restore no-op do not initialize",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto n=scalar(*b,"SELECT COUNT(*) FROM sqlite_master");
  auto r=s.lifecycle();check(!r["initialized"].get<bool>() && r["items"].empty(),"empty lazy view");
  check(scalar(*b,"SELECT COUNT(*) FROM sqlite_master")==n,"no read migration");
  auto f=seed(*b,"one");n=scalar(*b,"SELECT COUNT(*) FROM sqlite_master");
  const auto changes=sqlite3_total_changes(b->db().handle());
  check(s.restore(payload(f.id,1))["duplicate"]==true,"restore without archive no-op");
  check(!s.lifecycle()["archive_initialized"].get<bool>(),"no restore migration");
  check(sqlite3_total_changes(b->db().handle())==changes,"restore no-op writes nothing");
  check(scalar(*b,"SELECT COUNT(*) FROM sqlite_master")==n,"old schema unchanged");
 });
 scenario("explicit archive restore keep quote evidence and retirement status",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto f=seed(*b,"one");auto original=fact(s,f);
  const auto result=s.archive(payload(f.id,1));check(result["archived"]==true && result["revision"]==2,"archive advances revision");
  auto read=fact(s,f);check(read["object"]==original["object"] && read["evidence"]==original["evidence"] && read["status"]=="active","evidence and status unchanged");
  check(s.recall("命令行")["items"].empty(),"archived anchor excluded");
  check(s.lifecycle(f.id)["items"][0]["lifecycle"]["archived"]==true,"archive visible in inspection");
  check(s.archive(payload(f.id,2))["duplicate"]==true && rev(s,f)==2,"idempotent at current revision");
  denied([&]{s.restore(payload(f.id,1));},"fact_revision_conflict");
  check(s.restore(payload(f.id,2))["revision"]==3,"restore advances revision");
  check(!s.recall("命令行")["items"].empty(),"restore re-enables anchor");
  check(scalar(*b,"SELECT COUNT(*) FROM memory_fact_archive")==0,"restore removes policy row");
  check(scalar(*b,"SELECT COUNT(*) FROM pragma_table_info('memory_fact_archive')")==3,"policy stores no quote copy");
 });
 scenario("archive never suppresses required direct counter-evidence",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"a","I prefer terminal interface."),z=seed(*b,"z","I prefer graphical interface.");
  s.contradict({{"fact_id",a.id},{"other_id",z.id}});
  s.archive(payload(z.id,2));
  auto r=s.recall("terminal");check(r["items"].size()==1 && r["items"][0]["facts"].size()==2,"archived counterclaim retained");
  check(r["items"][0]["contradictions"].size()==1,"explicit edge retained");
  check(s.recall("graphical")["items"].empty(),"archived matching anchor not reintroduced");
  check(s.conflicts()["items"].size()==1,"explicit conflict inspection unchanged");
  s.archive(payload(a.id,2));check(s.recall_for_hook({})["items"].empty(),"all archived means no anchors");
  check(s.conflicts()["items"].size()==1,"all archived conflicts remain inspectable");
 });
 scenario("Hook composition excludes archived ordinary-memory bypass",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto f=seed(*b,"one");s.archive(payload(f.id,1));
  auto out=integration::detail::compose_fact_context(*b,"alpha","SessionStart","",8192,8);
  check(out.dump().find(f.quote)==std::string::npos,"archived quote not supplied as ordinary memory");
  check(!memory::read(*b,"alpha","命令行")["items"].empty(),"standalone memory semantics unchanged");
  s.restore(payload(f.id,2));out=integration::detail::compose_fact_context(*b,"alpha","SessionStart","",8192,8);
  // Quotes are escaped inside the outer Hook JSON; decoded context preserves UTF8.
  check(out.dump().find("命令行")!=std::string::npos,"restored quote enters opted-in composition");
 });
 scenario("promotion and duplicate create cannot remove archive policy",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto f=seed(*b,"one");s.archive(payload(f.id,1));
  auto second=seed(*b,"two");check(second.id==f.id && rev(s,f)==3,"fresh equal support attaches");
  check(s.recall("命令行")["items"].empty(),"promotion never restores same archived fact");
  check(s.create({{"predicate","memory.preference"},{"item_id",f.item}})["duplicate"]==true,"create retry is duplicate");
  check(s.lifecycle(f.id)["items"][0]["lifecycle"]["archived"]==true,"policy remains archived");
 });
 scenario("retirement and invalid evidence cannot be restored",[]{
  for(const auto* mutation:{"UPDATE memory_items SET quote='forged'","UPDATE pages SET deleted_at='gone'","UPDATE memory_events SET expires_at=1","DELETE FROM memory_items"}){
   auto b=fresh();memory::FactStore s(*b,"alpha");auto f=seed(*b,"one");s.archive(payload(f.id,1));b->db().exec(mutation);
   denied([&]{s.restore(payload(f.id,2));},"fact_not_found");check(s.lifecycle()["items"].empty(),"invalid fact hidden from lifecycle");
  }
  auto b=fresh();memory::FactStore s(*b,"alpha");auto f=seed(*b,"one");s.archive(payload(f.id,1));s.retract(payload(f.id,2));
  denied([&]{s.restore(payload(f.id,3));},"fact_state_conflict");
  check(fact(s,f,true)["status"]=="retracted","restore does not reverse retirement");
 });
 scenario("wall-clock expiry and supersession are not reversible archival",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");
  const auto until=std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count()+2;
  auto f=seed(*b,"expiry","I prefer a temporary original claim.","alpha",until);
  s.archive(payload(f.id,1));
  std::this_thread::sleep_until(std::chrono::system_clock::time_point(std::chrono::seconds(until+1)));
  denied([&]{s.restore(payload(f.id,2));},"fact_not_found");
  check(s.lifecycle(f.id)["items"].empty(),"actual expiry removes live lifecycle result");
  auto old=seed(*b,"old","I prefer former settings."),newer=seed(*b,"new","I prefer revised settings.");
  s.archive(payload(old.id,1));
  s.supersede({{"fact_id",old.id},{"replacement_id",newer.id},{"expected_revision",2}});
  denied([&]{s.restore(payload(old.id,3));},"fact_state_conflict");
  check(fact(s,old,true)["status"]=="superseded","restore cannot reverse explicit supersession");
 });
 scenario("last support forget cascades archival metadata",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto f=seed(*b,"one"),g=seed(*b,"two");s.archive(payload(f.id,2));
  memory::forget(*b,"alpha",f.event);check(scalar(*b,"SELECT COUNT(*) FROM memory_fact_archive")==1,"remaining independent support retains policy");
  memory::forget(*b,"alpha",g.event);check(scalar(*b,"SELECT COUNT(*) FROM memory_fact_archive")==0,"last support removes archive metadata");
  check(scalar(*b,"SELECT COUNT(*) FROM memory_facts")==0,"fact copy removed");
  denied([&]{s.restore(payload(f.id,4));},"fact_not_found");
 });
}
void boundaries(){
 scenario("advisory age boundary newest valid support and clock anomalies",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto f=seed(*b,"first"),second=seed(*b,"second");
  auto now=s.lifecycle(f.id)["evaluated_at"].get<int64_t>();
  b->db().exec("UPDATE memory_items SET created_at="+std::to_string(now-86400));
  check(s.lifecycle(f.id,"",1)["items"][0]["lifecycle"]["age_state"]=="stale","exact threshold stale");
  auto update=b->db().prepare("UPDATE memory_items SET created_at=? WHERE item_id=?");update.bind_int(1,now);update.bind_text(2,second.item);update.step_done();
  check(s.lifecycle(f.id,"",1)["items"][0]["lifecycle"]["age_state"]=="fresh","newest valid independent support");
  b->db().exec("UPDATE memory_items SET created_at=9223372036854775807");
  auto age=s.lifecycle(f.id)["items"][0]["lifecycle"];check(age["age_state"]=="clock_anomaly" && age["age_seconds"].is_null(),"future timestamp not freshness proof");
  b->db().exec("UPDATE memory_items SET created_at=-1");
  check(s.lifecycle(f.id)["items"][0]["lifecycle"]["age_state"]=="unknown","negative timestamps unknown");
  check(rev(s,f)==2 && s.lifecycle()["usage_measured"]==false,"age never changes revision or counts reads");
 });
 scenario("source filters and strict inputs fail closed",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha"),t(*b,"beta");auto f=seed(*b,"one");
  denied([&]{t.archive(payload(f.id,1));},"fact_not_found");check(t.lifecycle(f.id)["items"].empty(),"read id cannot switch source");
  for(const auto& val:J::array({true,1.5,"1",0,-1,2147483647,nullptr}))denied([&]{s.archive({{"fact_id",f.id},{"expected_revision",val}});},"fact_invalid_revision");
  denied([&]{s.archive({{"fact_id",f.id},{"expected_revision",1},{"confidence",0.9}});},"fact_unexpected_argument");
  denied([&]{s.archive(payload("bad",1));},"fact_invalid_id");
  for(int days:{0,-1,36501})denied([&]{s.lifecycle("","",days);},"fact_invalid_stale_days");
  denied([&]{s.lifecycle("","",180,0);},"invalid_read_budget");
  denied([&]{s.lifecycle("","",180,10,511);},"invalid_read_budget");
  check(s.lifecycle("","other")["items"].empty(),"exact predicate");
 });
 scenario("read only budgets and existing caller transactions",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto f=seed(*b,"one");s.archive(payload(f.id,1));
  int before=sqlite3_total_changes(b->db().handle());
  sqlite3_set_authorizer(b->db().handle(),[](void*,int a,const char*,const char*,const char*,const char*){
    return a==SQLITE_INSERT || a==SQLITE_UPDATE || a==SQLITE_DELETE || a==SQLITE_CREATE_TABLE?SQLITE_DENY:SQLITE_OK;
  },nullptr);
  auto r=s.lifecycle("","",180,50,512);check(r.dump().size()<=512 && r["truncated"]==true && r["items"].empty(),"no partial oversized fact");
  (void)s.lifecycle();(void)s.recall_for_hook({});
  sqlite3_set_authorizer(b->db().handle(),nullptr,nullptr);
  check(sqlite3_total_changes(b->db().handle())==before,"read only APIs make no writes");
  b->db().exec("BEGIN;INSERT INTO facts(entity_slug,object_text) VALUES('owner','KEEP')");
  (void)s.lifecycle();denied([&]{s.restore(payload(f.id,2));},"fact_transaction_active");
  check(sqlite3_get_autocommit(b->db().handle())==0,"caller owns transaction");b->db().exec("ROLLBACK");
  check(scalar(*b,"SELECT COUNT(*) FROM facts WHERE object_text='KEEP'")==0,"caller can roll back");
 });
 scenario("malformed module foreign keys and atomic migration failure",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto f=seed(*b,"one");
  sqlite3_set_authorizer(b->db().handle(),[](void*,int a,const char* name,const char*,const char*,const char*){
    return a==SQLITE_CREATE_TABLE && name && std::string(name)=="memory_fact_archive"?SQLITE_DENY:SQLITE_OK;
  },nullptr);
  denied([&]{s.archive(payload(f.id,1));});sqlite3_set_authorizer(b->db().handle(),nullptr,nullptr);
  check(scalar(*b,"SELECT COUNT(*) FROM sqlite_master WHERE name LIKE 'memory_fact_lifecycle%'")==0,"DDL rolls back atomically");
  s.archive(payload(f.id,1));b->db().exec("PRAGMA foreign_keys=OFF");denied([&]{s.lifecycle();},"fact_foreign_keys_required");b->db().exec("PRAGMA foreign_keys=ON");
  b->db().exec("DROP TABLE memory_fact_lifecycle_module;CREATE TABLE memory_fact_lifecycle_module(version INTEGER);INSERT INTO memory_fact_lifecycle_module VALUES(2)");
  denied([&]{s.recall("命令行");},"fact_lifecycle_version_unsupported");
  b->db().exec("UPDATE memory_fact_lifecycle_module SET version=1;DROP TABLE memory_fact_archive");
  denied([&]{s.lifecycle();},"fact_lifecycle_schema_incomplete");
 });
 scenario("transition failure rolls back metadata and revision together",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto f=seed(*b,"one");s.archive(payload(f.id,1));s.restore(payload(f.id,2));
  b->db().exec("CREATE TRIGGER fail_lifecycle BEFORE UPDATE ON memory_facts BEGIN SELECT RAISE(ABORT,'injected');END");
  denied([&]{s.archive(payload(f.id,3));});check(scalar(*b,"SELECT COUNT(*) FROM memory_fact_archive")==0 && rev(s,f)==3,"failed archive atomic");
  b->db().exec("DROP TRIGGER fail_lifecycle");s.archive(payload(f.id,3));
  b->db().exec("CREATE TRIGGER fail_lifecycle BEFORE UPDATE ON memory_facts BEGIN SELECT RAISE(ABORT,'injected');END");
  denied([&]{s.restore(payload(f.id,4));});check(scalar(*b,"SELECT COUNT(*) FROM memory_fact_archive")==1 && rev(s,f)==4,"failed restore atomic");
 });
 scenario("archived matches excluded before candidate cap",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto f=seed(*b,"one","I prefer needle older.");
  auto e=seed(*b,"other","I prefer needle newer.");
  for(int n=0;n<103;++n){auto g=s.create({{"predicate","p"+std::to_string(n)},{"item_id",e.item}});s.archive(payload(g["fact_id"],1));}
  s.archive(payload(e.id,1));auto r=s.recall("needle");check(r["items"].size()==1 && r["items"][0]["match_fact_id"]==f.id,"archive filter precedes cap");
 });
}
void real_connections(){
 scenario("disk backup and fixed two connection optimistic race",[]{
  const auto dir=unique_dir();const auto file=util::path_to_utf8(dir/"brain.db");
  {Brain a,b;a.open_at(file);a.ensure_source("alpha");a.save_config_value("memory.writeback","all");auto f=seed(a,"one");b.open_at(file);
   memory::FactStore sa(a,"alpha"),sb(b,"alpha");auto version=scalar(a,"SELECT MAX(version) FROM schema_version");
   // Both independent writers start together; exactly one current-revision transition.
   std::barrier start(3);std::string ea,eb;auto worker=[&](memory::FactStore& st,std::string& error){start.arrive_and_wait();try{st.archive(payload(f.id,1));}catch(const std::exception& e){error=e.what();}};
   std::thread t1(worker,std::ref(sa),std::ref(ea)),t2(worker,std::ref(sb),std::ref(eb));start.arrive_and_wait();t1.join();t2.join();
   check(int(ea.empty())+int(eb.empty())==1 && (ea=="fact_revision_conflict" || eb=="fact_revision_conflict"),"single archive winner with stale loser");
   check(rev(sa,f)==2 && scalar(a,"PRAGMA busy_timeout")==0,"exact revision and timeout restore");
   std::barrier restore_start(3);ea.clear();eb.clear();
   auto restore_worker=[&](memory::FactStore& st,std::string& error){restore_start.arrive_and_wait();try{st.restore(payload(f.id,2));}catch(const std::exception& e){error=e.what();}};
   std::thread r1(restore_worker,std::ref(sa),std::ref(ea)),r2(restore_worker,std::ref(sb),std::ref(eb));
   restore_start.arrive_and_wait();r1.join();r2.join();
   check(int(ea.empty())+int(eb.empty())==1 && (ea=="fact_revision_conflict" || eb=="fact_revision_conflict"),"single restore winner with stale loser");
   check(rev(sa,f)==3 && scalar(a,"SELECT COUNT(*) FROM memory_fact_archive")==0,"restore no lost update");
   check(scalar(a,"SELECT MAX(version) FROM schema_version")==version,"legacy migration version unchanged");
   int backups=0;bool all_open=true,all_before=true,all_closed=true;
   for(const auto& entry:std::filesystem::directory_iterator(dir)){
    if(entry.path().filename().string().find(".pre-lifecycle-v1-")==std::string::npos)continue;++backups;
    sqlite3* db=nullptr;sqlite3_stmt* stmt=nullptr;
    const bool opened=sqlite3_open_v2(util::path_to_utf8(entry.path()).c_str(),&db,SQLITE_OPEN_READONLY,nullptr)==SQLITE_OK;
    all_open=all_open&&opened;
    const bool prepared=opened && sqlite3_prepare_v2(db,"SELECT count(*) FROM sqlite_master WHERE name='memory_fact_archive'",-1,&stmt,nullptr)==SQLITE_OK;
    const bool prior=prepared && sqlite3_step(stmt)==SQLITE_ROW && sqlite3_column_int(stmt,0)==0;
    all_before=all_before&&prior;
    const int finalized=sqlite3_finalize(stmt),closed=sqlite3_close(db);
    all_closed=all_closed&&finalized==SQLITE_OK&&closed==SQLITE_OK;
   }
   // Scheduling may yield one or two backups. Inspect every file but count the
   // same five invariants, not one assertion pair per timing-dependent file.
   check(backups>=1,"on-disk backup exists");check(backups<=2,"only racing writers created backups");
   check(all_open,"all backups readable");check(all_before,"every backup precedes new table");
   check(all_closed,"all backup readers finalized and closed");
  }std::filesystem::remove_all(dir);
 });
 scenario("first archive committed mid read preserves coherent snapshot",[]{
  const auto dir=unique_dir();const auto file=util::path_to_utf8(dir/"brain.db");
  {Brain a,b;a.open_at(file);a.ensure_source("alpha");a.save_config_value("memory.writeback","all");auto f=seed(a,"one");b.open_at(file);
   memory::FactStore sa(a,"alpha"),sb(b,"alpha");
   struct State{memory::FactStore* writer;std::string id,error;bool fired=false;} state{&sb,f.id,"",false};
   sqlite3_trace_v2(a.db().handle(),SQLITE_TRACE_STMT,[](unsigned,void* ctx,void*,void* sql)->int{
     auto& s=*static_cast<State*>(ctx);const std::string text=sql?static_cast<const char*>(sql):"";
     if(!s.fired && text.find("SELECT fact_id FROM memory_facts WHERE source_id=?")==0){s.fired=true;try{s.writer->archive(payload(s.id,1));}catch(const std::exception& e){s.error=e.what();}}return 0;
   },&state);
   auto r=sa.recall("命令行");sqlite3_trace_v2(a.db().handle(),0,nullptr,nullptr);
   check(state.fired && state.error.empty(),"second real connection commits first archive");
   check(r["items"].size()==1,"in-progress read retains prior snapshot");
   check(sa.recall("命令行")["items"].empty(),"next call sees committed policy");
   check(sa.lifecycle(f.id)["items"][0]["lifecycle"]["archived"]==true,"next inspection sees archive");
  }std::filesystem::remove_all(dir);
 });
}
}
void test_n47f(){checks=0;scenarios=J::array();simple();boundaries();real_connections();std::cout<<"N47F lifecycle: "<<scenarios.size()<<" scenarios, "<<checks<<" checks passed\n";}
#ifdef QBRAIN_LIFECYCLE_STANDALONE
int main(int argc,char** argv){try{test_n47f();if(argc==3 && std::string(argv[1])=="--report"){
 std::ofstream out(argv[2],std::ios::binary);if(!out)throw std::runtime_error("report open failed");
 out<<J({{"result","PASS"},{"scenarios",scenarios},{"scenario_count",scenarios.size()},{"checks",checks}}).dump(2)<<'\n';if(!out)throw std::runtime_error("report write failed");
 }else if(argc!=1)throw std::runtime_error("invalid arguments");return 0;}catch(const std::exception& e){std::cerr<<"[FAIL] N47F: "<<e.what()<<'\n';return 1;}}
#endif
