# N46B operation and capability delta

Tested source: `2661e5205ba480c993210405d35c463efd8c6b6c`.
Evidence: [outcome review](nodes/N46B-HARD-AUDIT.md) and
[machine-readable result](nodes/n46b-evidence/RESULT.json).

| Area | Delta | Verification |
| --- | --- | --- |
| Shared Windows model HTTP | Bounded total network wait, response/request caps, partial-response rejection, explicit errors and safe cancellation lifetime | 51 native wire checks, 30 native input assertions |
| Chat timeout classification | Explicit transport result instead of elapsed-time inference | Production chat success/timeout/HTTP error/truncation fixtures |
| MCP operations | Zero additions/removals; registry and six-tool mode unchanged | Existing 17 MCP checks and complete 45-group regression |
| Model consent / capture / write authorization | Unchanged | Existing real process and both PowerShell consent tests |
| Storage schema | No migration or database-service addition | Existing memory/context process regression |
| Package evidence | Exact 45 registered groups and same-commit native HTTP report required | Seven gate unit tests and final Windows packaging success |

The historical OPS-PARITY-LEDGER.md is unchanged: this node does not newly implement
an operation or certify historical broad parity claims. Issue #2's HTTP transport
boundary is addressed, not the rest of its semantic retrieval, cost, host lifecycle
or PostgreSQL items. No full gbrain equivalence or new OpenViking module is claimed.
