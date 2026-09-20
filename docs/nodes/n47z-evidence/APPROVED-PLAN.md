# N47Z — Atomic batch management of caller-reported fact use

2026-09-20. Status: approved after the separate plan review.
Base main:82e1f4c3872b5e3813b68f94ed925849b1e6b7a0.
The owner asks to finish a complete module and separately self-review it.

## Complete module scope

Add fact usage-batch-preview and fact usage-batch-apply through the existing
memory_read view=usage_batch and memory_write action=fact_usage_batch. JSON payload
selects operation=report|revoke and 1..32 explicit items across at most8 facts in
one already-authorized source. Report items contain fact_id, usage_id,
expected_revision; revoke items contain fact_id and usage_id. No mixed operations.
A read-only preview returns a deterministic snapshot and every intended change
or no-op. Applying requires that exact snapshot and revalidation inside one
BEGIN IMMEDIATE transaction. All receipt changes commit together or none do.

## Acceptance gates

1. Strict unique JSON keys, exact fields/types, lowercase64hex IDs, no repeated
   usage_id within a batch, explicit operation, bounded payload/output. Canonical
   ordering makes input reordering harmless. Unknown/missing/wrong fields reject.
2. Preview never creates a receipt module, backup, fact or receipt. Use existing
   N47Y storage-class and alias validation before counting or planning. New reports
   require active supported unarchived current revisions; revoked IDs never revive.
   Revocation preserves the existing right on legal expired/retired/archived facts.
3. Snapshot binds source, operation, canonical items, current fact revisions and
   complete bounded receipt sets for all selected facts. It is not permission or
   a signed approval. Any relevant record/revision change rejects before mutation.
   Every apply requires a current preview; after actual changes, retry by previewing
   again. Existing identical reports/withdrawals are explicit no-ops, not duplicates.
4. Preflight precedes optional existing-module preparation. On first report, use
   the existing pre-module backup and initializer. Schema preparation is separate
   from receipt atomicity: a concurrent later rejection may leave an empty module
   and backup, never a partial batch. No new tables, migrations or batch log.
5. Under the write lock, recheck each target and source-wide requested ID alias,
   capacity4096 including tombstones, snapshot and permissions via existing routes.
   Then apply deterministic ordered changes. SQL/commit errors roll back all changes.
   No calls to per-item public writers that would create nested transactions.
6. CLI and real persistent MCP both exercise report/revoke, preview/nonmutation,
   mixed no-ops, source/write default-deny, stale snapshots, changed selection,
   corruption, capacity,32/33 items,8/9 facts, concurrent contenders, SQL ABORT after
   an earlier successful statement, natural expiry and post-error server usability.
7. Compile actual C++ on native Windows and Linux. Retain original full60 native,
   four portable core groups, N47Y123/72 and earlier75/71/process suites unchanged.
   Save source-bound binary/test hashes, synthetic command streams and reports.
   Separately inspect code, negatives and actual original artifacts before merge.

## Delivery, rollback and limitations

New route-local header plus existing CLI/operation dispatch/schema changes; payload
already has an MCP string type, so no new wire-gate field. No new MCP tool name,
model/client access, confidence/ranking/decay change or default write permission.
Batch entries are still caller attestations, never proof of truth or host use.
Read at most8 bounded sets (4096+sentinel each); no full-brain scan or scale claim.
A caller can compute a fingerprint; authorization is always the existing write gate.
After applying changes an old snapshot is intentionally stale. No automatic retry.
Only receipt updates are atomic, not OS backup creation or external delivery.
No hostile administrator/trigger sandbox, physical disk-fault guarantee or secure
WAL/backup erasure. Existing single-item commands stay byte-compatible.
Revert additive header/routes to roll back; no stored format conversion required.
Public N47X assets remain unchanged. Issue40 and real-client/model/PG/signing gates
are not closed by this module. Reviewer is the coordinating assistant in separate
owner-authorized engineering passes, not another agent or third party.
