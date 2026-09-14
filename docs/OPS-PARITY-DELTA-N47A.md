# N47A capability delta — accepted explicit evidence-backed facts

Reviewed/tested source: cccdacb61e63c29f8b9eaba1c38fbeed3e23e54b.
Stage acceptance and original independent reviews: nodes/N47A-HARD-AUDIT.md and
review/n47a-cccdacb6/. Merge state is the live PR #14 state; no new runtime code
is included in the acceptance documentation commit.

| Capability | Implementation | Evidence |
| --- | --- | --- |
| Explicit whole-quote fact versions | FactStore; fact CLI; existing memory_read/view=facts and memory_write/fact_* | Source review A/B; native fact unit and process suites |
| Attach/retract/supersede/contradict | Caller-labelled, same-source, optimistic revision; no automatic truth inference | Native lifecycle/source/permission/negative cases |
| Optional additive module | Separate memory_fact_*; lazy first valid write with backup; legacy facts untouched | Legacy compatibility and migration rollback scenarios |
| Privacy propagation | Live evidence checks plus last-support FK/trigger cleanup | Source/SQL review and native forget/tamper/expiry tests |
| Startup contention | Connection-setup-only 2500ms deadline and cleanup | Native deterministic lock tests; process idempotence schedule |

Native registry increases 48 to 49 named groups. No seventh memory-profile tool,
external-processing consent or automatic fact injection into Hook context.
No semantic entity/relation extractor, inferred conflict resolution, decay/score,
profile model, PostgreSQL parity, signed distribution or whole-project completion.
13 P3 observations remain visible in issue #16; do not equate PASS with zero
limitations. Future runtime edits require new tests and an independent review.
