#pragma once
// N48V: query vectors only. No Brain/database, global state or provider under lock.
#include "qbrain/ai/embed.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <functional>
#include <limits>
#include <list>
#include <mutex>
#include <new>
#include <stdexcept>
#include <utility>

namespace qbrain::ai {
class QueryEmbeddingCache {
 public:
  using Clock = std::chrono::steady_clock;
  using Time = Clock::time_point;
  struct Limits {
    std::size_t entries = 64;
    std::size_t bytes = 1024 * 1024;
    std::chrono::milliseconds ttl{60000};
  };
  struct Identity {
    std::string policy;
    std::string key;
    std::string model;
    int dimensions = 0;
  };
  struct Stats {
    std::uint64_t hits = 0, loads = 0, stored = 0, rejected = 0, evicted = 0;
    std::size_t entries = 0, bytes = 0;
  };
  QueryEmbeddingCache() : QueryEmbeddingCache(Limits{}, [] { return Clock::now(); }) {}
  explicit QueryEmbeddingCache(Limits limits, std::function<Time()> now = [] { return Clock::now(); })
      : limits_(limits), now_(std::move(now)) {
    if (!now_ || limits.entries == 0 || limits.entries > 64 || limits.bytes == 0 ||
        limits.bytes > 1024 * 1024 || limits.ttl.count() <= 0 || limits.ttl.count() > 60000)
      throw std::invalid_argument("invalid query cache limits");
  }
  QueryEmbeddingCache(const QueryEmbeddingCache&) = delete;
  QueryEmbeddingCache& operator=(const QueryEmbeddingCache&) = delete;

  void clear() {
    std::lock_guard<std::mutex> lock(mutex_);
    reset_locked();
  }
  Stats stats() const {
    std::lock_guard<std::mutex> lock(mutex_);
    auto result = stats_;
    result.entries = entries_.size(); result.bytes = bytes_;
    return result;
  }

  template<class Loader>
  EmbedResult get_or_load(bool enabled, Identity id, Loader&& loader) {
    const Time started = now_();
    std::uint64_t ticket = 0;
    bool retain = false;
    {
      std::lock_guard<std::mutex> lock(mutex_);
      if (!enabled || !valid_identity(id) || saturated_) {
        reset_locked();
      } else {
        if (policy_ != id.policy) {
          reset_locked();
          policy_ = id.policy;
        }
        // Admission time is not necessarily lookup time after a contended lock.
        purge_locked(now_());
        for (auto it = entries_.begin(); it != entries_.end(); ++it) {
          if (it->key == id.key && it->value.model == id.model && it->dimensions == id.dimensions) {
            EmbedResult copy = it->value;
            entries_.splice(entries_.begin(), entries_, it);
            bump(stats_.hits);
            return copy;
          }
        }
        ticket = generation_;
        retain = !saturated_;
      }
      bump(stats_.loads);
    }
    // Reentrant reset and independent concurrent misses are safe. Loader exceptions
    // propagate unchanged; errors are never installed or converted into cache hits.
    EmbedResult result = std::forward<Loader>(loader)();
    if (!retain) return result;
    if (!valid_result(result, id)) {
      std::lock_guard<std::mutex> lock(mutex_); bump(stats_.rejected);
      return result;
    }
    if (expired(started, now_())) return result;
    const std::size_t cost = id.key.size() + result.model.size() + result.vectors[0].size() * sizeof(float);
    if (cost > limits_.bytes) return result;
    try {
      // A compact copy; no caller-owned capacity, error body, query or credential is retained.
      Entry entry{id.key, id.dimensions, started, cost, {}};
      entry.value.ok = true;
      entry.value.model = result.model;
      entry.value.vectors.emplace_back(result.vectors[0].begin(), result.vectors[0].end());
      std::lock_guard<std::mutex> lock(mutex_);
      if (generation_ != ticket || saturated_ || policy_ != id.policy) return result;
      const Time publication = now_();
      if (expired(started, publication)) return result;
      purge_locked(publication);
      // First successful concurrent insertion wins. This is not request coalescing.
      for (const auto& existing : entries_)
        if (existing.key == id.key && existing.value.model == id.model && existing.dimensions == id.dimensions)
          return result;
      while (!entries_.empty() && (entries_.size() >= limits_.entries || bytes_ > limits_.bytes - cost)) {
        bytes_ -= entries_.back().bytes; entries_.pop_back(); bump(stats_.evicted);
      }
      entries_.push_front(std::move(entry)); bytes_ += cost; bump(stats_.stored);
    } catch (const std::bad_alloc&) {
      // Optional retention failure does not discard an already successful provider result.
    }
    return result;
  }

 private:
  struct Entry {
    std::string key;
    int dimensions;
    Time started;
    std::size_t bytes;
    EmbedResult value;
  };
  static void bump(std::uint64_t& value) {
    if (value != std::numeric_limits<std::uint64_t>::max()) ++value;
  }
  static bool digest(const std::string& value) {
    return value.size() == 64 && std::all_of(value.begin(), value.end(), [](char c) {
      return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
    });
  }
  static bool valid_identity(const Identity& id) {
    return digest(id.policy) && digest(id.key) && !id.model.empty() && id.model.size() <= 256 &&
      std::all_of(id.model.begin(), id.model.end(), [](unsigned char c) { return c > 0x20 && c < 0x7f; }) &&
      id.dimensions >= 0 && id.dimensions <= 16384;
  }
  static bool valid_result(const EmbedResult& r, const Identity& id) {
    if (!r.ok || !r.error.empty() || r.model != id.model || r.vectors.size() != 1) return false;
    const auto& v = r.vectors[0];
    return !v.empty() && v.size() <= 16384 && (id.dimensions == 0 || v.size() == std::size_t(id.dimensions)) &&
      std::all_of(v.begin(), v.end(), [](float x) { return std::isfinite(x); }) &&
      std::any_of(v.begin(), v.end(), [](float x) { return x != 0.0f; });
  }
  bool expired(Time started, Time now) const {
    return now < started || now - started >= limits_.ttl;
  }
  void purge_locked(Time now) {
    for (auto it = entries_.begin(); it != entries_.end();) {
      if (expired(it->started, now)) {
        bytes_ -= it->bytes; it = entries_.erase(it); bump(stats_.evicted);
      } else ++it;
    }
  }
  void reset_locked() {
    entries_.clear(); bytes_ = 0; policy_.clear();
    if (generation_ == std::numeric_limits<std::uint64_t>::max()) saturated_ = true;
    else ++generation_;
  }
  Limits limits_;
  std::function<Time()> now_;
  mutable std::mutex mutex_;
  std::list<Entry> entries_;
  std::string policy_;
  std::size_t bytes_ = 0;
  std::uint64_t generation_ = 0;
  bool saturated_ = false;
  Stats stats_;
};
} // namespace qbrain::ai
