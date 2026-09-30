#pragma once
#include "qbrain/accounting/logical_observation.hpp"
#include "qbrain/accounting/observation_command.hpp"

namespace qbrain::accounting::logical {
inline Event parse_event(const Json& j) {
  exact(j,{"sequence","entry","parent_sequence","parent_relation","return_state","path","api_result_ok",
           "fallback_taken","elapsed_ms","tokens","price","cost","retry_relation"});
  Event e;e.sequence=integer(j["sequence"],512);need(e.sequence>0,"logical_sequence");
  bool found=false;for(auto x:{Kind::chat,Kind::text_embedding,Kind::image_embedding,Kind::rerank})
    if(j["entry"]==name(x)){e.kind=x;found=true;}
  need(found,"logical_entry");found=false;
  for(auto x:{Path::unknown,Path::remote_candidate,Path::missing_credentials,Path::invalid_input,
              Path::mock,Path::empty_input,Path::disabled,Path::local_baseline,Path::callback})
    if(j["path"]==name(x)){e.path=x;found=true;}
  need(found,"logical_path");found=false;
  for(auto x:{Return::pending,Return::returned,Return::exception})
    if(j["return_state"]==name(x)){e.state=x;found=true;}
  need(found,"logical_return");found=false;
  for(auto x:{Parent::root,Parent::nested,Parent::capacity,Parent::other_session})
    if(j["parent_relation"]==name(x)){e.relation=x;found=true;}
  need(found,"logical_parent");
  if(!j["parent_sequence"].is_null()){e.parent=integer(j["parent_sequence"],512);need(e.parent>0&&e.parent<e.sequence,"logical_parent");}
  need((e.relation==Parent::nested)==bool(e.parent),"logical_parent");
  for(const auto* key:{"api_result_ok","fallback_taken"})need(j[key].is_null()||j[key].is_boolean(),"logical_bool");
  if(!j["api_result_ok"].is_null())e.result_ok=j["api_result_ok"].get<bool>();
  if(!j["fallback_taken"].is_null())e.fallback=j["fallback_taken"].get<bool>();
  if(e.state==Return::pending)need(j["elapsed_ms"].is_null()&&e.path==Path::unknown&&!e.result_ok&&!e.fallback,"logical_pending");
  else e.elapsed_ms=integer(j["elapsed_ms"],std::numeric_limits<Amount>::max());
  if(e.state!=Return::returned)need(!e.result_ok,"logical_exception_result");
  if(e.kind==Kind::rerank)need(!e.result_ok,"logical_reranker_result");
  for(const auto* key:{"tokens","price","cost","retry_relation"})need(j[key].is_null(),"logical_unpriced");
  need(json(e)==j,"logical_noncanonical");return e;
}
inline Json verify(const Json& logical,const Json& http_report) {
  const auto http_events=http::validate_report(http_report);
  exact(logical,{"schema","scope","sealed","recording_complete","completion_scope","counts","records","http_links",
    "dispatch_state","dispatch_return","process_exit","stdout_complete","stderr_complete","tokens","total_estimate",
    "currency","retry_relationships_inferred","billing_verified","all_model_calls_observed","automatic_thread_parent_propagation"});
  need(logical["schema"]=="qbrain-logical-observation-v1"&&
    logical["scope"]=="instrumented_model_entries_same_process"&&
    logical["completion_scope"]=="logical_call_records_only","logical_schema");
  need(logical["sealed"].is_boolean()&&logical["recording_complete"].is_boolean(),"logical_bool");
  for(const auto* key:{"process_exit","stdout_complete","stderr_complete","tokens","total_estimate","currency"})
    need(logical[key].is_null(),"logical_unknown");
  for(const auto* key:{"retry_relationships_inferred","billing_verified","all_model_calls_observed","automatic_thread_parent_propagation"})
    need(logical[key].is_boolean()&&!logical[key].get<bool>(),"logical_claim");
  for(const auto* key:{"dispatch_state","dispatch_return","process_exit","stdout_complete","stderr_complete"})
    need(logical[key]==http_report[key],"logical_dispatch_mismatch");
  need(logical["sealed"]==http_report["sealed"],"logical_seal_mismatch");
  exact(logical["counts"],{"started","finished","retained","dropped","pending","record_errors"});
  const auto& c=logical["counts"];
  const auto started=integer(c["started"],1000000000),finished=integer(c["finished"],1000000000),
    retained=integer(c["retained"],512),dropped=integer(c["dropped"],1000000000),
    pending=integer(c["pending"],1000000000),errors=integer(c["record_errors"],1000000000);
  need(finished<=started&&pending==started-finished&&retained+dropped==started,"logical_counts");
  need(logical["records"].is_array()&&logical["records"].size()==retained,"logical_records");
  std::vector<Event> events;Amount completed=0;
  for(const auto& j:logical["records"]){
    auto e=parse_event(j);need(e.sequence==events.size()+1,"logical_sequence");
    completed+=e.state!=Return::pending;events.push_back(e);
  }
  need(finished>=completed&&finished-completed<=dropped,"logical_finished");
  const bool complete=logical["sealed"].get<bool>()&&!dropped&&!pending&&!errors;
  need(logical["recording_complete"].get<bool>()==complete,"logical_completeness");
  need(logical["http_links"].is_array()&&logical["http_links"].size()<=http_events.size(),"logical_links");
  Amount linked=0;
  for(std::size_t i=0;i<logical["http_links"].size();++i){
    const auto& l=logical["http_links"][i];
    exact(l,{"http_sequence","logical_sequence","association"});
    need(integer(l["http_sequence"],512)==i+1,"logical_http_sequence");
    if(l["association"]=="innermost"){
      const auto id=integer(l["logical_sequence"],retained);need(id>0,"logical_link_target");++linked;
    }else{
      need(l["logical_sequence"].is_null()&&(l["association"]=="outside_instrumented_scope"||
        l["association"]=="logical_call_not_retained"||l["association"]=="different_session"),"logical_unattributed");
      if(l["association"]=="logical_call_not_retained")need(dropped>0,"logical_capacity_link");
    }
  }
  const bool inventory=logical["http_links"].size()==http_events.size();
  // A lost link is diagnosable as incomplete, never reinterpreted as no HTTP.
  need(inventory||errors>0,"logical_link_loss");
  return {{"schema","qbrain-model-observation-check-v1"},
    {"logical_recording_complete",complete},{"http_recording_complete",http_report["recording_complete"]},
    {"link_inventory_complete",inventory},{"recording_complete",complete&&inventory&&http_report["recording_complete"].get<bool>()},
    {"logical_calls",started},{"http_attempts",http_report["counts"]["started"]},
    {"linked_retained_http",linked},{"unattributed_retained_http",Amount(http_events.size())-linked},
    {"process_exit",nullptr},{"stdout_complete",nullptr},{"stderr_complete",nullptr},
    {"tokens",nullptr},{"total_estimate",nullptr},{"billing_verified",false},{"all_model_calls_observed",false}};
}
template<class Invoke>
int command(int argc,char** argv,Invoke&& invoke) {
  namespace io=maintenance::backup;
  try{
    if(argc==7&&std::string(argv[2])=="verify"&&std::string(argv[3])=="--logical"&&std::string(argv[5])=="--http"){
      auto l=util::parse_unique_json(io::read(io::path(argv[4]),2097152),2097152,32);
      auto h=util::parse_unique_json(io::read(io::path(argv[6]),2097152),2097152,32);
      auto r=verify(l,h);std::cout<<r.dump()<<'\n';return r["recording_complete"].get<bool>()?0:2;
    }
    need(argc>=6&&std::string(argv[2])=="--output"&&std::string(argv[4])=="--","logical_arguments");
    const std::string child=argv[5];need(child!="observe"&&child!="observe-model","logical_nested_command");
    need(!http::active(),"logical_session_active");
    const auto out=io::path(argv[3]);io::new_directory(out);
    io::new_directory(out/"calls");io::new_directory(out/"links");io::new_directory(out/"http");
    io::new_directory(out/"http"/"attempts");
    io::write_new(out/"started.json",Json{{"schema","qbrain-model-observation-start-v1"},
      {"private_content_recorded",false},{"abrupt_exit_is_unknown",true},{"all_model_calls_observed",false}}.dump()+"\n");
    auto collector=std::make_shared<Collector>([out](const Event& e){
      io::write_new(out/"calls"/(std::to_string(e.sequence)+(e.state==Return::pending?".start.json":".finish.json")),json(e).dump()+"\n");
    },[out](const Link& l){io::write_new(out/"links"/(std::to_string(l.http_sequence)+".json"),json(l).dump()+"\n");});
    std::vector<char*> args{argv[0]};for(int i=5;i<argc;++i)args.push_back(argv[i]);args.push_back(nullptr);
    std::optional<int> code;std::exception_ptr failure;std::shared_ptr<http::Collector> wire;
    {
      Session session(collector,[out](const http::Event& e){
        io::write_new(out/"http"/"attempts"/(std::to_string(e.sequence)+(e.complete?".finish.json":".start.json")),http::json(e).dump()+"\n");
      });wire=session.http_collector();
      try{code=invoke(int(args.size()-1),args.data());}catch(...){failure=std::current_exception();}
    }
    Json h=wire->report(true,code,bool(failure));Json l=collector->report(true,code,bool(failure));
    io::write_new(out/"http"/"report.json",h.dump()+"\n");io::write_new(out/"logical.json",l.dump()+"\n");
    Json checked=verify(l,h);io::write_new(out/"report.json",checked.dump()+"\n");
    if(failure){std::cerr<<"{\"error\":{\"code\":\"logical_command_exception\"}}\n";return 2;}
    if(!checked["recording_complete"].get<bool>()){std::cerr<<"{\"error\":{\"code\":\"logical_observation_incomplete\"}}\n";return 2;}
    return *code;
  }catch(const Error& e){std::cerr<<Json{{"error",{{"code",e.what()}}}}.dump()<<'\n';return 2;}
  catch(...){std::cerr<<"{\"error\":{\"code\":\"logical_observation_io_or_input_error\"}}\n";return 2;}
}
} // namespace qbrain::accounting::logical
