# N47V final review — case-sensitive installation identity protection

Recorded 2026-09-19 UTC (2026-09-20 Asia/Seoul at closure).
**PASS for the approved path-guard source scope, with a non-blocking reliability
observation tracked in Issue40. No P0/P1 finding remains in this limited scope.**
This is not an absolute bug-free guarantee or stable-v1 acceptance.
Reviewer: coordinating ChatGPT, separate engineering self-review authorized by the
owner; not a separate subagent, Claude Code or independent third party.

## Exact objects and original approval

Base main98b45d264696a23552ca14d12218555c57087528.
Original plan/plan review commit2e8ccaac0ceb2127e752de4c222f5fb10c7b1df7 preceded
implementation. Original plan is preserved under n47v-evidence/APPROVED-PLAN.md.
Product/original tests:192cdec2c3a39b6f35e7f6521d779425e61fee17, tree
92ff4e582c49d92839614f3ef903fee6e9effaf0.
Supplementary review tests:b28a6378b7e5ceb3b4ea785317905a891d363da0, tree
c1c59d1a1c31b6402136d6ed410bc70e8e02764b.

The continuation found PR39 unfinished and retained its product. It read the
implementation, original tests and failing CI, retried the exact failed job once,
then added a separate native file/junction-substitution test and reviewed its raw
results. It did not start a duplicate feature or call an old failure a success.
Only Install-QbrainMemory.ps1 changes among373 inherited code/test/build/workflow
files; all C++/schema/Hook/bridge/original tests/builds/ledgers remain unchanged.

## Approved criteria and concrete evidence

| Requirement | Evidence and outcome |
| --- | --- |
| Preserve ordinary identity, reject ambiguity | Actual NTFS case-only Project/project fixtures have distinct content but identical old IDs. Old Status reports the sibling installed. New Install/Uninstall/Status refuse both projects; ordinary path aliases retain the old ID. PASS. |
| Metadata-only native query | CreateFileW uses FILE_READ_ATTRIBUTES, share read/write/delete, OPEN_EXISTING and BACKUP_SEMANTICS/OPEN_REPARSE_POINT. Handle attribute/type query precedes FileCaseSensitiveInfo. Invalid query or nonzero flags reject. SafeFileHandle using scope disposes handles. PASS. |
| All relevant existing directory ancestors | Existing Safe calls cover project, configuration, pending journal, temporary/backup/owned paths and binary parents. Early binary check precedes owned-directory creation. No directory-flag cache, migration or flag toggle. PASS. |
| No writes on refused path scenarios | Both host formats and all actions preserve fixture files/directories after refusal. Pending recovery does not start on an unsupported path. No brain initialization or implicit permissions. PASS within checked scenarios. |
| Type substitution at metadata boundary | Separate22 checks per shell cover regular-file/missing handle, repeated success/error, and file/junction replacement at the Get-Item/native-open boundary for three actions. Native handle rejects substituted type; full fixture state equals original after tester-only restoration. PASS. |
| Ordinary recovery and compatibility | Both shells complete original24 snapshot,60 recovery,69 installer,16 consent,8 transport,33 fact-install and33 promotion checks. No assertion or timeout is relaxed. PASS with retry history below. |
| Full unchanged application regression | Fresh MSVC production/test build has BUILD_OK and all60 original registered groups, revalidated from original log. Live PG remains SKIP-PG. PASS for executed scope. |

The84 main checks include13 actual directory-flag observations per shell; they
are cases, not84 independent features. The additional22 checks are deliberately
scheduled real Windows filesystem changes, not all adversarial concurrency orders.
No PowerShell/Windows process was executed locally in the Linux review environment.
Windows CI is not a signed-in client's session or the owner's Windows11 machine.

## Exact runs, attempts and retained failure

Core workflow35450108456 at192c, push, attempt1:
source105915664609, PowerShell5.1 paths105915664584 and full-native105915664505
succeeded. PowerShell7 paths105915664586 passed84/24/60, then the unchanged original
installer suite stopped after check42 with Qbrain process timeout at
Invoke-QbrainJson.ps1:71 while invoking the installed Codex encoded Hook.
Following suites in that failed job were not executed and were not declared passed.

