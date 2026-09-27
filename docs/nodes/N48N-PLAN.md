# N48N — pinned-backup full-text search audit

2026-09-27. Status: approved after the separate plan review below.
Base: main f83d1b138c88d1413d38a3541d4c929ac82a3b0f, tree 5dbd64732245524648e011572bd4499a4f112e56.

## Goal and bounded contract

Add native `qbrain backup audit-search --backup DIR --expect-sha256 HASH
[--timeout-ms 10000]`. A structurally valid backup can still have a stale external
content FTS5 index. Check the canonical pages_fts against all pages (including
soft-deleted pages, as the existing triggers index all rows) and verify the three
canonical insert/update/delete maintenance trigger definitions. No rebuild or
repair, live database selection, registry initialization, MCP tool or schema migration.

First retain N48M exact inventory, external manifest pin, structural/FK validation,
256 MiB database cap and deadline. Audit only the verified bytes deserialized into
an isolated in-memory SQLite connection. Disable schema triggers on that connection;
use fixed SQL, no SQL supplied by the caller. Run FTS5 integrity-check with rank=1,
not COUNT(*) on an external-content table (that does not read the index).

Recognize only the canonical pages table rowid/columns and canonical FTS5 DDL.
Unknown layouts produce UNSUPPORTED, never a green success. Missing/noncanonical
maintenance triggers or SQLITE_CORRUPT_VTAB produce FAIL. Errors/timeouts give
structured failure, never a partial PASS. Exit 0 = PASS, 1 = FAIL, 2 = input/runtime
error or unsupported schema. Output metadata only: digests, counts, check status,
no paths, slugs, titles, body, SQL or SQLite error strings. Full application semantic
validation, index performance/ranking, embedding integrity and provenance remain false/unclaimed.

## Falsifiable acceptance

1. Canonical empty and populated snapshots pass; all three indexed columns,
   Unicode, NUL, multiple sources, large rows and soft deletion are exercised.
2. Independent fixture makes missing/stale/phantom index entries while ordinary
   backup verify succeeds. audit-search must fail and leave every input byte unchanged.
3. Correct index with deleted/no-op/wrong-table triggers fails; noncanonical FTS
   configuration and alternate content tables are UNSUPPORTED, not silently skipped.
4. Digest, malformed CLI, links, timeouts and sidecar rejection remain fail-closed.
5. Actual Windows/Linux product invocation, direct checks and sanitizer run;
   original backup tests, Windows60/core and existing55-step regression retained.
6. Separate post-implementation review includes different black-box fixtures,
   command/output readback, exact source/binary identity and original failures.

## Delivery and rollback

New header, narrow early main.cpp dispatch/help, direct/process tests, pinned CI,
Chinese guide and plan/outcome review. Update operational ledger and current status
only against observed evidence. Retain existing binaries/releases and N48M behavior.
Rollback is revert the module commit; there is no persistent data/schema change.
No user data, model calls, credentials, paid services, PG, signing/stable release or
Issue40 closure. Parent ACLs/process memory are not a hostile filesystem sandbox;
bounded SQLite progress does not hard-cancel OS I/O/hash/allocation. Memory use is
several copies of at most256MiB plus SQLite working memory, not a fixed RSS guarantee.
