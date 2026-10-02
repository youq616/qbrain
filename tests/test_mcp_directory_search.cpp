#include "qbrain/ai/embed.hpp"
#include "qbrain/mcp/server.hpp"
#include "qbrain/ops/registry.hpp"
#include "qbrain/search/hybrid.hpp"
#include "qbrain/search/vector.hpp"
#include <nlohmann/json.hpp>
#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

// Qualification requires Debug semantics in inherited production code too.
#ifdef NDEBUG
#error N49D tests require NDEBUG to be absent
#endif

using namespace qbrain;
using J = nlohmann::json;
namespace {
J checks = J::array();
void check(bool ok, const std::string& name) {
  checks.push_back({{"name", name}, {"passed", ok}});
  if (!ok) throw std::runtime_error(name);
}
struct Env {
  std::string name;
  std::optional<std::string> previous;
  explicit Env(std::string key, std::optional<std::string> value) : name(std::move(key)) {
    if (const char* p = std::getenv(name.c_str())) previous = p;
    set(value);
  }
  void set(const std::optional<std::string>& value) const {
#ifdef _WIN32
    if (_putenv_s(name.c_str(), value ? value->c_str() : ""))
      throw std::runtime_error("fixture environment setup failed");
#else
    if (value ? setenv(name.c_str(), value->c_str(), 1) : unsetenv(name.c_str()))
      throw std::runtime_error("fixture environment setup failed");
#endif
  }
  ~Env() {
    try { set(previous); } catch (...) {}
  }
};
// Frozen from the 112 register_one/Scope registration names in handlers.cpp,
// memory_ops.cpp and context_ops.cpp at cfe1ef58e244b51092c2248804b663b6c28913d7.
// Comparison is a fixed accepted-base set, not candidate registry self-equality.
const std::string base_names =
  "add_link add_tag add_timeline_entry advisor cancel_job capture chronicle_backfill chronicle_day "
  "chronicle_last_seen chronicle_on_this_day chronicle_since code_blast code_callees code_callers "
  "code_def code_flow code_refs code_traversal_cache_clear context_read context_write delete_page "
  "doctor_remediate extract_facts file_list file_upload file_url find_anomalies find_contradictions "
  "find_experts find_orphans find_trajectory forget_fact get_active_schema_pack get_backlinks "
  "get_brain_identity get_calibration_profile get_chunks get_health get_ingest_log get_job "
  "get_job_progress get_links get_page get_raw_data get_recent_salience get_recent_transcripts "
  "get_skill get_stats get_status_snapshot get_tags get_timeline get_versions list_brain_skillpack "
  "list_brains list_facts list_job_messages list_jobs list_link_sources list_pages list_schema_packs "
  "list_skills log_ingest memory_read memory_write ontology_conflicts ontology_dimensions ontology_get "
  "ontology_propose pause_job purge_deleted_pages put_page put_raw_data query recall reload_schema_pack "
  "remove_link remove_tag replay_job resolve_slugs restore_page resume_job retry_job revert_version "
  "run_doctor run_dream run_onboard run_skillopt schema_apply_mutations schema_explain_type schema_graph "
  "schema_lint schema_review_orphans schema_stats search search_by_image send_job_message sources_add "
  "sources_list sources_remove sources_status submit_agent submit_job sync_brain takes_calibration "
  "takes_list takes_scorecard takes_search think traverse_graph volunteer_chronicle volunteer_context whoami";
std::set<std::string> words(const std::string& text) {
  std::istringstream stream(text); std::set<std::string> out; std::string word;
  while (stream >> word) out.insert(word);
  return out;
}
J request(const J& args, const std::string& tool = "search") {
  return {{"jsonrpc", "2.0"}, {"id", 49}, {"method", "tools/call"},
          {"params", {{"name", tool}, {"arguments", args}}}};
}
J rpc(Brain& b, const mcp::ServeOptions& opts, const J& args,
      const std::string& tool = "search") {
  return J::parse(mcp::handle_rpc_body(b, opts, request(args, tool).dump()));
}
J payload(const J& response) {
  check(response.contains("result"), "tool response stays separate from JSON-RPC errors");
  return J::parse(response.at("result").at("content").back().at("text").get<std::string>());
}
std::set<std::string> slugs(const J& hits) {
  check(hits.is_array(), "search payload is an array");
  std::set<std::string> out;
  for (const auto& hit : hits) out.insert(hit.at("slug").get<std::string>());
  return out;
}
void source_only(const J& hits, const std::string& source) {
  check(!hits.empty(), "source control has positive evidence");
  for (const auto& hit : hits) check(hit.at("source_id") == source, "resolved source is retained");
}
ops::OpResult direct(Brain& b, std::unordered_map<std::string, std::string> args,
                     bool mcp = true, bool remote = false) {
  ops::OpContext c; c.brain = &b; c.via_mcp = mcp; c.remote = remote;
  c.args = std::move(args); return ops::global_registry().call("search", c);
}
void uri_error(const J& r) {
  check(r.at("result").at("isError") == true, "invalid URI is a tool error");
  const auto p = payload(r);
  check(p.at("error").at("code") == "invalid_argument" &&
        p.at("error").at("field") == "uri", "bounded URI argument error contract");
  check(r.dump().size() < 512 && !p.contains("hits"), "URI error is bounded without hits");
}
void add(Brain& b, int id, const std::string& source, const std::string& slug,
         const std::string& type, const std::string& body, const std::vector<float>& embedding) {
  auto p = b.db().prepare("INSERT INTO pages(id,source_id,slug,type,title,body) VALUES(?,?,?,?,?,?)");
  p.bind_int(1,id); p.bind_text(2,source); p.bind_text(3,slug); p.bind_text(4,type);
  p.bind_text(5,slug); p.bind_text(6,body); p.step_done();
  auto c = b.db().prepare("INSERT INTO content_chunks(page_id,chunk_index,text,embedding,dim,model) VALUES(?,0,?,?,?,?)");
  const auto blob = search::pack_f32(embedding);
  c.bind_int(1,id); c.bind_text(2,body); c.bind_blob(3,blob.data(),static_cast<int>(blob.size()));
  c.bind_int(4,static_cast<int64_t>(embedding.size())); c.bind_text(5,"mock-embedding"); c.step_done();
}
// Exact pre-change no-URI serialization at cfe1ef58e244b51092c2248804b663b6c28913d7.
// It invokes the unchanged hybrid engine rather than duplicating its ranking.
ops::OpResult legacy_result(Brain& b, const std::string& source, const std::string& query) {
  search::HybridOpts opts; opts.limit=20; opts.rrf_k=b.config().search_rrf_k;
  opts.source_id=source; opts.mode="balanced"; opts.config=&b.config();
  const auto hits=search::hybrid_search(b,query,nullptr,opts);
  J arr=J::array(); std::ostringstream text; int rank=1;
  for (const auto& h : hits) {
    arr.push_back({{"rank",rank},{"source_id",h.source_id},{"page_id",h.page_id},
      {"slug",h.slug},{"title",h.title},{"score",h.score},{"rerank_score",h.rerank_score},{"snippet",h.snippet}});
    text << rank << ". " << h.slug << "  (" << h.score << ")\n   " << h.title << "\n   " << h.snippet << "\n";
    ++rank;
  }
  ops::OpResult r; r.json=arr.dump(2); r.text=text.str().empty()?"(no results)\n":text.str(); return r;
}
void run() {
  Env mock("QBRAIN_EMBED_MOCK", "1"), source("QBRAIN_SOURCE", std::nullopt), pg("QBRAIN_PG_DSN", std::nullopt);
  ops::register_builtin_ops(); Brain b; b.open_at(":memory:");
  b.save_config_value("embed.auto","false",false);
  b.save_config_value("mcp.allowed_sources","alpha,0,1,7,missing",false);
  for (const auto* s : {"alpha","beta","0","1","7"}) b.ensure_source(s);
  const auto er=ai::embed_texts(b.config(),{"vectoronlyquery"});
  check(er.ok && er.model=="mock-embedding" && er.vectors.size()==1,"built-in no-network query-vector fixture");
  int id=1;
  for (const auto* s : {"default","alpha","beta","0","1","7"}) {
    add(b,id++,s,"docs/a","note","needle root",er.vectors[0]);
    add(b,id++,s,"docs/sub/b","note","needle nested",er.vectors[0]);
    add(b,id++,s,"docs-neighbor/c","note","needle neighbor",er.vectors[0]);
    add(b,id++,s,"Docs/case","note","needle case",er.vectors[0]);
    add(b,id++,s,"docs/tool","skill","needle skill",er.vectors[0]);
    add(b,id++,s,"docs/session","session_fragment","needle memory",er.vectors[0]);
    add(b,id++,s,"docs/deleted","note","needle deleted",er.vectors[0]);
    add(b,id++,s,"文档/深/页","note","这里有针",er.vectors[0]);
  }
  b.db().exec("UPDATE pages SET deleted_at='2026-10-01' WHERE slug='docs/deleted'");
  const auto changes=sqlite3_total_changes(b.db().handle());
  const std::string uri="qbrain://alpha/resources/docs/";
  const auto direct_result=direct(b,{{"source_id","alpha"},{"query","needle"},{"no_vector","1"},{"uri",uri}});
  check(direct_result.ok && slugs(J::parse(direct_result.json))==words("docs/a docs/sub/b"),"direct existing search narrows recursively");
  for (const auto& source_id : {std::string(""),std::string("default"),std::string("alpha")}) {
    auto args=std::unordered_map<std::string,std::string>{{"query","needle"},{"no_vector","1"},{"limit","20"}};
    if (!source_id.empty()) args["source_id"]=source_id;
    const auto actual=direct(b,args,!source_id.empty());
    const auto expected=legacy_result(b,source_id,"needle");
    check(actual.ok && actual.json==expected.json && actual.text==expected.text,"no-URI stable base hybrid bytes and text");
  }
  for (const auto* profile : {"full","memory"}) for (bool remote : {false,true}) {
    mcp::ServeOptions opts; opts.tool_profile=profile; opts.http_transport=remote;
    const auto listed=J::parse(mcp::handle_rpc_body(b,opts,R"({"jsonrpc":"2.0","id":1,"method":"tools/list"})"));
    std::set<std::string> names; J schema;
    for (const auto& t : listed.at("result").at("tools")) {
      names.insert(t.at("name").get<std::string>());
      if (t.at("name")=="search") schema=t.at("inputSchema");
    }
    const auto expected_names=std::string(profile)=="full"?words(base_names):words("search get_page memory_read memory_write context_read context_write");
    check(names==expected_names && listed.at("result").at("tools").size()==names.size(),"exact base tool-name set without duplicates");
    check(schema.at("properties").at("uri").at("type")=="string","both profiles advertise URI string");
    check(std::find(schema.at("required").begin(),schema.at("required").end(),J("uri"))==schema.at("required").end(),"URI remains optional");
    J args={{"query","needle"},{"source_id","alpha"},{"no_vector",true},{"limit",20}};
    auto legacy=legacy_result(b,"alpha","needle");
    auto unscoped=rpc(b,opts,args);
    check(unscoped.at("result")==J({{"isError",false},{"content",J::array({{{"type","text"},{"text",legacy.text}},{{"type","text"},{"text",legacy.json}}})}}),"no-URI MCP exact base text/structured wrapper");
    args["uri"]=uri;
    check(slugs(payload(rpc(b,opts,args)))==words("docs/a docs/sub/b"),"MCP resources excludes namespace sibling case source and deletion");
    args["limit"]=1;
    check(payload(rpc(b,opts,args)).size()==1,"MCP limit reaches existing directory engine");
    args["limit"]=20;
    args["uri"]="qbrain://alpha/resources/";
    check(slugs(payload(rpc(b,opts,args)))==words("docs/a docs/sub/b docs-neighbor/c Docs/case"),"namespace root recursively includes resources only");
    for (const auto& pair : std::vector<std::pair<std::string,std::string>>{{"skills","docs/tool"},{"memories","docs/session"}}) {
      args["uri"]="qbrain://alpha/"+pair.first+"/docs/";
      check(slugs(payload(rpc(b,opts,args)))==words(pair.second),"namespace isolated "+pair.first);
    }
    args["uri"]="qbrain://alpha/resources/文档/"; args["query"]="针";
    check(slugs(payload(rpc(b,opts,args)))==std::set<std::string>{"文档/深/页"},"Unicode directory/query preserves UTF8");
    args["uri"]="qbrain://alpha/resources/absent/"; args["query"]="needle";
    const auto empty=rpc(b,opts,args);
    check(!empty.at("result").at("isError").get<bool>() && payload(empty)==J::array() && empty.at("result").at("content")[0].at("text")=="(no results)\n","empty directory retains exact successful shape");
    args["uri"]=uri; args["query"]="vectoronlyquery";
    check(payload(rpc(b,opts,args)).empty(),"no_vector suppresses mock-only candidates");
    args["no_vector"]=false;
    check(slugs(payload(rpc(b,opts,args)))==words("docs/a docs/sub/b"),"mock query-vector integration remains source and namespace scoped");
    args["mode"]="conservative";
    check(payload(rpc(b,opts,args)).empty(),"conservative retains vector suppression");
    args.erase("mode"); args["query"]="needle";
    for (const J bad : {J(nullptr),J(true),J(7),J(1.5),J::array({"private-value"}),J{{"private-value",1}}}) {
      args["uri"]=bad; uri_error(rpc(b,opts,args));
      args["source_id"]="beta"; args["query"]=""; uri_error(rpc(b,opts,args));
      args["source_id"]="alpha"; args["query"]="needle";
    }
    const std::vector<std::string> bad_uris={"", "private-uri-marker", "qbrain://alpha/resources/docs", "qbrain://alpha/unknown/docs/", "qbrain://alpha/resources/../", "qbrain://alpha/resources/docs%2f/", "qbrain://alpha/resources/docs%5c/", "qbrain://alpha/resources//", "qbrain://alpha/resources/docs//", "qbrain://alpha/resources/a\\b/", "qbrain://ALPHA/resources/docs/", "QBRAIN://alpha/resources/docs/", "qbrain://beta/resources/docs/", "qbrain://missing/resources/docs/", "qbrain://alpha/resources/"+std::string(9000,'x')+"/", std::string("qbrain://alpha/resources/")+std::string("a\0b/",4)};
    for (const auto& bad : bad_uris) {
      args["uri"]=bad; const auto denied=rpc(b,opts,args); uri_error(denied);
      if (bad.size()>4) check(denied.dump().find(bad)==std::string::npos,"URI input is not echoed");
    }
    // Valid decoded strings keep the old query then source precedence.
    args["uri"]="private-uri-marker"; args["query"]=""; args["source_id"]="beta";
    auto precedence=rpc(b,opts,args);
    check(precedence.at("result").at("isError")==true && precedence.at("result").at("content")[0].at("text")=="query required","query error precedence unchanged for URI strings");
    args["query"]="needle";
    for (const auto& pair : std::vector<std::pair<std::string,std::string>>{{"beta","source_not_allowed"},{"missing","source_not_found"},{"","invalid_source"}}) {
      args["source_id"]=pair.first; const auto p=payload(rpc(b,opts,args));
      check(p.at("error").at("code")==pair.second && p.at("error").at("field")=="source_id","source error precedes URI parsing");
    }
    // Paired present/omitted URI calls preserve legacy source coercion, not just strings.
    for (const auto& pair : std::vector<std::pair<J,std::string>>{{nullptr,"default"},{"ALPHA","alpha"},{true,"1"},{false,"0"},{7,"7"}}) {
      J paired={{"query","needle"},{"no_vector",true},{"source_id",pair.first},{"limit",20}};
      source_only(payload(rpc(b,opts,paired)),pair.second);
      paired["uri"]="qbrain://"+pair.second+"/resources/docs/";
      auto hits=payload(rpc(b,opts,paired)); source_only(hits,pair.second);
      check(slugs(hits)==words("docs/a docs/sub/b"),"paired legacy source coercion scoped results");
    }
    for (const J bad : {J(""),J::array({"alpha"}),J{{"source","alpha"}}}) {
      J paired={{"query","needle"},{"source_id",bad}};
      const auto before=rpc(b,opts,paired); paired["uri"]=uri;
      check(before.at("result")==rpc(b,opts,paired).at("result") && payload(before).at("error").at("code")=="invalid_source","paired rejected source conversion is unchanged");
    }
    {
      Env ambient("QBRAIN_SOURCE","alpha");
      for (bool null_source : {false,true}) {
        J paired={{"query","needle"},{"no_vector",true},{"limit",20}};
        if(null_source) paired["source_id"]=nullptr;
        source_only(payload(rpc(b,opts,paired)),"alpha"); paired["uri"]=uri;
        source_only(payload(rpc(b,opts,paired)),"alpha");
        paired["source_id"]="default"; paired["uri"]="qbrain://default/resources/docs/";
        source_only(payload(rpc(b,opts,paired)),"default");
      }
    }
#ifndef _WIN32
    // Windows CRT removes empty values set in-process; the actual-process driver
    // supplies the present-empty environment at process creation on both platforms.
    {
      Env ambient("QBRAIN_SOURCE",""); J paired={{"query","needle"},{"source_id",nullptr}};
      auto before=rpc(b,opts,paired); paired["uri"]=uri;
      check(before.at("result")==rpc(b,opts,paired).at("result") && payload(before).at("error").at("code")=="invalid_source","present-empty ambient source does not default");
    }
#endif
    J select={{"query","needle"},{"uri",uri}}; uri_error(rpc(b,opts,select));
    auto write=rpc(b,opts,{{"action","capture"},{"payload","{}"}},"memory_write");
    check(write.at("result").at("isError")==true && write.dump().find("write_denied")!=std::string::npos,"default-deny writes unchanged");
    check(rpc(b,opts,{{"slug","docs/a"},{"uri",true}},"get_page").at("result").at("isError")==false,"URI type rule does not affect other tools");
    check(rpc(b,opts,{{"query",123},{"no_vector",true}}).at("result").at("isError")==false,"legacy query conversion remains unchanged");
    const auto prefix=std::string(R"({"jsonrpc":"2.0","id":49,"method":"tools/call","params":{"name":"search","arguments":{"query":"needle","uri":")");
    const auto suffix=std::string(R"("}}})");
    for (const auto& raw : std::vector<std::string>{"{", prefix+"\\ud800"+suffix, prefix+"\\uZZZZ"+suffix, prefix+std::string(1,'\xff')+suffix, prefix+std::string(1,'\0')+suffix}) {
      const auto parsed=J::parse(mcp::handle_rpc_body(b,opts,raw));
      check(parsed.contains("error") && parsed.at("id").is_null() && parsed.at("error").at("code")==-32700,"malformed wire bytes/escapes remain null-id JSON-RPC parse errors");
    }
  }
  for (const auto& bytes : {std::string(1,'\xff'),std::string("\xc0\xaf",2),std::string("\xed\xa0\x80",3),std::string("a\0b",3)}) {
    const auto bad=std::string("qbrain://alpha/resources/")+bytes+"/";
    const auto r=direct(b,{{"query","needle"},{"source_id","alpha"},{"uri",bad}});
    check(!r.ok && J::parse(r.json).at("error").at("field")=="uri","direct-handler invalid UTF8/NUL rejected without wire parser");
  }
  check(sqlite3_total_changes(b.db().handle())==changes,"search/error/write-denial matrix leaves application data unchanged");
}
} // namespace
int main() {
  try {
    run(); std::cout << J({{"schema","qbrain-n49d-mcp-directory-unit-v1"},{"passed",true},{"checks",checks},{"check_count",checks.size()},{"paid_requests",0},{"base_contract_commit","cfe1ef58e244b51092c2248804b663b6c28913d7"},{"expected_full_tool_count",112},{"expected_memory_tool_count",6}}).dump() << '\n'; return 0;
  } catch (const std::exception& e) {
    std::cout << J({{"schema","qbrain-n49d-mcp-directory-unit-v1"},{"passed",false},{"checks",checks},{"failure",e.what()}}).dump() << '\n'; return 1;
  }
}
