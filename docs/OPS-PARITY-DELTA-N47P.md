# N47P operation delta — installer reliability

2026-09-19. Accepted source9feed7c74926d53a7b2a7b21391af02275799f51;
fixed native run35415626607. No new operation, C++ implementation, schema,
MCP/source permission, Hook default or implicit capture/fact consent.

Only the project installer changes among inherited product/scripts files:
bounded32MiB aggregate journal with2MiB individual images, whole-journal and
all-destination preflight, retryable partial I/O recovery, and one input snapshot
for parsing/ownership/before images/backups. External edits observed by write-
preflight cannot be authorized through a later before-image reread.

Each native PowerShell5.1/7 environment passed24 snapshot cases,60 recovery cases,
and retained69/16/8/33/33 original installer/consent/transport/fact/promotion checks.
Exact prior snapshot baseline20 failures and published recovery baseline34 failures
are overlapping negative cases, not separate bug counts. Fresh60 native groups pass;
live PG remains SKIP-PG. See [final review](nodes/N47P-HARD-AUDIT.md).

Reviewer is the owner-authorized coordinating assistant in a separate engineering
self-review, not another agent or third party. No public package was changed;
the N47O installer remains unpatched there until a later integrated delivery.
The canonical ops ledger and frozen inventory remain intact, not replaced by this
delta. Non-atomic text-journal/race limits and unfinished v1/broad roadmap remain.
