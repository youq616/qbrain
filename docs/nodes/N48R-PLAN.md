# N48R — backend-correct Hook composition

2026-09-29. Base: N48Q candidate4f8b470f, tree927600dc. Status: approved following
N48R-PLAN-AUDIT.md. Owner has authorized continued implementation and separate
coordinator self-review. No third-party review is claimed.

Repair the actual Hook PostgreSQL path, not a simulated model-consumption layer.
Use internal existing-only PG opening (never create a core database from a Hook), while
preserving the existing SQLite file gate. Do not fall back to SQLite on PG errors.
Bind PG deduplication state to the effective server/database/role descriptor.
For fact recall compose both facts and legacy memories in one owned repeatable-read
read-only transaction. Ordinary session APIs must still refuse caller transactions;
only a private checked reader may borrow this fact snapshot. Never weaken write
transaction ownership, temporary-table protection, permissions, exact source evidence,
quote suppression, conflict groups or output budgets. Finish the read before capture.
No schema migration, provider call, inferred confidence or automatic permissions.

Acceptance: regression of existing SQLite Hook/session/fact tests; new same-source
native Windows/Linux PG+SQLite tests for composition, permission gating, source
isolation, withdrawal and capture/extraction/promotion. Explicit tests for caller
active/failed/read-only transactions and writer scopes, shadowing, no schema on empty
PG, no local SQLite gate/fallback, deduplication/reset, and bounded fail-open output.
Record actual runs and failed attempts. PG is required for remote qualification, not
an optional successful skip. New original source/executable identities are fixed by CI.
No user's actual device, provider account or brain is required. No claim of signed-in
client semantic consumption or resolution of Issue40 without its own evidence.

## Completion decision — 2026-09-30

Status: done within the original bounded contract, after N48R-HARD-AUDIT.md PASS.
Original runtime45a23853/full native36583542753 remains unchanged; independent
supplement a4acb118/run36652734242 passes both native platforms. Local regression,
sanitizer, complete archive/source identity and raw-output review completed.
First supplemental Windows reviewer cleanup failure and all driver errors remain
recorded. Actual merge is PR60; no full-project or signed-in-host claim.
