# N48E — Complete OpenCode project configuration lifecycle integration

2026-09-21. APPROVED after the separate plan review below. Owner explicitly requests a complete module and coordinator self-review. Base main ce2e26201fcdf977a507f895c081ab09f83359b8. This integrates the already-developed local N48A/B/C configuration module rather than adding another diagnostics-only capability. The old plan-only branch is not declared merged or overwritten.

## Scope

Integrate the exact supplied N48C combined source (local bundle qbrain-N48C-opencode-reconciliation-module.zip) with its A/B dependencies. Register native opencode commands before ordinary brain setup, beside but without modifying N48D mcp-check. Expose preview/install/status/audit/uninstall/recovery/reconciliation. Reconciliation adopts only unrelated edits around an unchanged managed entry; no arbitrary server takeover, automatic repair or privilege expansion. Existing owner-v1 and journal-v1/v2 semantics remain. Preserve original tests and historical local-only audits without relabelling them as native evidence.

Use three bounded JSONC/configuration/audit headers and an additive standalone CMake test project. Only main.cpp needs an inherited production change: no overwrite of the large CLI dispatch, root CMake, installed Hook, byte bridge, database, source permissions or ledger. No new MCP tool name. Defaults remain read-only and V1/V2 must be explicitly selected; official current configuration contracts are checked again. State files may contain private before-images and are not described as sanitized reports.

## Falsifiable acceptance

1. Compile actual new product on Windows MSVC and Linux. Execute all existing A/B/C direct and process tests without removing assertions. Native path/ACL/replace behavior is not inferred from Linux. Preserve original full60 Windows and six Linux core/batch groups, fourteen process suites and N48D runtime tests.
2. Preview/status/audit must not initialize the user's default brain; old no-argument/help behavior is retained apart from additive command help. Explicit approved mutations touch only a disposable project in tests. No credentials or real user configuration is used.
3. Exercise both configuration formats, both write settings, unrelated JSONC preservation, explicit edit reconciliation, normal access update, uninstall, interrupted apply and recovery. Record exact final binary/source/test identities, raw outputs and failures.
4. Separately review parser spans, managed-entry identity, journal consistency, lock and per-write rechecks, Windows encoding/path differences and code integration. Add tests for any blocking finding, preserve original failures and rerun changed code.
5. Verify generated configuration against official OpenCode schema/source. Attempt version-pinned real OpenCode configuration-loading/MCP catalog checks only on isolated fixtures without accounts, credentials, model prompts or tools/call. Record exact versions and boundaries. Unsupported/unavailable versions stay NOT_RUN rather than faking host acceptance; the source configuration-management module can only be accepted with its own native gates completed.
6. GitHub writes use the existing authorized connector only. A denial stops that attempted delivery; no alternate transport, workflow or destination circumvents it. No public release/tag is modified in this node.

## Separate plan review

Reviewer: coordinating ChatGPT, a separate owner-authorized engineering pass, not a subagent or third party. Verdict: APPROVED for this bounded integration. Reusing local-tested bytes is not native acceptance. Routing before brain setup reduces unnecessary side effects but requires fresh combined-binary tests. Keep all historical A/B/C assertions; create a new native evidence bundle instead of trusting earlier counts. Changed paths and unknown recovery images must refuse, not force restoration. Temporary projects and account-free host checks avoid private-data/provider exposure. Real host configuration loading does not prove model consumption, and self-reported bytes do not authenticate a release.

## Rollback and limits

Remove the additive headers/entry and tests to roll back code; a pending v2 journal must first be recovered by a compatible version. Per-file atomic replacements and cooperating locks do not constitute a cross-file transaction, hostile-admin defense or absence of final check-to-rename races. Do not close Issue40 or real-client/model/fees/PG/signing/stable-v1 gates. No promise of zero defects. Final outcome audit and exact merge readback are required before announcing integration complete.
