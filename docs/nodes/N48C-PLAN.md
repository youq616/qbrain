# N48C — Explicit edit-preserving OpenCode reconciliation

2026-09-21. Base main88c949bad4ea7e15e204008668fde4fdf85e13d2. Continue the verified local N48A lifecycle and N48B audit; their repository/native/host acceptance has not occurred. User explicitly requests a complete module and separate coordinator outcome review, not a claimed third-party audit.

## Module

Add reconcile-preview/reconcile to the native opencode command. Default install/uninstall keep refusing external edits. Reconciliation requires existing valid ownership, a single valid JSONC configuration, and the same semantic Qbrain server definition including executable, arguments, format and write permission. It may preserve comments, unrelated servers, provider changes and formatting, but cannot adopt a changed/missing/duplicated managed entry. No implicit privilege or format change.

After explicit digest approval, remove only the managed member and required separator from the current document, preserve other byte spans, then insert a canonical managed entry and write a new validated owner record with the preserved current unowned content as its undo baseline. Later normal permission update and uninstall must preserve that content. Empty containing objects are deliberately retained. Already exact ownership is a no-op; no automatic reconciliation.

## Falsifiable gates

1. Extend bounded JSONC spans to identify exact member/value/comma ranges; reject malformed/duplicate JSONC. Verify objects/arrays with comments, nested trailing commas, escaped keys, Unicode, BOM and CRLF against independently expected semantics, not only the same parser. Keep existing valid-byte behavior unchanged. Repair any discovered lexical/parser boundary issue with a regression against old code.
2. No scope expansion: selected project only, no symlinks/hardlinks or competing configuration layers, no command/model launch by reconciliation, no write-default change. Exact semantic managed definition required. Plan binds configuration, owner, pending/stages, executable bytes and target state directory. Recheck under existing cooperating lock; stale plans do not mutate configuration/ownership.
3. Reuse two-file atomic replacement and bounded write-ahead journal. New versioned reconcile journal independently reconstructs the before/after pair from valid old owner and external-edited configuration. Recovery restores the external-edited pre-operation configuration and old owner; reject unknown stages/edits or inconsistent journal. Legacy journal-v1 recovery remains supported and tested. This is per-file atomicity with recovery, not a global filesystem transaction.
4. Finish the lifecycle: external edits -> explicit reconcile -> ordinary read/write permission update -> uninstall, preserving unrelated text/semantics; interruption before/after each write and explicit recovery; repeated no-op; stale approvals; different managed settings; wrong types, duplicate keys and missing ownership; precise untouched-byte checks and normal/-O process tests. Retain N48A/B and existing core/receipt suites unchanged.
5. Separate outcome pass examines actual files, regression against old code, faults and source/binary identity. Native Windows and actual OpenCode loading remain distinct required acceptance when available; do not substitute local Linux or generated-command tests for them. No new release, private data, credentials or automatic paid call.

## Delivery and rollback

Add bounded JSONC edits and one explicit lifecycle action; no database or MCP changes. Old owner-v1 stays valid; new reconcile journal has a distinct schema. No schema-free claim about new temporary journal format. GitHub writes must use authorized connector only; preserve any blocked write result without alternate bypass. Save a checked full patch and incremental patch with evidence when repository/native gates cannot complete. Rollback requires clearing pending reconcile via matching version first; never hand-delete unknown recovery material.
