# N47B — read-only, evidence-backed conflict inspection

Baseline: b4fc453a22c20597f99e1d2dfa9713cfeb2704c4 (merged N47A).
Status: approved for implementation after N47B-PLAN-AUDIT.md.
Only youq616/qbrain, Windows-native C++20; no unrelated projects.

The owner now explicitly requests that the coordinating agent perform a separate
review after each stage: “每个阶段开发完，你自己做一下独立审核”. For this stage,
use separate plan and outcome engineering self-review passes, not a fictitious
subagent or third-party review. Do not request redundant local review or waive
runtime evidence. Preserve the original independent N47A reports unchanged.

## Scope

N47A can record contradictions but has no paired conflict inspection endpoint.
Add FactStore::conflicts, local `fact conflicts`, and `memory_read(view=conflicts)`
behind the existing read/source gates. Return ONLY explicitly recorded contradicts
edges whose two endpoints are active and still supported by validated complete
user quotes. Return both endpoints, current revisions and complete provenance
together, or omit the entire pair. No inferred contradictions or selected winner.

Reuse N47A evidence validation and its 512-check/8MiB work bounds. Keep an outer
SELECT active while loading both sides, so a result describes a single SQLite
snapshot. A concurrent forget is observed by the next call, not half-way through
a pair. Reject incompatible source/subject/predicate/self relations and canonicalize
pair order. Filter by optional fact_id or predicate, with stable ID ordering.
Limit output to 1..50 pairs, 512..32768 UTF-8 JSON bytes, at most 100 inspected
candidates plus a truncation sentinel. A pair that cannot fit is never reduced to
one side or truncated quote. Explicit truncation means empty is not proof of no
conflicts. Read-only calls never initialize tables, back up, schedule jobs, change
versions or perform provider I/O. No migration, new tool name, automatic capture,
write authority or Hook injection. PostgreSQL remains unsupported by FactStore.

## Acceptance

Real production-class tests for fresh/legacy databases, explicit versus inferred
edges, stable order and filters, two-sided completeness, byte/result/work limits,
source isolation, invalid fields, expiration, tampering, soft/hard deletion,
retraction, supersession and final-support forgetting. Demonstrate a committed
writer between pair enumeration and evidence loading using a second real WAL
connection; first call is a complete prior snapshot, next call hides forgotten
support. Assert read-only SQL with an authorizer and unchanged data/schema counts.

Real CLI/MCP tests must exercise default read access, source denial, rejected
history/query/event fields, strict types, unchanged six tools and write denial,
old facts and ordinary memory behavior, and no job creation. Register exactly one
additional native group (50 total) and a source/binary/script-bound process report.
All previous N47A, CJK, queue, HTTP, memory/Hook/context/PowerShell gates remain.
Preserve failures; no rerun-until-green or assertion reduction.

Out of scope: semantic contradiction detection, conflict resolution inference,
truth scoring, profile/decay, automatic fact recall and new clients. Existing
supersede/retract are explicit resolution actions. P3 findings from N47A remain
tracked separately. Rollback is a source revert with no stored-data downgrade.

Reference: https://www.sqlite.org/lang_transaction.html and
https://www.sqlite.org/isolation.html (read September 14, 2026).
