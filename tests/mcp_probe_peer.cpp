// Deterministic synthetic peer: never shipped as a product, never calls providers.
#include <nlohmann/json.hpp>
#include <filesystem>
#include <iostream>
#include <fstream>
#include <string>
#include <thread>
#include <chrono>
#include <cstdlib>
#ifdef _WIN32
#include <windows.h>
#include <io.h>
#include <fcntl.h>
#else
#include <unistd.h>
#endif
using J=nlohmann::json;namespace fs=std::filesystem;
void line(const J& v){std::cout<<v.dump()<<'\n'<<std::flush;}
void wait_forever(){std::this_thread::sleep_for(std::chrono::seconds(60));}
std::string mode;
void emit(const J& v){
  if(mode=="partial"){for(char c:v.dump()+"\n"){std::cout.put(c);std::cout.flush();std::this_thread::sleep_for(std::chrono::microseconds(80));}}
  else line(v);
}
J tools(){
  J a=J::array();for(const auto* name:{"context_read","context_write","get_page","memory_read","memory_write","search"}){
    J props=J::object();if(std::string(name)=="memory_read")props["view"]={{"enum",J::array({"usage_receipts","usage_batch"})}};
    if(std::string(name)=="memory_write")props["action"]={{"enum",J::array({"fact_usage_batch"})}};
    a.push_back({{"name",name},{"inputSchema",{{"type","object"},{"properties",props}}}});
  }return a;
}
int main(int argc,char** argv){
#ifdef _WIN32
  _setmode(_fileno(stdin),_O_BINARY);_setmode(_fileno(stdout),_O_BINARY);
#endif
  fs::path own_exe=fs::path(argv[0]);
#ifdef _WIN32
  wchar_t filename[32768]{};DWORD n=GetModuleFileNameW(nullptr,filename,32768);if(!n||n>=32768)return 67;
  own_exe=std::wstring(filename,n);
#endif
  const auto stem=own_exe.stem().string();const auto at=stem.find("peer-");mode=at==std::string::npos?"good":stem.substr(at+5);
  if(argc>1&&std::string(argv[1])=="hold"){wait_forever();return 0;}
  if(mode=="early")return 17;
  if(mode=="no-read"){wait_forever();return 0;}
  std::string raw;bool initialized=false;
  while(std::getline(std::cin,raw)){
    J request=J::parse(raw);const auto method=request.value("method","");
    if(method=="notifications/initialized"){initialized=true;continue;}
    if(method=="initialize"){
      if(mode=="stall-init"){wait_forever();return 0;}
      if(mode=="stderr-flood"){std::cerr<<std::string(100000,'x')<<std::flush;wait_forever();return 0;}
      if(mode=="stdout-flood"){for(int i=0;i<8;++i)line({{"jsonrpc","2.0"},{"method","notifications/message"},{"params",{{"data",std::string(60000,'x')}}}});wait_forever();return 0;}
      if(mode=="frame-flood"){std::cout<<std::string(70000,'x')<<std::flush;wait_forever();return 0;}
      if(mode=="invalid-utf8"){std::cout<<"{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"x\":\""<<char(0xff)<<"\"}}\n"<<std::flush;return 0;}
      if(mode=="partial-eof"){std::cout<<"{\"jsonrpc\":\"2.0\""<<std::flush;return 0;}
      if(mode=="empty-frame"){std::cout<<'\n'<<std::flush;return 0;}
      if(mode=="text-error"){std::cout<<"PRIVATE_PROVIDER_SECRET_TEST\n"<<std::flush;return 0;}
      if(mode=="duplicate-json"){std::cout<<"{\"jsonrpc\":\"2.0\",\"id\":1,\"id\":1,\"result\":{}}\n"<<std::flush;return 0;}
      if(mode=="server-request"){line({{"jsonrpc","2.0"},{"id",17},{"method","sampling/createMessage"},{"params",J::object()}});return 0;}
      if(mode=="notification-flood")for(int i=0;i<20;++i)line({{"jsonrpc","2.0"},{"method","notifications/message"},{"params",J::object()}});
      if(mode=="logs")for(int i=0;i<3;++i)line({{"jsonrpc","2.0"},{"method","notifications/message"},{"params",{{"data","PRIVATE_PROVIDER_SECRET_TEST"}}}});
      J result={{"protocolVersion","2024-11-05"},{"capabilities",{{"tools",J::object()}}},{"serverInfo",{{"name","qbrain"},{"version","synthetic"}}}};
      if(mode=="wrong-version")result["protocolVersion"]="2026-07-28";
      if(mode=="wrong-server")result["serverInfo"]["name"]="PRIVATE_PROVIDER_SECRET_TEST";
      if(mode=="missing-capability")result["capabilities"]=J::object();
      if(mode=="env"){
        for(auto key:{"OPENAI_API_KEY","ANTHROPIC_API_KEY","QBRAIN_API_KEY","QBRAIN_BRAIN","LD_PRELOAD","PYTHONPATH","N48D_PRIVATE_SENTINEL"})if(std::getenv(key))return 61;
        auto get=[](const char* key){auto p=std::getenv(key);return p?std::string(p):std::string();};
        if(get("QBRAIN_MCP_ALLOW_WRITE")!="0"||get("HOME")!=get("USERPROFILE")||get("HOME")!=get("APPDATA")||
            fs::u8path(get("HOME"))!=fs::current_path())return 62;
        if(argc!=6||std::string(argv[1])!="serve"||std::string(argv[2])!="--brain"||std::string(argv[3])!="probe"||
          std::string(argv[4])!="--tool-profile"||std::string(argv[5])!="memory")return 63;
      }
      J reply={{"jsonrpc","2.0"},{"id",1},{"result",result}};
      if(mode=="wrong-id")reply["id"]=19;
      if(mode=="string-id")reply["id"]="1";
      if(mode=="bool-id")reply["id"]=true;
      if(mode=="server-error"){reply.erase("result");reply["error"]={{"code",-1},{"message","PRIVATE_PROVIDER_SECRET_TEST"}};}
      emit(reply);
    }else if(method=="tools/list"){
      if(!initialized)return 64;
      if(mode=="stall-catalog"){wait_forever();return 0;}
      J result={{"tools",tools()}};
      if(mode=="missing-tool")result["tools"].erase(0);
      if(mode=="duplicate-tool")result["tools"][1]=result["tools"][0];
      if(mode=="wrong-schema")result["tools"][0]["inputSchema"]["type"]="string";
      if(mode=="missing-routes")result["tools"][3]["inputSchema"]["properties"]=J::object();
      if(mode=="paginated")result["nextCursor"]="extra";
      if(mode=="extra-tool")result["tools"].push_back({{"name","exec"}});
      emit({{"jsonrpc","2.0"},{"id",2},{"result",result}});
    }else if(method=="ping"){
      if(mode=="stall-ping"){wait_forever();return 0;}
      emit({{"jsonrpc","2.0"},{"id",3},{"result",mode=="wrong-ping"?J{{"invalid",true}}:J::object()}});
      if(mode=="trailing"){line({{"jsonrpc","2.0"},{"id",4},{"result",J::object()}});}
      if(mode=="trailing-partial"){std::cout<<"unfinished"<<std::flush;}
      if(mode=="shutdown-stall"){std::string rest;while(std::getline(std::cin,rest)){}wait_forever();return 0;}
      if(mode=="held-pipe"){
#ifdef _WIN32
        std::wstring command=L"\""+own_exe.wstring()+L"\" hold";STARTUPINFOW s{};s.cb=sizeof(s);s.dwFlags=STARTF_USESTDHANDLES;
        s.hStdInput=GetStdHandle(STD_INPUT_HANDLE);s.hStdOutput=GetStdHandle(STD_OUTPUT_HANDLE);s.hStdError=GetStdHandle(STD_ERROR_HANDLE);
        PROCESS_INFORMATION p{};if(!CreateProcessW(own_exe.c_str(),command.data(),nullptr,nullptr,TRUE,CREATE_NO_WINDOW,nullptr,nullptr,&s,&p))return 66;
        CloseHandle(p.hThread);CloseHandle(p.hProcess);
#else
        if(fork()==0){wait_forever();_exit(0);}
#endif
        return 0;
      }
    }else return 65; // Tool invocation is forbidden: a test failure, not simulated.
  }
  return mode=="nonzero"?7:0;
}
