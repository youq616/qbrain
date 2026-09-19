# N47P final engineering review — installer recovery and input snapshots

Date: 2026-09-19, Asia/Seoul.
**PASS for the approved installer source-repair scope. No known unresolved blocking
finding remains in that scope.** This is not an absolute bug-free claim, a new
application release, real-client acceptance or completion of the whole project.
Reviewer: coordinating ChatGPT in a separate implementation/outcome engineering
self-review, explicitly requested by the owner. No separate subagent or third-party
reviewer ran. The original plan and later snapshot addendum were reviewed before
implementation; their unchanged acceptance criteria are checked below.

## Reviewed source and the additional finding

Base main: `4734fe840081bc2215485e43031fc967b5a93c9d`.
Existing recovery candidate: `3ebecf26946ae6ddd04fb018085ffc023b5fcab0`.
Snapshot addendum approval: `c11b7b34598efc75179a138816eb40659e1965b6`.
Final tested candidate: `9feed7c74926d53a7b2a7b21391af02275799f51`.
Final tested tree: `d396b6170866b83db89e54e26f44685ebcd5c276`.
Installer Git blob: `90bf59912a58203de600c2ecaf970c7c5a183236`.

The earlier 3eb recovery/native run35413278453 was successful, but separate code
review found a remaining lost-update window: transformations used earlier reads
while Change fetched a later before image. An external edit made during planning
could then be treated as permission to overwrite it. The new repair binds parsed
input, ownership verification, before images and backup to the same reads, keeps
both current-image comparisons, and moves the second comparison before backup.
This finding was fixed and re-reviewed rather than covered by the older green run.

## Acceptance against both approved plans

| Requirement | Review and executed evidence | Verdict |
| --- | --- | --- |
| Recoverable bounded journal | Individual text images retain2MiB UTF-8; aggregate serialized journal uses32MiB. Generated images/envelope are checked before native init/backups/transaction writes. Large valid journal and interrupted large install recover; generated overflow is rejected without a new brain. | PASS |
| Preflight before rollback | Entire decoded version/fields/array/path uniqueness/images and final/temp destinations validated before rollback. Later invalid members, directory/junction collisions and external edits cannot roll back earlier members first. | PASS |
| Retry real partial failure | Actual native file-sharing lock interrupts second rollback write; unchanged pending journal is retained, then retry restores mixed before/after images and retires the journal. | PASS |
| Preserve absence/text/consent | Absent versus empty images, legacy small journal, Unicode paths and original install/upgrade/uninstall/default consent/fact/promotion suites retained and passed. | PASS |
| Input-snapshot consistency | Twenty deliberately scheduled edits across two hosts and five owned file types (present/absent) are rejected while preserving current bytes and creating no backup/journal/new brain. Four ordinary installation/uninstall controls pass. | PASS |
| Meaningful negative control | Exact3eb installer fails20/24 snapshot cases but passes all4 controls; published installer fails34/60 recovery cases while required legacy controls pass. These overlap and are not independent bug counts. | PASS |
| Native regression | Fixed push run35415626607 passes both native shell jobs and a fresh production/test MSVC build; all60 registered groups verified from original log, including N31. Real PG remains SKIP-PG. | PASS |
| Independent engineering pass | Same coordinator later reviewed source, new test seam, both baseline identities, full source tree, original reports/logs and additional negative verifier inputs. Identity is self-review, not another agent. | PASS |

Only the installer changes among259 inherited src/include/schema/tests/scripts
files compared with the accepted c26 source. No C++ implementation, schema,
existing test/build script, canonical ops ledger or frozen inventory changed.
The original60 recovery cases and all five earlier PowerShell suites were retained;
new snapshot tests and CI steps are additive. The closing change is documentation
and docs-scoped readback material only, not a different product candidate.

## Exact native run and artifacts

Fixed push/attempt1 run:
https://github.com/youq616/qbrain/actions/runs/35415626607

All four jobs and every required step completed successfully:
source105823613064, recovery(powershell)105823613055,
recovery(pwsh)105823613114, full-native105823613013.
The separate pull-request run may use a merge checkout; it is not the source
identity used for this acceptance.

All four original artifacts were downloaded and matched connector-retrieved
size/SHA256, ZIP CRC and source.txt/archive identity. ARTIFACT-PINS.json retains
IDs and hashes. Source archive reconstructs the exact1040-file Git tree above;
all1040 mounted source files match. Each shell evidence ZIP has22members; the
full-native ZIP has3. Native source.txt equals9feed and native-groups.log reports60.
The log contains BUILD_OK and the exact complete registered-group multiset, not
only a self-reported total. It also explicitly skips the unavailable live PG DSN.

| Actual test on each native shell | Outcome |
| --- | --- |
| New input snapshot suite | 24/24 passed |
| Same suite against exact prior3eb installer | 4 passed,20 expected failures; exit1 |
| Existing N47P recovery suite | 60/60 passed |
| Same recovery suite against published installer | 26 passed,34 expected failures; exit1 |
| Original installer / consent / transport | 69 /16 /8 checks passed |
| Original fact-install / promotion-install | 33 /33 checks passed |
| New snapshot-report validator unit suite | 5methods passed normally and with Python -O |

