#pragma once
// N48G: bounded offline response import. No provider request, content echo or DB.
#include "qbrain/accounting/token_cost.hpp"

namespace qbrain::accounting::usage_import {
inline constexpr std::size_t import_cap=1048576,response_cap=262144;
using Count=std::optional<Amount>;
inline void fields(const Json& j,std::initializer_list<const char*> allowed){
  need(j.is_object(),"usage_object");
  for(const auto& el:j.items()){
    bool known=false;for(const auto* k:allowed)known|=el.key()==k;
    need(known,"usage_fields");
  }
}
inline Count count(const Json& j,const char* k){
  if(!j.contains(k)||j[k].is_null())return {};
  const auto& n=j[k];need(n.is_number_integer()&&n>=0&&n<=token_cap,"usage_quantity");
  return n.get<Amount>();
}
inline Json detail(const Json& j,const char* key){
  if(!j.contains(key)||j[key].is_null())return Json::object();
  need(j[key].is_object(),"usage_detail_object");return j[key];
}
inline void subset(Count part,Count whole){if(part&&whole)need(*part<=*whole,"usage_inconsistent");}
inline void equality(Count actual,Count expected){if(actual&&expected)need(*actual==*expected,"usage_inconsistent");}
inline Count sum(Count a,Count b){return a&&b?Count(add(*a,*b)):Count{};}
inline void zero_audio(const Json& d){
  if(d.contains("audio_tokens")){
    auto n=count(d,"audio_tokens");need(n&&*n==0,"usage_audio_unsupported");
  }
}
inline void output_details(const Json& d,Count output,bool anthropic){
  if(anthropic)fields(d,{"thinking_tokens"});
  else fields(d,{"reasoning_tokens","accepted_prediction_tokens","rejected_prediction_tokens","audio_tokens"});
  for(const auto& el:d.items())subset(count(d,el.key().c_str()),output);
  zero_audio(d); // Details are already inside inclusive output; never add again.
}
struct Mapped {Values tokens{};Json notes=Json::array();};
inline Mapped openai_usage(const Json& u,bool responses){
  Mapped m;
  const auto* in=responses?"input_tokens":"prompt_tokens";
  const auto* out=responses?"output_tokens":"completion_tokens";
  const auto* ind=responses?"input_tokens_details":"prompt_tokens_details";
  const auto* outd=responses?"output_tokens_details":"completion_tokens_details";
  fields(u,{in,out,"total_tokens",ind,outd});
  const auto input=count(u,in),output=count(u,out),total=count(u,"total_tokens");
  const auto d=detail(u,ind);fields(d,{"cached_tokens","cache_write_tokens","audio_tokens"});zero_audio(d);
  auto read=count(d,"cached_tokens"),write=count(d,"cache_write_tokens");
  subset(read,input);subset(write,input);subset(sum(read,write),input);
  // Independent known lower bounds can contradict a supplied total too.
  if(input)need(read.value_or(0)+write.value_or(0)<=*input,"usage_inconsistent");
  const auto od=detail(u,outd);output_details(od,output,false);
  Amount minimum_output=output.value_or(0);
  for(const auto& el:od.items()){auto n=count(od,el.key().c_str());if(n)minimum_output=(std::max)(minimum_output,*n);}
  const Amount minimum_input=input.value_or(read.value_or(0)+write.value_or(0));
  if(total)need(add(minimum_input,minimum_output)<=*total,"usage_inconsistent");
  equality(total,sum(input,output));
  // Only a reported zero total input mathematically proves both cache buckets zero.
  if(input&&*input==0){read=0;write=0;}
  m.tokens[1]=read;m.tokens[2]=write;m.tokens[3]=output;
  if(input&&read&&write)m.tokens[0]=*input-*read-*write;
  else m.notes.push_back("input_partition_unknown");
  return m;
}
inline Mapped anthropic_usage(const Json& u){
  Mapped m;
  fields(u,{"input_tokens","output_tokens","cache_read_input_tokens","cache_creation_input_tokens",
    "cache_creation","output_tokens_details","server_tool_use","iterations","inference_geo","service_tier","speed"});
  m.tokens={count(u,"input_tokens"),count(u,"cache_read_input_tokens"),count(u,"cache_creation_input_tokens"),count(u,"output_tokens")};
  output_details(detail(u,"output_tokens_details"),m.tokens[3],true);
  if(u.contains("iterations")&&!u["iterations"].is_null())
    need(u["iterations"].is_array()&&u["iterations"].empty(),"usage_iterations_unsupported");
  if(u.contains("cache_creation")&&!u["cache_creation"].is_null()){
    const auto d=detail(u,"cache_creation");fields(d,{"ephemeral_5m_input_tokens","ephemeral_1h_input_tokens"});
    auto a=count(d,"ephemeral_5m_input_tokens"),b=count(d,"ephemeral_1h_input_tokens");
    need(a&&b,"usage_cache_ttl_incomplete");equality(m.tokens[2],sum(a,b));
    need(!(*a>0&&*b>0),"usage_mixed_cache_ttl");
    auto combined=sum(a,b);need(*combined<=token_cap,"usage_quantity");m.tokens[2]=combined;
    if(*a)m.notes.push_back("cache_write_ttl_5m");if(*b)m.notes.push_back("cache_write_ttl_1h");
  }else if(m.tokens[2]&&*m.tokens[2]>0)m.notes.push_back("cache_write_ttl_unspecified");
  const auto tools=detail(u,"server_tool_use");fields(tools,{"web_search_requests","web_fetch_requests"});
  bool excluded_tools=false;
  for(const auto& el:tools.items()){
    auto n=count(tools,el.key().c_str());
    excluded_tools|=!n||*n>0;
  }
  if(excluded_tools)m.notes.push_back("server_tool_fees_excluded");
  for(auto key:{"inference_geo","service_tier","speed"})if(u.contains(key)&&!u[key].is_null())
    need(u[key].is_string()&&u[key].get_ref<const std::string&>().size()<=128,"usage_metadata");
  return m;
}
inline std::string opaque_id(const Json& j){
  need(j.is_string(),"usage_response_identity");auto s=j.get<std::string>();
  need(!s.empty()&&s.size()<=256,"usage_response_identity");
  for(unsigned char c:s)need(c>=33&&c<=126,"usage_response_identity");return s;
}
inline bool is_error_envelope(const Json& r){
  return r.contains("error")&&!r["error"].is_null()&&!r.contains("object")&&r.value("type",Json())!="message";
}
inline Json import_report(const Json& root){
  exact(root,{"schema","currency","rates","records"});need(root["schema"]=="qbrain-usage-import-v1","usage_schema");
  need(root["records"].is_array()&&root["records"].size()<=128,"usage_record_count");
  Json normalized_input={{"schema","qbrain-cost-input-v1"},{"currency",root["currency"]},{"rates",root["rates"]},{"calls",Json::array()}};
  (void)accounting::report(normalized_input); // Reuse, never weaken, N48F rates/currency validation.
  std::map<std::string,Json> rate_cards,calls,metadata;
  std::set<std::string> responses_seen;
  for(auto& rate:normalized_input["rates"]){
    rate["per_million"]=normalized(amounts(rate["per_million"],true),true);
    rate_cards.emplace(rate["rate_id"].get<std::string>(),rate);
  }
  normalized_input["rates"]=Json::array();for(const auto& [key,value]:rate_cards)normalized_input["rates"].push_back(value);
  for(const auto& record:root["records"]){
    exact(record,{"call_id","stage","rate_id","attempt","outcome","format","response"});
    const auto cid=id(record["call_id"]),rid=id(record["rate_id"]),format=id(record["format"]),outcome=id(record["outcome"]);
    need(format=="openai_chat"||format=="openai_responses"||format=="anthropic_messages","usage_format");
    const bool anth=format=="anthropic_messages";const std::string provider=anth?"anthropic":"openai";
    Mapped m;Json reference=nullptr;const auto& r=record["response"];
    const auto card=rate_cards.find(rid);
    if(card!=rate_cards.end())need(card->second["provider"]==provider,"usage_rate_provider_mismatch");
    if(r.is_null()){
      need(outcome!="success","usage_response_missing");m.notes.push_back("response_missing");
    }else{
      need(r.is_object(),"usage_response_object");need(r.dump().size()<=response_cap,"usage_response_limit");
      if(is_error_envelope(r)){
        need(r["error"].is_object()&&outcome!="success","usage_error_envelope");
        need(!r.contains("usage")||r["usage"].is_null(),"usage_error_envelope");
        m.notes.push_back("error_response_without_usage");
      }else{
        need(r.contains("model")&&r["model"].is_string()&&r["model"].get_ref<const std::string&>().size()<=256,"usage_response_model");
        need(!r["model"].get_ref<const std::string&>().empty(),"usage_response_model");
        if(card!=rate_cards.end())need(card->second["model"]==r["model"],"usage_rate_model_mismatch");
        need(r.contains("id"),"usage_response_identity");const auto response_id=opaque_id(r["id"]);
        const auto identity=provider+"/"+response_id;
        need(responses_seen.insert(identity).second,"usage_duplicate_response");reference=util::sha256_hex(identity);
        if(anth){
          need(r.value("type",Json())=="message"&&r.value("role",Json())=="assistant","usage_response_kind");
          need(r.contains("stop_reason")&&r["stop_reason"].is_string()&&!r["stop_reason"].get_ref<const std::string&>().empty(),"usage_response_nonterminal");
        }else if(format=="openai_responses"){
          need(r.value("object",Json())=="response","usage_response_kind");
          const auto status=r.value("status",Json());need(status=="completed"||status=="failed"||status=="incomplete"||status=="cancelled","usage_response_nonterminal");
          need(outcome!="success"||status=="completed","usage_outcome_conflict");
        }else{
          need(r.value("object",Json())=="chat.completion","usage_response_kind");
          need(r.contains("choices")&&r["choices"].is_array()&&!r["choices"].empty(),"usage_response_nonterminal");
          for(const auto& c:r["choices"])need(c.is_object()&&c.contains("finish_reason")&&c["finish_reason"].is_string()&&!c["finish_reason"].get_ref<const std::string&>().empty(),"usage_response_nonterminal");
        }
        if(!r.contains("usage")||r["usage"].is_null())m.notes.push_back("usage_missing");
        else m=anth?anthropic_usage(r["usage"]):openai_usage(r["usage"],format=="openai_responses");
      }
    }
    bool complete=true;for(const auto& n:m.tokens)complete&=n.has_value();
    if(!complete)m.notes.push_back("unknown_usage_preserved");
    Json call={{"call_id",cid},{"stage",record["stage"]},{"rate_id",rid},{"attempt",record["attempt"]},{"outcome",outcome},{"tokens",normalized(m.tokens,false)}};
    need(calls.emplace(cid,call).second,"cost_duplicate_call");
    metadata.emplace(cid,Json{{"call_id",cid},{"format",format},{"provider",provider},{"response_reference_sha256",reference},
      {"usage_complete",complete},{"notes",m.notes}});
  }
  Json audit=Json::array();bool complete=true;
  for(const auto& [key,value]:calls){normalized_input["calls"].push_back(value);audit.push_back(metadata.at(key));complete&=metadata.at(key)["usage_complete"].get<bool>();}
  need(normalized_input.dump().size()<=accounting::input_cap,"usage_normalized_limit");
  auto costs=accounting::report(normalized_input);
  const auto fingerprint=util::sha256_hex(Json{{"cost_input",normalized_input},{"mapping",audit}}.dump());
  Json result={{"schema","qbrain-usage-import-report-v1"},{"normalization_sha256",fingerprint},
    {"cost_input",normalized_input},{"cost_report",costs},{"mapping",audit},{"usage_complete",complete},
    {"provider_requests_sent",0},{"source_authenticated",false},{"response_content_included",false},
    {"rate_applicability_verified",false},{"outcome_labels_verified",false},{"all_provider_calls_observed",false}};
  need(result.dump().size()+1<=accounting::output_cap,"usage_output_limit");return result;
}
inline Json parse(const std::string& raw){
  try{return import_report(util::parse_unique_json(raw,import_cap,48));}
  catch(const util::JsonInputError& e){
    if(e.failure()==util::JsonInputFailure::byte_limit)throw Error("usage_input_limit");
    if(e.failure()==util::JsonInputFailure::duplicate_key)throw Error("usage_duplicate_key");
    throw Error("usage_invalid_json");}
  catch(const nlohmann::json::exception&){throw Error("usage_invalid_json");}
}
inline int command(const std::vector<std::string>& args){
  try{
    need(args.size()==1&&args[0]=="import","usage_invalid_action");std::string raw;std::array<char,8192> buffer{};
    while(std::cin.read(buffer.data(),static_cast<std::streamsize>((std::min)(buffer.size(),import_cap+1-raw.size())))||std::cin.gcount()){
      raw.append(buffer.data(),static_cast<std::size_t>(std::cin.gcount()));need(raw.size()<=import_cap,"usage_input_limit");}
    need(!std::cin.bad(),"usage_input_error");const auto result=parse(raw).dump();std::cout<<result<<'\n';return 0;
  }catch(const Error& e){std::cout<<Json{{"error",{{"code",e.what()}}}}.dump()<<'\n';return 2;}
  catch(...){std::cout<<"{\"error\":{\"code\":\"usage_local_error\"}}\n";return 2;}
}
} // namespace qbrain::accounting::usage_import
