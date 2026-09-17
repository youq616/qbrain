# N47L independent interface and evidence review

Reviewer: real ChatGPT subagent `/root/recall_interface_review`, with a separate
report-gate subagent `/root/recall_interface_review/report_gate_review`.
This is owner-authorized independent engineering self-review, not third-party or
Claude Code review. The reviewer did not edit repository source, commit, push, or
post a GitHub comment.

Original candidate: `1118e0faf5b7acdd3f27f933c801b4a2b1278d41`.
Baseline: `d033bdb23ae483a9bc68893ce1bb32c77d76fb28`.
Final reviewed candidate: `17e9a435f94e45b3ca22d3da062ba4683c135c4b`.
Final reviewed tree: `f9d42819772df53dd8c6337c3cb19c8940d7023a`.
Both `AGENTS.md` and the approved `docs/nodes/N47L-PLAN.md` were read first.

Scope: CLI/MCP routing, literal compatibility, errors and view whitelists, help
and user documentation, process/unit evidence and CI/package report gates.
Core SQL and FactStore neighborhood implementation were assigned to another
reviewer and are outside this report's implementation verdict.

Initial verdict: **CHANGES REQUIRED**. Two P2 findings were reproduced.
Final verdict for the reviewed interface/report-gate scope: **PASS after fixes**.
Both findings are closed on the revised source hashes listed below; no additional
P0/P1/P2 issue was found. This verdict does not replace native Windows, whole-package
or storage acceptance.

## P2-1 — a literal `--match` query is reparsed as an option

Original locations: `src/qbrain/cli/commands.cpp:95-100` (`opt` scans all argv
positions) and `src/qbrain/cli/commands.cpp:457` (new mode extraction uses `opt`).

The strict validation loop skips option values, but subsequent extraction rescans
them. The new `--match` lookup therefore interprets the value of `--query` as an
option whenever the literal query is exactly `--match`.

On an initialized synthetic brain, the original candidate returns exit 1 and
`{"error":{"code":"fact_invalid_match"}}` for each of:

```text
qbrain fact recall --query --match --brain probe
qbrain fact recall --query --match --match literal --brain probe
```

The independently built baseline returns exit 0 for the first command and a
normal literal response. This is a real default-literal regression against the
approved byte-compatibility requirement, not merely missing test coverage.
The existing tests compared parsed JSON or two paths in the same new build and
did not include option-shaped literal input.

The revised implementation stores validated option values in a map, uses that
map for all `cmd_fact` fields, uses the validated flag positions for `--history`,
and forwards only the parsed `--brain` pair to `with_brain`. The fix was reviewed
before and after implementation. The global parser and other command families
remain outside this change.

Independent execution after the fix:

- 170/170 assertions passed. These include 29 valid/invalid query inputs checked
  as raw stdout bytes against the full baseline build for CLI default, CLI
  explicit literal, MCP default, and MCP explicit literal; and 9 option-shaped
  queries across all 3 modes in 2 option orders compared against MCP responses.
- The same 170-probe script on the preserved original candidate fails 23
  assertions. Five cover the single new `--match` issue: two baseline-byte
  comparisons and three query-first mode cases. The remaining 18 cover
  preexisting option-shaped-input aliasing also repaired by the single-parse
  implementation; they are not attributed to N47L.
- Another 11 assertions verified config fallback, environment-over-config,
  explicit-over-environment, empty-environment fallback, explicit empty brain
  rejection, missing mode/query, duplicate mode/brain/query, and absence of an
  unintended brain directory. Explicit empty `--brain` retains exit 2 with
  `error: invalid brain id`; no claim is made that this preexisting error is JSON.

Evidence files alongside this report:
[initial differential](recall-interface-1118-differential.json),
[fixed differential](recall-interface-fixed-differential.json), and
[initial brain-selection probe](recall-interface-fixed-brain.json).
The runnable independent probe is [recall_interface_probe.py](recall_interface_probe.py).

## P2-2 — duplicate or unidentified commands can satisfy the report gate

