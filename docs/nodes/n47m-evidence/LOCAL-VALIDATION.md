# N47M local validation — September 18, 2026

Scope: isolated synthetic SQLite on Linux, GCC 14.2, CMake Release, PG disabled.
This is executed engineering evidence, not an independent review or native PASS.

## Source and executable identity

Main base: `182e1c3ee64b56f4b114bb08ec1f4ba536f8752d`.
Source obtained from N44 run `35228307025`, artifact `10499777695`, produced
from `17e9a435f94e45b3ca22d3da062ba4683c135c4b`. The GitHub comparison from
that product commit to main contains documentation-only changes; production,
build scripts, tests and workflows are identical. The archive has no .git
metadata; local reports therefore do not invent a candidate commit identity.

| Object | SHA-256 |
| --- | --- |
| Downloaded source artifact ZIP | `f5332ce4deadac4c29f943b1b2e9f79d48a3334510cb86ce5642f48e4803479d` |
| Baseline executable | `88b3fefe192935684e658b830b040178d448d9507af5e55e443948e0a3cf1565` |
| Repaired executable | `ee78fc6666c35e031ebad5158bbf73ba5892478c0cf8016a5af8c6505a46a9f5` |
| Repaired commands.cpp | `adf11a724e41d6e2cb84781e9afbfd2c9b02e8c3f327213ee4d00b0143182013` |
| New test_named_arguments.py | `778cc5a64ae3e364f8d83e8a383b4622ee0c1fb270db39876129a46c73beea2e` |

Git blob identities checked before publishing: commands.cpp
`b1b1dd08ee9511bdd4b7fbd09ae821b343873c4b`; new regression script
`c5847239a1bbe7b9b6020f0bda8815474fbda40f`.

## Actual final results

| Test | Result |
| --- | --- |
| New candidate process suite, with optional baseline comparison | 67/67 checks, 127 process calls, exit 0 |
| Final same test script against baseline, no optional comparison | 39/60 checks, 21 failures, 100 process calls, exit 1 (expected rejection) |
| Existing memory process suite | 44 checks, exit 0 |
| Existing context process suite | 65 checks, exit 0 |
| Existing fact process suite | 34 checks, exit 0 |
| Existing multiterm process suite | 112 checks, 126 process calls, exit 0 |
| Existing MCP boundary suite | 17 checks, exit 0 |
| Existing local configuration suite | 6 checks, exit 0 |
| Focused memory/context/fact/multiterm CTest | 4/4 groups, exit 0 |

The new suite alone is 60 checks without the optional 7 ordinary-command raw
stdout/stderr/exit byte comparisons. It validates exact raw quotations, event
IDs, source IDs, raw pages/revisions, option-order invariance, brain precedence,
invalid/empty inputs, absence of accidental directories and consent boundaries.
The baseline is deliberately expected to fail; overlapping cases are not distinct
bug counts. Seven byte comparisons do not imply byte coverage of every command.

## Reproduction commands

```text
cmake -S . -B build/takeover -G Ninja -DCMAKE_BUILD_TYPE=Release -DQBRAIN_WITH_PG=OFF
cmake --build build/takeover --target qbrain --parallel 2
python .ci/test_named_arguments.py --binary build/takeover/qbrain --baseline /mnt/data/qbrain-evidence/qbrain-baseline --report /mnt/data/qbrain-evidence/n47m-fixed-v2.json
python .ci/test_named_arguments.py --binary /mnt/data/qbrain-evidence/qbrain-baseline --report /mnt/data/qbrain-evidence/n47m-baseline-final.json
cmake --build build/takeover --target qbrain_memory_tests qbrain_context_tests qbrain_fact_tests qbrain_multiterm_tests --parallel 2
ctest --test-dir build/takeover -R 'qbrain_(memory|context|fact|multiterm)_unit' --output-on-failure
python .ci/test_memory_cycle.py --binary build/takeover/qbrain
python .ci/test_context_process.py --binary build/takeover/qbrain
python .ci/test_fact_process.py --binary build/takeover/qbrain --report /mnt/data/qbrain-evidence/fact-process.json
python .ci/test_multiterm_process.py --binary build/takeover/qbrain --report /mnt/data/qbrain-evidence/multiterm-process.json
python .ci/test_mcp_boundaries.py --binary build/takeover/qbrain
python .ci/test_local_config.py --binary build/takeover/qbrain
```

The /mnt/data paths identify this execution environment, not files on the owner's
machine. Native reproduction is automated in n47m-validation.yml using the
unchanged PowerShell build scripts. Python is test-only, not a product dependency.

## Raw report identity and preserved limitations

| Local report | Bytes | SHA-256 |
| --- | ---: | --- |
| n47m-fixed-v2.json | 107754 | `95b31fac0def6380336554fce833ca382dbf11af2340b68b2ab403946d4ec03b` |
| n47m-baseline-final.json | 81522 | `421a9bf4ac0cb74c7ae35548f0e96329dbad3838fb2b2925cdf992946c53d99c` |
| fact-process.json | 22871 | `5167ed7e98e6ddad6bc1737b345bac482da85a48738a40d04c0cebc4f3b656e3` |
| multiterm-process.json | 76946 | `96b0277969993a9926719d9d8cf8ef3f8c2bd08602b8a6368906e2f731bcc698` |

Raw local reports are identified here but not embedded in this Markdown. New CI
uploads independently generated raw reports and logs as per-run artifacts; their
hashes will differ with platform and synthetic run IDs. Do not equate them with
these local byte identities. Retained initial failures are described in the outcome
checkpoint: MCP fixture authorization, missing report arguments, and pre-existing
Linux full-suite compiler errors. No live DSN/provider/client acceptance, no full
project completion, no independent outcome PASS, and no release are claimed.
