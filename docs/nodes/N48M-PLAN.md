# N48M — native SQLite snapshot backup, verification and restore-to-new

2026-09-27. Base main 1e7ff0d6a2a744c34e0051308301421bdaf50631,
tree 7f699d3ec48f3049e3177995ef2d9cf0947a7069. Status: approved after
N48M-PLAN-AUDIT.md. Current owner requests the coordinator's own separate review.

## Goal

Provide first-class native `backup create`, `backup verify`, and `backup restore`
for an explicitly selected SQLite brain.db. This closes a daily operational gap:
backup before installing/upgrading, validate independently, and recover to a NEW
external directory without touching the live brain or the default registry.
Use the SQLite online backup API with a pinned read transaction so committed WAL
content is included and uncommitted data is excluded. No raw copy of a live DB.

SQLite-only local administrative capability, not an MCP op or source-scoped read.
No PostgreSQL connection, env/credential lookup, model/HTTP call or background job.
The entire selected database (all sources and stored configuration) is sensitive,
plaintext, unencrypted. External files, installer state, host credentials and the
brain registry are NOT included. No automatic application of restored files.

## Acceptance contract

- create: --database PATH --output NEW_DIR [--timeout-ms 100..120000]. Valid
  selected source required before making output; SQLite source opened read-only,
  no migrations. Core qbrain schema_version/sources/pages tables required, schema
  version 1..13. Pin transaction; copy through checked incremental backup calls.
- verify: --backup DIR --expect-sha256 MANIFEST_SHA [--timeout-ms ...]. Required
  externally retained manifest SHA prevents silent acceptance of a rewritten DB
  and rewritten manifest together. Hashes are not signatures or origin proof.
- restore: same verification plus --output NEW_DIR. Restore only as brain.db in
  a new directory, never into an existing brain. Verify bytes and SQLite integrity
  before final receipt. Never edit registry or select restored brain automatically.
- Self-contained snapshot.sqlite3, rollback journal mode, no WAL/SHM dependencies;
  strict fixed manifest fields and exact two-file inventory. Manifest written LAST.
  A failed operation leaves no valid completed manifest; partial owned directories
  may remain and are never recursively deleted or overwritten on retry.
- Check SQLite integrity_check and foreign_key_check on the snapshot; do not claim
  full application semantic or virtual-index consistency solely from PRAGMAs.
- 256 MiB database cap, 8 KiB manifest cap, bounded monotonic SQLite lock/progress
  deadline. OS file I/O/hash/cleanup are not hard preemptible wall-clock deadlines.
- Refuse symlink/reparse paths, nonregular inputs, URI/special paths, Windows ADS,
  hard-linked database files and restore outputs inside a backup. Read-only verify
  must not alter bundle bytes. Existing outputs and unrelated files are preserved.
  This is not a hostile concurrent-filesystem or forged-executable sandbox.
- Tests: committed/uncommitted WAL, read transactions under concurrent commits,
  locks/timeouts, corruption/foreign keys, exact manifest binding, duplicate JSON,
  size/version/path edge cases, existing output, failed publication, and actual
  Qbrain facts/active+withdrawn receipts plus FTS before/after restore.
- Native Windows/Linux full-product tests, independent raw SQLite row oracle,
  direct tests and ASan/UBSan; old functional regression gates remain unchanged.

## Delivery

Pure native header and early CLI route; standalone direct/test-process suite,
new dedicated CI, user guide and honest separate outcome audit. Preserve existing
backup_to migration behavior and all old assertions. Normal expected-head PR;
no old ZIP/tag rewrite, actual user-machine operation or Issue40 closure.

## Outcome closure — 2026-09-27

Complete for the bounded SQLite source module at d9942612 / treea89ce43c after
actual native Windows/Linux qualification and the separate N48M-HARD-AUDIT.md
review. The initial candidate's failed Windows fixture remains recorded.
Manifest-last requires a successful receipt and externally pinned verification;
it is not a claim of OS-atomic publication or that every I/O fault leaves zero
marker bytes. The extra warning-as-error profile is not claimed to pass.
Closing changes are documentation/history/executed indices only. PR54 records
the actual merge. No existing package, live brain, PG, signing or Issue40 change.
