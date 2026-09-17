# N47L final evidence-document review

**Verdict: PASS_SCOPED for the final documented claims and their evidence bindings.**
Reviewer: `/root/recall_interface_review`, a separate actual engineering subagent.
Review date: 2026-09-17. No unresolved P0/P1/P2 documentation or evidence-claim
finding was identified in this review. This is an owner-authorized engineering
review, not third-party certification.

The reviewed product remains `17e9a435f94e45b3ca22d3da062ba4683c135c4b`, tree
`f9d42819772df53dd8c6337c3cb19c8940d7023a`, against baseline
`d033bdb23ae483a9bc68893ce1bb32c77d76fb28`. This final pass inspected the prepared
documentation before its documentation-only commit. It did not change or retest
production code, execute Windows, query live GitHub, publish a release, or repeat
the entire offline verifier.

The following identities were calculated from the actual final file bytes:

| Evidence file | SHA-256 |
| --- | --- |
| [SUMMARY.json](SUMMARY.json) | `771de3746760513abffd7bc0c94543c13678629e54d4cd4b9c84c6dcec6f963d` |
| [CI-METADATA.json](CI-METADATA.json) | `e3d4ebcf21131b6cfa891b0af2c3a72f10343986a142f2de5cd8a9f95b0832df` |
| [READBACK.json](READBACK.json) | `016bdd09c7c51d45c067e4e725438a3fe1f0b481da572062910e40639473e2c0` |
| [verify_candidate.py](verify_candidate.py) | `5a8f793b4f0054d55ffff0a134b013c770f3c686974c47dd46d57fd951ee80c6` |
| [n47l-publish-template.yml](n47l-publish-template.yml) | `aad1e079a252ce58dff3decebf95f040c46979530da75af3c9236d73cd7e651a` |

I cross-checked the outcome review, plan status, capability delta and ledger
against the final summary, CI audit, metadata/readback records and my actual
earlier interface execution. Repository/source/tree/run identities, artifact
IDs and the summary's readback values agree. The seven locally downloaded outer
CI archives were independently rehashed in this final pass: all seven sizes and
SHA-256 values match the fixed metadata. This is a local byte check; live
metadata authentication remains the separate CI review's work.

The native claims accurately reflect the archived evidence: N44 `35228307025`
and N42 `35228306922` are completed/successful, attempt 1, for the fixed product.
Each readback registry lists 60 groups. All required jobs succeeded; the two
named N44 publication jobs are explicitly skipped. Windows, portable and
sanitizer N47L reports each show 16 scenarios/258 assertions and 112 checks/126
commands. Server 2022 is correctly limited to HTTP and unit coverage, including
16/258; no full process-suite run is asserted for that platform.

The readback contains 1,094 distinct check records, 883 source files and 73
package manifest members. The summary and CI audit agree on the original inner
ZIP (2,114,341 bytes, SHA-256
`ed44a43d79e1e76efa768e74872223cd5d867dfb92881fe67aab129789cd4408`)
and packaged production EXE (4,068,864 bytes, SHA-256
`0bf0a19edcc672b750790016ed0979e001529a46d91def8f7d8b9bdffd8aae69`).
The coordinator's repeated verifier execution is attributed to that executor;
this review does not imply a third full verifier run. The repaired-candidate
14-test log says `Ran 14 tests ... OK`; its archived output, test script,
verifier and metadata hashes match `verifier-tests-provenance.json`. The earlier
historical-fixture run is separate, and the documents correctly avoid claiming
28 distinct test methods.

My interface evidence is represented without inflated counts: the fixed binary
passed 170 differential assertions and 63 boundary assertions (11 brain/argument
plus 52 MCP checks), and I independently ran the final 112/126 process suite.
The original binary's 23 failed differential assertions are correctly divided
into five assertions exposing the single new `--match` issue (two baseline-byte
comparisons and three mode cases) and 18 exposing preexisting aliases. Both
initial P2 findings remain visible: the CLI defect and the process-evidence gate
defect. Historical execution/source bindings are preserved.

The separate `report_gate_review` subagent rechecked its own final claims in this
pass: 881 rejected mutations are 630 + 125 + 126, with the original three
malformed histories counted separately; 20 final report tests are not conflated
with those mutations. The original 81-command argv/order/expected-exit schedule
and first 61 check names/order are retained, with an explicit statement that this
does not mean all old product responses were compared byte for byte. The 881
sweep's surviving report and probe remain labeled post-run transcriptions of an
inline execution, not contemporaneous raw logs or a new execution. Historical
subreview language leaving native/package review pending is superseded by the
final outcome and CI audit, without retroactively claiming native execution by
that subreviewer.

I checked local Markdown targets in the 11 final Markdown files then present:
all 33 relative targets existed. These were local-target checks, not external
URL requests. The publication-control section matches its separate review's
scope and evidence: a closed P2, 11 offline state cases against both versions,
and separately attributed author checks. Its placeholders still require factual
binding and an independent final-pin check; actual publication is not claimed.

The preserved limits are material and accurate: Linux execution is distinguished
from native CI; historical storage execution is bound through unchanged relevant
source; probe EXEs are not separately downloaded; PostgreSQL integration remains
`SKIP-PG`; signing, a new live host/model session and whole-project completion
are not claimed. Memory/context/search parser defects remain explicit unchanged
next-stage work. The documented remote publication race and successful-PATCH /
lost-response state are not described as atomic or automatically reversible.

This verdict approves the accuracy of the reviewed final documentation within
those boundaries. It does not replace the final concrete publication-pin check
or an actual release receipt.
