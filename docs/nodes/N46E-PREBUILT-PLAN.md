# N46E — compiler-free local acceptance

Scope: only youq616/qbrain, baseline main 3751d4da5cc7eb5d197455ffd6e245b530c51c09.
Owner requested repository-side work here and only necessary native tasks locally.
This node does not implement N47 or alter production C++/schemas/Agent settings.

The local report stopped before compilation because MSVC was absent. Separate
source-build acceptance from execution of the exact existing tested package.
Provide an offline pinned-archive validator, exclusive new-directory staging,
a PowerShell entry point, opt-in isolated native memory smoke, accurate status
counts and explicit not-tested host/full-regression markers.

Acceptance: reject wrong bytes/source/EXE, unsafe/duplicate paths, symlinks,
manifest errors and oversized expansion before writing; preserve an existing
output; clear sensitive/config state in a child environment without changing the
parent; count statuses from actual records; never call a Linux stub native PASS;
exercise the same pinned Windows EXE and both PowerShell entry points in CI.

Engineering design review by ChatGPT under the recorded owner override: accepted
for this scoped implementation. Review the fixed digest as the trust anchor,
not the archive's own manifest. No new automatic downloader, package manager,
paid provider, capture opt-in or bypass for host trust. The native smoke is not
real Agent lifecycle acceptance. Python remains an acceptance/CI dependency.
Rollback deletes these additive tools/tests/docs only; no database downgrade.
Outcome and remote workflow state will be reported from actual execution.
