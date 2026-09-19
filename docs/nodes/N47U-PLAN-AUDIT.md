# N47U separate plan review

2026-09-19. Reviewer: coordinating ChatGPT, owner-authorized separate engineering
self-review, not a subagent/third party. Verdict: PASS to implement.

The current product exposes aggregate counts but no list for locating receipt IDs.
This additive read-only feature makes explicit revocation usable without inventing
auto-consumption or relaxing prior eligibility. It fits the existing use-recording
roadmap. No schema, new public tool name, network service or write permission needed.

Required implementation invariants: one coherent local read snapshot; full bounded
row validation before filtering; complete byte-bounded row serialization; explicit
error on no progress; scope-bound snapshot plus cursor; invalidated continuation
on any receipt-state or fact-revision change. A SHA digest is not a signature or a
held transaction across calls. Restarting pagination on edits is preferable to
silently skipping newly inserted opaque IDs.

Native regression, unchanged N47T semantics and no schema/backup mutation are
blocking acceptance requirements. The final reviewer must separately exercise
faulty cursor/filter/scope, corruption outside a visible page, changed data after
the first page, and all byte limits. No known blocking issue in this bounded plan.
SQLite transaction reference: https://www.sqlite.org/lang_transaction.html .
