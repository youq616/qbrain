# N47E operation delta

Reviewed/tested source: c6c76a2f3fd2dd0b07326ef6e19c1a59283402e8.
Required native runs 34906704753 and 34906704707 passed. Outcome evidence is in
N47E-HARD-AUDIT.md and n47e-evidence/SUMMARY.json.

Added FactStore::promote_event, CLI fact promote --event, existing MCP
memory_write(action=fact_promote,event_id=...), and the default-off installer
EnableFactPromotion flag. Automatic promotion additionally requires explicit
capture and successful local extraction of the current user event. Recall is a
separate flag. No broader MCP authority or new tool name/provider permission.

Promote complete original quotes with fixed memory.category predicates; preserve
negation, source/provenance and confidence=null. Batch fact/evidence writes are
atomic after separate existing backup/schema preparation. Repeat inputs are
idempotent, equal independent statements share support, and retirement/caps are
not bypassed. Fresh current evidence can renew an active expired-support target
only if every historical support remains intact and truly expired; old expiry
and fact status are not reset, and expired support stays absent from live reads.

No new schema, semantic truth/contradiction inference, automatic resolution,
PostgreSQL parity or whole-project completion. Ordinary startup/read remains
unmodified. Hook/installer fixture success is not actual model consumption.

The exact native registry increases from 52 to 53. Promotion unit: 18 scenarios /
237 assertions; process fixtures: 68 checks / 77 expected exits; installer: 33
checks per PowerShell version. Earlier candidate logs cannot certify the repair.
Separate coordinating-agent review includes current sanitizer execution, a
source-isolated expected-state oracle, two rejected mutants and 216 readback
checks. It is engineering self-review, not external/subagent approval.
