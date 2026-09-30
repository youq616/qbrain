#pragma once
// N48Q: fact-local PostgreSQL dialect and owned transactions. No raw PG handles.
// Shared by FactStore and explicit-use receipts; never a global SQL rewriter.
#include "qbrain/memory/session_memory.hpp"
#include <algorithm>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <vector>

namespace qbrain::memory::pg_fact {
using DB=storage::Database;
inline bool enabled(DB& db){return db.backend_kind()==storage::BackendKind::postgres;}
inline void require(bool ok,const char* code){if(!ok)throw Error(code);}
// Only our live RAII scopes are borrowable. A same-thread caller BEGIN is not.
// Each thread still needs a separate Brain/Database, as required by FactStore.
inline thread_local std::vector<DB*> owned_connections;
inline bool owned(DB& db){return std::find(owned_connections.begin(),owned_connections.end(),&db)!=owned_connections.end();}
inline void remove_owner(DB& db) noexcept {
  auto it=std::find(owned_connections.begin(),owned_connections.end(),&db);
  if(it!=owned_connections.end())owned_connections.erase(it);
}
inline void namespace_check(DB& db){
  auto s=db.prepare("SELECT pg_catalog.current_schema(),pg_catalog.current_setting('server_encoding'),"
    "pg_catalog.current_setting('client_encoding'),pg_catalog.current_setting('session_replication_role')");
  require(s.step() && s.column_text(0)=="public" && s.column_text(1)=="UTF8" &&
    s.column_text(2)=="UTF8" && s.column_text(3)=="origin","fact_pg_schema_context");
  auto names=db.prepare("SELECT count(*) FROM (VALUES ('sources'),('pages'),('config'),"
    "('memory_module'),('memory_events'),('memory_items'),('memory_attempts'),"
    "('memory_fact_module'),('memory_facts'),('memory_fact_evidence'),('memory_fact_relations'),"
    "('memory_fact_lifecycle_module'),('memory_fact_archive'),('memory_fact_usage_module'),('memory_fact_usage')) n(name) "
    "WHERE pg_catalog.to_regclass(name) IS DISTINCT FROM pg_catalog.to_regclass('public.' || name)");
  require(names.step() && names.column_int(0)==0,"fact_pg_schema_context");
}
inline void validate_context(DB& db){
  if(!enabled(db))return;
  require(!db.transaction_active() || owned(db),"fact_transaction_active");
  require(!owned(db) || db.transaction_active(),"fact_transaction_lost");
  namespace_check(db);
}
inline void idle(DB& db){require(!db.transaction_active() && !owned(db),"fact_transaction_active");}
struct ReadScope {
  DB& db;bool owner=false;
  explicit ReadScope(DB& d):db(d){
    if(!enabled(db))return;
    if(owned(db)){validate_context(db);return;}
    idle(db);owned_connections.push_back(&db);owner=true;
    try{db.exec("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY");namespace_check(db);}
    catch(...){try{db.exec("ROLLBACK");}catch(...){}remove_owner(db);owner=false;throw;}
  }
  ~ReadScope(){if(owner){try{db.exec("ROLLBACK");}catch(...){}remove_owner(db);}}
  ReadScope(const ReadScope&)=delete;ReadScope& operator=(const ReadScope&)=delete;
};
inline bool exists(DB& db,const char* name,const char* type="table"){
  auto s=db.prepare("SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
    "WHERE n.nspname='public' AND c.relname=? AND c.relkind=?::\"char\"");
  s.bind_text(1,name);s.bind_text(2,std::string(type)=="index"?"i":"r");return s.step();
}
struct WriteScope {
  DB& db;bool owner=false;
  explicit WriteScope(DB& d):db(d){
    idle(db);namespace_check(db);owned_connections.push_back(&db);owner=true;
    try{
      db.exec("BEGIN ISOLATION LEVEL READ COMMITTED");
      db.exec("SET LOCAL lock_timeout='2500ms'");
      db.exec("LOCK TABLE public.sources,public.pages,public.config IN SHARE ROW EXCLUSIVE MODE");
      // Also exclude direct SQL writers of supporting rows; use the same order
      // after the shared core locks as every other fact writer. No provider call.
      for(const auto* name:{"memory_module","memory_events","memory_items","memory_attempts",
          "memory_fact_module","memory_facts","memory_fact_evidence","memory_fact_relations",
          "memory_fact_lifecycle_module","memory_fact_archive","memory_fact_usage_module","memory_fact_usage"})
        if(exists(db,name))db.exec(std::string("LOCK TABLE public.")+name+" IN SHARE ROW EXCLUSIVE MODE");
      namespace_check(db);
    }catch(...){try{db.exec("ROLLBACK");}catch(...){}remove_owner(db);owner=false;throw;}
  }
  void commit(){require(owner,"fact_transaction_lost");db.exec("COMMIT");remove_owner(db);owner=false;}
  ~WriteScope(){if(owner){try{db.exec("ROLLBACK");}catch(...){}remove_owner(db);}}
  WriteScope(const WriteScope&)=delete;WriteScope& operator=(const WriteScope&)=delete;
};
inline void replace_all(std::string& text,const std::string& from,const std::string& to){
  std::size_t at=0;while((at=text.find(from,at))!=std::string::npos){text.replace(at,from.size(),to);at+=to.size();}
}
inline std::string sql(DB& db,std::string text){
  if(!enabled(db))return text;
  // These expressions occur only in fixed fact-module SQL. Values stay bound.
  for(const auto* value:{"m.quote","p.body","a.object","b.object","f.object","object","fact_id","usage_id"})
    replace_all(text,std::string("length(CAST(")+value+" AS BLOB))",std::string("pg_catalog.octet_length(")+value+")");
  for(const auto* value:{"archived_at","created_at","f.revision","revision","version","fact_revision","reported_at","withdrawn_at","usage_id","fact_id","source_id"}){
    const std::string v=value;
    replace_all(text,"typeof("+v+")","(CASE WHEN "+v+" IS NULL THEN 'null' WHEN pg_catalog.pg_typeof("+v+")='pg_catalog.int8'::regtype THEN 'integer' WHEN pg_catalog.pg_typeof("+v+")='pg_catalog.text'::regtype THEN 'text' ELSE 'invalid' END)");
  }
  replace_all(text,"COLLATE BINARY","COLLATE \"C\"");
  replace_all(text,"instr(lower(object),lower(?))>0",
    "pg_catalog.strpos(pg_catalog.translate(object,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),pg_catalog.translate(?,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'))>0");
  require(text.find(" AS BLOB")==std::string::npos &&
    text.find("sqlite_master")==std::string::npos && text.find("PRAGMA")==std::string::npos,"fact_pg_sql_contract");
  return text;
}
inline DB::Statement prepare(DB& db,std::string text){return db.prepare(sql(db,std::move(text)));}

inline std::string quoted_names(const std::vector<std::string>& names){
  std::string s;for(const auto& name:names){if(!s.empty())s+=",";s+="'"+name+"'";}return s;
}
// Recognition of this bounded module schema, not hostile-owner DDL attestation.
// All names/layouts below are constants; no user identifier is interpolated.
inline bool layout(DB& db,const std::vector<std::string>& names,
    const std::map<std::string,std::string>& wanted,const std::set<std::string>& nullable,
    const char* conflict,const char* incomplete){
  const auto list=quoted_names(names);
  auto rels=db.prepare("SELECT c.relname,c.relkind FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname IN ("+list+")");
  std::set<std::string> found;
  while(rels.step()){require(rels.column_text(1)=="r",conflict);found.insert(rels.column_text(0));}
  if(found.empty())return false;
  require(found==std::set<std::string>(names.begin(),names.end()),incomplete);
  auto s=db.prepare("SELECT c.relname,a.attname,pg_catalog.format_type(a.atttypid,a.atttypmod),a.attnotnull,"
    "a.attcollation='pg_catalog.\"C\"'::regcollation,a.attidentity,a.attgenerated "
    "FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid "
    "WHERE n.nspname='public' AND a.attnum>0 AND NOT a.attisdropped AND c.relname IN ("+list+")");
  std::map<std::string,std::string> actual;
  while(s.step()){
    const auto key=s.column_text(0)+"."+s.column_text(1),type=s.column_text(2);
    require(s.column_text(3)==(nullable.count(key)?"f":"t") && s.column_text(5).empty() && s.column_text(6).empty(),incomplete);
    if(type=="text")require(s.column_text(4)=="t",incomplete);
    actual.emplace(key,type);
  }
  require(actual==wanted,incomplete);
  auto v=db.prepare("SELECT version FROM public."+names.front());
  require(v.step() && v.column_int(0)==1 && !v.step(),incomplete);
  return true;
}
inline void keys(DB& db,const char* table,const std::set<std::string>& expected,int checks,const char* error){
  auto s=db.prepare("SELECT c.contype,pg_catalog.array_to_string(c.conkey,','),rn.nspname,r.relname,"
    "pg_catalog.array_to_string(c.confkey,','),c.confdeltype,c.convalidated,c.condeferrable "
    "FROM pg_catalog.pg_constraint c LEFT JOIN pg_catalog.pg_class r ON r.oid=c.confrelid "
    "LEFT JOIN pg_catalog.pg_namespace rn ON rn.oid=r.relnamespace WHERE c.conrelid=pg_catalog.to_regclass(?)");
  s.bind_text(1,std::string("public.")+table);std::set<std::string> actual;int check_count=0;
  while(s.step()){
    require(s.column_text(6)=="t" && s.column_text(7)=="f",error);
    const auto type=s.column_text(0);
    if(type=="c"){++check_count;continue;}
    std::string item=type+":"+s.column_text(1);
    if(type=="f")item+=":"+s.column_text(2)+"."+s.column_text(3)+":"+s.column_text(4)+":"+s.column_text(5);
    require(actual.insert(item).second,error);
  }
  require(actual==expected && check_count==checks,error);
}
inline void index(DB& db,const char* name,const char* table,const char* columns,const char* error){
  auto s=db.prepare("SELECT i.indisvalid,i.indisready,i.indkey::text,i.indexprs IS NULL,i.indpred IS NULL "
    "FROM pg_catalog.pg_index i WHERE i.indexrelid=pg_catalog.to_regclass(?) AND i.indrelid=pg_catalog.to_regclass(?)");
  s.bind_text(1,std::string("public.")+name);s.bind_text(2,std::string("public.")+table);
  require(s.step() && s.column_text(0)=="t" && s.column_text(1)=="t" && s.column_text(2)==columns && s.column_text(3)=="t" && s.column_text(4)=="t" && !s.step(),error);
}
inline constexpr const char* cleanup_body=R"SQL(
BEGIN
 IF TG_OP = 'TRUNCATE' THEN
  DELETE FROM public.memory_facts f WHERE NOT EXISTS(SELECT 1 FROM public.memory_fact_evidence e WHERE e.fact_id=f.fact_id AND e.source_id=f.source_id);
 ELSE
  UPDATE public.memory_facts f SET revision=LEAST(f.revision+1,2147483647),
   updated_at=GREATEST(f.updated_at,FLOOR(EXTRACT(EPOCH FROM pg_catalog.clock_timestamp()))::BIGINT)
   WHERE f.fact_id=OLD.fact_id AND f.source_id=OLD.source_id
   AND EXISTS(SELECT 1 FROM public.memory_fact_evidence e WHERE e.fact_id=f.fact_id AND e.source_id=f.source_id);
  DELETE FROM public.memory_facts f WHERE f.fact_id=OLD.fact_id AND f.source_id=OLD.source_id
   AND NOT EXISTS(SELECT 1 FROM public.memory_fact_evidence e WHERE e.fact_id=f.fact_id AND e.source_id=f.source_id);
 END IF;
 RETURN NULL;
END;
)SQL";
inline bool cleanup(DB& db,bool present){
  auto f=db.prepare("SELECT p.oid,p.prosrc,p.prosecdef,p.pronargs,p.prorettype='pg_catalog.trigger'::regtype,l.lanname,pg_catalog.array_to_string(p.proconfig,',') "
    "FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace JOIN pg_catalog.pg_language l ON l.oid=p.prolang "
    "WHERE n.nspname='public' AND p.proname='qbrain_fact_evidence_gc_v1'");
  const bool found=f.step();
  if(!present){require(!found,"fact_schema_conflict");return false;}
  require(found && f.column_text(1)==cleanup_body && f.column_text(2)=="f" && f.column_int(3)==0 &&
    f.column_text(4)=="t" && f.column_text(5)=="plpgsql" && f.column_text(6)=="search_path=pg_catalog","fact_schema_incomplete");
  const auto oid=f.column_int(0);require(!f.step(),"fact_schema_incomplete");
  auto t=db.prepare("SELECT tgname,tgtype,tgenabled,tgfoid,tgnargs,tgqual IS NULL,tgattr::text,tgconstraint "
    "FROM pg_catalog.pg_trigger WHERE tgrelid='public.memory_fact_evidence'::regclass AND NOT tgisinternal "
    "AND tgname IN ('memory_fact_last_evidence','memory_fact_all_evidence')");
  std::map<std::string,int64_t> triggers;
  while(t.step()){
    require(t.column_text(2)=="O" && t.column_int(3)==oid && t.column_int(4)==0 && t.column_text(5)=="t" && t.column_text(6).empty() && t.column_int(7)==0,"fact_schema_incomplete");
    triggers.emplace(t.column_text(0),t.column_int(1));
  }
  require(triggers==std::map<std::string,int64_t>{{"memory_fact_last_evidence",9},{"memory_fact_all_evidence",32}},"fact_schema_incomplete");return true;
}
inline bool ready(DB& db){
  const bool present=layout(db,{"memory_fact_module","memory_facts","memory_fact_evidence","memory_fact_relations"},{
    {"memory_fact_module.version","bigint"},{"memory_facts.fact_id","text"},{"memory_facts.source_id","text"},
    {"memory_facts.subject","text"},{"memory_facts.predicate","text"},{"memory_facts.object","text"},{"memory_facts.status","text"},
    {"memory_facts.revision","bigint"},{"memory_facts.created_at","bigint"},{"memory_facts.updated_at","bigint"},
    {"memory_fact_evidence.fact_id","text"},{"memory_fact_evidence.source_id","text"},{"memory_fact_evidence.item_id","text"},
    {"memory_fact_evidence.quote_hash","text"},{"memory_fact_evidence.payload_hash","text"},{"memory_fact_evidence.created_at","bigint"},
    {"memory_fact_relations.source_id","text"},{"memory_fact_relations.from_id","text"},{"memory_fact_relations.to_id","text"},
    {"memory_fact_relations.relation","text"},{"memory_fact_relations.created_at","bigint"}}, {},"fact_schema_conflict","fact_schema_incomplete");
  if(!cleanup(db,present))return false;
  keys(db,"memory_fact_module",{"p:1"},1,"fact_schema_incomplete");
  keys(db,"memory_facts",{"p:1","u:1,2","f:2:public.sources:1:c"},3,"fact_schema_incomplete");
  keys(db,"memory_fact_evidence",{"p:1,3","f:3:public.memory_items:1:c","f:1,2:public.memory_facts:1,2:c"},0,"fact_schema_incomplete");
  keys(db,"memory_fact_relations",{"p:2,3,4","f:2,1:public.memory_facts:1,2:c","f:3,1:public.memory_facts:1,2:c"},2,"fact_schema_incomplete");
  index(db,"idx_memory_facts_source","memory_facts","2 6 4 8 1","fact_schema_incomplete");
  index(db,"idx_memory_fact_evidence_item","memory_fact_evidence","3","fact_schema_incomplete");
  index(db,"idx_memory_fact_relations_to","memory_fact_relations","3","fact_schema_incomplete");
  return true;
}
inline bool archive_ready(DB& db){
  if(!layout(db,{"memory_fact_lifecycle_module","memory_fact_archive"},{
    {"memory_fact_lifecycle_module.version","bigint"},{"memory_fact_archive.fact_id","text"},
    {"memory_fact_archive.source_id","text"},{"memory_fact_archive.archived_at","bigint"}}, {},
    "fact_lifecycle_schema_conflict","fact_lifecycle_schema_incomplete"))return false;
  keys(db,"memory_fact_lifecycle_module",{"p:1"},1,"fact_lifecycle_schema_incomplete");
  keys(db,"memory_fact_archive",{"p:1","f:1,2:public.memory_facts:1,2:c"},1,"fact_lifecycle_schema_incomplete");
  index(db,"idx_memory_fact_archive_source","memory_fact_archive","2 1","fact_lifecycle_schema_incomplete");return true;
}
inline bool usage_ready(DB& db){
  if(!layout(db,{"memory_fact_usage_module","memory_fact_usage"},{
    {"memory_fact_usage_module.version","bigint"},{"memory_fact_usage.source_id","text"},{"memory_fact_usage.usage_id","text"},
    {"memory_fact_usage.fact_id","text"},{"memory_fact_usage.fact_revision","bigint"},{"memory_fact_usage.reported_at","bigint"},
    {"memory_fact_usage.withdrawn_at","bigint"}}, {"memory_fact_usage.withdrawn_at"},
    "fact_usage_schema_conflict","fact_usage_schema_incomplete"))return false;
  keys(db,"memory_fact_usage_module",{"p:1"},1,"fact_usage_schema_incomplete");
  keys(db,"memory_fact_usage",{"p:1,2","f:3,1:public.memory_facts:1,2:c"},3,"fact_usage_schema_incomplete");
  index(db,"idx_memory_fact_usage_fact","memory_fact_usage","1 3 2","fact_usage_schema_incomplete");return true;
}
inline void create(DB& db){
  db.exec(R"SQL(
CREATE TABLE public.memory_fact_module(version BIGINT PRIMARY KEY CHECK(version=1));
INSERT INTO public.memory_fact_module VALUES(1);
CREATE TABLE public.memory_facts(
 fact_id TEXT COLLATE "C" PRIMARY KEY,source_id TEXT COLLATE "C" NOT NULL REFERENCES public.sources(id) ON DELETE CASCADE,
 subject TEXT COLLATE "C" NOT NULL CHECK(subject='user'),predicate TEXT COLLATE "C" NOT NULL,object TEXT COLLATE "C" NOT NULL,
 status TEXT COLLATE "C" NOT NULL DEFAULT 'active' CHECK(status IN ('active','superseded','retracted')),
 revision BIGINT NOT NULL DEFAULT 1 CHECK(revision BETWEEN 1 AND 2147483647),
 created_at BIGINT NOT NULL,updated_at BIGINT NOT NULL,UNIQUE(fact_id,source_id));
CREATE TABLE public.memory_fact_evidence(
 fact_id TEXT COLLATE "C" NOT NULL,source_id TEXT COLLATE "C" NOT NULL,
 item_id TEXT COLLATE "C" NOT NULL REFERENCES public.memory_items(item_id) ON DELETE CASCADE,
 quote_hash TEXT COLLATE "C" NOT NULL,payload_hash TEXT COLLATE "C" NOT NULL,created_at BIGINT NOT NULL,
 PRIMARY KEY(fact_id,item_id),FOREIGN KEY(fact_id,source_id) REFERENCES public.memory_facts(fact_id,source_id) ON DELETE CASCADE);
CREATE TABLE public.memory_fact_relations(
 source_id TEXT COLLATE "C" NOT NULL,from_id TEXT COLLATE "C" NOT NULL,to_id TEXT COLLATE "C" NOT NULL,
 relation TEXT COLLATE "C" NOT NULL CHECK(relation IN ('superseded_by','contradicts')),
 created_at BIGINT NOT NULL,CHECK(from_id<>to_id),PRIMARY KEY(from_id,to_id,relation),
 FOREIGN KEY(from_id,source_id) REFERENCES public.memory_facts(fact_id,source_id) ON DELETE CASCADE,
 FOREIGN KEY(to_id,source_id) REFERENCES public.memory_facts(fact_id,source_id) ON DELETE CASCADE);
CREATE INDEX idx_memory_facts_source ON public.memory_facts(source_id,status,predicate,created_at,fact_id);
CREATE INDEX idx_memory_fact_evidence_item ON public.memory_fact_evidence(item_id);
CREATE INDEX idx_memory_fact_relations_to ON public.memory_fact_relations(to_id);
)SQL");
  db.exec(std::string("CREATE FUNCTION public.qbrain_fact_evidence_gc_v1() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $qbrain$")+cleanup_body+"$qbrain$");
  db.exec("CREATE TRIGGER memory_fact_last_evidence AFTER DELETE ON public.memory_fact_evidence FOR EACH ROW EXECUTE FUNCTION public.qbrain_fact_evidence_gc_v1();"
    "CREATE TRIGGER memory_fact_all_evidence AFTER TRUNCATE ON public.memory_fact_evidence FOR EACH STATEMENT EXECUTE FUNCTION public.qbrain_fact_evidence_gc_v1()");
  require(ready(db),"fact_schema_incomplete");
}
inline void create_archive(DB& db){
  db.exec(R"SQL(
CREATE TABLE public.memory_fact_lifecycle_module(version BIGINT PRIMARY KEY CHECK(version=1));
INSERT INTO public.memory_fact_lifecycle_module VALUES(1);
CREATE TABLE public.memory_fact_archive(fact_id TEXT COLLATE "C" PRIMARY KEY,source_id TEXT COLLATE "C" NOT NULL,
 archived_at BIGINT NOT NULL CHECK(archived_at>=0),
 FOREIGN KEY(fact_id,source_id) REFERENCES public.memory_facts(fact_id,source_id) ON DELETE CASCADE);
CREATE INDEX idx_memory_fact_archive_source ON public.memory_fact_archive(source_id,fact_id);
)SQL");require(archive_ready(db),"fact_lifecycle_schema_incomplete");
}
inline void create_usage(DB& db){
  db.exec(R"SQL(
CREATE TABLE public.memory_fact_usage_module(version BIGINT PRIMARY KEY CHECK(version=1));
INSERT INTO public.memory_fact_usage_module VALUES(1);
CREATE TABLE public.memory_fact_usage(
 source_id TEXT COLLATE "C" NOT NULL,usage_id TEXT COLLATE "C" NOT NULL,fact_id TEXT COLLATE "C" NOT NULL,
 fact_revision BIGINT NOT NULL CHECK(fact_revision BETWEEN 1 AND 2147483647),reported_at BIGINT NOT NULL CHECK(reported_at>=0),
 withdrawn_at BIGINT CHECK(withdrawn_at IS NULL OR withdrawn_at>=reported_at),PRIMARY KEY(source_id,usage_id),
 FOREIGN KEY(fact_id,source_id) REFERENCES public.memory_facts(fact_id,source_id) ON DELETE CASCADE);
CREATE INDEX idx_memory_fact_usage_fact ON public.memory_fact_usage(source_id,fact_id,usage_id);
)SQL");require(usage_ready(db),"fact_usage_schema_incomplete");
}
} // namespace qbrain::memory::pg_fact
