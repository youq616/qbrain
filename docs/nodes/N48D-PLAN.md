# N48D — Explicit isolated MCP runtime check

2026-09-21. Status: done for the approved source-module scope.
Base main:88c949bad4ea7e15e204008668fde4fdf85e13d2.
Original plan:4104dbcc40bde994ca6f931ba151ec56f6e16391.
Separate plan review:0876ac9c82c0da79eef28e5d697214db439f1a97.
Accepted source:d9cf7111f4b751998cf5a7e1d4a2bd92e747eca7.
Accepted tree:5c5e6949fde975cf461671b9b2aae8234a076dbe.
Fixed push/attempt1 run:35595500574.

The [original approved plan](n48d-evidence/APPROVED-PLAN.md) remains byte-identical.
[N48D-HARD-AUDIT.md](N48D-HARD-AUDIT.md) maps its gates to actual Windows/Linux
execution, retained failures, artifact readback and separately authored edge probes.
This continuation finished the existing PR45, not a duplicate implementation.
The owner explicitly requests coordinator self-review; no subagent or third-party
review is claimed. Actual merge identity belongs in PR45, distinct from the build.

The native preview/run module qualifies the approved executable's legacy stdio
MCP lifecycle in a separate home/environment. It does not call tools, send model
requests, supply a real brain or certify agent loading. Directory isolation is not
an OS sandbox. N48A/B/C remain separate unmerged work. No public release, stored
schema, default permission or Issue40 root-cause result is changed by this closure.
