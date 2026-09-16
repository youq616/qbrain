# N47F outcome — reversible archival and advisory lifecycle inspection

Verdict: **PASS for this scoped N47F implementation**. Reviewer: ChatGPT,
separate engineering self-review authorized by the owner. Not an independent
subagent or third-party audit, and not a guarantee that all defects are absent.

Product source: `cafb48667177002ae6ea0f1976eea2f388826024`.
Product tree: `f0111dbec7b3158dc495b3a6394332c23f557212`.
Baseline main: `81a61e02dfb8fde6bb99e8ad38e09fc3e4145e4f`.
PR #22 is the integration location. This outcome supersedes the pending CI status
in N47F-REVIEW-CHECKPOINT.md; the checkpoint and original failures stay unchanged.
All post-candidate changes in this review are documentation, not product code.

## Scope versus the earlier conversation

Implemented: explicit `fact archive`, `fact restore`, `fact lifecycle`, and
corresponding actions/views within the existing memory tools. Archive is metadata
for recall organization, not a new truth/retirement status. The age display uses
the newest valid support creation time, never an invented last-use or trust score.

Not implemented: automatic usage/confirmation counters, semantic consolidation,
automatic aging/archival, inferred temporal supersession, profiles or million-event
performance guarantees. Different wording is not automatically the same fact;
chronology does not prove supersession. N47E already handles exact-equal local
quotes. Completing this slice does not complete the larger lifecycle roadmap.

## Plan acceptance and separate code review

| Requirement | Observed implementation and evidence | Outcome |
| --- | --- | --- |
| Explicit reversible policy | Archive/restore require current expected_revision, active status and complete live evidence; metadata/revision change in one write transaction | PASS |
| No resurrection | Retracted, superseded, expired, tampered and forgotten facts cannot be restored; same-ID promotion does not clear archival | PASS |
| No convenient suppression of counterclaims | Archive filters recall anchors before the cap but not valid direct counter-evidence for another anchor; explicit reads/conflicts remain available | PASS |
| Privacy cleanup | Archive table contains no quotes; fact/source foreign key cascades after final-support deletion | PASS |
| Lazy migration and honest failure semantics | First on-disk module setup backs up before DDL; ordinary reads and unarchived restore create no tables; later transition failure may leave empty module/backup, never a partial policy/revision change | PASS |
| Snapshot and caller transaction ownership | A live read statement pins optional-schema detection and evidence loading; no BEGIN/ROLLBACK on read; actual second-connection initialization interleaving and caller rollback tested | PASS |
| Strict advisory timestamps | INTEGER storage only; malformed support TEXT/REAL/BLOB gives unknown/null, malformed archive time fails closed; valid, negative and future time controls retained | PASS |
| Source and write gates | Bound source/ID/predicate; default write denial and six-tool registry unchanged; strict CLI/MCP inputs | PASS |
| Read-only and bounded output | Write/transaction-denying authorizer; no usage writes, no partial fact, candidate/work/byte limits and explicit truncation | PASS |
| Old features and delivery identity | Exact 54 native groups plus all inherited process/install/report gates; candidate and original package independently read back | PASS |

Archive is not a secrecy boundary or forget: archived facts may still appear as
mandatory counter-evidence, in explicit fact/conflict inspection, old ordinary
memory when fact recall is disabled, independent same-quote facts, backups or
existing client contexts. Older binaries ignore this policy; downgrading does not
preserve it. These are documented semantics, not a claim of secure erasure.

Schema setup and an ensuing archive transition are separate transactions. The
precheck avoids side effects for known-invalid input, but a concurrently invalidated
request may leave an empty prepared module and backup. No claim of total filesystem
rollback is made. First-write backup count may depend on concurrent initialization.

## Repaired defects and retained evidence

1. Original lifecycle BEGIN/ROLLBACK on read violated the old N47C authorizer.
   Native run 35058294020 failed. f585eed0 replaced transaction-control SQL with a
   pinned read statement and strengthened the new authorizer test. No old assertion
   was removed or weakened.
2. Further review on f585 reproduced TEXT `123not-a-timestamp`, REAL `123.75` and
   BLOB `123` being coerced to integer time 123. cafb4866 checks SQLite storage
   classes and adds the 17th named scenario. The report gate now rejects the former
   16-scenario report even with internally consistent old totals.

