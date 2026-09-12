// Production queue, storage and parser; only HTTP is replaced by a deterministic
// in-process provider. This executable never contacts a network service.
#include "qbrain/jobs/embedding_queue.hpp"
#include "qbrain/ai/http_client.hpp"
#include "qbrain/ai/embedding_policy.hpp"
#include "qbrain/util/paths.hpp"
#include <nlohmann/json.hpp>
#include <atomic>
#include <barrier>
#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <filesystem>
#include <functional>
#include <iostream>
#include <mutex>
#include <stdexcept>
#include <thread>

using J=nlohmann::json;
namespace fs=std::filesystem;
namespace {
int checks=0;
std::vector<std::string> scenarios;
std::vector<std::size_t> calls,wire_bytes;
std::function<void()> during_provider;
int fail_call=0;
void check(bool condition,const char* label) {
  if (!condition) throw std::runtime_error(label);
  ++checks;
}
struct Fixture {
  fs::path dir;
  qbrain::Brain b,peer;
  explicit Fixture(const std::string& label) {
    static std::atomic<int> serial{0};
    dir=fs::temp_directory_path()/("qbrain-queue-"+label+"-"+
        std::to_string(std::chrono::steady_clock::now().time_since_epoch().count())+"-"+
        std::to_string(serial.fetch_add(1)));
    fs::create_directories(dir);
    b.open_at(qbrain::util::path_to_utf8(dir/"brain.db"));
    b.save_config_value("embed.auto","false",false);
    peer.open_at(qbrain::util::path_to_utf8(dir/"brain.db"));
    for (auto* brain:{&b,&peer}) {
      brain->config().embedding_model="fixture-model";
      brain->config().embedding_dimensions=3;
      brain->config().embedding_api_key="fixture-key-not-a-secret";
    }
    calls.clear();wire_bytes.clear();during_provider={};fail_call=0;
  }
  ~Fixture() {
    during_provider={};peer.close();b.close();
    std::error_code error;fs::remove_all(dir,error);
  }
  int64_t page(const std::string& slug,std::size_t chunks=1) {
    qbrain::PageInput in;in.slug=slug;in.title="fixture";in.body="synthetic test input";
    const auto p=b.put_page(in);b.replace_chunks(p.id,std::vector<std::string>(chunks,"synthetic text"));return p.id;
  }
  int64_t queue(int64_t page_id,const std::string& queue="default") {
    return qbrain::jobs::submit_job(b,"embed",J({{"page_id",page_id}}).dump(),queue);
  }
  J job(int64_t id) {
    auto job=qbrain::jobs::get_job(b,id);check(job.has_value(),"job exists");
    return {{"status",job->status},{"attempts",job->attempts},{"result",job->result_json.empty()?J():J::parse(job->result_json)}};
  }
  int64_t embedded(int64_t page_id) {
    auto st=b.db().prepare("SELECT COUNT(*) FROM content_chunks WHERE page_id=? AND length(embedding)>0");
    st.bind_int(1,page_id);check(st.step(),"count query");return st.column_int(0);
  }
  int run(bool generic,int n=1) {
    return generic?qbrain::jobs::drain_jobs(b,n,"same-worker-label"):b.drain_embed_jobs(n);
  }
};
}
namespace qbrain::ai {
HttpResponse http_post_json(std::string_view,std::string_view,std::string_view,
    std::string_view request,int,std::size_t) {
  const auto body=J::parse(request);const auto size=body.at("input").size();
  check(size>0 && size<=EMBED_MAX_BATCH,"provider request count bounded");
  check(request.size()<=HTTP_MAX_REQUEST_BYTES,"provider JSON bytes bounded");
  calls.push_back(size);wire_bytes.push_back(request.size());
  if (during_provider) {auto callback=std::move(during_provider);during_provider={};callback();}
  if (fail_call && calls.size()==static_cast<std::size_t>(fail_call))
    return {503,{},"PRIVATE_PROVIDER_ERROR",HttpFailure::http_status};
  const auto dim=body.value("dimensions",3);
  J data=J::array();
  for (std::size_t i=0;i<size;++i)
    data.push_back({{"index",i},{"embedding",std::vector<double>(dim,0.5)}});
  return {200,J({{"model",body["model"]},{"data",data}}).dump(),{},HttpFailure::none};
}
}
namespace {
void paths(bool generic) {
  const std::string mode=generic?"generic":"automatic";
  auto scenario=[&](const char* name){scenarios.push_back(mode+": "+name);};
  {
    Fixture f("control");auto p=f.page("control");auto id=f.queue(p);
    check(f.run(generic)==1,"one-item return contract");auto j=f.job(id);
    check(j["status"]=="completed"&&j["result"]["chunks"]==1&&f.embedded(p)==1,"control stores one vector");
    scenario("one-item control");
  }
  {
    Fixture f("batch");auto p=f.page("large",2049);auto id=f.queue(p);
    check(f.run(generic)==(generic?1:2049),"large page return contract");auto j=f.job(id);
    check(calls==std::vector<std::size_t>({2048,1}),"2049 inputs split into two bounded batches");
    check(j["status"]=="completed"&&j["result"]["chunks"]==2049&&f.embedded(p)==2049,"all 2049 committed");
    scenario("QB-QUEUE-001: 2049 inputs");
  }
  {
    Fixture f("rechunk");auto p=f.page("replace");auto id=f.queue(p);
    during_provider=[&]{f.peer.replace_chunks(p,{"replacement"});};
    check(f.run(generic)==(generic?1:0),"stale return does not count non-writes");auto j=f.job(id);
    check(j["status"]=="failed"&&j["result"]["outcome"]=="stale"&&j["result"]["chunks"]==0&&f.embedded(p)==0,"rechunked response rejected");
    check(qbrain::jobs::retry_job(f.b,id),"stale explicitly retryable");f.run(generic);
    check(f.job(id)["status"]=="completed"&&f.embedded(p)==1,"explicit retry uses replacement chunks");
    scenario("QB-QUEUE-002: rechunk during response, explicit retry");
  }
  {
    Fixture f("deleted");auto p=f.page("deleted");auto id=f.queue(p);
    check(f.peer.soft_delete("deleted"),"delete before drain");f.run(generic);auto j=f.job(id);
    check(calls.empty()&&f.embedded(p)==0&&j["status"]=="cancelled"&&j["result"]["chunks"]==0,"deleted page never reaches provider");
    scenario("QB-QUEUE-003: deleted before dispatch");
  }
  {
    Fixture f("late-delete");auto p=f.page("late-delete");auto id=f.queue(p);
    during_provider=[&]{check(f.peer.soft_delete("late-delete"),"second connection delete during provider");};
    f.run(generic);auto j=f.job(id);
    check(calls.size()==1&&f.embedded(p)==0&&j["status"]=="cancelled","delete during provider discards response");
    scenario("deleted during dispatch, no lock across provider");
  }
  {
    Fixture f("counts");auto p=f.page("one"),p2=f.page("two");auto a=f.queue(p),b=f.queue(p2);
    check(f.run(generic,2)==2,"two jobs return");
    check(f.job(a)["result"]["chunks"]==1&&f.job(b)["result"]["chunks"]==1,"per-job count not invocation sum");
    scenario("QB-QUEUE-004: per-job counts");
  }
  {
    Fixture f("partial");auto p=f.page("partial",2049);auto id=f.queue(p);fail_call=2;
    check(f.run(generic)==(generic?1:2048),"partial return counts only committed batch");auto j=f.job(id);
    check(j["status"]=="failed"&&j["result"]["chunks"]==2048&&f.embedded(p)==2048,"first batch retained on later failure");
    check(j.dump().find("PRIVATE_PROVIDER_ERROR")==std::string::npos,"provider errors are constant and private");
    fail_call=0;check(qbrain::jobs::retry_job(f.b,id),"partial retry allowed");f.run(generic);
    check(calls==std::vector<std::size_t>({2048,1,1})&&f.embedded(p)==2049,"retry requests only pending chunk");
    check(f.job(id)["result"]["chunks"]==1,"retry count is this attempt's actual writes");
    scenario("partial failure and retry without resending committed batch");
  }
  {
    Fixture f("sqlfail");auto p=f.page("atomic",2);auto id=f.queue(p);
    f.b.db().exec("CREATE TRIGGER reject_second BEFORE UPDATE OF embedding ON content_chunks WHEN OLD.chunk_index=1 BEGIN SELECT RAISE(ABORT,'PRIVATE_SQL_ERROR'); END");
    f.run(generic);auto j=f.job(id);
    check(f.embedded(p)==0&&j["status"]=="failed"&&j["result"]["chunks"]==0,"current batch rolls back on SQL failure");
    check(j.dump().find("PRIVATE_SQL_ERROR")==std::string::npos,"no SQL exception echo");
    scenario("injected second-row write failure rolls back entire batch");
  }
  {
    Fixture f("changed-text");auto p=f.page("text-change",2);auto id=f.queue(p);
    during_provider=[&]{auto st=f.peer.db().prepare("UPDATE content_chunks SET text='edited' WHERE page_id=? AND chunk_index=1");st.bind_int(1,p);st.step_done();};
    f.run(generic);auto j=f.job(id);
    check(j["status"]=="failed"&&j["result"]["outcome"]=="stale"&&f.embedded(p)==0,"exact text guard and rollback of earlier row");
    scenario("in-place text change without new IDs");
  }
  for (bool pause:{false,true}) {
    Fixture f("cancel");auto p=f.page("cancel");auto id=f.queue(p);
    during_provider=[&]{check(pause?qbrain::jobs::pause_job(f.peer,id):qbrain::jobs::cancel_job(f.peer,id),"external transition");};
    f.run(generic);
    check(f.embedded(p)==0&&f.job(id)["status"]==(pause?"paused":"cancelled"),"late owner cannot revive pause/cancel");
    scenario(pause?"pause during provider":"cancel during provider");
  }
  {
    Fixture f("expire");auto p=f.page("expire");auto id=f.queue(p);
    during_provider=[&]{auto st=f.peer.db().prepare("UPDATE jobs SET lock_until='2000-01-01 00:00:00' WHERE id=?");st.bind_int(1,id);st.step_done();};
    f.run(generic);
    check(f.embedded(p)==0&&f.job(id)["status"]=="active","expired but unreclaimed claim cannot write");
    f.run(generic);
    check(f.embedded(p)==1&&f.job(id)["status"]=="completed","expired job reclaimed on later drain");
    scenario("lease expires before response and is reclaimed later");
  }
  {
    Fixture f("reassign");auto p=f.page("reassigned");auto id=f.queue(p);
    during_provider=[&]{
      auto st=f.peer.db().prepare("UPDATE jobs SET lock_until='2000-01-01 00:00:00' WHERE id=?");st.bind_int(1,id);st.step_done();
      auto claimed=qbrain::jobs::claim_job(f.peer,"new-owner",180000,"default",{"embed"});
      check(claimed.has_value(),"new owner claims expired attempt");
      check(qbrain::jobs::execute_embedding_job(f.peer,*claimed)==1,"new owner persists its response");
    };
    f.run(generic);auto j=f.job(id);
    check(calls.size()==2&&f.embedded(p)==1&&j["status"]=="completed"&&j["result"]["chunks"]==1,"old owner cannot overwrite new completion");
    scenario("lease reassignment and overlapping owner response");
  }
  {
    Fixture f("deleted-between");auto p=f.page("between",2049);auto id=f.queue(p);
    // A trigger deletes the page when batch 1's last vector is applied.
    f.b.db().exec("CREATE TRIGGER delete_between AFTER UPDATE OF embedding ON content_chunks WHEN NEW.chunk_index=2047 BEGIN UPDATE pages SET deleted_at='2026-09-12' WHERE id=NEW.page_id; END");
    f.run(generic);
    check(calls.size()==1&&f.job(id)["status"]=="cancelled","liveness checked before next batch");
    scenario("deleted between batches: no second request");
  }
  {
    Fixture f("invalidpayload");auto id=qbrain::jobs::submit_job(f.b,"embed","{\"page_id\":1.5}");
    f.run(generic);
    check(calls.empty()&&f.job(id)["status"]=="failed","malformed page identity no provider I/O");
    scenario("non-integral job identity fails before dispatch");
  }
  {
    Fixture f("huge");auto p=f.page("utf8");f.b.replace_chunks(p,{std::string("\xff",1)});auto id=f.queue(p);
    f.run(generic);
    check(calls.empty()&&f.job(id)["status"]=="failed","invalid UTF-8 never sent");
    scenario("invalid UTF-8 before network");
  }
}
int busy_timeout(qbrain::Brain& brain) {
  auto st=brain.db().prepare("PRAGMA busy_timeout");
  if (!st.step()) throw std::runtime_error("missing busy timeout");
  return static_cast<int>(st.column_int(0));
}
void simultaneous_claims() {
  {
    Fixture f("simultaneous");
    const auto old_a=busy_timeout(f.b),old_b=busy_timeout(f.peer);
    for (int i=0;i<128;++i) {
      auto id=qbrain::jobs::submit_job(f.b,"embed","{\"page_id\":1}");
      std::barrier ready(3);
      std::optional<qbrain::jobs::Job> one,two;
      std::exception_ptr e1,e2;
      const auto t1=qbrain::jobs::new_embedding_claim_token(),t2=qbrain::jobs::new_embedding_claim_token();
      std::thread x([&]{ready.arrive_and_wait();try{one=qbrain::jobs::claim_job(f.b,t1,180000,"default",{"embed"});}catch(...){e1=std::current_exception();}});
      std::thread y([&]{ready.arrive_and_wait();try{two=qbrain::jobs::claim_job(f.peer,t2,180000,"default",{"embed"});}catch(...){e2=std::current_exception();}});
      ready.arrive_and_wait();x.join();y.join();
      if (e1) std::rethrow_exception(e1);
      if (e2) std::rethrow_exception(e2);
      check(bool(one)!=bool(two),"simultaneous claim has exactly one winner");
      const auto job=qbrain::jobs::get_job(f.b,id);
      check(job&&job->status=="active"&&job->attempts==1,"one active attempt under simultaneous claim");
      check(job->lock_token==(one?t1:t2),"simultaneous winner owns the token");
      check(qbrain::jobs::complete_job(f.b,id,job->lock_token,"{}"),"close simultaneous-claim round");
    }
    check(busy_timeout(f.b)==old_a&&busy_timeout(f.peer)==old_b,"both claim timeout settings restored");
    scenarios.push_back("128 simultaneous two-connection claim races: one winner");
  }
  {
    Fixture f("busy-bound");auto p=f.page("held-lock");auto id=f.queue(p);
    f.b.db().exec("PRAGMA busy_timeout=50");
    f.peer.db().exec("BEGIN IMMEDIATE");
    const auto start=std::chrono::steady_clock::now();
    bool failed=false;
    try {qbrain::jobs::claim_job(f.b,"contended",180000,"default",{"embed"});}
    catch(const std::exception&){failed=true;}
    const auto elapsed=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count();
    f.peer.db().exec("ROLLBACK");
    check(failed&&elapsed<1500,"held writer causes bounded failure, never unbounded retry");
    check(busy_timeout(f.b)==50,"short configured timeout restored on exception");
    check(f.job(id)["status"]=="waiting"&&calls.empty(),"busy claim failure leaves job pending without provider call");
    f.run(false);
    check(f.embedded(p)==1&&busy_timeout(f.b)==50,"queue transaction restores caller timeout too");
    scenarios.push_back("held SQLite writer: bounded failure and timeout restoration");
  }
}

void bounds_and_overlap() {
  {
    Fixture f("bytes");auto p=f.page("bytes",2);
    f.b.replace_chunks(p,std::vector<std::string>(2,std::string(9*1024*1024,'"')));auto id=f.queue(p);
    f.run(false);
    check(calls==std::vector<std::size_t>({1,1})&&f.embedded(p)==2&&f.job(id)["status"]=="completed","escaped JSON byte batching, not raw byte truncation");
    scenarios.push_back("exact escaped-JSON byte batch split");
  }
  {
    Fixture f("single-oversize");auto p=f.page("too-big");
    f.b.replace_chunks(p,{std::string(6*1024*1024,'\0')});auto id=f.queue(p);
    f.run(false);
    check(calls.empty()&&f.job(id)["status"]=="failed"&&f.embedded(p)==0,"single escaped oversized input rejected");
    scenarios.push_back("single oversized escaped input: no provider call");
  }
  {
    Fixture f("dim");auto p=f.page("dim",16);auto id=f.queue(p);
    f.b.config().embedding_dimensions=16384;
    f.run(false);
    check(calls==std::vector<std::size_t>({15,1})&&f.embedded(p)==16&&f.job(id)["status"]=="completed","value budget respects maximum dimension");
    scenarios.push_back("maximum dimensionality and response value budget");
  }
  {
    Fixture f("unknown");auto p=f.page("unknown",16);auto id=f.queue(p);f.b.config().embedding_dimensions=0;
    f.run(false);
    check(calls==std::vector<std::size_t>({15,1})&&f.job(id)["status"]=="completed","unknown dimension uses conservative worst case");
    scenarios.push_back("unknown dimension conservative bounds");
  }
  {
    Fixture f("customqueue");auto p=f.page("custom");auto id=f.queue(p,"custom");
    check(f.b.drain_embed_jobs(1)==1&&f.job(id)["status"]=="completed","automatic drain preserves custom queues");
    scenarios.push_back("automatic all-queue compatibility");
  }
  {
    Fixture f("threads");auto p=f.page("threads");auto id=f.queue(p);
    std::mutex mutex;std::condition_variable cv;bool entered=false,release=false;
    std::exception_ptr error;int first=-1,second=-1;
    during_provider=[&]{
      std::unique_lock lock(mutex);entered=true;cv.notify_all();
      if (!cv.wait_for(lock,std::chrono::seconds(10),[&]{return release;})) throw std::runtime_error("provider test barrier timeout");
    };
    std::thread worker([&]{try{first=f.b.drain_embed_jobs(1);}catch(...){error=std::current_exception();}});
    {
      std::unique_lock lock(mutex);
      const bool ready=cv.wait_for(lock,std::chrono::seconds(10),[&]{return entered;});
      if (!ready) {release=true;cv.notify_all();lock.unlock();worker.join();throw std::runtime_error("worker did not enter provider");}
    }
    try {second=qbrain::jobs::drain_jobs(f.peer,1,"same-worker-label");}
    catch(...) {{std::lock_guard lock(mutex);release=true;}cv.notify_all();worker.join();throw;}
    {std::lock_guard lock(mutex);release=true;}cv.notify_all();worker.join();
    if (error)std::rethrow_exception(error);
    check(first==1&&second==0&&calls.size()==1,"two threads/entry points execute one live claim once");
    check(f.embedded(p)==1&&f.job(id)["result"]["chunks"]==1,"one terminal count for overlapping workers");
    scenarios.push_back("two connections and threads: live claim exclusion");
  }
}
}
int main() {
  try {
#ifdef _WIN32
    _putenv_s("QBRAIN_EMBED_MOCK","");
#else
    unsetenv("QBRAIN_EMBED_MOCK");
#endif
    paths(false);paths(true);bounds_and_overlap();simultaneous_claims();
    std::cout<<J({{"result","PASS"},{"checks",checks},{"scenarios",scenarios},
                 {"scenario_count",scenarios.size()},{"provider","in-process synthetic HTTP replacement"},
                 {"real_provider_calls",false},{"production_queue_and_storage",true}}).dump()<<'\n';
    return 0;
  } catch(const std::exception& e) {std::cerr<<"[FAIL] embedding queue: "<<e.what()<<'\n';return 1;}
}
