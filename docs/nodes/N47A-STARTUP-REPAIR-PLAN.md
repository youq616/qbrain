# N47A follow-up — startup contention and independent review

Baseline candidate: 12807f2be0a8692560d2553217b1df62f5511893.
The owner now requires an independent subagent review at the end of every stage.
Self-review, a CI job, a second shell process, or an unfulfilled reviewer request
is not that review. Continue repairs and tests, but do not mark the stage done,
merge, or automatically publish it without an actual source-bound independent
review result. This supersedes the earlier self-review-only release convention.

## Reproduced failure

Native run 34772721497 passed compilation and 14 fact-unit scenarios, then failed
the real two-process create test: one child exited 2 instead of 0. The process
harness omitted stderr and reported 29 PASS / 0 FAIL despite result=FAIL because
it threw before recording the interrupted scenario. The gate correctly failed;
the reporting detail still needs repair.

A separate fixed 64-round/two-process Linux diagnosis on unchanged source
reproduced exit 2, with stderr `open brain failed: database is locked`.
This occurs before FactStore's transaction wait. A separate long-held normal
WAL writer did not reproduce a read failure; do not claim all busy writers fail.
Opening/recovering/closing short-lived SQLite connections can require locks.

## Approved engineering change scope (before implementation)

Use a bounded SQLite busy callback only while a new backend performs startup
PRAGMAs. Share one steady-clock deadline across those setup calls, remove the
callback on success, and close the new connection on failure. No retry of an
entire user operation, no unbounded sleep or new persistent timeout setting.
Preserve foreign keys/WAL/synchronous settings and ordinary per-operation policy.
Test temporary vs persistent startup locks, connection cleanup/reusability,
unchanged default timeout, and fixed repeated true CLI process races. Add real
error capture with bounded/redacted fixture stderr, failure records and exact
new report/command-count checks; keep all old fact cases.

The native failure's original stderr was unavailable, so the local reproduction
supports an opening-lock diagnosis but is not a claim to have observed its exact
Windows PRAGMA. New tests must retain stderr for every future unexpected exit.
Do not alter transaction consistency or lower success criteria to hide contention.

## Review and release

Disable the automatic fact-preview publisher while independent review is pending;
CI artifacts may still be built as unapproved candidates. Preserve all Windows,
portable, HTTP, CJK, queue, memory and fact gates. Add an explicit review handoff
for a real independent agent with reviewed SHA, findings, tests and limitations.
Do not fabricate an agent identity or claim review from a request with no result.
No unrelated project, credentials, live user brain or paid model test is involved.
