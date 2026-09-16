#include "qbrain/integration/detail/hook_trace.hpp"
#include <fstream>
#include <iostream>
#include <set>
#include <limits>
namespace {
using J=nlohmann::json;
using namespace qbrain::integration::detail;
int checks=0;J scenarios;
void check(bool ok,const char* name){if(!ok)throw std::runtime_error(name);++checks;}
template<class F> void rejects(F call){try{call();}catch(const std::runtime_error& e){check(std::string(e.what())=="invalid_hook_trace_metadata","fixed non-sensitive diagnostic");return;}throw std::runtime_error("invalid trace accepted");}
template<class F> void scenario(const char* name,F call){const int before=checks;call();scenarios.push_back({{"name",name},{"status","PASS"},{"assertions",checks-before}});}
J base(){return {{"phase","complete"},{"recall_count",2},{"output_bytes",512}};}
J record(const J& in){return hook_trace_record(in,"claude","UserPromptSubmit",std::string(64,'a'),1700000000000LL,true);}
void run(){
 scenario("closed host event map has exactly ten safe filenames",[]{
  std::set<std::string> names;
  for(auto host:{"claude","codex"})for(auto event:{"SessionStart","UserPromptSubmit","Stop","PreCompact","SessionEnd"}){
   auto name=hook_trace_filename(host,event);names.insert(name);
   check(name.find('/')==std::string::npos&&name.find('\\')==std::string::npos,"fixed basename only");
   check(name=="trace-"+std::string(host)+"-"+event+".json","host and event fixed slot");
  }
  check(names.size()==10,"no unbounded filename inventory");
  for(const auto& value:std::vector<std::string>{"","Claude","../claude","claude/Stop",std::string("claude\0x",8)})rejects([&]{hook_trace_filename(value,"Stop");});
  for(auto value:{"", "UserPromptSubmit/../foo","../../secret","stop","Stop:stream","arbitrary"})rejects([&]{hook_trace_filename("claude",value);});
 });
 scenario("metadata projection excludes untrusted content and override claims",[]{
  auto in=base();for(auto field:{"prompt","quote","response","session_id","source_id","brain_id","exception","path","additionalContext"})in[field]="SENSITIVE-FIXTURE";
  in["provider_calls"]=99;in["host_consumption_confirmed"]=true;in["format_version"]=999;in["host"]="attacker";
  auto out=record(in);check(out.dump().find("SENSITIVE-FIXTURE")==std::string::npos,"no original values copied");
  check(out.size()==11,"only required fields plus selected counters");
  check(out["host_consumption_confirmed"]==false&&out["provider_calls"]==0,"consumption never inferred");
  check(out["format_version"]==2&&out["host"]=="claude"&&out["event"]=="UserPromptSubmit","checked identities authoritative");
  check(out["session_key"]==std::string(64,'a')&&out["completed_at_unix_ms"]==1700000000000LL,"correlation without raw identity");
 });
 scenario("failure phases cannot masquerade as completed processing",[]{
  for(auto phase:{"open","recall","capture","extract","promote","state"}){
   J in={{"phase",phase}};auto out=hook_trace_record(in,"codex","Stop",std::string(64,'b'),1,false);
   check(out["status"]=="failed"&&out["phase"]==phase,"accepted failure retains phase");
   rejects([&]{record(in);});
  }
  rejects([&]{hook_trace_record(base(),"claude","Stop",std::string(64,'b'),1,false);});
  for(J value:J::array({nullptr,42,true,"exception with quote"})){auto in=base();in["phase"]=value;rejects([&]{record(in);});}
  auto in=base();in.erase("phase");rejects([&]{record(in);});
 });
 scenario("counter and boolean types are bounded and exact",[]{
  for(auto name:{"recall_count","fact_group_count","output_bytes"})for(J value:J::array({nullptr,true,-1,1.5,"2",8193,std::numeric_limits<std::uint64_t>::max()})){
   auto in=base();in[name]=value;rejects([&]{record(in);});
  }
  auto in=base();in["recall_count"]=16;in["fact_group_count"]=16;in["output_bytes"]=8192;check(record(in)["output_bytes"]==8192,"upper exact bound");
  for(auto name:{"context_truncated","fact_recall_enabled","fact_promotion_enabled"}){
   for(J value:J::array({"true",0,nullptr})){auto bad=base();bad[name]=value;rejects([&]{record(bad);});}
   for(bool value:{false,true}){in[name]=value;check(record(in)[name]==value,"only genuine boolean accepted");}
  }
 });
 scenario("only finite capture extraction and promotion states persist",[]{
  for(auto name:{"capture_status","extraction_status"})for(auto value:{"archived","extracting","extracted","no_matches","failed","skipped"}){auto in=base();in[name]=value;check(record(in)[name]==value,"known state persists");}
  for(auto value:{"not_run","completed","failed"}){auto in=base();in["fact_promotion_status"]=value;check(record(in)["fact_promotion_status"]==value,"known promotion state");}
  for(auto name:{"capture_status","extraction_status","fact_promotion_status"})for(J value:J::array({1,nullptr,"failed: raw query and key"})){auto in=base();in[name]=value;rejects([&]{record(in);});}
 });
 scenario("promotion totals match and only enumerated counters are copied",[]{
  auto in=base();in["fact_promotion_status"]="completed";
  in["fact_promotion_counts"]={{"total",5},{"created",1},{"attached",1},{"duplicate",1},{"skipped_retired",1},{"skipped_limit",1},{"quote","PRIVATE"}};
  auto out=record(in);check(out["fact_promotion_counts"].size()==6&&out.dump().find("PRIVATE")==std::string::npos,"counter allowlist");
  for(auto key:{"total","created","attached","duplicate","skipped_retired","skipped_limit"})for(J value:J::array({true,-1,33,1.25,"1"})){
   auto bad=in;bad["fact_promotion_counts"][key]=value;rejects([&]{record(bad);});
  }
  auto bad=in;bad["fact_promotion_counts"]["total"]=4;rejects([&]{record(bad);});
  bad=in;bad["fact_promotion_counts"].erase("created");rejects([&]{record(bad);});
  bad=in;bad["fact_promotion_status"]="failed";rejects([&]{record(bad);});
 });
 scenario("pseudonymous session key and clock values are validated",[]{
  for(const auto& value:std::vector<std::string>{"session",std::string(63,'a'),std::string(64,'A'),std::string(64,'g'),std::string(65,'a')})rejects([&]{hook_trace_record(base(),"claude","Stop",value,1,true);});
  for(auto at:{std::int64_t(-1),std::int64_t(0),std::int64_t(253402300800000LL)})rejects([&]{hook_trace_record(base(),"claude","Stop",std::string(64,'a'),at,true);});
  check(hook_trace_record(base(),"claude","Stop",std::string(64,'a'),253402300799999LL,true)["completed_at_unix_ms"]==253402300799999LL,"exact time ceiling");
 });
 scenario("maximum complete projection is deterministic and within byte cap",[]{
  auto in=base();in["fact_group_count"]=16;in["recall_count"]=16;in["output_bytes"]=8192;
  for(auto key:{"context_truncated","fact_recall_enabled","fact_promotion_enabled"})in[key]=true;
  in["capture_status"]="no_matches";in["extraction_status"]="no_matches";in["fact_promotion_status"]="completed";
  in["fact_promotion_counts"]={{"total",32},{"created",0},{"attached",0},{"duplicate",0},{"skipped_retired",16},{"skipped_limit",16}};
  in["unused"]=std::string(50000,'x');auto a=record(in),b=record(in);
  check(a==b&&a.dump()==b.dump(),"deterministic metadata");check(a.dump().size()<max_hook_trace_bytes,"complete maximum projected fields fit cap");
  check(a["status"]=="processed"&&a["fact_promotion_counts"]["total"]==32,"no truncated partial counters");
  rejects([&]{record(J::array());});
 });
}
}
void test_n47j(){checks=0;scenarios=J::array();run();std::cout<<"N47J Hook checkpoints: "<<scenarios.size()<<" scenarios, "<<checks<<" checks passed\n";}
#ifdef QBRAIN_HOOK_TRACE_STANDALONE
int main(int argc,char**argv){try{test_n47j();if(argc==3&&std::string(argv[1])=="--report"){
 std::ofstream f(argv[2],std::ios::binary);f<<J({{"result","PASS"},{"scenarios",scenarios},{"scenario_count",scenarios.size()},{"checks",checks}}).dump(2)<<'\n';if(!f)throw std::runtime_error("cannot write report");
 }else if(argc!=1)throw std::runtime_error("invalid arguments");return 0;}catch(const std::exception&e){std::cerr<<"[FAIL] "<<e.what()<<'\n';return 1;}}
#endif
