# N48L design review

2026-09-26. Reviewer: ChatGPT, owner-authorized coordinator separate design pass.
Decision: PASS for implementation of this bounded offline join, not an outcome
acceptance or third-party audit. Baseline native/runtime remains unchanged.

Reviewed existing model_ab.parse_response/score_run, memory_task_contract.score,
model_cost.validate_run/analyze/execute and cost_comparison native rules. Crucial
finding: no-context grounding and common task resolution have different meanings.
A no-context abstainer can be 50/50 grounded and 0/25 resolved. Comparing only
accuracy or only successful requests gives a misleading efficiency assessment.

The plan preserves both metrics and their per-task outcomes. Aggregates cannot
hide a lost task behind a gained task. Strict observed dominance requires zero
per-task regressions, complete execution, comparable explicit costs and a strict
improvement. A null ratio at zero resolved tasks prevents free/infinite success
claims. Main-only scope and descriptive sample-level conclusions remain explicit.

Cross-stage source TOCTOU is addressed by matching cost source-manifest to the
in-memory scoring snapshot and rechecking original bytes; not a hostile concurrent
filesystem sandbox. The answer key is offline-only, bounded and only hashed into
provenance, never passed to native costing or a model. Output is new-only and must
verify by recomputation, not self-declared totals. No external dependency/service
is needed. All concerns have falsifiable tests; outcome review must follow actual
Windows/Linux evidence and must not weaken old scorers or tests to pass.
