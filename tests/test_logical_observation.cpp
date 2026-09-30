#include "qbrain/accounting/logical_command.hpp"
#include "qbrain/ai/chat.hpp"
#include "qbrain/ai/embed.hpp"
#include "qbrain/search/rerank.hpp"
#include <atomic>
#include <future>
#include <iostream>
#include <thread>
using namespace qbrain;
namespace l=accounting::logical;
namespace h=accounting::observation;
using J=nlohmann::json;
namespace {
J checks=J::array();
void check(bool x,const char* name){checks.push_back({{"name",name},{"passed",x}});if(!x)throw std::runtime_error(name);}
void env(const char* key,const char* value){
#ifdef _WIN32
 _putenv_s(key,value);
#else
 if(*value)setenv(key,value,1);else unsetenv(key);
#endif
}
void clean(){
 for(const auto* key:{"QBRAIN_PG_DSN","OPENAI_API_KEY","QBRAIN_API_KEY","QBRAIN_CHAT_MOCK",
                      "QBRAIN_EMBED_MOCK","LOCALAPPDATA"})env(key,"");
}
struct Capture {
 std::shared_ptr<l::Collector> c=std::make_shared<l::Collector>();
 l::Session session{c};
 std::pair<J,J> finish(){
   session.detach();auto http=session.http_collector()->report(true,0);
   auto logical=c->report(true,0);l::verify(logical,http);return {logical,http};
 }
};
void original_entries(){
 Config cfg;cfg.embedding_model="synthetic-model";cfg.chat_model="synthetic-model";
 clean();
 auto chat_before=ai::chat_complete(cfg,{{"user","PRIVATE_PROMPT"}});
 auto embed_before=ai::embed_texts(cfg,{"PRIVATE_PROMPT"});
 auto image_before=ai::embed_image(cfg,"PRIVATE_IMAGE");
 Capture capture;
 auto chat=ai::chat_complete(cfg,{{"user","PRIVATE_PROMPT"}});
 auto embed=ai::embed_texts(cfg,{"PRIVATE_PROMPT"});
 auto image=ai::embed_image(cfg,"PRIVATE_IMAGE");
 check(chat.ok==chat_before.ok&&chat.error==chat_before.error&&chat.failure_kind==chat_before.failure_kind,"chat output unchanged");
 check(embed.ok==embed_before.ok&&embed.error==embed_before.error&&embed.model==embed_before.model,"text output unchanged");
 check(image.ok==image_before.ok&&image.unavailable==image_before.unavailable&&image.error==image_before.error,"image unavailable unchanged");
 auto empty=ai::embed_texts(cfg,{});
 check(empty.ok&&empty.vectors.empty(),"empty batch retains success");
 cfg.embedding_dimensions=-1;
 check(!ai::embed_texts(cfg,{"input"}).ok,"invalid dimensions retains failure");
 cfg.embedding_dimensions=0;
 check(ai::embed_image(cfg,{}).unavailable,"empty image retains fallback");
 env("QBRAIN_EMBED_MOCK","1");
 auto mock=ai::embed_texts(cfg,{"PRIVATE_PROMPT"});auto mock_image=ai::embed_image(cfg,"PRIVATE_IMAGE");
 check(mock.ok&&mock_image.ok&&mock_image.mock,"mock paths retain outputs");
 env("QBRAIN_EMBED_MOCK","");
 const auto [log,http]=capture.finish();
 check(http["counts"]["started"]==0,"preflight mock and empty are never HTTP");
 const std::vector<std::string> paths={"missing_credentials","missing_credentials","missing_credentials",
   "empty_input","invalid_input","invalid_input","local_mock","local_mock"};
 check(log["records"].size()==paths.size(),"one record for each actual API entry");
 for(std::size_t i=0;i<paths.size();++i){
   const auto& r=log["records"][i];
   check(r["path"]==paths[i]&&r["return_state"]=="returned"&&r["parent_sequence"].is_null(),"exact preflight path");
   check(r["tokens"].is_null()&&r["cost"].is_null()&&r["price"].is_null(),"logical entries not billed");
 }
 check(log["records"][2]["fallback_taken"]==true&&log["records"][2]["api_result_ok"]==false,"image fallback distinct from API success");
 const auto text=log.dump()+http.dump();
 for(const auto* secret:{"PRIVATE_PROMPT","PRIVATE_IMAGE","synthetic-model","missing chat API key"})
   check(text.find(secret)==std::string::npos,"sidecars contain no private string");
 check(log["process_exit"].is_null()&&log["stdout_complete"].is_null(),"final process/output unknown");
}
void reranking(){
 clean();Config cfg;
 SearchHit hit;hit.page_id=1;hit.source_id="alpha";hit.slug="docs/test";hit.title="needle";hit.snippet="private snippet";
 std::vector<SearchHit> input{hit};search::RerankerOpts opts;
 Capture capture;
 auto disabled=search::apply_reranker(cfg,"needle",input,opts);
 check(disabled.size()==1&&disabled[0].title==hit.title,"disabled reranker unchanged");
 opts.enabled=true;
 check(search::apply_reranker(cfg,"needle",input,opts).size()==1,"local baseline kept");
 opts.use_llm=true;
 check(search::apply_reranker(cfg,"needle",input,opts).size()==1,"missing chat keeps local fallback");
 cfg.rerank_api_type="native";
 check(search::apply_reranker(cfg,"needle",input,opts).size()==1,"native missing credentials falls back");
 opts.llm_response_for_test=[](const auto&,const auto&)->std::string{throw std::runtime_error("PRIVATE_CALLBACK_ERROR");};
 check(search::apply_reranker(cfg,"needle",input,opts).size()==1,"callback exception remains fail-open");
 opts.llm_response_for_test=[](const auto&,const auto&){return "[0]";};
 search::apply_reranker(cfg,"needle",input,opts);
 const auto [log,http]=capture.finish();const auto& r=log["records"];
 check(r.size()==7&&http["counts"]["started"]==0,"six rerank calls plus one nested chat no HTTP");
 check(r[0]["path"]=="disabled"&&r[1]["path"]=="local_baseline","disabled/local labeled");
 check(r[2]["fallback_taken"]==true&&r[2]["api_result_ok"].is_null(),"rerank return not model success");
 check(r[3]["entry"]=="chat_complete"&&r[3]["parent_sequence"]==3&&r[3]["path"]=="missing_credentials","nested chat belongs to reranker");
 check(r[4]["path"]=="missing_credentials"&&r[4]["fallback_taken"]==true,"native rejection attributed");
 check(r[5]["path"]=="custom_callback"&&r[5]["fallback_taken"]==true,"callback failure labeled");
 check(r[6]["path"]=="custom_callback"&&r[6]["fallback_taken"]==false,"valid callback positive");
 check(log.dump().find("PRIVATE_CALLBACK_ERROR")==std::string::npos,"caught callback text not retained");
}
void synthetic_http(){ // Structural correlation only; not claimed network traffic.
 Capture capture;
 {
   l::Call parent(l::Kind::rerank);parent.path(l::Path::remote_candidate);
   {
     l::Call child(l::Kind::chat);child.path(l::Path::remote_candidate);
     h::Attempt attempt("/responses");
     ai::HttpResponse response;response.status=200;response.body=R"({"object":"response","status":"queued","error":{"message":"PRIVATE"},"output_text":"x","usage":{"input_tokens":4}})";
     attempt.finish(response,true);child.returned(true);
   }
   parent.fallback(false);parent.returned();
 }
 {
   h::Attempt outside("/embeddings");ai::HttpResponse response;
   response.failure=ai::HttpFailure::cancelled;outside.finish(response,true);
 }
 auto [log,http]=capture.finish();const auto& links=log["http_links"];
 check(links.size()==2&&links[0]["logical_sequence"]==2&&links[1]["logical_sequence"].is_null(),"HTTP belongs only to innermost scope");
 check(links[1]["association"]=="outside_instrumented_scope","unattributed direct HTTP is explicit");
 check(http["records"][0]["usage"]["provider_state"]=="pending","logical API return not provider terminality");
 check(http["records"][0]["usage"]["tokens"]["input_uncached"].is_null(),"pending stays unpriced");
 check(http["records"][1]["transport"]=="cancelled","actual HTTP cancellation not hidden");
 auto verified=l::verify(log,http);check(verified["linked_retained_http"]==1&&verified["unattributed_retained_http"]==1,"no duplicate parent billing");
 for(int i=0;i<10;++i){
   auto bad=log;
   if(i==0)bad["records"][0]["tokens"]=0;
   if(i==1)bad["process_exit"]=0;
   if(i==2)bad["records"][1]["parent_sequence"]=2;
   if(i==3)bad["http_links"][0]["logical_sequence"]=99;
   if(i==4)bad["http_links"].erase(bad["http_links"].begin());
   if(i==5)bad["all_model_calls_observed"]=true;
   if(i==6)bad["records"][1]["api_result_ok"]="true";
   if(i==7)bad["records"][0]["price"]=0;
   if(i==8)bad["dispatch_return"]=3;
   if(i==9)bad["records"][0]["prompt"]="PRIVATE";
   bool rejected=false;try{l::verify(bad,http);}catch(const accounting::Error&){rejected=true;}
   check(rejected,"strict paired validation rejects altered claim");
 }
}
void lifecycle(){
 clean();auto c=std::make_shared<l::Collector>();l::Session session(c);
 bool threw=false;
 try{l::invoke(l::Kind::chat,[](auto& scope)->ai::ChatResult{
   scope.path(l::Path::invalid_input);throw std::runtime_error("PRIVATE_THROW");
 });}catch(const std::runtime_error& e){threw=std::string(e.what())=="PRIVATE_THROW";}
 check(threw,"original exception propagated unchanged");
 // 1600 separate threads' entry executions with one global cap, no foreign parents.
 env("QBRAIN_EMBED_MOCK","1");std::vector<std::future<void>> tasks;
 for(int t=0;t<16;++t)tasks.push_back(std::async(std::launch::async,[]{
   Config cfg;cfg.embedding_model="synthetic";
   for(int j=0;j<100;++j)if(!ai::embed_texts(cfg,{"input"}).ok)throw std::runtime_error("mock failed");
 }));
 for(auto& f:tasks)f.get();env("QBRAIN_EMBED_MOCK","");
 session.detach();auto http=session.http_collector()->report(true,0);auto log=c->report(true,0);
 check(log["counts"]["started"]==1601&&log["counts"]["finished"]==1601,"concurrent actual API counts exact");
 check(log["records"].size()==512&&log["counts"]["dropped"]==1089&&!log["recording_complete"].get<bool>(),"capacity cannot claim completeness");
 check(log["records"][0]["return_state"]=="exception"&&log["records"][0]["api_result_ok"].is_null(),"exception no fabricated result");
 for(std::size_t i=1;i<log["records"].size();++i)
   if(log["records"][i]["parent_relation"]!="root")throw std::runtime_error("foreign thread parent");
 check(true,"worker root scopes are independent");
 check(l::verify(log,http)["recording_complete"]==false,"paired cap record is incomplete");
 auto before=log.dump();c->report(true,7,true);
 check(c->report().dump()==before,"first seal immutable including dispatch");
 // Callback logging errors cannot turn success into API failure.
 auto broken=std::make_shared<l::Collector>([](const auto&){throw std::runtime_error("PRIVATE_IO_ERROR");});
 {l::Session s(broken);auto r=l::invoke(l::Kind::chat,[](auto&){ai::ChatResult r;r.ok=true;return r;});check(r.ok,"logging failure keeps API success");}
 auto damaged=broken->report(true,0);
 check(damaged["counts"]["record_errors"]==2&&damaged["recording_complete"]==false,"writer loss not silently green");
 check(damaged.dump().find("PRIVATE_IO_ERROR")==std::string::npos,"logging error text suppressed");
}
void lifetime_sessions(){
 auto c=std::make_shared<l::Collector>();l::Session session(c);
 std::promise<void> entered,release;auto signal=release.get_future().share();
 auto task=std::async(std::launch::async,[&]{return l::invoke(l::Kind::chat,[&](auto&){
   entered.set_value();signal.wait();ai::ChatResult r;r.ok=true;return r;
 });});
 check(entered.get_future().wait_for(std::chrono::seconds(5))==std::future_status::ready,"worker call entered");
 session.detach();auto http=session.http_collector()->report(true,0);auto log=c->report(true,0);
 check(log["counts"]["pending"]==1&&log["records"][0]["return_state"]=="pending","seal retains unfinished call");
 release.set_value();check(task.get().ok,"late API result unchanged");
 check(c->report().dump()==log.dump(),"late completion cannot mutate sealed record");
 check(!l::verify(log,http)["recording_complete"].get<bool>(),"pending is not cancelled or complete");
 // Concurrent late old scope must not be attributed into a new observation session.
 auto first=std::make_shared<l::Collector>();l::Session a(first);
 std::promise<void> waiting,go;auto wake=go.get_future().share();
 auto old=std::async(std::launch::async,[&]{l::Call old_call(l::Kind::chat);waiting.set_value();wake.wait();
   h::Attempt attempt("/embeddings");ai::HttpResponse r;r.failure=ai::HttpFailure::invalid_request;attempt.finish(r,false);
   auto unused=l::invoke(l::Kind::text_embedding,[](auto& s){s.path(l::Path::empty_input);ai::EmbedResult r;r.ok=true;return r;});
   old_call.returned(false);
 });
 waiting.get_future().wait();a.detach();a.http_collector()->report(true,0);first->report(true,0);
 Capture b;go.set_value();old.get();
 auto [new_log,new_http]=b.finish();
 check(new_log["http_links"][0]["association"]=="different_session"&&new_log["http_links"][0]["logical_sequence"].is_null(),"old thread scope cannot steal new session identity");
 check(new_log["records"][0]["parent_relation"]=="different_session"&&new_log["records"][0]["parent_sequence"].is_null(),"cross-session parent is unknown");
 // Ownership and original observe session rejection stay explicit.
 auto standalone=std::make_shared<h::Collector>();
 {h::Session s(standalone);bool refused=false;try{Capture conflict;}catch(const std::runtime_error&){refused=true;}check(refused,"nested original session not replaced");}
 Capture after;auto pair=after.finish();check(pair.first["counts"]["started"]==0,"failed activation leaves no active logical collector");
 bool reused=false;try{l::Session reuse(c);}catch(const std::runtime_error&){reused=true;}
 check(reused,"one collector cannot span different HTTP capture identities");
 Capture distinct;session.detach();
 auto result=l::invoke(l::Kind::chat,[](auto&){ai::ChatResult r;r.ok=true;return r;});
 auto final=distinct.finish();check(result.ok&&final.first["counts"]["started"]==1,"repeated detach leaves new session active");
}
void capacity_links(){
 auto c=std::make_shared<l::Collector>(l::Collector::Writer{},l::Collector::LinkWriter{},1);
 l::Session session(c);
 {
   l::Call parent(l::Kind::rerank);
   {
     l::Call dropped(l::Kind::chat);
     h::Attempt attempt("/responses");ai::HttpResponse r;r.failure=ai::HttpFailure::timeout;
     attempt.finish(r,true);dropped.returned(false);
   }
   parent.fallback(true);parent.returned();
 }
 session.detach();auto http=session.http_collector()->report(true,0);auto log=c->report(true,0);
 check(log["http_links"][0]["logical_sequence"].is_null()&&
       log["http_links"][0]["association"]=="logical_call_not_retained","dropped child HTTP cannot be charged to parent");
 check(l::verify(log,http)["recording_complete"]==false,"dropped child coverage stays incomplete");
 auto once=std::make_shared<l::Collector>();
 {
   l::Session s(once);l::Call call(l::Kind::chat);call.returned(false);call.returned(true);call.threw();
 }
 auto one=once->report(true,0);
 check(one["counts"]["finished"]==1&&one["records"][0]["api_result_ok"]==false,"one logical finish and immutable API result");
 auto bad_link=std::make_shared<l::Collector>(l::Collector::Writer{},[](const l::Link&){throw std::runtime_error("PRIVATE_LINK_ERROR");});
 l::Session s(bad_link);
 {h::Attempt a("/responses");ai::HttpResponse r;r.failure=ai::HttpFailure::cancelled;a.finish(r,true);}
 s.detach();http=s.http_collector()->report(true,0);log=bad_link->report(true,0);
 check(http["recording_complete"]==true&&log["counts"]["record_errors"]==1&&
       !l::verify(log,http)["recording_complete"].get<bool>(),"logical link IO error not hidden by complete HTTP report");
 check(log.dump().find("PRIVATE_LINK_ERROR")==std::string::npos,"link writer failure suppresses text");
}

}
int main(){try{original_entries();reranking();synthetic_http();lifecycle();lifetime_sessions();capacity_links();
 std::cout<<J({{"schema","qbrain-n48x-native-v1"},{"passed",true},{"checks",checks},{"check_count",checks.size()},{"real_network_requests",0}}).dump()<<'\n';return 0;
}catch(const std::exception& e){std::cout<<J({{"passed",false},{"checks",checks},{"failure",e.what()}}).dump()<<'\n';return 1;}}