Recorded shells: Windows PowerShell5.1.26100.33296 and PowerShell7.6.5, both on
native Windows CI. They are not a claim to have exercised the owner's Windows11
machine or authenticated Claude/Codex. Original integration tests call real Qbrain
processes with synthetic data; they do not become new signed-in host consumption.

The additional snapshot suite wraps ConvertTo-Json only in the test process,
performs a real scheduled file edit, and delegates serialization to the original
cmdlet. The unmodified installer has no test switch. This is deterministic
interleaving during initial-install planning, not general concurrency stress.
Uninstall/reinstall behavior is covered by the retained ordinary suites and new
normal controls; every possible concurrent uninstall window is not claimed tested.

## Bytes, local checks and reproduction

| Object | SHA-256 |
| --- | --- |
| Fixed installer Git/LF source | bde21f5c1aabb7b517a1324f3fb076b482a5652387eaab26a1050bb0feb97dd2 |
| Fixed installer tested Windows CRLF | d802c230d2e5b0938b81baa115d5cf5b475aa855fce0df28f0305f00575fcc51 |
| Exact prior3eb tested Windows installer | f0af9ec30a22fcdafaf1bcadbb6a5f6e6d5249db7e0ccff92512910e56adee77 |
| Published c26 baseline installer | 99d864bf1e87c75a2b7c22a7f2c27d3b25210a153ef10516e9fff366313a22a6 |
| Fixed released EXE used in installer jobs | c35fadde8c8356b7243bf0b34cfd5c836bda27bb46da87eddcc79c1031bf05b5 |

The only accepted checkout transform is exact LF-to-CRLF; it was matched to every
relevant report hash, including test scripts. No generic whitespace normalization
was used to declare identity. The fresh full-native build is a separate execution;
its EXE bytes were not downloaded or equated with the fixed installer-test EXE.
No new EXE or public application package is published in this node.

The coordinator reran the source-owned report validators against both downloaded
shell artifacts and the original native log. Five new validator test methods
(4positive and21negative subcases) passed under ordinary/optimized Python;32
existing native-log validator tests passed in both modes, and10 MSVC manifest
tests passed locally. Four additional corrupt source/run/artifact-pin inputs were
rejected by the offline readback tool without writing a success report.
These local Python executions are not local PowerShell or native Windows runs.

The tested docs helper `n47p-evidence/readback.py` is committed with Git blob
f6bd570ceec4b4da9f90ef9ebaa73431ab722a17. Its positive readback result is retained
as READBACK.json. It delegates original recovery/fact/promotion/native validators
and checks source/installer/test/EXE identity and ordered log labels. Its metadata
is normalized from actual connector reads, not a signed API response. The offline
helper itself does not query GitHub or observe already-deleted temporary files.

To reproduce, obtain the original four artifact IDs in ARTIFACT-PINS.json, rename
them to its file fields, extract the nested source archive at9feed to a separate
root, use the original public c26 product ZIP, and provide the LF installer bytes
from3eb (Git blobff7042fa94b3d6a7b85e06572557fe575ad18c74). Do not pass a later
main checkout as the original source root, or substitute a different baseline.

```text
python docs/nodes/n47p-evidence/readback.py --root <extracted-9feed-source> --evidence <four-original-zips> --metadata docs/nodes/n47p-evidence/ARTIFACT-PINS.json --package <original-c26-product.zip> --prior-installer <3eb-LF-installer.ps1> --report readback.json
```

Native reproduction uses the unchanged commands in n47p-validation.yml, including
both named shells and exact negative-control exits. Raw native logs remain in the
original Actions artifacts subject to their2026-10-03 expiration; small derived
receipts, hashes and the verifier are committed. The full raw archives are not
silently represented as embedded in Git.

## Historical failures and explicit limits

The earlier run35412963277 PS5 harness failed before tests because its optional
parameter default evaluated PSScriptRoot too early. The default was moved into the
body. Separate prior review also closed PS7 one-element root-array enumeration;
the original cases were retained and grew58to60. INITIAL-REVIEW.md preserves this
history. In this continuation the new snapshot candidate's tests passed on first
execution; the exact prior installer was intentionally rejected, not counted as
a failed new implementation. A local absent manifest-test filename was not run;
the actual test_msvc_link_manifest.py subsequently passed10tests. Network retrieval
limitations led to verified Actions source artifacts, not invented local checkouts.

No known blocking finding remains within the approved scope. Files are decoded
text, not binary-exact BOM/encoding journals. Snapshots are not simultaneous, and
an external writer can still race after the final comparison. Multi-file rollback
can be interrupted by I/O; the journal enables retry, not filesystem-wide atomicity.
Brain initialization is not rolled back after a later conflict. Existing strict
validation concerns decoded journal structure, not cryptographic authenticity or
a complete duplicate-key JSON decoder replacement. No hard-link/hostile-admin
protection, new ACL/DLP, PG, model quality/cost/egress or code signing is claimed.

Current public N47O assets stay unchanged and do not include N47P's installer.
After final docs-only diff/current-head checks this source repair may be merged;
record the actual merge/tree in PR33 rather than substituting it for9feed's build
identity. New merge-triggered CI is not predeclared successful. The v1 planning
estimate is now3–5 further substantive rounds including integration/delivery;
broader15–25 stays a rough unchanged interval because its main unknowns remain.
