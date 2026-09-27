"""N48L: offline paired answer quality + scheduled-main-request costs.

One original N47S run is scored with its offline evaluator key and priced using
unchanged N48J/native accounting. Descriptive paired comparisons are not a claim
of real model provenance, general quality, statistical significance or total
pipeline savings. Exported files contain counts/identities, never answer values.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import os
from pathlib import Path
import subprocess

import memory_task_contract as c
import model_ab as m
import model_cost as b

MODES = ('without-context', 'with-context')
SCHEMA = 'qbrain-model-evaluation-v1'
RULE = 'paired-no-regression-main-cost-v1'


def fraction(value: Fraction | None):
    """String integers avoid precision loss in downstream JSON number readers."""
    if value is None:
        return None
    return {'numerator': str(value.numerator), 'denominator': str(value.denominator)}


def measure(numerator: int, denominator: int) -> dict:
    return {'count': numerator, 'total': denominator,
            'rate': fraction(Fraction(numerator, denominator)) if denominator else None}


def transitions(rows: list[dict], field: str) -> dict:
    result = dict(improved=0, regressed=0, both_correct=0, both_incorrect=0)
    for row in rows:
        before, after = [row[mode][field] for mode in MODES]
        result['both_correct' if before and after else 'both_incorrect' if not before and not after
               else 'improved' if after else 'regressed'] += 1
    result['total'] = len(rows)
    return result


def summarize(plan: dict, run: dict, key: dict, snapshot: b.Snapshot) -> tuple[dict, list[dict]]:
    """Scoring uses the very bytes N48J validated, without reopening response files."""
    answers = {mode: [] for mode in MODES}
    observations = {(row['mode'], row['case_id']): row for row in run['rows']}
    for row in run['rows']:
        if row['status'] == 'completed':
            raw = snapshot.files[f"{row['index']:03d}/response.bin"]
            answer, _ = m.parse_response(raw, row)
            answers[row['mode']].append(answer)
    scores, indexed_answers, indexed_scores = {}, {}, {}
    for mode in MODES:
        raw = plan['packet_text'][mode].encode('utf-8')
        submitted = {'schema': 'qbrain-memory-task-answers-v1', 'run_id': plan['run_id'],
                     'packet_sha256': b.sha(raw), 'answers': answers[mode], 'usage': None}
        scores[mode] = c.score(key, raw, submitted)
        indexed_answers[mode] = {a['case_id']: c.answer(a) for a in answers[mode]}
        indexed_scores[mode] = {row['case_id']: row for row in scores[mode]['cases']}
    pairs = []
    for case in c.CASES:
        cid = case['id']
        answerable = c.EXPECTED_STATES[cid] in ('known', 'conflict')
        pair = dict(task_id=cid, kind=case['kind'], answerable=answerable)
        wanted = c.answer(key['expected'][cid])
        for mode in MODES:
            score = indexed_scores[mode][cid]
            pair[mode] = {'status': observations[mode, cid]['status'],
                          'answered': score['answered'], 'grounded_correct': score['correct'],
                          'resolved': indexed_answers[mode].get(cid) == wanted if answerable else None}
        pairs.append(pair)
    return scores, pairs


def decision(grounded: dict, resolved: dict, cost: dict, completed: int) -> dict:
    """Case-wise Pareto rule: net improvements never cancel a regressed case."""
    blocked = []
    if completed != m.COUNT:
        blocked.append('incomplete_responses')
    comparison = cost['comparison']
    if comparison is None:
        blocked.append('unattempted_planned_requests')
    elif not comparison['comparison_eligible']:
        blocked.extend(comparison['unavailable_reasons'])
    if blocked:
        return {'rule': RULE, 'result': 'NOT_COMPARABLE', 'unavailable_reasons': blocked,
                'candidate_no_quality_regressions': None, 'candidate_dominates_observed_cases': None,
                'baseline_dominates_observed_cases': None}
    improves = grounded['improved'] + resolved['improved']
    regresses = grounded['regressed'] + resolved['regressed']
    delta = Fraction(comparison['change']['candidate_minus_baseline'])
    cand = regresses == 0 and delta <= 0 and (improves > 0 or delta < 0)
    base = improves == 0 and delta >= 0 and (regresses > 0 or delta > 0)
    result = ('CANDIDATE_DOMINATES_OBSERVED_CASES' if cand else
              'BASELINE_DOMINATES_OBSERVED_CASES' if base else
              'NO_CHANGE_OBSERVED' if improves == regresses == 0 and delta == 0 else 'TRADEOFF_OBSERVED')
    return {'rule': RULE, 'result': result, 'unavailable_reasons': [],
            'candidate_no_quality_regressions': regresses == 0,
            'candidate_dominates_observed_cases': cand, 'baseline_dominates_observed_cases': base}


def analyze(run_dir: Path, key_path: Path, rates_path: Path, binary: Path):
    snapshot = b.Snapshot(run_dir)
    plan, _, run, _ = b.validate_run(snapshot)
    key_path = b.safe_path(key_path)
    key_raw = b.read(key_path, b.CAP)
    key = b.decode(key_raw)
    scores, pairs = summarize(plan, run, key, snapshot)
    cost, cost_files = b.analyze(run_dir, rates_path, binary)
    cost_source = b.decode(cost_files['source-manifest.json'])
    b.need(b.same(cost_source['files'], snapshot.manifest()), 'evaluation_source_mismatch')
    b.need(cost['plan_sha256'] == b.sha(snapshot.files['plan.json']) and
           cost['run_id'] == plan['run_id'] and cost['completed_responses'] == run['completed'] and
           cost['attempted_requests'] == run['attempted'], 'evaluation_run_mismatch')
    answerable = [p for p in pairs if p['answerable']]
    grounded = transitions(pairs, 'grounded_correct')
    resolved = transitions(answerable, 'resolved')
    outcome = decision(grounded, resolved, cost, run['completed'])
    eligible = outcome['result'] != 'NOT_COMPARABLE'
    arms = {}
    for mode in MODES:
        s = scores[mode]
        resolved_count = sum(p[mode]['resolved'] for p in answerable)
        b.need(resolved_count == s['answerable_resolution']['resolved'] and
               len(answerable) == s['answerable_resolution']['total'], 'evaluation_score_mismatch')
        subtotal = cost['ledgers'][mode]['cost_report']['summary']['total_estimate']
        ratio = Fraction(subtotal) / resolved_count if eligible and resolved_count else None
        arms[mode] = {'packet_grounded': measure(s['correct'], s['total']),
                      'answerable_resolution': measure(resolved_count, len(answerable)),
                      'answered': s['answered'], 'missing_or_failed': s['missing'],
                      'cost_per_resolved_task': {'currency': cost['ledgers'][mode]['cost_input']['currency'],
                          'amount': fraction(ratio), 'cost_scope': b.SCOPE,
                          'unavailable_reason': 'comparison_not_eligible' if not eligible else
                                                'zero_resolved_tasks' if not resolved_count else None}}
    def rate_delta(field):
        left, right = [arms[mode][field] for mode in MODES]
        return fraction(Fraction(right['count'], right['total']) - Fraction(left['count'], left['total'])) if eligible else None
    result = {'schema': SCHEMA, 'run_id': plan['run_id'], 'plan_sha256': cost['plan_sha256'],
              'execution_kind': cost['execution_kind'], 'cost_scope': b.SCOPE,
              'scoring_scope': 'structured_fixed_memory_tasks', 'planned_requests': m.COUNT,
              'attempted_requests': run['attempted'], 'completed_responses': run['completed'],
              'arms': arms, 'paired': {'packet_grounded': grounded, 'answerable_resolution': resolved},
              'changes': {'packet_grounded_rate': rate_delta('packet_grounded'),
                          'answerable_resolution_rate': rate_delta('answerable_resolution'),
                          'main_cost': cost['comparison']['change'] if cost['comparison'] is not None else None},
              'decision': outcome, 'cases': pairs,
              'evaluator_key_authenticated': False, 'source_provenance_authenticated': False,
              'general_answer_quality_verified': False, 'statistical_generalization_verified': False,
              'quality_preserving_savings_verified': False, 'host_consumption_verified': False,
              'billing_verified': False, 'full_pipeline_costs_included': False,
              'provider_requests_sent_by_evaluator': 0}
    # No key/answer contents flow to native commands or exports, only the key digest.
    provenance = {'schema': 'qbrain-model-evaluation-source-v1', 'cost_source': cost_source,
                  'evaluator_key_sha256': b.sha(key_raw), 'evaluator_key_bytes': len(key_raw),
                  'evaluation_tool_sha256': b.sha(b.read(Path(__file__), b.CAP)),
                  'rule': RULE, 'key_authenticated': False}
    snapshot.recheck()
    b.need(b.read(key_path, b.CAP) == key_raw, 'evaluation_key_changed')
    b.need(b.sha(b.read(rates_path, 262144)) == cost_source['rates_sha256'], 'evaluation_rates_changed')
    b.need(b.sha(b.read(binary, 128 * 1024 * 1024)) == cost_source['binary_sha256'], 'evaluation_binary_changed')
    files = {'evaluation.json': b.encode(result), 'quality-scores.json': b.encode(scores),
             'cost-analysis.json': cost_files['analysis.json'],
             'comparison-input.json': cost_files['comparison-input.json'],
             'provenance.json': b.encode(provenance)}
    b.need(all(len(raw) <= b.CAP for raw in files.values()), 'evaluation_output_limit')
    files['MANIFEST.json'] = b.encode({'schema': 'qbrain-model-evaluation-bundle-v1',
        'files': {name: {'bytes': len(raw), 'sha256': b.sha(raw)} for name, raw in files.items()}})
    return result, files


def execute(run_dir: Path, key: Path, rates: Path, binary: Path, output: Path, verify=False):
    source = b.safe_path(run_dir, True)
    target = Path(os.path.abspath(output))
    b.safe_path(target.parent, True)
    b.need(target != source and source not in target.parents, 'evaluation_output_inside_source')
    if not verify:
        b.need(not target.exists() and not target.is_symlink(), 'evaluation_output_exists')
    result, outputs = analyze(source, key, rates, binary)
    if verify:
        b.safe_path(target, True)
        b.need(sorted(p.name for p in target.iterdir()) == sorted(outputs), 'evaluation_bundle_inventory')
        for name, raw in outputs.items():
            b.need(b.read(target / name, b.CAP) == raw, 'evaluation_bundle_changed')
    else:
        target.mkdir()
        for name, raw in outputs.items():
            with (target / name).open('xb') as stream:
                stream.write(raw)
    return {'result': 'VERIFIED' if verify else 'EXPORTED', 'evaluation': result['decision']['result'],
            'execution_kind': result['execution_kind'], 'cost_scope': b.SCOPE,
            'completed_responses': result['completed_responses'], 'provider_requests_sent_by_evaluator': 0}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('export', 'verify'))
    for name in ('run', 'key', 'rates', 'binary', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    try:
        print(b.encode(execute(a.run, a.key, a.rates, a.binary, a.output, a.command == 'verify')).decode(), end='')
        return 0
    except b.Reject as exc:
        print(b.encode({'error': {'code': str(exc)}}).decode(), end='')
    except (OSError, ValueError, TypeError, KeyError, IndexError, RecursionError, OverflowError, subprocess.SubprocessError):
        print('{"error":{"code":"evaluation_input_or_local_failure"}}')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
