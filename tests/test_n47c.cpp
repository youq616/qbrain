#include "qbrain/memory/fact_store.hpp"
#include "qbrain/util/hash.hpp"
#include "qbrain/util/paths.hpp"
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <set>
#include <thread>

namespace {
using namespace qbrain;
using J=nlohmann::json;
int checks=0;J scenarios=J::array();
void check(bool ok,const char* why) {if(!ok)throw std::runtime_error(why);++checks;}
template<class F> void scenario(const char* name,F f) {
  const int before=checks;f();scenarios.push_back({{"name",name},{"status","PASS"},{"assertions",checks-before}});
}
template<class F> void reject(F f,const char* code) {
  try {f();}catch(const memory::Error& e){check(std::string(e.what())==code,"stable error");return;}
  throw std::runtime_error("expected rejection");
}
std::unique_ptr<Brain> fresh() {
  auto b=std::make_unique<Brain>();b->open_at(":memory:");b->ensure_source("alpha");b->ensure_source("beta");
  b->save_config_value("memory.writeback","salient");return b;
}
struct Seed {std::string event,item,quote;};
Seed seed(Brain& b,const std::string& tag,const std::string& quote,
          const std::string& source="alpha",int64_t expires=0,bool large=false) {
  J messages=J::array({{{"role","user"},{"content",quote}}});
  if(large)for(int i=0;i<4;++i)messages.push_back({{"role","assistant"},{"content",std::string(64990,'x')}});
  auto captured=memory::capture(b,source,{{"session_id","recall-test"},{"fragment_id",tag},
      {"expires_at",expires},{"messages",messages}},true);
  const auto event=captured["event_id"].get<std::string>();
  check(memory::extract(b,source,event)["item_count"]==1,"real extracted user quote");
  auto s=b.db().prepare("SELECT item_id FROM memory_items WHERE event_id=?");s.bind_text(1,event);
  check(s.step(),"real evidence item exists");return {event,s.column_text(0),quote};
}
J claim(memory::FactStore& s,const Seed& e,const std::string& pred="preference.editor") {
  return s.create({{"predicate",pred},{"item_id",e.item}});
}
void link(memory::FactStore& s,const J& a,const J& b) {s.contradict({{"fact_id",a["fact_id"]},{"other_id",b["fact_id"]}});}
int64_t scalar(Brain& b,const std::string& sql) {auto s=b.db().prepare(sql);check(s.step(),"scalar");return s.column_int(0);}
void basic() {
  scenario("lazy recall validates query without initializing schema",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");const auto before=scalar(*b,"SELECT COUNT(*) FROM sqlite_master");
    const auto r=s.recall("界");check(r["items"].empty() && r["initialized"]==false,"no schema initialization");
    check(scalar(*b,"SELECT COUNT(*) FROM sqlite_master")==before,"schema count unchanged");
    for(const auto& q:std::vector<std::string>{""," \t\r\n",std::string(1025,'a'),std::string("a\0b",3),
          std::string("\xff"),std::string("\xe4\xb8"),std::string("\xc0\xaf"),std::string("界\xff")})
      reject([&]{s.recall(q);},"fact_invalid_query");
    check(s.recall(std::string(1024,'a'))["items"].empty(),"exact query byte boundary accepted");
    reject([&]{s.recall("x","",0);},"invalid_read_budget");
    reject([&]{s.recall("x","",51);},"invalid_read_budget");
    reject([&]{s.recall("x","",1,511);},"invalid_read_budget");
    reject([&]{s.recall("x","",1,32769);},"invalid_read_budget");
    reject([&]{s.recall("x","bad predicate");},"fact_invalid_predicate");
  });
  scenario("literal whole quotes preserve negation and Unicode",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");const auto e=seed(*b,"one","我偏好不使用 MT5，而使用命令行。😀 日本語 한국어 𠀀");
    auto a=claim(s,e);
    for(const auto& query:std::vector<std::string>{"命","命令行","mt5","不使用 MT5","😀","日本語","한국어","𠀀"}) {
      auto r=s.recall(query);check(r["items"].size()==1,"literal matches quote");
      const auto& f=r["items"][0]["facts"][0];
      check(f["object"]==e.quote && f["fact_id"]==a["fact_id"],"never turn negation into positive claim");
      check(f["confidence"].is_null() && f["untrusted_data"]==true,"no inferred truth score");
      check(f["evidence"][0]["event_id"]==e.event && f["evidence"][0]["item_id"]==e.item,"original evidence retained");
    }
    check(s.recall("命令 行")["items"].empty(),"no implicit token splitting");
    check(s.recall("圖形")["items"].empty(),"no unrequested conversion or synonyms");
  });
  scenario("query matches before candidate cap and filters remain scoped",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha"),other(*b,"beta");
    auto old=claim(s,seed(*b,"old","I prefer rareNeedle."));
    b->db().exec("UPDATE memory_facts SET created_at=1");
    auto noise=seed(*b,"noise","I prefer irrelevant notes.");
    for(int n=0;n<105;++n)claim(s,noise,"noise"+std::to_string(n));
    check(s.recall("rareNeedle")["items"][0]["match_fact_id"]==old["fact_id"],"old relevant fact survives irrelevant recent corpus");
    check(s.recall("rareNeedle","other.predicate")["items"].empty(),"exact predicate intersects query");
    check(other.recall("rareNeedle")["items"].empty(),"foreign source cannot see candidate");
    auto beta=claim(other,seed(*b,"beta","I prefer rareNeedle.","beta"));
    check(other.recall("rareNeedle")["items"][0]["match_fact_id"]==beta["fact_id"],"same quote in other source independent");
    check(s.recall("irrelevant","noise23")["items"].size()==1,"predicate filter applied before cap");
  });
  scenario("wildcards and SQL syntax are literal not executable",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");
    claim(s,seed(*b,"wild","I prefer 100% a_b path\\name and ' OR 1=1 -- text."));
    claim(s,seed(*b,"plain","I prefer unrelated stuff."));
    for(const auto& q:std::vector<std::string>{"%","_","\\","' OR 1=1 --"})
      check(s.recall(q)["items"].size()==1,"bound literal query cannot match all or inject SQL");
    check(scalar(*b,"SELECT COUNT(*) FROM memory_facts")==2,"input did not mutate facts");
  });
  scenario("query does not hide nonmatching direct counterclaims",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");
    const auto e=seed(*b,"a","I prefer command line."),f=seed(*b,"b","I prefer graphical menus.");
    auto a=claim(s,e),c=claim(s,f);
    auto r=s.recall("command");check(r["items"][0]["facts"].size()==1,"different quote is not inferred contradiction");
    link(s,a,c);r=s.recall("command");
    check(r["items"].size()==1 && r["items"][0]["facts"].size()==2,"nonmatching counterpart retained");
    const auto& i=r["items"][0];check(i["match_fact_id"]==a["fact_id"] && i["facts"][0]["fact_id"]==a["fact_id"],"anchor association explicit");
    check(i["facts"][1]["object"]==f.quote && i["facts"][1]["revision"]==2,"counterclaim complete and current");
    check(i["conflict_state"]=="recorded_conflict" && i["contradictions"].size()==1,"no selected winner");
    check(r["neighbors_recursively_expanded"]==false && r["conflict_scope"]=="direct_active_assertions","scope explicitly nontransitive");
    check(r==s.recall("command"),"stable response on unchanged data");
  });
  scenario("matching counterpart remains an anchor with its own edges",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");
    auto a=claim(s,seed(*b,"a","I prefer needle alpha.")),c=claim(s,seed(*b,"b","I prefer needle beta.")),
         d=claim(s,seed(*b,"c","I prefer unrelated gamma."));link(s,a,c);link(s,c,d);
    const auto r=s.recall("needle");check(r["items"].size()==2,"two matching anchors not deduplicated away");
    for(const auto& item:r["items"]) {
      if(item["match_fact_id"]==a["fact_id"])check(item["facts"].size()==2,"A does not recursively traverse B-C");
      else check(item["facts"].size()==3 && item["contradictions"].size()==2,"B retains B-C even after appearing in A group");
    }
  });
  scenario("recall is read-only and respects schema integrity",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");claim(s,seed(*b,"a","I prefer safe reads."));
    const int before=sqlite3_total_changes(b->db().handle());
    sqlite3_set_authorizer(b->db().handle(),[](void*,int action,const char*,const char*,const char*,const char*) {
      switch(action){case SQLITE_INSERT:case SQLITE_UPDATE:case SQLITE_DELETE:case SQLITE_TRANSACTION:
        case SQLITE_CREATE_TABLE:case SQLITE_CREATE_INDEX:return SQLITE_DENY;}return SQLITE_OK;
    },nullptr);
    auto r=s.recall("safe");sqlite3_set_authorizer(b->db().handle(),nullptr,nullptr);
    check(r["items"].size()==1 && sqlite3_total_changes(b->db().handle())==before,"no data revisions or schema written");
    check(scalar(*b,"SELECT COUNT(*) FROM jobs")==0,"no provider jobs");
    b->db().exec("PRAGMA foreign_keys=OFF");reject([&]{s.recall("safe");},"fact_foreign_keys_required");
    b->db().exec("PRAGMA foreign_keys=ON; DROP TRIGGER memory_fact_last_evidence");
    reject([&]{s.recall("safe");},"fact_schema_incomplete");
  });
}
void lifecycle() {
  scenario("invalid anchor or counter-evidence is not recalled",[] {
    for(const auto& table:std::vector<std::string>{"memory_items","memory_events","pages","memory_fact_evidence"}) {
      for(bool anchor:{true,false}) {
        auto b=fresh();memory::FactStore s(*b,"alpha");
        auto e=seed(*b,"a","I prefer anchorNeedle."),f=seed(*b,"b","I prefer counterpart.");
        auto a=claim(s,e),c=claim(s,f);link(s,a,c);
        const auto event=anchor?e.event:f.event,item=anchor?e.item:f.item;
        std::string sql;
        if(table=="memory_items")sql="UPDATE memory_items SET quote='forged' WHERE item_id='"+item+"'";
        if(table=="memory_events")sql="UPDATE memory_events SET payload_hash='forged' WHERE event_id='"+event+"'";
        if(table=="pages")sql="UPDATE pages SET deleted_at='deleted' WHERE id=(SELECT page_id FROM memory_events WHERE event_id='"+event+"')";
        if(table=="memory_fact_evidence")sql="UPDATE memory_fact_evidence SET quote_hash='forged' WHERE item_id='"+item+"'";
        b->db().exec(sql);auto r=s.recall("anchorNeedle");
        if(anchor)check(r["items"].empty(),"invalid anchor hidden");
        else check(r["items"].size()==1 && r["items"][0]["facts"].size()==1 && r["items"][0]["contradictions"].empty(),"invalid counterpart is not copied as evidence");
      }
    }
  });
  scenario("oversized counterclaim rejected before loading its body",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");auto a=claim(s,seed(*b,"a","I prefer lengthNeedle.")),
      c=claim(s,seed(*b,"b","I prefer counter text."));link(s,a,c);
    auto update=b->db().prepare("UPDATE memory_facts SET object=? WHERE fact_id=?");
    update.bind_text(1,std::string(65536,'x'));update.bind_text(2,c["fact_id"].get<std::string>());update.step_done();
    int loads=0;
    sqlite3_trace_v2(b->db().handle(),SQLITE_TRACE_STMT,[](unsigned,void* ctx,void* raw,void*)->int {
      const char* text=sqlite3_sql(static_cast<sqlite3_stmt*>(raw));
      if(text && std::string(text).starts_with("SELECT subject,predicate,object,status"))++*static_cast<int*>(ctx);
      return 0;
    },&loads);
    const auto r=s.recall("lengthNeedle");sqlite3_trace_v2(b->db().handle(),0,nullptr,nullptr);
    check(loads==1,"oversized target is not passed to full materialization");
    check(r["items"].size()==1 && r["items"][0]["facts"].size()==1,"only genuinely supported bounded facts returned");
  });
  scenario("forget support retraction and supersession update next recall",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");auto e=seed(*b,"a","I prefer anchorNeedle."),
        support=seed(*b,"support",e.quote),f=seed(*b,"b","I prefer counterpart.");
    auto a=claim(s,e),c=claim(s,f);link(s,a,c);s.attach({{"fact_id",a["fact_id"]},{"item_id",support.item}});
    memory::forget(*b,"alpha",e.event);auto r=s.recall("anchorNeedle");
    check(r["items"][0]["facts"][0]["evidence_count"]==1 && r["items"][0]["facts"][0]["revision"]==4,"one surviving original support");
    s.supersede({{"fact_id",a["fact_id"]},{"replacement_id",c["fact_id"]},{"expected_revision",4}});
    check(s.recall("anchorNeedle")["items"].empty(),"superseded anchor not recalled");
    memory::forget(*b,"alpha",f.event);check(s.recall("anchorNeedle")["items"].empty(),"replacement loss does not revive anchor");
    auto other=claim(s,seed(*b,"d","I prefer retractNeedle."));
    s.retract({{"fact_id",other["fact_id"]},{"expected_revision",1}});
    check(s.recall("retractNeedle")["items"].empty(),"retracted anchor hidden");
    memory::forget(*b,"alpha",support.event);check(s.recall("anchorNeedle")["items"].empty(),"last support cascade removes anchor");
  });
  scenario("wall clock expiry invalidates counterclaim without cleanup",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");
    const auto at=std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count()+2;
    auto a=claim(s,seed(*b,"a","I prefer lastingNeedle.")),c=claim(s,seed(*b,"b","I prefer temporary.","alpha",at));link(s,a,c);
    check(s.recall("lastingNeedle")["items"][0]["facts"].size()==2,"counterclaim before expiry");
    std::this_thread::sleep_until(std::chrono::system_clock::time_point(std::chrono::seconds(at+1)));
    const auto r=s.recall("lastingNeedle");check(r["items"][0]["facts"].size()==1 && r["items"][0]["contradictions"].empty(),"expired counterclaim omitted next call");
    check(scalar(*b,"SELECT COUNT(*) FROM memory_fact_relations")==1,"read did not delete expired stored relation");
  });
}
void bounds() {
  scenario("whole neighborhood exact byte and count budgets",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");auto a=claim(s,seed(*b,"a","I prefer needle alpha.")),
        c=claim(s,seed(*b,"b","I prefer beta.")),d=claim(s,seed(*b,"c","I prefer gamma."));link(s,a,c);link(s,a,d);
    const auto r=s.recall("needle","",50,32768);const auto size=int(r.dump().size());
    check(size>512 && size<=32768 && r["items"][0]["facts"].size()==3,"whole star neighborhood baseline");
    check(s.recall("needle","",50,size)==r,"exact JSON byte budget accepted");
    const auto shorted=s.recall("needle","",50,size-1);
    check(shorted["items"].empty() && shorted["truncated"]==true && int(shorted.dump().size())<=size-1,"cannot return anchor with only some counterclaims");
    const auto tiny=s.recall("needle","",1,512);check(tiny["items"].empty() && tiny["truncated"]==true && tiny.dump().size()<=512,"small valid budget does not hide truncation");
    claim(s,seed(*b,"d","I prefer needle delta."));
    auto limited=s.recall("needle","",1,32768);check(limited["items"].size()==1 && limited["truncated"]==true,"matched anchor count bounded");
  });
  scenario("candidate and relation limits are explicit",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");auto e=seed(*b,"all","I prefer allNeedle.");
    for(int i=0;i<101;++i)claim(s,e,"p"+std::to_string(i));
    b->db().exec("UPDATE memory_fact_evidence SET quote_hash='forged'");
    auto r=s.recall("allNeedle","",50,32768);check(r["items"].empty() && r["truncated"]==true,"filtered bad evidence cannot bypass candidate cap");
    auto clean=fresh();memory::FactStore t(*clean,"alpha");auto a=claim(t,seed(*clean,"a","I prefer boundNeedle."));
    for(int i=0;i<33;++i) {
      auto c=claim(t,seed(*clean,"b"+std::to_string(i),"I prefer option "+std::to_string(i)+"."));
      auto x=a["fact_id"].get<std::string>(),y=c["fact_id"].get<std::string>();if(y<x)std::swap(x,y);
      auto q=clean->db().prepare("INSERT INTO memory_fact_relations VALUES('alpha',?,?,'contradicts',1)");q.bind_text(1,x);q.bind_text(2,y);q.step_done();
    }
    reject([&]{t.recall("boundNeedle","",50,32768);},"fact_relation_limit");
  });
  scenario("evidence work limit discards in-progress neighborhood",[] {
    auto b=fresh();memory::FactStore s(*b,"alpha");auto a=claim(s,seed(*b,"a","I prefer budgetNeedle.","alpha",0,true));
    for(int i=0;i<32;++i) {auto c=claim(s,seed(*b,"b"+std::to_string(i),"I prefer large option "+std::to_string(i)+".","alpha",0,true));link(s,a,c);}
    const auto r=s.recall("budgetNeedle","",50,32768);
    check(r["items"].empty() && r["truncated"]==true && r["work_limited"]==true,"8MiB work exhaustion never emits partial star");
    check(r.dump().size()<=32768,"work failure metadata bounded");
  });
}
void snapshot() {
  scenario("anchor and all counterclaims share a real WAL snapshot",[] {
    const auto dir=std::filesystem::temp_directory_path()/std::filesystem::path("qbrain-recall-"+
      util::sha256_hex(std::to_string(std::chrono::steady_clock::now().time_since_epoch().count())).substr(0,16));
    std::filesystem::create_directory(dir);
    { Brain reader;reader.open_at(util::path_to_utf8(dir/"brain.db"));reader.ensure_source("alpha");reader.save_config_value("memory.writeback","salient");
      memory::FactStore s(reader,"alpha");auto a=seed(reader,"a","I prefer snapshotNeedle."),b=seed(reader,"b","I prefer old counterpart.");link(s,claim(s,a),claim(s,b));
      Brain writer;writer.open_at(util::path_to_utf8(dir/"brain.db"));
      struct State {Brain* writer;sqlite3* reader;std::string event;bool fired=false,committed=false,snapshot=false;int loads=0;} state{&writer,reader.db().handle(),b.event};
      sqlite3_trace_v2(reader.db().handle(),SQLITE_TRACE_STMT,[](unsigned,void* ctx,void* raw,void*)->int {
        auto& x=*static_cast<State*>(ctx);const char* text=sqlite3_sql(static_cast<sqlite3_stmt*>(raw));
        if(text && std::string(text).starts_with("SELECT subject,predicate,object,status") && ++x.loads==2) {
          x.fired=true;x.snapshot=sqlite3_txn_state(x.reader,"main")==SQLITE_TXN_READ;
          try{memory::forget(*x.writer,"alpha",x.event);x.committed=true;}catch(...){}
        }return 0;
      },&state);
      const auto first=s.recall("snapshotNeedle");sqlite3_trace_v2(reader.db().handle(),0,nullptr,nullptr);
      check(state.fired && state.snapshot && state.committed,"second real connection commits before neighbor loads");
      check(first["items"].size()==1 && first["items"][0]["facts"].size()==2,"current complete neighborhood from prior snapshot");
      const auto next=s.recall("snapshotNeedle");check(next["items"][0]["facts"].size()==1 && next["items"][0]["contradictions"].empty(),"next call sees forget and has no stale evidence cache");
      check(sqlite3_txn_state(reader.db().handle(),"main")==SQLITE_TXN_NONE,"read snapshot released");
    }
    std::filesystem::remove_all(dir);
  });
}
}
void test_n47c() {
  checks=0;scenarios=J::array();basic();lifecycle();bounds();snapshot();
  std::cout<<"N47C fact recall: "<<scenarios.size()<<" scenarios, "<<checks<<" checks passed\n";
}
#ifdef QBRAIN_RECALL_STANDALONE
int main(int argc,char** argv) {
  try {test_n47c();if(argc==3 && std::string(argv[1])=="--report") {
    std::ofstream f(argv[2],std::ios::binary);if(!f)throw std::runtime_error("report open");
    f<<J({{"result","PASS"},{"scenario_count",scenarios.size()},{"checks",checks},{"scenarios",scenarios}}).dump(2)<<'\n';if(!f)throw std::runtime_error("report write");
  }else if(argc!=1)throw std::runtime_error("arguments");return 0;}
  catch(const std::exception& e){std::cerr<<"[FAIL] N47C: "<<e.what()<<'\n';return 1;}
}
#endif
