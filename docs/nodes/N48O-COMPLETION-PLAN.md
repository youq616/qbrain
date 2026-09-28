# N48O completion plan / separate design review — 2026-09-28

Continuation baseline: ed79b44951db626556b2d2cbca924fcd1c33dd86, tree
9521be3ae28a43aaddf707a9f70db47c2eb51545. PR57 already implements PostgreSQL session
memory; the two preceding chat-only proposals did not implement a real-client
verification layer. Complete this bounded existing module, not a duplicate N48O.

Separate pre-change review: current_schema() == public does not guarantee that an
unqualified table resolves to public: PostgreSQL implicitly searches pg_temp first.
The memory code locks public tables but queries unqualified names. Test a same-
connection temporary config whose writeback policy disagrees with public.config.
Do not describe this as a remote privilege escalation or as a reproduced historical
release bug. First preserve a run against the unchanged parent, then require the
repaired module to reject mismatched resolution before reading source/policy and
again before each short transaction (including after a provider callback).

Approved change: compare effective OIDs with public OIDs for the seven module
relations using pg_catalog functions. Absent optional tables may remain absent.
Do not modify search_path or drop temporary objects. Nonshadowing temporary tables
and explicit public-before-pg_temp resolution must continue working. Retain the
UTF8/current_schema check and caller-owned transaction guard. SQLite behavior and
existing assertions remain unchanged.

Acceptance: separately compiled real-PG tests on Windows/Linux, a parent-code
characterization on Linux, all existing 122 native and 75-command differential
checks and full original regressions; exact source and raw-result readback. Test
all public entry points under each conflicting temp table, post-provider
revalidation, unrelated temp objects, no writes on refusal and transaction
ownership. New tests are synthetic on explicitly disposable test DBs only.
No model network, user DB, automatic confidence update, cross-brain guarantees,
fact/context PG parity, installer/release or Issue40 closure.

Reviewer: current assistant's owner-authorized separate design pass. PASS to
implement this amendment; no outcome PASS or third-party/subagent claim.
