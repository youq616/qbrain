#pragma once
// N48B: bounded, read-only registration diagnostics. Never launches the host or
// registered command. Output contains fixed labels, not paths or configuration.
#include "qbrain/integration/opencode_install.hpp"
#include <array>

namespace qbrain::integration::opencode {
struct AuditOptions {
  fs::path project;
  int expected_format=0; // 0 means no expectation, not version autodetection.
  int expected_write=-1; // -1 means no expectation, 0/1 are checks only.
};
namespace audit_detail {
struct Observations {
  std::vector<Image> images;
  std::vector<fs::perms> permissions;
  std::vector<bool> ancestor_configs;
  bool environment_override=false;
  bool operator==(const Observations&) const = default;
};
inline const std::array<const char*,15> checks={
  "paths_readable","configuration_unambiguous","no_ancestor_configuration",
  "no_environment_override","no_pending_recovery","no_staging_conflict",
  "owned_registration_present","ownership_valid","configuration_matches",
  "executable_exists","executable_matches","executable_eligible",
  "expected_format_matches","expected_access_matches","observations_stable"};
inline Observations observe(const fs::path& root,const fs::path& state) {
  Observations out;
  const std::array<std::pair<fs::path,std::size_t>,10> paths={{
    {root/"opencode.json",config_limit},{root/"opencode.jsonc",config_limit},
    {root/".opencode/opencode.json",config_limit},{root/".opencode/opencode.jsonc",config_limit},
    {state/"owner.json",state_limit},{state/"pending.json",journal_limit},
    {staging(root/"opencode.json"),config_limit},{staging(root/"opencode.jsonc"),config_limit},
    {staging(state/"owner.json"),state_limit},{staging(state/"pending.json"),journal_limit}
  }};
  for(const auto& [p,cap]:paths) {
    auto image=read_image(p,cap);
    out.permissions.push_back(image?fs::status(p).permissions():fs::perms::unknown);
    out.images.push_back(std::move(image));
  }
  for(const auto* name:{"OPENCODE_CONFIG","OPENCODE_CONFIG_CONTENT","OPENCODE_CONFIG_DIR"})
    if(const auto* value=std::getenv(name))out.environment_override|=(*value!='\0');
  // Presence-only conservative warning: no reading or executing ancestor config.
  // No global/remote config is inspected, so no effective-host conclusion follows.
  auto parent=root.parent_path();unsigned depth=0;
  while(!parent.empty() && parent!=root) {
    need(++depth<=256,"opencode_audit_ancestor_bound");
    for(const char* name:{"opencode.json","opencode.jsonc",".opencode/opencode.json",".opencode/opencode.jsonc"}) {
      std::error_code error;auto status=fs::symlink_status(parent/name,error);
      need(!error||error==std::errc::no_such_file_or_directory,"opencode_audit_observation_failed");
      out.ancestor_configs.push_back(fs::exists(status));
    }
    auto next=parent.parent_path();if(next==parent)break;parent=next;
  }
  return out;
}
inline bool executable_eligible(const fs::path& file) {
#ifdef _WIN32
  auto extension=file.extension().wstring();
  std::transform(extension.begin(),extension.end(),extension.begin(),::towlower);
  return extension==L".exe"; // Eligibility, NOT Windows loader/PE validation.
#else
  const bool any_execute=(fs::status(file).permissions()&
    (fs::perms::owner_exec|fs::perms::group_exec|fs::perms::others_exec))!=fs::perms::none;
#ifdef AT_EACCESS
  // A mode bit for *another* class is not permission for the current caller.
  // This is a read-only effective-credential query, not a later-exec guarantee.
  return any_execute && ::faccessat(AT_FDCWD,file.c_str(),X_OK,AT_EACCESS)==0;
#else
  // Without effective-ID access support we cannot certify this observation.
  return false;
#endif
#endif
}
} // namespace audit_detail

inline Json audit_registration(const AuditOptions& options) {
  using namespace audit_detail;
  need(options.expected_format==0||options.expected_format==1||options.expected_format==2,"opencode_audit_format");
  need(options.expected_write>=-1&&options.expected_write<=1,"opencode_audit_access");
  Json rows=Json::array();
  for(const auto* label:checks)rows.push_back({{"check",label},{"passed",nullptr}});
  Json report={{"schema","qbrain-opencode-audit-v1"},{"result","UNVERIFIABLE"},{"checks",rows},
    {"registered_format",nullptr},{"registered_write_enabled",nullptr},
    {"expected_format",options.expected_format?Json(options.expected_format):Json(nullptr)},
    {"expected_write_enabled",options.expected_write<0?Json(nullptr):Json(options.expected_write==1)},
    {"registered_bytes_verified",false},{"process_started",false},{"model_calls",0},
    {"effective_configuration_verified",false},{"host_consumption_verified",false},
    {"global_configuration_inspected",false},{"remote_configuration_inspected",false},
    {"read_only",true},{"observation_scope","project_registration_and_ancestor_presence"},
    {"limitations",Json::array({"Not a host load, model call or effective-config verification",
      "Before/after read agreement is not a lock, permanent snapshot or ABA defense",
      "Executable eligibility is not a PE/signature/authenticity check",
      "No automatic recovery, cleanup, permission change or global-config inspection"})}};
  auto set=[&](std::size_t i,Json value){report["checks"][i]["passed"]=std::move(value);};
  try {
    Installer installer({options.project,{},0,"",false});
    auto root=safe_path(options.project);const auto& directory=installer.state_directory();
    auto before=observe(root,directory);set(0,true);
    const auto& images=before.images;
    set(1,!(images[0]&&images[1])&&!images[2]&&!images[3]);
    set(2,std::none_of(before.ancestor_configs.begin(),before.ancestor_configs.end(),[](bool present){return present;}));
    set(3,!before.environment_override);set(4,!images[5]);
    set(5,std::none_of(images.begin()+6,images.end(),[](const Image& image){return image.has_value();}));
    set(6,images[4].has_value());
    Image executable_before;fs::perms executable_mode=fs::perms::unknown;fs::path executable;
    bool owner_ok=false;
    if(images[4]&&!images[5]) {
      try {
        // Existing status fully validates the owner and reconstructs its expected
        // inserted config. Reuse this authority rather than inventing a looser one.
        auto status=installer.status();set(7,true);owner_ok=true;
        set(8,status["configuration_matches"]);
        auto registered=strict(*images[4],state_limit);
        report["registered_format"]=registered["format"];
        report["registered_write_enabled"]=registered["allow_write"];
        if(options.expected_format)set(12,registered["format"]==options.expected_format);
        if(options.expected_write>=0)set(13,registered["allow_write"]==(options.expected_write==1));
        executable=path(registered["binary_path"].get<std::string>());
        need(executable.is_absolute(),"opencode_audit_binary_path");
        executable_before=read_image(executable,32*1024*1024);
        set(9,executable_before.has_value());
        if(executable_before) {
          set(10,util::sha256_hex(*executable_before)==registered["binary_sha256"].get<std::string>());
          executable_mode=fs::status(executable).permissions();
          set(11,!executable_before->empty()&&executable_eligible(executable));
        }
      } catch(...) {
        if(!owner_ok)set(7,false);
        else {set(9,false);set(10,nullptr);set(11,nullptr);}
      }
    }
    bool stable=before==observe(root,directory);
    if(!executable.empty()) {
      try {
        auto after=read_image(executable,32*1024*1024);
        stable&=(after==executable_before);
        if(after)stable&=(fs::status(executable).permissions()==executable_mode);
      } catch(...) {stable=false;}
    }
    set(14,stable);
    if(!stable)report["result"]="UNVERIFIABLE";
    else if(!images[4]&&!images[5])report["result"]="NOT_REGISTERED";
    else {
      bool ready=true;
      for(std::size_t i=0;i<checks.size();++i) {
        if((i==12&&!options.expected_format)||(i==13&&options.expected_write<0))continue;
        ready&=(report["checks"][i]["passed"]==true);
      }
      report["registered_bytes_verified"]=ready;
      report["result"]=ready?"LOCAL_REGISTRATION_CHECKS_PASSED":"BLOCKED";
    }
  } catch(...) {
    set(0,false);set(14,nullptr);report["result"]="UNVERIFIABLE";
    report["registered_bytes_verified"]=false;
  }
  need(report.dump().size()+1<=8192,"opencode_audit_output_bound");
  return report;
}

inline int audit_command(const std::vector<std::string>& args) {
  try {
    need(!args.empty()&&args[0]=="audit","opencode_audit_action");
    std::map<std::string,std::string> values;
    for(std::size_t i=1;i<args.size();i+=2) {
      const auto& key=args[i];
      need(key=="--project"||key=="--expect-format"||key=="--expect-access","opencode_audit_argument");
      need(i+1<args.size()&&values.emplace(key,args[i+1]).second,"opencode_audit_argument");
    }
    need(values.count("--project")&&!values["--project"].empty(),"opencode_project_required");
    AuditOptions options;options.project=path(values["--project"]);
    if(values.count("--expect-format")) {
      auto value=values["--expect-format"];need(value=="v1"||value=="v2","opencode_audit_format");
      options.expected_format=value=="v1"?1:2;
    }
    if(values.count("--expect-access")) {
      auto value=values["--expect-access"];need(value=="read-only"||value=="read-write","opencode_audit_access");
      options.expected_write=value=="read-write"?1:0;
    }
    auto report=audit_registration(options);std::cout<<report.dump()<<'\n';
    return report["result"]=="LOCAL_REGISTRATION_CHECKS_PASSED"?0:1;
  } catch(...) {
    // No arbitrary filesystem/error text or user-controlled option values.
    std::cout<<"{\"error\":{\"code\":\"opencode_audit_invalid_request\"}}\n";return 2;
  }
}
} // namespace qbrain::integration::opencode