Locations: `.ci/validate_multiterm_report.py:28-31` and missing negative coverage
in `.ci/test_multiterm_report.py:14-18,42-49` of the original candidate.

The validator requires 81 command records and compares each record's self-reported
exit code with its self-reported expected exit code. It does not verify command
identity, order, or predeclared expected exits. It does not even require `args`.

The report-gate subagent used the official `process_fixture()`, replaced only
`commands`, and called its `vp()` helper. Each of these three reports was accepted
as `{'checks': 61, 'commands': 81}`:

```python
[{"args": ["init"], "exit_code": 0, "expected_exit": 0}] * 81
[{"exit_code": 0, "expected_exit": 0}] * 81
[{"args": ["init"], "exit_code": 1, "expected_exit": 1}] * 81
```

This is an integrity gap for incomplete/corrupted execution evidence. It does
not establish that the normal process runner omitted a command or that a product
permission was bypassed. A fixed command schedule with stable identities and
validator-owned expected exits, plus negative tests for substitutions, missing
identities, order changes and altered rejection expectations, is required to
close this finding. Existing N47K diagnostics provide a repository precedent.

The revised gate at `.ci/validate_multiterm_report.py:47-59` now checks a fixed
126-command identity and order, validator-owned expected exits, complete argv,
and parsed stdin JSON. Types are exact, dynamic IDs remain consistent across
commands, and duplicate embedded JSON keys are rejected. The original 81 commands'
argv/order/expected exits and first 61 checks remain intact. The process runner
also validates its transcript before it can emit PASS.

Independent re-review closed P2-2:

- All three original corrupted reports are rejected.
- 881 additional mutations are rejected: 630 deletions of each command's five
  required fields, 125 adjacent command swaps, and 126 joint changes to each
  command's actual/expected exit codes.
- The revised real process runner was independently executed by this reviewer:
  exit 0, 112/112 checks, 126/126 commands. The report-gate subagent independently
  accepted that real transcript with `validate_commands()`.
- Final report negative tests pass 20/20, with hashes stable before/after execution.
- The parent identified and fixed the new standalone script's validator import
  dependency in the package. The report-gate subagent verified both packaged
  members using AST inspection and ran isolated `python -I -S -B` dependency
  controls with a synthetic transcript: both files present produce exit 0/PASS;
  omitting the validator produces exit 1/FAIL/ModuleNotFoundError and preserves
  all 126 command records. This dependency test does not execute the product.
  Both outcomes correctly avoid claiming Git source identity outside a checkout.

Additional evidence: [revised process report](recall-interface-revised-process.json).
The reviewer reran the real process suite after the source repair was committed:
its exact `source_commit` is `17e9a435f94e45b3ca22d3da062ba4683c135c4b`,
`tracked_tree_clean=true`, and `native_windows=false`. This supporting portable
report must not be substituted for current native package provenance.

## Other checks and limitations

Independent real-process MCP probes passed 52 checks: mode type and enum errors,
omitted/empty mode and query distinctions, all unrelated read views including
omitted view, representative write actions with writes explicitly enabled,
NUL/byte-budget rejection, and whole-input sensitive rejection. Non-string mode
values produce tool `invalid_argument` on field `match`; invalid enum strings
produce `fact_invalid_match`; wrong read views produce
`fact_unexpected_argument`. No untrusted query content was needed in the error
payload. CLI help and the N47L Chinese guide describe explicit modes and the
documented ASCII/Unicode limits consistently with the interface.

The original MCP and brain-selection probes were saved as the runnable
[recall_interface_boundary_probe.py](recall_interface_boundary_probe.py), then
independently rerun against the frozen final candidate. All 63 assertions passed
(52 MCP and 11 brain/CLI-boundary assertions); see
[boundary report](recall-interface-boundaries.json). The earlier isolated MCP
results remain in [initial MCP error results](recall-interface-errors.json).

The report-gate subagent verified source/EXE/script/test-source binding, native
Windows requirement, package inclusion, the 60-group native registration gate,
and Windows/Server2022/portable/sanitizer wiring. Existing report negative tests
passed 11/11 and native-log tests passed 32/32 before repairs.

