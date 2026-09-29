# N48P — PostgreSQL layered context and invalidated summary cache

2026-09-29. Base main17a9998f5e874cd233ebb5b4ac70748fbe9e412d, tree
9e53b940d1c936932b5c95968b96dd00540ef91a. Status: approved after the separate
plan review. Owner asks for one complete core module and coordinator self-review.

Extend existing context list/read/summary, including MCP routes, to PostgreSQL:
L0/L1 previews, revision-bound UTF8 L2 pagination, source/namespace isolation,
optional summary cache and explicit separately permitted model summarization.
No new scoring/receipt module. SQLite remains default and its SQL/output contract
must be preserved. No fact_store/Hook PG parity or real model/host consumption claim.

Acceptance:
1. Explicit public/UTF8 context only. Reject active or failed caller transactions
   and conflicting effective sources/pages/config/context table resolutions before
   reading policy/source, and after callbacks. Do not change caller search_path.
2. A PG read uses one REPEATABLE READ READ ONLY snapshot. Summary collects its
   evidence and consent in such a snapshot, closes it BEFORE any provider callback,
   then rechecks source, evidence and consent under fixed-order short locks on
   public.sources/pages/config. No automatic paid-request retry.
3. Lazy optional context_module-v1/context_cache initialization is atomic inside
   the publish transaction. Read-only calls/denied external calls perform no
   optional DDL. Reject orphan/wrong layouts or wrong/missing invalidation function
   and triggers; do not CREATE OR REPLACE unknown caller-owned objects.
4. Fully qualified SECURITY INVOKER trigger function invalidates and clears derived
   text/references on insert/update/delete and PG TRUNCATE. Source moves invalidate
   both sources, soft deletes and namespace changes invalidate, rollback restores.
5. PG uses byte counts and C ordering compatible with SQLite for bounded observed
   content. Preserve original URI, byte budget, revision, Unicode pagination and
   model-result limits. New storage path reuses preview/response formatting.
6. Real disposable PostgreSQL and SQLite tests cover exact outputs, cross-backend
   behavior, missing cache, invalidation, transactions, pg_temp shadowing, concurrent
   initializers/readers, callback mutation/revocation and bounded lock failure.
   Windows/Linux fixed-source CI and original context/core/full60/55-step gates
   required before merge. Tests do not substitute a mock for the PG server.
7. Add Chinese usage, synthetic examples and separate outcome review with raw
   records/actual limits. No real user DB, release replacement, permission change,
   install or credentials. Same DSN with a different brain is not a tenant boundary.

Rollback: reverting this additive runtime route support leaves optional PG tables
unchanged; do not automatically delete user data. Schema has no SQLite migration.
The server administrator owns PG backup/TLS/roles. Not a hostile DB-owner sandbox,
full DDL attestation, invoice/quality test or high-throughput guarantee.

## Outcome closure — 2026-09-29

The bounded module is source-qualified at136a4828 after actual Windows/Linux PG
execution and a separate owner-authorized outcome review. See N48P-HARD-AUDIT.md
and n48p-evidence/RESULT.json for exact results and limits. Post-qualification
closure changes documentation and already-executed review material only; original
product, CI and tests remain identical. Actual merge identity is recorded by PR58.
