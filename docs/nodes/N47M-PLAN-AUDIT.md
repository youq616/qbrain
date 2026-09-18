# N47M plan review

Verdict: APPROVED FOR IMPLEMENTATION under the September 12 owner waiver.
Reviewer: coordinating ChatGPT, separate engineering self-review pass.
This is not a separate subagent, Claude Code, or third-party review.
Reviewed before implementation against base `182e1c3e` and the recorded
N47L next-stage scope.

The implementation is restricted to the two existing named-option parsers.
The existing fact parser provides an in-tree precedent, so a global parser
rewrite or new grammar is unnecessary. Map lookup must distinguish absent
values from explicit empty strings; do not default through `value.empty()`.
The brain resolver must receive only an actual validated brain option, or
an empty vector, preserving environment/file/default precedence.

Flags are also vulnerable to second scanning: capture checks `--manual`
against all argv tokens. Reading only the validated `seen` set is required
so an option-shaped source/brain name cannot grant manual capture consent.
Validation must finish before brain opening or stdin consumption, preserving
no-side-effect failures for duplicate, unknown, and missing options.

P0: none found in the plan. P1: none found in the plan.
P2 addressed in the plan: add manual-consent regression, empty-value/default
semantics and fixture-directory checks, not just successful read results.

The scope is Windows/C++20 compatible; Python remains a test dependency.
No schema, authorization, live DSN, provider call, install, or runtime dependency
change is proposed. Existing gates must remain intact. The coordinator may
implement and test, but the September 17 independent outcome review remains
unfulfilled until a real separate reviewer is available and records evidence.
Do not use this plan approval as an outcome PASS or authorize merging/releasing.
