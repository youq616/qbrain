# N47H outcome review — bounded lifecycle candidate discovery

Verdict: PASS for the scoped N47H implementation. Reviewer: ChatGPT, separate
engineering self-review under the owner's explicit authorization. Not an independent
subagent or third-party audit; no promise that every possible defect is excluded.

Baseline: 612ccf22688bde71656e1ea5f771bd5afbd12ed5.
Actual product and original native source: 80fe1b9d31de6cc41d06be6db0e1035c1a747eb7.
Source tree: 5d17b1f68344d1c6370d4a113fddf5def1dc0e63.
Recovered 811 files from the fixed original source artifact; all matched locally
and reconstructed the exact Git tree. Product code, original tests, build files
and delivered ZIP bytes were not changed during this outcome pass.

## Acceptance against the approved plan

| Requirement | Actual check | Result |
| --- | --- | --- |
| Usable read-only discovery | FactStore::lifecycle_candidates, fact candidates, existing memory_read view | PASS |
| Live source-bound archive/restore eligibility | Active supported claims; archive needs unarchived stale support, restore needs archived live support; unknown/future age not stale | PASS |
| Age reuse without changed truth semantics | Shared strict N47F support age, original lifecycle17/180 rerun | PASS |
| More than first100 rows reachable | Keyset seek before bounded scan, empty continuation and deleted boundary ID tests | PASS |
| No interrupted-row loss | Whole metadata item and batch input accepted together; output/work interruption leaves current row unconsumed | PASS |
| Explicit no-progress behavior | Budget control fields retained, unchanged seek key identified; bigger budget resumes | PASS |
| Source/read permissions | Bound source/predicate/cursor, route-specific field/type rejection; old six tool names and write-default-deny preserved | PASS |
| Discovery never authorizes apply | N47G preview/apply revalidates actual evidence and expected revisions; intervening new support rejects whole apply | PASS |
| Read snapshot and no writes | Denying SQLite authorizer, caller transaction retained; real second WAL connection commits forget mid-read, next call sees removal | PASS |
| Current native and delivery evidence |56 registered Windows groups, new and retained suites, same-source package and sanitizer jobs | PASS |

archive/restore here selects candidates, not automatic application. after_id is
an untrusted seek filter, not an authorization token or cross-page snapshot lease.
A newly inserted or changed earlier key requires a restarted scan. has_more means
raw candidates remain, not that the next page is guaranteed to contain suggestions.
The newest valid support creation time is not last use, confirmation or confidence.
No additional schema, installer toggle, model request or automated maintenance.

## Current-source native execution

Development run35111907426 and N42 run35111907432 completed successfully. Required
source, portable, full Windows build/regression/package, Server2022 and sanitized
jobs succeeded. The generic publication jobs were skipped deliberately and are
not evidence that a Release has already been published.

- Exact Windows regression registry:56 groups, real PG DSN cases explicitly SKIP-PG.
- Candidate unit:17 scenarios/647 assertions on Server2025, Server2022, portable,
  and the Linux ASan+UBSan job.
- Candidate real CLI/MCP:43 named checks/63 commands on Windows, portable and
  sanitizer; native schedule has57 expected exit0 and6 expected negative exit1.
- Old batch15/259, lifecycle17/180, promotion18/237, Hook13/229, recall15/330,
  conflict13/346 and facts15/380 plus their process suites retained.
- Both Windows HTTP wire suites have81 checks and retain fixed cancellation and
  shutdown accounting. Existing queue/CJK/embedding/memory/MCP/Hook/context and
  PowerShell5.1/7 tests and explicit installer consent gates retained.

Downloaded six original artifacts, verified external SHA256 before interpretation,
bounded members/CRC, reconstructed source tree, compared all package inventory
members and original native report bytes, and reran full report validators:
254 readback checks passed. This checker does not run the Windows application.
Unit probe binaries were not independently downloaded: identities are anchored
in externally pinned original reports and the original package job's actual
probe-file checks. This limitation is not relabelled as separate binary verification.

## Additional outcome-pass execution

Rebuilt unchanged source with GCC14.2 on Linux. Candidate17/647, actual process43/63,
previous lifecycle17/180 and batch15/259 passed. Eleven current/retained report
and registry suites ran141 tests successfully. These are fresh local executions,
not Windows or a signed-in Claude/Codex client run. The archive-only local process
report retains source_commit=null; source bytes are bound separately by the tree.

The first build tool call was interrupted by the call time limit. Resuming the
unchanged incremental build succeeded. Neither source nor a product assertion
was altered because of this tool interruption; logs are retained locally.

A separate C++ model-based paging probe seeds288 synthetic claims across two
sources, including stale/fresh, archived/unarchived, unknown/future time, retracted,
forgotten, tampered and multiple-support cases. It models eligibility and expected
revision independently, then compares complete result sets under multiple output
budgets and page counts. It also explicitly applies selected pages and verifies
its own archive/restore writes do not cause later keys to be skipped.

The probe passed46 complete traversals and695 page calls, with12107 assertions:
332 fixture/setup assertions plus11775 assertions in three named scenarios.
No missing or repeated ID was observed against this independent expected model.
This is a finite synthetic experiment, not a million-event performance benchmark.
Its original source and result are archived under n47h-evidence.

A deliberately broken temporary copy advances consumed past an unreturned row
on output-budget exhaustion. Compiling and executing the original candidate unit
against that copy failed exactly at `unchanged cursor explicitly indicates retry
or stop` with exit1. The actual candidate files/libraries remained unchanged.
This checks that the budget-continuation assertion catches that fault; it is not
complete mutation coverage. The probe and fault copy use no real user brain.

## Findings and remaining limits

No unresolved scoped P0/P1 defect was found in this separate review. The earlier
implementation record describes a missing MCP operation whitelist field caught by
its first real process test, fixed before80fe1b9d; positive cursor/restore and old
view rejection cases now pass. That earlier failure is not rewritten as a pass.
The process test's opening docstring still says batch; this is cosmetic inherited
wording, not evidence the candidate suite was omitted (43 exact names verified).

Every page is one SQLite snapshot, not a snapshot across the complete walk. Do
not blindly retry an unchanged continuation forever. A conservative envelope
reservation can reject a very small byte budget even without a returned item.
Candidate/work/output limits are not limits on backup I/O, total SQL scan work or
hard-real-time latency. Archive remains a policy, not privacy deletion; valid
counter-evidence stays available and older binaries can ignore archive policy.
All inherited threat-model and PG-parity limitations remain.

SQLite documentation checked for keyset/scrolling-query and isolation semantics:
https://www.sqlite.org/rowvalue.html
https://www.sqlite.org/isolation.html

## Delivery decision

Original inner ZIP:2044265 bytes; SHA256
6d4747d0332fc39e45a5ca4b2e815ee01e135959b97722ae92287dbaa14508cd.
EXE:4027392 bytes; SHA256
db0e27e9f14e263a11aad19c31eaaeac78abbe117556c067c624fcf328df4421.
No rebuild/repack of these delivered bytes; unsigned development preview.
The stage may be merged and this exact tested package promoted through a fixed
reviewed Release step, without overwriting old releases or enabling generic
unreviewed publication. No new local-agent task or repeated N47E live-host test
is required. Auto-aging, usage counts, semantic consolidation, profiles, PG parity,
full ACL/DLP and whole-project completion are not established by this stage.
