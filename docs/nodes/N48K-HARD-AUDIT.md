# N48K Windows integrated candidate — separate outcome review

2026-09-26. Reviewer: ChatGPT, owner-authorized engineering self-review after the
implementation. This is not a third-party or independent-subagent approval.

## Frozen identities and scope

Native product source: `24345f85e0c4962c93205a7fab0fbdb380a5ff09`, product tree
`b9b5f8a50e34ca7b897c85b2490e0b61100ab756` (merged N48J). The original reviewed
packaging and full qualification source is `f261896e8ccf97cb0f0630b3488151d1b91927d0`,
tree `7c3e6dc91662de6cdf5f60900ceeb3969e3a4095`.

The delivered executable is SHA256
`8f9ae1f7d644de107defa8a664184458cee946c50aa912b268b7ad8117477b1b`.
The immutable 51-member Windows ZIP is exactly 4,890,639 bytes, SHA256
`58d56b7bd7c9a662514e41d20bacb88c68c92bbe3fc380496a09331bf1f5cafa`.
It was built by the original native Windows job, not recompiled or patched here.
Two original assemblies are byte-identical. This establishes repeatable assembly
from the same inputs, not reproducibility of all compiler outputs.

This completes a bounded Windows integration and upgrade delivery module, not a
new model-quality experiment. It packages the existing installer, UTF-8 bridge,
14 optional evaluation scripts, 16 integration guides and 13 synthetic examples,
including the post-N47X source modules through N48J. Python is not an application
service requirement; it is needed only for the optional evaluation scripts.

## Intake and earlier failures

The module was already under development in PR #52 when this turn began. I did not
claim the existing packaging implementation or its prior fixes as newly authored
work. The PR description was stale: it referred to c1fb7000 while the branch had
already advanced to f261896e and its full qualification had succeeded.

Two earlier Windows runs remain failures: 36225556969 and 36227104972. The first
failed when a compiler driver inherited an empty isolated user profile; the next
failed when a PowerShell 7 -> Python -> Windows PowerShell child inherited the
wrong PSModulePath. The inherited fixes separate toolchain discovery from runtime
home isolation, clear only PSModulePath for explicit Windows PowerShell children,
and add native shell/compiler preflight. Existing product and installer bytes,
old assertions and time limits are unchanged. The final f261896e run succeeded
on its first attempt; that does NOT turn earlier candidates into passing runs.
This turn checked the earlier job failures but did not redownload their archives.

## Separate review finding and new development

**Acceptance coverage gap:** the original upgrade script created its receipt
only AFTER upgrading. It tested old fact preservation and subsequent receipt
retention on uninstall, not preservation of PREEXISTING receipts across upgrade.
This was a test coverage defect, not demonstrated product data loss.

I added `.ci/test_n48k_existing_receipts.py` and a separately pinned native Windows
workflow in commit `a21461380cb5408183716541ec9bc036a03092cb`, tree
`08ac0cf2f3fd341edd4f08ee0d699071b3d09d95`. The supplemental plan records this exact
distinction. The new workflow downloads the original digest-pinned CI artifact
and tests the same already-qualified ZIP: no new EXE, package rewrite, inherited
test edit, or permission bypass is involved.

With BOTH PowerShell 5 and 7, for BOTH Claude and Codex fixture configurations, the
new regression creates a fact, an active receipt and a withdrawn receipt using
the OLD N47X executable. It snapshots full fact, usage summary and all/current/
withdrawn receipt views BEFORE installing the new version. It then upgrades,
rolls back to N47X, upgrades again, and uninstalls. Every stage compares the entire
snapshot, not only its count. Default-brain and unrelated configuration checks,
installation Status checks and idempotent duplicate reporting are included.
All subprocess requests, outputs, exit codes and snapshots are retained.

## Original fixed-source execution and artifact review

Workflow 36228428928 has two completed successful jobs: Windows 108366806549 and
portable 108366806605, attempt 1. The portable job checks packaging, not a Linux
installer; it must not be described as a second native Windows runtime execution.

| Gate | Observed evidence |
| --- | --- |
| Native product build | Fresh pinned Windows C++ build and original 60 registered test groups pass. |
| Packaging units | Each OS and each Python mode: 25 tests, no skips; portable also passes 26 inherited delivery unit tests. |
| Assembly | Two identical ZIPs; all 51 members, source bytes, executable and construction receipt independently checked. |
| Actual extracted package | 23 ordered qualification steps with expected exits; includes 12 cost examples, package-local bridge 27 and prior acceptance 48 tests in both Python modes. |
| Installer snapshots and recovery | PowerShell 5/7 each pass the unchanged 24-case snapshot suite and 60-case recovery suite. |
| Original upgrade checks | PowerShell 5/7 each pass 50 checks; the preexisting-receipt limitation above is explicitly corrected by the new supplement. |
| Retained native/application regression | The extracted EXE passes the unchanged 55-step driver, including lifecycle 16 and application 18 nested steps. |

The Windows original artifact is 46,268,002 bytes, SHA256
`42677bf75e3ea3a1d94a9cbae1e8bc3bd5122991a015112913928c2e02b844b0`.
The portable original artifact is 12,734,098 bytes, SHA256
`0ddfedefefdde1d52d74df652bcf55087f94d66779f6268d4cd423c7b1e8dbb6`.
Both were downloaded, CRC-checked and compared against their externally retrieved
metadata. The 1,422-file source tree was reconstructed from exact Git blob bytes.
Windows source differs only in 1,407 exact LF-to-CRLF conversions; the 1,414-file
product snapshot independently matches the frozen product tree.

