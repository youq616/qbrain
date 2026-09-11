#include "qbrain/context/context.hpp"
#include "qbrain/memory/session_memory.hpp"
#include "qbrain/mcp/server.hpp"
#include "qbrain/ops/registry.hpp"
#include <iostream>
#include <stdexcept>
namespace {
using namespace qbrain;using J=nlohmann::json;int checks;
void check(bool x,const char* m){if(!x)throw std::runtime_error(m);++checks;}
template<class F>void denied(F f){bool bad=false;try{f();}catch(...){bad=true;}check(bad,"expected rejection");}
void page(Brain& b,const std::string& src,const std::string& slug,const std::string& text){auto s=b.db().prepare("INSERT INTO pages(source_id,slug,title,body) VALUES(?,?,?,?)");s.bind_text(1,src);s.bind_text(2,slug);s.bind_text(3,slug);s.bind_text(4,text);s.step_done();}
}
void test_n45(){using namespace qbrain;checks=0;
 Brain b;b.open_at(":memory:");b.ensure_source("alpha");b.ensure_source("beta");
 page(b,"alpha","docs/a","Alpha 中文😀 original\r\n");page(b,"beta","docs/a","PRIVATE_BETA");
 const std::string uri="qbrain://alpha/resources/docs/";
 for(const auto& bad:{"qbrain://beta/resources/docs/","qbrain://alpha/resources/../","qbrain://alpha/resources/a%2fb/","qbrain://alpha/resources//","qbrain://alpha/nope/","qbrain://alpha/resources/a\\b/"})denied([&]{context::read(b,"alpha",bad);});
 check(context::read(b,"alpha",uri).dump().find("PRIVATE_BETA")==std::string::npos,"source separation");
 denied([&]{context::read(b,"alpha",uri,"L2");});denied([&]{context::read(b,"alpha",uri,"L1",511);});
 const auto raw=context::read(b,"alpha",uri+"a","L2");
 denied([&]{context::read(b,"alpha",uri+"a","L2",8192,1);});
 denied([&]{context::read(b,"alpha",uri+"a","L2",8192,7,raw["revision"]);}); // inside UTF-8 Chinese scalar
 check(context::read(b,"alpha",uri+"a","L2",8192,raw["content"].get<std::string>().size(),raw["revision"])["content"]=="","valid end cursor");
 int calls=0;
 auto provider=[&](const std::vector<ai::ChatMessage>& req,int timeout){++calls;check(timeout==30000,"bounded provider timeout");check(req.size()==2&&req.back().content.find("PRIVATE_BETA")==std::string::npos,"only scoped evidence leaves process");ai::ChatResult r;r.ok=true;r.content=R"({"l0":"Summary","l1":"Generated, not authoritative."})";r.input_tokens=22;r.output_tokens=9;return r;};
 denied([&]{context::summary(b,"alpha",uri,"model",provider);});check(calls==0,"no provider without consent");
 b.save_config_value("context.external_summary","allow");
 const auto generated=context::summary(b,"alpha",uri,"model",provider);
 check(calls==1&&generated["input_tokens"]==22&&generated["cost"].is_null(),"measured usage not fabricated cost");
 const auto cached=context::read(b,"alpha",uri,"L1");check(cached["method"]=="model"&&cached["cache_status"]=="fresh","generated cache tagged");
 auto mutate=[&](const auto& req,int timeout){auto r=provider(req,timeout);b.db().exec("UPDATE pages SET body='new evidence' WHERE source_id='alpha'");return r;};
 denied([&]{context::summary(b,"alpha",uri,"model",mutate);});
 check(context::read(b,"alpha",uri,"L1")["content"].get<std::string>().find("new evidence")!=std::string::npos,"late model output cannot override current evidence");
 auto revoke=[&](const auto& req,int timeout){auto r=provider(req,timeout);b.save_config_value("context.external_summary","deny");return r;};
 denied([&]{context::summary(b,"alpha",uri,"model",revoke);});
 b.save_config_value("context.external_summary","allow");
 auto invalid=[&](const auto&,int){ai::ChatResult r;r.ok=true;r.content=R"({"l0":"bad","l1":false})";return r;};
 denied([&]{context::summary(b,"alpha",uri,"model",invalid);});
 context::summary(b,"alpha",uri);
 b.db().exec("UPDATE pages SET source_id='beta',slug='docs/moved' WHERE source_id='alpha'");
 check(context::read(b,"alpha",uri,"L1")["content"]=="","source movement clears old source preview");
 denied([&]{context::read(b,"alpha",uri+"a","L2");});
 page(b,"alpha","docs/a","new page");context::summary(b,"alpha",uri);
 b.db().exec("DELETE FROM pages WHERE source_id='alpha'");check(context::read(b,"alpha",uri)["page_count"]==0,"hard deletion clears cache");
 ops::register_builtin_ops();b.save_config_value("mcp.allowed_sources","alpha");mcp::ServeOptions opts;opts.tool_profile="memory";
 auto call=[&](const J& args){return J::parse(mcp::handle_rpc_body(b,opts,J({{"jsonrpc","2.0"},{"id",1},{"method","tools/call"},{"params",{{"name","context_read"},{"arguments",args}}}}).dump()));};
 for(const auto& bad:J::array({true,1.5,"512",nullptr,-1}))check(call({{"source_id","alpha"},{"uri",uri},{"max_bytes",bad}})["result"]["isError"]==true,"strict MCP numeric types");
 check(call({{"source_id","alpha"},{"uri",uri},{"unexpected",1}})["result"]["isError"]==true,"MCP unknown keys rejected");
 check(call({{"source_id","alpha"},{"uri","qbrain://beta/resources/docs/"}})["result"]["isError"]==true,"URI cannot change authorized scope");
 check(memory::drain(b,"alpha","model")["reason"]=="external_extraction_denied","batch cannot self grant consent");
 std::cout<<"[N45] "<<checks<<" checks passed; provider fixtures, no live model.\n";
}
#ifdef QBRAIN_CONTEXT_STANDALONE
int main(){try{test_n45();return 0;}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
#endif
