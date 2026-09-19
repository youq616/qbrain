# N47W separate plan review

2026-09-20. Reviewer: coordinating ChatGPT, owner-authorized separate engineering
self-review; not a separate subagent, Claude Code or third party.
Verdict: APPROVED. No blocking plan finding within the bounded bridge scope.

Issue40 supplies a concrete diagnostic gap, not a proven root cause. Preserve its
failed attempt and successful unchanged retry; do not close it merely because
controlled timeout fixtures pass. New metadata must have a strict allowlist and
nullable unknowns, and must never include raw errors or streams. Default result
shape and original timeout strings remain compatible; success diagnostics opt in.

The current input wait uses the entire timeout even though the stopwatch already
includes startup. Align that wait with the other phases' remaining budget, without
claiming cancellable synchronous OS startup or a hard end-to-end time ceiling.
Preserve original concurrent stdout/stderr readers and finite cleanup behavior.
Add native child fixtures for independent input, process and output-drain stalls;
retain old suites unchanged. Test-only descendant cleanup must not become a new
production process-tree kill. No secrets or paid requests in CI.

Official references checked: Microsoft Process.WaitForExit(Int32), StandardOutput
and Exception.Data documentation. Finite process exit wait and asynchronous output
completion are different observations. A returned process handle does not prove
application startup or host consumption. Final outcome needs original Windows
artifacts plus a separate code/privacy/compatibility pass, not invented local
PowerShell execution. Current user explicitly requests coordinator self-review.
