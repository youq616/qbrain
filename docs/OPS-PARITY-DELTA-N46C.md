# N46C operation and performance delta

Tested source `728c2502ff66cedae218722458cac47f957236fc`. [Outcome review](nodes/N46C-HARD-AUDIT.md) and
[machine-readable evidence](nodes/n46c-evidence/RESULT.json).

| Area | Delta | Acceptance |
| --- | --- | --- |
| Vector candidate selection | Exact full scan; at most K retained best-page candidates | Native differential/property checks, same results and scores |
| Hybrid backlink score | Source+slug counts in batches of 100; no link-content materialization | Native SQL trace and field authorizer; 554 queries to 6 in fixture |
| MCP operations | Zero additions/removals | Existing registry and boundary regression |
| Storage / consent / permissions | No migration, new service, opt-in or authorization change | Existing process and PowerShell checks |
| Package acceptance | Exact 46 groups plus same-source/tree Windows benchmark | Eight evidence-gate tests and native package success |

No ANN, embedding/result cache, semantic quality, billing or full gbrain-equivalence
claim. Historical OPS-PARITY-LEDGER.md remains unchanged because this does not add
an operation or validate its broader historical claims. Windows timing is synthetic,
not an end-to-end Agent speedup or total-memory measurement.
