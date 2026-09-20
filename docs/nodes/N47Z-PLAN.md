# N47Z — Atomic receipt batches

Recorded 2026-09-20 UTC. Status: done for the approved source module.
Base main:82e1f4c3872b5e3813b68f94ed925849b1e6b7a0.
Original persisted plan:bd559fff55228faf469123e5b34e200e9145b1b4.
Continuation approval:25311885a7ebb80e5acdfa3d530fb4cdc7a6f065.
Accepted product/tests:7898dec68b5162b33a193cb30295bdd1744e5269.
Accepted tree:83312db93cd4302c2e98cfbc92b0266b38939be3.
Fixed push/attempt1 native run:35516145384.

The [original approved plan](n47z-evidence/APPROVED-PLAN.md) is preserved unchanged.
[N47Z-HARD-AUDIT.md](N47Z-HARD-AUDIT.md) maps every gate to code and actual evidence.
The previously local-only module and blocked write history are not retroactively
called accepted. PR44 holds actual final merge identity, not the original build ID.

The module provides read-only canonical previews and explicitly approved report/
revoke batches of up to32 receipts across8 facts in one source. Receipt updates
are atomic; module initialization/backup is separately bounded. The final guard
preserves caller-owned explicit and implicit transactions;18/41 direct tests run
on both platforms, separately from the original Windows60 registered groups.

A final independent reference-ledger test runs24 mixed batch rounds through actual
persistent MCP, checking all summaries/pages. Existing89/123/72/75/71 and original
process suites are retained. Review is the coordinator's separately performed,
owner-authorized engineering self-review, not a subagent or third-party guarantee.
No new public package, real model/client result, PG or signing approval is claimed.
