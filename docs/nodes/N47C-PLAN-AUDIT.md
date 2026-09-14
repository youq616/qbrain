# N47C design review

Reviewer: ChatGPT, separate owner-authorized engineering self-review.
Verdict: PASS for scoped implementation; no runtime acceptance yet.

N47B gives explicit conflict inspection but not query-directed fact retrieval.
The proposed recall view makes existing source-backed facts useful for task
queries without treating matching alone as evidence of truth. The main risk is
confirmation bias through dropping a nonmatching contradiction. Requiring all
valid direct neighbors inside one indivisible output item addresses that risk.

Do not recursively expand neighbors: cycles/dense graphs need a bounded contract.
Explicitly state that neighbor conflicts are not themselves expanded and never
skip other matching anchors solely because they appeared as a neighbor. This
preserves their independent counter-edges within the stated candidate/byte limits.

Snapshot and work accounting must span matching and counter-evidence reads. Work
failure after loading an anchor must omit that entire in-progress neighborhood.
Use an active outer statement and a deterministic two-connection runtime test.
Filter matching before candidate limit; test an old matching claim behind more
than 100 irrelevant recent claims. Limit count is not a bound on SQL scan cost.

Strict query validation, source gates, no implicit truth confidence, read-only
schema behavior and no post-review byte changes remain requirements. Existing
Hook output is not modified; claiming automatic recall from this read API alone
would be incorrect. New tests and packaging gates must fail on empty, partial,
stale or wrong-source reports. Retain all prior suites and historical failures.

P0/P1 design blockers: none after explicit neighborhood, budget and scope rules.
Primary implementation gates: no one-sided counter-evidence, no read mutations,
correct source and snapshot, exact old-view compatibility, actual native tests.
A later outcome review is required, not a reuse of this design verdict.
