# N48P — existing context operations gain PostgreSQL support

context_read/context_write and context CLI now support the declared public/UTF8
PostgreSQL path, preserving previews, version-bound raw pagination and permissions.
No registry operation is added or recounted. This is not fact_store/Hook/full PG
parity, RLS or real model-consumption acceptance. Qualified136a4828, actual merge
PR58. See [outcome audit](nodes/N48P-HARD-AUDIT.md) and
[usage](integration/POSTGRES-LAYERED-CONTEXT.zh-CN.md). Prior ledger rows unchanged.
