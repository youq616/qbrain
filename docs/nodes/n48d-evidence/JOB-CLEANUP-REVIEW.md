# Separate Windows owned-job cleanup observation review

2026-09-21. Source-review hardening approved by the coordinating assistant under
the existing positive-cleanup requirement. Not a claim of reproduced user data loss.
The process result originally waited only on the direct child after requesting Job
termination. Direct-child exit does not independently observe every process in the
owned Job. Require both direct-process signaling and Job ActiveProcesses==0 within
the existing2000ms cleanup waiting budget before marking cleanup successful or
removing the workspace. A failed query or deadline keeps the workspace and returns
cleanup_incomplete; do not add arbitrary PID scans or increase the protocol budget.

Microsoft documents TerminateJobObject as termination of the associated processes,
with TerminateProcess semantics, and exposes ActiveProcesses through basic Job
accounting. This extra positive observation is required for the final Windows code;
the earlier73 direct checks and incomplete process run do not certify it. Re-run
new and original native tests on the final candidate. Linux code and behavior are
unchanged; recompiling the conditional change produced the same local Linux EXE
hash. This is not an OS sandbox or a guarantee against escaped malicious children,
uninterruptible kernel work, all ACL races or hostile administrators.
