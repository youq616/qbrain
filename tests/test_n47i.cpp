#include "qbrain/util/strict_json.hpp"
#include "qbrain/memory/fact_store.hpp"
#include "qbrain/mcp/server.hpp"
#include "qbrain/ops/registry.hpp"
#include <fstream>
#include <iostream>
#include <memory>

namespace {
using namespace qbrain;
using J=nlohmann::json;
int checks=0;J scenarios=J::array();
void check(bool ok,const char* label){if(!ok)throw std::runtime_error(label);++checks;}
template<class F>void scenario(const char* name,F f){int before=checks;f();scenarios.push_back({{"name",name},{"status","PASS"},{"assertions",checks-before}});}
J parse(const std::string& s,int depth=8,std::size_t bytes=262144){return util::parse_unique_json(s,bytes,depth);}
void rejects(const std::string& s,util::JsonInputFailure failure,int depth=8,std::size_t bytes=262144){
 try{parse(s,depth,bytes);}catch(const util::JsonInputError& e){check(e.failure()==failure,"specific parser boundary");check(std::string(e.what())=="json_input_rejected","fixed private diagnostic");return;}
 throw std::runtime_error("ambiguous input accepted");
}
std::unique_ptr<Brain> fresh(){auto b=std::make_unique<Brain>();b->open_at(":memory:");b->ensure_source("alpha");b->ensure_source("beta");b->save_config_value("memory.writeback","all");return b;}
J invoke(Brain& b,const std::string& action,const std::string& raw,bool write=true){
 ops::OpContext c;c.brain=&b;c.args={{"source_id","alpha"},{write?"action":"view",action},{"payload",raw}};
 if(action=="capture")c.args["manual"]="true";
 return J::parse(ops::global_registry().call(write?"memory_write":"memory_read",c).json);
}
int64_t scalar(Brain& b,const std::string& sql){auto s=b.db().prepare(sql);check(s.step(),"scalar present");return s.column_int(0);}
std::string seed(Brain& b){
 auto e=memory::capture(b,"alpha",{{"session_id","seed"},{"fragment_id","one"},{"messages",J::array({{{"role","user"},{"content","我偏好完整原话，不改变证据。"}}})}},true);
 memory::extract(b,"alpha",e["event_id"]);auto s=b.db().prepare("SELECT item_id FROM memory_items WHERE event_id=?");s.bind_text(1,e["event_id"].get<std::string>());check(s.step(),"real extracted seed");return s.column_text(0);
}
void parser_tests(){
 scenario("unique inputs preserve Unicode values and sibling object scopes",[]{
  for(const std::string raw:{R"({"messages":[{"role":"user","content":"中文😀"},{"role":"assistant","content":"ok"}]})",R"({"a":{"id":1},"b":{"id":2}})",R"([{},[{"key":1},{"key":2}],{}])",R"({"x":"{\"id\":1,\"id\":2}","y":null})",R"({"A":1,"a":2,"é":3,"e\u0301":4})",R"({"a\u0000b":1,"a":2})"})
   check(parse(raw)==J::parse(raw),"unique JSON has exactly original meaning");
  check(parse("\xEF\xBB\xBF{\"a\":1}")["a"]==1,"existing UTF8 BOM supported");
 });
 scenario("duplicates rejected per object including decoded escaped keys",[]{
  for(const std::string raw:{R"({"a":1,"a":2})",R"({"a":1,"a":1})",R"({"x":{"id":1,"id":2}})",R"([{"a":1,"\u0061":2}])",R"({"😀":1,"\ud83d\ude00":2})",R"({"a\u0000b":1,"a\u0000b":2})",R"({"outer":[{},[{"z":0,"z":1}]]})"})
   rejects(raw,util::JsonInputFailure::duplicate_key);
 });
 scenario("byte limit exact boundary and raw NUL cannot terminate parsing",[]{
  const std::string raw=R"({"a":"😀"})";
  check(parse(raw,8,raw.size())["a"]=="😀","exact UTF8 byte budget");
  rejects(raw,util::JsonInputFailure::byte_limit,8,raw.size()-1);
  for(auto v:{std::string("{}\0{}",5),std::string("{\0}",3),std::string("{}\0",3)})rejects(v,util::JsonInputFailure::raw_nul);
  check(parse(R"({"a":"\u0000"})")["a"].get<std::string>().size()==1,"escaped NUL not confused with raw NUL");
 });
 scenario("depth limit covers arrays objects keys and values without discarding",[]{
  for(int depth:{1,8,32}){
   auto raw=std::string(depth,'[')+"0"+std::string(depth,']');check(parse(raw,depth).is_array(),"exact array event depth permitted");
   rejects("["+raw+"]",util::JsonInputFailure::depth_limit,depth);
   raw="0";for(int n=0;n<depth;++n)raw="{\"k\":"+raw+"}";
   check(parse(raw,depth).is_object(),"exact object event depth permitted");rejects("{\"k\":"+raw+"}",util::JsonInputFailure::depth_limit,depth);
  }
 });
 scenario("malformed syntax UTF8 surrogate and trailing documents never succeed",[]{
  for(const std::string raw:std::vector<std::string>{"", "{", "{}{}", "{\"a\":1,}", "[NaN]", "[Infinity]", R"({"a":"\ud800"})",std::string("{\"a\":\"\xff\"}")}){
   bool rejected=false;try{parse(raw);}catch(const std::exception&){rejected=true;}check(rejected,"invalid JSON rejected");
  }
 });
}
void memory_tests(){
 scenario("ambiguous capture rejected before optional schema or events exist",[]{
  auto b=fresh();const auto tables=scalar(*b,"SELECT COUNT(*) FROM sqlite_master");const auto changes=sqlite3_total_changes(b->db().handle());
  for(const std::string raw:{R"({"session_id":"one","session_id":"two","fragment_id":"f","messages":[{"role":"user","content":"I prefer a."}]})",R"({"session_id":"s","fragment_id":"f","messages":[{"role":"assistant","role":"user","content":"I prefer a."}]})",R"({"session_id":"s","fragment_id":"f","messages":[{"role":"user","content":"old","\u0063ontent":"I prefer a."}]})"}){
   auto r=invoke(*b,"capture",raw);check(r["error"]["code"]=="memory_duplicate_key","capture stable duplicate error");
  }
  check(sqlite3_total_changes(b->db().handle())==changes && scalar(*b,"SELECT COUNT(*) FROM sqlite_master")==tables,"invalid captures have no data or schema side effects");
 });
 scenario("single fact duplicate fields cannot create or retire a fact",[]{
  auto b=fresh();const auto item=seed(*b);const auto changes=sqlite3_total_changes(b->db().handle());
  auto raw="{\"predicate\":\"bad\",\"predicate\":\"memory.preference\",\"item_id\":\""+item+"\"}";
  check(invoke(*b,"fact_create",raw)["error"]["code"]=="fact_duplicate_key","fact create duplicate rejected");
  check(sqlite3_total_changes(b->db().handle())==changes && scalar(*b,"SELECT COUNT(*) FROM sqlite_master WHERE name='memory_facts'")==0,"rejection does not initialize fact module");
  auto f=invoke(*b,"fact_create",J({{"predicate","memory.preference"},{"item_id",item}}).dump());auto id=f["fact_id"].get<std::string>();
  for(const auto* action:{"fact_attach","fact_retract","fact_supersede","fact_contradict","fact_archive","fact_restore"}){
   auto p="{\"fact_id\":\""+id+"\",\"fact_id\":\""+id+"\",\"expected_revision\":1}";
   check(invoke(*b,action,p)["error"]["code"]=="fact_duplicate_key","all ordinary fact mutations share strict parser");
  }
  check(memory::FactStore(*b,"alpha").read(id)["items"][0]["revision"]==1,"no rejected write advances revision");
 });
 scenario("existing batch errors and valid siblings retain their contract",[]{
  auto b=fresh();const auto item=seed(*b);auto f=invoke(*b,"fact_create",J({{"predicate","memory.preference"},{"item_id",item}}).dump());
  auto raw="{\"operation\":\"restore\",\"operation\":\"archive\",\"items\":[{\"fact_id\":\""+f["fact_id"].get<std::string>()+"\",\"expected_revision\":1}]}";
  for(bool apply:{false,true})check(invoke(*b,apply?"fact_lifecycle_batch":"lifecycle_batch",raw,apply)["error"]["code"]=="fact_batch_duplicate_key","historical batch duplicate code retained");
  check(invoke(*b,"fact_create",std::string(16385,' '))["error"]["code"]=="fact_invalid_payload","fact payload size retained");
  check(invoke(*b,"capture",std::string(262145,' '))["error"]["code"]=="payload_too_large","capture byte limit retained");
  check(invoke(*b,"fact_create",std::string("{}\0{}",5))["error"]["code"]=="invalid_json","raw NUL stable syntax rejection");
 });
}
void rpc_tests(){
 auto error=[](const J& r){return r.contains("error") && r["error"]["code"]==-32700 && r["id"].is_null() && r["error"]["message"]=="parse error";};
 scenario("MCP duplicate envelope and nested arguments rejected before dispatch",[&]{
  auto b=fresh();mcp::ServeOptions opts;opts.allow_write=true;opts.tool_profile="memory";
  const auto changes=sqlite3_total_changes(b->db().handle());
  const std::vector<std::string> raws={R"({"jsonrpc":"2.0","id":1,"id":2,"method":"initialize"})",R"({"jsonrpc":"2.0","id":1,"method":"tools/list","method":"initialize"})",R"({"jsonrpc":"2.0","id":1,"method":"initialize","params":{},"params":{}})",R"({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"memory_read","arguments":{"source_id":"beta","source_id":"alpha"}}})",R"({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"memory_read","name":"memory_write","arguments":{}}})",R"({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"memory_write","arguments":{"action":"forget","\u0061ction":"capture"}}})"};
  for(const auto& raw:raws)check(error(J::parse(mcp::handle_rpc_body(*b,opts,raw))),"ambiguous request has null id fixed parse error");
  check(sqlite3_total_changes(b->db().handle())==changes,"MCP rejection cannot dispatch data mutation");
 });
 scenario("MCP notifications limits and invalid input fail before a valid next call",[&]{
  auto b=fresh();mcp::ServeOptions opts;opts.tool_profile="memory";
  for(auto raw:{std::string(R"({"jsonrpc":"2.0","method":"notifications/initialized","method":"tools/call"})"),std::string("{}\0{}",5),std::string(33,'[')+"0"+std::string(33,']'),std::string(16*1024*1024+1,' ')})
   check(error(J::parse(mcp::handle_rpc_body(*b,opts,raw))),"MCP bounded rejection and no ambiguous notification dispatch");
  auto valid=J::parse(mcp::handle_rpc_body(*b,opts,R"({"jsonrpc":"2.0","id":7,"method":"initialize","params":{"clientInfo":{"name":"fixture","version":"1"}}})"));
  check(valid["id"]==7 && valid.contains("result"),"valid request following rejections still works");
 });
 scenario("valid MCP permissions sources and memory tool registry unchanged",[]{
  auto b=fresh();mcp::ServeOptions opts;opts.tool_profile="memory";
  auto raw=[](const char* name,const J& args){return J({{"jsonrpc","2.0"},{"id",7},{"method","tools/call"},{"params",{{"name",name},{"arguments",args}}}}).dump();};
  auto r=mcp::handle_rpc_body(*b,opts,raw("memory_write",{{"action","capture"},{"payload","{}"}}));check(r.find("write_denied")!=std::string::npos,"default MCP write denied");
  r=mcp::handle_rpc_body(*b,opts,raw("memory_read",{{"source_id","beta"}}));check(r.find("source_not_allowed")!=std::string::npos,"source gate unchanged");
  auto listed=J::parse(mcp::handle_rpc_body(*b,opts,R"({"jsonrpc":"2.0","id":9,"method":"tools/list"})"));
  std::set<std::string> names;for(const auto& tool:listed["result"]["tools"])names.insert(tool["name"]);
  check(names==std::set<std::string>{"search","memory_read","memory_write","context_read","context_write","get_page"},"same six profile tools");
 });
}
} // namespace
void test_n47i(){checks=0;scenarios=J::array();ops::register_builtin_ops();parser_tests();memory_tests();rpc_tests();std::cout<<"N47I strict JSON: "<<scenarios.size()<<" scenarios, "<<checks<<" checks passed\n";}
#ifdef QBRAIN_STRICT_JSON_STANDALONE
int main(int argc,char**argv){
 if(argc==2 && std::string(argv[1])=="--parse-lines"){
  std::string line;while(std::getline(std::cin,line)){bool accepted=false;try{(void)parse(line,32,1048576);accepted=true;}catch(const std::exception&){}std::cout<<J({{"accepted",accepted}}).dump()<<'\n';}return 0;
 }
 try{test_n47i();if(argc==3 && std::string(argv[1])=="--report"){
  std::ofstream out(argv[2],std::ios::binary);if(!out)throw std::runtime_error("report open failed");out<<J({{"result","PASS"},{"scenarios",scenarios},{"scenario_count",scenarios.size()},{"checks",checks}}).dump(2)<<'\n';if(!out)throw std::runtime_error("report write failed");
 }else if(argc!=1)throw std::runtime_error("invalid args");return 0;}catch(const std::exception&e){std::cerr<<"[FAIL] N47I: "<<e.what()<<'\n';return 1;}
}
#endif
