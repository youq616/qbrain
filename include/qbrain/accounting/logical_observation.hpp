#pragma once
// N48X: observed API lifecycle, not provider success or a second billing ledger.
#include "qbrain/accounting/runtime_observation.hpp"
#include <exception>
#include <type_traits>

namespace qbrain::accounting::logical {
namespace http = observation;
enum class Kind { chat, text_embedding, image_embedding, rerank };
enum class Path { unknown, remote_candidate, missing_credentials, invalid_input,
                  mock, empty_input, disabled, local_baseline, callback };
enum class Return { pending, returned, exception };
enum class Parent { root, nested, capacity, other_session };
enum class Association { innermost, outside_scope, capacity, other_session };
inline const char* name(Kind x) {switch(x){
  case Kind::chat:return "chat_complete";case Kind::text_embedding:return "embed_texts";
  case Kind::image_embedding:return "embed_image";default:return "apply_reranker";}}
inline const char* name(Path x) {switch(x){
  case Path::remote_candidate:return "remote_candidate";case Path::missing_credentials:return "missing_credentials";
  case Path::invalid_input:return "invalid_input";case Path::mock:return "local_mock";
  case Path::empty_input:return "empty_input";case Path::disabled:return "disabled";
  case Path::local_baseline:return "local_baseline";case Path::callback:return "custom_callback";
  default:return "unknown";}}
inline const char* name(Return x) {return x==Return::returned?"returned":x==Return::exception?"exception":"pending";}
inline const char* name(Parent x) {return x==Parent::nested?"nested":x==Parent::capacity?"parent_not_retained":
  x==Parent::other_session?"different_session":"root";}
inline const char* name(Association x) {return x==Association::innermost?"innermost":
  x==Association::capacity?"logical_call_not_retained":x==Association::other_session?"different_session":"outside_instrumented_scope";}
struct Event {
  Amount sequence=0,parent=0,elapsed_ms=0;
  Kind kind=Kind::chat;Path path=Path::unknown;Return state=Return::pending;Parent relation=Parent::root;
  std::optional<bool> result_ok,fallback;
};
inline Json json(const Event& e) {
  return {{"sequence",e.sequence},{"entry",name(e.kind)},{"parent_sequence",e.parent?Json(e.parent):Json(nullptr)},
    {"parent_relation",name(e.relation)},{"return_state",name(e.state)},{"path",name(e.path)},
    {"api_result_ok",e.result_ok?Json(*e.result_ok):Json(nullptr)},
    {"fallback_taken",e.fallback?Json(*e.fallback):Json(nullptr)},
    {"elapsed_ms",e.state==Return::pending?Json(nullptr):Json(e.elapsed_ms)},
    {"tokens",nullptr},{"price",nullptr},{"cost",nullptr},{"retry_relation",nullptr}};
}
struct Link {
  Amount http_sequence=0,logical_sequence=0;
  Association association=Association::outside_scope;
};
inline Json json(const Link& e) {
  return {{"http_sequence",e.http_sequence},{"logical_sequence",e.logical_sequence?Json(e.logical_sequence):Json(nullptr)},
          {"association",name(e.association)}};
}
class Collector;
struct Frame {Collector* owner=nullptr;Amount sequence=0;};
inline thread_local Frame* current_frame=nullptr;

class Collector {
 public:
  using Writer=std::function<void(const Event&)>;
  using LinkWriter=std::function<void(const Link&)>;
  struct Ticket {Amount sequence=0;bool accepted=false;};
  explicit Collector(Writer writer={},LinkWriter links={},std::size_t capacity=512)
    :writer_(std::move(writer)),link_writer_(std::move(links)),capacity_(capacity){
    if(!capacity||capacity>512)throw std::invalid_argument("logical_capacity");
    events_.reserve(capacity);links_.reserve(512);
  }
  void claim() {
    std::lock_guard lock(mutex_);
    if(claimed_||sealed_)throw std::runtime_error("logical_collector_already_used");
    claimed_=true;
  }
  Ticket begin(Kind kind,const Frame* parent) {
    std::lock_guard lock(mutex_);if(sealed_)return {};
    ++started_;
    if(events_.size()==capacity_){++dropped_;return {0,true};}
    Event e;e.sequence=started_;e.kind=kind;
    if(parent){
      if(parent->owner!=this)e.relation=Parent::other_session;
      else if(parent->sequence){e.relation=Parent::nested;e.parent=parent->sequence;}
      else e.relation=Parent::capacity;
    }
    events_.push_back(e);write(e);return {e.sequence,true};
  }
  void finish(Ticket t,Return state,Path path,std::optional<bool> ok,
              std::optional<bool> fallback,Amount elapsed) noexcept {
    try {
      std::lock_guard lock(mutex_);if(sealed_||!t.accepted)return;
      if(t.sequence){
        if(t.sequence>events_.size()){++errors_;return;}
        auto& e=events_[std::size_t(t.sequence-1)];
        if(e.state!=Return::pending)return;
        e.state=state;e.path=path;e.result_ok=state==Return::returned?ok:std::nullopt;
        e.fallback=fallback;e.elapsed_ms=elapsed;write(e);
      }
      ++finished_;
    }catch(...){loss();}
  }
  void link(const http::Event& h,const Frame* frame) noexcept {
    if(h.complete)return;
    try {
      std::lock_guard lock(mutex_);if(sealed_)return;
      if(!h.sequence||links_.size()>=512||h.sequence!=links_.size()+1){++errors_;return;}
      Link l;l.http_sequence=h.sequence;
      if(frame){
        if(frame->owner!=this)l.association=Association::other_session;
        else if(!frame->sequence)l.association=Association::capacity;
        else {l.association=Association::innermost;l.logical_sequence=frame->sequence;}
      }
      links_.push_back(l);
      if(link_writer_)try{link_writer_(l);}catch(...){++errors_;}
    }catch(...){loss();}
  }
  void loss() noexcept {try{std::lock_guard lock(mutex_);if(!sealed_)++errors_;}catch(...){}}
  Json report(bool seal=false,std::optional<int> code=std::nullopt,bool exception=false) {
    std::lock_guard lock(mutex_);
    if(seal&&!sealed_){sealed_=true;dispatch_=exception?std::nullopt:code;dispatch_exception_=exception;}
    const auto returned=sealed_?dispatch_:(exception?std::nullopt:code);
    const bool threw=sealed_?dispatch_exception_:exception;
    Json events=Json::array(),links=Json::array();
    for(const auto& e:events_)events.push_back(json(e));
    for(const auto& l:links_)links.push_back(json(l));
    return {{"schema","qbrain-logical-observation-v1"},{"scope","instrumented_model_entries_same_process"},
      {"sealed",sealed_},{"recording_complete",sealed_&&!dropped_&&!errors_&&started_==finished_},
      {"completion_scope","logical_call_records_only"},
      {"counts",{{"started",started_},{"finished",finished_},{"retained",events_.size()},
                 {"dropped",dropped_},{"pending",started_-finished_},{"record_errors",errors_}}},
      {"records",events},{"http_links",links},{"dispatch_state",threw?"exception":returned?"returned":"not_observed"},
      {"dispatch_return",returned?Json(*returned):Json(nullptr)},{"process_exit",nullptr},
      {"stdout_complete",nullptr},{"stderr_complete",nullptr},{"tokens",nullptr},{"total_estimate",nullptr},
      {"currency",nullptr},{"retry_relationships_inferred",false},{"billing_verified",false},
      {"all_model_calls_observed",false},{"automatic_thread_parent_propagation",false}};
  }
 private:
  void write(const Event& e) noexcept {if(writer_)try{writer_(e);}catch(...){++errors_;}}
  std::mutex mutex_;Writer writer_;LinkWriter link_writer_;std::size_t capacity_;
  std::vector<Event> events_;std::vector<Link> links_;
  Amount started_=0,finished_=0,dropped_=0,errors_=0;bool sealed_=false,claimed_=false;
  std::optional<int> dispatch_;bool dispatch_exception_=false;
};
inline std::mutex active_mutex;
inline std::shared_ptr<Collector> active_collector;
class Call {
 public:
  explicit Call(Kind kind) noexcept {
    try {
      std::lock_guard lock(active_mutex);owner_=active_collector;
      if(owner_)ticket_=owner_->begin(kind,current_frame);
    }catch(...){if(owner_)owner_->loss();owner_.reset();}
    if(ticket_.accepted){
      start_=http::Clock::now();previous_=current_frame;frame_={owner_.get(),ticket_.sequence};current_frame=&frame_;
    }
  }
  ~Call(){if(ticket_.accepted){if(!done_)threw();current_frame=previous_;}}
  Call(const Call&)=delete;Call& operator=(const Call&)=delete;
  void path(Path value) noexcept {path_=value;}
  void fallback(bool value) noexcept {fallback_=value;}
  void returned(std::optional<bool> ok=std::nullopt) noexcept {finish(Return::returned,ok);}
  void threw() noexcept {finish(Return::exception,std::nullopt);}
 private:
  void finish(Return state,std::optional<bool> ok) noexcept {
    if(!ticket_.accepted||done_)return;done_=true;
    const auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(http::Clock::now()-start_).count();
    owner_->finish(ticket_,state,path_,ok,fallback_,ms>0?Amount(ms):0);
  }
  std::shared_ptr<Collector> owner_;Collector::Ticket ticket_;Frame frame_;Frame* previous_=nullptr;
  http::Clock::time_point start_;Path path_=Path::unknown;std::optional<bool> fallback_;bool done_=false;
};
template<class Function>
auto invoke(Kind kind,Function&& function) {
  Call call(kind);
  try {
    auto result=std::forward<Function>(function)(call);
    static_assert(std::is_nothrow_move_constructible_v<decltype(result)>);
    if constexpr(requires{result.ok;})call.returned(result.ok);
    else call.returned();
    return result;
  }catch(...){call.threw();throw;}
}
class Session {
 public:
  explicit Session(std::shared_ptr<Collector> logical,http::Collector::Writer writer={},std::size_t http_cap=512)
    :logical_(std::move(logical)){
    if(!logical_)throw std::invalid_argument("logical_collector_required");
    http_=std::make_shared<http::Collector>([c=logical_,writer=std::move(writer)](const http::Event& e){
      c->link(e,current_frame);if(writer)writer(e);
    },http_cap);
    std::lock_guard lock(active_mutex);
    if(active_collector)throw std::runtime_error("logical_observation_already_active");
    http_session_=std::make_unique<http::Session>(http_);
    logical_->claim();
    active_collector=logical_;attached_=true;
  }
  ~Session(){detach();}
  void detach() noexcept {
    std::lock_guard lock(active_mutex);
    if(!attached_)return;
    attached_=false;
    if(active_collector==logical_)active_collector.reset();
    http_session_.reset();
  }
  std::shared_ptr<http::Collector> http_collector()const noexcept{return http_;}
  Session(const Session&)=delete;Session& operator=(const Session&)=delete;
 private:
  std::shared_ptr<Collector> logical_;std::shared_ptr<http::Collector> http_;
  std::unique_ptr<http::Session> http_session_;bool attached_=false;
};
} // namespace qbrain::accounting::logical
