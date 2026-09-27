# N48O — PostgreSQL session-memory lifecycle

2026-09-28. Base d038aa1f0ba5df064306ada87d44bf3bc5a43fbf.
Status: approved after N48O-PLAN-AUDIT.md. Owner requested implementation and the
coordinator's own separate outcome review; no independent third party is claimed.

## Fixed scope

Close the existing PostgreSQL rejection in session_memory: archive/capture,
local or explicitly authorized model extraction, read/status, drain and forget.
Keep SQLite the default and its existing SQL path/tests unchanged. Reuse the
existing PostgreSQL opt-in (QBRAIN_PG_DSN) and public v13 core schema. This is NOT
PostgreSQL parity for fact_store, context, hooks or every other project feature.
No automatic conversion of a SQLite database or copying private user records.

## Design

Add backend-neutral transaction-active inspection so PG cannot silently join and
commit a caller's transaction. PG short write sections use an explicit READ
COMMITTED transaction, transaction-local lock_timeout=2500ms, and conservative
SHARE ROW EXCLUSIVE locks on public sources/pages/config. This serializes module
writers and excludes source/page/policy changes while validating and publishing.
The provider call occurs after commit, never under these locks. Post-provider
ownership, evidence, lease and consent checks remain mandatory. Locks are not a
performance/scalability claim; deadlocks/timeouts fail rather than retry providers.

Create optional PG memory tables/indexes atomically under the same lock with
BIGINT times and page references, deterministic C-collation memory identifiers.
Never send a connection descriptor to SQLite's local backup path. New tables only,
no destructive existing-table migration; reject unsupported optional schema.
Read/unconfigured automatic capture must not create optional tables. Require the
existing public UTF8 schema context; preserve quoting and complete user evidence.
Translate ASCII A-Z only when matching recall, so Unicode case behavior stays
SQLite-compatible rather than depending on PostgreSQL server locale.

CMake on non-Windows should discover libpq with FindPostgreSQL; preserve Windows
root discovery and delayed libpq loading. A requested PG-required test must fail
when libpq or the server is unavailable, never report a skip as a pass.

## Falsifiable acceptance

1. Fresh real PostgreSQL + native client: no-create read/off; atomic initial DDL;
   source separation; same-fragment dedup/conflict; exact user-only extraction;
   unknown usage/cost, expiry, Unicode, literal matching and output budgets.
2. Forget revokes items and preserves tombstone; recapture cannot resurrect;
   modified/reassigned evidence is not deleted; late provider cannot republish;
   changed policy/lease and invalid candidates reject atomically.
3. Independent connections: concurrent first init/capture dedup; concurrent claims
   issue one provider call; policy changes/forget during provider call win;
   locked writes time out and rollback while leaving other connection settings
   and unrelated caller transactions intact. No schema/version weakening.
4. Existing SQLite direct, full Windows registry and core/process regressions stay
   enabled. Test actual PG on Windows and Linux against the committed source.
   Keep original outputs/identities and failures. Local environment may lack a
   PG server; this is not evidence of a passed local integration test.
5. Separate post-implementation review compares raw server state/outputs and fixes
   blockers; docs distinguish this module from overall PG/project completion.

## Delivery and rollback

Deliver source, tests, native CI artifacts and Chinese usage. No Release, existing
ZIP replacement, user machine write, model credential or paid provider request.
Disabling PG / reverting the feature does not delete persisted optional tables.
A user-requested PG connection transmits memory to that configured database; TLS,
access policy and backup are operator responsibilities, not SQLite privacy.
