#pragma once
#include <nlohmann/json.hpp>
#include <algorithm>
#include <cstdint>
#include <initializer_list>
#include <stdexcept>
#include <string>
#include <string_view>

namespace qbrain::integration::detail {
inline constexpr std::size_t max_hook_trace_bytes = 4096;
inline bool trace_choice(std::string_view value, std::initializer_list<std::string_view> allowed) {
  return std::find(allowed.begin(), allowed.end(), value) != allowed.end();
}
inline void trace_require(bool ok) {
  if (!ok) throw std::runtime_error("invalid_hook_trace_metadata");
}
// These ten names are a closed set, never a path supplied by an event or caller.
inline std::string hook_trace_filename(std::string_view host, std::string_view event) {
  trace_require(trace_choice(host,{"claude","codex"}) &&
    trace_choice(event,{"SessionStart","UserPromptSubmit","Stop","PreCompact","SessionEnd"}));
  return "trace-" + std::string(host) + "-" + std::string(event) + ".json";
}
inline bool trace_hex_key(std::string_view key) {
  return key.size()==64 && std::all_of(key.begin(),key.end(),[](unsigned char c) {
    return (c>='0' && c<='9') || (c>='a' && c<='f');
  });
}
// Only this projection is persisted. Future raw trace additions cannot silently
// start logging original data, storage exceptions or additionalContext contents.
inline nlohmann::json hook_trace_record(const nlohmann::json& input,
    std::string_view host, std::string_view event, std::string_view session_key,
    std::int64_t completed_at_ms, bool processed) {
  using J=nlohmann::json;
  (void)hook_trace_filename(host,event);
  trace_require(input.is_object() && trace_hex_key(session_key) &&
      completed_at_ms>0 && completed_at_ms<=253402300799999LL);
  trace_require(input.contains("phase") && input["phase"].is_string());
  const auto& phase=input["phase"].get_ref<const std::string&>();
  trace_require(trace_choice(phase,{"open","recall","capture","extract","promote","state","complete"}));
  trace_require(processed == (phase=="complete"));
  J out={{"format_version",2},{"host",host},{"event",event},{"session_key",session_key},
      {"completed_at_unix_ms",completed_at_ms},{"status",processed?"processed":"failed"},
      {"phase",phase},{"provider_calls",0},{"host_consumption_confirmed",false}};
  auto count=[&](const J& obj,const char* name,std::int64_t cap) {
    trace_require(obj.contains(name) && obj[name].is_number_integer() && obj[name]>=0 && obj[name]<=cap);
    return obj[name].get<std::int64_t>();
  };
  for (const auto* name:{"recall_count","fact_group_count"})
    if(input.contains(name))out[name]=count(input,name,16);
  if(input.contains("output_bytes"))out["output_bytes"]=count(input,"output_bytes",8192);
  for (const auto* name:{"context_truncated","fact_recall_enabled","fact_promotion_enabled"})
    if(input.contains(name)){trace_require(input[name].is_boolean());out[name]=input[name];}
  auto state=[&](const char* name,std::initializer_list<std::string_view> allowed) {
    if(!input.contains(name))return;
    trace_require(input[name].is_string() && trace_choice(input[name].get_ref<const std::string&>(),allowed));
    out[name]=input[name];
  };
  state("capture_status",{"archived","extracting","extracted","no_matches","failed","skipped"});
  state("extraction_status",{"archived","extracting","extracted","no_matches","failed","skipped"});
  state("fact_promotion_status",{"not_run","completed","failed"});
  if(input.contains("fact_promotion_counts")) {
    trace_require(out.value("fact_promotion_status",std::string())=="completed");
    const auto& counts=input["fact_promotion_counts"];trace_require(counts.is_object());
    J selected=J::object();std::int64_t sum=0;
    for(const auto* name:{"created","attached","duplicate","skipped_retired","skipped_limit"}) {
      const auto n=count(counts,name,32);selected[name]=n;sum+=n;
    }
    selected["total"]=count(counts,"total",32);
    trace_require(sum==selected["total"].get<std::int64_t>());
    out["fact_promotion_counts"]=std::move(selected);
  }
  trace_require(out.dump().size()<=max_hook_trace_bytes);
  return out;
}
}  // namespace qbrain::integration::detail
