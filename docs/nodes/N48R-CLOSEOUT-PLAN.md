# N48R closeout plan

2026-09-30. Intake runtime: 45a238534e67c173b6baa4f2ed257f6117b72044.
Main now contains N48Q at b4793e2a1694fbd2668aaf5880f51b4c5dc34bff.
Status: approved after the separate plan review below, before supplemental implementation.

Complete the existing PostgreSQL Hook module rather than introducing an unrelated
feature. Retarget PR60 to main, keep the qualified runtime unless a demonstrated
blocking defect requires repair. Independently verify both original CI archives,
source-tree identity, raw Hook requests/responses and retained regression records.
Compile the actual source locally and run SQLite native/Hook regressions and
sanitizers. Add separate process tests (no producer imports) for permission barriers,
full-quote composition, reset/dedup, withdrawn-quote suppression, diagnostic privacy,
failed PG admission with a populated SQLite fallback, empty/unknown PG schema, and
same session+same item across two actual PostgreSQL databases. Execute the additional
matrix on native Windows/Linux; synthetic hosts are not signed-in clients.

No real brain, secret, model call, installer or release mutation. PostgreSQL review
uses fixed disposable loopback databases only. Capture, fact promotion, external
inference and MCP writes remain separate permissions. A new review failure stays
recorded; no silent test/timeout weakening. Runtime changes would require a new
full original native qualification, not merely the supplemental test.

## Separate plan review

Reviewer: owner-authorized ChatGPT coordinator, self-review, not subagent/third party.
Reviewed the original approved N48R plan, runtime admission and private snapshot
reader, existing tests and qualified artifact identities. The extension tests gaps
in effective database dedup and error/no-fallback behavior, not new public features.
Full original qualification stays bound to 45a23853 and may only be inherited with
an exact runtime/test/build comparison. Supplemental execution results will be
reported separately. Missing PG, failed compiler or unknown evidence blocks a pass.
Verdict: PASS for this closeout plan. No known blocking plan findings.
