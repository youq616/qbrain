# N48L outcome review — paired quality and scheduled-main costs

2026-09-27. Reviewer: ChatGPT, owner-authorized separate engineering self-review
after implementation. This is not a third-party, Claude Code or subagent review.

## Source identities and attribution

Base main: 89a4e1c88341409fe726a82cdd5779af52ded5ef (N48K).
Inherited implementation: d79181be96d4cfb3db74ec01048562e6db06e177,
tree c07e715eaaa2af0b4602420b3942d8ae2fbaf41a.
This continuation's independent reviewer and native workflow:
7e5d4ddc407c6656b64e06f8c475881313dc2efb,
tree 352dc9dea6dd6a412af95d933b2b131da66665fd.

PR53 was already open on intake. Its core implementation and initial passing CI
are inherited work, not newly authored in this turn. The continuation adds three
files: independent stdlib-only reviewer, native supplemental workflow and its
plan. All inherited tools, scorers, native code and qualification tests/workflows
remain byte-identical. Local Git mirrors have matching trees, not recreated
upstream commit metadata. The immutable N48K ZIP is not rebuilt or replaced.

## Approved contract and findings

| Gate | Evidence and review |
| --- | --- |
| One source for quality and costs | Scores use N48J-validated in-memory response bytes. Its later cost source manifest must equal the scoring snapshot; final source/key/rate/binary rechecks remain. Original mutation tests reject crossed source manifests and changed keys. |
| Distinguish grounding from solution | Preserve original 50-task packet-grounded semantics and separate 25-task answerable resolution. No-context correct abstention can be 50/50 grounded and 0/25 resolved. Missing/failed answers remain in denominators. Independent oracle reconstructs every result from response state/value/evidence sets. |
| Never cancel per-task regression with gains | Every applicable case/dimension must be non-regressing for dominance. The original 48 Boolean/cost subcases and aggregate-tie counterexample are retained. New review exercises a regression separately at all 50 task positions, plus incorrect conflict values/evidence and order-invariant sets. |
| Exact costs and ratios | Pricing delegates to unchanged N48J/native N48G/F/I. Independent Fraction sums check original cache buckets, total change and cost per resolved task. A zero resolved denominator gives null; incomplete or unknown costs withhold joint conclusions. |
| Bounded offline/read-only behavior | No paid executor, answer-key forwarding, brain access or installation is introduced. Existing strict path/file/JSON/size and no-overwrite helpers are reused. Export manifest is last; verify recalculates exact outputs instead of trusting mutable hashes. |
| Honest interpretation | Dominance is descriptive on the observed structured-task dimensions and main-request costs only. It is not statistical noninferiority, free-text quality, total-pipeline savings, authentic provider telemetry or live client memory consumption. Even two equally unsuccessful systems can have a relative cost dominance; users must inspect absolute solution rates. |

No blocking product defect was found in the reviewed contract. The additional
work improves independent coverage; it is not a claimed repair of a demonstrated
product scoring defect. Original tests and expected results were not weakened.

## Actual native qualification and raw-artifact review

Original N48L run 36239071944 succeeded on Windows (job108396078616) and Linux
(job108396078764). Its original archives10905815734/10905263046 were downloaded,
checked against external SHA256 and CRC, and matched to the exact 1,434-file
source tree. Windows has only 1,419 exact LF-to-CRLF transformations.

Each OS/mode passes 28 N48L tests (including 48 Boolean/cost subcases), 27 N48J
tests and 48 retained acceptance tests, without skips. The joint suite performs
100 real numeric-loopback HTTP requests through the original N47S executor into
actual native accounting and export/verify. The responder explicitly supplies
synthetic reference answers; this is not independent model inference.

Both original 55-step native/application drivers completed with exit0 and every
recorded log hash was rechecked. Windows original60 registration/log agreement
was independently verified. All24 original accounting report sets were re-read
using each platform's exact archived scripts and binary identity, with existing
negative mutations enabled. Four joint report bundles were recomputed: evaluation,
quality scores, costs and comparison-input bytes match exactly. Provenance matches
apart from the explicitly substituted Linux binary digest for Windows-data replay;
original Windows binary and bundle manifest digests are separately checked.
This local replay is not execution of a Windows EXE.

Supplement run36305969704 succeeded on both platforms: jobs108582590365 and
108582590502. It reuses the two immutable original qualified binaries, verifies
all original source files, and executes the new independent reviewer in both
Python modes. The reviewer imports no product/scorer/fixture/reference code.
Each OS/mode completes all68 scenarios without sharding: 50 single-position
regressions, 12 other quality/cost scenarios and six failed-run coverage positions.
All four raw supplemental groups were re-read: 272 saved runs, complete original
response-derived paired outcomes, exact ratios, actual stdout/stderr, provenance
bindings and bundle manifests match. Supplemental archives have 1,437 source files;
Windows has only 1,422 exact CRLF conversions. Same binaries as original CI.

Local ordinary/optimized reviewer execution also completed all68 scenarios per
mode in four explicit17-case shards. A separate reconciliation verifies zero
exits, exact script hashes, unique complete inventory and raw output digests.
Two controlled reviewer-mutation runs (ordinary and optimized) reject12 variants
each: erased/changed case, bool-as-count, wrong denominator/solution count/ratio,
wrong dominance, changed source/key binding, overstated scope, bad cost and duplicate
JSON, including updated bundle hashes. This checks the reader, not authenticity
against a colluding source/executable/report producer.

## Retained local failures and limits

The first local reviewer used lazily captured generator variables for dimensions,
producing a TypeError on the first valid fixture. It was fixed by materializing
each tuple immediately; the failed script, stdout and traceback are retained.
This is a new test-tool implementation error, not a discovered product bug.

Two subsequent unsharded local invocations hit the execution-tool limit after
38 recorded zero-exit calls each. Neither is counted as a full pass. Final explicit
shards completed all cases, and both native CI jobs independently ran unsharded
matrices to completion. Product timeouts and assertions were never changed.
An unavailable streaming execution facility was also not treated as execution.
No new native product modification or sanitizer run is claimed for this Python
module. Existing fixed-source native tests provide the retained runtime evidence.

The published Chinese guide and examples are documentation, not a statement that
the owner's PC or its PowerShell commands were executed. Original native CI runs
on hosted Windows/Linux. Snapshot rechecks are not a hostile concurrent-filesystem
sandbox; caller-supplied answer keys and model/rate provenance remain unauthenticated.

## Outcome

**PASS for the bounded N48L joint-quality/main-request-cost source module.**
No known unresolved blocking finding remains in the implementation and exercised
results. This is not an absolute zero-defect guarantee or completion of Qbrain.
Only documentation, historical snapshots and executed result indices may be added
after qualified7e5d4ddc. Actual merge identity belongs to PR53/delivery record.

The N48K Windows ZIP remains unchanged and does not automatically acquire this
new Python tool. The separate evaluator toolkit may include the original qualified
Windows native executable and exact archived Python bytes, with a clearly labeled
synthetic demo, but is not a new signed installer or replacement N48K release.
Real client later-session consumption, representative real-model experiments,
full-pipeline costs, PG parity, signing, stable acceptance and Issue40 remain open.
