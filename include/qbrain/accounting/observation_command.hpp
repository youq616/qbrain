#pragma once
#include "qbrain/accounting/runtime_observation.hpp"
#include "qbrain/maintenance/sqlite_backup.hpp"
#include <sstream>

namespace qbrain::accounting::observation {
inline Event parse_event(const Json& j) {
  exact(j,{"sequence","api","complete","transport","send_invoked","http_status","elapsed_ms","usage","retry_relation","price","cost"});
  Event e;e.sequence=integer(j["sequence"],512);
  need(e.sequence>0&&j["complete"].is_boolean(),"observation_record");e.complete=j["complete"].get<bool>();
  bool found=false;for(auto v:{Api::chat,Api::responses,Api::embeddings,Api::rerank,Api::other})if(j["api"]==name(v)){e.kind=v;found=true;}
  need(found,"observation_api");found=false;
  for(auto v:{Outcome::pending,Outcome::http_completed,Outcome::http_error,Outcome::invalid_request,Outcome::transport_error,
              Outcome::timeout,Outcome::cancelled,Outcome::response_limit,Outcome::unsupported_platform,Outcome::local_exception})
    if(j["transport"]==name(v)){e.result=v;found=true;}
  need(found&&e.complete==(e.result!=Outcome::pending),"observation_outcome");
  if(e.complete){need(j["send_invoked"].is_boolean(),"observation_send");e.send_invoked=j["send_invoked"].get<bool>();e.elapsed_ms=integer(j["elapsed_ms"],std::numeric_limits<Amount>::max());}
  else need(j["send_invoked"].is_null()&&j["elapsed_ms"].is_null(),"observation_pending");
  if(!j["http_status"].is_null()){e.http_status=int(integer(j["http_status"],599));need(e.http_status>=100&&e.complete,"observation_status");}
  exact(j["usage"],{"state","provider_state","provider_error_present","provider_status_conflict",
                     "input_inclusive","output_inclusive","total_inclusive","tokens"});
  const auto& u=j["usage"];found=false;
  for(auto v:{UsageState::unavailable,UsageState::recognized,UsageState::embedding_input_only,UsageState::invalid,UsageState::unsupported})
    if(u["state"]==name(v)){e.usage.state=v;found=true;}
  need(found,"observation_usage_state");found=false;
  for(auto v:{ProviderState::unknown,ProviderState::completed,ProviderState::failed,ProviderState::cancelled,ProviderState::incomplete,ProviderState::pending})
    if(u["provider_state"]==name(v)){e.usage.provider=v;found=true;}
  need(found,"observation_provider_state");
  need(u["provider_error_present"].is_null()||u["provider_error_present"].is_boolean(),"observation_error_presence");
  if(!u["provider_error_present"].is_null())e.usage.provider_error_present=u["provider_error_present"].get<bool>();
  need(u["provider_status_conflict"].is_boolean(),"observation_status_conflict");
  e.usage.provider_status_conflict=u["provider_status_conflict"].get<bool>();
  const bool conflict=e.kind==Api::responses && e.usage.provider==ProviderState::completed &&
    e.usage.provider_error_present==true;
  need(e.usage.provider_status_conflict==conflict,"observation_status_conflict");
  if(e.usage.provider!=ProviderState::unknown || e.usage.state==UsageState::recognized ||
     e.usage.state==UsageState::embedding_input_only)
    need(e.usage.provider_error_present.has_value(),"observation_error_presence");
  e.usage.input=usage_import::count(u,"input_inclusive");e.usage.output=usage_import::count(u,"output_inclusive");e.usage.total=usage_import::count(u,"total_inclusive");
  e.usage.tokens=amounts(u["tokens"],false);
  need(j["retry_relation"].is_null()&&j["price"].is_null()&&j["cost"].is_null(),"observation_private_or_unpriced_fields");
  if(e.usage.state!=UsageState::recognized){for(auto x:e.usage.tokens)need(!x,"observation_unknown_tokens");}
  if(e.usage.state!=UsageState::recognized&&e.usage.state!=UsageState::embedding_input_only)
    need(!e.usage.input&&!e.usage.output&&!e.usage.total,"observation_unknown_usage");
  if(e.result!=Outcome::http_completed){need(e.usage.state==UsageState::unavailable&&e.usage.provider==ProviderState::unknown&&
    !e.usage.provider_error_present.has_value()&&!e.usage.provider_status_conflict,"observation_failure_usage");}
  if(e.result==Outcome::http_completed)need(e.http_status>=200&&e.http_status<300,"observation_status");
  usage_import::subset(e.usage.tokens[1],e.usage.input);usage_import::subset(e.usage.tokens[2],e.usage.input);
  usage_import::equality(e.usage.tokens[3],e.usage.output);
  const auto sum=usage_import::sum(usage_import::sum(e.usage.tokens[0],e.usage.tokens[1]),e.usage.tokens[2]);
  usage_import::equality(sum,e.usage.input);
  if(e.usage.state==UsageState::embedding_input_only)usage_import::equality(e.usage.input,e.usage.total);
  else usage_import::equality(e.usage.total,usage_import::sum(e.usage.input,e.usage.output));
  if(e.usage.state==UsageState::recognized){
    need(e.kind==Api::chat||e.kind==Api::responses,"observation_usage_api");
    const bool responses=e.kind==Api::responses;
    Json raw={{responses?"input_tokens":"prompt_tokens",quantity(e.usage.input)},
      {responses?"output_tokens":"completion_tokens",quantity(e.usage.output)},{"total_tokens",quantity(e.usage.total)},
      {responses?"input_tokens_details":"prompt_tokens_details",{{"cached_tokens",quantity(e.usage.tokens[1])},{"cache_write_tokens",quantity(e.usage.tokens[2])}}}};
    need(usage_import::openai_usage(raw,responses).tokens==e.usage.tokens,"observation_partition");
    if(responses)need(e.usage.provider!=ProviderState::pending&&e.usage.provider!=ProviderState::unknown,"observation_nonterminal_usage");
  }
  if(e.usage.state==UsageState::embedding_input_only)need(e.kind==Api::embeddings&&!e.usage.output,"observation_embedding_usage");
  if(e.result==Outcome::invalid_request||e.result==Outcome::unsupported_platform)
    need(!e.send_invoked&&e.http_status==0,"observation_no_send");
  need(json(e)==j,"observation_noncanonical");return e;
}
inline std::vector<Event> validate_report(const Json& r) {
  need(r.is_object()&&r.value("schema",Json())=="qbrain-runtime-observation-v2","observation_schema");
  exact(r,{"schema","scope","sealed","dispatch_state","dispatch_return","process_exit","stdout_complete","stderr_complete",
           "completion_scope","recording_complete","counts","transport_counts","records",
           "retry_attempts","total_estimate","currency","price_basis","billing_verified","all_provider_calls_observed",
           "server_receipt_verified","application_success_verified"});
  need(r["scope"]=="same_process_http_post_json_invocations","observation_schema");
  need(r["sealed"].is_boolean()&&r["recording_complete"].is_boolean(),"observation_booleans");
  if(r["dispatch_state"]=="returned")
    need(r["dispatch_return"].is_number_integer()&&r["dispatch_return"]>=std::numeric_limits<int>::min()&&
         r["dispatch_return"]<=std::numeric_limits<int>::max(),"observation_dispatch_return");
  else need((r["dispatch_state"]=="exception"||r["dispatch_state"]=="not_observed")&&
            r["dispatch_return"].is_null(),"observation_dispatch_return");
  need(r["process_exit"].is_null()&&r["stdout_complete"].is_null()&&r["stderr_complete"].is_null()&&
       r["completion_scope"]=="http_attempt_records_only","observation_completion_claim");
  for(const auto* field:{"billing_verified","all_provider_calls_observed","server_receipt_verified","application_success_verified"})
    need(r[field].is_boolean()&&!r[field].get<bool>(),"observation_claim");
  need(r["retry_attempts"].is_null()&&r["total_estimate"].is_null()&&r["currency"].is_null()&&r["price_basis"]=="unassigned","observation_unpriced");
  exact(r["counts"],{"started","finished","retained","dropped","pending","io_errors"});const auto& c=r["counts"];
  const auto started=integer(c["started"],1000000000),finished=integer(c["finished"],1000000000),retained=integer(c["retained"],512),
    dropped=integer(c["dropped"],1000000000),pending=integer(c["pending"],1000000000),errors=integer(c["io_errors"],1000000000);
  need(finished<=started&&pending==started-finished&&retained+dropped==started,"observation_counts");
  need(r["records"].is_array()&&r["records"].size()==retained,"observation_records");
  std::vector<Event> events;Json totals=Json::object();Amount completed=0;
  for(const auto& value:r["records"]){auto e=parse_event(value);need(e.sequence==events.size()+1,"observation_sequence");
    completed+=e.complete;const auto k=name(e.result);totals[k]=totals.value(k,Amount(0))+1;events.push_back(e);}
  need(finished>=completed&&finished-completed<=dropped,"observation_finished");
  need(r["transport_counts"].is_object(),"observation_transport_counts");
  for(const auto& item:r["transport_counts"].items())(void)integer(item.value(),512);
  need(totals==r["transport_counts"],"observation_transport_counts");
  const bool complete=r["sealed"].get<bool>()&&dropped==0&&pending==0&&errors==0;
  need(r["recording_complete"].get<bool>()==complete,"observation_completeness");return events;
}
inline Json price(const Json& capture,const Json& supplied) {
  const auto events=validate_report(capture);
  exact(supplied,{"schema","currency","rates","assignments"});need(supplied["schema"]=="qbrain-observation-rates-v1","observation_rates_schema");
  need(supplied["assignments"].is_array()&&supplied["assignments"].size()==events.size(),"observation_assignment_coverage");
  Json input={{"schema","qbrain-cost-input-v1"},{"currency",supplied["currency"]},{"rates",supplied["rates"]},{"calls",Json::array()}};
  (void)accounting::report(input); // Reuse the original exact arithmetic/rate contracts.
  std::set<Amount> used;
  for(const auto& a:supplied["assignments"]){
    exact(a,{"sequence","call_id","attempt","stage","rate_id"});const auto sequence=integer(a["sequence"],events.size());
    need(sequence>0&&used.insert(sequence).second,"observation_assignment_sequence");const auto& e=events[sequence-1];
    std::string state="unknown"; // HTTP200 cannot certify application success.
    if(e.complete&&e.result!=Outcome::http_completed)state="failure";
    if(!e.usage.provider_status_conflict &&
       (e.usage.provider==ProviderState::failed||e.usage.provider==ProviderState::cancelled))state="failure";
    input["calls"].push_back({{"call_id",a["call_id"]},{"attempt",a["attempt"]},{"stage",a["stage"]},{"rate_id",a["rate_id"]},
      {"outcome",state},{"tokens",normalized(e.usage.tokens,false)}});
  }
  const auto priced=accounting::report(input);
  return {{"schema","qbrain-observation-cost-v2"},{"scope","retained_runtime_http_records"},
    {"recording_complete",capture["recording_complete"]},{"capture_counts",capture["counts"]},
    {"completion_scope",capture["completion_scope"]},{"dispatch_state",capture["dispatch_state"]},
    {"dispatch_return",capture["dispatch_return"]},{"process_exit",nullptr},
    {"stdout_complete",nullptr},{"stderr_complete",nullptr},{"application_success_verified",false},
    {"total_estimate",capture["recording_complete"].get<bool>()?priced["summary"]["total_estimate"]:Json(nullptr)},
    {"observed_record_cost",priced},{"rate_applicability_verified",false},{"retry_labels","caller_supplied_not_inferred"},
    {"billing_verified",false},{"all_provider_calls_observed",false},{"provider_requests_sent",0}};
}
template<class Invoke>
int command(int argc,char** argv,Invoke&& invoke) {
  namespace io=maintenance::backup;
  try {
    if(argc==7&&std::string(argv[2])=="cost"&&std::string(argv[3])=="--report"&&std::string(argv[5])=="--assignments"){
      const auto r=util::parse_unique_json(io::read(io::path(argv[4]),2097152),2097152,32);
      const auto a=util::parse_unique_json(io::read(io::path(argv[6]),262144),262144,16);
      std::cout<<price(r,a).dump()<<'\n';return 0;
    }
    need(argc>=6&&std::string(argv[2])=="--output"&&std::string(argv[4])=="--"&&std::string(argv[5])!="observe","observation_arguments");
    const auto output=io::path(argv[3]);io::new_directory(output);io::new_directory(output/"attempts");
    io::write_new(output/"started.json",Json{{"schema","qbrain-observation-start-v2"},{"scope","same_process_http_post_json_invocations"},
      {"argv_recorded",false},{"private_content_recorded",false},{"abrupt_exit_is_unknown",true}}.dump()+"\n");
    auto collector=std::make_shared<Collector>([output](const Event& e){
      io::write_new(output/"attempts"/(std::to_string(e.sequence)+(e.complete?".finish.json":".start.json")),json(e).dump()+"\n");
    });
    std::vector<char*> forwarded;forwarded.push_back(argv[0]);for(int i=5;i<argc;++i)forwarded.push_back(argv[i]);forwarded.push_back(nullptr);
    std::optional<int> code;std::exception_ptr failure;
    { Session session(collector);try{code=invoke(int(forwarded.size()-1),forwarded.data());}catch(...){failure=std::current_exception();} }
    Json final=collector->report(true,code,bool(failure));io::write_new(output/"report.json",final.dump()+"\n");
    if(failure){std::cerr<<"{\"error\":{\"code\":\"observed_command_exception\"}}\n";return 2;}
    if(!final["recording_complete"].get<bool>()){std::cerr<<"{\"error\":{\"code\":\"observation_incomplete\"}}\n";return 2;}
    return *code;
  }catch(const Error& e){std::cerr<<Json{{"error",{{"code",e.what()}}}}.dump()<<'\n';return 2;}
  catch(...){std::cerr<<"{\"error\":{\"code\":\"observation_io_or_input_error\"}}\n";return 2;}
}
} // namespace qbrain::accounting::observation
