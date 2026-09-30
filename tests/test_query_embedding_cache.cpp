#include "qbrain/ai/query_embedding_cache.hpp"
#include <nlohmann/json.hpp>
#include <atomic>
#include <barrier>
#include <future>
#include <iostream>
#include <limits>
#include <thread>
#include <vector>

using Cache = qbrain::ai::QueryEmbeddingCache;
using Result = qbrain::ai::EmbedResult;
using J = nlohmann::json;
namespace {
J checks = J::array();
void check(bool ok, const char* name) {
  checks.push_back({{"name", name}, {"passed", ok}});
  if (!ok) throw std::runtime_error(name);
}
Cache::Identity id(char key='a', char policy='b', int dim=3) {
  return {std::string(64,policy), std::string(64,key), "model", dim};
}
Result good(float value=1) { return {true, "", {{value,2,3}}, "model"}; }
void basic() {
  Cache c; int loads=0;
  auto load=[&]{++loads; return good();};
  c.get_or_load(false,id(),load); c.get_or_load(false,id(),load);
  check(loads==2 && c.stats().entries==0, "default off calls loader twice");
  c.get_or_load(true,id(),load);
  auto hit=c.get_or_load(true,id(),load);
  check(loads==3 && c.stats().hits==1 && hit.vectors==good().vectors, "exact successful hit");
  hit.vectors[0][0]=999; hit.model="changed";
  check(c.get_or_load(true,id(),load).vectors==good().vectors, "caller result cannot poison cache");
  c.get_or_load(true,id('c'),load);
  check(loads==4 && c.stats().entries==2, "different query-source key misses");
  c.get_or_load(true,id('a','d'),load);
  check(loads==5 && c.stats().entries==1, "policy switch clears partition");
  c.get_or_load(true,id('a','b'),load);
  check(loads==6, "switching back does not revive old partition");
  c.clear(); check(c.stats().entries==0 && c.stats().bytes==0, "explicit clear removes payload");
  c.get_or_load(true,id(),load); c.get_or_load(false,id(),load); c.get_or_load(true,id(),load);
  check(loads==9, "disable flushes before later enable");
}
void invalid_results() {
  std::vector<Result> invalid;
  auto r=good();r.ok=false;invalid.push_back(r);
  r=good();r.error="provider error";invalid.push_back(r);
  r=good();r.model="other";invalid.push_back(r);
  r=good();r.vectors.clear();invalid.push_back(r);
  r=good();r.vectors.push_back({1,2,3});invalid.push_back(r);
  r=good();r.vectors[0].clear();invalid.push_back(r);
  r=good();r.vectors[0]={0,0,0};invalid.push_back(r);
  r=good();r.vectors[0]={1,2};invalid.push_back(r);
  r=good();r.vectors[0][0]=std::numeric_limits<float>::infinity();invalid.push_back(r);
  r=good();r.vectors[0][0]=std::numeric_limits<float>::quiet_NaN();invalid.push_back(r);
  r=good();r.vectors[0].assign(16385,1);invalid.push_back(r);
  for (const auto& value:invalid) {
    Cache c; int loads=0;
    auto loader=[&]{++loads;return value;};
    c.get_or_load(true,id(),loader);c.get_or_load(true,id(),loader);
    check(loads==2 && c.stats().entries==0 && c.stats().rejected==2, "invalid result never cached");
  }
  Cache c; int loads=0;
  auto wide=id();wide.dimensions=0;
  c.get_or_load(true,wide,[&]{++loads;return good();});
  c.get_or_load(true,wide,[&]{++loads;return good();});
  check(loads==1, "provider-chosen dimensions positive");
  for (int what=0;what<5;++what) {
    Cache other;auto bad=id();
    if(what==0)bad.key="raw query";
    if(what==1)bad.policy=std::string(64,'z');
    if(what==2)bad.model="invalid model";
    if(what==3)bad.dimensions=-1;
    if(what==4)bad.dimensions=16385;
    other.get_or_load(true,bad,[]{return good();});
    check(other.stats().entries==0, "invalid identity bypasses retention");
  }
  bool threw=false;
  try { c.get_or_load(true,id('c'),[]{throw std::runtime_error("synthetic");return good();}); }
  catch(const std::runtime_error&){threw=true;}
  check(threw, "loader exception propagated");
  check(c.get_or_load(true,id('c'),[]{return good(5);}).vectors[0][0]==5, "error not negative-cached");
}
void limits_and_time() {
  std::atomic<long long> tick{0};
  auto now=[&]{return Cache::Time{}+std::chrono::milliseconds(tick.load());};
  Cache c({2,1024,std::chrono::milliseconds(60000)},now);int loads=0;
  auto load=[&]{++loads;return good();};
  c.get_or_load(true,id('a'),load);c.get_or_load(true,id('b'),load);c.get_or_load(true,id('a'),load);
  c.get_or_load(true,id('c'),load);
  check(c.stats().entries==2 && c.stats().evicted==1, "entry cap enforced");
  c.get_or_load(true,id('a'),load);check(loads==3, "LRU retains touched entry");
  c.get_or_load(true,id('b'),load);check(loads==4, "LRU evicted oldest key");
  c.clear();tick=0;c.get_or_load(true,id(),load);int before=loads;
  tick=59999;c.get_or_load(true,id(),load);check(loads==before, "before exact TTL is hit");
  tick=60000;c.get_or_load(true,id(),load);check(loads==before+1, "hit does not slide exact TTL");
  c.clear();tick=0;
  c.get_or_load(true,id(),[&]{tick=60000;return good();});
  check(c.stats().entries==0, "slow loader cannot install already expired result");
  c.clear();tick=100;c.get_or_load(true,id(),load);tick=99;before=loads;
  c.get_or_load(true,id(),load);check(loads==before+1, "backward injected time expires conservatively");
  Cache bytes({64,100,std::chrono::milliseconds(60000)});
  bytes.get_or_load(true,id('a'),[]{return good();});bytes.get_or_load(true,id('b'),[]{return good();});
  check(bytes.stats().entries==1 && bytes.stats().bytes==81, "defined key model vector payload cap");
  Cache too_small({64,80,std::chrono::milliseconds(60000)});
  too_small.get_or_load(true,id(),[]{return good();});
  check(too_small.stats().entries==0, "entry above payload budget bypasses");
  Cache full;
  for(int i=0;i<70;++i){auto ident=id();ident.key=std::string(60,'a')+"0000";const char* hex="0123456789abcdef";ident.key[62]=hex[i/16];ident.key[63]=hex[i%16];full.get_or_load(true,ident,[]{return good();});}
  check(full.stats().entries==64 && full.stats().bytes<=1048576, "production entry bound");
  for(int which=0;which<4;++which){bool rejected=false;auto lim=Cache::Limits{};if(which==0)lim.entries=0;if(which==1)lim.entries=65;if(which==2)lim.bytes=1048577;if(which==3)lim.ttl=std::chrono::milliseconds(0);try{Cache bad(lim);}catch(const std::invalid_argument&){rejected=true;}check(rejected,"invalid constructor bounds rejected");}
}
void generation_and_reentrancy() {
  Cache c;int loads=0;
  c.get_or_load(true,id(),[&]{++loads;c.clear();return good();});
  check(c.stats().entries==0, "clear during load fences late insert");
  c.get_or_load(true,id(),[&]{++loads;c.get_or_load(false,id(),[]{return good();});return good();});
  check(c.stats().entries==0, "disable during load fences late insert");
  c.get_or_load(true,id(),[&]{++loads;c.get_or_load(true,id('c','d'),[]{return good(7);});c.get_or_load(true,id('d','b'),[]{return good(8);});return good(9);});
  auto before=c.stats().loads;
  auto r=c.get_or_load(true,id(),[]{return good(10);});
  check(r.vectors[0][0]==10 && c.stats().loads==before+1, "A B A generation prevents old result repopulation");
  c.clear();
  std::promise<void> entered, release; auto signal=release.get_future().share();
  auto task=std::async(std::launch::async,[&]{return c.get_or_load(true,id(),[&]{entered.set_value();signal.wait();return good();});});
  check(entered.get_future().wait_for(std::chrono::seconds(3))==std::future_status::ready, "loader starts outside cache lock");
  c.clear();release.set_value();check(task.get().ok && c.stats().entries==0, "cross-thread reset preserves provider success without caching");
}
void concurrent_misses() {
  Cache c;std::barrier rendezvous(8);std::atomic<int> loads=0;
  std::vector<std::future<Result>> futures;
  for(int i=0;i<8;++i)futures.push_back(std::async(std::launch::async,[&]{return c.get_or_load(true,id(),[&]{++loads;rendezvous.arrive_and_wait();return good();});}));
  for(auto& f:futures)check(f.get().vectors==good().vectors, "concurrent caller receives valid own result");
  check(loads==8 && c.stats().entries==1 && c.stats().stored==1, "concurrent misses allowed; only one retained entry");
  c.get_or_load(true,id(),[&]{++loads;return good();});check(loads==8, "subsequent concurrent result hit");
}
}
int main(){try{basic();invalid_results();limits_and_time();generation_and_reentrancy();concurrent_misses();std::cout<<J({{"schema","qbrain-n48v-cache-tests-v1"},{"passed",true},{"check_count",checks.size()},{"checks",checks},{"provider_network_requests",0}}).dump()<<'\n';return 0;}catch(const std::exception& e){std::cout<<J({{"passed",false},{"checks",checks},{"failure",e.what()}}).dump()<<'\n';return 1;}}
