// Actual original model APIs and HTTP transport, numeric loopback only.
#include "qbrain/accounting/observation_command.hpp"
#include "qbrain/ai/chat.hpp"
#include "qbrain/ai/embed.hpp"
#include "qbrain/core/brain.hpp"
#include <iostream>
namespace obs=qbrain::accounting::observation;
using J=nlohmann::json;
int main(int argc,char** argv){
  if(argc!=3&&argc!=4)return 2;
  const std::string url=argv[1],prefix="http://127.0.0.1:";
  if(!url.starts_with(prefix))return 2;
  const auto p=url.substr(prefix.size());
  if(p.empty()||p.size()>5||p.find_first_not_of("0123456789")!=std::string::npos||std::stoi(p)<1024||std::stoi(p)>65535)return 2;
  std::vector<std::string> args={"probe","observe","--output",argv[2],"--","probe"};
  std::vector<char*> pointers;for(auto& a:args)pointers.push_back(a.data());pointers.push_back(nullptr);
  return obs::command(int(args.size()),pointers.data(),[&](int,char**){
    using namespace qbrain;
    const auto need=[](bool ok){if(!ok)throw std::runtime_error("fixture_response_changed");};
    Config cfg;cfg.embedding_base_url=url;cfg.chat_base_url=url;cfg.embedding_dimensions=3;
    cfg.embedding_model="PRIVATE_MODEL_SENTINEL";cfg.chat_model=cfg.embedding_model;
    cfg.embedding_api_key="PRIVATE_KEY_SENTINEL";cfg.chat_api_key=cfg.embedding_api_key;cfg.chat_endpoint="chat_completions";
    auto raw=[&](const char* path,const char* fixture,int timeout=2000,std::size_t cap=8192){return ai::http_post_json(url,path,"PRIVATE_KEY_SENTINEL",
      J{{"fixture",fixture},{"prompt","PRIVATE_PROMPT_SENTINEL"}}.dump(),timeout,cap);};
    if(argc==4){raw("/responses","hold",30000);return 0;}
    auto chat=ai::chat_complete(cfg,{{"user","PRIVATE_PROMPT_SENTINEL"}});need(chat.ok&&chat.input_tokens==100&&chat.output_tokens==20);
    auto embed=ai::embed_texts(cfg,{"PRIVATE_PROMPT_SENTINEL"});need(embed.ok&&embed.vectors.size()==1&&embed.vectors[0].size()==3);
    cfg.chat_endpoint="responses";need(ai::chat_complete(cfg,{{"user","PRIVATE_PROMPT_SENTINEL"}}).ok);
    need(raw("/rerank","rerank").status==200);
    for(int i=0;i<2;++i){auto r=raw("/chat/completions","error");need(r.failure==ai::HttpFailure::http_status&&r.status==429&&r.body.empty());}
    need(raw("/chat/completions","missing").status==200);
    need(raw("/responses","failed").status==200);
    need(raw("/responses","cancelled").status==200);
    need(raw("/responses","pending").status==200);
    need(raw("/chat/completions","duplicate").status==200);
    need(raw("/chat/completions","invalid").status==200);
    need(raw("/responses","oversize",2000,256).failure==ai::HttpFailure::response_too_large);
    need(raw("/responses","timeout",120).failure==ai::HttpFailure::timeout);
    need(raw("/responses","truncated").failure==ai::HttpFailure::transport);
    need(ai::http_post_json("invalid PRIVATE_URL_SENTINEL","/responses","PRIVATE_KEY_SENTINEL","PRIVATE_PROMPT_SENTINEL").failure==ai::HttpFailure::invalid_request);
    std::cout<<"{\"probe_complete\":true}\n";return 0;
  });
}
