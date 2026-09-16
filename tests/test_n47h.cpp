#include "qbrain/memory/fact_store.hpp"
#include "qbrain/util/hash.hpp"
#include "qbrain/util/paths.hpp"
#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <set>
#include <vector>

namespace {
using namespace qbrain;using J=nlohmann::json;
int checks=0;J scenarios=J::array();
void check(bool ok,const char* text){if(!ok)throw std::runtime_error(text);++checks;}
template<class F>void scenario(const char* name,F f){int before=checks;f();scenarios.push_back({{"name",name},{"status","PASS"},{"assertions",checks-before}});}
template<class F>void denied(F f,const std::string& code=""){
 try{f();}catch(const std::exception& e){check(code.empty() || code==e.what(),"stable expected rejection");return;}
 throw std::runtime_error("expected candidate rejection");
}
int64_t now(){return std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count();}
int64_t scalar(Brain& b,const std::string& sql){auto s=b.db().prepare(sql);check(s.step(),"scalar exists");return s.column_int(0);}
std::unique_ptr<Brain> fresh(){auto b=std::make_unique<Brain>();b->open_at(":memory:");b->ensure_source("alpha");b->ensure_source("beta");b->save_config_value("memory.writeback","all");return b;}
struct Seed{std::string id,event,item,quote;};
Seed seed(Brain& b,const std::string& tag,const std::string& source="alpha",bool large=false,const std::string& quote=""){
 const std::string text=quote.empty()?"我偏好保留完整原话，不自动修改设置。"+tag:quote;
 J messages=J::array({{{"role","user"},{"content",text}}});
 if(large)for(int i=0;i<4;++i)messages.push_back({{"role","assistant"},{"content",std::string(62000,'x')}});
 const std::string event=memory::capture(b,source,{{"session_id","candidate-fixture"},{"fragment_id",tag},{"messages",messages}},true)["event_id"];
 memory::extract(b,source,event);auto p=memory::FactStore(b,source).promote_event(event);
 check(p["items"].size()==1,"real local promotion seed");return {p["items"][0]["fact_id"],event,p["items"][0]["item_id"],text};
}
void timestamp(Brain& b,const Seed& f,int64_t time){auto s=b.db().prepare("UPDATE memory_items SET created_at=? WHERE item_id=?");s.bind_int(1,time);s.bind_text(2,f.item);s.step_done();}
J selection(const Seed& f,int rev=1){return {{"fact_id",f.id},{"expected_revision",rev}};}
std::vector<std::string> ids(const J& r){std::vector<std::string> out;for(const auto& f:r["items"])out.push_back(f["fact_id"]);return out;}
void core(){
 scenario("empty discovery is read only without initializing optional modules",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto count=scalar(*b,"SELECT COUNT(*) FROM sqlite_master");
  for(const auto* operation:{"archive","restore"}){auto r=s.lifecycle_candidates(operation);check(r["initialized"]==false && r["items"].empty() && r["batch_payload"].is_null(),"empty optional brain");check(r["next_after_id"].is_null() && r["has_more"]==false,"empty scan ends");}
  check(scalar(*b,"SELECT COUNT(*) FROM sqlite_master")==count,"empty reads no schema");
 });
 scenario("stale discovery returns metadata and explicit batch input only",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto old=seed(*b,"old"),recent=seed(*b,"new");timestamp(*b,old,now()-200*86400);
  auto r=s.lifecycle_candidates("archive");check(ids(r)==std::vector<std::string>{old.id},"only stale live unarchived selection");
  check(r["items"][0]["age"]["age_state"]=="stale" && r["items"][0]["expected_revision"]==1,"age and exact current revision");
  check(r.dump().find(old.quote)==std::string::npos && !r["items"][0].contains("object") && !r["items"][0].contains("evidence"),"no quote or evidence copy in metadata");
  check(r["batch_payload"]==J({{"operation","archive"},{"items",J::array({selection(old)})}}),"payload compatible with existing batch");
  check(s.lifecycle_batch(r["batch_payload"])["applied"]==false,"discovery payload preview is not apply");
  check(s.lifecycle_batch(r["batch_payload"],true)["counts"]["change"]==1,"explicit apply archives selected fact");
  check(s.lifecycle_candidates("archive")["items"].empty(),"archived no longer archive candidate");
  check(s.read(recent.id)["items"][0]["revision"]==1,"unselected fact unchanged");
 });
 scenario("restore selects live archived facts independently of advisory age",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"a"),z=seed(*b,"z");s.archive(selection(a));
  auto r=s.lifecycle_candidates("restore");check(ids(r)==std::vector<std::string>{a.id} && r["items"][0]["age"]["age_state"]=="fresh","fresh archived restore candidate");
  check(r["batch_payload"]["items"][0]["expected_revision"]==2,"restore current revision");
  timestamp(*b,a,0);check(s.lifecycle_candidates("restore")["items"][0]["age"]["age_state"]=="unknown","restore not falsely time-gated");
  s.lifecycle_batch(r["batch_payload"],true);check(s.lifecycle_candidates("restore")["items"].empty(),"restored policy disappears");
 });
 scenario("strict operation cursor predicate and budget validation",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");
  for(auto op:{"","auto","ARCHIVE","archive;DROP"})denied([&]{s.lifecycle_candidates(op);},"fact_batch_invalid_operation");
  for(auto cur:{std::string("x"),std::string(64,'A'),std::string(65,'a'),std::string("a\0x",3)})denied([&]{s.lifecycle_candidates("archive","",180,cur);},"fact_invalid_id");
  for(auto pred:{"Bad","abc space","中文"})denied([&]{s.lifecycle_candidates("archive",pred);},"fact_invalid_predicate");
  for(int days:{0,-1,36501})denied([&]{s.lifecycle_candidates("archive","",days);},"fact_invalid_stale_days");
  for(int limit:{0,-1,33})denied([&]{s.lifecycle_candidates("archive","",180,"",limit);},"invalid_read_budget");
  for(int budget:{0,511,32769})denied([&]{s.lifecycle_candidates("archive","",180,"",1,budget);},"invalid_read_budget");
 });
 scenario("latest valid support and strict stored times control stale eligibility",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"time");timestamp(*b,a,now()-400*86400);
  check(s.lifecycle_candidates("archive")["items"].size()==1,"old valid time is stale");
  auto recent=seed(*b,"again","alpha",false,a.quote);check(recent.id==a.id,"identical quote promoted into same fact");
  check(s.lifecycle_candidates("archive")["items"].empty(),"newest valid support prevents stale suggestion");
  for(const auto* value:{"0","-1","'123not-a-time'","123.75","X'313233'"}){
   b->db().exec(std::string("UPDATE memory_items SET created_at=")+value);
   check(s.lifecycle_candidates("archive")["items"].empty(),"unknown time cannot cause stale selection");
  }
  timestamp(*b,a,now()+86400);timestamp(*b,recent,now()-500*86400);
  check(s.lifecycle_candidates("archive")["items"].empty(),"future support blocks stale classification");
  timestamp(*b,a,now()-181*86400);timestamp(*b,recent,now()-181*86400);
  auto r=s.lifecycle_candidates("archive");auto age=s.lifecycle(a.id)["items"][0]["lifecycle"];age.erase("archived");check(r["items"].size()==1 && r["items"][0]["age"]["age_state"]==age["age_state"] && r["items"][0]["age"]["latest_valid_support_created_at"]==age["latest_valid_support_created_at"],"same strict age contract as N47F");
 });
}
void filtering(){
 scenario("invalid expired deleted and retired evidence is never suggested",[]{
  for(const auto* mutation:{"UPDATE memory_items SET quote='forged'","UPDATE memory_events SET expires_at=1","UPDATE pages SET deleted_at='gone'","DELETE FROM memory_items","UPDATE memory_facts SET status='retracted'","UPDATE memory_facts SET status='superseded'"}){
   auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"invalid");timestamp(*b,a,now()-200*86400);s.archive(selection(a));b->db().exec(mutation);
   check(s.lifecycle_candidates("archive")["items"].empty() && s.lifecycle_candidates("restore")["items"].empty(),"invalid evidence absent from both policies");
  }
 });
 scenario("source predicate and arbitrary seek keys never grant cross source access",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha"),other(*b,"beta");auto a=seed(*b,"scope"),z=seed(*b,"foreign","beta");timestamp(*b,a,now()-200*86400);timestamp(*b,z,now()-200*86400);
  check(ids(s.lifecycle_candidates("archive","memory.preference"))==std::vector<std::string>{a.id},"exact predicate and source");
  check(s.lifecycle_candidates("archive","memory.decision")["items"].empty(),"different predicate excluded");
  check(ids(other.lifecycle_candidates("archive"))==std::vector<std::string>{z.id},"separate source only");
  auto r=s.lifecycle_candidates("archive","",180,z.id);const auto found=ids(r);check(std::find(found.begin(),found.end(),z.id)==found.end(),"seek key does not expose foreign fact");
 });
 scenario("damaged oversize quotes and unusable revisions are filtered before load",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"oversize");timestamp(*b,a,now()-200*86400);
  b->db().exec("UPDATE memory_facts SET object=printf('%.*c',100000,'x')");
  int loaded=0;sqlite3_trace_v2(b->db().handle(),SQLITE_TRACE_STMT,[](unsigned,void* p,void*,void* q)->int{if(q && std::string(static_cast<char*>(q)).find("SELECT subject,predicate,object")!=std::string::npos)++*static_cast<int*>(p);return 0;},&loaded);
  check(s.lifecycle_candidates("archive")["items"].empty() && loaded==0,"oversize rejected before object load");sqlite3_trace_v2(b->db().handle(),0,nullptr,nullptr);
  auto update=b->db().prepare("UPDATE memory_facts SET object=?,revision=2147483647");update.bind_text(1,a.quote);update.step_done();
  check(s.lifecycle_candidates("archive")["items"].empty(),"no unwriteable terminal revision selected");
 });
 scenario("corrupt archive metadata fails closed without writing",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"metadata");s.archive(selection(a));b->db().exec("UPDATE memory_fact_archive SET archived_at='bad-time'");
  int before=sqlite3_total_changes(b->db().handle());denied([&]{s.lifecycle_candidates("restore");},"fact_lifecycle_invalid_metadata");
  check(sqlite3_total_changes(b->db().handle())==before,"metadata failure remains read only");
 });
}
void pagination(){
 scenario("scan limit yields an empty continuation without losing older eligible rows",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");std::vector<Seed> all;for(int i=0;i<105;++i)all.push_back(seed(*b,"scan-"+std::to_string(i)));
  std::sort(all.begin(),all.end(),[](const auto& a,const auto& b){return a.id<b.id;});timestamp(*b,all.back(),now()-200*86400);
  auto first=s.lifecycle_candidates("archive");check(first["items"].empty() && first["stop_reason"]=="scan_limit" && first["scanned"]==100,"empty bounded first page");
  check(first["has_more"]==true && first["next_after_id"]==all[99].id && first["progressed"]==true,"cursor follows fully examined candidates");
  auto second=s.lifecycle_candidates("archive","",180,first["next_after_id"]);
  check(ids(second)==std::vector<std::string>{all.back().id} && second["scanned"]==5 && second["next_after_id"].is_null(),"later old fact reachable");
 });
 scenario("static keyset pagination matches an independent complete sorted inventory",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");std::vector<std::string> expected;
  for(int n=0;n<69;++n){auto f=seed(*b,"pages-"+std::to_string(n));timestamp(*b,f,now()-200*86400);expected.push_back(f.id);}std::sort(expected.begin(),expected.end());
  for(int limit:{1,7,32}){std::vector<std::string> found;std::string after;int pages=0;
   for(;;){check(++pages<=70,"paging makes bounded progress");auto r=s.lifecycle_candidates("archive","",180,after,limit,32768);auto page=ids(r);found.insert(found.end(),page.begin(),page.end());
    check(page.size()<=static_cast<size_t>(limit) && r.dump().size()<=32768,"page respects size");
    check(r["batch_payload"].dump().size()<=8192 && r["batch_payload"]["items"].size()==page.size(),"payload contains exactly selections");
    if(!r["has_more"].get<bool>())break;check(r["next_after_id"].get<std::string>()>after,"seek cursor strictly increases");after=r["next_after_id"];
   }check(found==expected,"no duplicates or skipped IDs on unchanged brain");
  }
 });
 scenario("deleting the previous seek key does not break continuation",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");std::vector<Seed> all;for(int n=0;n<4;++n){all.push_back(seed(*b,"delete-"+std::to_string(n)));timestamp(*b,all.back(),now()-200*86400);}
  std::sort(all.begin(),all.end(),[](auto& a,auto& b){return a.id<b.id;});auto first=s.lifecycle_candidates("archive","",180,"",2);
  memory::forget(*b,"alpha",all[1].event);auto second=s.lifecycle_candidates("archive","",180,first["next_after_id"],2);
  check(ids(second)==std::vector<std::string>{all[2].id,all[3].id},"continuation requires no surviving cursor row");
 });
 scenario("output interruption does not consume the unreturned candidate",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"budget");timestamp(*b,a,now()-200*86400);
  auto r=s.lifecycle_candidates("archive","",180,"",10,768);
  check(r["items"].empty() && r["stop_reason"]=="output_budget" && r["has_more"]==true,"small budget emits no partial item");
  check(r["next_after_id"]=="" && r["scanned"]==0 && r["progressed"]==false && r["batch_payload"].is_null(),"unchanged cursor explicitly indicates retry or stop");
  check(r.dump().size()<=768 && ids(s.lifecycle_candidates("archive","",180,r["next_after_id"],10,8192))==std::vector<std::string>{a.id},"larger budget retains first candidate");
 });
 scenario("evidence work interruption resumes from the unfinished row",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");std::vector<Seed> all;
  for(int n=0;n<37;++n)all.push_back(seed(*b,"large-"+std::to_string(n),"alpha",true));
  std::sort(all.begin(),all.end(),[](auto& a,auto& b){return a.id<b.id;});timestamp(*b,all.back(),now()-200*86400);
  auto r=s.lifecycle_candidates("archive");check(r["items"].empty() && r["stop_reason"]=="evidence_budget" && r["has_more"]==true,"fresh excluded rows still consume evidence budget");
  check(r["scanned"].get<int>()>0 && r["scanned"].get<int>()<37 && r["next_after_id"]==all[r["scanned"].get<int>()-1].id,"cursor only covers completely evaluated rows");
  check(ids(s.lifecycle_candidates("archive","",180,r["next_after_id"]))==std::vector<std::string>{all.back().id},"next call has fresh work and finds remaining stale fact");
 });
}
void consistency(){
 scenario("candidate reads preserve caller transactions and deny all writes",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"readonly");timestamp(*b,a,now()-200*86400);auto count=scalar(*b,"SELECT COUNT(*) FROM sqlite_master");int changes=sqlite3_total_changes(b->db().handle());
  b->db().exec("BEGIN");sqlite3_set_authorizer(b->db().handle(),[](void*,int op,const char*,const char*,const char*,const char*){return op==SQLITE_INSERT || op==SQLITE_DELETE || op==SQLITE_UPDATE || op==SQLITE_CREATE_TABLE || op==SQLITE_TRANSACTION?SQLITE_DENY:SQLITE_OK;},nullptr);
  auto r=s.lifecycle_candidates("archive");check(r["items"].size()==1 && sqlite3_get_autocommit(b->db().handle())==0,"no hidden transaction control");
  sqlite3_set_authorizer(b->db().handle(),nullptr,nullptr);b->db().exec("ROLLBACK");
  check(sqlite3_total_changes(b->db().handle())==changes && scalar(*b,"SELECT COUNT(*) FROM sqlite_master")==count,"no data counters backups or migrations");
 });
 scenario("selection is not a lease and new support invalidates its revision",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"lease");timestamp(*b,a,now()-200*86400);auto r=s.lifecycle_candidates("archive");
  auto newer=seed(*b,"lease-new","alpha",false,a.quote);check(newer.id==a.id,"new support changes same fact");
  denied([&]{s.lifecycle_batch(r["batch_payload"],true);},"fact_revision_conflict");
  check(s.lifecycle_candidates("archive")["items"].empty() && !s.lifecycle(a.id)["items"][0]["lifecycle"]["archived"].get<bool>(),"no stale apply or automatic archival");
 });
 scenario("one call uses a coherent snapshot when a second WAL connection forgets",[]{
  auto dir=std::filesystem::temp_directory_path()/("qbrain-candidates-"+util::sha256_hex(std::to_string(std::chrono::steady_clock::now().time_since_epoch().count())).substr(0,20));std::filesystem::create_directory(dir);
  {Brain a,b;a.open_at(util::path_to_utf8(dir/"brain.db"));a.ensure_source("alpha");a.save_config_value("memory.writeback","all");auto f=seed(a,"snapshot");timestamp(a,f,now()-200*86400);b.open_at(util::path_to_utf8(dir/"brain.db"));
   struct Hook{Brain* writer;std::string event;bool called=false,committed=false;};Hook h{&b,f.event};
   sqlite3_trace_v2(a.db().handle(),SQLITE_TRACE_STMT,[](unsigned,void* context,void*,void* text)->int{auto& h=*static_cast<Hook*>(context);if(!h.called && text && std::string(static_cast<char*>(text)).find("SELECT subject,predicate,object")!=std::string::npos){h.called=true;try{memory::forget(*h.writer,"alpha",h.event);h.committed=true;}catch(...){}}return 0;},&h);
   memory::FactStore s(a,"alpha");auto first=s.lifecycle_candidates("archive");sqlite3_trace_v2(a.db().handle(),0,nullptr,nullptr);
   check(h.called && h.committed && ids(first)==std::vector<std::string>{f.id},"second writer committed during a complete prior snapshot");
   check(s.lifecycle_candidates("archive")["items"].empty(),"next call observes committed forget");denied([&]{s.lifecycle_batch(first["batch_payload"],true);},"fact_not_found");
  }std::filesystem::remove_all(dir);
 });
}
}
void test_n47h(){checks=0;scenarios=J::array();core();filtering();pagination();consistency();std::cout<<"N47H lifecycle candidates: "<<scenarios.size()<<" scenarios, "<<checks<<" checks passed\n";}
#ifdef QBRAIN_CANDIDATE_STANDALONE
int main(int argc,char** argv){try{test_n47h();if(argc==3 && std::string(argv[1])=="--report"){std::ofstream out(argv[2],std::ios::binary);if(!out)throw std::runtime_error("report open");out<<J({{"result","PASS"},{"scenario_count",scenarios.size()},{"checks",checks},{"scenarios",scenarios}}).dump(2)<<'\n';if(!out)throw std::runtime_error("report write");}else if(argc!=1)throw std::runtime_error("invalid args");return 0;}catch(const std::exception& e){std::cerr<<"[FAIL] N47H: "<<e.what()<<'\n';return 1;}}
#endif
