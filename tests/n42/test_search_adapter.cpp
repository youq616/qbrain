#include "qbrain/search/hybrid.hpp"
#include "qbrain/search/vector.hpp"
#include "qbrain/util/utf8_display.hpp"
#include <iostream>
#include <limits>
#include <stdexcept>
#define CHECK(x) do{if(!(x))throw std::runtime_error(#x);++checks;}while(0)
int main(){
  int checks=0;
  try{
    qbrain::Brain b;
    b.db().exec("CREATE TABLE pages(id INTEGER PRIMARY KEY,source_id TEXT,slug TEXT,title TEXT,type TEXT,body TEXT,updated_at TEXT,deleted_at TEXT); CREATE TABLE content_chunks(page_id INTEGER,text TEXT,embedding BLOB); CREATE TABLE links(source_id TEXT,from_slug TEXT,to_slug TEXT); CREATE VIRTUAL TABLE page_fts USING fts5(title,body);");
    auto add=[&](int id,const std::string&source,const std::string&slug,const std::string&body,const std::vector<float>&vec){
      auto st=b.db().prepare("INSERT INTO pages VALUES(?,?,?,?,'note',?,'2026-09-10',NULL)");
      st.bind_int(1,id);st.bind_text(2,source);st.bind_text(3,slug);st.bind_text(4,slug);st.bind_text(5,body);st.step();
      auto ft=b.db().prepare("INSERT INTO page_fts(rowid,title,body) VALUES(?,?,?)");ft.bind_int(1,id);ft.bind_text(2,slug);ft.bind_text(3,body);ft.step();
      auto cs=b.db().prepare("INSERT INTO content_chunks VALUES(?,?,?)");cs.bind_int(1,id);cs.bind_text(2,body);auto blob=qbrain::search::pack_f32(vec);cs.bind_blob(3,blob.data(),static_cast<int>(blob.size()));cs.step();
    };
    std::string chinese;for(int i=0;i<67;++i)chinese+="\xE4\xB8\xAD";
    add(1,"default","deployment","default-only",{1,0});
    add(2,"project-a","deployment",chinese,{1,0});
    auto rows=qbrain::search::vector_search(b,{1,0},10);
    CHECK(rows.size()==2);
    CHECK(rows[0].source_id=="default"&&rows[1].source_id=="project-a");
    CHECK(rows[1].snippet.size()==198&&qbrain::util::valid_utf8(rows[1].snippet));
    rows=qbrain::search::vector_search(b,{1,0},10,"project-a");
    CHECK(rows.size()==1&&rows[0].page_id==2);
    auto fts=qbrain::search::fts_search(b,"deployment",10);
    CHECK(fts.size()==2&&fts[0].source_id!=fts[1].source_id);
    qbrain::search::HybridOpts opts;opts.limit=10;opts.source_id="project-a";opts.mode="conservative";
    auto joined=qbrain::search::hybrid_search(b,"deployment",nullptr,opts);
    CHECK(joined.size()==1&&joined[0].source_id=="project-a");
    b.db().force_fts_failure=true;
    auto fallback=qbrain::search::fts_search(b,"deployment",10,"project-a");
    CHECK(fallback.size()==1&&fallback[0].source_id=="project-a");
    add(3,"project-a","rate_100%","literal",{1});
    add(4,"project-a","rateA100X","not literal",{std::numeric_limits<float>::quiet_NaN(),0});
    fallback=qbrain::search::fts_search(b,"rate_100%",10,"project-a");
    CHECK(fallback.size()==1&&fallback[0].page_id==3);
    rows=qbrain::search::vector_search(b,{1,0},10);
    CHECK(rows.size()==2); // wrong dimension and NaN candidates must not enter ranking
    CHECK(qbrain::search::vector_search(b,{std::numeric_limits<float>::quiet_NaN(),0},10).empty());
    b.db().exec("UPDATE pages SET deleted_at='deleted' WHERE id=2;");
    CHECK(qbrain::search::vector_search(b,{1,0},10).size()==1);
    CHECK(qbrain::search::fts_search(b,"deployment",10,"project-a").empty());
    b.db().force_fts_failure=false;
    CHECK(qbrain::search::fts_search(b,"deployment",10).size()==1);
    std::cout<<"[PASS] "<<checks<<" checks: production hybrid/RRF/vector sources over real SQLite TEST ADAPTER.\n";
    std::cout<<"Not tested: production storage facade, PostgreSQL, providers, MCP dispatch, Windows.\n";
    return 0;
  }catch(const std::exception&e){std::cerr<<"[FAIL] "<<e.what()<<'\n';return 1;}
}
