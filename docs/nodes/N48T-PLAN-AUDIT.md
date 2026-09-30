# N48T separate design review

2026-09-30. Reviewer: owner-authorized ChatGPT engineering self-review, not third party.
Verdict: PASS to implement this bounded SQLite slice; no outcome PASS asserted.

Compared original issue #2 N45 request, current source-wide SQLite triggers and N48P
PG guarded schema, current context snapshot/publish flow and N48S ownership manifest.
Cache computation is an actual runtime hot path. Whole-source invalidation is safe but
unnecessarily discards unrelated model summaries. Smaller invalidation scope is useful
without requiring account, host login, a model, signing key or a new delivery ZIP.

Rejected approaches: LIKE patterns (wildcards/case aliasing); invalidating only existing
refs (misses new/empty/capped pages); only NEW image on moves/replacements (stale old
scope); upgrading custom triggers; DDL before final evidence/consent revalidation;
claiming unexecuted PostgreSQL/Windows or signed-in host acceptance.

Chosen mechanism: three named SQLite BEFORE/AFTER triggers with literal full-URI prefix
membership. BEFORE INSERT/UPDATE must also cover unique-conflict rows that REPLACE can
delete without firing DELETE triggers when recursive_triggers is off. Known-v1 upgrade
is inside existing summary publication transaction and a full cache clear, preserving
content confidentiality. Reads do not auto-upgrade; unknown trigger state refuses.

No N48S file dependency, no PR merge/write to its branch, no changes to published ZIPs.
The original PG behavior is left intact instead of altering an untestable server migration.
Current owner explicitly requests self-review. Native Windows gate remains pending until
executed; a Linux success cannot close the complete module/release acceptance gate.

Capability-amendment review: PASS for isolated branch publication and a new native
qualification workflow, with no N48S/main write or PR merge. Keep the shared root
CMakeLists byte-identical using an opt-in deferred test target file. Missing native
execution remains a pending gate, not a rationale for weakening any test.
