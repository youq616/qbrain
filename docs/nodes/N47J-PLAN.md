# N47J — bounded per-event Hook diagnostic checkpoints

Baseline: 487711c03ceb2ed7a15e1c3e2ac4f205f9642cef (merged N47I).
Status: approved after N47J-PLAN-AUDIT.md; implementation/outcome pending.
Only Windows-native youq616/qbrain. Owner permits a separate coordinator
engineering self-review; do not call it a third-party or subagent audit.

## Reproduced need and usable scope

The owner relayed that N47E's UserPromptSubmit trace was overwritten by a later
SessionEnd. Current hook.cpp writes only last-trace.json. Keep that compatibility
path and add one fixed checkpoint per allowed host/event, at most ten files:
trace-{claude|codex}-{SessionStart|UserPromptSubmit|Stop|PreCompact|SessionEnd}.json.
Do not use user-supplied path fragments or create unbounded logs/history.

After existing event/project/config validation and runtime-lock acquisition,
construct a scope-bound diagnostic writer inside the lock. On success or a later
processing exception, write only a strict metadata projection: event/host, a
pseudonymous session key, wall-clock completion time, processing phase/status,
existing bounded counters and finite enumerated capture/extraction/promotion
states. No prompt, quote, response text/hash, raw session/source/brain IDs,
filesystem path, token, exception text or copied context. Limit each serialized
record to4096 bytes; host_consumption_confirmed remains false and provider_calls
is the inherited configured-path declaration, not independent network measurement.

Use the existing same-directory temporary-file replacement under the existing
runtime lock. Each event checkpoint and last-trace is replaced independently,
not one atomic pair. Failure of either diagnostic write must not block the other,
change application data, suppress valid Hook output, or fabricate success. Failed
accepted processing must be distinguishable from an older successful event;
invalid/untrusted input rejected before lock remains inert and unrecorded.
No new schema, permissions, capture/promotion defaults, model call or MCP name.

## Evidence limits and retention

Each slot stores only the most recent acquired/accepted invocation of that
host/event, not every event or concurrent attempt. Same-event invocations replace
the prior slot. Lock-busy, disabled, invalid or unauthorized attempts need not
produce a record; disk failure can leave stale records. Consumers must compare
session_key/event/time and never equate file presence or processed with actual
model consumption. Hash-based session correlation is pseudonymity, not anonymity
or authenticity. Completion timestamps are wall-clock observations, not monotonic
ordering or a hard real-time guarantee. Files remain under the existing owned
config root and inherited local permissions; uninstall retention follows existing
owned-directory behavior. No real user's historical logs are uploaded.

## Falsifiable acceptance

Native C++ metadata-unit cases: exact host/event paths, unknown/path-injection
rejection, only allowed keys and values, secret/untrusted extras absent, count
bounds/types, malformed statuses rejected, session-key/time validation, deterministic
serialization and exact fixed record cap. New accurate native group58.

Real process tests on synthetic isolated brains and both host fixtures: automatic
capture/extraction/promotion followed by Stop/SessionEnd preserves UserPromptSubmit;
new session changes correlation; different host/event slots do not overwrite;
known accepted processing error replaces old success with failed stage; malformed,
disabled and outside-project events have no writes; sensitive content never enters
traces; repeated events retain fixed inventory; corrupt/missing brain failure is
nonblocking. Force event slot or compatibility target failure independently and
verify valid context still returns and other checkpoint writes. Keep existing
promotion/Hook/install/strict-JSON boundaries unchanged.

Require source/executable/test-bound unit and process reports with negative report
tests. Retain full Windows regression, Server2022, portable and sanitizer gates.
Do a separate outcome pass and repair discovered issues before merge or release.
Synthetic Hook fixtures are not new signed-in client acceptance. No owner local
work is required for implementation or regression; no repeated paid-model calls.
Rollback removes new writer code; old binaries ignore extra metadata files.
