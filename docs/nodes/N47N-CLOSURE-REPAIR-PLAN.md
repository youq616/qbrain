# N47N closure repair — plan and pre-implementation review

Date: 2026-09-19 (Asia/Seoul). Starting head: f2ba7ffc38fc53997b20caf6458e957b99a524fc.
Status: approved for implementation; outcome and fresh native gates pending.
Reviewer: coordinating ChatGPT in a separate engineering plan-review pass,
explicitly authorized by the owner's current continuation request. Not a
separate agent, Claude Code, or third-party review.

## Observed blocking regression

N47N PR run 35362126565 failed its full Windows suite. Downloaded artifact
10555277264 (SHA-256 7ebb8e8d9493f4e8176cdb3ff9ddd5c4cb6ccdf2a662efdb44aef6d8042e3c97)
contains windows-tests.log with n31_a_counts_mapping failing at test_n31.cpp:278.
The f2ba closure replaced docs/OPS-PARITY-LEDGER.md with an archive link, so the
unchanged runtime reconciliation no longer finds its 104 upstream and four
extension rows. Passing product tests on a587e175 do not cover this later
fixture change. Earlier closure statements are provisional until repaired.

## Scoped repair and falsifiable acceptance

1. Restore the entire tested inherited ledger byte-for-byte. N47N adds zero
   operations; its new grammar remains documented in its dedicated delta and
   current status. Do not weaken the original C++ test or frozen inventory.
2. Add a fast, read-only Python preflight for this documentation contract:
   parse the two canonical tables, compare exact names and section membership
   to the frozen 108-entry generated inventory, reject missing/duplicate/wrong
   rows and malformed inventory. It is not a replacement for runtime tests.
3. Add negative regression tests including the exact rejected f2ba ledger,
   same-count substitutions and duplicate rows. Ordinary and optimized Python
   invocations must enforce checks, with no assert-dependent production gate.
4. Trigger the preflight for its code, inventory, canonical ledger and native
   reconciliation source; run on Windows and Ubuntu. Include these fixture
   paths in existing N47N/N42/N44 push filters without changing their jobs,
   assertions, permissions, frozen counts, or publication conditions.
5. Run focused compilation and actual search/memory regressions locally;
   inspect fresh fixed-source native results and artifacts before source merge.
   Separately review the code change, checker mutations and final documentation.

## Limits and rollback

No change to production search code, other handlers, DB, authorization, providers,
Hook defaults, runtime dependencies, user data, tags or releases. Python remains
CI tooling. Preserve failed closure/CI identities and original reports. Restore
prior documentation/checker changes to roll back; no migration. Stage completion
is blocked on the actual repaired evidence, not waived by this plan approval.
