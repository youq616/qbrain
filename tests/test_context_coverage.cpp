// Bounded coverage publication: public API, independent row/digest observations.
// Synthetic providers only. No internal context snapshot/guard helpers imported.
#include "qbrain/context/context.hpp"
#include "qbrain/util/hash.hpp"
#include <filesystem>
#include <functional>
#include <iomanip>
#include <iostream>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace qbrain;
using J=nlohmann::json;
namespace {
int checks=0;
J observations=J::array();
const std::string uri="qbrain://alpha/resources/docs/";
void check(bool ok,const std::string& message){++checks;if(!ok)throw std::runtime_error(message);}
void page(storage::Database& db,int id,const std::string& source="alpha",
          const std::string& prefix="docs/",const std::string& type="note"){
  std::ostringstream slug;slug<<prefix<<std::setfill('0')<<std::setw(4)<<id;
  auto s=db.prepare("INSERT INTO pages(id,source_id,slug,title,body,type) VALUES(?,?,?,'t','b',?)");
  s.bind_int(1,id);s.bind_text(2,source);s.bind_text(3,slug.str());s.bind_text(4,type);s.step_done();
}
J query(storage::Database& db,const std::string& sql,int cols){
  J result=J::array();auto s=db.prepare(sql);
  while(s.step()){J row=J::array();for(int c=0;c<cols;++c)row.push_back(s.column_text(c));result.push_back(row);}return result;
}
J state(Brain& b){
  J out={{"ddl",query(b.db(),"SELECT type,name,tbl_name,sql FROM main.sqlite_master ORDER BY type,name",4)},
         {"pages",query(b.db(),"SELECT id,source_id,slug,title,body,type,deleted_at FROM pages ORDER BY id",7)}};
  auto s=b.db().prepare("SELECT 1 FROM main.sqlite_master WHERE type='table' AND name='context_cache'");
  if(s.step())out["cache"]=query(b.db(),"SELECT source_id,uri,signature,l0,l1,refs_json,page_count,method,dirty,partial FROM context_cache ORDER BY source_id,uri",10);
  return out;
}
struct Coverage {std::string signature;int count=0;bool partial=false;};
Coverage observed(Brain& b){
  Coverage out;std::string digests;
  // This fixture has 1-byte titles/bodies. Only the page-cap can truncate input.
  auto s=b.db().prepare("SELECT id,slug,title,body FROM pages WHERE source_id='alpha' AND deleted_at IS NULL AND type NOT IN ('skill','session_fragment') AND instr(slug,'docs/')=1 ORDER BY slug,id");
  while(s.step()){
    if(out.count==256){out.partial=true;break;}
    ++out.count;digests+=util::sha256_hex(J::array({s.column_int(0),s.column_text(1),s.column_text(2),s.column_text(3)}).dump());
  }
  out.signature=util::sha256_hex(digests);return out;
}
ai::ChatResult answer(){ai::ChatResult r;r.ok=true;r.content=R"({"l0":"Synthetic","l1":"Synthetic bounded summary"})";return r;}
void init(Brain& b,int n,const std::string& path=":memory:"){
  b.open_at(path);check(b.db().backend_kind()==storage::BackendKind::sqlite,"SQLite fixture only");
  b.ensure_source("alpha");b.ensure_source("beta");
  b.save_config_value("embed.auto","false",false);b.save_config_value("context.external_summary","allow",false);
  b.db().exec("BEGIN");for(int i=1;i<=n;++i)page(b.db(),i);b.db().exec("COMMIT");
}
void validate_cached(Brain& b,const Coverage& expected,const J& result){
  check(result["status"]=="cached"&&result["provider_calls"]==1,"one explicit provider request published");
  check(result["page_count"]==expected.count&&result["truncated"]==expected.partial,"summary metadata matches current bounded source");
  auto s=b.db().prepare("SELECT signature,page_count,partial,dirty,l0,l1 FROM context_cache WHERE source_id='alpha' AND uri=?");s.bind_text(1,uri);
  check(s.step(),"cache row exists");
  check(s.column_text(0)==expected.signature&&s.column_int(1)==expected.count&&s.column_int(2)==int(expected.partial)&&s.column_int(3)==0,"persisted signature/count/coverage/freshness");
  check(s.column_text(4)=="Synthetic"&&s.column_text(5)=="Synthetic bounded summary","provider text unchanged");
  // End the statement before the public read, preserving implicit-transaction rules.
  s=storage::Database::Statement{};
  auto read=context::read(b,"alpha",uri,"L1",32768);
  check(read["revision"]==expected.signature&&read["page_count"]==expected.count,"public read identity");
  check(read["cache_status"]=="fresh"&&read["method"]=="model"&&read["content"]=="Synthetic bounded summary","public read uses valid cached model result");
  check(read["truncated"]==expected.partial,"public truncated flag matches coverage with sufficient JSON budget");
  check(!b.db().transaction_pending(),"no owned snapshot/write transaction leaked");
}
void run_case(const std::string& name,int n,bool warm,const std::function<void(storage::Database&)>& change,
              bool reject,bool same_selected_signature,const std::function<void(storage::Database&)>& prepare={}){
  Brain b;init(b,n);if(prepare)prepare(b.db());if(warm)context::summary(b,"alpha",uri);
  const auto before=observed(b);J after_callback,result;int calls=0;std::string code;
  auto provider=[&](const auto&,int){++calls;check(!b.db().transaction_pending(),"read scope released before callback");change(b.db());after_callback=state(b);return answer();};
  try{result=context::summary(b,"alpha",uri,"model",provider);}catch(const memory::Error&e){code=e.what();}
  const auto after=observed(b);
  check((before.signature==after.signature)==same_selected_signature,"independent selected-evidence comparison: "+name);
  observations.push_back({{"case",name},{"initial_pages",n},{"warm_cache",warm},{"error",code},
    {"provider_calls",calls},{"before_signature",before.signature},{"after_signature",after.signature},
    {"before_partial",before.partial},{"after_partial",after.partial},{"result",result}});
  check(calls==1,"callback must run once, not be erased/retried");
  if(reject){
    check(code=="evidence_changed","changed coverage/evidence must refuse: "+name);
    check(state(b)==after_callback,"no stale cache publication or post-callback DDL: "+name);
    check(!b.db().transaction_pending(),"failure releases owned transaction");
    int retry_calls=0;auto retry=[&](const auto&,int){++retry_calls;return answer();};
    auto retried=context::summary(b,"alpha",uri,"model",retry);
    check(retry_calls==1,"only explicit caller retry invokes again");validate_cached(b,after,retried);
  }else{
    check(code.empty(),"unchanged bounded observation remains publishable: "+name);validate_cached(b,after,result);
  }
}
struct TempDir {
  std::filesystem::path path;
  TempDir(){std::random_device r;for(int i=0;i<16;++i){path=std::filesystem::temp_directory_path()/ ("qbrain-coverage-"+std::to_string(r()));if(std::filesystem::create_directory(path))return;}throw std::runtime_error("no unique temporary test directory");}
  ~TempDir(){std::error_code ec;std::filesystem::remove_all(path,ec);}
};
void two_connections(bool removing){
  TempDir dir;const auto u8=(dir.path/"brain.db").u8string();std::string path(u8.begin(),u8.end());
  Brain b;init(b,removing?257:256,path);context::summary(b,"alpha",uri);
  storage::Database writer;writer.open(path);int calls=0;J after_callback;std::string code;
  auto provider=[&](const auto&,int){++calls;check(!b.db().transaction_pending(),"cross-connection callback has no reader transaction");
    writer.exec("BEGIN IMMEDIATE");if(removing)writer.exec("DELETE FROM pages WHERE id=257");else page(writer,257);writer.exec("COMMIT");after_callback=state(b);return answer();};
  try{context::summary(b,"alpha",uri,"model",provider);}catch(const memory::Error&e){code=e.what();}
  check(calls==1&&code=="evidence_changed","separate committed writer changes coverage");
  check(state(b)==after_callback,"writer commit preserved, model cache not republished");
  check(!b.db().transaction_pending()&&!writer.transaction_pending(),"both connections leave transactions idle");
  auto c=observed(b);check(c.partial==!removing,"fresh snapshot sees other connection commit");
  observations.push_back({{"case",removing?"other-connection-257-to-256":"other-connection-256-to-257"},{"provider_calls",calls},{"error",code},{"after_partial",c.partial}});
}
void suite(){
  for(bool warm:{false,true}){
    const std::string suffix=warm?"-warm":"-absent";
    run_case("256-to-257"+suffix,256,warm,[](auto&db){page(db,257);},true,true);
    run_case("257-to-256"+suffix,257,warm,[](auto&db){db.exec("DELETE FROM pages WHERE id=257");},true,true);
    run_case("stable-256"+suffix,256,warm,[](auto&){},false,true);
    run_case("stable-257"+suffix,257,warm,[](auto&){},false,true);
    run_case("257-to-258"+suffix,257,warm,[](auto&db){page(db,258);},false,true);
  }
  run_case("soft-delete-tail",257,true,[](auto&db){db.exec("UPDATE pages SET deleted_at='2030-01-01' WHERE id=257");},true,true);
  run_case("restore-tail",257,true,[](auto&db){db.exec("UPDATE pages SET deleted_at=NULL WHERE id=257");},true,true,
    [](auto&db){db.exec("UPDATE pages SET deleted_at='2030-01-01' WHERE id=257");});
  run_case("tail-to-skill",257,true,[](auto&db){db.exec("UPDATE pages SET type='skill' WHERE id=257");},true,true);
  run_case("tail-to-other-source",257,true,[](auto&db){db.exec("UPDATE pages SET source_id='beta' WHERE id=257");},true,true);
  run_case("tail-body-change",257,true,[](auto&db){db.exec("UPDATE pages SET body='changed-tail' WHERE id=257");},false,true);
  run_case("other-directory",256,true,[](auto&db){page(db,257,"alpha","other/");},false,true);
  run_case("neighboring-prefix",256,true,[](auto&db){page(db,257,"alpha","docs-other/");},false,true);
  run_case("other-source",256,true,[](auto&db){page(db,257,"beta");},false,true);
  run_case("other-namespace",256,true,[](auto&db){page(db,257,"alpha","docs/","skill");},false,true);
  run_case("rollback-tail-insert",256,true,[](auto&db){db.exec("BEGIN");page(db,257);db.exec("ROLLBACK");},false,true);
  run_case("selected-body-change",256,true,[](auto&db){db.exec("UPDATE pages SET body='changed-prefix' WHERE id=1");},true,false);
  run_case("255-to-256",255,true,[](auto&db){page(db,256);},true,false);
  run_case("empty-to-one",0,false,[](auto&db){page(db,1);},true,false);
  two_connections(false);two_connections(true);
}
}
int main(int argc,char**argv){try{
  if(argc==2&&std::string(argv[1])=="--repro-only")run_case("256-to-257-absent",256,false,[](auto&db){page(db,257);},true,true);
  else if(argc==1)suite();else throw std::runtime_error("invalid arguments");
  std::cout<<J{{"schema","qbrain-context-coverage-v1"},{"passed",true},{"scenarios",observations.size()},{"checks",checks},{"observations",observations},{"real_provider_calls",0},{"postgres_executed",false}}.dump()<<'\n';return 0;
}catch(const std::exception&e){std::cout<<J{{"schema","qbrain-context-coverage-v1"},{"passed",false},{"checks",checks},{"error",e.what()},{"observations",observations},{"real_provider_calls",0}}.dump()<<'\n';return 1;}}
