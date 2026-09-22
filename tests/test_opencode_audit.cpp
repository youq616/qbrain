#include "qbrain/integration/opencode_audit.hpp"
#include <chrono>
#include <iostream>
using namespace qbrain::integration::opencode;
namespace {
int count=0;
void check(bool ok,const char* name){if(!ok)throw std::runtime_error(name);++count;}
void put(const fs::path& file,const std::string& bytes){fs::create_directories(file.parent_path());std::ofstream out(file,std::ios::binary);out<<bytes;out.close();check(bool(out),"fixture write");}
void home(const fs::path& root){
#ifdef _WIN32
 _wputenv_s(L"LOCALAPPDATA",root.c_str());
#else
 setenv("HOME",root.c_str(),1);
#endif
}
void environment(const char* key,const std::string& value){
#ifdef _WIN32
 _putenv_s(key,value.c_str());
#else
 if(value.empty())unsetenv(key);else setenv(key,value.c_str(),1);
#endif
}
std::string state(const fs::path& root){
 Json rows=Json::array();std::vector<fs::path> files;
 for(const auto& e:fs::recursive_directory_iterator(root))files.push_back(e.path());
 std::sort(files.begin(),files.end());
 for(const auto& p:files){auto s=fs::symlink_status(p);std::string bytes;
  if(fs::is_regular_file(s)){std::ifstream in(p,std::ios::binary);bytes.assign(std::istreambuf_iterator<char>(in),{});}
  rows.push_back(Json::array({path_text(p),int(s.type()),int(s.permissions()),bytes}));}
 return qbrain::util::sha256_hex(rows.dump());
}
Json observed(const Json& r,const char* label){for(const auto& c:r["checks"])if(c["check"]==label)return c["passed"];throw std::runtime_error("missing check");}
void run(){
 auto root=fs::temp_directory_path()/("n48b-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));fs::create_directories(root);
 struct Clean{fs::path p;~Clean(){std::error_code e;fs::remove_all(p,e);}}clean{root};
 home(root/"home");auto project=root/"sensitive-project-PRIVATE";fs::create_directory(project);
 auto binary=root/"sensitive-program-PRIVATE.exe";put(binary,"synthetic-executable-private");fs::permissions(binary,fs::perms::owner_all);
 const std::string original="\xEF\xBB\xBF// DO-NOT-LEAK-secret\r\n{\"provider\":{\"key\":\"DO-NOT-LEAK-secret\"},}\r\n";
 put(project/"opencode.jsonc",original);
 auto inspect=[&](const AuditOptions& options){auto before=state(root);auto report=audit_registration(options);check(state(root)==before,"audit never mutates files or modes");
  auto text=report.dump();check(text.size()+1<=8192,"output bounded");
  for(const auto& secret:{std::string("DO-NOT-LEAK"),path_text(root),std::string("sensitive-project"),std::string("sensitive-program"),std::string("synthetic-executable")})check(text.find(secret)==std::string::npos,"no diagnostic secret or path");
  for(const char* k:{"host_consumption_verified","effective_configuration_verified","global_configuration_inspected","remote_configuration_inspected","process_started"})check(report[k]==false,"scope not invented");
  check(report["read_only"]==true&&report["model_calls"]==0,"no write or provider claim");return report;};
 auto absent=inspect({project});check(absent["result"]=="NOT_REGISTERED","missing owner is not installed");
 for(int major:{1,2})for(bool write:{false,true}){
  Installer actor({project,binary,major,"audit-fixture",write});auto plan=actor.plan("install");actor.apply("install",plan.result["plan_sha256"]);
  auto report=inspect({project,major,write?1:0});check(report["result"]=="LOCAL_REGISTRATION_CHECKS_PASSED"&&report["registered_bytes_verified"]==true,"healthy installed contract");
  check(report["registered_format"]==major&&report["registered_write_enabled"]==write,"registered settings exact");
  auto other=inspect({project,major==1?2:1,write?0:1});check(other["result"]=="BLOCKED"&&observed(other,"expected_format_matches")==false&&observed(other,"expected_access_matches")==false,"expectations do not mutate permission or format");
 }
 Installer actor({project,binary,2,"audit-fixture",true});const auto dir=actor.state_directory();
 auto installed=*read_image(project/"opencode.jsonc",config_limit);auto owned=*read_image(dir/"owner.json",state_limit);
 put(binary,"different-bytes-private");check(actor.status()["configuration_matches"]==true,"legacy status only checks registered config");
 auto changed=inspect({project});check(observed(changed,"executable_matches")==false&&changed["result"]=="BLOCKED","binary replacement is diagnosed");
 put(binary,"synthetic-executable-private");
#ifndef _WIN32
 fs::permissions(binary,fs::perms::owner_read|fs::perms::owner_write);auto mode=inspect({project});check(observed(mode,"executable_eligible")==false,"non-executable bits blocked");fs::permissions(binary,fs::perms::owner_all);
#endif
 fs::rename(binary,root/"saved.exe");auto missing=inspect({project});check(observed(missing,"executable_exists")==false&&missing["result"]=="BLOCKED","missing executable blocked");fs::rename(root/"saved.exe",binary);
 put(project/"opencode.jsonc",installed+"// external-private\n");auto external=inspect({project});check(observed(external,"configuration_matches")==false,"external edit detected without undo");put(project/"opencode.jsonc",installed);
 put(dir/"owner.json","{bad-json DO-NOT-LEAK}");auto corrupt=inspect({project});check(observed(corrupt,"ownership_valid")==false,"malformed ownership does not get trust");put(dir/"owner.json",owned);
 auto value=strict(owned);value["allow_write"]=false;put(dir/"owner.json",value.dump());auto forged=inspect({project});check(observed(forged,"ownership_valid")==false,"inconsistent owner fails reconstruction");put(dir/"owner.json",owned);
 for(const auto* name:{"opencode.json",".opencode/opencode.json",".opencode/opencode.jsonc"}){
  put(project/name,"{}");auto layer=inspect({project});check(observed(layer,"configuration_unambiguous")==false,"project layer conflict");fs::remove(project/name);
 }
 for(const auto* key:{"OPENCODE_CONFIG","OPENCODE_CONFIG_CONTENT","OPENCODE_CONFIG_DIR"}){
  environment(key,"DO-NOT-LEAK-secret-missing-target");auto env=inspect({project});check(observed(env,"no_environment_override")==false,"override presence only");environment(key,"");
 }
 put(root/"opencode.jsonc",std::string(70000,'x'));auto ancestor=inspect({project});check(observed(ancestor,"no_ancestor_configuration")==false,"ancestor presence not parsed as oversized config");fs::remove(root/"opencode.jsonc");
 for(const auto& stage:{staging(project/"opencode.json"),staging(project/"opencode.jsonc"),staging(dir/"owner.json"),staging(dir/"pending.json")}){
  put(stage,"unowned partial DO-NOT-LEAK");auto conflict=inspect({project});check(observed(conflict,"no_staging_conflict")==false&&conflict["result"]=="BLOCKED","staging images retained and never accepted");fs::remove(stage);
 }
 put(dir/"pending.json","{\"unknown\":\"DO-NOT-LEAK\"}");auto pending=inspect({project});check(observed(pending,"no_pending_recovery")==false&&pending["result"]=="BLOCKED","pending recovery blocks audit without interpreting unsafe journal");fs::remove(dir/"pending.json");
 auto undo=actor.plan("uninstall");actor.apply("uninstall",undo.result["plan_sha256"]);
 for(int cut:{1,2,3}){
  int calls=0;auto plan=actor.plan("install");try{actor.apply("install",plan.result["plan_sha256"],[&](const fs::path& p,const Image& im){atomic_write(p,im);if(++calls==cut)throw Error("test_cut");});}catch(const Error&){}
  auto report=inspect({project});check(observed(report,"no_pending_recovery")==false&&report["registered_bytes_verified"]==false,"all interrupted install boundaries blocked");
  auto recovery=actor.plan("recover");actor.apply("recover",recovery.result["plan_sha256"]);check(inspect({project})["result"]=="NOT_REGISTERED","explicit owner recovery stays separate");
 }
#ifndef _WIN32
 put(root/"elsewhere","{}");fs::create_symlink(root/"elsewhere",project/"opencode.json");check(inspect({project})["result"]=="UNVERIFIABLE","symlink rejected");fs::remove(project/"opencode.json");
 fs::create_hard_link(root/"elsewhere",project/"opencode.json");check(inspect({project})["result"]=="UNVERIFIABLE","hard link rejected");fs::remove(project/"opencode.json");
#endif
 auto plan=actor.plan("install");actor.apply("install",plan.result["plan_sha256"]);
 check(inspect({project})["result"]=="LOCAL_REGISTRATION_CHECKS_PASSED","healthy restored control passes");
}
}
int main(){try{run();std::cout<<Json{{"schema","qbrain-n48b-unit-v1"},{"result","PASS"},{"checks",count},{"host_started",false}}.dump()<<'\n';return 0;}catch(const std::exception& e){std::cerr<<e.what()<<" after "<<count<<" checks\n";return 1;}}
