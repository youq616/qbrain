# N47K — bounded read-only inspection of Hook checkpoints

Baseline main: 03665e99865069a13212d84357b938c8e9cc662d.
Status: approved after N47K-PLAN-AUDIT.md; implementation/outcome pending.
Windows-native youq616/qbrain only. The owner authorizes separate engineering
self-review; do not invent an independent subagent or a third-party PASS.

## Practical slice

N47J preserves checkpoints but users must manually locate and interpret raw JSON.
Add `qbrain hook diagnostics --config <absolute installed config>` with optional
`--event <fixed event>` and `--session-key <64 lowercase hex characters>`.
No new MCP tool or remote local-file access. Route before normal Hook stdin handling;
normal `hook --config ...` behavior and nonblocking exit contract remain unchanged.

Read only the five known event filenames belonging to config.host. Ignore arbitrary
files, .tmp and legacy last-trace; never fall back to a stale different event.
Config must be bounded strict unique-key JSON with version=1, host=claude|codex and
boolean enabled; other installer fields are not followed or returned. Disabled
configuration may be inspected, but its checkpoints are historical, not live proof.
No Brain open/init, lock creation, migration, capture, provider call or file write.

Revalidate each record against N47J's canonical metadata projection. Require format2,
exact integer/boolean types, known status/phase coupling, matching host/event and no
extra top-level or nested fields. Invalid records never return their original bytes.
Return per-slot present/missing/invalid/unreadable/unsafe_path/oversized/session_mismatch
without original exception text or filesystem path. Optional session filter only
selects an exact stored key, not a user identity or authentication claim.

Bound config to64KiB, record to4096 bytes, at most five record reads and output to
32KiB. Use read-only OS handles, reject nonregular files and final links/reparse
points; check ancestor directories before access. This is not protection against a
hostile actor concurrently rewriting every parent directory or record, a hard-link
privacy boundary, network/OS hard-real-time guarantee or multi-file snapshot.
Separate replacements may be observed at different times. `INSPECTED` means only
successful inspection; missing data is not disabled execution, present/processed
is not model consumption, and hashes are neither authentication nor anonymity.

## Falsifiable acceptance

Header/production C++ tests: canonical valid records, wrong host/event, unknown keys,
secret extras, nested extras, duplicate decoded keys, types/bounds/unsupported version,
forgotten statuses, sensitive error rejection, config/session/event validation,
fixed output budgets and schema-free/byte-unchanged reads. Real CLI tests generate
actual Hook records in disposable brains and inspect both host formats, forgotten
replay, SessionEnd retention and exact session filtering. Corrupt/oversized/directory/
link records are reported without content leakage, with no mutation or brain open.
Bad command/config errors are fixed JSON with nonzero exit; a complete diagnostic
report may include non-present statuses and must not be described as a product PASS.

Register native group59 and standalone tests, source/EXE/script-bound unit/process
reports with negative gate tests; retain all existing Windows/Server2022/portable/
sanitzer and package gates. Review code and fault cases separately after development.
No new real signed-in host run is needed for this local diagnostic command.
Rollback removes the read command only; no data or diagnostic schema downgrade.

References consulted September17,2026: Microsoft CreateFileW and reparse-point
file operations documentation. No extra GitHub authorization or local-agent task.
