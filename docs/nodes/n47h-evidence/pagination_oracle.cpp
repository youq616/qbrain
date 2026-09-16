// Outcome-review-only probe. Reuses original disposable fixture helpers; the
// expected selection model below does not call the production eligibility code.
#include "tests/test_n47h.cpp"
#include <map>
namespace {
struct Model {Seed f;std::string source;int rev=1;bool live=true,archived=false;int64_t latest=0;};
std::map<std::string,Model> model;
int traversals=0,pages_observed=0,unchanged_cursor_checks=0;
void set_quote(Brain& b,const std::string& item){auto st=b.db().prepare("UPDATE memory_items SET quote='fixture corrupted' WHERE item_id=?");st.bind_text(1,item);st.step_done();}
void populate(Brain& b){
 const auto at=now();
 for(const auto source:{"alpha","beta"})for(int n=0;n<144;++n){
  auto f=seed(b,std::string(source)+"-oracle-"+std::to_string(n),source);
  Model m{f,source};m.latest=at-220*86400;timestamp(b,f,m.latest);
  memory::FactStore s(b,source);
  switch(n%13){
   case 3:case 5:case 6:
    m.archived=true;m.rev=s.archive(selection(f))["revision"];break;
   case 8:m.live=false;m.rev=s.retract(selection(f))["revision"];break;
   case 9:m.live=false;set_quote(b,f.item);break;
   case 10:{auto other=seed(b,std::string(source)+"-recent-"+std::to_string(n),source,false,f.quote);m.rev=2;m.latest=at;timestamp(b,other,m.latest);break;}
   case 11:m.live=false;memory::forget(b,source,f.event);break;
   case 12:{auto other=seed(b,std::string(source)+"-support-"+std::to_string(n),source,false,f.quote);m.rev=2;m.latest=at-200*86400;timestamp(b,other,m.latest);set_quote(b,f.item);break;}
  }
  if(n%13==4 || n%13==5){m.latest=at;timestamp(b,f,m.latest);}
  if(n%13==6){m.latest=0;timestamp(b,f,0);}
  if(n%13==7){m.latest=at+86400;timestamp(b,f,m.latest);}
  model.emplace(f.id,std::move(m));
 }
}
std::vector<std::string> expected(const std::string& source,const std::string& op){
 std::vector<std::string> v;for(const auto&[id,m]:model)
  if(m.source==source && m.live && (op=="restore"?m.archived:!m.archived && m.latest>0 && now()-m.latest>=180*86400))v.push_back(id);
 return v;
}
void traverse(Brain& b,const std::string& source,const std::string& op,int limit,int budget,bool mutate){
 ++traversals;memory::FactStore s(b,source);auto oracle=expected(source,op);
 std::vector<std::string> seen;std::string after;int pages=0;
 for(;;){
  check(++pages<=160,"finite forward progress on mixed-state inventory");++pages_observed;
  const int before=sqlite3_total_changes(b.db().handle());
  auto r=s.lifecycle_candidates(op,"",180,after,limit,budget);
  check(sqlite3_total_changes(b.db().handle())==before,"every discovery page is write-free");
  check(r.dump().size()<=static_cast<size_t>(budget) && r["scanned"]<=100,"entire envelope and scan bounds");
  check(r["items"].size()<=static_cast<size_t>(limit),"result count bound");
  std::string prev=after;
  for(const auto& it:r["items"]){
   auto id=it["fact_id"].get<std::string>();const auto& m=model.at(id);
   check(id>prev && m.source==source && it["expected_revision"]==m.rev && it["archived"]==m.archived,"ordered exact-source metadata revision");prev=id;
   check(!it.contains("object") && !it.contains("evidence"),"no copied quote or evidence");
   if(m.latest>0 && m.latest<=r["evaluated_at"].get<int64_t>())check(it["age"]["age_seconds"]==r["evaluated_at"].get<int64_t>()-m.latest,"age follows each call evaluation time");
   seen.push_back(id);
  }
  if(r["items"].empty())check(r["batch_payload"].is_null(),"no empty apply batch manufactured");
  else{
   auto p=r["batch_payload"];check(p["operation"]==op && p["items"].size()==r["items"].size() && p.dump().size()<=8192,"exact bounded batch input");
   for(size_t i=0;i<p["items"].size();++i)check(p["items"][i]==J({{"fact_id",r["items"][i]["fact_id"]},{"expected_revision",r["items"][i]["expected_revision"]}}),"batch input matches metadata");
   if(mutate){check(s.lifecycle_batch(p)["applied"]==false,"preview never applies");check(s.lifecycle_batch(p,true)["applied"]==true,"apply only after explicit call");
    for(const auto& it:p["items"]){auto& m=model.at(it["fact_id"]);m.archived=op=="archive";++m.rev;}
   }
  }
  if(!r["has_more"].get<bool>()){check(r["next_after_id"].is_null(),"end carries no seek continuation");break;}
  auto next=r["next_after_id"].get<std::string>();
  check(r["progressed"]==J(next!=after),"progress field agrees with continuation");
  check(next>after,"tested fitting budget advances even through exclusions");after=next;
 }
 check(seen==oracle,"entire paginated set equals independent model without duplicate or skip");
}
void run_oracle(){
 auto b=fresh();populate(*b);
 scenario("mixed-state pages match reference model under varied counts and byte budgets",[&]{
  for(const auto source:{"alpha","beta"})for(const auto op:{"archive","restore"})
   for(int limit:{1,7,32})for(int budget:{1536,4096,32768})traverse(*b,source,op,limit,budget,false);
 });
 scenario("non-fitting envelope never advances past a selected row",[&]{
  for(const auto source:{"alpha","beta"}){memory::FactStore s(*b,source);auto wanted=expected(source,"archive");auto r=s.lifecycle_candidates("archive","",180,"",32,768);
   check(r["items"].empty() && r["has_more"]==true && r["stop_reason"]=="output_budget","small envelope stops before emitting partial selection");
   auto after=r["next_after_id"].get<std::string>();check(after<wanted.front(),"seek does not consume pending match");
   auto retry=s.lifecycle_candidates("archive","",180,after,1,4096);check(ids(retry)==std::vector<std::string>{wanted.front()},"larger budget recovers exact pending first match");++unchanged_cursor_checks;
  }
 });
 scenario("explicit page-by-page apply does not skip keys removed by own policy changes",[&]{
  for(const auto source:{"alpha","beta"}){traverse(*b,source,"archive",7,4096,true);traverse(*b,source,"archive",32,32768,false);traverse(*b,source,"restore",7,4096,true);traverse(*b,source,"restore",32,32768,false);traverse(*b,source,"archive",32,32768,false);}
 });
}
}
int main(int argc,char**argv){try{checks=0;scenarios=J::array();run_oracle();
 int measured=0;for(const auto& x:scenarios)measured+=x["assertions"].get<int>();
 J r={{"setup_assertions",checks-measured},{"result","PASS"},{"source_commit","80fe1b9d31de6cc41d06be6db0e1035c1a747eb7"},{"source_attribution","Fixed source used for linkage; independently tree-verified, not runtime Git"},{"platform","Linux GCC14.2 supplemental review"},{"scenario_count",scenarios.size()},{"assertions",checks},{"traversals",traversals},{"pages",pages_observed},{"seeded_claims",model.size()},{"scenarios",scenarios}};
 if(argc==2){std::ofstream out(argv[1]);out<<r.dump(2)<<'\n';if(!out)throw std::runtime_error("report write failed");}std::cout<<r.dump()<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<"[FAIL] paging review: "<<e.what()<<'\n';return 1;}}
