#include "qbrain/accounting/provider_usage.hpp"
#include <functional>
using namespace qbrain::accounting;
namespace ui=qbrain::accounting::usage_import;
namespace {
int checks=0;
void check(bool b,const char* message){if(!b)throw std::runtime_error(message);++checks;}
void reject(const std::function<void()>& fn,const char* code){try{fn();}catch(const Error& e){check(std::string(e.what())==code,code);return;}throw std::runtime_error("unexpected acceptance");}
Json base(){return {{"schema","qbrain-usage-import-v1"},{"currency","USD"},{"rates",Json::array({{{"rate_id","r"},{"provider","openai"},{"model","example"},{"per_million",{{"input_uncached","1"},{"input_cache_read","0.1"},{"input_cache_write","2"},{"output","3"}}}}})},{"records",Json::array()}};}
Json response(){return {{"object","response"},{"id","resp-1"},{"model","example"},{"status","completed"},{"usage",{{"input_tokens",100},{"output_tokens",50},{"total_tokens",150},{"input_tokens_details",{{"cached_tokens",30},{"cache_write_tokens",20}}},{"output_tokens_details",{{"reasoning_tokens",40}}}}}};}
Json entry(){return {{"call_id","one"},{"stage","main"},{"rate_id","r"},{"attempt",1},{"outcome","success"},{"format","openai_responses"},{"response",response()}};}
Json fixture(){auto x=base();x["records"].push_back(entry());return x;}
}
int main(){try{
 auto x=fixture();const auto original=x;auto r=ui::import_report(x);
 check(x==original,"pure input");check(r["cost_input"]["calls"][0]["tokens"]==Json{{"input_uncached",50},{"input_cache_read",30},{"input_cache_write",20},{"output",50}},"inclusive partition");
 check(r["cost_report"]["summary"]["total_estimate"]=="0.000243000000","exact linked cost");
 check(qbrain::accounting::report(r["cost_input"])==r["cost_report"],"existing report reused");
 auto text=x;text["records"][0]["response"]["output"]=Json::array({{{"text","PRIVATE_RESPONSE_SENTINEL"}}});
 check(ui::import_report(text)==r,"body independent report and digest");
 auto missing=x;missing["records"][0]["response"]["usage"]["input_tokens_details"].erase("cache_write_tokens");
 auto m=ui::import_report(missing);check(m["cost_input"]["calls"][0]["tokens"]["input_uncached"].is_null(),"missing cache write leaves ordinary unknown");
 check(m["cost_input"]["calls"][0]["tokens"]["input_cache_write"].is_null(),"missing cache write is not free");
 check(m["cost_report"]["summary"]["total_estimate"].is_null(),"missing usage not complete");
 for(auto bad:{Json(true),Json(false),Json(-1),Json(1.0),Json("1"),Json::array(),Json::object(),Json(1000000001ULL)}){
  auto t=x;t["records"][0]["response"]["usage"]["input_tokens"]=bad;reject([&]{ui::import_report(t);},"usage_quantity");
 }
 for(int i=0;i<16;++i){auto t=x;auto& u=t["records"][0]["response"]["usage"];
  if(i&1)u["input_tokens"]=nullptr;if(i&2)u["input_tokens_details"]["cached_tokens"]=nullptr;
  if(i&4)u["input_tokens_details"]["cache_write_tokens"]=nullptr;if(i&8)u["output_tokens"]=nullptr;
  auto out=ui::import_report(t);check(out["usage_complete"]==(i==0),"unknown combinations");
 }
 auto dup=x;auto e=entry();e["call_id"]="two";e["attempt"]=2;dup["records"].push_back(e);
 reject([&]{ui::import_report(dup);},"usage_duplicate_response");
 e["response"]["id"]="resp-2";dup["records"][1]=e;check(ui::import_report(dup)["cost_report"]["summary"]["calls"]==2,"distinct attempts priced");
 auto inconsistent=x;inconsistent["records"][0]["response"]["usage"]["input_tokens_details"]["cached_tokens"]=90;
 reject([&]{ui::import_report(inconsistent);},"usage_inconsistent");
 inconsistent=x;inconsistent["records"][0]["response"]["usage"]["total_tokens"]=149;
 reject([&]{ui::import_report(inconsistent);},"usage_inconsistent");
 auto partial=x;auto& pu=partial["records"][0]["response"]["usage"];
 pu["input_tokens"]=nullptr;pu["output_tokens"]=0;pu["output_tokens_details"]=Json::object();pu["total_tokens"]=5;
 reject([&]{ui::import_report(partial);},"usage_inconsistent");
 partial=x;partial["records"][0]["response"]["usage"]["input_tokens"]=0;
 partial["records"][0]["response"]["usage"]["input_tokens_details"]=Json::object();
 partial["records"][0]["response"]["usage"]["output_tokens"]=nullptr;partial["records"][0]["response"]["usage"]["total_tokens"]=5;
 reject([&]{ui::import_report(partial);},"usage_inconsistent");
 auto zero=x;zero["records"][0]["response"]["usage"]={{"input_tokens",0},{"output_tokens",0},{"total_tokens",0}};
 check(ui::import_report(zero)["usage_complete"]==true,"zero total proves zero cache");
 auto failure=x;failure["records"][0]["response"]["status"]="failed";
 reject([&]{ui::import_report(failure);},"usage_outcome_conflict");
 failure["records"][0]["outcome"]="failure";
 check(ui::import_report(failure)["cost_report"]["summary"]["total_estimate"]=="0.000243000000","failed attempt is billed");
 failure["records"][0]["response"]=nullptr;check(ui::import_report(failure)["cost_report"]["summary"]["total_estimate"].is_null(),"missing failed response unknown");
 auto a=x;a["rates"][0]["provider"]="anthropic";auto& ar=a["records"][0];ar["format"]="anthropic_messages";
 ar["response"]={{"type","message"},{"role","assistant"},{"id","msg-1"},{"model","example"},{"stop_reason","end_turn"},
  {"usage",{{"input_tokens",50},{"cache_read_input_tokens",30},{"cache_creation_input_tokens",20},{"output_tokens",50},
  {"cache_creation",{{"ephemeral_5m_input_tokens",20},{"ephemeral_1h_input_tokens",0}}}}}};
 check(ui::import_report(a)["cost_input"]["calls"][0]["tokens"]==r["cost_input"]["calls"][0]["tokens"],"Anthropic separate counters");
 auto mixed=a;mixed["records"][0]["response"]["usage"]["cache_creation"]={{"ephemeral_5m_input_tokens",10},{"ephemeral_1h_input_tokens",10}};
 reject([&]{ui::import_report(mixed);},"usage_mixed_cache_ttl");
 for(auto first:{Json(1),Json()}){
  auto invalid_tool=a;invalid_tool["records"][0]["response"]["usage"]["server_tool_use"]={{"web_fetch_requests",first},{"web_search_requests","invalid"}};
  reject([&]{ui::import_report(invalid_tool);},"usage_quantity");
 }
 auto it=a;it["records"][0]["response"]["usage"]["iterations"]=Json::array({Json::object()});
 reject([&]{ui::import_report(it);},"usage_iterations_unsupported");
 auto audio=x;audio["records"][0]["response"]["usage"]["output_tokens_details"]["audio_tokens"]=1;
 reject([&]{ui::import_report(audio);},"usage_audio_unsupported");
 auto wrong=x;wrong["rates"][0]["model"]="different";reject([&]{ui::import_report(wrong);},"usage_rate_model_mismatch");
 wrong=x;wrong["rates"][0]["provider"]="different";reject([&]{ui::import_report(wrong);},"usage_rate_provider_mismatch");
 wrong=x;wrong["records"][0]["response"]["status"]="in_progress";reject([&]{ui::import_report(wrong);},"usage_response_nonterminal");
 wrong=x;wrong["records"][0]["response"]["usage"]["unexpected"]=1;reject([&]{ui::import_report(wrong);},"usage_fields");
 reject([&]{ui::parse("{\"schema\":1,\"\\u0073chema\":2}");},"usage_duplicate_key");
 reject([&]{ui::parse(std::string(ui::import_cap+1,' '));},"usage_input_limit");
 reject([&]{ui::parse("{}{}");},"usage_invalid_json");
 reject([&]{ui::parse(std::string(1,char(0xff)));},"usage_invalid_json");
 auto bound=x;bound["records"]=Json::array();for(int i=0;i<128;++i){auto en=entry();en["call_id"]=std::to_string(i);en["response"]["id"]="r"+std::to_string(i);bound["records"].push_back(en);}
 check(ui::import_report(bound)["cost_report"]["summary"]["calls"]==128,"128 record boundary");
 bound["records"].push_back(entry());reject([&]{ui::import_report(bound);},"usage_record_count");
 auto empty=base();check(ui::import_report(empty)["cost_report"]["summary"]["total_estimate"]=="0.000000000000","empty supplied list only");
 std::cout<<Json{{"schema","qbrain-n48g-direct-v1"},{"passed",checks},{"failed",0},{"provider_requests_sent",0}}.dump()<<'\n';return 0;
 }catch(const std::exception& e){std::cerr<<"direct failure after "<<checks<<": "<<e.what()<<'\n';return 1;}}
