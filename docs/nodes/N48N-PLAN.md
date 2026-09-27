# N48N plan — read-only SQLite deep health inspection

Status: approved after the separate plan audit below; base f83d1b138c88d1413d38a3541d4c929ac82a3b0f.
Owner's current instruction explicitly requests the coordinator's own separate audit.

## Goal and contract
Add `qbrain database check --database PATH [--timeout-ms N]`, routed before default
Brain/registry/credential initialization. Leave old doctor, backup, all tests and
MCP permissions unchanged. This is a local Windows-native C++20 diagnostic, not a
Python service, automatic repair or a declaration that all business semantics pass.

Open the explicit local SQLite file READONLY/NOFOLLOW; hold a fixed read transaction,
include committed WAL and exclude uncommitted updates; copy via online backup into
a private in-memory connection with the source page size. No output DB or source
migration/rebuild; SQLite may do normal WAL/SHM bookkeeping (including creating empty sidecars). Cap logical DB at 256 MiB;
100–120000 ms monotonic SQLite budget, no hard OS I/O or process RAM guarantee.

Report a fixed, content/path/SQL-error-free JSON schema with stable check IDs:
SQLite structure; declared foreign keys; known v13 core table/column/index inventory;
page/source and page-child references; canonical FTS declaration; canonical three
maintenance triggers; and FTS5 integrity-check with rank=1 against external content.
Expected FTS/trigger definitions come from the existing embedded canonical schema;
compare SQL tokens (not a whitespace-deleting substring test). Unknown/missing FTS
layouts never pass. Findings return exit1, complete bounded checks passing exit0,
input/open/resource/timeout/operational failures exit2. Dependent checks not run are
explicitly NOT_RUN; no skipped check can yield CHECK_PASSED.

## Acceptance / tests
Actual full product creates disposable brains and edits synthetic SQLite copies.
Demonstrate a stale index for which PRAGMA integrity_check returns ok but the new
command fails; also cover altered/missing triggers and ordinary-table impersonation.
Exercise FK violations, explicit orphans when FK clauses are absent, missing schema
objects, newer/legacy version, corrupt/truncated files, unsupported args, Unicode
paths, links/sidecars, no registry/env contact, exclusive locking/deadline, committed
and uncommitted WAL, varied page sizes/UTF-16, and pristine/empty/large-row databases.
Check original main/WAL bytes before/after each applicable probe. A newly created
empty WAL and SHM bookkeeping are explicitly permitted, never nonempty WAL changes. Keep raw outputs, exact executable/source hashes, and unsuccessful attempts.
Run standalone C++ and sanitizers; native Windows full60 plus portable retained
core tests; old backup and old accounting/lifecycle driver unchanged. Independently
review code after implementation and add black-box adversarial probes that do not
import the implementation. Evaluate outcomes, not just green CI summaries.

## Security / limits
Explicit local input only; reuse N48M path validation without changing it. Disable
trusted schema, triggers, views and extensions on diagnostic connections. Fixed SQL
and metadata only; no arbitrary SQL argument, repair flag, model/provider or network.
The memory image contains plaintext entire DB, may be paged by OS; not a sandbox for
hostile SQLite/filesystem exploits. Snapshot is one point in time, not later writes.
Core inventory is not every DDL constraint, receipt semantic, model quality, client
consumption or authenticity check. Signature/stable/PG/Issue40 gates stay open.

## Delivery / rollback
New header, early CLI route, standalone C++ and process tests, native workflow,
Chinese guide, separate audit and actual evidence index. A new unsigned Windows
toolkit is separate from fixed N48K/N48M archives and public releases. No user data.
Reverting N48N restores the old CLI; it requires no DB rollback because N48N never
migrates or repairs source data. Publish only after review; merge only qualified
bytes, preserve any failures and distinguish docs-only closure.

## Pre-candidate plan clarification from actual SQLite behavior
The first process test incorrectly required absence of a WAL file to remain absence.
A READONLY open of an offline WAL-format DB created an empty WAL and SHM; main bytes
were unchanged. Preserve that failed test and raw report. Update the contract and
validator explicitly: preserve every existing main/WAL byte; allow only newly empty
WAL plus SQLite SHM bookkeeping. No immutable=1 shortcut, checkpoint or file deletion
is used to hide normal SQLite behavior. No user DB or previous assertion was changed.
