#pragma once
// N48H: offline bounded SSE replay into unchanged N48G/N48F accounting.
#include "qbrain/accounting/provider_usage.hpp"
namespace qbrain::accounting::stream_import {
inline constexpr std::size_t envelope_cap=4194304,stream_cap=524288,event_cap=262144,event_limit=4096;
struct Event {std::string name,data;};
inline std::vector<Event> events(const std::string& raw){
  need(!raw.empty()&&raw.size()<=stream_cap,"stream_body_limit");need(raw.find('\0')==std::string::npos,"stream_nul");
  try{(void)Json(raw).dump();}catch(...){throw Error("stream_invalid_utf8");}
  std::size_t at=raw.compare(0,3,"\xEF\xBB\xBF")==0?3:0;std::vector<Event> result;Event current;bool named=false,data=false;
  while(at<raw.size()){
    const auto end=raw.find_first_of("\r\n",at);need(end!=std::string::npos,"stream_unterminated_line");
    const auto line=raw.substr(at,end-at);at=end+1;if(raw[end]=='\r'&&at<raw.size()&&raw[at]=='\n')++at;
    if(line.empty()){
      if(data){need(result.size()<event_limit,"stream_event_count");result.push_back(std::move(current));}
      else need(!named,"stream_event_without_data");current=Event{};named=false;data=false;continue;
    }
    if(line[0]==':')continue;const auto colon=line.find(':');const auto key=line.substr(0,colon);
    auto value=colon==std::string::npos?std::string{}:line.substr(colon+1);if(!value.empty()&&value[0]==' ')value.erase(0,1);
    if(key=="event"){
      need(!named&&!value.empty()&&value.size()<=128,"stream_event_name");for(unsigned char c:value)need(c>=33&&c<=126,"stream_event_name");
      current.name=value;named=true;
    }else if(key=="data"){
      if(data)current.data+='\n';current.data+=value;data=true;need(current.data.size()<=event_cap,"stream_event_limit");
    }else throw Error("stream_sse_field");
  }
  need(!named&&!data,"stream_unterminated_event");need(!result.empty(),"stream_empty");return result;
}
inline Json json(const Event& e){
  try{auto j=util::parse_unique_json(e.data,event_cap,48);need(j.is_object(),"stream_event_object");return j;}
  catch(const util::JsonInputError& x){if(x.failure()==util::JsonInputFailure::duplicate_key)throw Error("stream_duplicate_key");throw Error("stream_event_json");}
  catch(const nlohmann::json::exception&){throw Error("stream_event_json");}
}
inline std::string text(const Json& j,const char* key,std::size_t max=256){
  need(j.contains(key)&&j[key].is_string(),"stream_field_type");auto s=j[key].get<std::string>();need(!s.empty()&&s.size()<=max,"stream_field_bound");return s;
}
inline void object(const Json& j,const char* key){need(j.contains(key)&&j[key].is_object(),"stream_field_type");}
inline void event_name(const Event& e,const std::string& type){need(e.name.empty()||e.name==type,"stream_event_mismatch");}
inline void string_field(const Json& j,const char* key,bool nullable=false){need(j.contains(key)&&(j[key].is_string()||(nullable&&j[key].is_null())),"stream_field_type");}
struct Identity {std::string response,model;
  void observe(const Json& j){need(j.contains("id"),"stream_identity");auto rid=usage_import::opaque_id(j["id"]);auto mod=text(j,"model");
    need(response.empty()||(rid==response&&mod==model),"stream_identity_changed");response=rid;model=mod;}
};
struct Replayed {Json response,observation;};
inline Replayed chat(const std::vector<Event>& stream){
  Identity id;std::map<Amount,std::string> choices;Json usage=nullptr;bool tail=false,ended=false;std::size_t count=0;
  for(const auto& e:stream){
    ++count;need(!ended,"stream_after_terminal");need(e.name.empty()||e.name=="message","stream_event_mismatch");
    if(e.data=="[DONE]"){
      need(!choices.empty(),"stream_chat_choices");for(const auto& [i,finish]:choices)need(!finish.empty(),"stream_chat_unfinished_choice");ended=true;continue;
    }
    need(!tail,"stream_chat_after_usage");const auto j=json(e);
    usage_import::fields(j,{"id","object","created","model","choices","usage","system_fingerprint","service_tier"});
    need(j.value("object",Json())=="chat.completion.chunk","stream_response_kind");id.observe(j);
    need(j.contains("choices")&&j["choices"].is_array()&&j["choices"].size()<=32,"stream_chat_choices");
    if(j["choices"].empty()){
      need(!choices.empty()&&j.contains("usage")&&j["usage"].is_object(),"stream_chat_usage_tail");
      for(const auto& [i,finish]:choices)need(!finish.empty(),"stream_chat_unfinished_choice");
      (void)usage_import::openai_usage(j["usage"],false);usage=j["usage"];tail=true;continue;
    }
    need(!j.contains("usage")||j["usage"].is_null(),"stream_chat_usage_position");std::set<Amount> seen;
    for(const auto& c:j["choices"]){
      usage_import::fields(c,{"index","delta","finish_reason","logprobs"});need(c.contains("index"),"stream_chat_index");auto i=integer(c["index"],31);
      need(seen.insert(i).second,"stream_chat_duplicate_choice");auto& finish=choices[i];need(finish.empty(),"stream_chat_choice_closed");object(c,"delta");
      const auto& d=c["delta"];usage_import::fields(d,{"role","content","refusal","tool_calls","function_call"});
      for(auto k:{"content","refusal"})if(d.contains(k))string_field(d,k,true);
      if(d.contains("role"))need(d["role"]=="assistant","stream_chat_role");
      if(d.contains("tool_calls"))need(d["tool_calls"].is_array(),"stream_field_type");
      if(d.contains("function_call"))need(d["function_call"].is_object(),"stream_field_type");
      if(c.contains("logprobs"))need(c["logprobs"].is_null()||c["logprobs"].is_object(),"stream_field_type");
      need(c.contains("finish_reason"),"stream_field_type");
      if(!c["finish_reason"].is_null()){
        finish=text(c,"finish_reason",64);need(finish=="stop"||finish=="length"||finish=="tool_calls"||finish=="content_filter"||finish=="function_call","stream_chat_finish_reason");}
    }
  }
  need(ended,"stream_missing_terminal");Json out=Json::array();for(const auto& [i,finish]:choices)out.push_back({{"index",i},{"finish_reason",finish}});
  return {{{"id",id.response},{"model",id.model},{"object","chat.completion"},{"choices",out},{"usage",usage}},
    {{"data_events",count},{"terminal","[DONE]"},{"usage_source",tail?"final_chunk":"absent"},{"sequence_origin",nullptr}}};
}
// Null remains unknown but cannot erase earlier numeric lower bounds.
inline void monotonic(const Json& j,std::map<std::string,Amount>& observed,const std::string& path=""){
  if(!j.is_object())return;
  for(const auto& el:j.items()){
    auto key=path+"/"+el.key();const auto& v=el.value();
    if(v.is_object())monotonic(v,observed,key);
    else if(v.is_number_integer()){const auto n=integer(v,token_cap);auto it=observed.find(key);
      need(it==observed.end()||n>=it->second,"stream_usage_decreased");observed[key]=n;}
  }
}
// Validate a currently reported aggregate against all earlier numeric lower bounds.
// A missing CURRENT aggregate does not assert an old total is still current.
inline Amount lower(const std::map<std::string,Amount>& b,const char* key){auto it=b.find(key);return it==b.end()?0:it->second;}
inline void openai_bounds(const Json& u,const std::map<std::string,Amount>& b){
  const auto cache=add(lower(b,"/input_tokens_details/cached_tokens"),lower(b,"/input_tokens_details/cache_write_tokens"));
  if(auto v=usage_import::count(u,"input_tokens"))need(cache<=*v,"stream_usage_lower_bound");
  Amount minimum_output=lower(b,"/output_tokens");
  for(auto key:{"/output_tokens_details/reasoning_tokens","/output_tokens_details/accepted_prediction_tokens","/output_tokens_details/rejected_prediction_tokens"})
    minimum_output=(std::max)(minimum_output,lower(b,key));
  if(auto v=usage_import::count(u,"output_tokens"))need(minimum_output<=*v,"stream_usage_lower_bound");
  if(auto v=usage_import::count(u,"total_tokens"))need(add((std::max)(cache,lower(b,"/input_tokens")),minimum_output)<=*v,"stream_usage_lower_bound");
}
inline void anthropic_bounds(const Json& u,const std::map<std::string,Amount>& b){
  const auto short_ttl=lower(b,"/cache_creation/ephemeral_5m_input_tokens"),long_ttl=lower(b,"/cache_creation/ephemeral_1h_input_tokens");
  need(!short_ttl||!long_ttl,"usage_mixed_cache_ttl");
  if(auto v=usage_import::count(u,"cache_creation_input_tokens"))need(add(short_ttl,long_ttl)<=*v,"stream_usage_lower_bound");
  if(auto v=usage_import::count(u,"output_tokens"))need(lower(b,"/output_tokens_details/thinking_tokens")<=*v,"stream_usage_lower_bound");
}
inline Replayed responses(const std::vector<Event>& stream){
  Identity id;Json final;std::optional<Amount> next;Amount origin=0;bool ended=false;std::string terminal;std::map<std::string,Amount> bounds;
  const std::set<std::string> allowed={"response.output_item.added","response.output_item.done","response.content_part.added","response.content_part.done",
    "response.output_text.delta","response.output_text.done","response.refusal.delta","response.refusal.done",
    "response.function_call_arguments.delta","response.function_call_arguments.done","response.reasoning_summary_part.added","response.reasoning_summary_part.done",
    "response.reasoning_summary_text.delta","response.reasoning_summary_text.done","response.reasoning_text.delta","response.reasoning_text.done"};
  for(const auto& e:stream){
    need(!ended,"stream_after_terminal");const auto j=json(e);const auto type=text(j,"type",128);event_name(e,type);
    need(j.contains("sequence_number"),"stream_sequence");const auto seq=integer(j["sequence_number"],event_limit+1);
    if(!next){need(type=="response.created"&&seq<=1,"stream_sequence_origin");origin=seq;next=seq;}
    need(seq==*next,"stream_sequence");++*next;
    if(type=="response.created"||type=="response.in_progress"||type=="response.completed"||type=="response.failed"||type=="response.incomplete"){
      if(type=="response.created")need(seq==origin,"stream_repeated_start");
      object(j,"response");const auto& r=j["response"];id.observe(r);need(r.value("object",Json())=="response","stream_response_kind");
      const auto status=text(r,"status",64);
      if(type=="response.created")need(status=="queued"||status=="in_progress","stream_status");
      else if(type=="response.in_progress")need(status=="in_progress","stream_status");
      else {need(type=="response."+status,"stream_status");ended=true;terminal=type;}
      Json u=r.value("usage",Json());if(!u.is_null()){(void)usage_import::openai_usage(u,true);monotonic(u,bounds);openai_bounds(u,bounds);}
      if(ended)final={{"id",id.response},{"model",id.model},{"object","response"},{"status",status},{"usage",u}};
    }else{
      need(allowed.count(type)!=0,"stream_event_unsupported");need(!j.contains("usage"),"stream_usage_position");
      if(j.contains("response_id"))need(j["response_id"]==id.response,"stream_identity_changed");
      need(j.contains("output_index"),"stream_field_type");(void)integer(j["output_index"],4095);
      if(type=="response.output_item.added"||type=="response.output_item.done"){
        object(j,"item");const auto kind=text(j["item"],"type",64);need(kind=="message"||kind=="function_call"||kind=="reasoning","stream_content_unsupported");
        need(j["item"].contains("id"),"stream_field_type");(void)usage_import::opaque_id(j["item"]["id"]);
      }else{
        need(j.contains("item_id"),"stream_field_type");(void)usage_import::opaque_id(j["item_id"]);
        if(type.find(".delta")!=std::string::npos)string_field(j,"delta");
        else if(type=="response.function_call_arguments.done")string_field(j,"arguments");
        else if(type=="response.refusal.done")string_field(j,"refusal");
        else if(type=="response.output_text.done"||type=="response.reasoning_summary_text.done"||type=="response.reasoning_text.done")string_field(j,"text");
        else {object(j,"part");const auto part=text(j["part"],"type",64);need(part=="output_text"||part=="refusal"||part=="summary_text"||part=="reasoning_text","stream_content_unsupported");}
      }
    }
  }
  need(ended,"stream_missing_terminal");return {final,{{"data_events",stream.size()},{"terminal",terminal},{"usage_source","terminal_response"},{"sequence_origin",origin}}};
}
inline void merge_usage(Json& target,const Json& update){
  for(const auto& el:update.items()){
    if(el.value().is_object()){
      if(!target.contains(el.key())||!target[el.key()].is_object())target[el.key()]=Json::object();merge_usage(target[el.key()],el.value());
    }else target[el.key()]=el.value();
  }
}
inline Replayed anthropic(const std::vector<Event>& stream){
  Identity id;Json usage=Json::object();bool started=false,delta=false,ended=false,final_output=false;
  std::string stop;std::map<Amount,std::string> active;std::set<Amount> used;std::map<std::string,Amount> bounds;
  for(const auto& e:stream){
    need(!ended,"stream_after_terminal");const auto j=json(e);const auto type=text(j,"type",128);event_name(e,type);
    if(type=="ping"){usage_import::fields(j,{"type"});continue;}
    if(type=="message_start"){
      usage_import::fields(j,{"type","message"});need(!started,"stream_repeated_start");object(j,"message");const auto& m=j["message"];
      id.observe(m);need(m.value("type",Json())=="message"&&m.value("role",Json())=="assistant","stream_response_kind");
      need(m.contains("content")&&m["content"].is_array()&&m["content"].empty(),"stream_anthropic_initial_content");
      need(!m.contains("stop_reason")||m["stop_reason"].is_null(),"stream_status");
      if(m.contains("usage")&&!m["usage"].is_null()){(void)usage_import::anthropic_usage(m["usage"]);usage=m["usage"];monotonic(usage,bounds);anthropic_bounds(usage,bounds);}
      started=true;continue;
    }
    need(started,"stream_missing_start");
    if(type=="content_block_start"){
      usage_import::fields(j,{"type","index","content_block"});need(!delta&&j.contains("index"),"stream_block_order");const auto index=integer(j["index"],4095);
      need(index==used.size()&&used.insert(index).second,"stream_block_index");object(j,"content_block");
      const auto& b=j["content_block"];const auto kind=text(b,"type",64);need(kind=="text"||kind=="thinking"||kind=="redacted_thinking"||kind=="tool_use","stream_content_unsupported");
      if(kind=="text")string_field(b,"text");
      else if(kind=="thinking"){string_field(b,"thinking");if(b.contains("signature"))string_field(b,"signature");}
      else if(kind=="redacted_thinking")string_field(b,"data");
      else {need(b.contains("id"),"stream_field_type");(void)usage_import::opaque_id(b["id"]);(void)text(b,"name");object(b,"input");}
      active[index]=kind;
    }else if(type=="content_block_delta"||type=="content_block_stop"){
      need(!delta&&j.contains("index"),"stream_block_order");const auto index=integer(j["index"],4095);need(active.count(index)!=0,"stream_block_index");
      if(type=="content_block_stop"){usage_import::fields(j,{"type","index"});active.erase(index);}
      else {usage_import::fields(j,{"type","index","delta"});object(j,"delta");const auto& d=j["delta"];const auto kind=text(d,"type",64);const auto& block=active.at(index);
        need((kind=="text_delta"&&block=="text")||((kind=="thinking_delta"||kind=="signature_delta")&&block=="thinking")||
          (kind=="input_json_delta"&&block=="tool_use"),"stream_delta_type");
        string_field(d,kind=="text_delta"?"text":kind=="thinking_delta"?"thinking":kind=="signature_delta"?"signature":"partial_json");}
    }else if(type=="message_delta"){
      usage_import::fields(j,{"type","delta","usage"});need(active.empty(),"stream_unclosed_block");object(j,"delta");usage_import::fields(j["delta"],{"stop_reason","stop_sequence"});
      const auto& d=j["delta"];need(stop.empty()||!d.contains("stop_reason")||!d["stop_reason"].is_null(),"stream_stop_changed");if(d.contains("stop_reason")&&!d["stop_reason"].is_null()){
        auto reason=text(d,"stop_reason",64);need(stop.empty()||stop==reason,"stream_stop_changed");stop=reason;}
      if(d.contains("stop_sequence"))string_field(d,"stop_sequence",true);
      if(j.contains("usage")&&!j["usage"].is_null()){
        need(j["usage"].is_object(),"usage_object");Json merged=usage;merge_usage(merged,j["usage"]);
        (void)usage_import::anthropic_usage(merged);monotonic(j["usage"],bounds);anthropic_bounds(j["usage"],bounds);usage=std::move(merged);
        if(j["usage"].contains("output_tokens"))final_output=true;
      }else if(j.contains("usage")){
        usage={{"input_tokens",nullptr},{"cache_read_input_tokens",nullptr},{"cache_creation_input_tokens",nullptr},{"output_tokens",nullptr}};
        final_output=true;
      }
      delta=true;
    }else if(type=="message_stop"){usage_import::fields(j,{"type"});need(delta&&active.empty()&&!stop.empty(),"stream_anthropic_nonterminal");ended=true;}
    else throw Error("stream_event_unsupported");
  }
  need(started&&ended,"stream_missing_terminal");if(!final_output)usage["output_tokens"]=nullptr;
  (void)usage_import::anthropic_usage(usage);
  return {{{"id",id.response},{"model",id.model},{"type","message"},{"role","assistant"},{"stop_reason",stop},{"usage",usage}},
    {{"data_events",stream.size()},{"terminal","message_stop"},{"usage_source","cumulative_message_delta"},{"sequence_origin",nullptr}}};
}
inline Json import_stream(const Json& root){
  exact(root,{"schema","currency","rates","records"});need(root["schema"]=="qbrain-stream-import-v1","stream_schema");
  need(root["records"].is_array()&&root["records"].size()<=32,"stream_record_count");
  Json input={{"schema","qbrain-usage-import-v1"},{"currency",root["currency"]},{"rates",root["rates"]},{"records",Json::array()}};std::map<std::string,Json> observations;
  for(const auto& record:root["records"]){
    exact(record,{"call_id","stage","rate_id","attempt","outcome","format","stream"});const auto cid=id(record["call_id"]),format=id(record["format"]);
    need(record["stream"].is_string(),"stream_body_type");const auto ev=events(record["stream"].get<std::string>());Replayed replay;
    if(format=="openai_chat")replay=chat(ev);else if(format=="openai_responses")replay=responses(ev);else if(format=="anthropic_messages")replay=anthropic(ev);else throw Error("stream_format");
    Json imported=record;imported.erase("stream");imported["response"]=std::move(replay.response);input["records"].push_back(std::move(imported));
    replay.observation["call_id"]=cid;replay.observation["format"]=format;need(observations.emplace(cid,std::move(replay.observation)).second,"cost_duplicate_call");
  }
  auto result=usage_import::import_report(input);result["schema"]="qbrain-stream-import-report-v1";
  result["stream_observations"]=Json::array();for(const auto& [key,value]:observations)result["stream_observations"].push_back(value);
  result["stream_contract_validated"]=true;result["response_content_validated"]=false;need(result.dump().size()+1<=accounting::output_cap,"stream_output_limit");return result;
}
inline Json parse(const std::string& raw){
  try{return import_stream(util::parse_unique_json(raw,envelope_cap,48));}
  catch(const util::JsonInputError& e){if(e.failure()==util::JsonInputFailure::byte_limit)throw Error("stream_input_limit");
    if(e.failure()==util::JsonInputFailure::duplicate_key)throw Error("stream_duplicate_key");throw Error("stream_invalid_json");}
  catch(const nlohmann::json::exception&){throw Error("stream_invalid_json");}
}
inline int command(const std::vector<std::string>& args){
  try{need(args.size()==1&&args[0]=="import-stream","stream_invalid_action");std::string raw;std::array<char,8192> buffer{};
    while(std::cin.read(buffer.data(),static_cast<std::streamsize>((std::min)(buffer.size(),envelope_cap+1-raw.size())))||std::cin.gcount()){
      raw.append(buffer.data(),static_cast<std::size_t>(std::cin.gcount()));need(raw.size()<=envelope_cap,"stream_input_limit");}
    need(!std::cin.bad(),"stream_input_error");const auto result=parse(raw).dump();std::cout<<result<<'\n';return 0;
  }catch(const Error& e){std::cout<<Json{{"error",{{"code",e.what()}}}}.dump()<<'\n';return 2;}
  catch(...){std::cout<<"{\"error\":{\"code\":\"stream_local_error\"}}\n";return 2;}
}
} // namespace qbrain::accounting::stream_import
