# N47W final outcome review — process bridge diagnostics

2026-09-20. **PASS for the approved source feature. No known unresolved blocking
finding remains within this scope.** Issue40 stays open; its historic timeout cause
is not established. This is not an absolute defect-free or stable-v1 guarantee.
Reviewer: coordinating ChatGPT, in a separate engineering outcome review explicitly
authorized by the owner, not another subagent, Claude Code or a third party.

## Reviewed identity and scope

Base main: a3436c09e1eaed1d1e4eb6dcfaffbe19cc443eca.
Approved plan/review: ecdf4eac7dacd0c0c6583aa21ea4a973a7430570, before implementation.
Accepted source: ea3b3f5a4ea1cd03541a5aedbf413ed0f1a3a6c1.
Accepted tree: 2243a7baccecf13e2150f04e74363fbe8684bb9a.
Fixed workflow:35477227325, push, attempt1. All four jobs and required steps passed.
The original plan is preserved at n47w-evidence/APPROVED-PLAN.md without reducing
its acceptance criteria. Only Invoke-QbrainJson.ps1 changes among inherited
production files. C++, schema, installer, Hook definitions, old tests/builds,
permissions, canonical operation ledger and inventory remain unchanged.

## Acceptance mapping and independent outcome review

| Approved criterion | Actual code and executed evidence |
| --- | --- |
| Useful, private phase diagnostics | Fixed primitive-only allowlist distinguishes start, input, process wait and output drain. Metadata samples task status and nullable direct-process exit before cleanup, without reading task fault messages or including streams/arguments/paths/environment. Native sentinel and strict field tests pass. |
| Default compatibility | Ordinary success has exactly ExitCode/Stdout/Stderr. The test's exact original/new outputs match for Unicode content and nonzero exit7. IncludeDiagnostics changes only the opt-in result. Original transport and installer tests remain unchanged and pass. |
| Correct wait budget | The old input Wait used the full timeout after startup. The new helper uses the same elapsed-time remainder as process/output waits, clamps zero and long elapsed values, and keeps default10000/range100..120000 and original timeout strings. Native recorded wait budgets are non-increasing and consume startup. |
| Failure classifications | A compiled native test child deliberately stalls input, remains alive after stdin closure, or exits while a descendant holds output. Actual observations distinguish these conditions. Invalid executable and invalid UTF-8 also yield the intended fixed category without raw native error text. |
| Cleanup and test safety | Existing direct-child Kill/2000ms cleanup is retained, with no production tree-kill. Separate review found the fixture cleanup relied on PID alone; final harness checks the exact executable path before terminating and refuses the running PowerShell host. Its repaired source was retested. |
| Original gates and raw readback | Both native shells passed29 new checks/6 observations,24 snapshot,60 recovery and five original installer suites. Source-owned checkers were rerun against downloaded exact reports/scripts/executables; native60 groups and BUILD_OK were verified separately from the original log. |

The original29 assertions and names were retained during the cleanup correction,
with a stronger identity-refusal conjunct. See SEPARATE-REVIEW-FINDING.md. This is a
review-discovered test-harness issue, not a claimed reproduction or fix of Issue40.
The earlier50dda native diagnostic passes are historical, not substituted for the
final repaired-harness run. No test timeout was raised, retried-until-green policy
introduced, or original assertion removed to achieve acceptance.

## Exact executed evidence

Final job IDs: source105988461031; PowerShell5.1 transport105988461093;
PowerShell7 transport105988461064; full-native105988460945.
The two transport jobs compile the deterministic .NET Framework test-only child,
use the exact original N47R/c26 executable for unchanged Qbrain regressions, and
execute the candidate bridge from the checkout. The independent full-native job
freshly builds the production application and its original full test suite; its
binary is not falsely equated with the separately pinned released EXE.

Per native shell:29 diagnostic checks,6 observations;24 snapshot and60 recovery;
69 installation,16 consent,8 byte transport,33 fact-install and33 promotion-install
checks. Full native:60 registered groups individually validated, with BUILD_OK.
Actual PostgreSQL remains SKIP-PG. These induced failures test observation behavior,
not a logged-in client, paid provider, broad performance or historic timeout cause.

Four original artifacts were downloaded and their IDs, sizes, SHA256, CRCs and
source markers checked; complete pins are in SUMMARY.json. The canonical source
archive reconstructs1173 files and exactly the accepted Git tree. Native bridge
bytes equal the exact CRLF representation of the reviewed source. The original
bridge is independently bound to its unchanged Git blob. Test-child and test-script
hashes match each report and the original compiled artifact. The EXE used by old
suites was independently recovered from the hash-pinned N47R bundle.

The original new-report validator, snapshot/recovery and fact/promotion validators
were rerun on the downloaded reports and matching component bytes. Ordered29
labels, original69/16/8 log sequences and snapshot/recovery names agree. Normal and
optimized Python both pass the complete local readback and the4 checker methods
covering25 malformed report/diagnostic/JSON variants. An additional8 mutations of
the actual PS5 report were rejected, and the unchanged positive control passed.
These are local evidence processing, not local Windows execution or authenticity
certification of arbitrary caller reports. No PowerShell/native Windows process
was executed in the Linux review environment.

## Meaning and remaining limits

Exception.Data[QbrainTransport] and optional Transport are the shareable payloads;
an entire PowerShell ErrorRecord may still contain call-site data, and successful
Stdout/Stderr remain raw application output. Preflight/binder failures may have no
diagnostic. Non-timeout native start/stream exceptions now use generic messages and
omit inner exceptions; that intentional compatibility boundary avoids path leakage.
No diagnostic is automatically written to disk or uploaded, and inherited installed
Hook exception handling is unchanged. Swallowed errors do not become durable logs.

Process.Start returning means a process was started, not that its internal startup
or host/model initialized. Timings include bookkeeping; stage sums need not equal
elapsed_ms, and task/exit states are sequential samples rather than a frozen snapshot.
Synchronous OS start, input close and finite cleanup are not cancellable by this
budget. Thus no strict total wall-clock ceiling is promised. At zero remaining
budget an already-completed task can still succeed. Existing unbounded output
capture and direct-child-only cleanup are not an untrusted-executable sandbox.

The historical Issue40 observation remains open with unknown cause. This stage
fixes the separately visible input-budget allocation and supplies future diagnostic
observations; neither establishes why the previous Codex Hook timed out. Full native
and synthetic child tests do not replace real client/model/usage-cost acceptance.
No new Release/tag or public package is created. Current N47R downloads lack these
bridge changes. Final candidate integration, true external use, PG and signing gates
remain uncompleted; existing conditional round estimates are not mechanically reduced.

The final closing commit is restricted to documentation/history and derived evidence
records. Compare it with ea3 before merge, preserve the accepted product/test/workflow
bytes, and record the actual merged tree in PR41. Merge-triggered CI is not assumed
successful in advance. Raw Actions artifacts have their declared retention windows;
Git summaries are derivative records, not an assertion that entire raw archives are
permanently retained in this repository.
