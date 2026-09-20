# N47Z separate review: caller-owned implicit transactions

2026-09-20. Reviewer: coordinating ChatGPT in a separate owner-authorized
engineering review, not a subagent or third party. Native acceptance is pending.

The original local module checked only sqlite3_get_autocommit before applying.
A direct C++ reproducer, compiled against that exact local header, starts an
unfinished INSERT...RETURNING with two caller-owned config rows. Autocommit is1
while sqlite3_txn_state isWRITE. An all-no-op batch then begins an explicit
transaction, fails COMMIT because the caller statement is unfinished, and its
rollback removes the caller's two pending rows. This is an actual candidate
boundary defect, not a fixture error or a claim that released code has this batch.

Observed before repair: caller_rows_before=2, caller_rows_after=0,
transaction_state_before=2, autocommit_before=1; exception is
cannot commit transaction - SQL statements in progress. The old local header
SHA256 is9fa998fb06f168a7660fb61c65ce1a4c009cb65d7525f9231cc49aa2ff2a16c5.
The identical reproducer source SHA256 is
f88ca9095ca83a634b69b835790002f369d5612c86aa0398fc2864f9e6eb923d.
The prior locally delivered archive and original failure logs remain preserved.

Repair only the apply-ownership guard: require both autocommit enabled and
sqlite3_txn_state(connection,nullptr)==SQLITE_TXN_NONE before initialization or
batch transaction acquisition. Active read/write statements, blob handles and
attached database transactions therefore remain the caller's property. Preview
continues to work in caller transactions. The API does not reset, finalize,
commit or roll back caller statements; idle prepared or completed statements do
not unnecessarily block a new owned transaction. Concurrent unsynchronized use
of one Brain connection is not a supported guarantee.

Add a separate41-check direct suite, retaining the original18 checks unchanged:
implicit pending writes, read cursors, explicit savepoints, attached database
writes, healthy no-op/revoke paths and test-only commit denial after an insertion.
The latter verifies rollback of the batch's own work and preservation of prior
caller data. Both standalone suites must actually execute in Windows CI in
addition to the unchanged full60 native suite. Linux local41/18 and89 end-to-end
checks already pass; these results do not replace the pending native gate.

No N47Y single-item writer, persistent schema, permission, original test assertion,
Hook, installer, bridge, Release/tag or model/client result changed by this repair.
The original platform write rejection was not bypassed; the same plan operation
succeeded on this continuation before submitting the implementation.
