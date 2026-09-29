// N48O completion: real-PG public-resolution/ownership regression.
// Uses public memory entry points, not pg_session helper internals or old fixtures.
#include "qbrain/memory/session_memory.hpp"
#include <cstdlib>
#include <functional>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

using namespace qbrain;
using J = nlohmann::json;
namespace {
J checks = J::array(), records = J::array();
void require(bool ok, const std::string& name) {
  checks.push_back({{"name",name},{"passed",ok}});
  if (!ok) throw std::runtime_error(name);
}
int64_t scalar(Brain& b, const std::string& sql) {
  auto s=b.db().prepare(sql);
  if (!s.step()) throw std::runtime_error("missing scalar");
  return s.column_int(0);
}
std::string text(Brain& b, const std::string& sql) {
  auto s=b.db().prepare(sql);
  if (!s.step()) throw std::runtime_error("missing text");
  return s.column_text(0);
}
J payload(const std::string& fragment) {
  return {{"session_id","scope-session"},{"fragment_id",fragment},
    {"messages",J::array({
      {{"role","user"},{"content","I prefer exact public-scope evidence."}},
      {{"role","assistant"},{"content","I prefer untrusted assistant suggestions."}},
      {{"role","user"},{"content","I decided to retain only my complete statement."}}
    })}};
}
void rejected(const std::function<void()>& fn, const std::string& label,
              const std::string& code="memory_pg_schema_context") {
  try { fn(); }
  catch (const memory::Error& e) {
    require(std::string(e.what())==code,label+":exact-error");
    return;
  }
  throw std::runtime_error(label+":unexpected acceptance");
}
void reset(Brain& b) {
  require(text(b,"SELECT current_database()") == "qbrain_n48o_native","disposable-db");
  require(scalar(b,"SELECT CASE WHEN rolsuper THEN 1 ELSE 0 END FROM pg_catalog.pg_roles "
                   "WHERE rolname=current_user")==0,"non-superuser");
  b.db().exec("DROP TABLE IF EXISTS public.memory_attempts,public.memory_items,"
             "public.memory_events,public.memory_module CASCADE");
  b.db().exec("DELETE FROM public.pages;DELETE FROM public.config");
  b.ensure_source("scope-alpha");b.ensure_source("scope-beta");
  b.save_config_value("memory.writeback","salient",false);
  b.save_config_value("embed.auto","false",false);
}
J state(Brain& b) {
  J out;
  for (const auto& entry:std::vector<std::pair<std::string,std::string>>{
       {"memory_module","version"},{"memory_events","event_id"},{"memory_items","item_id"},
       {"memory_attempts","attempt_id"},{"pages","id"},{"config","key"},{"sources","id"}}) {
    auto q=b.db().prepare("SELECT row_to_json(t)::text FROM (SELECT * FROM public."+
                          entry.first+" ORDER BY "+entry.second+") t");
    out[entry.first]=J::array();
    while(q.step()) out[entry.first].push_back(J::parse(q.column_text(0)));
  }
  return out;
}
J outcome(bool legacy) {
  return {{"schema","qbrain-n48o-scope-review-v1"},
    {"mode",legacy?"parent-characterization":"fixed-regression"},
    {"passed",true},{"real_server",true},{"paid_provider_requests",0},
    {"checks",checks},{"count",checks.size()},{"records",records}};
}
}
int main(int argc,char** argv) {
  bool legacy=false;
  try {
    if (argc==2 && std::string(argv[1])=="--characterize-parent") legacy=true;
    else if(argc!=1) throw std::runtime_error("unsupported argument");
    const char* dsn=std::getenv("QBRAIN_PG_MEMORY_TEST_DSN");
    const char* allow=std::getenv("QBRAIN_PG_MEMORY_TEST_DISPOSABLE");
    if(!dsn || !*dsn || !allow || std::string(allow)!="1")
      throw std::runtime_error("explicit disposable PG required; no skipped pass");
    Brain b;b.open_pg(dsn);
    require(b.db().backend_kind()==storage::BackendKind::postgres,"real-pg-backend");
    reset(b);
    if(legacy) {
      b.save_config_value("memory.writeback","off",false);
      b.db().exec("CREATE TEMP TABLE config AS SELECT * FROM public.config;"
                 "UPDATE pg_temp.config SET value='salient' WHERE key='memory.writeback'");
      require(text(b,"SELECT current_schema()") == "public","legacy-current-schema-public");
      auto r=memory::capture(b,"scope-alpha",payload("parent-policy"));
      require(r.at("status")=="archived","legacy-shadow-policy-accepted");
      require(scalar(b,"SELECT count(*) FROM public.memory_events")==1,"legacy-public-write-observed");
      require(text(b,"SELECT value FROM public.config WHERE key='memory.writeback'")=="off",
              "legacy-public-policy-still-off");
      records.push_back({{"case","temporary-policy-shadow"},{"observed",r},
                         {"public_policy","off"},{"temporary_policy","salient"}});
      b.db().exec("DROP TABLE pg_temp.config");
      reset(b);
      std::cout<<outcome(true).dump()<<'\n';
      return 0;
    }
    require(memory::read(b,"scope-alpha").at("initialized")==false,"fresh-no-optional-schema");
    b.db().exec("CREATE TEMP TABLE memory_events(event_id TEXT)");
    rejected([&]{memory::read(b,"scope-alpha");},"preinit-shadow");
    require(scalar(b,"SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n "
                     "ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname='memory_module'")==0,
            "preinit-no-ddl");
    b.db().exec("DROP TABLE pg_temp.memory_events;CREATE TEMP TABLE scope_control(v INTEGER)");
    require(memory::read(b,"scope-alpha").at("initialized")==false,"unrelated-temp-allowed");
    b.save_config_value("memory.writeback","off",false);
    require(memory::capture(b,"scope-alpha",payload("off")).at("status")=="skipped","public-off-respected");
    b.save_config_value("memory.writeback","salient",false);
    const auto id=memory::capture(b,"scope-alpha",payload("normal")).at("event_id").get<std::string>();
    require(memory::extract(b,"scope-alpha",id).at("item_count")==2,"whole-user-evidence");
    require(memory::read(b,"scope-beta").at("items").empty(),"scope-beta-isolation");
    for(const std::string table:{"sources","pages","config","memory_module","memory_events","memory_items","memory_attempts"}) {
      const auto before=state(b);
      b.db().exec("CREATE TEMP TABLE "+table+" AS SELECT * FROM public."+table);
      require(text(b,"SELECT current_schema()") == "public",table+":schema-alone-insufficient");
      int provider_calls=0;
      rejected([&]{memory::read(b,"scope-alpha");},table+":read");
      rejected([&]{memory::read(b,"scope-alpha","",10,8192,id);},table+":status");
      rejected([&]{memory::capture(b,"scope-alpha",payload("refused"));},table+":capture");
      rejected([&]{memory::capture(b,"scope-alpha",payload("manual"),true);},table+":manual");
      rejected([&]{memory::extract(b,"scope-alpha",id);},table+":extract");
      rejected([&]{memory::extract(b,"scope-alpha",id,"model",[&](const auto&,int) {
        ++provider_calls;return ai::ChatResult{};});},table+":model");
      rejected([&]{memory::drain(b,"scope-alpha");},table+":drain");
      rejected([&]{memory::forget(b,"scope-alpha",id);},table+":forget");
      require(provider_calls==0,table+":no-provider");
      require(!b.db().transaction_active(),table+":idle-on-refusal");
      const auto after=state(b);
      require(before==after,table+":public-state-identical");
      records.push_back({{"case",table},{"before",before},{"after",after}});
      b.db().exec("DROP TABLE pg_temp."+table);
    }
    // A same-named temp object is harmless when PUBLIC really resolves first.
    b.db().exec("CREATE TEMP TABLE config AS SELECT * FROM public.config;"
               "SET search_path=public,pg_temp");
    require(memory::read(b,"scope-alpha").at("items").size()==2,"effective-public-first-allowed");
    require(text(b,"SHOW search_path")=="public, pg_temp","caller-search-path-not-overwritten");
    b.db().exec("SET search_path=public;DROP TABLE pg_temp.config");
    b.save_config_value("memory.writeback","off",false);
    b.db().exec("CREATE TEMP TABLE config AS SELECT * FROM public.config;"
               "UPDATE pg_temp.config SET value='salient' WHERE key='memory.writeback'");
    const auto off_state=state(b);
    rejected([&]{memory::capture(b,"scope-alpha",payload("policy"));},"conflicting-temp-policy");
    require(state(b)==off_state,"off-policy-state-preserved");
    b.db().exec("DROP TABLE pg_temp.config");
    b.save_config_value("memory.writeback","salient",false);
    // The callback is synthetic; it alters this connection to test reacquisition.
    const auto later=memory::capture(b,"scope-alpha",payload("after-provider")).at("event_id").get<std::string>();
    b.save_config_value("memory.external_extraction","allow",false);
    int provider_calls=0;
    rejected([&]{memory::extract(b,"scope-alpha",later,"model",[&](const auto&,int) {
      ++provider_calls;
      require(!b.db().transaction_active(),"provider-outside-write-transaction");
      b.db().exec("CREATE TEMP TABLE config AS SELECT * FROM public.config");
      ai::ChatResult r;r.ok=true;
      r.content=J::array({{{"message_index",0},{"category","preference"},
        {"quote","I prefer exact public-scope evidence."}}}).dump();
      return r;
    });},"post-provider-context-recheck");
    require(provider_calls==1,"single-synthetic-callback");
    require(scalar(b,"SELECT count(*) FROM public.memory_items")==2,"no-late-items-published");
    require(!b.db().transaction_active(),"post-provider-idle");
    b.db().exec("DROP TABLE pg_temp.config");
    memory::forget(b,"scope-alpha",later);
    require(memory::capture(b,"scope-alpha",payload("after-provider")).at("status")=="forgotten",
            "post-provider-forget-wins");
    b.db().exec("BEGIN;INSERT INTO public.config(key,value) VALUES('caller-owned','uncommitted')");
    rejected([&]{memory::capture(b,"scope-alpha",payload("caller"));},"caller-transaction","memory_transaction_active");
    require(b.db().transaction_active(),"caller-still-active");
    b.db().exec("ROLLBACK");
    require(scalar(b,"SELECT count(*) FROM public.config WHERE key='caller-owned'")==0,"caller-rollback-retained");
    b.db().exec("BEGIN");
    try{b.db().exec("SELECT 1/0");}catch(const std::exception&){}
    rejected([&]{memory::read(b,"scope-alpha");},"failed-caller-transaction","memory_transaction_active");
    require(b.db().transaction_active(),"failed-transaction-not-committed");
    b.db().exec("ROLLBACK");
    require(memory::read(b,"scope-alpha").at("items").size()==2,"normal-recall-after-recovery");
    reset(b);
    std::cout<<outcome(false).dump()<<'\n';
    return 0;
  }catch(const std::exception& e) {
    std::cout<<J{{"schema","qbrain-n48o-scope-review-v1"},{"passed",false},
                 {"mode",legacy?"parent-characterization":"fixed-regression"},
                 {"checks",checks},{"records",records},{"error",e.what()}}.dump()<<'\n';
    return 1;
  }
}
