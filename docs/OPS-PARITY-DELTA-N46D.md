# N46D candidate capability delta

Tested source `6f88c073ad8332e0e629d3ab33ab6cd0b621451b`; PR #9 remains
pending independent review. This is not a new operation or full parity claim.

| Area | Change | Automated evidence |
| --- | --- | --- |
| Embedding response | Bounded all-or-nothing indexed float batches; model label checks | 65 unit and 26 native wire checks |
| Production retrieval | Active model and dimension predicates, source/deletion preserved | 11 real CLI/MCP checks |
| Compatibility | FTS retained; no legacy relabelling/deletion or automatic re-embedding | Native process tests |
| Validation | N42 adapter repaired and included before merge | Two successful workflows and 47 native groups |
| MCP/storage/runtime dependencies | No new operations, schema or required service | Existing regression retained |

See nodes/N46D-HARD-AUDIT.md and nodes/n46d-evidence/SUMMARY.json.
No independent audit PASS or node-done status is claimed by this ledger.
