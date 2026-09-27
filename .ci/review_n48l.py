"""Independent N48L saved-response oracle and black-box CLI qualification.

stdlib only. Imports no product, scorer, fixture or inherited test module.
Use only the pinned synthetic LOOPBACK_TEST fixture. No model/network execution.
Every test stores its actual source, exit/stdout/stderr and output bundle.
"""
from __future__ import annotations
import argparse
import copy
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

MODES = ('without-context', 'with-context')
KINDS = ('preference', 'replay', 'forget', 'supersede', 'conflict',
         'archive_restore', 'isolation', 'assistant', 'capture_off', 'budget')
IDS = tuple(f'{kind}-{i:02}' for kind in KINDS for i in range(1, 6))
SCOPE = 'scheduled_main_requests_only'


def need(ok, label):
    if not ok:
        raise ValueError(label)


def enc(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dec(raw):
    def unique(pairs):
        out = {}
        for k, v in pairs:
            need(k not in out, 'duplicate JSON')
            out[k] = v
        return out
    def invalid(_):
        raise ValueError('nonfinite JSON')
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique, parse_constant=invalid)


def equal(a, b, label):
    need(enc(a) == enc(b), label)  # excludes bool/int aliasing


def frac(value):
    return None if value is None else dict(numerator=str(value.numerator), denominator=str(value.denominator))


def answer(a):
    return (a['state'], frozenset(a['values']), frozenset(a['fact_ids']))


def expected(directory):
    """Independent semantic projection, not a call into the production scorer."""
    run = dec((directory/'run/run.json').read_bytes())
    plan_raw = (directory/'run/plan.json').read_bytes()
    key = dec((directory/'key.json').read_bytes())
    prices = dec((directory/'rates.json').read_bytes())
    cards = {p['model']: p['per_million'] for p in prices['rates']}
    need(run['execution_kind'] == 'LOOPBACK_TEST', 'synthetic fixture only')
    need(set(key['expected']) == set(IDS) and len(run['rows']) == 100, 'fixture coverage')
    rows = {(r['mode'], r['case_id']): r for r in run['rows']}
    costs = {mode: Fraction(0) for mode in MODES}
    costs_known = True
    pairs = []
    for cid in IDS:
        kind = cid.rsplit('-', 1)[0]
        is_answerable = kind in ('preference', 'replay', 'supersede', 'conflict', 'archive_restore')
        wanted = answer(key['expected'][cid])
        pair = dict(task_id=cid, kind=kind, answerable=is_answerable)
        for mode in MODES:
            r = rows[mode, cid]
            got = None
            if r['status'] == 'completed':
                response = dec((directory/f"run/{r['index']:03}/response.bin").read_bytes())
                got = answer(dec(response['choices'][0]['message']['content'].encode()))
                usage = response.get('usage')
                card = cards.get(response['model'])
                if usage is None or card is None:
                    costs_known = False
                else:
                    inp = usage.get('prompt_tokens'); out = usage.get('completion_tokens')
                    detail = usage.get('prompt_tokens_details') or {}
                    read = detail.get('cached_tokens'); write = detail.get('cache_write_tokens')
                    uncached = inp-read-write if all(type(x) is int for x in (inp, read, write)) else None
                    for bucket, quantity in zip(('input_uncached','input_cache_read','input_cache_write','output'),
                                                (uncached, read, write, out)):
                        rate = card.get(bucket)
                        if quantity is None or (quantity and rate is None):
                            costs_known = False
                        else:
                            costs[mode] += Fraction(quantity) * Fraction(rate or '0') / 10**6
            elif r['status'] != 'not_attempted':
                # This review generates failed HTTP attempts without a billable response.
                costs_known = False
            pair[mode] = dict(status=r['status'], answered=got is not None,
                              grounded_correct=got == (wanted if mode == 'with-context' else ('unknown',frozenset(),frozenset())),
                              resolved=(got == wanted) if is_answerable else None)
        pairs.append(pair)
    transitions = {}
    for name, field, selected in [('packet_grounded', 'grounded_correct', pairs),
                                  ('answerable_resolution', 'resolved', [p for p in pairs if p['answerable']])]:
        t = dict(improved=0, regressed=0, both_correct=0, both_incorrect=0, total=len(selected))
        for p in selected:
            a, b = [p[mode][field] for mode in MODES]
            t['improved' if b and not a else 'regressed' if a and not b else 'both_correct' if a else 'both_incorrect'] += 1
        transitions[name] = t
    eligible = run['completed'] == 100 and costs_known
    dimensions = [tuple(p[mode][field] for mode in MODES) for p in pairs
                  for field in ('grounded_correct', 'resolved') if field != 'resolved' or p['answerable']]
    delta = costs['with-context'] - costs['without-context']
    no_loss = all(after >= before for before, after in dimensions)
    no_gain = all(after <= before for before, after in dimensions)
    has_gain = any(after > before for before, after in dimensions)
    has_loss = any(after < before for before, after in dimensions)
    cand = eligible and no_loss and delta <= 0 and (has_gain or delta < 0)
    base = eligible and no_gain and delta >= 0 and (has_loss or delta > 0)
    label = ('NOT_COMPARABLE' if not eligible else 'CANDIDATE_DOMINATES_OBSERVED_CASES' if cand else
             'BASELINE_DOMINATES_OBSERVED_CASES' if base else 'NO_CHANGE_OBSERVED' if not has_gain and not has_loss and not delta
             else 'TRADEOFF_OBSERVED')
    arms = {}
    for mode in MODES:
        g = sum(p[mode]['grounded_correct'] for p in pairs)
        solved = sum(p[mode]['resolved'] for p in pairs if p['answerable'])
        answered = sum(p[mode]['answered'] for p in pairs)
        arms[mode] = dict(packet_grounded=dict(count=g,total=50,rate=frac(Fraction(g,50))),
                          answerable_resolution=dict(count=solved,total=25,rate=frac(Fraction(solved,25))),
                          answered=answered,missing_or_failed=50-answered,
                          cost_per_resolved_task=dict(currency=prices['currency'],cost_scope=SCOPE,
                             amount=frac(costs[mode]/solved) if eligible and solved else None,
                             unavailable_reason='comparison_not_eligible' if not eligible else 'zero_resolved_tasks' if not solved else None))
    return dict(cases=pairs, paired=transitions, arms=arms, decision=label, eligible=eligible,
                cand=cand if eligible else None, base=base if eligible else None,
                no_loss=no_loss if eligible else None, costs=costs, cost_known=costs_known,
                plan_sha256=sha(plan_raw), run=run)


