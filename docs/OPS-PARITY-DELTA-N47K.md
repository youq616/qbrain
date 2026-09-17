# N47K capability delta

Tested source a23800df3709ac9ef73a51d150b64d2d20d7d21f, tree
b95af421ea5ebb756a127fe8cc519b5b62e17cf6. Required runs35186099196 and35186099174
completed successfully. See N47K-HARD-AUDIT.md and n47k-evidence/SUMMARY.json.

Added local `hook diagnostics --config <absolute installed config>` with optional
fixed event and exact session-key. Read only config.host's five known checkpoints;
no MCP endpoint, Brain open, model call, file creation or normal Hook behavior
change. Complete strict canonical-record checks reject unknown/type-confused or
malformed metadata, without echoing rejected contents or original paths.

Output INSPECTED and per-slot present/missing/invalid/unreadable/unsafe_path/
oversized/session_mismatch. These describe inspection, not live-host consumption,
record authenticity or installation health. Disabled configuration and historical
records remain distinct. Byte/file counts are bounded; filesystem races, hardlinks,
OS access-time changes and cross-file snapshot consistency remain documented limits.

The direct-MSVC source/object omission was repaired in both link lists and ten
static closure tests were added without a new standalone-script dependency.
Actual59-group native regression and final package now pass; diagnostic11/107
unit and60/68 CLI reports are source-bound. This stage completes the scoped
local diagnostic command, not automatic lifecycle policies or the whole project.
