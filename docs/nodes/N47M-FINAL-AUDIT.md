# N47M final engineering review — September 18, 2026

## Verdict and actual reviewer

**PASS for the approved N47M source-repair scope. No known unresolved blocking
findings remain in that scope.** This is not an assertion that all software is
bug-free, all Qbrain functionality is finished, or a new release was published.

Reviewer: the coordinating ChatGPT, in a separate implementation/evidence
engineering self-review pass. No separate subagent, Claude Code or third-party
reviewer ran in this continuation. The owner explicitly instructed:
“好的，你继续开发，本阶段开发完，请由你自己进行独立审核，确保没问题。”
`N47M-CONTINUATION-PLAN.md` records this node-specific authorization. The initial
pending checkpoint and plan are preserved under `n47m-evidence/INITIAL-*`.

## Exact review object

| Object | Identity |
| --- | --- |
| Base main | `182e1c3ee64b56f4b114bb08ec1f4ba536f8752d` |
| Original product repair | `c510e60ec935dcf756e7e29315908af060be999f` |
| Full native evidence source | `15f6f3962984cb9a9d20c3b6a2790a9b768f119e` |
| Full native evidence source tree | `571c24873615aa867fe037b0fb2f83975307371c` |
| Fixed commands.cpp Git blob | `b1b1dd08ee9511bdd4b7fbd09ae821b343873c4b` |
| Existing named-argument test Git blob | `c5847239a1bbe7b9b6020f0bda8815474fbda40f` |
| Newly authored review probe Git blob | `41cb7abdba0b9644bceefa84f2e6ce40aecde811` |

The GitHub c510..15f comparison contains only a continuation plan and one branch
allowlist edit in each existing N42/N44 workflow. Product, tests, build scripts,
permissions, job commands and assertions are unchanged. The final archive commit
adds only documentation and documentation-scoped review material; it does not
rebuild the product. Before merging, compare its tree with 15f and confirm main
and PR head still match. Record the actual merged tree in the PR receipt.

## Acceptance against the approved plan

| Criterion | Actual review and evidence | Result |
| --- | --- | --- |
| Two handlers only | Read production diff; only cmd_memory/cmd_context changed. Fact, search, global resolver, storage/schema and operation authorization unchanged. | PASS |
| Option-shaped data never rescanned | Strict parse saves option-position values, consumers use the map, manual flag uses validated seen set; only the actual brain option reaches resolver. | PASS |
| Source/brain/evidence isolation | Existing 60-case process suite plus separate 912 argument-order permutations verify source, quote/event ID, raw page/revision and absence of unexpected brain directories. | PASS |
| Default/empty/error behavior | Explicit > environment > file > default, empty environment, missing/unknown/duplicate arguments and supported empty values; rejected calls preserve application rows. | PASS |
| Mutation and consent behavior | Existing capture/extract/status/forget/drain/summary tests retained. Source AND brain named --manual do not grant consent; the real flag works. Model summary still denied without permission. | PASS |
| Ordinary compatibility | Seven fixed/baseline exit/stdout/stderr byte comparisons on the same synthetic state; not a byte comparison of every command. | PASS |
| Native and existing gates | N47M Windows/portable and full N42/N44 required jobs succeeded; original artifacts and registered groups read back, not just green status. | PASS |
| Additional self-review | Fresh local builds, independently authored probe logic, baseline rejection, original process/unit/validator tests, source and package identity checks. Same reviewer, not an independent agent. | PASS |

## Native evidence actually checked