def validate(directory):
    want = expected(directory)
    r = dec((directory/'out/evaluation.json').read_bytes())
    need(r['schema'] == 'qbrain-model-evaluation-v1', 'schema')
    equal(r['cases'], want['cases'], 'all 50 original-response outcomes')
    equal(r['paired'], want['paired'], 'paired directions')
    equal(r['arms'], want['arms'], 'fixed denominators and exact ratios')
    equal(r['decision']['result'], want['decision'], 'case-wise dominance')
    for key, value in [('candidate_dominates_observed_cases',want['cand']),('baseline_dominates_observed_cases',want['base']),
                       ('candidate_no_quality_regressions',want['no_loss'])]:
        equal(r['decision'][key], value, 'decision flag '+key)
    for field in ('attempted','completed'):
        equal(r[field+('_requests' if field=='attempted' else '_responses')], want['run'][field], 'coverage')
    equal(r['planned_requests'],100,'planned denominator')
    equal(r['plan_sha256'],want['plan_sha256'],'plan binding')
    for field in ('evaluator_key_authenticated','source_provenance_authenticated','general_answer_quality_verified',
                  'statistical_generalization_verified','quality_preserving_savings_verified','host_consumption_verified',
                  'billing_verified','full_pipeline_costs_included'):
        need(r[field] is False, 'scope '+field)
    equal(r['provider_requests_sent_by_evaluator'],0,'no provider requests')
    equal(r['execution_kind'],'LOOPBACK_TEST','test label')
    equal(r['cost_scope'],SCOPE,'cost scope')
    for field in ('packet_grounded','answerable_resolution'):
        a,b = [want['arms'][mode][field] for mode in MODES]
        value = frac(Fraction(b['count'],b['total'])-Fraction(a['count'],a['total'])) if want['eligible'] else None
        equal(r['changes'][field+'_rate'],value,'quality delta')
    cost = dec((directory/'out/cost-analysis.json').read_bytes())
    for mode in MODES:
        if want['cost_known']:
            need(Fraction(cost['ledgers'][mode]['cost_report']['summary']['total_estimate'])==want['costs'][mode],'independent cost sum')
    change = r['changes']['main_cost']
    if want['eligible']:
        delta=want['costs']['with-context']-want['costs']['without-context']
        need(Fraction(change['candidate_minus_baseline'])==delta,'exact cost delta')
        denominator=want['costs']['without-context']
        equal(change['relative_change'],frac(delta/denominator) if denominator else None,'exact cost ratio')
    else:
        need(change is None or change['candidate_minus_baseline'] is None,'no partial cost comparison')
    prov=dec((directory/'out/provenance.json').read_bytes())
    equal(prov['evaluator_key_sha256'],sha((directory/'key.json').read_bytes()),'key binding')
    actual={p.relative_to(directory/'run').as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
            for p in (directory/'run').rglob('*') if p.is_file()}
    equal(prov['cost_source']['files'],actual,'same source used for cost and score')
    # Check key secrets, not generic shared IDs. No source text/answer field in any output.
    exported=b''.join(p.read_bytes() for p in (directory/'out').iterdir())
    need(not any(token in exported for token in (b'QBN47Q_fixture',b'"values"',b'"fact_ids"',b'"packet_text"',b'"expected"')),'private body export')
    return want['decision']


def scenarios():
    yield from ('perfect-less','perfect-equal','perfect-more','both-wrong-less','both-wrong-equal','both-wrong-more',
                'all-abstain','conflict-order','wrong-conflict-value','wrong-conflict-evidence','unknown-cache','unknown-rates')
    for cid in IDS:
        yield 'regress-'+cid
    for position in (1,2,49,50,99,100):
        yield f'stop-{position}'


