# N47M — Preserve parsed memory/context option values

Status: done — scoped source acceptance, 2026-09-18; no new public release.
Plan review: `N47M-PLAN-AUDIT.md` and `N47M-CONTINUATION-PLAN.md`.
Outcome: `N47M-FINAL-AUDIT.md` (owner-authorized separate self-review).
Base: `182e1c3ee64b56f4b114bb08ec1f4ba536f8752d`.
Native candidate: `15f6f3962984cb9a9d20c3b6a2790a9b768f119e`.
Scope: Windows-native qbrain only; no Ultrabrain changes.
The original plan is preserved byte-for-byte in `n47m-evidence/INITIAL-PLAN.md`;
relative links in that historical snapshot refer to its original nodes location.

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

The September 18 owner authorization recorded in the continuation plan permits
this node's outcome review by the coordinator in a separate engineering pass.
It supersedes the initial pending separate-subagent gate for N47M only. It does
not authorize fabricating a subagent, waiving native evidence or changing safety
requirements. Final acceptance is documented against the unchanged criteria above.
Source approval and merge do not themselves publish a new application release.

## Security, dependencies and rollback

Use temporary synthetic SQLite brains and scrub provider/QBRAIN environment
variables from subprocesses. Do not access real local clients, live PostgreSQL,
real brain stores, provider credentials or networks from tests. Python is a
CI/test dependency only, not a product runtime dependency. No new dependencies.
Rollback is reverting the scoped candidate commit; no data migration is needed.
The ops ledger describes parser hardening only, not new memory capabilities.
