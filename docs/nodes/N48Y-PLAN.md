# N48Y — native Cursor project Hook adapter

2026-09-30. Base e0a27f829d970c24ed8c566023ada0911c0042b3, tree534c86de.
Status: approved after N48Y-PLAN-AUDIT.md; not outcome-complete.
Original obligation: Issue2/N44 Cursor-specific integration, interpreted alongside
09-PROJECT-COMPLETION history and master plan v2.1 §6. This closes the native adapter
and installer slice, NOT logged-in-client semantic consumption or final integration.

## Contract and scope

Extend the existing native hook route and recoverable Windows installer to host=cursor.
Project-only .cursor/hooks.json and .cursor/mcp.json, five documented events:
sessionStart, beforeSubmitPrompt, afterAgentResponse, preCompact, sessionEnd.
Use the official Cursor hook contract fetched2026-09-30 (https://cursor.com/docs/hooks).
No Claude-shaped hook groups in Cursor JSON. Output additional_context ONLY at
sessionStart. beforeSubmitPrompt can collect authorized user evidence but returns
continue=true, never pretend it supports query-time additional context. Do not add
stop follow-ups, tool interception, thinking capture, or auto-loop behavior.

Normalize conversation_id (cross-check optional session_id), generation_id (required
for prompt/response capture identity), workspace_roots and the event-specific body
into the existing internal event contract. Exactly one workspace root must equal the
installed root and actual current working directory; reject multi-root/background
input rather than guess scope. Ignore model/email/transcript/attachments, never open
those paths or collect their strings. Validate prior to brain open/state changes.
Retain exact user statements, independent capture and fact-promotion consent,
source restrictions, sensitive-text suppression, local/deferred extraction and
withdrawal semantics. Unknown event cannot invoke any operation. Session state uses
host=cursor namespace; normalized fixed event names in bounded metadata only.

Installer adds Cursor to the existing transaction/ownership machinery: flat Cursor
entries, version1 validation, JSON MCP map, existing static encoded Windows bridge,
no global config. Refuse modified owned entries/colliding MCP names; preserve unrelated
hooks/settings/MCP, backups, before-images, crash recovery and uninstall disable.
Do not weaken any old guard or assertion. All tests use disposable directories/brains.

## Acceptance

1. Native adapter unit tests: exact public/internal event mapping, typed fields,
IDs/workspace roots/conflicts, all unrecognized events, limits/UTF8/NUL/privacy,
only correct response schema and fixed host trace. No filesystem lookup of input
attachments/transcript; root is explicitly canonicalized for scope checking only.
2. Actual complete binary: cross-session capture/recall, full Unicode quote and
assistant-only nonpromotion, stable generation replay and conflicting repeated ID,
consent off/default, sensitive fields, source/project isolation, fact withdrawal,
empty/error/unsupported event behavior, budget, final state cleanup and trace privacy.
3. Windows PowerShell5/7: install/status/idempotence/uninstall, exact flat hook schema,
version refusal before writes, unrelated entries preserved, explicit capture flags,
actual installed command invocation, late external edit refusal and recovery reuse.
4. Original native/CLI/Hook/installer suites unchanged, fresh Windows/Linux builds,
sanitizers where runnable. Synthetic Cursor events are not signed-in app acceptance.
5. Publish on separate feature/n48y-cursor-hooks with exact tree and reversible patch;
no merge/deploy. Non-author review remains a distinct gate.

## Isolation, risks and rollback

Open PR61–66 file inventories read before editing. This touches only Hook adapter,
trace host allowlist, installer and new tests/docs/workflow. No main/Brain/ops, cache,
context/storage, AI/observation or frozen PG test edits. No new runtime archive.
Other requirement candidates (retention writes, semantic consolidation) are not
silently implemented without their explicit evidence/transaction policies. Client
login/trust confirmation, cloud support, actual consumption, fee budgets, signing,
final60/55 integration and PR63 forbidden upload remain separate dependencies.
Rollback removes owned installation using the existing transaction; no DB migration.
Old executables do not support host=cursor, so install must use the matching candidate.
