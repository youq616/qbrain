#pragma once
// N48F: pure bounded pricing of caller-normalized token records. No DB/network.
#include "qbrain/util/strict_json.hpp"
#include "qbrain/util/hash.hpp"
#include <algorithm>
#include <stdexcept>
#include <array>
#include <cstdint>
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <string>
#include <vector>

namespace qbrain::accounting {
using Json=nlohmann::json;
using Amount=std::uint64_t;
inline constexpr std::size_t input_cap=262144,output_cap=2097152;
inline constexpr Amount rate_scale=1000000,cost_scale=1000000000000ULL;
inline constexpr Amount token_cap=1000000000,rate_cap=1000000000000ULL;
inline const std::array<const char*,4> buckets={"input_uncached","input_cache_read","input_cache_write","output"};
struct Error:std::runtime_error {using std::runtime_error::runtime_error;};
inline void need(bool ok,const char* code){if(!ok)throw Error(code);}
inline Amount add(Amount a,Amount b){need(b<=std::numeric_limits<Amount>::max()-a,"cost_overflow");return a+b;}
inline Amount multiply(Amount a,Amount b){need(!a||b<=std::numeric_limits<Amount>::max()/a,"cost_overflow");return a*b;}
inline void exact(const Json& j,std::initializer_list<const char*> fields){
  need(j.is_object()&&j.size()==fields.size(),"cost_fields");
  for(auto field:fields)need(j.contains(field),"cost_fields");
}
inline std::string id(const Json& j){
  need(j.is_string(),"cost_identifier");const auto s=j.get<std::string>();
  need(!s.empty()&&s.size()<=64,"cost_identifier");
  for(unsigned char c:s)need((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'||c=='.'||c==':',"cost_identifier");
  return s;
}
inline Amount integer(const Json& j,Amount maximum){
  need(j.is_number_integer()&&j>=0&&j<=maximum,"cost_quantity");return j.get<Amount>();
}
inline std::string decimal(Amount n,Amount scale,unsigned digits){
  auto tail=std::to_string(n%scale);
  return std::to_string(n/scale)+"."+std::string(digits-tail.size(),'0')+tail;
}
inline std::optional<Amount> rate(const Json& j){
  if(j.is_null())return {};
  need(j.is_string(),"cost_rate_decimal");auto s=j.get<std::string>();
  need(!s.empty()&&s.size()<=14,"cost_rate_decimal");
  const auto dot=s.find('.');const auto whole=dot==std::string::npos?s.size():dot;
  need(whole>=1&&whole<=7&&(whole==1||s[0]!='0'),"cost_rate_decimal");
  const auto decimals=dot==std::string::npos?0:s.size()-dot-1;
  need(dot==std::string::npos||(decimals>=1&&decimals<=6),"cost_rate_decimal");
  Amount value=0;
  for(std::size_t i=0;i<s.size();++i){if(i==dot)continue;
    need(s[i]>='0'&&s[i]<='9',"cost_rate_decimal");value=add(multiply(value,10),Amount(s[i]-'0'));}
  for(std::size_t i=decimals;i<6;++i)value=multiply(value,10);
  need(value<=rate_cap,"cost_rate_range");return value;
}
using Values=std::array<std::optional<Amount>,4>;
inline Values amounts(const Json& j,bool prices){
  exact(j,{"input_uncached","input_cache_read","input_cache_write","output"});Values out;
  for(std::size_t i=0;i<buckets.size();++i)out[i]=prices?rate(j[buckets[i]]):
    (j[buckets[i]].is_null()?std::optional<Amount>{}:std::optional<Amount>{integer(j[buckets[i]],token_cap)});
  return out;
}
inline Json normalized(const Values& v,bool prices){
  Json j=Json::object();for(std::size_t i=0;i<buckets.size();++i)
    j[buckets[i]]=v[i]?(prices?Json(decimal(*v[i],rate_scale,6)):Json(*v[i])):Json(nullptr);
  return j;
}
struct Rate {std::string provider,model;Values values;};
struct Call {std::string call_id,stage,rate_id,outcome;Amount attempt;Values tokens;};
struct Aggregate {
  Amount calls=0,failed=0,unknown_outcomes=0,retries=0,known=0,missing=0;
  std::array<Amount,4> tokens{},unknown_tokens{};
  void include(const Call& c,Amount subtotal,Amount gaps){
    calls=add(calls,1);failed+=c.outcome=="failure";unknown_outcomes+=c.outcome=="unknown";
    retries+=c.attempt>1;known=add(known,subtotal);missing=add(missing,gaps);
    for(std::size_t i=0;i<4;++i){if(c.tokens[i])tokens[i]=add(tokens[i],*c.tokens[i]);else ++unknown_tokens[i];}
  }
  Json json()const{
    Json usage=Json::object();for(std::size_t i=0;i<4;++i)usage[buckets[i]]={
      {"known_tokens",tokens[i]},{"unknown_calls",unknown_tokens[i]},
      {"total_tokens",unknown_tokens[i]?Json(nullptr):Json(tokens[i])}};
    return {{"calls",calls},{"failed_calls",failed},{"unknown_outcome_calls",unknown_outcomes},{"retry_calls",retries},
      {"known_subtotal",decimal(known,cost_scale,12)},{"total_estimate",missing?Json(nullptr):Json(decimal(known,cost_scale,12))},
      {"complete",missing==0},{"unknown_components",missing},{"tokens",usage}};
  }
};
inline Json report(const Json& root){
  exact(root,{"schema","currency","rates","calls"});
  need(root["schema"]=="qbrain-cost-input-v1","cost_schema");
  need(root["currency"].is_string(),"cost_currency");auto currency=root["currency"].get<std::string>();
  need(currency.size()==3,"cost_currency");for(char c:currency)need(c>='A'&&c<='Z',"cost_currency");
  need(root["rates"].is_array()&&root["rates"].size()<=64,"cost_rate_count");
  need(root["calls"].is_array()&&root["calls"].size()<=512,"cost_call_count");
  std::map<std::string,Rate> rates;std::map<std::string,Call> calls;
  for(const auto& r:root["rates"]){exact(r,{"rate_id","provider","model","per_million"});
    auto key=id(r["rate_id"]);Rate card{id(r["provider"]),id(r["model"]),amounts(r["per_million"],true)};
    need(rates.emplace(key,std::move(card)).second,"cost_duplicate_rate");}
  const std::set<std::string> stages={"main","embedding","summary","extraction","rerank","other"};
  for(const auto& c:root["calls"]){exact(c,{"call_id","stage","rate_id","attempt","outcome","tokens"});
    Call call{id(c["call_id"]),id(c["stage"]),id(c["rate_id"]),id(c["outcome"]),integer(c["attempt"],100),amounts(c["tokens"],false)};
    need(call.attempt>=1,"cost_attempt");need(stages.count(call.stage)!=0,"cost_stage");
    need(call.outcome=="success"||call.outcome=="failure"||call.outcome=="unknown","cost_outcome");
    // Keep the map key before moving call (evaluation order must not lose it).
    const auto key=call.call_id;need(calls.emplace(key,std::move(call)).second,"cost_duplicate_call");}
  Json canonical={{"schema","qbrain-cost-input-v1"},{"currency",currency},{"rates",Json::array()},{"calls",Json::array()}};
  for(const auto& [key,r]:rates)canonical["rates"].push_back({{"rate_id",key},{"provider",r.provider},{"model",r.model},{"per_million",normalized(r.values,true)}});
  Json rows=Json::array();Aggregate total;std::map<std::string,Aggregate> stage_totals,rate_totals;
  for(const auto& [key,c]:calls){
    canonical["calls"].push_back({{"call_id",key},{"stage",c.stage},{"rate_id",c.rate_id},{"attempt",c.attempt},{"outcome",c.outcome},{"tokens",normalized(c.tokens,false)}});
    auto card=rates.find(c.rate_id);Amount known=0,gaps=0;Json components=Json::object();
    for(std::size_t i=0;i<4;++i){
      auto price=card==rates.end()?std::optional<Amount>{}:card->second.values[i];
      std::optional<Amount> cost;Json missing=nullptr;
      if(!c.tokens[i])missing="usage_unknown";
      else if(*c.tokens[i]==0)cost=0;
      else if(!price)missing=card==rates.end()?"rate_card_missing":"rate_unknown";
      else cost=multiply(*c.tokens[i],*price);
      if(cost)known=add(known,*cost);else ++gaps;
      components[buckets[i]]={{"tokens",c.tokens[i]?Json(*c.tokens[i]):Json(nullptr)},
        {"rate_per_million",price?Json(decimal(*price,rate_scale,6)):Json(nullptr)},
        {"cost",cost?Json(decimal(*cost,cost_scale,12)):Json(nullptr)},{"missing",missing}};
    }
    rows.push_back({{"call_id",key},{"stage",c.stage},{"rate_id",c.rate_id},{"attempt",c.attempt},{"outcome",c.outcome},
      {"components",components},{"known_subtotal",decimal(known,cost_scale,12)},
      {"total_estimate",gaps?Json(nullptr):Json(decimal(known,cost_scale,12))},{"complete",gaps==0},{"unknown_components",gaps}});
    total.include(c,known,gaps);stage_totals[c.stage].include(c,known,gaps);rate_totals[c.rate_id].include(c,known,gaps);
  }
  Json by_stage=Json::array(),by_rate=Json::array();
  for(const auto& [key,t]:stage_totals){auto j=t.json();j["stage"]=key;by_stage.push_back(j);}
  for(const auto& [key,t]:rate_totals){auto j=t.json();j["rate_id"]=key;auto r=rates.find(key);
    j["provider"]=r==rates.end()?Json(nullptr):Json(r->second.provider);
    j["model"]=r==rates.end()?Json(nullptr):Json(r->second.model);by_rate.push_back(j);}
  Json out={{"schema","qbrain-cost-report-v1"},{"currency",currency},{"input_sha256",util::sha256_hex(canonical.dump())},
    {"basis","caller_supplied_disjoint_token_counts_and_rate_cards"},{"rate_unit","currency_per_million_tokens"},
    {"decimal_places",12},{"summary",total.json()},{"by_stage",by_stage},{"by_rate",by_rate},{"calls",rows},
    {"billing_verified",false},{"all_provider_calls_observed",false},{"provider_requests_sent",0},
    {"fees_taxes_discounts_included",false},{"currency_conversion_performed",false}};
  need(out.dump().size()+1<=output_cap,"cost_output_limit");return out;
}
inline Json parse_report(const std::string& raw){
  try{return report(util::parse_unique_json(raw,input_cap,16));}
  catch(const util::JsonInputError& e){
    if(e.failure()==util::JsonInputFailure::byte_limit)throw Error("cost_input_limit");
    if(e.failure()==util::JsonInputFailure::duplicate_key)throw Error("cost_duplicate_key");
    throw Error("cost_invalid_json");}
  catch(const nlohmann::json::exception&){throw Error("cost_invalid_json");}
}
inline int command(const std::vector<std::string>& args){
  try{
    need(args.size()==1&&args[0]=="report","cost_invalid_action");
    std::string raw;std::array<char,8192> buffer{};
    while(std::cin.read(buffer.data(),static_cast<std::streamsize>((std::min)(buffer.size(),input_cap+1-raw.size())) )||std::cin.gcount()){
      raw.append(buffer.data(),static_cast<std::size_t>(std::cin.gcount()));need(raw.size()<=input_cap,"cost_input_limit");}
    need(!std::cin.bad(),"cost_input_error");
    const auto result=parse_report(raw).dump();std::cout<<result<<'\n';return 0;
  }catch(const Error& e){std::cout<<Json{{"error",{{"code",e.what()}}}}.dump()<<'\n';return 2;}
  catch(...){std::cout<<"{\"error\":{\"code\":\"cost_local_error\"}}\n";return 2;}
}
} // namespace qbrain::accounting
