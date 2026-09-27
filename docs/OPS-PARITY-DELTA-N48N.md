# N48N ledger delta — CLI maintenance only

Native CLI `database check --database PATH` inspects one committed read-only
snapshot in private memory: seven bounded structure/reference/FTS checks, exit0/1/2
for complete pass/findings/operational error. No repair, default-brain change or
MCP operation is added; existing registry operation counts are unchanged. Qualified
b6d0e800 passed native Windows/Linux gates and separate raw-evidence review; see
[nodes/N48N-HARD-AUDIT.md](nodes/N48N-HARD-AUDIT.md). Inventory is not full DDL or
application parity; empty WAL/SHM bookkeeping remains possible. PG, real client/model,
signing/stable and Issue40 remain separate. Prior ledger text is unchanged.
