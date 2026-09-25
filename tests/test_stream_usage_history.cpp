// N48H continuation: direct aggregate-history regressions, original tests intact.
#include "qbrain/accounting/stream_usage.hpp"
#include <functional>

using namespace qbrain::accounting;
namespace stream = qbrain::accounting::stream_import;
namespace {
int passed = 0;
void check(bool result, const char* label) {
  if (!result) throw std::runtime_error(label);
  ++passed;
}
void rejects(const std::function<void()>& action) {
  try { action(); }
  catch (const Error& e) {
    check(std::string(e.what()) == "stream_usage_lower_bound", "exact history error");
    return;
  }
  throw std::runtime_error("contradictory aggregate accepted");
}
Json response(const char* status, const Json& usage) {
  return {{"id", "review-response"}, {"model", "synthetic"},
          {"object", "response"}, {"status", status}, {"usage", usage}};
}
std::vector<stream::Event> response_events(const Json& early, const Json& final,
                                         bool reset, int origin = 0) {
  std::vector<stream::Event> result;
  auto append = [&](const char* type, const char* status, const Json& usage) {
    Json j = {{"type", type}, {"sequence_number", origin++},
              {"response", response(status, usage)}};
    result.push_back({type, j.dump()});
  };
  append("response.created", "in_progress", early);
  if (reset) append("response.in_progress", "in_progress", nullptr);
  append("response.completed", "completed", final);
  return result;
}
std::vector<stream::Event> anthropic_events(const Json& early, const Json& final,
                                          bool reset) {
  Json start = {{"type", "message_start"}, {"message", {
      {"id", "review-message"}, {"model", "synthetic"}, {"type", "message"},
      {"role", "assistant"}, {"content", Json::array()}, {"usage", early}}}};
  std::vector<stream::Event> result = {{"message_start", start.dump()}};
  if (reset) {
    Json middle = {{"type", "message_delta"}, {"delta", Json::object()}, {"usage", nullptr}};
    result.push_back({"message_delta", middle.dump()});
  }
  Json delta = {{"type", "message_delta"}, {"delta", {{"stop_reason", "end_turn"}}},
                {"usage", final}};
  result.push_back({"message_delta", delta.dump()});
  result.push_back({"message_stop", "{\"type\":\"message_stop\"}"});
  return result;
}
}
int main() {
  try {
    for (bool reset : {false, true}) for (int origin : {0, 1}) {
      for (bool explicit_null : {false, true}) {
        Json final = {{"input_tokens", 5}, {"output_tokens", 5}};
        if (explicit_null) final["total_tokens"] = nullptr;
        rejects([&] { stream::responses(response_events({{"total_tokens", 100}}, final, reset, origin)); });
        final["input_tokens"] = 95;
        check(stream::responses(response_events({{"total_tokens", 100}}, final, reset, origin)).response["usage"] == final,
              "equal derived total stays final-only");
        final["input_tokens"] = 96;
        check(stream::responses(response_events({{"total_tokens", 100}}, final, reset, origin)).response["usage"] == final,
              "increasing derived total accepted");
        final["input_tokens"] = nullptr;
        check(stream::responses(response_events({{"total_tokens", 100}}, final, reset, origin)).response["usage"]["input_tokens"].is_null(),
              "missing partition is not filled from history");
      }
    }
    for (bool reset : {false, true}) for (bool long_ttl : {false, true}) {
      Json early = {{"input_tokens", 10}, {"output_tokens", 0},
                    {"cache_read_input_tokens", 0}, {"cache_creation_input_tokens", 100}};
      auto usage = [&](int value) -> Json {
        return {{"output_tokens", 10}, {"cache_creation_input_tokens", nullptr},
                {"cache_creation", {{"ephemeral_5m_input_tokens", long_ttl ? 0 : value},
                                    {"ephemeral_1h_input_tokens", long_ttl ? value : 0}}}};
      };
      rejects([&] { stream::anthropic(anthropic_events(early, usage(10), reset)); });
      for (int value : {100, 101}) {
        auto r = stream::anthropic(anthropic_events(early, usage(value), reset));
        check(usage_import::anthropic_usage(r.response["usage"]).tokens[2] == value,
              "TTL equality/increase accepted without summing snapshots");
      }
    }
    std::map<std::string, Amount> observed = {{"/total_tokens", token_cap}};
    stream::openai_bounds({{"input_tokens", token_cap}, {"output_tokens", token_cap}}, observed);
    check(true, "large current partition uses checked addition");
    rejects([&] { stream::openai_bounds({{"input_tokens", token_cap - 1}, {"output_tokens", 0}}, observed); });
    observed = {{"/cache_creation_input_tokens", token_cap}};
    rejects([&] { stream::anthropic_bounds({{"cache_creation", {{"ephemeral_5m_input_tokens", token_cap - 1},
                                                                {"ephemeral_1h_input_tokens", 0}}}}, observed); });
    std::cout << Json{{"schema", "qbrain-n48h-history-direct-v1"}, {"passed", passed}, {"failed", 0}}.dump() << '\n';
    return 0;
  } catch (const std::exception& e) {
    std::cerr << "FAIL after " << passed << ": " << e.what() << '\n';
    return 1;
  }
}
