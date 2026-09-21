#pragma once
// N48D: explicit local runtime qualification, not host registration verification.
#include "qbrain/integration/detail/probe_process.hpp"
#include "qbrain/util/hash.hpp"
#include "qbrain/util/strict_json.hpp"
#include <charconv>
#include <cwctype>
#include <fstream>
#include <iostream>
#include <random>
#include <set>

namespace qbrain::integration::probe {
using Json=nlohmann::json;
inline constexpr const char* protocol="2024-11-05";
inline const std::array<const char*,6> tool_names={"context_read","context_write","get_page","memory_read","memory_write","search"};
inline fs::path absolute_regular_path(const fs::path& p,bool directory=false){
  require(p.is_absolute(),"absolute_path_required");for(const auto& part:p)require(part!="..","parent_path_refused");
  auto full=p.lexically_normal();require(util::path_to_utf8(full).size()<=2048,"path_bound");
#ifdef _WIN32
  require(full.root_name().wstring().size()==2,"local_drive_required");
  for(const auto& part:full.relative_path()){auto name=part.wstring();require(name.find(L':')==std::wstring::npos&&
    (name.empty()||(name.back()!=L'.'&&name.back()!=L' ')),"path_alias_refused");}
#endif
  for(auto at=full;!at.empty();){auto st=fs::symlink_status(at);require(!fs::is_symlink(st),"path_link_refused");
#ifdef _WIN32
    auto attrs=GetFileAttributesW(at.c_str());require(attrs!=INVALID_FILE_ATTRIBUTES&&!(attrs&FILE_ATTRIBUTE_REPARSE_POINT),"path_link_refused");
#endif
    auto parent=at.parent_path();if(parent==at)break;at=parent;}
  require(directory?fs::is_directory(full):fs::is_regular_file(full),"path_type_refused");
  if(!directory)require(fs::hard_link_count(full)==1,"binary_links_refused");return full;
}
inline Json executable_stamp(const fs::path& binary){
  auto full=absolute_regular_path(binary);const auto bytes=fs::file_size(full);
  require(bytes>0&&bytes<=32*1024*1024,"binary_bound");
#ifdef _WIN32
  auto ext=full.extension().wstring();std::transform(ext.begin(),ext.end(),ext.begin(),::towlower);
  require(ext==L".exe","binary_ineligible");
#else
  require(::faccessat(AT_FDCWD,full.c_str(),X_OK,AT_EACCESS)==0,"binary_ineligible");
#endif
  std::ifstream file(full,std::ios::binary);require(file.good(),"binary_unreadable");std::string data;char buf[8192];
  while(file.read(buf,sizeof(buf))||file.gcount()){data.append(buf,std::size_t(file.gcount()));require(data.size()<=32*1024*1024,"binary_bound");}
  require(file.eof()&&!file.bad()&&data.size()==bytes,"binary_changed_during_read");
  return {{"path",util::path_to_utf8(full)},{"sha256",util::sha256_hex(data)},{"bytes",bytes},
    {"permissions",static_cast<unsigned>(fs::status(full).permissions())}};
}
inline Json preview(const fs::path& binary,int timeout){
  require(timeout>=1000&&timeout<=30000,"timeout_range");
  auto root=absolute_regular_path(fs::absolute(fs::temp_directory_path()),true);
  Json plan={{"schema","qbrain-mcp-check-plan-v1"},{"binary",executable_stamp(binary)},
    {"temporary_parent",util::path_to_utf8(root)},{"timeout_ms",timeout},{"protocol",protocol},
    {"arguments",Json::array({"serve","--brain","probe","--tool-profile","memory"})},
    {"environment_policy","private-home-minimal-env-write-disabled-v1"},
    {"cleanup_policy","owned-process-family-v1"},{"frame_bytes",frame_cap},{"stdout_bytes",stdout_cap},
    {"stderr_bytes",stderr_cap},{"message_limit",16},{"tools_called",0},
    {"will_open_real_brain",false},{"will_start_selected_executable",true},
    {"os_security_sandbox",false},{"opencode_started",false}};
  plan["approval_sha256"]=util::sha256_hex(plan.dump());return plan;
}
class Workspace {
  fs::path path_;bool owned_=false,created_=false,retained_=false;
#ifdef _WIN32
  DWORD volume_=0,index_hi_=0,index_lo_=0;
  bool same()const{
    HANDLE h=CreateFileW(path_.c_str(),FILE_READ_ATTRIBUTES,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,
      OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
    if(h==INVALID_HANDLE_VALUE)return false;BY_HANDLE_FILE_INFORMATION i{};bool ok=GetFileInformationByHandle(h,&i);CloseHandle(h);
    return ok&&(i.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY)&&!(i.dwFileAttributes&FILE_ATTRIBUTE_REPARSE_POINT)&&
      i.dwVolumeSerialNumber==volume_&&i.nFileIndexHigh==index_hi_&&i.nFileIndexLow==index_lo_;
  }
#else
  dev_t device_{};ino_t inode_{};
  bool same()const{struct stat i{};return ::lstat(path_.c_str(),&i)==0&&S_ISDIR(i.st_mode)&&i.st_dev==device_&&i.st_ino==inode_;}
#endif
 public:
  Workspace()=default;Workspace(const Workspace&)=delete;Workspace& operator=(const Workspace&)=delete;
  ~Workspace(){cleanup();}
  void create(const fs::path& root){
    require(!owned_,"workspace_already_created");std::random_device random;
    for(int attempt=0;attempt<8;++attempt){std::string nonce;for(int i=0;i<8;++i)nonce+=std::to_string(random())+":";
      path_=root/("qbrain-mcp-check-"+util::sha256_hex(nonce));
#ifdef _WIN32
      if(!CreateDirectoryW(path_.c_str(),nullptr)){require(GetLastError()==ERROR_ALREADY_EXISTS,"workspace_create_error");continue;}
      created_=true;
      HANDLE h=CreateFileW(path_.c_str(),FILE_READ_ATTRIBUTES,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,nullptr,
        OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
      require(h!=INVALID_HANDLE_VALUE,"workspace_identity_error");BY_HANDLE_FILE_INFORMATION i{};
      bool ok=GetFileInformationByHandle(h,&i);CloseHandle(h);require(ok,"workspace_identity_error");
      volume_=i.dwVolumeSerialNumber;index_hi_=i.nFileIndexHigh;index_lo_=i.nFileIndexLow;
#else
      if(::mkdir(path_.c_str(),0700)!=0){require(errno==EEXIST,"workspace_create_error");continue;}
      created_=true;
      struct stat i{};require(::lstat(path_.c_str(),&i)==0,"workspace_identity_error");device_=i.st_dev;inode_=i.st_ino;
#endif
      owned_=true;fs::create_directory(path_/"tmp");return;
    }throw Error("workspace_create_error");
  }
  const fs::path& path()const{return path_;}
  void retain()noexcept{retained_=true;} // Unsafe/incomplete process cleanup: do not remove its workspace.
  bool cleanup()noexcept{
    if(!created_)return true;if(!owned_||retained_)return false;
    try{if(!same())return false;fs::remove_all(path_);owned_=false;created_=false;return true;}catch(...){return false;}
  }
};
inline std::map<std::string,std::string> environment(const fs::path& home){
  std::map<std::string,std::string> env;
  for(auto k:{"HOME","USERPROFILE","LOCALAPPDATA","APPDATA"})env[k]=util::path_to_utf8(home);
  for(auto k:{"TEMP","TMP","TMPDIR"})env[k]=util::path_to_utf8(home/"tmp");
  env["QBRAIN_MCP_ALLOW_WRITE"]="0";
#ifdef _WIN32
  std::array<wchar_t,32768> system{};const auto n=GetWindowsDirectoryW(system.data(),UINT(system.size()));
  require(n>0&&n<system.size(),"system_environment_error");auto root=fs::path(std::wstring(system.data(),n));
  env["SystemRoot"]=util::path_to_utf8(root);env["WINDIR"]=env["SystemRoot"];
  env["PATH"]=util::path_to_utf8(root/L"System32");
#else
  env["LANG"]="C.UTF-8";env["PATH"]="/usr/bin:/bin";
#endif
  return env;
}
inline Json decode(const std::string& line){
  try{return util::parse_unique_json(line,frame_cap,32);}catch(...){throw Error("invalid_protocol_json");}
}
inline Json response(Process& child,int id,unsigned& messages){
  for(;;){require(messages<16,"message_limit");const auto raw=child.receive();++messages;Json j=decode(raw);
    require(j.is_object()&&j.value("jsonrpc",Json())=="2.0","invalid_protocol_envelope");
    if(j.contains("method")){
      require(!j.contains("id")&&!j.contains("result")&&!j.contains("error")&&j["method"]=="notifications/message"&&
        j.contains("params")&&j["params"].is_object(),"unsolicited_message");continue;
    }
    require(j.contains("id")&&j["id"].is_number_integer()&&j["id"]==id,"response_id_mismatch");
    require(!j.contains("error")&&j.contains("result")&&j["result"].is_object(),"server_response_error");
    return j["result"];
  }
}
inline void initialize_result(const Json& j){
  require(j.contains("protocolVersion")&&j["protocolVersion"]==protocol,"protocol_version_mismatch");
  require(j.contains("capabilities")&&j["capabilities"].is_object()&&j["capabilities"].contains("tools")&&
    j["capabilities"]["tools"].is_object(),"tools_capability_missing");
  require(j.contains("serverInfo")&&j["serverInfo"].is_object()&&j["serverInfo"].value("name",Json())=="qbrain"&&
    j["serverInfo"].contains("version")&&j["serverInfo"]["version"].is_string()&&
    !j["serverInfo"]["version"].get_ref<const std::string&>().empty()&&j["serverInfo"]["version"].get_ref<const std::string&>().size()<=128,"server_identity_mismatch");
}
inline std::string catalog_result(const Json& j){
  require(!j.contains("nextCursor")&&j.contains("tools")&&j["tools"].is_array()&&j["tools"].size()==tool_names.size(),"catalog_shape");
  std::map<std::string,Json> catalog;
  for(const auto& t:j["tools"]){
    require(t.is_object()&&t.contains("name")&&t["name"].is_string()&&t.contains("inputSchema")&&t["inputSchema"].is_object(),"catalog_tool_shape");
    auto name=t["name"].get<std::string>();require(std::find(tool_names.begin(),tool_names.end(),name)!=tool_names.end()&&
      catalog.emplace(name,t).second,"catalog_tool_identity");
    const auto& schema=t["inputSchema"];
    require(schema.value("type",Json())=="object"&&schema.contains("properties")&&schema["properties"].is_object(),"catalog_schema");
  }
  auto has=[&](const char* tool,const char* field,const char* value){const auto& properties=catalog.at(tool)["inputSchema"]["properties"];
    if(!properties.contains(field)||!properties[field].is_object()||!properties[field].contains("enum")||!properties[field]["enum"].is_array())return false;
    return std::find(properties[field]["enum"].begin(),properties[field]["enum"].end(),Json(value))!=properties[field]["enum"].end();};
  require(has("memory_read","view","usage_batch")&&has("memory_read","view","usage_receipts")&&
    has("memory_write","action","fact_usage_batch"),"catalog_required_routes_missing");
  return util::sha256_hex(Json(catalog).dump());
}
inline Json run(const fs::path& binary,int timeout,const std::string& approved){
  auto plan=preview(binary,timeout);
  require(approved==plan["approval_sha256"].get<std::string>(),"approval_mismatch");
  Workspace space;Process child;const auto begin=Clock::now();unsigned messages=0;
  Json report={{"schema","qbrain-mcp-check-result-v1"},{"result","FAILED"},{"code","not_started"},{"phase","preflight"},
    {"approval_sha256",approved},{"binary_sha256",plan["binary"]["sha256"]},{"process_started",false},
    {"initialize_verified",false},{"catalog_verified",false},{"ping_verified",false},{"clean_shutdown_verified",false},
    {"catalog_sha256",nullptr},{"tool_count",0},{"messages_received",0},{"stdout_bytes",0},{"stderr_bytes",0},
    {"exit_code",nullptr},{"process_cleanup_verified",false},{"workspace_cleanup_verified",false},
    {"elapsed_ms",0},{"tools_called",0},{"model_requests_sent",0},{"real_brain_supplied",false},{"opencode_started",false},
    {"host_consumption_verified",false},{"write_authorization_verified",false},{"os_security_sandbox",false}};
  try{
    report["phase"]="workspace";space.create(util::utf8_to_path(plan["temporary_parent"].get<std::string>()));
    // Recheck AFTER workspace preparation, just before launch. This is not atomic
    // executable attestation or protection from a hostile last-moment replacement.
    require(preview(binary,timeout)==plan,"approval_changed_before_start");
    report["phase"]="start";child.start(binary,space.path(),{"serve","--brain","probe","--tool-profile","memory"},environment(space.path()),timeout);
    auto send=[&](const Json& j){child.send(j.dump()+"\n");};
    report["phase"]="initialize";
    send({{"jsonrpc","2.0"},{"id",1},{"method","initialize"},{"params",{{"protocolVersion",protocol},{"capabilities",Json::object()},
      {"clientInfo",{{"name","qbrain-isolated-check"},{"version","1"}}}}}});
    initialize_result(response(child,1,messages));report["initialize_verified"]=true;
    send({{"jsonrpc","2.0"},{"method","notifications/initialized"}});
    report["phase"]="catalog";send({{"jsonrpc","2.0"},{"id",2},{"method","tools/list"},{"params",Json::object()}});
    report["catalog_sha256"]=catalog_result(response(child,2,messages));report["catalog_verified"]=true;report["tool_count"]=6;
    report["phase"]="ping";send({{"jsonrpc","2.0"},{"id",3},{"method","ping"},{"params",Json::object()}});
    require(response(child,3,messages).empty(),"invalid_ping_result");report["ping_verified"]=true;
    report["phase"]="shutdown";child.shutdown();report["clean_shutdown_verified"]=true;
    require(executable_stamp(binary)==plan["binary"],"binary_changed_during_run");
    report["phase"]="complete";report["code"]="verified";report["result"]="ISOLATED_MCP_VERIFIED";
  }catch(const Error& e){report["code"]=e.what();}
  catch(...){report["code"]="local_runtime_error";}
  report["process_started"]=child.started();if(child.exit_code())report["exit_code"]=*child.exit_code();
  report["messages_received"]=messages;report["stdout_bytes"]=child.stdout_bytes();report["stderr_bytes"]=child.stderr_bytes();
  const bool stopped=child.cleanup();report["process_cleanup_verified"]=stopped;
  if(!stopped)space.retain();
  const bool removed=stopped&&space.cleanup();report["workspace_cleanup_verified"]=removed;
  if(!stopped||!removed){report["result"]="FAILED";report["code"]="cleanup_incomplete";}
  report["elapsed_ms"]=std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now()-begin).count();
  require(report.dump().size()+1<=8192,"result_bound");return report;
}
inline int command(const std::vector<std::string>& args){
  try{
    require(!args.empty()&&(args[0]=="preview"||args[0]=="run"),"invalid_action");
    std::map<std::string,std::string> values;
    for(std::size_t i=1;i<args.size();i+=2){require((args[i]=="--binary"||args[i]=="--timeout-ms"||args[i]=="--approve-sha256")&&
      i+1<args.size()&&values.emplace(args[i],args[i+1]).second,"invalid_option");}
    require(values.count("--binary"),"binary_required");const bool execution=args[0]=="run";
    require(execution?values.count("--approve-sha256")==1:values.count("--approve-sha256")==0,"explicit_approval_required");
    int timeout=10000;if(values.count("--timeout-ms")){
      const auto& s=values["--timeout-ms"];auto result=std::from_chars(s.data(),s.data()+s.size(),timeout);
      require(result.ec==std::errc{}&&result.ptr==s.data()+s.size(),"timeout_integer");}
    const auto binary=util::utf8_to_path(values["--binary"]);
    Json result=execution?run(binary,timeout,values["--approve-sha256"]):preview(binary,timeout);
    std::cout<<result.dump()<<'\n';return execution&&result["result"]!="ISOLATED_MCP_VERIFIED"?1:0;
  }catch(const Error& e){std::cout<<Json{{"error",{{"code",e.what()}}}}.dump()<<'\n';return 2;}
  catch(...){std::cout<<"{\"error\":{\"code\":\"local_preflight_error\"}}\n";return 2;}
}
} // namespace qbrain::integration::probe
