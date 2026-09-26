# N48L — paired quality and main-request cost evaluation

2026-09-26. Baseline main89a4e1c88341409fe726a82cdd5779af52ded5ef,
treef2743f41f6eb3774982182caff00dbc88ea1e991. Status: approved after the
separate design review in N48L-PLAN-AUDIT.md. Current owner requests the
coordinator's own post-implementation review, not a third-party certification.

## Goal

Add optional offline `model_evaluation.py export|verify` to join N47S answer
scoring and N48J costs for ONE exact saved run. Prevent cheap missing answers,
all-abstention, or improvements in aggregate scores hiding per-task regressions
from being labeled quality-preserving improvement. No new paid execution, client
installation, native pricing algorithm, database change or MCP permission.

## Acceptance contract

- Strictly validate original run with unchanged N48J; compute scores from those
  in-memory response bytes and the separately supplied, bounded evaluator key.
  N48J cost source manifest must match that exact snapshot; recheck source/key/rates
  and native identities before output. Never join independently supplied summaries.
- Use unchanged N47Q/N47S answer semantics. Report packet-grounded correctness
  (50 tasks per arm) SEPARATELY from common answerable resolution (25 tasks).
  Missing and failed answers remain in both fixed denominators, where applicable.
  Show each paired outcome and count improved/regressed/tied cases. No raw answer
  values, evidence IDs, key, prompt or endpoint is copied into output.
- Describe observed Pareto dominance only if all100 responses are complete,
  native main-cost comparison is eligible, no scored per-task dimension regresses,
  and at least one dimension improves (or cost strictly decreases). Opposite
  dominance and tradeoffs are explicit. Do not infer noninferiority from net sums.
  Incomplete/noncomparable runs withhold decisions/differences; retain counts.
- Exact rate differences and cost-per-resolved-task use rational numbers. A zero
  resolved denominator yields null, not zero/free/infinity. Main-only scope from
  N48J stays explicit, including failed attempts. No quality-generalization,
  authenticated provider/key, full-pipeline savings or statistical significance.
- Exclusive new output folder outside input run; deterministic files and manifest
  written last. verify recomputes from run/key/rates/binary, rejects changed hashes,
  counters, flags, missed files and original source mutations. Paths, links,
  byte/depth bounds and error redaction reuse tested N48J helpers.
- Execute positive/adversarial unit and actual native integration tests in normal
  and optimized Python. Test all-abstention, grounded-vs-resolution disagreement,
  compensating paired regressions, zero denominators, partial/failed/unknown costs,
  model drift, changed key/bindings, symlinks, no-overwrite and self-rehashed bundles.
  Real100-request numeric-loopback execution must feed actual saved receipts into
  both scoring/costs; explicitly synthetic, not real model/client consumption.
- Fresh Windows/Linux CI builds and tests new code and retained original suites.
  Retain raw records, script/binary/source identities, separate review findings and
  failed attempts. Only docs/evidence may change after qualification without rerun.

Delivery: new tool, new tests, CI, Chinese usage guide, documented example output,
separate review and exact source/evidence archive. Preserve all existing product,
scorers, cost bridge, packaging scripts and the immutable N48K ZIP byte-for-byte.
Rollback removes additive files; no migration. The tool remains optional Python,
not a required application service. PG/signing/Issue40 and real host/model gates
remain separate. Do not silently substitute a synthetic test for them.
