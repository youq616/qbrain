#include "qbrain/ai/detail/embedding_response.hpp"
#include "qbrain/ai/embed.hpp"
#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <numeric>
#include <random>
#include <stdexcept>

namespace {
using namespace qbrain::ai;
using namespace qbrain::ai::detail;
using J = nlohmann::json;
int checks;
void check(bool ok, const char* label) {
  ++checks;
  if (!ok) throw std::runtime_error(std::string("N46D: ") + label);
}
J item(J index, J vector = J::array({1.0, -2.0})) {
  return {{"index", std::move(index)}, {"embedding", std::move(vector)}};
}
std::string payload(J items) { return J{{"data", std::move(items)}}.dump(); }
void rejected(const std::string& raw, std::size_t count = 1, int dimensions = 0,
              bool image = false, std::size_t cap = HTTP_DEFAULT_RESPONSE_BYTES) {
  const auto result = parse_embedding_response(raw, count, dimensions, image, cap);
  check(!result.ok && result.vectors.empty() && !result.error.empty(),
        "bad payload returns no partial vectors");
  check(result.error.size() < 100 && result.error.find("PRIVATE-SENTINEL") == std::string::npos,
        "bad payload does not echo untrusted data");
}
void parser_cases() {
  auto two = payload(J::array({item(1, J::array({3,4})), item(0)}));
  auto result = parse_embedding_response(two, 2, 2);
  check(result.ok && result.error.empty() && result.vectors ==
        std::vector<std::vector<float>>{{1,-2},{3,4}}, "reorders complete batch by input index");
  result = parse_embedding_response(two, 2);
  check(result.ok, "infer consistent dimensions when not requested");
  const auto single = payload(J::array({{{"embedding", J::array({1,2})}}}));
  check(parse_embedding_response(single, 1, 0, true).ok, "legacy image missing index accepted");
  rejected(single);
  rejected(two, 2, 3);
  for (const auto& index : {J(-1), J(-9223372036854775807LL), J(1),
       J(2147483647), J(4294967295ULL), J(18446744073709551615ULL), J(0.0),
       J(0.5), J(true), J(nullptr), J("PRIVATE-SENTINEL"), J::array(), J::object()})
    rejected(payload(J::array({item(index)})));
  rejected(payload(J::array({item(1)})), 1, 0, true);
  for (const std::string& raw : {"", "null", "[]", "{}", "{\"data\":null}",
       "{\"data\":{}}", "{\"data\":[]}", "{\"data\":[null]}",
       "{\"data\":[\"PRIVATE-SENTINEL\"]}", "{\"data\":[1]}",
       "{\"data\":[{\"index\":0}]}", "{\"PRIVATE-SENTINEL\":",
       "{\"data\":[{\"index\":0,\"index\":0,\"embedding\":[1]}]}",
       "{\"data\":[],\"data\":[{\"index\":0,\"embedding\":[1]}]}"}) rejected(raw);
  for (const auto& vector : {J::array(), J(nullptr), J::object(), J("PRIVATE-SENTINEL"),
       J::array({0,0}), J::array({-0.0,0.0}), J::array({1e-100,0.0}),
       J::array({1,"PRIVATE-SENTINEL"}), J::array({true,1}), J::array({1,nullptr}),
       J::array({1,J::array({2})}), J::array({1,1e100}), J::array({1,-1e100})}) {
    rejected(payload(J::array({item(0,vector)})));
    rejected(payload(J::array({item(0),item(1,vector)})),2);
  }
  rejected("{\"data\":[{\"index\":0,\"embedding\":[1,1e10000]}]}");
  rejected("{\"data\":[{\"index\":0,\"embedding\":[NaN]}]}");
  rejected(payload(J::array({item(0),item(0)})), 2);
  rejected(payload(J::array({item(0)})), 2);
  rejected(two, 1);
  rejected(payload(J::array({item(0),item(1,J::array({1}))})),2);
  rejected(two, 0); rejected(two, EMBED_MAX_BATCH+1);
  rejected(two, 2, -1); rejected(two, 2, static_cast<int>(EMBED_MAX_DIMENSIONS+1));
  rejected(two, 2, 2, false, two.size()-1);
  check(parse_embedding_response(two,2,2,false,two.size()).ok, "exact byte cap accepted");
  rejected(two, 2, 2, false, 0);
  rejected(two, 2, 2, false, HTTP_DEFAULT_RESPONSE_BYTES+1);
  rejected(std::string(HTTP_DEFAULT_RESPONSE_BYTES+1,' '));
  rejected("{\"ignored\":"+std::string(100000,'[')+"0"+std::string(100000,']')+
           ",\"data\":[{\"index\":0,\"embedding\":[1]}]}");
  auto many_keys = J::object();
  for (int i=0;i<129;++i) many_keys["key-"+std::to_string(i)]=i;
  rejected(J{{"metadata", many_keys},{"data",J::array({item(0)})}}.dump());
  auto duplicate_nested = R"({"metadata":{"x":1,"x":2},"data":[{"index":0,"embedding":[1]}]})";
  rejected(duplicate_nested);
  // Same key in distinct sibling/nested objects is legal, never a false duplicate.
  auto metadata = J{{"a",{{"x",1}}},{"b",{{"x",2}}}};
  check(parse_embedding_response(J{{"metadata",metadata},{"data",J::array({item(0)})}}.dump(),1).ok,
        "duplicate-key guard keeps separate object scopes");
  auto wide=std::vector<float>(EMBED_MAX_DIMENSIONS,1);
  check(parse_embedding_response(payload(J::array({item(0,wide)})),1).ok,"dimension cap exact");
  wide.push_back(1); rejected(payload(J::array({item(0,wide)})));
  J large=J::array();
  for (int i=0;i<33;++i) large.push_back(item(i,std::vector<float>(32768,1)));
  rejected(payload(large),33); // aggregate >1,048,576, raw payload still <8 MiB
  large.erase(large.end()-1);
  check(parse_embedding_response(payload(large),32).ok,"aggregate component cap exact");
  // A huge irrelevant array must not bypass the JSON event budget.
  std::string extra="{\"metadata\":[";
  for(std::size_t i=0;i<EMBED_MAX_PARSE_EVENTS;++i) extra+="0,";
  extra+="0],\"data\":[{\"index\":0,\"embedding\":[1]}]}";
  rejected(extra);
  auto bad_utf8=payload(J::array({item(0)}));
  bad_utf8.insert(1,"\"x\":\""+std::string("\xc0\xaf",2)+"\","); rejected(bad_utf8);
  const auto extreme=payload(J::array({item(0,J::array({
      std::numeric_limits<float>::max(),std::numeric_limits<float>::lowest(),
      std::numeric_limits<float>::denorm_min()}))}));
  check(parse_embedding_response(extreme,1).ok,"finite representable float boundaries");
}
void properties() {
  std::mt19937 generator(4604);
  for (int n=1;n<=32;++n) {
    std::vector<int> permutation(n); std::iota(permutation.begin(),permutation.end(),0);
    std::shuffle(permutation.begin(),permutation.end(),generator);
    J data=J::array();
    for(int i:permutation) data.push_back(item(i,J::array({i+1,-i-1,0.25})));
    const auto good=parse_embedding_response(payload(data),n,3);
    check(good.ok && good.vectors.size()==static_cast<std::size_t>(n),"permutation accepted");
    for(int i=0;i<n;++i) check(good.vectors[i][0]==i+1,"each output belongs to its input index");
    data.back()["index"]=std::numeric_limits<std::uint64_t>::max();
    rejected(payload(data),n,3);
  }
  std::string bytes;
  for (int i=0;i<128;++i) bytes+=static_cast<char>(i);
  bytes+="中文 😀";
  const auto size=J(bytes).dump().size();
  check(json_string_bytes(bytes,size)==size,"JSON preflight matches actual escaped Unicode serialization");
  check(json_string_bytes(bytes,size-1)>size-1,"preflight detects escaping expansion");
  check(json_string_bytes("",2)==2 && json_string_bytes("",1)>1,"empty JSON string size");
}
}
void test_n46d() {
  checks=0; parser_cases(); properties();
  std::cout<<"N46D embedding integrity: "<<checks<<" checks passed\n";
}
#ifdef QBRAIN_EMBEDDING_STANDALONE
int main() {
  try {test_n46d();return 0;}
  catch(const std::exception& e){std::cerr<<"[FAIL] "<<e.what()<<'\n';return 1;}
}
#endif
