# N48R — PostgreSQL Hook parity delta

The existing Hook operation now admits an initialized public/UTF8/v13 PostgreSQL
backend without requiring a local brain.db. Errors do not create schema or fall
back to SQLite. Facts and session memories compose in one owned repeatable-read
read-only snapshot; caller transactions stay protected, withdrawal suppresses the
legacy lane, and capture runs only after read completion. PG legacy dedup binds
the effective database/server/role descriptor. Default permissions are unchanged.

No public MCP/CLI operation or registry count is added; this closes the backend
path of an existing operation. The detailed historical ops ledger is not rewritten.
Original45a23853/full run36583542753 and supplemental a4acb118/run36652734242
supply actual native evidence. Local sanitizer and independent archive/output
readback complete the bounded review. See [outcome](nodes/N48R-HARD-AUDIT.md),
[results](nodes/n48r-evidence/RESULT.json) and [guide](integration/POSTGRES-HOOKS.zh-CN.md).

Real-client/model consumption, whole-project, RLS, Issue40 and signed/stable release
are not closed by this backend module. Same DSN/another label is not isolation.
