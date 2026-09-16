# N47F outcome finding: snapshot must not issue transaction-control SQL

Candidate a8ee9a8dedbdf09ee6a8c8764a1f8a843b28959e is NOT accepted for delivery.
Native run35058294020 passed the new lifecycle unit/process checks but failed the
existing N47C recall unit in portable and Server2022. Direct local execution of
the unchanged old recall test reproduced `[FAIL] N47C: not authorized`.

Root cause: new ReadSnapshot issued BEGIN/ROLLBACK to cover optional schema
inspection and candidate reads. The existing N47C read-only authorizer expressly
denies SQLITE_TRANSACTION. Read-only data is insufficient: adding transaction
control breaks an existing supported caller policy. The original unit assertion
must remain unchanged, not be relaxed to make the new code pass.

Repair scope: hold a SELECT COUNT(*) FROM sqlite_master statement at SQLITE_ROW
through schema detection and nested reads. That establishes a normal implicit
read snapshot without transaction-control SQL; statement finalization releases
only its own read and preserves any caller-owned transaction. Release the read
statement before acquiring a write transaction in initialization. Strengthen the
new lifecycle authorizer test to deny SQLITE_TRANSACTION too, preserving all
previous checks and scenario limits. Actual deterministic two-connection reads,
backup, archive/restore and all old standalone units must be rerun, not just the
new tests or old process suites.

This is a production correction requiring a new source-bound native run and
fresh outcome review. Earlier new-test PASS and sanitizer runs do not certify the
repair. Native failure artifacts and local reproduction log are retained. The
old recall wrapper did not retain child stderr in its report; local direct unit
execution supplies the diagnostic, not an invented original Windows stderr.

Engineering repair review: approved under the owner's separate self-review
instruction. Preserve source, evidence, counterclaim and output policy; no schema
migration adjustment, permission expansion or automatic publishing.
