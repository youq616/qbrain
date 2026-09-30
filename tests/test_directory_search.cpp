#include "qbrain/search/directory.hpp"
#include "qbrain/search/vector.hpp"
#include <algorithm>
#include <iostream>
#include <nlohmann/json.hpp>
#include <stdexcept>
#include <vector>
using namespace qbrain;
using J = nlohmann::json;
namespace {
J checks = J::array();
void check(bool ok, const char* name) {
  checks.push_back({{"name", name}, {"passed", ok}});
  if (!ok) throw std::runtime_error(name);
}
void add(Brain& b, int id, const std::string& source, const std::string& slug,
         const std::string& type, const std::string& title,
         const std::string& body, const std::vector<float>& emb = {}) {
  auto s = b.db().prepare(
      "INSERT INTO pages(id,source_id,slug,type,title,body) VALUES(?,?,?,?,?,?)");
  s.bind_int(1, id); s.bind_text(2, source); s.bind_text(3, slug);
  s.bind_text(4, type); s.bind_text(5, title); s.bind_text(6, body); s.step_done();
  if (!emb.empty()) {
    auto c = b.db().prepare(
        "INSERT INTO content_chunks(page_id,chunk_index,text,embedding,dim,model) "
        "VALUES(?,?,?,?,?,?)");
    const auto blob = search::pack_f32(emb);
    c.bind_int(1, id); c.bind_int(2, 0); c.bind_text(3, body);
    c.bind_blob(4, blob.data(), static_cast<int>(blob.size()));
    c.bind_int(5, static_cast<int64_t>(emb.size()));
    c.bind_text(6, b.config().embedding_model); c.step_done();
  }
}
std::vector<std::string> slugs(const std::vector<SearchHit>& hits) {
  std::vector<std::string> out;
  for (const auto& h : hits) out.push_back(h.slug);
  return out;
}
void run() {
  Brain b; b.open_at(":memory:"); b.ensure_source("alpha"); b.ensure_source("beta");
  b.save_config_value("embed.auto", "false", false);
  add(b,1,"alpha","docs/a","note","Needle Alpha","needle root",{1,0,0});
  add(b,2,"alpha","docs/sub/b","note","Nested","needle nested",{.9f,.1f,0});
  add(b,3,"alpha","docs-neighbor/c","note","Neighbor","needle outside",{1,0,0});
  add(b,4,"alpha","docs/tool","skill","Tool","needle skill",{1,0,0});
  add(b,5,"alpha","docs/session","session_fragment","Session","needle memory",{1,0,0});
  add(b,6,"beta","docs/beta","note","Beta","needle beta",{1,0,0});
  add(b,7,"alpha","Docs/case","note","Case","needle case",{1,0,0});
  add(b,8,"alpha","文档/深/页","note","中文针","这里有针",{.8f,.2f,0});
  for (int i=0;i<700;++i)
    add(b,1000+i,"alpha","other/"+std::to_string(i),"note","Needle crowd","needle crowd");
  b.db().exec("UPDATE pages SET deleted_at=CURRENT_TIMESTAMP WHERE id=2");

  auto docs = search::parse_directory_scope(b,"qbrain://alpha/resources/docs/");
  search::DirectorySearchOpts opts; opts.limit=20; opts.mode="balanced"; opts.config=&b.config();
  auto lexical = search::directory_search(b,"needle",nullptr,docs,opts);
  check(slugs(lexical)==std::vector<std::string>{"docs/a"},
        "recursive scope excludes neighbor namespace source and deleted");
  check(lexical[0].source_id=="alpha","source identity retained despite crowd");

  b.db().exec("UPDATE pages SET deleted_at=NULL WHERE id=2");
  lexical=search::directory_search(b,"needle",nullptr,docs,opts);
  auto ls=slugs(lexical);
  check(std::find(ls.begin(),ls.end(),"docs/a")!=ls.end() &&
        std::find(ls.begin(),ls.end(),"docs/sub/b")!=ls.end(),
        "recursive descendants included");
  check(std::find(ls.begin(),ls.end(),"docs-neighbor/c")==ls.end(),
        "literal prefix boundary");
  check(std::find(ls.begin(),ls.end(),"Docs/case")==ls.end(),
        "prefix is case-sensitive");

  auto skills=search::parse_directory_scope(b,"qbrain://alpha/skills/docs/");
  check(slugs(search::directory_search(b,"needle",nullptr,skills,opts))==
        std::vector<std::string>{"docs/tool"},"skills namespace isolated");
  auto memories=search::parse_directory_scope(b,"qbrain://alpha/memories/docs/");
  check(slugs(search::directory_search(b,"needle",nullptr,memories,opts))==
        std::vector<std::string>{"docs/session"},"memories namespace isolated");

  auto root=search::parse_directory_scope(b,"qbrain://alpha/resources/");
  auto root_hits=slugs(search::directory_search(b,"needle",nullptr,root,opts));
  check(std::find(root_hits.begin(),root_hits.end(),"docs-neighbor/c")!=root_hits.end(),
        "namespace root recursively includes sibling directories");

  std::vector<float> q={1,0,0};
  auto vector_only=search::directory_search(b,"not-present",&q,docs,opts);
  auto vs=slugs(vector_only);
  check(std::find(vs.begin(),vs.end(),"docs/a")!=vs.end() &&
        std::find(vs.begin(),vs.end(),"docs/sub/b")!=vs.end(),
        "vector lane obeys recursive scope");
  check(std::find(vs.begin(),vs.end(),"docs-neighbor/c")==vs.end(),
        "vector lane excludes prefix neighbor");

  auto cjk=search::parse_directory_scope(b,"qbrain://alpha/resources/文档/");
  check(slugs(search::directory_search(b,"针",nullptr,cjk,opts))==
        std::vector<std::string>{"文档/深/页"},"UTF8 directory and query");
  check(search::parse_directory_scope(b,"qbrain://alpha/resources/").slug_prefix.empty(),
        "empty namespace-root prefix");

  for (const auto& bad : std::vector<std::string>{
      "qbrain://alpha/resources/docs",
      "qbrain://alpha/unknown/docs/",
      "qbrain://missing/resources/docs/",
      "qbrain://alpha/resources/../",
      "qbrain://alpha/resources/docs%2f/",
      "qbrain://alpha/resources//",
      "qbrain://alpha/resources/docs//"}) {
    bool rejected=false;
    try { (void)search::parse_directory_scope(b,bad); }
    catch (const std::invalid_argument&) { rejected=true; }
    check(rejected,"invalid URI rejected");
  }

  opts.limit=1;
  check(search::directory_search(b,"needle",nullptr,docs,opts).size()==1,
        "limit enforced");
  opts.limit=0;
  check(search::directory_search(b,"needle",nullptr,docs,opts).size()==1,
        "low limit clamped");
  opts.mode="conservative";
  check(search::directory_search(b,"not-present",&q,docs,opts).empty(),
        "conservative disables vector lane");
  opts.mode="bogus";
  bool rejected=false;
  try { (void)search::directory_search(b,"needle",nullptr,docs,opts); }
  catch (const std::invalid_argument&) { rejected=true; }
  check(rejected,"invalid mode rejected");
}
}
int main() {
  try {
    run();
    std::cout<<J({{"schema","qbrain-n48z-directory-search-v1"},{"passed",true},
      {"check_count",checks.size()},{"checks",checks},{"provider_requests",0}}).dump()<<"\n";
    return 0;
  } catch (const std::exception& e) {
    std::cout<<J({{"passed",false},{"checks",checks},{"failure",e.what()}}).dump()<<"\n";
    return 1;
  }
}
