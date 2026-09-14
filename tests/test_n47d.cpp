#include "qbrain/integration/detail/fact_context.hpp"
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
void check(bool ok,const char* label){if(!ok)throw std::runtime_error(label);++checks;}
template<class F> void scenario(const char* name,F f){const int n=checks;f();scenarios.push_back({{"name",name},{"status","PASS"},{"assertions",checks-n}});}
template<class F> void reject(F f){try{f();}catch(const std::exception&){++checks;return;}throw std::runtime_error("expected rejection");}
std::unique_ptr<Brain> fresh(){auto b=std::make_unique<Brain>();b->open_at(":memory:");b->ensure_source("alpha");b->ensure_source("beta");b->save_config_value("memory.writeback","salient");return b;}
struct Seed{std::string item,event,quote;};
Seed seed(Brain& b,const std::string& tag,const std::string& quote,const std::string& source="alpha",int64_t until=0){
 const std::string event=memory::capture(b,source,{{"session_id","hook-facts"},{"fragment_id",tag},{"expires_at",until},
    {"messages",J::array({{{"role","user"},{"content",quote}}})}},true)["event_id"];
 check(memory::extract(b,source,event)["item_count"]==1,"real extracted quote");
 auto st=b.db().prepare("SELECT item_id FROM memory_items WHERE event_id=?");st.bind_text(1,event);check(st.step(),"real item");return{st.column_text(0),event,quote};
}
J claim(memory::FactStore& s,const Seed& e){return s.create({{"predicate","preference.editor"},{"item_id",e.item}});}
void link(memory::FactStore& s,const J& a,const J& b){s.contradict({{"fact_id",a["fact_id"]},{"other_id",b["fact_id"]}});}
J compose(Brain& b,const std::string& event="UserPromptSubmit",const std::string& prompt="needle",int budget=8192,int limit=8,const std::set<std::string>& seen={}){
 return integration::detail::compose_fact_context(b,"alpha",event,prompt,budget,limit,seen);
}
J payload(const J& result){auto text=result["output"]["hookSpecificOutput"]["additionalContext"].get<std::string>();return J::parse(text.substr(text.find('\n')+1));}
int64_t scalar(Brain& b,const std::string& sql){auto st=b.db().prepare(sql);check(st.step(),"scalar row");return st.column_int(0);}
void basic(){
 scenario("lazy opt-in composition retains ordinary memory without migration",[]{
  auto b=fresh();seed(*b,"raw","I prefer ordinary needle memory.");
  const auto n=scalar(*b,"SELECT COUNT(*) FROM sqlite_master");const int changed=sqlite3_total_changes(b->db().handle());
  sqlite3_set_authorizer(b->db().handle(),[](void*,int action,const char*,const char*,const char*,const char*){
   switch(action){case SQLITE_INSERT:case SQLITE_UPDATE:case SQLITE_DELETE:case SQLITE_CREATE_TABLE:case SQLITE_CREATE_INDEX:return SQLITE_DENY;}return SQLITE_OK;
  },nullptr);
  const auto r=compose(*b);sqlite3_set_authorizer(b->db().handle(),nullptr,nullptr);
  check(payload(r)["memories"].size()==1 && payload(r)["fact_groups"].empty(),"ordinary lane available");
  check(n==scalar(*b,"SELECT COUNT(*) FROM sqlite_master") && changed==sqlite3_total_changes(b->db().handle()),"read adds no tables or data");
  check(scalar(*b,"SELECT COUNT(*) FROM jobs")==0,"no jobs");
 });
 scenario("one context retains counterclaim and suppresses duplicate raw quotes",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");const auto a=seed(*b,"a","I prefer needle command line, not a GUI."),c=seed(*b,"b","I prefer a graphical interface.");
  auto f=claim(s,a),g=claim(s,c);link(s,f,g);seed(*b,"duplicate",a.quote);seed(*b,"ordinary","I prefer needle unrelated memory.");
  const auto r=compose(*b);const auto p=payload(r);
  check(p["fact_groups"].size()==1 && p["fact_groups"][0]["facts"].size()==2,"full matched neighborhood");
  check(p["fact_groups"][0]["facts"][1]["object"]==c.quote,"nonmatching counterclaim present");
  check(p["memories"].size()==1 && p["memories"][0]["quote"]=="I prefer needle unrelated memory.","raw exact-quote copy cannot bypass facts");
  check(r["fact_group_count"]==1 && r["memory_count"]==1,"counts describe actual output");
  check(r["output"].size()==1 && !r["output"].contains("decision"),"context only, no workflow decision");
 });
 scenario("entire serialized envelope obeys exact byte boundary",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");const auto a=seed(*b,"a","我偏好 needle \"引号\" 和反斜线 \\，但不喜欢遗漏。😀"),c=seed(*b,"b","我偏好完整的另一方意见。😀");
  auto f=claim(s,a),g=claim(s,c);link(s,f,g);seed(*b,"copy",a.quote);
  const auto full=compose(*b);const int size=int(full["output"].dump().size());check(size>512 && size<8192,"fixture crosses envelope minimum");
  check(compose(*b,"UserPromptSubmit","needle",size)["output"]==full["output"],"exact serialized boundary accepted");
  const auto less=compose(*b,"UserPromptSubmit","needle",size-1);
  check(less["fact_group_count"]==0 && less["memory_count"]==0 && less["truncated"]==true,"never split or fallback to a bound quote");
  check(less["output"].dump().size()<=std::size_t(size-1),"metadata stays bounded");
  for(int budget=512;budget<=8192;budget+=127){auto r=compose(*b,"UserPromptSubmit","needle",budget);check(r["output"].dump().size()<=std::size_t(budget),"UTF8 and escaping included in byte cap");if(r["fact_group_count"]!=0)check(payload(r)["fact_groups"][0]["facts"].size()==2,"budget retains whole pair");}
 });
 scenario("one item budget prioritizes complete fact neighborhoods",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");claim(s,seed(*b,"a","I prefer needle fact."));seed(*b,"b","I prefer needle ordinary.");
  auto r=compose(*b,"UserPromptSubmit","needle",8192,1);
  check(r["fact_group_count"]==1 && r["memory_count"]==0 && r["truncated"]==true,"fact priority and total item budget");
  r=compose(*b,"UserPromptSubmit","needle",8192,2);check(r["fact_group_count"]==1 && r["memory_count"]==1,"both lanes share count budget");
 });
 scenario("lexical terms share one query and empty prompts do not enumerate facts",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");claim(s,seed(*b,"a","I prefer alphaNeedle."));claim(s,seed(*b,"b","I prefer betaNeedle."));
  auto r=compose(*b,"UserPromptSubmit","Please check alphaNeedle and betaNeedle alphaNeedle");
  check(r["fact_group_count"]==2,"OR literal terms return both anchors without duplicates");
  check(compose(*b,"UserPromptSubmit","please check and the")["output"].empty(),"no usable terms means no context");
  check(compose(*b,"UserPromptSubmit","")["output"].empty(),"empty prompt cannot enumerate recent facts");
  check(compose(*b,"SessionStart","")["fact_group_count"]==2,"SessionStart intentionally recalls recent active facts");
  check(s.recall_for_hook({"alphaNeedle","betaNeedle"})["items"].size()==2,"internal multi-term entry shares row selection");
  reject([&]{s.recall_for_hook(std::vector<std::string>(9,"x"));});
  reject([&]{s.recall_for_hook({std::string(600,'x'),std::string(600,'y')});});
  reject([&]{s.recall_for_hook({""});});
  reject([&]{s.recall("");});check(s.recall("alphaNeedle")["items"].size()==1,"public single query semantics retained");
 });
 scenario("invalid prompt flags budgets and secrets fail closed",[]{
  auto b=fresh();
  for(const auto& q:std::vector<std::string>{std::string("a\0b",3),std::string("\xff"),std::string(131073,'x')})reject([&]{compose(*b,"UserPromptSubmit",q);});
  reject([&]{compose(*b,"Stop");});reject([&]{compose(*b,"SessionStart","",511);});reject([&]{compose(*b,"SessionStart","",8193);});
  reject([&]{compose(*b,"SessionStart","",8192,0);});reject([&]{compose(*b,"SessionStart","",8192,17);});
  check(compose(*b,"UserPromptSubmit","password=synthetic-do-not-store")["output"].empty(),"sensitive prompt not recalled or echoed");
 });
}
void lifecycle(){
 scenario("retracted and superseded claims do not return via ordinary memory",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");const auto a=seed(*b,"a","I prefer needle old choice.");auto f=claim(s,a);seed(*b,"duplicate",a.quote);
  s.retract({{"fact_id",f["fact_id"]},{"expected_revision",1}});
  check(compose(*b)["output"].empty(),"retracted quote absent from both lanes");
  auto g=claim(s,seed(*b,"b","I prefer needle candidate.")),h=claim(s,seed(*b,"c","I prefer needle replacement."));
  s.supersede({{"fact_id",g["fact_id"]},{"replacement_id",h["fact_id"]},{"expected_revision",1}});
  const auto r=compose(*b);check(r["fact_group_count"]==1 && r["memory_count"]==0,"only active replacement is emitted");
 });
 scenario("fact groups refresh independently of memory dedup and revision changes",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");const auto a=seed(*b,"a","I prefer needle.");auto f=claim(s,a);
  const auto raw=seed(*b,"raw","I prefer needle ordinary.");const auto before=compose(*b);
  auto g=claim(s,seed(*b,"b","I prefer another interface."));link(s,f,g);
  const auto after=compose(*b,"UserPromptSubmit","needle",8192,8,{a.item,raw.item,f["fact_id"].get<std::string>()});
  check(after["fact_group_count"]==1 && after["memory_count"]==0,"fact refresh never suppressed by seen state");
  check(payload(after)["fact_groups"][0]["facts"].size()==2,"new nonmatching counterevidence delivered");
  check(payload(before)["fact_groups"][0]["facts"][0]["revision"]==1 && payload(after)["fact_groups"][0]["facts"][0]["revision"]==2,"current revisions revalidated");
 });
 scenario("invalid expired or forgotten evidence cannot reenter either lane",[]{
  for(const auto& sql:std::vector<std::string>{"UPDATE memory_items SET quote='forged'","UPDATE memory_events SET expires_at=1","UPDATE pages SET deleted_at='deleted'","UPDATE memory_fact_evidence SET quote_hash='tampered'"}){
   auto b=fresh();memory::FactStore s(*b,"alpha");claim(s,seed(*b,"a","I prefer needle."));b->db().exec(sql);
   check(compose(*b)["output"].empty(),"bad fact or evidence hidden, no raw bypass");
  }
  auto b=fresh();memory::FactStore s(*b,"alpha");const auto a=seed(*b,"a","I prefer needle."),c=seed(*b,"b",a.quote);auto f=claim(s,a);
  s.attach({{"fact_id",f["fact_id"]},{"item_id",c.item}});memory::forget(*b,"alpha",a.event);
  check(payload(compose(*b))["fact_groups"][0]["facts"][0]["evidence_count"]==1,"one valid support survives");
  memory::forget(*b,"alpha",c.event);check(compose(*b)["output"].empty(),"last evidence forgotten disappears");
 });
 scenario("source isolation applies to both lanes and quote suppression",[]{
  auto b=fresh();memory::FactStore other(*b,"beta");const auto foreign=seed(*b,"beta","I prefer needle shared text.","beta");claim(other,foreign);
  seed(*b,"alpha",foreign.quote);auto r=compose(*b);
  check(r["fact_group_count"]==0 && r["memory_count"]==1,"foreign fact neither leaks nor suppresses current source memory");
  reject([&]{integration::detail::compose_fact_context(*b,"missing","SessionStart","",8192,8);});
  check(scalar(*b,"SELECT COUNT(*) FROM jobs")==0,"no extra extraction or model job");
 });
 scenario("failed composition rolls back only its own read transaction",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");claim(s,seed(*b,"a","I prefer needle."));
  b->db().exec("BEGIN");reject([&]{compose(*b);});check(!sqlite3_get_autocommit(b->db().handle()),"nested rejection preserves caller transaction");b->db().exec("ROLLBACK");
  b->db().exec("DROP TRIGGER memory_fact_last_evidence");reject([&]{compose(*b);});
  check(sqlite3_get_autocommit(b->db().handle()),"exception closes owned transaction");
 });
 scenario("wall clock expiry is rechecked without persisted fact context",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto until=std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count()+2;
  claim(s,seed(*b,"exp","I prefer needle temporary.","alpha",until));check(compose(*b)["fact_group_count"]==1,"unexpired context");
  std::this_thread::sleep_until(std::chrono::system_clock::time_point(std::chrono::seconds(until+1)));
  check(compose(*b)["output"].empty(),"next event sees expiry without edits");
 });
}
void snapshot(){
 scenario("both context lanes use one snapshot across a committed WAL forget",[]{
  const auto path=std::filesystem::temp_directory_path()/("qbrain-n47d-"+util::sha256_hex(std::to_string(std::chrono::steady_clock::now().time_since_epoch().count())).substr(0,16));
  std::filesystem::create_directory(path);
  {Brain reader;reader.open_at(util::path_to_utf8(path/"brain.db"));reader.ensure_source("alpha");reader.save_config_value("memory.writeback","salient");
   auto a=seed(reader,"a","I prefer needle snapshot."),c=seed(reader,"b","I prefer alternative snapshot.");memory::FactStore s(reader,"alpha");auto f=claim(s,a),g=claim(s,c);link(s,f,g);
   Brain writer;writer.open_at(util::path_to_utf8(path/"brain.db"));
   struct Interleave{Brain* b;std::string event;bool fired=false;std::string error;};Interleave state{&writer,a.event};
   sqlite3_trace_v2(reader.db().handle(),SQLITE_TRACE_STMT,[](unsigned,void* raw,void*,void* text)->int{
    auto& x=*static_cast<Interleave*>(raw);std::string sql=static_cast<const char*>(text);
    if(!x.fired&&sql.find("SELECT fact_id FROM memory_facts")!=std::string::npos){x.fired=true;try{memory::forget(*x.b,"alpha",x.event);}catch(const std::exception& e){x.error=e.what();}}
    return 0;
   },&state);
   auto r=compose(reader);sqlite3_trace_v2(reader.db().handle(),0,nullptr,nullptr);
   check(state.fired&&state.error.empty(),"real second connection commits during read");
   check(payload(r)["fact_groups"][0]["facts"].size()==2 && r["memory_count"]==0,"complete old snapshot and bound-memory suppression");
   check(compose(reader)["output"].empty(),"next event observes committed forget");
   check(sqlite3_get_autocommit(reader.db().handle()),"snapshot closed before potential capture");
  }std::filesystem::remove_all(path);
 });
}
}
void test_n47d(){checks=0;scenarios=J::array();basic();lifecycle();snapshot();std::cout<<"N47D Hook fact context: "<<scenarios.size()<<" scenarios, "<<checks<<" checks passed\n";}
#ifdef QBRAIN_HOOK_FACT_STANDALONE
int main(int argc,char** argv){try{test_n47d();if(argc==3&&std::string(argv[1])=="--report"){std::ofstream out(argv[2],std::ios::binary);out<<J{{"result","PASS"},{"scenarios",scenarios},{"scenario_count",scenarios.size()},{"checks",checks}}.dump(2)<<'\n';if(!out)throw std::runtime_error("report write failed");}else if(argc!=1)throw std::runtime_error("arguments");return 0;}catch(const std::exception& e){std::cerr<<"[FAIL] N47D: "<<e.what()<<'\n';return 1;}}
#endif
