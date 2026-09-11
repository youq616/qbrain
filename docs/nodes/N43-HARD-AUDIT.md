# N43 / N44A outcome review

Reviewer: ChatGPT under the owner's standing delegation to implement and review. This is not an independent review or a Claude Code review.

Verdict: PASS for the scoped SQLite memory core and native Unicode/transport gate; not a claim of complete upstream parity or a live Agent/model acceptance.

Tested source: `45c544a929999027789a911614162a06e547fd32`.
Workflow: https://github.com/youq616/qbrain/actions/runs/34579166130
Windows log artifact: `10191172532`.
Downloaded ZIP SHA-256: `6be3c616adf135a310885de3b082fa580bf1e12b42f843a1f898f6fbacb10c8f`.

## Verified results

- Complete native MSVC application build: PASS.
- All 43 names registered by the tested `tests/test_main.cpp`: each appeared exactly once as a complete `[PASS] <name>` line, with no `[FAIL]` lines. Inline subtest messages were not counted as extra groups.
- N43 C++ unit checks: 85 on Windows (platform-specific checks included).
- Real executable memory/CLI/MCP/restart/concurrency checks: 44 PASS, four observed lock retries; retries converged without duplicate events.
- Existing N42 real executable MCP source/read-boundary checks: 17 PASS.
- Native PowerShell 5.1: 8 PASS. Native PowerShell 7: 8 PASS. Both exercised Chinese, emoji, literal quotes, terminal backslashes, empty argv elements, oversized input and NUL rejection.
- Portable complete build, memory tests, process checks and N42 targets: corresponding CI job PASS.
- PostgreSQL live integration: SKIPPED (no `QBRAIN_PG_TEST_DSN`). The registered PG unit group passing is not live PG evidence.
- No real user memory, live model endpoint or real API credentials were used.

The first native run correctly failed because the mandatory string-array bridge parameter rejected an empty element. `[AllowEmptyString()]` fixes the parameter contract; the original assertion remains. The final bridge preserves CRT terminal-backslash doubling. Failed runs remain visible in Actions.

## Scope and remaining work

N43 stores whole, source-linked user quotes with policy/consent separation, event idempotency, publication leases, retries, revocation and partial provider usage. Local markers are conservative rules, not broad semantic understanding. Model candidate validation checks source quotes, not truth or general classifier quality.

N44A supplies Unicode argv/environment paths and byte-preserving process transport. It does not install actual host lifecycle hooks; N44B supplies that separately. Source-folder summaries and compact tool profiles are separate N45/N46 work.

Forgetting is not secure erasure of disk, WAL or backups. Expiry controls recall, not automatic raw-archive deletion. The optional new memory schema currently rejects PostgreSQL explicitly. Windows Server CI is not the user's interactive Windows 11 host session.
