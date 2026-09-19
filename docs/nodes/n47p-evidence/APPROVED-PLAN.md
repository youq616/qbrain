# N47P — Bounded, preflighted installer recovery

2026-09-19. Status: approved for implementation after N47P-PLAN-AUDIT.md.
Base: 4734fe840081bc2215485e43031fc967b5a93c9d.
Owner requests continued development and a separate coordinator outcome review.

## Goal and scope

Close daily-use v1's installer interruption-recovery gaps, not another general CLI
rewrite. Existing Install-QbrainMemory.ps1 reads every file, including pending.json,
with a 2 MiB limit although a journal contains before/after images of several files.
Recovery checks paths/current images before writes but not all image types, duplicate
paths or temporary destinations. Correct those gaps while retaining journal version1,
original hooks/MCP definitions, opt-in consent, Windows/PowerShell5.1/7 and no new
runtime dependency. Do not alter C++/schema/ledger or published N47O assets.

## Falsifiable acceptance

1. Normal configuration images remain limited to 2 MiB UTF-8 each. Pending journals
   have a separate 32 MiB serialized UTF-8 cap. Bound new serialization before
   brain init/backup/transaction writes so the installer cannot produce a journal
   that it refuses to read later. Overflow must leave configured files untouched.
2. Fully validate version1, nonempty bounded changes array, exact member types,
   unique owned paths and null-or-string before/after images. Preserve empty strings
   versus absent files. Invalid journals remain for inspection and cause no rollback
   writes, no brain init and no backup creation (the existing lock is not new data).
3. Preflight all final and .tmp destinations before first recovery write; reject
   directory/reparse collisions. Compare all current images before recovery. A
   deterministic later-member error must not roll back an earlier member first.
   Unexpected I/O failures can still interrupt multi-file recovery; keep the journal
   for a safe next retry, never claim a filesystem-wide atomic transaction.
4. Recover a valid journal larger than2MiB, retain legacy small journals, and exercise
   absent/empty/text images, interrupted multi-file rollback, external edits and
   retries. Preserve original installation/upgrade/uninstall/consent/Unicode tests.
5. Native PowerShell5.1 and7 tests on isolated synthetic Windows directories must
   reject the baseline with the new regressions and pass the fixed installer. Use
   the fixed released EXE for fast installer tests, and separately fresh-build/run
   the original native unit suite. No real owner brain, client login or model call.
6. Separately review code and test coverage, record actual failures/fixes and native
   evidence, then merge only if scoped gates pass. No new release in this node;
   old released installer explicitly remains unpatched until next delivery.

## Review, security and rollback

Current explicit owner request authorizes coordinator separate plan/outcome self-
review, not a fabricated independent agent. Tests/gates are not waived. Rollback
is a scoped revert, no migration. The journal is an owned local recovery record,
not cryptographic authentication against an administrator able to rewrite files.
The change does not promise binary-exact BOM/encoding preservation for legacy text
journals, hard-link defense or atomic snapshots against concurrent external writers.
Document these existing boundaries. Update the v1 roadmap by evidence, not automatic
round countdown; pending host/quality/PG work remains visible.
