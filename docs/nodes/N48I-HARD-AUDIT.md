# N48I outcome review — paired task cost comparison

2026-09-25. Auditor: ChatGPT, owner-authorized separate coordinator engineering
self-review after implementation. The current owner explicitly asked me to conduct
this review myself. This is not Claude Code, a separate subagent or third-party
certification; historical review rules/outcomes remain unchanged.

## Candidate and implementation boundary

Base main `b2ae3380e96de13256094166bda7015778418e96`, tree
`6158b2728b315811094867a9a50d6d91d956377d`. Implementation candidate
`3880dde71190b15af7f9b4831ecfc02a6e433fef`, tree
`efcaae2f25bd55fa611a7491a284f5551ff55172`. This nine-path change contains two plan
records, one pure accounting header, three precise main.cpp route/help edits,
standalone direct tests, an independent process oracle, a qualification driver
and a dedicated workflow. Local staged source and remote Git tree matched before
qualification. No divergent branch or old patch was overwritten.

N48I implements native offline `cost compare`. Existing N48F/G/H accounting and
normalization sources, original tests/workflows and the PowerShell bridge retain
base bytes. No database migration, MCP operation/registry count, key/environment
read, provider request, storage write, permissions or timeout change is added.
The CLI dispatch precedes ordinary brain initialization. Python is an optional
test/evaluation dependency, not a required runtime service.

## Review against the approved plan

| Plan gate | Implementation and executed evidence |
| --- | --- |
| Bound both arms to common tasks/conditions | Exact root/arm/task fields, lowercase digest format, task-set/digest/conditions/currency agreement and distinct labels. Invalid/missing/duplicate bindings are atomically rejected; no report of a smaller silently selected subset. |
| Every submitted call assigned once | Task or shared ownership map rejects absent, duplicate and unassigned references; every task needs main, shared main is forbidden. New direct tests, generated multi-task cases and independent cross-task reuse probes exercise this. All submitted failures and retries remain billed. |
| Recompute rather than trust totals | The unchanged N48F report recomputes each full ledger and each disjoint subset. Full independent Fraction output comparisons cover every component, aggregate, task, stage, shared total, metadata and canonical hash. A separate three-command N48H -> N48I composition test preserves imported cost_input unchanged and obtains identical recomputed per-arm reports. |
| Withhold misleading differences | Either coverage declaration false, any unknown cost component, unknown/multiple/different primary model, or different/multiple primary schedules withholds every difference. An independent two-task probe confirms that a complete first task gets no delta when only the second is incomplete. Known zero usage and unknown usage remain distinct, including zero prices. |
| Exact signed delta/ratio | Nonnegative uint64 magnitudes are subtracted in the safe direction and rendered with an explicit sign. No signed cast, floating-point price or multiplication by 100. std::gcd reduces the exact ratio; zero baseline has null ratio. Additional probes reach exactly 2^64-1 scaled units, both signs of the next-lower difference, maximal ratio denominator and one-unit overflow rejection. |
| Bounds and deterministic outputs | 1 MiB raw input/depth32, 256 KiB serialized ledger, 64 cards/512 calls/128 tasks per arm, 8 MiB output. Tests exercise the maximum manifest, root exact/over limit, malformed exact/over ledger boundary, invalid UTF-8/duplicate keys/nonfinite/bool/float quantities. Full array permutations preserve canonical results; changing ownership changes the binding hash. The final output cap is statically enforced; it is not falsely described as an independently saturated 8 MiB valid fixture. |
| Native integration and regression | New direct/process tests plus the unmodified cost/import/stream/lifecycle/MCP/application contracts are driven by 55 stop-on-failure steps. Windows must use actual native CI and exact source artifacts; the separate local Linux evidence cannot replace it. Details below. |
| Documentation and operational limits | Chinese usage, six executed synthetic examples, caller-declaration limitations, no quality-preserving savings certification and old-release boundaries are documented. No automatic N47S run.json adapter or paid execution is claimed. |

## Findings, corrections and residual risks

An initial local direct-test compile failed because the test used an unqualified
`accounting::report` name. It was corrected to `qbrain::accounting::report` before
the candidate; the original failing log is retained. This was a test compilation
error, not a discovered billing vulnerability. No test assertion or product bound
was weakened. The later completed builds and tests are the reported passes.

Separate static and black-box review found no additional blocking product defect
within this bounded contract. This does not prove universal correctness or certify
maliciously fabricated input ledgers. In particular:

- The task/conditions digests and ledger_complete flag are caller statements. They
  are compared, not authenticated. Omitting the same task from both manifests or
  omitting an unsubmitted call cannot be detected without external observation.
- Declared provider/model/rate agreement cannot verify the provider actually used
  that model, settings or price. Reusing renamed responses is not authenticated
  deduplication. Call IDs intentionally have separate namespaces between arms.
- Cost eligibility is not task-success or quality equivalence. Failed main calls
  may be cheaper and remain in costs; quality_verified is always false. Actual
  quality and failure/answer denominators require the separate evaluation workflow.
- Primary schedules are conservatively required to match even for unused nonzero
  price components; auxiliary models/prices can differ and all submitted costs
  remain included. Shared costs are separate from per-task rows, but included in
  the overall difference. Users must not select only favorable task rows.