[N47M push 35290029136](https://github.com/youq616/qbrain/actions/runs/35290029136)
ran the exact c510 commit. Its Windows artifact 10525864463 was downloaded and
hash-checked. source.txt and named-arguments.json agree on c510; the report has
60 passed checks, 0 failures and 113 actual commands, with every exit checked.
The native full original suite and portable job also completed successfully.

[N42 35292424658](https://github.com/youq616/qbrain/actions/runs/35292424658) and
[N44 35292424683](https://github.com/youq616/qbrain/actions/runs/35292424683) ran
15f. All required jobs/steps succeeded. N44's two publication jobs were correctly
skipped, not treated as missing test passes. Native logs from BOTH runs contain
the complete 60-group registry and retain production/test MSVC manifest checks.
Live PostgreSQL remains explicit SKIP-PG inside its registered group.

The unchanged N47L `verify_candidate.py` was executed with the new explicit
source/tree/run/metadata pins. It passed **1,177 checks over seven original
artifacts**, reconstructing the exact 966-file source Git tree, validating the
73-entry product manifest, original report content, expected process sequences,
Windows/N42 registered logs, package bytes and executable identity. Server 2022
unit/HTTP, portable and Linux ASan/UBSan artifacts were included. Server 2022 is
not a second run of the whole CLI suite; Linux sanitizers are not Windows ones.

Metadata was normalized from actual GitHub connector results. It is not a raw,
signed API response. Where the step-summary endpoint omits job source/attempt,
the containing run provides those fields; archive and native logs separately
confirm the source. The offline verifier did not independently requery GitHub.
Probe executables were not separately downloaded, and the verifier did not run
the packaged Windows product. Those limits remain explicit in READBACK.json.

## New executions during the final self-review

The source artifact was unpacked, its identity checked, and the product plus
focused unit targets rebuilt with GCC 14.2 / CMake Release / PG OFF. A baseline
was built with the exact original commands.cpp and otherwise identical product
sources/libraries. The fixed source was restored and rechecked after that build.

| Execution | Actual result |
| --- | --- |
| Newly authored review_probe.py on fixed product | 937 passed, 0 failed; 967 real subprocess calls; exit 0 |
| Same probe on baseline | 653 passed, 284 failed; 965 calls; exit 1, expected rejection |
| Original N47M suite with baseline byte comparisons | 67/67; 127 calls; exit 0 |
| Existing memory/context/fact/multiterm process suites | 44 / 65 / 34 / 112 checks passed; multiterm retains 126 calls |
| Existing MCP boundary/local config suites | 17 / 6 checks passed |
| Focused memory/context/fact/multiterm CTest | 4/4 groups passed |
| Report-validator unit tests | 193 passed |
| MSVC source/object manifest tests | 10 passed; production/test source counts 50/59 verified |
| Native-log validator tests | 32 passed |

937 checks include six query literals across 120 permutations each (720), eight
context sources across 24 permutations each (192), and 25 further checks.
They verify exact evidence, read/rejection non-mutation, brain precedence and
manual-consent boundaries. Repeated permutations are not distinct capabilities;
284 baseline failures are overlapping cases, not 284 separate vulnerabilities.
The separate probe is published under `n47m-evidence/review_probe.py` and uses
synthetic temporary SQLite only. These additional executions were on Linux,
not Windows, real client sessions or production user data.

## Binary identities must not be conflated

| Binary/package | SHA-256 |
| --- | --- |
| Linux fixed product used by final probes | `ee78fc6666c35e031ebad5158bbf73ba5892478c0cf8016a5af8c6505a46a9f5` |
| Linux original-handler baseline | `88b3fefe192935684e658b830b040178d448d9507af5e55e443948e0a3cf1565` |
| N47M c510 native process-report EXE | `677dabb700c244c47e3abf04b0aaf6163fc30cd4bdbeb33b76b268df1f1b9caf` |
| N44 15f packaged EXE, 4,070,912 bytes | `c455a082d4ee55c9ff61688919e39ba0b0a3a54f63a4de696285e5f7ecdb0faa` |
| N44 inner ZIP, 2,115,638 bytes | `9072c0ae4cae517cc6b759b17d1657fac7dd46265eece04461b757771f308ee3` |

The native process suite and N44 package have identical product/test source
but different EXE bytes. Do not claim the c510-specific process report executed
the 15f packaged EXE. The full N42/N44 gates cover the exact 15f source. The
packaged Windows EXE was not executable in the current Linux environment.

## Findings, repairs, and preserved failures

No new blocking product finding was discovered in this final review. The
existing repair also closes the previously untested brain-name --manual consent
case; the separately written probe confirmed the old executable fails it.

The initial stage's MCP fixture omitted explicit source permission; the fixture
was corrected without loosening product authorization. Two earlier invocations
omitted required --report arguments and exited 2; corrected commands passed.
Those historical results remain in INITIAL-HARD-AUDIT.md / LOCAL-VALIDATION.md.
The baseline all-tests Linux build has existing Windows-only _putenv_s/gmtime_s
calls; no test was removed. Full native tests ran in Windows CI, and the four
portable targets ran locally. This is not a claim the entire suite builds on Linux.

During final review one command mistakenly named nonexistent .ci/test_native_log.py
and exited 2 before testing anything. The correct .ci/test_validate_native_log.py
ran 32 tests successfully. This is a corrected invocation, not a repaired product
failure or a discarded assertion. Report-validator negative fixtures intentionally
emit failure-shaped JSON; the enclosing 193-test unittest suite finished OK.

## Reproduction and evidence retention

The exact new probe and machine-readable summary/pins are committed in
`n47m-evidence/`. The original source still contains the N47L artifact verifier
and existing process suites. Native artifacts can be retrieved by the IDs in
FINAL-SUMMARY.json while retained by GitHub (expiry 2026-10-02).
Full locally generated raw reports are identified by size/hash in that summary;
they are not silently represented as committed files. The conversation evidence
bundle contains those raw reports and logs. The reproduction helper records how
the normalized metadata snapshot was assembled, not a fresh online API check.

```text
python docs/nodes/n47m-evidence/review_probe.py --binary <fixed-binary> --report PROBE-CANDIDATE.json
python docs/nodes/n47m-evidence/review_probe.py --binary <baseline-binary> --report PROBE-BASELINE.json
python .ci/test_named_arguments.py --binary <fixed-binary> --baseline <baseline-binary> --report NAMED-ARGUMENTS.json
ctest --test-dir build/review -R "qbrain_(memory|context|fact|multiterm)_unit" --output-on-failure
```

Use an ordinary Python invocation (not -O) for the historical metadata helper.
Its /mnt/data paths describe the recorded review environment, not the owner's
machine. Python is test tooling, not a new product runtime requirement.

## Remaining scope and merge decision

The limited node is acceptable for source merge after final documentation-only
diff and current-head checks. No new Release/tag, installation, user-brain change,
model call or client trust override is performed. The published N47L download
still lacks this repair. Old status and ops ledger are preserved as
`CURRENT-STATUS-N47L.md` and `docs/OPS-PARITY-LEDGER-N47L.md`.

Search's literal-query grammar remains a separate next node. Real PG, complete
ACL/DLP, semantic merging/conflict inference, automatic decay, profiles, actual
model quality/fees, client consumption/egress and formal signing are not accepted
by this review. Existing project limits are not erased by this PASS.
