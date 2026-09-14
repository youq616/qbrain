#include "qbrain/memory/fact_store.hpp"
#include "qbrain/util/hash.hpp"
#include "qbrain/util/paths.hpp"
#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {
using namespace qbrain;
using J = nlohmann::json;
int checks=0;
J scenarios=J::array();
void check(bool condition,const char* label) {
  if(!condition) throw std::runtime_error(label);
  ++checks;
}
template<class F> void rejects(F f,const std::string& expected) {
  try { f(); } catch(const memory::Error& e) {
    check(e.what()==expected,"stable rejection code"); return;
  }
  throw std::runtime_error("expected rejection missing");
}
template<class F> void scenario(const char* name,F f) {
  const int before=checks;f();scenarios.push_back({{"name",name},{"status","PASS"},{"assertions",checks-before}});
}
std::unique_ptr<Brain> fresh() {
  auto b=std::make_unique<Brain>();b->open_at(":memory:");b->ensure_source("alpha");b->ensure_source("beta");
  b->save_config_value("memory.writeback","salient");return b;
}
struct Seed {std::string event,item,quote;};
Seed seed(Brain& b,const std::string& fragment,const std::string& quote,const std::string& source="alpha") {
  const auto event=memory::capture(b,source,{{"session_id","conflicts"},{"fragment_id",fragment},
      {"messages",J::array({{{"role","user"},{"content",quote}}})}},true)["event_id"].get<std::string>();
  check(memory::extract(b,source,event)["item_count"]==1,"real local extraction");
  auto s=b.db().prepare("SELECT item_id FROM memory_items WHERE event_id=?");s.bind_text(1,event);
  check(s.step(),"real evidence item");return {event,s.column_text(0),quote};
}
J claim(memory::FactStore& s,const Seed& e,const std::string& pred="editor.preference") {
  return s.create({{"predicate",pred},{"item_id",e.item}});
}
J link(memory::FactStore& s,const J& a,const J& b) {
  return s.contradict({{"fact_id",a["fact_id"]},{"other_id",b["fact_id"]}});
}
int64_t scalar(Brain& b,const std::string& text) {
  auto s=b.db().prepare(text);check(s.step(),"scalar result");return s.column_int(0);
}
std::pair<J,J> pair(Brain& b,memory::FactStore& s,const std::string& key="p") {
  auto a=claim(s,seed(b,key+"a","我偏好不使用 MT5，而使用命令行。😀"),key);
  auto c=claim(s,seed(b,key+"b","我偏好图形编辑界面，不使用命令行。"),key);
  link(s,a,c);return {a,c};
}
void basic() {
  scenario("lazy conflict view and no automatic contradiction",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");
    auto schema=scalar(*b,"SELECT COUNT(*) FROM sqlite_master");
    auto r=s.conflicts();check(!r["initialized"].get<bool>() && r["items"].empty(),"no lazy initialization");
    check(scalar(*b,"SELECT COUNT(*) FROM sqlite_master")==schema,"read leaves old schema intact");
    const auto a=claim(s,seed(*b,"a","I prefer CLI.")),c=claim(s,seed(*b,"b","I prefer GUI."));
    check(s.conflicts()["items"].empty(),"different claims alone are not contradictions");
    link(s,a,c);check(s.conflicts()["items"].size()==1,"explicit edge is visible");
  });
  scenario("canonical complete pairs and provenance",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");auto [a,c]=pair(*b,s);
    check(link(s,c,a)["duplicate"].get<bool>(),"opposite direction is the same assertion");
    const auto r=s.conflicts();const auto p=r["items"][0];
    check(r["untrusted_data"]==true && r["semantics"]=="explicit_contradictions_only","untrusted explicit semantics");
    check(p["relation"]=="contradicts" && p["resolution"]=="unresolved","no winner selected");
    check(p["facts"].size()==2 && p["from_id"]<p["to_id"],"one canonical pair");
    check(p["facts"][0]["fact_id"]==p["from_id"] && p["facts"][1]["fact_id"]==p["to_id"],"stable endpoint association");
    for(const auto& f:p["facts"]) {
      check(f["status"]=="active" && f["revision"]==2 && f["confidence"].is_null(),"active revision not verified confidence");
      check(f["source_id"]=="alpha" && f["evidence"].size()==1 && f["evidence"][0]["event_id"].get<std::string>().size()==64,"whole original provenance");
      check(f["object"].get<std::string>().find("不使用")!=std::string::npos,"negation retained");
    }
    check(s.conflicts()==r,"unchanged data yields stable JSON");
  });
  scenario("source predicate and either-endpoint filters",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha"),other(*b,"beta");auto [a,c]=pair(*b,s,"editor");
    pair(*b,s,"shell");
    check(s.conflicts()["items"].size()==2,"two explicit pairs");
    check(s.conflicts(a["fact_id"])["items"].size()==1 && s.conflicts(c["fact_id"])["items"].size()==1,"either endpoint works");
    check(s.conflicts("","editor")["items"].size()==1 && s.conflicts(a["fact_id"],"shell")["items"].empty(),"filters intersect");
    check(other.conflicts()["items"].empty() && other.conflicts(a["fact_id"])["items"].empty(),"source scope is mandatory");
    const auto ba=claim(other,seed(*b,"ba","I prefer CLI.","beta"),"editor");
    const auto bc=claim(other,seed(*b,"bc","I prefer GUI.","beta"),"editor");link(other,ba,bc);
    check(other.conflicts()["items"].size()==1 && s.conflicts()["items"].size()==2,"each populated source returns only its pairs");
    check(s.conflicts(std::string(64,'f'))["items"].empty(),"unknown well-formed ID stays empty");
    rejects([&]{s.conflicts("' OR 1=1");},"fact_invalid_id");
    rejects([&]{s.conflicts("","x';DELETE");},"fact_invalid_predicate");
    rejects([&]{s.conflicts("",std::string("p\0x",3));},"fact_invalid_predicate");
    rejects([&]{s.conflicts("","",0);},"invalid_read_budget");
    rejects([&]{s.conflicts("","",51);},"invalid_read_budget");
    rejects([&]{s.conflicts("","",1,511);},"invalid_read_budget");
    rejects([&]{s.conflicts("","",1,32769);},"invalid_read_budget");
  });
  scenario("read-only SQL and no scheduled work",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");pair(*b,s);
    const auto changes=sqlite3_total_changes(b->db().handle());
    const auto schema=scalar(*b,"SELECT COUNT(*) FROM sqlite_master");
    sqlite3_set_authorizer(b->db().handle(),[](void*,int action,const char*,const char*,const char*,const char*) {
      switch(action) {case SQLITE_INSERT:case SQLITE_UPDATE:case SQLITE_DELETE:
        case SQLITE_CREATE_TABLE:case SQLITE_CREATE_INDEX:case SQLITE_TRANSACTION:return SQLITE_DENY;}
      return SQLITE_OK;
    },nullptr);
    const auto r=s.conflicts();
    sqlite3_set_authorizer(b->db().handle(),nullptr,nullptr);
    check(r["items"].size()==1,"pure read under write-denying authorizer");
    check(sqlite3_total_changes(b->db().handle())==changes && scalar(*b,"SELECT COUNT(*) FROM sqlite_master")==schema,"no data or schema write");
    check(scalar(*b,"SELECT COUNT(*) FROM jobs")==0,"no implicit provider jobs");
  });
}
void lifetime() {
  scenario("retraction and supersession hide current conflicts",[] {
    for(bool retract:{false,true}) {
      auto b=fresh();memory::FactStore s(*b,"alpha");auto [a,c]=pair(*b,s);
      if(retract) s.retract({{"fact_id",a["fact_id"]},{"expected_revision",2}});
      else s.supersede({{"fact_id",a["fact_id"]},{"replacement_id",c["fact_id"]},{"expected_revision",2}});
      check(s.conflicts()["items"].empty(),"inactive endpoint hides pair");
      check(s.read(a["fact_id"],"",true)["items"].size()==1,"fact history remains explicit");
      check(scalar(*b,"SELECT COUNT(*) FROM memory_fact_relations WHERE relation='contradicts'")==1,"inspection did not delete historical assertion");
    }
  });
  scenario("support forgetting and next-call invalidation",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");auto e=seed(*b,"first","I prefer command line.");
    auto support=seed(*b,"support",e.quote),other=seed(*b,"other","I prefer windows.");
    auto a=claim(s,e),c=claim(s,other);link(s,a,c);s.attach({{"fact_id",a["fact_id"]},{"item_id",support.item}});
    memory::forget(*b,"alpha",e.event);
    auto r=s.conflicts();check(r["items"].size()==1,"other complete support survives");
    for(const auto& f:r["items"][0]["facts"]) if(f["fact_id"]==a["fact_id"])
      check(f["evidence_count"]==1 && f["revision"]==4,"current support and revision only");
    memory::forget(*b,"alpha",support.event);
    check(s.conflicts()["items"].empty(),"final support forget invalidates next call");
    check(scalar(*b,"SELECT COUNT(*) FROM memory_fact_relations")==0,"privacy cascade removed copied edge");
  });
  scenario("invalid or unavailable evidence never yields half a pair",[] {
    const std::vector<std::string> changes={
      "UPDATE pages SET deleted_at='deleted'", "DELETE FROM pages", "DELETE FROM memory_events", "DELETE FROM memory_items",
      "UPDATE memory_items SET expires_at=1", "UPDATE memory_events SET status='archived'",
      "UPDATE memory_items SET quote='forged'", "UPDATE memory_events SET payload_hash='forged'",
      "UPDATE memory_fact_evidence SET quote_hash='forged'", "UPDATE pages SET source_id='beta'",
      "UPDATE memory_facts SET object='not original'", "UPDATE memory_facts SET predicate=fact_id",
      "UPDATE memory_fact_relations SET source_id='beta'"};
    for(const auto& sql:changes) {
      auto b=fresh();memory::FactStore s(*b,"alpha");pair(*b,s);
      // Composite source constraints intentionally bypassed only for the corrupt-row fixture.
      if(sql.find("SET source_id")!=std::string::npos)b->db().exec("PRAGMA foreign_keys=OFF");
      b->db().exec(sql);b->db().exec("PRAGMA foreign_keys=ON");
      check(s.conflicts()["items"].empty(),"bad evidence or incompatible metadata suppressed");
    }
  });
  scenario("wall-clock expiration hides the complete conflict",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");
    const auto until=std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()).count()+2;
    const std::string quote="I prefer a temporary setting.";
    const auto event=memory::capture(*b,"alpha",{{"session_id","expires"},{"fragment_id","one"},
        {"expires_at",until},{"messages",J::array({{{"role","user"},{"content",quote}}})}},true)["event_id"].get<std::string>();
    check(memory::extract(*b,"alpha",event)["item_count"]==1,"expiring quote is extracted");
    Seed e{event,"",quote};
    { auto q=b->db().prepare("SELECT item_id FROM memory_items WHERE event_id=?");q.bind_text(1,event);
      check(q.step(),"expiring item exists");e.item=q.column_text(0); }
    const auto a=claim(s,e),c=claim(s,seed(*b,"permanent","I prefer a lasting setting."));link(s,a,c);
    check(s.conflicts()["items"].size()==1,"pair visible before expiry");
    std::this_thread::sleep_until(std::chrono::system_clock::time_point(std::chrono::seconds(until+1)));
    check(s.conflicts()["items"].empty(),"expired side hides both without modifying stored rows");
    check(scalar(*b,"SELECT COUNT(*) FROM memory_fact_relations")==1,"expiration inspection is non-destructive");
  });
  scenario("two-sided byte and pair limits",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");pair(*b,s,"a");pair(*b,s,"b");pair(*b,s,"c");
    const auto all=s.conflicts("","",50,32768);
    check(all["items"].size()==3 && !all["truncated"].get<bool>(),"complete three-pair view");
    auto r=s.conflicts("","",1,32768);
    check(r["items"].size()==1 && r["truncated"]==true && r["items"][0]==all["items"][0],"stable prefix under pair limit");
    r=s.conflicts("","",50,512);
    check(r["items"].empty() && r["truncated"]==true && r.dump().size()<=512,"cannot fit a pair: no one-sided disclosure");
    r=s.conflicts("","",50,int(all.dump().size()));
    check(r==all,"exact total byte cap fits");
    r=s.conflicts("","",50,int(all.dump().size())-1);
    check(r["items"].size()==2 && r["truncated"]==true,"one byte short omits entire last pair");
    for(const auto& p:r["items"])check(p["facts"].size()==2,"all bounded outputs have both endpoints");
  });
  scenario("candidate limit remains explicit for filtered-out evidence",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");auto x=seed(*b,"x","I prefer first."),y=seed(*b,"y","I prefer second.");
    for(int i=0;i<101;++i) {auto a=claim(s,x,"p"+std::to_string(i)),c=claim(s,y,"p"+std::to_string(i));link(s,a,c);}
    b->db().exec("UPDATE memory_fact_evidence SET quote_hash='invalid'");
    const auto r=s.conflicts("","",50,32768);
    check(r["items"].empty() && r["truncated"]==true && r["work_limited"]==false,"candidate truncation is not a false no-conflict answer");
    check(r["candidate_limit"]==100,"explicit candidate policy");
  });
  scenario("evidence work cap suppresses incomplete pair",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");
    for(int i=0;i<36;++i)pair(*b,s,"p"+std::to_string(i));
    auto q=b->db().prepare("UPDATE pages SET body=?");q.bind_text(1,std::string(250000,'x'));q.step_done();
    const auto r=s.conflicts("","",50,32768);
    check(r["items"].empty() && r["truncated"]==true && r["work_limited"]==true,"8MiB evidence work cap stops corrupt corpus");
    check(r.dump().size()<=32768,"bounded error metadata");
  });
}
void snapshot() {
  scenario("two endpoints share snapshot across concurrent forget",[] {
    const auto dir=std::filesystem::temp_directory_path()/std::filesystem::path("qbrain-conflict-"+
      util::sha256_hex(std::to_string(std::chrono::steady_clock::now().time_since_epoch().count())).substr(0,16));
    std::filesystem::create_directory(dir);
    {
      Brain reader;reader.open_at(util::path_to_utf8(dir/"brain.db"));reader.ensure_source("alpha");
      reader.save_config_value("memory.writeback","salient");
      memory::FactStore store(reader,"alpha");auto a=seed(reader,"a","I prefer CLI."),b=seed(reader,"b","I prefer GUI.");
      link(store,claim(store,a),claim(store,b));
      Brain writer;writer.open_at(util::path_to_utf8(dir/"brain.db"));
      struct State {Brain* writer;sqlite3* reader;std::string event;bool fired=false,committed=false,read_snapshot=false;} state{&writer,reader.db().handle(),a.event};
      sqlite3_trace_v2(reader.db().handle(),SQLITE_TRACE_STMT,[](unsigned,void* ctx,void* raw,void*)->int {
        auto& c=*static_cast<State*>(ctx);const char* sql=sqlite3_sql(static_cast<sqlite3_stmt*>(raw));
        if(!c.fired && sql && std::string(sql).starts_with("SELECT subject,predicate,object,status")) {
          c.fired=true;c.read_snapshot=sqlite3_txn_state(c.reader,"main")==SQLITE_TXN_READ;
          try {memory::forget(*c.writer,"alpha",c.event);c.committed=true;}catch(...){}
        }
        return 0;
      },&state);
      const auto first=store.conflicts();sqlite3_trace_v2(reader.db().handle(),0,nullptr,nullptr);
      check(state.fired && state.read_snapshot && state.committed,"writer really committed during the active outer read");
      check(first["items"].size()==1 && first["items"][0]["facts"].size()==2,"both endpoints remain on the complete prior snapshot");
      check(store.conflicts()["items"].empty(),"new call sees completed forget, no cross-call cache");
      check(sqlite3_txn_state(reader.db().handle(),"main")==SQLITE_TXN_NONE,"read statement closes its snapshot");
    }
    std::filesystem::remove_all(dir);
  });
  scenario("schema errors and foreign key policy fail closed",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");pair(*b,s);
    b->db().exec("PRAGMA foreign_keys=OFF");rejects([&]{s.conflicts();},"fact_foreign_keys_required");
    b->db().exec("PRAGMA foreign_keys=ON; DROP TRIGGER memory_fact_last_evidence");
    rejects([&]{s.conflicts();},"fact_schema_incomplete");
  });
}
}
void test_n47b() {
  checks=0;scenarios=J::array();basic();lifetime();snapshot();
  std::cout<<"N47B conflict inspection: "<<scenarios.size()<<" scenarios, "<<checks<<" checks passed\n";
}
#ifdef QBRAIN_CONFLICT_STANDALONE
int main(int argc,char** argv) {
  try {
    test_n47b();
    if(argc==3 && std::string(argv[1])=="--report") {
      std::ofstream f(argv[2],std::ios::binary);if(!f)throw std::runtime_error("report open failed");
      f<<J({{"result","PASS"},{"scenario_count",scenarios.size()},{"checks",checks},{"scenarios",scenarios}}).dump(2)<<'\n';
      if(!f)throw std::runtime_error("report write failed");
    } else if(argc!=1) throw std::runtime_error("invalid arguments");
    return 0;
  } catch(const std::exception& e) {std::cerr<<"[FAIL] N47B: "<<e.what()<<'\n';return 1;}
}
#endif
