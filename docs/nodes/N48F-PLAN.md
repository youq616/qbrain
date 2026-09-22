# N48F — Bounded opt-in query embedding cache

2026-09-22. Status: approved after N48F-PLAN-AUDIT at044e4565.
Base main:6c4f779ee752bd4043847eb79a6d1a5e694d024e.
Owner requests a complete module and coordinator self-review. This implements
one existing roadmap performance item, not another OpenCode closure.

## Complete scope

Add an in-memory cache for query embeddings used by search and think only. Each
Brain owns its cache; each entry keys the exact query and resolved source. A policy
fingerprint binds provider, endpoint, model, dimensions, resolved credential and
mock/real mode. No raw queries, credentials or paths are stored in cache entries.
Only validated successful single-query embeddings are eligible. Indexing/batch/
image embeddings remain uncached. Search results and database evidence are NEVER
cached, so every search still performs live retrieval and authorization.

Explicit local config search.query_embedding_cache=1 enables this cache; missing
or other values disable it. Read this existing config key per query, without a new
schema or changing global file configuration. Disabled queries clear existing
entries and retain the original embed_texts behavior. Config reload, close and
reopen clear entries. Credential/provider/model changes flush the policy partition.
Long-lived MCP sessions benefit; separate one-shot CLI processes do not share data.

Use a mutex-protected bounded cache: at most64 entries,1MiB retained vector/model/
key payload,60s non-sliding maximum age. Fixed defaults, explicit constructor limits
and a clock type for deterministic direct tests; no production test flag. Expiry is
checked on access rather than a timer or secure-erasure promise. Release the mutex
before embedding; concurrent misses may each call the provider, never a promise of
exactly-once or request coalescing. Clearing/changing policy must prevent delayed
old results from repopulating the cache. Returned results are caller-owned copies.

## Falsifiable acceptance

1. Default-off results match prior behavior; never cache errors, empty/zero/nonfinite
   vectors, unexpected models/dimensions or multi-vector results. Oversized inputs
   bypass retention without weakening the original embedding request validation.
2. Cache hits preserve exact vector values, model and response shape. Source, Brain,
   endpoint, model, dimensions, credential and mock-policy boundaries are tested.
3. LRU entry/byte bounds and exact TTL boundary are independently tested. Slow loads,
   loader errors, reset during a load and out-of-order policy completions cannot
   violate state or revive discarded entries. Loader executes outside the lock.
4. Real registered search/think paths use the wrapper only after source resolution.
   no_vector/conservative paths remain bypasses. Actual page insertion/deletion
   after warming the cache still changes search results immediately.
5. No new MCP tool, write permission, network authorization or automatic external
   call. Tests use deterministic embeddings/synthetic data, and native Windows
   loopback provider requests when feasible, never provider accounts or keys.
6. Build and run actual Windows/Linux code. Preserve original Windows60 groups,
   existing core/embedding/14 process suites and the integrated OpenCode/N48D gates.
   Add explicit new cache/direct/registered-operation tests; do not count old groups
   as new cache coverage. Save exact source/script/binary identities and logs.
7. After implementation perform a separate code/privacy/concurrency/outcome review,
   fix blockers and rerun changed code before scoped acceptance. Keep failures.

## Boundaries and rollback

No persistent vectors, database migration, automatic semantic change, rankings or
facts are cached. Within60s an opt-in caller may reuse a successful provider result;
this does not assert deterministic provider weights or quality/cost improvements
without measurement. Bounds concern retained payload, not total process RSS or
concurrent callers' returned vectors. No secure memory erasure guarantee.
Thread safety covers the cache, not previously unsupported concurrent Brain/SQLite
or process-environment mutation. Internal counters are metadata only, not billing.
Only Brain ownership/cleanup and two query call sites change among inherited product
files; new header(s)/tests/documentation are additive. Revert these to disable the
feature; no data recovery is needed. No release/tag, real model/client acceptance,
Issue40 closure, PostgreSQL parity or signing claim is included.