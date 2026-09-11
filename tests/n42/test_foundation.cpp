#include "qbrain/search/rrf.hpp"
#include "qbrain/search/result_identity.hpp"
#include "qbrain/util/utf8_display.hpp"
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
std::size_t assertions = 0;
void check(bool value, const char* expression, int line) {
  ++assertions;
  if (!value) throw std::runtime_error(std::string(expression) + " at line " + std::to_string(line));
}
#define N42_CHECK(x) check((x), #x, __LINE__)
using qbrain::SearchHit;
using qbrain::search::rrf_fusion;
using qbrain::search::rrf_fusion_weighted;
using qbrain::util::valid_utf8;
using qbrain::util::utf8_excerpt;
SearchHit hit(int64_t id, const std::string& source, const std::string& slug) {
  SearchHit h;
  h.page_id = id; h.source_id = source; h.slug = slug; h.title = slug;
  return h;
}
void legacy_fusion() {
  std::vector<SearchHit> a={{1,"a","A"},{2,"b","B"},{3,"c","C"}};
  std::vector<SearchHit> b={{2,"b","B"},{1,"a","A"},{4,"d","D"}};
  const auto r=rrf_fusion({a,b});
  N42_CHECK(r.size()==4);
  N42_CHECK(r.front().slug=="a" || r.front().slug=="b");
}
void sources_stay_distinct() {
  auto a=hit(1,"default","deployment"), b=hit(2,"project-a","deployment");
  a.snippet="first-source"; b.snippet="second-source";
  const auto r=rrf_fusion({{a,b},{b,a}});
  N42_CHECK(r.size()==2);
  N42_CHECK(r[0].source_id=="default");
  N42_CHECK(r[1].source_id=="project-a");
  N42_CHECK(r[1].snippet=="second-source");
}
void idless_identity() {
  auto a=hit(0,"a","b:c"), b=hit(0,"a:b","c");
  N42_CHECK(qbrain::search::result_identity(a)!=qbrain::search::result_identity(b));
  N42_CHECK(rrf_fusion({{a,b}}).size()==2);
  auto legacy=hit(0,"","17"), numbered=hit(17,"default","");
  N42_CHECK(qbrain::search::result_identity(legacy)!=qbrain::search::result_identity(numbered));
  N42_CHECK(rrf_fusion({{legacy,numbered}}).size()==2);
}
void duplicate_votes() {
  const auto a=hit(1,"default","a");
  const auto r=rrf_fusion({{a,a,a}});
  N42_CHECK(r.size()==1);
  N42_CHECK(std::abs(r[0].score-1.0/61.0)<1e-15);
  const auto votes=rrf_fusion({{a},{a}});
  N42_CHECK(std::abs(votes[0].score-2.0/61.0)<1e-15);
}
void malformed_ranking() {
  const auto a=hit(1,"default","a"), b=hit(2,"default","b");
  const auto nan=std::numeric_limits<double>::quiet_NaN();
  const auto inf=std::numeric_limits<double>::infinity();
  N42_CHECK(rrf_fusion_weighted({{a},{b}},{nan,1}).size()==1);
  N42_CHECK(rrf_fusion_weighted({{a}},{inf}).empty());
  N42_CHECK(rrf_fusion_weighted({{a}},{-1}).empty());
  const auto r=rrf_fusion({{a,b}},std::numeric_limits<int>::min());
  N42_CHECK(r.size()==2 && std::isfinite(r[0].score));
  const auto maximum=std::numeric_limits<double>::max();
  N42_CHECK(std::isfinite(rrf_fusion_weighted({{a},{a}},{maximum,maximum},0)[0].score));
  N42_CHECK(rrf_fusion({{SearchHit{}}}).empty());
}
void repeatable_ties() {
  const auto a=hit(2,"a","same"), b=hit(1,"b","same");
  for (int i=0;i<100;++i) {
    const auto r=i%2 ? rrf_fusion({{a},{b}}) : rrf_fusion({{b},{a}});
    N42_CHECK(r.size()==2 && r[0].source_id=="a" && r[1].source_id=="b");
  }
}
void text_boundaries() {
  const std::string chinese="\xE4\xB8\xAD", emoji="\xF0\x9F\xA7\xA0";
  std::string s;
  for(int i=0;i<67;++i) s+=chinese;
  N42_CHECK(s.size()==201);
  N42_CHECK(!valid_utf8(s.substr(0,200)));
  N42_CHECK(utf8_excerpt(s,200)==s.substr(0,198));
  N42_CHECK(utf8_excerpt(emoji,3).empty());
  N42_CHECK(utf8_excerpt(emoji,4)==emoji);
  std::string mixed="A"+chinese+emoji+"Z";
  const std::vector<std::size_t> boundaries={0,1,4,8,9};
  for(std::size_t cap=0;cap<14;++cap) {
    const auto out=utf8_excerpt(mixed,cap);
    std::size_t end=0;for(auto p:boundaries) if(p<=cap) end=p;
    N42_CHECK(out==mixed.substr(0,end));
    N42_CHECK(valid_utf8(out) && out.size()<=cap);
  }
  N42_CHECK(utf8_excerpt("abcdefghijklmnop",11,true)=="[truncated]");
  N42_CHECK(utf8_excerpt("abcdefghijklmnop",13,true)=="ab[truncated]");
  N42_CHECK(utf8_excerpt("short",99,true)=="short");
}
void malformed_utf8() {
  const std::vector<std::string> bad={"\x80","\xC0\xAF","\xE0\x80\xAF","\xED\xA0\x80",
      "\xF0\x80\x80\xAF","\xF4\x90\x80\x80","\xF5\x80\x80\x80","\xE4\xB8"};
  for(const auto& s:bad) {
    N42_CHECK(!valid_utf8(s));
    for(std::size_t cap=0;cap<24;++cap) {
      const auto out=utf8_excerpt(s,cap,true);
      N42_CHECK(out.size()<=cap && valid_utf8(out));
    }
  }
  N42_CHECK(utf8_excerpt("\xFF",3)=="\xEF\xBF\xBD");
  const std::string nul("x\0y",3);
  N42_CHECK(utf8_excerpt(nul,3)==nul);
}
void fuzz_display() {
  std::mt19937 rng(42);
  for(int n=0;n<1000;++n) {
    std::string s;const auto length=rng()%64;
    for(unsigned i=0;i<length;++i) s.push_back(static_cast<char>(rng()&255));
    const auto original=s;
    for(std::size_t cap=0;cap<80;cap+=7) {
      auto out=utf8_excerpt(s,cap,n%2==0);
      N42_CHECK(out.size()<=cap);
      N42_CHECK(valid_utf8(out));
      N42_CHECK(s==original);
    }
  }
}
#ifdef QBRAIN_N42_STANDALONE
std::string hex(const std::string& s) {
  constexpr char digits[]="0123456789abcdef";std::string out;
  for(unsigned char c:s){out+=digits[c>>4];out+=digits[c&15];}return out;
}
void emit_cases() {
  std::mt19937 rng(63);
  for(int n=0;n<1000;++n) {
    std::string s; const auto len=rng()%50;
    for(unsigned i=0;i<len;++i) s.push_back(static_cast<char>(rng()&255));
    const auto cap=rng()%90;
    std::cout<<cap<<'\t'<<hex(s)<<'\t'<<hex(utf8_excerpt(s,cap))<<'\n';
  }
}
#endif
}  // namespace

void test_n42_foundation() {
  assertions=0;
  struct Scenario {const char* name;void(*run)();};
  const Scenario scenarios[]={{"legacy RRF",legacy_fusion},{"same slug across sources",sources_stay_distinct},
      {"idless framed identity",idless_identity},{"duplicate votes",duplicate_votes},
      {"invalid ranking inputs",malformed_ranking},{"deterministic ties",repeatable_ties},
      {"Chinese and emoji boundaries",text_boundaries},{"invalid UTF-8 display",malformed_utf8},
      {"deterministic byte fuzz",fuzz_display}};
  for(const auto& s:scenarios){s.run();std::cout<<"[PASS] "<<s.name<<'\n';}
  std::cout<<"N42 foundation: 9 scenarios; "<<assertions<<" assertions\n";
}
#ifdef QBRAIN_N42_STANDALONE
int main(int argc,char** argv) {
  try {
    if(argc==2 && std::string(argv[1])=="--emit-utf8"){emit_cases();return 0;}
    test_n42_foundation();return 0;
  }catch(const std::exception& e){std::cerr<<"[FAIL] "<<e.what()<<'\n';return 1;}
}
#endif
