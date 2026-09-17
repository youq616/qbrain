#include "qbrain/memory/fact_store.hpp"
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
int checks=0; J scenarios=J::array();
void check(bool ok,const char* why){if(!ok)throw std::runtime_error(why);++checks;}
template<class F>void scenario(const char* name,F f){const auto before=checks;f();scenarios.push_back({{"name",name},{"status","PASS"},{"assertions",checks-before}});}
template<class F>void reject(F f,const char* code){try{f();}catch(const memory::Error& e){check(std::string(e.what())==code,"stable rejection code");return;}throw std::runtime_error("expected rejection");}
std::unique_ptr<Brain> fresh(){auto b=std::make_unique<Brain>();b->open_at(":memory:");b->ensure_source("alpha");b->ensure_source("beta");b->save_config_value("memory.writeback","salient");return b;}
struct Seed{std::string event,item,quote;};
Seed seed(Brain& b,const std::string& tag,const std::string& quote,const std::string& source="alpha",int64_t expires=0){
 auto c=memory::capture(b,source,{{"session_id","multiterm-unit"},{"fragment_id",tag},{"expires_at",expires},{"messages",J::array({{{"role","user"},{"content",quote}}})}},true);
 const auto event=c["event_id"].get<std::string>();check(memory::extract(b,source,event)["item_count"]==1,"real local extracted quote");
 auto s=b.db().prepare("SELECT item_id FROM memory_items WHERE event_id=?");s.bind_text(1,event);check(s.step(),"evidence exists");return{event,s.column_text(0),quote};
}
J claim(memory::FactStore& s,const Seed& e,const std::string& pred="preference.editor"){return s.create({{"item_id",e.item},{"predicate",pred}});}
void link(memory::FactStore& s,const J& a,const J& b){s.contradict({{"fact_id",a["fact_id"]},{"other_id",b["fact_id"]}});}
J recall(memory::FactStore& s,const std::string& q,const std::string& mode,int limit=50,int bytes=32768,const std::string& pred=""){return s.recall(q,pred,limit,bytes,mode);}
std::set<std::string> ids(const J& r){std::set<std::string> out;for(const auto& i:r["items"])out.insert(i["match_fact_id"].get<std::string>());return out;}
int64_t scalar(Brain& b,const std::string& sql){auto s=b.db().prepare(sql);check(s.step(),"scalar read");return s.column_int(0);}
int64_t now(){return std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count();}
void basic(){
 scenario("explicit modes validate before lazy schema initialization",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto n=scalar(*b,"SELECT COUNT(*) FROM sqlite_master");
  for(const auto* mode:{"literal","all_terms","any_terms"}){auto r=recall(s,"one two",mode);check(r["items"].empty() && r["initialized"]==false,"lazy read");check(r["match_mode"]==(std::string(mode)=="literal"?"literal_substring":mode),"accurate explicit mode");}
  for(const auto* mode:{"","ALL_TERMS","or","recent_active","literal_substring"})reject([&]{recall(s,"x",mode);},"fact_invalid_match");
  for(const auto* mode:{"literal","all_terms","any_terms"})for(const auto& q:std::vector<std::string>{""," \t\r\n",std::string("a\0b",3),std::string("\xff"),std::string("中\xff"),std::string("\xc0\xaf"),std::string("\xed\xa0\x80")})reject([&]{recall(s,q,mode);},"fact_invalid_query");
  check(scalar(*b,"SELECT COUNT(*) FROM sqlite_master")==n,"all rejects and reads leave schema alone");
 });
 scenario("default and explicit literal retain exact legacy output bytes",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=claim(s,seed(*b,"a","I prefer red then blue 命令行."));auto c=claim(s,seed(*b,"b","I prefer a GUI."));link(s,a,c);
  for(const auto& q:std::vector<std::string>{"red","red blue","red then blue","命令","GUI","absent"," red"}){
   auto legacy=s.recall_for_hook({q},10,8192).dump();check(s.recall(q).dump()==legacy,"default bytes equal preexisting internal literal path");check(s.recall(q,"",10,8192,"literal").dump()==legacy,"explicit literal bytes unchanged");
  }
  check(s.recall_for_hook({"red","GUI"})["match_mode"]=="any_literal_term","Hook multi-query mode unchanged");check(s.recall_for_hook({})["match_mode"]=="recent_active","Hook empty query unchanged");
 });
 scenario("all terms match one anchor and never combine separate facts",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=claim(s,seed(*b,"a","I prefer red then blue."));auto r=claim(s,seed(*b,"r","I prefer red."));auto blue=claim(s,seed(*b,"b","I prefer blue."));
  check(ids(recall(s,"red blue","all_terms"))==std::set<std::string>{a["fact_id"]},"AND does not become OR");
  check(ids(recall(s,"blue red","all_terms"))==std::set<std::string>{a["fact_id"]},"term order irrelevant");
  s.retract({{"fact_id",a["fact_id"]},{"expected_revision",1}});check(recall(s,"red blue","all_terms")["items"].empty(),"no cross-fact conjunction");
  check(ids(recall(s,"red blue","any_terms"))==std::set<std::string>{r["fact_id"],blue["fact_id"]},"OR still selects independent anchors");
 });
 scenario("any terms use union without duplicate anchors and preserve ordering",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=claim(s,seed(*b,"a","I prefer red then blue."));auto r=claim(s,seed(*b,"r","I prefer red."));auto z=claim(s,seed(*b,"z","I prefer other."));
  b->db().exec("UPDATE memory_facts SET created_at=10");auto out=recall(s,"red blue red","any_terms");check(ids(out)==std::set<std::string>{a["fact_id"],r["fact_id"]},"OR union and distinct anchors");
  check(out["items"].size()==2 && out["items"][0]["match_fact_id"]<out["items"][1]["match_fact_id"],"same timestamp sorted by ID");check(out["order"]=="created_desc_id","no semantic score order");
  check(out==recall(s,"blue red red","any_terms"),"equivalent query term order identical output");
 });
 scenario("ASCII separators and duplicate term bounds are explicit",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");claim(s,seed(*b,"a","I prefer red then blue."));
  for(const auto* mode:{"all_terms","any_terms"}){
   check(recall(s," \tred\r\n blue \t",mode)["items"].size()==1,"only specified ASCII separators split");
   check(recall(s,"red red red red red red red red",mode)["items"].size()==1,"eight repeated terms allowed");
   reject([&]{recall(s,"red red red red red red red red red",mode);},"fact_invalid_query");
   check(recall(s,"red\vblue",mode)["items"].empty(),"vertical tab is not a separator");
   check(recall(s,"red\fblue",mode)["items"].empty(),"form feed is not a separator");
   check(recall(s,"red\xc2\xa0" "blue",mode)["items"].empty(),"NBSP is not a separator");
  }
 });
 scenario("mixed scripts and negation preserve full user evidence",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto e=seed(*b,"a","我偏好不使用 MT5，而用命令行。日本語 한국어 😀 ÉCOLE 𠀀");auto a=claim(s,e);
  for(const auto* mode:{"all_terms","any_terms"}){
   auto r=recall(s,"mt5 命令",mode);check(r["items"].size()==1,"mixed terms match");const auto& f=r["items"][0]["facts"][0];
   check(f["object"]==e.quote && f["fact_id"]==a["fact_id"],"negated original quote not rewritten");check(f["confidence"].is_null() && f["untrusted_data"]==true,"not truth scoring");
   check(f["evidence"][0]["item_id"]==e.item && f["evidence"][0]["event_id"]==e.event,"real evidence binding");
   check(recall(s,"日本語 한국어 😀 𠀀",mode)["items"].size()==1,"non-BMP and scripts retained");check(recall(s,"école",mode)["items"].empty(),"no non-ASCII case folding promised");
  }
 });
 scenario("original query bytes include all whitespace before splitting",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");
  for(const auto* mode:{"literal","all_terms","any_terms"}){
   check(recall(s,std::string(1024,'x'),mode)["items"].empty(),"1024 byte query accepted");
   reject([&]{recall(s,std::string(1025,'x'),mode);},"fact_invalid_query");
   check(recall(s,std::string(1023,' ')+"x",mode)["items"].empty(),"1024 including whitespace accepted");
   reject([&]{recall(s,std::string(1024,' ')+"x",mode);},"fact_invalid_query");
   std::string q;for(int i=0;i<341;++i)q+="界";q+='x';check(recall(s,q,mode)["items"].empty(),"UTF8 byte boundary accepted");q+='y';reject([&]{recall(s,q,mode);},"fact_invalid_query");
  }
 });
 scenario("whole sensitive input is rejected before token boundaries",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");
  for(const auto* mode:{"literal","all_terms","any_terms"})for(const auto& q:std::vector<std::string>{"Bearer value","api key = value","seed phrase : value","password : value","red ghp_dummyvalue","密钥 ： value"})reject([&]{recall(s,q,mode);},"sensitive_material_rejected");
  check(scalar(*b,"SELECT COUNT(*) FROM sqlite_master WHERE name='memory_facts'")==0,"sensitive inputs cannot initialize facts");
 });
 scenario("SQL and wildcard text stay literal bound values",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=claim(s,seed(*b,"a","I prefer 100% a_b ' OR 1=1 -- path\\name."));claim(s,seed(*b,"b","I prefer ordinary text."));
  for(const auto* mode:{"all_terms","any_terms"})for(const auto& q:std::vector<std::string>{"% _","' 1=1","path\\name","-- %"})check(ids(recall(s,q,mode))==std::set<std::string>{a["fact_id"]},"literal SQL and wildcards cannot expand query");
  check(scalar(*b,"SELECT COUNT(*) FROM memory_facts")==2,"no SQL mutation");
 });
 scenario("matching precedes candidate cap and source predicate filters",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha"),other(*b,"beta");auto a=claim(s,seed(*b,"old","I prefer ancientRare then termNeedle."));b->db().exec("UPDATE memory_facts SET created_at=1");auto n=seed(*b,"noise","I prefer unrelated recent data.");
  for(int i=0;i<105;++i)claim(s,n,"noise"+std::to_string(i));
  for(const auto* mode:{"all_terms","any_terms"}){
   check(ids(recall(s,"ancientRare termNeedle",mode))==std::set<std::string>{a["fact_id"]},"old matching candidate survives 105 unrelated facts");
   check(recall(s,"ancientRare termNeedle",mode,50,32768,"other")["items"].empty(),"predicate narrows matches");check(recall(other,"ancientRare termNeedle",mode)["items"].empty(),"source isolation");
  }
 });
 scenario("archived nonmatching counterclaims remain complete",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=claim(s,seed(*b,"a","I prefer red then blue."));auto e=seed(*b,"b","I prefer graphical menus.");auto c=claim(s,e);
  check(recall(s,"red blue","all_terms")["items"][0]["facts"].size()==1,"no inferred conflict");link(s,a,c);s.archive({{"fact_id",c["fact_id"]},{"expected_revision",2}});
  for(const auto* mode:{"all_terms","any_terms"}){
   auto r=recall(s,"red blue",mode);check(r["items"].size()==1 && r["items"][0]["facts"].size()==2,"required nonmatching archived counterclaim retained");check(r["items"][0]["facts"][1]["object"]==e.quote,"complete opposing quote");check(r["items"][0]["conflict_state"]=="recorded_conflict","explicit conflict not decided");
   check(recall(s,"graphical",mode)["items"].empty(),"archive still suppresses matching anchors");
  }
  s.archive({{"fact_id",a["fact_id"]},{"expected_revision",2}});check(recall(s,"red blue","any_terms")["items"].empty(),"archived anchor hidden");
 });
 scenario("matching neighbors keep independent one-hop counter-evidence",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=claim(s,seed(*b,"a","I prefer red then blue."));auto c=claim(s,seed(*b,"b","I prefer blue then red."));auto d=claim(s,seed(*b,"c","I prefer another method."));link(s,a,c);link(s,c,d);
  for(const auto* mode:{"all_terms","any_terms"}){auto r=recall(s,"red blue",mode);check(r["items"].size()==2,"both matching anchors included");for(const auto& i:r["items"]){if(i["match_fact_id"]==a["fact_id"])check(i["facts"].size()==2,"not a transitive graph traversal");else check(i["facts"].size()==3,"neighbor anchor keeps its own other edge");}check(r["neighbors_recursively_expanded"]==false,"one hop declared");}
 });
 scenario("forget expiry and tamper invalidate both modes without revival",[]{
  for(const auto* mode:{"all_terms","any_terms"}){
   auto b=fresh();memory::FactStore s(*b,"alpha");auto a=claim(s,seed(*b,"a","I prefer red then blue."));auto e=seed(*b,"b","I prefer another method.");auto c=claim(s,e);link(s,a,c);
   b->db().exec("UPDATE memory_items SET expires_at=1 WHERE item_id='"+e.item+"'");check(recall(s,"red blue",mode)["items"][0]["facts"].size()==1,"expired counterclaim omitted");
   b->db().exec("UPDATE memory_items SET expires_at=0 WHERE item_id='"+e.item+"'");check(recall(s,"red blue",mode)["items"][0]["facts"].size()==2,"live evidence revalidated");
   memory::forget(*b,"alpha",e.event);check(recall(s,"red blue",mode)["items"][0]["facts"].size()==1,"forgotten counterclaim absent");
   auto replacement=claim(s,seed(*b,"new","I prefer different blue and red."));auto rev=s.read(a["fact_id"])["items"][0]["revision"];s.supersede({{"fact_id",a["fact_id"]},{"replacement_id",replacement["fact_id"]},{"expected_revision",rev}});
   check(ids(recall(s,"red blue",mode))==std::set<std::string>{replacement["fact_id"]},"superseded original excluded");
   b->db().exec("UPDATE memory_fact_evidence SET quote_hash='damaged' WHERE fact_id='"+replacement["fact_id"].get<std::string>()+"'");check(recall(s,"red blue",mode)["items"].empty(),"damaged replacement does not revive old assertion");
  }
 });
 scenario("byte and result bounds preserve entire multi-term groups",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=claim(s,seed(*b,"a","I prefer red then blue."));auto c=claim(s,seed(*b,"b","I prefer GUI."));link(s,a,c);
  for(const auto* mode:{"all_terms","any_terms"}){auto full=recall(s,"red blue",mode);const int bytes=int(full.dump().size());check(recall(s,"red blue",mode,50,bytes)==full,"exact whole output budget");auto r=recall(s,"red blue",mode,50,bytes-1);check(r["items"].empty() && r["truncated"]==true && r.dump().size()<=static_cast<std::size_t>(bytes-1),"one byte short must not emit half-group");
   for(const auto& pair:std::vector<std::pair<int,int>>{{0,8192},{51,8192},{1,511},{1,32769}})reject([&]{recall(s,"red blue",mode,pair.first,pair.second);},"invalid_read_budget");
  }
 });
 scenario("term recall does not write or control caller transactions",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");claim(s,seed(*b,"a","I prefer red then blue."));auto changes=sqlite3_total_changes(b->db().handle());
  b->db().exec("BEGIN");sqlite3_set_authorizer(b->db().handle(),[](void*,int action,const char*,const char*,const char*,const char*){switch(action){case SQLITE_INSERT:case SQLITE_UPDATE:case SQLITE_DELETE:case SQLITE_TRANSACTION:case SQLITE_CREATE_TABLE:return SQLITE_DENY;}return SQLITE_OK;},nullptr);
  for(const auto* mode:{"literal","all_terms","any_terms"}){auto r=recall(s,"red",mode);check(r["items"].size()==1,"read accepted by write denying authorizer");check(sqlite3_get_autocommit(b->db().handle())==0,"caller transaction preserved");}
  sqlite3_set_authorizer(b->db().handle(),nullptr,nullptr);b->db().exec("ROLLBACK");check(sqlite3_total_changes(b->db().handle())==changes,"read did not write revisions or evidence");check(scalar(*b,"SELECT COUNT(*) FROM jobs")==0,"no provider jobs");
 });
 scenario("multi-term anchors and neighbors share one actual WAL snapshot",[]{
  for(const auto* mode:{"all_terms","any_terms"}){
   auto dir=std::filesystem::temp_directory_path()/("qbrain-n47l-snapshot-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));std::filesystem::create_directories(dir);
   {Brain reader;reader.open_at(util::path_to_utf8(dir/"brain.db"));reader.ensure_source("alpha");reader.save_config_value("memory.writeback","salient");reader.db().exec("PRAGMA journal_mode=WAL");memory::FactStore s(reader,"alpha");
    auto a=claim(s,seed(reader,"a","I prefer red then blue."));auto e=seed(reader,"b","I prefer opposite.");auto c=claim(s,e);link(s,a,c);Brain writer;writer.open_at(util::path_to_utf8(dir/"brain.db"));
    struct State{Brain* writer;std::string event;bool fired=false,committed=false;} state{&writer,e.event};
    sqlite3_trace_v2(reader.db().handle(),SQLITE_TRACE_STMT,[](unsigned,void* p,void*,void* sql)->int{auto& x=*static_cast<State*>(p);if(!x.fired && sql && std::string(static_cast<char*>(sql)).find("SELECT r.from_id")!=std::string::npos){x.fired=true;try{memory::forget(*x.writer,"alpha",x.event);x.committed=true;}catch(...) {}}return 0;},&state);
    auto first=recall(s,"red blue",mode);sqlite3_trace_v2(reader.db().handle(),0,nullptr,nullptr);check(state.fired && state.committed,"independent connection commits during active reader");check(first["items"].size()==1 && first["items"][0]["facts"].size()==2,"first result retains complete earlier snapshot");auto next=recall(s,"red blue",mode);check(next["items"][0]["facts"].size()==1 && next["items"][0]["contradictions"].empty(),"next call observes committed forget");check(sqlite3_txn_state(reader.db().handle(),"main")==SQLITE_TXN_NONE,"no snapshot leak");
   }std::filesystem::remove_all(dir);
  }
 });
}
}
void test_n47l(){checks=0;scenarios=J::array();basic();std::cout<<"N47L multi-term recall: "<<scenarios.size()<<" scenarios, "<<checks<<" checks passed\n";}
#ifdef QBRAIN_MULTITERM_STANDALONE
int main(int argc,char** argv){try{test_n47l();if(argc==3 && std::string(argv[1])=="--report"){std::ofstream f(argv[2],std::ios::binary);if(!f)throw std::runtime_error("report open");f<<J({{"result","PASS"},{"scenario_count",scenarios.size()},{"checks",checks},{"scenarios",scenarios}}).dump(2)<<'\n';if(!f)throw std::runtime_error("report write");}else if(argc!=1)throw std::runtime_error("arguments");return 0;}catch(const std::exception& e){std::cerr<<"[FAIL] N47L: "<<e.what()<<'\n';return 1;}}
#endif
