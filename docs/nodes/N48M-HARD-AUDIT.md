# N48M separate outcome review — native SQLite backup and restore

2026-09-27. Reviewer: ChatGPT, owner-authorized separate post-implementation
engineering self-review, not a subagent, Claude Code or third party.

## Final disposition

**PASS for the bounded N48M SQLite backup/verify/restore-to-new source module.**
No known unresolved blocking implementation defect was found in the reviewed
contract and executed results. This is not a guarantee of zero defects, full
application semantic integrity, authentic provenance or complete disaster recovery.

## Fixed sources and exact scope

Base main `1e7ff0d6a2a744c34e0051308301421bdaf50631`, tree
`7f699d3ec48f3049e3177995ef2d9cf0947a7069`. Initial candidate
`9626aed13dfb9d24348ff408ddf79f442b2b7ed0`, tree
`2d02475ff1587a04f0179f0425b8ef4c1262cffe`. Qualified candidate
`d9942612a2ed3aecd1696265802d3f554715d0dd`, tree
`a89ce43cd785faf1cc26f3d97a5bf2688d5b2828`.

All 1,443 base files except the precise early main.cpp route/help remain unchanged.
Seven added files and that route edit give 1,450 candidate files. The fixed candidate
changes only two test fixtures relative to the initial candidate, not product
behavior. The local Git objects are explicit byte-identical tree mirrors, not
re-created original GitHub commits. Existing storage backup_to, old assertions,
MCP permissions, installer and immutable N48K ZIP are not modified.

The native administrative commands act only on an explicitly selected SQLite
file, before ordinary Brain/registry initialization. They create a read snapshot,
verify an externally pinned manifest, or restore into a NEW directory. They do
not migrate or replace a live database, select a default brain, call a model,
read environment credentials or add a MCP operation. The complete selected DB
includes all sources, DB-stored configuration and possibly freed-page residues.
It is plaintext and unencrypted. External attachments, registry, client/installer
configuration and external credentials are not backed up. PostgreSQL is excluded.

## Review against the plan

| Requirement | Verified implementation and evidence |
| --- | --- |
| Consistent committed snapshot | A read-only source connection begins a read transaction before page count and online backup. The backup API copies incrementally, requires DONE plus successful finish, and closes the source without checkpointing it. Real WAL fixtures include committed rows and exclude an uncommitted transaction; three live-writer snapshots preserve paired committed values. |
| Self-contained image and structural checks | Destination is sealed in DELETE journal mode and checked by integrity_check and foreign_key_check before the manifest is written. Exact two-file inventory excludes sidecars. Restored images retain all 32 fixture tables, BLOB/NUL values and actual Qbrain facts/current/withdrawn receipts; independent layout probes also execute FTS queries. |
| External verification rather than self-consistency alone | Verify/restore require a supplied external manifest SHA256 before interpreting the canonical manifest. Changing DB and manifest together fails the old pin; explicitly trusting the new hash is a different trust decision, not authenticated origin. Duplicate/typed/noncanonical manifests and extra files are rejected. |
| No destructive recovery | Parent paths and file types are checked; output directories must not exist. Files use CREATE_NEW or O_EXCL, and source data/default registry remain unchanged. Restore creates only a new brain.db plus a final receipt, never automatically activates it. |
| Bounds, failures and resource safety | 256 MiB DB/8 KiB manifest limits, schema max version1–13, no-follow paths and a bounded SQLite busy/progress deadline. The close/deadline lifetime defect below is fixed and regression-tested. Controlled POSIX file-size failures return errors without a successful marker; subsequent attempts do not overwrite partial output. |
| Windows integration and unchanged regressions | Actual fixed-source native Windows and Linux jobs execute the new direct and process tests, original full60/core and unchanged55-step accounting/lifecycle/application driver. Each platform's archived scripts and EXE identities are kept distinct during independent replay. |

