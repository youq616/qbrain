# N46D verified capability delta

Tested source `464045e2451ec71ca37dd8e92bcf4ac0d9325a0b`. Owner-authorized ChatGPT self-review and
source-bound native validation are recorded in nodes/N46D-QUEUE-HARD-AUDIT.md.
The external-review prerequisite was explicitly waived; no third-party audit is claimed.

| Area | Change | Evidence |
| --- | --- | --- |
| Embedding response | Bounded all-or-nothing float batches, model labels, image response cap | 65 unit / 26 native wire checks |
| Production retrieval | Model/dimension plus source/deletion filtering; FTS retained | 11 real CLI/MCP checks |
| Both embedding queue entry points | Batching, live-version checks, atomic progress, ownership fences and truthful counts | 40 scenarios / 776 assertions |
| Simultaneous writer contention | Scoped bounded SQLite waits; timeout restoration | 128 claim races and held-lock case within queue suite |
| Regression/package | N42 adapter retained, 47 exact groups and same-source native reports | Both native workflows and artifact readback |
| MCP/storage/runtime dependencies | Zero new operations, migrations or required services | Existing scope unchanged |

Historical ops-parity claims are not newly certified. This node is not full
gbrain equivalence, semantic quality, real PG/Win11 acceptance or a signed release.
