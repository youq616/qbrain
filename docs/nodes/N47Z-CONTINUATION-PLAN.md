# N47Z continuation: native acceptance and transaction ownership

2026-09-20. APPROVED by coordinating ChatGPT in a separate owner-authorized plan
review, not another agent or third party. The identical previously blocked plan
write succeeded through the same connector operation; plan commit bd559fff now
exists. Earlier local deliverables and their uncompleted Windows gate remain
historical, not retroactively relabelled as repository acceptance.

Continue the existing local N47Z module; do not start a competing implementation.
Verify the input archive and base product file identities, retain all89 CLI/MCP,
18 direct C++ and previous integrity/use/page/native tests. Submit source to the
existing feature branch, run fixed-source Windows/Linux gates and inspect actual
artifacts before merge. Add the missing explicit Windows execution of the direct
C++ batch suite: the unchanged full60 test executable does not include that
standalone CMake target. Run it separately without replacing the original gate.

Separate transaction review must examine unfinished RETURNING/write statements as
well as explicit BEGIN. SQLite autocommit can remain enabled while an implicit
write transaction is held by an unfinished statement. A second BEGIN followed by
failed COMMIT/ROLLBACK can affect the caller's pending changes. Reproduce against
the original local module first, with no product code changes; preserve observed
results. If confirmed, reject ownership before optional initialization or any batch
transaction using the actual SQLite transaction state, while preserving read-only
preview in caller transactions and all existing public behavior. Do not reset,
finalize, commit or roll back statements owned by the caller.

Add a separately authored direct test for pending reads/writes, savepoints, foreign
key requirements and failure/reuse. Keep original18 checks unchanged. Extend actual
native/portable validation to both standalone suites. Retain no new schema, default
permissions, automatic retries, model calls, user-machine work or release changes.
Native tests are required; local Linux results alone cannot finish this stage.

Primary references: https://www.sqlite.org/lang_transaction.html and
https://www.sqlite.org/c3ref/get_autocommit.html . Tests and source review determine
the finding; documentation alone does not prove a Qbrain bug or its correction.