Manifest-last is an acceptance protocol, not an OS transactional directory commit.
The original plan's failure-marker wording must not be read as a guarantee that
no bytes can ever remain after any write/sync/power failure. Completion requires a
successful operation receipt and full verification against the trusted external
pin. A file merely existing does not prove a completed or power-loss-durable backup.
No directory-fsync, storage-hardware or hostile concurrent-filesystem guarantee is
claimed. Windows output inherits parent ACLs; database size may require several
copies in memory. SQLite deadlines do not hard-preempt OS open/read/write/hash/flush.

Core-table/version recognition is intentionally coarse; minimal legacy fixtures
are not proof of complete semantics for every historical Qbrain version. PRAGMA
success is not proof of all business invariants or FTS content synchronization.
The native result explicitly keeps application_semantics_verified=false. Read-only
source connections may still involve SQLite shared-memory bookkeeping; only the
exercised business data/main/WAL byte preservation is claimed.

## Actual implementation defect found and fixed

The first local new Db::close sequence checked the deadline after closing SQLite
but before clearing the handle. If close succeeded and the check then threw,
the destructor could access a freed connection. Before the initial remote candidate,
the implementation was corrected to clear the pointer immediately on successful
close, then check the return/deadline. A direct regression expires the deadline
and requires both the timeout error and a null pointer.

A TEMPORARY controlled reconstruction reverted only that statement order. The
same regression under AddressSanitizer produced heap-use-after-free and exit1.
This is explicitly reconstructed pre-candidate code from this turn, NOT an archived
failure of an old released upstream build. Its source, compiler invocation and
original diagnostics are retained. The fixed implementation passes62 direct
ASan/UBSan checks with exit0 and empty captured diagnostic stderr. No sanitizer
failure was hidden by suppressing checks or changing assertions.

## Fixture corrections and failures retained

The initial process fixture did not match the existing extractor's explicit input
rule, leaving no matching item. Only synthetic wording was corrected to a recognized
I-prefer statement; the old extractor and assertions remained unchanged.

Initial Windows run36308697498 passed the product/full60 stage, then failed the
new direct CTest before its first counted assertion: file_size could not resolve
the Chinese WAL path. Three test constructions were changed from narrow fs::path
to fs::u8path. A separate portability review also corrected two Python fixture
scopes to contextlib.closing: SQLite connection context managers govern transactions,
not closure. UTF-8/emoji test paths, runtime code and every assertion were retained.
The failed Windows archive10928194373 was downloaded and kept, SHA256
`5f0e3a07ade60c4797599ea9d840d427bb5b5bf4aa61df839f6e35a7cd372bdc`.
The initial portable result is not reused as qualification for the fixed test bytes.

An additional local -Wall/-Wextra/-Wpedantic/-Werror syntax profile failed on five
libstdc++14 deprecation diagnostics for filesystem::u8path. This is retained as a
failed EXTRA warning profile; it is not the repository's configured build gate.
No warning suppression or relaxed CI flags were applied. Warning-free compilation
under that stricter profile is NOT claimed. The qualified project configuration
remains C++20; moving away from this deprecated helper is a future compatibility
cleanup, not an unobserved runtime fix claimed here.

## Actual native qualification

Fixed run36309034614 completed Windows job108592708176 and Linux job108592708070
successfully, attempt1. Additional unchanged N48D run36309037673 completed Windows
108591288263 and portable108591288397, attempt1. Those extra N48D jobs were read;
their separate archives were not downloaded or claimed independently replayed.
No failed job was rerun to erase the original candidate's failure.

| Fixed-source gate | Actual result |
| --- | --- |
| New direct C++ checks | Windows59; Linux62. The three-count difference is explicit POSIX-only link tests in C++; Windows process tests independently cover hard links/symlinks and ADS/UNC paths. |
| Actual backup/recovery process matrix | Each Python mode: Windows47 commands/112 checks, Linux45 commands/106 checks; no skipped probes on either runner. |
| Old original functionality | Windows60 groups verified against registration and raw log; Linux6 core CTests pass; both unchanged55-step drivers complete with ordered steps, exit0 and matching log digests. |
| Independent new evidence replay | Four process reports re-read with each artifact's exact script/binary identity; all32 tables, restored file bytes, fact/receipt content and canonical result fields independently checked. Four runs each reject all14 corrupted evidence variants. |
| Retained report replay | Per OS:12 accounting,6 lifecycle,1 MCP and4 receipt reports; 46 replay commands in total finish with exit0 and original corruption checks enabled. |

