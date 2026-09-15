# N47E outcome review — local event-to-fact promotion

Verdict: **PASS for the scoped repository implementation**, including the expired
support renewal repair. Reviewer: ChatGPT, a separate engineering self-review
under the owner's instruction. Not a third-party or independent-subagent audit,
and not a guarantee that no latent defect exists. Review date: September 15, 2026.

## Exact reviewed source

Baseline: dfca4b6a7b01730431df92974fe5a6251c999953 (merged N47D).
Reviewed implementation: c6c76a2f3fd2dd0b07326ef6e19c1a59283402e8.
Reviewed tree: 07f00ef07fc1cb79642472b63052221c84bb2db1.
The 760-file source artifact was checked against its external SHA256, extracted
with bounded safe member handling, and reconstructed to this exact Git tree.
Every local source byte still equals that artifact after the additional checks.
This outcome pass adds records and a local acceptance task, not product edits.

The earlier aa34e59b candidate is NOT the release candidate. The preserved
N47E-RENEWAL-REPAIR-PLAN.md documents the original whole-support-expiry liveness
failure and the approved narrow repair. Its earlier passing CI does not certify
c6c76a2f. The new native runs and the supplemental execution below do.

## Plan-by-plan assessment

| Requirement | Reviewed implementation and evidence | Result |
| --- | --- | --- |
| Actual automatic connection | FactStore::promote_event, fact promote --event, existing memory_write fact_promote; opted-in Hook invokes it after current-event local extraction | PASS |
| Independent consent | EnableFactPromotion defaults off and requires EnableCapture; does not enable recall, model extraction or MCP writes; strict booleans, reinstall reset, uninstall | PASS |
| Exact evidence rather than inferred truth | Whole extracted user quotes, fixed memory.category predicates, confidence=null; assistant/model-method/expired/tampered/wrong-source input rejected | PASS |
| Atomic business writes | All incoming items preflighted and revalidated inside BEGIN IMMEDIATE; injected failure rolls back the fact/evidence batch; existing backup/schema preparation is separate | PASS |
| Idempotence and bounded support | Replay does not advance revisions; identical independent quotes attach; physical support cap 16 and explicit skipped_limit; no duplicate overflow fact | PASS |
| Retirement is not undone | Any same-source retired equal quote vetoes automatic promotion even across predicates; manual operations remain unchanged | PASS |
| Safe expiry renewal | Existing active exact-quote target is renewed only from a new currently valid event, with all historical supports intact and expired; status/old expiry unchanged, no expired evidence in live reads | PASS |
| Privacy and concurrency | Forget cascades, remaining support retention, no revival; two actual connections, held-writer timeout and deterministic preflight invalidation tests | PASS |
| Failure transparency | Receipt counts derived from actual outcomes, no raw quotes in receipts/trace, promotion failure separate from capture/extraction success, no retry loop | PASS |
| Compatibility and packaging | Exact 53-group registry plus retained native suites and complete source/EXE/script-bound evidence checked before packaging | PASS |

The historical at=0 validation is eligibility checking inside promotion only.
It is not used to publish historical evidence as live. If only part of the old
support set validates, renewal is rejected; one valid historical row is not
sufficient. Full expired support sets still hit the physical 16-support limit.
A fresh independent event is required: replaying the expired event remains denied.

## New native results, not inherited candidate results

Development run 34906704753 and N42 run 34906704707 completed successfully on
c6c76a2f. All required source, portable, full Windows regression/package and
Server 2022 jobs passed. Generic publishing jobs stayed skipped/disabled.

- Exact Windows registry: 53 groups. Real PostgreSQL DSN cases remain SKIP-PG.
- New promotion unit: 18 scenarios / 237 assertions on Server 2025, Server 2022
  and Linux portable, including the new expired-target transitions.
- New CLI/MCP/Hook fixtures: 68 named checks / 77 commands on Windows and portable;
  70 expected exit-0 results and seven expected negative exit-1 results.
- New promotion installer: 33 checks on each of PowerShell 5.1 and PowerShell 7.
- Prior Hook fact composition: 13 scenarios / 229 assertions, 52 process checks /
  72 commands and 33 installer checks per PowerShell version.
- Prior facts: 15/380 unit and 34/118 process; conflicts: 13/346 and 38/75;
  recall: 15/330 and 44/71; CJK: 72 unit / 36 process.
- Each Windows HTTP job: 81 wire checks, fixed cancellation controls/current
  repeats and explicit final cache shutdown. Queue: 40 scenarios / 776 assertions.
- Embedding unit/wire/search: 65/26/11. Memory/MCP/Hook/context/config: 44/17/69/65/6.
- Existing PowerShell 5.1/7 each: install 69, consent 16 and transport 8.

