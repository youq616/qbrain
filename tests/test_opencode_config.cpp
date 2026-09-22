#include "qbrain/integration/opencode_install.hpp"
#include <random>
#include <chrono>
using namespace qbrain::integration::opencode;
static int count=0;
static void test(bool ok,const std::string& name){if(!ok)throw std::runtime_error(name);++count;}
template<class Fn>static void rejects(Fn fn,const std::string& name){bool caught=false;try{fn();}catch(...){caught=true;}test(caught,name);}
static Settings settings(int major){return {major,"C:\\Qbrain 中文\\qbrain.exe","review","qbrain_0123456789abcdef01234567","C:\\Project space",false};}
static void parser_tests(){
  const std::vector<std::string> samples={"{}","{ }\n", "\xEF\xBB\xBF//comment 中文\n{\"model\":\"keep\",}\n",
    "/*start*/{\"mcp\":{/*existing*/},\"values\":[1,2,],}//end",
    "{\"mcp\":{\"other\":{\"type\":\"remote\",\"url\":\"https://not-called.invalid\"},},\"x\":1}",
    "{\"string\":\"// not comment /* not */ ,}\\\"\",\"escaped\\u006bey\":true}",
    "{\"mcp\":{/* multi\nline */\"other\":{},//comment\n},\"huge\":1234567890123456789}",
    "{\"mcp\":{\"other\":{} /*end*/}, \"url\":\"{env:EXISTING_SETTING}\"}"};
  for(auto major:{1,2}) for(auto text:samples){
    // Existing V1 server maps are intentionally refused when explicitly selecting V2.
    auto spec=settings(major);Document before(text);
    if(major==2&&before.parsed.contains("mcp")&&before.parsed["mcp"].contains("other")&&before.parsed["mcp"]["other"].contains("type")){
      rejects([&]{insert_server(text,spec);},"mixed version refusal");continue;
    }
    auto output=insert_server(text,spec);Document after(output);Json wanted=before.parsed;
    if(major==1)wanted["mcp"][spec.name]=server_definition(spec);else wanted["mcp"]["servers"][spec.name]=server_definition(spec);
    test(after.parsed==wanted,"only intended JSON value inserted");
    // Exact input can be obtained by removing one contiguous insertion.
    std::size_t prefix=0;while(prefix<text.size()&&prefix<output.size()&&text[prefix]==output[prefix])++prefix;
    auto suffix=text.size()-prefix;test(output.substr(output.size()-suffix)==text.substr(prefix),"original bytes preserved");
    rejects([&]{insert_server(output,spec);},"unowned matching name refused");
    auto definition=major==1?after.parsed["mcp"][spec.name]:after.parsed["mcp"]["servers"][spec.name];
    test(definition["environment"]["QBRAIN_MCP_ALLOW_WRITE"]=="0","ambient write denied");
    test(definition["command"].size()==6,"default read-only command");
  }
  // Independent expectations transcribed from the official versioned schemas,
  // not server_definition used as both implementation and oracle.
  auto one=server_definition(settings(1)),two=server_definition(settings(2));
  test(one["timeout"].is_number_integer()&&one["timeout"]==10000,"V1 timeout scalar");
  test(two["timeout"]==Json{{"startup",10000},{"catalog",10000}},"V2 timeout stage object");
  test(!one.contains("disabled")&&!two.contains("enabled"),"version-specific fields do not leak");
  test(!two["timeout"].contains("execution"),"V2 tool execution limit not silently changed");
  auto s=settings(2);auto text="{\"mcp\":{\"servers\":{\"unrelated\":{}},\"timeout\":{\"execution\":50000}},\"a\":null}";
  test(Document(insert_server(text,s)).parsed["mcp"]["timeout"]==Json{{"execution",50000}},"v2 unrelated MCP field retained");
  s.allow_write=true;test(server_definition(s)["command"].back()=="--allow-write","explicit write flag");
  s.binary="C:\\{env:EVIL}\\q.exe";rejects([&]{server_definition(s);},"host interpolation refused");
  s=settings(1);s.project="C:\\line\nbreak";rejects([&]{server_definition(s);},"path control refused");
  s=settings(1);s.brain="../bad";rejects([&]{server_definition(s);},"brain path refused");
  for(const std::string bad:{"", "[]", "null", "{,}","{\"a\":,}","{\"a\":[,]}","{\"a\":1,,}","{\"mcp\":{},\"mcp\":{}}",
       "{\"mcp\":{},\"\\u006dcp\":{}}", "{\"a\":{\"x\":1,\"x\":2}}", "/*unfinished", "{\"x\":NaN}", "{\"x\":\"\\ud800\"}",
       "{}garbage", "{\"x\":true false}", "{\"x\":1e9999}", "{\"x\":'no'}", "{\"x\":0x01}"})
    rejects([&]{Document doc(bad);},"malformed or ambiguous JSONC");
  rejects([&]{Document doc(std::string("//\xff\n{}",6));},"invalid UTF8 in comments");
  rejects([&]{Document doc(std::string("{}\0junk",7));},"NUL suffix");
  rejects([&]{Document doc(std::string(config_limit+1,' '));},"config byte bound");
  rejects([&]{Document doc(std::string(100,'[')+std::string(100,']'));},"depth bound");
  for(auto wrong:{"{\"mcp\":null}","{\"mcp\":[]}","{\"mcp\":false}"})rejects([&]{insert_server(wrong,settings(1));},"wrong MCP type");
  rejects([&]{insert_server("{\"mcp\":{\"servers\":[]}}",settings(2));},"wrong servers type");
  rejects([&]{insert_server("{\"mcp\":{\"servers\":{}}}",settings(1));},"v1-v2 conflict");
  // Independently generated comments/trailing commas with exact semantic oracle.
  std::mt19937 gen(4801);
  for(int i=0;i<500;++i){
    Json base={{"n",i},{"text",std::string(i%17,'x')+"\\\"},//"},{"array",Json::array({i,true,nullptr})}};
    if(i%2)base["mcp"]=Json::object();if(i%3==0)base["nested"]={{"keep",Json::array({1,2,3})}};
    auto raw=base.dump(2);std::string noisy;bool quote=false,escape=false;
    for(char c:raw){noisy+=c;if(quote){if(escape)escape=false;else if(c=='\\')escape=true;else if(c=='"')quote=false;continue;}
      if(c=='"'){quote=true;continue;}if(c==','||c=='{'||c=='[')noisy+=(gen()%2?"/*noise*/":"//noise\n");}
    for(int version:{1,2}){auto spec=settings(version);auto out=insert_server(noisy,spec);auto expected=base;
      if(version==1)expected["mcp"][spec.name]=server_definition(spec);else expected["mcp"]["servers"][spec.name]=server_definition(spec);
      test(Document(out).parsed==expected,"generated semantic oracle");}
  }
}
static void set_home(const fs::path& p){
#ifdef _WIN32
  _wputenv_s(L"LOCALAPPDATA",p.c_str());
#else
  setenv("HOME",p.c_str(),1);
#endif
}
static void file(const fs::path& p,const std::string& text){fs::create_directories(p.parent_path());std::ofstream(p,std::ios::binary)<<text;}
static void lifecycle_tests(){
  auto root=fs::temp_directory_path()/("qbrain-n48a-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
  fs::create_directories(root);struct Cleanup{fs::path p;~Cleanup(){std::error_code ec;fs::remove_all(p,ec);}}cleanup{root};
  set_home(root/"home");auto project=root/"project";fs::create_directory(project);
  auto binary=root/"fake.exe";file(binary,"synthetic-not-executed");fs::permissions(binary,fs::perms::owner_all);
  const std::string original="\xEF\xBB\xBF// original 中文\r\n{\"model\":\"keep\",}\r\n";
  file(project/"opencode.jsonc",original);Options options{project,binary,1,"test-brain",false};Installer inst(options);
  test(!fs::exists(inst.state_directory()),"constructor does not create state");auto preview=inst.plan("install");
  test(!fs::exists(inst.state_directory())&&read_image(project/"opencode.jsonc",config_limit)==original,"preview read-only");
  rejects([&]{inst.apply("install",std::string(64,'0'));},"wrong approval rejected");
  test(!fs::exists(inst.state_directory()),"wrong approval no metadata");
  inst.apply("install",preview.result["plan_sha256"]);test(inst.status()["configuration_matches"]==true,"installed status");
  test(inst.status()["effective_configuration_verified"]==false,"registration is not host readiness");
  file(project/"opencode.json","{}");test(inst.status()["project_layer_conflict"]==true,"status reports new competing root config");fs::remove(project/"opencode.json");
  file(project/".opencode/opencode.json","{}");test(inst.status()["project_layer_conflict"]==true,"status reports new higher project layer");fs::remove(project/".opencode/opencode.json");
  auto installed=read_image(project/"opencode.jsonc",config_limit);auto owner_before=read_image(inst.state_directory()/"owner.json",state_limit);
  auto again=inst.plan("install");test(again.result["would_change"]==false,"idempotent reinstall");inst.apply("install",again.result["plan_sha256"]);
  test(read_image(inst.state_directory()/"owner.json",state_limit)==owner_before,"idempotent state bytes");
  options.major=2;options.allow_write=true;Installer upgrade(options);auto up=upgrade.plan("install");upgrade.apply("install",up.result["plan_sha256"]);
  test(upgrade.status()["format"]==2&&upgrade.status()["write_enabled"]==true,"explicit format/write upgrade");
  installed=read_image(project/"opencode.jsonc",config_limit);file(project/"opencode.jsonc",*installed+"// external\n");
  test(upgrade.status()["configuration_matches"]==false,"external edit status");
  rejects([&]{upgrade.plan("uninstall");},"uninstall never clobbers external edit");
  file(project/"opencode.jsonc",*installed);auto undo=upgrade.plan("uninstall");upgrade.apply("uninstall",undo.result["plan_sha256"]);
  test(read_image(project/"opencode.jsonc",config_limit)==original&&!fs::exists(inst.state_directory()/"owner.json"),"undo exact original bytes");
  for(int cut:{1,2,3}){
    auto p=inst.plan("install");int writes=0;
    rejects([&]{inst.apply("install",p.result["plan_sha256"],[&](const fs::path& target,const Image& image){atomic_write(target,image);if(++writes==cut)throw Error("test_cut");});},"injected multi-file interruption");
    test(inst.status()["recovery_required"]==true,"interruption retained journal");
    auto recovery=inst.plan("recover");inst.apply("recover",recovery.result["plan_sha256"]);
    test(read_image(project/"opencode.jsonc",config_limit)==original&&!fs::exists(inst.state_directory()/"owner.json")&&!fs::exists(inst.state_directory()/"pending.json"),"all interruption points restore exact bytes");
  }
  auto p=inst.plan("install");int writes=0;
  rejects([&]{inst.apply("install",p.result["plan_sha256"],[&](const fs::path& target,const Image& image){atomic_write(target,image);if(++writes==2)throw Error("test_cut");});},"recovery conflict fixture");
  auto half=read_image(project/"opencode.jsonc",config_limit);file(project/"opencode.jsonc","{\"changed\":true}");
  auto journal=read_image(inst.state_directory()/"pending.json",journal_limit);
  rejects([&]{inst.plan("recover");},"recovery rejects unrelated external state");
  test(read_image(inst.state_directory()/"pending.json",journal_limit)==journal,"recovery conflict keeps evidence");
  file(project/"opencode.jsonc",*half);
  auto malformed=strict(*journal,journal_limit);malformed["changes"][0]["before"]=hex("{\"injected\":true}");
  file(inst.state_directory()/"pending.json",malformed.dump());
  rejects([&]{inst.plan("recover");},"inconsistent backup and owner blocked");file(inst.state_directory()/"pending.json",*journal);
  auto r=inst.plan("recover");inst.apply("recover",r.result["plan_sha256"]);
  auto ready=inst.plan("install");inst.apply("install",ready.result["plan_sha256"]);
  auto active_config=read_image(project/"opencode.jsonc",config_limit),active_owner=read_image(inst.state_directory()/"owner.json",state_limit);
  for(const auto& action:{std::string("uninstall"),std::string("install")})for(int cut:{1,2,3}) {
    const auto& actor=action=="install"?upgrade:inst;auto approved=actor.plan(action);int completed=0;
    rejects([&]{actor.apply(action,approved.result["plan_sha256"],[&](const fs::path& target,const Image& image){atomic_write(target,image);if(++completed==cut)throw Error("test_cut");});},"undo/update interrupted at durable boundary");
    auto back=actor.plan("recover");actor.apply("recover",back.result["plan_sha256"]);
    test(read_image(project/"opencode.jsonc",config_limit)==active_config&&read_image(inst.state_directory()/"owner.json",state_limit)==active_owner,"undo/update recovery preserves exact prior installation");
  }
  auto altered=inst.plan("install");file(binary,"changed-binary-identity");
  rejects([&]{inst.apply("install",altered.result["plan_sha256"]);},"binary change invalidates even no-op plan");file(binary,"synthetic-not-executed");
  {Lock held(inst.state_directory()/"operation.lock");auto un=inst.plan("uninstall");rejects([&]{inst.apply("uninstall",un.result["plan_sha256"]);},"cooperating lock refuses another mutation");}
  test(read_image(project/"opencode.jsonc",config_limit)==active_config,"lock refusal preserves current bytes");
  auto un=inst.plan("uninstall");inst.apply("uninstall",un.result["plan_sha256"]);
  // A known staged image is recoverable; an arbitrary partial image is not erased.
  auto first=inst.plan("install");int done=0;
  rejects([&]{inst.apply("install",first.result["plan_sha256"],[&](const fs::path& target,const Image& image){atomic_write(target,image);if(++done==1)throw Error("test_cut");});},"staged-recovery journal fixture");
  auto data=strict(*read_image(inst.state_directory()/"pending.json",journal_limit),journal_limit);
  auto next=image_from(data["changes"][0]["after"],config_limit);auto temp=staging(project/"opencode.jsonc");file(temp,"unknown-partial-stage");
  rejects([&]{inst.plan("recover");},"unknown partial stage preserved");
  test(read_image(temp,config_limit)=="unknown-partial-stage","unknown stage is not deleted");
  file(temp,*next);auto rec=inst.plan("recover");file(temp,original);
  rejects([&]{inst.apply("recover",rec.result["plan_sha256"]);},"staging changes invalidate recovery approval");
  rec=inst.plan("recover");inst.apply("recover",rec.result["plan_sha256"]);
  test(!fs::exists(temp)&&read_image(project/"opencode.jsonc",config_limit)==original,"known stage cleaned after reapproved recovery");
  // Absence is distinct from empty: uninstall removes only a newly created config.
  fs::remove(project/"opencode.jsonc");auto empty=inst.plan("install");inst.apply("install",empty.result["plan_sha256"]);
  auto del=inst.plan("uninstall");inst.apply("uninstall",del.result["plan_sha256"]);test(!fs::exists(project/"opencode.jsonc"),"new config removed on undo");
#ifndef _WIN32
  file(root/"elsewhere","{}");fs::create_symlink(root/"elsewhere",project/"opencode.jsonc");
  rejects([&]{inst.plan("install");},"symlink target rejected");fs::remove(project/"opencode.jsonc");
  fs::create_hard_link(root/"elsewhere",project/"opencode.jsonc");
  rejects([&]{inst.plan("install");},"hardlink target rejected");fs::remove(project/"opencode.jsonc");
#endif
  file(project/"opencode.json","{}");file(project/"opencode.jsonc","{}");rejects([&]{inst.plan("install");},"ambiguous two config files");
  fs::remove(project/"opencode.json");file(project/".opencode/opencode.jsonc","{}");rejects([&]{inst.plan("install");},"higher project layer rejected");
}
int main(){try{parser_tests();lifecycle_tests();std::cout<<Json{{"result","PASS"},{"checks",count},{"native_windows",
#ifdef _WIN32
true
#else
false
#endif
},{"real_client_verified",false}}.dump()<<'\n';return 0;}catch(const std::exception& e){std::cerr<<e.what()<<" after "<<count<<" checks\n";return 1;}}
