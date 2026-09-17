# N47L outcome review — explicit multi-term fact recall

Status: **PASS_SCOPED — implementation and evidence gates complete**. The
repaired product meets this node’s approved acceptance criteria after actual
independent subagent review, completed current native CI and exact artifact
readback. No unresolved P0/P1/P2 finding remains in the reviewed node scope.
Merge may proceed; publication is limited to the verified original CI bytes
after the separately reviewed final publication pins are bound and checked.

Coordinator: ChatGPT. Actual independent reviewers:
`/root/recall_storage_review`, `/root/recall_interface_review` (including its
`report_gate_review` subagent), and `/root/ci_handoff_audit` for CI provenance.
These are real separate engineering agents, not third-party/Claude Code review.

Baseline: `d033bdb23ae483a9bc68893ce1bb32c77d76fb28`.
Repaired product: `17e9a435f94e45b3ca22d3da062ba4683c135c4b`.
Source tree: `f9d42819772df53dd8c6337c3cb19c8940d7023a`.
Current required runs: N44 `35228307025`, N42 `35228306922`.

## Findings that required repair

The original `1118e0fa` candidate passed its existing CI but failed independent
review. Its complete original CI identity and the two P2 findings are retained in
[INITIAL-CANDIDATE.json](n47l-evidence/INITIAL-CANDIDATE.json).

1. A literal `--match` query was scanned again as an option. For example,
   `fact recall --query --match --brain probe` failed with `fact_invalid_match`,
   while the independently built baseline returned a normal literal response.
   `cmd_fact` now stores its strictly parsed values once, reads every fact field
   from those values, and passes only the actual brain option to brain selection.
   This also repairs older aliases involving literal `--source`/`--brain` text.
2. The process report accepted repeated/replaced command histories because only
   command count and self-reported exit expectations were checked. It now checks
   a fixed semantic schedule, complete argv and decoded stdin, consistent dynamic
   IDs and validator-owned expected exits. The new validator dependency is also
   included in the development package and tested outside the repository layout.

The preserved original binary is rejected by the new process test at command 86;
the first 61 original checks had already passed. Neither issue is hidden by
deleting or weakening the original checks. The original 81-command argv/order/expected-exit schedule and the first 61
check names/order were compared against the revised history and retained before
the 45 appended calls. This is not a byte comparison of every original command
response.

## Acceptance against the approved plan

| Requirement | Implementation and independent evidence | Status |
| --- | --- | --- |
| Explicit literal/AND/OR modes | Fixed enum selects only bound SQL predicates on one anchor; 600 independent query/mode oracle cases | Reviewed |
| Complete direct counter-evidence | Source/lifecycle/evidence checks precede complete group output; archived nonmatching counterclaims retained | Reviewed |
| Bounds and snapshot | Full-input validation, 8 terms/1024 bytes, candidate filtering, 512-evidence work limit, two real WAL connections | Reviewed |
| Default and explicit literal compatibility | Independently built baseline; 170 CLI/MCP byte/semantic checks and original Hook path retained | Reviewed |
| Fact option parsing and brain selection | 11 independent fallback/empty/duplicate/selection checks; nonempty option-shaped quote/evidence regressions | Reviewed |
| MCP error types and wrong views | 52 independent checks, fixed enum/type errors and unrelated read/write views rejected | Reviewed |
| Report schedule integrity | 20 report tests; original three substitutions plus 881 independent mutations rejected | Reviewed |
| Native compilation and 60 registered groups | N44 35228307025 and N42 35228306922 completed successfully; each exact 60-group registry matched actual logs | PASS |
| Original package and source/EXE/script identity | 7 fixed CI archives, 883 source files, all 73 manifest members and original report/EXE identities; 1094 checks, repeated independently with identical report bytes | PASS |

## Actual local and independent execution

GCC 13.3 Release built the repaired CLI and standalone targets. Current committed
source reports show 16 N47L scenarios/258 assertions and 112 real CLI/MCP checks
over 126 commands. All 18 unchanged prior process suites passed. Report-validator
tests passed 193/193 and native registry/MSVC source-object closure tests 32/32.
These are Linux engineering checks, not a claim of running Windows here.

The independent storage probe used real capture/extract/fact operations and an
independent substring oracle. Its 3415 assertions include fixture assertions and
600 generated query/mode cases. Additional probes cover 101 newer partial matches
before the candidate cap, a 528-support neighborhood exceeding the 512-evidence
limit with whole-group discard, and archive-schema creation by a second WAL
connection after the read snapshot is pinned. The storage source is unchanged
between the initial candidate and repaired product.

The independent interface reviewer built the complete baseline separately, with
no candidate libraries reused. The fixed binary passed 170 comparison checks,
11 brain/argument checks and 52 MCP checks. The original binary failed 23 of the
same 170 comparisons. Five failed assertions cover the single new `--match`
issue: two baseline byte comparisons and three mode cases. The remaining 18
cover preexisting option-alias defects repaired by the single parser. The reviewer also independently ran
the final 112/126 process suite. The report reviewer rejected all 881 mutations
(630 missing-field, 125 adjacent-order and 126 expected-exit changes), in addition
to the original three failing-integrity examples.

