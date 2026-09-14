# N47B capability delta

Tested/reviewed product: 7999d39b9e6a253d62557a6ccc8341598ccdebb6.
Native runs 34798495285 and 34798495355 completed required checks successfully.
See N47B-HARD-AUDIT.md and n47b-evidence/SUMMARY.json for scope and exact bytes.

Added FactStore::conflicts, CLI `fact conflicts`, and existing
`memory_read(view=conflicts)`. Only explicitly recorded active contradiction
pairs with valid original evidence are returned. Both complete endpoints carry
revisions and provenance together; no winner, inferred conflict or confidence.
Source gates, read-only behavior, coherent snapshot and whole-pair byte limits
remain mandatory. Truncated empty output must not be called absence of conflict.

No database migration, new MCP tool name, automatic provider call, capture consent,
new dependency or automatic fact recall. Previous fact writes and history remain.
CLI help now states that fact writes read JSON stdin; behavior does not change.

The native registry is now 50 groups. New tests cover 13 unit scenarios and 38
actual CLI/MCP checks. Both Windows versions test the conflict unit and inherited
HTTP implementation. Local Clang sanitizer execution is additional Linux evidence,
not substituted for native checks. No PostgreSQL conflict view, semantic resolver,
N47 completion or whole-project parity claim. Review is a separate coordinating
agent engineering pass, not a fabricated external/subagent approval.
