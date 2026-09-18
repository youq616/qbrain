# N47N operation delta

Accepted source scope: existing `search` CLI only, zero additional operations.
The pure parser captures --query/--query= and delimiter-based literal content,
validates syntax before opening the brain, and dispatches only actual option
values/flags. Original search ranking, retrieval, MCP/source authorization,
provider policy and all other CLI handlers are unchanged.

The accepted scope includes intentional rejection of formerly ignored unknown,
duplicate, missing, mixed, empty and malformed numeric/mode inputs. Valid legacy
ordinary input retains 22 tested exit/stdout/stderr byte comparisons. Literal
CLI data does not promise exact-substring matching or punctuation-only hits.

Fixed source a587e175 passed N47N, N42 and N44 gates; see the final audit for
226/302 native process evidence, 361 parser checks, 1,193 original artifact
checks, generated parser review, baseline rejection and the repaired Windows
validation-entry defect. Review is the owner's requested separate self-review
by the coordinator, not a third party. No new Release/tag or local install.

[Audit](nodes/N47N-HARD-AUDIT.md) · [Usage](integration/SEARCH-ARGUMENTS.zh-CN.md).
