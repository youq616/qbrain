// Independent expected quantities and lifecycle checks; no private input is echoed.
#include "qbrain/accounting/observation_command.hpp"
#include <atomic>
#include <future>
#include <iostream>
#include <thread>
using namespace qbrain;
using namespace qbrain::accounting;
namespace obs=accounting::observation;
namespace {
Json checks=Json::array();
void check(bool value,const char* label){checks.push_back({{"name",label},{"passed",value}});if(!value)throw std::runtime_error(label);}
void rejects(const std::function<void()>& f){bool rejected=false;try{f();}catch(const std::exception&){rejected=true;}check(rejected,"invalid evidence or assignment rejected");}
ai::HttpResponse chat(Json usage){return {200,Json{{"object","chat.completion"},{"usage",usage},
  {"model","PRIVATE_MODEL_SENTINEL"},{"id","PRIVATE_ID_SENTINEL"},
  {"choices",Json::array({{{"message",{{"content","PRIVATE_REPLY_SENTINEL"}}},{"finish_reason","stop"}}})}}.dump(),{},ai::HttpFailure::none};}
Json known(){return {{"prompt_tokens",100},{"completion_tokens",20},{"total_tokens",120},
  {"prompt_tokens_details",{{"cached_tokens",30},{"cache_write_tokens",10}}}};}
void quantities(){
  auto u=obs::project_usage(obs::Api::chat,chat(known()));
  check(u.state==obs::UsageState::recognized&&u.input==100&&u.output==20&&u.total==120,"reported inclusive usage");
  check(u.tokens==Values{60,30,10,20},"independent exact disjoint token buckets");
  auto partial=known();partial.erase("prompt_tokens_details");u=obs::project_usage(obs::Api::chat,chat(partial));
  check(u.tokens==Values{std::nullopt,std::nullopt,std::nullopt,20}&&u.input==100,"missing cache detail remains unknown not uncached100");
  for(int which=0;which<8;++which){auto bad=known();
    if(which==0)bad["prompt_tokens"]=true;if(which==1)bad["completion_tokens"]=-1;
    if(which==2)bad["total_tokens"]=1;if(which==3)bad["prompt_tokens_details"]["cached_tokens"]=95;
    if(which==4)bad["prompt_tokens_details"]["audio_tokens"]=1;
    if(which==5)bad["completion_tokens"]=20.1;if(which==6)bad["prompt_tokens"]=1000000001ULL;
    if(which==7)bad["unrecognized_billing"]=0;
    u=obs::project_usage(obs::Api::chat,chat(bad));check(u.state==obs::UsageState::invalid&&u.tokens==Values{},"contradictory or unsupported usage fully unknown");}
  auto response=chat(known());response.body="{\"object\":\"chat.completion\",\"usage\":{},\"usage\":{}}";
  check(obs::project_usage(obs::Api::chat,response).state==obs::UsageState::invalid,"duplicate-key usage rejected without body echo");
  response.body=std::string(1048577,'x');check(obs::project_usage(obs::Api::chat,response).state==obs::UsageState::invalid,"observation parser cap");
  response=chat(known());response.failure=ai::HttpFailure::timeout;
  check(obs::project_usage(obs::Api::chat,response).tokens==Values{},"incomplete transport never supplies usage");
  response=chat(known());check(obs::project_usage(obs::Api::rerank,response).state==obs::UsageState::unsupported,"unknown rerank billing cannot borrow chat quantities");
  response={200,R"({"object":"list","usage":{"prompt_tokens":8,"total_tokens":8},"data":[]})",{},ai::HttpFailure::none};
  u=obs::project_usage(obs::Api::embeddings,response);check(u.input==8&&u.total==8&&u.tokens==Values{},"embedding inclusive input observed without invented cache buckets");
  for(auto state:{"completed","failed","cancelled","incomplete"}){
    response={200,Json{{"object","response"},{"status",state},{"usage",{{"input_tokens",100},{"output_tokens",20},{"total_tokens",120},
      {"input_tokens_details",{{"cached_tokens",30},{"cache_write_tokens",10}}}}}}.dump(),{},ai::HttpFailure::none};
    u=obs::project_usage(obs::Api::responses,response);check(u.tokens==Values{60,30,10,20},"terminal success or failed response usage retained");
  }
  for(auto state:{"queued","in_progress","unexpected"}){
    response={200,Json{{"object","response"},{"status",state},{"usage",{{"input_tokens",100},{"output_tokens",20}}}}.dump(),{},ai::HttpFailure::none};
    check(obs::project_usage(obs::Api::responses,response).tokens==Values{},"nonterminal response never priced as complete usage");
    auto with_error=Json::parse(response.body);with_error["error"]={{"message","PRIVATE_NONTERMINAL_ERROR"}};
    with_error["usage"]["total_tokens"]=120;
    with_error["usage"]["input_tokens_details"]={{"cached_tokens",30},{"cache_write_tokens",10}};
    response.body=with_error.dump();
    u=obs::project_usage(obs::Api::responses,response);
    check(u.state==obs::UsageState::unsupported&&u.tokens==Values{},"error object cannot promote nonterminal status into priced usage");
  }
}
void capture_and_cost(){
  auto c=std::make_shared<obs::Collector>();
  {obs::Session scope(c);
    {obs::Attempt a("/chat/completions");a.finish(chat(known()),true);}
    {obs::Attempt a("/chat/completions");a.finish({429,{},"PRIVATE_ERROR_KEY",ai::HttpFailure::http_status},true);}
    {obs::Attempt a("/chat/completions");a.finish(chat(known()),true);}
    {obs::Attempt a("/responses");a.finish({0,{},"PRIVATE_CANCELLED",ai::HttpFailure::cancelled},true);}
    {obs::Attempt a("/private/path?secret");a.finish_exception(false);}
    rejects([&]{obs::Session nested(c);});
  }
  auto r=c->report(true,1);auto parsed=obs::validate_report(r);
  check(parsed.size()==5&&r["counts"]["finished"]==5&&r["recording_complete"]==true,"one start and finish per invocation");
  check(r["records"][1]["transport"]=="http_error"&&r["records"][3]["transport"]=="cancelled","failed and explicitly cancelled attempts kept");
  check(r["retry_attempts"].is_null()&&r["total_estimate"].is_null(),"no guessed retry or free cost");
  check(r.dump().find("PRIVATE_")==std::string::npos&&r.dump().find("private/path")==std::string::npos,"no response error model id path or secret persisted");
  Json rates={{"schema","qbrain-observation-rates-v1"},{"currency","USD"},{"rates",Json::array()}, {"assignments",Json::array()}};
  for(int i=1;i<=5;++i)rates["assignments"].push_back({{"sequence",i},{"call_id","a"+std::to_string(i)},{"attempt",i==3?2:1},{"stage","main"},{"rate_id","test"}});
  auto unknown=obs::price(r,rates);check(unknown["total_estimate"].is_null(),"missing rate cannot become zero");
  rates["rates"].push_back({{"rate_id","test"},{"provider","synthetic"},{"model","synthetic"},
    {"per_million",{{"input_uncached","2"},{"input_cache_read","1"},{"input_cache_write","3"},{"output","4"}}}});
  auto priced=obs::price(r,rates);
  check(priced["observed_record_cost"]["summary"]["known_subtotal"]=="0.000520000000","exact reused cost engine arithmetic on two known attempts");
  check(priced["total_estimate"].is_null(),"failed calls with unknown usage prevent total");
  check(priced["observed_record_cost"]["summary"]["retry_calls"]==1&&priced["retry_labels"]=="caller_supplied_not_inferred","explicit retry annotation not observation inference");
  auto only=std::make_shared<obs::Collector>();{obs::Session scope(only);obs::Attempt a("/chat/completions");a.finish(chat(known()),true);}
  auto one=rates;one["assignments"].erase(one["assignments"].begin()+1,one["assignments"].end());
  check(obs::price(only->report(true),one)["total_estimate"]=="0.000260000000","fully assigned observed-record estimate");
  for(int i=0;i<10;++i){auto a=rates;auto forged=r;
    if(i==0)a["assignments"].erase(a["assignments"].begin());
    if(i==1)a["assignments"][0]["sequence"]=2;
    if(i==2)a["assignments"][0]["tokens"]=Json::object();
    if(i==3)a["assignments"][0]["attempt"]=false;
    if(i==4)forged["recording_complete"]=false;
    if(i==5)forged["records"][0]["usage"]["tokens"]["input_uncached"]=500;
    if(i==6)forged["records"][0]["complete"]=1;
    if(i==7)forged["records"][0]["private_text"]="PRIVATE_SENTINEL";
    if(i==8)forged["billing_verified"]=true;
    if(i==9)forged["counts"]["finished"]=0;
    rejects([&]{obs::price(forged,a);});
  }
}
void limits_concurrency(){
  auto c=std::make_shared<obs::Collector>(obs::Collector::Writer{},2);
  {obs::Session scope(c);for(int i=0;i<3;++i){obs::Attempt a("/responses");a.finish({0,{},"ignored",ai::HttpFailure::timeout},true);}}
  auto r=c->report(true);check(r["counts"]["started"]==3&&r["counts"]["finished"]==3&&r["counts"]["dropped"]==1&&!r["recording_complete"].get<bool>(),"capacity marks incomplete without dropping invocation count");
  obs::validate_report(r);
  auto io=std::make_shared<obs::Collector>([](const obs::Event&){throw std::runtime_error("private filesystem exception");});
  {obs::Session scope(io);obs::Attempt a("/embeddings");a.finish(chat(known()),true);}
  r=io->report(true);check(r["counts"]["io_errors"]==2&&!r["recording_complete"].get<bool>()&&r.dump().find("filesystem")==std::string::npos,"sidecar failures mark gaps without exception text");
  auto parallel=std::make_shared<obs::Collector>();
  {obs::Session scope(parallel);std::vector<std::thread> workers;for(int n=0;n<8;++n)workers.emplace_back([]{for(int k=0;k<20;++k){obs::Attempt a("/chat/completions");a.finish(chat(known()),true);}});for(auto& w:workers)w.join();}
  r=parallel->report(true);check(r["counts"]["started"]==160&&r["counts"]["finished"]==160&&r["recording_complete"]==true,"worker thread observations complete and serialized");obs::validate_report(r);
  auto pending=std::make_shared<obs::Collector>();std::unique_ptr<obs::Attempt> a;
  {obs::Session scope(pending);a=std::make_unique<obs::Attempt>("/responses");}
  const auto frozen=pending->report(true);check(frozen["counts"]["pending"]==1&&frozen["records"][0]["send_invoked"].is_null()&&!frozen["recording_complete"].get<bool>(),"unfinished start not called cancellation or zero-send");
  a->finish(chat(known()),true);a.reset();check(pending->report()==frozen,"late completion cannot mutate sealed result");
  auto disabled=std::make_shared<obs::Collector>();{obs::Attempt outside("/responses");outside.finish(chat(known()),true);}check(disabled->report()["counts"]["started"]==0,"default-off no collector attached");
  auto actual=std::make_shared<obs::Collector>();{obs::Session scope(actual);auto result=ai::http_post_json("bad PRIVATE_URL","/chat/completions","PRIVATE_KEY","PRIVATE_PROMPT");check(result.failure==ai::HttpFailure::invalid_request,"original transport validation unchanged");}
  r=actual->report(true);check(r["counts"]["started"]==1&&r["records"][0]["transport"]=="invalid_request"&&r["records"][0]["send_invoked"]==false,"actual shared boundary observed before transport rejection");
  check(r.dump().find("PRIVATE_")==std::string::npos,"actual wrapper never records request material");
}
}
int main(){try{quantities();capture_and_cost();limits_concurrency();std::cout<<Json{{"schema","qbrain-n48w-native-v1"},{"passed",true},{"check_count",checks.size()},{"checks",checks}}.dump()<<'\n';return 0;}catch(const std::exception& e){std::cout<<Json{{"passed",false},{"checks",checks},{"failure",e.what()}}.dump()<<'\n';return 1;}}
