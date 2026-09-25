# N48I — Paired task cost comparison

2026-09-25. Status: approved after N48I-PLAN-AUDIT.md.
Base main b2ae3380e96de13256094166bda7015778418e96,
tree 6158b2728b315811094867a9a50d6d91d956377d.
The owner explicitly requests a complete module and separate coordinator self-review.
No third-party or independent-subagent review is claimed.

## Goal and scope

Add native, offline `cost compare` to compare two explicitly supplied normalized
cost ledgers, with identical task manifests and declared common conditions.
This closes paired COST analysis, not execution/scoring of real model tasks.
Existing N47S scoring remains separate; N48G/H cost_input can be embedded unchanged.
No new MCP op, provider call, key, database, runtime service or permission change.

Input schema qbrain-cost-comparison-v1 has comparison_id, currency, baseline,
candidate. Each arm has label, conditions_sha256, ledger_complete (boolean),
cost_input (existing N48F input), tasks and shared_call_ids. Each task has task_id,
task_sha256 and nonempty call_ids. A task digest identifies the common task and
source snapshot, NOT the different experimental context/request body. Common
conditions digest excludes only the intentional treatment. Both are caller
assertions, not authenticated provenance. Labels must differ.

## Falsifiable acceptance

1. Reject mismatched task sets/digests/common conditions/currency, duplicate tasks,
   missing/duplicate/unassigned calls, empty task manifests and malformed fields.
   Every submitted call is owned exactly once by a task or shared overhead. Each
   task requires at least one main-stage call; shared main calls are rejected.
2. Recompute each arm using unchanged N48F arithmetic, never trust prior reported
   totals. Preserve failed/retried calls, all stages, shared overhead and unknowns.
   Same call_id may occur in different arms (separate namespaces).
3. Check one known declared main provider/model per arm and equal primary price
   schedules; missing/multiple/mismatched primary models or prices withhold deltas.
   Auxiliary rates may differ and all their submitted costs remain included.
   ledger_complete=false or ANY unknown cost component withholds all deltas,
   including complete-case subsets. Do not equate a partial known subtotal to zero
   or a full total. Known zero usage retains N48F zero-price semantics.
4. Output recomputed cost reports, per-task/shared/stage breakdowns and a signed
   candidate-minus-baseline amount. A ratio is an exact reduced signed fraction,
   null at zero baseline. Never cast large unsigned amounts to signed or multiply
   by100 for percentage formatting. No float, guessed price or inferred quality.
5. Bounds: 1MiB input, 8MiB output, 128 tasks per arm, N48F 64 rates/512 calls and
   256KiB per normalized ledger; strict duplicate-key JSON, depth32, bounded IDs.
   Canonical fingerprint independent of array order; assignments and scope bind it.
   Failures return an atomic structured code and no report/body/path echo.
6. Direct tests, real CLI fixtures and a separately written Python Fraction oracle
   cover exact arithmetic, signed uint64 extremes, unknown propagation, workload
   binding, both success and error branches, permutation/swap/retry/overhead effects,
   JSON/bounds/overflow and original cost/import/stream regressions.
   Native Windows and Linux builds must test the exact committed candidate. Existing
   60 Windows groups, core/lifecycle/MCP/application regressions remain required.
7. Documentation and synthetic examples explain integration, fees/taxes/unknowns,
   that coverage/config/model/rate authenticity is NOT verified, and that costs
   alone do not prove quality-preserving savings. Actual model/client evidence and
   new installer/signing/PG/Issue40 remain open.

## Delivery and rollback

One new pure accounting header, early CLI route/help, standalone tests, independent
process oracle, a dedicated qualification workflow and docs/examples. Original
accounting/import/stream sources and their tests remain unchanged. Retain raw inputs,
outputs, exits and exact identities; review implementation and executed results
against this plan before acceptance. Roll back additive route/header without any
DB migration. Use a new branch/expected-head merge, no force push or release change.
