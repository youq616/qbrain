# Closure repair plan addendum

Date: 2026-09-19 (Asia/Seoul). Reviewer: coordinating ChatGPT, separate self-review.
Approved before publishing repair implementation. This supersedes only the
trigger-integration part of item 4 in N47N-CLOSURE-REPAIR-PLAN.md.

Use one dedicated read-only Windows/Ubuntu workflow, triggered by the canonical
ledger, frozen inventory, rejected fixture, native N31 source and checker files.
Leave all existing N47N/N42/N44 workflow bytes unchanged. This avoids modifying
large established packaging workflows for a documentation-only contract check.
The added .ci code triggers those existing full native workflows for this repair.
Future documentation-only changes receive the fast guard; it is explicitly not
a runtime-registry proof. The unchanged native N31 test remains authoritative.
All other acceptance criteria, fresh fixed-source native verification, separate
outcome self-review, failure retention and no-release scope remain unchanged.

The restored ledger is the exact inherited N47M inventory, including historical
qualifications. N47N adds no operation rows; its current status is in the N47N
delta and CURRENT-STATUS.md, not a destructive replacement of the frozen tables.
