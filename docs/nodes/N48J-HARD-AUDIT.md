# N48J separate outcome review — execution-to-cost bridge

2026-09-26. Reviewer: ChatGPT, owner-authorized separate coordinator self-review
performed after implementation. This is not a subagent, Claude Code or third-party
review, and not a guarantee that every possible defect is absent.

## Exact change and accounting scope

Base main `3c944a9df0ca1867ff3b320a20f4a3632c92ff0f`, tree
`f162c1ce07af8c869a9a8bb7312afa6bfbf74307`. Candidate
`bb5ea5fea724407ddb1ab1422f42bd80a2fbc122`, tree
`96f148ab8937f7b847b8bf135f688d6ff710c9d6` adds exactly five files: the optional
Python bridge, its tests, dedicated CI, plan and design review. All existing native
product sources, N47S execution/scoring/consent code, tests and CI files retain
base bytes. The local Git commit is a mirror with an identical tree, not a
re-created original GitHub commit. Native local tests use the already qualified
N48I Linux executable; N48J does not change that executable's source.

The bridge reads only an explicitly selected saved N47S run, rate document and
trusted native executable. It validates source evidence and delegates normalization,
pricing and paired comparison to unchanged native N48G/F/I. It does not call the
HTTP executor, read the answer key, read a model credential or access a brain.
Its required scope is `scheduled_main_requests_only`: no claim of total pipeline
costs, authentic invoices or quality-preserving savings is made.

## Review against the approved contract

| Requirement | Actual review disposition |
| --- | --- |
| Fixed plan/run identity and coverage | Strict fields/types, regenerated schedule/request bytes, started/finished receipts, parsed completed response metadata, hashes and directory inventories are checked. A missing final run.json is refused; unattempted rows are not fabricated provider calls. |
| Preserve original cache information | Cost normalization receives the explicit terminal response projection from verified raw JSON, not the lossy input/output totals in receipts. Missing/null/contradictory/unsupported usage retains unchanged N48G behavior. Duplicate response IDs are checked across both arms. |
| Keep failure costs without invented completeness | Failed terminal answers retain available token usage; absent/nonterminal/redacted responses become unknown failed attempts. Partial runs retain observed calls and all planned coverage; no paired result is emitted until all 100 positions were attempted. A final failure with 100 attempts still withholds differences. |
| Correct common-task binding | Common conditions and each task bind the same plan and packet PAIR, not different treatment requests. Exactly 50 tasks per arm are used only when all requests were attempted. Native N48I model/price/unknown checks remain decisive. |
| Safe read-only input/new output | File, parent-link/reparse and bounded-read checks, strict JSON, source/binary rechecks and a new output directory are enforced. Original input is not altered. Output manifest is written last. This is not a hostile concurrent-filesystem or arbitrary-executable sandbox. |
| Report readback independent of saved hashes | Verify recalculates all outputs from the original source/rates/trusted executable; rehashing a wrong amount or false scope in the saved bundle is rejected. Prompt/answer/endpoint text is not exported; metadata and hashes are not automatic anonymity. |
| Real pipeline rather than only mocks | New tests use actual native accounting. In each qualified mode a real numeric-loopback HTTP server executes 100 requests through unchanged N47S, followed by export and verify. A separate local 520-command Qbrain engine run generates 50 fresh synthetic tasks before another 100-request loopback pipeline and independent offline scoring. These are not real model answers or a signed-in client. |

## Separate post-implementation review

A separate stdlib-only black-box review imports neither bridge/test fixtures nor
their reference functions. It executes 26 actual bridge CLI probes against saved
synthetic evidence, including paired receipt/run mutations, recomputed response
hashes with duplicate JSON or contradictory cache counts, duplicate cross-arm IDs,
partial coverage at attempts 1/2/49/50/99/100, missing rates/cache and a rehashed
incorrect output bundle. It passed against the local native executable and again
against the original downloaded Linux CI source/executable. The full inputs,
outputs, exits and script identity are preserved outside the repository in the
source/evidence package; compact indices identify those exact original records.

No additional blocking implementation defect was found in the exercised contract.
This is a scoped engineering conclusion, not proof of absence of all defects.
The primary remaining limitations are intentional: unsigned caller/receipt source
metadata, a bounded strict Chat subset, main-only rather than whole-pipeline cost,
no hard-crash recovery, and no independent authentication of a supplied executable.