Reports and executable probes are archived in [n47l-evidence](n47l-evidence/).
The source-bound local reports distinguish the clean committed run from earlier
working-copy tests and copied standalone scripts whose source remains unknown.
The supplementary report-gate statement and probe transcription explicitly identify
their post-run provenance: the 881-case sweep originally ran inline and did not
create a separate raw log. The transcription is not labeled as a new execution.

## Current native CI and exact package readback

[N44 run 35228307025](https://github.com/youq616/qbrain/actions/runs/35228307025)
and [N42 run 35228306922](https://github.com/youq616/qbrain/actions/runs/35228306922)
are completed/successful for the repaired product and source tree above. Both
Windows full-regression logs match all 60 current source-registered groups.
Windows, portable and ASan/UBSan reports each contain N47L 16 scenarios/258
assertions and 112 checks/126 real CLI/MCP commands. Windows Server 2022 verifies
HTTP and unit suites, including N47L 16/258; it does not run the full process suite.
All required original Windows jobs/steps, both PowerShell versions and native
source/object closure gates are retained. Live PostgreSQL remains `SKIP-PG`.

The independent CI reviewer downloaded seven original artifacts and authenticated
their fixed metadata/digests. The offline verifier reconstructed the complete
883-file Git tree and derived the complete package inventory from the source
packaging script: all 73 manifest members, original Windows report bytes,
production EXE and source/script attachments agree. The coordinator separately
ran the same pinned verifier against an immutable candidate checkout. Both runs
completed **1094 checks** and produced byte-identical JSON reports. The CI
reviewer also reran the 14 verifier regression tests on these current candidate
artifacts; all passed. The earlier 14-test historical-fixture log remains separate,
so these are not counted as 28 different test methods.

- [CI-METADATA.json](n47l-evidence/CI-METADATA.json), SHA-256 `e3d4ebcf21131b6cfa891b0af2c3a72f10343986a142f2de5cd8a9f95b0832df`.
- [READBACK.json](n47l-evidence/READBACK.json), SHA-256 `016bdd09c7c51d45c067e4e725438a3fe1f0b481da572062910e40639473e2c0`.
- Original inner ZIP: **2,114,341 bytes**, SHA-256 `ed44a43d79e1e76efa768e74872223cd5d867dfb92881fe67aab129789cd4408`.
- Packaged production EXE: **4,068,864 bytes**, SHA-256 `0bf0a19edcc672b750790016ed0979e001529a46d91def8f7d8b9bdffd8aae69`.

The offline verifier executes no product, signs nothing and makes no publication
request. Probe executables are not separately included in the downloaded
artifacts; their identity fields are report attestations. The source/EXE/package
checks do not certify a new signed-in host or model-consumption session.

## Separate publication-control review

The candidate product is unchanged while its exact-byte delivery procedure is
reviewed separately. `/root/recall_storage_review` found and independently
reproduced a P2 in the draft publication template: a same-name/same-size asset
replacement escaped the final checks. `/root/multiterm_test_repair` repaired it;
the corrected template pins each asset's unique ID, size and SHA-256 against the
local original bytes and retains those pins through the final public check.
The independent original-tail simulation ran 11 state cases against both
versions, closing the concrete counterexample before the publication PATCH.
The implementation author separately checked 45 malformed pins, 20 asset mutations
and 3 API failure cases. These are offline synthetic tests, not actual releases.

[The full publication-control review](n47l-evidence/n47l-publication-review.md)
binds corrected template SHA-256
`aad1e079a252ce58dff3decebf95f040c46979530da75af3c9236d73cd7e651a`.
Its unresolved placeholders must be replaced with the actual reviewed commit,
merge and content pins and independently checked before installing the workflow.
The template never rebuilds or repackages the verified CI inner ZIP. Multi-request
remote publication is not atomic: a successful remote PATCH followed by a failed
response can leave a public release without a local success receipt. A failed
attempt after a possible PATCH requires read-only remote inspection, not blind
republication or a promise of automatic rollback.

## Scope and limits

No new schema, MCP tool, collection/egress permission, Hook default, installer
consent or model call is introduced. Matching uses literal substrings with ASCII case folding. Only explicit
`all_terms`/`any_terms` modes split on the four documented ASCII separators;
omitted/explicit literal retain whole-query substring semantics. This is not
Chinese segmentation, semantic inference, confidence scoring or truth adjudication.

The native and package gates above close this stage’s implementation review.
Actual release receipts are recorded separately after publication. The
[known unchanged parser issues](n47l-evidence/NEXT-STAGE.md) remain next-stage work.
PostgreSQL facts/context parity, signed delivery,
new signed-in host/model acceptance and full project completion remain outside
this stage. An engineering PASS is bounded by the reviewed scope and evidence;
it is not a guarantee that every possible defect has been eliminated.
