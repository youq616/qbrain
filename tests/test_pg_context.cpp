// N48P: actual PostgreSQL + SQLite differential context and publication tests.
#include "qbrain/context/context.hpp"
#include "qbrain/context/pg_context.hpp"
#include "qbrain/mcp/server.hpp"
#include "qbrain/ops/registry.hpp"
#include <atomic>
#include <chrono>
#include <cstdlib>
#include <future>
#include <iostream>
#include <memory>
#include <thread>
using namespace qbrain;
using J=nlohmann::json;
namespace {
J checks=J::array(); std::string dsn,backend;
void check(bool ok,const std::string& name) {
  checks.push_back({{"name",backend+":"+name},{"passed",ok}});
  if(!ok)throw std::runtime_error(name);
}
template<class F>void reject(F f,const std::string& code) {
  try{f();}catch(const memory::Error& e){check(std::string(e.what())==code,"reject:"+code);return;}
  throw std::runtime_error("accepted:"+code);
}
std::string text(Brain& b,const std::string& sql){auto s=b.db().prepare(sql);if(!s.step())throw std::runtime_error("missing scalar");return s.column_text(0);}
int64_t number(Brain& b,const std::string& sql){auto s=b.db().prepare(sql);if(!s.step())throw std::runtime_error("missing number");return s.column_int(0);}
bool postgres(Brain& b){return b.db().backend_kind()==storage::BackendKind::postgres;}
std::unique_ptr<Brain> worker(){auto b=std::make_unique<Brain>();b->open_pg(dsn);return b;}
void reset(Brain& b) {
  if(postgres(b)) {
    check(text(b,"SELECT current_database()") == "qbrain_n48p_native","disposable-database-name");
    b.db().exec("DROP TABLE IF EXISTS public.context_cache,public.context_module CASCADE;"
                "DROP FUNCTION IF EXISTS public.qbrain_context_invalidate_v1() CASCADE");
  } else b.db().exec("DROP TRIGGER IF EXISTS ctx_page_insert; DROP TRIGGER IF EXISTS ctx_page_update;"
                    "DROP TRIGGER IF EXISTS ctx_page_delete; DROP TABLE IF EXISTS context_cache");
  b.db().exec("DELETE FROM pages; DELETE FROM config");
  b.ensure_source("alpha");b.ensure_source("beta");
  b.save_config_value("embed.auto","false",false);
}
void page(Brain& b,int64_t id,const std::string& source,const std::string& slug,
          const std::string& body,const std::string& type="note") {
  auto s=b.db().prepare(std::string("INSERT INTO pages(id,source_id,slug,title,body,type) ")+
    (postgres(b)?"OVERRIDING SYSTEM VALUE ":"")+"VALUES(?,?,?,?,?,?)");
  s.bind_int(1,id);s.bind_text(2,source);s.bind_text(3,slug);s.bind_text(4,slug);s.bind_text(5,body);s.bind_text(6,type);s.step_done();
}
int64_t optional_count(Brain& b) {
  return number(b,postgres(b)?"SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname IN ('context_cache','context_module')":
    "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='context_cache'");
}
const std::string uri="qbrain://alpha/resources/docs/";
ai::ChatResult answer(){ai::ChatResult r;r.ok=true;r.content=R"({"l0":"Generated 中文","l1":"Synthetic summary; not authoritative."})";r.input_tokens=21;r.output_tokens=8;return r;}
J shared(Brain& b) {
  reset(b);std::string body;
  for(int i=0;i<80;++i)body+="Alpha 中文😀 CRLF\r\n \"quoted\" ";
  page(b,100,"alpha","docs/a",body);page(b,200,"beta","docs/a","PRIVATE_BETA");
  page(b,300,"alpha","docs/tool","SKILL_PRIVATE","skill");
  page(b,400,"alpha","docs/session","SESSION_PRIVATE","session_fragment");
  J observed=J::object();
  observed["root"]=context::read(b,"alpha","");
  observed["uncached"]=context::read(b,"alpha",uri,"L1",2048);
  check(observed["uncached"]["page_count"]==1 && observed["uncached"]["cache_status"]=="missing","uncached-one-page");
  check(observed["uncached"].dump().find("PRIVATE")==std::string::npos,"source-and-namespace-filter");
  check(optional_count(b)==0,"read-no-optional-ddl");
  for(const auto* invalid:{"qbrain://beta/resources/docs/","qbrain://alpha/resources/../","qbrain://alpha/resources/a%2fb/",
                          "qbrain://alpha/resources//","qbrain://alpha/nope/","qbrain://alpha/resources/a\\b/"}) {
    bool bad=false;try{context::read(b,"alpha",invalid);}catch(...){bad=true;}check(bad,"invalid-uri");
  }
  reject([&]{context::read(b,"alpha",uri,"L2");},"directory_requires_preview");
  reject([&]{context::read(b,"alpha",uri,"L1",511);},"invalid_read_budget");
  reject([&]{context::read(b,"alpha",uri,"L4");},"invalid_layer");
  reject([&]{context::read(b,"alpha",uri+"missing","L2");},"page_not_found");
  J chunks=J::array();std::string reconstructed,rev;int64_t offset=0;
  for(int i=0;i<80;++i) {
    auto r=context::read(b,"alpha",uri+"a","L2",512,offset,rev);
    check(r.dump().size()<=512,"bounded-pagination");chunks.push_back(r);
    reconstructed+=r["content"].get<std::string>();rev=r["revision"];
    if(r["next_offset"].is_null())break;
    check(r["next_offset"].get<int64_t>()>offset,"advancing-pagination");offset=r["next_offset"];
  }
  check(reconstructed==body,"raw-byte-exact-roundtrip");observed["pages"]=chunks;
  reject([&]{context::read(b,"alpha",uri+"a","L2",512,7,rev);},"stale_or_invalid_cursor");
  reject([&]{context::read(b,"alpha",uri+"a","L2",512,1);},"stale_or_invalid_cursor");
  check(context::read(b,"alpha",uri+"a","L2",512,body.size(),rev)["content"]=="","end-cursor");
  int calls=0;
  auto provider=[&](const auto& req,int timeout){++calls;check(!b.db().transaction_active(),"provider-outside-transaction");
    check(timeout==30000 && req.size()==2 && req[1].content.find("PRIVATE")==std::string::npos,"provider-scope-and-timeout");return answer();};
  reject([&]{context::summary(b,"alpha",uri,"model",provider);},"external_summary_denied");
  check(calls==0 && optional_count(b)==0,"denied-provider-no-ddl");
  observed["summary"]=context::summary(b,"alpha",uri);
  observed["fresh"]=context::read(b,"alpha",uri,"L1",2048);
  check(observed["fresh"]["cache_status"]=="fresh" && observed["fresh"]["method"]=="extractive","fresh-extractive");
  context::summary(b,"beta","qbrain://beta/resources/docs/");
  b.db().exec("UPDATE pages SET body='NEW 中文😀 BODY' WHERE id=100");
  check(text(b,"SELECT l0 || l1 || refs_json FROM context_cache WHERE source_id='alpha'")=="[]","changed-text-cleared");
  check(number(b,"SELECT dirty FROM context_cache WHERE source_id='beta'")==0,"unrelated-source-cache-fresh");
  observed["stale"]=context::read(b,"alpha",uri,"L1");
  check(observed["stale"]["cache_status"]=="stale" && observed["stale"]["content"].get<std::string>().find("NEW")!=std::string::npos,"stale-fallback");
  reject([&]{context::read(b,"alpha",uri+"a","L2",512,1,rev);},"stale_or_invalid_cursor");
  b.save_config_value("context.external_summary","allow",false);
  observed["model-summary"]=context::summary(b,"alpha",uri,"model",provider);
  observed["model-read"]=context::read(b,"alpha",uri,"L1");
  check(observed["model-read"]["content"]=="Synthetic summary; not authoritative." && observed["model-read"]["method"]=="model","model-tagged");
  b.db().exec("UPDATE pages SET source_id='beta',slug='docs/moved' WHERE id=100");
  check(number(b,"SELECT SUM(dirty) FROM context_cache")==2,"move-invalidates-both-sources");
  check(context::read(b,"alpha",uri)["page_count"]==0,"moved-source-empty");
  page(b,500,"alpha","docs/new","inserted");context::summary(b,"alpha",uri);
  page(b,600,"alpha","docs/new2","second");check(number(b,"SELECT dirty FROM context_cache WHERE source_id='alpha'")==1,"insert-invalidates");
  context::summary(b,"alpha",uri);b.db().exec("UPDATE pages SET deleted_at=CURRENT_TIMESTAMP WHERE id=500");
  check(context::read(b,"alpha",uri)["page_count"]==1,"soft-delete-invalidates");
  context::summary(b,"alpha",uri);b.db().exec("DELETE FROM pages WHERE id=600");
  check(context::read(b,"alpha",uri)["page_count"]==0,"hard-delete-invalidates");
  page(b,700,"alpha","docs/keep","stable");context::summary(b,"alpha",uri);
  b.db().exec("BEGIN");b.db().exec("UPDATE pages SET body='ROLLED_BACK' WHERE id=700");b.db().exec("ROLLBACK");
  check(context::read(b,"alpha",uri)["cache_status"]=="fresh","rollback-invalidation-rolled-back");
  auto changing=[&](const auto& req,int t){auto r=provider(req,t);b.db().exec("UPDATE pages SET body='AFTER_CALLBACK' WHERE id=700");return r;};
  reject([&]{context::summary(b,"alpha",uri,"model",changing);},"evidence_changed");
  check(context::read(b,"alpha",uri,"L1")["content"].get<std::string>().find("AFTER_CALLBACK")!=std::string::npos,"late-result-not-published");
  auto revoking=[&](const auto& req,int t){auto r=provider(req,t);b.save_config_value("context.external_summary","deny",false);return r;};
  reject([&]{context::summary(b,"alpha",uri,"model",revoking);},"external_summary_denied");
  check(!b.db().transaction_active(),"error-releases-own-transaction");
  observed["final"]=context::read(b,"alpha",uri,"L1");
  return observed;
}
void pg_only(Brain& b) {
  reset(b);page(b,10,"alpha","docs/a","initial");
  for(const auto* table:{"sources","pages","config","context_cache","context_module"}) {
    b.db().exec(std::string("CREATE TEMP TABLE ")+table+"(fake text)");
    reject([&]{context::read(b,"alpha",uri);},"context_pg_schema_context");
    reject([&]{context::summary(b,"alpha",uri);},"context_pg_schema_context");
    check(number(b,"SELECT count(*) FROM public.pages")==1,"shadow-refusal-no-public-write");
    b.db().exec(std::string("DROP TABLE pg_temp.")+table);
  }
  b.db().exec("CREATE TEMP TABLE unrelated(x int)");check(context::read(b,"alpha",uri)["page_count"]==1,"unrelated-temp-allowed");
  b.db().exec("CREATE TEMP TABLE pages(fake text); SET search_path=public,pg_temp");
  check(context::read(b,"alpha",uri)["page_count"]==1,"explicit-public-first-allowed");
  b.db().exec("DROP TABLE pg_temp.pages; RESET search_path");
  b.db().exec("BEGIN");
  reject([&]{context::read(b,"alpha",uri);},"context_transaction_active");
  reject([&]{context::summary(b,"alpha",uri);},"context_transaction_active");
  check(b.db().transaction_active(),"caller-still-owns-transaction");
  try{b.db().exec("SELECT 1/0");}catch(...){}
  reject([&]{context::read(b,"alpha",uri);},"context_transaction_active");b.db().exec("ROLLBACK");
  b.db().exec("SET default_transaction_read_only=on");
  check(context::read(b,"alpha",uri)["page_count"]==1,"readonly-default-read-works");
  b.db().exec("RESET default_transaction_read_only");
  { context::pg::ReadSnapshot snapshot(b.db());
    check(text(b,"SHOW transaction_isolation")=="repeatable read" && text(b,"SHOW transaction_read_only")=="on","actual-read-mode");
    check(text(b,"SELECT body FROM public.pages WHERE id=10")=="initial","snapshot-initial");
    auto other=worker();other->db().exec("UPDATE pages SET body='COMMITTED_LATER' WHERE id=10");
    check(text(b,"SELECT body FROM public.pages WHERE id=10")=="initial","one-fixed-snapshot");
  }
  check(context::read(b,"alpha",uri+"a","L2")["content"]=="COMMITTED_LATER","next-read-observes-commit");
  b.save_config_value("context.external_summary","allow",false);
  auto callback=[&](const auto&,int){
    check(!b.db().transaction_active(),"callback-connection-idle");auto other=worker();
    other->db().exec("UPDATE pages SET body='CONCURRENT_EDIT' WHERE id=10");return answer();};
  reject([&]{context::summary(b,"alpha",uri,"model",callback);},"evidence_changed");
  check(optional_count(b)==0,"changed-evidence-no-optional-ddl");
  auto shadow=[&](const auto&,int){b.db().exec("CREATE TEMP TABLE config(key text,value text)");return answer();};
  reject([&]{context::summary(b,"alpha",uri,"model",shadow);},"context_pg_schema_context");
  check(optional_count(b)==0,"post-callback-shadow-no-ddl");b.db().exec("DROP TABLE pg_temp.config");
  auto caller=[&](const auto&,int){b.db().exec("BEGIN");return answer();};
  reject([&]{context::summary(b,"alpha",uri,"model",caller);},"context_transaction_active");
  check(b.db().transaction_active(),"callback-created-transaction-kept");b.db().exec("ROLLBACK");
  b.db().exec("SET lock_timeout='4321ms'");
  {auto lock=worker();lock->db().exec("BEGIN; LOCK TABLE public.sources IN SHARE ROW EXCLUSIVE MODE");
    bool refused=false;try{context::summary(b,"alpha",uri);}catch(const std::exception& e){refused=std::string(e.what()).find("database is locked")!=std::string::npos;}
    check(refused && !b.db().transaction_active(),"lock-failure-rollback");
    check(text(b,"SHOW lock_timeout")=="4321ms","local-lock-timeout-restored");lock->db().exec("ROLLBACK");}
  std::vector<std::future<J>> futures;
  for(int i=0;i<4;++i) futures.push_back(std::async(std::launch::async,[&]{auto other=worker();return context::summary(*other,"alpha",uri);}));
  for(auto& f:futures)check(f.get()["status"]=="cached","concurrent-initializer-complete");
  check(number(b,"SELECT count(*) FROM public.context_module")==1 && number(b,"SELECT count(*) FROM public.context_cache")==1,"one-atomic-schema-and-cache");
  check(context::read(b,"alpha",uri)["cache_status"]=="fresh","fresh-after-race");
  for(const auto* name:{"ctx_page_insert","ctx_page_update","ctx_page_delete","ctx_page_truncate"}) {
    b.db().exec(std::string("ALTER TABLE public.pages DISABLE TRIGGER ")+name);
    reject([&]{context::read(b,"alpha",uri);},"context_schema_incomplete");
    b.db().exec(std::string("ALTER TABLE public.pages ENABLE TRIGGER ")+name);
  }
  b.db().exec("ALTER FUNCTION public.qbrain_context_invalidate_v1() SECURITY DEFINER");
  reject([&]{context::read(b,"alpha",uri);},"context_schema_incomplete");
  b.db().exec("ALTER FUNCTION public.qbrain_context_invalidate_v1() SECURITY INVOKER");
  b.db().exec("TRUNCATE public.pages CASCADE");
  check(number(b,"SELECT dirty FROM public.context_cache")==1 && text(b,"SELECT l0||l1||refs_json FROM public.context_cache")=="[]","truncate-clears-all-cache");
  check(context::read(b,"alpha",uri)["page_count"]==0,"truncate-preview-empty");
  b.db().exec("ALTER TABLE public.context_module DROP CONSTRAINT context_module_version_check; UPDATE public.context_module SET version=2");
  reject([&]{context::read(b,"alpha",uri);},"context_schema_version_unsupported");
  reset(b);b.db().exec("CREATE TABLE public.context_cache(fake TEXT)");
  reject([&]{context::read(b,"alpha",uri);},"context_schema_version_unsupported");
  check(number(b,"SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='context_cache'")==1,"unknown-schema-not-overwritten");
  reset(b);page(b,1,"alpha","docs/a","public");b.ensure_source("volatile");
  const std::string empty="qbrain://volatile/resources/";
  b.save_config_value("context.external_summary","allow",false);
  auto remove=[&](const auto&,int){b.db().exec("DELETE FROM public.sources WHERE id='volatile'");return answer();};
  reject([&]{context::summary(b,"volatile",empty,"model",remove);},"invalid_source");
  check(optional_count(b)==0,"removed-empty-source-not-published");
  page(b,20,"alpha","large/a",std::string(9*1024*1024,'x'));
  page(b,21,"alpha","large/b",std::string(9*1024*1024,'y'));
  reject([&]{context::read(b,"alpha","qbrain://alpha/resources/large/","L1");},"directory_evidence_too_large");
  page(b,22,"alpha","large/oversize",std::string(17*1024*1024,'z'));
  reject([&]{context::read(b,"alpha","qbrain://alpha/resources/large/oversize","L2");},"raw_page_too_large");
  b.db().exec("DELETE FROM public.pages WHERE id IN (20,21,22)");
  for(int i=2;i<=258;++i)page(b,i,"alpha","docs/p"+std::to_string(i),"small");
  auto bounded=context::read(b,"alpha",uri,"L1",1024);
  check(bounded["truncated"]==true && bounded["page_count"]==256 && bounded.dump().size()<=1024,"directory-page-and-byte-cap");
}
}
int main(int argc,char** argv) {
  J result;
  try {
    backend="sqlite";Brain sqlite;sqlite.open_at(":memory:");auto expected=shared(sqlite);
    const bool only=argc==2 && std::string(argv[1])=="--sqlite-only";
    if(!only) {
      const char* flag=std::getenv("QBRAIN_PG_CONTEXT_TEST_DISPOSABLE");const char* connection=std::getenv("QBRAIN_PG_CONTEXT_TEST_DSN");
      if(!flag || std::string(flag)!="1" || !connection || !*connection)throw std::runtime_error("real disposable PG required; no skip");
      dsn=connection;backend="postgres";auto pg=worker();check(postgres(*pg),"actual-postgres-backend");
      auto actual=shared(*pg);check(actual==expected,"whole-cross-backend-results-identical");pg_only(*pg);
    }
    result={{"schema","qbrain-n48p-native-v1"},{"passed",true},{"real_postgres",!only},{"checks",checks},
            {"count",checks.size()},{"observations",expected},{"real_model_calls",0},{"real_client_consumption_verified",false}};
    std::cout<<result.dump()<<'\n';return 0;
  }catch(const std::exception& e){
    std::cout<<J{{"schema","qbrain-n48p-native-v1"},{"passed",false},{"error",e.what()},{"checks",checks},{"count",checks.size()}}.dump()<<'\n';return 1;
  }
}