Both original fixed-source archives were checked against external metadata, ZIP
CRC and exact Git blob bytes. Each has1,450 source files; Windows differs in1,435
files only by exact LF-to-CRLF conversion. Windows verification uses those archived
CRLF script bytes, not local LF hashes. Exact archive/executable identities and
per-mode counts are in [RESULT.json](n48m-evidence/RESULT.json).

Linux qualified executable SHA256:
`c013962e1dc219aef3029143a983e40db3aae757ca16f18fd53e269024518786`.
Windows qualified executable SHA256:
`f81ad718576e02b527bd3542794f215c407c83d2218bb4128597340582dc4bd5`.
Actual Windows execution happened on Windows CI, not Linux emulation or the
owner's Windows11 PC. The archive review and SQLite row inspection here do not
execute Windows EXEs and are not relabeled as native Windows runs.

## Local independent post-implementation probes

The separately compiled local Linux product has SHA256
`218c8901d767f03f324b63f1f958bb0ce7bcbd1db7bbbd5485fd9c44507c49ff`.
Its final ordinary/optimized process runs each pass45 commands/106 checks.
Direct and ASan/UBSan executions each pass62 checks; no diagnostic stderr in the
successful sanitizer run. Local and CI binaries are not described as identical.

A separately written standard-library black-box reviewer imports neither product
nor original test helpers. Each Python mode runs58 actual commands/199 checks:
12 page-size/encoding/auto-vacuum layouts, multiple sources, NUL/BLOB/int64 values,
a17MiB single row, exact restored data/FTS, unchanged coarse legacy versions,
external pin vs rewritten data/manifest, invalid FK and no-overwrite on partial
output. Both modes also pass on the downloaded Linux CI executable. These repeated
runs are not counted as distinct unrelated product features.

Four further POSIX child-process probes use a4096-byte RLIMIT_FSIZE and ignore
SIGXFSZ to exercise actual recoverable write failures. Create returns backup_copy;
restore returns backup_write; source bytes remain unchanged, successful markers
are absent in these cases, and both retries refuse the existing partial directory.
This is not a Windows disk-full test, a simulated power loss or a general promise
that every possible I/O failure leaves no bytes.

The independent raw-evidence reader validates exact command order, expected error
exits, canonical result JSON, external manifest pins, all SQL row values and full
active/withdrawn receipt histories including duplicate-report idempotence. Each
mode rejects14 mutations including rehashed wrong output, bool/int substitutions,
missing withdrawals and changed timestamps. These checks detect the exercised
inconsistencies, not a colluding replacement of all producers, binaries and checks.

## Delivery and boundaries

The source module, qualified native programs, complete user guide and separate
outcome review are complete. Final closure may add only documentation, historical
copies and already executed result indices; no changed product/test/workflow may
inherit an old candidate's results. Actual merge identity belongs in PR54 and the
final delivery record, not in an earlier frozen CI report.

The Windows toolkit is a separate unsigned utility delivery, not an installer or
replacement for the immutable N48K ZIP. It must retain the exact qualified EXE and
sample bytes; any packaged sample is synthetic, never user data. Full raw records,
reviewer sources, earlier failures and compiled artifacts are preserved in the
separate source/evidence ZIP, with compact repository indices where appropriate.

No real user brain, private session, paid model, permission change, PostgreSQL
backup, signing, stable-version release or Issue40 closure was performed. Real
client memory consumption and model quality remain independent project gates.

Primary API references reviewed on2026-09-27:
https://www.sqlite.org/backup.html
https://www.sqlite.org/c3ref/backup_finish.html
https://docs.python.org/3/library/sqlite3.html#how-to-use-the-connection-context-manager
