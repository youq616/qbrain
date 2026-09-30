// PR62 R1 regression: no product-internal guard/SQL helpers imported.
#include "qbrain/context/context.hpp"
#include <functional>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
using namespace qbrain;
using J=nlohmann::json;
namespace {
J observations=J::array();int checks=0;
const std::string uri="qbrain://alpha/resources/docs/";
void check(bool ok,const std::string& name){++checks;if(!ok)throw std::runtime_error(name);}
J query(Brain& b,const std::string& sql,int cols){J r=J::array();auto s=b.db().prepare(sql);while(s.step()){J row=J::array();for(int i=0;i<cols;++i)row.push_back(s.column_text(i));r.push_back(row);}return r;}
J state(Brain& b){J j={{"schema",query(b,"SELECT type,name,tbl_name,sql FROM main.sqlite_master ORDER BY type,name",4)},
 {"temp",query(b,"SELECT type,name,tbl_name,sql FROM temp.sqlite_master ORDER BY type,name",4)},
 {"pages",query(b,"SELECT id,source_id,slug,type,title,body,deleted_at FROM main.pages ORDER BY id",7)},
 {"config",query(b,"SELECT key,value FROM main.config ORDER BY key",2)}};
 auto q=b.db().prepare("SELECT 1 FROM main.sqlite_master WHERE name='context_cache' AND type='table'");
 if(q.step())j["cache"]=query(b,"SELECT source_id,uri,signature,l0,l1,refs_json,dirty FROM main.context_cache ORDER BY source_id,uri",7);
 return j;
}
void init(Brain& b,bool cached=true){b.open_at(":memory:");b.ensure_source("alpha");
 b.save_config_value("context.external_summary","allow",false);b.save_config_value("embed.auto","false",false);
 b.db().exec("INSERT INTO pages(source_id,slug,title,body) VALUES('alpha','docs/a','Synthetic','SYNTHETIC ORIGINAL 中文')");
 if(cached)context::summary(b,"alpha",uri);
}
ai::ChatResult answer(){ai::ChatResult r;r.ok=true;r.content=R"({"l0":"Synthetic","l1":"Synthetic guarded response"})";return r;}
std::string failure(const std::function<void()>& f){try{f();return "accepted";}catch(const memory::Error& e){return e.what();}}
void denied(Brain& b,const std::string& label,const std::string& expected,bool reads=true){
 const auto before=state(b);const bool caller=b.db().transaction_active();int calls=0;
 auto provider=[&](const auto&,int){++calls;return answer();};
 const auto code=failure([&]{context::summary(b,"alpha",uri,"model",provider);});
 observations.push_back({{"case",label},{"error",code},{"provider_calls",calls},{"expected_calls",0}});
 check(code==expected,label+": error");check(calls==0,label+": provider called before rejection");
 check(state(b)==before,label+": mutated state");check(b.db().transaction_active()==caller,label+": stole/leaked transaction");
 if(reads)for(const auto& item:std::vector<std::pair<std::string,std::string>>{{uri,"L1"},{uri+"a","L2"},{"","L1"}}){
  check(failure([&]{context::read(b,"alpha",item.first,item.second);})==expected,label+": read admission");
  check(state(b)==before&&b.db().transaction_active()==caller,label+": read state changed");
 }
}
void exact_repro(){Brain b;init(b);b.db().exec("DROP TRIGGER ctx_page_insert;CREATE TRIGGER ctx_page_insert AFTER INSERT ON pages BEGIN SELECT 1; END");denied(b,"reviewer-exact-repro","context_schema_incomplete");}
void malformed(){
 for(const auto& name:{"insert","update","delete"}){
  Brain b;init(b);b.db().exec(std::string("DROP TRIGGER ctx_page_")+name);denied(b,std::string("missing-")+name,"context_schema_incomplete");
 }
 for(const auto& item:std::vector<std::pair<std::string,std::string>>{
  {"DROP TRIGGER ctx_page_update;CREATE TRIGGER ctx_page_update AFTER UPDATE ON pages BEGIN SELECT 1; END","context_schema_incomplete"},
  {"DROP TRIGGER ctx_page_delete;CREATE TRIGGER ctx_page_delete AFTER DELETE ON pages BEGIN SELECT 1; END","context_schema_incomplete"},
  {"DROP TRIGGER ctx_page_insert;CREATE TRIGGER CTX_PAGE_INSERT AFTER INSERT ON pages BEGIN SELECT 1; END","context_schema_incomplete"},
  {"DROP TABLE context_cache;CREATE TABLE Context_Cache(fake TEXT)","context_schema_version_unsupported"},
  {"ALTER TABLE context_cache ADD COLUMN unexpected TEXT","context_schema_version_unsupported"},
  {"DROP TABLE context_cache","context_schema_conflict"},
  {"DROP TABLE context_cache;CREATE VIEW context_cache AS SELECT 1 AS placeholder","context_schema_version_unsupported"},
  {"DROP TRIGGER ctx_page_insert;CREATE TRIGGER ctx_page_insert AFTER INSERT ON pages BEGIN\n UPDATE context_cache SET dirty=1,l0='',l1='',refs_json='[]' WHERE source_id=NEW.source_id; END","context_schema_incomplete"}
 }){Brain b;init(b);b.db().exec(item.first);denied(b,item.first,item.second);}
}
void ownership(){
 for(const auto& begin:{"BEGIN","BEGIN IMMEDIATE","SAVEPOINT owner"}){
  Brain b;init(b);const J committed=state(b);b.db().exec(begin);b.db().exec("UPDATE pages SET body='PRIVATE UNCOMMITTED' WHERE source_id='alpha'");
  denied(b,begin,"context_transaction_active");b.db().exec("ROLLBACK");check(state(b)==committed,"caller can rollback its own work");
 }
}
void implicit_ownership(){
 {
  Brain b;init(b);auto pending=b.db().prepare("INSERT INTO config(key,value) VALUES('owner.one','keep'),('owner.two','keep') RETURNING key");
  check(pending.step()&&sqlite3_get_autocommit(b.db().handle())!=0,"implicit writer with autocommit enabled");
  denied(b,"implicit-main-writer","context_transaction_active");
  check(sqlite3_txn_state(b.db().handle(),nullptr)==SQLITE_TXN_WRITE,"pending writer transaction survives");
  check(query(b,"SELECT key FROM config WHERE key LIKE 'owner.%' ORDER BY key",1).size()==2,"pending caller rows survive");
  check(pending.step()&&!pending.step(),"caller can complete pending writer");
  check(query(b,"SELECT key FROM config WHERE key LIKE 'owner.%' ORDER BY key",1).size()==2,"caller rows commit on caller completion");
 }
 {
  Brain b;init(b);auto pending=b.db().prepare("SELECT key FROM config ORDER BY key");
  check(pending.step()&&sqlite3_txn_state(b.db().handle(),nullptr)==SQLITE_TXN_READ,"implicit reader is active");
  denied(b,"implicit-reader","context_transaction_active");check(pending.step(),"caller read cursor still usable");
 }
 {
  Brain b;init(b);b.db().exec("ATTACH ':memory:' AS peer;CREATE TABLE peer.owned(v)");
  auto pending=b.db().prepare("INSERT INTO peer.owned VALUES(1),(2) RETURNING v");
  check(pending.step()&&sqlite3_txn_state(b.db().handle(),"main")==SQLITE_TXN_NONE,"attached writer without main transaction");
  denied(b,"implicit-attached-writer","context_transaction_active");
  check(query(b,"SELECT v FROM peer.owned ORDER BY v",1).size()==2,"attached caller data survives");
  check(pending.step()&&!pending.step(),"attached caller can finish its writer");
 }
 {
  Brain b;init(b);auto idle=b.db().prepare("SELECT slug FROM pages");int calls=0;
  auto provider=[&](const auto&,int){++calls;return answer();};
  check(context::summary(b,"alpha",uri,"model",provider)["status"]=="cached"&&calls==1,"unstepped statement is not a pending transaction");
  check(idle.step(),"idle caller statement remains usable");
  observations.push_back({{"case","idle-prepared-positive"},{"provider_calls",calls}});
 }
 {
  Brain b;init(b);storage::Database::Statement pending;int calls=0;J after;
  auto provider=[&](const auto&,int){++calls;pending=b.db().prepare("INSERT INTO config(key,value) VALUES('late.one','keep'),('late.two','keep') RETURNING key");check(pending.step(),"callback starts implicit writer");after=state(b);return answer();};
  const auto code=failure([&]{context::summary(b,"alpha",uri,"model",provider);});
  check(code=="context_transaction_active"&&calls==1,"late implicit writer blocks publication only");
  check(state(b)==after&&sqlite3_txn_state(b.db().handle(),nullptr)==SQLITE_TXN_WRITE,"late caller transaction/data untouched");
  check(pending.step()&&!pending.step(),"late caller can complete pending writer");
  check(query(b,"SELECT key FROM config WHERE key LIKE 'late.%' ORDER BY key",1).size()==2,"late caller rows commit normally");
  observations.push_back({{"case","late-implicit-writer"},{"provider_calls",calls},{"error",code}});
 }
}

void shadows(){
 for(const auto& name:{"sources","pages","config","context_cache","PaGeS"}){
  Brain b;init(b);b.db().exec(std::string("CREATE TEMP TABLE ")+name+"(untrusted TEXT)");denied(b,std::string("temp-")+name,"context_sqlite_schema_context");
 }
 Brain b;init(b);b.db().exec("CREATE TEMP VIEW pages AS SELECT * FROM main.pages");denied(b,"temp-view","context_sqlite_schema_context");
}
void valid_callbacks(){
 for(bool cached:{false,true}){
  Brain b;init(b,cached);b.db().exec("CREATE TEMP TABLE unrelated(value TEXT)");int calls=0;
  auto provider=[&](const auto&,int){++calls;check(!b.db().transaction_active(),"provider must be outside read transaction");return answer();};
  auto r=context::summary(b,"alpha",uri,"model",provider);
  check(calls==1&&r["status"]=="cached"&&r["provider_calls"]==1,"valid model positive control");
  check(!b.db().transaction_active(),"valid publication releases its transaction");
  observations.push_back({{"case",cached?"valid-scoped":"valid-absent"},{"provider_calls",calls},{"status",r["status"]}});
 }
 Brain b;init(b);b.db().exec("DROP TRIGGER ctx_page_insert; DROP TRIGGER ctx_page_update; DROP TRIGGER ctx_page_delete");
 b.db().exec("CREATE TRIGGER ctx_page_insert AFTER INSERT ON pages BEGIN\n UPDATE context_cache SET dirty=1,l0='',l1='',refs_json='[]' WHERE source_id=NEW.source_id; END");
 b.db().exec("CREATE TRIGGER ctx_page_update AFTER UPDATE ON pages BEGIN\n UPDATE context_cache SET dirty=1,l0='',l1='',refs_json='[]' WHERE source_id=NEW.source_id OR source_id=OLD.source_id; END");
 b.db().exec("CREATE TRIGGER ctx_page_delete AFTER DELETE ON pages BEGIN\n UPDATE context_cache SET dirty=1,l0='',l1='',refs_json='[]' WHERE source_id=OLD.source_id; END");
 int calls=0;auto provider=[&](const auto&,int){++calls;check(!b.db().transaction_active(),"legacy callback outside snapshot");return answer();};
 check(context::summary(b,"alpha",uri,"model",provider)["status"]=="cached"&&calls==1,"valid legacy cache can upgrade");
 observations.push_back({{"case","valid-legacy"},{"provider_calls",calls}});
}
void callback_changes(){
 for(const auto& item:std::vector<std::pair<std::string,std::string>>{
  {"UPDATE pages SET body='CHANGED DURING CALLBACK'","evidence_changed"},
  {"DROP TRIGGER ctx_page_insert;CREATE TRIGGER ctx_page_insert AFTER INSERT ON pages BEGIN SELECT 1; END","context_schema_incomplete"},
  {"CREATE TEMP TABLE config(key TEXT,value TEXT)","context_sqlite_schema_context"},
  {"BEGIN;UPDATE pages SET body='CALLBACK OWNED'","context_transaction_active"}
 }){
  Brain b;init(b);int calls=0;J after;
  auto provider=[&](const auto&,int){++calls;check(!b.db().transaction_active(),"read released before callback mutation");b.db().exec(item.first);after=state(b);return answer();};
  const auto code=failure([&]{context::summary(b,"alpha",uri,"model",provider);});
  check(code==item.second&&calls==1,"late mutation refuses publication, not past authorized call");
  check(state(b)==after,"no write after callback rejection");
  const bool owned=item.second=="context_transaction_active";check(b.db().transaction_active()==owned,"callback ownership preserved");
  if(owned)b.db().exec("ROLLBACK");
  observations.push_back({{"case","late:"+item.second},{"error",code},{"provider_calls",calls}});
 }
}
}
int main(int argc,char** argv){try{
 exact_repro();if(argc==1){malformed();ownership();implicit_ownership();shadows();valid_callbacks();callback_changes();}
 else if(argc!=2||std::string(argv[1])!="--repro-only")throw std::runtime_error("invalid arguments");
 std::cout<<J({{"schema","qbrain-context-preflight-v1"},{"passed",true},{"checks",checks},{"observations",observations},{"real_provider_calls",0}}).dump()<<'\n';return 0;
 }catch(const std::exception& e){std::cout<<J({{"schema","qbrain-context-preflight-v1"},{"passed",false},{"checks",checks},{"error",e.what()},{"observations",observations},{"real_provider_calls",0}}).dump()<<'\n';return 1;}}
