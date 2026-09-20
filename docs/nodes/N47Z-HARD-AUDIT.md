# N47Z outcome — atomic receipt batches and transaction ownership

Recorded 2026-09-20 UTC. **PASS for the approved batch-module source scope. No
known unresolved blocking finding remains within that scope.** This is not an
absolute defect-free guarantee, stable-v1, real-client/model, PG or signing approval.
Reviewer: coordinating ChatGPT, separate engineering self-review under the owner's
explicit current instruction, not another subagent or third party.

## Objects and review sequence

Base main:82e1f4c3872b5e3813b68f94ed925849b1e6b7a0.
Original plan persisted:bd559fff55228faf469123e5b34e200e9145b1b4.
Transaction/native completion plan:25311885a7ebb80e5acdfa3d530fb4cdc7a6f065.
Accepted product/tests:7898dec68b5162b33a193cb30295bdd1744e5269.
Accepted tree:83312db93cd4302c2e98cfbc92b0266b38939be3.
Fixed push/attempt1 run:35516145384.

Earlier platform write rejection and the original local-only deliverables remain
historical. On the preceding continuation the same authorized write operation
succeeded, the transaction correction was committed, and PR44 was created. This
final pass found that actual PR, reviewed its source and completed native evidence,
then ran independent tests. It did not create a competing implementation or claim
to have newly performed earlier compilation/reproduction work. The approved plan
is preserved verbatim under n47z-evidence/APPROVED-PLAN.md.

## Original acceptance mapped to execution

| Gate | Evidence and result |
| --- | --- |
| Complete bounded interface | CLI usage-batch-preview/apply and existing memory_read/write routes accept one report/revoke operation,1–32 unique receipt IDs and at most8 facts in one authorized source. Exact fields/types, duplicate JSON keys, payload8192/output16384 byte bounds are tested. PASS. |
| Nonmutating preview | Current fact eligibility and inherited N47Y integrity precede decisions. Preview leaves application rows, schema and backups unchanged; sorted selection produces the same plan. No new table or batch journal. PASS. |
| Atomic mutation | All planned inserts or withdrawals run under one owned IMMEDIATE transaction; no loop of independently committed writers. Deliberate failure on a later statement rolls back earlier changes. Separate commit-denial test confirms a performed insertion is rolled back too. PASS. |
| Snapshot and no-op behavior | Source, operation, canonical selection, revisions and full bounded selected-fact receipt sets bind approval. Changed selection/state rejects. First module preparation is logically equivalent to empty valid state; no-op fresh approvals preserve times and state. Old changed-state approval cannot be blindly reused. PASS. |
| Eligibility and permissions | Active supported unarchived current-revision reports; legal expired/retired/archived receipts remain revocable. Existing source/write gates,4096 capacity including tombstones and corruption checks remain. Actual MCP previews do not grant write access. PASS. |
| Caller-owned transaction safety | Apply requires autocommit and sqlite3_txn_state(connection,nullptr)==NONE before initialization. Pending readers/writers, savepoints and attached-database transactions remain owned by their caller. Preview still works there. Original18 and additional41 direct C++ checks run on both platforms. PASS. |
| Native and original regression | Windows full60 plus standalone18/41, Linux six CTest targets, both-platform normal/-O89 scenarios, original123/72 integrity and75/71 receipt suites plus all nine old process gates. Original report/stream readback succeeded. PASS. |

Among inherited production files only the existing memory operation route/schema
and fact CLI change; the batch header is new. CMake adds two standalone test targets.
Existing single-receipt implementation, FactStore, MCP typed gate, Hook, installer,
bridge, stored schema, permissions, canonical ledger and old tests/build scripts
remain unchanged. The full60 original suite is not misleadingly said to include
the new standalone tests: both were separately built and executed on Windows.

## Review finding retained and final verification

The earlier local candidate checked autocommit alone. The committed
TRANSACTION-OWNERSHIP-FINDING.md records its direct reproducer: an unfinished
INSERT RETURNING held two caller-owned rows while autocommit remained enabled;
a batch COMMIT failure followed by ROLLBACK removed those pending rows. It is a
candidate defect, not a claim that the public N47X release contained this batch.

The accepted guard additionally checks actual transaction state across attached
databases. In this final pass the downloaded direct-test binaries both executed
successfully on Linux:18 basic checks and41 ownership/commit checks. Their Windows
counterparts passed in native CI, and the ordered41 result records were compared.
No source change after7898 is used to hide or bypass that corrected boundary.
The original historical reproducer was not recompiled in this last pass; its
recorded finding remains distinct from the newly rerun final regression.

