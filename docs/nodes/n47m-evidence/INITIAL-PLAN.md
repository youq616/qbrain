# N47M — Preserve parsed memory/context option values

Status: approved for implementation; outcome/native gates pending.
Plan review: `N47M-PLAN-AUDIT.md` (owner-authorized coordinator self-review).
Base: `182e1c3ee64b56f4b114bb08ec1f4ba536f8752d`.
Scope: Windows-native qbrain only; no Ultrabrain changes.

## Goal and constraints

Close the pre-existing memory/context second-scan defects recorded in
`n47l-evidence/NEXT-STAGE.md`. Reuse the local N47L fact-parser pattern:
record named values during the existing strict validation pass, read only
that map afterward, and pass only the validated real brain option to the
existing resolver. Read flags only at validated option positions.

Do not change global parsing, search syntax, fact behavior, DB schemas,
source authorization, writeback policy, external-provider consent, default
brain precedence, default limits, tool profiles, or Hook defaults.
In particular a source named `--manual` is data, not capture consent.

## Deliverables and falsifiable acceptance

1. Only `cmd_memory` and `cmd_context` production bodies change. All current
   actions, option allowlists, duplicate/unknown/missing-value errors and
   omitted versus explicitly empty value behavior remain intact.
2. Real-process regressions exercise memory read source shadowing, real
   brain options before/after option-shaped values, and context source
   `--brain`. Check exact source/content/revision and no stray brain dirs.
3. Cover explicit > environment > file config > default brain selection;
   empty, unknown, missing and duplicate arguments fail as before without
   accidental brain creation. Do not invent a new `--` grammar.
4. Capture, extract, status, forget, drain and context summary keep their
   original write/consent semantics. A `--manual` value must not authorize
   manual capture; the actual `--manual` flag must still work.
5. Check ordinary read output byte compatibility against a baseline built
   from the unchanged main product sources. Compare on identical synthetic
   state. Assert rejected writes do not modify application tables.
6. Run existing memory/context/fact/multiterm process checks and full native
   gates. Add dedicated Windows and portable process CI; preserve existing
   gates and test assertions. Record exact source, command, exit and limits.

## Review gates

The September 12 owner waiver allows a coordinator plan review; record it
as self-review, not Claude Code or an independent reviewer. The September 17
real independent outcome-subagent requirement remains. Do not mark this node
done, merge the candidate, or publish an application release until that review
and required native evidence actually exist. A missing capability is a reported
blocker, never a fabricated PASS. Use a draft PR for incomplete gates.

## Security, dependencies and rollback

Use temporary synthetic SQLite brains and scrub provider/QBRAIN environment
variables from subprocesses. Do not access real local clients, live PostgreSQL,
real brain stores, provider credentials or networks from tests. Python is a
CI/test dependency only, not a product runtime dependency. No new dependencies.
Rollback is reverting the scoped candidate commit; no data migration is needed.
The ops ledger must describe only parser hardening, not new memory capabilities.
