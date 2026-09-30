# N48Q — PostgreSQL paths for existing fact and explicit-use APIs

Existing FactStore fact/evidence, explicit relations, lifecycle and use-receipt
operations now support the bounded public/UTF8 PostgreSQL path. No MCP operation
is added or registry count changed. Complete quotes, source binding, expected
revisions, explicit retirement, historical/withdrawn receipts, full-set pagination
and atomic selected batches retain their existing semantics. Missing final support
removes derived copies; use reporting is not host/model-consumption certification.

Runtime4f8b470f has original full qualification. Supplement28d64ae7 adds separately
written actual-process review and native Windows/Linux/sanitizer qualification;
runtime and prior test bytes are checked unchanged before/after execution.
[Outcome](nodes/N48Q-HARD-AUDIT.md) and [results](nodes/n48q-evidence/RESULT.json)
record exact execution scope. Actual merge is PR59. Same DSN/other brain is not
RLS/tenant isolation. PG Hook, real-client/model, full-project and signing/stable
acceptance remain open. Prior ledger rows are unchanged.