## Interrupted local operations are not passing evidence

A local attempt to run the unchanged full native qualification driver hit the
container execution time limit while building the retained stream tests. It has
14 recorded steps, 13 completed, and no successful final driver record. It is not
reported as a successful local 55-step regression. The original partial driver
and compilation logs remain unchanged; completed native CI is the qualification.

Two offline optimized artifact-readback wrappers (one per artifact) hit tool time
limits after six successful accounting replays, while beginning lifecycle replay.
Both empty interrupted logs and partial lists are retained. Each remaining set
of three lifecycle replays was executed separately and passed, without altering
original artifacts, checker flags or product timeouts. No CI retry or weakened
assertion was requested. No root cause beyond the observed tool interruptions is
claimed.

## Fixed-source native qualification and final verdict

**PASS for the bounded N48J source module at the qualified candidate.**

N48J workflow 36216040990 completed both Windows and Linux jobs on attempt 1.
The separate retained N47S run 36216058802 also completed both jobs. The two N48J
original archives passed size/SHA256/CRC checks, and each source archive matched
all 1,403 candidate files. Windows differed only by exact CRLF conversion in
1,388 files. Script and native identities were kept platform-specific.

| Executed gate | Result |
| --- | --- |
| New bridge suite | Each OS and each Python mode: 27 tests pass, zero skips. |
| Original acceptance tools | Each OS and each mode: 48 tests pass, zero skips. |
| Real loopback in the new suite | Each OS/mode executes 100 actual HTTP requests, then native export and verify; all remain labeled LOOPBACK_TEST. |
| Retained native suite | Both unchanged 55-step drivers pass; Windows original 60 registered groups verified, Linux original six core CTests pass. |
| Original accounting/lifecycle/MCP evidence | 24 accounting, 12 lifecycle and two MCP report sets re-read with the original checkers and corruption tests. Full driver order and log hashes checked; nested driver counts and log hashes checked. |
| Bridge cross-platform replay | Four saved analysis/comparison-input pairs recomputed byte-for-byte; source manifests match apart from the explicitly different native binary hash when using Linux for Windows data. Original binary and bundle hashes separately verified. |
| Separate black-box review | 26 actual CLI probes pass locally, then another 26 on the downloaded Linux CI source and native program. |
| Independent engine composition | 520 real Qbrain commands produce 50 synthetic tasks; 100 HTTP loopback requests, separate offline scoring and new cost export/verify pass. |

The qualified Linux native executable has SHA256
`6610eb3803bf8ed59ff14d87e50d9499b2eed8ca9c95c65807bc71a412e178fa`;
the Windows executable has SHA256
`ce7d662a3241b729a14c9190e21292b550866f31260f8a24219843722be69592`.
The application source is unchanged; no new ASan run or native product change is
claimed for this Python bridge. Original native qualification is retained.

Detailed identities and counts are in [RESULT.json](n48j-evidence/RESULT.json).
The original CI archives expire on 2026-10-10; the separate deliverable preserves
them and the full local raw proof records. Counts are test executions, not claims
about distinct real-world customers or independent model-quality scenarios.

Only documentation, history copies, the already exercised synthetic price example
and executed evidence indices may be added after this candidate. Final tree checks
must show unchanged bridge/test/workflow bytes. Actual merge identity is recorded
in PR #51 and the delivery record, not invented in the frozen earlier test output.

## Evidence interpretation and release boundary

Local native replay for Windows artifacts can check saved EXE identities and
recompute semantic results with the Linux program, but cannot execute a Windows
binary here. Actual Windows export/verify is exercised on the Windows CI runner.
The independent cross-platform replay must compare analysis and comparison-input
bytes, source manifests excluding only the explicitly different native binary
hash, and the original bundle manifests; it is not relabeled as native Windows
execution. All source/tool/binary identities remain separately recorded.

The old N47S PR regression is additional evidence, not another downloaded set of
artifacts: its Windows engine step ran; the engine step on Linux was skipped by
that original workflow's platform condition. New N48J qualification must stand
on its own actual two-platform outputs.

Public N47X release assets are not changed. Real provider usage/quality, later-session
client memory consumption, full pipeline costs, PG parity, signing, new installer
acceptance and the unresolved Issue40 startup-timeout cause remain open. No real
user sessions, secrets or paid providers are used by this work.
