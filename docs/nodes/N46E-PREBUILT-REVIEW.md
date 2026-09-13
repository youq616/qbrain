# N46E — prebuilt acceptance engineering review

Verdict: PASS for the additive acceptance helper. Reviewer: ChatGPT under the
recorded owner override; this is engineering self-review, not an independent
third-party or Claude Code audit. It is not N47 implementation or whole-product
acceptance. No production C++, schema or existing installation scripts changed.

## Provenance

Helper source: `d1e1a4937489f25305765725f7a071fee90a47d6`.
Helper tree: `3243ea0f68cf31884c7a030fe9fb27dce22fdab3`.
Product EXE remains the original `464045e2451ec71ca37dd8e92bcf4ac0d9325a0b`
N46D queue-fix build; the main baseline `3751d4da5cc7eb5d197455ffd6e245b530c51c09`
contains that runtime plus subsequent documentation. The two source identities
must not be conflated. This outcome document is added after the tested helper.

[Run 34749654838](https://github.com/youq616/qbrain/actions/runs/34749654838)
completed/success at 2026-09-13T09:34:05Z. Jobs `103703844671` (Ubuntu)
and `103703844673` (Windows) succeeded. No compiler was invoked in this workflow.
The Windows runner is Windows Server 2025, not the user's Windows Server 2022.

## Plan acceptance

| Requirement | Observed evidence |
| --- | --- |
| Fixed external trust anchor before staging | Original archive SHA256, EXE SHA256, source and per-member manifest checks; wrong/tampered fixtures rejected |
| Windows path and bounded archive handling | Device/stream/traversal/case/symlink and expansion fixtures; no output written for invalid package |
| Existing output preservation | Exclusive new-directory preparation; test preserves existing sentinel file |
| Child-only state isolation | Environment unit test plus real native memory smoke under new data root |
| Honest result counts | Generated from records; unit test makes 6 PASS + 10 BLOCKED total 16 |
| No false host or Linux-native certification | Linux refusal test; native/full-regression/Agent scope explicitly separated |
| PowerShell compatibility | Corrected wrapper executes on both PowerShell 5.1 and 7 |
| Original EXE actually runs | Six commands: init A, capture, local extract, separate-process recall, init B, empty B recall |

Helper suite: 21 tests pass locally and in Ubuntu CI; Windows runs 20 tests and
explicitly skips the one Linux-only refusal test. The Windows EXE smoke is a
separate execution, not that skipped unit. Package checks plus six CLI commands
and the exact-quote/isolation assertion yield 8 PASS records; local build, full
native regression and actual Agent lifecycle remain 3 NOT_RUN records (total 11).
Each verify-only PowerShell wrapper summary has 1 PASS and 4 NOT_RUN (total 5).
No Qbrain provider call, real user memory or real signed-in host was exercised.

## Downloaded evidence

Artifact `10314924014`, `qbrain-prebuilt-acceptance-evidence`, 5309 bytes.
SHA256: `002c2159e232706e606e9f705ec5b513838c4a97ff99a9baf094bb4d364c3e3a`.
Download digest/CRC and the native/PS5.1/PS7 summaries were rechecked; each total
matches its states and real_agent_verified remains false. No database or EXE is
included in the evidence artifact.

The pinned product inner ZIP is unchanged, SHA256
`4f43e91853602bd141822ad11650ddab9643a3471f8a86bd2c615ffb61c460ee`.
The executable is unchanged, SHA256
`0fae586ddb6d2d12a539c94d87d5a6532da42682e34e3e8d039af140f8058d7c`.
It remains an unsigned development executable, not a signed release.

## First failure and correction

Run `34749526300` passed archive verification and the native CLI smoke, then
failed the PowerShell 5.1 wrapper. Get-Command returned two Python applications,
and invoking the Source array joined the paths into one invalid command.
The corrected helper selects one executable with Select-Object -First 1. The
failed run was retained; no request assertion, checksum, isolation rule or test
was removed. The following run tested the changed source, not a retry-until-green
of the same implementation.

## Scope limits and rollback

This resolves the unnecessary coupling of local runtime acceptance to local
compiler installation. Missing tools still block genuine local source builds;
those builds were not performed here. Real client Hooks, authenticated sessions,
project A/B recall, local PowerShell/runtime behavior on Server 2022 and uninstall
remain tasks for the owner's local Agent, using synthetic data.

The helper is offline locally and Python is an acceptance-only dependency.
No package manager, persistent environment edit, privilege elevation or automatic
Agent approval is introduced. It does not defend against another malicious process
with equivalent local file permissions. The CI-only fixed historical artifact
expires September 26, 2026; expiry must fail clearly, never fall back to latest or
dist. Retained original ZIP files continue to work offline. Rollback removes the
additive helper/tests/workflow/docs only; no stored-data downgrade is needed.
