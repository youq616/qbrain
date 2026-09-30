# N48V — opt-in in-memory query embedding reuse

2026-09-30. Base e0a27f829d970c24ed8c566023ada0911c0042b3.
Status: approved after N48V-PLAN-AUDIT.md. Original requirement: Issue2/N46 query/vector caching. The abandoned query-cache branch49edf765 contains an approved plan, not a delivered implementation; its plan is retained, not overwritten or claimed implemented.

## Scope and acceptance

Implement the planned query-vector slice at the two existing registered search/think embedding call sites, after their existing source authorization. Indexing/batches/images, search results, pages and facts are not cached. Every retrieval and evidence read remains live. No database schema/migration, automatic external permission, new MCP op, runtime package or deployment.

Each Brain owns an in-memory mutex-protected cache. Explicit DB config search.query_embedding_cache=1 enables it; missing or any other value means off. Disabled eligible query clears retained state. Brain open/reopen/close/load_config clears it. Per-call fingerprint includes provider, endpoint, requested and expected model, dimensions, resolved credential and mock mode; key includes exact query and resolved source. Entries retain only digests, model and validated successful single vector, never raw query/credential/endpoint. Hashes and vectors are not anonymous or securely erased memory.

At most64 entries and1MiB defined vector/model/key payload,60s non-sliding age from loader start; fixed production defaults, bounded constructor parameters and injectable monotonic clock for unit tests. Cache locking never surrounds the provider call. Concurrent misses may duplicate calls (no single-flight promise). Generation fencing prevents a load begun before reset/policy change/disable from repopulating it, including A->B->A policy changes. Returned vectors are copies.

Do not retain failure, thrown load, unexpected/multiple/empty/zero/nonfinite vector, wrong model/dimension or oversized cache input. Bypass returns unchanged loader behavior. Query cache is optional: retention allocation failure must not relabel provider success as failure. Metadata counters are not telemetry, invoices or evidence of paid savings.

Tests must cover default-off equivalence; exact TTL/LRU/byte caps; source/policy/model/key/mock separation; copied outputs; failure/no retention; reset/disable during load; reentrant/out-of-order/concurrent loaders; Brain close/reopen/reload; registered search AND think; no_vector/conservative bypass; source permission revoked after warming; live page edits/deletion after vector hit. Synthetic providers/mock embeddings only, no real accounts. Fresh native Windows/Linux and sanitizers required for bounded code acceptance. Preserve old core and process tests; full60/55 release integration and non-author outcome are separate pending gates.

## Isolation and execution

Do not change PR61/62/63 code or heads. No upload, execution, repackaging or retransmission of rejected tests/test_pg_directory_cache.cpp; this module has no PG policy/DDL tests and is unrelated to that refused action. Comments record the user-provided848 independent PASS and the fetched18ab CI success, but do not change their candidate bytes.

Current container and Python execution return ClientError. Use a dedicated new feature/n48v-query-vector-cache branch and fresh GitHub Actions. To edit three large inherited files without manual full-file retyping, a readable deterministic source recipe verifies their exact base Git blobs and applies three narrowly bounded integrations. It preserves originals, emits a complete reversible Git patch, and refuses mismatched files. A single prepare job may commit ONLY those three files to this exact feature branch with normal fast-forward push, no force/main writes. Subsequent read-only jobs checkout the resulting exact SHA. Workflow event SHA and tested derived SHA must be separately reported. This mechanism is for unrelated query-cache files, not the refused PG upload.

All code changes must be actual remote source at the tested commit, not a hidden compile-time patch. If the prepare push fails, report it and preserve the recoverable recipe; do not claim published integration. Preserve every failed run and raw stdout/stderr. End this turn with exact candidate/tree, test provenance and gaps; do not wait for PR62's already completed review.

## Limits and rollback

Long-lived Brain/MCP use benefits; independent one-shot processes never share the cache. No disk vector store, global cache, ANN, result cache, model-weight attestation, hard RSS bound or thread-safety extension to concurrent Brain/database/environment mutation. TTL permits reuse of provider output without a repeated request, so opt-in callers accept that freshness tradeoff. Off/close clears payload but is not secure erasure; memory may page. Revert the isolated code diff or disable the config; no database recovery is necessary.
