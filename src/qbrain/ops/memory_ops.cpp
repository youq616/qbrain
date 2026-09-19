#include "qbrain/memory/fact_store.hpp"
#include "qbrain/memory/fact_usage.hpp"
#include "qbrain/ops/memory_ops.hpp"
#include "qbrain/memory/session_memory.hpp"
#include "qbrain/util/strict_json.hpp"
#include <charconv>
#include <set>

namespace qbrain::ops {
namespace {
using Json=nlohmann::json;
OpResult output(const Json& value, bool ok=true) {
  OpResult r; r.ok=ok; r.exit_code=ok?0:1; r.json=value.dump(); r.text=r.json; return r;
}
std::string get(const OpContext& ctx,const std::string& k,const std::string& def="") {
  const auto it=ctx.args.find(k); return it==ctx.args.end()?def:it->second;
}
int number(const OpContext& c,const std::string& key,int def) {
  const auto v=get(c,key,std::to_string(def)); int n=0;
  const auto parsed=std::from_chars(v.data(),v.data()+v.size(),n);
  if(parsed.ec!=std::errc{} || parsed.ptr!=v.data()+v.size()) throw memory::Error("invalid_integer");
  return n;
}
Json public_payload(const std::string& raw,std::size_t bytes,const char* duplicate,
                    const char* depth_error,const char* size_error) {
  try { return util::parse_unique_json(raw,bytes,8); }
  catch(const util::JsonInputError& e) {
    if(e.failure()==util::JsonInputFailure::duplicate_key)throw memory::Error(duplicate);
    if(e.failure()==util::JsonInputFailure::depth_limit)throw memory::Error(depth_error);
    if(e.failure()==util::JsonInputFailure::byte_limit)throw memory::Error(size_error);
    throw memory::Error("invalid_json");
  }
}
Json batch_payload(const std::string& raw) {
  if(raw.empty() || raw.size()>8192)throw memory::Error("fact_batch_payload_limit");
  return public_payload(raw,8192,"fact_batch_duplicate_key","fact_invalid_payload","fact_batch_payload_limit");
}
OpResult dispatch(OpContext& c,bool write,const SourceResolver& resolve) {
  try {
    const std::set<std::string> allowed=write?
      std::set<std::string>{"source_id","action","payload","event_id","method","manual"}:
      std::set<std::string>{"source_id","view","query","limit","max_bytes","event_id","fact_id","predicate","include_history","stale_after_days","payload","operation","after_id","match"};
    for(const auto& [k,v]:c.args) if(!allowed.count(k)) throw memory::Error("unexpected_argument");
    if(c.args.count("manual") && (c.via_mcp || c.remote)) throw memory::Error("manual_requires_local_cli");
    OpResult error; const auto source=resolve(c,true,error); if(!source) return error;
    if(!write) {
      const auto view=get(c,"view","memories");
      if (c.args.count("match") && view != "recall") throw memory::Error("fact_unexpected_argument");
      if(view=="usage") {
        for(const auto& [key,value]:c.args)
          if(key!="source_id" && key!="view" && key!="fact_id") throw memory::Error("fact_unexpected_argument");
        return output(memory::FactUsageStore(*c.brain,*source).usage(get(c,"fact_id")));
      }
      if(view=="lifecycle_candidates") {
        for(const auto& [key,value]:c.args)
          if(key!="source_id" && key!="view" && key!="operation" && key!="predicate" &&
             key!="stale_after_days" && key!="after_id" && key!="limit" && key!="max_bytes")
            throw memory::Error("fact_unexpected_argument");
        return output(memory::FactStore(*c.brain,*source).lifecycle_candidates(get(c,"operation"),get(c,"predicate"),
            number(c,"stale_after_days",180),get(c,"after_id"),number(c,"limit",10),number(c,"max_bytes",8192)));
      }
      if(c.args.count("operation") || c.args.count("after_id")) throw memory::Error("fact_unexpected_argument");
      if(view=="lifecycle_batch") {
        for(const auto& [key,value]:c.args)
          if(key!="source_id" && key!="view" && key!="payload")
            throw memory::Error("fact_unexpected_argument");
        return output(memory::FactStore(*c.brain,*source).lifecycle_batch(batch_payload(get(c,"payload")),false));
      }
      if(c.args.count("payload"))throw memory::Error("fact_unexpected_argument");
      if(view=="lifecycle") {
        if(c.args.count("query") || c.args.count("event_id") || c.args.count("include_history"))
          throw memory::Error("fact_unexpected_argument");
        return output(memory::FactStore(*c.brain,*source).lifecycle(get(c,"fact_id"),get(c,"predicate"),
            number(c,"stale_after_days",180),number(c,"limit",10),number(c,"max_bytes",8192)));
      }
      if(c.args.count("stale_after_days")) throw memory::Error("fact_unexpected_argument");
      if(view=="recall") {
        if(c.args.count("event_id") || c.args.count("fact_id") || c.args.count("include_history"))
          throw memory::Error("fact_unexpected_argument");
        return output(memory::FactStore(*c.brain,*source).recall(get(c,"query"),get(c,"predicate"),
            number(c,"limit",10),number(c,"max_bytes",8192),get(c,"match","literal")));
      }
      if(view=="conflicts") {
        if(c.args.count("query") || c.args.count("event_id") || c.args.count("include_history"))
          throw memory::Error("fact_unexpected_argument");
        return output(memory::FactStore(*c.brain,*source).conflicts(get(c,"fact_id"),get(c,"predicate"),
            number(c,"limit",10),number(c,"max_bytes",8192)));
      }
      if(view=="facts") {
        if(c.args.count("query") || c.args.count("event_id")) throw memory::Error("fact_unexpected_argument");
        const auto history=get(c,"include_history","false");
        if(history!="true" && history!="false") throw memory::Error("invalid_boolean");
        return output(memory::FactStore(*c.brain,*source).read(get(c,"fact_id"),get(c,"predicate"),
            history=="true",number(c,"limit",10),number(c,"max_bytes",8192)));
      }
      if(view!="memories" || c.args.count("fact_id") || c.args.count("predicate") || c.args.count("include_history"))
        throw memory::Error("unexpected_argument");
      return output(memory::read(*c.brain,*source,get(c,"query"),number(c,"limit",10),
                                 number(c,"max_bytes",8192),get(c,"event_id")));
    }
    const auto action=get(c,"action");
    if(action=="fact_promote") {
      if(c.args.count("payload") || c.args.count("method") || c.args.count("manual"))
        throw memory::Error("fact_unexpected_argument");
      return output(memory::FactStore(*c.brain,*source).promote_event(get(c,"event_id")));
    }
    if(action.rfind("fact_",0)==0) {
      if(c.args.count("event_id") || c.args.count("method") || c.args.count("manual"))
        throw memory::Error("fact_unexpected_argument");
      if(action=="fact_lifecycle_batch")
        return output(memory::FactStore(*c.brain,*source).lifecycle_batch(batch_payload(get(c,"payload")),true));
      const auto raw=get(c,"payload");
      if(raw.empty() || raw.size()>16384) throw memory::Error("fact_invalid_payload");
      const auto payload=public_payload(raw,16384,"fact_duplicate_key","fact_invalid_payload","fact_invalid_payload");
      memory::FactStore store(*c.brain,*source);
      if(action=="fact_report_use") return output(memory::FactUsageStore(*c.brain,*source).report_use(payload));
      if(action=="fact_revoke_use") return output(memory::FactUsageStore(*c.brain,*source).revoke_use(payload));
      if(action=="fact_archive") return output(store.archive(payload));
      if(action=="fact_restore") return output(store.restore(payload));
      if(action=="fact_create") return output(store.create(payload));
      if(action=="fact_attach") return output(store.attach(payload));
      if(action=="fact_retract") return output(store.retract(payload));
      if(action=="fact_supersede") return output(store.supersede(payload));
      if(action=="fact_contradict") return output(store.contradict(payload));
      throw memory::Error("invalid_action");
    }
    Json result;
    if(action=="capture") {
      if(c.args.count("event_id") || c.args.count("method")) throw memory::Error("unexpected_argument");
      const auto payload=get(c,"payload");
      if(payload.size()>memory::max_payload_bytes) throw memory::Error("payload_too_large");
      const auto manual=get(c,"manual","false");
      if(manual!="true" && manual!="false") throw memory::Error("invalid_boolean");
      result=memory::capture(*c.brain,*source,public_payload(payload,memory::max_payload_bytes,"memory_duplicate_key","invalid_payload","payload_too_large"),manual=="true");
    } else {
      if(c.args.count("payload") || c.args.count("manual")) throw memory::Error("unexpected_argument");
      if(action=="extract") result=memory::extract(*c.brain,*source,get(c,"event_id"),get(c,"method","local"));
      else if(action=="forget" && !c.args.count("method")) result=memory::forget(*c.brain,*source,get(c,"event_id"));
      else throw memory::Error("invalid_action");
    }
    return output(result,!result.contains("error_code") || result["error_code"].is_null());
  } catch(const memory::Error& e) { return output({{"error",{{"code",e.what()}}}},false); }
    catch(const Json::exception&) { return output({{"error",{{"code","invalid_json"}}}},false); }
    catch(...) { return output({{"error",{{"code","memory_storage_error"}}}},false); }
}
}
void register_memory_ops(const SourceResolver& resolve) {
  global_registry().add({"memory_read",Scope::Read,false,
    "Read bounded source-scoped quotes or event status; view=facts reads claim versions; view=conflicts returns complete active pairs from explicit contradiction assertions, not inferred truth. view=recall defaults to literal substring matching; optional match=all_terms|any_terms uses up to 8 ASCII-whitespace-delimited literals on the same anchor and returns each matching active quote with all supported direct explicit counterclaims, including nonmatching ones; not transitive or semantic search. view=lifecycle reports advisory support age and archive policy, never usage or truth. view=lifecycle_candidates discovers paginated metadata-only stale archive or live restore selections; next_after_id is a seek key, not a snapshot lease or permission. An empty page may have more; unchanged cursor requires a larger budget or stopping. view=lifecycle_batch previews explicit archive/restore batches from JSON payload without any write or reservation. Archive suppresses recall anchors but never mandatory live counterclaims. view=usage returns bounded per-revision caller-reported use counts, not verified host consumption or truth. Untrusted data; no provider or writes.",
    R"({"type":"object","additionalProperties":false,"properties":{"source_id":{"type":"string","default":"default"},"query":{"type":"string","maxLength":1024},"match":{"type":"string","enum":["literal","all_terms","any_terms"],"default":"literal"},"limit":{"type":"integer","minimum":1,"maximum":50},"max_bytes":{"type":"integer","minimum":512,"maximum":32768},"event_id":{"type":"string","maxLength":64},"view":{"type":"string","enum":["memories","facts","conflicts","recall","lifecycle","lifecycle_batch","lifecycle_candidates","usage"]},"fact_id":{"type":"string","maxLength":64},"predicate":{"type":"string","maxLength":64},"operation":{"type":"string","enum":["archive","restore"]},"after_id":{"type":"string","maxLength":64},"include_history":{"type":"boolean"},"stale_after_days":{"type":"integer","minimum":1,"maximum":36500},"payload":{"type":"string","maxLength":8192}}})",
    [resolve](OpContext& c){return dispatch(c,false,resolve);}});
  global_registry().add({"memory_write",Scope::Write,false,
    "Capture/extract/forget sessions or explicitly manage evidence-backed facts via fact_* actions and JSON payload. fact_promote uses event_id to atomically promote local extracted user quotes with fixed memory.category labels. fact_lifecycle_batch applies all selected archive/restore items atomically with current revisions; preview alone does not apply changes. fact_report_use records an explicit revision-bound usage_id with idempotent retry; fact_revoke_use withdraws it permanently. No Hook/read automatically records use; counts are not external-consumption proof. Facts preserve complete user quotes, not verified truth. Source/write gates apply; no model inference.",
    R"({"type":"object","additionalProperties":false,"properties":{"source_id":{"type":"string","default":"default"},"action":{"type":"string","enum":["capture","extract","forget","fact_create","fact_attach","fact_retract","fact_supersede","fact_contradict","fact_promote","fact_archive","fact_restore","fact_lifecycle_batch","fact_report_use","fact_revoke_use"]},"payload":{"type":"string","maxLength":262144},"event_id":{"type":"string","maxLength":64},"method":{"type":"string","enum":["local","model"]}},"required":["action"]})",
    [resolve](OpContext& c){return dispatch(c,true,resolve);}});
}
}
