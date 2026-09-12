#include "qbrain/ai/detail/embedding_response.hpp"
#include "qbrain/search/hybrid.hpp"
#include "qbrain/search/vector.hpp"
#include <iostream>
#include <limits>
#include <stdexcept>

namespace {
using J = nlohmann::json;
int checks = 0;
void check(bool ok, const char* message) {
  if (!ok) throw std::runtime_error(std::string("N46D: ") + message);
  ++checks;
}
J item(J index, J vector = J::array({1.0, 0.25, -0.5})) {
  return {{"index", index}, {"embedding", vector}};
}
J payload() { return {{"model", "fixture-model"}, {"data", J::array({item(0), item(1)})}}; }
void rejects(const std::string& body, std::size_t count = 2, int dims = 3,
             std::size_t cap = qbrain::ai::HTTP_DEFAULT_RESPONSE_BYTES) {
  const auto r = qbrain::ai::detail::parse_embedding_response(body, "fixture-model", count, dims, cap);
  check(!r.ok && r.vectors.empty() && r.model.empty() && r.error == "invalid embedding response",
        "malformed batch must fail atomically with a constant error");
}
void parsing() {
  using qbrain::ai::detail::parse_embedding_response;
  auto p = payload();
  auto r = parse_embedding_response(p.dump(), "fixture-model", 2, 3);
  check(r.ok && r.vectors.size()==2 && r.model=="fixture-model", "complete batch accepted");
  p["data"] = J::array({item(1, J::array({3,2,1})),item(0)});
  r = parse_embedding_response(p.dump(), "fixture-model", 2, 0);
  check(r.ok && r.vectors[0][0]==1 && r.vectors[1][0]==3, "reordering follows indices");
  p.erase("model");
  check(parse_embedding_response(p.dump(),"fixture-model",2).ok,"missing optional model uses request identity");
  for (const J& index : {J(-1), J(2), J(0.5), J(0.0), J(true), J("0"), J(nullptr),
                         J(std::numeric_limits<std::uint64_t>::max())}) {
    p=payload();p["data"][1]["index"]=index;rejects(p.dump());
  }
  p=payload();p["data"][1]["index"]=0;rejects(p.dump());
  p=payload();p["data"][1].erase("index");rejects(p.dump());
  p=payload();p["data"].erase(1);rejects(p.dump());
  p=payload();p["data"].push_back(item(2));rejects(p.dump());
  p=payload();p["data"]=J::object();rejects(p.dump());
  p=payload();p["data"][1]=nullptr;rejects(p.dump());
  for (const J& vector : {J::array(),J::array({1,2}),J::array({1,2,3,4}),
       J::array({0,0,0}),J::array({1e-300,0,0}),J::array({1e100,0,0}),
       J::array({true,1,1}),J::array({"PRIVATE_PROVIDER_TEXT",1,1}),
       J::array({nullptr,1,1}),J::array({J::array({1}),1,1}),J("encoded-base64")}) {
    p=payload();p["data"][1]["embedding"]=vector;rejects(p.dump());
  }
  for (const J& model : {J("other-model"),J("FIXTURE-MODEL"),J("fixture-model "),J(""),J(nullptr),J(12)}) {
    p=payload();p["model"]=model;rejects(p.dump());
  }
  rejects("null"); rejects("[]"); rejects("{}"); rejects("PRIVATE_PROVIDER_TEXT{");
  rejects("{\"data\":[{\"index\":0,\"embedding\":[1e400]}]}",1,0);
  rejects("{\"data\":[{\"index\":0,\"index\":0,\"embedding\":[1]}]}",1,0);
  rejects("{\"data\":[],\"data\":[]}");
  rejects(std::string(40,'[')+"0"+std::string(40,']'));
  p=payload(); const auto valid=p.dump();
  check(parse_embedding_response(valid,"fixture-model",2,3,valid.size()).ok,"exact body cap accepted");
  rejects(valid,2,3,valid.size()-1); rejects(valid,0);rejects(valid,2049);rejects(valid,2,-1);rejects(valid,2,16385);
  p=payload();p["data"][1]["embedding"]=std::vector<int>(16385,1);rejects(p.dump(),2,0);
  p=payload();p["junk"]=std::string("\xff",1);
  rejects("{\"model\":\"\xff\",\"data\":[]}");
  check(!parse_embedding_response(valid,"",2).ok,"empty request identity rejected");
  check(!parse_embedding_response(valid,std::string(257,'x'),2).ok,"bounded model identity");
}
void model_filtering() {
  using namespace qbrain;
  Brain b; b.open_at(":memory:"); b.ensure_source("alpha"); b.ensure_source("beta");
  b.config().embedding_model="model-a";
  auto p=b.db().prepare("INSERT INTO pages(id,source_id,slug,title,body) VALUES(?,?,?,?,?)");
  auto c=b.db().prepare("INSERT INTO content_chunks(page_id,chunk_index,text,embedding,dim,model) VALUES(?,0,'vector-only evidence',?,?,?)");
  const auto blob=search::pack_f32({1,0,0});
  for(int n=1;n<=6;++n) {
    p.reset();p.clear_bindings();p.bind_int(1,n);p.bind_text(2,n==6?"beta":"alpha");
    p.bind_text(3,"page-"+std::to_string(n));p.bind_text(4,"page");p.bind_text(5,"lexicalterm");p.step_done();
    c.reset();c.clear_bindings();c.bind_int(1,n);c.bind_blob(2,blob.data(),static_cast<int>(blob.size()));
    c.bind_int(3,n==5?2:3);
    if(n==4)c.bind_null(4);else c.bind_text(4,n==2?"model-b":n==3?"":"model-a");c.step_done();
  }
  const std::vector<float> query={1,0,0};
  search::HybridOpts opts;opts.source_id="alpha";
  opts.embedding_model.reset();
  auto default_hits=search::hybrid_search(b,"no-lexical-match",&query,opts);
  check(ai::embedding_mock_enabled() ? default_hits.empty() :
      default_hits.size()==1&&default_hits[0].page_id==1,"absent override uses active model, not wildcard");
  b.config().embedding_model="model-b";
  default_hits=search::hybrid_search(b,"no-lexical-match",&query,opts);
  check(ai::embedding_mock_enabled() ? default_hits.empty() :
      default_hits.size()==1&&default_hits[0].page_id==2,"active configuration change is immediately visible");
  b.config().embedding_model="model-a";
  // Explicit query model isolates this test from the test runner's mock setting.
  opts.embedding_model="model-a";
  auto hits=search::hybrid_search(b,"no-lexical-match",&query,opts);
  check(hits.size()==1&&hits[0].page_id==1,"matching source/model/metadata only");
  opts.embedding_model="model-b";
  hits=search::hybrid_search(b,"no-lexical-match",&query,opts);
  check(hits.size()==1&&hits[0].page_id==2,"model changes do not reuse previous vectors");
  opts.embedding_model="";
  check(search::hybrid_search(b,"no-lexical-match",&query,opts).empty(),"empty identity disables vector lane");
  check(!search::hybrid_search(b,"lexicalterm",&query,opts).empty(),"lexical fallback remains available");
  opts.embedding_model="model-a";opts.source_id="beta";
  hits=search::hybrid_search(b,"no-lexical-match",&query,opts);
  check(hits.size()==1&&hits[0].page_id==6,"matching labels cannot cross source filters");
  b.db().exec("UPDATE pages SET deleted_at='2026-09-12' WHERE id=6");
  check(search::hybrid_search(b,"no-lexical-match",&query,opts).empty(),"deleted vectors not resurrected");
  check(search::vector_search(b,query,10,"alpha",nullptr,"model-a").size()==1,"explicit raw model predicate");
  check(search::vector_search(b,query,10,"alpha",nullptr,"model-a' OR 1=1 --").empty(),"model is a bound SQL parameter");
  check(search::vector_search(b,query,10,"alpha").size()==5,"raw legacy helper intentionally unchanged");
  check(search::vector_search(b,{0,0,0},10,"alpha",nullptr,"model-a").empty(),"zero query rejected in strict lane");
  b.db().exec("UPDATE content_chunks SET embedding=X'000000000000000000000000' WHERE page_id=1");
  check(search::vector_search(b,query,10,"alpha",nullptr,"model-a").empty(),"legacy zero stored vector excluded in strict lane");
}
}
void test_n46d() {
  checks=0;parsing();model_filtering();
  std::cout<<"N46D embedding contracts: "<<checks<<" checks passed\n";
}
#ifdef QBRAIN_EMBEDDING_STANDALONE
int main() {
  try {test_n46d();return 0;}
  catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
#endif
