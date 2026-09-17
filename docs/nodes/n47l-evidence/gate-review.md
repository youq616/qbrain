# N47L report gate review — supplementary execution record

Reviewer: `/root/recall_interface_review/report_gate_review`.

This Markdown report was written **after** the executions described below, at the
coordinator's request, for archiving. It is an independent review statement
supported by the actual tool-call records in this conversation. It is **not** an
original captured test log or a machine-generated execution artifact.

## Artifact provenance

The 881-case mutation sweep was executed inline through `functions.exec` using
`tools.exec_command` and a `python3 -B - <<'PY'` heredoc. The working directory was
`/workspace/scratch/8ee4dd18bee0/qbrain`. No original probe file or separate summary
file was saved at that time. The tool returned the execution output to the
conversation, with process exit code 0.

`SUPPLEMENTARY-PROBE.py` is a **post-run transcription** of the inline Python from
that actual call, preceded by provenance comments. It was transcribed from the
still-visible conversation context; it has **not** been executed as a file. Do
not label it an original execution artifact or imply that writing it repeated
the tests. The historical report path read by that script is
`build/takeover/multiterm-after-report-repair.json`; availability of that path is
not implied by delivery of this supplementary file.

The sweep ran while the repaired files were changes on top of candidate
`1118e0faf5b7acdd3f27f933c801b4a2b1278d41`. The report test file then contained 19
tests. Its subsequent standalone-import test and package-dependency assertion
were reviewed, and the final 20-test version was executed separately. The
process runner and validator bytes were unchanged between those two executions.
Later read-only documentation review confirmed the final four hashes below in
committed product `17e9a435f94e45b3ca22d3da062ba4683c135c4b`.

## Finding and repaired behavior

The original process validator accepted incomplete/repeated command histories
because it checked only 81 rows and each row's self-reported matching
`exit_code`/`expected_exit`. The original three reproductions replaced commands
with repeated `init` successes, omitted command identity, or made every row a
self-asserted expected rejection. Each was accepted by the original validator.

The repaired validator checks a fixed command identity/order schedule and derives
each expected exit from the fixed negative-case set. It also checks complete
argv and decoded stdin, strict JSON types, consistent generated-ID references,
and duplicate keys in embedded JSON payloads. The real runner calls this command
validator before reporting success.

The original P2 is closed within this review's report-gate scope. No new P0/P1/P2
finding was identified in that scope. This is not final native or release
approval.

## Actual supplementary mutation sweep

The executed sweep used the repaired `process_fixture()` and performed:

| Mutation | Cases | Actual result |
| --- | ---: | --- |
| Remove each of `name`, `args`, `stdin_json`, `expected_exit`, `exit_code` from each of 126 commands | 630 | All rejected |
| Swap each adjacent pair in the 126-command schedule | 125 | All rejected |
| Jointly flip each command's expected and actual exit from 0 to 1 or 1 to 0 | 126 | All rejected |
| Original three malformed-history shapes, expanded to the repaired schedule length | 3 | All rejected |

The **881** figure is `630 + 125 + 126`. It excludes the three original shapes;
including those shapes gives 884 rejected malformed reports. These are
supplementary independent review mutations, not 881 additional source-owned test
methods.

The same tool call accepted the command transcript in the real repaired process
report and read its reported `result=PASS`, `check_count=112`, and command count
126. I invoked `validate_commands()` on that transcript; I did **not** rerun the
product process in this call or authenticate its complete source/EXE identity by
feeding self-reported identities back into the full validator.

The tool output below is transcribed from the actual returned stdout; this fenced
block was not produced by rerunning the supplementary file:

```json
[
  [
    "original all duplicate init success",
    "REJECTED"
  ],
  [
    "original no command identity",
    "REJECTED"
  ],
  [
    "original all self asserted rejection",
    "REJECTED"
  ],
  [
    "each required field missing per command",
    630
  ],
  [
    "each adjacent command swap rejected",
    125
  ],
  [
    "each flipped expected exit rejected",
    126
  ],
  [
    "real process command transcript",
    {
      "result": "PASS",
      "checks": 112,
      "commands": 126
    }
  ],
  [
    ".ci/test_multiterm_process.py",
    "5d8562bc3923794b33093d7e8509e104bbf028107e5f7356e0ffbaba012c684e"
  ],
  [
    ".ci/validate_multiterm_report.py",
    "6198275e5a7952d886ca876c86d66193692f8dd9d535e6651c28d088df269831"
  ],
  [
    ".ci/test_multiterm_report.py",
    "da92bd6cd613b462da7a122b364e49bbeff199bef2aa2ed90c2dfacea07d6cea"
  ]
]
```

## Other checks I actually performed

- The final `.ci/test_multiterm_report.py` completed **20 tests, OK** with exit
  code 0. The process and validator hashes matched the sweep; all four final
  source hashes were checked before and after the final test.
- I compared the original 81-command report against the revised schedule's argv,
  order, and fixed expected exits, and compared the first 61 check names/order
  against the revised report. They were retained before the 45 appended calls.
  This was not a byte-for-byte comparison of all 81 old/new product outputs.
- I statically parsed the package script with Python AST and confirmed inclusion
  of both `verification/test_multiterm_process.py` and
  `verification/validate_multiterm_report.py`.
- I ran an isolated dependency positive/negative control in a fresh temporary
  directory using `python -I -S -B`. With only those two files copied and `run`
  replaced by a synthetic complete transcript, `process.main()` returned 0/PASS.
  Omitting the validator returned 1/FAIL with `ModuleNotFoundError`, preserving
  126 command records. Both cases kept `source_commit=None` and
  `tracked_tree_clean=False`. This control did not execute a product binary.
- Before the repair, I had run the original report tests (11/11) and native-log
  validator tests (32/32), and read the Windows/Server2022/portable/sanitizer and
  package wiring. Those are separate earlier checks, not current native CI.

## Final reviewed file identities

| File | SHA-256 |
| --- | --- |
| `.ci/test_multiterm_process.py` | `5d8562bc3923794b33093d7e8509e104bbf028107e5f7356e0ffbaba012c684e` |
| `.ci/validate_multiterm_report.py` | `6198275e5a7952d886ca876c86d66193692f8dd9d535e6651c28d088df269831` |
| `.ci/test_multiterm_report.py` | `639f8fa2be2cd23a8b1e894168f35d279447d5acb7e25271fe45cadb3a1718d7` |
| `.ci/package_n44_development.py` | `5f7eb486395193164062621f0fccf71b3f6de13ba869a14b17836f7ac8b788e2` |

## Limits

This subreview did not execute Windows-native builds, full package creation, or
GitHub Actions. It did not certify current native CI, release signing, live
host/model consumption, or complete project readiness. JSON structure and
schedule validation do not independently authenticate external execution
metadata or prove the truth of every reported product output. Current native and
package closeout remain the coordinator's separate pending gates.

No repository files were edited by this reviewer. Only these two supplementary
files were written outside the repository at the coordinator's request.
