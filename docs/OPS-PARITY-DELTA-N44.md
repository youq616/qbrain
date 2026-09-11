# N42–N46A operation delta (current verified preview)

This supplements the historical `OPS-PARITY-LEDGER.md`; it does not relabel its heuristic subsets as upstream equivalence. Verified source: `5ee79dfd`, workflow 34616855167.

| Capability | Current disposition | Evidence / limit |
|---|---|---|
| Original 108 operation registry | Retained, frozen names independently compared | Native regression, no claim of complete upstream semantic parity |
| memory_read / memory_write | Implemented | N43 provenance, source/policy checks, default-deny writes; SQLite only |
| context_read / context_write | Implemented | N45 URI, budgets, revisions, cache/model consent; SQLite only |
| Full MCP profile | 112 registered tools | 108 baseline + four named extensions |
| Memory MCP profile | Six tools, list AND call filtering | 65 context-process fixtures; profile is not a complete multi-tenant ACL |
| Native Hook integration | Claude/Codex event-contract adapter | 69 process fixtures; not logged-in host/model consumption |
| Reversible Windows installation | Install / Status / Uninstall | PS 5.1 and 7 each 69 + 16 checks; host trust not bypassed |
| L0 / L1 | Default extractive, optional model output | Clearly labeled; model factual accuracy not evaluated |
| L2 | Exact raw UTF-8 pagination with revision | Reconstruction checks; partial output explicit |
| Batch extraction | Finite batch/retry caps, consent retained | Budget between calls; not a hard total deadline |
| ANN / real cost-quality comparison / Cursor automatic hooks | Not delivered | Roadmap #2, no speculative performance claims |

Historical read-boundary restrictions remain: MCP image filesystem search is refused until an ownership model exists; read-only synthesis cannot save implicitly. This wave is not an audit of every legacy operation. Synthetic evidence uses no user memory or live provider keys. Executable SHA and all counts are in `nodes/n44-evidence/RESULT.json`.
