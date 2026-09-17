#include "qbrain/integration/diagnostics.hpp"
#include "qbrain/util/paths.hpp"
#include <chrono>
#include <fstream>
#include <iostream>
#include <limits>
namespace {
using J=nlohmann::json;namespace fs=std::filesystem;
using qbrain::integration::detail::inspect_hook_checkpoint;
int checks;J scenarios;
void check(bool yes,const char* label){if(!yes)throw std::runtime_error(label);++checks;}
template<class F>void scenario(const char* name,F f){auto n=checks;f();scenarios.push_back({{"name",name},{"status","PASS"},{"assertions",checks-n}});}
J base(const std::string& host="claude",const std::string& event="SessionStart") {
 return qbrain::integration::detail::hook_trace_record({{"phase","complete"},{"recall_count",1}},host,event,std::string(64,'a'),1700000000000LL,true);
}
J inspect(const J& j){return inspect_hook_checkpoint(j.dump(),"claude","SessionStart");}
void invalid(const J& j){auto r=inspect(j);check(r["state"]=="invalid"&&!r.contains("record"),"invalid input has no record");}
struct Fixture {
 fs::path dir=fs::temp_directory_path()/fs::path("qbrain-n47k-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
 fs::path config=dir/"config.json";
 Fixture(){fs::create_directory(dir);write(config,"{\"version\":1,\"enabled\":true,\"host\":\"claude\",\"brain_id\":\"do-not-open\"}");}
 ~Fixture(){std::error_code ec;fs::remove_all(dir,ec);}
 static void write(const fs::path& path,const std::string& text){std::ofstream out(path,std::ios::binary);out<<text;if(!out)throw std::runtime_error("fixture write");}
 J read(const std::string& event={},const std::string& key={}){return qbrain::integration::inspect_hook_diagnostics(config,event,key);}
};
void run(){
 scenario("canonical records and exact session filtering",[]{
  for(const auto* h:{"claude","codex"})for(const auto* e:{"SessionStart","UserPromptSubmit","Stop","PreCompact","SessionEnd"}) {
   auto b=base(h,e);auto r=inspect_hook_checkpoint(b.dump(),h,e);
   check(r["state"]=="present" && r["record"]==b,"complete canonical record");
   r=inspect_hook_checkpoint(b.dump(),h,e,std::string(64,'b'));
   check(r["state"]=="session_mismatch"&&!r.contains("record"),"other session not emitted");
   check(inspect_hook_checkpoint(b.dump(),h,e,std::string(64,'a'))["state"]=="present","matching session retained");
  }
 });
 scenario("unknown and nested input fields cannot be echoed",[]{
  for(const auto* k:{"prompt","quote","answer","path","error","token"}){
   auto b=base();b[k]="NEVER_ECHO_SENTINEL";auto r=inspect(b);
   check(r["state"]=="invalid" && r.dump().find("NEVER_ECHO_SENTINEL")==std::string::npos,"unknown values suppressed");
  }
  auto b=base();b["fact_promotion_status"]="completed";b["fact_promotion_counts"]={{"created",1},{"attached",0},{"duplicate",0},{"skipped_retired",0},{"skipped_limit",0},{"total",1}};
  check(inspect(b)["state"]=="present","valid complete nested counts");
  b["fact_promotion_counts"]["private"]="NEVER_ECHO_SENTINEL";invalid(b);
 });
 scenario("required record values and numeric types remain exact",[]{
  for(const auto* k:{"format_version","completed_at_unix_ms","provider_calls"}) {
   for(const auto& value:J::array({true,nullptr,"2",2.0,-1,std::numeric_limits<std::uint64_t>::max()})) {auto b=base();b[k]=value;invalid(b);}
   auto b=base();b.erase(k);invalid(b);
  }
  for(const auto& value:J::array({true,0,"false",nullptr})) {auto b=base();b["host_consumption_confirmed"]=value;invalid(b);}
  for(const auto& pair:std::vector<std::pair<std::string,std::string>>{{"host","codex"},{"event","Stop"},{"status","unknown"},{"phase","capture"},{"session_key",std::string(64,'A')}}){auto b=base();b[pair.first]=pair.second;invalid(b);}
 });
 scenario("raw duplicate keys malformed UTF8 and depth are rejected",[]{
  auto raw=base().dump();raw.insert(1,"\"status\":\"processed\",");
  check(inspect_hook_checkpoint(raw,"claude","SessionStart")["state"]=="invalid","duplicate raw key rejected");
  raw=base().dump();raw.insert(1,"\"\\u0073tatus\":\"processed\",");
  check(inspect_hook_checkpoint(raw,"claude","SessionStart")["state"]=="invalid","decoded duplicate key rejected");
  for(const auto& x:std::vector<std::string>{"[]","null","{",std::string("{\0}",3),"{\"a\":\"\xff\"}",std::string(20,'[')+"0"+std::string(20,']')})
   check(inspect_hook_checkpoint(x,"claude","SessionStart")["state"]=="invalid","malformed raw input rejected");
 });
 scenario("record byte cap cannot truncate a valid prefix",[]{
  auto raw=base().dump();raw+=std::string(4096-raw.size(),' ');
  check(inspect_hook_checkpoint(raw,"claude","SessionStart")["state"]=="present","exact byte cap legal");raw+=' ';
  check(inspect_hook_checkpoint(raw,"claude","SessionStart")["state"]=="oversized","over cap not parsed as prefix");
 });
 scenario("forgotten replay and failed phases never become consumption",[]{
  for(bool done:{false,true}){
   auto r=qbrain::integration::detail::hook_trace_record({{"phase",done?"complete":"extract"},{"capture_status","forgotten"}},"claude","SessionStart",std::string(64,'a'),1,done);
   auto out=inspect(r);check(out["state"]=="present"&&out["record"]["capture_status"]=="forgotten","forgotten is preserved");
   check(out["record"]["host_consumption_confirmed"]==false,"no new consumption claim");
  }
  auto b=base();b["extraction_status"]="forgotten";invalid(b);
 });
 scenario("inspection of empty config directory is read only",[]{
  Fixture f;const auto before=fs::file_size(f.config);auto r=f.read();
  check(r["result"]=="INSPECTED"&&r["counts"]["missing"]==5,"no records is missing not PASS");
  check(r["slots"].size()==5&&r["host_consumption_confirmed"]==false,"fixed slots no consumer proof");
  check(std::distance(fs::directory_iterator(f.dir),fs::directory_iterator())==1&&fs::file_size(f.config)==before,"no lock state or database created");
  Fixture::write(f.config,"{\"version\":1,\"enabled\":false,\"host\":\"claude\"}");
  check(f.read()["config_enabled"]==false,"disabled config is inspected without enabling");
 });
 scenario("all five records retain fixed order and complete metadata",[]{
  Fixture f;for(const auto* e:{"SessionStart","UserPromptSubmit","Stop","PreCompact","SessionEnd"})Fixture::write(f.dir/qbrain::integration::detail::hook_trace_filename("claude",e),base("claude",e).dump());
  auto r=f.read();check(r["counts"]["present"]==5&&r["counts"]["selected"]==5,"complete five slots");
  check(r["slots"][0]["event"]=="SessionStart"&&r["slots"][4]["event"]=="SessionEnd","stable event order");
  check(r.dump().size()<=32768&&r["consistency"]=="independent_latest_files","bounded non-atomic observation");
  check(f.read("Stop")["slots"].size()==1,"exact event selection");
  check(f.read("Stop",std::string(64,'b'))["counts"]["session_mismatch"]==1,"filter protects wrong session");
 });
 scenario("bad files are independent and never returned as raw bytes",[]{
  Fixture f;Fixture::write(f.dir/"trace-claude-SessionStart.json",base().dump());
  Fixture::write(f.dir/"trace-claude-Stop.json","{\"secret\":\"NEVER_ECHO_SENTINEL\"}");
  Fixture::write(f.dir/"trace-claude-SessionEnd.json",std::string(4097,'x'));
  fs::create_directory(f.dir/"trace-claude-PreCompact.json");
  auto r=f.read();check(r["counts"]["present"]==1&&r["counts"]["invalid"]==1&&r["counts"]["oversized"]==1&&r["counts"]["unsafe_path"]==1&&r["counts"]["missing"]==1,"one invalid slot does not hide others");
  check(r.dump().find("NEVER_ECHO_SENTINEL")==std::string::npos&&r.dump().find(f.dir.string())==std::string::npos,"no private content or path");
  check(std::distance(fs::directory_iterator(f.dir),fs::directory_iterator())==5,"no read side effect");
 });
 scenario("direct API rejects ambiguous paths and invalid selection",[]{
  Fixture f;
  std::vector<fs::path> paths={fs::path("relative.json"),f.dir/".."/"config.json",f.dir/"config.json:stream"};
  auto nul=f.config.native();nul.push_back(0);nul+=fs::path("suffix").native();paths.emplace_back(nul);
  for(const auto& p:paths){bool rejected=false;try{qbrain::integration::inspect_hook_diagnostics(p);}catch(const std::exception& e){rejected=std::string(e.what())=="invalid_diagnostic_arguments";}check(rejected,"ambiguous direct path rejected");}
  for(const auto& pair:std::vector<std::pair<std::string,std::string>>{{"../Stop",""},{"",std::string(64,'A')}}){bool rejected=false;try{f.read(pair.first,pair.second);}catch(const std::exception& e){rejected=std::string(e.what())=="invalid_diagnostic_arguments";}check(rejected,"selection checked before reading config");}
 });
 scenario("config validation cannot select another host or follow database settings",[]{
  Fixture f;
  for(const auto* raw:{"[]","{\"version\":1.0,\"enabled\":true,\"host\":\"claude\"}","{\"version\":1,\"enabled\":1,\"host\":\"claude\"}","{\"version\":1,\"enabled\":true,\"host\":\"other\"}","{\"version\":1,\"version\":1,\"enabled\":true,\"host\":\"claude\"}"}) {
   Fixture::write(f.config,raw);bool failed=false;try{f.read();}catch(const std::exception& e){failed=std::string(e.what())=="diagnostic_config_invalid";}check(failed,"strict fixed config diagnostic");
  }
  Fixture::write(f.config,std::string(65537,' '));bool failed=false;try{f.read();}catch(const std::exception& e){failed=std::string(e.what())=="diagnostic_config_unavailable";}check(failed,"config over cap does not parse");
 });
}
}
void test_n47k(){checks=0;scenarios=J::array();run();std::cout<<"N47K diagnostic inspection: "<<scenarios.size()<<" scenarios, "<<checks<<" assertions passed\n";}
#ifdef QBRAIN_DIAGNOSTIC_STANDALONE
int main(int argc,char** argv){try{test_n47k();if(argc==3&&std::string(argv[1])=="--report"){std::ofstream f(argv[2],std::ios::binary);f<<J({{"result","PASS"},{"scenario_count",scenarios.size()},{"checks",checks},{"scenarios",scenarios}}).dump(2)<<'\n';if(!f)throw std::runtime_error("report write");}else if(argc!=1)throw std::runtime_error("arguments");return 0;}catch(const std::exception&e){std::cerr<<"[FAIL] "<<e.what()<<'\n';return 1;}}
#endif
