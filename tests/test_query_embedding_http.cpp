// Invoked only by the disposable numeric-loopback provider test, never a real account.
#include "qbrain/ai/query_embedding.hpp"
#include <nlohmann/json.hpp>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
using namespace qbrain;
using J=nlohmann::json;
int main(int argc,char** argv){
  J checks=J::array();
  const auto check=[&](bool ok,const char* name){checks.push_back({{"name",name},{"passed",ok}});if(!ok)throw std::runtime_error(name);};
  try{
    if(argc!=2)throw std::runtime_error("numeric loopback endpoint required");
    std::string url=argv[1], prefix="http://127.0.0.1:";
    if(!url.starts_with(prefix))throw std::runtime_error("refuse non-loopback endpoint");
    auto port=url.substr(prefix.size());
    if(port.empty()||port.size()>5||port.find_first_not_of("0123456789")!=std::string::npos||std::stoi(port)<1024||std::stoi(port)>65535)throw std::runtime_error("refuse non-loopback endpoint");
#ifdef _WIN32
    _putenv_s("QBRAIN_EMBED_MOCK","");_putenv_s("QBRAIN_PG_DSN","");_putenv_s("OPENAI_API_KEY","");_putenv_s("QBRAIN_API_KEY","");
#else
    unsetenv("QBRAIN_EMBED_MOCK");unsetenv("QBRAIN_PG_DSN");unsetenv("OPENAI_API_KEY");unsetenv("QBRAIN_API_KEY");
#endif
    Brain b;b.open_at(":memory:");b.ensure_source("alpha");b.ensure_source("beta");b.save_config_value("search.query_embedding_cache","1",false);
    auto& c=b.config();c.embedding_provider="synthetic-local";c.embedding_base_url=url+"/v1";c.embedding_model="fixture-model";c.embedding_dimensions=3;c.embedding_api_key="n48v-synthetic-only";
    auto get=[&](std::string query="A",std::string source="alpha"){return ai::query_embedding(b,query,source);};
    auto first=get();auto second=get();check(first.ok&&first.vectors==second.vectors,"same query wire vector copied");
    check(b.query_embedding_cache().stats().loads==1&&b.query_embedding_cache().stats().hits==1,"second query avoids HTTP loader");
    check(get("A","beta").ok,"second source");check(get("B").ok,"second query");
    b.db().exec("UPDATE config SET value='0' WHERE key='search.query_embedding_cache'");check(get().ok&&get().ok,"off performs both requests");
    b.db().exec("UPDATE config SET value='1' WHERE key='search.query_embedding_cache'");check(get().ok&&get().ok,"reenable does not revive off-era entry");
    auto before=b.query_embedding_cache().stats();
    check(ai::embed_texts(c,{"A"}).ok&&ai::embed_texts(c,{"A"}).ok,"indexing single-text calls never use query cache");
    check(b.query_embedding_cache().stats().loads==before.loads,"uncached API cannot increment cache counter");
    check(!get("bad").ok&&!get("bad").ok,"malformed provider result not cached");
    c.embedding_api_key="n48v-rotated-synthetic";check(get().ok&&get().ok,"credential rotation misses once");
    c.embedding_base_url=url+"/v2";check(get().ok,"endpoint rotation");
    c.embedding_dimensions=2;auto resized=get();check(resized.ok&&resized.vectors.size()==1&&resized.vectors[0].size()==2,"dimension rotation");
    c.embedding_model="fixture-other";check(get().model=="fixture-other","model rotation");
    std::cout<<J({{"schema","qbrain-n48v-http-client-v1"},{"passed",true},{"checks",checks},{"check_count",checks.size()},{"real_paid_provider",false}}).dump()<<'\n';return 0;
  }catch(const std::exception& e){std::cout<<J({{"passed",false},{"checks",checks},{"failure",e.what()}}).dump()<<'\n';return 1;}
}
