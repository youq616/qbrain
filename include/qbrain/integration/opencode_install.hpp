#pragma once
// Recoverable two-file configuration transaction, not a cross-file atomic commit.
#include "qbrain/integration/opencode_config.hpp"
#include <filesystem>
#include <fstream>
#include <functional>
#include <cwctype>
#include <iostream>
#include <optional>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace qbrain::integration::opencode {
namespace fs=std::filesystem;
using Image=std::optional<std::string>;
inline constexpr std::size_t state_limit=262144, journal_limit=2097152;
inline std::string path_text(const fs::path& p) { return util::path_to_utf8(p); }
inline fs::path path(const std::string& s) {return util::utf8_to_path(s);}
inline std::string identity(const fs::path& p) {
#ifdef _WIN32
  const auto w=p.wstring();std::wstring lower(w.size(),L'\0');
  need(LCMapStringEx(LOCALE_NAME_INVARIANT,LCMAP_LOWERCASE,w.data(),static_cast<int>(w.size()),
       lower.data(),static_cast<int>(lower.size()),nullptr,nullptr,0)>0,"opencode_path_identity");
  return util::wide_to_utf8(lower);
#else
  return path_text(p);
#endif
}
inline fs::path safe_path(const fs::path& input) {
  need(!input.empty(),"opencode_path_required");
  for(const auto& part:input)need(part!="..","opencode_parent_path");
  const auto full=fs::absolute(input).lexically_normal();
  need(path_text(full).size()<=2048,"opencode_path_bound");
#ifdef _WIN32
  // Reject alternate streams and ambiguous Win32 normalization, including NT paths.
  need(full.has_root_name() && full.root_name().wstring().size()==2,"opencode_local_drive_required");
  for(const auto& part:full.relative_path()) {
    const auto s=part.wstring();need(s.empty()||(s.back()!=L' '&&s.back()!=L'.'),"opencode_path_alias");
    need(s.find(L':')==std::wstring::npos,"opencode_path_alias");
  }
#endif
  for(auto at=full;!at.empty();) {
    std::error_code ec;auto stat=fs::symlink_status(at,ec);
    need(!ec||ec==std::errc::no_such_file_or_directory,"opencode_path_unreadable");
    need(!fs::is_symlink(stat),"opencode_link_refused");
    if(fs::exists(stat)) {
      need(fs::is_directory(stat)||fs::is_regular_file(stat),"opencode_special_file");
#ifdef _WIN32
      auto attrs=GetFileAttributesW(at.c_str());
      need(attrs!=INVALID_FILE_ATTRIBUTES && !(attrs&FILE_ATTRIBUTE_REPARSE_POINT),"opencode_link_refused");
      if(fs::is_directory(stat)) {
        HANDLE h=CreateFileW(at.c_str(),FILE_READ_ATTRIBUTES,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
          nullptr,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
        need(h!=INVALID_HANDLE_VALUE,"opencode_path_unverifiable");
        struct Tags {DWORD attributes;DWORD tag;} tags{};DWORD flags=0;
        const bool valid=GetFileInformationByHandleEx(h,static_cast<FILE_INFO_BY_HANDLE_CLASS>(9),&tags,sizeof(tags)) &&
          (tags.attributes&FILE_ATTRIBUTE_DIRECTORY) && !(tags.attributes&FILE_ATTRIBUTE_REPARSE_POINT) &&
          GetFileInformationByHandleEx(h,static_cast<FILE_INFO_BY_HANDLE_CLASS>(23),&flags,sizeof(flags));
        CloseHandle(h);need(valid&&flags==0,"opencode_case_sensitive_or_unverifiable");
      }
#endif
    }
    auto parent=at.parent_path();if(parent==at)break;at=parent;
  }
  return full;
}
inline Image read_image(const fs::path& p,std::size_t cap) {
  safe_path(p);std::error_code ec;auto status=fs::symlink_status(p,ec);
  if(!fs::exists(status)) {need(!ec||ec==std::errc::no_such_file_or_directory,"opencode_io_error");return {};}
  need(fs::is_regular_file(status)&&fs::hard_link_count(p)==1,"opencode_regular_single_link_required");
  need(fs::file_size(p)<=cap,"opencode_file_bound");
  std::ifstream in(p,std::ios::binary);need(in.good(),"opencode_io_error");
  std::string raw;char block[8192];
  while(in.read(block,sizeof(block))||in.gcount()) {raw.append(block,static_cast<std::size_t>(in.gcount()));need(raw.size()<=cap,"opencode_file_bound");}
  need(in.eof()&&!in.bad(),"opencode_io_error");return raw;
}
inline std::string hex(const std::string& bytes) {
  static constexpr char digits[]="0123456789abcdef";std::string out;out.reserve(bytes.size()*2);
  for(unsigned char c:bytes){out.push_back(digits[c>>4]);out.push_back(digits[c&15]);}return out;
}
inline Json image_json(const Image& image) {return image?Json(hex(*image)):Json(nullptr);}
inline Image image_from(const Json& value,std::size_t cap) {
  if(value.is_null())return {};
  need(value.is_string(),"opencode_image_shape");const auto& s=value.get_ref<const std::string&>();
  need(s.size()%2==0&&s.size()/2<=cap,"opencode_image_bound");std::string result;result.reserve(s.size()/2);
  auto digit=[](char c)->int {if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;throw Error("opencode_image_hex");};
  for(std::size_t i=0;i<s.size();i+=2)result.push_back(static_cast<char>(16*digit(s[i])+digit(s[i+1])));return result;
}
inline Json stamp(const Image& im) {return im?Json{{"bytes",im->size()},{"sha256",util::sha256_hex(*im)}}:Json(nullptr);}
inline fs::path staging(const fs::path& p) {auto q=p;q+=path(".qbrain-stage");return q;}
inline void destination(const fs::path& p) {
  safe_path(p);safe_path(staging(p));
  need(!fs::exists(staging(p)),"opencode_stage_conflict");
  if(fs::exists(p))need(fs::is_regular_file(p)&&fs::hard_link_count(p)==1,"opencode_regular_single_link_required");
  need(fs::is_directory(p.parent_path()),"opencode_parent_missing");
}
inline void sync_directory(const fs::path& p) {
#ifndef _WIN32
  int fd=::open(p.c_str(),O_RDONLY|O_DIRECTORY|O_CLOEXEC);need(fd>=0,"opencode_io_error");
  const int rc=::fsync(fd);::close(fd);need(rc==0,"opencode_io_error");
#else
  (void)p;
#endif
}
inline void atomic_write(const fs::path& p,const Image& image) {
  destination(p);
  if(!image){if(fs::exists(p)){need(fs::remove(p),"opencode_io_error");sync_directory(p.parent_path());}return;}
  const auto temp=staging(p);
#ifdef _WIN32
  HANDLE h=CreateFileW(temp.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
  need(h!=INVALID_HANDLE_VALUE,"opencode_stage_conflict");DWORD written=0;
  bool ok=WriteFile(h,image->data(),static_cast<DWORD>(image->size()),&written,nullptr)&&written==image->size()&&FlushFileBuffers(h);
  CloseHandle(h);
  if(!ok){DeleteFileW(temp.c_str());throw Error("opencode_io_error");}
  if(fs::exists(p))ok=ReplaceFileW(p.c_str(),temp.c_str(),nullptr,0,nullptr,nullptr);
  else ok=MoveFileExW(temp.c_str(),p.c_str(),MOVEFILE_WRITE_THROUGH);
  if(!ok){DeleteFileW(temp.c_str());throw Error("opencode_io_error");}
#else
  int fd=::open(temp.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600);
  need(fd>=0,"opencode_stage_conflict");bool ok=true;
  struct stat old{};if(::stat(p.c_str(),&old)==0)ok=::fchmod(fd,old.st_mode&0777)==0;
  std::size_t sent=0;
  while(ok&&sent<image->size()) {auto n=::write(fd,image->data()+sent,image->size()-sent);if(n<=0)ok=false;else sent+=static_cast<std::size_t>(n);}
  if(ok)ok=::fsync(fd)==0;::close(fd);
  if(!ok){::unlink(temp.c_str());throw Error("opencode_io_error");}
  if(::rename(temp.c_str(),p.c_str())!=0){::unlink(temp.c_str());throw Error("opencode_io_error");}
  sync_directory(p.parent_path());
#endif
}
class Lock {
#ifdef _WIN32
  HANDLE h_=INVALID_HANDLE_VALUE;
#else
  int fd_=-1;
#endif
 public:
  explicit Lock(const fs::path& p) {
    safe_path(p);if(fs::exists(p))need(fs::is_regular_file(p)&&fs::hard_link_count(p)==1,"opencode_lock_invalid");
#ifdef _WIN32
    h_=CreateFileW(p.c_str(),GENERIC_READ|GENERIC_WRITE,0,nullptr,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    need(h_!=INVALID_HANDLE_VALUE,"opencode_locked");
#else
    fd_=::open(p.c_str(),O_CREAT|O_RDWR|O_CLOEXEC|O_NOFOLLOW,0600);need(fd_>=0,"opencode_locked");
    if(::flock(fd_,LOCK_EX|LOCK_NB)!=0){::close(fd_);fd_=-1;throw Error("opencode_locked");}
#endif
  }
  Lock(const Lock&)=delete;Lock& operator=(const Lock&)=delete;
  ~Lock(){
#ifdef _WIN32
    if(h_!=INVALID_HANDLE_VALUE)CloseHandle(h_);
#else
    if(fd_>=0){::flock(fd_,LOCK_UN);::close(fd_);}
#endif
  }
};
struct Options {fs::path project,binary;int major=0;std::string brain;bool allow_write=false;};
struct Change {std::string slot;Image before,after;};
struct Plan {Json result;std::string name;std::vector<Change> changes;Image journal;};
class Installer {
  Options o_;fs::path root_,dir_,state_,journal_;std::string id_;
  Json owner(const Image& raw) const {
    need(raw.has_value(),"opencode_not_installed");auto j=strict(*raw,state_limit);
    exact(j,{"schema","project","config_name","before","after_sha256","format","brain_id","allow_write","binary_path","binary_sha256","server_name"});
    need(j["schema"]=="qbrain-opencode-owner-v1"&&j["project"].is_string()&&
      identity(path(j["project"].get<std::string>()))==identity(root_),"opencode_owner_identity");
    need(j["config_name"]=="opencode.json"||j["config_name"]=="opencode.jsonc","opencode_owner_target");
    need(j["server_name"]=="qbrain_"+id_&&j["after_sha256"].is_string()&&hex_id(j["after_sha256"].get<std::string>())&&
      j["binary_sha256"].is_string()&&hex_id(j["binary_sha256"].get<std::string>()),"opencode_owner_identity");
    need(j["format"].is_number_integer()&&(j["format"]==1||j["format"]==2)&&j["allow_write"].is_boolean()&&j["brain_id"].is_string()&&j["binary_path"].is_string(),"opencode_owner_fields");
    Settings setting{j["format"].get<int>(),j["binary_path"].get<std::string>(),j["brain_id"].get<std::string>(),"qbrain_"+id_,j["project"].get<std::string>(),j["allow_write"].get<bool>()};
    server_definition(setting);auto before=image_from(j["before"],config_limit);
    // Verify owner backup/definition consistency, not just its self-reported digest.
    auto after=insert_server(before.value_or("{}\n"),setting);
    need(util::sha256_hex(after)==j["after_sha256"].get<std::string>(),"opencode_owner_inconsistent");return j;
  }
  std::pair<std::string,std::string> reconcile_pair(const Image& current,const Image& raw) const {
    auto stored=owner(raw);need(current.has_value(),"opencode_managed_entry_missing");
    if(util::sha256_hex(*current)==stored["after_sha256"].get<std::string>())return {*current,*raw};
    Settings settings{stored["format"].get<int>(),stored["binary_path"].get<std::string>(),
      stored["brain_id"].get<std::string>(),stored["server_name"].get<std::string>(),
      stored["project"].get<std::string>(),stored["allow_write"].get<bool>()};
    const auto baseline=strip_server(*current,settings);const auto next=insert_server(baseline,settings);
    stored["before"]=image_json(baseline);stored["after_sha256"]=util::sha256_hex(next);
    const auto next_owner=stored.dump()+"\n";owner(next_owner);return {next,next_owner};
  }
  fs::path slot(const std::string& name,const std::string& cfg) const {
    need(cfg=="opencode.json"||cfg=="opencode.jsonc","opencode_owner_target");
    if(name=="config")return root_/cfg;if(name=="state")return state_;throw Error("opencode_journal_slot");
  }
  std::size_t cap(const std::string& name)const{return name=="config"?config_limit:state_limit;}
  void environment_guard()const {
    for(const auto* name:{"OPENCODE_CONFIG","OPENCODE_CONFIG_CONTENT","OPENCODE_CONFIG_DIR"})
      if(const auto* value=std::getenv(name))need(*value=='\0',"opencode_override_present");
    for(const auto* name:{"opencode.json","opencode.jsonc"})
      need(!read_image(root_/".opencode"/name,config_limit).has_value(),"opencode_layer_conflict");
  }
 public:
  explicit Installer(Options o):o_(std::move(o)) {
    root_=safe_path(o_.project);need(fs::is_directory(root_),"opencode_project_directory");
    id_=util::sha256_hex(identity(root_)).substr(0,24);
    dir_=safe_path(util::qbrain_root()/"integrations"/"opencode"/id_);state_=dir_/"owner.json";journal_=dir_/"pending.json";
  }
  const fs::path& state_directory()const{return dir_;}
  Plan plan(const std::string& operation)const {
    need(operation=="install"||operation=="uninstall"||operation=="recover"||operation=="reconcile","opencode_operation");
    auto a=read_image(root_/"opencode.json",config_limit),b=read_image(root_/"opencode.jsonc",config_limit);
    auto raw=read_image(state_,state_limit),pending=read_image(journal_,journal_limit);
    Plan p;p.journal=pending;p.name=a?"opencode.json":"opencode.jsonc";
    std::string binary_hash;Json settings=nullptr;Json selected_format=nullptr,selected_write=nullptr;
    if(operation=="recover") {
      need(!read_image(staging(journal_),journal_limit),"opencode_stage_conflict");
      need(pending.has_value(),"opencode_no_recovery");auto j=strict(*pending,journal_limit);
      exact(j,{"schema","project","config_name","changes"});
      const bool reconciliation=j["schema"]=="qbrain-opencode-reconcile-journal-v2";
      need((j["schema"]=="qbrain-opencode-journal-v1"||reconciliation)&&j["project"]==identity(root_)&&j["config_name"].is_string(),"opencode_journal_identity");
      p.name=j["config_name"].get<std::string>();slot("config",p.name);
      need(j["changes"].is_array()&&j["changes"].size()==2,"opencode_journal_shape");
      for(std::size_t i=0;i<2;++i) {
        const auto& c=j["changes"][i];exact(c,{"slot","before","after"});
        need(c["slot"]==(i==0?"config":"state"),"opencode_journal_slot");auto label=c["slot"].get<std::string>();
        auto before=image_from(c["before"],cap(label)),after=image_from(c["after"],cap(label));
        if(label=="state"){if(before)owner(before);if(after)owner(after);}
        else {if(before)Document check(*before);if(after)Document check(*after);}
        const auto dest=slot(label,p.name);auto current=read_image(dest,cap(label));
        need(current==before||current==after,"opencode_recovery_conflict");
        // A known staged full image may be cleaned; unknown partial/user data is retained.
        auto temp=read_image(staging(dest),cap(label));if(temp)need(temp==before||temp==after,"opencode_stage_conflict");
        p.changes.push_back({label,current,before});
      }
      const auto& config_change=j["changes"][0];const auto& state_change=j["changes"][1];
      auto cb=image_from(config_change["before"],config_limit),ca=image_from(config_change["after"],config_limit);
      auto sb=image_from(state_change["before"],state_limit),sa=image_from(state_change["after"],state_limit);
      need(sb||sa,"opencode_journal_inconsistent");
      if(reconciliation) {
        need(cb&&ca&&sb&&sa,"opencode_journal_inconsistent");
        const auto pair=reconcile_pair(cb,sb);
        need(ca==Image(pair.first)&&sa==Image(pair.second)&&owner(sb)["config_name"]==p.name&&owner(sa)["config_name"]==p.name,"opencode_journal_inconsistent");
      } else {
      if(sb){auto before_owner=owner(sb);need(cb&&util::sha256_hex(*cb)==before_owner["after_sha256"].get<std::string>()&&before_owner["config_name"]==p.name,"opencode_journal_inconsistent");
        if(!sa)need(ca==image_from(before_owner["before"],config_limit),"opencode_journal_inconsistent");}
      if(sa){auto after_owner=owner(sa);need(ca&&util::sha256_hex(*ca)==after_owner["after_sha256"].get<std::string>()&&after_owner["config_name"]==p.name,"opencode_journal_inconsistent");
        need(image_from(after_owner["before"],config_limit)==(sb?image_from(owner(sb)["before"],config_limit):cb),"opencode_journal_inconsistent");}
      }
    } else {
      need(!pending,"opencode_recovery_required");need(!(a&&b),"opencode_multiple_configs");
      Image original=a?a:b;auto current=original;
      if(operation=="reconcile") {
        environment_guard();auto stored=owner(raw);p.name=stored["config_name"].get<std::string>();
        need((a&&p.name=="opencode.json")||(b&&p.name=="opencode.jsonc"),"opencode_owner_target");
        auto executable=safe_path(path(stored["binary_path"].get<std::string>()));
        auto bytes=read_image(executable,32*1024*1024);
        need(bytes&&!bytes->empty()&&util::sha256_hex(*bytes)==stored["binary_sha256"].get<std::string>(),"opencode_binary_changed");
#ifdef _WIN32
        auto extension=executable.extension().wstring();std::transform(extension.begin(),extension.end(),extension.begin(),::towlower);
        need(extension==L".exe","opencode_executable_required");
#else
        const auto mode=fs::status(executable).permissions();
        need((mode&(fs::perms::owner_exec|fs::perms::group_exec|fs::perms::others_exec))!=fs::perms::none,"opencode_executable_required");
#ifdef AT_EACCESS
        need(::faccessat(AT_FDCWD,executable.c_str(),X_OK,AT_EACCESS)==0,"opencode_executable_required");
#else
        need(false,"opencode_executable_required");
#endif
#endif
        const auto pair=reconcile_pair(current,raw);
        binary_hash=util::sha256_hex(*bytes);selected_format=stored["format"];selected_write=stored["allow_write"];
        Settings chosen{stored["format"].get<int>(),stored["binary_path"].get<std::string>(),stored["brain_id"].get<std::string>(),stored["server_name"].get<std::string>(),stored["project"].get<std::string>(),stored["allow_write"].get<bool>()};
        settings=server_definition(chosen);p.changes={{"config",current,pair.first},{"state",raw,pair.second}};
        for(const auto& c:p.changes)need(!read_image(staging(slot(c.slot,p.name)),cap(c.slot)),"opencode_stage_conflict");
        need(!read_image(staging(journal_),journal_limit),"opencode_stage_conflict");
      } else {
      if(raw){auto j=owner(raw);p.name=j["config_name"].get<std::string>();
        need(current&&util::sha256_hex(*current)==j["after_sha256"].get<std::string>()&&((a&&p.name=="opencode.json")||(b&&p.name=="opencode.jsonc")),"opencode_external_edit");
        original=image_from(j["before"],config_limit);
      }
      if(operation=="uninstall") {
        need(raw.has_value(),"opencode_not_installed");p.changes={{"config",current,original},{"state",raw,{}}};
      } else {
        environment_guard();need(o_.major==1||o_.major==2,"opencode_format_required");
        auto executable=safe_path(o_.binary);auto bytes=read_image(executable,32*1024*1024);
        need(bytes&& !bytes->empty(),"opencode_binary_required");
#ifdef _WIN32
        auto extension=executable.extension().wstring();std::transform(extension.begin(),extension.end(),extension.begin(),::towlower);
        need(extension==L".exe","opencode_executable_required");
#else
        need((fs::status(executable).permissions()&(fs::perms::owner_exec|fs::perms::group_exec|fs::perms::others_exec))!=fs::perms::none,"opencode_executable_required");
#endif
        Settings chosen{o_.major,path_text(executable),o_.brain,"qbrain_"+id_,path_text(root_),o_.allow_write};
        auto next=insert_server(original.value_or("{}\n"),chosen);binary_hash=util::sha256_hex(*bytes);
        auto stored=Json{{"schema","qbrain-opencode-owner-v1"},{"project",path_text(root_)},{"config_name",p.name},
          {"before",image_json(original)},{"after_sha256",util::sha256_hex(next)},{"format",o_.major},{"brain_id",o_.brain},
          {"allow_write",o_.allow_write},{"binary_path",path_text(executable)},{"binary_sha256",binary_hash},{"server_name",chosen.name}};
        settings=server_definition(chosen);p.changes={{"config",current,next},{"state",raw,stored.dump()+"\n"}};
      }
      }
    }
    Json changes=Json::array();bool changed=false;
    for(const auto& c:p.changes){changes.push_back({{"slot",c.slot},{"before",stamp(c.before)},{"after",stamp(c.after)}});changed|=c.before!=c.after;}
    Json stages=Json::array();for(const auto& c:p.changes)stages.push_back(stamp(read_image(staging(slot(c.slot,p.name)),cap(c.slot))));
    const Json binding={{"schema","qbrain-opencode-plan-v1"},{"project",identity(root_)},{"state_directory",identity(dir_)},{"operation",operation},{"config_name",p.name},
      {"json",stamp(a)},{"jsonc",stamp(b)},{"owner",stamp(raw)},{"pending",stamp(pending)},{"changes",changes},{"definition",settings},{"binary_sha256",binary_hash},{"staging",stages}};
    p.result={{"schema","qbrain-opencode-plan-v1"},{"operation",operation},{"plan_sha256",util::sha256_hex(binding.dump())},
      {"configuration_file",p.name},{"server_name","qbrain_"+id_},{"would_change",changed},{"write_enabled",operation=="install"?Json(o_.allow_write):selected_write},
      {"format",operation=="install"?Json(o_.major):selected_format},{"host_consumption_verified",false},{"model_calls",0}};
    return p;
  }
  Json status()const {
    auto pending=read_image(journal_,journal_limit),raw=read_image(state_,state_limit);
    Json out={{"schema","qbrain-opencode-status-v1"},{"recovery_required",pending.has_value()},
      {"host_consumption_verified",false},{"effective_configuration_verified",false}};
    // Status concerns our registered bytes only. Expose known competing layers;
    // never equate a matching project file with the host's merged configuration.
    out["config_override_present"]=false;
    for(const auto* name:{"OPENCODE_CONFIG","OPENCODE_CONFIG_CONTENT","OPENCODE_CONFIG_DIR"})
      if(const auto* value=std::getenv(name))if(*value)out["config_override_present"]=true;
    bool layered=read_image(root_/"opencode.json",config_limit).has_value() &&
                 read_image(root_/"opencode.jsonc",config_limit).has_value();
    for(const auto* name:{"opencode.json","opencode.jsonc"})
      layered|=read_image(root_/".opencode"/name,config_limit).has_value();
    out["project_layer_conflict"]=layered;
    if(pending){out["installed"]=nullptr;out["configuration_matches"]=nullptr;return out;}
    if(!raw){out["installed"]=false;out["configuration_matches"]=false;return out;}
    auto j=owner(raw);auto current=read_image(root_/j["config_name"].get<std::string>(),config_limit);
    out["installed"]=true;out["configuration_matches"]=current&&util::sha256_hex(*current)==j["after_sha256"].get<std::string>();
    out["format"]=j["format"];out["write_enabled"]=j["allow_write"];out["server_name"]=j["server_name"];
    return out;
  }
  // File-writer dependency is internal and also enables deterministic fault tests.
  Json apply(const std::string& operation,const std::string& approved,
      const std::function<void(const fs::path&,const Image&)>& write=atomic_write)const {
    need(hex_id(approved),"opencode_approval_required");auto initial=plan(operation);
    need(initial.result["plan_sha256"]==approved,"opencode_plan_conflict");
    if(!initial.result["would_change"].get<bool>()&&operation!="recover") {auto r=initial.result;r["applied"]=true;return r;}
    fs::create_directories(dir_);safe_path(dir_);
#ifndef _WIN32
    fs::permissions(dir_,fs::perms::owner_all,fs::perm_options::replace);
#endif
    Lock lock(dir_/"operation.lock");auto current=plan(operation);
    need(current.result["plan_sha256"]==approved,"opencode_plan_conflict");
    std::vector<Image> observed;for(const auto& c:current.changes)observed.push_back(c.before);
    auto unchanged=[&](const Image& expected_journal) {
      need(!read_image(staging(journal_),journal_limit),"opencode_stage_conflict");
      need(read_image(journal_,journal_limit)==expected_journal,"opencode_journal_changed");
      for(std::size_t i=0;i<current.changes.size();++i) {
        const auto& c=current.changes[i];
        need(read_image(slot(c.slot,current.name),cap(c.slot))==observed[i],"opencode_write_conflict");
      }
      need(!read_image(root_/(current.name=="opencode.json"?"opencode.jsonc":"opencode.json"),config_limit),"opencode_multiple_configs");
    };
    if(operation=="recover") {
      std::vector<Image> stages;
      for(const auto& c:current.changes) {
        auto dest=slot(c.slot,current.name);safe_path(dest);
        if(fs::exists(dest))need(fs::is_regular_file(dest)&&fs::hard_link_count(dest)==1,"opencode_regular_single_link_required");
        stages.push_back(read_image(staging(dest),cap(c.slot)));
      }
      // Recreate the approval before any cleanup. Plan includes these stage images.
      need(plan(operation).result["plan_sha256"]==approved,"opencode_plan_conflict");
      for(std::size_t i=0;i<current.changes.size();++i) {
        unchanged(current.journal);const auto& c=current.changes[i];auto temp=staging(slot(c.slot,current.name));
        need(read_image(temp,cap(c.slot))==stages[i],"opencode_stage_conflict");
        if(stages[i]){need(fs::remove(temp),"opencode_io_error");sync_directory(temp.parent_path());}
      }
      for(std::size_t i=current.changes.size();i-->0;) {
        unchanged(current.journal);const auto& c=current.changes[i];
        if(c.before!=c.after)write(slot(c.slot,current.name),c.after);
        observed[i]=c.after;
      }
    } else {
      destination(journal_);for(const auto& c:current.changes)destination(slot(c.slot,current.name));
      unchanged({});
      Json changes=Json::array();for(const auto& c:current.changes)changes.push_back({{"slot",c.slot},{"before",image_json(c.before)},{"after",image_json(c.after)}});
      const std::string journal=Json{{"schema",operation=="reconcile"?"qbrain-opencode-reconcile-journal-v2":"qbrain-opencode-journal-v1"},
        {"project",identity(root_)},{"config_name",current.name},{"changes",changes}}.dump()+"\n";
      need(journal.size()<=journal_limit,"opencode_journal_bound");write(journal_,journal);current.journal=journal;
      for(std::size_t i=0;i<current.changes.size();++i) {
        unchanged(current.journal);const auto& c=current.changes[i];
        if(c.before!=c.after)write(slot(c.slot,current.name),c.after);
        observed[i]=c.after;
      }
    }
    for(const auto& c:current.changes)need(read_image(slot(c.slot,current.name),cap(c.slot))==c.after,"opencode_write_verification");
    need(read_image(journal_,journal_limit)==current.journal,"opencode_journal_changed");atomic_write(journal_,{});
    auto result=current.result;result["applied"]=true;return result;
  }
};
inline int command(const std::vector<std::string>& args) {
  try {
    need(!args.empty(),"opencode_action_required");const auto& action=args[0];
    const std::map<std::string,std::string> actions={{"preview","install"},{"install","install"},{"uninstall-preview","uninstall"},{"uninstall","uninstall"},{"recovery-preview","recover"},{"recover","recover"},{"status","status"},{"reconcile-preview","reconcile"},{"reconcile","reconcile"}};
    need(actions.count(action),"opencode_action");const auto op=actions.at(action);
    std::map<std::string,std::string> values;bool allow=false;std::set<std::string> seen;
    for(std::size_t i=1;i<args.size();++i) {
      auto k=args[i];need(seen.insert(k).second,"opencode_duplicate_argument");
      if(k=="--allow-write") {need(op=="install","opencode_argument");allow=true;continue;}
      need(k=="--project"||k=="--approve-sha256"||(op=="install"&&(k=="--format"||k=="--brain"||k=="--binary")),"opencode_argument");
      need(i+1<args.size(),"opencode_argument_value");values[k]=args[++i];
    }
    const bool applying=action=="install"||action=="uninstall"||action=="recover"||action=="reconcile";
    need(applying?values.count("--approve-sha256")==1:values.count("--approve-sha256")==0,"opencode_approval_required");
    need(values.count("--project"),"opencode_project_required");Options opts;opts.project=path(values["--project"]);opts.allow_write=allow;
    if(op=="install") {
      need(values.count("--binary")&&values.count("--brain"),"opencode_install_arguments");
      need(values["--format"]=="v1"||values["--format"]=="v2","opencode_format_required");
      opts.major=values["--format"]=="v1"?1:2;opts.brain=values["--brain"];opts.binary=path(values["--binary"]);
    }
    Installer installer(opts);auto result=op=="status"?installer.status():applying?installer.apply(op,values["--approve-sha256"]):installer.plan(op).result;
    std::cout<<result.dump()<<'\n';return 0;
  }catch(const Error& e){std::cout<<Json{{"error",{{"code",e.what()}}}}.dump()<<'\n';return 1;}
  catch(...){std::cout<<"{\"error\":{\"code\":\"opencode_io_error\"}}\n";return 1;}
}
} // namespace qbrain::integration::opencode
