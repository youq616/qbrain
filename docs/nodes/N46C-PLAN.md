# N46C — exact bounded candidate selection and batched backlink scoring

Status: done for scoped N46C after N46C-HARD-AUDIT.md; not full-project completion. Baseline: youq616/qbrain @ c9f3ed5229f43e9a88a53fc64b988d8d0bb89502.
Scope: native Windows C++20 Qbrain only; issue #2's candidate-scan performance item.

## Implementation scope

Replace all-chunk candidate materialization with an exact, streaming, per-page
Top-K selector retaining at most K page candidates. Do not truncate the vector
scan, approximate cosine scores, introduce ANN, add embedding cache, or change
model-selection/authorization policy. Keep best-chunk snippet ties and final
source/slug/page-id order. All database rows are still scanned through the
existing backend statement; only C++ candidate retention is bounded.

Batch backlink counts for already-selected hybrid candidates in groups of at
most 100 using bound parameters and source+slug identity. Do not load link
context/text. Preserve existing counting semantics and maximum-five-link boost.
Add optional C++ numeric diagnostics only, no MCP operation or raw-text logging.

## Falsifiable acceptance

1. Differential tests against the baseline exhaustive selector on fixed/random
   corpora, interleaved chunks, tie permutations, eviction and page re-entry,
   duplicate slugs across sources, Unicode, invalid vectors and clamped limits.
   Compare page identity, snippet, rank and score, not just result count.
2. Candidate high-water never exceeds K; full valid-row scan still occurs.
3. Batched boosts equal legacy per-hit counting, including zero/many links,
   same slug in different sources and batch boundaries. SQL trace must prove
   <=ceil(hit_count/100) backlink statements and no link-context projection.
4. Updates, soft deletion and source-restricted queries are immediately visible;
   no new cache or cross-source fallback. Searches do not write persistent data.
5. Full native Windows regression and the existing HTTP/memory/context/MCP/Hook/
   PowerShell gates remain. Add a 46th named group with negative evidence tests;
   old 45-group logs cannot pass the new package gate.
6. Synthetic baseline-vs-new benchmarks: identical inputs/results, bounded
   candidate counts, wall time reported without a hard speedup threshold.
   Windows execution and local portable execution are labelled separately.

## Security, compatibility and evidence

No schema migration, new runtime service, paid model call, provider consent,
MCP write authority or operation-list change. A batch uses <=300 SQL parameters.
No full DLP, multi-tenant ACL, semantic quality or paid cost claim. PG statement
implementations may materialize rows; bounded C++ candidates are NOT a bound on
backend result buffers or entire process RSS. Existing model provenance policy
is unchanged and remains a separate task.

Work on optimization/n46c-exact-retrieval. Record actual source/tree/Actions
and package hashes. Do not merge main or mark done until native checks and
outcome review pass. Rollback by reverting code/test/build changes; no data
migration to undo.
