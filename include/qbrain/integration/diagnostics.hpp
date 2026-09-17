#pragma once
#include "qbrain/integration/detail/hook_trace.hpp"
#include "qbrain/util/strict_json.hpp"
#include <filesystem>
#include <vector>

namespace qbrain::integration {
// Local administrative read, not a remotely callable MCP operation.
nlohmann::json inspect_hook_diagnostics(const std::filesystem::path& config,
    const std::string& event = {}, const std::string& session_key = {});
int run_hook_diagnostics(const std::vector<std::string>& args);
namespace detail {
// No rejected input bytes are returned. Equality with the canonical projection
// rejects unknown/nested fields rather than silently presenting a sanitized forgery.
inline nlohmann::json inspect_hook_checkpoint(std::string_view raw,
    const std::string& host, const std::string& event, const std::string& filter = {}) {
  using J=nlohmann::json;
  (void)hook_trace_filename(host,event);
  trace_require(filter.empty() || trace_hex_key(filter));
  J slot={{"event",event},{"state","invalid"}};
  if(raw.size()>max_hook_trace_bytes) {slot["state"]="oversized";return slot;}
  try {
    const auto in=util::parse_unique_json(raw,max_hook_trace_bytes,8);
    trace_require(in.is_object() && in.contains("format_version") &&
        in["format_version"].is_number_integer() && in["format_version"]==2 &&
        in.value("host",std::string())==host && in.value("event",std::string())==event &&
        in.contains("completed_at_unix_ms") && in["completed_at_unix_ms"].is_number_integer() &&
        in["completed_at_unix_ms"]>0 && in["completed_at_unix_ms"]<=253402300799999LL &&
        in.contains("provider_calls") && in["provider_calls"].is_number_integer() && in["provider_calls"]==0 &&
        in.contains("host_consumption_confirmed") && in["host_consumption_confirmed"].is_boolean() &&
        in["host_consumption_confirmed"]==false);
    const auto state=in.value("status",std::string());
    trace_require(state=="processed" || state=="failed");
    const auto key=in.value("session_key",std::string());
    const auto canonical=hook_trace_record(in,host,event,key,
        in["completed_at_unix_ms"].get<std::int64_t>(),state=="processed");
    trace_require(in==canonical);
    if(!filter.empty() && key!=filter){slot["state"]="session_mismatch";return slot;}
    slot["state"]="present";slot["record"]=canonical;
  } catch (...) { /* Fail closed; no raw input or exception text. */ }
  return slot;
}
} // namespace detail
} // namespace qbrain::integration
