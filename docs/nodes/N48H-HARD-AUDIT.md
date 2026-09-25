# N48H separate outcome review — integrated complete-stream accounting

2026-09-25. Reviewer: ChatGPT, owner-authorized separate coordinator engineering
self-review after implementation and execution. The current owner explicitly
requested this review mode; it is not an independent subagent, Claude Code review,
third-party certification or a guarantee of zero defects. Historical instructions
and earlier review outcomes are not silently rewritten.

## Candidate and exact scope

Acceptance candidate: `0227db92efa736075086ae222e8fbb6ad82d41f5`, source tree
`9b95184ae32a2ca0b9512820da56e2bd7e951737`. Parent repaired implementation:
`817d222a727bfe190f6ea0ee66d08eb61a0624b4`, tree
`0481139c8c17372af126e24a004dd15a0045cd7b`. Main before this module is
`9c61049d29d9638b0b9558243025cb92a6d7e54d` (N48G). PR #49 records actual merge
state; a source review verdict is not a statement that a release was published.

The prior chat's divergent local repair was not force-pushed over the remote
parent. The remote product header and its 47-check original direct test, 543-case
independent review, original stream/provider/cost checkers and original N48H CI
workflow remain byte-identical to 817d222a. The integrated commit changes exactly
five paths: the supplementary 711-case script, its separate 47-check C++ source,
standalone CMake registration, a separate native CI workflow and the integration
plan note. No product behavior changes in this integration commit.

The result is the bounded native `cost import-stream` module: complete saved
Chat/Responses/Anthropic SSE -> mutually exclusive token counts -> unchanged
N48G/N48F exact costing. It is not live collection, a generic EventSource client,
complete text/tool reconstruction or an authenticated invoice pipeline.

## Actual defects and review disposition

| Finding | Evidence and disposition |
| --- | --- |
| Historical total lower-bound bypass | Earlier 0a7d0385 accepted historical total 100 followed by known final components summing to 10 when final total was absent/null. Remote 817d222a repairs the reverse bound; original and supplementary suites retain regressions. The prior local repair and remote repair are distinguished, not merged by overwriting. |
| Historical cache aggregate bypass | Earlier 0a7d0385 accepted a complete current cache-TTL partition below a historical aggregate after a null reset. Remote 817d222a validates merged current usage and keeps numeric history as a bound. It does not fill unknown values with history. |
| Supplementary checker Boolean alias | Intake of the previous 711-case script reproduced acceptance of False replacing zero in normalized tokens. This was the checker `evaluate` path, not a new product defect. Type-preserving JSON equality and exact integer checks now reject it, including when output hashes are recalculated. |
| Supplementary checker duplicate JSON | The inherited decoder accepted a duplicate top-level key using last-value-wins parsing. Strict unique-key decoding at every object depth and nonfinite-number rejection now fail the same captured output. The inherited source hash and both before-inputs are retained. |

The supplementary checker source before repair was
`3a12bbd02254f80eef146a9ff36fd6010ddee6369b207e5f95ca8ce2f278d2eb`.
Integrated LF source SHA256 is
`cfc643130c3288803e97cc34a2b0bb9a878834bcadd0d6d0d5847eccfe3d7803`.
Windows archives use their own actual CRLF script bytes for identity verification.
The deterministic 711-case generator functions have unchanged ASTs relative to
the prior delivery. No test was relaxed to erase an earlier failure.

## Review against the approved N48H plan

| Plan requirement | Verification and limitation |
| --- | --- |
| SSE framing and bounds | Original direct and 187-check process contracts exercise CR/LF/CRLF, BOM, comments, multiline data, unterminated input, UTF-8/NUL, duplicate keys and byte/event/record limits. Additional evidence mutations test the verifier separately; they are not counted as parser tests. |
| Chat final usage | Choice identity/finish state, one optional final usage tail and [DONE] are retained; original process contracts and supplementary missing/null/known partitions check final-only accounting. |
| Responses identity/order/final snapshot | Existing validated amendment permits origin 0 or 1, then strict continuity, rather than arbitrary resumed fragments. This differs explicitly from the original plan's initial “from0” wording and is not a new relaxation in this integration. Three terminal statuses, unknown final values and historical aggregate bounds are exercised. |
| Anthropic cumulative counters | Sparse deltas merge, numeric updates replace rather than add, explicit null clears current values, and historical bounds survive. Initial output alone is not final. Original 543 and supplementary 711 generators cover these cases independently. |
| Precise costing, unknowns and atomicity | Original N48F/G files and gates are unchanged. Independent Fraction checks verify components and every subtotal/total. Unknown remains unknown; failed attempts with usage remain billable; either order of a bad/good batch yields only the structured error. |
| Native integration and original regressions | Fixed-source native jobs, their raw artifacts and exact source identities must all pass before the verdict below becomes accepting. Windows is verified from actual Windows jobs, not Linux emulation or an old EXE. |

Static review also checked the early CLI dispatch before brain initialization,
checked integer additions, output bounds, existing response/call deduplication and
absence of new permission, timeout, network or storage code. The new workflow uses
read-only contents permission and a fresh complete native product on each OS;
original qualification steps are not replaced or disabled. Python remains a test
and development dependency, not a required application service.

