// N48U read-only PostgreSQL predicate execution. No table mutation or schema setup.
#include "qbrain/context/pg_directory_policy.hpp"
#include "qbrain/storage/database.hpp"
#include "qbrain/storage/pg_backend.hpp"
#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
using J=nlohmann::json;
int main(){J rows=J::array();try{
#if defined(QBRAIN_WITH_PG)
 const char* allow=std::getenv("QBRAIN_PG_DIRECTORY_READONLY_TEST");const char* input=std::getenv("PGPORT");
 if(!allow||std::string(allow)!="1"||!input)throw std::runtime_error("explicit read-only test environment required");
 const std::string port=input;
 if(port.empty()||port.size()>5||!std::all_of(port.begin(),port.end(),[](char c){return c>='0'&&c<='9';})||std::stoul(port)==0||std::stoul(port)>65535)throw std::runtime_error("valid loopback port required");
 qbrain::storage::Database db;
 db.adopt_backend(qbrain::storage::make_pg_backend("host=127.0.0.1 port="+port+" dbname=qbrain_n48u_readonly user=qbrain_n48o connect_timeout=2"));
 db.exec("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY");
 auto count=[&]{auto s=db.prepare("SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public'");if(!s.step())throw std::runtime_error("missing catalog count");return s.column_int(0);};
 if(count()!=0)throw std::runtime_error("expected empty test schema");
 const std::vector<std::string> slugs={"docs/a","docs/sub/a","docs-neighbor/a","a_b/a","A_b/a","axb/a","中文😀/a"};
 const std::vector<std::string> paths={"","docs/","docs/sub/","a_b/","A_b/","axb/","中文😀/"};
 const auto sql="WITH p(source_id,slug,type) AS (VALUES(?::text,?::text,?::text)),c(source_id,uri) AS (VALUES(?::text,?::text)) SELECT "+qbrain::context::pg::directory_policy::member("p")+" FROM p,c";
 for(const auto& src:{"alpha","beta"})for(const auto& kind:{"note","skill","session_fragment"})for(const auto& slug:slugs)
 for(const auto& target:{"alpha","beta"})for(const auto& ns:{"resources","skills","memories"})for(const auto& path:paths){
  const std::string space=std::string(kind)=="skill"?"skills":std::string(kind)=="session_fragment"?"memories":"resources";
  const std::string uri="qbrain://"+std::string(target)+"/"+ns+"/"+path;
  const bool expected=std::string(src)==target&&space==ns&&slug.starts_with(path);
  auto q=db.prepare(sql);q.bind_text(1,src);q.bind_text(2,slug);q.bind_text(3,kind);q.bind_text(4,target);q.bind_text(5,uri);
  if(!q.step())throw std::runtime_error("missing predicate result");
  const bool actual=q.column_text(0)=="t";
  rows.push_back({{"source",src},{"kind",kind},{"slug",slug},{"cache_source",target},{"uri",uri},{"matched",actual}});
  if(actual!=expected||q.step())throw std::runtime_error("literal predicate mismatch");
 }
 if(count()!=0)throw std::runtime_error("test schema changed");
 db.exec("ROLLBACK");
 std::cout<<J{{"schema","qbrain-n48u-readonly-predicate-v1"},{"passed",true},{"cases",rows},{"case_count",rows.size()},{"real_postgres",true},{"application_writes",0}}.dump()<<'\n';return 0;
#else
 throw std::runtime_error("PostgreSQL required, no successful skip");
#endif
}catch(const std::exception& e){std::cout<<J{{"schema","qbrain-n48u-readonly-predicate-v1"},{"passed",false},{"error",e.what()},{"cases",rows}}.dump()<<'\n';return 1;}}
