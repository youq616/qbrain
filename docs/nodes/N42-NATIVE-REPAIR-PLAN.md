# N42 native validation repair addendum

Reviewer: ChatGPT under the user's existing N42 review exception; not Claude Code.
Plan verdict: approved for the two bounded failures below. Native outcome remains pending.

## Evidence

The downloaded original artifact for Actions run 34554749593 shows 41 of 42 registered test groups passing and only `n32_scan_integration` failing on `cpp_traps.cpp`. The earlier parsed job-log summary disagreed; the preserved raw `windows-tests.log` is the evidence used here. No n14/n17/n30 regression is asserted from that summary.

Reproduction: the unchanged parser matches the checked-in cpp_traps golden for LF input but emits extra `side_effect`/`x` symbols for CRLF input. `SkipPreprocessorLine` checks the byte immediately before LF and mistakes CR for macro content. Repair CRLF continuation recognition without normalizing stored input or changing golden outputs. Add explicit LF/CRLF parity checks to the original test and a focused target, preserving all old assertions.

Run 34555340213 executes all seventeen real MCP assertions successfully, then fails temporary-directory cleanup because Python SQLite context managers commit/rollback without closing the connection. Use `contextlib.closing` for fixture/snapshot connections; retain explicit fixture commit and cleanup errors. Do not ignore PermissionError or weaken assertions.

## Acceptance

- Both C++ and TypeScript trap fixtures match unchanged golden JSON with LF and CRLF.
- EOF edge inputs remain bounded; byte positions and line accounting are unchanged.
- All seventeen real-executable MCP checks pass on Windows and temporary cleanup succeeds.
- Full old suite plus N42 runs, preserving existing tests and explicit PostgreSQL skip.

The patch is source-only, applies to four hash-checked preimages, and introduces no runtime/model dependency. Native CI uses disposable fixtures, never user memory. No claim of full semantic memory or new Windows 11 host integration.
