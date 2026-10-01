#pragma once
// Cursor project Hook protocol, not a Claude-compatible event envelope.
#include "qbrain/util/paths.hpp"
#include "qbrain/util/utf8_display.hpp"
#include <filesystem>
#include <nlohmann/json.hpp>
#include <stdexcept>
#include <string>

namespace qbrain::integration::detail::cursor {
using J = nlohmann::json;
namespace fs = std::filesystem;
inline void require(bool ok) { if (!ok) throw std::runtime_error("invalid_cursor_event"); }
inline std::string text(const J& j, const char* key, std::size_t cap, bool empty=false) {
  require(j.contains(key) && j[key].is_string());
  auto value=j[key].get<std::string>();
  require(value.size()<=cap && (empty||!value.empty()) && value.find('\0')==std::string::npos && util::valid_utf8(value));
  return value;
}
inline J noop(const J& input) {
  if(input.is_object() && input.contains("hook_event_name") && input["hook_event_name"]=="beforeSubmitPrompt")
    return J{{"continue",true}};
  return J::object();
}
// Only projected fields survive. Input model/email/attachment/transcript are ignored.
inline J normalize(const J& raw, const fs::path& installed_root, const fs::path& actual_cwd) {
  require(raw.is_object());
  const auto name=text(raw,"hook_event_name",32);
  std::string kind;
  if(name=="sessionStart")kind="SessionStart";
  else if(name=="beforeSubmitPrompt")kind="UserPromptSubmit";
  else if(name=="afterAgentResponse")kind="Stop";
  else if(name=="preCompact")kind="PreCompact";
  else if(name=="sessionEnd")kind="SessionEnd";
  else throw std::runtime_error("unsupported_cursor_event");
  require(raw.contains("workspace_roots") && raw["workspace_roots"].is_array() && raw["workspace_roots"].size()==1);
  J workspace={{"root",raw["workspace_roots"][0]}};
  const auto root=util::utf8_to_path(text(workspace,"root",4096));
  require(root.is_absolute() && installed_root.is_absolute() && actual_cwd.is_absolute());
  require(fs::equivalent(fs::canonical(root),fs::canonical(installed_root)) &&
          fs::equivalent(fs::canonical(actual_cwd),fs::canonical(installed_root)));
  if(raw.contains("cwd")) {
    const auto cwd=util::utf8_to_path(text(raw,"cwd",4096));
    require(cwd.is_absolute() && fs::equivalent(fs::canonical(cwd),fs::canonical(actual_cwd)));
  }
  if(raw.contains("is_background_agent"))require(raw["is_background_agent"].is_boolean() && !raw["is_background_agent"].get<bool>());
  const auto session=text(raw,"conversation_id",128);
  if(raw.contains("session_id"))require(text(raw,"session_id",128)==session);
  J event={{"hook_event_name",kind},{"session_id",session},{"cwd",util::path_to_utf8(actual_cwd)}};
  if(name=="beforeSubmitPrompt" || name=="afterAgentResponse") {
    event["turn_id"]=text(raw,"generation_id",128);
    if(name=="beforeSubmitPrompt")event["prompt"]=text(raw,"prompt",131072,true);
    else event["last_assistant_message"]=text(raw,"text",131072,true);
  }
  return event;
}
inline J output(const J& internal) {
  if(internal.empty())return J::object();
  require(internal.is_object() && internal.contains("hookSpecificOutput"));
  const auto& value=internal["hookSpecificOutput"];
  require(value.is_object() && value.value("hookEventName",std::string())=="SessionStart");
  return J{{"additional_context",text(value,"additionalContext",8192)}};
}
} // namespace qbrain::integration::detail::cursor
