#include "qbrain/accounting/stream_usage.hpp"
#include <functional>
using namespace qbrain::accounting;
namespace s=qbrain::accounting::stream_import;
int n=0;
void check(bool value,const char* label){if(!value)throw std::runtime_error(label);++n;}
void rejects(const std::function<void()>& fn,const char* code){try{fn();}catch(const Error& e){check(std::string(e.what())==code,code);return;}throw std::runtime_error("accepted invalid fixture");}
int main(){try{
  for(const std::string line:{"\n","\r","\r\n"}){
    auto a=s::events("\xEF\xBB\xBF: comment"+line+line+"event: ping"+line+"data: {"+line+"data: \"type\":\"ping\"}"+line+line);
    check(a.size()==1&&a[0].name=="ping"&&s::json(a[0])["type"]=="ping","SSE line/BOM/multiline");
  }
  for(auto raw:{"data: {}","data: {}\n", "event: ping\n\n", "retry: 1\n\n", "event: x\nevent: x\ndata: {}\n\n"}){
    bool failed=false;try{(void)s::events(raw);}catch(const Error&){failed=true;}check(failed,"invalid SSE refused");
  }
  rejects([]{s::events("");},"stream_body_limit");
  rejects([]{s::events(std::string("data: {}\n\n")+char(0));},"stream_nul");
  rejects([]{s::events(std::string(":")+char(0xff)+"\n");},"stream_invalid_utf8");
  auto a=s::events("data: "+std::string(s::event_cap,' ')+"\n\n");check(a[0].data.size()==s::event_cap,"exact event data bound");
  rejects([]{s::events("data: "+std::string(s::event_cap+1,' ')+"\n\n");},"stream_event_limit");
  std::string many;for(std::size_t i=0;i<s::event_limit;++i)many+="data: {}\n\n";
  check(s::events(many).size()==s::event_limit,"exact event count");rejects([&]{s::events(many+"data: {}\n\n");},"stream_event_count");
  for(auto value:{"{\"nested\":{\"a\":1,\"a\":2}}","{\"id\":1,\"\\u0069d\":2}"})rejects([&]{s::json({"",value});},"stream_duplicate_key");
  rejects([]{s::json({"","[1,2]"});},"stream_event_object");
  rejects([]{s::json({"","{\"a\":NaN}"});},"stream_event_json");
  std::map<std::string,Amount> observed;s::monotonic({{"input_tokens",20}},observed);s::monotonic({{"input_tokens",nullptr}},observed);
  rejects([&]{s::monotonic({{"input_tokens",19}},observed);},"stream_usage_decreased");
  s::monotonic({{"input_tokens",20}},observed);check(observed.at("/input_tokens")==20,"equal cumulative value remains20");
  Json usage={{"input_tokens",20},{"output_tokens",1},{"cache_creation",{{"ephemeral_5m_input_tokens",0},{"ephemeral_1h_input_tokens",0}}}};
  s::merge_usage(usage,{{"output_tokens",8}});check(usage["input_tokens"]==20&&usage["output_tokens"]==8,"cumulative replacement not summation");
  s::merge_usage(usage,{{"cache_creation",{{"ephemeral_5m_input_tokens",7}}}});check(usage["cache_creation"]["ephemeral_1h_input_tokens"]==0,"partial details merge retains observed fields");
  s::merge_usage(usage,{{"output_tokens",nullptr}});check(usage["output_tokens"].is_null(),"explicit null is not zero");
  Json empty={{"schema","qbrain-stream-import-v1"},{"currency","USD"},{"rates",Json::array()},{"records",Json::array()}};
  auto out=s::parse(empty.dump());check(out["stream_observations"].empty()&&out["cost_input"]["calls"].empty(),"empty batch remains empty");
  auto full=empty.dump();full.append(s::envelope_cap-full.size(),' ');check(s::parse(full)==out,"exact envelope bound");
  rejects([&]{s::parse(full+" ");},"stream_input_limit");
  Json created={{"type","response.created"},{"sequence_number",0},{"response",{{"id","response-direct"},{"model","example"},{"object","response"},{"status","in_progress"}}}};
  Json finished={{"type","response.completed"},{"sequence_number",1},{"response",{{"id","response-direct"},{"model","example"},{"object","response"},{"status","completed"}}}};
  for(int origin:{0,1}){created["sequence_number"]=origin;finished["sequence_number"]=origin+1;
    auto r=s::responses({{"response.created",created.dump()},{"response.completed",finished.dump()}});
    check(r.observation["sequence_origin"]==origin&&r.response["usage"].is_null(),"both documented sequence origins keep missing final usage unknown");}
  created["sequence_number"]=2;rejects([&]{s::responses({{"",created.dump()},{"",finished.dump()}});},"stream_sequence_origin");
  created["sequence_number"]=0;finished["sequence_number"]=2;
  rejects([&]{s::responses({{"",created.dump()},{"",finished.dump()}});},"stream_sequence");
  finished["sequence_number"]=1;finished["response"]["id"]="other";
  rejects([&]{s::responses({{"",created.dump()},{"",finished.dump()}});},"stream_identity_changed");
  finished["response"]["id"]="response-direct";finished["response"]["usage"]={{"input_tokens",nullptr},{"total_tokens",20},{"output_tokens",5}};
  created["response"]["usage"]={{"input_tokens",100}};
  rejects([&]{s::responses({{"",created.dump()},{"",finished.dump()}});},"stream_usage_lower_bound");
  rejects([]{s::chat({{"","[DONE]"}});},"stream_chat_choices");
  Json start={{"type","message_start"},{"message",{{"id","msg-direct"},{"model","example"},{"type","message"},{"role","assistant"},{"content",Json::array()},
    {"usage",{{"input_tokens",9},{"output_tokens",1}}}}}};
  Json delta={{"type","message_delta"},{"delta",{{"stop_reason","end_turn"}}},{"usage",Json::object()}};
  Json stop={{"type","message_stop"}};
  auto aonly=s::anthropic({{"",start.dump()},{"",delta.dump()},{"",stop.dump()}});
  check(aonly.response["usage"]["input_tokens"]==9&&aonly.response["usage"]["output_tokens"].is_null(),"initial output alone is never final output");
  delta["usage"]=nullptr;auto unknown=s::anthropic({{"",start.dump()},{"",delta.dump()},{"",stop.dump()}});
  check(unknown.response["usage"]["input_tokens"].is_null()&&unknown.response["usage"]["output_tokens"].is_null(),"null usage invalidates initial totals");
  rejects([&]{s::anthropic({{"",start.dump()},{"",stop.dump()}});},"stream_anthropic_nonterminal");
  // Reverse aggregate bounds: an omitted/null aggregate does not erase history.
  for(int total_mode:{0,1}){
    created["response"]["usage"]={{"total_tokens",100}};
    finished["response"]["usage"]={{"input_tokens",5},{"output_tokens",5}};
    if(total_mode)finished["response"]["usage"]["total_tokens"]=nullptr;
    rejects([&]{s::responses({{"",created.dump()},{"",finished.dump()}});},"stream_usage_lower_bound");
    finished["response"]["usage"]["output_tokens"]=95;
    check(s::responses({{"",created.dump()},{"",finished.dump()}}).response["usage"]["output_tokens"]==95,"equal derived total allowed");
    finished["response"]["usage"]["output_tokens"]=nullptr;
    check(s::responses({{"",created.dump()},{"",finished.dump()}}).response["usage"]["output_tokens"].is_null(),"unknown component not fabricated from earlier total");
  }
  for(int ttl:{0,1}){
    start["message"]["usage"]={{"input_tokens",9},{"output_tokens",1},{"cache_creation_input_tokens",100}};
    delta["usage"]={{"output_tokens",5},{"cache_creation_input_tokens",nullptr},
      {"cache_creation",{{"ephemeral_5m_input_tokens",ttl?0:5},{"ephemeral_1h_input_tokens",ttl?5:0}}}};
    rejects([&]{s::anthropic({{"",start.dump()},{"",delta.dump()},{"",stop.dump()}});},"stream_usage_lower_bound");
    delta["usage"]["cache_creation"][ttl?"ephemeral_1h_input_tokens":"ephemeral_5m_input_tokens"]=100;
    auto same=s::anthropic({{"",start.dump()},{"",delta.dump()},{"",stop.dump()}});
    check(usage_import::anthropic_usage(same.response["usage"]).tokens[2]==100,"equal TTL-derived cache total allowed");
  }
  std::cout<<Json{{"schema","qbrain-n48h-direct-v1"},{"passed",n},{"failed",0}}.dump()<<'\n';return 0;
}catch(const std::exception& e){std::cerr<<"FAIL after "<<n<<": "<<e.what()<<'\n';return 1;}}
