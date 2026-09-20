# N47Y — Consistent, fail-closed use-receipt integrity

2026-09-20. Status: approved after the separate plan review below.
Base main: ad31f404ba5ca94b15dc992bf9f219fa572ab167.
Owner requests continued development and coordinator's separate outcome self-review.

## Observed defect and scope

On the retained native Linux product (SHA2567399af97dde5b97cc87667dc7e0e3fbdbf79b8b435fbfb62f01f2cb4cfd4e57e),
a public-CLI-created receipt was deliberately changed from TEXT usage_id to BLOB
inside a disposable database. The current summary counted it, the page API rejected
it, and reporting the same visible ID again added a second row. The tested receipt
headers are the same blobs used by current main. This is corruption/import hardening,
not a claim that normal application writes create such rows or a user database is damaged.

Unify bounded row validation for summary, pages and writes. Do not add lifecycle
policy, automatic cleanup, schema migration, ranking, provider calls or new APIs.
Normal valid-state output, pagination fingerprints, permissions and withdrawal
semantics must remain unchanged. Old releases are not replaced by this node.

## Falsifiable acceptance

1. One source/fact-scoped bounded reader validates actual SQLite types, lowercase
   64-hex IDs, order/duplicates, revisions and timestamps before counting/filtering.
   Reads consider exact byte-equivalent TEXT/BLOB scope variants and reject BLOB
   aliases rather than coerce them to a trusted identity. Check ID byte length
   before copying malformed large values. Do not scan another source's whole data.
2. All four public routes fail closed on a malformed target set. Reporting checks
   both the target collection and source-scoped requested-ID aliases under the
   existing IMMEDIATE transaction before inserting or declaring a duplicate.
   Same-ID alias attached to another fact cannot be silently reused. Revocation
   validates stored fact revision without requiring it to remain active/unexpired,
   so valid retired/archived/expired receipts remain withdrawable.
3. Reads/rejected writes preserve every application row, schema and backup file.
   No repair, deletion, implicit schema creation for an invalid claim, or silent
   normalization of imported/damaged records. Capacity4096 including tombstones,
   rollback, last-support cleanup and source/write gates stay unchanged.
4. Reproduce the original defect against a pinned baseline executable. New tests
   include BLOB aliases of usage/fact/source, malformed/oversize IDs, bad types and
   future revisions, cross-fact collisions, off-page corruption, independence of
   unrelated facts/sources, restored positive control, concurrency and valid-state
   baseline/new exact read results. SQL writes only in named corruption/cap fixtures;
   ordinary evidence and receipts come from public CLI. Save raw synthetic streams.
5. Compile actual changed C++ on Windows and Linux. Retain unchanged usage75,
   pages71 and original process suites; full original60 native groups and portable
   focused groups remain gates. Inspect candidate source/diff, original native
   evidence, negative controls and separate review results before merge.

## Security, rollback and scope limits

Only receipt implementation headers plus additive tests/workflow/docs change.
Existing FactStore, Hook, installer, CLI/MCP names and ledger are unchanged. Source
is still SQLite-only. Invalid or retired fact reads do not gain access. A new
validation error does not authorize the caller to repair the database or delete
receipts. Revert the code to roll back; no new stored layout or data conversion.

Bounded indexed lookups cover the selected logical identities, not an entire
hostile database integrity audit. No defense against an administrator replacing
schema/indexes/triggers or corrupting arbitrary unrelated rows is promised. Same
coordinator reviews plan and outcome in separate passes, not another agent or
third-party certification. Issue40 and actual client/model/PG/signing gates remain.
