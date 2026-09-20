// Independent outcome-review tests: a batch must never take the caller's transaction.
#include "qbrain/memory/fact_usage_batch.hpp"
#include <iostream>
#include <stdexcept>

namespace {
using namespace qbrain;
using J=nlohmann::json;
J checks=J::array();
void check(bool ok,const char* label){
  checks.push_back({{"name",label},{"passed",ok}});
  if(!ok)throw std::runtime_error(label);
}
int64_t scalar(Brain& b,const char* sql){
  auto s=b.db().prepare(sql);if(!s.step())throw std::runtime_error("scalar missing");return s.column_int(0);
}
void rejects(Brain& b,const J& p){
  try{memory::usage_batch(b,"alpha",p,true);}
  catch(const memory::Error& e){check(std::string(e.what())=="fact_transaction_active","reject with transaction ownership code");return;}
  throw std::runtime_error("caller transaction was not rejected");
}
J approve(Brain& b,const J& req){auto p=req;p["snapshot"]=memory::usage_batch(b,"alpha",req)["snapshot"];return p;}
struct CommitGate {int calls=0;};
int deny_commit(void* raw,int code,const char* operation,const char*,const char*,const char*){
  auto& gate=*static_cast<CommitGate*>(raw);
  if(code==SQLITE_TRANSACTION && operation && std::string(operation)=="COMMIT"){++gate.calls;return SQLITE_DENY;}
  return SQLITE_OK;
}
}
int main(){
  std::string error;
  try{
    Brain b;b.open_at(":memory:");b.ensure_source("alpha");b.save_config_value("memory.writeback","salient");
    auto event=memory::capture(b,"alpha",{{"session_id","ownership"},{"fragment_id","one"},
        {"messages",J::array({{{"role","user"},{"content","I prefer preserving caller transaction ownership."}}})}},true);
    memory::extract(b,"alpha",event["event_id"]);
    std::string iid;{auto q=b.db().prepare("SELECT item_id FROM memory_items WHERE event_id=?");q.bind_text(1,event["event_id"].get<std::string>());check(q.step(),"public setup has evidence");iid=q.column_text(0);}
    const auto fact=memory::FactStore(b,"alpha").create({{"predicate","review.preference"},{"item_id",iid}});
    J request={{"operation","report"},{"items",J::array({{{"fact_id",fact["fact_id"]},{"usage_id",std::string(64,'1')},{"expected_revision",fact["revision"]}}})}};
    auto approved=approve(b,request);
    const auto busy=scalar(b,"PRAGMA busy_timeout");
    {
      auto pending=b.db().prepare("INSERT INTO config(key,value) VALUES('owner.a','keep'),('owner.b','keep') RETURNING key");
      check(pending.step(),"pending first-write returning row exists");
      check(sqlite3_get_autocommit(b.db().handle())!=0 && sqlite3_txn_state(b.db().handle(),nullptr)==SQLITE_TXN_WRITE,"implicit writer exists while autocommit enabled");
      const auto before=sqlite3_total_changes(b.db().handle());
      const auto preview=memory::usage_batch(b,"alpha",request);
      check(preview["snapshot"]==approved["snapshot"],"preview works inside implicit writer without receipt mutation");
      rejects(b,approved);
      check(sqlite3_total_changes(b.db().handle())==before && scalar(b,"SELECT COUNT(*) FROM config WHERE key LIKE 'owner.%'")==2,"first-write rejection preserves pending caller rows and total changes");
      check(scalar(b,"SELECT COUNT(*) FROM sqlite_master WHERE name='memory_fact_usage'")==0,"pending writer rejected before optional module creation");
      check(pending.step() && !pending.step(),"caller can finish returning statement after refusal");
    }
    check(sqlite3_txn_state(b.db().handle(),nullptr)==SQLITE_TXN_NONE && scalar(b,"SELECT COUNT(*) FROM config WHERE key LIKE 'owner.%'")==2,"caller writes commit only when caller finishes statement");
    {
      auto pending=b.db().prepare("SELECT key FROM config ORDER BY key");
      check(pending.step() && sqlite3_txn_state(b.db().handle(),nullptr)==SQLITE_TXN_READ,"implicit read snapshot is active");
      rejects(b,approved);
      check(memory::usage_batch(b,"alpha",request)["snapshot"]==approved["snapshot"],"preview remains usable with active read cursor");
      check(pending.step(),"caller read cursor remains usable");
    }
    {
      auto idle=b.db().prepare("SELECT key FROM config ORDER BY key");
      check(sqlite3_txn_state(b.db().handle(),nullptr)==SQLITE_TXN_NONE,"prepared but unstepped statement owns no transaction");
      check(memory::usage_batch(b,"alpha",approved,true)["changed"]==1,"idle prepared statement does not block legitimate batch");
      check(idle.step(),"unstepped caller statement still executes after batch");
      while(idle.step()){}
      auto no_op=approve(b,request);
      check(memory::usage_batch(b,"alpha",no_op,true)["changed"]==0,"completed statement allows idempotent batch");
    }
    const J revoke={{"operation","revoke"},{"items",J::array({{{"fact_id",fact["fact_id"]},{"usage_id",std::string(64,'1')}}})}};
    for(bool withdrawing:{false,true}){
      auto plan=approve(b,withdrawing?revoke:request);
      auto owner=b.db().prepare("UPDATE config SET value='pending' WHERE key LIKE 'owner.%' RETURNING key");
      check(owner.step(),"initialized-module caller writer started");
      const auto before=sqlite3_total_changes(b.db().handle());
      rejects(b,plan);
      check(scalar(b,"SELECT COUNT(*) FROM config WHERE key LIKE 'owner.%' AND value='pending'")==2 && sqlite3_total_changes(b.db().handle())==before,"no-op or revoke rejection preserves caller updates");
      check(scalar(b,"SELECT COUNT(*) FROM memory_fact_usage WHERE withdrawn_at IS NULL")==1,"rejection does not withdraw existing receipt");
      check(owner.step() && !owner.step(),"caller finishes initialized-module writer after refusal");
    }
    b.db().exec("SAVEPOINT caller; INSERT INTO config(key,value) VALUES('savepoint.owner','keep')");
    auto no_op=approve(b,request);rejects(b,no_op);
    check(scalar(b,"SELECT COUNT(*) FROM config WHERE key='savepoint.owner'")==1 && sqlite3_get_autocommit(b.db().handle())==0,"savepoint and its uncommitted row survive refusal");
    b.db().exec("ROLLBACK TO caller; RELEASE caller");
    check(scalar(b,"SELECT COUNT(*) FROM config WHERE key='savepoint.owner'")==0,"only caller rolls back its savepoint");
    b.db().exec("ATTACH ':memory:' AS auxiliary; CREATE TABLE auxiliary.owned(v)");
    {
      auto auxiliary=b.db().prepare("INSERT INTO auxiliary.owned VALUES(1),(2) RETURNING v");
      check(auxiliary.step() && sqlite3_txn_state(b.db().handle(),"main")==SQLITE_TXN_NONE && sqlite3_txn_state(b.db().handle(),nullptr)==SQLITE_TXN_WRITE,"implicit write in attached database is detected");
      rejects(b,no_op);
      check(scalar(b,"SELECT COUNT(*) FROM auxiliary.owned")==2,"attached caller changes survive rejected batch");
      check(auxiliary.step() && !auxiliary.step(),"attached caller statement remains finishable");
    }
    b.db().exec("DETACH auxiliary");
    auto second=request;second["items"][0]["usage_id"]=std::string(64,'2');
    auto second_plan=approve(b,second);
    const auto before_changes=sqlite3_total_changes(b.db().handle());CommitGate gate;
    check(sqlite3_set_authorizer(b.db().handle(),deny_commit,&gate)==SQLITE_OK,"install test-only commit-denial authorizer");
    bool failed=false;
    try{memory::usage_batch(b,"alpha",second_plan,true);}
    catch(const std::exception&){failed=true;}
    sqlite3_set_authorizer(b.db().handle(),nullptr,nullptr);
    check(failed && gate.calls==1 && sqlite3_total_changes(b.db().handle())>before_changes,"insertion executed before simulated commit failure");
    check(scalar(b,"SELECT COUNT(*) FROM memory_fact_usage")==1 && sqlite3_get_autocommit(b.db().handle())!=0,"commit failure rolls back whole owned batch and releases transaction");
    check(scalar(b,"SELECT COUNT(*) FROM config WHERE key LIKE 'owner.%'")==2,"commit failure leaves previously committed caller data intact");
    check(approve(b,second)["snapshot"]==second_plan["snapshot"],"rolled-back batch retains original logical snapshot");
    check(memory::usage_batch(b,"alpha",second_plan,true)["changed"]==1,"same approval usable after actual full rollback");
    check(scalar(b,"PRAGMA busy_timeout")==busy,"all paths restore original busy timeout");
  }catch(const std::exception& e){error=e.what();}
  std::cout<<J({{"suite","n47z-transaction-ownership"},{"result",error.empty()?"PASS":"FAIL"},{"checks",checks},{"count",checks.size()},{"error",error},{"sqlite_version",sqlite3_libversion()}}).dump()<<"\n";
  return error.empty()?0:1;
}
