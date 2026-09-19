# N47N plan review

Verdict: APPROVED FOR IMPLEMENTATION. Reviewer: coordinating ChatGPT, separate
engineering self-review, explicitly authorized by the owner's current request.
The pre-implementation review is recorded in N47N-PLAN.md, committed as
fa69035e3a579981b97eb02057809e2fce46034a before product code was published.
This file indexes that review; it is not a later claim of a subagent audit.

The scoped grammar distinguishes literal query data from actual options. Named
query consumes exactly one token (including --); delimiter stops scanning, and
all later tokens remain data. Values/flags are consumed once. Unknown, duplicate,
missing, mixed and invalid inputs fail before opening a brain. Existing valid
ordinary input, limit clamping, empty limit/mode fallbacks and brain precedence
must remain. Explicit query preserves its bytes; positional text retains legacy
join/trim. MCP and ranking/provider rules remain unchanged.

No blocking plan finding. Test both prefix literals and punctuation-only empty
search results without mistaking no hits for parser loss. Do not confuse
--no-vector with disabling optional LLM reranking. Native N42/N44 evidence and
separate outcome self-review still required; no release/tag changes authorized
by this node's implementation approval.