The baseline was independently compiled from a detached `d033bdb2` worktree with
GCC 13.3, Release, PostgreSQL disabled, and two compiler workers; no candidate
libraries were reused. The original candidate executable was preserved as
`qbrain-1118-interface-review`, SHA256
`314a244e37dc193b10f48cd7a3612344bfd77c2f25b374d2933b0904742ffb5b`.
The differential report records both actual executable hashes.

Revised executable SHA256:
`030b4b0a86431e301f3e83d0184c19d5a5ee4f0f6a11ccf024a1da2c399cfe3c`.
Independent baseline executable SHA256:
`e3d043071b3bb89faa701f14e72baaca45d206089b9e3cda721f849409df7c6d`.

Source SHA256 values verified against the final committed candidate:

| File | SHA256 |
|---|---|
| `src/qbrain/cli/commands.cpp` | `bb722e47737e071495e236fcb619498d0c40c83d9ab30759d877d28513f7c945` |
| `.ci/test_multiterm_process.py` | `5d8562bc3923794b33093d7e8509e104bbf028107e5f7356e0ffbaba012c684e` |
| `.ci/validate_multiterm_report.py` | `6198275e5a7952d886ca876c86d66193692f8dd9d535e6651c28d088df269831` |
| `.ci/test_multiterm_report.py` | `639f8fa2be2cd23a8b1e894168f35d279447d5acb7e25271fe45cadb3a1718d7` |
| `.ci/package_n44_development.py` | `5f7eb486395193164062621f0fccf71b3f6de13ba869a14b17836f7ac8b788e2` |

## Reproducing the supporting portable probes

All evidence links above are relative to this directory. Keep both independent
probe scripts and their JSON reports alongside this review when archiving it.
The stored JSON also records the original local executable paths for provenance;
those paths are historical metadata and need not exist when rerunning the probes.

Use a Linux audit environment with GCC 13.3/CMake/Ninja and Python 3. This is an
optional supporting audit environment, not a required Qbrain product runtime.
Build a `qbrain` executable from each exact baseline and final-candidate revision
in separate detached worktrees, with Release and `QBRAIN_WITH_PG=OFF`. For each
worktree the build commands are:

```sh
cmake -S . -B build/review -G Ninja -DCMAKE_BUILD_TYPE=Release -DQBRAIN_WITH_PG=OFF
cmake --build build/review --target qbrain --parallel 2
```

From this evidence directory, pass the resulting executable paths explicitly:

```sh
python3 -B recall_interface_probe.py --baseline /path/to/baseline/build/review/qbrain --candidate /path/to/final/build/review/qbrain --report repeated-interface-differential.json
python3 -B recall_interface_boundary_probe.py --binary /path/to/final/build/review/qbrain --report repeated-interface-boundaries.json
```

Expected exits are 0 with 170 and 63 passing assertions, respectively. Repeating
the first command with an executable built from original candidate `1118e0fa`
instead of the final candidate must exit 1 with the original regression visible;
the archived run reports 23 failed assertions. Exact binary hashes can differ on
a different build environment; the input commits, compiler profile, result data,
and actual executable hashes must be recorded rather than silently relabeled.

From a clean checkout of the final candidate, the source-owned runners can be
repeated as follows. The process runner and validator must stay together under
`.ci` (or together in a detached `verification` directory for source-less reruns):

```sh
python3 -B .ci/test_multiterm_process.py --binary build/review/qbrain --report /tmp/repeated-multiterm-process.json
python3 -B .ci/test_multiterm_report.py
```

Expected results for the reviewed versions are 112 checks/126 commands and
20 report tests. The additional 881 mutation sweep was executed by the separate
report-gate subagent; it is supplementary review evidence, not falsely presented
as one of the 20 source-owned tests.

All independent runtime checks here ran on Linux in isolated synthetic data
roots. They do not certify native Windows behavior, signed-in host integration,
provider egress, release signing, or complete project readiness. Current native
CI/package evidence and the separate storage review remain the parent's release
gates. No blanket outcome PASS is inferred from this interface report.
