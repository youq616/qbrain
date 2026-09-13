#include "qbrain/memory/fact_store.hpp"
#include "qbrain/mcp/server.hpp"
#include "qbrain/ops/registry.hpp"
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
using namespace qbrain;
using J = nlohmann::json;
int checks = 0;
J scenarios = J::array();
void check(bool ok, const char* label) { if (!ok) throw std::runtime_error(label); ++checks; }
template<class F> void denied(F action, const std::string& code = "") {
  try { action(); }
  catch (const memory::Error& e) {
    check(code.empty() || std::string(e.what()) == code, "expected stable fact error code"); return;
  }
  catch (...) { check(code.empty(),"unexpected storage exception"); return; }
  throw std::runtime_error("operation should have been rejected");
}
template<class F> void scenario(const char* name, F action) {
  const int before = checks; action();
  scenarios.push_back({{"name",name},{"status","PASS"},{"assertions",checks-before}});
}
int64_t scalar(Brain& b, const std::string& sql) { auto s=b.db().prepare(sql); check(s.step(),"scalar has row");return s.column_int(0); }
std::unique_ptr<Brain> fresh() {
  auto b=std::make_unique<Brain>(); b->open_at(":memory:"); b->ensure_source("alpha"); b->ensure_source("beta");
  b->save_config_value("memory.writeback","salient"); return b;
}
struct Seed { std::string item,event,quote; };
Seed seed(Brain& b, const std::string& fragment, const std::string& quote = "我偏好不使用 MT5，而使用命令行。😀",
          const std::string& source="alpha", int64_t expires=0) {
  auto p=J({{"session_id","facts-fixture"},{"fragment_id",fragment},{"expires_at",expires},
            {"messages",J::array({{{"role","user"},{"content",quote}}})}});
  const std::string event=memory::capture(b,source,p,true)["event_id"];
  const auto extracted=memory::extract(b,source,event);
  check(extracted["item_count"]==1,"seed is an actually extracted user quote");
  auto s=b.db().prepare("SELECT item_id FROM memory_items WHERE event_id=?");s.bind_text(1,event);
  check(s.step(),"seed item exists");return {s.column_text(0),event,quote};
}
J create(memory::FactStore store,const Seed& e,const std::string& pred="interface.preference") {
  return store.create({{"predicate",pred},{"item_id",e.item}});
}
J row(memory::FactStore& store,const J& f,bool history=false) {
  const auto r=store.read(f["fact_id"],"",history,10,32768);
  check(r["items"].size()==1,"one supported fact");return r["items"][0];
}
void lifecycle_tests() {
  scenario("lazy schema and legacy compatibility",[] {
    auto b=fresh();b->db().exec("INSERT INTO facts(entity_slug,object_text) VALUES('legacy','KEEP');");
    const auto version=scalar(*b,"SELECT MAX(version) FROM schema_version");
    const auto tables=scalar(*b,"SELECT COUNT(*) FROM sqlite_master");
    memory::FactStore store(*b,"alpha");const auto read=store.read();
    check(read["initialized"]==false && read["items"].empty(),"read does not initialize optional facts");
    check(scalar(*b,"SELECT COUNT(*) FROM sqlite_master")==tables,"read does not add schema");
    const auto e=seed(*b,"one");const auto f=create(store,e);const auto found=row(store,f);
    check(found["object"]==e.quote && found["object"].get<std::string>().find("不使用")!=std::string::npos,
          "complete quote preserves negation and Unicode");
    check(found["confidence"].is_null() && found["untrusted_data"]==true,"no invented truth or confidence");
    check(found["evidence"][0]["item_id"]==e.item && found["evidence"][0]["event_id"]==e.event,
          "evidence references original extracted quote");
    check(create(store,e)["duplicate"]==true && scalar(*b,"SELECT COUNT(*) FROM memory_facts")==1,
          "same request idempotent");
    check(scalar(*b,"SELECT MAX(version) FROM schema_version")==version &&
          scalar(*b,"SELECT COUNT(*) FROM facts WHERE object_text='KEEP'")==1,"legacy data/version unchanged");
    const int changes=sqlite3_total_changes(b->db().handle());
    for(int i=0;i<3;++i) (void)store.read();
    check(sqlite3_total_changes(b->db().handle())==changes,"reads are write-free");
    const auto bounded=store.read("","",false,50,512);
    check(bounded.dump().size()<=512 && bounded["truncated"]==true,"whole quote not chopped to fit budget");
  });
  scenario("source identity and strict input validation",[] {
    auto b=fresh();const auto e=seed(*b,"one");memory::FactStore a(*b,"alpha"),other(*b,"beta");
    denied([&]{create(other,e);},"fact_evidence_unavailable");
    denied([&]{memory::FactStore(*b,"ALPHA");},"invalid_source");
    for(const auto& p:std::vector<std::string>{"","A","-a","bad space","x';DELETE",std::string(65,'a'),std::string("a\0x",3),"中文"})
      denied([&]{create(a,e,p);},"fact_invalid_predicate");
    for(const auto& id:std::vector<std::string>{"",std::string(63,'a'),std::string(64,'A'),"../source",std::string("a\0b",3)})
      denied([&]{a.create({{"predicate","p"},{"item_id",id}});},"fact_invalid_id");
    denied([&]{a.create({{"predicate","p"},{"item_id",e.item},{"object","MT5"}});},"fact_unexpected_argument");
    denied([&]{a.create({{"predicate","p"},{"item_id",e.item},{"subject","assistant"}});},"fact_invalid_subject");
    denied([&]{a.create({{"predicate","p"},{"item_id",e.item},{"confidence",0.9}});},"fact_unexpected_argument");
    const auto f=create(a,e);check(other.read(f["fact_id"])["items"].empty(),"fact ID never changes scope");
    denied([&]{other.retract({{"fact_id",f["fact_id"]},{"expected_revision",1}});},"fact_not_found");
    for(const auto& rev:J::array({true,1.5,"1",0,-1,nullptr,2147483647}))
      denied([&]{a.retract({{"fact_id",f["fact_id"]},{"expected_revision",rev}});},"fact_invalid_revision");
    denied([&]{a.read("","",false,0);},"invalid_read_budget");
    denied([&]{a.read("","",false,10,32769);},"invalid_read_budget");
  });
  scenario("support attachment and final-evidence privacy cascade",[] {
    auto b=fresh();memory::FactStore store(*b,"alpha");const auto first=seed(*b,"one"),second=seed(*b,"two");
    const auto f=create(store,first);
    auto attach=store.attach({{"fact_id",f["fact_id"]},{"item_id",second.item}});
    check(attach["revision"]==2 && row(store,f)["evidence_count"]==2,"additional original support retained");
    check(store.attach({{"fact_id",f["fact_id"]},{"item_id",second.item}})["duplicate"]==true,"duplicate support no revision drift");
    const auto different=seed(*b,"different","我偏好不同设置。");
    denied([&]{store.attach({{"fact_id",f["fact_id"]},{"item_id",different.item}});},"fact_quote_mismatch");
    const auto foreign=seed(*b,"foreign",first.quote,"beta");
    denied([&]{store.attach({{"fact_id",f["fact_id"]},{"item_id",foreign.item}});},"fact_evidence_unavailable");
    memory::forget(*b,"alpha",first.event);
    check(row(store,f)["evidence_count"]==1 && row(store,f)["revision"]==3,"remaining support survives with a new revision");
    memory::forget(*b,"alpha",second.event);
    check(store.read(f["fact_id"],"",true)["items"].empty(),"last evidence loss suppresses even history");
    check(scalar(*b,"SELECT COUNT(*) FROM memory_facts")==0 && scalar(*b,"SELECT COUNT(*) FROM memory_fact_evidence")==0,
          "last support forget physically removes fact copies");
    denied([&]{create(store,first);},"fact_evidence_unavailable");
  });
  scenario("explicit conflict supersession retraction and stale revisions",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");const auto ea=seed(*b,"a"),eb=seed(*b,"b","我偏好另一种设置。");
    auto a=create(s,ea),c=create(s,eb);
    check(s.read()["items"].size()==2,"different values do not automatically override");
    auto edge=s.contradict({{"fact_id",a["fact_id"]},{"other_id",c["fact_id"]}});
    check(edge["resolution"]=="unresolved" && s.read()["items"].size()==2,"explicit conflict retains both claims");
    check(s.contradict({{"fact_id",c["fact_id"]},{"other_id",a["fact_id"]}})["duplicate"]==true,"symmetric edge is idempotent");
    denied([&]{s.supersede({{"fact_id",a["fact_id"]},{"replacement_id",c["fact_id"]},{"expected_revision",1}});},"fact_revision_conflict");
    auto changed=s.supersede({{"fact_id",a["fact_id"]},{"replacement_id",c["fact_id"]},{"expected_revision",2}});
    check(changed["status"]=="superseded" && changed["revision"]==3,"replacement changes one exact version");
    check(s.read()["items"].size()==1 && row(s,a,true)["object"]==ea.quote,"history preserved but not active recall");
    denied([&]{s.supersede({{"fact_id",c["fact_id"]},{"replacement_id",a["fact_id"]},{"expected_revision",2}});},"fact_state_conflict");
    check(create(s,ea)["status"]=="superseded","create retry cannot reset old status");
    memory::forget(*b,"alpha",eb.event);
    check(s.read()["items"].empty() && row(s,a,true)["status"]=="superseded","loss of replacement never revives old claim");
    check(scalar(*b,"SELECT COUNT(*) FROM memory_fact_relations")==0,"forgotten target relations are removed");
    const auto retracted=s.retract({{"fact_id",a["fact_id"]},{"expected_revision",3}});
    check(retracted["status"]=="retracted" && row(s,a,true)["revision"]==4,"retraction available for old versions");
    check(s.retract({{"fact_id",a["fact_id"]},{"expected_revision",4}})["duplicate"]==true,"repeat current retraction no-op");
    check(create(s,ea)["status"]=="retracted","retry does not undo retraction");
    denied([&]{s.attach({{"fact_id",a["fact_id"]},{"item_id",ea.item}});},"fact_state_conflict");
  });
  scenario("incompatible and cross-source relation rejection",[] {
    auto b=fresh();memory::FactStore a(*b,"alpha"),beta(*b,"beta");
    const auto e=seed(*b,"a"),f=seed(*b,"b","我偏好另一个。");
    const auto x=create(a,e),y=create(a,f,"other.predicate"),same=create(a,seed(*b,"same"));
    const auto foreign=create(beta,seed(*b,"foreign",f.quote,"beta"));
    for(const auto& target:J::array({x["fact_id"],y["fact_id"],same["fact_id"]}))
      denied([&]{a.contradict({{"fact_id",x["fact_id"]},{"other_id",target}});},"fact_incompatible_relation");
    denied([&]{a.contradict({{"fact_id",x["fact_id"]},{"other_id",foreign["fact_id"]}});},"fact_not_found");
    check(scalar(*b,"SELECT COUNT(*) FROM memory_fact_relations")==0,"no partial incompatible edge");
  });
}
void integrity_tests() {
  scenario("live evidence validation rejects deletion and tampering",[] {
    const std::vector<std::string> mutations={
      "UPDATE pages SET deleted_at='deleted'",
      "UPDATE pages SET body='untrusted replacement'",
      "UPDATE pages SET content_hash='incorrect'",
      "UPDATE pages SET source_id='beta'",
      "UPDATE memory_events SET status='archived'",
      "UPDATE memory_events SET expires_at=1",
      "UPDATE memory_events SET session_id='changed'",
      "UPDATE memory_events SET payload_hash='changed'",
      "UPDATE memory_items SET quote='I prefer forged content'",
      "UPDATE memory_items SET message_index=999",
      "UPDATE memory_items SET category='fabricated'",
      "UPDATE memory_items SET expires_at=1",
      "UPDATE memory_fact_evidence SET quote_hash='forged'",
      "UPDATE memory_fact_evidence SET payload_hash='forged'",
      "UPDATE memory_facts SET object='forged value'",
      "DELETE FROM pages", "DELETE FROM memory_events", "DELETE FROM memory_items"};
    for(const auto& mutation:mutations) {
      auto b=fresh();memory::FactStore store(*b,"alpha");auto e=seed(*b,"one");auto f=create(store,e);
      b->db().exec(mutation);
      check(store.read(f["fact_id"],"",true)["items"].empty(),"unavailable evidence cannot publish fact text");
    }
  });
  scenario("no assistant or tool claim promotion even with forged extracted row",[] {
    for(const auto* role:{"assistant","tool","system","unknown"}) {
      auto b=fresh();const std::string quote="I prefer invented content.";
      auto p=J({{"session_id","roles"},{"fragment_id",role},
                {"messages",J::array({{{"role",role},{"content",quote}}})}});
      const std::string event=memory::capture(*b,"alpha",p,true)["event_id"];
      b->db().exec("UPDATE memory_events SET status='extracted'");
      const auto item=util::sha256_hex(event+J({{"message_index",0},{"category","preference"},{"quote",quote}}).dump());
      auto st=b->db().prepare("INSERT INTO memory_items VALUES(?,?,'preference',?,0,0,0)");
      st.bind_text(1,item);st.bind_text(2,event);st.bind_text(3,quote);st.step_done();
      denied([&]{memory::FactStore(*b,"alpha").create({{"predicate","p"},{"item_id",item}});},"fact_evidence_unavailable");
      check(scalar(*b,"SELECT COUNT(*) FROM sqlite_master WHERE name='memory_fact_module'")==0,"invalid evidence does not initialize schema");
    }
  });
  scenario("real wall-clock evidence expiration",[] {
    auto b=fresh();const auto at=std::chrono::system_clock::now();
    const auto until=std::chrono::duration_cast<std::chrono::seconds>(at.time_since_epoch()).count()+2;
    const auto e=seed(*b,"expiring","I prefer temporary fixture.","alpha",until);
    memory::FactStore s(*b,"alpha");const auto f=create(s,e);(void)row(s,f);
    std::this_thread::sleep_until(std::chrono::system_clock::time_point(std::chrono::seconds(until+1)));
    check(s.read(f["fact_id"],"",true)["items"].empty(),"expired evidence hidden without edits or cleanup");
  });
  scenario("atomic writes and revision rollback",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");auto a=create(s,seed(*b,"a"));const auto e=seed(*b,"b","I prefer second.");
    const auto before=scalar(*b,"SELECT COUNT(*) FROM memory_facts");
    b->db().exec("CREATE TRIGGER fail_fact_evidence BEFORE INSERT ON memory_fact_evidence BEGIN SELECT RAISE(ABORT,'injected'); END;");
    denied([&]{create(s,e);});check(scalar(*b,"SELECT COUNT(*) FROM memory_facts")==before,"failed evidence insert rolls back fact");
    b->db().exec("DROP TRIGGER fail_fact_evidence;");auto c=create(s,e);
    b->db().exec("CREATE TRIGGER fail_fact_revision BEFORE UPDATE ON memory_facts BEGIN SELECT RAISE(ABORT,'injected'); END;");
    denied([&]{s.supersede({{"fact_id",a["fact_id"]},{"replacement_id",c["fact_id"]},{"expected_revision",1}});});
    check(scalar(*b,"SELECT COUNT(*) FROM memory_fact_relations")==0 && row(s,a)["revision"]==1,"failed transition rolls back edge and state");
    b->db().exec("DROP TRIGGER fail_fact_revision;");
    check(s.supersede({{"fact_id",a["fact_id"]},{"replacement_id",c["fact_id"]},{"expected_revision",1}})["status"]=="superseded","same operation recovers after injected failure");
  });
  scenario("module compatibility and foreign-key requirement",[] {
    auto b=fresh();memory::FactStore store(*b,"alpha");const auto e=seed(*b,"one");(void)create(store,e);
    b->db().exec("PRAGMA foreign_keys=OFF");
    denied([&]{store.read();},"fact_foreign_keys_required");
    denied([&]{create(store,e);},"fact_foreign_keys_required");
    b->db().exec("PRAGMA foreign_keys=ON; DROP TABLE memory_fact_module; CREATE TABLE memory_fact_module(version INTEGER); INSERT INTO memory_fact_module VALUES(2);");
    denied([&]{store.read();},"fact_schema_version_unsupported");
    b->db().exec("UPDATE memory_fact_module SET version=1; DROP TRIGGER memory_fact_last_evidence;");
    denied([&]{store.read();},"fact_schema_incomplete");
    auto c=fresh();c->db().exec("CREATE TABLE memory_facts(unrelated TEXT);");
    denied([&]{memory::FactStore(*c,"alpha").read();},"fact_schema_conflict");
  });
  scenario("migration failure is atomic",[] {
    auto b=fresh();const auto e=seed(*b,"one");
    sqlite3_set_authorizer(b->db().handle(),[](void*,int action,const char* table,const char*,const char*,const char*) {
      return action==SQLITE_CREATE_TABLE && table && std::string(table)=="memory_fact_relations" ? SQLITE_DENY : SQLITE_OK;
    },nullptr);
    denied([&]{memory::FactStore(*b,"alpha").create({{"predicate","p"},{"item_id",e.item}});});
    sqlite3_set_authorizer(b->db().handle(),nullptr,nullptr);
    check(scalar(*b,"SELECT COUNT(*) FROM sqlite_master WHERE name IN ('memory_fact_module','memory_facts','memory_fact_evidence','memory_fact_relations')")==0,"all module DDL rolled back");
    check(memory::read(*b,"alpha")["items"].size()==1,"legacy evidence survives migration failure");
  });
  scenario("evidence and relation caps",[] {
    auto b=fresh();memory::FactStore store(*b,"alpha");const auto original=seed(*b,"seed");const auto f=create(store,original);
    for(int n=1;n<=16;++n) {
      const auto e=seed(*b,"support-"+std::to_string(n));
      if(n<16) (void)store.attach({{"fact_id",f["fact_id"]},{"item_id",e.item}});
      else denied([&]{store.attach({{"fact_id",f["fact_id"]},{"item_id",e.item}});},"fact_evidence_limit");
    }
    check(row(store,f)["evidence_count"]==16,"support bound exactly enforced");
    for(int n=0;n<33;++n) {
      const auto g=create(store,seed(*b,"other-"+std::to_string(n),"I prefer choice "+std::to_string(n)+"."));
      if(n<32) (void)store.contradict({{"fact_id",f["fact_id"]},{"other_id",g["fact_id"]}});
      else denied([&]{store.contradict({{"fact_id",f["fact_id"]},{"other_id",g["fact_id"]}});},"fact_relation_limit");
    }
    check(scalar(*b,"SELECT COUNT(*) FROM memory_fact_relations")==32,"edge cap exactly enforced");
  });
}
void bounded_read_test() {
  scenario("fact output candidates and transcript work bounds",[] {
    auto b=fresh();memory::FactStore store(*b,"alpha");
    const auto e=seed(*b,"small");
    for(int n=0;n<102;++n) (void)create(store,e,"p"+std::to_string(n));
    auto r=store.read("","",false,50,32768);
    check(r["truncated"]==true && r["items"].size()<=50 && r.dump().size()<=32768,"bounded result and candidate count");
    auto large=fresh();memory::FactStore big(*large,"alpha");
    for(int n=0;n<36;++n) {
      const std::string quote="I prefer fixture "+std::to_string(n)+".";
      J messages=J::array({{{"role","user"},{"content",quote}}});
      for(int i=0;i<4;++i)messages.push_back({{"role","assistant"},{"content",std::string(62000,'x')}});
      const auto event=memory::capture(*large,"alpha",{{"session_id","large"},{"fragment_id",std::to_string(n)},{"messages",messages}},true)["event_id"].get<std::string>();
      memory::extract(*large,"alpha",event);
      auto st=large->db().prepare("SELECT item_id FROM memory_items WHERE event_id=?");st.bind_text(1,event);check(st.step(),"large transcript has real quote");
      (void)big.create({{"predicate","p"},{"item_id",st.column_text(0)}});
    }
    r=big.read("","",false,50,32768);
    check(r["truncated"]==true && r.value("work_limited",false) && r.dump().size()<=32768,
          "whole-call evidence work stops at explicit byte budget");
  });
}
void concurrent_test() {
  scenario("two-connection create and stale revision races",[] {
    const auto path=std::filesystem::temp_directory_path()/std::filesystem::path("qbrain-n47a-"+
        util::sha256_hex(std::to_string(std::chrono::steady_clock::now().time_since_epoch().count())).substr(0,16));
    std::filesystem::create_directory(path);
    { Brain seedbrain;seedbrain.open_at(util::path_to_utf8(path/"brain.db"));seedbrain.ensure_source("alpha");
      seedbrain.save_config_value("memory.writeback","salient");const auto e=seed(seedbrain,"race");
      Brain one,two;one.open_at(util::path_to_utf8(path/"brain.db"));two.open_at(util::path_to_utf8(path/"brain.db"));
      one.db().exec("PRAGMA busy_timeout=123");two.db().exec("PRAGMA busy_timeout=456");
      J a,c;std::exception_ptr ae,ce;std::barrier start(3);
      std::thread t1([&]{start.arrive_and_wait();try{a=create(memory::FactStore(one,"alpha"),e);}catch(...){ae=std::current_exception();}});
      std::thread t2([&]{start.arrive_and_wait();try{c=create(memory::FactStore(two,"alpha"),e);}catch(...){ce=std::current_exception();}});
      start.arrive_and_wait();t1.join();t2.join();if(ae)std::rethrow_exception(ae);if(ce)std::rethrow_exception(ce);
      check(a["fact_id"]==c["fact_id"] && a["duplicate"]!=c["duplicate"],"one created fact and one idempotent duplicate");
      check(scalar(one,"SELECT COUNT(*) FROM memory_facts")==1,"concurrent first initialization has one fact");
      check(scalar(one,"PRAGMA busy_timeout")==123 && scalar(two,"PRAGMA busy_timeout")==456,"original busy timeouts restored");
      std::barrier second(3);int success=0;std::string e1,e2;
      auto attempt=[&](Brain& b,std::string& err) {second.arrive_and_wait();try{memory::FactStore(b,"alpha").retract({{"fact_id",a["fact_id"]},{"expected_revision",1}});}
        catch(const std::exception& ex){err=ex.what();}};
      std::thread t3(attempt,std::ref(one),std::ref(e1)),t4(attempt,std::ref(two),std::ref(e2));second.arrive_and_wait();t3.join();t4.join();
      success=int(e1.empty())+int(e2.empty());check(success==1 && (e1=="fact_revision_conflict" || e2=="fact_revision_conflict"),"one stale revision loser");
      check(memory::FactStore(seedbrain,"alpha").read("","",true)["items"][0]["revision"]==2,"no lost updates or duplicate transition");
      const auto next=seed(seedbrain,"blocked-writer","I prefer bounded locks.");
      two.db().exec("BEGIN IMMEDIATE");
      const auto before=std::chrono::steady_clock::now();
      denied([&]{create(memory::FactStore(one,"alpha"),next);});
      const auto elapsed=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-before).count();
      check(elapsed<8000,"writer contention has one bounded wait, not a retry loop");
      check(scalar(one,"PRAGMA busy_timeout")==123,"timeout restored after failed transaction acquisition");
      two.db().exec("ROLLBACK");
      check(create(memory::FactStore(one,"alpha"),next)["duplicate"]==false,"retry is explicit and commits only once");
      bool backup=false;for(const auto& file:std::filesystem::directory_iterator(path))
        if(file.path().filename().string().find(".pre-facts-v1-")!=std::string::npos) backup=true;
      check(backup,"on-disk first fact write has an actual backup");
    }
    std::filesystem::remove_all(path);
  });
}
} // namespace
void test_n47a() {
  checks=0;scenarios=J::array();lifecycle_tests();integrity_tests();bounded_read_test();concurrent_test();
  std::cout<<"N47A evidence facts: "<<scenarios.size()<<" scenarios, "<<checks<<" checks passed\n";
}
#ifdef QBRAIN_FACT_STANDALONE
int main(int argc,char** argv) {
  try {test_n47a();if(argc==3 && std::string(argv[1])=="--report") {
    std::ofstream f(argv[2],std::ios::binary);if(!f)throw std::runtime_error("report open failed");
    f<<J({{"result","PASS"},{"scenarios",scenarios},{"scenario_count",scenarios.size()},{"checks",checks}}).dump(2)<<'\n';
    if(!f)throw std::runtime_error("report write failed");
  } else if(argc!=1)throw std::runtime_error("invalid arguments");return 0;}
  catch(const std::exception& e){std::cerr<<"[FAIL] N47A: "<<e.what()<<'\n';return 1;}
}
#endif
