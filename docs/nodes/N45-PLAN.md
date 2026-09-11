# N45 — Logical directory context, bounded previews and exact raw reads
Status: scoped preview accepted; see N45-HARD-AUDIT.md. Not full OpenViking parity.
Scope: independent C++20 design inspired by directory context, no upstream code.
Logical qbrain://source/{memories,resources,skills}/ paths are never disk paths.
L0/L1 previews explicitly extractive by default; optional model summary requires
persistent context.external_summary=allow and a configured provider. L2 returns
raw UTF-8 pages with byte-offset pagination and revision checks.
Required gates: strict source/URI and argument checks, JSON byte budget,
backup before optional SQLite schema, cache purging triggers on page changes,
no cache writes on read, snapshot revalidation before summary publication,
read-default MCP, compact six-tool profile rejects hidden tool calls.
No promise of model factual accuracy, comprehensive DLP, PG compatibility,
ANN performance or end-to-end fee savings. Fixture reports must label bytes.
Rollback: optional module can remain unused, page originals are unchanged.
Tests: UTF-8/CRLF reconstruction, stale revision, scope/permission denial,
cache invalidation, model consent/keyless behavior, compact definitions,
old 108-op ledger remains exact with four explicitly tested additions.
