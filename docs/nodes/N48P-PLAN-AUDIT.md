# N48P plan review

2026-09-29. Coordinator's owner-authorized separate design review, not third party.
PASS for implementation; no outcome acceptance yet.

The present 149-line context implementation explicitly rejects PG. This is a core
missing path named in the completion roadmap, not another peripheral evidence tool.
Reuse its URI/pagination/preview algorithm; specialize catalog, byte length, prefix,
DDL and transaction behavior. Merely translating BEGIN IMMEDIATE is insufficient:
PG read snapshots differ at READ COMMITTED and publishing must exclude page/policy
changes. Use repeatable read for observation, release before provider and table
locks for publication, matching N48O lock order to avoid introducing inverse order.

Reject unverified temp lookup, caller transaction commits and assuming DELETE
triggers handle TRUNCATE. Function is SECURITY INVOKER with qualified public writes
and fixed pg_catalog path; fail closed on unsupported schema instead of replacing it.
Direct tests must prove foreign source data absent, raw bytes reconstruct and model
callback is outside a transaction. Real PG native CI, not SQLite alone, is necessary.
No paid model, owner environment, new permissions or old installed ZIP changes.
References: PostgreSQL14 transaction-iso / sql-createtrigger and16 SET TRANSACTION.
