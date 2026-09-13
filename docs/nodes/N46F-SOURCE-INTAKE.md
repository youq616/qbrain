# N46F source intake, September 13, 2026

## Evidence received and missing source

The owner supplied an archive containing report.md, summary.json, issues.md,
handoff.json, five logs and a nested report ZIP. Neither archive contains the
actual patch, a Git bundle, or changed source files. Local commits reported are
plan a0adf373c686d1bbc1845d58d84fb6d1b0da372c and implementation
9426692fe40ba41880f9312534f02fde0459cfad, based on
48a498bbf2ea14b39f1023cd1d67e30fb98848f9. They are not yet remotely reviewed code.
Do not reconstruct or overwrite those changes merely from their descriptions.

The supplied old-binary test report supports five passing memory substring
checks followed by the expected failing search-phrase check. Its aggregate
counts nevertheless say total=6, pass=6. The test harness and package gate need
review after source intake: expect total=6, PASS=5, FAIL=1 for that run. This is
not evidence that the actual patched C++ compiled or the full new suite passed.
The separate top-level summary of 16 checks counts 9 PASS, 1 BLOCKED and 6 NOT_RUN.
The old memory_read attribution was correctly withdrawn; ordinary search is the
reported CJK substring gap. No credential or private log is copied into this repo.

## Owner-authorized engineering plan and review

Scope: an offline exporter only. Repository-side writes are available in this
continuation; the local machine does not need GitHub authentication to hand over
code. Exact source is required before production review or native CI.

Design accepted by ChatGPT engineering self-review: pin the existing baseline,
two commits and local branch; verify ancestry and allowlisted regular UTF-8 source
paths; reject dirty worktrees and changed tips rather than resetting them. Export
an incremental Git bundle and a binary-safe format-patch with hashes and a manifest.
Use only local Git object reads/bundle creation, no credential helper, network,
checkout, index edit, push or commit. Ordinary commit author metadata is retained.
No auth configuration, databases, acceptance logs or whole repository is copied.
Pattern checks are not a full DLP guarantee; examine the exported code before
publishing it. Import into the already-known baseline; never execute imported
workflows before reviewing their permissions and contents.

The exporter is tools/handoff/export_n46f_source.py. Python 3.10+ and Git are
already sufficient; there is no compiler requirement. Download it at the exact
verified repository commit, validate its externally supplied SHA256, then run:

python -B export_n46f_source.py --repo <existing-qbrain-n46f-worktree> --output <new-directory-outside-repo>

Output is one qbrain-n46f-source-handoff.zip containing n46f.bundle, n46f.patch,
manifest.json and README.txt. Export success is SOURCE_EXPORTED, never a product
PASS. Provide that single ZIP back to the repository-side developer. No local
GitHub login, coding, model requests, Codex auth changes or repeated host tests
are needed for this handoff.

## Validation and limitations

Twelve local helper tests passed using disposable Git repositories, including
exact commit-hash roundtrip, source preservation, wrong origin/tip/commit range,
private-path and key-pattern refusal, non-UTF8/NUL and size bounds. A dedicated
Windows/Ubuntu workflow executes the same tests. Its actual outcome is recorded
in Actions; local results alone are not Windows acceptance. No N46F production
source, existing tests, CMake or database schema is changed by this helper.
Rollback removes these additive helper/test/document/workflow files.

Git bundle reference: https://git-scm.com/docs/git-bundle
Git format-patch reference: https://git-scm.com/docs/git-format-patch
