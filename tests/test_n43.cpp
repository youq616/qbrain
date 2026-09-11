#include "qbrain/memory/session_memory.hpp"
#include "qbrain/ops/registry.hpp"
#include "qbrain/util/hash.hpp"
#include "qbrain/util/paths.hpp"
#include <iostream>
#include <memory>
#include <stdexcept>

namespace {
using namespace qbrain;
using J = nlohmann::json;
int checks = 0;
void check(bool ok, const char* label) {
  if (!ok) throw std::runtime_error(std::string("N43: ")+label);
  ++checks;
}
template<class F> void denied(F fn, const std::string& code) {
  try { fn(); } catch (const memory::Error& e) { check(e.what()==code,"expected error code"); return; }
  throw std::runtime_error("N43: expected rejection "+code);
}
std::unique_ptr<Brain> fresh() {
  auto b=std::make_unique<Brain>(); b->open_at(":memory:"); b->ensure_source("alpha"); b->ensure_source("beta");
  b->save_config_value("memory.writeback","salient"); return b;
}
J payload(std::string fragment="0-3",std::string session="会话 😀") {
  return {{"session_id",session},{"fragment_id",fragment},{"messages",J::array({
    {{"role","user"},{"content","我偏好使用中文回答，并且不要使用 Docker。😀"}},
    {{"role","assistant"},{"content","I prefer invented assistant assertions."}},
    {{"role","tool"},{"content","I prefer fabricated tool assertions."}},
    {{"role","user"},{"content","I decided to keep the Windows native implementation."}}
  })}};
}
int64_t count(Brain& b,const std::string& table) {
  auto s=b.db().prepare("SELECT COUNT(*) FROM "+table); s.step(); return s.column_int(0);
}
std::string cap(Brain& b,const J& p=payload(),const std::string& source="alpha") {
  return memory::capture(b,source,p)["event_id"].get<std::string>();
}
J candidates(const J& p) {
  return J::array({{{"message_index",0},{"category","preference"},{"quote",p["messages"][0]["content"]}}});
}
ai::ChatResult response(const J& value) {
  ai::ChatResult r; r.ok=true; r.content=value.dump(); r.input_tokens=31; r.output_tokens=17; return r;
}
}
void test_n43() {
  using namespace qbrain; checks=0;
  check(util::sha256_hex("")=="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","SHA empty");
  check(util::sha256_hex("abc")=="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad","SHA abc");
  check(util::sha256_hex(std::string(1000000,'a'))=="cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0","SHA million a");
  check(util::sha256_hex(std::string("a\0b",3))!=util::sha256_hex("a"),"SHA embedded NUL");
  {
    auto b=fresh();
    const auto schema=count(*b,"sqlite_master");
    auto empty=memory::read(*b,"alpha");
    check(empty["initialized"]==false && empty["items"].empty(),"read uninitialized");
    check(count(*b,"sqlite_master")==schema,"read does not create schema");
    b->save_config_value("memory.writeback","off");
    check(memory::capture(*b,"alpha",payload())["status"]=="skipped","automatic off");
    check(count(*b,"sqlite_master")==schema && count(*b,"pages")==0,"off no archive or DDL");
    auto manual=memory::capture(*b,"alpha",payload(),true);
    check(manual["status"]=="archived" && manual["extracted"]==false,"manual is only archival");
    check(memory::extract(*b,"alpha",manual["event_id"])["item_count"]==2,"manual explicit local extraction");
  }
  {
    auto b=fresh(); const auto p=payload(); auto id=cap(*b,p);
    check(memory::capture(*b,"alpha",p)["duplicate"]==true,"capture retry idempotent");
    check(count(*b,"pages")==1 && count(*b,"page_versions")==0 && count(*b,"jobs")==0,"no overwrite or embeddings");
    auto changed=p; changed["messages"][0]["content"]="我偏好不同内容";
    denied([&]{memory::capture(*b,"alpha",changed);},"fragment_conflict");
    check(cap(*b,p,"beta")!=id,"source in identity");
    check(cap(*b,payload("0-3","second"))!=id,"same-second session separation");
    auto result=memory::extract(*b,"alpha",id);
    check(result["item_count"]==2 && result["provider_attempts"]==0,"only local supported user statements");
    auto again=memory::extract(*b,"alpha",id);
    check(again["duplicate"]==true && count(*b,"memory_items")==2,"extraction retry idempotent");
    auto rows=memory::read(*b,"alpha"); check(rows["items"].size()==2,"read user memories");
    check(rows.dump().find("invented")==std::string::npos && rows.dump().find("fabricated")==std::string::npos,"no assistant or tool claims");
    check(rows.dump().find("😀")!=std::string::npos,"UTF-8 emoji");
    check(memory::read(*b,"beta")["items"].empty(),"no cross-source read");
    denied([&]{memory::extract(*b,"beta",id);},"event_not_found");
    check(memory::read(*b,"alpha","Docker")["items"].size()==1,"literal keyword recall");
    auto bounded=memory::read(*b,"alpha","",50,512);
    check(bounded.dump().size()<=512 && bounded["truncated"]==true,"bounded JSON output");
    denied([&]{memory::read(*b,"alpha","",51);},"invalid_read_budget");
    b->save_config_value("memory.writeback","off");
    denied([&]{memory::extract(*b,"alpha",id);},"writeback_off");
  }
  {
    auto b=fresh(); auto bad=payload(); bad["messages"][0]["content"]="api_key="+std::string("fake-unit-test-not-a-key");
    const auto tables=count(*b,"sqlite_master");
    denied([&]{memory::capture(*b,"alpha",bad);},"sensitive_material_rejected");
    check(count(*b,"pages")==0 && count(*b,"sqlite_master")==tables,"secret blocked before persistence");
    bad=payload(); bad["messages"][0]["content"]=std::string("\xc0\xaf",2);
    denied([&]{memory::capture(*b,"alpha",bad);},"invalid_text");
    bad=payload(); bad["unexpected"]=true;
    denied([&]{memory::capture(*b,"alpha",bad);},"unexpected_argument");
    bad=payload(); bad["messages"][0]["role"]="developer";
    denied([&]{memory::capture(*b,"alpha",bad);},"invalid_role");
    bad=payload(); bad["expires_at"]=-1;
    denied([&]{memory::capture(*b,"alpha",bad);},"invalid_expiry");
    check(memory::contains_sensitive_material("密码：fake-value"),"Chinese secret label");
  }
  {
    auto b=fresh(); auto p=payload(); auto id=cap(*b,p);
    denied([&]{memory::extract(*b,"alpha",id,"model");},"external_extraction_denied");
    check(count(*b,"memory_attempts")==0,"no provider attempted without consent");
    b->save_config_value("memory.external_extraction","allow");
    int calls=0;
    auto provider=[&](const std::vector<ai::ChatMessage>& messages,int timeout) {
      ++calls; check(timeout==60000,"bounded provider timeout");
      check(messages.size()==2 && messages[1].content.find("assistant")==std::string::npos,"provider gets user text only");
      return response(candidates(p));
    };
    auto result=memory::extract(*b,"alpha",id,"model",provider);
    check(result["item_count"]==1 && calls==1,"grounded model seam publishes exact quote");
    check(memory::extract(*b,"alpha",id,"model",provider)["duplicate"]==true && calls==1,"provider not repeated after success");
    auto status=memory::read(*b,"alpha","",10,8192,id);
    check(status["usage"][0]["input_tokens"]==31 && status["usage"][0]["output_tokens"]==17,"provider usage retained");
    check(status["usage"][0]["cost"].is_null(),"unknown monetary cost not zero");
    check(memory::read(*b,"alpha","",10,512,id).dump().size()<=512,"status budget");
  }
  {
    auto b=fresh(); auto p=payload(); auto id=cap(*b,p); b->save_config_value("memory.external_extraction","allow");
    auto invalid=candidates(p);
    invalid.push_back({{"message_index",1},{"category","preference"},{"quote",p["messages"][1]["content"]}});
    auto bad=[&](const auto&,int){return response(invalid);};
    auto r=memory::extract(*b,"alpha",id,"model",bad);
    check(r["error_code"]=="ungrounded_extraction" && count(*b,"memory_items")==0,"batch atomic rejection for assistant claim");
    auto partial=candidates(p); partial[0]["quote"]="使用 Docker";
    denied([&]{memory::validate_candidates(p["messages"],partial,"salient");},"ungrounded_extraction");
    auto duplicate=candidates(p); duplicate.push_back(duplicate[0]);
    check(memory::validate_candidates(p["messages"],duplicate,"salient").size()==1,"duplicate candidate de-duplication");
    check(memory::extract(*b,"alpha",id,"local")["item_count"]==2,"explicit retry after invalid model output");
    check(count(*b,"memory_attempts")==2,"retry history retained");
  }
  for (int kind=0;kind<5;++kind) {
    auto b=fresh(); auto p=payload(); if(kind==2) p["expires_at"]=1;
    const auto id=cap(*b,p); const auto slug="sessions/"+id;
    if(kind==0) b->soft_delete(slug,"alpha");
    if(kind==1) { PageInput x; x.source_id="alpha";x.slug=slug;x.title="changed";x.body="new body";b->put_page(x); }
    if(kind<=2) denied([&]{memory::extract(*b,"alpha",id);},"evidence_unavailable");
    else {
      memory::extract(*b,"alpha",id);
      if(kind==3) b->soft_delete(slug,"alpha");
      if(kind==4) b->db().exec("UPDATE pages SET body='tampered without updating hash'");
    }
    check(memory::read(*b,"alpha")["items"].empty(),"deleted edited expired or corrupt evidence hidden");
  }
  {
    auto b=fresh(); const auto p=payload(); const auto id=cap(*b,p);
    memory::extract(*b,"alpha",id); auto r=memory::forget(*b,"alpha",id);
    check(r["status"]=="forgotten" && count(*b,"memory_items")==0 && count(*b,"pages")==0,"forget deletes owned archive and memory");
    check(memory::capture(*b,"alpha",p)["status"]=="forgotten","tombstone prevents replay resurrection");
    denied([&]{memory::extract(*b,"alpha",id);},"event_forgotten");
    check(count(*b,"memory_events")==1,"tombstone retained");
  }
  {
    auto b=fresh(); const auto id=cap(*b);
    b->soft_delete("sessions/"+id,"alpha");
    memory::forget(*b,"alpha",id);
    check(count(*b,"pages")==0,"forget also removes unchanged soft-deleted archive");
  }
  {
    auto b=fresh(); const auto p=payload(); const auto id=cap(*b,p);
    b->save_config_value("memory.external_extraction","allow");
    auto revoke=[&](const auto&,int){memory::forget(*b,"alpha",id); return response(candidates(p));};
    denied([&]{memory::extract(*b,"alpha",id,"model",revoke);},"stale_extraction");
    check(count(*b,"memory_items")==0 && memory::read(*b,"alpha","",10,8192,id)["status"]=="forgotten","late provider cannot resurrect forgotten event");
  }
  {
    auto b=fresh(); const auto p=payload(); const auto id=cap(*b,p);
    b->save_config_value("memory.external_extraction","allow");
    auto revoke=[&](const auto&,int){b->save_config_value("memory.external_extraction","deny");return response(candidates(p));};
    check(memory::extract(*b,"alpha",id,"model",revoke)["error_code"]=="external_extraction_denied","consent rechecked after provider");
    check(count(*b,"memory_items")==0,"revoked policy prevents publication");
  }
  {
    auto b=fresh(); const auto p=payload(); const auto id=cap(*b,p);
    b->save_config_value("memory.external_extraction","allow");
    auto stale=[&](const auto&,int){b->db().exec("UPDATE memory_events SET lease_until=0");return response(candidates(p));};
    denied([&]{memory::extract(*b,"alpha",id,"model",stale);},"stale_extraction");
    check(count(*b,"memory_items")==0,"expired worker publishes nothing");
    check(memory::extract(*b,"alpha",id)["item_count"]==2,"expired lease recovers");
    check(memory::read(*b,"alpha","",10,8192,id).dump().find("abandoned_usage_unknown")!=std::string::npos,"abandoned usage remains unknown");
  }
  {
    auto b=fresh(); auto id=cap(*b);
    b->db().exec("CREATE TRIGGER n43_fail BEFORE INSERT ON memory_items BEGIN SELECT RAISE(ABORT,'injected'); END;");
    bool failed=false;try{memory::extract(*b,"alpha",id);}catch(const std::exception&){failed=true;}
    check(failed && count(*b,"memory_items")==0,"publication failure rolls back all rows");
    b->db().exec("DROP TRIGGER n43_fail; UPDATE memory_events SET lease_until=0;");
    check(memory::extract(*b,"alpha",id)["item_count"]==2,"publication retry recovers after crash lease");
  }
  {
    auto b=fresh(); auto p=payload(); p["messages"]=J::array({{{"role","user"},{"content","I use Windows 11."}}});
    const auto id=cap(*b,p); check(memory::extract(*b,"alpha",id)["status"]=="no_matches","salient excludes general facts");
    b->save_config_value("memory.writeback","all"); p["fragment_id"]="all";
    check(memory::extract(*b,"alpha",cap(*b,p))["item_count"]==1,"all mode explicit fact marker");
    p["fragment_id"]="tighten"; const auto tightened=cap(*b,p); b->save_config_value("memory.writeback","salient");
    check(memory::extract(*b,"alpha",tightened)["item_count"]==0,"tightened policy wins");
    p["fragment_id"]="raw";p["messages"][0]["role"]="unknown";
    check(memory::extract(*b,"alpha",cap(*b,p))["item_count"]==0,"unlabelled legacy text never a user fact");
  }
  {
    auto b=fresh(); ops::register_builtin_ops(); ops::OpContext c;c.brain=b.get();c.via_mcp=true;
    c.args={{"action","capture"},{"source_id","alpha"},{"payload",payload().dump()}};
    const auto tables=count(*b,"sqlite_master");
    check(!ops::global_registry().call("memory_write",c).ok,"MCP write default deny");
    c.allow_write=true;
    check(!ops::global_registry().call("memory_write",c).ok,"source allowlist also required");
    check(count(*b,"sqlite_master")==tables,"denied calls do not initialize memory schema");
    b->save_config_value("mcp.allowed_sources","alpha");c.args["manual"]="true";
    check(!ops::global_registry().call("memory_write",c).ok,"MCP cannot claim local manual bypass");
    c.args.erase("manual");auto r=ops::global_registry().call("memory_write",c);check(r.ok,"MCP allowed source capture");
    c.args={{"source_id","beta"}};
    check(!ops::global_registry().call("memory_read",c).ok,"MCP reads source scoped");
    c.args={{"source_id","alpha"},{"limit","oops"}};
    check(!ops::global_registry().call("memory_read",c).ok,"strict numeric arguments");
    c.args={{"action","capture"},{"payload",payload().dump()},{"source_id","alpha"}};
    c.remote=true; check(!ops::global_registry().call("memory_write",c).ok,"network writes require capability not local flag");
  }
#ifdef _WIN32
  {
    const std::string utf8="中文 空格 😀";
    check(util::wide_to_utf8(util::utf8_to_wide(utf8))==utf8,"native UTF-16 roundtrip");
    bool bad=false;try{util::utf8_to_wide(std::string("\xc0\xaf",2));}catch(...){bad=true;}
    check(bad,"invalid UTF-8 rejected");
    bad=false;try{util::wide_to_utf8(std::wstring(1,wchar_t(0xd800)));}catch(...){bad=true;}
    check(bad,"unpaired UTF-16 surrogate rejected");
  }
#endif
  std::cout << "[N43] " << checks << " checks passed; synthetic data; provider seam only, no live model.\n";
}
#ifdef QBRAIN_MEMORY_STANDALONE
int main() { try { test_n43(); return 0; } catch(const std::exception& e) {std::cerr<<e.what()<<"\n";return 1;} }
#endif
