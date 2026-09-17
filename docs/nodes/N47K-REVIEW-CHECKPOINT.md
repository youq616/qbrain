# N47K engineering review checkpoint — native delivery still pending

Product: a23800df3709ac9ef73a51d150b64d2d20d7d21f.
Tree: b95af421ea5ebb756a127fe8cc519b5b62e17cf6.
Baseline main: 03665e99865069a13212d84357b938c8e9cc662d.
Reviewer: ChatGPT, separate owner-authorized engineering self-review, not an
independent subagent or third party. This is NOT final stage acceptance, a merge
approval or a release record. Native59-group/package gates remain pending here.

## Actual defect and correction

Original candidate e9d8f3e1 failed the full Windows build in run35178697281,
job105065990875. diagnostics.cpp compiled, but diagnostics.obj was missing from
both direct-MSVC link lists, producing LNK2019 for run_hook_diagnostics. The N42
run35178697254 failed too. CMake success did not certify the direct-MSVC path.
The repair plan was committed before editing. a23800df adds the object to both
lists and adds ten strict default source/object-closure tests. The new real-source
check fails against the original scripts and passes on the correction. It runs
through the existing registry test entry point, without adding Python as a
requirement of standalone MSVC scripts. Default lists only; custom source-list
behavior is not certified by this static checker.

## Code review and actual supplemental execution

The inspector dispatches before normal Hook handling and does not open a Brain.
Only fixed host/event filenames are read. OS handles are read-only, bounded and
closed on early returns. Whole canonical-record equality and strict JSON/type
checks reject additional fields rather than silently presenting a sanitized
forgery. Disabled config and historical records are distinct. No new MCP route,
consent, schema, model call, diagnostic write or normal Hook behavior change.

From the fixed source on Linux GCC14.2: production build succeeded, diagnostic
11 scenarios/107 assertions and actual CLI60 checks/68 commands passed. The68
commands include54 expected exit0 and14 expected argument/config exit2 results.
Sixteen inherited process suites passed. Fourteen report/registry suites totaled
204 tests; the31 registry/manifest tests are included, not added again.

An independently constructed metadata oracle executed328 CLI commands and2472
assertions. It tests valid and invalid field/type/budget cases, no sensitive
fixture/path echo, unchanged file bytes/mtime/inventory and300 atomic replacements
scheduled with80 reads. It checks each returned record against an independent
expected complete version. This concurrent schedule does not prove every read
overlapped a write and is not hostile directory-topology or multi-file evidence.

A separate C++ probe executed2000 repeated inspection calls and nonregular/link
cases,2006 assertions, with Linux descriptors4 before and4 after. This finite
observation is not universal leak freedom or a Windows handle test. A further
six real unprivileged subprocesses (child UID65534 only, no persistent settings)
verified27 assertions for unreadable config, parent and record files on synthetic
fixtures. No real user data or credentials were read.

A temporary compiled copy with the canonical equality check removed exited1 at
`unknown values suppressed`, as required. The original product/header/libraries
were unchanged by this negative test. No assertion was dropped to obtain success.

## Source binding and retained local limitations

The fixed source artifact10481837565 has SHA256
2e0c242c7d0f2c75bfaf366b61e0c7f07a091af921b1577b3b61517547a0e7a6.
All866 files match the working copy. A separate empty Git index populated only
from that exact member list reproduces b95af421. An initial broad local index
included one generated Python bytecode file; it was excluded from the separate
source index, not mistaken for a product difference or pushed to the repository.
Archive-only wrappers retain source_commit=null; source identity is established
separately, not fabricated. Supplemental scripts' fixed declared source identity
is not a runtime Git measurement. An initial local build used an incorrect target
name and failed before compilation; using the existing actual target succeeded
without any source change. Original failures remain evidence, not suppressed.

Reads may affect OS access times; supplemental no-mutation checks cover content,
mtime and topology, not atime. Static link/reparse checks are not protection from
hostile concurrent parent substitution or hardlinks. Per-file reads are not a
multi-file snapshot. INSPECTED/present is not an authentic record or proof of
model consumption. These limits remain explicit in the user documentation.

## Native snapshot and next gate

Current-source development35186099196: source and Server2022 succeeded; full
Windows production linking now succeeds and subsequent fixtures are running.
Portable and sanitizer jobs were still queued at the latest observation. N42
35186099174 portable succeeded; its Windows job was still queued. The original
old-candidate successful subsets do not certify this candidate's pending jobs.
Downloaded current Server2022 evidence10482402970, SHA256
9ef49cece6ba43f1c8e72fc08f5d0da9376c79fc32ddba842739d172ef3236b5,
and revalidated full diagnostic11/107 and fixed HTTP lifecycle/shutdown reports.
Probe executables were not separately downloaded; their hashes remain grounded
in the fixed original reports and actual CI checks.

No further local-review defect identified after the native link correction, but
full native acceptance and exact final package readback must finish before final
outcome approval, merge or publication. Keep PR27 draft. No local-agent, compiler,
GitHub credential, real-client rerun or Codex authentication task is required.
