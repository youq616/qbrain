# N42 - Foundation repair, bounded slice

Status: implementation under validation; not a completed full optimization.
Plan audit: approved for the bounded slice (user-authorized ChatGPT review).
Outcome audit: pending native regression and transport evidence.
Upstream baseline: `2e5c4f0bf310ca4f340b3a2295d2dfd79d3b8325`.

## Authorization and scope

The owner approved ChatGPT review for N42 in the project conversation; this is not a Claude Code review. The owner subsequently selected `youq616/qbrain` as the development destination and explicitly authorized writing there. This supersedes the earlier patch-package instruction not to push. Preserve the imported main baseline while reviewing the optimization branch. Do not access user databases or credentials.

## Deliverables and acceptance

A1. Preserve source identity through FTS/vector retrieval, RRF and rerank; same slugs in different sources remain distinct.
A2. Synthesis loads the matched source and checks page ID; no implicit default fallback.
A3. Affected MCP source checks happen before content reads and provider requests.
A4. Scoped fact reads require an active owning page in the permitted source.
A5. Chinese, emoji, malformed bytes and truncation boundaries produce valid bounded UTF-8 display copies without mutating originals.
A6. MCP image search is temporarily refused before filesystem access; local image querying no longer uploads. Read-only MCP synthesis cannot save.
A7. Deterministic ordering and invalid-score defenses remain tested.
A8. Full native MSVC application, original regression groups and real-process MCP checks must be evaluated before node completion. Focused adapter tests are supplementary.

## Tests

`tests/n42`: existing nine foundation scenarios and thirteen SQLite-adapter checks.
`.ci/test_mcp_boundaries.py`: migrated disposable production SQLite database and real executable/stdio transport. Synthetic multi-source fixtures, same-slug pages, deleted/unowned facts, UTF-8, denied writes and row snapshots. Python is only a test dependency; no external model API calls.
GitHub Actions runs native production scripts in a clean Windows runner. `-SkipProductionBuild` is used only after the same job has just built production objects; no cross-run cached objects.

## Exclusions

No semantic session extraction, automatic recall hooks, L0/L1 semantic summaries, database migrations, ANN, global ACL equivalence, exact token savings, Windows argv redesign, or full gbrain parity claim.

## Rollback

Do not merge an unaccepted change. Retain baseline main and revert the reviewed commit if needed. No production executable replacement or memory migration is performed by this work.
