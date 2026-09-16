# N47I — unambiguous bounded public JSON inputs

Baseline main: f4a07e71df831843989996d8d537e036364591bc.
Status: approved after N47I-PLAN-AUDIT.md; implementation/outcome pending.
Scope: Windows-native youq616/qbrain only. Separate owner-authorized engineering
self-review, not an invented external reviewer or independent subagent.

## Gap and explicit policy

N47G batch payloads reject duplicate object keys, but ordinary fact mutations,
memory capture, the MCP envelope and incoming Hook event currently use parsers
that discard the earlier duplicate before application validation. Repeating an
item_id, expected_revision, source_id, role or prompt is therefore ambiguous.
RFC8259 recommends unique names; this node makes rejection an application policy,
not a claim that every duplicate object is syntactically invalid JSON.

Add a small shared parsing helper that checks decoded key uniqueness separately
for every object, including escaped spellings and nested objects in arrays. Throw
rather than return false from a callback (which would silently discard a value).
Use existing vendored JSON library; no new dependency, schema or persisted data.
Bound raw bytes and parser nesting before accepting a full input. Sibling objects
may use the same keys; case-distinct or normalization-distinct Unicode keys remain
distinct. Do not apply substring matching or normalize user strings.

Apply to public ordinary fact JSON payloads, memory capture payloads, the common
MCP request body and incoming Hook stdin event. Preserve existing batch duplicate
error codes and payload/depth contracts. Ordinary memory/fact duplicate errors
are stable and do not echo the key, values, source or credentials. MCP ambiguous
or over-depth input returns a fixed parse error with id=null before dispatch;
no tool, notification, read or write runs. Hook rejects the event and returns its
existing benign failure response without opening a brain/capturing a partial event.
Existing installed configuration and stored canonical transcript parsers are NOT
rewritten by this node; their broader audit is outside the entry-point scope.

## Compatibility and privacy

All well-formed unique-key inputs retain current behavior and output. Preserve
MCP source/write gates, capability handling, six memory-profile tools, installer
opt-ins, no automatic provider calls and all N47A-H evidence/recall semantics.
Malformed ambiguous inputs intentionally cease to work. No permission is gained
by creating a duplicate, but silent choice is a data-integrity risk; do not invent
an authentication bypass claim. Bounds apply to parsing, not total database I/O.

## Falsifiable acceptance

- Demonstrate old ordinary fact/capture or MCP duplicate acceptance using a
  disposable real CLI/server request; record actual selected value and no secrets.
- Parser unit matrix: top-level, nested, escaped duplicate, key containing NUL,
  identical repeated values, sibling object independence, arrays, string literals
  containing object text, Unicode/case distinction, invalid UTF-8/surrogates,
  malformed syntax, byte and exact depth limits. No partial/discarded success.
- Public C++ routes: ambiguous valid writes must not create schema/events/facts or
  change revision/policy; permissions remain enforced for valid input. MCP duplicate
  source/action/name/id/params is rejected pre-dispatch even for notifications.
- Real CLI/MCP/Hook process tests using raw bytes, not dicts that erase duplicates;
  synthetic local data root, no actual user host/model. Correct UTF-8 and JSON-RPC
  framing/ids, clean process after invalid request followed by valid request,
  installer-generated Hook arguments and zero data change for rejected Hook input.
- Keep existing batch error code and all old suites. Register exactly one new
  native group (57 total), strict source/EXE/script-bound unit and process reports,
  negative report tests and packaging gates. Windows/portable/Server2022 and
  sanitizer validation must use the new source; old green artifacts do not suffice.

Separate outcome review will inspect nested-scope bookkeeping and exception paths,
run a generated duplicate-key corpus against an independent parser oracle and
retain original failures. No stage completion or release until actual results.
Rollback is a source revert; no data migration. No new local-agent task is needed.

References consulted September17,2026:
https://www.rfc-editor.org/rfc/rfc8259#section-4
https://json.nlohmann.me/features/parsing/parser_callbacks/
