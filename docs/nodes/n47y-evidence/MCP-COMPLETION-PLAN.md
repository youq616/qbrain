# N47Y completion review: advertised MCP receipt paging must actually work

2026-09-20. Approved before repair by the coordinating ChatGPT in a separate
engineering review, under the user's request to finish a complete module and
self-review it. This is not a separate subagent or third-party audit.

The candidate39357bae has successful native/portable CI, but an independently
written long-lived stdio MCP test exposed a real integration gap. The published
memory_read schema advertises receipt_state and snapshot; the independent typed
MCP argument gate in src/qbrain/mcp/server.cpp does not accept either. A filtered
page returns invalid_argument before the receipt validator is reached, and a
snapshot continuation would be blocked too. CLI-only or denial-only tests cannot
certify this advertised MCP path. Do not accept39357 as the complete module.

Scope addition to the original approved integrity plan: add exactly receipt_state
and snapshot as Type::String to memory_read's existing typed allowlist. Retain all
unknown-field, wrong-type, source/write and route-local validation. No new tool,
parameter semantics, stored schema, automatic repair, privilege or default.
This is a necessary wire-adapter completion of existing APIs, not a blanket
relaxation or a new PostgreSQL/real-client acceptance claim.

Add a separate test file, leaving all123 integrity,75 usage,71 page and existing
native/process tests unchanged. Exercise actual authorized persistent MCP: healthy
advertised four-state pages and full continuation; malformed types/filter/cursor;
all seven nonempty TEXT/BLOB identity combinations across five execution paths;
three controlled writer-lock corruption schedules; revoke-abort rollback and
post-error reuse. Preserve the first failed report and prove the new test rejects
the exact previous candidate, then run it on repaired Windows/Linux products.

The original full60 Windows and four focused Linux groups remain mandatory.
Update the existing N47Y workflow only by adding the new test and its trigger;
retain original compilation and every old assertion. Final review must recheck
fixed artifacts and bytes after repair. This changes the original two-header-only
boundary by one explicitly reviewed MCP adapter file; original read/write behavior
and production module data policy are not widened. Issue40 and external gates remain.
