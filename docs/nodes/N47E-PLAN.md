# N47E — explicitly enabled local event-to-fact promotion

Baseline: dfca4b6a7b01730431df92974fe5a6251c999953 (N47D already shipped).
Status: done for the scoped repository implementation after N47E-HARD-AUDIT.md.
Tested/reviewed source: c6c76a2f3fd2dd0b07326ef6e19c1a59283402e8.
Native evidence: 34906704753 and 34906704707; publication is recorded separately.
Includes the narrow expired-support renewal repair in N47E-RENEWAL-REPAIR-PLAN.md;
old aa34e59b results do not certify the repaired candidate or its delivery bytes.
Scope: Windows-native youq616/qbrain only. Owner authorizes separate coordinating
agent engineering review, not an invented external/subagent review.

## Actual missing connection

N47D recalls facts but still requires explicit fact creation. Add bounded
FactStore::promote_event, CLI `fact promote --event ID`, existing
memory_write(action=fact_promote,event_id=ID), and an independent default-off
installer switch `-EnableFactPromotion`. The switch requires -EnableCapture;
it does not enable fact recall, model extraction, summaries or MCP write access.
After a captured prompt has actually been locally extracted, an opted-in Hook
promotes its extracted complete user quotes automatically, without model calls.
Read/recall happens before capture and promotion; no caller transaction is reused.

Only local extracted events are eligible. Up to 32 items, ordered by original
message index and item ID, are validated before optional module initialization
and again under one write transaction. Invalid/expired/tampered/cross-source
items fail the entire batch of fact/evidence changes. A valid no-matches event
produces a no-op without creating the optional module. Fact predicates are the
fixed labels memory.<existing category>; values remain entire original quotes,
confidence stays null and no semantic truth or contradiction is inferred.

A same-source, same-predicate active equal quote receives additional support
rather than a duplicate fact. Deterministically choose the oldest matching fact.
Previously attached items are no-ops. Any existing inactive fact with the same
source/quote vetoes automatic promotion, irrespective of predicate; do not revive
retracted/superseded claims by replaying or repeating a quote. The 16-support cap
is respected with an explicit skipped-limit outcome, not a second fact. Do not
change manual create/attach behavior, revive status, or merge unrelated predicates.

Return bounded receipts and counts (created/attached/duplicate/skipped-retired/
skipped-limit), no raw quotes. Fact/evidence batch changes are atomic; existing
lazy schema initialization/backup is a separate preparatory operation and may
remain after a later batch rollback. Document this distinction. No new schema,
persistent promotion queue, model permission or broad knowledge claim.

## Host consent and failure semantics

The config boolean fact_promotion is strict, default false. Both installer and
Hook require capture and local extraction for automatic promotion. Install Status
reports the effective flag; reinstall without it turns it off, uninstall disables
it. Existing installations remain unchanged when the field is absent. Promotion
errors are recorded separately from successful capture/extraction, never as PASS;
do not include prompt/quote/credentials in trace. No silent retry loop. Failed
promotion can be explicitly retried by event ID. Client egress is unchanged and
real authenticated client consumption is not certified by event fixtures.

## Falsifiable acceptance and review

Actual production unit tests: multi-category complete quotes/negation, local-only,
no module on no-op, strict IDs and source checks, replay/idempotence, two supports,
retired quote veto, support cap, atomic injected rollback, expiration/tampering,
forget cascades, simultaneous two-connection promotion, held-writer bounded waits,
legacy schema and unchanged manual behavior. Real CLI/MCP and Hook subprocess
checks exercise consent defaults, invalid config, source/write denial, no partial
batch, current-event promotion and following-event recall. Real PowerShell 5.1/7
installer tests verify dependency, reset and rollback/ownership behavior.

Register group 53 and standalone/source-EXE-script-bound evidence. Keep all prior
fact/recall/conflict/Hook/HTTP/CJK/queue/memory/PowerShell/native gates. Fail-closed
report tests must catch partial, stale, wrong-count, wrong-code and malformed
results. Review implementation separately, including fault injection and an
independent expected-state oracle where practical. Do not mark stage done without
actual native results; no Linux-as-Windows claim. Preserve existing failures.

Rollback is a code revert; existing promoted facts remain ordinary N47A facts and
can be explicitly retracted/forgotten. Forget is per support event, not secure
erase of backups or independent unforgotten equal quotes. Automatic semantic
extraction, conflict inference, decay/profiles, real host/model quality and PG
parity remain outside this local deterministic promotion stage.

References consulted: https://www.sqlite.org/lang_transaction.html and
https://www.sqlite.org/c3ref/backup_finish.html.
