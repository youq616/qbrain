# N47N plan review

Verdict: APPROVED FOR IMPLEMENTATION, 2026-09-18.
Auditor: coordinating ChatGPT; owner-authorized separate engineering self-review.
No subagent/Claude Code/third-party review claimed.

Reviewed before implementation. A search-only parser avoids changing other
handlers and can be tested without a database or model. Explicit boundary and
named-query syntax eliminate the ambiguity without guessing shell quotation
(which is unavailable in argv). Unknown/duplicate/missing options are deliberate
new rejections, not claims of compatibility for invalid historical inputs.
Attached values preserve access to legal option-shaped brain names. Empty query
is rejected before brain opening, but retains the legacy exit/output contract.

P0/P1 plan findings: none. Addressed P2: define missing-value versus literal-data
rules; assert actual flags/query contents as well as search hits; verify nonempty
fixtures; state no-vector is not blanket egress denial. Reject mixed query forms
instead of silently concatenating. Negative tests must compare old binary too.

Native gates and source/EXE identity review remain mandatory. Tests with synthetic
or no-model fixtures do not demonstrate live providers, PostgreSQL or real clients.
