# N48N separate outcome audit — SQLite and FTS health

Reviewer: ChatGPT coordinator, owner-authorized separate post-implementation
self-review. This is not a subagent/third-party/Claude Code certification.

## Disposition

**PASS for the bounded native N48N database-check module.** The existing in-flight
implementation was completed through fixed-source qualification, newly written
outcome/boundary reviewers, raw artifact replay and delivery documentation. No
known unresolved blocking defect was found within the reviewed contract and
executed tests. This is not a zero-defect or complete application-health guarantee.

Base `f83d1b138c88d1413d38a3541d4c929ac82a3b0f`; initial candidate
`58a61cf04de0ff61aaf819f03eda06ca696dba17`; qualified candidate
`b6d0e8002cefffbf94d21144080a66a5a198f238`, tree
`ad735d477df04c08a0d6242b2be489b04f576480`. Final closure changes only documentation,
historical copies and an executed-result index. Product, original tests and CI
remain byte-identical to the qualified candidate. Actual closure/merge identity
belongs to PR55 and the delivery record, not the older CI reports.

## Implementation review against the approved plan

| Acceptance | Reviewed implementation and executed evidence |
| --- | --- |
| Explicit read-only source, no default configuration | Early main.cpp dispatch precedes ordinary Brain/registry/env setup. Source uses READONLY/NOFOLLOW, query_only, defensive configuration and disabled triggers/views. A separate actual-program test poisons HOME/APPDATA/LOCALAPPDATA with a file and injects unusable credential values: diagnostic still succeeds without creating a default registry or printing these values. |
| Consistent, bounded snapshot | A read transaction is pinned before page sizing and 128-page backup steps. Source page size is applied to private RAM destination; source closes before the deep checks. Native fixtures prove committed WAL inclusion, uncommitted drift exclusion, page sizes512–65536 and UTF-16. Supplementary live-writer checks pass while committed transactions change the DB. |
| Real FTS consistency rather than table presence | Seven fixed checks distinguish ordinary integrity, FK, inventory, references, FTS declaration, three triggers and rank=1 external-content consistency. Canonical triggers restored after changing text do not hide stale indices. Independent term/document/column/position reconstruction detects reordered positions, column/row changes, deleted/phantom rows and empty index. |
| Conservative schema and lexical handling | Ordinary-table impersonation, alternate content table, missing columns/indexes, unknown versions, conditional/wrong triggers and orphans without FK declarations fail. SQL tokens preserve boundaries and literal bytes rather than deleting whitespace. Normalization-equivalent text is not incorrectly called stale. |
| Non-destructive failure and truthful result | Deep INSERT syntax runs exclusively in private memory; no source repair or migration. PASS requires all seven checks PASS; dependency omissions remain NOT_RUN. Exit0/1/2 separate complete pass, found problems and operational errors. Existing source bytes are checked where no independent writer is active. |
| Resources, privacy and scope | RAII closes memory DB/statements/backup on exceptional paths; successful source close retains the N48M pointer-lifetime fix. SQLite errors are converted to fixed codes, not path/body/SQL messages. 256MiB and bounded SQLite busy/progress budget remain enforced. Direct34 and ASan/UBSan34 pass, with empty sanitizer stderr. |
| Regression and Windows availability | Native Windows full60, Linux core6, both original55-step drivers, old backup and independent reviewer stages pass. Exact Windows EXE is delivered separately, not replaced with a Linux build or unqualified source. |

The review read the complete new header, early CLI route, required canonical
schema and reused N48M resource/path helpers. No product repair was required in
this closeout. Do not recast the documented test-fixture corrections as fixes to
released product defects. There is no claim that all compiler warning profiles,
hostile files, memory exhaustion, sudden power loss or every business invariant
have been exhaustively exercised.

## Native qualification and independently read artifacts

N48N run36324081781: Linux job108633348850 and Windows108633348925 both succeeded,
attempt1. Additional unchanged N48D run36324155761: Windows108633561578 and
Linux108633561701 both succeeded, attempt1. The extra N48D jobs were checked;
their separate artifacts were not downloaded or independently replayed here.

| Exact-source result | Linux | Windows |
| --- | --- | --- |
| New direct C++ checks |34|34|
| Primary actual CLI matrix, each normal/optimized Python mode |47 commands /198 checks|49 commands /204 checks|
| Independent native index reviewer, each mode |22 scenarios /23 commands|22 scenarios /23 commands|
| Old backup direct checks |62|59|
| Original regression |core6 plus55-step driver|full60 plus55-step driver|

Primary cases had no skips. Windows counts include native ADS/UNC rejection cases;
Python optimization does not delete explicit requirements. Repeated runs are not
counted as unrelated new product features.

Downloaded original qualified archives were checked against external SHA256,
ZIP CRC, exact source tree and preserved worktree scripts. Each contains1465 source
files; 1450 Windows files are exact LF-to-CRLF transforms and the other15 identical.
All132 Windows worktree scripts match exact CRLF bytes. Replay uses those archived
bytes for identity checks, not local LF substitutes. The1465-file candidate changes
only main.cpp among1457 base files, adding eight files; no old storage/test/installer
implementation is rewritten.

Windows artifact10934026463 SHA256:
`6e02bd2cb66d7230a38756d29e83818baa61bf2d2a579944f6d7aede16d23809`.
Linux artifact10933636804 SHA256:
`0a107ad81bcabf407ea3d659167f7acee51e913d92059b81a7c7fdcf5d580263`.
Windows executable SHA256:
`aa182648bf19e326e2e957acfb636dcd8fe2895aab83aea26c2e91de5fbaa0b4`.
Linux executable SHA256:
`05310ca5fa8c2ec5549f2d81777a2c4f2f2d3071f049d3086372799260ffbee1`.

