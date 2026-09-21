# Separate outcome findings and correction approval

2026-09-21. Same coordinating ChatGPT, separate engineering review. The first
native Linux product passed172 process assertions. A separately authored silent-
peer probe then reproduced a false observation: stdout_bytes=0 but messages_received=1
on initialization timeout. Cause: counter increased before receive completed.
APPROVED: increment only after a complete frame is actually received; preserve
zero on timeout/partial EOF and add separate regression. Preserve the old failed
report and executable digest, do not redefine attempted reads as received messages.

Additional source-review tightening before native acceptance: preserve the identity
of partially created workspaces and refuse unknown cleanup; avoid automatic temp
removal while process cleanup is incomplete; normalize pipe descriptors above
stdio; refuse automatic SIGCHLD reaping policies before spawning and do not signal
a process group after loss of child identity. Do not change global signal handlers.
These are ownership-boundary precautions, not claimed reproductions of data loss
or Issue40. Enforce original byte budgets and retain prior process tests unchanged.
Final positive/negative/native/sanitizer gates must run on corrected bytes.
