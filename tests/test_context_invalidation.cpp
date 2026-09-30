// N48T: independent native acceptance. No implementation-policy/header imports.
#include "qbrain/context/context.hpp"
#include <functional>
#include <iostream>
#include <map>
#include <stdexcept>
#include <vector>
using namespace qbrain;
using J=nlohmann::json;
namespace {
J evidence=J::array();
void check(bool ok,const std::string& name){evidence.push_back({{"name",name},{"passed",ok}});if(!ok)throw std::runtime_error(name);}
void rejects(const std::function<void()>& f,const std::string& code){try{f();}catch(const memory::Error& e){check(e.what()==code,"reject:"+code);return;}throw std::runtime_error("accepted:"+code);}
std::string scalar(Brain& b,const std::string& q){auto s=b.db().prepare(q);if(!s.step())return "";return s.column_text(0);}
void page(Brain& b,int id,const std::string& source,const std::string& slug,const std::string& type="note"){
 auto s=b.db().prepare("INSERT INTO pages(id,source_id,slug,title,body,type) VALUES(?,?,?,?,?,?)");
 s.bind_int(1,id);s.bind_text(2,source);s.bind_text(3,slug);s.bind_text(4,slug);s.bind_text(5,"Original 中文😀 "+slug);s.bind_text(6,type);s.step_done();}
void setup(Brain& b){b.open_at(":memory:");b.ensure_source("alpha");b.ensure_source("beta");b.save_config_value("embed.auto","false",false);}
std::string uri(const std::string& path,const std::string& source="alpha",const std::string& space="resources"){return "qbrain://"+source+"/"+space+"/"+path;}
J rows(Brain& b){J r=J::array();auto s=b.db().prepare("SELECT source_id,uri,signature,l0,l1,refs_json,page_count,method,dirty,partial FROM context_cache ORDER BY source_id,uri");while(s.step())r.push_back(J::array({s.column_text(0),s.column_text(1),s.column_text(2),s.column_text(3),s.column_text(4),s.column_text(5),s.column_int(6),s.column_text(7),s.column_int(8),s.column_int(9)}));return r;}
void cache(Brain& b,const std::string& path,const std::string& source="alpha",const std::string& space="resources"){context::summary(b,source,uri(path,source,space));}
void legacy(Brain& b){b.db().exec(R"SQL(
CREATE TABLE context_cache(source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,uri TEXT NOT NULL,
 signature TEXT NOT NULL,l0 TEXT NOT NULL,l1 TEXT NOT NULL,refs_json TEXT NOT NULL,page_count INTEGER NOT NULL,
 method TEXT NOT NULL,dirty INTEGER NOT NULL DEFAULT 0,partial INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(source_id,uri));
CREATE TRIGGER ctx_page_insert AFTER INSERT ON pages BEGIN
 UPDATE context_cache SET dirty=1,l0='',l1='',refs_json='[]' WHERE source_id=NEW.source_id; END;
CREATE TRIGGER ctx_page_update AFTER UPDATE ON pages BEGIN
 UPDATE context_cache SET dirty=1,l0='',l1='',refs_json='[]' WHERE source_id=NEW.source_id OR source_id=OLD.source_id; END;
CREATE TRIGGER ctx_page_delete AFTER DELETE ON pages BEGIN
 UPDATE context_cache SET dirty=1,l0='',l1='',refs_json='[]' WHERE source_id=OLD.source_id; END;
)SQL");}
void selectivity(){
 Brain b;setup(b);page(b,1,"alpha","docs/a");page(b,2,"alpha","other/b");page(b,3,"alpha","docs/skill","skill");page(b,4,"beta","docs/c");
 for(const auto& p:{"", "docs/", "other/", "empty/"})cache(b,p);
 cache(b,"docs/","alpha","skills");cache(b,"docs/","beta");
 const J before=rows(b);
 b.db().exec("UPDATE pages SET body='CHANGED' WHERE id=1");
 auto after=rows(b);int changed=0,untouched=0;
 for(std::size_t i=0;i<before.size();++i){
  const bool affected=before[i][0]=="alpha"&&(before[i][1]==uri("")||before[i][1]==uri("docs/"));
  if(affected){++changed;check(after[i][8]==1&&after[i][3]==""&&after[i][4]==""&&after[i][5]=="[]","erase affected preview/ref");}
  else{++untouched;check(after[i]==before[i],"unrelated cache row preserved byte-for-byte");}
 }
 check(changed==2&&untouched==4,"only changed directory and ancestors");
 check(context::read(b,"alpha",uri("docs/"),"L1")["content"].get<std::string>().find("CHANGED")!=std::string::npos,"affected preview recomputed");
 check(context::read(b,"alpha",uri("other/"))["cache_status"]=="fresh","sibling remains fresh");
 page(b,5,"alpha","empty/new");check(context::read(b,"alpha",uri("empty/"))["page_count"]==1,"empty cache invalidates on new page");
}
void transitions(){
 for(const auto& mutation:std::vector<std::string>{
  "UPDATE pages SET slug='other/moved' WHERE id=1",
  "UPDATE pages SET source_id='beta' WHERE id=1",
  "UPDATE pages SET type='skill' WHERE id=1",
  "UPDATE pages SET deleted_at=CURRENT_TIMESTAMP WHERE id=1",
  "DELETE FROM pages WHERE id=1"}){
  Brain b;setup(b);page(b,1,"alpha","docs/a");page(b,2,"alpha","independent/b");
  cache(b,"docs/");cache(b,"other/");cache(b,"docs/","alpha","skills");cache(b,"docs/","beta");cache(b,"independent/");
  J original=rows(b);b.db().exec("BEGIN");b.db().exec(mutation);b.db().exec("ROLLBACK");check(rows(b)==original,"row change plus invalidation rollback");
  b.db().exec(mutation);auto r=context::read(b,"alpha",uri("docs/"));check(r["cache_status"]=="stale"&&r["page_count"]==0,"old scope invalidated");
  check(context::read(b,"alpha",uri("independent/"))["cache_status"]=="fresh","unrelated scope retained through transition");
  if(mutation.find("other/moved")!=std::string::npos)check(context::read(b,"alpha",uri("other/"))["page_count"]==1,"new slug scope invalidated");
  if(mutation.find("source_id")!=std::string::npos)check(context::read(b,"beta",uri("docs/","beta"))["page_count"]==1,"new source invalidated");
  if(mutation.find("type=")!=std::string::npos)check(context::read(b,"alpha",uri("docs/","alpha","skills"))["page_count"]==1,"new namespace invalidated");
  if(mutation.find("deleted_at")!=std::string::npos){cache(b,"docs/");b.db().exec("UPDATE pages SET deleted_at=NULL WHERE id=1");check(context::read(b,"alpha",uri("docs/"))["page_count"]==1,"restore makes cached empty visible");}
 }
}
void literal_paths(){
 Brain b;setup(b);page(b,1,"alpha","a_b/中文😀/leaf");page(b,2,"alpha","axb/file");page(b,3,"alpha","A_b/file");page(b,4,"alpha","a_b-neighbor/file");
 for(const auto& p:{"","a_b/","a_b/中文😀/","axb/","A_b/","a_b-neighbor/"})cache(b,p);
 b.db().exec("UPDATE pages SET title='new' WHERE id=1");
 for(const auto& p:{"","a_b/","a_b/中文😀/"})check(context::read(b,"alpha",uri(p))["cache_status"]=="stale","literal Unicode ancestor invalidation");
 for(const auto& p:{"axb/","A_b/","a_b-neighbor/"})check(context::read(b,"alpha",uri(p))["cache_status"]=="fresh","underscore/case/neighbor not wildcard");
}
void replacement(){
 for(const auto& sql:std::vector<std::string>{
  "INSERT OR REPLACE INTO pages(id,source_id,slug,title,body,type) VALUES(1,'beta','other/new','new','NEW','note')",
  "INSERT OR REPLACE INTO pages(id,source_id,slug,title,body,type) VALUES(9,'alpha','docs/a','new','NEW','skill')",
  "UPDATE OR REPLACE pages SET source_id='alpha',slug='docs/a' WHERE id=2"}){
  Brain b;setup(b);page(b,1,"alpha","docs/a","skill");page(b,2,"beta","other/two");
  // The third mutation removes the skill-page conflict victim, whose namespace
  // differs from both OLD and NEW of the updated note. DELETE trigger is suppressed.
  if(sql.find("VALUES(9")!=std::string::npos)b.db().exec("UPDATE pages SET type='note' WHERE id=1");
  for(const auto& source:{"alpha","beta"})for(const auto& space:{"skills","resources"})for(const auto& path:{"docs/","other/"})cache(b,path,source,space);
  b.db().exec("PRAGMA recursive_triggers=OFF");b.db().exec(sql);
  if(sql.find("VALUES(9")!=std::string::npos)check(context::read(b,"alpha",uri("docs/"))["page_count"]==0,"REPLACE changed namespace erases old note");
  else check(context::read(b,"alpha",uri("docs/","alpha","skills"))["page_count"]==0,"REPLACE clears displaced skill page");
  check(context::read(b,"beta",uri("docs/","beta"))["cache_status"]=="fresh","REPLACE keeps unrelated cache");
 }
}
void old_upgrade(){
 Brain b;setup(b);page(b,1,"alpha","docs/a");page(b,2,"alpha","other/b");legacy(b);
 const auto old=scalar(b,"SELECT sql FROM sqlite_master WHERE name='ctx_page_insert'");
 context::read(b,"alpha",uri("docs/"));check(scalar(b,"SELECT sql FROM sqlite_master WHERE name='ctx_page_insert'")==old,"read does not upgrade legacy");
 rejects([&]{context::summary(b,"alpha",uri("docs/"),"model");},"external_summary_denied");
 check(scalar(b,"SELECT sql FROM sqlite_master WHERE name='ctx_page_insert'")==old,"denied model leaves legacy DDL unchanged");
 b.save_config_value("context.external_summary","allow",false);
 auto change=[&](const auto&,int){b.db().exec("UPDATE pages SET body='after' WHERE id=1");ai::ChatResult r;r.ok=true;r.content=R"({"l0":"x","l1":"x"})";return r;};
 rejects([&]{context::summary(b,"alpha",uri("docs/"),"model",change);},"evidence_changed");
 check(scalar(b,"SELECT sql FROM sqlite_master WHERE name='ctx_page_insert'")==old,"late evidence cannot publish schema upgrade");
 cache(b,"docs/");check(scalar(b,"SELECT sql FROM sqlite_master WHERE name='ctx_page_insert'")!=old,"explicit successful summary upgrades legacy");
 cache(b,"other/");b.db().exec("UPDATE pages SET body='new' WHERE id=1");check(context::read(b,"alpha",uri("other/"))["cache_status"]=="fresh","legacy upgrade has scoped policy");
 b.db().exec("DROP TRIGGER ctx_page_insert;CREATE TRIGGER ctx_page_insert AFTER INSERT ON pages BEGIN SELECT 1; END;");
 J saved=rows(b);const auto unknown=scalar(b,"SELECT sql FROM sqlite_master WHERE name='ctx_page_insert'");
 rejects([&]{cache(b,"docs/");},"context_schema_incomplete");
 rejects([&]{context::read(b,"alpha",uri("docs/"));},"context_schema_incomplete");
 check(saved==rows(b)&&scalar(b,"SELECT sql FROM sqlite_master WHERE name='ctx_page_insert'")==unknown,"unknown trigger not overwritten");
}
void atomic_upgrade_and_cap(){
 Brain b;setup(b);page(b,1,"alpha","docs/a");legacy(b);
 b.db().exec("INSERT INTO context_cache VALUES('alpha','qbrain://alpha/resources/docs/','old','OLD','OLD PRIVATE','[]',1,'model',0,0)");
 const J before=rows(b);const auto ddl=scalar(b,"SELECT group_concat(sql,'|') FROM sqlite_master WHERE name LIKE 'ctx_page_%' ORDER BY name");
 b.db().exec("CREATE TEMP TRIGGER reject_publication BEFORE INSERT ON main.context_cache BEGIN SELECT RAISE(ABORT,'synthetic publish refusal'); END");
 bool failed=false;try{cache(b,"docs/");}catch(const std::exception&){failed=true;}
 check(failed,"synthetic cache publication aborted");
 check(rows(b)==before&&scalar(b,"SELECT group_concat(sql,'|') FROM sqlite_master WHERE name LIKE 'ctx_page_%' ORDER BY name")==ddl,"trigger migration and legacy wipe roll back with publish failure");
 b.db().exec("DROP TRIGGER temp.reject_publication");cache(b,"docs/");
 check(context::read(b,"alpha",uri("docs/"))["cache_status"]=="fresh","retry after failed migration valid");
 for(int i=0;i<257;++i)page(b,1000+i,"alpha","cap/x"+std::to_string(1000+i));
 cache(b,"cap/");auto prior=context::read(b,"alpha",uri("cap/"));check(prior["page_count"]==256&&prior["truncated"]==true,"bounded directory baseline");
 page(b,2000,"alpha","cap/first");auto now=context::read(b,"alpha",uri("cap/"));
 check(now["cache_status"]=="stale"&&now["revision"]!=prior["revision"],"new page outside old references still invalidates capped ancestor");
}

void model_preservation(){
 Brain b;setup(b);page(b,1,"alpha","left/a");page(b,2,"alpha","right/b");b.save_config_value("context.external_summary","allow",false);int calls=0;
 auto model=[&](const auto&,int){++calls;ai::ChatResult r;r.ok=true;r.content=R"({"l0":"Synthetic","l1":"Unchanged synthetic model summary"})";return r;};
 context::summary(b,"alpha",uri("right/"),"model",model);auto before=context::read(b,"alpha",uri("right/"),"L1");
 b.db().exec("UPDATE pages SET body='other text' WHERE id=1");
 check(context::read(b,"alpha",uri("right/"),"L1")==before&&calls==1,"unrelated edit preserves model summary without another provider call");
}
}
int main(){try{selectivity();transitions();literal_paths();replacement();old_upgrade();atomic_upgrade_and_cap();model_preservation();
 std::cout<<J({{"schema","qbrain-n48t-native-v1"},{"passed",true},{"checks",evidence},{"check_count",evidence.size()},{"real_model_calls",0},{"postgres_executed",false}}).dump()<<'\n';return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';std::cout<<J({{"schema","qbrain-n48t-native-v1"},{"passed",false},{"checks",evidence}}).dump()<<'\n';return 1;}}
