# N48U — PostgreSQL directory-scoped cache invalidation

2026-09-30. Base e0a27f829d970c24ed8c566023ada0911c0042b3, tree
534c86deabf43e30d3b2533cd3bf1f0728cf8400. Status: approved after separate
N48U-PLAN-AUDIT.md. Origin: Issue2/N45 finer ancestor-directory updates. This is
the real PostgreSQL counterpart, not another packaging/evidence-only module.

## Ownership and original backlog

PR62 stays at848ef980 for its already-arranged non-author incremental review; no
wait for b821's already-closed review. Its six changed paths and all its other
files remain unchanged here. PR61's six files and head4fb5f7bc remain untouched.
No merge, deployment, release, new EXE package or changes to existing test gates.
Implement on a distinct branch based on published main, with no dependency on either
unmerged branch. Required later: compose with PR62 and requalify the unified version.

The still-open original requirements include PG fine-grained invalidation (chosen),
all-runtime attempt/usage accounting (Issue2/N46), query/vector caches and model
provenance, guarded semantic merge/cleanup, full access-control audit, and real-client
and real-model validation. Historical SQLite-only statements are superseded by
N48O/P/Q/R, not a reason to redevelop those backends. Scope/deployment decisions and
remaining version/scale requirements stay in the master plan, not deleted here.

## Contract

Change only PG helper(s) and new tests/workflow/documents; no context.cpp edit.
The existing cache column layout/module version1 remains the schema contract. A
recognized function body distinguishes source-wide policy1 from directory policy2.
Keep its existing SQL function name/OID/triggers/ACL during a verified upgrade.

- Literal source + namespace + ancestor-directory membership, including namespace
  root, empty cache and capped previews. No LIKE wildcard/case folding. Unrelated
  complete rows/model summaries remain byte-identical. Old and new row identity on
  moves/soft delete/restore; INSERT/UPDATE/DELETE/UPSERT handled. TRUNCATE clears all.
- Reads accept the known legacy policy without migration. Explicit summary publication
  rechecks evidence/consent, then initializes/upgrades under the existing ordered
  source/pages/config write locks. Only an exactly recognized owned legacy function
  may be CREATE OR REPLACEd; its identity/ownership/ACL remain. Unknown functions,
  altered/extra trigger users or malformed module layouts fail closed before provider.
- Upgrade clears all legacy derived l0/l1/refs once. Function replacement, legacy
  clearing and current summary write are one transaction. Publication failure or
  lock timeout leaves the old function and cache rows intact. No CASCADE or schema
  downgrade operation. Two initializers/upgraders serialize correctly.
- Do not narrow permissions, make new provider calls or change write/read ownership.
  Model callbacks still outside read transactions. No provider reattempt on failure.
- An older binary expects the old exact body: after a policy2 upgrade its context
  access fails closed. This compatibility boundary must be documented and tested;
  operator rollback requires a pre-upgrade PG backup or a separately reviewed policy
  restoration, never silently downgrade/delete server data.

## Falsifiable validation

New real PostgreSQL tests (no mock server substitution) inspect complete cache rows,
function OID/owner/ACL, caller transactions, migration rollback and unrelated caches.
An old-policy fixture must fail the new selectivity expectation before upgrade.
Cross-source/namespace/case/underscore/Unicode/root/ancestor and 256-cap cases; normal
UPSERT, conflict no-op and rollback; disabled/wrong/extra triggers/functions, denied
provider, late evidence/consent change; concurrent initializers and actual two-connection
lock timeout. Positive model summary retains a single synthetic provider call.

Fresh Linux/Windows PG builds and original N48P198 plus core and related old suites
must execute on the candidate. Add an independent real-CLI/psql mutation oracle with
raw commands, stdout/stderr/exits and complete before/after rows. Checks survive -O.
Retain all failed attempts. Local compilation/sanitizer is additional, not PG server
validation. Full60/55 release acceptance and new non-author outcome review remain
separate; do not invent those passes.

No user database, paid model or login is used. Same DSN/different brain is not hard
isolation. Trusted schema owner, no malicious-DDL concurrency guarantee. PostgreSQL
server roles/TLS/backups are operational responsibilities. Existing statement/lock
budgets unchanged. Trigger scans are not a measured throughput/cost improvement.

## Tool-boundary amendment before candidate publication

The connector rejected upload of tests/test_pg_directory_cache.cpp via a platform
safety check. No alternative encoding/interface is used to submit or execute that
blocked test. Its local source and attempted operation remain recorded, not counted
as native PG execution. The mutation/process tests are not part of the remote
candidate. Their specific migration/rollback coverage remains PENDING.

Continue permitted work with an actually read-only PostgreSQL SELECT/VALUES predicate
matrix (no schema/application writes), plus the repository's already existing,
unchanged native PG/context/memory/fact and public CLI regressions. This narrower
qualification cannot close every dedicated migration/selectivity gate above. The
module remains draft/incomplete acceptance even if these permitted checks pass.
No comparison with unavailable test counts is presented as success.
