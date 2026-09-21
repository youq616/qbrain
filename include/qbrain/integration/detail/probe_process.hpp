#pragma once
// N48D owned subprocess transport. No shell, user-brain lookup or raw error output.
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#include "qbrain/util/paths.hpp"
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <cerrno>
#include <fcntl.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <spawn.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

namespace qbrain::integration::probe {
namespace fs=std::filesystem;
struct Error:std::runtime_error {using std::runtime_error::runtime_error;};
inline void require(bool value,const char* code){if(!value)throw Error(code);}
using Clock=std::chrono::steady_clock;
inline constexpr std::size_t frame_cap=65536,stdout_cap=262144,stderr_cap=65536;
inline constexpr int cleanup_ms=2000;

#ifdef _WIN32
struct Handle {
  HANDLE value=nullptr;
  Handle()=default; explicit Handle(HANDLE h):value(h){}
  Handle(const Handle&)=delete;Handle& operator=(const Handle&)=delete;
  ~Handle(){reset();}
  void reset(HANDLE h=nullptr){if(value&&value!=INVALID_HANDLE_VALUE)CloseHandle(value);value=h;}
};
inline std::wstring crt_quote(const std::wstring& value){
  std::wstring out=L"\"";std::size_t slashes=0;
  for(wchar_t c:value){if(c==L'\\'){++slashes;continue;}
    out.append(c==L'"'?2*slashes+1:slashes,L'\\');out+=c;slashes=0;}
  out.append(2*slashes,L'\\');out+=L'"';return out;
}
#else
struct Fd {
  int value=-1;
  Fd()=default;explicit Fd(int v):value(v){}
  Fd(const Fd&)=delete;Fd& operator=(const Fd&)=delete;
  ~Fd(){reset();}
  void reset(int v=-1){if(value>=0)::close(value);value=v;}
};
// Suppress only this thread's newly generated pipe signal; retain its previous
// mask and pre-existing pending SIGPIPE. Never change a global signal handler.
struct PipeSignal {
  sigset_t old{},one{};bool consume=false;
  PipeSignal(){sigemptyset(&one);sigaddset(&one,SIGPIPE);
    require(pthread_sigmask(SIG_BLOCK,&one,&old)==0,"process_signal_setup");
    sigset_t pending{};sigpending(&pending);consume=!sigismember(&old,SIGPIPE)&&!sigismember(&pending,SIGPIPE);}
  ~PipeSignal(){if(consume){timespec zero{};while(sigtimedwait(&one,nullptr,&zero)<0&&errno==EINTR){}}
    pthread_sigmask(SIG_SETMASK,&old,nullptr);}
};
#endif

class Process {
#ifdef _WIN32
  Handle input_,output_,error_,process_,job_;
#else
  Fd input_,output_,error_;pid_t pid_=-1;bool identity_lost_=false;
#endif
  bool started_=false,cleaned_=false,out_eof_=false,err_eof_=false;
  std::optional<int> exit_;
  std::size_t out_bytes_=0,err_bytes_=0,input_bytes_=0;bool cleanup_ok_=true;
  Clock::time_point deadline_{};
  std::string pending_;
  void timecheck()const {require(Clock::now()<deadline_,"protocol_timeout");}
  void append(const char* data,std::size_t n,bool standard){
    auto& count=standard?out_bytes_:err_bytes_;count+=n;
    require(count<=(standard?stdout_cap:stderr_cap),standard?"stdout_limit":"stderr_limit");
    if(standard){pending_.append(data,n);
      auto last=pending_.find_last_of('\n');
      const auto unfinished=last==std::string::npos?pending_.size():pending_.size()-last-1;
      require(unfinished<=frame_cap,"frame_limit");}
  }
#ifdef _WIN32
  void drain(Handle& handle,bool& eof,bool standard){
    if(eof||!handle.value)return;
    for(int i=0;i<4;++i){DWORD available=0;
      if(!PeekNamedPipe(handle.value,nullptr,0,nullptr,&available,nullptr)){
        require(GetLastError()==ERROR_BROKEN_PIPE,"pipe_read_error");eof=true;handle.reset();return;}
      if(!available)return;std::array<char,8192> block{};DWORD read=0;
      require(ReadFile(handle.value,block.data(),(std::min)({available,DWORD(block.size()),DWORD((standard?stdout_cap:stderr_cap)-(standard?out_bytes_:err_bytes_)+1)}),&read,nullptr)!=0,"pipe_read_error");
      if(!read){eof=true;handle.reset();return;}append(block.data(),read,standard);
    }
  }
#else
  void drain(Fd& fd,bool& eof,bool standard){
    if(eof||fd.value<0)return;
    for(int i=0;i<4;++i){std::array<char,8192> block{};const auto n=::read(fd.value,block.data(),(std::min)(block.size(),(standard?stdout_cap:stderr_cap)-(standard?out_bytes_:err_bytes_)+1));
      if(n>0){append(block.data(),std::size_t(n),standard);continue;}
      if(n==0){eof=true;fd.reset();return;}
      if(errno==EINTR){--i;continue;}
      require(errno==EAGAIN||errno==EWOULDBLOCK,"pipe_read_error");return;}
  }
#endif
  void pump(){timecheck();drain(output_,out_eof_,true);drain(error_,err_eof_,false);observe_exit();}
  void pause(){std::this_thread::sleep_for(std::chrono::milliseconds(2));}
 public:
  Process()=default;Process(const Process&)=delete;Process& operator=(const Process&)=delete;
  ~Process(){cleanup();}
  bool started()const{return started_;}
  std::optional<int> exit_code()const{return exit_;}
  std::size_t stdout_bytes()const{return out_bytes_;}
  std::size_t stderr_bytes()const{return err_bytes_;}
  void start(const fs::path& binary,const fs::path& home,const std::vector<std::string>& args,
             const std::map<std::string,std::string>& env,int milliseconds){
    require(!started_,"process_already_started");deadline_=Clock::now()+std::chrono::milliseconds(milliseconds);
    require(binary.is_absolute()&&home.is_absolute(),"process_absolute_paths");
#ifdef _WIN32
    SECURITY_ATTRIBUTES sa{sizeof(sa),nullptr,TRUE};Handle ci,co,ce;
    HANDLE r=nullptr,w=nullptr;
    auto pipe=[&](){require(CreatePipe(&r,&w,&sa,16384)!=0,"pipe_create_error");};
    pipe();ci.reset(r);input_.reset(w);
    pipe();output_.reset(r);co.reset(w);
    pipe();error_.reset(r);ce.reset(w);
    for(auto* h:{&input_,&output_,&error_})require(SetHandleInformation(h->value,HANDLE_FLAG_INHERIT,0)!=0,"pipe_inherit_error");
    SIZE_T size=0;InitializeProcThreadAttributeList(nullptr,1,0,&size);
    std::vector<unsigned char> storage(size);auto attrs=reinterpret_cast<LPPROC_THREAD_ATTRIBUTE_LIST>(storage.data());
    require(InitializeProcThreadAttributeList(attrs,1,0,&size)!=0,"process_attributes_error");
    struct Guard{LPPROC_THREAD_ATTRIBUTE_LIST p;~Guard(){DeleteProcThreadAttributeList(p);}} guard{attrs};
    std::array<HANDLE,3> inherited={ci.value,co.value,ce.value};
    require(UpdateProcThreadAttribute(attrs,0,PROC_THREAD_ATTRIBUTE_HANDLE_LIST,inherited.data(),sizeof(inherited),nullptr,nullptr)!=0,"process_attributes_error");
    STARTUPINFOEXW startup{};startup.StartupInfo.cb=sizeof(startup);startup.lpAttributeList=attrs;
    startup.StartupInfo.dwFlags=STARTF_USESTDHANDLES;startup.StartupInfo.hStdInput=ci.value;
    startup.StartupInfo.hStdOutput=co.value;startup.StartupInfo.hStdError=ce.value;
    std::wstring command=crt_quote(binary.wstring());
    for(const auto& arg:args){command+=L' ';command+=crt_quote(util::utf8_to_wide(arg));}
    std::wstring environment;
    // Keys supplied by this module are fixed ASCII and map order is sorted.
    for(const auto& [k,v]:env){environment+=util::utf8_to_wide(k+"="+v);environment+=L'\0';}
    environment+=L'\0';
    job_.reset(CreateJobObjectW(nullptr,nullptr));require(job_.value!=nullptr,"job_create_error");
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    require(SetInformationJobObject(job_.value,JobObjectExtendedLimitInformation,&limits,sizeof(limits))!=0,"job_config_error");
    PROCESS_INFORMATION child{};
    require(CreateProcessW(binary.c_str(),command.data(),nullptr,nullptr,TRUE,
      CREATE_SUSPENDED|CREATE_NO_WINDOW|CREATE_UNICODE_ENVIRONMENT|EXTENDED_STARTUPINFO_PRESENT,
      environment.data(),home.c_str(),&startup.StartupInfo,&child)!=0,"process_start_error");
    process_.reset(child.hProcess);Handle thread(child.hThread);started_=true;
    if(!AssignProcessToJobObject(job_.value,process_.value)){
      TerminateProcess(process_.value,1);WaitForSingleObject(process_.value,cleanup_ms);throw Error("job_assign_error");}
    require(ResumeThread(thread.value)!=DWORD(-1),"process_resume_error");
#else
#if defined(__linux__) && defined(__GLIBC__) && __GLIBC_PREREQ(2,34)
    struct sigaction policy{};require(sigaction(SIGCHLD,nullptr,&policy)==0&&policy.sa_handler==SIG_DFL&&!(policy.sa_flags&SA_NOCLDWAIT),"unsupported_reaping_policy");
    Fd ci,co,ce;int fds[2];
    auto pipe=[&](){
      require(::pipe2(fds,O_CLOEXEC)==0,"pipe_create_error");
      for(int i=0;i<2;++i)if(fds[i]<3){const int next=fcntl(fds[i],F_DUPFD_CLOEXEC,3);
        if(next<0){::close(fds[0]);::close(fds[1]);throw Error("pipe_descriptor_error");}
        ::close(fds[i]);fds[i]=next;}
    };
    pipe();ci.reset(fds[0]);input_.reset(fds[1]);pipe();output_.reset(fds[0]);co.reset(fds[1]);pipe();error_.reset(fds[0]);ce.reset(fds[1]);
    posix_spawn_file_actions_t actions;require(posix_spawn_file_actions_init(&actions)==0,"process_actions_error");
    struct A{posix_spawn_file_actions_t* p;~A(){posix_spawn_file_actions_destroy(p);}} action_guard{&actions};
    for(auto pair:{std::pair{ci.value,STDIN_FILENO},std::pair{co.value,STDOUT_FILENO},std::pair{ce.value,STDERR_FILENO}})
      require(posix_spawn_file_actions_adddup2(&actions,pair.first,pair.second)==0,"process_actions_error");
    require(posix_spawn_file_actions_addclosefrom_np(&actions,3)==0&&posix_spawn_file_actions_addchdir_np(&actions,home.c_str())==0,"process_actions_error");
    posix_spawnattr_t attr;require(posix_spawnattr_init(&attr)==0,"process_attributes_error");
    struct B{posix_spawnattr_t* p;~B(){posix_spawnattr_destroy(p);}} attribute_guard{&attr};
    sigset_t none,defaults;sigemptyset(&none);sigemptyset(&defaults);sigaddset(&defaults,SIGPIPE);
    require(posix_spawnattr_setflags(&attr,POSIX_SPAWN_SETPGROUP|POSIX_SPAWN_SETSIGMASK|POSIX_SPAWN_SETSIGDEF)==0&&
      posix_spawnattr_setpgroup(&attr,0)==0&&posix_spawnattr_setsigmask(&attr,&none)==0&&posix_spawnattr_setsigdefault(&attr,&defaults)==0,"process_attributes_error");
    std::vector<std::string> arguments{binary.string()},environment;
    arguments.insert(arguments.end(),args.begin(),args.end());for(const auto& [k,v]:env)environment.push_back(k+"="+v);
    std::vector<char*> argv,envp;for(auto& v:arguments)argv.push_back(v.data());argv.push_back(nullptr);
    for(auto& v:environment)envp.push_back(v.data());envp.push_back(nullptr);
    const int rc=posix_spawn(&pid_,binary.c_str(),&actions,&attr,argv.data(),envp.data());
    if(rc){pid_=-1;throw Error("process_start_error");}started_=true;
    for(int fd:{input_.value,output_.value,error_.value})require(fcntl(fd,F_SETFL,fcntl(fd,F_GETFL)|O_NONBLOCK)==0,"pipe_nonblocking_error");
#else
    (void)args;(void)env;throw Error("process_platform_unsupported");
#endif
#endif
  }
  void observe_exit(){
    if(!started_||exit_)return;
#ifdef _WIN32
    const DWORD state=WaitForSingleObject(process_.value,0);require(state!=WAIT_FAILED,"process_observation_error");
    if(state==WAIT_OBJECT_0){DWORD code=0;require(GetExitCodeProcess(process_.value,&code)!=0,"process_observation_error");exit_=static_cast<int>(code);}
#else
    siginfo_t info{};int rc;do{rc=waitid(P_PID,pid_,&info,WEXITED|WNOHANG|WNOWAIT);}while(rc<0&&errno==EINTR);
    if(rc<0&&errno==ECHILD)identity_lost_=true;
    require(rc==0,"process_observation_error");
    if(info.si_pid==pid_)exit_=info.si_code==CLD_EXITED?info.si_status:128+info.si_status;
#endif
  }
  void send(const std::string& text){
    // Fixed protocol requests are collectively <2KiB, less than our Windows
    // pipe capacity; never expose this as an arbitrary unbounded writer.
    require(!text.empty()&&text.size()<=1024&&text.find('\n')==text.size()-1,"request_bound");input_bytes_+=text.size();require(input_bytes_<=2048,"request_total_bound");timecheck();
#ifdef _WIN32
    DWORD wrote=0;require(input_.value&&WriteFile(input_.value,text.data(),DWORD(text.size()),&wrote,nullptr)&&wrote==text.size(),"pipe_write_error");
#else
    PipeSignal signal;std::size_t at=0;
    while(at<text.size()) {timecheck();const auto n=::write(input_.value,text.data()+at,text.size()-at);
      if(n>0){at+=std::size_t(n);continue;}if(n<0&&errno==EINTR)continue;
      if(n<0&&(errno==EAGAIN||errno==EWOULDBLOCK)){pump();pause();continue;}throw Error("pipe_write_error");}
#endif
  }
  std::optional<std::string> line(){
    const auto at=pending_.find('\n');if(at==std::string::npos)return {};
    require(at<=frame_cap,"frame_limit");std::string out=pending_.substr(0,at);pending_.erase(0,at+1);
    if(!out.empty()&&out.back()=='\r')out.pop_back();require(!out.empty(),"empty_frame");return out;
  }
  std::string receive(){
    for(;;){timecheck();if(auto value=line())return *value;pump();if(auto value=line())return *value;
      require(!out_eof_,pending_.empty()?"unexpected_eof":"incomplete_frame");pause();}
  }
  void shutdown(){
    input_.reset();
    for(;;){pump();require(pending_.empty(),"trailing_output");
      if(exit_&&out_eof_&&err_eof_){require(*exit_==0,"nonzero_exit");return;}pause();}
  }
  bool cleanup() noexcept {
    if(cleaned_)return cleanup_ok_;
    input_.reset();output_.reset();error_.reset();bool ok=true;
#ifdef _WIN32
    if(started_&&process_.value){
      if(job_.value)TerminateJobObject(job_.value,1);
      // Also covers the suspended child before assignment could succeed.
      if(WaitForSingleObject(process_.value,0)==WAIT_TIMEOUT)TerminateProcess(process_.value,1);
      ok=WaitForSingleObject(process_.value,cleanup_ms)==WAIT_OBJECT_0;
    }
    process_.reset();job_.reset();
#else
    if(pid_>0&&identity_lost_){ok=false;}
    else if(pid_>0){
      // Do not reap until AFTER group cleanup: reserved PID prevents reuse.
      if(::kill(-pid_,SIGKILL)<0&&errno!=ESRCH)ok=false;
      const auto end=Clock::now()+std::chrono::milliseconds(cleanup_ms);
      for(;;){int status=0;const auto r=::waitpid(pid_,&status,WNOHANG);
        if(r==pid_){pid_=-1;break;}if(r<0&&errno==EINTR)continue;
        if(r<0){ok=false;break;}if(Clock::now()>=end){ok=false;break;}
        std::this_thread::sleep_for(std::chrono::milliseconds(2));}
    }
#endif
    cleaned_=true;cleanup_ok_=ok;return ok;
  }
};
} // namespace qbrain::integration::probe