The independent metadata review checks original registration/log consistency,
ordered driver inventories, every recorded log hash, expected error exits,
environment scopes and both shell identities. Existing readback validators were
then run on 12 accounting, six lifecycle, one MCP and four application receipt
report sets. All 23 semantic readback commands completed successfully. Four
installer reports and the two original upgrade reports were validated separately.
The two package-local model-cost loopback reports were recomputed on Linux:
analysis/comparison-input bytes match, and source manifests match after excluding
ONLY the explicitly different native executable digest. This is semantic replay,
not local execution of the Windows EXE.

Two independent mutation runs, ordinary Python and Python -O, each reject all
152 controlled package/acceptance variants, including self-rehashed changed EXE
content, missing/extra files, bad ZIP framing, changed scope, omitted upgrade
checks, Boolean numeric aliases and modified raw output. These are bounded
negative probes, not proof against a fully colluding artifact producer/verifier.

## Supplemental native result

Both supplemental native runs have now completed successfully on attempt 1:
36235526784 (a2146138, windows-latest) and 36236062404 (b38c30bd, windows-2022).
The second commit is `b38c30bdb6c375831df886e9c78fc67cac2aedd1`, tree
`ffd16b9a6e905d01b8c23c81e8ab17c0696fea83`. While the first was observed queued,
the runner was fixed to Windows 2022 for another execution of the identical test;
the workflow also uses output redirection for its SHA marker. No test assertion,
PowerShell requirement, timeout, permissions, executable or ZIP changed. The
original queued run subsequently passed as well; no queued state was counted as a
pass and no failed attempt was retried or erased.

Each image executes BOTH PowerShell 5 and 7, each with 79 checks / 98 commands and
12 complete stage snapshots. All four groups pass, totaling 316 recorded checks,
392 commands and 48 before/after snapshots. These are repeated execution checks,
not 316 unrelated product features or customer scenarios.

Both supplemental archives were downloaded and independently checked for their
external SHA256, CRC, source marker and exact source tree (1,425 files, 1,410 exact
Windows newline conversions). Their candidate ZIPs are the same frozen package.
The separate raw-evidence reader reconstructs expected command order, checks OLD
receipt creation before NEW installation, matches saved snapshots to actual
stdout, and compares full receipt contents/timestamps/revisions at every stage.
It also checks native shell/installer Status and recorded source/executable hashes.
All 48 snapshots match. Configuration/default-brain byte preservation is checked
by the native test itself; those disposable files are not separately exported.

Two further local reader mutation runs (ordinary/-O) each reject 40 variants,
including erased old tombstones, changed timestamps, self-rehashed incorrect
stdout, moved receipt creation to the new executable and fabricated shell/state
metadata. No Windows executable is run in this local replay. The gap is closed
by actual native CI execution plus the independent raw-data review, not by merely
adding tests or obtaining an aggregate green status.

## Local errors and verification limits

The first two local reviewer attempts incorrectly assumed an LF package guide and
an extra nested log directory. Those assumptions were corrected to the original
Windows guide bytes and actual driver layout; artifacts were never rewritten and
checks were not relaxed. Both failing logs are retained. A combined replay shell
invocation hit its execution wrapper limit; its recorded per-command results and
later standalone lifecycle/application completions are retained. The interrupted
wrapper is not reported as a complete successful execution.

The new Linux receipt-fixture development initially parsed the plain `init` output
as JSON and used an unsupported receipt page limit of 100. Correcting the fixture
to the existing interface (`limit=50`) produced 64 checks / 79 CLI calls in each of ordinary and optimized Python. All
original failure records remain in the evidence package. This local check did
NOT run Windows installers and cannot replace the supplemental native gate.

The original N48K guide included in the fixed ZIP is not edited after testing.
Its internal MANIFEST legitimately remains `BUILT_NOT_YET_ACCEPTED`, the state at
construction. The separately issued ACCEPTANCE.json binds this exact unchanged
ZIP to completed original qualification, the supplement and the final review.
No signature or official release status is inferred from a JSON file or hashes.

## Final disposition

**PASS for the bounded N48K Windows integration candidate and the exact ZIP above.**

The original fixed-source package/runtime qualification, supplemental native
preexisting-receipt tests and separate raw-artifact review are complete. No known
unresolved blocking defect remains in this reviewed scope. This is not an absolute
absence-of-defects guarantee. Final acceptance is external to the unchanged ZIP,
with every source, native program, test and workflow identity retained separately.

Closing repository changes must contain only reviewed documentation, historical
snapshots and executed evidence indices. The product/package bytes and the newly
qualified supplemental script/workflow remain unchanged. Actual merge identity is
recorded in PR #52 and DELIVERY.json, not inserted into an earlier frozen CI result.

The package is an unsigned Windows x64 development candidate. Native CI is not the
user's Windows 11 PC. No real user brain or logged-in Claude/Codex session was
used; those names identify tested configuration fixtures, not verified semantic
memory consumption. Real model quality, full-pipeline costs, PG parity, signing,
stable-version acceptance and Issue #40's startup-timeout cause remain open.
The previous N47X public Release is unchanged; this is a separately delivered ZIP.
