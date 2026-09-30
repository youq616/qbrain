// N49A: real combined Brain/registry/cache/context/observer behavior. Synthetic only.
#include "qbrain/accounting/logical_observation.hpp"
#include "qbrain/ai/query_embedding.hpp"
#include "qbrain/context/context.hpp"
#include "qbrain/memory/session_memory.hpp"
#include "qbrain/ops/registry.hpp"
#include "qbrain/search/rerank.hpp"
#include <cstdlib>
#include <iostream>
#include <functional>
#include <stdexcept>
#include <string>

using namespace qbrain;
using J = nlohmann::json;
namespace logical = accounting::logical;
namespace {
J checks = J::array(), phases = J::array();
const std::string uri = "qbrain://alpha/resources/docs/";
const std::string private_query = "SYNTHETIC_QUERY_MARKER";
const std::string private_body = "SYNTHETIC_BODY_MARKER";
void need(bool value, const std::string& name) {
  checks.push_back({{"name", name}, {"passed", value}});
  if (!value) throw std::runtime_error(name);
}
void env(const char* key, const char* value) {
#ifdef _WIN32
  _putenv_s(key, value);
#else
  if (*value) setenv(key, value, 1); else unsetenv(key);
#endif
}
void clean() {
  for (const char* key : {"QBRAIN_PG_DSN", "QBRAIN_SCHEMA", "QBRAIN_API_KEY",
       "OPENAI_API_KEY", "QBRAIN_CHAT_MOCK", "QBRAIN_EMBED_MOCK"}) env(key, "");
}
void setup(Brain& b, bool cache = true) {
  b.open_at(":memory:"); b.ensure_source("alpha"); b.ensure_source("beta");
  b.save_config_value("embed.auto", "false", false);
  b.save_config_value("search.query_embedding_cache", cache ? "1" : "0", false);
  b.config().embedding_api_key.clear(); b.config().chat_api_key.clear();
}
void page(Brain& b) {
  PageInput p; p.source_id="alpha"; p.slug="docs/a";
  p.title=private_query; p.body=private_body;
  const auto saved=b.put_page(p); b.replace_chunks(saved.id,{p.body});
  const auto chunks=b.get_chunks(saved.id);
  const auto embedding=ai::embed_texts(b.config(),{private_query});
  need(embedding.ok,"seed uses valid synthetic vector");
  b.update_chunk_embedding(chunks.at(0).id,embedding.vectors.at(0),embedding.model);
}
struct Capture {
  std::shared_ptr<logical::Collector> collector=std::make_shared<logical::Collector>();
  logical::Session session{collector};
  J finish(const std::string& name) {
    auto http=session.http_collector(); session.detach();
    J result={{"logical",collector->report(true,0)}, {"http",http->report(true,0)}};
    need(result["logical"]["recording_complete"]==true,name+": logical records complete");
    need(result["http"]["recording_complete"]==true,name+": HTTP records complete");
    need(result["logical"]["total_estimate"].is_null() &&
         result["http"]["total_estimate"].is_null(),name+": no invented cost");
    need(result["logical"]["process_exit"].is_null() &&
         result["http"]["process_exit"].is_null(),name+": no premature process-exit claim");
    const auto text=result.dump();
    for (const std::string marker : {private_query,private_body,std::string("SYNTHETIC_KEY_MARKER"),
         std::string("SYNTHETIC_MODEL_MARKER"),std::string("127.0.0.1"),std::string("synthetic.invalid")})
      need(text.find(marker)==std::string::npos,name+": metadata excludes "+marker);
    phases.push_back({{"name",name},{"observation",result}}); return result;
  }
};
std::size_t entries(const J& r,const std::string& entry) {
  std::size_t count=0;
  for(const auto& row:r["logical"]["records"]) if(row["entry"]==entry) ++count;
  return count;
}
void no_calls(const J& r,const std::string& name) {
  need(r["logical"]["records"].empty() && r["http"]["records"].empty(),name+": zero logical and HTTP calls");
}
J search(Brain& b,bool remote=false,const std::string& mode="balanced",bool no_vector=false) {
  ops::OpContext c; c.brain=&b; c.remote=remote; c.via_mcp=remote;
  c.args={{"query",private_query},{"source_id","alpha"},{"mode",mode}};
  if(no_vector)c.args["no_vector"]="true";
  return J::parse(ops::global_registry().call("search",c).json);
}
template<class F> void error(F&& f,const std::string& expected) {
  std::string actual="accepted";
  try { f(); } catch(const memory::Error& e) { actual=e.what(); }
  need(actual==expected,"expected rejection: "+expected);
}
ai::ChatResult answer() { ai::ChatResult r;r.ok=true;r.content=R"({"l0":"Synthetic","l1":"Synthetic result"})";return r; }
int64_t scalar(Brain& b,const std::string& sql) {auto s=b.db().prepare(sql);need(s.step(),"scalar row exists");return s.column_int(0);}

void cache_and_registry() {
  Brain b;setup(b,false);page(b);
  {Capture c;ai::query_embedding(b,private_query,"alpha");ai::query_embedding(b,private_query,"alpha");
   auto r=c.finish("default-off");need(entries(r,"embed_texts")==2,"default-off observes two actual embedding entries");}
  b.save_config_value("search.query_embedding_cache","1",false);
  {Capture c;auto first=search(b);auto second=search(b);
   need(!first.empty()&&first==second,"registered cold and warm search preserve exact live result");
   auto r=c.finish("cold-warm-registry");need(entries(r,"embed_texts")==1,"one miss plus one hit records exactly one embedding entry");
   need(r["http"]["records"].empty(),"mock path has no HTTP attempts");
   need(b.query_embedding_cache().stats().hits==1,"registered warm query is a real cache hit");}
  {Capture c;b.db().exec("UPDATE pages SET title='CHANGED LIVE TITLE' WHERE source_id='alpha'");
   auto updated=search(b);need(!updated.empty()&&updated[0]["title"]=="CHANGED LIVE TITLE","warm vector reads changed page evidence");
   b.soft_delete("docs/a","alpha");need(search(b).empty(),"warm vector cannot resurrect deleted evidence");
   b.restore_page("docs/a","alpha");need(!search(b).empty(),"restored live evidence immediately visible");
   auto r=c.finish("live-evidence");need(entries(r,"embed_texts")==0,"live-evidence hits do not invent embedding calls");}
  b.save_config_value("mcp.allowed_sources","alpha",false);
  need(!search(b,true).empty(),"authorized remote query warms alpha vector before revocation");
  need(b.query_embedding_cache().stats().entries==1,"alpha vector is retained before revocation");
  {const auto before=b.query_embedding_cache().stats();Capture c;
   b.db().exec("UPDATE config SET value='beta' WHERE key='mcp.allowed_sources'");
   need(b.query_embedding_cache().stats().entries==before.entries,"direct ACL revocation does not cold-clear the vector");
   auto denied=search(b,true);
   need(denied["error"]["code"]=="source_not_allowed","revoked source rejected on warm vector");
   auto r=c.finish("source-revocation");no_calls(r,"source-revocation");
   need(b.query_embedding_cache().stats().hits==before.hits && b.query_embedding_cache().stats().loads==before.loads &&
        b.query_embedding_cache().stats().entries==before.entries,
        "source revocation precedes cache access");}
  {Capture c;search(b,false,"conservative");search(b,false,"balanced",true);
   auto r=c.finish("no-vector");need(entries(r,"embed_texts")==0,"conservative and no-vector perform no embedding entry");}
  {Capture c;ai::query_embedding(b,private_query,"beta");
   b.config().embedding_provider="SYNTHETIC_MODEL_MARKER";ai::query_embedding(b,private_query,"alpha");
   auto r=c.finish("partition-change");need(entries(r,"embed_texts")==2,"source and effective policy changes miss separately");}
  {Capture c;b.config().embedding_dimensions=-1;auto invalid=ai::query_embedding(b,private_query,"alpha");
   need(!invalid.ok && b.query_embedding_cache().stats().entries==0,"invalid policy clears cached vector and fails");
   auto r=c.finish("invalid-policy");need(entries(r,"embed_texts")==1 && r["logical"]["records"][0]["path"]=="invalid_input",
     "invalid policy retains true logical failure path");}
  b.config().embedding_dimensions=3;
  ai::query_embedding(b,private_query,"alpha");env("QBRAIN_EMBED_MOCK","");
  {Capture c;auto missing=ai::query_embedding(b,private_query,"alpha");
   need(!missing.ok && b.query_embedding_cache().stats().entries==0,"mock-to-real cannot reuse mock vector");
   auto r=c.finish("missing-credentials");need(entries(r,"embed_texts")==1 && r["logical"]["records"][0]["path"]=="missing_credentials",
     "missing credentials recorded without fabricated HTTP call");need(r["http"]["records"].empty(),"no credentials sends no HTTP");}
  env("QBRAIN_EMBED_MOCK","1");ai::query_embedding(b,private_query,"alpha");
  {Capture c;Brain moved(std::move(b));ai::query_embedding(moved,private_query,"alpha");
   need(b.is_open()==false && moved.is_open(),"move keeps sole database/cache owner");
   moved.close();need(moved.query_embedding_cache().stats().entries==0,"close clears payload");
   setup(moved);ai::query_embedding(moved,private_query,"alpha");
   auto r=c.finish("move-close-reopen");need(entries(r,"embed_texts")==1,"move hit then reopened miss has one real call");}
}

void nested_cache() {
  Brain b;setup(b);SearchHit hit;hit.page_id=1;hit.source_id="alpha";hit.slug="docs/a";hit.title=private_body;
  search::RerankerOpts opts;opts.enabled=true;opts.use_llm=true;
  opts.llm_response_for_test=[&](const auto&,const auto&){
    need(ai::query_embedding(b,private_query,"alpha").ok,"nested cold mock succeeds");
    need(ai::query_embedding(b,private_query,"alpha").ok,"nested warm mock succeeds");return "[0]";
  };
  Capture c;auto result=search::apply_reranker(b.config(),private_query,{hit},opts);
  need(result.size()==1&&result[0].page_id==1,"nested callback preserves reranker identity");
  auto r=c.finish("nested-cache");need(r["logical"]["records"].size()==2,"one rerank and one actual embedding entry");
  const auto& outer=r["logical"]["records"][0];const auto& inner=r["logical"]["records"][1];
  need(outer["entry"]=="apply_reranker"&&outer["path"]=="custom_callback"&&outer["fallback_taken"]==false,
       "actual rerank callback returns without fallback");
  need(inner["entry"]=="embed_texts"&&inner["parent_sequence"]==outer["sequence"]&&inner["parent_relation"]=="nested",
       "cold embedding attributed to real outer rerank; hit adds no child");
}

struct ReadWatch {
  sqlite3* db;int content_reads=0;
  explicit ReadWatch(Brain& b):db(b.db().handle()) {
    need(sqlite3_set_authorizer(db,[](void* p,int action,const char* table,const char* column,const char*,const char*){
      auto& self=*static_cast<ReadWatch*>(p);
      if(action==SQLITE_READ&&table&&column&&std::string(table)=="pages"&&
         (std::string(column)=="body"||std::string(column)=="title")){++self.content_reads;return SQLITE_DENY;}
      return SQLITE_OK;
    },this)==SQLITE_OK,"authorizer installed");
  }
  ~ReadWatch(){sqlite3_set_authorizer(db,nullptr,nullptr);}
};
void context_boundaries() {
  for(int kind=0;kind!=4;++kind) {
    Brain b;setup(b);page(b);b.save_config_value("context.external_summary","allow",false);
    context::summary(b,"alpha",uri);ai::query_embedding(b,private_query,"alpha");
    if(kind==0)b.db().exec("DROP TRIGGER ctx_page_insert;CREATE TRIGGER ctx_page_insert AFTER INSERT ON pages BEGIN SELECT 1; END");
    if(kind==1)b.db().exec("ALTER TABLE context_cache ADD COLUMN unknown TEXT");
    if(kind==2)b.db().exec("CREATE TEMP TABLE pages(untrusted TEXT)");
    storage::Database::Statement pending;
    if(kind==3){pending=b.db().prepare("INSERT INTO config(key,value) VALUES('caller.a','keep'),('caller.b','keep') RETURNING key");
      need(pending.step()&&sqlite3_get_autocommit(b.db().handle())!=0,"pending implicit writer has autocommit flag set");}
    const auto expected=kind==0?"context_schema_incomplete":kind==1?"context_schema_version_unsupported":
                        kind==2?"context_sqlite_schema_context":"context_transaction_active";
    int provider=0;auto callback=[&](const auto&,int){++provider;ai::query_embedding(b,private_query,"alpha");return answer();};
    Capture c;
    {ReadWatch watch(b);
      error([&]{context::summary(b,"alpha",uri,"model",callback);},expected);
      error([&]{context::read(b,"alpha",uri);},expected);
      error([&]{context::read(b,"alpha",uri+"a","L2");},expected);
      need(watch.content_reads==0,"invalid preflight reads no page title/body");}
    need(provider==0,"invalid preflight invokes no callback");
    auto r=c.finish("preflight-"+std::to_string(kind));no_calls(r,"preflight");
    if(kind==3){need(sqlite3_txn_state(b.db().handle(),nullptr)==SQLITE_TXN_WRITE,"rejected preflight preserves caller writer");
      need(pending.step()&&!pending.step(),"caller can finish both RETURNING rows");
      need(scalar(b,"SELECT count(*) FROM config WHERE key IN ('caller.a','caller.b')")==2,"caller rows commit on caller completion");}
  }
  {Brain b;setup(b);page(b);context::summary(b,"alpha",uri);int provider=0;Capture c;
   auto callback=[&](const auto&,int){++provider;return answer();};
   error([&]{context::summary(b,"alpha",uri,"model",callback);},"external_summary_denied");
   need(provider==0,"external-summary consent required with observer active");no_calls(c.finish("summary-consent"),"summary-consent");}
  {Brain b;setup(b);page(b);b.save_config_value("context.external_summary","allow",false);context::summary(b,"alpha",uri);
   storage::Database::Statement pending;int provider=0;Capture c;
   auto callback=[&](const auto&,int){++provider;
     need(!b.db().transaction_pending(),"context releases read snapshot before callback");
     need(ai::query_embedding(b,private_query,"alpha").ok,"admitted callback's true embedding call succeeds");
     pending=b.db().prepare("INSERT INTO config(key,value) VALUES('late.a','keep'),('late.b','keep') RETURNING key");
     need(pending.step(),"callback starts pending writer");return answer();};
   error([&]{context::summary(b,"alpha",uri,"model",callback);},"context_transaction_active");
   need(provider==1 && sqlite3_txn_state(b.db().handle(),nullptr)==SQLITE_TXN_WRITE,"late publication rejection preserves callback ownership");
   need(pending.step()&&!pending.step(),"late caller completes RETURNING cursor");
   need(scalar(b,"SELECT count(*) FROM config WHERE key IN ('late.a','late.b')")==2,"late caller rows retained");
   auto r=c.finish("late-writer");need(entries(r,"embed_texts")==1,"past authorized callback call retained despite rejected publication");}
  {Brain b;setup(b);page(b);b.save_config_value("context.external_summary","allow",false);context::summary(b,"alpha",uri);
   int provider=0;Capture c;auto callback=[&](const auto&,int){++provider;b.db().exec("UPDATE config SET value='deny' WHERE key='context.external_summary'");return answer();};
   error([&]{context::summary(b,"alpha",uri,"model",callback);},"external_summary_denied");
   need(provider==1 && b.get_config_value("context.external_summary")=="deny","late consent revocation retained and prevents publication");
   no_calls(c.finish("late-consent"),"callback is not an instrumented model API");}
}

void memory_consent_and_forget() {
  Brain b;setup(b);ai::query_embedding(b,private_query,"alpha");
  need(b.query_embedding_cache().stats().entries==1,"memory lifecycle starts with a retained alpha vector");
  J payload={{"session_id","synthetic-session"},{"fragment_id","0-1"},
    {"messages",J::array({{{"role","user"},{"content","I prefer native Windows tools."}}})}};
  Capture c;b.db().exec("INSERT INTO config(key,value) VALUES('memory.writeback','off') ON CONFLICT(key) DO UPDATE SET value=excluded.value");
  need(b.query_embedding_cache().stats().entries==1,"capture-off policy transition leaves vector warm");
  need(memory::capture(b,"alpha",payload)["status"]=="skipped","observation and warm cache do not enable capture");
  b.db().exec("UPDATE config SET value='salient' WHERE key='memory.writeback'");
  need(b.query_embedding_cache().stats().entries==1,"local capture policy transition leaves vector warm");
  auto saved=memory::capture(b,"alpha",payload);const auto id=saved["event_id"].get<std::string>();
  int provider=0;auto callback=[&](const auto&,int){++provider;return answer();};
  error([&]{memory::extract(b,"alpha",id,"model",callback);},"external_extraction_denied");
  need(provider==0,"memory model extraction keeps independent consent gate");
  need(memory::extract(b,"alpha",id)["item_count"]==1,"explicit local extraction still works");
  need(b.query_embedding_cache().stats().entries==1,"vector remains warm before forget");
  memory::forget(b,"alpha",id);
  need(memory::read(b,"alpha")["items"].empty(),"forgotten memory excluded with warm vector and active observer");
  need(memory::capture(b,"alpha",payload)["status"]=="forgotten","same evidence cannot resurrect forgotten memory");
  need(b.query_embedding_cache().stats().entries==1,"forget and tombstone checks retain vector without reloading it");
  no_calls(c.finish("memory-consent-forget"),"local lifecycle preserves zero model calls");
}

void wire(const std::string& url) {
#ifndef _WIN32
  throw std::runtime_error("native wire qualification requires Windows");
#else
  const std::string prefix="http://127.0.0.1:";
  need(url.starts_with(prefix),"numeric loopback only");const auto port=url.substr(prefix.size());
  need(!port.empty()&&port.size()<=5&&port.find_first_not_of("0123456789")==std::string::npos&&
       std::stoi(port)>=1024&&std::stoi(port)<=65535,"bounded numeric loopback port");
  Brain b;setup(b);auto& config=b.config();config.embedding_base_url=url;
  config.embedding_provider="synthetic-only";config.embedding_model="SYNTHETIC_MODEL_MARKER";
  config.embedding_api_key="SYNTHETIC_KEY_MARKER";config.embedding_dimensions=3;
  Capture c;need(ai::query_embedding(b,private_query,"alpha").ok,"wire miss succeeds");
  need(ai::query_embedding(b,private_query,"alpha").ok,"wire hit succeeds");
  SearchHit hit;hit.page_id=1;hit.source_id="alpha";hit.slug="docs/a";hit.title=private_body;
  search::RerankerOpts opts;opts.enabled=true;opts.use_llm=true;
  opts.llm_response_for_test=[&](const auto&,const auto&){
    need(ai::query_embedding(b,private_query,"beta").ok,"nested source miss succeeds");
    need(ai::query_embedding(b,private_query,"beta").ok,"nested source hit succeeds");return "[0]";};
  need(search::apply_reranker(config,private_query,{hit},opts).size()==1,"wire nested rerank returns");
  auto r=c.finish("wire");need(entries(r,"embed_texts")==2&&entries(r,"apply_reranker")==1,"wire count excludes both cache hits");
  need(r["http"]["records"].size()==2&&r["logical"]["http_links"].size()==2,"exactly two real HTTP attempts linked");
  const auto& links=r["logical"]["http_links"];
  need(links[0]["logical_sequence"]==1&&links[1]["logical_sequence"]==3&&
       links[0]["association"]=="innermost"&&links[1]["association"]=="innermost","HTTP attaches to actual embedding, never outer rerank or cache hit");
  need(r["logical"]["records"][2]["parent_sequence"]==2,"nested wire entry retains actual rerank parent");
  need(b.query_embedding_cache().stats().hits==2&&b.query_embedding_cache().stats().loads==2,"wire cache counters match calls");
#endif
}
}
int main(int argc,char** argv) {
  try {
    clean();ops::register_builtin_ops();
    if(argc==2) wire(argv[1]);
    else {
      need(argc==1,"usage: optional numeric loopback URL only");env("QBRAIN_EMBED_MOCK","1");
      cache_and_registry();nested_cache();context_boundaries();memory_consent_and_forget();
    }
    clean();std::cout<<J({{"schema","qbrain-n49a-integration-v1"},{"passed",true},
      {"check_count",checks.size()},{"checks",checks},{"phases",phases},{"paid_provider_calls",0}}).dump()<<'\n';return 0;
  } catch(const std::exception& e) {
    clean();std::cout<<J({{"passed",false},{"failure",e.what()},{"check_count",checks.size()},
      {"checks",checks},{"phases",phases}}).dump()<<'\n';return 1;
  }
}
