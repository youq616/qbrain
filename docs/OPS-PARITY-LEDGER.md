# Ops Parity Ledger

Current reviewed node: **N47N**, 2026-09-18 UTC.

This node changes only the existing search CLI grammar and its argument
handoff. It adds **zero operations**, schemas, provider permissions or Hook
defaults. Explicit query data and delimiter tails cannot be reinterpreted as
control options. Existing search scope, ranking and MCP authorization remain.
Unknown/duplicate/missing/mixed/invalid syntax is intentionally rejected before
opening a brain rather than preserving the former silent permissive behavior.

The complete inherited operation inventory and all historical qualification
notes are preserved byte-for-byte in [OPS-PARITY-LEDGER-N47M.md](OPS-PARITY-LEDGER-N47M.md).
Its historical counts and implemented/deferred labels retain their original
scope; N47N neither recounts them nor turns them into full upstream parity.
The earlier N47L inventory is also retained in OPS-PARITY-LEDGER-N47L.md.

N47N uses fixed source a587e175 and source tree 3c2b5ef5; N47N/N42/N44 required
native and portable gates passed. Outcome review is owner-authorized separate
coordinator self-review, not a separate agent. See [N47N delta](OPS-PARITY-DELTA-N47N.md),
[final audit](nodes/N47N-HARD-AUDIT.md) and [current status](../CURRENT-STATUS.md).
No public package is released by this node. Live PG, full-project completion,
new host/model consumption and comprehensive source/ACL parity are not claimed.
