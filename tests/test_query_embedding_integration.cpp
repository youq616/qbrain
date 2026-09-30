// Actual registered operations and Brain lifetime; synthetic embeddings only.
#include "qbrain/ai/query_embedding.hpp"
#include "qbrain/ops/registry.hpp"
#include <nlohmann/json.hpp>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
using namespace qbrain;
using J=nlohmann::json;
namespace {
J checks=J::array();
void check(bool ok,const char* name){checks.push_back({{"name",name},{"passed",ok}});if(!ok)throw std::runtime_error(name);}
void env(const char* key,const char* value){
#ifdef _WIN32
  _putenv_s(key,value);
#else
  if(*value)setenv(key,value,1);else unsetenv(key);
#endif
}
void setup(Brain& b){b.open_at(":memory:");b.ensure_source("alpha");b.ensure_source("beta");b.save_config_value("embed.auto","false",false);}
J search(Brain& b,const std::string& query="needle",const std::string& source="alpha",bool remote=false,const std::string& mode="balanced",bool no_vector=false){
  ops::OpContext ctx;ctx.brain=&b;ctx.remote=remote;ctx.via_mcp=remote;ctx.args={{"query",query},{"source_id",source},{"mode",mode}};
  if(no_vector)ctx.args["no_vector"]="true";
  auto result=ops::global_registry().call("search",ctx);
  if(!result.ok){return J::parse(result.json);}
  check(result.exit_code==0,"registered search success");return J::parse(result.json);
}
void run(){
  for(const char* k:{"QBRAIN_PG_DSN","QBRAIN_SCHEMA","QBRAIN_API_KEY","OPENAI_API_KEY","QBRAIN_CHAT_MOCK"})env(k,"");
  env("QBRAIN_EMBED_MOCK","1");
  ops::register_builtin_ops();Brain b("query-cache-test");setup(b);
  PageInput in;in.source_id="alpha";in.slug="docs/one";in.title="needle";in.body="needle original evidence";
  auto p=b.put_page(in);b.replace_chunks(p.id,{in.body});
  auto chunks=b.get_chunks(p.id);auto vector=ai::embed_texts(b.config(),{"needle"});
  b.update_chunk_embedding(chunks[0].id,vector.vectors[0],vector.model);
  const auto tables_before=[&]{auto q=b.db().prepare("SELECT count(*) FROM sqlite_master WHERE type='table'");q.step();return q.column_int(0);}();
  auto before=b.query_embedding_cache().stats();auto uncached=search(b);search(b);
  check(b.query_embedding_cache().stats().loads==before.loads+2 && b.query_embedding_cache().stats().entries==0,"registered default-off behavior");
  b.save_config_value("search.query_embedding_cache","1",false);
  before=b.query_embedding_cache().stats();auto first=search(b);auto second=search(b);
  check(first==uncached && second==first,"cached search preserves complete result");
  check(b.query_embedding_cache().stats().loads==before.loads+1 && b.query_embedding_cache().stats().hits==before.hits+1,"registered search actually reuses vector");
  auto hits=b.query_embedding_cache().stats().hits;
  ops::OpContext think;think.brain=&b;think.args={{"question","needle"},{"source_id","alpha"}};
  auto thought=ops::global_registry().call("think",think);
  check(thought.ok && b.query_embedding_cache().stats().hits==hits+1,"registered think shares authorized query vector");
  auto thought_json=J::parse(thought.json);check(thought_json.value("degraded",false),"think without key remains gather-only");
  // Result caching would incorrectly leave this old title/snippet visible.
  b.db().exec("UPDATE pages SET title='needle changed evidence' WHERE id="+std::to_string(p.id));
  auto changed=search(b);check(!changed.empty() && changed[0]["title"]=="needle changed evidence","cache hit still reads live page data");
  b.soft_delete(in.slug,"alpha");check(search(b).empty(),"cache hit cannot return deleted page");
  b.restore_page(in.slug,"alpha");check(!search(b).empty(),"restored page is immediately visible");
  before=b.query_embedding_cache().stats();search(b,"needle","beta");
  check(b.query_embedding_cache().stats().loads==before.loads+1,"resolved source partitions vectors");
  before=b.query_embedding_cache().stats();search(b,"needle ","alpha");
  check(b.query_embedding_cache().stats().loads==before.loads+1,"exact query whitespace not normalized");
  before=b.query_embedding_cache().stats();search(b,"needle","alpha",false,"conservative");search(b,"needle","alpha",false,"balanced",true);
  check(b.query_embedding_cache().stats().loads==before.loads && b.query_embedding_cache().stats().hits==before.hits,"conservative and no_vector bypass embedding cache");
  b.save_config_value("mcp.allowed_sources","alpha",false);search(b,"needle","alpha",true);
  before=b.query_embedding_cache().stats();b.db().exec("UPDATE config SET value='beta' WHERE key='mcp.allowed_sources'");
  auto denied=search(b,"needle","alpha",true);
  check(denied.contains("error") && denied["error"]["code"]=="source_not_allowed","revoked source denies warm query");
  check(b.query_embedding_cache().stats().loads==before.loads && b.query_embedding_cache().stats().hits==before.hits,"source rejection precedes cache access");
  for(int part=0;part<5;++part){
    ai::query_embedding(b,"policy-key","alpha");before=b.query_embedding_cache().stats();
    if(part==0)b.config().embedding_provider="other-provider";
    if(part==1)b.config().embedding_base_url="https://synthetic.invalid/other";
    if(part==2)b.config().embedding_model="another-model";
    if(part==3)b.config().embedding_dimensions=12;
    if(part==4)b.config().embedding_api_key="synthetic-key-only";
    ai::query_embedding(b,"policy-key","alpha");
    check(b.query_embedding_cache().stats().loads==before.loads+1,"effective config rotation invalidates policy");
  }
  b.config().embedding_api_key.clear();env("QBRAIN_EMBED_MOCK","");
  before=b.query_embedding_cache().stats();auto missing=ai::query_embedding(b,"policy-key","alpha");
  check(!missing.ok && b.query_embedding_cache().stats().loads==before.loads+1 && b.query_embedding_cache().stats().entries==0,"mock-to-unconfigured-real cannot serve cached vector");
  env("QBRAIN_EMBED_MOCK","1");ai::query_embedding(b,"again","alpha");
  b.db().exec("UPDATE config SET value='true' WHERE key='search.query_embedding_cache'");
  before=b.query_embedding_cache().stats();ai::query_embedding(b,"again","alpha");ai::query_embedding(b,"again","alpha");
  check(b.query_embedding_cache().stats().entries==0 && b.query_embedding_cache().stats().loads==before.loads+2,"only literal config1 enables");
  b.save_config_value("search.query_embedding_cache","1",false);ai::query_embedding(b,"again","alpha");
  check(b.query_embedding_cache().stats().entries==1,"cache enabled after prior disable");
  b.load_config();check(b.query_embedding_cache().stats().entries==0,"configuration reload clears payload");
  ai::query_embedding(b,"again","alpha");before=b.query_embedding_cache().stats();
  ai::embed_texts(b.config(),{"again"});ai::embed_texts(b.config(),{"one","two"});
  check(b.query_embedding_cache().stats().loads==before.loads && b.query_embedding_cache().stats().hits==before.hits,"indexing and batch API unchanged");
  ai::query_embedding(b,std::string(262145,'x'),"alpha");check(b.query_embedding_cache().stats().entries==0,"oversized query bypasses retention");
  for(const auto& raw:std::vector<std::string>{std::string("nonutf8-")+char(0xff),std::string("a\0b",3)}){
    auto expected=ai::embed_texts(b.config(),{raw});before=b.query_embedding_cache().stats();
    auto a=ai::query_embedding(b,raw,"alpha");auto again=ai::query_embedding(b,raw,"alpha");
    check(a.ok && a.vectors==expected.vectors && again.vectors==expected.vectors,"byte query preserves original mock result");
    check(b.query_embedding_cache().stats().loads==before.loads+1 && b.query_embedding_cache().stats().hits==before.hits+1,"byte query safely cached without JSON coercion");
  }
  check(ai::query_cache_detail::fingerprint({"ab","c"})!=ai::query_cache_detail::fingerprint({"a","bc"}),"length framing distinguishes concatenation aliases");
  check(ai::query_cache_detail::fingerprint({"a",std::string_view("b\0c",3)})!=ai::query_cache_detail::fingerprint({"a","b"}),"length framing retains NUL suffix");
  {auto q=b.db().prepare("SELECT count(*) FROM sqlite_master WHERE type='table'");q.step();check(q.column_int(0)==tables_before,"no cache database table");}
  {Brain other("query-cache-test");setup(other);other.save_config_value("search.query_embedding_cache","1",false);ai::query_embedding(other,"again","alpha");check(other.query_embedding_cache().stats().loads==1,"same-name Brain objects isolated");}
  ai::query_embedding(b,"again","alpha");b.close();check(b.query_embedding_cache().stats().entries==0,"close clears cache");
  setup(b);check(b.query_embedding_cache().stats().entries==0,"reopen does not reuse address-identity cache");
  env("QBRAIN_EMBED_MOCK","");
}
}
int main(){try{run();std::cout<<J({{"schema","qbrain-n48v-integration-v1"},{"passed",true},{"check_count",checks.size()},{"checks",checks},{"real_network_requests",0},{"postgres_executed",false}}).dump()<<'\n';return 0;}catch(const std::exception& e){std::cout<<J({{"passed",false},{"checks",checks},{"failure",e.what()}}).dump()<<'\n';return 1;}}
