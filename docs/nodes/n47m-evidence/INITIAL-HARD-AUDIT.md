# N47M outcome checkpoint — NOT a completed independent audit

Verdict: PENDING native evidence and real independent outcome review.
Reviewer of the work recorded below: coordinating ChatGPT, separate self-review.
No independent subagent or third-party reviewer ran in this environment.
The node is not done. Do not merge or release based on this document.

## Scope checked

Production changes are confined to `cmd_memory` and `cmd_context` in
`src/qbrain/cli/commands.cpp`. Validated keys retain their values; subsequent
lookup does not rescan arbitrary argv. Brain resolution receives only an actual
brain option. Manual capture checks the validated flag set, not source contents.
Fact/search/global parser, storage, schema, operation authorization and providers
are unchanged. Existing tests and native build scripts are unchanged.

The final local candidate passed 67 process checks (127 command calls), including
7 ordinary command byte comparisons against the baseline; the same final test
script without comparison rejects the baseline with 21 failures out of 60 checks.
The 21 failures are overlapping regression cases, not 21 distinct product bugs.
Existing process suites passed: memory 44, context 65, facts 34, multiterm 112,
MCP boundaries 17, local configuration 6. Four focused CTest groups passed.
These are Linux engineering results, not Windows acceptance.

## Self-review findings and limitations

- Fixed within scope: query/source tokens could retarget source or brain, create
  unintended brain directories, shadow method/event/limit values, or grant manual
  capture by a source value named `--manual`.
- Test fixture correction: the first fixed run failed MCP parity because synthetic
  sources were not explicitly authorized. The fixture now permits only alpha and
  --brain. Production authorization was not weakened; the existing MCP boundary
  suite also passed. The final baseline rejection was rerun after this correction.
- Two initial existing-suite invocations omitted mandatory `--report` arguments;
  they exited 2 without testing the product. Correct invocations then passed.
- The baseline Linux all-tests build encounters pre-existing Windows-only
  `_putenv_s` / `gmtime_s` calls. No tests were removed or changed. Focused Linux
  targets ran; the original full suite is included in the new Windows CI job.
- Existing N42/N44 workflows are preserved. This new workflow does not by itself
  claim completion of all their platform, sanitizer, packaging and report gates.
- No available independent-subagent execution entry point was found. The latest
  owner review gate remains unmet; self-review is not substituted for that gate.

## Remaining acceptance

Obtain and inspect native N47M process/full-suite logs on the exact candidate;
complete the required N42/N44 matrix/evidence for that candidate; obtain a real
separate reviewer outcome, repair blocking findings, and re-review. Keep the
candidate draft meanwhile. No user-local installation task is necessary solely
to perform this repository work. Search grammar and PG remain separate scope.

See `n47m-evidence/LOCAL-VALIDATION.md` for commands and exact local identities.
