#include "qbrain/integration/opencode_audit.hpp"
#include <chrono>
#include <random>
using namespace qbrain::integration::opencode;
static int checks=0;
static void verify(bool value,const std::string& name){if(!value)throw std::runtime_error(name);++checks;}
template<class F>static void reject(F fn,const std::string& name){bool failed=false;try{fn();}catch(...){failed=true;}verify(failed,name);}
static void put(const fs::path& p,const std::string& s){fs::create_directories(p.parent_path());std::ofstream out(p,std::ios::binary);out<<s;need(out.good(),"test_write");}
static void home(const fs::path& p){
#ifdef _WIN32
  _wputenv_s(L"LOCALAPPDATA",p.c_str());
#else
  setenv("HOME",p.c_str(),1);
#endif
}
static Settings setting(int version){return {version,"C:\\test\\qbrain.exe","test-brain","qbrain_0123456789abcdef01234567","C:\\Project",false};}
static void parser(){
  for(int major:{1,2}){
    auto s=setting(major);const auto key=Json(s.name).dump();const auto def=server_definition(s).dump();
    // All expected byte strings are assembled independently of the production spans.
    const std::vector<std::pair<std::string,std::string>> cases={
      {"{/*H*/"+key+":"+def+"/*T*/}","{/*H*//*T*/}"},
      {"{/*H*/"+key+":"+def+"/*B*/,/*T*/}","{/*H*//*B*//*T*/}"},
      {"{"+key+":"+def+",/*R*/\"z\":2}","{/*R*/\"z\":2}"},
      {"{\"a\":1/*L*/,/*M*/"+key+":"+def+"/*R*/}","{\"a\":1/*L*//*M*//*R*/}"},
      {"{\"a\":1,/*L*/"+key+":"+def+",/*R*/\"z\":2,}","{\"a\":1,/*L*//*R*/\"z\":2,}"},
      {"{\"qbrain_0123456789abcdef0123456\\u0037\":"+def+",\"z\":{\"array\":[[1,2,],],},}","{\"z\":{\"array\":[[1,2,],],},}"}
    };
    for(const auto& [obj,expected]:cases){
      const std::string prefix="\xEF\xBB\xBF//outside 中文\r\n{\"mcp\":"+(major==1?std::string(""):std::string("{\"servers\":"));
      const std::string suffix=(major==1?std::string(""):std::string("}"))+",\"provider\":{\"keep\":true,},}\r\n";
      auto raw=prefix+obj+suffix;auto out=strip_server(raw,s);
      verify(out==prefix+expected+suffix,"exact untouched byte ranges");
      auto parsed=Document(raw).parsed;auto& servers=major==1?parsed["mcp"]:parsed["mcp"]["servers"];servers.erase(s.name);
      verify(Document(out).parsed==parsed,"only selected member removed");
    }
    std::mt19937 rng(483);
    for(int i=0;i<300;++i){
      Json model={{"n",i},{"str","\"}, // not comment 中文"},{"a",Json::array({i,true,nullptr})}};
      Json servers={{"aa",model},{s.name,server_definition(s)},{"zz",Json::array({model})}};
      Json target={{"mcp",major==1?servers:Json{{"servers",servers}}},{"model","untouched"}};
      auto raw=target.dump(2);std::string noisy;bool quoted=false,escaped=false;
      for(char c:raw){noisy+=c;if(quoted){if(escaped)escaped=false;else if(c=='\\')escaped=true;else if(c=='"')quoted=false;continue;}
        if(c=='"'){quoted=true;continue;}if(c==','||c=='{'||c=='[')noisy+=(rng()%2?"/*comment*/":"//comment\r\n");}
      auto& obj=major==1?target["mcp"]:target["mcp"]["servers"];obj.erase(s.name);
      auto stripped=strip_server(noisy,s);verify(Document(stripped).parsed==target,"generated removal semantic oracle");
      const auto reinserted=insert_server(stripped,s);auto back=Document(reinserted).parsed;
      verify(back==Document(noisy).parsed,"round trip preserves entire definition");
    }
    for(const std::string bad:{"{,}","{\"a\":,}","{\"a\":[1,,]}","{\"a\":1,\"\\u0061\":2}","{\"a\":1} false","{\"a\":1/*"})
      reject([&]{Document parsed(bad);},"invalid/duplicate JSONC refused");
    auto raw=insert_server("{}",s);for(const auto& field:{"command","cwd","environment","timeout",major==1?"enabled":"disabled"}){
      auto parsed=Document(raw).parsed;auto& defn=major==1?parsed["mcp"][s.name]:parsed["mcp"]["servers"][s.name];defn[field]=nullptr;
      reject([&]{strip_server(parsed.dump(),s);},"modified typed setting never adopted");}
    reject([&]{strip_server("{}",s);},"missing managed entry refused");
  }
}
struct Fixture{
  fs::path root,project,binary;Options options;std::unique_ptr<Installer> inst;
  explicit Fixture(int major,bool allow){root=fs::temp_directory_path()/("n48c-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    fs::create_directories(root);home(root/"home");project=root/"project";fs::create_directory(project);binary=root/"qbrain.exe";
    put(binary,"synthetic-not-executed");fs::permissions(binary,fs::perms::owner_all);options={project,binary,major,"review",allow};inst=std::make_unique<Installer>(options);
    put(project/"opencode.jsonc","{/*before*/\"user\":\"initial\"}\r\n");auto p=inst->plan("install");inst->apply("install",p.result["plan_sha256"]);}
  ~Fixture(){std::error_code e;fs::remove_all(root,e);}
  fs::path config()const{return project/"opencode.jsonc";}fs::path owner()const{return inst->state_directory()/"owner.json";}
  fs::path pending()const{return inst->state_directory()/"pending.json";}
  std::pair<std::string,std::string> edited(){
    auto o=strict(*read_image(owner(),state_limit));Settings s{options.major,path_text(binary),"review",o["server_name"],path_text(project),options.allow_write};
    const std::string head="\xEF\xBB\xBF// external comment 中文\r\n{\"model\":\"new/provider\",\"mcp\":"+(options.major==1?std::string(""):std::string("{\"servers\":"));
    const std::string part="{\"unrelated\":{\"type\":\"remote\",\"url\":\"https://unused.invalid\"},/*preserve*/";
    const std::string tail="/*trivia*/}"+(options.major==1?std::string(""):std::string("}"))+",\"extras\":[[1,2,],],}\r\n";
    const auto raw=head+part+Json(s.name).dump()+":"+server_definition(s).dump()+","+tail;
    // The member was last with a trailing comma: retain previous comma and all trivia.
    const auto baseline=head+part+tail;put(config(),raw);return {raw,baseline};
  }
};
static void lifecycle(){
  for(int major:{1,2})for(bool allow:{false,true}){
    Fixture f(major,allow);auto original_owner=read_image(f.owner(),state_limit);auto exact_before=read_image(f.config(),config_limit);
    auto no=f.inst->plan("reconcile");verify(no.result["would_change"]==false,"exact registration is no-op");f.inst->apply("reconcile",no.result["plan_sha256"]);
    verify(read_image(f.owner(),state_limit)==original_owner&&read_image(f.config(),config_limit)==exact_before,"no-op exact bytes");
    auto [edited,baseline]=f.edited();reject([&]{f.inst->plan("install");},"default reinstall does not adopt edited text");reject([&]{f.inst->plan("uninstall");},"default uninstall does not overwrite external edit");
    auto plan=f.inst->plan("reconcile");verify(read_image(f.config(),config_limit)==edited&&read_image(f.owner(),state_limit)==original_owner,"preview is read-only");
    verify(plan.result["format"]==major&&plan.result["write_enabled"]==allow,"reconcile cannot change format/access");
    put(f.config(),edited+"//later");reject([&]{f.inst->apply("reconcile",plan.result["plan_sha256"]);},"stale preview refused");
    verify(!fs::exists(f.pending()),"stale rejection does not journal");put(f.config(),edited);
    f.inst->apply("reconcile",plan.result["plan_sha256"]);verify(f.inst->status()["configuration_matches"]==true,"reconciled registration validated");
    auto owned=strict(*read_image(f.owner(),state_limit));verify(image_from(owned["before"],config_limit)==baseline,"new undo baseline preserves exact external bytes");
    auto repeated=f.inst->plan("reconcile");verify(repeated.result["would_change"]==false,"reconciliation repeated no-op");
    auto audit=audit_registration({f.project,major,allow?1:0});verify(audit["registered_bytes_verified"]==true,"existing audit accepts coherent reconciled ownership");
    auto updated=f.options;updated.allow_write=!allow;Installer switcher(updated);auto update=switcher.plan("install");switcher.apply("install",update.result["plan_sha256"]);
    verify(switcher.status()["write_enabled"]==!allow,"ordinary explicit access update remains usable");
    auto un=switcher.plan("uninstall");switcher.apply("uninstall",un.result["plan_sha256"]);
    verify(read_image(f.config(),config_limit)==baseline&&!fs::exists(f.owner()),"final uninstall preserves new unowned baseline exactly");
  }
}
static void recovery(){
  for(int major:{1,2})for(int cut:{1,2,3}){
    Fixture f(major,false);auto old_owner=read_image(f.owner(),state_limit);auto [edited,baseline]=f.edited();auto plan=f.inst->plan("reconcile");int completed=0;
    reject([&]{f.inst->apply("reconcile",plan.result["plan_sha256"],[&](const fs::path& dest,const Image& im){atomic_write(dest,im);if(++completed==cut)throw Error("fixture_interrupt");});},"interrupt after each durable image");
    auto journal=read_image(f.pending(),journal_limit);verify(journal&&strict(*journal)["schema"]=="qbrain-opencode-reconcile-journal-v2","distinct reconcile journal");
    auto known_config=read_image(f.config(),config_limit);put(f.config(),*known_config+"//unknown");reject([&]{f.inst->plan("recover");},"recovery refuses unknown current image");put(f.config(),*known_config);
    auto corrupt=strict(*journal,journal_limit);corrupt["changes"][0]["before"]=image_json(edited+"//tampered-journal");put(f.pending(),corrupt.dump());reject([&]{f.inst->plan("recover");},"recovery reconstructs pair rather than trusting hashes");put(f.pending(),*journal);
    auto r=f.inst->plan("recover");f.inst->apply("recover",r.result["plan_sha256"]);
    verify(read_image(f.config(),config_limit)==edited&&read_image(f.owner(),state_limit)==old_owner&&!fs::exists(f.pending()),"recovery restores pre-operation external edit and prior owner");
    // Reapprove, finish and then uninstall: recovered conflict remains explicitly reconcilable.
    auto p=f.inst->plan("reconcile");f.inst->apply("reconcile",p.result["plan_sha256"]);auto u=f.inst->plan("uninstall");f.inst->apply("uninstall",u.result["plan_sha256"]);
    verify(read_image(f.config(),config_limit)==baseline,"recovered lifecycle ends with preserved external content");
  }
  Fixture f(1,false);auto [edited,baseline]=f.edited();auto original_owner=read_image(f.owner(),state_limit);auto p=f.inst->plan("reconcile");int n=0;
  reject([&]{f.inst->apply("reconcile",p.result["plan_sha256"],[&](const fs::path& dest,const Image& im){atomic_write(dest,im);if(++n==1)throw Error("fixture");});},"stage recovery setup");
  auto data=strict(*read_image(f.pending(),journal_limit),journal_limit);auto temp=staging(f.config());put(temp,"unknown-partial");
  reject([&]{f.inst->plan("recover");},"unknown partial stage retained");verify(read_image(temp,config_limit)=="unknown-partial","unknown stage not deleted");
  auto after=image_from(data["changes"][0]["after"],config_limit);put(temp,*after);auto r=f.inst->plan("recover");put(temp,edited);
  reject([&]{f.inst->apply("recover",r.result["plan_sha256"]);},"stale recovery stage refuses");r=f.inst->plan("recover");f.inst->apply("recover",r.result["plan_sha256"]);
  verify(!fs::exists(temp)&&read_image(f.config(),config_limit)==edited&&read_image(f.owner(),state_limit)==original_owner,"known stage explicitly recovered");
}
int main(){try{parser();lifecycle();recovery();std::cout<<Json{{"schema","qbrain-n48c-unit-v1"},{"result","PASS"},{"checks",checks},{"host_started",false}}.dump()<<'\n';return 0;}catch(const std::exception& e){std::cerr<<e.what()<<" after "<<checks<<'\n';return 1;}}
