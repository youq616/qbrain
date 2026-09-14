# N47B plan review

Reviewer: ChatGPT, separate engineering self-review under the owner's latest
explicit instruction. Not an external or independent-subagent review.
Verdict: PASS for this implementation scope; outcome/native checks pending.

The implementation must reuse validated whole-quote facts instead of inventing a
new inference model. Reading an explicit contradiction does not establish either
claim's truth, and differing predicates/quotes alone do not create an edge.
Both sides must survive the same source, status and evidence checks; a byte or
work limit must never expose a misleading one-sided conflict. No recursion into
other relations, so cyclic or densely connected graphs stay bounded.

Keep the outer SQLite statement active through nested reads; verify this using
an actual second-connection write, not just a comment. Read snapshot semantics
allow a pre-forget pair already being read, but the next call must see the forget.
No same-connection mutation or multi-thread sharing is supported. Generic default
source policy is inherited, not broadened by this new view.

No schema initialization or backup on read. Reuse existing CLI/MCP gates and
reject irrelevant fields rather than silently ignoring them. Do not alter old
memory/read semantics to force tests to pass. Add exact registry/report gates and
retain legacy suites before marking the stage complete. Output count is not a
bound on total SQLite rows examined; describe this honestly.

P0/P1 design blockers: none after paired output and snapshot requirements.
Main implementation risks: partial-pair output, stale evidence cache across calls,
incomplete snapshots, source leakage, false conflict inference and misleading
truncation. Each has a required falsifiable test. No paid model experiment or
new local-host task is needed. Final outcome review is a separate pass.
