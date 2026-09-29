# N48P separate outcome audit — PostgreSQL layered context

2026-09-29. Reviewer: ChatGPT coordinator, explicitly authorized by the owner to
perform a separate engineering self-review. Not a third-party/subagent review and
not a zero-defect guarantee. **PASS for the bounded N48P source module.**

## Exact scope and contribution

Base main17a9998f5e874cd233ebb5b4ac70748fbe9e412d. Qualified candidate
136a4828ec31eeb5d870b3a3814d5b5c533783d6, tree
557fe883fa403c86eddd02567cb13248ba82aec6. PR58 already contained the runtime support
and the corrected Windows UTF8 fixture when this continuation began. This closeout
does not misattribute those changes as newly authored runtime fixes. It contributes
independent semantic readback code, separately written actual process probes,
completed execution review, documentation and a fixed-binary delivery.

The module adds the PG path to existing context list/read/summary and MCP operations,
not another memory-confidence ledger, fact_store implementation or real-host harness.
SQLite stays default; no automatic migration, new MCP operation, release replacement,
credential or real-user database use. Actual merge identity belongs to PR58 and the
delivery record, not the earlier frozen CI record.

## Review against the approved plan

| Contract | Inspected mechanism and executed evidence |
| --- | --- |
| Explicit source/schema and transaction ownership | PG helper checks public, UTF8, origin replication role and effective relation identities. Active/failed caller transactions are refused. Real native tests exercise five temp-table conflicts, explicit public-first lookup, unrelated temp objects, active/failed transactions and callback-created caller transactions. |
| Consistent read and publication | REPEATABLE READ READ ONLY wraps each observation; native two-connection tests observe the old snapshot, then the next committed state. The read transaction ends before the model callback. Publication takes the same ordered sources/pages/config locks as N48O and rechecks evidence, source and permission. Callback edits, revocation, deletion and temp-shadow creation refuse late publication. |
| Atomic optional schema | Only a valid summary publication creates the two optional tables/function/triggers. Four concurrent initializers produce one module row and one cache entry. Unknown layouts, disabled triggers and SECURITY DEFINER substitution fail closed; no CREATE OR REPLACE of unknown user objects. |
| Invalidation | Fully qualified SECURITY INVOKER function, fixed pg_catalog path; INSERT/UPDATE/DELETE/TRUNCATE clear derived l0/l1/refs and mark dirty. Source moves affect both sides, soft/hard deletion and rollback are exercised. Complete final COPY cache and module rows are independently checked without executing dump SQL. |
| Text and bounds | Fixed UTF8 body/revision and nine512-byte pages per backend are independently reconstructed from raw CLI results. Namespace/source/prefix filtering, stale cursor refusal, 256-page/16MiB selected-directory limits and single-page16MiB refusal are exercised. PG CASE keeps oversized body results out of libpq transfer. This does not bound server work, total process RAM or all metadata widths. |
| Existing interfaces/permissions | Full CLI and three-message MCP results are reconstructed: allowed read, disallowed source and default-denied write. Original permissions and caller source resolver are unchanged. Default extractive operation makes no model call. |
| Regression and delivery | Native Windows/Linux real server jobs, old core/full60/55-step regression, full-tree identity, separate output replay and documented limits below. New reviewer code is executed locally and archived; it is not falsely described as part of the earlier native CI job. |

Read the complete pg_context.hpp, changed context.cpp, URI/UTF8 helper, MCP dispatch,
approved plan, native test and CLI/MCP test. No new unresolved blocking product defect
was found. A missing complete-DDL/RLS/hostile-owner guarantee is a limitation, not a
passing test. The code intentionally rejects noncanonical invalidation definitions.

## Fixed-source qualification

Workflow36512018075, attempt1: Linux109226490391 and Windows109226490563 completed
successfully. Actual server versions recorded in the archives: PostgreSQL16.15 on
Linux,14.24 on Windows. This is not an exhaustive PG-version matrix.

Each platform runs198 native assertions:68 SQLite and130 PostgreSQL/setup assertions.
Do not misreport all198 as PG-only. Each Python mode records55 process calls:
42 Qbrain and13psql, with173 checks. Original N48O122/112 direct checks and differential
workflow stages remain. Original Windows60 groups were matched to the registered
source/log. Both original55-step drivers and six core CTests pass.

