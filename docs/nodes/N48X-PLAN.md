# N48X — logical model invocation lifecycle, separate from HTTP attempts

2026-09-30. Base 0e3c12390ee0f7c2bd8ee9881b6630f4346038fd /
tree572a6c28aaa5827baba2932043409ab60e5a82ed. Status: approved after the separate
N48X-PLAN-REVIEW.md. Original Issue2/N46 full-call visibility; the preceding actual
probe demonstrated pre-HTTP failures and mock success invisible to HTTP-only observation.

## Deliverable and boundary

New explicit observe-model wrapper records four instrumented existing entry points:
chat_complete, embed_texts, embed_image and apply_reranker. Missing credentials,
invalid input, empty/disabled calls, local mock/baseline, explicit test callbacks,
remote branches and fallback are fixed enums, not inferred by parsing error strings.
Function return/exception is distinct from provider completion and process exit.
Logical tokens, prices and costs remain null; known quantities stay exclusively
in unchanged HTTP records and existing offline pricing. No second billed call per
parent, no invented HTTP for local outcomes, no automatic request retry.

Reuse the 0e3c HTTP Collector/Session without changing its source or schemas.
Its synchronous Writer callback records a separate bounded link from an actual HTTP
sequence to the innermost same-thread logical scope in this observation session.
Nested API calls have parent IDs; worker threads start independent roots, not
implicitly propagated parents. Outside-scope, dropped-call and mismatched-session
HTTP links remain explicitly unattributed. An HTTP attempt is not proof of delivery.

Independent process-wide opt-in session, bounded 512 logical calls and 512 retained
HTTP links, all fixed enums/numbers/nullable fields. No prompt, reply, endpoint,
model name, error text/code, credentials, response IDs or hashes of private strings.
Original command stdout/stderr and legacy rerank audit are unchanged and outside
this sidecar privacy claim. No claimed complete application/model coverage.

## Acceptance

- The four actual entry points return identical results and preserve original
  exception/fail-open behavior with observation on/off. Default off creates no files.
- Preflight failure/mock/empty/noop yield zero actual HTTP entries. Valid remote
  paths use real HTTP Collector IDs. Nested rerank->chat links to child only;
  direct uninstrumented HTTP remains unattributed instead of guessed.
- Original outcome/status/error/dispatch semantics remain unchanged. Tokens/prices,
  final process_exit, stdout_complete and stderr_complete stay unknown where
  unobserved. Closed-reader behavior/signals and flush ordering are not changed.
- Start/finish files and bounded final reports retain pending/exception/fallback.
  Abrupt kill leaves start-only evidence, not synthetic cancellation/success.
- Independent concurrent call scopes, nested and exception unwinding, capacity,
  writer errors, duplicate finishes, session transitions and late completion are
  tested. Sealed reports are immutable. No instrumentation lock across model work
  or HTTP; active session acquisition order is fixed.
- Strict paired-report verifier checks enums/types/counts/parents and HTTP link
  cardinality against original HTTP validator. It authenticates neither colluding
  evidence producers nor billing. No automatic v1/v2 metadata upgrade.
- New native and actual CLI/loopback tests plus unchanged original observation,
  semantics, transport/core/rerank regressions on exact new Windows/Linux candidate.
  Local ASan/UBSan and cache-free concurrency tests bind exact sources; native queue
  waiting is not PASS. A new non-author review is required and separately attributed.

## Isolation, recovery and rollback

Implement on feature/n48x-logical-observation branched at 0e3c; never update PR65's
frozen branch. No writes to PR61 six files, PR62/63, PR64/d57 or their CI. The rejected
GitHub.create_blob -> tests/test_pg_directory_cache.cpp remains frozen without
retries, substitution or retransmission. No merge/deployment/paid model/user data.
No new runtime toolkit. Retain exact diff, full tree, failed attempts and logs.
No database schema change; removing the new code or not selecting observe-model
restores unobserved behavior. Existing observe output stays byte-contract compatible.
The new branch depends on 0e3c interfaces, not on its unreturned non-author verdict;
its own correctness and integration must be independently assessed.


## Publication amendment, reviewed before push

To avoid manual retranscription of four long inherited files, the new branch carries
a readable git patch with exact before/after blob IDs in .ci/stage_n48x_runtime.py.
Its prepare job is the only contents-write job, can fast-forward only this new branch
at its expected trigger head, and commits only those four files. It refuses dirty,
mixed or unrelated bytes. All native jobs then checkout the emitted actual commit;
bootstrap trigger SHA is not claimed as the tested source SHA. The complete recoverable
diff and tree are saved. No hidden compile-time patch, protected-branch write, force
push, merge or frozen PG action is involved. Design review accepts this bounded
publication mechanism; the exact local assembled tree must match final remote tree.
