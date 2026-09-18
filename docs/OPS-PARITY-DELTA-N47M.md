# N47M ops delta — draft candidate

Existing operations only: `memory_read`, `memory_write`, local memory drain,
`context_read`, `context_write`. No added tool, migration, external permission,
Hook default or semantic capability.

The candidate repairs CLI named-value and manual-flag routing in memory/context.
The CLI must pass the intended source and brain to the existing operations even
when query/source values equal switch names. Existing operation authorization and
consent checks remain the authority. No claim is made that all CLI handlers share
a strict grammar; search remains a separate documented issue.

Status: local implementation/tests passed in the recorded scope; native and real
independent outcome gates remain pending. Main ledger completion is not advanced
by this delta. See `nodes/N47M-PLAN.md`, `nodes/N47M-HARD-AUDIT.md` and
`nodes/n47m-evidence/LOCAL-VALIDATION.md`. Do not use this draft as release approval.
