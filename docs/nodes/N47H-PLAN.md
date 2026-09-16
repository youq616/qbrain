# N47H — bounded, paginated lifecycle candidate discovery

Baseline main: 612ccf22688bde71656e1ea5f771bd5afbd12ed5.
Status: approved for implementation after N47H-PLAN-AUDIT.md.
Windows-native youq616/qbrain only; separate owner-authorized engineering review.

N47G applies explicitly selected batches but does not discover selections in a
large brain. Add FactStore::lifecycle_candidates, local `fact candidates`, and
existing `memory_read(view=lifecycle_candidates)`. Required operation is archive
or restore. Archive candidates are active, unarchived assertions with valid
support and an advisory age at least stale_after_days (default180). Restore
candidates are active archived assertions with live evidence, regardless of age.
No automatic write, truth inference, semantic merge or resurrection. Return only
metadata and a bounded batch_payload compatible with N47G, or null for no choices.
Discovery is neither approval nor a reservation; explicit batch preview/apply
still revalidates current revisions and evidence. Read permission cannot apply.

Use bound source/predicate filters, stable binary fact_id ordering and optional
strict64-hex after_id. Inspect at most100 eligible-policy raw candidates plus a
sentinel per call; return at most1..32 selections. Reuse one 512-check/8MiB evidence
budget and the N47F strict valid-support age calculation. Unknown/future timestamps
never qualify as stale. Damaged oversized quotes are excluded before materializing.
Full JSON response must fit512..32768 bytes, batch_payload<=8192 bytes, no quotes.

One read snapshot per call, no writes/DDL/backups/transaction-control SQL. No
cross-page snapshot or cursor authentication is claimed: after_id is a seek key,
not access permission or evidence. New/changed earlier keys may require restarting
the scan. Empty pages may have more candidates. Cursor advances only past fully
examined rows; output/work-budget interruption retains the unconsumed current row.
next_after_id=null means end; an unchanged cursor means retry with a larger output
budget or explicitly stop, never loop forever. Expose stop_reason and scanned.
No hidden unbounded loop, OFFSET or whole-table transcript materialization.
Limits do not guarantee total SQL work, wall-time or million-event performance.

Public CLI/MCP require operation, reject irrelevant query/history/event/fact_id/
payload fields and invalid types. Preserve old views, defaults and six tool names.
No new schema, archive behavior, installer change, provider request or live-host task.
The existing age method may be factored without changing its observable behavior.

Acceptance: valid archive/restore candidates and exact metadata; multiple supports
with newest valid creation time; unknown/future/malformed/expired/tampered/deleted
support; source and predicate isolation; 32-selection and100-scan boundaries;
more than100 irrelevant facts with continuation to an old matching candidate;
no repeats on static data, deleted seek key, output/work-budget resume without
skipping; independent reference model of several page sizes; read-only authorizer
and caller transaction preservation; second WAL connection changing evidence
mid-read, coherent current call and revalidated next call; preview/apply race.
Real CLI/MCP routes, unchanged write default denial and tools; strict unit/process
report binding and negative report tests;56 native groups and all previous gates.

After implementation perform a separate outcome review, repair findings, run
native Windows/portable/sanitizer evidence and inspect exact source/package bytes.
No old green evidence promoted as new. Rollback is source-only, no data downgrade.
References consulted September16,2026: https://www.sqlite.org/rowvalue.html and
https://www.sqlite.org/isolation.html.
