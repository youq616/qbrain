// Diagnostic executable only: same transport with compile-time counters enabled.
#include "../../src/qbrain/ai/http_client.cpp"
#include <tlhelp32.h>
#include <nlohmann/json.hpp>
#include <iostream>
#include <thread>

using J = nlohmann::json;
J snapshot() {
  using namespace qbrain::ai;
  DWORD handles=0;
  if (!GetProcessHandleCount(GetCurrentProcess(), &handles)) throw std::runtime_error("process handles");
  HANDLE snap=CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD,0);
  if(snap==INVALID_HANDLE_VALUE) throw std::runtime_error("thread snapshot");
  THREADENTRY32 entry{};entry.dwSize=sizeof(entry);int threads=0;
  if(Thread32First(snap,&entry)) do {
    if(entry.th32OwnerProcessID==GetCurrentProcessId()) ++threads;
  } while(Thread32Next(snap,&entry));
  CloseHandle(snap);
  return {{"process_handles",handles},{"process_threads",threads},
          {"owned_handles",diagnostic_handles.load()},{"async_states",diagnostic_states.load()},
          {"created_handles",diagnostic_created.load()},{"closed_handles",diagnostic_closed.load()},
          {"close_errors",diagnostic_close_errors.load()},{"final_callbacks",diagnostic_final_callbacks.load()}};
}
int main(int argc,char** argv) {
  try {
    if(argc!=2) throw std::runtime_error("Usage: diagnostic loopback-base");
    J report={{"initial",snapshot()},{"batches",J::array()}};
    int failures=0;long requests=0;
    for(int round=0;round<8;++round) {
      J batch={{"round",round},{"samples",J::array()}};
      for(int i=0;i<32;++i) {
        auto r=qbrain::ai::http_post_json(argv[1],"/stall-body","fixture","{}",40,1024);
        if(r.failure!=qbrain::ai::HttpFailure::timeout || r.status!=0 || !r.body.empty()) ++failures;
        ++requests;
      }
      batch["samples"].push_back(snapshot());
      std::this_thread::sleep_for(std::chrono::milliseconds(250));
      batch["samples"].push_back(snapshot());
      std::this_thread::sleep_for(std::chrono::milliseconds(1750));
      batch["samples"].push_back(snapshot());
      std::cerr<<batch.dump()<<'\n';
      report["batches"].push_back(std::move(batch));
    }
    std::this_thread::sleep_for(std::chrono::seconds(30));
    const auto final=snapshot();
    report["after_fixed_30s"]=final;report["requests"]=requests;report["unexpected_results"]=failures;
    const bool released=final["owned_handles"]==0 && final["async_states"]==0 &&
        final["close_errors"]==0 && final["created_handles"]==final["closed_handles"] &&
        final["final_callbacks"]==requests && failures==0;
    report["owned_lifetimes_released"]=released;
    report["note"]="Diagnostic only; original process-handle acceptance is unchanged.";
    std::cout<<report.dump(2)<<'\n';
    return released ? 0 : 1;
  } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
