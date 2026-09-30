// PR65 P2: independent expectations, not imports from the original test fixtures.
#include "qbrain/accounting/observation_command.hpp"
#include <iostream>
#include <stdexcept>

using J=nlohmann::json;
namespace obs=qbrain::accounting::observation;
namespace {
J checks=J::array();
void check(bool ok,const char* name){checks.push_back({{"name",name},{"passed",ok}});if(!ok)throw std::runtime_error(name);}
void refuses(const J& r){bool rejected=false;try{obs::validate_report(r);}catch(const std::exception&){rejected=true;}check(rejected,"forged report semantics refused");}
J response(const char* status,int error){
 J j={{"object","response"},{"status",status},{"usage",{{"input_tokens",10},{"output_tokens",2},{"total_tokens",12},
  {"input_tokens_details",{{"cached_tokens",2},{"cache_write_tokens",1}}}}},
  {"model","PRIVATE_MODEL_SENTINEL"},{"output_text","PRIVATE_REPLY_SENTINEL"}};
 if(error==1)j["error"]=nullptr;
 if(error==2)j["error"]={{"message","PRIVATE_ERROR_SENTINEL"},{"code","PRIVATE_KEY_SENTINEL"}};
 if(error==3)j["error"]=0;
 if(error==4)j["error"]=false;
 return j;
}
J record(const J& body){
 auto c=std::make_shared<obs::Collector>();
 {obs::Session session(c);obs::Attempt a("/responses");a.finish({200,body.dump(),{},qbrain::ai::HttpFailure::none},true);}
 return c->report(true,0);
}
J assignments(){return {{"schema","qbrain-observation-rates-v1"},{"currency","USD"},
 {"rates",J::array({{{"rate_id","synthetic"},{"provider","synthetic"},{"model","synthetic"},
 {"per_million",{{"input_uncached","1"},{"input_cache_read","2"},{"input_cache_write","3"},{"output","4"}}}}})},
 {"assignments",J::array({{{"sequence",1},{"call_id","c1"},{"attempt",1},{"stage","main"},{"rate_id","synthetic"}}})}};}
void provider_matrix(){
 for(const char* status:{"completed","cancelled","incomplete","failed","queued","in_progress","unexpected"}){
  const std::string s=status;const bool terminal=s=="completed"||s=="cancelled"||s=="incomplete"||s=="failed";
  for(int error=0;error<5;++error){
   const J r=record(response(status,error));const auto& u=r["records"][0]["usage"];
   const std::string expected=s=="queued"||s=="in_progress"?"pending":s=="unexpected"?"unknown":s;
   check(u["provider_state"]==expected,"explicit status retained despite separate error field");
   check(u["provider_error_present"].is_boolean()&&u["provider_error_present"]==bool(error>=2),"nullable Boolean presence never error text");
   check(u["provider_status_conflict"]==(s=="completed"&&error>=2),"only explicitly completed plus nonnull error marked conflict");
   check(obs::validate_report(r).size()==1,"roundtrip exact record and report");
   check(r.dump().find("PRIVATE_")==std::string::npos,"no model reply key or error text in sidecar");
   auto cost=obs::price(r,assignments());
   check(cost["observed_record_cost"]["calls"][0]["outcome"]==((s=="failed"||s=="cancelled")?"failure":"unknown"),"cost outcome not inferred from contradictory error envelope");
   check(cost["application_success_verified"]==false&&cost["process_exit"].is_null()&&cost["stdout_complete"].is_null(),"cost estimate not process or output completion evidence");
   check(cost.dump().find("PRIVATE_")==std::string::npos,"cost does not copy private error contents");
   if(terminal){
    check(u["tokens"]==J{{"input_uncached",7},{"input_cache_read",2},{"input_cache_write",1},{"output",2}},"valid explicitly terminal reported quantities preserved");
    check(cost["total_estimate"]=="0.000022000000","terminal estimate reuses exact pricing without declaring success");
   }else{
    check(u["tokens"]==J{{"input_uncached",nullptr},{"input_cache_read",nullptr},{"input_cache_write",nullptr},{"output",nullptr}},"f7 guard: pending and unknown error do not create final usage");
    check(cost["total_estimate"].is_null(),"nonterminal total remains unknown");
   }
  }
 }
 // Independently parsed status/error survives an invalid or absent usage member.
 for(auto status:{"completed","cancelled","incomplete","failed"}){
  for(bool missing:{true,false}){
   J body=response(status,2);if(missing)body.erase("usage");else body["usage"]["input_tokens"]=true;
   J r=record(body);const auto& u=r["records"][0]["usage"];
   check(u["provider_state"]==status&&u["provider_error_present"]==true,"invalid or missing usage cannot erase known status/error");
   check(u["provider_status_conflict"]==(std::string(status)=="completed"),"conflict retained when quantities unavailable");
   check(u["state"]==(missing?"unavailable":"invalid")&&u["input_inclusive"].is_null(),"bad usage remains unknown not partially priced");
   obs::validate_report(r);check(obs::price(r,assignments())["total_estimate"].is_null(),"bad usage never free");
  }
 }
}
void report_semantics(){
 auto c=std::make_shared<obs::Collector>();
 auto preview=c->report();check(preview["dispatch_state"]=="not_observed"&&preview["dispatch_return"].is_null(),"unknown dispatch not invented zero");
 auto frozen=c->report(true,7);
 check(frozen["dispatch_state"]=="returned"&&frozen["dispatch_return"]==7,"dispatch return explicitly typed and scoped");
 check(frozen["recording_complete"]==true&&frozen["completion_scope"]=="http_attempt_records_only","HTTP completeness does not imply command success");
 check(frozen["process_exit"].is_null()&&frozen["stdout_complete"].is_null()&&frozen["stderr_complete"].is_null()&&!frozen.contains("command_exit"),"no fabricated final process or output completion");
 check(c->report(true,8,true)==frozen&&c->report()==frozen,"first sealing preserves dispatch metadata after later calls");
 obs::validate_report(frozen);
 auto failed=std::make_shared<obs::Collector>()->report(true,std::nullopt,true);
 check(failed["dispatch_state"]=="exception"&&failed["dispatch_return"].is_null(),"throw not invented returned2");
 obs::validate_report(failed);
 for(int which=0;which<12;++which){auto bad=frozen;
  if(which==0)bad["process_exit"]=0;if(which==1)bad["stdout_complete"]=true;if(which==2)bad["stderr_complete"]=false;
  if(which==3)bad["command_exit"]=0;if(which==4)bad["dispatch_return"]=false;if(which==5)bad["dispatch_return"]=nullptr;
  if(which==6)bad["dispatch_state"]="exception";if(which==7)bad["dispatch_state"]="not_observed";
  if(which==8)bad["dispatch_return"]=2147483648LL;if(which==9)bad["completion_scope"]="entire_process";
  if(which==10)bad["schema"]="qbrain-runtime-observation-v1";if(which==11)bad["dispatch_state"]="success";
  refuses(bad);
 }
 auto complete=record(response("completed",2));
 for(int which=0;which<6;++which){auto bad=complete;auto& u=bad["records"][0]["usage"];
  if(which==0)u["provider_error_present"]=1;if(which==1)u["provider_error_present"]=nullptr;
  if(which==2)u["provider_status_conflict"]=false;if(which==3)u["provider_status_conflict"]=1;
  if(which==4)u["provider_error_present"]="PRIVATE_ERROR_SENTINEL";if(which==5)u["error_message"]="PRIVATE_ERROR_SENTINEL";
  refuses(bad);
 }
 auto cancelled=record(response("cancelled",2));cancelled["records"][0]["usage"]["provider_status_conflict"]=true;refuses(cancelled);
 auto no_error=record(response("completed",0));no_error["records"][0]["usage"]["provider_status_conflict"]=true;refuses(no_error);
}
}
int main(int argc,char** argv){
 // Actual existing HTTP transport, numeric-loopback-only test driver.
 if(argc==4&&std::string(argv[1])=="--wire"){
  const std::string url=argv[2],prefix="http://127.0.0.1:";
  if(!url.starts_with(prefix))return 2;
  const auto port=url.substr(prefix.size());
  if(port.empty()||port.size()>5||port.find_first_not_of("0123456789")!=std::string::npos||std::stoi(port)<1024||std::stoi(port)>65535)return 2;
  std::vector<std::string> words={argv[0],"observe","--output",argv[3],"--","fixture"};std::vector<char*> args;
  for(auto& w:words)args.push_back(w.data());args.push_back(nullptr);
  return obs::command(int(words.size()),args.data(),[&](int,char**){
   for(auto status:{"completed","cancelled","incomplete","failed","queued","in_progress","unexpected"}){
    const auto r=qbrain::ai::http_post_json(url,"/responses","PRIVATE_KEY_SENTINEL",
      J{{"fixture",status},{"prompt","PRIVATE_PROMPT_SENTINEL"}}.dump(),2000,8192);
    if(r.failure!=qbrain::ai::HttpFailure::none||r.status!=200)throw std::runtime_error("wire fixture failed");
   }
   return 0;
  });
 }
 // Subprocess fixture: wrapper catches the exception without recording private text.
 if(argc==3&&std::string(argv[1])=="--throw"){
  std::vector<std::string> words={argv[0],"observe","--output",argv[2],"--","fixture"};std::vector<char*> args;
  for(auto& w:words)args.push_back(w.data());args.push_back(nullptr);
  return obs::command(int(words.size()),args.data(),[](int,char**)->int{throw std::runtime_error("PRIVATE_DISPATCH_EXCEPTION");});
 }
 try{provider_matrix();report_semantics();std::cout<<J{{"schema","qbrain-observation-semantics-tests-v1"},{"passed",true},{"checks",checks},{"check_count",checks.size()},{"paid_provider_calls",0}}.dump()<<'\n';return 0;}
 catch(const std::exception& e){std::cout<<J{{"passed",false},{"checks",checks},{"failure",e.what()}}.dump()<<'\n';return 1;}
}
