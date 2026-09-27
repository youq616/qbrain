#pragma once
// N48O: PostgreSQL dialect/concurrency for the existing session-memory module.
// No libpq handle escapes the storage facade. Only the configured public DB is used.
#include "qbrain/memory/session_memory.hpp"
#include <map>
#include <string>

namespace qbrain::memory::pg_session {
using DB = storage::Database;
inline bool enabled(DB& db) { return db.backend_kind() == storage::BackendKind::postgres; }

inline void require_context(DB& db) {
  if (db.transaction_active()) throw Error("memory_transaction_active");
  auto s = db.prepare("SELECT current_schema(), current_setting('server_encoding')");
  if (!s.step() || s.column_text(0) != "public" || s.column_text(1) != "UTF8")
    throw Error("memory_pg_schema_context");
}

inline void begin(DB& db) {
  if (db.transaction_active()) throw Error("memory_transaction_active");
  db.exec("BEGIN ISOLATION LEVEL READ COMMITTED");
  try {
    db.exec("SET LOCAL lock_timeout = '2500ms'");
    // Unlike BEGIN IMMEDIATE -> deferred BEGIN, these real table locks exclude
    // page/source/policy writers until commit. Never held across provider calls.
    // One fixed order; lock errors roll back, not auto-retry a model request.
    db.exec("LOCK TABLE public.sources, public.pages, public.config IN SHARE ROW EXCLUSIVE MODE");
  } catch (...) {
    try { db.exec("ROLLBACK"); } catch (...) {}
    throw;
  }
}

inline bool ready(DB& db) {
  auto table = db.prepare("SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n "
                          "ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname='memory_module' AND c.relkind='r'");
  if (!table.step() || table.column_int(0) == 0) return false;
  // Reject unsupported versions and incompatible integer/text field layouts.
  // This is recognition of our schema, not an audit against a malicious DB owner.
  const std::map<std::string, std::string> layouts = {
    {"memory_module.version", "bigint"},
    {"memory_events.event_id", "text"}, {"memory_events.source_id", "text"},
    {"memory_events.session_id", "text"}, {"memory_events.fragment_id", "text"},
    {"memory_events.payload_hash", "text"}, {"memory_events.page_id", "bigint"},
    {"memory_events.page_hash", "text"}, {"memory_events.automatic", "bigint"},
    {"memory_events.capture_mode", "text"}, {"memory_events.expires_at", "bigint"},
    {"memory_events.status", "text"}, {"memory_events.method", "text"},
    {"memory_events.last_error", "text"}, {"memory_events.lease_token", "text"},
    {"memory_events.lease_until", "bigint"}, {"memory_events.attempts", "bigint"},
    {"memory_events.created_at", "bigint"}, {"memory_items.item_id", "text"},
    {"memory_items.event_id", "text"}, {"memory_items.category", "text"},
    {"memory_items.quote", "text"}, {"memory_items.message_index", "bigint"},
    {"memory_items.expires_at", "bigint"}, {"memory_items.created_at", "bigint"},
    {"memory_attempts.attempt_id", "text"}, {"memory_attempts.event_id", "text"},
    {"memory_attempts.method", "text"}, {"memory_attempts.status", "text"},
    {"memory_attempts.provider_attempts", "bigint"}, {"memory_attempts.input_tokens", "bigint"},
    {"memory_attempts.output_tokens", "bigint"}, {"memory_attempts.elapsed_ms", "bigint"},
    {"memory_attempts.created_at", "bigint"}
  };
  std::map<std::string, std::string> actual;
  auto columns = db.prepare("SELECT c.relname,a.attname,pg_catalog.format_type(a.atttypid,a.atttypmod) "
    "FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
    "JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid "
    "WHERE n.nspname='public' AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped "
    "AND c.relname IN ('memory_module','memory_events','memory_items','memory_attempts')");
  while (columns.step()) actual.emplace(columns.column_text(0)+"."+columns.column_text(1),columns.column_text(2));
  if (actual != layouts) throw Error("memory_schema_version_unsupported");
  auto version = db.prepare("SELECT version FROM public.memory_module");
  if (!version.step() || version.column_int(0) != 1 || version.step())
    throw Error("memory_schema_version_unsupported");
  return true;
}

// Called only while begin()'s serializing locks are held, followed by a ready()
// recheck. Plain CREATE refuses unknown preexisting objects rather than overwrites.
inline void create(DB& db) {
  db.exec(R"SQL(
CREATE TABLE public.memory_module(version BIGINT PRIMARY KEY CHECK(version=1));
CREATE TABLE public.memory_events(
 event_id TEXT COLLATE "C" PRIMARY KEY,
 source_id TEXT COLLATE "C" NOT NULL REFERENCES public.sources(id) ON DELETE CASCADE,
 session_id TEXT COLLATE "C" NOT NULL, fragment_id TEXT COLLATE "C" NOT NULL,
 payload_hash TEXT NOT NULL, page_id BIGINT REFERENCES public.pages(id) ON DELETE SET NULL,
 page_hash TEXT NOT NULL, automatic BIGINT NOT NULL, capture_mode TEXT NOT NULL,
 expires_at BIGINT NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'archived',
 method TEXT NOT NULL DEFAULT '', last_error TEXT NOT NULL DEFAULT '',
 lease_token TEXT NOT NULL DEFAULT '', lease_until BIGINT NOT NULL DEFAULT 0,
 attempts BIGINT NOT NULL DEFAULT 0, created_at BIGINT NOT NULL,
 UNIQUE(source_id,session_id,fragment_id));
CREATE TABLE public.memory_items(
 item_id TEXT COLLATE "C" PRIMARY KEY,
 event_id TEXT COLLATE "C" NOT NULL REFERENCES public.memory_events(event_id) ON DELETE CASCADE,
 category TEXT NOT NULL, quote TEXT NOT NULL, message_index BIGINT NOT NULL,
 expires_at BIGINT NOT NULL, created_at BIGINT NOT NULL);
CREATE TABLE public.memory_attempts(
 attempt_id TEXT COLLATE "C" PRIMARY KEY,
 event_id TEXT COLLATE "C" NOT NULL REFERENCES public.memory_events(event_id) ON DELETE CASCADE,
 method TEXT NOT NULL, status TEXT NOT NULL, provider_attempts BIGINT NOT NULL,
 input_tokens BIGINT, output_tokens BIGINT, elapsed_ms BIGINT, created_at BIGINT NOT NULL);
CREATE INDEX idx_memory_events_source ON public.memory_events(source_id,created_at,event_id);
CREATE INDEX idx_memory_items_event ON public.memory_items(event_id);
CREATE INDEX idx_memory_attempts_event ON public.memory_attempts(event_id);
INSERT INTO public.memory_module VALUES(1);
)SQL");
}

inline constexpr const char* literal_match =
  "strpos(translate(m.quote,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),"
  "translate(?,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'))>0 ";
} // namespace qbrain::memory::pg_session
