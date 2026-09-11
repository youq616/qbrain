# N45 outcome review — bounded directory context

Auditor: owner-delegated ChatGPT, not independent Claude Code review.
Verdict: **PASS for the approved bounded-preview scope**, not full OpenViking equivalence.

| Acceptance | Evidence |
|---|---|
| Logical namespace/source binding | URI parser and MCP argument checks; database keys never become filesystem paths |
| Honest L0/L1 | Defaults explicitly labeled extractive; optional model summary has separate persistent consent and key checks |
| Exact L2 | UTF-8/CRLF round-trip reconstruction, stale revision/character-offset denial, source checks |
| Derived cache | Backup before optional SQLite schema, ordinary read has no hidden cache/model write, insert/update/delete invalidate affected source |
| Late model output | Evidence and external consent revalidated before publication; seam tests cover mutation/revocation |
| MCP defaults and profile | Read/write split, source restrictions, six-tool profile rejects hidden calls as well as hiding definitions |
| Regression | 37 context unit checks and 65 real-process context checks; Windows full 44-group runner and portable build pass |

Memory/context C++ modules passed local ASan/UBSan checks. This does not prove all legacy code, bundled C, live provider or transport safety. Source-wide invalidation favors correctness, not minimal incremental recomputation. Directory bounds and truncated flags remain explicit; neither extractive nor model summaries replace original evidence.

Known limitations do not constitute completed features: SQLite-only new modules, no live summary factual-quality test, no full DLP/ACL guarantee, no sophisticated graph/recursive retrieval parity, no ANN or token/fee claim. Optional provider transport is not certified to enforce a strict overall deadline. Rollback leaves optional cache unused; originals remain unchanged.

## Shared provenance

Tested source: `5ee79dfd5ab2512f024fefc9054bd3da12d64f1f`.
Native run: https://github.com/youq616/qbrain/actions/runs/34616855167
Windows log artifact: 10270422765, SHA-256 `aa73772d02792c2a1b194912b5b92414139f221f9a3d9c82fec2a79b62651624`.
EXE SHA-256: `3bd43e8a099d9b4136aa0b96bd941fed7366a320a09b8bd253a0f272194ecdf8`.
Independent ZIP/manifest verification, registered-group parsing and all gate logs were inspected, not inferred from a green icon alone. Complete results are in `n44-evidence/RESULT.json`. The 44-group status includes a documented skip for actual PG DSN integration.