Five original artifacts were downloaded and checked against external digests.
The complete package inventory, original report byte equality, full unit scenario
lists, assertion sums, command exits, source/script/EXE identities, both Windows
HTTP schedules and original registry/logs passed **216 readback checks**.
Probe executables were not downloaded separately: their hashes come from pinned
original reports and the original packaging job's checks of actual probe files.
This readback is not a new Windows runtime execution.

## Separate supplemental execution in this continuation

Rebuilt unchanged bundled SQLite C and application C++ with Clang 17,
AddressSanitizer and UndefinedBehaviorSanitizer, -O1 and halt-on-error. Actual
promotion unit 18/237 and real CLI/MCP/Hook 68/77 completed successfully without
sanitizer diagnostics. Linux instrumentation is not Windows sanitizer evidence.

An independently written expected-state oracle used the actual CLI, not the
implementation's query as its expected-state model. A fixed seed drove two
sources, repeated/independent statements, retirement, forgetting, cap exhaustion
and capacity release. Additional real wall-clock expiry cases compared intact
history with partially damaged history. **47 synthetic events, 218 commands and
1,003 repeated state assertions passed**. These are not 1,003 distinct user
scenarios. The oracle verifies exact supporting event sets, unchanged old expiry,
same-ID renewal, no writes on rejected renewal and no automatic relations/jobs.

Two isolated, deliberately broken implementation copies were compiled against
the same sanitized test harness. Bypassing the retirement veto failed with
"repeated quote cannot auto-revive retirement"; bypassing complete historical
support validation failed with "operation should have failed". Both exited 1 as
expected. Neither mutation was applied to the candidate or delivered executable.
These prove detection of those two defects, not exhaustive mutation coverage.

All 96 existing report-gate tests were rerun successfully: promotion 13, Hook
fact 12, recall 10, conflict 10, fact 12, CJK 10, HTTP lifecycle 14, registry 15.
The archive reconstruction deliberately has no HEAD commit; local unit/process
reports retain source_commit=null rather than fabricated attribution. Their
exact source bytes are bound separately by the reconstructed tree.

## Findings, preserved failures and limits

No unresolved scoped P0/P1 blocker identified after checking the renewal repair.
The initial readback helper referred to a nonexistent installer test filename;
it was corrected to the actual test_promotion_install.ps1/test_hook_fact_install.ps1
names. Its original KeyError log was retained. One preliminary gate orchestration
call timed out before its final suite completed; all 96 gates were subsequently
executed in a complete run. Product code and assertions were not changed for
these helper/orchestration corrections.

The original renewal failure remains documented; this review does not repeat or
relabel the earlier candidate's success. Existing N47A P3 observations remain
follow-ups, not silently fixed. The promotion pre-read uses existing storage
policy; finite concurrency tests are not a guarantee of every scheduling outcome.
The batch limit and support caps do not promise a whole-operation latency bound.

Schema/backup preparation can remain after a failed business transaction. Closing
promotion does not retract existing facts. Forget operates on support events;
other independently retained equal quotes and backups/WAL/previous client context
are not secure-erased. Hashes provide local integrity checks, not signatures or
protection against an actor who can rewrite the entire database and all hashes.

This deterministic local-marker promotion is not general semantic extraction,
truth verification, automatic contradiction inference or conflict resolution.
No new schema, MCP tool name, provider permission or user-global client setting.
Hook output can be sent by the user's client to its model; no extra Qbrain model
call is not evidence of no client egress.

## Delivery and remaining real-host boundary

Original tested inner ZIP: 1,986,872 bytes, SHA256
50395502dbcf65d142fd36a0f511dc8b764971bcfd5854d466e8d2e38e04ae73.
EXE: 3,965,952 bytes, SHA256
f9ed4d157f46e5ee25fc1f92449a805b1c9a51bdf65faf9a42b443c9266e2c29.
PE32+ AMD64, no embedded Authenticode certificate; unsigned development preview.
Neither file was rebuilt/repacked for delivery. Integration and fixed versioned
promotion may proceed after verifying this documentation-only outcome head.

Real authenticated Claude/Codex consumption is not established by fixtures.
The repository task N47E-LOCAL-ACCEPTANCE.zh-CN.md limits the necessary local work
to fresh isolated client sessions using the published exact package. No compiler,
source edits, repeated code audit, GitHub write credentials or Codex key changes.
Full project/N47 completion, PG parity and signed production release are not claimed.

Primary references checked during this review:
https://www.sqlite.org/lang_transaction.html
https://www.sqlite.org/c3ref/backup_finish.html
https://code.claude.com/docs/en/hooks
