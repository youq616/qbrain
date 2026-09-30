# N48U separate plan review

2026-09-30. Reviewer: ChatGPT coordinator, owner-authorized design self-review;
not a non-author outcome approval. Verdict: PASS to implement this bounded contract.

Read Issue2 original N45/N46 requirements, main PG context policy/publication flow,
original PG tests and the PR61/PR62 protected paths. The runtime scope touches only
PG helper code; no file collision or prerequisite from either unmerged branch.

Chose verified CREATE OR REPLACE of the known legacy function rather than DROP and
recreate: preserves OID/ownership/privileges and avoids changing public trigger names
used by existing tests. All unknown/custom body, function flags and foreign trigger
users must refuse; it is not carte blanche to replace SQL objects. Module version1
is the unchanged row schema, not an assertion that old binaries understand policy2.
Old clients must fail closed; no automatic downgrade.

Rejected refs-only invalidation (misses new/empty/capped pages), LIKE (wildcards and
collation), new-row-only updates (old source/namespace stale), and migration before
permission/evidence revalidation. Fixed literal membership and transactional legacy
clear preserve confidentiality and rollback. No need to touch PR62's snapshot metadata
fix: that has separate review, and is neither credited here nor copied into this branch.

Native PG outcome is a gate. Local apt/network failure or a SQLite pass is not PG
qualification. Changes to exact DDL/permissions and rollback receive dedicated
negative and positive tests. Real host/model, RLS/DLP, scale and signing remain open.

Primary sources reviewed: PostgreSQL14 CREATE FUNCTION (OID/ACL preservation under
replacement, SECURITY INVOKER), CREATE TRIGGER (AFTER row and TRUNCATE semantics),
dependency tracking. This plan is approved before runtime implementation; outcome
verdict will be based on executed evidence, not this approval.

Tool-boundary amendment review: permit the separate read-only SQL test and unchanged
existing regressions, not a retransmission of the refused test or implementation
of the refused operations by another tool. No dedicated mutation/upgrade acceptance
claim without the original missing coverage. Keep the candidate draft and separate.
