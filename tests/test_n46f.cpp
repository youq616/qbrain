#include "qbrain/memory/session_memory.hpp"
#include "qbrain/search/hybrid.hpp"
#include "qbrain/storage/detail/cjk_literal.hpp"
#include "qbrain/util/hash.hpp"
#include "qbrain/util/utf8_display.hpp"
#include <iostream>
#include <set>
#include <stdexcept>

namespace {
using namespace qbrain;
using J = nlohmann::json;
int checks = 0;
void check(bool ok, const char* label) {
  if (!ok) throw std::runtime_error(std::string("N46F: ") + label);
  ++checks;
}
Page put(Brain& b, const std::string& slug, const std::string& body,
         const std::string& source = "alpha", const std::string& title = "fixture") {
  PageInput in; in.slug=slug; in.body=body; in.title=title; in.source_id=source;
  return b.put_page(in);
}
bool has(const std::vector<SearchHit>& hits, const std::string& slug) {
  for (const auto& h : hits) if (h.slug == slug) return true;
  return false;
}
void policy() {
  using storage::detail::cjk_literal_eligible;
  for (const auto& query : {"中", "日志", "日誌前綴", "かな", "カナ", "ﾒﾓ", "메모", "𠀀", "MT5日志", "日志%_"})
    check(cjk_literal_eligible(query), "explicit CJK ranges allowed");
  for (const auto& query : {"", "ASCII tokens", "café", "😀", "\n中文", "中文\t"})
    check(!cjk_literal_eligible(query), "non-CJK or control input leaves extra lane off");
  check(!cjk_literal_eligible(std::string("中文\0tail",11)), "embedded NUL not eligible");
  check(!cjk_literal_eligible(std::string("中文")+"\xc0\xaf"), "invalid UTF8 not eligible");
  check(cjk_literal_eligible(std::string("中")+std::string(1021,'x')), "exact byte cap");
  check(!cjk_literal_eligible(std::string("中")+std::string(1022,'x')), "over byte cap");
}
void pages() {
  Brain b; b.open_at(":memory:"); b.ensure_source("alpha"); b.ensure_source("beta");
  put(b,"joined","我偏好使用中文日志前缀");
  auto hits=search::fts_search(b,"日志前缀",10,"alpha");
  check(hits.size()==1 && hits[0].slug=="joined", "continuous Chinese substring recovered");
  for (const auto& query : {"中", "日志", "日志前缀"})
    check(has(search::fts_search(b,query,10,"alpha"),"joined"), "one two or multiple Han characters");
  put(b,"exact","日志前缀");
  put(b,"joined","其他来源中文日志前缀", "beta");
  hits=search::fts_search(b,"日志前缀",10,"alpha");
  check(hits.size()==2 && hits[0].slug=="exact" && hits[1].slug=="joined", "FTS results first; nonzero FTS still supplemented");
  check(hits[0].fts_rank==1 && hits[1].fts_rank==2, "single ranked lexical list");
  check(search::fts_search(b,"日志前缀",1,"alpha")[0].slug=="exact", "no replacement of existing full top result");
  hits=search::fts_search(b,"日志前缀",10);
  check(hits.size()==3, "same slug in different sources is retained as two pages");
  std::set<int64_t> ids;
  for(const auto& h:hits) ids.insert(h.page_id);
  check(ids.size()==hits.size(), "FTS and literal lanes never duplicate page ID");
  for(const auto& h:search::fts_search(b,"日志前缀",10,"alpha")) check(h.source_id=="alpha","source identities preserved");
  check(search::fts_search(b,"日志前缀",10,"absent").empty(),"missing source does not fall back");
  check(search::fts_search(b,"日志前缀",10,"alpha' OR 1=1 --").empty(),"source is bound SQL data");
  const std::pair<const char*,const char*> multilingual[] = {
    {"日誌前綴","我偏好使用日誌前綴設定"}, {"ソフト","あいうソフトウェアかきく"},
    {"メモ","毎日メモを使う"}, {"메모리","매일메모리를사용"}, {"𠀀","前𠀀𠀁後"},
    {"MT5日志","前MT5日志後"}, {"日志%_","前日志%_後"}, {"日志' OR 1=1 --","前日志' OR 1=1 --後"}};
  int index=0;
  for(const auto& [query,body]:multilingual) {
    const auto slug="language-"+std::to_string(index++); put(b,slug,body);
    hits=search::fts_search(b,query,10,"alpha");
    check(has(hits,slug),"CJK or mixed literal query is found");
    for(const auto& h:hits) check(util::valid_utf8(h.snippet),"snippet valid UTF8");
  }
  check(!has(search::fts_search(b,"日志%_",20,"alpha"),"joined"),"percent and underscore are not substring wildcards");
  check(!has(search::fts_search(b,"日志' OR 1=1 --",20,"alpha"),"joined"),"SQL-looking text does not broaden literal lane");
  put(b,"title-only","unrelated body","alpha","前标题查询后");
  put(b,"前路径查询后","unrelated body");
  check(has(search::fts_search(b,"标题查询",10,"alpha"),"title-only"),"title literal lane");
  check(has(search::fts_search(b,"路径查询",10,"alpha"),"前路径查询后"),"slug literal lane");
  put(b,"long",std::string(3000,'x')+"前长文中文目标后"+std::string(3000,'y'));
  hits=search::fts_search(b,"中文目标",10,"alpha");
  check(hits.size()==1 && hits[0].snippet.find("中文目标")!=std::string::npos && hits[0].snippet.size()<=640,
        "bounded excerpt includes late literal match");
  put(b,"ascii-exact","anchor"); put(b,"ascii-compound","preanchorpost");
  hits=search::fts_search(b,"anchor",10,"alpha");
  check(hits.size()==1 && hits[0].slug=="ascii-exact", "ASCII token behavior not broadened to substrings");
  put(b,"exact","replacement body"); put(b,"joined","replacement body");
  check(search::fts_search(b,"日志前缀",10,"alpha").empty(),"updated pages immediately stop matching");
  put(b,"joined","我偏好使用中文日志前缀"); b.soft_delete("joined","alpha");
  check(search::fts_search(b,"日志前缀",10,"alpha").empty(),"soft deleted literal page excluded");
  const auto changes=sqlite3_total_changes(b.db().handle());
  for(int i=0;i<3;++i) search::fts_search(b,"标题查询",10,"alpha");
  check(sqlite3_total_changes(b.db().handle())==changes,"read does not write or create index/cache");
}
void bounds() {
  Brain b; b.open_at(":memory:"); b.ensure_source("alpha");
  b.db().exec("BEGIN");
  for(int i=0;i<510;++i) put(b,"row-"+std::to_string(i),"前有界查询后");
  b.db().exec("COMMIT");
  auto first=search::fts_search(b,"有界查询",999,"alpha");
  auto second=search::fts_search(b,"有界查询",999,"alpha");
  check(first.size()==500 && second.size()==500,"combined result cap stays 500");
  bool equal=true;for(std::size_t i=0;i<first.size();++i) equal=equal&&first[i].page_id==second[i].page_id;
  check(equal,"unchanged data yields deterministic ordering");
  check(search::fts_search(b,"有界查询",1,"alpha").size()==1,"small candidate limit");
}
void memories() {
  Brain b; b.open_at(":memory:"); b.ensure_source("alpha"); b.ensure_source("beta");
  const J payload={{"session_id","synthetic"},{"fragment_id","one"},{"messages",J::array({
    {{"role","user"},{"content","我偏好使用中文日志前缀"}}})}};
  const auto e=memory::capture(b,"alpha",payload,true)["event_id"].get<std::string>();
  check(memory::read(b,"alpha","日志前缀")["items"].empty(),"unextracted archive not exposed as a memory");
  memory::extract(b,"alpha",e);
  const auto result=memory::read(b,"alpha","日志前缀");
  check(result["items"].size()==1 && result["items"][0]["quote"]==payload["messages"][0]["content"],
        "memory_read already supports exact Chinese substring");
  check(result["items"][0]["event_id"]==e && result["untrusted_data"]==true,"evidence and untrusted marker retained");
  check(memory::read(b,"alpha","中文 前缀")["items"].empty(),"memory_read does not invent noncontiguous phrase matches");
  check(memory::read(b,"beta","日志前缀")["items"].empty(),"memory source isolation");
  check(memory::read(b,"alpha","",50,512).dump().size()<=512,"memory byte budget unchanged");
  b.db().exec("UPDATE memory_items SET expires_at=1");
  check(memory::read(b,"alpha","日志前缀")["items"].empty(),"expired memory not resurrected");
  b.db().exec("UPDATE memory_items SET expires_at=0");
  memory::forget(b,"alpha",e);
  check(memory::read(b,"alpha","日志前缀")["items"].empty(),"forgotten memory not resurrected");
}
}
void test_n46f() {
  checks=0; policy(); pages(); bounds(); memories();
  std::cout<<"N46F CJK recall: "<<checks<<" checks passed\n";
}
#ifdef QBRAIN_CJK_STANDALONE
int main() {
  try {test_n46f();return 0;}
  catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
#endif