SQLite's autocommit mode and active transaction state are different properties;
pending writes may prevent COMMIT, and rollback may abort pending work. Primary
references: https://www.sqlite.org/c3ref/get_autocommit.html ,
https://www.sqlite.org/c3ref/txn_state.html and
https://www.sqlite.org/lang_transaction.html . Same-connection unsynchronized
concurrent use is not supported or certified by this guard.

## Fixed native artifacts and independently checked contents

Windows job106092309012 and portable106092309117, all required steps successful.
Original downloaded artifacts:

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| windows10606659850 |18879361|612b72fc76814538f1f82a1b81393dffcacf374390b41dd428fdb6924d664660|
| portable10606593858 |20792136|c8f574d2ae3ec0f4520c53af6414137ee4b97a7b6a5c41993e20d639d10659ce|

ZIP hashes/CRCs and source markers were checked. The canonical archive reconstructs
1231 files and the exact accepted Git tree. Windows membership/modes match, with
1217 files differing only by exact LF-to-CRLF conversion. Product EXE hashes:
Windows149a710652bd69d4d3c8cd90a0f71cf8869cc0cca2f09034070d5de4fcface5e;
Linux4087415b478ba0d02a22d1751b2c599bad494b59eaf2ebf5929e5d1a71f5f7ae.

Each platform and Python mode:89 batch scenarios,165 calls,495 raw streams and51
successful batch results revalidated;12 malformed-report cases reject. Original
integrity123/156/468, usage75/118, pages71/111/333, and both72-check persistent-MCP
reports were rechecked using their source-owned validators and exact executable/
script representations. Fact34, multiterm112, Hook52 and lifecycle40 semantic
reports were revalidated; named60/search226 checks and memory44/MCP17 logs checked.
The inherited context65 gate has a summary and successful CI, not saved individual
command bodies. No missing evidence was invented. Real PG remains SKIP-PG.

Windows native log: BUILD_OK,60 original registered groups and a matching60-group
receipt. Linux CTest: six targets, consisting of four existing core groups plus
two new batch targets. Separate18/41 JSON outputs and executable digests are pinned
in SUMMARY.json. Offline readback ran normally and with Python-O with identical
results. This is evidence inspection, not local Windows execution.

## Additional independent reference-ledger review

review_reference_model.py was authored in this final pass after the supplemental
review plan. It runs only public API writes; SQL snapshots are read-only. A persistent
MCP process executes24 sequential batch rounds over8 facts, accumulating125 receipts,
including32-item limits, shuffled selections, mixed no-ops, stale approvals and
fresh no-op replay. Every round checks summaries and complete paged timestamps/IDs
against a separately maintained Python reference ledger.

Actual downloaded Linux product:1933 assertions,35 public CLI setup calls and656
MCP requests pass in each of normal and optimized Python. Those are two executions
of24 scenarios, not thousands of independent product features. Original89 batch
scenarios and18/41 binaries were also rerun here. No new local C++ build or native
Windows execution is claimed. Script and exact result hashes are archived in
REFERENCE-REVIEW.json; raw local reports are not embedded in that derived record.

## Limits, delivery and merge

Only receipt mutations are atomic. Existing module initialization and its backup
are a separate phase; a later rejection may leave an empty module/backup. A snapshot
is not a signature, credential or grant of permission. Actual changes make the old
approval stale; callers must repreview, not automatically retry. No-op results do
not establish external exactly-once delivery. Fact validity is rechecked at execution,
not guaranteed indefinitely after return. Output budget excludes the MCP envelope.

Tests use disposable corruption, SQL ABORT and commit denial, not physical disk
failure, every interleaving, hostile triggers/administrators or all datasets. Natural
expiry is a guarded real-clock fixture. The reference-ledger test is sequential and
has no corruption writes. No automatic repair, model use, ranking, profile or decay
behavior is added. Issue40, real-client/model/fees, PG, signing and stable-v1 gates
remain open. Public N47X assets are unchanged and do not contain N47Y/N47Z.

Closing additions are restricted to docs/history and already-executed review code
and derived records. Check their diff and actual merge tree before declaring merge.
Newly triggered merge CI is not predeclared passed. Actions artifacts follow their
2026-10-04 retention; Git summaries and review code are not entire raw archives.
