// Additional outcome-review probes. Includes production test seed helpers, not
// their assertions; expected database snapshots are checked independently below.
#include "tests/test_n47g.cpp"
namespace {
J snapshot(Brain& b) {
 auto st=b.db().prepare("SELECT f.fact_id,f.status,f.revision,f.object,f.updated_at,"
     "(SELECT COUNT(*) FROM memory_fact_archive a WHERE a.fact_id=f.fact_id) "
     "FROM memory_facts f ORDER BY f.fact_id");
 J out=J::array();while(st.step())out.push_back(J::array({st.column_text(0),st.column_text(1),st.column_int(2),st.column_text(3),st.column_int(4),st.column_int(5)}));
 return out;
}
void commit_veto() {
 scenario("commit veto rolls back archive and restore receipts",[]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"cv-a"),z=seed(*b,"cv-z","I prefer GUI.");
  s.archive(item(a));s.restore(item(a,2));b->db().exec("PRAGMA busy_timeout=71");
  for(int round=0;round<2;++round){
   auto p=request(round?"restore":"archive",J::array({item(a,3+round),item(z,1+round)}));
   auto before=snapshot(*b);int vetoes=0;
   sqlite3_commit_hook(b->db().handle(),[](void* ctx)->int{++*static_cast<int*>(ctx);return 1;},&vetoes);
   bool rejected=false;try{s.lifecycle_batch(p,true);}catch(const std::exception&){rejected=true;}
   sqlite3_commit_hook(b->db().handle(),nullptr,nullptr);
   check(rejected && vetoes==1,"commit veto surfaced as failure, never APPLIED");
   check(snapshot(*b)==before,"commit veto leaves all policy revision quote and time unchanged");
   check(sqlite3_get_autocommit(b->db().handle())==1,"veto leaves no active transaction");
   check(scalar(*b,"PRAGMA busy_timeout")==71,"veto restores prior busy timeout");
   check(s.lifecycle_batch(p,true)["counts"]["change"]==2,"explicit retry after veto applies both");
  }
 });
}
void statement_errors(){
 for(const auto* mode:{"ABORT","FAIL","ROLLBACK"})scenario((std::string("late statement ")+mode+" leaves no partial batch").c_str(),[&]{
  auto b=fresh();memory::FactStore s(*b,"alpha");auto a=seed(*b,"st-a"),z=seed(*b,"st-z","I prefer second.");
  s.archive(item(a));s.restore(item(a,2));b->db().exec("PRAGMA busy_timeout=83");
  for(int round=0;round<2;++round){
   auto p=request(round?"restore":"archive",J::array({item(a,3+round),item(z,1+round)}));
   const std::string kind=round?"DELETE":"INSERT",entity=round?"OLD":"NEW";
   b->db().exec("CREATE TRIGGER fail_review BEFORE "+kind+" ON memory_fact_archive WHEN "+entity+".fact_id='"+z.id+"' BEGIN SELECT RAISE("+mode+",'fixture'); END;");
   auto before=snapshot(*b);denied([&]{s.lifecycle_batch(p,true);});
   check(snapshot(*b)==before,"late statement error rolls back prior item and all revisions");
   check(sqlite3_get_autocommit(b->db().handle())==1,"late error leaves autocommit restored");
   check(scalar(*b,"PRAGMA busy_timeout")==83,"late error restores timeout");
   b->db().exec("DROP TRIGGER fail_review");
   check(s.lifecycle_batch(p,true)["counts"]["change"]==2,"explicit retry after removing fault succeeds");
  }
 });
}
void blocked_commit(){
 scenario("blocked COMMIT rolls back batch before caller regains control",[]{
  auto dir=tempdir();
  {Brain b;b.open_at(util::path_to_utf8(dir/"brain.db"));b.ensure_source("alpha");b.save_config_value("memory.writeback","all");
   memory::FactStore s(b,"alpha");auto a=seed(b,"bc-a"),z=seed(b,"bc-z","I prefer other.");s.archive(item(a));s.restore(item(a,2));
   b.db().exec("PRAGMA journal_mode=DELETE; PRAGMA busy_timeout=97");
   sqlite3* rd=nullptr;check(sqlite3_open(util::path_to_utf8(dir/"brain.db").c_str(),&rd)==SQLITE_OK,"open independent blocker");
   struct Close {sqlite3* db;~Close(){sqlite3_exec(db,"ROLLBACK",nullptr,nullptr,nullptr);sqlite3_close(db);}} close{rd};
   check(sqlite3_exec(rd,"BEGIN; SELECT COUNT(*) FROM memory_facts;",nullptr,nullptr,nullptr)==SQLITE_OK,"hold real separate rollback-journal reader");
   int commits=0;sqlite3_trace_v2(b.db().handle(),SQLITE_TRACE_STMT,[](unsigned,void* ctx,void*,void* sql)->int{
     if(sql && std::string(static_cast<char*>(sql))=="COMMIT")++*static_cast<int*>(ctx);return 0;},&commits);
   auto before=snapshot(b);auto start=std::chrono::steady_clock::now();auto p=request("archive",J::array({item(a,3),item(z)}));
   bool failed=false;try{s.lifecycle_batch(p,true);}catch(const std::exception&){failed=true;}
   sqlite3_trace_v2(b.db().handle(),0,nullptr,nullptr);
   auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count();
   check(failed && commits==1,"failure actually occurred after attempting COMMIT");
   check(ms>=2000 && ms<8000,"commit busy wait remains bounded");
   check(snapshot(b)==before && sqlite3_get_autocommit(b.db().handle())==1,"COMMIT busy failure rolls back entire batch");
   check(scalar(b,"PRAGMA busy_timeout")==97,"blocked commit restores caller timeout");
   check(sqlite3_exec(rd,"ROLLBACK",nullptr,nullptr,nullptr)==SQLITE_OK,"release blocker");
   check(s.lifecycle_batch(p,true)["counts"]["change"]==2,"same batch can succeed after explicit blocker release");
  }
  std::filesystem::remove_all(dir);
 });
}
}
int main(int argc,char**argv){try{checks=0;scenarios=J::array();commit_veto();statement_errors();blocked_commit();
 J report={{"result","PASS"},{"source_commit","b1292b54543b9f54cd5e2b71f4ae4bf5f6247385"},{"scope","Additional Linux transaction probes, not new Windows or live-host acceptance"},{"scenario_count",scenarios.size()},{"checks",checks},{"scenarios",scenarios}};
 if(argc==2){std::ofstream out(argv[1]);out<<report.dump(2)<<'\n';}
 std::cout<<report.dump()<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<"[FAIL] review probe: "<<e.what()<<'\n';return 1;}}
