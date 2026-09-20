# N47Z separate plan review

2026-09-20. Reviewer: coordinating ChatGPT, separate owner-authorized engineering
plan review; not another subagent or third-party certification.
Verdict: APPROVED for the bounded atomic batch module.

The existing single-receipt and paged-audit module is the correct validated base.
A batch must not be implemented as a loop of independently committing writers.
Use a common preflight, a source/selection/state fingerprint and one IMMEDIATE
transaction with a second complete validation. Failure after a successful first
statement must prove rollback, not just refusal before any work starts.

The plan explicitly distinguishes read-only preview from permission and module
initialization from atomic receipt mutation. A successful non-no-op batch changes
its snapshot, so blindly replaying the old approval is not permitted; a fresh
preview surfaces prior changes as no-ops. This avoids inventing a persistent batch
idempotency journal or accepting unrelated modified selections on stale approval.

Required risk checks: current support can expire between preview and apply; a
revoke need not revive or expose an expired/retired fact; source-level usage IDs
may collide across facts; pending new rows collectively consume capacity. All
routes retain typed/duplicate-key/unknown-field and source/write authorization.
Snapshots include off-selection rows in each selected fact, not other sources.
No observed use/truth or real-model result is implied. Existing tables and helper
semantics remain unchanged.32 items/8 facts bound both work and output.

SQLite transaction/storage-class behavior was checked against official
https://www.sqlite.org/lang_transaction.html and https://www.sqlite.org/datatype3.html .
Final acceptance remains conditional on real native artifacts and separate outcome
review; no PASS is inferred from the existence of tests or an uncompleted CI run.
