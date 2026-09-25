#include "qbrain/accounting/cost_comparison.hpp"
#include <functional>
using namespace qbrain::accounting;
namespace cp = qbrain::accounting::comparison;
namespace {
int passed = 0;
void check(bool ok, const char* label) {
  if (!ok) throw std::runtime_error(label);
  ++passed;
}
Json tokens(Amount input, Amount output = 20) {
  return {{"input_uncached", input}, {"input_cache_read", 0}, {"input_cache_write", 0}, {"output", output}};
}
Json input(Amount n) {
  Json prices = Json::object(); for (const auto* k : buckets) prices[k] = "1";
  return {{"schema", "qbrain-cost-input-v1"}, {"currency", "USD"},
    {"rates", Json::array({{{"rate_id", "r"}, {"provider", "synthetic"}, {"model", "model-v1"}, {"per_million", prices}}})},
    {"calls", Json::array({{{"call_id", "c"}, {"rate_id", "r"}, {"stage", "main"}, {"attempt", 1}, {"outcome", "success"}, {"tokens", tokens(n)}}})}};
}
Json arm(const char* label, Amount n) {
  return {{"label", label}, {"conditions_sha256", std::string(64, 'a')}, {"ledger_complete", true}, {"cost_input", input(n)},
    {"tasks", Json::array({{{"task_id", "t"}, {"task_sha256", std::string(64, 'b')}, {"call_ids", Json::array({"c"})}}})},
    {"shared_call_ids", Json::array()}};
}
Json fixture() {
  return {{"schema", "qbrain-cost-comparison-v1"}, {"comparison_id", "synthetic"}, {"currency", "USD"},
    {"baseline", arm("without-context", 100)}, {"candidate", arm("with-context", 50)}};
}
void rejected(const Json& j, const char* code) {
  try { (void)cp::parse(j.dump()); }
  catch (const Error& e) { check(std::string(e.what()) == code, e.what()); return; }
  throw std::runtime_error("expected rejection");
}
void withheld(const Json& j, const char* reason) {
  const auto r = cp::parse(j.dump());
  check(r["comparison_eligible"] == false, "not eligible");
  check(std::find(r["unavailable_reasons"].begin(), r["unavailable_reasons"].end(), reason) != r["unavailable_reasons"].end(), "specific reason");
  check(r["change"]["candidate_minus_baseline"].is_null(), "null delta");
  check(r["by_task"][0]["change"]["candidate_minus_baseline"].is_null(), "no complete case cherry picking");
  check(r["shared"]["change"]["candidate_minus_baseline"].is_null(), "no shared cherry picking");
}
}
int main() {
  try {
    const auto original = fixture(); auto x = original;
    auto r = cp::parse(x.dump());
    check(r["comparison_eligible"] == true, "complete");
    check(r["change"]["candidate_minus_baseline"] == "-0.000050000000", "signed delta");
    check(r["change"]["relative_change"] == Json{{"numerator", "-5"}, {"denominator", "12"}}, "exact fraction");
    check(r["baseline"]["cost_report"] == qbrain::accounting::report(x["baseline"]["cost_input"]), "original pricing retained");
    for (auto flag : {"billing_verified", "quality_verified", "host_consumption_verified", "conditions_authenticated", "all_provider_calls_observed"})
      check(r[flag] == false, "scope");
    check(r["provider_requests_sent"] == 0, "no provider calls");
    x["baseline"]["cost_input"]["rates"][0]["per_million"]["output"] = "1.000000";
    check(cp::report(x) == r, "canonical equivalent rates");
    x = original; std::swap(x["baseline"], x["candidate"]);
    check(cp::report(x)["change"]["candidate_minus_baseline"] == "0.000050000000", "swap sign");
    check(cp::report(x)["change"]["relative_change"] == Json{{"numerator", "5"}, {"denominator", "7"}}, "swap denominator");
    x = original;
    auto extra = x["candidate"]["cost_input"]["calls"][0];
    extra["call_id"] = "aux"; extra["stage"] = "embedding"; extra["tokens"] = tokens(60, 0);
    x["candidate"]["cost_input"]["calls"].push_back(extra); x["candidate"]["shared_call_ids"].push_back("aux");
    r = cp::report(x);
    check(r["change"]["candidate_minus_baseline"] == "0.000010000000", "shared reverses apparent savings");
    check(r["shared"]["candidate"]["total_estimate"] == "0.000060000000", "shared cost");
    extra["call_id"] = "retry"; extra["stage"] = "main"; extra["outcome"] = "failure"; extra["attempt"] = 2;
    x["candidate"]["cost_input"]["calls"].push_back(extra); x["candidate"]["tasks"][0]["call_ids"].push_back("retry");
    r = cp::report(x);
    check(r["candidate"]["cost_report"]["summary"]["failed_calls"] == 1, "failed included");
    check(r["candidate"]["cost_report"]["summary"]["retry_calls"] == 1, "retry included");
    check(r["change"]["candidate_minus_baseline"] == "0.000070000000", "retry cost included");
    const auto stable = r;
    std::reverse(x["candidate"]["cost_input"]["calls"].begin(), x["candidate"]["cost_input"]["calls"].end());
    std::reverse(x["candidate"]["tasks"][0]["call_ids"].begin(), x["candidate"]["tasks"][0]["call_ids"].end());
    check(cp::report(x) == stable, "permutation");
    for (const auto* side : {"baseline", "candidate"}) {
      x = original; x[side]["ledger_complete"] = false; withheld(x, "declared_coverage_incomplete");
      for (const auto* bucket : buckets) {
        x = original; x[side]["cost_input"]["calls"][0]["tokens"][bucket] = nullptr;
        withheld(x, "cost_components_unknown");
      }
      x = original; x[side]["cost_input"]["rates"] = Json::array();
      withheld(x, "primary_model_unknown_or_multiple");
      x = original; x[side]["cost_input"]["rates"][0]["model"] = "different";
      withheld(x, "primary_model_mismatch");
      x = original; x[side]["cost_input"]["rates"][0]["per_million"]["output"] = "2";
      withheld(x, "primary_price_schedule_mismatch");
      x = original; x[side]["ledger_complete"] = 1; rejected(x, "comparison_coverage_flag");
      x = original; x[side]["tasks"] = Json::array(); rejected(x, "comparison_task_count");
      x = original; x[side]["tasks"][0]["call_ids"] = Json::array(); rejected(x, "comparison_call_ids");
      x = original; x[side]["tasks"][0]["call_ids"].push_back("c"); rejected(x, "comparison_call_reused");
      x = original; x[side]["tasks"][0]["call_ids"] = Json::array({"missing"}); rejected(x, "comparison_call_missing");
      x = original; x[side]["cost_input"]["calls"][0]["stage"] = "embedding"; rejected(x, "comparison_main_missing");
      x = original; auto dup = x[side]["tasks"][0]; x[side]["tasks"].push_back(dup); rejected(x, "comparison_duplicate_task");
      x = original; x[side]["shared_call_ids"].push_back("c"); rejected(x, "comparison_call_reused");
      x = original; extra = x[side]["cost_input"]["calls"][0]; extra["call_id"] = "other";
      x[side]["cost_input"]["calls"].push_back(extra); rejected(x, "comparison_unassigned_call");
      x[side]["shared_call_ids"].push_back("other"); rejected(x, "comparison_shared_main");
      x = original; x[side]["conditions_sha256"] = std::string(64, 'g'); rejected(x, "comparison_digest");
      x = original; x[side]["cost_input"]["currency"] = "EUR"; rejected(x, "comparison_currency");
      x = original; x[side]["cost_input"]["calls"][0]["tokens"]["output"] = true; rejected(x, "cost_quantity");
    }
    x = original; x["candidate"]["tasks"][0]["task_id"] = "different"; rejected(x, "comparison_task_set");
    x = original; x["candidate"]["tasks"][0]["task_sha256"] = std::string(64, 'c'); rejected(x, "comparison_task_mismatch");
    x = original; x["candidate"]["conditions_sha256"] = std::string(64, 'c'); rejected(x, "comparison_conditions_mismatch");
    x = original; x["candidate"]["label"] = "without-context"; rejected(x, "comparison_labels");
    x = original; x["extra"] = "not accepted"; rejected(x, "cost_fields");
    x = original; x["schema"] = "wrong"; rejected(x, "comparison_schema");
    for (auto n : {Amount(0), Amount(1), token_cap}) {
      x = original;
      for (const auto* side : {"baseline", "candidate"}) x[side]["cost_input"]["calls"][0]["tokens"] = tokens(0, 0);
      x["candidate"]["cost_input"]["calls"][0]["tokens"] = tokens(n, 0);
      r = cp::report(x);
      check(r["change"]["relative_change"].is_null(), "zero baseline fraction undefined");
      check(r["change"]["candidate_minus_baseline"] == decimal(n * rate_scale, cost_scale, 12), "zero baseline exact delta");
    }
    x = original;
    for (const auto* side : {"baseline", "candidate"}) {
      x[side]["cost_input"]["calls"][0]["tokens"] = tokens(0, 0);
      for (const auto* bucket : buckets) x[side]["cost_input"]["rates"][0]["per_million"][bucket] = "10000";
    }
    x["candidate"]["cost_input"]["calls"][0]["tokens"] = tokens(token_cap, 0);
    check(cp::report(x)["change"]["candidate_minus_baseline"] == "10000000.000000000000", "above signed64 positive");
    std::swap(x["baseline"], x["candidate"]);
    check(cp::report(x)["change"]["candidate_minus_baseline"] == "-10000000.000000000000", "above signed64 negative");
    extra = x["baseline"]["cost_input"]["calls"][0]; extra["call_id"] = "overflow";
    x["baseline"]["cost_input"]["calls"].push_back(extra); rejected(x, "cost_overflow");
    for (const auto& raw : {std::string("{}"), std::string("{\"schema\":1,\"schema\":2}"), std::string("{\"a\":NaN}"),
                            std::string(cp::comparison_input_cap + 1, ' ')}) {
      try { (void)cp::parse(raw); throw std::runtime_error("invalid raw accepted"); }
      catch (const Error&) { ++passed; }
    }
    std::cout << Json{{"schema", "qbrain-cost-comparison-direct-v1"}, {"passed", passed}, {"failed", 0}}.dump() << '\n';
    return 0;
  } catch (const std::exception& e) { std::cerr << "FAIL after " << passed << ": " << e.what() << '\n'; return 1; }
}
