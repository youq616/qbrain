# N47F plan review

Reviewer: ChatGPT, owner-authorized separate engineering self-review, not an
independent subagent or third-party audit. Verdict: PASS for implementation of
the bounded scope in N47F-PLAN.md. Implementation status is approved by this
record; outcome, native tests and publication are still pending.

The proposed status expansion is deliberately NOT applied to the fact truth/
retirement state machine. Archive is an explicit per-fact recall policy with
optimistic revisions; age is advisory and is derived only from valid supports.
Reads do not mutate use counters, confidence or database schema. There is no
automatic semantic merge or inference that newer text contradicts older text.

Blocking invariants reviewed before code changes:
- Archive may not remove a valid direct counterclaim from another active anchor.
- Restore requires an active fact with currently valid original evidence; no
  retirement, expiry or final-evidence deletion can be undone by policy changes.
- The new metadata references fact/source and cascades with final evidence loss;
  it stores no copy of private quotes. Archive itself is not forget or secure erase.
- Lazy policy inspection and candidate selection must use one read snapshot;
  concurrent initialization/transition cannot make selection inconsistent.
- Writes revalidate revision/evidence under BEGIN IMMEDIATE; nested caller
  transactions are not committed or rolled back by the new API.
- New module backup precedes DDL, but schema preparation is distinct from a later
  failed state transition. Existing data and previous facts schema_version stay.
- Every CLI/MCP action stays behind existing source/read/write authorization and
  has strict fields/types. Default source policy is inherited, not strengthened
  or broadened under an unrelated lifecycle feature.

P0/P1 design blockers: none with those constraints. Required negative tests cover
partial read groups, bad metadata, foreign keys, stale writes, broken evidence,
query/type failures and deliberate removal of archive/counterclaim protection.
Retain fixed schedules and exact native evidence counts; record skipped tests.
Old binaries ignoring archive policy is an explicit downgrade warning, not a
silent compatibility claim. No live-client changes are required merely to run
repository tests; any later local task must be one fixed repository handoff.
