// Independently authored outcome probes. Mutations are scheduled by the internal
// writer dependency, not a production flag or claims of all possible schedules.
#include "qbrain/integration/opencode_install.hpp"
#include <chrono>
#include <memory>
using namespace qbrain::integration::opencode;
static int checks=0;
static void check(bool v,const char* n){if(!v)throw std::runtime_error(n);++checks;}
static void save(const fs::path& p,const std::string& x){fs::create_directories(p.parent_path());std::ofstream o(p,std::ios::binary);o<<x;need(o.good(),"test_file");}
struct F{
  fs::path root,project,exe;std::unique_ptr<Installer> actor;
  explicit F(int version){root=fs::temp_directory_path()/("opencode-race-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));fs::create_directories(root);
#ifdef _WIN32
    _wputenv_s(L"LOCALAPPDATA",(root/"home").c_str());
#else
    setenv("HOME",(root/"home").c_str(),1);
#endif
    project=root/"project";fs::create_directory(project);exe=root/"fixture.exe";save(exe,"fixture-not-executed");fs::permissions(exe,fs::perms::owner_all);
    save(project/"opencode.jsonc","{\"user\":\"before\"}\n");actor=std::make_unique<Installer>(Options{project,exe,version,"scope",false});}
  ~F(){std::error_code ec;fs::remove_all(root,ec);}
  fs::path config(){return project/"opencode.jsonc";}fs::path state(){return actor->state_directory()/"owner.json";}fs::path log(){return actor->state_directory()/"pending.json";}
  fs::path target(int i){return i==0?config():i==1?state():log();}
  void install(){auto p=actor->plan("install");actor->apply("install",p.result["plan_sha256"]);}
};
static void forward(const std::string& op){
  for(int major:{1,2})for(int cut:{1,2,3})for(int target:{0,1,2}){
    F f(major);if(op=="reconcile"){f.install();save(f.config(),*read_image(f.config(),config_limit)+"// approved external comment\n");}
    auto p=f.actor->plan(op);int writes=0;const std::string unexpected="{\"user\":\"noncooperating-write\"}\n";bool rejected=false;
    try{f.actor->apply(op,p.result["plan_sha256"],[&](const fs::path& dest,const Image& image){
      atomic_write(dest,image);if(++writes==cut)save(f.target(target),unexpected);
    });}catch(const Error&){rejected=true;}
    check(rejected,"unknown external edit must reject completion");
    check(read_image(f.target(target),journal_limit)==unexpected,"unknown external edit must not be overwritten");
    check(fs::exists(f.log()),"rejected transaction preserves recovery evidence");
  }
}
static void recovery(){
  for(int major:{1,2})for(int target:{0,1,2})for(int cut:{1,2}){
    F f(major);f.install();save(f.config(),*read_image(f.config(),config_limit)+"// keep external\n");auto p=f.actor->plan("reconcile");int n=0;
    try{f.actor->apply("reconcile",p.result["plan_sha256"],[&](const fs::path& dest,const Image& image){atomic_write(dest,image);if(++n==3)throw Error("cut");});}catch(const Error&){}
    check(n==3,"recovery fixture reaches both destinations");auto r=f.actor->plan("recover");int written=0;bool rejected=false;const std::string external="{\"user\":\"edit-during-recovery\"}\n";
    try{f.actor->apply("recover",r.result["plan_sha256"],[&](const fs::path& dest,const Image& image){atomic_write(dest,image);if(++written==cut)save(f.target(target),external);});}catch(const Error&){rejected=true;}
    check(rejected,"recovery stops on a changed destination or journal");check(read_image(f.target(target),journal_limit)==external,"recovery preserves unknown image");
    check(fs::exists(f.log()),"recovery conflict retains journal");
  }
}
static void journal_stage(){
  for(int major:{1,2}) {
    F f(major);f.install();save(f.config(),*read_image(f.config(),config_limit)+"// external baseline\n");
    auto p=f.actor->plan("reconcile");int n=0;
    try{f.actor->apply("reconcile",p.result["plan_sha256"],[&](const fs::path& dest,const Image& im){atomic_write(dest,im);if(++n==3)throw Error("cut");});}catch(const Error&){}
    check(n==3,"journal-stage fixture reaches both destinations");
    const auto config=read_image(f.config(),config_limit),owner=read_image(f.state(),state_limit),log=read_image(f.log(),journal_limit);
    save(staging(f.log()),"unknown-external-journal-stage");bool refused=false;
    try{auto recovery=f.actor->plan("recover");f.actor->apply("recover",recovery.result["plan_sha256"]);}catch(const Error&){refused=true;}
    check(refused,"unknown journal stage refuses recovery");
    check(read_image(f.config(),config_limit)==config&&read_image(f.state(),state_limit)==owner,
      "unknown journal stage refuses before mutating either destination");
    check(read_image(f.log(),journal_limit)==log&&read_image(staging(f.log()),journal_limit)=="unknown-external-journal-stage",
      "unknown journal and stage retained exactly");
  }
}
int main(int argc,char** argv){try{if(argc>1&&std::string(argv[1])=="--journal-stage-only")journal_stage();else{forward("install");if(argc==1){forward("reconcile");recovery();journal_stage();}}
  std::cout<<Json{{"schema","qbrain-n48c-write-recheck-v1"},{"result","PASS"},{"checks",checks},{"host_started",false}}.dump()<<'\n';return 0;
}catch(const std::exception& e){std::cout<<Json{{"schema","qbrain-n48c-write-recheck-v1"},{"result","FAIL"},{"checks",checks},{"finding",e.what()},{"host_started",false}}.dump()<<'\n';return 1;}}
