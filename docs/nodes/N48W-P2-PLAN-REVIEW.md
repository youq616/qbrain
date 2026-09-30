# N48W P2 report-semantics repair plan and review

Base dd1f35d9abe0048c9d81043ea551b5196f87086b, tree
b42d8742cc71168737842213f6a8953cd6127f77. Owner supplied a non-author review:
no remaining P0/P1 in the same-process HTTP sidecar scope, with two P2 findings.
Reported independent evidence: native55, 15 extra lifecycle cases,1600 concurrent
attempts/cap512, normal/-O19CLI, original8 groups, exact Windows archive/source1556,
55native/66process/81transport/9CTest/privacy. These are attributed owner-relayed
results, not new coordinator executions. No whole-run/native/sanitizer/PG/real-user
completion is inferred. Existing dd1 and all older artifacts/queues stay intact.

## Required behavior

P2-1: Keep explicit Responses completed/failed/cancelled/incomplete; retain the
existing pending/unknown classification and no-final-usage guard. Observe only a
nullable Boolean provider_error_present, never error text/type/code. A completed
status with a nonnull error has provider_status_conflict=true; it is not evidence
of success or failure. Cancelled/incomplete plus error need not contradict their
states: retain both facts without rewriting either to failed. Cancellation retains
its existing conservative cost outcome; incomplete and completed remain unknown.
The error text cannot promote a nonterminal status. Contradictory completed data
may retain independently valid *reported terminal usage* for an estimate, but price
outcome remains unknown and application_success_verified stays false. This is not
invoice authentication. Invalid usage preserves only independently parsed status
and error metadata; none of its quantities survives.

P2-2: Report v2 removes command_exit. It records dispatch_state
returned/exception/not_observed and nullable dispatch_return. Final process_exit,
stdout_complete and stderr_complete are always null: same-process sidecar writing
before final stream flush cannot authenticate them. recording_complete keeps its
existing formula, explicitly scoped to http_attempt_records_only, not process or
output delivery success. On invocation exception the dispatch return is null, not
an invented returned2. First report sealing also freezes these dispatch fields.
No signal handler, SIGPIPE ignore/block, pre-exit cout/cerr flush, retry, waitpid or
main/transport dispatch behavior changes. A report can truthfully record a returned
0 while its externally supervised process subsequently dies of SIGPIPE.

Observation v1 is not silently upgraded: old report command_exit and error-overwritten
provider states are ambiguous. New validator/cost ingress accepts v2 only; old files
remain evidence. Cost report becomes v2 and propagates the limited completion scope.
Do not modify old account arithmetic or token normalization. Strict types and unknown
metadata refusals apply on offline readback.

## Falsifiable acceptance

1. Reproduce old three terminal+error overwrites and old actual Linux closed-reader
   help/observed-help/init signal deaths using dd1. Keep original outputs and return
   signals. Compare new output/exit with ordinary CLI; no monkeypatch signal behavior.
2. Cross terminal/pending/unknown status with absent/null/object/scalar error; test
   missing/invalid usage, exact roundtrip and forged fields. Positive terminal usage
   and f7 pending+error regressions survive. No error canary in sidecar or cost output.
3. Real parent/child pipe: close reader before spawning. Python restore_signals=True
   restores the normal child disposition. Actual help/observed-help/init must retain
   the inherited SIGPIPE on POSIX; report v2, when present, has returned0 but unknown
   process/output completion. Ordinary successful output and dispatch error paths are
   also exercised. Windows results must not be mislabeled as POSIX signal evidence.
4. Fixed new SHA native Windows/Linux, retained55/core/process/HTTP tests, new explicit
   semantics/pipe regression and local sanitizers. New request/record counts must be
   attributed to that candidate; dd1 green cannot qualify this delta.
5. No PR61/62/63/d57 modifications, no frozen tests/test_pg_directory_cache.cpp action,
   no cancellation of old queues, merge, deployment, paid provider or runtime package.

## Separate coordinator plan review — before implementation

Read full collector/projection, strict report/price ingress and wrapper, original
native/process/HTTP suites and early dispatch. External references are POSIX write
(SIGPIPE when no reader) and the OpenAI Responses schema's separate status/error
fields; implementation supports a bounded subset, not arbitrary provider behavior.
Chosen fix changes evidence semantics rather than masking final I/O failures. Treat
retention completeness and command/process status independently. Explicit cancelled
is not silently renamed failed; completed+error gets a conflict flag. No source
content is persisted by new fields. Version the document instead of inventing legacy
metadata. First-seal dispatch state must not later change. Native/author review is
not a non-author review. Verdict: PASS to implement this limited plan; no outcome
PASS or full module acceptance declared. Reviewer: owner-authorized coordinator.
