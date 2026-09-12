# Current continuation: N46D contracts and queue repairs

Tested source `464045e2451ec71ca37dd8e92bcf4ac0d9325a0b`. Development run 34682889565 and N42 run
34682889570 completed successfully. The dedicated queue suite reports 40 scenarios /
776 assertions (including repeated simultaneous-claim races), in addition to the 47
original native registered groups and existing process/wire/PowerShell gates.

Owner-authorized self-review supersedes the earlier external-review blocker.
[Outcome review](../nodes/N46D-QUEUE-HARD-AUDIT.md) and
[current evidence](../nodes/n46d-queue-evidence/SUMMARY.json) are authoritative for
this milestone. The 6f88c073 package predates queue repairs and is not current.
No new migration, required service, provider consent or MCP permission. Unsigned
development, not complete PG/live-provider/signed-in Win11 acceptance.

---

# Current continuation: N46C exact retrieval

Tested source `728c2502ff66cedae218722458cac47f957236fc`. [Run 34661114802](https://github.com/youq616/qbrain/actions/runs/34661114802)
passed the native Windows/portable/source gates and exact 46-group package gate.
[Outcome and failed-check analysis](../nodes/N46C-HARD-AUDIT.md),
[numeric source-bound evidence](../nodes/n46c-evidence/RESULT.json).
Full scan and exact outputs remain; candidates bounded to K and backlinks counted
in source-scoped batches. Synthetic timings are not semantic quality, billing,
process-RSS or end-to-end latency promises. Native Win11 host, PG and signing
remain unverified. The records below describe older source/artifacts.

---

# Current continuation: N46B native HTTP boundaries

Tested source `2661e5205ba480c993210405d35c463efd8c6b6c`; final run
https://github.com/youq616/qbrain/actions/runs/34626277700 completed successfully.
Windows 45 registered groups, 51 native HTTP checks, all prior memory/context/MCP/
Hook process tests, both PowerShell installation/transport/consent suites and the
same-commit package gate passed. See [N46B outcome](../nodes/N46B-HARD-AUDIT.md),
[upgrade notes](N46B-UPGRADE.zh-CN.md), and [evidence](../nodes/n46b-evidence/RESULT.json).
This is a scoped unsigned development build, not full-project acceptance.
The following content is retained as the historical N44/N45/N46A record; its old
EXE hashes and timeout wording do not describe the N46B artifact.

---

# Qbrain verified memory preview

Repository: youq616/qbrain. Original upstream is unchanged.
Tested code: `5ee79dfd5ab2512f024fefc9054bd3da12d64f1f`.
Workflow: https://github.com/youq616/qbrain/actions/runs/34616855167
PR #1 (N42) and #3 (N43/N44A) were merged before this wave. PR #4 carries N44B, N45 and scoped N46A. GitHub's PR state, not this prose, determines whether the latest wave is merged.

## Verified scope

Windows/MSVC complete application, 44 registered regression groups, 44 real memory checks, 17 prior MCP checks, 69 hook fixtures, 65 context fixtures and six local-configuration checks. On EACH PowerShell 5.1 and 7: 69 installer, 16 consent/path and eight transport checks passed. Packaging also revalidated the logs and launched the identical executable in an isolated directory with only System32 on PATH. The old optional PostgreSQL real-DSN integration was skipped, not certified by its enclosing group's status.

C++ memory/context ASan and UBSan checks passed locally (82 + 37 assertions); this is not sanitizer coverage of PowerShell, the entire bundled C library, live WinHTTP or a logged-in host. See `../nodes/n44-evidence/RESULT.json` for hashes and exact limits.

## Failures found and fixed

Native CI found three genuine defects before delivery: PowerShell's null backup argument for File.Replace, project configuration accidentally mirroring brain_id into global config, and Process.Start inheriting a different working directory than Set-Location. Repairs preserve atomic replacement, add explicit DB-only `config set ... --local`, and set the child filesystem working directory. Original assertions remained; no failing regression was removed.

Capture also now requires the installation's own opt-in even for an already salient shared brain. Reinstall without opt-in returns to recall-only. Case-alias checks use filesystem identity. Installer support for distinct case-sensitive NTFS A/a names is not certified.

## Artifact and usage boundaries

The EXE SHA-256 is `3bd43e8a099d9b4136aa0b96bd941fed7366a320a09b8bd253a0f272194ecdf8` (3,792,384 bytes, PE32+ x86-64, unsigned). Its upstream internal version was not changed; identify this preview by SHA and manifest. Historical dist installers are not this executable.

The original CI package contains a model-timeout documentation error, corrected in WINDOWS-MEMORY.md. A documentation-only repack must retain executable and script bytes and preserve the original manifest/provenance. Model drain checks its budget between calls; the configured 60,000 ms transport timeout is not a guaranteed total wall-clock bound.

## Not completed by this milestone

Real logged-in Claude/Codex model consumption, Win11 user-environment acceptance, online model quality/billing, new PostgreSQL memory/context parity, Cursor automation, semantic cross-session conflict merging, ANN, complete multi-tenant ACL/DLP, and full gbrain equivalence. Default L0/L1 is an extractive preview. Synthetic byte/latency results are not task-quality or token-cost results.

Roadmap remains open in issue #2. Node audits are owner-delegated ChatGPT reviews, not independent Claude Code audits. Full project completion is not claimed.
