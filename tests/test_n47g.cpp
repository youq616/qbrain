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
using namespace qbrain; using J=nlohmann::json;
int checks=0; J scenarios=J::array();
void check(bool ok,const char* label){if(!ok)throw std::runtime_error(label);++checks;}
template<class F> void scenario(const char* name,F f){int before=checks;f();scenarios.push_back({{"name",name},{"status","PASS"},{"assertions",checks-before}});}
template<class F> void denied(F f,const std::string& code=""){
  try{f();}catch(const std::exception& e){check(code.empty() || code==e.what(),"stable expected rejection");return;}
  throw std::runtime_error("expected batch rejection");
}
int64_t scalar(Brain& b,const std::string& sql){auto s=b.db().prepare(sql);check(s.step(),"scalar has row");return s.column_int(0);}
std::unique_ptr<Brain> fresh(){auto b=std::make_unique<Brain>();b->open_at(":memory:");b->ensure_source("alpha");b->ensure_source("beta");b->save_config_value("memory.writeback","all");return b;}
struct Seed{std::string id,event,item,quote;};
Seed seed(Brain& b,const std::string& tag,const std::string& quote="I prefer command line.",const std::string& source="alpha",int64_t expiry=0,bool large=false){
 J messages=J::array({{{"role","user"},{"content",quote}}});
 if(large)for(int i=0;i<4;++i)messages.push_back({{"role","assistant"},{"content",std::string(62000,'x')}});
 const std::string event=memory::capture(b,source,{{"session_id","batch-tests"},{"fragment_id",tag},{"expires_at",expiry},{"messages",messages}},true)["event_id"];
 memory::extract(b,source,event);auto p=memory::FactStore(b,source).promote_event(event);
 check(p["items"].size()==1,"seed uses real local promotion");return {p["items"][0]["fact_id"],event,p["items"][0]["item_id"],quote};
}
J item(const Seed& f,int64_t rev=1){return {{"fact_id",f.id},{"expected_revision",rev}};}
J request(std::string op,J items){return {{"operation",op},{"items",items}};}
J facts(memory::FactStore& s,const Seed& f){auto r=s.read(f.id,"",true);check(r["items"].size()==1,"fact remains supported");return r["items"][0];}
int64_t revision(memory::FactStore& s,const Seed& f){return facts(s,f)["revision"];}
bool archived(memory::FactStore& s,const Seed& f){return s.lifecycle(f.id)["items"][0]["lifecycle"]["archived"];}
std::filesystem::path tempdir(){auto p=std::filesystem::temp_directory_path()/("qbrain-batch-"+util::sha256_hex(std::to_string(std::chrono::steady_clock::now().time_since_epoch().count())).substr(0,20));std::filesystem::create_directory(p);return p;}
void core(){
 scenario("preview is read only with no schema initialization",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto tables=scalar(*b,"SELECT COUNT(*) FROM sqlite_master");
  denied([&]{s.lifecycle_batch(request("archive",J::array({{{"fact_id",std::string(64,'a')},{"expected_revision",1}}})));},"fact_not_found");
  check(scalar(*b,"SELECT COUNT(*) FROM sqlite_master")==tables,"invalid empty-brain preview no schema");
  auto a=seed(*b,"a"),z=seed(*b,"z","我偏好保留完整中文原话。😀");tables=scalar(*b,"SELECT COUNT(*) FROM sqlite_master");
  int before=sqlite3_total_changes(b->db().handle());
  sqlite3_set_authorizer(b->db().handle(),[](void*,int op,const char*,const char*,const char*,const char*){
    return op==SQLITE_INSERT || op==SQLITE_UPDATE || op==SQLITE_DELETE || op==SQLITE_CREATE_TABLE || op==SQLITE_TRANSACTION?SQLITE_DENY:SQLITE_OK;
  },nullptr);
  auto p=s.lifecycle_batch(request("archive",J::array({item(a),item(z)})));
  check(p["result"]=="PREVIEW" && p["applied"]==false && p["counts"]["change"]==2,"preview never claims application");
  check(p["schema_preparation_required"]==true && p["archive_initialized"]==false,"first-use preparation disclosed");
  check(p["items"][0]["revision_before"]==1 && p["items"][0]["revision_after"]==2,"preview predicts revision only");
  check(p.dump().find(a.quote)==std::string::npos && p.dump().find(z.quote)==std::string::npos,"receipts do not copy quotes");
  check(sqlite3_total_changes(b->db().handle())==before,"preview no hidden data writes");
  sqlite3_set_authorizer(b->db().handle(),nullptr,nullptr);
  check(scalar(*b,"SELECT COUNT(*) FROM sqlite_master")==tables && revision(s,a)==1,"preview no schema or revision changes");
  auto no=s.lifecycle_batch(request("restore",J::array({item(a),item(z)})),true);
  check(no["counts"]["unchanged"]==2 && no["applied"]==true,"apply no-ops explicitly reported");
  check(scalar(*b,"SELECT COUNT(*) FROM sqlite_master")==tables && sqlite3_total_changes(b->db().handle())==before,"restore absent policies no DDL or writes");
 });
 scenario("batch archive restore and no-op revisions preserve evidence",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"a"),z=seed(*b,"z","I prefer graphical tools.");
  const auto original=facts(s,a);auto r=s.lifecycle_batch(request("archive",J::array({item(z),item(a)})),true);
  check(r["applied"]==true && r["result"]=="APPLIED" && r["counts"]["total"]==2,"archive applied as one batch");
  check(r["items"][0]["fact_id"]==z.id && r["items"][1]["fact_id"]==a.id,"input order preserved");
  check(archived(s,a) && archived(s,z) && revision(s,a)==2 && revision(s,z)==2,"both policies and revisions changed");
  auto after=facts(s,a);check(after["evidence"]==original["evidence"] && after["object"]==original["object"] && after["status"]=="active","quote evidence retirement unchanged");
  r=s.lifecycle_batch(request("archive",J::array({item(a,2),item(z,2)})),true);
  check(r["counts"]["change"]==0 && revision(s,a)==2 && revision(s,z)==2,"same revision replay no drift");
  denied([&]{s.lifecycle_batch(request("archive",J::array({item(a),item(z)})),true);},"fact_revision_conflict");
  r=s.lifecycle_batch(request("restore",J::array({item(a,2),item(z,2)})),true);
  check(r["counts"]["change"]==2 && !archived(s,a) && !archived(s,z),"batch restore clears both policies");
  check(revision(s,a)==3 && revision(s,z)==3 && s.recall_for_hook({})["items"].size()==2,"restored anchors observable");
 });
 scenario("strict batch size keys identifiers and revision types",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"a");
  for(auto p:J::array({J::array(),J::object(),{{"operation","archive"}},{{"operation","archive"},{"items",nullptr}},request("archive",J::array()),request("retire",J::array({item(a)}))}))denied([&]{s.lifecycle_batch(p,true);});
  auto p=request("archive",J::array({item(a)}));p["apply"]=true;denied([&]{s.lifecycle_batch(p);},"fact_unexpected_argument");
  p=request("archive",J::array({item(a),item(a)}));denied([&]{s.lifecycle_batch(p,true);},"fact_batch_duplicate_id");
  for(auto rev:J::array({true,0,-1,1.5,"1",nullptr,2147483647,18446744073709551615ULL})){
    p=request("archive",J::array({item(a)}));p["items"][0]["expected_revision"]=rev;
    denied([&]{s.lifecycle_batch(p,true);},"fact_invalid_revision");
  }
  p=request("archive",J::array({item(a)}));p["items"][0]["source_id"]="beta";
  denied([&]{s.lifecycle_batch(p,true);},"fact_unexpected_argument");
  p["items"][0].erase("source_id");p["items"][0]["fact_id"]="../other";
  denied([&]{s.lifecycle_batch(p,true);},"fact_invalid_id");
  check(revision(s,a)==1 && !s.lifecycle()["archive_initialized"].get<bool>(),"invalid input no preparation");
 });
 scenario("invalid final selection prevents every earlier change",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"a"),z=seed(*b,"z","I prefer second.");auto beta=seed(*b,"foreign","I prefer isolated.","beta");
  for(const auto& bad:J::array({item(beta),item(z,2),{{"fact_id",std::string(64,'f')},{"expected_revision",1}}})){
    denied([&]{s.lifecycle_batch(request("archive",J::array({item(a),bad})),true);});
    check(revision(s,a)==1 && !s.lifecycle()["archive_initialized"].get<bool>(),"last invalid member no partial change or DDL");
  }
  s.retract(item(z));denied([&]{s.lifecycle_batch(request("archive",J::array({item(a),item(z,2)})),true);},"fact_state_conflict");
  check(revision(s,a)==1 && !s.lifecycle()["archive_initialized"].get<bool>(),"retired final member blocks all");
 });
 scenario("oversized stored object refused before quote materialization",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"a"),z=seed(*b,"z","I prefer second.");
  auto edit=b->db().prepare("UPDATE memory_facts SET object=? WHERE fact_id=?");edit.bind_text(1,std::string(100000,'x'));edit.bind_text(2,z.id);edit.step_done();
  int loaded=0;sqlite3_trace_v2(b->db().handle(),SQLITE_TRACE_STMT,[](unsigned,void* context,void*,void* text)->int {
    if(text && std::string(static_cast<const char*>(text)).find("SELECT subject,predicate,object")!=std::string::npos)++*static_cast<int*>(context);
    return 0;
  },&loaded);
  denied([&]{s.lifecycle_batch(request("archive",J::array({item(a),item(z)})),true);},"fact_not_found");
  sqlite3_trace_v2(b->db().handle(),0,nullptr,nullptr);
  check(loaded==1,"only valid first quote materialized");
  check(revision(s,a)==1 && scalar(*b,"SELECT COUNT(*) FROM sqlite_master WHERE name='memory_fact_archive'")==0,"bad stored quote cannot cause partial change");
 });
 scenario("full 32 selections and 33 rejection with mixed no-ops",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");J entries=J::array();std::vector<Seed> seeds;
  for(int n=0;n<33;++n){seeds.push_back(seed(*b,std::to_string(n),"I prefer choice "+std::to_string(n)+"."));entries.push_back(item(seeds.back()));}
  denied([&]{s.lifecycle_batch(request("archive",entries),true);},"fact_batch_invalid_size");
  check(scalar(*b,"SELECT COUNT(*) FROM memory_facts WHERE revision<>1")==0,"oversize changes none");
  entries.erase(entries.end()-1);s.archive(item(seeds[0]));entries[0]=item(seeds[0],2);
  auto result=s.lifecycle_batch(request("archive",entries),true);
  check(result["counts"]==J({{"total",32},{"change",31},{"unchanged",1}}),"exact bound and mixed changes");
  check(result.dump().size()<32768 && result["items"].size()==32,"complete bounded receipt");
  check(scalar(*b,"SELECT COUNT(*) FROM memory_fact_archive")==32 && revision(s,seeds[0])==2 && revision(s,seeds[32])==1,"32 applied last unselected unchanged");
 });
}
void safety(){
 scenario("mid-archive SQL failure rolls back metadata and revisions",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"a"),z=seed(*b,"z","I prefer second.");
  s.archive(item(a));s.restore(item(a,2));
  b->db().exec("CREATE TRIGGER fail_batch BEFORE INSERT ON memory_fact_archive WHEN NEW.fact_id='"+z.id+"' BEGIN SELECT RAISE(ABORT,'injected batch'); END");
  denied([&]{s.lifecycle_batch(request("archive",J::array({item(a,3),item(z)})),true);});
  check(scalar(*b,"SELECT COUNT(*) FROM memory_fact_archive")==0 && revision(s,a)==3 && revision(s,z)==1,"first write rolled back on second failure");
  b->db().exec("DROP TRIGGER fail_batch");
  check(s.lifecycle_batch(request("archive",J::array({item(a,3),item(z)})),true)["counts"]["change"]==2,"explicit corrected retry applies whole batch");
 });
 scenario("mid-restore SQL failure preserves the complete archive",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"a"),z=seed(*b,"z","I prefer second.");
  s.lifecycle_batch(request("archive",J::array({item(a),item(z)})),true);
  b->db().exec("CREATE TRIGGER fail_restore BEFORE DELETE ON memory_fact_archive WHEN OLD.fact_id='"+z.id+"' BEGIN SELECT RAISE(ABORT,'injected restore'); END");
  denied([&]{s.lifecycle_batch(request("restore",J::array({item(a,2),item(z,2)})),true);});
  check(archived(s,a) && archived(s,z) && revision(s,a)==2 && revision(s,z)==2,"restore rollback retains all metadata and revisions");
 });
 scenario("restore cannot revive unavailable or retired selections",[]{
  for(const char* mutation:{"UPDATE memory_items SET quote='forged'","UPDATE pages SET deleted_at='gone'","DELETE FROM memory_items","UPDATE memory_events SET expires_at=1","UPDATE memory_facts SET status='retracted'","UPDATE memory_facts SET status='superseded'"}){
    auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"a");s.lifecycle_batch(request("archive",J::array({item(a)})),true);
    b->db().exec(mutation);denied([&]{s.lifecycle_batch(request("restore",J::array({item(a,2)})),true);});
    check(scalar(*b,"SELECT COUNT(*) FROM memory_facts WHERE revision>2")==0,"unavailable or retired state never restored");
  }
 });
 scenario("preview is not a lease and apply rechecks revisions",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"a"),z=seed(*b,"z","I prefer second.");auto p=request("archive",J::array({item(a),item(z)}));
  auto preview=s.lifecycle_batch(p);check(preview["counts"]["change"]==2,"initial plan matches");
  seed(*b,"new-support",z.quote);check(revision(s,z)==2,"intervening evidence advances selected revision");
  denied([&]{s.lifecycle_batch(p,true);},"fact_revision_conflict");
  check(!s.lifecycle()["archive_initialized"].get<bool>() && revision(s,a)==1,"stale plan cannot partly apply");
  p["items"][1]=item(z,2);check(s.lifecycle_batch(p,true)["counts"]["change"]==2,"fresh selection explicitly accepted");
 });
 scenario("batches preserve counterclaims Hook filtering and forget",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"a","I prefer terminal."),z=seed(*b,"z","I prefer graphical.");
  s.contradict({{"fact_id",a.id},{"other_id",z.id}});
  s.lifecycle_batch(request("archive",J::array({item(z,2)})),true);
  auto r=s.recall("terminal");check(r["items"].size()==1 && r["items"][0]["facts"].size()==2,"batch archived counterclaim still present");
  check(s.recall("graphical")["items"].empty(),"archived matching anchor excluded");
  s.lifecycle_batch(request("archive",J::array({item(a,2)})),true);
  auto h=integration::detail::compose_fact_context(*b,"alpha","SessionStart","",8192,8);
  check(h.dump().find("terminal")==std::string::npos && h.dump().find("graphical")==std::string::npos,"all archived no ordinary-memory bypass in fact Hook");
  seed(*b,"again",a.quote);check(archived(s,a) && revision(s,a)==4,"promotion keeps policy and current revision");
  memory::forget(*b,"alpha",z.event);check(scalar(*b,"SELECT COUNT(*) FROM memory_fact_archive")==1,"last-support forget cascades archived metadata");
  denied([&]{s.lifecycle_batch(request("restore",J::array({item(a,4),item(z,3)})),true);},"fact_not_found");
  check(archived(s,a) && revision(s,a)==4,"forgotten final selection blocks valid first restore");
 });
 scenario("preview preserves caller transaction and apply rejects nesting",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"a");
  b->db().exec("BEGIN; INSERT INTO config(key,value) VALUES('batch.caller','alive')");
  s.lifecycle_batch(request("archive",J::array({item(a)})));
  check(sqlite3_get_autocommit(b->db().handle())==0,"preview leaves caller transaction open");
  denied([&]{s.lifecycle_batch(request("archive",J::array({item(a)})),true);},"fact_transaction_active");
  check(sqlite3_get_autocommit(b->db().handle())==0 && scalar(*b,"SELECT COUNT(*) FROM config WHERE key='batch.caller'")==1,"failed nested apply never rolls back owner");
  b->db().exec("ROLLBACK");check(revision(s,a)==1,"caller rollback leaves fact unchanged");
 });
 scenario("aggregate evidence work limit rejects whole batch",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");J entries=J::array();
  for(int n=0;n<8;++n){Seed first;std::string quote="I prefer bounded batch "+std::to_string(n)+".";
    for(int k=0;k<5;++k){auto x=seed(*b,std::to_string(n)+"-"+std::to_string(k),quote,"alpha",0,true);if(k==0)first=x;}
    entries.push_back(item(first,5));
  }
  denied([&]{s.lifecycle_batch(request("archive",entries),true);},"fact_read_work_limit");
  check(scalar(*b,"SELECT COUNT(*) FROM memory_facts WHERE revision<>5")==0,"work limit changes no revision");
  check(scalar(*b,"SELECT COUNT(*) FROM sqlite_master WHERE name='memory_fact_archive'")==0,"work-limited batch no preparation");
 });
}
void disk(){
 scenario("disk preview backup and competing connection batches",[]{
  auto path=tempdir();
  {Brain base;base.open_at(util::path_to_utf8(path/"brain.db"));base.ensure_source("alpha");base.save_config_value("memory.writeback","all");
   auto a=seed(base,"a"),z=seed(base,"z","I prefer second.");memory::FactStore s(base,"alpha");
   auto backups=[&]{int count=0;for(const auto& e:std::filesystem::directory_iterator(path))if(e.path().filename().string().find(".pre-lifecycle-v1-")!=std::string::npos)++count;return count;};
   auto p=request("archive",J::array({item(a),item(z)}));s.lifecycle_batch(p);check(backups()==0,"preview never makes lifecycle backup");
   s.lifecycle_batch(p,true);check(backups()==1,"first apply prepares backed-up lifecycle module");
   s.lifecycle_batch(request("restore",J::array({item(a,2),item(z,2)})),true);
   Brain one,two;one.open_at(util::path_to_utf8(path/"brain.db"));two.open_at(util::path_to_utf8(path/"brain.db"));
   one.db().exec("PRAGMA busy_timeout=123");two.db().exec("PRAGMA busy_timeout=456");
   for(int round=0;round<2;++round){
    const int before=3+round;auto q=request(round==0?"archive":"restore",J::array({item(a,before),item(z,before)}));
    std::barrier start(3);std::string errors[2];J results[2];
    auto attempt=[&](Brain& b,int i){start.arrive_and_wait();try{results[i]=memory::FactStore(b,"alpha").lifecycle_batch(q,true);}catch(const std::exception& e){errors[i]=e.what();}};
    std::thread t1(attempt,std::ref(one),0),t2(attempt,std::ref(two),1);start.arrive_and_wait();t1.join();t2.join();
    check(int(errors[0].empty())+int(errors[1].empty())==1,"exactly one concurrent batch wins");
    check(errors[0]=="fact_revision_conflict" || errors[1]=="fact_revision_conflict","loser detects stale revision");
    check(revision(s,a)==before+1 && revision(s,z)==before+1,"winner updates both exactly once");
   }
   check(scalar(one,"PRAGMA busy_timeout")==123 && scalar(two,"PRAGMA busy_timeout")==456,"per-connection timeouts restored");
  }
  std::filesystem::remove_all(path);
 });
 scenario("preview uses one snapshot across concurrent policy change",[]{
  auto path=tempdir();
  {Brain a,b;a.open_at(util::path_to_utf8(path/"brain.db"));a.ensure_source("alpha");a.save_config_value("memory.writeback","all");
   auto x=seed(a,"x"),y=seed(a,"y","I prefer second.");b.open_at(util::path_to_utf8(path/"brain.db"));
   struct Hook{Brain* writer;Seed selected;bool called=false;bool committed=false;};Hook hook{&b,y};
   sqlite3_trace_v2(a.db().handle(),SQLITE_TRACE_STMT,[](unsigned,void* context,void*,void* text)->int{
    auto& h=*static_cast<Hook*>(context);const std::string sql=text?static_cast<const char*>(text):"";
    if(!h.called && sql.find("SELECT subject,predicate,object")!=std::string::npos){h.called=true;try{memory::FactStore(*h.writer,"alpha").archive(item(h.selected));h.committed=true;}catch(...){}}
    return 0;
   },&hook);
   memory::FactStore s(a,"alpha");auto p=request("archive",J::array({item(x),item(y)}));auto preview=s.lifecycle_batch(p);
   sqlite3_trace_v2(a.db().handle(),0,nullptr,nullptr);
   check(hook.called && hook.committed,"second connection really committed during read");
   check(preview["items"][0]["revision_before"]==1 && preview["items"][1]["revision_before"]==1 && preview["counts"]["change"]==2,"single snapshot retains whole old plan");
   denied([&]{s.lifecycle_batch(p,true);},"fact_revision_conflict");
   check(revision(s,x)==1 && revision(s,y)==2 && !archived(s,x) && archived(s,y),"next apply sees commit and changes nothing else");
  }
  std::filesystem::remove_all(path);
 });
}
}
void test_n47g(){checks=0;scenarios=J::array();core();safety();disk();std::cout<<"N47G lifecycle batch: "<<scenarios.size()<<" scenarios, "<<checks<<" checks passed\n";}
#ifdef QBRAIN_BATCH_STANDALONE
int main(int argc,char** argv){try{test_n47g();if(argc==3 && std::string(argv[1])=="--report"){
 std::ofstream f(argv[2],std::ios::binary);if(!f)throw std::runtime_error("report open failed");f<<J({{"result","PASS"},{"scenarios",scenarios},{"scenario_count",scenarios.size()},{"checks",checks}}).dump(2)<<'\n';if(!f)throw std::runtime_error("report write failed");
 }else if(argc!=1)throw std::runtime_error("invalid arguments");return 0;}catch(const std::exception& e){std::cerr<<"[FAIL] N47G: "<<e.what()<<'\n';return 1;}}
#endif
