# N47P plan review

2026-09-19. Verdict: PASS for implementation. Reviewer: coordinating ChatGPT in a
separate pre-implementation engineering review under current owner authorization.
Not a separate subagent or third-party/Claude Code review.

The source establishes a real recoverability mismatch: Raw applies2MiB to both
single configuration and aggregate before/after journal. The plan separates the
bounded serialized envelope from each decoded image and requires checking a newly
serialized envelope before any transaction effects.32MiB is a chosen installation
budget, not unlimited JSON support; escape-heavy inputs exceeding it are refused.

The second gap is validation ordering. Current recovery validates only allowed path
and current image. Validate the entire schema, duplicate paths, image encoding/size
and deterministic final/temp path collisions before writing any member. Preserve
version1 null/empty semantics and support old valid journals. Keep unexpected I/O
failure retryable; preflight cannot eliminate races or grant cross-file atomicity.

Windows/Powershell5.1/7 fit, no new dependency, consent/source/DB unchanged. Test
normal and adversarial files using synthetic data; original installer suites remain.
Run a fresh original native regression job separately and actual fixed/baseline
installer tests on both shells. No need to repeat logged-in client tasks to test
this repository-local defect. Exact native runs/exit/report identities are required
for closure. No unresolved P0/P1 plan issue; existing encoding/race limitations are
explicitly outside the change rather than mislabeled solved.