- Bounded processing is not a hard wall-clock guarantee. There is no new OS sandbox,
  invoice/tax/fee/exchange-rate coverage, DLP or automatic capture claim.

There is no known unresolved P0/P1/P2 defect in the reviewed source scope. The
external validation boundaries above are limitations, not tests that were run.

## Actual local execution

Fresh complete Linux product SHA256:
`404360c944c80f481a51f3145839c5f1ce95af1774d2825d567cedef85db13f2`.
Independent process script LF SHA256:
`f6f3d2608eb92370ddccea19ef060a28959a36f376c85c6ea647d1d30ff9ed76`.

| Executed local gate | Result |
| --- | --- |
| New C++ direct tests | 144 checks pass. |
| Independent Fraction CLI oracle | Ordinary Python and -O each 288 calls pass: 197 valid inputs (including deliberately ineligible reports), 91 rejected inputs. Each full report is compared, not just its final total. |
| Evidence checker negative variants | All 20 corrupted variants rejected in each completed mode, including recomputed hashes with wrong amounts/ratios, Boolean aliases and duplicate JSON. |
| Whole qualification driver | All 55 steps completed with exit0; original cost149, provider231, stream187, independent543/history711 per-mode gates retained, plus direct and lifecycle/MCP/application checks. |
| Original portable core | Six registered CTests pass. |
| Clang ASan/UBSan | 144 checks pass; captured diagnostic stderr empty. |
| Separate post-implementation probes | 65 calls/292 checks pass; another six ledger-limit/cross-task/quantity probes pass. These are distinct review scripts, not a reuse of the main oracle. |
| Composition and examples | Three actual import/import/compare calls pass; six synthetic examples pass with expected exits/amounts. Windows shell snippets are usage instructions, not claimed executed on the owner's machine. |

All process calls use synthetic data and isolated temporary home locations; raw
stdin/stdout/stderr and source/binary identities are retained. Such declarations
and local sentinels are not independently authenticated network egress telemetry.

## Fixed-candidate Windows/Linux qualification

Both fixed-candidate N48I native jobs completed successfully on attempt1 in run
`36140168439` (Windows job `108087765380`, portable job `108087765736`). The retained
N48D PR run `36140207308` also completed successfully on both platforms, attempt1
(jobs `108087906296`, `108087906757`). These additional N48D job results were read;
their separate archives are not claimed downloaded here.

The two N48I original archives were downloaded and matched against GitHub size and
SHA256 metadata, CRC-checked, and their source.txt/source.zip identities verified.
Each has exactly 1,379 source files matching the qualified Git tree. Linux matches
raw bytes; Windows has 1,364 files differing by exact LF-to-CRLF conversion only.
Windows checks use its archived CRLF script bytes, not the local LF script hash.

| Fixed-source native/readback gate | Actual result |
| --- | --- |
| N48I direct tests | Each platform 144 checks pass. |
| N48I full-program oracle | Each platform and each Python mode 288 calls pass (197 valid, 91 rejected); all 20 report mutations rejected. |
| Existing accounting/import/stream | Each platform retains the original per-mode 149/231/187 checks and 543/711 independent cases, unchanged. |
| Qualification driver | Both original driver.json files have exactly 55 ordered successful steps and matching log hashes. Original Windows60 registration/log is verified; portable six core tests pass. |
| Lifecycle/application/MCP | Lifecycle16 steps, retained14 suites/18 steps and MCP172 checks remain successful; nested step order, binary/log hashes and all six lifecycle reports per OS are re-read. |
| Independent artifact replay | 12 accounting report sets + six lifecycle reports + one MCP report per OS; all 38 readback commands across the two artifacts exit0. Their original corruption tests remain enabled. |

Qualified Linux binary SHA256:
`6610eb3803bf8ed59ff14d87e50d9499b2eed8ca9c95c65807bc71a412e178fa`.
Qualified Windows binary SHA256:
`447dff451173dcdd75b0aad86daddbb0f5465ddc48dc701a6ba0685042d70c87`.
The local build is a different binary and is not relabeled as either CI artifact.
The downloaded Linux direct executable and all 65 separate black-box review calls
were additionally rerun locally and passed. Windows executables were not executed
on Linux or on the owner's PC. No rerun, timeout increase or skipped assertion was
used to turn a failed CI job into success. Compiler warning-free status is not claimed.

Raw records, artifact summaries and exact file identities are retained in the
separate delivery package; compact repository records are under n48i-evidence/.
GitHub's original artifacts expire on 2026-10-09. No new provider traffic or genuine
quality experiment is inferred from synthetic CI or from consistent hashes.

## Final disposition

**PASS for the bounded N48I paired-cost source module at the qualified commit.**
The approved implementation, fixed-source native evidence, strict report replay,
separate probes and operational documentation have no known unresolved blocking
finding in the reviewed scope. This is a completed source module, not a guarantee
of zero defects or a statement that the whole Qbrain project is complete.

The eventual documentation closure must add only reviewed documentation, historical
snapshots, synthetic examples and already executed review materials after fixed
source qualification. No product/test/workflow modification may inherit the old
candidate's results. Actual merge identity belongs in PR #50/delivery record, not
in a frozen earlier test report.

Public N47X assets are unchanged. Real logged-in client later-session memory
consumption, representative model quality/cost evaluation, PG parity, signing,
new installer qualification and Issue40's unresolved startup timeout remain open.