SQLite permits non-INTEGER storage in ordinary integer-affinity columns, and
implicit transaction lifetime is tied to active statements. References checked:
https://www.sqlite.org/datatype3.html
https://www.sqlite.org/lang_transaction.html

## Completed new-source native execution

Development run **35076641849** and N42 run **35076641751** completed all required
jobs successfully on cafb4866. The two generic publisher jobs were deliberately
skipped; their status is not evidence of a release.

- Full Windows registry: 54 named groups, with real PostgreSQL DSN cases explicitly SKIP-PG.
- Lifecycle unit: 17 scenarios / 180 assertions on Server 2025, Server 2022 and portable.
- Lifecycle CLI/MCP/Hook process: 36 checks / 58 commands on Windows and portable;
  52 expected exit-0 and six expected negative exit-1 results, not all zero exits.
- Prior promotion: 18/237 unit, 68/77 process; Hook composition: 13/229 unit, 52/72 process.
- Prior recall: 15/330 unit, 44/71 process; conflicts: 13/346 unit, 38/75 process;
  facts: 15/380 unit, 34/118 process.
- Both Windows HTTP jobs: 81 wire checks and unchanged fixed cancellation/shutdown gates.
- CJK 72 unit / 36 process; queue 40 scenarios / 776 assertions; embedding 65/26/11.
- Memory/MCP/Hook/context/config 44/17/69/65/6; PowerShell 5.1 and 7 each retain
  installer69, consent16, transport8, fact-recall installer33 and promotion installer33.

## Sanitizers and current continuation checks

The earlier local ASan execution failed before main due to shadow-address
reservation under its environment's 4TiB hard limit. That record is not rewritten.
Separate read-only workflow **35077139073**, workflow source 9db6bab6, checked out
immutable cafb4866, built SQLite C and C++ with ASan+UBSan, and actually passed
lifecycle17/180, lifecycle process36/58, old recall15/330 and 14 report tests with
halt-on-error and leak detection enabled. The downloaded full report/summary and
source identity were revalidated. This is Linux instrumentation, not Windows ASan.

This continuation additionally rebuilt the unchanged archive with GCC 14.2 and
ran lifecycle17/180, old recall15/330 and the actual 36-check/58-command lifecycle
suite; all returned exit0. The source archive has no Git HEAD, so local process
source_commit remains null; identity is bound separately by exact tree rebuilding.
All 111 report/registry tests reran successfully. Prior graph/state oracle and
mutation checks remain separately recorded in N47F-REVIEW-CHECKPOINT.md and are
not misrepresented as additional executions in this continuation.

Six original artifacts were downloaded with fixed external SHA256, bounded member
parsing and CRC checks. **212 readback checks** verified the 782-file source tree,
complete package inventory, byte-identical original native reports, complete unit
scenarios/assertion sums, process exits, source/test/EXE binding, installer reports
and both HTTP schedules. Unit probe binaries were not separately downloaded; their
identity comes from fixed original reports and same-source packaging checks of the
actual probe files. The readback itself did not execute the Windows EXE.

Our first exploratory readback used an incorrect lifecycle report filename and
raised FileNotFoundError; the archive inventory identified the actual
fact-lifecycle-unit.json path. No original report or product assertion was changed.

## Delivery and remaining limits

Original tested inner ZIP: 2,005,834 bytes; SHA256
`c16f15a7ad318beb58059b05d3f400399b33d34c000d040c3c1ddcc179641f55`.
EXE: 3,986,432 bytes; SHA256
`7032a300215874111bcc0f40b47a9bb2efd357cac85b047b99942fd637304ca1`.
They are unchanged, unsigned development artifacts, not a new signed-in host test.

No unresolved scoped P0/P1 defect was identified. Age is advisory; result/candidate
limits do not bound all SQLite scans or provide hard-real-time latency. Direct
malicious database rewriting and backup/WAL erasure are outside these guarantees.
The N47A P3 register and broader roadmap remain open. Stage integration and exact
versioned promotion may proceed, with no rebuild/repack, old-release overwrite or
general unreviewed auto-publication. Any promotion must bind the reviewed source
and original evidence again. No local-agent task, compiler install or credentials
are required for this repository-side completion.
