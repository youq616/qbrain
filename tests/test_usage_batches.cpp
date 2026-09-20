#include "qbrain/memory/fact_usage_batch.hpp"
#include "qbrain/ops/registry.hpp"
#include <iostream>
#include <stdexcept>

namespace {
using namespace qbrain;
using J=nlohmann::json;
int checks=0;
void check(bool ok,const char* name){if(!ok)throw std::runtime_error(name);++checks;}
template<class F> void denied(F f,const char* code){
  try{f();}catch(const memory::Error& e){check(std::string(e.what())==code,"exact rejection code");return;}
  throw std::runtime_error("expected typed rejection");
}
int64_t scalar(Brain& b,const char* q){auto s=b.db().prepare(q);if(!s.step())throw std::runtime_error("scalar missing");return s.column_int(0);}
}
int main(){
 try{
  Brain b;b.open_at(":memory:");b.ensure_source("alpha");b.save_config_value("memory.writeback","salient");
  const auto ev=memory::capture(b,"alpha",{{"session_id","batch-core"},{"fragment_id","one"},
      {"messages",J::array({{{"role","user"},{"content","I prefer batch transaction safety."}}})}},true);
  memory::extract(b,"alpha",ev["event_id"]);
  std::string id;
  {auto q=b.db().prepare("SELECT item_id FROM memory_items WHERE event_id=?");q.bind_text(1,ev["event_id"].get<std::string>());check(q.step(),"public extraction made evidence");id=q.column_text(0);}
  const auto fact=memory::FactStore(b,"alpha").create({{"predicate","test.preference"},{"item_id",id}});
  J req={{"operation","report"},{"items",J::array({{{"fact_id",fact["fact_id"]},{"usage_id",std::string(64,'1')},{"expected_revision",fact["revision"]}}})}};
  const auto original_timeout=scalar(b,"PRAGMA busy_timeout");
  const auto preview=memory::usage_batch(b,"alpha",req);
  check(!preview["applied"].get<bool>() && preview["would_change"]==1,"direct preview no write");
  check(scalar(b,"SELECT COUNT(*) FROM sqlite_master WHERE name='memory_fact_usage'")==0,"preview has no module");
  J apply=req;apply["snapshot"]=preview["snapshot"];
  b.db().exec("BEGIN; INSERT INTO config(key,value) VALUES('batch.owner','untouched')");
  const auto before=sqlite3_total_changes(b.db().handle());
  check(memory::usage_batch(b,"alpha",req)==preview,"preview allowed in caller transaction");
  check(sqlite3_get_autocommit(b.db().handle())==0 && sqlite3_total_changes(b.db().handle())==before,"preview preserves owner transaction");
  denied([&]{memory::usage_batch(b,"alpha",apply,true);},"fact_transaction_active");
  check(sqlite3_get_autocommit(b.db().handle())==0 && scalar(b,"SELECT COUNT(*) FROM config WHERE key='batch.owner'")==1,"rejected nested apply leaves caller changes intact");
  check(scalar(b,"SELECT COUNT(*) FROM sqlite_master WHERE name='memory_fact_usage'")==0,"nested apply rejects before module initialization");
  b.db().exec("ROLLBACK");
  b.db().exec("PRAGMA foreign_keys=OFF");
  denied([&]{memory::usage_batch(b,"alpha",apply,true);},"fact_foreign_keys_required");
  check(scalar(b,"SELECT COUNT(*) FROM sqlite_master WHERE name='memory_fact_usage'")==0,"foreign key failure leaves module absent");
  b.db().exec("PRAGMA foreign_keys=ON");
  auto result=memory::usage_batch(b,"alpha",apply,true);
  check(result["changed"]==1 && scalar(b,"SELECT COUNT(*) FROM memory_fact_usage")==1,"apply works after boundary failures");
  const auto current=memory::usage_batch(b,"alpha",req);apply["snapshot"]=current["snapshot"];
  b.db().exec("BEGIN");
  denied([&]{memory::usage_batch(b,"alpha",apply,true);},"fact_transaction_active");
  check(sqlite3_get_autocommit(b.db().handle())==0,"no-op cannot commit owner transaction");b.db().exec("ROLLBACK");
  check(memory::usage_batch(b,"alpha",apply,true)["changed"]==0,"no-op under own transaction is safe");
  denied([&]{memory::usage_batch(b,"beta",req);},"invalid_source");
  J revoke={{"operation","revoke"},{"items",J::array({{{"fact_id",fact["fact_id"]},{"usage_id",std::string(64,'1')}}})}};
  auto revplan=memory::usage_batch(b,"alpha",revoke);revoke["snapshot"]=revplan["snapshot"];
  check(memory::usage_batch(b,"alpha",revoke,true)["changed"]==1,"direct revoke works");
  denied([&]{memory::usage_batch(b,"alpha",req);},"fact_usage_withdrawn");
  check(scalar(b,"PRAGMA busy_timeout")==original_timeout,"operation restores caller busy timeout");
  std::cout<<J({{"result","PASS"},{"checks",checks},{"suite","n47z-transaction-boundary"}}).dump()<<"\n";return 0;
 }catch(const std::exception& e){std::cerr<<"FAIL after "<<checks<<": "<<e.what()<<"\n";return 1;}
}
