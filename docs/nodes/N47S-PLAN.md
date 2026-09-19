# N47S — Controlled model-comparison execution

2026-09-19. Status: done for the approved source-tooling scope after actual
Windows/Linux execution, full native regression and separate outcome self-review.
Not a real provider/model, signed-in client or stable-v1 acceptance result.

Base main a1557ca26fea534c62ef332429f4c1fd773b1414.
Accepted execution code b88698bd041d960edcc2a4a2e9beb6fa407ffc47,
tree69e581bcd68b6c1e2170b729abc0b0228d577f17; fixed run35433697805.
Additional full native gate db791b0027e807f592917d9221704820f46bf867,
treeb8e41cd0800b5ac43da0f4b54ea8ab3a5cba9055; fixed run35434346909.
The latter adds validation files only, not different implementation bytes.

The original plan is preserved byte-for-byte in
[n47s-evidence/APPROVED-PLAN.md](n47s-evidence/APPROVED-PLAN.md).
Plan audit remains N47S-PLAN-AUDIT.md. The session-label addendum was approved
before correction and remains in n47s-evidence/SESSION-LABEL-REVIEW-PLAN.md.
[N47S-HARD-AUDIT.md](N47S-HARD-AUDIT.md) checks the original criteria and addendum
against actual results, including all48 tool methods,50 engine tasks,100 HTTP
requests,60 full native groups, raw artifact readback and adverse-copy tests.

The coordinating assistant performed the owner's requested separate self-review,
not an independent subagent or third-party certification. No original tests,
runtime, installer, schema, ledger or release assets were changed. Model/host
results remainNOT_RUN; loopback fixtures and null actual costs remain explicit.
Actual final merge/tree is recorded in PR36; later CI is not predeclared passed.
