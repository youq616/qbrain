# N48O plan audit

2026-09-28. Reviewer: ChatGPT coordinator, separate design pass under the current
owner's explicit self-review authorization. PASS for implementation, not outcomes.

The session module is an existing functional gap (explicit PG rejection), not an
additional diagnostic module. A simple backend-guard deletion is unsafe: PRAGMA,
SQLite introspection/backup filenames, ASCII-only lower, 64-bit time values and
eager write exclusion all require real dialect/concurrency treatment. The plan
addresses each and preserves no-implicit external model permission.

Conservative database-wide short table locks deliberately favor correctness over
throughput. They must end before the provider call, guard page/source/config
mutation, and avoid silently committing an existing caller transaction. Optional
DDL is atomic/additive; a half-created schema must not be repaired silently.
The read/off paths must remain non-initializing. Real server tests must run on
both platforms and explicitly fail without a server. Existing SQLite evidence
cannot stand in for PostgreSQL evidence. Fact/context/host/quality parity remains
outside this module and must not be marked complete by its success.