Twelve original verify invocations re-read both platforms/modes for the diagnostic,
independent token oracle and backup reports. Another46 unchanged verifier invocations
re-read24 accounting,12 lifecycle,2 MCP and8 application-receipt evidence sets, with
original negative checks retained. Both55-step driver records, all exit codes,
script/binary identity and raw-log hashes were checked. The archive/source identity
review does not execute a Windows EXE on Linux and is never labeled a new Windows run.

## New, separately written outcome and boundary probes

The closeout adds two independent standard-library reviewers, importing neither
product nor original test helpers. Their exact source hashes and results are in
[RESULT.json](n48n-evidence/RESULT.json); sources and raw outputs are preserved in
the separate source/evidence ZIP, not substituted for the original native tests.

`review_outcome.py` re-reads each of four archived22-scenario/23-command runs against
hardcoded expectations and pinned executable identities. It uses strict duplicate-key
and typed JSON validation, recomputes FTS term/doc/column/offset tuples from synthetic
offline fixtures, and checks raw reports, command ordering, no-repair flags and private
content suppression. Each run rejects20 controlled corruptions, including rehashed
forged-green results and expectations, removed failure/NOT_RUN states, Boolean/int
substitutions, rewritten stale fixtures and a changed command requesting repair.
This catches the exercised evidence inconsistencies; it cannot authenticate a
colluding replacement of all tools/producers or a real provider/client statement.

`review_boundaries.py` executes23 actual Linux diagnostic commands per normal/optimized
mode: nine sidecar symlink/hardlink/directory cases, parent/input links, poisoned
default-environment configuration, an offline DELETE-mode DB in read-only directory
permissions under unprivileged uid65534, and ten snapshots during a real WAL writer.
Each final run observes35 committed writer transactions and passes. Existing file
bytes and guard files remain unchanged in nonconcurrent cases. No byte-immutability
claim is made while that deliberately independent writer is active. These are POSIX
checks, not Windows ACL tests. They supplement rather than replace native Windows
hardlink, symlink, Unicode, ADS and UNC checks.

The downloaded qualified Linux product was also re-executed through the original
47-command/198-check matrix and22-scenario/23-command index reviewer in both modes.
Standalone tests were freshly compiled locally: direct34 and ASan/UBSan34 passed,
with empty successful sanitizer stderr. A full product was not recompiled locally
in this closeout; its actual compilation is the qualified native CI build.

## Failures and corrections retained

Initial Windows run36316882996 passed the original60 and new34 direct checks,
then its fixture attempted a hardlink from checkout D: to TEMP C: (WinError17).
Candidate b6d0e800 places the hardlink beside its source on the same volume. It does
not skip the rejection case, weaken assertions, extend timeouts or change product
C++. The original failed archive10930484877 is preserved, SHA256
`1554d6499060e6cf5ecad09150a4bd24b5969b570fa808ae65dda00524675fd4`.
Initial portable results are not reused as qualification of the corrected test bytes.

The inherited plan/commit record earlier local fixture failures: assuming readonly
could not create an empty WAL; reading/closing a descriptor in the locking POSIX
process; applying diagnostic privacy rules to init output; and retaining an inline
UNIQUE clause in the duplicate-row fixture. These historical accounts are retained
as accounts; their earlier raw local logs were not newly retrieved here. This delivery
does not pretend those raw logs are present alongside the actually downloaded Windows
failure. The abandoned PR56 experiment is not merged or credited in any counts.

This closeout initially compared the Windows CRLF archive directly to an LF Git tree,
then corrected the reviewer to verify every exact CRLF transform. The failed reviewer
and explanation are retained. One combined local tool invocation was interrupted
while starting a retained comparison replay; its partial failed record is preserved.
Fresh final replay directories then completed all46 checks, rather than relabeling
the partial run as success. An unsupported streaming execution tool attempt did not
start a test and contributes no result. A harmless import cleanup to the boundary
reviewer was followed by fresh normal/optimized runs with the final exact script hash.

## Limits, delivery and review conclusion

Checks are for one committed snapshot of the whole selected SQLite DB, including
all sources. Known-v13 inventory does not prove every DDL constraint, semantic
relationship, FTS use case or authentic provenance. Semantically equivalent but
noncanonical custom declarations can require human review. SQLite readonly can
create empty WAL/SHM or update shared-memory bookkeeping; it is not a filesystem
no-op. The report explicitly discloses that limitation. Private memory may be paged.
The timeout is not hard-preemption of OS I/O, scheduling or allocations;256MiB is
not a hard peak-RAM ceiling. There is no hostile concurrent-filesystem sandbox.

The new unsigned Windows toolkit retains the exact qualified EXE and two synthetic
native-Windows fixture/output pairs. It does not install, collect data, repair,
automatically select a brain or replace old N48K/N48M/public release artifacts.
No real owner data, paid model call, PG/signing/stable release or Issue40 closure is
performed. Real client memory consumption and real model quality/cost remain gates.

Within these boundaries the module is complete and no known blocking defect remains.
Review evidence supports this bounded conclusion, not an absolute safety warranty.

Primary API references reviewed on2026-09-27:
https://www.sqlite.org/fts5.html#the_integrity_check_command
https://www.sqlite.org/wal.html#read_only_databases
https://www.sqlite.org/backup.html
