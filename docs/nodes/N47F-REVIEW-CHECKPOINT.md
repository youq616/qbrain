# N47F outcome-review checkpoint — native acceptance pending

Reviewed candidate: cafb48667177002ae6ea0f1976eea2f388826024.
Candidate tree: f0111dbec7b3158dc495b3a6394332c23f557212.
Baseline main: 81a61e02dfb8fde6bb99e8ad38e09fc3e4145e4f.
Reviewer: ChatGPT, separate owner-authorized engineering self-review, not a
third party or an independently spawned subagent. **Stage acceptance is PENDING**.
The corrected product must receive its own native results before merge/release.
This checkpoint is not N47F-HARD-AUDIT PASS and does not mark the plan done.

## Actual scope, correcting earlier conversational overreach

Implemented: explicit per-fact archive/restore with expected_revision and live
original evidence, plus read-only advisory lifecycle age. Archived facts cease
to be recall anchors but remain mandatory direct counter-evidence for other live
anchors. They are still available to explicit fact/conflict inspection. Archive
is not forget, a confidentiality boundary or a replacement for retirement.

The lazy archive table stores only IDs/source/time, with FK cascade after final
support deletion. The first disk initialization backs up the database. Preparation
and the later state transition are separate; failed transitions can leave an
empty optional schema and backup, but not a partial policy/revision mutation.
Restore cannot revive retracted, superseded, expired or forgotten evidence.

Not implemented: semantic consolidation, usage/confirmation counters, automatic
aging or archival, inferred temporal supersession, trust scoring or million-event
performance guarantees. Age uses newest valid support creation time, not use.
Old binaries ignore archive policy; downgrade is not transparent preservation.

## Defects identified and repaired before this checkpoint

1. The original lifecycle snapshot implementation issued BEGIN/ROLLBACK, violating
   the existing N47C authorizer that denies transaction-control SQL. Native run
   35058294020 failed. Commit f585eed0 instead holds a read statement at SQLITE_ROW
   across optional schema detection and nested reads. It never controls the
   caller's transaction. The original assertion remains; lifecycle tests now deny
   SQLITE_TRANSACTION as well. Runs 35059423059 and 35059423055 subsequently passed
   on f585, but those results are not new-candidate acceptance.
2. This outcome review then reproduced malformed TEXT `123not-a-timestamp`, REAL
   `123.75` and BLOB `123` support timestamps being coerced to integer123 and called
   stale. This was a P2 advisory data-quality defect, not source/evidence disclosure.
   A plan was committed before the narrow correction. Candidate cafb4866 checks
   SQLite storage type: non-INTEGER support time produces unknown/null age/time;
   malformed archive time fails with fact_lifecycle_invalid_metadata. Existing
   negative/zero/future handling and complete-evidence checks remain unchanged.
   A new named scenario covers malformed types, valid controls, unchanged revision
   and archive metadata. The gate rejects the formerly valid old scenario set.

## Separate review checklist

| Area | Observed local evidence | Disposition |
| --- | --- | --- |
| Revision and evidence safety | Fresh/no-op, stale revision, live evidence, retract/supersede/expiry/forget, transaction rollback and two-connection races | Tests pass; native revalidation pending |
| Counter-evidence | Independent expected adjacency sets over archive/restore/attach/retract/forget; archived neighbors retained | Tests pass; deliberate violation caught |
| Read-only compatibility | Old recall authorizer plus caller transactions; no usage writes or migration during reads | Old and new units pass |
| Time quality | TEXT/REAL/BLOB and integer controls in new scenario | Fixed; old-report gate rejects omission |
| Source/MCP/Hook boundaries | Existing source denial/default write refusal and all twelve process suites retained | Tests pass locally |
| Source identity | Old 781-file archive reconstructed; every changed local blob matches uploaded object; mutations did not modify candidate | Checked separately from null local HEAD |
| Delivery | No new native package or ASan result has been certified | Merge and publication remain blocked on evidence |

## What actually ran here

Compiler: Clang17, Linux. Bundled SQLite C and application C++ were built with
UndefinedBehaviorSanitizer and halt-on-error. Corrected lifecycle: **17 scenarios,
180 assertions**. Actual lifecycle CLI/MCP/Hook process suite: **36 checks,
58 commands** (52 expected exit0, six expected exit1). Both passed.

All twelve process suites completed exit0: local_config, memory_cycle,
mcp_boundaries, hooks, context_process, embedding_search, fact_process,
conflict_process, recall_process, hook_fact_process, promotion_process and
lifecycle_process. Old standalone units also passed: fact15/380, conflict13/346,
recall15/330, Hook13/229 and promotion18/237. These are new local runs, not a
substitute for Windows. A long initial multi-unit tool call was interrupted by
the host execution limit; remaining units completed in a bounded worker with
saved per-command logs rather than inheriting a success from the interrupted call.

Independent graph/state oracle: two sources, eight facts each, archive/restore/
attach/retract/forget phases and fifteen budget/limit combinations per source and
phase. **1,180 state assertions / 217 real CLI commands passed**. Assertions repeat
across states; do not call them 1,180 unique user scenarios or a scale benchmark.
The oracle derives expected revisions, status, anchors and adjacency independently.

Two temporary mutated implementations failed as intended: removing the support
storage-type guard fails `noninteger support time is unknown`; hiding archived
neighbors fails `archived counterclaim retained`. The first result matcher expected
an inaccurately paraphrased message and initially failed; original logs were kept,
the actual source assertion was verified, and no product assertion was changed.
The second mutation was executed separately. Neither changed candidate bytes.

Report/registry gate suites rerun: CJK10, conflict10, fact12, Hook12, HTTP14,
lifecycle14, promotion13, recall10, registry16 — **111 tests**, all successful.
Local archive-only reports keep source_commit=null and do not invent a clean HEAD;
exact source identity is established from the downloaded archive and changed blobs.

## Instrumentation limitation and queued work

AddressSanitizer compilation succeeded locally, but execution failed before main
while reserving its shadow address range under this runtime's 4TiB hard address
limit. ASan execution is **BLOCKED here**, not PASS or a product failure. UBSan is
separate evidence. The failed ASan log is retained.

A read-only GitHub job now checks out immutable cafb4866 and builds/runs both ASan
and UBSan on a separate Linux runner, including new lifecycle and old recall units,
actual lifecycle processes and source-bound report checks. Workflow commit
9db6bab6f56c6943822e1147c5441fb21535b7c0 / run35077139073 adds no product files.

At this checkpoint, new native development run35076641849, N42 run35076641751 and
sanitizer run35077139073 are queued. The native jobs have no assigned runner or
executed steps in the last retrieved response. Do not speculate about billing or
outage, retry unchanged code until green, reuse the earlier package, or ask the
owner to install a compiler as a workaround. No local-agent task is required.

Next gate is actual completed new-source native results and exact artifact
readback, followed by final acceptance. No current runtime defect remains known
from this pass, but this is not proof of universal correctness or permission to
mark the stage complete while required checks are pending.
