#include "qbrain/memory/fact_store.hpp"
#include "qbrain/integration/detail/fact_context.hpp"
#include "qbrain/util/hash.hpp"
#include "qbrain/util/paths.hpp"
#include <barrier>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <thread>

namespace {
using namespace qbrain;using J=nlohmann::json;
int checks=0;J scenarios=J::array();
void check(bool ok,const char* label){if(!ok)throw std::runtime_error(label);++checks;}
template<class F> void scenario(const char* name,F f){const int n=checks;f();scenarios.push_back({{"name",name},{"status","PASS"},{"assertions",checks-n}});}
template<class F> void denied(F f,const std::string& code=""){
 try{f();}catch(const std::exception& e){check(code.empty()||code==e.what(),"expected stable error");return;}
 throw std::runtime_error("operation should have failed");
}
std::unique_ptr<Brain> fresh(){auto b=std::make_unique<Brain>();b->open_at(":memory:");b->ensure_source("alpha");b->ensure_source("beta");b->save_config_value("memory.writeback","all");return b;}
int64_t scalar(Brain& b,const std::string& sql){auto s=b.db().prepare(sql);check(s.step(),"scalar row");return s.column_int(0);}
std::string seed(Brain& b,const std::string& tag,const std::vector<std::string>& quotes={"我偏好不用图形界面，而用命令行。😀"},const std::string& source="alpha",int64_t expires=0){
 J messages=J::array();for(const auto& q:quotes)messages.push_back({{"role","user"},{"content",q}});
 const std::string id=memory::capture(b,source,{{"session_id","promotion"},{"fragment_id",tag},{"expires_at",expires},{"messages",messages}},true)["event_id"];
 auto r=memory::extract(b,source,id,"local");check(r["status"]=="extracted"||r["status"]=="no_matches","real local extraction");return id;
}
J facts(memory::FactStore& s,bool history=false){return s.read("","",history,50,32768)["items"];}
std::string item(Brain& b,const std::string& e){auto s=b.db().prepare("SELECT item_id FROM memory_items WHERE event_id=? ORDER BY message_index");s.bind_text(1,e);check(s.step(),"real memory item");return s.column_text(0);}
void basic(){
 scenario("local no-match events do not initialize fact schema",[]{
  auto b=fresh();const auto e=seed(*b,"none",{"An ordinary statement without a supported prefix."});memory::FactStore s(*b,"alpha");
  const auto n=scalar(*b,"SELECT COUNT(*) FROM sqlite_master");auto r=s.promote_event(e);
  check(r["counts"]["total"]==0 && r["items"].empty(),"no-match receipt");
  check(n==scalar(*b,"SELECT COUNT(*) FROM sqlite_master") && s.read()["initialized"]==false,"no lazy migration on empty event");
  const std::string a=memory::capture(*b,"alpha",{{"session_id","assistant"},{"fragment_id","one"},{"messages",J::array({{{"role","assistant"},{"content","I prefer an invented choice."}}})}},true)["event_id"];
  memory::extract(*b,"alpha",a);check(s.promote_event(a)["items"].empty(),"assistant not promoted");
 });
 scenario("all local categories preserve full original quotes and negation",[]{
  auto b=fresh();const std::vector<std::string> quotes={"我偏好不使用 MT5，而使用命令行。😀","I decided not to deploy.","I will check the complete message.","I learned that quoting matters.","I attended a synthetic meeting.","我使用测试工具。"};
  auto e=seed(*b,"categories",quotes);memory::FactStore s(*b,"alpha");auto r=s.promote_event(e);
  check(r["counts"]["total"]==6 && r["counts"]["created"]==6,"one fact per complete category quote");
  check(r["model_inference"]==false && r.dump().find("MT5")==std::string::npos,"receipt has no raw quote or inferred truth");
  auto rows=facts(s);check(rows.size()==6,"six facts stored");
  for(const auto& f:rows){check(f["confidence"].is_null() && f["untrusted_data"]==true,"not verified truth");check(f["evidence_count"]==1,"actual support");bool found=false;for(const auto& q:quotes)if(f["object"]==q)found=true;check(found,"object equals entire original message");check(f["predicate"].get<std::string>().rfind("memory.",0)==0,"fixed category predicate");}
  check(scalar(*b,"SELECT COUNT(*) FROM memory_fact_relations")==0 && scalar(*b,"SELECT COUNT(*) FROM jobs")==0,"no inferred relations or model jobs");
 });
 scenario("same-event replay and equal messages are idempotent",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto e=seed(*b,"twice",{"I prefer the same complete sentence.","I prefer the same complete sentence."});
  auto r=s.promote_event(e);check(r["counts"]["created"]==1 && r["counts"]["attached"]==1,"two messages one fact two supports");
  const int changes=sqlite3_total_changes(b->db().handle());r=s.promote_event(e);
  check(r["counts"]["duplicate"]==2 && sqlite3_total_changes(b->db().handle())==changes,"replay does not write or advance revisions");
  check(facts(s)[0]["revision"]==2 && facts(s)[0]["evidence_count"]==2,"stable replay revision");
 });
 scenario("independent equal events attach without merging manual predicates",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"a"),c=seed(*b,"c");
  s.create({{"predicate","manual.interface"},{"item_id",item(*b,a)}});
  auto r=s.promote_event(a);const auto id=r["items"][0]["fact_id"];
  r=s.promote_event(c);check(r["counts"]["attached"]==1 && r["items"][0]["fact_id"]==id,"same-predicate equal quote support");
  check(scalar(*b,"SELECT COUNT(*) FROM memory_facts")==2,"manual predicate is not merged or overwritten");
  check(s.read(id)["items"][0]["evidence_count"]==2,"two independent supports");
 });
 scenario("retired equal quotes veto automatic promotion across predicates",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"a"),c=seed(*b,"c");
  auto f=s.create({{"predicate","manual.preference"},{"item_id",item(*b,a)}});
  s.retract({{"fact_id",f["fact_id"]},{"expected_revision",1}});auto r=s.promote_event(c);
  check(r["counts"]["skipped_retired"]==1 && r["counts"]["created"]==0,"repeated quote cannot auto-revive retirement");
  check(facts(s).empty() && facts(s,true)[0]["revision"]==2,"retired status and revision untouched");
  auto newer=s.create({{"predicate","manual.preference"},{"item_id",item(*b,c)}});
  check(newer["status"]=="active","manual create semantics retained");
  check(s.promote_event(c)["counts"]["skipped_retired"]==1,"automatic veto does not undo manual choice");
 });
 scenario("superseded statements stay retired when repeated",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto e=seed(*b,"old"),n=seed(*b,"new",{"I prefer another choice."});
  auto a=s.promote_event(e)["items"][0],c=s.promote_event(n)["items"][0];
  s.supersede({{"fact_id",a["fact_id"]},{"replacement_id",c["fact_id"]},{"expected_revision",1}});
  check(s.promote_event(seed(*b,"repeat"))["counts"]["skipped_retired"]==1,"supersession cannot be reset by new support");
  check(facts(s).size()==1 && facts(s)[0]["fact_id"]==c["fact_id"],"only replacement active");
 });
 scenario("support cap is explicit and never creates overflow facts",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");std::string first;
  for(int i=0;i<17;++i){auto e=seed(*b,"cap-"+std::to_string(i));if(i==0)first=e;auto r=s.promote_event(e);check(r["counts"][i==0?"created":i<16?"attached":"skipped_limit"]==1,"exact support cap outcome");}
  check(scalar(*b,"SELECT COUNT(*) FROM memory_facts")==1 && facts(s)[0]["evidence_count"]==16,"bounded support, no duplicate overflow");
  check(s.promote_event(first)["counts"]["duplicate"]==1,"existing support stays duplicate at cap");
 });
}
void integrity(){
 scenario("strict IDs local method and source boundaries",[]{
  auto b=fresh();memory::FactStore a(*b,"alpha"),other(*b,"beta");auto e=seed(*b,"a");
  for(const auto& id:std::vector<std::string>{"","x",std::string(64,'A'),std::string("a\0b",3)})denied([&]{a.promote_event(id);},"fact_invalid_id");
  denied([&]{other.promote_event(e);},"fact_event_unavailable");
  b->db().exec("UPDATE memory_events SET method='model'");denied([&]{a.promote_event(e);},"fact_local_extraction_required");
  check(a.read()["initialized"]==false,"invalid selection never initializes facts");
 });
 scenario("all evidence preflight rejects invalid batches before initialization",[]{
  for(const auto& mutation:std::vector<std::string>{"UPDATE memory_items SET quote='forged' WHERE message_index=1","UPDATE pages SET deleted_at='gone'","UPDATE memory_events SET expires_at=1","UPDATE memory_events SET status='archived'","UPDATE pages SET content_hash='changed'"}){
   auto b=fresh();memory::FactStore s(*b,"alpha");auto e=seed(*b,"bad",{"I prefer valid first.","I decided valid second."});b->db().exec(mutation);denied([&]{s.promote_event(e);});
   check(scalar(*b,"SELECT COUNT(*) FROM sqlite_master WHERE name='memory_facts'")==0,"invalid batch has no preparatory fact migration");
  }
 });
 scenario("fact and evidence batch rollback is atomic on injected failure",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");s.promote_event(seed(*b,"prior"));auto e=seed(*b,"batch",{"I prefer first new choice.","I decided second new choice."});
  auto n=scalar(*b,"SELECT COUNT(*) FROM memory_facts"),m=scalar(*b,"SELECT COUNT(*) FROM memory_fact_evidence");
  b->db().exec("CREATE TRIGGER fail_second BEFORE INSERT ON memory_fact_evidence WHEN (SELECT category FROM memory_items WHERE item_id=NEW.item_id)='decision' BEGIN SELECT RAISE(ABORT,'fixture');END;");
  denied([&]{s.promote_event(e);});check(scalar(*b,"SELECT COUNT(*) FROM memory_facts")==n && scalar(*b,"SELECT COUNT(*) FROM memory_fact_evidence")==m,"no partial fact or support survives");
  b->db().exec("DROP TRIGGER fail_second");check(s.promote_event(e)["counts"]["created"]==2,"explicit retry succeeds after fault removed");
 });
 scenario("failed first batch may leave prepared schema but no fact writes",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto e=seed(*b,"first-failure");
  sqlite3_set_authorizer(b->db().handle(),[](void*,int action,const char* table,const char*,const char*,const char*){
   return action==SQLITE_INSERT && table && std::string(table)=="memory_fact_evidence"?SQLITE_DENY:SQLITE_OK;
  },nullptr);
  denied([&]{s.promote_event(e);});sqlite3_set_authorizer(b->db().handle(),nullptr,nullptr);
  check(s.read()["initialized"]==true && scalar(*b,"SELECT COUNT(*) FROM memory_facts")==0 && scalar(*b,"SELECT COUNT(*) FROM memory_fact_evidence")==0,"preparatory schema separate from atomic fact batch");
  check(s.promote_event(e)["counts"]["created"]==1,"explicit retry on prepared module");
 });
 scenario("support forgetting retains remaining evidence and removes final copies",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"a"),c=seed(*b,"c");s.promote_event(a);s.promote_event(c);
  memory::forget(*b,"alpha",a);check(facts(s).size()==1 && facts(s)[0]["evidence_count"]==1,"remaining support valid");
  denied([&]{s.promote_event(a);},"fact_event_unavailable");memory::forget(*b,"alpha",c);
  check(facts(s,true).empty() && scalar(*b,"SELECT COUNT(*) FROM memory_fact_evidence")==0,"last-support cleanup removes fact copies");
 });
 scenario("wall-clock expiry blocks promotion and recall",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");const auto until=std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count()+2;
  auto e=seed(*b,"expiry",{"I prefer a temporary choice."},"alpha",until);check(s.promote_event(e)["counts"]["created"]==1,"live item promoted");
  std::this_thread::sleep_until(std::chrono::system_clock::time_point(std::chrono::seconds(until+1)));
  denied([&]{s.promote_event(e);},"fact_event_unavailable");check(facts(s).empty(),"expiry revalidated without cleanup");
 });
 scenario("maximum batch has bounded receipts and no implicit relations",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");std::vector<std::string> messages;for(int i=0;i<32;++i)messages.push_back("I prefer choice "+std::to_string(i)+".");
  auto e=seed(*b,"full",messages);auto r=s.promote_event(e);check(r["counts"]["total"]==32 && r["items"].size()==32 && r.dump().size()<=32768,"full bounded batch");
  check(scalar(*b,"SELECT COUNT(*) FROM memory_fact_relations")==0,"different values are not inferred conflicts");
  check(s.promote_event(e)["counts"]["duplicate"]==32,"full-batch replay");
 });
 scenario("caller transactions are never committed or rolled back by promotion",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto e=seed(*b,"nested");b->db().exec("BEGIN;INSERT INTO facts(entity_slug,object_text) VALUES('caller','KEEP')");
  denied([&]{s.promote_event(e);},"fact_transaction_active");check(sqlite3_get_autocommit(b->db().handle())==0 && scalar(*b,"SELECT COUNT(*) FROM facts WHERE entity_slug='caller'")==1,"caller transaction retained");
  b->db().exec("ROLLBACK");check(scalar(*b,"SELECT COUNT(*) FROM facts WHERE entity_slug='caller'")==0,"caller controls rollback");
 });
}
void concurrent(){
 scenario("independent connections promote one event exactly once",[]{
  namespace fs=std::filesystem;auto dir=fs::temp_directory_path()/("qbrain-promote-"+util::sha256_hex(std::to_string(std::chrono::steady_clock::now().time_since_epoch().count())).substr(0,16));fs::create_directory(dir);
  {Brain setup;auto path=util::path_to_utf8(dir/"brain.db");setup.open_at(path);setup.ensure_source("alpha");setup.save_config_value("memory.writeback","all");auto e=seed(setup,"race",{"I prefer first.","I decided second."});
   Brain one,two;one.open_at(path);two.open_at(path);one.db().exec("PRAGMA busy_timeout=123");two.db().exec("PRAGMA busy_timeout=456");std::barrier start(3);J a,b;std::exception_ptr ae,be;
   std::thread x([&]{start.arrive_and_wait();try{a=memory::FactStore(one,"alpha").promote_event(e);}catch(...){ae=std::current_exception();}}),y([&]{start.arrive_and_wait();try{b=memory::FactStore(two,"alpha").promote_event(e);}catch(...){be=std::current_exception();}});
   start.arrive_and_wait();x.join();y.join();if(ae)std::rethrow_exception(ae);if(be)std::rethrow_exception(be);
   check(a["counts"]["created"].get<int>()+b["counts"]["created"].get<int>()==2 && a["counts"]["duplicate"].get<int>()+b["counts"]["duplicate"].get<int>()==2,"one complete create and one duplicate batch");
   check(scalar(setup,"SELECT COUNT(*) FROM memory_facts")==2 && scalar(setup,"SELECT COUNT(*) FROM memory_fact_evidence")==2,"no race duplicates");
   check(scalar(one,"PRAGMA busy_timeout")==123 && scalar(two,"PRAGMA busy_timeout")==456,"caller busy timeouts restored");
   auto blocked=seed(setup,"blocked",{"I prefer bounded waits."});two.db().exec("BEGIN IMMEDIATE");auto before=std::chrono::steady_clock::now();denied([&]{memory::FactStore(one,"alpha").promote_event(blocked);});
   const auto elapsed=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-before).count();check(elapsed>=2000 && elapsed<8000,"one bounded writer wait");
   check(scalar(one,"PRAGMA busy_timeout")==123,"timeout restored on acquisition failure");two.db().exec("ROLLBACK");check(memory::FactStore(one,"alpha").promote_event(blocked)["counts"]["created"]==1,"explicit retry only");
   auto changed=seed(setup,"preflight-race",{"I prefer a preflight race."});
   struct Interleave {Brain* writer;std::string event;bool fired=false;std::exception_ptr error;} interleave{&setup,changed};
   sqlite3_trace_v2(one.db().handle(),SQLITE_TRACE_STMT,[](unsigned,void* ptr,void*,void* sql)->int{
    auto& c=*static_cast<Interleave*>(ptr);
    if(!c.fired && sql && std::string(static_cast<const char*>(sql))=="BEGIN IMMEDIATE"){
     c.fired=true;try{auto st=c.writer->db().prepare("UPDATE memory_items SET quote='forged after preflight' WHERE event_id=?");st.bind_text(1,c.event);st.step_done();}catch(...){c.error=std::current_exception();}
    }return 0;
   },&interleave);
   const auto before_count=scalar(setup,"SELECT COUNT(*) FROM memory_facts");
   denied([&]{memory::FactStore(one,"alpha").promote_event(changed);},"fact_evidence_unavailable");
   sqlite3_trace_v2(one.db().handle(),0,nullptr,nullptr);if(interleave.error)std::rethrow_exception(interleave.error);
   check(interleave.fired && scalar(setup,"SELECT COUNT(*) FROM memory_facts")==before_count,"second WAL connection invalidation is revalidated inside write transaction");
   bool backup=false;for(const auto& p:fs::directory_iterator(dir))if(p.path().filename().string().find(".pre-facts-v1-")!=std::string::npos)backup=true;check(backup,"initialization preserved actual backup");
  }fs::remove_all(dir);
 });
 scenario("promoted facts feed existing context without changing legacy tables",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto e=seed(*b,"context",{"I prefer needle command line, not a GUI."});b->db().exec("INSERT INTO facts(entity_slug,object_text) VALUES('legacy','KEEP')");const auto version=scalar(*b,"SELECT MAX(version) FROM schema_version");
  s.promote_event(e);const auto r=integration::detail::compose_fact_context(*b,"alpha","SessionStart","",8192,8,{});
  check(r["fact_group_count"]==1 && r["memory_count"]==0,"existing composer uses promoted facts without duplicate raw lane");
  check(scalar(*b,"SELECT MAX(version) FROM schema_version")==version && scalar(*b,"SELECT COUNT(*) FROM facts WHERE object_text='KEEP'")==1,"legacy table and schema version unchanged");
 });
}
}
void test_n47e(){checks=0;scenarios=J::array();basic();integrity();concurrent();std::cout<<"N47E local fact promotion: "<<scenarios.size()<<" scenarios, "<<checks<<" checks passed\n";}
#ifdef QBRAIN_PROMOTION_STANDALONE
int main(int argc,char** argv){try{test_n47e();if(argc==3&&std::string(argv[1])=="--report"){std::ofstream f(argv[2],std::ios::binary);f<<J({{"result","PASS"},{"scenarios",scenarios},{"scenario_count",scenarios.size()},{"checks",checks}}).dump(2)<<'\n';if(!f)throw std::runtime_error("report write failed");}else if(argc!=1)throw std::runtime_error("arguments");return 0;}catch(const std::exception& e){std::cerr<<"[FAIL] N47E: "<<e.what()<<'\n';return 1;}}
#endif