## Local execution and interrupted attempts

The remote parent's qualified whole Linux executable was used for local matrix
runs; the runtime source is unchanged in 0227db92. Ordinary and final optimized
runs each passed 711 cases (641 valid, 70 contradictory). The same hardened script
also rejected all 22 evidence mutations per mode. A local Clang build ran both
native suites, 47 + 47 checks; separate AddressSanitizer/UndefinedBehaviorSanitizer
executions passed the same 94 checks with empty captured diagnostic stderr.

Two local tool invocations ended on the execution tool's time limit: an initial
optimized matrix left a partial directory without a report, and a GCC Release
build was interrupted. Neither is an acceptance run. Their partial records/logs
remain separate. The completed optimized rerun and completed Clang build have
actual zero exits. Product timeouts and assertions were not changed; this is not
a claim of warning-free compilation.

Both parent-platform original report sets were separately re-read (16 sets total)
as intake evidence, not as proof of new tests. The five documented synthetic
examples were then executed against the fresh 0227db92 Linux CI product and their
raw inputs/outputs/exit codes retained. The displayed PowerShell/cmd shell examples
were not themselves executed on the owner's Windows machine.

## Fixed-source native qualification

All three fixed-candidate workflows completed successfully on attempt 1:
original N48H `36133311806`, integrated supplement `36133311818`, and retained
N48D PR regression `36133315619` (six successful native jobs in total).
Four original N48H/supplement archives were downloaded, ZIP-checked and matched to
GitHub's size/digest metadata. Each source archive contains 1,355 files matching
the qualified tree; Windows differs only in exact CRLF conversion for 1,341 files.
The two N48D job results are checked as additional CI evidence, not claimed to be
another pair of archives independently downloaded here.

| Fixed-source gate | Result |
| --- | --- |
| Direct stream + additional history | Windows and Linux each run 47 + 47 checks successfully. |
| Supplementary independent CLI matrix | Each OS and Python mode: 711 calls, 641 valid / 70 rejected contradictions; 2,133 raw input/output/error files. All 22 evidence mutations rejected on re-read. |
| Original independent stream review | Each OS and mode: 543 calls, 444 accepted / 99 rejected. Remains a separate suite, not interchangeable with or added as disjoint cases to the 711 matrix. |
| Original stream contracts | Each OS and mode: 187 checks, 171 calls, 513 raw files; 15 report mutations rejected. |
| Existing N48G/N48F | 59 / 103 direct checks; per mode 231 / 149 process checks and both sets of 12 report mutations pass. |
| Application gates | Exact Windows original 60 registered groups verified against source and log; portable core six targets, lifecycle four direct targets / 16 driver steps, 14 retained process suites / 18 driver steps, and MCP 172 checks retained. |
| Independent artifact readback | All 20 main accounting report sets verified from exact archived scripts and binaries. Lifecycle/retained driver order, exits and output hashes matched; MCP report re-read with all 14 corruption cases rejected on each OS. |

Binary hashes are recorded separately per artifact in [RESULT.json](n48h-evidence/integration/RESULT.json).
Different Windows builds are not falsely described as the same EXE bytes. Local
Windows activity is report/source inspection only; Windows native execution took
place on the real Windows CI runners. Downloaded Linux direct binaries were also
executed locally. No missing/failed check was converted to success by a retry or
raised product timeout. The qualification archives expire on 2026-10-09; the
separate delivered evidence package retains the relevant source and raw records.


## Operational limits and final verdict

**PASS for the bounded N48H source module and this integrated candidate.**

No unresolved blocking defect was found in the reviewed implementation, test-tool
repairs and exercised fixed-source results. This does not establish universal
provider compatibility or prove absence of every defect. The module's source
acceptance is complete; actual merge identity is recorded by PR #49 and the
closing delivery record, not fabricated inside an earlier frozen test report.


Chat's optional tail usage and interruption caveat, and Anthropic cumulative delta
usage, were rechecked against current primary documentation on 2026-09-25:
https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events
https://developers.openai.com/api/reference/resources/responses/streaming-events
https://platform.claude.com/docs/en/build-with-claude/streaming

The implementation deliberately supports an explicit subset. Newly added provider
fields/event types, audio, fallback and advanced billing formats are not silently
accepted. Caller IDs, outcome labels and rate applicability are not authenticated;
hashes and self-declared zero provider calls do not prove network egress or invoice
origin. Strict readback detects the exercised inconsistencies, not adversarial
replacement of every executable, verifier and record together.

No private brain, actual user session, API key or paid model was used. There is no
Release/tag replacement, signing or complete gbrain/PG parity claim. Public N47X
still lacks the later source modules. Real later-session memory consumption,
representative model quality/usage/cost comparison, integrated release acceptance,
Issue #40's unresolved startup timeout cause, PG parity and signing remain open.
Closing changes must contain only documentation, synthetic examples and already
executed review evidence; compare the final tree before any merge. A newly
triggered additional run must not be predeclared successful.
