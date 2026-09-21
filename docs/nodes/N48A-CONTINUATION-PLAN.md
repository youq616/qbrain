# N48A continuation — finish OpenCode project-local MCP module

2026-09-21. Base main:88c949bad4ea7e15e204008668fde4fdf85e13d2.
The current user explicitly requests completion of a whole module and separate
coordinator self-review. The previously delivered local N48A patch is the starting
point; do not duplicate it or substitute its Linux evidence for Windows acceptance.

## Goal and acceptance

1. Preserve the original local PLAN/PLAN-AUDIT and historical local review. Submit
   the exact inspected source through the now available authorized GitHub write
   actions. Confirm modified existing files against the fixed base and exact
   archive/patch contents. No historical claim of commit or Windows success.
2. Compile the actual module on native Windows and Linux. Run standalone parser,
   ownership, rollback and process tests and all inherited native/receipt gates.
   Fix any platform defects and rerun the changed candidate, retaining failures.
   Validate workflow syntax, Windows flags and expected platform-specific checks.
3. Verify the schema against current official OpenCode V1/V2 documentation. Where
   a pinned real OpenCode binary is available, test actual isolated configuration
   loading and local Qbrain MCP discovery without a model/provider request. Do not
   equate direct Qbrain protocol calls with OpenCode loading or authenticated use.
4. Separately review implementation, schema/version boundaries, filesystem and
   recovery ownership, default-deny permission and evidence. Fix blocking findings
   before source acceptance. Read back actual CI artifacts, source and binary hashes
   and test outputs. No unsupported PASS, absent Windows run, or fabricated subagent.
5. Merge only the reviewed source and documentation after fixed-source validation.
   Preserve existing public Release/tag, user data, other integrations, database
   and model defaults. Report any genuinely unexecuted host/model/ACL/signing gate.

## Constraints and rollback

One native module with preview/install/status/uninstall/recovery. Explicit V1/V2,
no guessed installed version, only project-local JSONC and private owned metadata.
Exact undo refuses external edits. Individual atomic file writes plus journal are
not cross-file atomicity or protection against hostile administrator replacement.
No credentials, actual-user files, paid provider calls or global host settings.
Generated Qbrain command uses the six-tool memory profile and explicit write opt-in.
A rollback is revert of additive source; existing managed data must be undone or
recovered with its validated commands, not silently removed.

The branch creation succeeded normally on this turn. That does not yet mean code
is committed or CI has run. Current permissions are observed from the actual tool
interface, not inferred from the prior turn's lack of mutation tools.
