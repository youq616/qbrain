# N42 outcome review - foundation repair

**Reviewer:** ChatGPT, under the owner's explicit N42 review exception; not Claude Code.
**Verdict:** PENDING final native regression. No node-complete or full-project acceptance claim.
**Code under test:** `d8fcec42b343668836af6974e38c05550083a655`.
**Upstream:** `Lordakee/qbrain@2e5c4f0bf310ca4f340b3a2295d2dfd79d3b8325`.
**Native workflow:** https://github.com/youq616/qbrain/actions/runs/34556246262

## Actual implementation

Source identity is carried through FTS/vector results, RRF and rerank, with source-correct synthesis reads and a page-ID cross-check. UTF-8 excerpt handling acts on display copies only. The affected MCP page/search/fact paths use the existing source resolver; scoped facts require an active owning page. Read-only MCP synthesis rejects save before a provider call. MCP image search is temporarily refused before local filesystem access; local image querying no longer uploads implicitly. The CRLF macro-continuation bug exposed by native CI was fixed without changing golden outputs. No schema/data migration is included.

## Evidence and limits

| Gate | Observed result |
|---|---|
| Focused GCC / Clang builds | Three CTest targets passed on each: foundation, LF/CRLF original goldens, SQLite search adapter |
| Full GCC production application | Built; real executable used for source/transport checks |
| Real executable stdio MCP | Seventeen assertions passed locally; same step succeeded on the current native Windows job, including cleanup |
| Original N32 production test group | Passed locally when initialized with the registry setup the full runner supplies; no assertion removed |
| Native MSVC complete application | Current Windows job step succeeded |
| Original 41 groups plus N42 group | Current native run was still executing when this review was recorded; do not infer PASS |
| PostgreSQL integration / real model provider / actual Windows 11 Agent lifecycle | Not verified in this work |

The seventeen MCP assertions run against a disposable database created with production migrations, not a mocked Brain. They cover default/allowed/denied sources, same-slug evidence, Chinese/emoji, deleted/unowned facts, refusal of implicit writes/filesystem access, and unchanged page/fact/file/chunk/job/version rows. They do not certify all 108 operations or every transport.

The SQLite search adapter test remains supplementary and does not prove production PostgreSQL behavior. Python is CI/test tooling only; the product remains C++20. No real personal memory or live model key was used by the new integration test.

## Failures preserved and corrected

The initial raw artifact from run 34554749593 shows one failing registered group, `n32_scan_integration`, not the three failures reported in an inconsistent parsed log summary. Unchanged LF input matched the golden; CRLF leaked macro-body symbols. The source fix preserves original byte positions and all golden assertions, and adds explicit LF/CRLF checks.

Run 34555340213 passed all seventeen MCP assertions but failed cleanup because the Python test retained open SQLite connections. Explicit `contextlib.closing` fixed test resource ownership; exceptions are not ignored.

## Acceptance blockers and exclusions

Keep this PR Draft until the complete native regression result is examined. Do not install the old `dist/` binaries as N42 builds. Semantic session extraction, per-agent automatic hooks, L0/L1 semantic summaries, global ACL equivalence, Windows Unicode argv redesign and total-cost benchmarks remain issue #2 work, not implicit deliverables of this patch.

`.ci/n42.applied.json` is the historical first-application manifest, not a hash manifest for every later commit. The development working tree contains normal source; temporary source-applying workflows have been removed. CI only builds/tests/archives, with contents-read permission.
