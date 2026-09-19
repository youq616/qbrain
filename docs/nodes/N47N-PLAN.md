# N47N — Explicit search query boundaries

Status: done for the approved source-repair and closure-repair scope, 2026-09-19
(Asia/Seoul). No new public application release or tag is included.

The original pre-implementation plan is preserved in
[n47n-evidence/APPROVED-PLAN.md](n47n-evidence/APPROVED-PLAN.md), committed in
fa69035e3a579981b97eb02057809e2fce46034a before product implementation.
Its grammar, security, compatibility and rollback criteria remain unchanged.
The additional ledger repair is governed by
[N47N-CLOSURE-REPAIR-PLAN.md](N47N-CLOSURE-REPAIR-PLAN.md) and its
[approved addendum](N47N-CLOSURE-REPAIR-ADDENDUM.md).

Plan review: [N47N-PLAN-AUDIT.md](N47N-PLAN-AUDIT.md).
Current outcome: [N47N-HARD-AUDIT.md](N47N-HARD-AUDIT.md).
Base main: b530f361dc9c36cf23127cc2f3c584f3215fb890.
Final native-tested candidate: c26ec5e512d9ba960b86c9ced5b9b4976b031f2c.
Final native-tested tree: 2beda65c13421a995826c147aad606ea48d7f694.

The earlier a587/f2ba completion was invalidated by a later documentation
fixture regression; it is not the acceptance basis for this closure. The restored
canonical ledger, fixed byte-reading preflight and complete native gates were
reverified on c26. Historical audit/status/summary bytes remain in PRE-CLOSURE-*
under n47n-evidence; their relative links refer to their original locations.

The owner authorized the coordinator's separate outcome self-review. No separate
subagent or third-party audit is claimed. Source acceptance and merge do not
publish an application release; the actual merge identity is recorded in PR #31.
