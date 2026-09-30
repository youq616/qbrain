#include "qbrain/integration/detail/cursor_hook.hpp"
#include "qbrain/integration/detail/hook_trace.hpp"
#include <chrono>
#include <functional>
#include <iostream>
#include <vector>
using namespace qbrain::integration::detail;
using J=nlohmann::json;namespace fs=std::filesystem;
namespace {
J checks=J::array();
void check(bool ok,const char* name){checks.push_back({{"name",name},{"passed",ok}});if(!ok)throw std::runtime_error(name);}
void rejects(const std::function<void()>& f){bool refused=false;try{f();}catch(const std::exception&){refused=true;}check(refused,"invalid input refused");}
void run(const fs::path& root,const fs::path& other){
 auto raw=[&](std::string name){return J{{"hook_event_name",name},{"conversation_id","conversation-1"},{"generation_id","generation-1"},{"workspace_roots",J::array({qbrain::util::path_to_utf8(root)})},{"session_id","conversation-1"},{"is_background_agent",false},{"prompt","I prefer C++ 中文😀.\r\n"},{"text","Assistant-only claim"},{"model","PRIVATE_MODEL"},{"user_email","PRIVATE_EMAIL"},{"transcript_path","PRIVATE_NOT_OPENED"},{"attachments",J::array({{{"file_path","PRIVATE_NOT_OPENED"}}})}};};
 const std::vector<std::pair<std::string,std::string>> names={{"sessionStart","SessionStart"},{"beforeSubmitPrompt","UserPromptSubmit"},{"afterAgentResponse","Stop"},{"preCompact","PreCompact"},{"sessionEnd","SessionEnd"}};
 for(const auto& [wire,internal]:names){auto value=raw(wire);auto normalized=cursor::normalize(value,root,root);
  J expected={{"hook_event_name",internal},{"session_id","conversation-1"},{"cwd",qbrain::util::path_to_utf8(root)}};
  if(wire=="beforeSubmitPrompt"){expected["prompt"]=value["prompt"];expected["turn_id"]="generation-1";}
  if(wire=="afterAgentResponse"){expected["last_assistant_message"]="Assistant-only claim";expected["turn_id"]="generation-1";}
  check(normalized==expected,"exact event and role projection");
  check(normalized.dump().find("PRIVATE_")==std::string::npos,"irrelevant private fields omitted");
  check(cursor::noop(value)==(wire=="beforeSubmitPrompt"?J{{"continue",true}}:J::object()),"exact no-op response contract");
 }
 auto good=raw("beforeSubmitPrompt");
 for(int test=0;test<23;++test){auto v=good;
  if(test==0)v["conversation_id"]=nullptr;
  if(test==1)v["conversation_id"]="";
  if(test==2)v["conversation_id"]=std::string(129,'a');
  if(test==3)v["conversation_id"]=std::string("a\0b",3);
  if(test==4)v["session_id"]="different";
  if(test==5)v["session_id"]=2;
  if(test==6)v["generation_id"]="";
  if(test==7)v.erase("generation_id");
  if(test==8)v["prompt"]=false;
  if(test==9)v["prompt"]=std::string(131073,'x');
  if(test==10)v["prompt"]=std::string(1,char(0xff));
  if(test==11)v["prompt"]=std::string("a\0b",3);
  if(test==12)v["workspace_roots"]=J::array();
  if(test==13)v["workspace_roots"].push_back(qbrain::util::path_to_utf8(other));
  if(test==14)v["workspace_roots"][0]=42;
  if(test==15)v["workspace_roots"][0]="relative";
  if(test==16)v["workspace_roots"][0]=qbrain::util::path_to_utf8(other);
  if(test==17)v["cwd"]=qbrain::util::path_to_utf8(other);
  if(test==18)v["is_background_agent"]=true;
  if(test==19)v["is_background_agent"]=1;
  if(test==20)v["hook_event_name"]="SessionStart";
  if(test==21)v["hook_event_name"]="afterAgentThought";
  if(test==22)v["hook_event_name"]="stop";
  rejects([&]{cursor::normalize(v,root,root);});
 }
 rejects([&]{cursor::normalize(good,root,other);});
 for(const auto& event:{"sessionStart","sessionEnd"}){auto v=raw(event);v.erase("session_id");v.erase("generation_id");check(cursor::normalize(v,root,root)["session_id"]=="conversation-1","common conversation identity sufficient for lifecycle");}
 auto empty=good;empty["prompt"]="";check(cursor::normalize(empty,root,root)["prompt"]=="","empty prompt is no capture not parse failure");
 J envelope={{"hookSpecificOutput",{{"hookEventName","SessionStart"},{"additionalContext","Untrusted fixture"}}}};
 check(cursor::output(envelope)==J{{"additional_context","Untrusted fixture"}},"Cursor envelope not Claude envelope");
 check(cursor::output(J::object()).empty(),"no result does not manufacture context");
 envelope["hookSpecificOutput"]["hookEventName"]="UserPromptSubmit";rejects([&]{cursor::output(envelope);});
 J t={{"phase","complete"},{"recall_count",1},{"output_bytes",16},{"raw_prompt","PRIVATE_PROMPT"}};
 auto tr=hook_trace_record(t,"cursor","SessionStart",std::string(64,'a'),1,true);
 check(tr["host"]=="cursor" && tr["host_consumption_confirmed"]==false,"trace attribution without false host acceptance");
 check(tr.dump().find("PRIVATE_")==std::string::npos && !tr.contains("raw_prompt"),"trace fixed projection");
 check(hook_trace_filename("cursor","SessionStart")=="trace-cursor-SessionStart.json","fixed Cursor metadata destination");
}
}
int main(){fs::path root;bool own=false;try{
 root=fs::temp_directory_path()/std::string("qbrain-cursor-unit-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));own=fs::create_directory(root);if(!own)throw std::runtime_error("test root collision");fs::create_directory(root/"project");fs::create_directory(root/"other");run(root/"project",root/"other");
 fs::remove_all(root);own=false;std::cout<<J({{"schema","qbrain-n48y-unit-v1"},{"passed",true},{"checks",checks},{"check_count",checks.size()},{"real_cursor_session",false}}).dump()<<'\n';return 0;
}catch(const std::exception& e){if(own){std::error_code ec;fs::remove_all(root,ec);}std::cout<<J({{"passed",false},{"checks",checks},{"failure",e.what()}}).dump()<<'\n';return 1;}}
