#include "qbrain/integration/mcp_probe.hpp"
#include <iostream>
#include <functional>
#ifndef _WIN32
#include <sys/stat.h>
#endif
using namespace qbrain::integration::probe;
namespace {
int count=0;
void check(bool ok,const std::string& name){if(!ok)throw std::runtime_error(name);++count;}
void rejected(const std::function<void()>& fn,const char* code){try{fn();}catch(const Error& e){check(std::string(e.what())==code,std::string("error code ")+code);return;}throw std::runtime_error(std::string("accepted ")+code);}
Json valid_init(){return {{"protocolVersion",protocol},{"capabilities",{{"tools",Json::object()}}},{"serverInfo",{{"name","qbrain"},{"version","test"}}}};}
Json valid_catalog(){Json tools=Json::array();for(const auto* n:tool_names){Json p=Json::object();
  if(std::string(n)=="memory_read")p["view"]={{"enum",Json::array({"usage_batch","usage_receipts"})}};
  if(std::string(n)=="memory_write")p["action"]={{"enum",Json::array({"fact_usage_batch"})}};
  tools.push_back({{"name",n},{"inputSchema",{{"type","object"},{"properties",p}}}});}
  return {{"tools",tools}};}
}
int main(int argc,char** argv){try{
  if(argc!=2)throw std::runtime_error("fixture executable argument required");auto peer=fs::absolute(fs::u8path(argv[1]));
  auto init=valid_init();initialize_result(init);check(true,"valid initialization");
  for(auto value:{Json(),Json(false),Json(1),Json(""),Json::array()}){
    auto j=init;j["protocolVersion"]=value;rejected([&]{initialize_result(j);},"protocol_version_mismatch");
    j=init;j["capabilities"]=value;rejected([&]{initialize_result(j);},"tools_capability_missing");
    j=init;j["serverInfo"]=value;rejected([&]{initialize_result(j);},"server_identity_mismatch");
  }
  auto catalog=valid_catalog();const auto hash=catalog_result(catalog);check(hash.size()==64,"valid catalog");
  auto reversed=catalog;std::reverse(reversed["tools"].begin(),reversed["tools"].end());check(catalog_result(reversed)==hash,"catalog order normalization");
  for(auto field:{"properties","type"}){auto j=catalog;j["tools"][0]["inputSchema"].erase(field);rejected([&]{catalog_result(j);},"catalog_schema");}
  for(auto value:{Json(),Json(true),Json(7),Json::array(),Json("x")}){auto j=catalog;j["tools"][0]["inputSchema"]=value;rejected([&]{catalog_result(j);},"catalog_tool_shape");}
  for(const std::string raw:std::vector<std::string>{"{\"x\":1,\"x\":2}","{\"x\":NaN}","{\"x\":\"\\ud800\"}","[",std::string(1,char(0xff))})
    rejected([&]{decode(raw);},"invalid_protocol_json");
  check(decode(std::string(frame_cap-2,' ')+"{}")==Json::object(),"exact parser frame bound");
  rejected([&]{decode(std::string(frame_cap-1,' ')+"{}");},"invalid_protocol_json");
  std::string nested="0";for(int i=0;i<40;++i)nested="["+nested+"]";rejected([&]{decode(nested);},"invalid_protocol_json");
  const auto temp=fs::absolute(fs::temp_directory_path());
  Workspace w;w.create(temp);auto work=w.path();check(fs::exists(work),"new workspace exists");
#ifndef _WIN32
  struct stat st{};check(lstat(work.c_str(),&st)==0&&(st.st_mode&0777)==0700,"private workspace mode");
#endif
  const auto vars=environment(work);for(auto key:{"HOME","LOCALAPPDATA","APPDATA","USERPROFILE"})check(vars.at(key)==qbrain::util::path_to_utf8(work),"isolated home values");
  check(vars.at("QBRAIN_MCP_ALLOW_WRITE")=="0"&&!vars.count("OPENAI_API_KEY")&&!vars.count("QBRAIN_BRAIN"),"no user key or brain override");
  auto run_peer=[&]{Process child;child.start(peer,work,{"serve","--brain","probe","--tool-profile","memory"},vars,3000);
    child.send("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\"}\n");unsigned frames=0;
    initialize_result(response(child,1,frames));check(frames==1,"one actually received frame");
    child.send("{\"jsonrpc\":\"2.0\",\"method\":\"notifications/initialized\"}\n");
    child.send("{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/list\"}\n");catalog_result(response(child,2,frames));
    child.send("{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"ping\"}\n");check(response(child,3,frames).empty(),"actual ping");child.shutdown();
    check(child.exit_code()==0&&child.cleanup()&&child.cleanup(),"clean direct process and idempotent cleanup");};
  run_peer();
#ifdef _WIN32
  DWORD before=0,after=0;check(GetProcessHandleCount(GetCurrentProcess(),&before)!=0,"observe handles before");
#else
  auto fds=[](){return std::distance(fs::directory_iterator("/proc/self/fd"),fs::directory_iterator());};auto before=fds();
#endif
  for(int i=0;i<8;++i)run_peer();
#ifdef _WIN32
  check(GetProcessHandleCount(GetCurrentProcess(),&after)!=0&&before==after,"repeated probes release handles");
#else
  check(fds()==before,"repeated probes release descriptors");
  struct sigaction prior{},ignore{};ignore.sa_handler=SIG_IGN;sigemptyset(&ignore.sa_mask);
  check(sigaction(SIGCHLD,&ignore,&prior)==0,"set test reaping policy");
  Process denied;bool correct=false;try{denied.start(peer,work,{},vars,1000);}catch(const Error& e){correct=std::string(e.what())=="unsupported_reaping_policy";}
  sigaction(SIGCHLD,&prior,nullptr);check(correct&&!denied.started(),"refuse auto-reaping without starting or signalling");
  struct sigaction oldpipe{},newpipe{};sigaction(SIGPIPE,nullptr,&oldpipe);{PipeSignal mask;}
  sigaction(SIGPIPE,nullptr,&newpipe);check(oldpipe.sa_handler==newpipe.sa_handler,"SIGPIPE handler unchanged");
#endif
  // Unknown replacement must not become cleanup authority over another directory.
  auto moved=work;moved+="-moved";fs::rename(work,moved);fs::create_directory(work);
  std::ofstream(work/"unrelated.txt")<<"KEEP";
  check(!w.cleanup()&&fs::exists(work/"unrelated.txt"),"foreign workspace identity retained");
  fs::remove_all(work);fs::rename(moved,work);check(w.cleanup()&&!fs::exists(work),"restored original workspace can be cleaned");
  check(w.cleanup(),"workspace cleanup idempotent");
#ifdef _WIN32
  // Native delete-sharing failure is not permission to force another handle.
  Workspace transient;transient.create(temp);const auto transient_path=transient.path();
  fs::remove(transient_path/"tmp"); // Empty directory: isolate sharing from not-empty errors.
  Handle held(CreateFileW(transient_path.c_str(),FILE_LIST_DIRECTORY|FILE_READ_ATTRIBUTES,FILE_SHARE_READ|FILE_SHARE_WRITE,
    nullptr,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS,nullptr));
  check(held.value!=INVALID_HANDLE_VALUE,"hold owned directory without delete sharing");
  const bool refused=RemoveDirectoryW(transient_path.c_str())==FALSE;const DWORD sharing=GetLastError();
  check(refused&&sharing==ERROR_SHARING_VIOLATION,"OS confirms delete-sharing refusal");
  const HANDLE raw_handle=held.value;
  std::jthread release([raw_handle]{std::this_thread::sleep_for(std::chrono::milliseconds(60));CloseHandle(raw_handle);});
  held.value=nullptr;
  const bool released=transient.cleanup(Clock::now()+std::chrono::milliseconds(cleanup_ms));
  release.join();
  check(released&&!fs::exists(transient_path),"bounded cleanup succeeds after directory handle release");
  Workspace persistent;persistent.create(temp);
  held.reset(CreateFileW(persistent.path().c_str(),FILE_LIST_DIRECTORY|FILE_READ_ATTRIBUTES,FILE_SHARE_READ|FILE_SHARE_WRITE,
    nullptr,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS,nullptr));
  check(held.value!=INVALID_HANDLE_VALUE,"hold second directory through cleanup deadline");
  const bool cleaned=persistent.cleanup(Clock::now()+std::chrono::milliseconds(30));
  check(!cleaned&&fs::exists(persistent.path())&&persistent.cleanup_error()==ERROR_SHARING_VIOLATION,
    "persistent sharing failure preserves owned workspace and numeric reason");
  held.reset();check(persistent.cleanup(),"explicit cleanup after release succeeds without forcing access");
#endif

  // Standalone timeout counter test is independent of the process suite.
  Workspace silent;silent.create(temp);auto copy=silent.path()/(std::string("peer-stall-init")+
#ifdef _WIN32
    ".exe"
#else
    ""
#endif
  );fs::copy_file(peer,copy);fs::permissions(copy,fs::perms::owner_all);
  auto p=preview(copy,1000);auto r=run(copy,1000,p["approval_sha256"]);
  check(r["result"]=="FAILED"&&r["code"]=="protocol_timeout"&&r["stdout_bytes"]==0&&r["messages_received"]==0,"silent peer reports zero observed messages");
  check(silent.cleanup(),"silent fixture cleaned");
  std::cout<<Json{{"schema","qbrain-n48d-direct-v1"},{"passed",count},{"failed",0},{"real_client_verified",false}}.dump()<<'\n';return 0;
}catch(const std::exception& e){std::cerr<<"direct test failed after "<<count<<": "<<e.what()<<'\n';return 1;}}
