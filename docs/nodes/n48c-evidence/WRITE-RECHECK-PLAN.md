# N48C separate outcome finding and approved correction

2026-09-21. Reviewer: coordinating ChatGPT, owner-authorized separate engineering
review, not a subagent or third party. The first local candidate passed926 direct
checks and92 process checks. A separately authored scheduled-write test then
failed: after the journal persisted, a noncooperating editor changed the config;
the candidate overwrote it. This is a real preservation defect, not fixture error.

APPROVED correction: for reconciliation, compare the journal and both destination
images immediately before each forward write, including previously written slots.
For explicit recovery compare the pending journal and each target before restoring
it. Refuse changed bytes and keep the journal instead of continuing. Retain all old
and new tests. Re-run the independent failure and final regression; preserve the
initial failed record. No stronger atomicity or race-free claim: a final read-to-
rename race, identical-state ABA and malicious administrators remain outside scope.
This does not add a silent retry, auto-merge or arbitrary rollback of unknown data.
