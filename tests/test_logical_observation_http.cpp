// Executes only numeric-loopback fixtures and local entry points. No account/client.
#include "qbrain/accounting/logical_command.hpp"
#include "qbrain/ai/chat.hpp"
#include "qbrain/ai/embed.hpp"
#include "qbrain/search/rerank.hpp"
#include <chrono>
#include <thread>
using namespace qbrain;
namespace l=accounting::logical;
using J=nlohmann::json;
namespace {
void need(bool ok){if(!ok)throw std::runtime_error("fixture_check_failed");}
void env(const char* k,const char* v){
#ifdef _WIN32
 _putenv_s(k,v);
#else
 if(*v)setenv(k,v,1);else unsetenv(k);
#endif
}
void clean(){for(const auto* k:{"QBRAIN_PG_DSN","QBRAIN_EMBED_MOCK","QBRAIN_CHAT_MOCK","OPENAI_API_KEY","QBRAIN_API_KEY","LOCALAPPDATA"})env(k,"");}
int dispatch(int argc,char** argv){
 if(argc>1&&std::string(argv[1])=="observe-model")return l::command(argc,argv,dispatch);
 need(argc>=2);clean();Config c;c.chat_model="PRIVATE_MODEL_MARKER";c.embedding_model="PRIVATE_MODEL_MARKER";
 const std::string mode=argv[1];
 if(mode=="local"){
   need(!ai::chat_complete(c,{{"user","PRIVATE_PROMPT_MARKER"}}).ok);
   need(!ai::embed_texts(c,{"PRIVATE_PROMPT_MARKER"}).ok);
   c.embedding_dimensions=-1;need(!ai::embed_texts(c,{"PRIVATE_PROMPT_MARKER"}).ok);
   c.embedding_dimensions=0;env("QBRAIN_EMBED_MOCK","1");
   need(ai::embed_texts(c,{"PRIVATE_PROMPT_MARKER"}).ok);env("QBRAIN_EMBED_MOCK","");
   std::cout<<"local-entry-fixtures\n";return 0;
 }
 if(mode=="many"){
   env("QBRAIN_EMBED_MOCK","1");
   for(int i=0;i<520;++i)need(ai::embed_texts(c,{"synthetic"}).ok);
   env("QBRAIN_EMBED_MOCK","");std::cout<<"all-api-results-success\n";return 0;
 }
 if(mode=="exception"){
   l::invoke(l::Kind::chat,[](auto&)->ai::ChatResult{throw std::runtime_error("PRIVATE_EXCEPTION_MARKER");});return 0;
 }
 if(mode=="hold"){
   return l::invoke(l::Kind::chat,[](auto&)->ai::ChatResult{
     std::this_thread::sleep_for(std::chrono::seconds(60));return {};
   }).ok?0:1;
 }
 need(mode=="wire"&&argc==3);
 const std::string base=argv[2],prefix="http://127.0.0.1:";
 need(base.starts_with(prefix));
 const auto port=base.substr(prefix.size());
 need(!port.empty()&&port.size()<=5&&port.find_first_not_of("0123456789")==std::string::npos&&std::stoi(port)>=1024&&std::stoi(port)<=65535);
 need(!ai::chat_complete(c,{{"user","PRIVATE_PROMPT_MARKER"}}).ok);
 c.embedding_dimensions=-1;need(!ai::embed_texts(c,{"PRIVATE_PROMPT_MARKER"}).ok);c.embedding_dimensions=3;
 env("QBRAIN_EMBED_MOCK","1");need(ai::embed_texts(c,{"mock"}).ok);need(ai::embed_image(c,"PRIVATE_IMAGE_MARKER").ok);env("QBRAIN_EMBED_MOCK","");
 c.chat_api_key="PRIVATE_KEY_MARKER";c.embedding_api_key="PRIVATE_KEY_MARKER";
 c.chat_base_url=base;c.embedding_base_url=base;c.rerank_base_url=base;c.chat_endpoint="chat/completions";
 need(ai::embed_texts(c,{"valid"}).ok);
 need(ai::chat_complete(c,{{"user","normal"}}).ok);
 c.chat_endpoint="responses";need(ai::chat_complete(c,{{"user","pending"}}).ok);c.chat_endpoint="chat/completions";
 need(ai::embed_image(c,"PRIVATE_IMAGE_MARKER").unavailable);
 SearchHit hit;hit.page_id=1;hit.source_id="alpha";hit.slug="synthetic";hit.title="PRIVATE_PROMPT_MARKER";hit.snippet="PRIVATE_PROMPT_MARKER";
 search::RerankerOpts opts;opts.enabled=true;opts.use_llm=true;
 c.rerank_api_type="native";need(search::apply_reranker(c,"native",{hit},opts).size()==1);
 c.rerank_api_type="chat";need(search::apply_reranker(c,"chat",{hit},opts).size()==1);
 need(ai::embed_texts(c,{"repeat"}).ok);need(ai::embed_texts(c,{"repeat"}).ok);
 need(!ai::embed_texts(c,{"malformed"}).ok);
 auto outside=ai::http_post_json(base,"/direct","PRIVATE_KEY_MARKER","{}");need(outside.status==200);
 opts.llm_response_for_test=[&](const auto&,const auto&){
   need(ai::embed_texts(c,{"callback"}).ok);need(ai::chat_complete(c,{{"user","normal"}}).ok);return "[0]";
 };
 need(search::apply_reranker(c,"callback",{hit},opts).size()==1);
 std::cout<<"wire-entry-fixtures\n";return 0;
}
}
int main(int argc,char** argv){try{return dispatch(argc,argv);}catch(...){std::cerr<<"fixture_exception\n";return 2;}}
