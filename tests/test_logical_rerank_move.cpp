// N48X regression: fail allocations only during the real rerank call.
// No allocation hook is linked into product or existing test binaries.
#include "qbrain/search/rerank.hpp"
#include "qbrain/accounting/logical_observation.hpp"
#include <cstdlib>
#include <iostream>
#include <limits>
#include <new>
#include <utility>
#ifdef _WIN32
#include <malloc.h>
#endif

namespace fault {
thread_local bool enabled = false;
thread_local bool tracking = false;
thread_local std::size_t attempts = 0, all_attempts = 0;
thread_local std::size_t minimum_bytes = 0;
// MSVC Debug allocates small iterator proxies even for legitimate vector moves.
// Block every SearchHit payload allocation there; Release and other builds block all.
#if defined(_MSC_VER) && _ITERATOR_DEBUG_LEVEL != 0
constexpr std::size_t call_minimum_bytes = sizeof(qbrain::SearchHit);
#else
constexpr std::size_t call_minimum_bytes = 0;
#endif
void check(std::size_t n) {
  if (tracking) { ++all_attempts; if (n >= minimum_bytes) ++attempts; }
  if (enabled && n >= minimum_bytes) throw std::bad_alloc();
}
void* allocate(std::size_t n) {
  check(n);
  if (auto p = std::malloc(n ? n : 1)) return p;
  throw std::bad_alloc();
}
void* aligned(std::size_t n, std::size_t alignment) {
  check(n);
#ifdef _WIN32
  if (auto p = _aligned_malloc(n ? n : 1, alignment)) return p;
#else
  void* p = nullptr;
  if (posix_memalign(&p, alignment, n ? n : 1) == 0) return p;
#endif
  throw std::bad_alloc();
}
void aligned_free(void* p) noexcept {
#ifdef _WIN32
  _aligned_free(p);
#else
  std::free(p);
#endif
}
}
void* operator new(std::size_t n) { return fault::allocate(n); }
void* operator new[](std::size_t n) { return fault::allocate(n); }
void operator delete(void* p) noexcept { std::free(p); }
void operator delete[](void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }
void operator delete[](void* p, std::size_t) noexcept { std::free(p); }
void* operator new(std::size_t n, std::align_val_t a) { return fault::aligned(n, std::size_t(a)); }
void* operator new[](std::size_t n, std::align_val_t a) { return fault::aligned(n, std::size_t(a)); }
void operator delete(void* p, std::align_val_t) noexcept { fault::aligned_free(p); }
void operator delete[](void* p, std::align_val_t) noexcept { fault::aligned_free(p); }
void operator delete(void* p, std::size_t, std::align_val_t) noexcept { fault::aligned_free(p); }
void operator delete[](void* p, std::size_t, std::align_val_t) noexcept { fault::aligned_free(p); }

