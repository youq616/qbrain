// Independently authored edge peer for the fixed N48D outcome review.
// Synthetic data only; no network or external program execution.
#include <nlohmann/json.hpp>
#include <filesystem>
#include <iostream>
#include <string>
#include <cstdlib>
#include <cerrno>
#include <fcntl.h>
using J=nlohmann::json;
namespace fs=std::filesystem;
static void emit(const J& value,std::size_t length=0){
 std::string data=value.dump();if(length){if(data.size()>length)std::exit(90);data.append(length-data.size(),' ');}
 std::cout<<data<<'\n'<<std::flush;
}
static J note(){return {{"jsonrpc","2.0"},{"method","notifications/message"},{"params",{{"data","SYNTHETIC_DO_NOT_COPY"}}}};}
static J catalog(){
 J list=J::array();
 for(const auto* name:{"memory_read","memory_write","context_read","context_write","get_page","search"}){
  J properties=J::object();
  if(std::string(name)=="memory_read")properties["view"]={{"type","string"},{"enum",J::array({"usage_batch","usage_receipts"})}};
  if(std::string(name)=="memory_write")properties["action"]={{"type","string"},{"enum",J::array({"fact_usage_batch"})}};
  list.push_back({{"name",name},{"inputSchema",{{"type","object"},{"properties",properties}}}});
 }
 return {{"tools",list}};
}
int main(int argc,char** argv){
 if(argc!=6 || std::string(argv[1])!="serve" || std::string(argv[3])!="probe")return 91;
 const auto mode=fs::path(argv[0]).stem().string().substr(5);
 const bool total=mode=="total-limit"||mode=="total-over";
 std::string raw;bool initialized=false;
 while(std::getline(std::cin,raw)){
  const J req=J::parse(raw);const auto method=req.value("method","");
  if(method=="notifications/initialized"){initialized=true;continue;}
  if(method=="initialize"){
   if(mode=="early-eof")return 0;
   if(mode=="partial-tail"){emit(note());std::cout<<"{\"jsonrpc\":\"2.0\""<<std::flush;return 0;}
   if(mode=="duplicate-escaped"){std::cout<<"{\"jsonrpc\":\"2.0\",\"id\":1,\"\\u0069d\":1,\"result\":{}}\n"<<std::flush;return 0;}
   if(mode=="depth-limit"){std::cout<<std::string(40,'[')<<"0"<<std::string(40,']')<<'\n'<<std::flush;return 0;}
   if(mode=="array"){emit(J::array());return 0;}
   if(mode=="unsupported-notice"){emit({{"jsonrpc","2.0"},{"method","notifications/tools/list_changed"}});return 0;}
   if(mode=="server-request"){emit({{"jsonrpc","2.0"},{"id",19},{"method","roots/list"}});return 0;}
   if(mode=="stderr-limit"||mode=="stderr-over")std::cerr<<std::string(mode=="stderr-limit"?65536:65537,'z')<<std::flush;
   if(mode=="fd-close"){
    if(fcntl(77,F_GETFD)!=-1||errno!=EBADF)return 92;
    for(const char* k:{"OPENAI_API_KEY","N48D_REVIEW_SENTINEL","QBRAIN_BRAIN"})if(std::getenv(k))return 93;
   }
   if(mode=="linked-child")fs::create_directory_symlink(fs::current_path().parent_path()/"outside",fs::current_path()/"linked");
   if(mode=="messages16"||mode=="messages17")for(int i=0;i<(mode=="messages16"?13:14);++i)emit(note());
   if(total)emit(note(),65536);
   J result={{"protocolVersion","2024-11-05"},{"serverInfo",{{"name","qbrain"},{"version","edge-fixture"}}},{"capabilities",{{"tools",J::object()}}}};
   if(mode=="missing-version")result.erase("protocolVersion");
   J reply={{"jsonrpc","2.0"},{"id",1},{"result",result}};
   if(mode=="float-id")reply["id"]=1.0;
   if(mode=="null-id")reply["id"]=nullptr;
   if(mode=="negative-id")reply["id"]=-1;
   if(mode=="null-result")reply["result"]=nullptr;
   const auto length=mode=="frame-over"?65537:(mode=="frame-limit"||total?65536:0);
   emit(reply,length);
  }else if(method=="tools/list"){
   if(!initialized)return 94;
   emit({{"jsonrpc","2.0"},{"id",2},{"result",catalog()}},total?65536:0);
  }else if(method=="ping"){
   emit({{"jsonrpc","2.0"},{"id",3},{"result",J::object()}},total?(mode=="total-over"?65533:65532):0);
   if(mode=="late-empty")std::cout<<'\n'<<std::flush;
  }else return 95;
 }
 return mode=="late-nonzero"?7:0;
}
