# N47E design review

Reviewer: ChatGPT, separate owner-authorized engineering self-review.
Verdict: PASS for scoped implementation, not completed runtime acceptance.

The useful new behavior is automatic opt-in connection from existing local
extraction to evidence-backed facts, not another read-only planning document.
Using fixed category predicates and COMPLETE quotes avoids converting a negated
preference into a positive claim. Local-only event selection avoids implicitly
extending model extraction consent or claiming model-verified truth.

All evidence must be checked before first schema write and rechecked inside the
single fact batch write transaction. The preparatory lazy schema initialization
is explicitly separate; its prior backup/table creation is not falsely called
rolled back when a later batch fails. No caller transaction should be committed.
Retired equal-quote veto, exact predicate support grouping, support cap and
idempotent receipts must be tested with real database state, not mocked results.

Automatic write authorization is separate from capture and recall. Requiring
capture plus local extraction at both installer and Hook boundary prevents an
ambiguous one-switch opt-in. Trace must distinguish promotion failure from prior
successful capture; no secret/raw prompt echo and no retry-until-green behavior.
Existing model consent and MCP write gate remain authoritative for explicit RPC.

P0/P1 design blockers: none after these bounds. Main risks: partial batch writes,
retired-claim revival through a new event, duplicate support races, inference of
truth from category labels, accidental activation and conflated success reporting.
Each has a required negative test. Existing P3 issues and real authenticated host
consumption remain separate; no redundant local compiler or review request.