Both downloaded artifacts match the externally observed size/SHA256 and ZIP CRC.
Their complete1505-file source tree matches the qualified Git tree; Windows1490 files
are exact LF/CRLF transformations and15 match raw bytes. Context pretest program and
test-script hashes were checked. Raw source and program identities are separate;
a ZIP comment alone is not used as source proof.

Four old integrated-gate recomputations match original outputs. Another46 offline
original checker commands (accounting, lifecycle, MCP and receipts) pass with their
negative controls retained. Full driver/nested-driver exits and log digests were
checked. Four additional new context-output readers pass; total54 completed replay
commands. Windows EXEs are read/hashed here, not executed on Linux or the owner's PC.

## Newly written independent checks

review_pg_context.py imports no product or producer helper. It rebuilds the synthetic
source text, whole previews/revisions, raw body pagination, expected native arguments,
fixture SQL strings, MCP results, error codes and all cross-backend observations.
Each of four original reports rejects22 corruptions, including rehashed wrong output,
false cache freshness, unauthorized MCP write, changed source/SQL/cursor and JSON types.
It checks actual complete outputs rather than merely accepting matching report hashes.
Producer native assertions remain producer assertions; this reader is not authenticated
server observation or proof against collusion of all binaries/pins/reports.

probe_context_lifecycle.py is separately written and invokes the actual qualified
Linux product33 times with87 checks in each Python mode. It covers different budgets,
Unicode combining marks/emoji/CRLF, exact byte reconstruction, namespace/source/prefix
separation, optional-DDL avoidance, denied model summaries, rollback, source moves,
cache erasure, soft/hard deletion, stale cursors and the256-page cap. These extra
process tests use SQLite, not a new local PostgreSQL server or model/host consumption.

Local fresh Clang builds run68 new SQLite direct checks and37 original context checks.
A separately configured full ASan/UBSan test build runs the68 checks with zero exit and
empty diagnostic stderr. Both ordinary/optimized original CLI SQLite tests pass21
calls/72 checks. Six documented native demo commands execute in isolated SQLite and
reconstruct the shipped synthetic sample exactly. PowerShell examples are not claimed
executed on the owner's Windows environment.

## Failures retained honestly

The first independent reader expected a DROP FUNCTION SQL string without CASCADE;
fixing the independently constructed expected string resolved the mismatch. The first
metadata helper indexed the outer row list rather than its first row, then was corrected.
The initial replay wrapper wrongly assumed a nested driver's log directory;23 successful
commands before that failure remain partial evidence, not a complete pass. The unchanged
54-command final replay completed in a separate directory. Initial code and logs remain.
An unsupported streaming container invocation started no test and contributes no result.
None of these helper corrections changed runtime code, old assertions or timeouts.

Upstream136a documents the initial Windows psql ANSI-argv fixture failure and its UTF8
hex fix. The corrected candidate retains Chinese/emoji/CRLF; this closeout did not
retrieve the initial failed archive and does not claim its raw logs are in this package.
It is a fixture correction, not a new billing or deployed-user memory vulnerability.

## Final disposition and limits

PASS within the approved bounded module. No known unresolved blocker in reviewed code
and executed evidence. Post-qualification closure may change only docs, the already
executed review material and synthetic sample; original runtime/test/workflow bytes
must remain unchanged before expected-head merge. This is not every possible defect,
throughput, source authenticity, RLS/DLP or full business-semantics acceptance.

Same PG DSN plus another brain label is not a separate tenant. Model summaries remain
untrusted derivatives, tokens/fees are not inferred, and synthetic providers do not
prove model quality. Budgets are byte limits, not model token limits. PG provisioning,
roles/TLS/backups and libpq/VC dependencies remain operator responsibilities. New EXE
is unsigned and no installer/old ZIP/public Release is replaced. fact_store/Hook and
other PG parity, real client consumption, representative model evaluation, signing,
stable release and Issue40 stay open.

Primary PostgreSQL documentation checked2026-09-29:
https://www.postgresql.org/docs/14/transaction-iso.html
https://www.postgresql.org/docs/14/sql-createtrigger.html
https://www.postgresql.org/docs/14/sql-createfunction.html