def build(fixture, dest, name):
    shutil.copytree(fixture/'run',dest/'run')
    shutil.copyfile(fixture/'evaluator-key.SYNTHETIC.json',dest/'key.json')
    shutil.copyfile(fixture/'rates.json',dest/'rates.json')
    key=dec((dest/'key.json').read_bytes())
    run=dec((dest/'run/run.json').read_bytes())
    need(run['execution_kind']=='LOOPBACK_TEST','refuse provider fixture')
    stop=int(name.split('-')[1]) if name.startswith('stop-') else None
    for row in run['rows']:
        index=row['index']; path=dest/f'run/{index:03}'
        if stop and index>stop:
            shutil.rmtree(path)
            for field in tuple(row):
                if field not in ('index','case_id','mode','request_id','status'): del row[field]
            row['status']='not_attempted'
            continue
        if stop and index==stop:
            row['status']='http_error'; row['http_status']=503
            for field in ('response_id','reported_model','usage'): row.pop(field,None)
            data=b''
        else:
            value=dec((path/'response.bin').read_bytes()); cid=row['case_id']; mode=row['mode']
            a=copy.deepcopy(key['expected'][cid]) if mode=='with-context' else dict(state='unknown',values=[],fact_ids=[])
            if name.startswith('both-wrong') and key['expected'][cid]['state'] in ('known','conflict'):
                a=dict(state='known',values=['QBN47Q_WRONG'],fact_ids=['f'*64])
            if name=='all-abstain': a=dict(state='unknown',values=[],fact_ids=[])
            if mode=='with-context':
                if name=='regress-'+cid: a=dict(state='known',values=['QBN47Q_WRONG'],fact_ids=['f'*64])
                if cid=='conflict-01':
                    if name=='conflict-order': a['values'].reverse();a['fact_ids'].reverse()
                    if name=='wrong-conflict-value': a['values'][0]='QBN47Q_WRONG'
                    if name=='wrong-conflict-evidence': a['fact_ids'][0]='f'*64
            a['case_id']=row['request_id']
            value['choices'][0]['message']['content']=enc(a).decode()
            n=100 if mode=='without-context' or name.endswith('-equal') else 150 if name.endswith('-more') else 50
            value['usage']['prompt_tokens']=n;value['usage']['total_tokens']=n+20
            if name=='unknown-cache': value['usage']['prompt_tokens_details']['cached_tokens']=None
            row['usage']['input_tokens']=n
            data=enc(value)
        (path/'response.bin').write_bytes(data)
        row.update(response_received_bytes=len(data),response_received_sha256=sha(data),response_saved_sha256=sha(data))
        (path/'receipt.json').write_bytes(enc(row))
    if stop: run.update(attempted=stop,completed=stop-1,result='INCOMPLETE')
    (dest/'run/run.json').write_bytes(enc(run))
    if name=='unknown-rates':
        p=dec((dest/'rates.json').read_bytes());p['rates']=[];(dest/'rates.json').write_bytes(enc(p))


def run_review(fixture, tool, binary, output, shard=0, shards=1):
    output.mkdir(parents=True,exist_ok=False)
    rows=[]
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
    inventory=list(scenarios())
    need(type(shard) is int and type(shards) is int and 1 <= shards <= len(inventory) and 0 <= shard < shards, 'invalid shard')
    for name in inventory[shard::shards]:
        dest=output/name;dest.mkdir();build(fixture,dest,name)
        command=[sys.executable]+(['-O'] if not __debug__ else [])+[str(tool),'export','--run',str(dest/'run'),
                 '--key',str(dest/'key.json'),'--rates',str(dest/'rates.json'),'--binary',str(binary),'--output',str(dest/'out')]
        p=subprocess.run(command,capture_output=True,env=env,timeout=90)
        (dest/'stdout').write_bytes(p.stdout);(dest/'stderr').write_bytes(p.stderr)
        row=dict(case=name,exit=p.returncode,stdout_sha256=sha(p.stdout),stderr_sha256=sha(p.stderr));rows.append(row)
        (output/'progress.json').write_bytes(enc(rows))
        need(p.returncode==0 and not p.stderr,'CLI failure '+name)
        row['decision']=validate(dest)
    result=dict(schema='qbrain-n48l-independent-review-v1',cases=len(rows),passed=True,
                binary_sha256=sha(binary.read_bytes()),tool_sha256=sha(tool.read_bytes()),reviewer_sha256=sha(Path(__file__).read_bytes()),
                optimized=not __debug__,records=rows,shard=shard,shards=shards,full_inventory=inventory,
                synthetic_only=True,real_model_or_client_verified=False)
    (output/'RESULT.json').write_bytes(enc(result))
    print(enc({k:v for k,v in result.items() if k!='records'}).decode(),end='')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('fixture','tool','binary','output'): p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--shard',type=int,default=0);p.add_argument('--shards',type=int,default=1)
    a=p.parse_args()
    run_review(a.fixture.resolve(strict=True),a.tool.resolve(strict=True),a.binary.resolve(strict=True),a.output.resolve(),a.shard,a.shards)
