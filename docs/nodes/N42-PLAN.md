# N42 - Foundation repair, bounded slice

Status: done for this bounded foundation slice, not the full optimization roadmap.
Plan audit: PASS, user-authorized ChatGPT review (`N42-PLAN-AUDIT.md`).
Native addendum: approved (`N42-NATIVE-REPAIR-PLAN.md`).
Outcome audit: PASS (`N42-HARD-AUDIT.md`), with named scope exclusions.
Tested code: `d8fcec42b343668836af6974e38c05550083a655`.
Upstream baseline: `2e5c4f0bf310ca4f340b3a2295d2dfd79d3b8325`.

## Authorization

The owner approved ChatGPT review for N42 and selected `youq616/qbrain` as the development destination with permission to write. This is not a Claude Code review. Preserve the imported main baseline while the optimization PR is reviewed; do not access user memory or credentials.

## Acceptance

A1. Preserve source identity through FTS/vector retrieval, RRF and rerank; same slugs in different sources remain distinct.
A2. Synthesis loads the matched source and checks page ID; no implicit default fallback.
A3. Affected MCP source checks precede content reads and provider requests.
A4. Scoped facts require an active owning page in the permitted source.
A5. Chinese, emoji, malformed bytes and truncation boundaries produce valid bounded display UTF-8 without mutating originals.
A6. MCP image search is temporarily refused before filesystem access; local image querying no longer uploads. Read-only MCP synthesis cannot save.
A7. Deterministic ordering and invalid-score defenses remain tested.
A8. Native MSVC application, original regression groups and real-process MCP checks are evaluated before completion.

All assertions are mapped to actual evidence in the outcome audit. Windows 42/42 registered groups and 17 real MCP assertions passed. PG integration is explicitly skipped, not claimed.

## Tests and rollback

Focused C++ foundation, SQLite test adapter and original-golden LF/CRLF parity tests. Original N32 tests retain their expected outputs and gain explicit newline comparisons. Real-process MCP uses production migrations and disposable synthetic fixtures. CI compiles native production objects immediately before reusing them for tests; no cross-run object cache.

Review before merging. If the bounded change must be rolled back, revert the PR; do not delete the original repository or memory data. No production installation or data migration is performed by this work.

## Exclusions

No semantic session extraction, automatic Agent hooks, L0/L1 semantic summaries, global ACL equivalence, ANN, exact token savings, Unicode argv redesign, real provider/PG acceptance or full gbrain parity. These remain separately scoped work in issue #2.
