# N47G outcome review — explicit atomic lifecycle batches

Verdict: PASS for this scoped implementation. Reviewer: ChatGPT, a separate
owner-authorized engineering self-review after implementation. Not an independent
subagent or third-party audit, and not a guarantee of universally defect-free code.

Baseline main: a81df391448b278797c21a246a2253bb77fe046f.
Actual tested/reviewed product: b1292b54543b9f54cd5e2b71f4ae4bf5f6247385.
Actual source tree: 572dce7081140b7869821e9e2f98b7f1429d6328.
All 796 source files were recovered from the hash-pinned native source artifact
and the complete Git index reconstructed to that exact tree. This outcome pass
made no product, original test, build or package-byte changes.

## Plan-by-plan acceptance

| Requirement | Implementation and actual evidence | Outcome |
| --- | --- | --- |
| Explicit batch, not inferred maintenance | FactStore::lifecycle_batch, fact batch-preview/batch-apply, existing memory read/write routes | PASS |
| Preview has no writes or lease | Read snapshot; write/transaction-denying authorizer; no schema/backup; caller-owned transaction preserved | PASS |
| All-or-nothing policy updates | Whole selection revalidated inside one BEGIN IMMEDIATE; one COMMIT, no public single-item loop | PASS |
| Failure after an earlier item | Original late archive/restore SQL failures; additional ABORT/FAIL/ROLLBACK and commit-stage probes | PASS |
| Preview not authorization | Subsequent evidence/revision changes reject whole batch; apply selected internally, payload apply/force rejected | PASS |
| Strict bounded inputs | 1..32 unique IDs, current revisions, strict fields/types, duplicate raw JSON keys including escaped keys, 8KiB input | PASS |
| Preserved evidence and policy | Same-source valid active facts only; no resurrection, quote mutation, counterclaim hiding or implicit unarchive | PASS |
| Aggregate bounded work | One evidence budget per validation pass; 32KiB complete metadata receipt; no partial-success skipping | PASS |
| Existing entry-point compatibility | Old lifecycle stale_after_days now passes its advertised MCP gate; old views reject unrelated fields | PASS |
| Native regression and delivery | 55 registered groups, new and retained process/unit gates, full source-bound native package | PASS |

The implementation validates selections before optional N47F schema preparation,
then repeats validation with fresh work/cache inside the policy transaction. A
backup and empty optional schema can remain if a later conflict rejects policy
application. This is documented and is not claimed as a rollback of preparation.
No new schema beyond N47F, no extra MCP tool names, no installer default changes,
no model calls, no semantic merge, automatic aging or usage counters.

## Original execution checked in this outcome pass

Development run 35093371931: source, portable, windows, windows-http-2022 and
batch-sanitized all completed/success. N42 run 35093372100 also completed/success.
Generic publisher jobs were deliberately skipped; that is not release evidence.

Windows original registry: 55 names. New batch unit: 15 scenarios / 259 assertions
on Server 2025, Server 2022 and portable. New batch CLI/MCP: 40 named checks /
54 commands on Windows and portable; 39 expected exit0, 15 expected negative exit1.
Batch-sanitized uses Clang18.1.3 and ASan+UBSan for bundled SQLite C and application
C++; new unit/process and old recall15/330 passed. This is Linux instrumentation,
not a Windows sanitizer or a new signed-in Claude/Codex session.

Existing lifecycle17/180 and36/58, promotion18/237 and68/77, Hook13/229 and52/72,
recall15/330 and44/71, conflict13/346 and38/75, facts15/380 and34/118 retained.
CJK72/36, queue40 scenarios/776 assertions, embedding65/26/11 and original memory/
MCP/Hook/context/config/PowerShell flows retained. Both Windows HTTP wire suites
have81 checks and retain fixed cancellation/shutdown schedules. Real PostgreSQL
DSN tests explicitly remain SKIP-PG, not certified by the surrounding group PASS.

Six original artifacts were downloaded, matched to external API SHA256, checked
for CRC and member identities. Complete package inventory and native report bytes
were compared. Full unit scenario sets/assertion sums, process names/expected
exits, source/EXE/test/script identities, installer reports and both HTTP schedules
were revalidated: 234 readback checks passed. Diagnostic probe binaries were not
independently downloaded; their hashes are tied to the externally pinned original
reports and the original package job's checks of actual probe files.

## Additional execution during this review

Recompiled exact original source with GCC14.2 in the current Linux environment.
New unit15/259, real batch process40/54, previous lifecycle17/180, batch-report14
and registry17 tests all passed. Archive-only wrappers correctly retain a null
source_commit; exact source bytes are bound separately by the reconstructed tree.
No new local Windows execution or full local55-group claim is made.

A separate C++ transaction probe linked the same unchanged production libraries
and used original synthetic seed helpers, but checked independent raw database
snapshots instead of trusting success receipts. Five scenarios /67 assertions:

1. sqlite3_commit_hook veto: archive and restore throw instead of returning APPLIED;
   every policy, revision, quote and updated_at remains equal to its prior snapshot.
2. Late ABORT after an earlier member update rolls back archive and restore.
3. Late FAIL likewise rolls back the whole batch rather than preserving prior writes.
4. Late ROLLBACK leaves no policy change or abandoned transaction.
5. A second actual rollback-journal reader blocks COMMIT; a trace confirms COMMIT
   was attempted, bounded wait fails, and the complete batch is rolled back before
   the caller regains control. Releasing the blocker permits an explicit retry.

Every case checks autocommit recovery and restoration of the caller's original
busy_timeout. These probes were executed, not merely proposed. Their source and
machine-readable result are archived in n47g-evidence. They are Linux supplemental
fault tests, not five new user-host scenarios or a filesystem crash/power-loss test.
SQLite references checked for COMMIT-busy and commit-veto behavior:
https://www.sqlite.org/lang_transaction.html
https://www.sqlite.org/c3ref/commit_hook.html

## Findings, retained failures and limitations

Implementation already corrected the real MCP preview payload whitelist omission
and the advertised N47F stale_after_days whitelist omission, with positive and
negative public-route tests. It also rejects damaged oversized stored quotes before
materializing them. Those changes are in b1292b54; this outcome did not quietly
modify a previously tested candidate. No unresolved scoped P0/P1 was identified.

The first local readback helper used an incorrect installer test filename and
stopped with FileNotFoundError. Its original helper was preserved; the path was
corrected to the actual source .ci/test_hook_fact_install.ps1. No product assertion,
report, expected value or gate was weakened to make the check pass.

Preview has no freshness lease: apply may later fail. No-op items still require
current evidence/revision. Receipt after-values are predictions until APPLIED.
Output/input/evidence limits do not bound backup I/O, database scan cost or hard
real-time latency. Archive is not a privacy boundary; mandatory valid counterclaims
remain visible. Old binaries ignore archive policy. Existing expiry/snapshot and
whole-database-tampering limitations remain. No new real user brain or credentials
were accessed. Codex gateway authentication remains a separate untested blocker.

## Delivery decision

The original tested inner ZIP is2025933 bytes, SHA256
85e0f15f907c2bf4ac39c6356d231637251209a902eb7fe6a50476161ae10603.
EXE is4007424 bytes, SHA256
4b236684116664ad31609cd7d7342d13f8e01a2875541cd1049caabfb68ab6c0.
No rebuild/repack of delivery bytes, no embedded-signature claim. Integration and
fixed versioned preview promotion may proceed after this outcome record. General
unreviewed publishing remains disabled. No new local-agent task is required.
N47G completion is not automatic lifecycle management or whole-project completion.
