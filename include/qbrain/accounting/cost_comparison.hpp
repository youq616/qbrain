#pragma once
// N48I: bounded paired ledger analysis. No network, filesystem or brain access.
#include "qbrain/accounting/token_cost.hpp"
#include <numeric>

namespace qbrain::accounting::comparison {
inline constexpr std::size_t comparison_input_cap = 1048576;
inline constexpr std::size_t comparison_output_cap = 8388608;
inline constexpr std::size_t task_cap = 128;

inline std::string fingerprint(const Json& value) {
  need(value.is_string(), "comparison_digest");
  const auto s = value.get<std::string>();
  need(s.size() == 64, "comparison_digest");
  for (char ch : s) need((ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f'), "comparison_digest");
  return s;
}

// Only called on a freshly recomputed N48F report, never on a caller's report.
inline Amount report_units(const Json& value) {
  const auto s = value.get<std::string>();
  Amount result = 0;
  for (char ch : s) {
    if (ch == '.') continue;
    need(ch >= '0' && ch <= '9', "comparison_internal_amount");
    result = add(multiply(result, 10), static_cast<Amount>(ch - '0'));
  }
  return result;
}

inline Json change(const Json& baseline, const Json& candidate, bool eligible) {
  Json result = {{"candidate_minus_baseline", nullptr}, {"relative_change", nullptr}};
  if (!eligible) { result["unavailable_reason"] = "comparison_not_eligible"; return result; }
  const auto a = report_units(baseline.at("known_subtotal"));
  const auto b = report_units(candidate.at("known_subtotal"));
  const bool negative = b < a;
  const Amount magnitude = negative ? a - b : b - a;
  const std::string sign = negative ? "-" : "";
  result["candidate_minus_baseline"] = sign + decimal(magnitude, cost_scale, 12);
  result["unavailable_reason"] = nullptr;
  if (a == 0) { result["relative_change_unavailable_reason"] = "zero_baseline"; return result; }
  const auto divisor = std::gcd(magnitude, a);
  result["relative_change"] = {{"numerator", sign + std::to_string(magnitude / divisor)},
                                {"denominator", std::to_string(a / divisor)}};
  result["relative_change_unavailable_reason"] = nullptr;
  return result;
}

struct Task {
  std::string digest;
  std::vector<std::string> calls;
  Json summary;
};
struct Arm {
  std::string label, conditions;
  bool ledger_complete = false, primary_known = true;
  std::set<std::string> primary_models, primary_prices;
  std::map<std::string, Task> tasks;
  std::map<std::string, Json> calls, rates, stages;
  std::vector<std::string> shared;
  Json costs, shared_summary;
};

inline std::vector<std::string> own_calls(const Json& ids, const Arm& arm,
                                         std::set<std::string>& owned, bool shared) {
  need(ids.is_array() && ids.size() <= 512 && (shared || !ids.empty()), "comparison_call_ids");
  std::vector<std::string> result;
  bool main_seen = false;
  for (const auto& value : ids) {
    const auto key = id(value);
    const auto call = arm.calls.find(key);
    need(call != arm.calls.end(), "comparison_call_missing");
    need(owned.insert(key).second, "comparison_call_reused");
    const bool main = call->second.at("stage") == "main";
    need(!shared || !main, "comparison_shared_main");
    main_seen |= main;
    result.push_back(key);
  }
  need(shared || main_seen, "comparison_main_missing");
  std::sort(result.begin(), result.end());
  return result;
}

inline Json subset_summary(const Json& input, const Arm& arm, const std::vector<std::string>& ids) {
  Json subset = input;
  subset["calls"] = Json::array();
  for (const auto& key : ids) subset["calls"].push_back(arm.calls.at(key));
  return accounting::report(subset).at("summary");
}

inline Arm read_arm(const Json& value, const Json& currency) {
  exact(value, {"label", "conditions_sha256", "ledger_complete", "cost_input", "tasks", "shared_call_ids"});
  Arm arm;
  arm.label = id(value["label"]);
  arm.conditions = fingerprint(value["conditions_sha256"]);
  need(value["ledger_complete"].is_boolean(), "comparison_coverage_flag");
  arm.ledger_complete = value["ledger_complete"].get<bool>();
  const auto& input = value["cost_input"];
  need(input.dump().size() <= accounting::input_cap, "comparison_ledger_limit");
  arm.costs = accounting::report(input);
  need(input.at("currency") == currency, "comparison_currency");
  for (const auto& c : input.at("calls")) arm.calls.emplace(c.at("call_id").get<std::string>(), c);
  for (const auto& r : input.at("rates")) arm.rates.emplace(r.at("rate_id").get<std::string>(), r);
  for (const auto& s : arm.costs.at("by_stage")) arm.stages.emplace(s.at("stage").get<std::string>(), s);
  need(value["tasks"].is_array() && !value["tasks"].empty() && value["tasks"].size() <= task_cap,
       "comparison_task_count");
  std::set<std::string> owned;
  for (const auto& t : value["tasks"]) {
    exact(t, {"task_id", "task_sha256", "call_ids"});
    const auto key = id(t["task_id"]);
    need(arm.tasks.count(key) == 0, "comparison_duplicate_task");
    Task task;
    task.digest = fingerprint(t["task_sha256"]);
    task.calls = own_calls(t["call_ids"], arm, owned, false);
    task.summary = subset_summary(input, arm, task.calls);
    arm.tasks.emplace(key, std::move(task));
  }
  arm.shared = own_calls(value["shared_call_ids"], arm, owned, true);
  need(owned.size() == arm.calls.size(), "comparison_unassigned_call");
  arm.shared_summary = subset_summary(input, arm, arm.shared);
  // Require one known primary identity and price schedule, including failed retries.
  for (const auto& [key, c] : arm.calls) {
    (void)key;
    if (c.at("stage") != "main") continue;
    const auto card = arm.rates.find(c.at("rate_id").get<std::string>());
    if (card == arm.rates.end()) { arm.primary_known = false; continue; }
    const auto& r = card->second;
    arm.primary_models.insert(Json::array({r.at("provider"), r.at("model")}).dump());
    arm.primary_prices.insert(normalized(amounts(r.at("per_million"), true), true).dump());
  }
  return arm;
}

inline Json binding(const Arm& arm) {
  Json tasks = Json::array();
  for (const auto& [key, task] : arm.tasks)
    tasks.push_back({{"task_id", key}, {"task_sha256", task.digest}, {"call_ids", task.calls}});
  return {{"label", arm.label}, {"conditions_sha256", arm.conditions}, {"ledger_complete", arm.ledger_complete},
          {"cost_input_sha256", arm.costs.at("input_sha256")}, {"tasks", tasks}, {"shared_call_ids", arm.shared}};
}

inline Json report(const Json& root) {
  exact(root, {"schema", "comparison_id", "currency", "baseline", "candidate"});
  need(root["schema"] == "qbrain-cost-comparison-v1", "comparison_schema");
  const auto key = id(root["comparison_id"]);
  const auto a = read_arm(root["baseline"], root["currency"]);
  const auto b = read_arm(root["candidate"], root["currency"]);
  need(a.label != b.label, "comparison_labels");
  need(a.conditions == b.conditions, "comparison_conditions_mismatch");
  need(a.tasks.size() == b.tasks.size(), "comparison_task_set");
  for (const auto& [task_id, task] : a.tasks) {
    const auto other = b.tasks.find(task_id);
    need(other != b.tasks.end(), "comparison_task_set");
    need(task.digest == other->second.digest, "comparison_task_mismatch");
  }
  Json reasons = Json::array();
  if (!a.ledger_complete || !b.ledger_complete) reasons.push_back("declared_coverage_incomplete");
  if (!a.costs["summary"]["complete"].get<bool>() || !b.costs["summary"]["complete"].get<bool>())
    reasons.push_back("cost_components_unknown");
  const bool primary_known = a.primary_known && b.primary_known &&
    a.primary_models.size() == 1 && b.primary_models.size() == 1;
  const bool same_model = primary_known && a.primary_models == b.primary_models;
  const bool same_prices = same_model && a.primary_prices.size() == 1 && b.primary_prices.size() == 1 &&
    a.primary_prices == b.primary_prices;
  if (!primary_known) reasons.push_back("primary_model_unknown_or_multiple");
  else if (!same_model) reasons.push_back("primary_model_mismatch");
  if (same_model && !same_prices) reasons.push_back("primary_price_schedule_mismatch");
  const bool eligible = reasons.empty();
  Json pairs = Json::array();
  for (const auto& [task_id, task] : a.tasks) {
    const auto& other = b.tasks.at(task_id);
    pairs.push_back({{"task_id", task_id}, {"task_sha256", task.digest}, {"baseline", task.summary},
                    {"candidate", other.summary}, {"change", change(task.summary, other.summary, eligible)}});
  }
  std::set<std::string> stages;
  for (const auto& [stage, _] : a.stages) stages.insert(stage);
  for (const auto& [stage, _] : b.stages) stages.insert(stage);
  Json by_stage = Json::array();
  const Json zero = Aggregate{}.json();
  for (const auto& stage : stages) {
    const auto left = a.stages.count(stage) ? a.stages.at(stage) : zero;
    const auto right = b.stages.count(stage) ? b.stages.at(stage) : zero;
    by_stage.push_back({{"stage", stage}, {"baseline", left}, {"candidate", right}, {"change", change(left, right, eligible)}});
  }
  Json canonical = {{"schema", root["schema"]}, {"comparison_id", key}, {"currency", root["currency"]},
                    {"baseline", binding(a)}, {"candidate", binding(b)}};
  Json result = {{"schema", "qbrain-cost-comparison-report-v1"}, {"comparison_id", key},
    {"currency", root["currency"]}, {"input_sha256", util::sha256_hex(canonical.dump())},
    {"comparison_eligible", eligible}, {"unavailable_reasons", reasons},
    {"same_declared_primary_model", same_model}, {"same_declared_primary_prices", same_prices},
    {"task_count", a.tasks.size()}, {"binding", canonical},
    {"baseline", {{"label", a.label}, {"cost_report", a.costs}}},
    {"candidate", {{"label", b.label}, {"cost_report", b.costs}}},
    {"change", change(a.costs["summary"], b.costs["summary"], eligible)}, {"by_task", pairs}, {"by_stage", by_stage},
    {"shared", {{"baseline", a.shared_summary}, {"candidate", b.shared_summary},
                {"change", change(a.shared_summary, b.shared_summary, eligible)}}},
    {"coverage_is_caller_declaration", true}, {"conditions_authenticated", false},
    {"billing_verified", false}, {"quality_verified", false}, {"host_consumption_verified", false},
    {"all_provider_calls_observed", false}, {"provider_requests_sent", 0},
    {"fees_taxes_discounts_included", false}, {"currency_conversion_performed", false}};
  need(result.dump().size() + 1 <= comparison_output_cap, "comparison_output_limit");
  return result;
}

inline Json parse(const std::string& raw) {
  try { return report(util::parse_unique_json(raw, comparison_input_cap, 32)); }
  catch (const util::JsonInputError& e) {
    if (e.failure() == util::JsonInputFailure::byte_limit) throw Error("comparison_input_limit");
    if (e.failure() == util::JsonInputFailure::duplicate_key) throw Error("comparison_duplicate_key");
    throw Error("comparison_invalid_json");
  } catch (const nlohmann::json::exception&) { throw Error("comparison_invalid_json"); }
}
inline int command(const std::vector<std::string>& args) {
  try {
    need(args.size() == 1 && args[0] == "compare", "comparison_invalid_action");
    std::string raw;
    std::array<char, 8192> buffer{};
    while (std::cin.read(buffer.data(), static_cast<std::streamsize>((std::min)(buffer.size(), comparison_input_cap + 1 - raw.size()))) || std::cin.gcount()) {
      raw.append(buffer.data(), static_cast<std::size_t>(std::cin.gcount()));
      need(raw.size() <= comparison_input_cap, "comparison_input_limit");
    }
    need(!std::cin.bad(), "comparison_input_error");
    const auto value = parse(raw).dump();
    std::cout << value << '\n';
    return 0;
  } catch (const Error& e) { std::cout << Json{{"error", {{"code", e.what()}}}}.dump() << '\n'; return 2; }
  catch (...) { std::cout << "{\"error\":{\"code\":\"comparison_local_error\"}}\n"; return 2; }
}
} // namespace qbrain::accounting::comparison
