#pragma once
// N48W: finite metadata only. No request/URL/key/model/error text is retained.
#include "qbrain/ai/http_client.hpp"
#include "qbrain/accounting/provider_usage.hpp"
#include <chrono>
#include <functional>
#include <memory>
#include <mutex>

namespace qbrain::accounting::observation {
using Clock = std::chrono::steady_clock;
enum class Api { chat, responses, embeddings, rerank, other };
enum class Outcome { pending, http_completed, http_error, invalid_request, transport_error,
                     timeout, cancelled, response_limit, unsupported_platform, local_exception };
enum class UsageState { unavailable, recognized, embedding_input_only, invalid, unsupported };
enum class ProviderState { unknown, completed, failed, cancelled, incomplete, pending };
inline const char* name(Api v) { switch(v) {
  case Api::chat:return "chat";case Api::responses:return "responses";case Api::embeddings:return "embeddings";
  case Api::rerank:return "rerank";default:return "other"; } }
inline const char* name(Outcome v) { switch(v) {
  case Outcome::pending:return "pending";case Outcome::http_completed:return "http_completed";
  case Outcome::http_error:return "http_error";case Outcome::invalid_request:return "invalid_request";
  case Outcome::transport_error:return "transport_error";case Outcome::timeout:return "timeout";
  case Outcome::cancelled:return "cancelled";case Outcome::response_limit:return "response_limit";
  case Outcome::unsupported_platform:return "unsupported_platform";default:return "local_exception"; } }
inline const char* name(UsageState v) { switch(v) {
  case UsageState::recognized:return "recognized";case UsageState::embedding_input_only:return "embedding_input_only";
  case UsageState::invalid:return "invalid";case UsageState::unsupported:return "unsupported";default:return "unavailable"; } }
inline const char* name(ProviderState v) { switch(v) {
  case ProviderState::completed:return "completed";case ProviderState::failed:return "failed";
  case ProviderState::cancelled:return "cancelled";case ProviderState::incomplete:return "incomplete";
  case ProviderState::pending:return "pending";default:return "unknown"; } }
inline Api api(std::string_view path) noexcept {
  if(path=="/chat/completions")return Api::chat;
  if(path=="/responses")return Api::responses;
  if(path=="/embeddings")return Api::embeddings;
  if(path=="/rerank")return Api::rerank;
  return Api::other;
}
struct Usage {
  UsageState state=UsageState::unavailable;
  ProviderState provider=ProviderState::unknown;
  std::optional<bool> provider_error_present;
  bool provider_status_conflict=false;
  std::optional<Amount> input,output,total;
  Values tokens{};
};
inline Usage project_usage(Api kind,const ai::HttpResponse& response) noexcept {
  Usage u;
  if(response.failure!=ai::HttpFailure::none || response.status<200 || response.status>=300)return u;
  if(kind==Api::rerank || kind==Api::other){u.state=UsageState::unsupported;return u;}
  try {
    // One response is already bounded by the transport. This lower observation cap
    // and depth bound cannot change the original provider result or expose its text.
    const auto j=util::parse_unique_json(response.body,1048576,24);
    if(!j.is_object()){u.state=UsageState::invalid;return u;}
    const bool has_error=j.contains("error")&&!j["error"].is_null();
    u.provider_error_present=has_error;
    if(kind==Api::responses && j.value("object",Json())=="response") {
      const auto s=j.value("status",Json());
      if(s=="completed")u.provider=ProviderState::completed;
      else if(s=="failed")u.provider=ProviderState::failed;
      else if(s=="cancelled")u.provider=ProviderState::cancelled;
      else if(s=="incomplete")u.provider=ProviderState::incomplete;
      else if(s=="queued"||s=="in_progress")u.provider=ProviderState::pending;
    }
    // An error object cannot promote queued/unknown Responses status into a
    // terminal billable snapshot. Classify terminality before error projection.
    if(kind==Api::responses && (u.provider==ProviderState::pending || u.provider==ProviderState::unknown)){u.state=UsageState::unsupported;return u;}
    // Status and error presence are separate observations. Never overwrite an
    // explicit Responses status. Only completed+error contradicts a success label;
    // cancellation/incompleteness may legitimately carry diagnostic metadata.
    u.provider_status_conflict=kind==Api::responses &&
      u.provider==ProviderState::completed && has_error;
    if(has_error && kind!=Api::responses)u.provider=ProviderState::failed;
    if(!j.contains("usage")||j["usage"].is_null())return u;
    const auto& usage=j["usage"];
    if(kind==Api::chat || kind==Api::responses) {
      const auto object=j.value("object",Json());
      if((kind==Api::chat && object!="chat.completion") ||
         (kind==Api::responses && object!="response")){u.state=UsageState::unsupported;return u;}
      const bool responses=kind==Api::responses;
      auto mapped=usage_import::openai_usage(usage,responses);
      u.input=usage_import::count(usage,responses?"input_tokens":"prompt_tokens");
      u.output=usage_import::count(usage,responses?"output_tokens":"completion_tokens");
      u.total=usage_import::count(usage,"total_tokens");
      u.tokens=mapped.tokens;u.state=UsageState::recognized;
    } else {
      if(j.value("object",Json())!="list"){u.state=UsageState::unsupported;return u;}
      usage_import::fields(usage,{"prompt_tokens","total_tokens"});
      u.input=usage_import::count(usage,"prompt_tokens");u.total=usage_import::count(usage,"total_tokens");
      usage_import::equality(u.input,u.total);
      // Embedding input total is not disjoint cache evidence; no guessed zero buckets.
      u.state=UsageState::embedding_input_only;
    }
  }catch(...){
    const auto provider=u.provider;const auto error=u.provider_error_present;
    const bool conflict=u.provider_status_conflict;u={};u.provider=provider;
    u.provider_error_present=error;u.provider_status_conflict=conflict;u.state=UsageState::invalid;
  }
  return u;
}
inline Outcome outcome(const ai::HttpResponse& r) noexcept {
  switch(r.failure){
    case ai::HttpFailure::invalid_request:return Outcome::invalid_request;
    case ai::HttpFailure::transport:return Outcome::transport_error;
    case ai::HttpFailure::timeout:return Outcome::timeout;
    case ai::HttpFailure::cancelled:return Outcome::cancelled;
    case ai::HttpFailure::response_too_large:return Outcome::response_limit;
    case ai::HttpFailure::unsupported_platform:return Outcome::unsupported_platform;
    case ai::HttpFailure::http_status:return Outcome::http_error;
    default:return r.status>=200&&r.status<300?Outcome::http_completed:Outcome::http_error;
  }
}
struct Event {
  Amount sequence=0;
  Api kind=Api::other;
  Outcome result=Outcome::pending;
  bool complete=false,send_invoked=false;
  int http_status=0;
  Amount elapsed_ms=0;
  Usage usage{};
};
inline Json quantity(const std::optional<Amount>& n){return n?Json(*n):Json(nullptr);}
inline Json json(const Event& e) {
  return {{"sequence",e.sequence},{"api",name(e.kind)},{"complete",e.complete},
    {"transport",name(e.result)},{"send_invoked",e.complete?Json(e.send_invoked):Json(nullptr)},
    {"http_status",e.http_status?Json(e.http_status):Json(nullptr)},
    {"elapsed_ms",e.complete?Json(e.elapsed_ms):Json(nullptr)},
    {"usage",{{"state",name(e.usage.state)},{"provider_state",name(e.usage.provider)},
      {"provider_error_present",e.usage.provider_error_present?Json(*e.usage.provider_error_present):Json(nullptr)},
      {"provider_status_conflict",e.usage.provider_status_conflict},
      {"input_inclusive",quantity(e.usage.input)},{"output_inclusive",quantity(e.usage.output)},
      {"total_inclusive",quantity(e.usage.total)},{"tokens",normalized(e.usage.tokens,false)}}},
    {"retry_relation",nullptr},{"price",nullptr},{"cost",nullptr}};
}
class Collector {
 public:
  using Writer=std::function<void(const Event&)>;
  explicit Collector(Writer writer={},std::size_t cap=512):writer_(std::move(writer)),cap_(cap){
    if(cap==0||cap>512)throw std::invalid_argument("observation_capacity");events_.reserve(cap);
  }
  Amount begin(Api kind) {
    std::lock_guard lock(mutex_);
    if(sealed_)return 0;
    ++started_;
    if(events_.size()==cap_){++dropped_;return 0;}
    Event e;e.sequence=started_;e.kind=kind;events_.push_back(e);write(e);return e.sequence;
  }
  void finish(Amount sequence,Outcome result,int status,bool sent,Amount elapsed,Usage usage) noexcept {
    try {
      std::lock_guard lock(mutex_);
      if(sealed_)return; // Finalized report remains immutable; pending already prevents PASS.
      ++finished_;
      if(!sequence)return;
      for(auto& e:events_)if(e.sequence==sequence){
        if(e.complete){--finished_;return;}
        e.complete=true;e.result=result;e.http_status=status>=100&&status<=599?status:0;
        e.send_invoked=sent;e.elapsed_ms=elapsed;e.usage=std::move(usage);write(e);break;
      }
    }catch(...){/* no exception from observation may replace a provider result */}
  }
  Json report(bool seal=false,std::optional<int> dispatch_return=std::nullopt,bool dispatch_exception=false) {
    std::lock_guard lock(mutex_);
    // First seal freezes dispatch evidence too. No same-process report can certify
    // final process exit or output delivered after its own write.
    if(seal&&!sealed_){
      dispatch_return_=dispatch_exception?std::nullopt:dispatch_return;
      dispatch_exception_=dispatch_exception;sealed_=true;
    }
    const auto returned=sealed_?dispatch_return_:(dispatch_exception?std::nullopt:dispatch_return);
    const bool threw=sealed_?dispatch_exception_:dispatch_exception;
    Json events=Json::array(),totals=Json::object();
    for(const auto& e:events_){events.push_back(json(e));auto k=name(e.result);totals[k]=totals.value(k,Amount(0))+1;}
    const bool complete=sealed_&&dropped_==0&&io_errors_==0&&started_==finished_;
    return {{"schema","qbrain-runtime-observation-v2"},{"scope","same_process_http_post_json_invocations"},
      {"sealed",sealed_},{"dispatch_state",threw?"exception":returned?"returned":"not_observed"},
      {"dispatch_return",returned?Json(*returned):Json(nullptr)},
      {"process_exit",nullptr},{"stdout_complete",nullptr},{"stderr_complete",nullptr},
      {"completion_scope","http_attempt_records_only"},{"recording_complete",complete},
      {"counts",{{"started",started_},{"finished",finished_},{"retained",events_.size()},
                 {"dropped",dropped_},{"pending",started_-finished_},{"io_errors",io_errors_}}},
      {"transport_counts",totals},{"records",events},
      {"retry_attempts",nullptr},{"total_estimate",nullptr},{"currency",nullptr},
      {"price_basis","unassigned"},{"billing_verified",false},{"all_provider_calls_observed",false},
      {"server_receipt_verified",false},{"application_success_verified",false}};
  }
 private:
  void write(const Event& e)noexcept{if(writer_)try{writer_(e);}catch(...){++io_errors_;}}
  std::mutex mutex_;Writer writer_;std::size_t cap_;std::vector<Event> events_;
  Amount started_=0,finished_=0,dropped_=0,io_errors_=0;bool sealed_=false;
  std::optional<int> dispatch_return_;bool dispatch_exception_=false;
};
inline std::mutex active_mutex;
inline std::shared_ptr<Collector> active_collector;
inline std::shared_ptr<Collector> active(){std::lock_guard lock(active_mutex);return active_collector;}
class Session {
 public:
  explicit Session(std::shared_ptr<Collector> c):collector_(std::move(c)){
    std::lock_guard lock(active_mutex);
    if(!collector_||active_collector)throw std::runtime_error("observation_already_active");
    active_collector=collector_;
  }
  ~Session(){std::lock_guard lock(active_mutex);if(active_collector==collector_)active_collector.reset();}
  Session(const Session&)=delete;Session& operator=(const Session&)=delete;
 private:std::shared_ptr<Collector> collector_;
};
class Attempt {
 public:
  explicit Attempt(std::string_view path):kind_(api(path)),start_(Clock::now()){
    // Session detach and acquisition+start are one ordered boundary.
    std::lock_guard lock(active_mutex);collector_=active_collector;
    if(collector_)sequence_=collector_->begin(kind_);
  }
  ~Attempt(){if(collector_&&!done_)finish_exception(false);}
  void finish(const ai::HttpResponse& r,bool sent)noexcept{
    if(!collector_||done_)return;
    const auto elapsed=milliseconds();
    collector_->finish(sequence_,outcome(r),r.status,sent,elapsed,project_usage(kind_,r));done_=true;
  }
  void finish_exception(bool sent)noexcept{
    if(!collector_||done_)return;
    collector_->finish(sequence_,Outcome::local_exception,0,sent,milliseconds(),{});done_=true;
  }
  Attempt(const Attempt&)=delete;Attempt& operator=(const Attempt&)=delete;
 private:
  Amount milliseconds()const noexcept{const auto n=std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now()-start_).count();return n>0?Amount(n):0;}
  std::shared_ptr<Collector> collector_;Api kind_;Clock::time_point start_;Amount sequence_=0;bool done_=false;
};
} // namespace qbrain::accounting::observation
