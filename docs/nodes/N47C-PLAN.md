# N47C — query-directed fact recall with explicit counter-evidence

Baseline main: 309d71ab79e8bfb55f8b8161ec0126e80514e965.
Status: done for scoped implementation after N47C-HARD-AUDIT.md.
Tested source: 1311bdd51b779e8da6b6420b62ea3f653edfa27f.
Original native evidence: 34854466927 and 34854466971. Publication tracked separately.
Only the Windows-native youq616/qbrain project. Owner authorizes a separate
coordinator engineering review, not a fabricated external/subagent approval.

## Usable capability

Add FactStore::recall(query, predicate, limit, max_bytes), CLI `fact recall
--query ...`, and `memory_read(view=recall, query=...)` behind the existing
source/read gates. Unlike listing the newest facts, filter literal quote matches
BEFORE the 100-candidate cap. Query must be nonempty valid UTF-8, NUL-free,
<=1024 bytes and pass the existing sensitive-input check. Optional predicate is
an exact filter. Preserve SQL binding and ASCII case behavior of SQLite lower;
no embedding, synonym, segmentation or truth-score claim.

For each active, valid matching fact, include its COMPLETE original quote and
all currently supported direct active explicit contradiction neighbors, even
when neighbors do not match the query. This prevents query selection from hiding
counter-evidence. One result item is a whole neighborhood: match_fact_id,
facts with provenance/revisions, and canonical contradiction edges. It is not a
transitive conflict component: explicitly label direct-neighbor-only semantics.
No recursive traversal, no winner or automatically inferred contradictions.

All endpoint reads share the candidate SELECT's SQLite snapshot and one call-local
ReadWork (512 evidence validations / 8MiB transcript work). Retain 32-relation
per-fact bound and enforce it before publishing a neighborhood. Results are ordered
created_at descending then fact_id, not by assumed truth/relevance. Independent
matching anchors may repeat counterpart facts; do not skip a matched counterpart
and silently lose its other edges. Limit 1..50 neighborhoods and 512..32768 UTF-8
JSON bytes. An incomplete/non-fitting neighborhood is never partially emitted;
stop and mark truncated. Empty with truncated does not establish absence.

## Compatibility and non-goals

No new schema, migrations, writes, backups, jobs, provider calls, capture consent
or MCP names. Existing memories/facts/conflicts views keep their behavior. Recall
rejects history/event/fact_id parameters, strict unknown fields and types. The
current Hook is deliberately unchanged: automatic host injection requires its
own opt-in and total-context budgeting stage; this usable retrieval endpoint is
its prerequisite, not an automatic-host-acceptance claim. PostgreSQL remains
outside FactStore support. Existing P3 observations remain tracked separately.

## Falsifiable acceptance

Tests cover no schema on reads; matching older-than-100 facts; whole negated
Chinese/mixed quotes; literal wildcards and SQL syntax; mandatory query and strict
UTF-8/NUL/length/types; source/predicate isolation; hidden invalid/expired/forgotten
facts; nonmatching valid counterparts; no inference from differing quotes; complete
star neighborhoods and explicitly nontransitive output; multiple anchors and no
lost counter-edges; exact byte/limit/work truncation; unchanged revisions/jobs and
write-denying authorizer. Deterministically commit a second WAL connection's
forget during a read: complete prior neighborhood now, updated next call.

Exercise real CLI/MCP with default write refusal, source allow-list, six-tool
registry and unchanged prior views. Add the 51st native group, standalone unit
and source/EXE/script-bound process reports, strict negative report tests, all
old Windows/portable/Server2022 gates and original package identity checks.
Run a separate outcome review, fix its findings, and do not claim Windows PASS
from Linux checks. Rollback is a source revert; no database downgrade needed.

Reference: https://www.sqlite.org/isolation.html (read September 14, 2026).
