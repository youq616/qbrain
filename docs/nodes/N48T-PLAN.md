# N48T — SQLite directory-scoped context cache invalidation

2026-09-30. Base e0a27f829d970c24ed8c566023ada0911c0042b3 / tree
534c86deabf43e30d3b2533cd3bf1f0728cf8400. Status: approved after N48T-PLAN-AUDIT.md.
Origin: issue #2, N45 unchecked finer parent-directory incremental update requirement.
This slice replaces default SQLite source-wide invalidation with source + namespace +
directory-ancestor invalidation. It does not introduce background summary generation.

Ownership: do NOT modify any of the six N48S files assigned to 乔咪咪, tools/delivery,
N48S packaging or runtime ZIPs, PR61, existing workflows, public main or any PR merge.
This feature builds directly on merged N48R; no dependency on the six unpublished files.
Only local code/test/doc changes and a separately applicable patch are in this delivery.

Acceptance before claiming implementation success:
- Exact byte-prefix directory matching (not LIKE); invalidate every affected ancestor,
  including empty/capped previews, but keep unrelated directory/namespace/source cache
  rows byte-identical. A root namespace cache is an affected ancestor.
- Handle INSERT, UPDATE, DELETE, soft deletion/restoration, source/slug/type moves, and
  replacement conflict victims; changes and invalidation roll back atomically.
- Eagerly erase l0/l1/refs_json in invalidated rows. Do not merely tag sensitive stale text.
- Recognize exact old source-wide triggers; preserve old read behavior until an existing
  explicit context summary write. Under one SQLite write transaction verify and upgrade
  only known triggers, clear legacy cache, publish the new summary; reject unknown or
  mixed triggers. Do not alter core schema version or app permissions. Backup before
  optional schema upgrade for file-backed databases, matching the prior context policy.
- Denied model summary and failed evidence revalidation cannot publish/upgraded DDL.
  No new provider calls. Full source versions and old cursor checks remain authoritative.
- Run original context/Hook/memory/fact regressions unchanged where tools allow, a new
  native suite, independent real-process randomized SQL mutation checks and sanitizers.
  Retain all failed attempts. Verify old code fails at least one new selective-cache
  expectation, without relabeling the old safe source-wide policy as a data-loss defect.

PostgreSQL intentionally remains source-wide in this slice, with untouched code/tests.
No real PG server or Windows execution is inferred from local compilation. Full Windows
native qualification and eventual PG scoped invalidation remain open acceptance items.
No new package, real user database, paid model, default collection, RLS/DLP or signing.
The stronger statement 'incremental summaries' is not made: affected cache is erased and
subsequent explicit summary recomputes it; unrelated model cache is retained.

Rollback: SQLite older application can read the same cache columns and benefit from
scoped triggers; no data migration. Remove optional derived-cache objects only by an
explicit operator decision; do not automatically destroy data on downgrade. Unknown
schema or custom trigger definitions are not silently rewritten.

## Capability amendment, before publishing the new candidate

GitHub branch/blob creation is now available. Publish this distinct feature on
feature/n48t-directory-cache and open a draft PR if required to retain review history.
Do not merge it or PR61. Add a new narrow native Windows/Linux test workflow, without
editing existing workflows or packaging. That isolated write does not include any
N48S file and cannot change the previously accepted runtime ZIP. Native results are
reported only after actual completion. The original runtime is still pinned to e0a27f82.
