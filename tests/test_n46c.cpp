#include "qbrain/search/hybrid.hpp"
#include "qbrain/search/detail/exact_topk.hpp"
#include "qbrain/search/vector.hpp"
#include "qbrain/util/utf8_display.hpp"
#include "n46c_reference.hpp"
#include <algorithm>
#include <chrono>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <random>
#include <stdexcept>
#include <nlohmann/json.hpp>

namespace {
using namespace qbrain;
using namespace qbrain::search;
using J = nlohmann::json;
int checks = 0;
void check(bool value, const char* label) {
  ++checks;
  if (!value) throw std::runtime_error(std::string("N46C: ") + label);
}
void same(const std::vector<SearchHit>& a, const std::vector<SearchHit>& b) {
  check(a.size() == b.size(), "result count equals exhaustive oracle");
  for (std::size_t i = 0; i < a.size(); ++i) {
    check(a[i].page_id == b[i].page_id && a[i].source_id == b[i].source_id &&
          a[i].slug == b[i].slug && a[i].title == b[i].title && a[i].type == b[i].type &&
          a[i].snippet == b[i].snippet && a[i].score == b[i].score &&
          a[i].vector_rank == b[i].vector_rank && a[i].fts_rank == b[i].fts_rank,
          "identity, selected snippet, exact score and ranks equal oracle");
  }
}
std::vector<SearchHit> exhaustive(const std::vector<SearchHit>& input, int limit) {
  std::map<std::string, SearchHit> best;
  for (const auto& hit : input) {
    if (!std::isfinite(hit.score)) continue;
    auto it = best.find(result_identity(hit));
    if (it == best.end() || hit.score > it->second.score ||
        (hit.score == it->second.score && hit.snippet < it->second.snippet))
      best[result_identity(hit)] = hit;
  }
  std::vector<SearchHit> out;
  for (const auto& entry : best) out.push_back(entry.second);
  std::sort(out.begin(), out.end(), [](const auto& a, const auto& b) {
    return a.score != b.score ? a.score > b.score : result_identity_less(a,b);
  });
  out.resize(std::min(out.size(), static_cast<std::size_t>(std::clamp(limit,1,500))));
  for (std::size_t i=0;i<out.size();++i) out[i].vector_rank = static_cast<double>(i+1);
  return out;
}
void selector_properties() {
  std::mt19937 rng(4603);
  std::vector<SearchHit> input;
  for (int i=0;i<1800;++i) {
    SearchHit hit;
    hit.page_id=1+rng()%137; hit.source_id=hit.page_id%2 ? "alpha" : "beta";
    hit.slug="same-"+std::to_string(hit.page_id/2); hit.title="确定性 😀";
    hit.snippet="片段-"+std::to_string(rng()%300); hit.score=(static_cast<int>(rng()%21)-10)/10.0;
    input.push_back(std::move(hit));
  }
  // A page must re-enter after eviction, then choose the lower snippet on a tie.
  SearchHit a; a.page_id=200; a.source_id="alpha"; a.slug="reentry"; a.snippet="z"; a.score=-1;
  input.push_back(a); a.score=0.99; input.push_back(a); a.snippet="a"; input.push_back(a);
  a.score=std::numeric_limits<double>::infinity(); input.push_back(a);
  for (int round=0;round<8;++round) {
    std::shuffle(input.begin(),input.end(),rng);
    for (int limit : {-2,0,1,2,7,30,100,500,999}) {
      detail::ExactPageTopK top(limit);
      for (const auto& hit : input) {
        top.consider(hit);
        check(top.size()<=static_cast<std::size_t>(std::clamp(limit,1,500)),"selector stays within K after every row");
      }
      same(top.results(),exhaustive(input,limit));
    }
  }
  // Explicitly exercise eviction/re-entry even when randomized data has top ties.
  detail::ExactPageTopK one(1); a.score=.1; a.snippet="old"; one.consider(a);
  SearchHit b=a; b.page_id=201; b.slug="other"; b.score=.2; one.consider(b);
  a.score=.3; a.snippet="z"; one.consider(a); a.snippet="a"; one.consider(a);
  check(one.results()[0].page_id==200 && one.results()[0].snippet=="a","evicted page re-enters and updates tied snippet");
}
void seed(Brain& brain, int pages, int chunks, int dimension, bool links) {
  brain.open_at(":memory:"); brain.ensure_source("alpha"); brain.ensure_source("beta");
  auto p=brain.db().prepare("INSERT INTO pages(id,source_id,slug,title,body,type) VALUES(?,?,?,?,?,'note')");
  auto c=brain.db().prepare("INSERT INTO content_chunks(page_id,chunk_index,text,embedding,dim,model) VALUES(?,?,?,?,?,'synthetic-fixture')");
  auto l=brain.db().prepare("INSERT INTO links(source_id,from_slug,to_slug,context) VALUES(?,?,?,?)");
  std::mt19937 rng(46);
  brain.db().exec("BEGIN");
  for (int i=1;i<=pages;++i) {
    const std::string source=i%2 ? "alpha" : "beta", slug="shared-"+std::to_string((i-1)/2);
    p.reset(); p.clear_bindings(); p.bind_int(1,i); p.bind_text(2,source); p.bind_text(3,slug);
    p.bind_text(4,"retrieval fixture "+slug); p.bind_text(5,"retrieval corpus data"); p.step_done();
    for (int j=0;j<chunks;++j) {
      std::vector<float> embedding(dimension);
      for (auto& f:embedding) f=(static_cast<int>(rng()%2001)-1000)/1000.0f;
      if (j==0 && i%11==0) std::fill(embedding.begin(),embedding.end(),1.f);
      auto blob=pack_f32(embedding);
      c.reset(); c.clear_bindings(); c.bind_int(1,i); c.bind_int(2,j);
      c.bind_text(3,"中文😀 retrieval snippet-"+std::to_string(j)+std::string(210,'x'));
      c.bind_blob(4,blob.data(),static_cast<int>(blob.size())); c.bind_int(5,dimension); c.step_done();
    }
    if (links) for (int j=0;j<i%9;++j) {
      l.reset(); l.clear_bindings(); l.bind_text(1,source); l.bind_text(2,"ref-"+std::to_string(j));
      l.bind_text(3,slug); l.bind_text(4,"PRIVATE-LINK-CONTEXT"+std::string(1024,'x')); l.step_done();
    }
  }
  brain.db().exec("COMMIT");
}
struct Trace {
  std::size_t batches=0, legacy_links=0;
  static int record(unsigned, void* context, void* statement, void*) {
    auto& self=*static_cast<Trace*>(context);
    const char* raw=sqlite3_sql(static_cast<sqlite3_stmt*>(statement));
    const std::string sql=raw ? raw : "";
    if (sql.starts_with("WITH wanted(hit_index")) ++self.batches;
    if (sql.find("FROM links WHERE source_id=? AND to_slug=?")!=std::string::npos) ++self.legacy_links;
    return 0;
  }
};
void database_equivalence() {
  Brain brain; seed(brain,420,4,8,true);
  const std::vector<float> query(8,1.f);
  for (const std::string& source : {std::string{},std::string("alpha"),std::string("beta"),std::string("missing")}) {
    for (int limit : {-10,1,7,30,100,500,999}) {
      RetrievalDiagnostics d;
      auto actual=vector_search(brain,query,limit,source,&d);
      same(actual,n46c_reference::reference_vector_search(brain,query,limit,source));
      check(d.chunks_scanned== (source.empty()?1680:source=="missing"?0:840),"complete source-filtered vector scan");
      check(d.peak_retained_pages<=static_cast<std::size_t>(std::clamp(limit,1,500)),"production selector bound");
      for (const auto& hit:actual) check(util::valid_utf8(hit.snippet) && hit.snippet.size()<=200,"Unicode snippet byte boundary");
    }
  }
  for (int limit : {1,34,67,100}) for (const std::string& source:{std::string{},std::string("alpha"),std::string("beta")}) {
    HybridOpts opts; opts.limit=limit; opts.source_id=source;
    RetrievalDiagnostics d; opts.diagnostics=&d;
    sqlite3_set_authorizer(brain.db().handle(), [](void*, int action, const char* table,
        const char* column, const char*, const char*) -> int {
      if (action==SQLITE_READ && table && column && std::string(table)=="links" &&
          (std::string(column)=="context" || std::string(column)=="from_slug" ||
           std::string(column)=="link_type" || std::string(column)=="link_source")) return SQLITE_DENY;
      return SQLITE_OK;
    }, nullptr);
    Trace trace; sqlite3_trace_v2(brain.db().handle(),SQLITE_TRACE_STMT,Trace::record,&trace);
    const auto changes=sqlite3_total_changes(brain.db().handle());
    auto actual=hybrid_search(brain,"retrieval",&query,opts);
    sqlite3_trace_v2(brain.db().handle(),0,nullptr,nullptr);
    sqlite3_set_authorizer(brain.db().handle(),nullptr,nullptr);
    check(sqlite3_total_changes(brain.db().handle())==changes,"search performs no writes");
    check(trace.batches==d.backlink_queries && trace.legacy_links==0,"real SQLite trace confirms batched path only");
    check(d.backlink_queries==(d.backlink_candidates+99)/100,"backlink query count bounded across source identities");
    opts.diagnostics=nullptr;
    same(actual,n46c_reference::reference_hybrid_search(brain,"retrieval",&query,opts));
  }
  HybridOpts opts; opts.mode="conservative"; RetrievalDiagnostics d; opts.diagnostics=&d;
  same(hybrid_search(brain,"retrieval",&query,opts),n46c_reference::reference_hybrid_search(brain,"retrieval",&query,opts));
  check(d.chunks_scanned==0,"conservative mode still avoids vector scan");
  same(hybrid_search(brain,"absent-token",nullptr,opts),n46c_reference::reference_hybrid_search(brain,"absent-token",nullptr,opts));
  check(d.backlink_queries==0,"empty candidates make no backlink query");
  // Mutations cannot be hidden by a stale result cache: there is no new cache.
  brain.db().exec("UPDATE pages SET deleted_at='2026-01-01' WHERE id=1");
  brain.db().exec("UPDATE content_chunks SET embedding=X'01' WHERE page_id=2");
  auto st=brain.db().prepare("UPDATE content_chunks SET embedding=? WHERE page_id=3");
  auto bad=pack_f32({std::numeric_limits<float>::quiet_NaN(),1,1,1,1,1,1,1});
  st.bind_blob(1,bad.data(),static_cast<int>(bad.size())); st.step_done();
  auto found=vector_search(brain,query,500,"",&d);
  same(found,n46c_reference::reference_vector_search(brain,query,500,""));
  check(d.chunks_scanned==1676 && d.invalid_chunks==8,"deleted row and malformed/nonfinite embeddings excluded");
  for (const auto& hit:found) check(hit.page_id>3,"no stale deleted or invalid page returned");
  for (const auto& q : {std::vector<float>{},std::vector<float>{1,2},std::vector<float>(8,0.f),std::vector<float>{std::numeric_limits<float>::infinity()}})
    same(vector_search(brain,q,10),n46c_reference::reference_vector_search(brain,q,10,""));
  brain.db().exec("UPDATE pages SET deleted_at=NULL WHERE id=1");
  same(vector_search(brain,query,500),n46c_reference::reference_vector_search(brain,query,500,""));
}
double median(std::vector<double> values) { std::sort(values.begin(),values.end()); return values[values.size()/2]; }
J benchmark() {
  Brain brain; constexpr int pages=2000,chunks=8,dim=64,limit=50;
  seed(brain,pages,chunks,dim,true);
  const std::vector<float> query(dim,1.f); RetrievalDiagnostics d;
  std::vector<double> old_ms,new_ms;
  for (int i=0;i<7;++i) {
    std::vector<SearchHit> old_result,new_result;
    auto run=[&](bool old) {
      const auto start=std::chrono::steady_clock::now();
      auto result=old ? n46c_reference::reference_vector_search(brain,query,limit,"") : vector_search(brain,query,limit,"",&d);
      const double ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
      if (old) {old_ms.push_back(ms);old_result=std::move(result);} else {new_ms.push_back(ms);new_result=std::move(result);}
    };
    run(i%2==0); run(i%2!=0); same(new_result,old_result);
  }
  check(d.chunks_scanned==pages*chunks && d.valid_chunks==pages*chunks && d.peak_retained_pages<=limit,"benchmark full scan and candidate cap");
  HybridOpts opts; opts.limit=100;
  Trace before; sqlite3_trace_v2(brain.db().handle(),SQLITE_TRACE_STMT,Trace::record,&before);
  auto legacy=n46c_reference::reference_hybrid_search(brain,"retrieval",&query,opts);
  Trace after; sqlite3_trace_v2(brain.db().handle(),SQLITE_TRACE_STMT,Trace::record,&after);
  RetrievalDiagnostics hybrid_d; opts.diagnostics=&hybrid_d;
  auto current=hybrid_search(brain,"retrieval",&query,opts);
  sqlite3_trace_v2(brain.db().handle(),0,nullptr,nullptr); same(current,legacy);
  check(before.legacy_links==hybrid_d.backlink_candidates && after.batches==hybrid_d.backlink_queries,
        "benchmark confirms exact reduction in backlink SQL statements");
  return {{"result","PASS"},{"fixture","synthetic in-memory SQLite; no provider"},
    {"hybrid_results_equal",true},{"backlink_candidates",hybrid_d.backlink_candidates},
    {"baseline_backlink_queries",before.legacy_links},{"optimized_backlink_queries",after.batches},
    {"pages",pages},{"chunks",pages*chunks},{"dimensions",dim},{"limit",limit},{"repetitions",7},
    {"results_equal",true},{"baseline_candidate_records",pages*chunks},{"peak_retained_pages",d.peak_retained_pages},
    {"chunks_scanned",d.chunks_scanned},{"baseline_median_ms",median(old_ms)},{"optimized_median_ms",median(new_ms)},
    {"baseline_samples_ms",old_ms},{"optimized_samples_ms",new_ms},{"whole_process_memory_measured",false},
    {"semantic_quality_measured",false},{"paid_cost_measured",false}};
}
}  // namespace
void test_n46c() {
  checks=0; selector_properties(); database_equivalence();
  std::cout<<"N46C exact retrieval: "<<checks<<" checks passed\n";
}
#ifdef QBRAIN_RETRIEVAL_STANDALONE
int main(int argc,char** argv) {
  try {
    if (argc==3 && std::string(argv[1])=="--benchmark") {
      std::ofstream report(argv[2],std::ios::binary); if (!report) throw std::runtime_error("Cannot open benchmark output");
      report<<benchmark().dump(2)<<'\n'; if (!report) throw std::runtime_error("Cannot write benchmark output");
    } else if (argc==1) test_n46c();
    else throw std::runtime_error("Usage: qbrain_retrieval_tests [--benchmark output.json]");
    return 0;
  } catch (const std::exception& e) {std::cerr<<"[FAIL] "<<e.what()<<'\n';return 1;}
}
#endif
