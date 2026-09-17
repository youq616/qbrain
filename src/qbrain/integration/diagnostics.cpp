#include "qbrain/integration/diagnostics.hpp"
#include "qbrain/util/paths.hpp"
#include "qbrain/util/utf8_display.hpp"
#include <array>
#include <cerrno>
#include <iostream>
#include <set>
#ifdef _WIN32
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif
namespace qbrain::integration {
namespace {
namespace fs=std::filesystem;
using J=nlohmann::json;
struct Read {std::string state;std::string bytes;};
constexpr std::array<const char*,5> events={"SessionStart","UserPromptSubmit","Stop","PreCompact","SessionEnd"};
void require(bool ok,const char* code){if(!ok)throw std::runtime_error(code);}
bool valid_path(const fs::path& p) {
  if(!p.is_absolute() || p.native().find(static_cast<fs::path::value_type>(0))!=fs::path::string_type::npos) return false;
#ifdef _WIN32
  const auto root=p.root_name().native();
  if(root.size()!=2 || root[1]!=L':' || !((root[0]>=L'A'&&root[0]<=L'Z')||(root[0]>=L'a'&&root[0]<=L'z')))return false;
#endif
  unsigned parts=0;
  for(const auto& c:p.relative_path()) {
    if(++parts>256 || c=="." || c==".." || c.native().find(static_cast<fs::path::value_type>(':'))!=fs::path::string_type::npos)return false;
  }
  return parts>0;
}
// Static parent checks plus a no-follow final handle. The owner must control
// the directory: this is not a concurrent hostile-directory or hard-link defense.
std::string path_state(const fs::path& p) {
  fs::path current=p.root_path();
  for(const auto& part:p.relative_path()) {
    current/=part;
#ifdef _WIN32
    const DWORD attributes=GetFileAttributesW(current.c_str());
    if(attributes==INVALID_FILE_ATTRIBUTES) {
      const auto e=GetLastError();return (e==ERROR_FILE_NOT_FOUND||e==ERROR_PATH_NOT_FOUND)?"missing":"unreadable";
    }
    if(attributes&FILE_ATTRIBUTE_REPARSE_POINT)return "unsafe_path";
    if(current!=p && !(attributes&FILE_ATTRIBUTE_DIRECTORY))return "unsafe_path";
    if(current==p && (attributes&FILE_ATTRIBUTE_DIRECTORY))return "unsafe_path";
#else
    struct stat s{};
    if(::lstat(current.c_str(),&s)!=0)return (errno==ENOENT||errno==ENOTDIR)?"missing":"unreadable";
    if(S_ISLNK(s.st_mode) || (current!=p&&!S_ISDIR(s.st_mode)) || (current==p&&!S_ISREG(s.st_mode)))return "unsafe_path";
#endif
  }
  return "";
}
Read read_regular(const fs::path& p,std::size_t cap) {
  auto state=path_state(p);if(!state.empty())return {state,{}};
  std::string out;out.resize(cap+1);std::size_t used=0;
#ifdef _WIN32
  struct Handle {HANDLE h=INVALID_HANDLE_VALUE;~Handle(){if(h!=INVALID_HANDLE_VALUE)CloseHandle(h);}} file;
  file.h=CreateFileW(p.c_str(),GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
      nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
  if(file.h==INVALID_HANDLE_VALUE) {
    const auto e=GetLastError();return {(e==ERROR_FILE_NOT_FOUND||e==ERROR_PATH_NOT_FOUND)?"missing":"unreadable",{}};
  }
  BY_HANDLE_FILE_INFORMATION info{};LARGE_INTEGER size{};
  if(GetFileType(file.h)!=FILE_TYPE_DISK || !GetFileInformationByHandle(file.h,&info) ||
      (info.dwFileAttributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT)))return {"unsafe_path",{}};
  if(!GetFileSizeEx(file.h,&size))return {"unreadable",{}};
  if(size.QuadPart<0 || static_cast<unsigned long long>(size.QuadPart)>cap)return {"oversized",{}};
  while(used<out.size()) {
    DWORD n=0;if(!ReadFile(file.h,out.data()+used,static_cast<DWORD>(out.size()-used),&n,nullptr))return {"unreadable",{}};
    if(n==0)break;used+=n;
  }
#else
  struct Handle {int h=-1;~Handle(){if(h>=0)::close(h);}} file;
  file.h=::open(p.c_str(),O_RDONLY|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC);
  if(file.h<0)return {errno==ENOENT?"missing":errno==ELOOP?"unsafe_path":"unreadable",{}};
  struct stat info{};
  if(::fstat(file.h,&info)!=0)return {"unreadable",{}};
  if(!S_ISREG(info.st_mode))return {"unsafe_path",{}};
  if(info.st_size<0 || static_cast<unsigned long long>(info.st_size)>cap)return {"oversized",{}};
  while(used<out.size()) {
    const auto n=::read(file.h,out.data()+used,out.size()-used);
    if(n<0){if(errno==EINTR)continue;return {"unreadable",{}};}
    if(n==0)break;used+=static_cast<std::size_t>(n);
  }
#endif
  if(used>cap)return {"oversized",{}};
  out.resize(used);return {"read",std::move(out)};
}
} // namespace

J inspect_hook_diagnostics(const fs::path& path,const std::string& event,const std::string& key) {
  require(valid_path(path),"invalid_diagnostic_arguments");
  require(event.empty() || detail::trace_choice(event,{"SessionStart","UserPromptSubmit","Stop","PreCompact","SessionEnd"}),"invalid_diagnostic_arguments");
  require(key.empty() || detail::trace_hex_key(key),"invalid_diagnostic_arguments");
  const auto input=read_regular(path,65536);
  require(input.state=="read","diagnostic_config_unavailable");
  J config;std::string host;bool enabled=false;
  try {
    config=util::parse_unique_json(input.bytes,65536,16);
    require(config.is_object() && config.contains("version") && config["version"].is_number_integer() && config["version"]==1 &&
        config.contains("host") && config["host"].is_string() && config.contains("enabled") && config["enabled"].is_boolean(),"diagnostic_config_invalid");
    host=config["host"].get<std::string>();enabled=config["enabled"].get<bool>();
    require(detail::trace_choice(host,{"claude","codex"}),"diagnostic_config_invalid");
  }catch(...){throw std::runtime_error("diagnostic_config_invalid");}
  J result={{"format_version",1},{"result","INSPECTED"},{"host",host},{"config_enabled",enabled},
      {"session_filter_applied",!key.empty()},{"consistency","independent_latest_files"},
      {"record_authenticity_verified",false},{"host_consumption_confirmed",false},{"slots",J::array()},
      {"counts",{{"selected",0},{"present",0},{"missing",0},{"invalid",0},{"unreadable",0},{"unsafe_path",0},{"oversized",0},{"session_mismatch",0}}}};
  for(const auto* name:events) {
    if(!event.empty() && event!=name)continue;
    const auto file=read_regular(path.parent_path()/detail::hook_trace_filename(host,name),detail::max_hook_trace_bytes);
    J slot=file.state=="read"?detail::inspect_hook_checkpoint(file.bytes,host,name,key):J{{"event",name},{"state",file.state}};
    const auto state=slot["state"].get<std::string>();
    result["counts"][state]=result["counts"][state].get<int>()+1;
    result["counts"]["selected"]=result["counts"]["selected"].get<int>()+1;
    result["slots"].push_back(std::move(slot));
  }
  require(result.dump().size()<=32768,"diagnostic_output_limit");
  return result;
}
int run_hook_diagnostics(const std::vector<std::string>& args) {
  try {
    require(!args.empty() && args.size()%2==0,"invalid_diagnostic_arguments");
    std::set<std::string> seen;std::string path,event,key;
    for(std::size_t i=0;i<args.size();i+=2) {
      const auto& option=args[i];const auto& value=args[i+1];
      require(seen.insert(option).second && !value.empty() && value.size()<=4096 &&
          value.find('\0')==std::string::npos && util::valid_utf8(value),"invalid_diagnostic_arguments");
      if(option=="--config")path=value;
      else if(option=="--event")event=value;
      else if(option=="--session-key")key=value;
      else throw std::runtime_error("invalid_diagnostic_arguments");
    }
    require(!path.empty(),"invalid_diagnostic_arguments");
    std::cout<<inspect_hook_diagnostics(util::utf8_to_path(path),event,key).dump()<<'\n';return 0;
  } catch(const std::exception& e) {
    std::string code=e.what();
    if(!detail::trace_choice(code,{"invalid_diagnostic_arguments","diagnostic_config_unavailable","diagnostic_config_invalid","diagnostic_output_limit"}))code="diagnostic_inspection_failed";
    std::cout<<J({{"result","ERROR"},{"error",{{"code",code}}}}).dump()<<'\n';return 2;
  } catch(...) {std::cout<<"{\"result\":\"ERROR\",\"error\":{\"code\":\"diagnostic_inspection_failed\"}}\n";return 2;}
}
} // namespace qbrain::integration