One explicit rerun of that exact failed job produced attempt2/job105920556280,
which completed all gates successfully. No installer, EXE, bridge, test assertion
or10-second timeout changed. The run's attempt2 status is success; acceptance uses
original source/PS5/full-native evidence plus the PS7 attempt2 artifact, not an
invented claim that all earlier successful tasks were newly rerun.

**P2 observation: Issue40 remains open.** The single observed timeout did not recur
in that retry. Its cause is not established; neither CI load nor product root cause
is asserted. The rerun is not a fix. N47V modifies installer path checks, not the
executed Hook/bridge bytes. Scoped guard approval does not close reliability or
real-client acceptance. Further occurrences should retain privacy-safe startup and
process timing data rather than increase timeout or retry until green.

Supplementary workflow35452314972 atb28a, push/attempt1:
review(pwsh)105921493179 and review(powershell)105921493365 both succeeded, each22
exact checks. That source adds only the review script, workflow and continuation
plan; product bytes match the original accepted installer.

## Byte and report readback actually performed

Seven original artifact ZIPs were downloaded, checked against connector IDs,
sizes/SHA256, CRCs and source markers; pins are retained in SUMMARY.json. These
include the failed PS7 artifact, not only successful evidence. Source artifact
reconstructs1155 files and the exact192c tree. Supplementary archives reconstruct
1158 files and the exactb28a tree, with1141 inherited files differing solely by
exact LF-to-CRLF conversion. Canonical ledger/frozen inventory remain intact.

Installer Git blob:64fb3962e5bdd4c2ac3ba262c43af4adef0ec3a4.
Git/LF SHA256:b2c6b64a4ad33adb9ab7b4d436c2a3427191fec7965482cfa97c2a824f6da64b.
Tested Windows CRLF SHA256:8800b24d1eda8f4aefc85e64c9ded46406983c03271f2365acb9014ccbb2d860.
Prior tested installer CRLF:d802c230d2e5b0938b81baa115d5cf5b475aa855fce0df28f0305f00575fcc51.
Installer-test EXE:c35fadde8c8356b7243bf0b34cfd5c836bda27bb46da87eddcc79c1031bf05b5.
The separate full native build is not asserted to produce those same EXE bytes.

Original case-path, snapshot, recovery and fact/promotion report validators were
rerun locally against exact report/script/runtime bytes. Case/log name sequences,
original69/16/8 checks, all22 supplemental labels, scope flags and source hashes
were checked. Core validator's3 methods passed normal and optimized Python,
including18 malformed-input variants and duplicate JSON key rejection. A local
readback pass then succeeded normally and under Python-O; its8012-byte result
hash is0e53733b03bc3e6d49ae1a68279e629be39bee6aa813baea0c7a0d84844aecf1.
This is local evidence processing, not local native execution or external model use.

## Earlier harness corrections, limits and merge boundary

Inherited INITIAL-FAILURE.md retains the test helper collision with PowerShell's
Dir alias. METADATA-FAILURE-REVIEW.md records the invalid assumption that denying
file sharing also denies read-attribute metadata. Seventy-eight valid checks were
retained and six correct compatibility/disappearance checks made the final84;
those harness corrections did not alter product behavior or conceal new failures.

This refusal is NOT full case-sensitive-project support. Existing unsupported
installations require inspected recovery/migration; no automatic flag changes,
record merging or data deletion is authorized. Add-Type requires the host's normal
.NET interop capability. Unsupported filesystems, query permissions or constrained
language can cause refusal; no unsafe fallback is added. Native metadata calls and
layouts were checked against official Microsoft documentation, not localized text.

Checks do not provide atomic protection against arbitrary replacement or flag
changes after the final check, preloaded hostile types, or an administrator. The
existing recovery transaction is not rewritten. Public N47R assets still contain
the prior installer, and no new release/tag is made here. The scope includes no
new real model/client, usage/fees, PostgreSQL or signing evidence.

The closing commit must contain documentation/history only overb28a. Verify its
diff and actual merge tree; do not predeclare newly triggered merge CI successful.
The current broad route and v1 external acceptance estimates remain conditional,
not mechanically reduced because one unsupported-path guard has been delivered.
