# N47G — explicit atomic lifecycle batches and read-only preview

Baseline: a81df391448b278797c21a246a2253bb77fe046f, merged N47F.
Status: done for the scoped implementation after N47G-HARD-AUDIT.md.
Tested/reviewed source b1292b54543b9f54cd5e2b71f4ae4bf5f6247385.
Native evidence35093371931 and35093372100; versioned publication is separate.
Windows-native Qbrain only. Owner-authorized engineering self-review, not a third party.

## User-visible slice

Long-lived brains need safe multi-fact organization, not one request per fact
with partial success. Add FactStore::lifecycle_batch(payload, apply=false),
CLI `fact batch-preview` and `fact batch-apply`, and the existing tools:
`memory_read(view=lifecycle_batch,payload=...)` previews; explicit
`memory_write(action=fact_lifecycle_batch,payload=...)` applies. No new tool name.

Both accept {operation: archive|restore, items: [{fact_id, expected_revision}]}.
Require 1..32 unique fact IDs, strict fields/types, positive bounded revisions,
<=8192 serialized payload bytes, and reject duplicate keys in the public raw
JSON payload. apply is an internal routing decision, never a field the caller
can smuggle into a read. Preserve source allow-lists and default write refusal.

Preview validates the whole requested batch in one read snapshot, returns only
IDs, before/after revision and archive policy, and marks result PREVIEW/applied
false. It does not initialize optional tables, make a backup, take a writer lock,
modify usage/evidence/revisions or control a caller-owned transaction. It is not
a reservation: apply must validate every item afresh; a preview is never proof
that later application will succeed or has happened.

Application requires no caller-owned transaction. Validate all items before any
schema preparation; use the existing archive backup/lazy module preparation only
when archiving needs it. Then take one bounded BEGIN IMMEDIATE transaction,
revalidate all items and live evidence under that transaction, and change all
requested policies/revisions atomically. Any invalid fact, stale revision, work
limit or SQL failure aborts the entire batch; never loop over the public single
archive method that commits once per item. Duplicate/no-op targets do not advance
revisions, but still require current revision and evidence. Return full receipts
only after successful commit. Preserve input order; duplicate IDs are rejected.

Use one shared ReadWork per validation pass (512 evidence checks / 8MiB transcript
work), no stale evidence cache across passes. Apply needs at most two passes;
preview needs one. Bound metadata response to32768 bytes and check before commit.
Schema preparation and policy application remain separate transactions: an empty
new module/backup can remain on later conflict, but never partial policy changes.
SQLite backup cost is not bounded by this batch size. Eligibility is measured at
the common validation time, not a claim facts cannot expire subsequently.

## Semantics and compatibility

Archive is not retirement, privacy deletion or semantic truth. Preserve complete
counter-evidence, old fact/recall/Hook semantics, source isolation, N47F no-revival,
last-support metadata cascade, and exact-quote promotion retaining archive policy.
No automatic stale selection, usage counters, inference, scheduled maintenance,
background tasks, new schema version or changed install defaults. Existing single
fact archive/restore entry points retain behavior. PG remains unsupported here.

## Falsifiable acceptance

Actual C++ production-class cases: successful archive/restore and current-revision
idempotence, preview under write/transaction-denying authorizer, no migration or
backup in preview, invalid last member with no partial changes, empty/33-entry/
duplicate/foreign/retired/expired/tampered/revision limits,32-entry boundary,
SQL-trigger failure after an earlier member write, atomic restore failure,
whole-batch work limit, inherited counterclaims/Hook filtering/forget/promotion,
caller transaction preservation/rejection, disk first-use backup, and two real
connections submitting competing batches with exactly one stale-revision loser.
Check a second-connection change after preview makes apply fail, not silently
update a revised selection. Count/schema/evidence identity must remain accurate.

Actual CLI/MCP cases: JSON stdin, raw duplicate-key rejection, strict route fields,
read-only preview under default permissions, default denied apply, source denial,
allowed application, invalid final item rollback, unchanged six-tool list and
old ordinary memory. Add group55, standalone batch unit and actual process suite,
strict source/EXE/script report validators and negative validator tests; keep all
N47A-F, HTTP, queue, CJK, installer, Windows/portable and Server2022 gates.

After implementation perform a separate outcome review, repair discovered issues,
run current-source native CI and sanitizer checks, inspect original reports and
package identity. No inherited old-package PASS or native claims from Linux.
Rollback is source-only; no new data schema beyond N47F. Release only reviewed,
exact tested candidate bytes, not a general unreviewed automatic publisher.

References consulted September16,2026:
https://www.sqlite.org/lang_transaction.html
https://www.sqlite.org/isolation.html
