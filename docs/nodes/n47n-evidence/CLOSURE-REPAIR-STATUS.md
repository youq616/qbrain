# N47N closure repair checkpoint

2026-09-19 Asia/Seoul. PENDING fresh native acceptance and final outcome review.
The f2ba7ffc closure must not be treated as completed: its follow-up N47N native
run 35362126565 failed n31_a_counts_mapping because the live ledger was replaced
by an archive link. The replacement is retained byte-for-byte in REJECTED-LEDGER.md
(blob 7dd3c86e777ef33c6c185fa7016e091872e23b6c).

Restored canonical ledger is byte-identical to the inherited N47M inventory
(blob 495862c7a4c869bf349b90343f9e34767374792a). No product source, native tests,
original workflows, frozen count, operation or provider authorization changed.
A separate static Windows/Ubuntu documentation check now rejects missing,
duplicate and wrong-identity table rows; it does not replace runtime tests.

Executed locally before publication: 17 checker unit tests passed normally and
with Python -O; original failed ledger rejected; 361 parser checks, 226 real
CLI/MCP search checks (302 command calls), and four focused CTest groups passed.
These are Linux engineering results, not new native Windows acceptance.
Local product source came from verified a587e175 source artifact 10553760842;
Git tree reconstructed exactly as 3c2b5ef5f1ce76d271f19e235f33703120d4891c.

Retained initial test-fixture error: two negative cases changed already-zero
inventory counts to zero, so they were not corruptions. The fixture now changes
each count to count+1. Production checker and native assertions were not relaxed.
Current user authorization allows coordinator self-review, not fabricated agents.
Do not merge, declare final completion or publish a release from this checkpoint.
