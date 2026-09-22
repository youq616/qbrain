# N48G delta — offline provider response to exact token-cost report

cost import adds a brain-free CLI path for three explicitly selected final-response
formats. It returns normalized N48F input and the unchanged exact report. Known
cache partitions, unknown quantities, failed attempts and within-batch duplicate
identities are handled without provider calls, automatic prices or persistent state.

Only an early main.cpp dispatch and a new pure header affect production. No new
MCP tool name, database schema, permission, Hook, installer or canonical inventory
change. Original cost arithmetic and tests remain byte-identical. The canonical
operation ledger stays unchanged; this delta describes the additive diagnostic.

Fixed4182 native Windows/Linux59 direct plus per-mode231/230/690 and all retained
gates passed; independent generated/Fraction checks and sanitizer review completed.
[Audit](nodes/N48G-HARD-AUDIT.md) and [usage](integration/PROVIDER-USAGE-IMPORT.zh-CN.md)
record actual source/bytes and exclusions. No new public release, real provider bill,
model memory consumption, PG or signing result. Issue40 remains open.
