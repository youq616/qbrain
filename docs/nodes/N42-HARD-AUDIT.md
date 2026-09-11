# N42 outcome review - foundation repair

**Reviewer:** ChatGPT, under the owner's explicit N42 review exception; not Claude Code.
**Verdict:** PASS for the bounded N42 foundation-repair plan and native-repair addendum. This is not full-project or full-Agent acceptance.
**Tested code:** `d8fcec42b343668836af6974e38c05550083a655`. Subsequent completion changes are documentation only.
**Upstream:** `Lordakee/qbrain@2e5c4f0bf310ca4f340b3a2295d2dfd79d3b8325`.
**Workflow:** https://github.com/youq616/qbrain/actions/runs/34556246262
**Windows job:** 103129467321. All steps completed successfully.

## Implementation versus acceptance

| Assertion | Evidence and result |
|---|---|
| A1 Source identity survives retrieval/fusion/rerank | Source fields, framed identities and callback identity checks in implementation; focused C++ cases, actual source/page IDs in MCP search; PASS |
| A2 Correct synthesis evidence | Matched source and page ID rechecked before reading; real keyless synthesis returns ALPHA_ONLY, not same-slug DEFAULT/BETA content; PASS |
| A3 Affected source checks precede content/provider access | Existing resolver used in affected operations; denied-source real MCP responses; PASS within named scope |
| A4 Facts require active authorized ownership | Actual migrated SQLite fixtures exclude other-source, deleted-page and unowned facts; PASS |
| A5 UTF-8 bounded display copies | Foundation fuzz/boundary cases; real Chinese/emoji MCP round trip; original stored text is not rewritten; PASS |
| A6 No implicit writes on named read paths | MCP synthesis save and image filesystem requests rejected; row snapshots unchanged; local image query no longer uploads; PASS |
| A7 Ranking validation | Identity, duplicate vote/index, non-finite score and deterministic tie cases; PASS |
| A8 Native build and regression | MSVC application build, all 42 registered groups and 17 real-process MCP assertions; PASS with explicit PG integration exclusion |
| Native addendum: CRLF / test cleanup | Unchanged LF/CRLF golden comparisons, old N32 group, and successful Windows temporary SQLite cleanup; PASS |

## Verified counts

- Windows original 41 groups plus the N42 foundation group: **42/42 PASS**, zero FAIL lines.
- Windows real executable/stdio MCP: **17/17 assertions PASS**, cleanup successful.
- GCC and Clang: three focused CTest targets passed on each.
- Full GCC production app built; actual-process MCP checks and the complete N32 production test group passed locally. Isolated N32 runner explicitly performs the registry initialization supplied by earlier groups in the full runner.
- Actual PostgreSQL integration was **not run**: the log explicitly says no `QBRAIN_PG_TEST_DSN`. The n38 group's local checks passing is not a PG integration pass.

Counts were checked against the static test_main registration names and the downloaded raw artifacts, not inferred from prose summaries. The source.txt artifact identifies the exact tested code commit. Machine-readable evidence: `n42-evidence/RESULT.json`.

Log artifact ID: 10182811445.
ZIP SHA-256: `3653e3d33d94668094e4169de4f52091470bf4387fbcc438bde181c6acaf3265`.
Raw Windows tests SHA-256: `63ec1e5f9c5ab2439d4eb4e30c0f39ffc294c8b07ff02e048d0254c842ab8312`.

## Earlier failures, fixed rather than suppressed

The initial raw artifact from run 34554749593 showed one failing registered group, n32_scan_integration. An inconsistent parsed log summary reported other failures; it was not used as acceptance evidence. LF matched the golden; CRLF leaked macro-body symbols. The source fix preserves byte positions and all golden assertions while adding explicit newline parity checks.

Run 34555340213 passed all seventeen MCP assertions but failed cleanup because the Python test retained SQLite handles. Explicit contextlib.closing fixed resource ownership. No cleanup errors or failing assertions were suppressed.

## Scope and release limits

This certifies only the bounded N42 repair. It does not certify all operations/transports, full gbrain parity, semantic session extraction, automatic recall/capture hooks, L0/L1 semantic summaries, exact token/cost savings, real providers, PostgreSQL, Windows Unicode argv or actual Windows 11 host lifecycle integration. These remain issue #2 work.

New integration tests use disposable synthetic data and no live model keys. Python is test tooling only; the product remains Windows-native C++20. No memory database migration occurred. dist contains upstream historical artifacts, not rebuilt N42 installation packages. Do not install those as the fixed release.

The initial `.ci/n42.applied.json` is historical application evidence, not a manifest of every later file. Source-applying workflows were removed after verified application; normal CI has read-only repository permission. Main remains the imported baseline until the separate PR is merged.
