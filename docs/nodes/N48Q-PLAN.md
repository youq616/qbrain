# N48Q — PostgreSQL structured facts, lifecycle and explicit-use receipts

2026-09-29. Base cfa00185dc0575b1dbf7c418082608f7563a3b91.
Status: approved after N48Q-PLAN-AUDIT.md. Owner delegates implementation decisions
and continuing project closeout; original requirements are not silently deferred.

## Scope
Extend the existing FactStore and explicit-use APIs to PostgreSQL: evidence-backed
create/attach/promotion, explicit contradiction/supersession/retraction, source-scoped
read/recall/conflicts, archive/restore and atomic selected lifecycle batches, and
report/revoke/read/page/batch use receipts. Preserve SQLite SQL, output, consent and
no-automatic-inference semantics. No public API addition, invented confidence, model
call, automatic SQLite migration or statement that real clients consumed memory.

## Acceptance
1. public/UTF8/origin and exact effective relation identity before source access;
   reject caller-owned active/failed transactions. A bounded module-owned read may
   be reused by nested evidence validation, but never by an unrelated caller writer.
2. PostgreSQL multi-query reads use one REPEATABLE READ READ ONLY snapshot; writers
   take sources/pages/config locks in the N48O/P order then existing dependent tables
   under a local 2500ms lock budget. No broad changes to the PG backend translator.
3. Lazily initialize BIGINT/text-C optional fact/lifecycle/use schemas inside owned
   short transactions. Recognize column/key/FK layout and enabled canonical cleanup
   function/triggers. Unknown/partial layouts are refused, not replaced. Do not
   attempt file backup of a DSN. SQLite pre-migration backups remain as before.
4. Last-support deletion removes orphan facts and their relations/archive/receipts;
   removal of one of multiple supports advances the surviving revision. Exact quotes,
   complete evidence, tombstones, expiry, expected revisions, direct counter-evidence,
   ASCII literal matching and whole-pair byte limits remain unchanged.
5. Use receipts remain caller reports, not host-consumption or truth proof. Preserve
   current/historical/withdrawn, idempotence, 4096 capacity, full-set paged snapshots,
   explicit batch-preview binding and all-or-nothing application. PostgreSQL typed
   columns replace SQLite storage-class probes without weakening SQLite corruption tests.
6. Fresh local SQLite regressions/sanitizers, independent multi-operation CLI checks,
   actual disposable PostgreSQL native/concurrent tests, Windows and Linux fixed-source
   qualification including old context/session/core/55-step gates. Missing PG is a
   failed acceptance prerequisite, not a successful skip. Audit raw results separately.

## Security / rollback
No real owner DB, secrets, paid traffic, installer or public-release change. Same DSN
with different brain labels is not a tenant boundary; logical source is not RLS.
Raw SQL schema owners are trusted, not sandboxed. Revert additive PG paths without
automatically dropping optional tables. No signed/stable/full-project claim until
separate original acceptance requirements are actually closed.
