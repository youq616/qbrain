# N46C — exact retrieval performance outcome review

Verdict: **PASS for the scoped N46C node**, with the limitations and failed diagnostics
recorded below. Review date: September 12, 2026 (Asia/Seoul). Auditor: ChatGPT under
the owner-approved continuation in issue #2; not an independent or Claude Code audit.

## Source, execution and delivery

Baseline `c9f3ed5229f43e9a88a53fc64b988d8d0bb89502`. Tested source `728c2502ff66cedae218722458cac47f957236fc`; tree `3636b0bb9652e9a012fa0e7caad07aa9efe353ad`.
[PR #7](https://github.com/youq616/qbrain/pull/7) is the delivery discussion; its actual
GitHub state determines merge status. [Run 34661114802](https://github.com/youq616/qbrain/actions/runs/34661114802)
completed successfully at 2026-09-12T00:30:22Z. Windows job 103463641048,
portable job 103463641054 and source job 103463640879 succeeded.
The run's complete 633-file source archive was byte-matched to the local candidate.

The Windows artifact underwent 73 separate readback
checks against original logs and manifests. This is a second verification procedure,
not an external audit. Delivered inner ZIP bytes are unchanged from CI. Source hashes,
original native timings, every readback assertion and explicit skipped scope are in
[n46c-evidence/RESULT.json](n46c-evidence/RESULT.json).

ZIP: 1830557 bytes; SHA-256 `1f25ebbed82051f9f824485d92ea6b4a63871993b6a24cfe05780ad1feb9507b`.
EXE: 3797504 bytes; SHA-256 `49ef05ea8827be71e53778a87e51c77a7e205a6b5c018373c002ddad35cf147c`.
The EXE is PE32+ AMD64 and unsigned. Tested PowerShell script bytes are retained;
the exact LF-to-CRLF Git checkout conversion is the only accepted script difference.

## Plan acceptance

| Requirement | Evidence | Outcome |
| --- | --- | --- |
| Preserve exact per-page vector results | Frozen baseline implementation plus independent map/sort oracle; shuffled chunks, ties, eviction/re-entry, negative/invalid vectors, Unicode and clamped limits | PASS |
| Bound candidates without truncating the scan | All 16000 fixture chunks scanned; selector peak 50 at K=50; bound checked after each insertion | PASS |
| Batch source-scoped backlink scores | Native SQLite trace; same-source+slug counts equal legacy; field authorizer forbids loading private link context; zero/multiple batches | PASS |
| Keep live mutation/source behavior | Restricted/all-source duplicate slugs, deleted/updated invalid-vector rows and restoration; no writes during reads | PASS |
| Retain original regression | 46 exact registered groups; original HTTP, memory, context, MCP, hooks and both PowerShell suites; same-source/tree package gate | PASS |
| Report baseline benchmark honestly | Seven alternating runs per implementation, same synthetic data/results; raw samples, candidate counts and statement counts retained | PASS, not semantic or cost evaluation |

Native retrieval tests executed 139107 assertions, including repeated
property checks. This is **not** 139107 independent business scenarios.
Existing suites remain: memory 44, MCP 17, hooks 69, context 65, local configuration 6,
HTTP input 30 and wire checks 51. PowerShell 5.1 and 7 each passed installer 69,
consent/path identity 16 and byte transport 8. Eight evidence-gate unit tests passed.
An old 45-group log cannot certify the new 46-group package. Real PostgreSQL DSN
coverage still explicitly emits SKIP-PG; an enclosing PASS does not certify PG.

## Measured Windows synthetic results

Fixture: in-memory SQLite, 2,000 pages, 16,000 chunks, 64 dimensions, K=50.

| Metric | Frozen baseline | Optimized |
| --- | ---: | ---: |
| Full vector scan | 16,000 chunks | 16,000 chunks |
| Vector candidate records retained | 16,000 chunk candidates | peak 50 page candidates |
| Median vector-only time (7 samples) | 45.739900 ms | 12.800900 ms |
| Backlink SQL statements for 554 fused candidates | 554 | 6 |
| Returned vector/hybrid results | baseline | exact identity/snippet/score/rank match |

The vector timing ratio here is 3.57x; it is not an end-to-end Agent speedup
promise. Candidate count is **not** allocator bytes, process RSS or database-buffer
size. No paid-provider call, billed-token comparison or semantic-relevance quality
experiment was performed. The scan remains linear in embedded chunks.

## Failed checks, diagnosis and changes

Initial run 34660468442 passed portable tests and Windows compilation but failed
the pre-existing HTTP process-handle growth check before the native retrieval step.
It did not record handle numbers before that assertion, so its magnitude and precise
root cause cannot be reconstructed from that log. The failed run remains visible.

A fixture-only follow-up records the historical 250ms observation and a fixed 2000ms
post-return observation, leaving every per-request deadline and the +16 handle
ceiling unchanged. This changes the handle measurement to allow bounded asynchronous
teardown; it is not a retry-until-green loop. Expected cancellation peer resets are
counted instead of producing long server traceback output. Product WinHTTP code
was not changed. Final handle samples: `{"at_250ms": [195, 207], "after_fixed_2000ms": [195, 207], "allowed_growth": 16}`.
All 64 cancellations and mixed concurrent requests passed in the final run. These
finite samples do not prove universal leak freedom or conclusively explain the
first failure. No statement that the initial assertion was definitely spurious is made.

Additional local all-C/C++ GCC14.2 ASan/UBSan stopped in the unchanged bundled SQLite
`balance_nonroot` expression during INSERT, before retrieval. A minimal SQLite-only
program with no Qbrain code reproduced the diagnostic. The exact expression and
message match [GCC120837, reported by SQLite's author](https://gcc.gnu.org/pipermail/gcc-bugs/2025-June/919344.html)
and [SQLite's analysis](https://sqlite.org/forum/forumpost/1d7c25d4a2d6f5e2).
This supports classification as the documented GCC sanitizer false positive; the GCC
run is nevertheless recorded as **not passed**, not silently converted to PASS.

A second build with Clang17 ASan/UBSan instrumented both C++ and the same bundled
SQLite C and passed the complete retrieval suite without changing source or disabling
checks. Separate debug-iterator enumeration passed 1,628,718 sequence/K comparisons.
These are local Linux checks, not Windows sanitizer or full-application coverage.
Bundled SQLite was neither patched nor upgraded by this node.

## Design and compatibility review

The selector retains an ordered set of at most K best page candidates and a matching
identity-to-iterator map. A page is updated only for a higher score or a smaller
snippet at the same score. The retained worst rank can only improve, so an evicted
page's old chunk cannot become relevant later; a genuinely better later chunk can
re-enter. Page metadata identity is stable within the original statement snapshot.
Existing per-page tie rules and best-chunk snippets are preserved.
Differential equality was checked on unchanged fixture data. Hybrid search still
uses multiple live statements; this node does not create an atomic cross-statement
snapshot or promise identical timing-dependent results during concurrent writes.

Backlink batches bind at most 300 parameters for 100 candidates, match both source
and slug, and use the existing links index. Counting semantics, including the old
maximum-five-links boost, are unchanged. No raw link content is projected. Source
and deletion filters remain on the original vector statement; there is no new
result or embedding cache whose invalidation could resurrect deleted memories.

No schema migration, added required runtime, new MCP operation, changed provider
consent or broadened write authority. Rollback is a source/test/build revert, with
no database-format downgrade. The operation delta is recorded separately.

## Remaining limitations

No blocking defect in this scoped retrieval change was identified after the checks
above. This is not blanket approval of historical Qbrain code. PostgreSQL buffering
and parity, full ACL/DLP audit, model-provenance policy improvements, ANN, real
logged-in Win11 Agent consumption, semantic conflict resolution, paid quality/cost
experiments and signed production release remain separate tasks. Native CI platform:
`Windows-2025Server-10.0.26100-SP0`. Issue #2 stays open; do not mark all performance or memory work done.
