#include "qbrain/accounting/token_cost.hpp"
#include <functional>
#include <iostream>
using namespace qbrain::accounting;
namespace {
int checks=0;
void check(bool b,const char* name){if(!b)throw std::runtime_error(name);++checks;}
void refuses(const std::function<void()>& f,const char* code){try{f();}catch(const Error& e){check(std::string(e.what())==code,code);return;}throw std::runtime_error(std::string("accepted ")+code);}
Json usage(Json value=0){Json j=Json::object();for(auto b:buckets)j[b]=value;return j;}
Json fixture(){return {{"schema","qbrain-cost-input-v1"},{"currency","USD"},
 {"rates",Json::array({{{"rate_id","r1"},{"provider","synthetic"},{"model","m1"},{"per_million",usage("2.5")}}})},
 {"calls",Json::array({{{"call_id","c1"},{"stage","main"},{"rate_id","r1"},{"attempt",1},{"outcome","success"},{"tokens",usage(1)}}})}};}
}
int main(){try {
 check(decimal(0,cost_scale,12)=="0.000000000000","zero decimal");
 check(decimal(1,cost_scale,12)=="0.000000000001","smallest decimal");
 check(decimal(std::numeric_limits<Amount>::max(),cost_scale,12)=="18446744.073709551615","max decimal");
 check(add(0,std::numeric_limits<Amount>::max())==std::numeric_limits<Amount>::max(),"max add");
 refuses([]{add(std::numeric_limits<Amount>::max(),1);},"cost_overflow");
 check(multiply(0,std::numeric_limits<Amount>::max())==0,"zero multiply");
 check(multiply(1,std::numeric_limits<Amount>::max())==std::numeric_limits<Amount>::max(),"max multiply");
 refuses([]{multiply(std::numeric_limits<Amount>::max(),2);},"cost_overflow");
 for(const auto& [text,n]:std::map<std::string,Amount>{{"0",0},{"0.000001",1},{"2.5",2500000},{"1000000.000000",rate_cap}})
   check(rate(text)==n,"valid rate");
 check(!rate(nullptr),"null rate");
 for(Json j:{Json(1),Json(1.5),Json(true),Json(""),Json("01"),Json("1e2"),Json("-1"),Json("+1"),Json("1."),Json(".1"),Json("1.1234567"),Json(" 1"),Json("1\n"),Json("1.1.1")})
   refuses([&]{rate(j);},"cost_rate_decimal");
 refuses([]{rate("1000000.000001");},"cost_rate_range");
 for(Json j:{Json(-1),Json(1.0),Json(true),Json("1"),Json(nullptr),Json(token_cap+1)})
   refuses([&]{integer(j,token_cap);},"cost_quantity");
 for(Json j:{Json("bad id"),Json(std::string("bad\0id",6)),Json("中文"),Json(std::string(65,'x')),Json(true),Json("")})
   refuses([&]{id(j);},"cost_identifier");
 auto input=fixture();auto result=report(input);
 check(result["summary"]["total_estimate"]=="0.000010000000","exact four-component sum");
 check(result["summary"]["complete"]==true&&result["summary"]["unknown_components"]==0,"complete fixture");
 auto normalized_input=input;normalized_input["rates"][0]["per_million"]=usage("2.500000");
 check(report(normalized_input)==result,"rate spelling canonicalized");
 for(auto bucket:buckets){
  auto j=input;j["calls"][0]["tokens"][bucket]=nullptr;auto out=report(j);
  check(out["summary"]["total_estimate"].is_null()&&out["summary"]["known_subtotal"]=="0.000007500000","unknown tokens preserve known cost");
  check(out["calls"][0]["components"][bucket]["missing"]=="usage_unknown","unknown usage reason");
  check(out["summary"]["tokens"][bucket]["total_tokens"].is_null(),"unknown token total");
  j=input;j["rates"][0]["per_million"][bucket]=nullptr;out=report(j);
  check(out["calls"][0]["components"][bucket]["missing"]=="rate_unknown","unknown rate reason");
  j["calls"][0]["tokens"][bucket]=0;out=report(j);
  check(out["summary"]["complete"]==true&&out["calls"][0]["components"][bucket]["cost"]=="0.000000000000","zero tokens need no rate");
  j=input;j["calls"][0]["tokens"][bucket]=nullptr;j["rates"][0]["per_million"][bucket]="0";
  check(report(j)["summary"]["complete"]==false,"free unknown usage remains unknown");
 }
 auto no_rate=input;no_rate["rates"]=Json::array();auto unknown=report(no_rate);
 check(unknown["summary"]["known_subtotal"]=="0.000000000000"&&unknown["summary"]["total_estimate"].is_null(),"missing rate is not a free call");
 check(unknown["by_rate"][0]["provider"].is_null()&&unknown["summary"]["unknown_components"]==4,"missing card metadata");
 no_rate["calls"][0]["tokens"]=usage(0);check(report(no_rate)["summary"]["total_estimate"]=="0.000000000000","all-zero missing card");
 auto dup=input;dup["calls"].push_back(input["calls"][0]);refuses([&]{report(dup);},"cost_duplicate_call");
 dup=input;dup["rates"].push_back(input["rates"][0]);refuses([&]{report(dup);},"cost_duplicate_rate");
 auto empty=input;empty["calls"]=Json::array();empty["rates"]=Json::array();auto e=report(empty);
 check(e["summary"]["calls"]==0&&e["summary"]["total_estimate"]=="0.000000000000"&&e["by_stage"].empty(),"empty observations correctly labelled");
 auto invalid=input;invalid["prompt"]="private";refuses([&]{report(invalid);},"cost_fields");
 for(auto field:{"call_id","stage","rate_id","attempt","outcome","tokens"}){auto j=input;j["calls"][0].erase(field);refuses([&]{report(j);},"cost_fields");}
 invalid=input;invalid["calls"][0]["attempt"]=0;refuses([&]{report(invalid);},"cost_attempt");
 invalid=input;invalid["calls"][0]["stage"]="guess";refuses([&]{report(invalid);},"cost_stage");
 invalid=input;invalid["calls"][0]["outcome"]="skipped";refuses([&]{report(invalid);},"cost_outcome");
 for(auto cur:{Json("usd"),Json("US"),Json("USDx"),Json(1)}){auto j=input;j["currency"]=cur;refuses([&]{report(j);},"cost_currency");}
 invalid=input;invalid["schema"]="future";refuses([&]{report(invalid);},"cost_schema");
 auto large=input;large["rates"][0]["per_million"]=usage("1000000");large["calls"][0]["tokens"]=usage(token_cap);
 refuses([&]{report(large);},"cost_overflow");
 large=input;large["rates"][0]["per_million"]=usage("10000");large["calls"][0]["tokens"]=usage(0);
 large["calls"][0]["tokens"]["output"]=1000000000;
 auto second=large["calls"][0];second["call_id"]="c2";large["calls"].push_back(second);
 refuses([&]{report(large);},"cost_overflow"); // Each call fits; aggregate does not.
 Json many=fixture();many["calls"]=Json::array();
 for(int i=0;i<512;++i){auto c=input["calls"][0];c["call_id"]="c"+std::to_string(i);c["attempt"]=i%2+1;
   c["stage"]=(i%2?"embedding":"main");c["outcome"]=(i%3?"success":"failure");many["calls"].push_back(c);}
 auto m=report(many);check(m["summary"]["calls"]==512&&m["summary"]["retry_calls"]==256,"maximum and retry counts");
 check(m["summary"]["failed_calls"]==171&&m["summary"]["total_estimate"]=="0.005120000000","failure outcomes still costed");
 std::reverse(many["calls"].begin(),many["calls"].end());check(report(many)==m,"input order independent");
 many["calls"].push_back(input["calls"][0]);refuses([&]{report(many);},"cost_call_count");
 for(const auto& raw:std::vector<std::string>{"{\"schema\":1,\"schema\":2}","{\"x\":1,\"\\u0078\":2}"})refuses([&]{parse_report(raw);},"cost_duplicate_key");
 for(const auto& raw:std::vector<std::string>{"", "[", "{\"x\":NaN}",std::string(1,char(255)),std::string("{}\0",3)})refuses([&]{parse_report(raw);},"cost_invalid_json");
 auto serialized=input.dump();check(parse_report(serialized+std::string(input_cap-serialized.size(),' '))==result,"exact byte limit");
 refuses([&]{parse_report(serialized+std::string(input_cap-serialized.size()+1,' '));},"cost_input_limit");
 std::cout<<Json{{"schema","qbrain-n48f-direct-v1"},{"passed",checks},{"failed",0},{"provider_calls",0}}.dump()<<'\n';
 return 0;
}catch(const std::exception& e){std::cerr<<"test failed after "<<checks<<": "<<e.what()<<'\n';return 1;}}