using namespace qbrain;
using J = nlohmann::json;
namespace logical = accounting::logical;
namespace {
J checks = J::array(), cases = J::array();
bool passed = true;
void check(bool ok, const char* name) {
  checks.push_back({{"name", name}, {"passed", ok}}); passed = passed && ok;
}
bool equal(const SearchHit& a, const SearchHit& b) {
  return a.page_id==b.page_id && a.slug==b.slug && a.title==b.title &&
    a.snippet==b.snippet && a.score==b.score && a.fts_rank==b.fts_rank &&
    a.vector_rank==b.vector_rank && a.rerank_score==b.rerank_score &&
    a.reranker_delta==b.reranker_delta && a.type==b.type && a.source_id==b.source_id;
}
std::vector<SearchHit> inputs(bool empty) {
  std::vector<SearchHit> hits; hits.reserve(11);
  if (!empty) for (int i=0; i<3; ++i) {
    SearchHit h; h.page_id=41+i; h.slug="docs/item-"+std::to_string(i);
    h.title=std::string(8192, char('a'+i)); h.snippet=std::string(4096,char('k'+i));
    h.score=3.25-i; h.fts_rank=6.5+i; h.vector_rank=8.75+i;
    h.rerank_score=19.5-i; h.reranker_delta=-3+i;
    h.type="note"; h.source_id="synthetic-source"; hits.push_back(std::move(h));
  }
  return hits;
}
void run_case(const char* name, bool enabled, int top_n, bool empty, bool observe, bool fail) {
  Config cfg, capture; capture.chat_model="capture-unchanged";
  search::RerankerOpts opts; opts.enabled=enabled; opts.top_n_in=top_n;
  opts.top_n_out=1; opts.use_llm=true; opts.cfg_capture_for_test=&capture;
  bool callback=false;
  opts.llm_fn_for_test=[&](const auto&,const auto&){callback=true;return std::vector<SearchHit>{};};
  const std::string query="synthetic rerank query";
  auto hits=inputs(empty); const auto expected=hits;
  const auto data=hits.data(); const auto capacity=hits.capacity();
  const auto title=hits.empty()?nullptr:hits[0].title.data();
  std::shared_ptr<logical::Collector> collector;
  std::unique_ptr<logical::Session> session;
  if(observe){collector=std::make_shared<logical::Collector>();session=std::make_unique<logical::Session>(collector);}
  std::vector<SearchHit> out;
  bool returned=false, bad_alloc=false, other_exception=false;
  fault::attempts=0; fault::all_attempts=0; fault::minimum_bytes=fault::call_minimum_bytes;
  fault::tracking=true; fault::enabled=fail;
  try {out=search::apply_reranker(cfg,query,std::move(hits),opts);returned=true;}
  catch(const std::bad_alloc&){bad_alloc=true;}
  catch(...){other_exception=true;}
  fault::enabled=false; fault::tracking=false;
  const auto attempts=fault::attempts, all_attempts=fault::all_attempts;
  check(returned && !bad_alloc && !other_exception,"early return does not throw");
  check(attempts==0,"no attempted payload allocation; all allocations blocked outside MSVC Debug");
  check(out.size()==expected.size(),"nonempty membership not lost or truncated");
  check(out.data()==data && out.capacity()==capacity,"vector buffer ownership transferred");
  check(out.empty() || out[0].title.data()==title,"heap-backed title ownership transferred");
  bool same=out.size()==expected.size();
  if(same)for(std::size_t i=0;i<out.size();++i)same=same&&equal(out[i],expected[i]);
  check(same,"all SearchHit fields and order unchanged");
  check(!callback && capture.chat_model=="capture-unchanged","config capture and callback bypassed");
  if(observe){
    auto lr=collector->report(true,0);auto hr=session->http_collector()->report(true,0);
    check(lr["counts"]["started"]==1 && lr["counts"]["finished"]==1,"one completed logical call");
    const auto& r=lr["records"][0];
    check(r["path"]==(empty?"empty_input":"disabled") && r["return_state"]=="returned","existing classification unchanged");
    check(r["api_result_ok"].is_null() && r["fallback_taken"].is_null() && r["tokens"].is_null() && r["cost"].is_null(),"no invented success fallback usage or cost");
    check(hr["counts"]["started"]==0 && lr["http_links"].empty(),"no HTTP request or link");
    session.reset();
  }
  cases.push_back({{"name",name},{"observe",observe},{"allocation_failure",fail},
    {"returned",returned},{"bad_alloc",bad_alloc},{"other_exception",other_exception},
    {"allocation_attempts",attempts},{"all_allocation_attempts",all_attempts},{"result_size",out.size()},{"ownership_transferred",out.data()==data}});
}
void calibration() {
  fault::minimum_bytes=0;
  auto h=inputs(false);bool failed=false;
  fault::attempts=0;fault::tracking=true;fault::enabled=true;
  try{auto copied=h; (void)copied;}catch(const std::bad_alloc&){failed=true;}
  fault::enabled=false; fault::tracking=false;
  check(failed && fault::attempts==1,"allocation injection rejects a real SearchHit vector copy");
  bool aligned=false;fault::attempts=0;fault::tracking=true;fault::enabled=true;
  try{auto p=::operator new(64,std::align_val_t(64));::operator delete(p,std::align_val_t(64));}
  catch(const std::bad_alloc&){aligned=true;}
  fault::enabled=false; fault::tracking=false;
  check(aligned && fault::attempts==1,"aligned allocation gate active");
}
}
int main() {
  try {
    calibration();
    for(bool observe:{false,true})for(bool fail:{false,true}){
      run_case("disabled",false,30,false,observe,fail);
      run_case("zero_top_n",true,0,false,observe,fail);
      run_case("negative_top_n",true,-1,false,observe,fail);
      run_case("minimum_top_n",true,std::numeric_limits<int>::min(),false,observe,fail);
      run_case("empty_reserved",true,30,true,observe,fail);
    }
    std::cout<<J({{"schema","qbrain-n48x-rerank-move-v1"},{"passed",passed},
      {"case_count",cases.size()},{"check_count",checks.size()},{"cases",cases},{"checks",checks},
      {"provider_requests",0},{"allocation_failure_scope","apply_reranker_only"},
      {"fault_minimum_bytes",fault::call_minimum_bytes},{"search_hit_bytes",sizeof(SearchHit)}}).dump()<<'\n';
    return passed?0:1;
  }catch(const std::exception& e){fault::enabled=false; fault::tracking=false;std::cerr<<e.what()<<'\n';return 2;}
}
