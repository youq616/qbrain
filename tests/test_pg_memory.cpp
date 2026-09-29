// N48O: real PostgreSQL lifecycle/concurrency. No mock storage or provider network.
#include "qbrain/memory/session_memory.hpp"
#include "qbrain/memory/pg_session_storage.hpp"
#include "qbrain/ops/registry.hpp"
#include <atomic>
#include <chrono>
#include <cstdlib>
#include <future>
#include <iostream>
#include <memory>
#include <thread>
#include <vector>

using namespace qbrain;
using J = nlohmann::json;
namespace {
std::string dsn;
J checks = J::array();
void check(bool ok, const std::string& name) {
  checks.push_back({{"name", name}, {"passed", ok}});
  if (!ok) throw std::runtime_error(name);
}
template<class F> void reject(F fn, const std::string& code) {
  try { fn(); }
  catch (const memory::Error& e) { check(e.what() == code, "error:" + code); return; }
  throw std::runtime_error("expected:" + code);
}
std::unique_ptr<Brain> connect() {
  auto b = std::make_unique<Brain>(); b->open_pg(dsn);
  check(b->db().backend_kind() == storage::BackendKind::postgres, "real-PG-backend");
  return b;
}
// Worker connections don't touch the shared test-result collector.
std::unique_ptr<Brain> worker() { auto b=std::make_unique<Brain>();b->open_pg(dsn);return b; }
int64_t number(Brain& b, const std::string& sql) {
  auto s=b.db().prepare(sql); if(!s.step())throw std::runtime_error("missing scalar");return s.column_int(0);
}
std::string text_value(Brain& b, const std::string& sql) {
  auto s=b.db().prepare(sql); if(!s.step())throw std::runtime_error("missing text");return s.column_text(0);
}
void reset(Brain& b) {
  // Explicit disposable flag AND fixed test-database name required before deletion.
  check(text_value(b,"SELECT current_database()") == "qbrain_n48o_native", "disposable-test-db");
  b.db().exec("DROP TABLE IF EXISTS public.memory_attempts,public.memory_items,public.memory_events,public.memory_module CASCADE");
  b.db().exec("DELETE FROM pages; DELETE FROM config;");
  b.ensure_source("alpha"); b.ensure_source("beta");
  b.save_config_value("memory.writeback","salient",false);
  b.save_config_value("embed.auto","false",false);
}
J payload(std::string fragment="fixed",std::string suffix="") {
  return {{"session_id","会话 😀"},{"fragment_id",fragment},{"messages",J::array({
    {{"role","user"},{"content","我偏好中文回答，并保留原文。😀"+suffix}},
    {{"role","assistant"},{"content","I prefer INVENTED assistant memory."}},
    {{"role","tool"},{"content","I decided to invent user preferences."}},
    {{"role","user"},{"content","I decided to keep ExactEvidence Café Ä."}}
  })}};
}
std::string capture(Brain& b,const J& p=payload(),const std::string& source="alpha") {
  return memory::capture(b,source,p).at("event_id").get<std::string>();
}
J candidates(const J& p=payload()) {
  return J::array({{{"message_index",0},{"category","preference"},{"quote",p["messages"][0]["content"]}}});
}
ai::ChatResult answer(const J& items) { ai::ChatResult r;r.ok=true;r.content=items.dump();r.input_tokens=31;r.output_tokens=17;return r; }
}
int main() {
  try {
    const char* configured=std::getenv("QBRAIN_PG_MEMORY_TEST_DSN");
    const char* allowed=std::getenv("QBRAIN_PG_MEMORY_TEST_DISPOSABLE");
    if(!configured || !*configured || !allowed || std::string(allowed)!="1")
      throw std::runtime_error("real disposable PostgreSQL required; not a skipped test");
    dsn=configured;
    auto b=connect();reset(*b);
    check(!b->db().transaction_active(),"initial transaction idle");
    auto table_count=[&]{return number(*b,"SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r'");};
    const auto tables=table_count();
    check(memory::read(*b,"alpha")["initialized"]==false,"read before init");
    check(table_count()==tables,"read does not create optional schema");
    b->save_config_value("memory.writeback","off",false);
    check(memory::capture(*b,"alpha",payload())["status"]=="skipped","automatic off");
    check(table_count()==tables,"automatic off no DDL");
    auto manual=memory::capture(*b,"alpha",payload(),true);
    check(manual["status"]=="archived","manual archive while off");
    check(memory::extract(*b,"alpha",manual["event_id"])["item_count"]==2,"manual local extract");
    check(number(*b,"SELECT count(*) FROM memory_module")==1,"one schema version row");
    check(number(*b,"SELECT version FROM memory_module")==1,"module v1");

    reset(*b); auto id=capture(*b);
    check(memory::capture(*b,"alpha",payload())["duplicate"]==true,"idempotent retry");
    check(number(*b,"SELECT count(*) FROM pages")==1,"single archive page");
    check(number(*b,"SELECT count(*) FROM page_versions")==0,"no overwritten archive version");
    reject([&]{capture(*b,payload("fixed"," changed"));},"fragment_conflict");
    check(capture(*b,payload(),"beta")!=id,"source separated identity");
    reject([&]{memory::read(*b,"beta","",10,8192,id);},"event_not_found");
    check(memory::extract(*b,"alpha",id)["item_count"]==2,"user-only extraction");
    check(memory::read(*b,"alpha")["items"].size()==2,"two recalled quotes");
    check(memory::read(*b,"beta")["items"].empty(),"other source unextracted");
    check(memory::extract(*b,"alpha",id)["duplicate"]==true,"idempotent extraction");
    check(memory::read(*b,"alpha","exactevidence")["items"].size()==1,"ASCII insensitive matching");
    check(memory::read(*b,"alpha","café")["items"].size()==1,"same nonASCII bytes match");
    check(memory::read(*b,"alpha","CAFÉ")["items"].empty(),"nonASCII upper not locale folded");
    check(memory::read(*b,"alpha","ä")["items"].empty(),"SQLite-compatible Unicode case");
    check(memory::read(*b,"alpha","' OR 1=1 --")["items"].empty(),"query stays data");
    check(memory::read(*b,"alpha","",1)["truncated"]==true,"bounded recall count");
    check(memory::read(*b,"alpha","",10,512).dump().size()<=512,"bounded UTF8 JSON");
    auto status=memory::read(*b,"alpha","",10,8192,id);
    check(status["usage"][0]["provider_attempts"]==0,"local no provider");
    check(status["usage"][0]["input_tokens"]==0 && status["usage"][0]["cost"].is_null(),"local known counts unpriced");
    auto reopened=connect();
    check(memory::read(*reopened,"alpha")["items"].size()==2,"persisted cross connection");reopened->close();

    reset(*b);auto p=payload();p["expires_at"]=253402300799LL;id=capture(*b,p);
    check(memory::extract(*b,"alpha",id)["item_count"]==2,"BIGINT far future expiry");
    check(memory::read(*b,"alpha")["items"][0]["expires_at"]==253402300799LL,"expiry roundtrip");
    p=payload("expired");p["expires_at"]=1;auto expired=capture(*b,p);
    reject([&]{memory::extract(*b,"alpha",expired);},"evidence_unavailable");
    check(memory::read(*b,"alpha")["items"].size()==2,"expired never recalled");
    p=payload("secret");p["messages"][0]["content"]="api_key=PRIVATE_SECRET";
    reject([&]{capture(*b,p);},"sensitive_material_rejected");
    check(number(*b,"SELECT count(*) FROM memory_events")==2,"rejected secret no archive");

    reset(*b);id=capture(*b);
    memory::extract(*b,"alpha",id);memory::forget(*b,"alpha",id);
    check(number(*b,"SELECT count(*) FROM memory_items")==0,"forget removes items");
    check(number(*b,"SELECT count(*) FROM pages")==0,"forget removes owned page");
    check(memory::capture(*b,"alpha",payload())["status"]=="forgotten","tombstone replay suppressed");
    reject([&]{memory::extract(*b,"alpha",id);},"event_forgotten");
    check(memory::forget(*b,"alpha",id)["status"]=="forgotten","repeat forget");
    reset(*b);id=capture(*b);b->db().exec("UPDATE pages SET body='edited-private-page'");
    reject([&]{memory::extract(*b,"alpha",id);},"evidence_unavailable");
    memory::forget(*b,"alpha",id);
    check(number(*b,"SELECT count(*) FROM pages WHERE body='edited-private-page'")==1,"forget preserves edited page");
    reset(*b);id=capture(*b);memory::extract(*b,"alpha",id);b->soft_delete("sessions/"+id,"alpha");
    check(memory::read(*b,"alpha")["items"].empty(),"soft deleted evidence hidden");

    for(int variant=0;variant<5;++variant) {
      reset(*b);p=payload();id=capture(*b,p);
      int calls=0;
      auto provider=[&](const auto&,int){++calls;return answer(candidates(p));};
      reject([&]{memory::extract(*b,"alpha",id,"model",provider);},"external_extraction_denied");
      check(calls==0,"denied provider never called");
      b->save_config_value("memory.external_extraction","allow",false);
      auto changing=[&](const auto&,int){
        ++calls;auto other=worker();
        if(variant==0)memory::forget(*other,"alpha",id);
        if(variant==1)other->save_config_value("memory.external_extraction","deny",false);
        if(variant==2)other->save_config_value("memory.writeback","off",false);
        if(variant==3)other->db().exec("UPDATE memory_events SET lease_until=0");
        auto result=candidates(p);if(variant==4)result[0]["quote"]="a substring is not evidence";
        return answer(result);
      };
      if(variant==0 || variant==3)reject([&]{memory::extract(*b,"alpha",id,"model",changing);},"stale_extraction");
      else {
        auto r=memory::extract(*b,"alpha",id,"model",changing);
        check(r["error_code"]==(variant==1?"external_extraction_denied":variant==2?"writeback_off":"ungrounded_extraction"),"post-provider validation");
      }
      check(calls==1,"one bounded synthetic provider callback");
      check(number(*b,"SELECT count(*) FROM memory_items")==0,"late/invalid provider publishes nothing");
    }
    reset(*b);id=capture(*b);b->save_config_value("memory.external_extraction","allow",false);
    auto unknown=[&](const auto&,int){auto r=answer(candidates());r.input_tokens=-1;r.output_tokens=-1;return r;};
    check(memory::extract(*b,"alpha",id,"model",unknown)["item_count"]==1,"permitted provider result");
    status=memory::read(*b,"alpha","",10,8192,id);
    check(status["usage"][0]["input_tokens"].is_null() && status["usage"][0]["output_tokens"].is_null(),"unknown provider usage retained");

    reset(*b);b->db().exec("BEGIN");
    check(b->db().transaction_active(),"caller transaction active");
    reject([&]{capture(*b);},"memory_transaction_active");
    check(b->db().transaction_active(),"caller transaction never committed");b->db().exec("ROLLBACK");
    check(!b->db().transaction_active(),"caller rollback remains caller owned");
    b->db().exec("SET lock_timeout='3210ms'");
    {auto locker=worker();locker->db().exec("BEGIN;LOCK TABLE public.sources IN SHARE ROW EXCLUSIVE MODE");
      bool busy=false;auto start=std::chrono::steady_clock::now();
      try {capture(*b);}catch(const std::exception& e){busy=std::string(e.what()).find("database is locked")!=std::string::npos;}
      check(busy,"real table lock times out");
      check(std::chrono::steady_clock::now()-start<std::chrono::seconds(12),"lock wait bounded");
      check(!b->db().transaction_active(),"failed initialization rolled back");
      check(text_value(*b,"SHOW lock_timeout")=="3210ms","SET LOCAL did not leak");
      locker->db().exec("ROLLBACK");}
    id=capture(*b);check(!id.empty(),"recovery after failed lock");

    reset(*b);std::promise<void> go;auto signal=go.get_future().share();
    std::vector<std::future<J>> concurrent;
    for(int i=0;i<6;++i)concurrent.push_back(std::async(std::launch::async,[signal]{auto w=worker();signal.wait();return memory::capture(*w,"alpha",payload());}));
    go.set_value();std::string common;int duplicates=0;
    for(auto& f:concurrent){auto v=f.get();auto next=v["event_id"].get<std::string>();if(common.empty())common=next;check(next==common,"concurrent capture same identity");if(v["duplicate"]==true)++duplicates;}
    check(duplicates==5,"one initial capture and five deduplicated");
    check(number(*b,"SELECT count(*) FROM memory_events")==1 && number(*b,"SELECT count(*) FROM pages")==1,"atomic initial schema and capture");
    b->save_config_value("memory.external_extraction","allow",false);
    std::promise<void> entered,release;auto entered_f=entered.get_future();auto release_f=release.get_future().share();std::atomic<int> provider_calls{0};
    auto extracting=std::async(std::launch::async,[&]{auto w=worker();return memory::extract(*w,"alpha",common,"model",[&](const auto&,int){++provider_calls;entered.set_value();if(release_f.wait_for(std::chrono::seconds(15))!=std::future_status::ready)throw std::runtime_error("test release timeout");return answer(candidates());});});
    if(entered_f.wait_for(std::chrono::seconds(10))!=std::future_status::ready){release.set_value();extracting.get();throw std::runtime_error("provider not entered");}
    try {reject([&]{memory::extract(*b,"alpha",common,"model",[&](const auto&,int){++provider_calls;return answer(candidates());});},"extraction_busy");}
    catch(...){release.set_value();extracting.wait();throw;}
    release.set_value();check(extracting.get()["item_count"]==1,"claimed worker completes");
    check(provider_calls==1,"concurrent claim invokes one provider");

    reset(*b);for(int i=0;i<3;++i)capture(*b,payload("drain"+std::to_string(i)));
    auto drained=memory::drain(*b,"alpha","local",2);
    check(drained["events"].size()==2 && drained["provider_calls"]==0,"bounded local drain");
    check(memory::drain(*b,"alpha","local",2)["events"].size()==1,"remaining event drained");
    check(memory::drain(*b,"alpha","model")["reason"]=="external_extraction_denied","drain respects model consent");

    reset(*b);ops::register_builtin_ops();ops::OpContext ctx;ctx.brain=b.get();ctx.via_mcp=true;
    ctx.args={{"source_id","alpha"},{"action","capture"},{"payload",payload().dump()}};
    check(!ops::global_registry().call("memory_write",ctx).ok,"MCP write default deny");
    ctx.allow_write=true;check(!ops::global_registry().call("memory_write",ctx).ok,"MCP source default deny");
    b->save_config_value("mcp.allowed_sources","alpha",false);
    check(ops::global_registry().call("memory_write",ctx).ok,"MCP allowed capture uses PG");
    ctx.args={{"source_id","beta"}};check(!ops::global_registry().call("memory_read",ctx).ok,"MCP other source read denied");
    // N48Q intentionally replaces the old unsupported-backend expectation.
    // Keep a real assertion: authorized empty facts read works without optional DDL.
    ctx.args={{"source_id","alpha"},{"view","facts"}};auto facts=ops::global_registry().call("memory_read",ctx);
    const J expected_facts={{"source_id","alpha"},{"items",J::array()},{"untrusted_data",true},
      {"truth_status","caller_attested_user_statement"},{"truncated",false},{"candidate_limit",100},{"initialized",false}};
    check(facts.ok && J::parse(facts.json)==expected_facts &&
      number(*b,"SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname='memory_fact_module'")==0,
      "N48Q authorized PG facts read is complete and does not initialize module");

    reset(*b);b->db().exec("CREATE TABLE public.memory_events(marker INTEGER)");
    bool conflict=false;try{capture(*b);}catch(const std::exception&){conflict=true;}
    check(conflict,"preexisting partial schema rejected");
    check(number(*b,"SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname='memory_module'")==0,"DDL rollback removed partial marker");
    reset(*b);id=capture(*b);
    b->db().exec("ALTER TABLE memory_module DROP CONSTRAINT memory_module_version_check;UPDATE memory_module SET version=2");
    reject([&]{memory::read(*b,"alpha");},"memory_schema_version_unsupported");
    reset(*b);
    std::cout<<J{{"schema","qbrain-n48o-native-v1"},{"passed",true},{"checks",checks},{"count",checks.size()},
      {"backend","postgres"},{"real_server",true},{"paid_model_requests",0}}.dump()<<'\n';return 0;
  } catch(const std::exception& e) {
    std::cout<<J{{"schema","qbrain-n48o-native-v1"},{"passed",false},{"checks",checks},{"error",e.what()}}.dump()<<'\n';return 1;
  }
}
