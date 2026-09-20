# N47W — Privacy-safe process-bridge phase diagnostics

2026-09-20. Status: done for the approved source feature; Issue40 remains open.
Base main: a3436c09e1eaed1d1e4eb6dcfaffbe19cc443eca.
Plan/review approval: ecdf4eac7dacd0c0c6583aa21ea4a973a7430570.
Accepted source: ea3b3f5a4ea1cd03541a5aedbf413ed0f1a3a6c1.
Accepted tree: 2243a7baccecf13e2150f04e74363fbe8684bb9a.
Fixed push/attempt1 workflow: 35477227325.

[Original approved plan](n47w-evidence/APPROVED-PLAN.md) is retained byte-for-byte.
The [outcome review](N47W-HARD-AUDIT.md) records native checks, original regressions,
source/artifact readback and the separately found test-cleanup correction. Review
is the coordinating assistant's owner-authorized separate engineering self-review,
not a separate agent or third party. Final merge identity belongs in PR41 rather
than being substituted for the original test source.

The bridge gains phase-only diagnostics and a shared remaining input-wait budget.
Default successful results and timeout limits remain compatible. No raw parameters,
paths, streams or environment values enter the diagnostic payload. No logging,
provider calls, client-consumption proof or new Release is introduced. The observed
historic Issue40 timeout remains unexplained; neither this diagnostic feature nor
its controlled failures retroactively establish or repair that root cause.
