"""N48I independent paired-cost oracle and process/readback tests. Synthetic only.

No product/old-fixture imports. Fraction from decimal strings checks ALL output
amounts, canonical inputs and exact ratios without binary floating-point pricing.
Checks remain active under python -O. Raw streams and executable identities persist.
"""
from __future__ import annotations
import argparse
import copy
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import tempfile

BUCKETS = ('input_uncached', 'input_cache_read', 'input_cache_write', 'output')
SIDES = ('baseline', 'candidate')
SCALE = 10**12


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def decode(raw):
    require(len(raw) <= 8388608, 'output byte bound')
    def unique(pairs):
        result = {}
        for k, v in pairs:
            require(k not in result, 'duplicate JSON key')
            result[k] = v
        return result
    def invalid(_):
        raise ValueError('nonfinite JSON')
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique, parse_constant=invalid)


def exact_money(value, digits=12):
    scaled = value * 10**digits
    require(scaled.denominator == 1, 'unrepresentable synthetic decimal')
    n = scaled.numerator
    return ('-' if n < 0 else '') + str(abs(n) // 10**digits) + '.' + str(abs(n) % 10**digits).zfill(digits)


def cost_oracle(ledger):
    cards = {r['rate_id']: r for r in ledger['rates']}
    rows = []
    for call in sorted(ledger['calls'], key=lambda x: x['call_id']):
        prices = cards.get(call['rate_id'], {}).get('per_million', {})
        components = {}
        for key, quantity in call['tokens'].items():
            price = prices.get(key)
            cost = None if quantity is None or (quantity != 0 and price is None) else Fraction(quantity) * Fraction(price or '0') / 10**6
            missing = None if cost is not None else ('usage_unknown' if quantity is None else ('rate_unknown' if call['rate_id'] in cards else 'rate_card_missing'))
            components[key] = dict(tokens=quantity, rate_per_million=None if price is None else exact_money(Fraction(price), 6),
                                   cost=None if cost is None else exact_money(cost), missing=missing)
        values = [x['cost'] for x in components.values()]
        known = sum((Fraction(v) for v in values if v is not None), Fraction())
        gaps = values.count(None)
        rows.append({**{k: call[k] for k in ('call_id', 'stage', 'rate_id', 'attempt', 'outcome')},
                     'components': components, 'known_subtotal': exact_money(known), 'unknown_components': gaps,
                     'complete': gaps == 0, 'total_estimate': None if gaps else exact_money(known)})
    def aggregate(selected):
        gaps = sum(c['unknown_components'] for c in selected)
        total = sum((Fraction(c['known_subtotal']) for c in selected), Fraction())
        usage = {}
        for k in BUCKETS:
            counts = [c['components'][k]['tokens'] for c in selected]
            known = sum(x for x in counts if x is not None)
            usage[k] = dict(known_tokens=known, unknown_calls=counts.count(None), total_tokens=None if None in counts else known)
        return dict(calls=len(selected), failed_calls=sum(c['outcome'] == 'failure' for c in selected),
                    unknown_outcome_calls=sum(c['outcome'] == 'unknown' for c in selected),
                    retry_calls=sum(c['attempt'] > 1 for c in selected), known_subtotal=exact_money(total),
                    total_estimate=None if gaps else exact_money(total), complete=gaps == 0, unknown_components=gaps, tokens=usage)
    by_stage = [{**aggregate([c for c in rows if c['stage'] == s]), 'stage': s} for s in sorted({c['stage'] for c in rows})]
    by_rate = [{**aggregate([c for c in rows if c['rate_id'] == r]), 'rate_id': r,
                'provider': cards.get(r, {}).get('provider'), 'model': cards.get(r, {}).get('model')}
               for r in sorted({c['rate_id'] for c in rows})]
    canonical = copy.deepcopy(ledger)
    canonical['rates'].sort(key=lambda r: r['rate_id'])
    canonical['calls'].sort(key=lambda c: c['call_id'])
    for card in canonical['rates']:
        card['per_million'] = {k: None if v is None else exact_money(Fraction(v), 6) for k, v in card['per_million'].items()}
    return dict(schema='qbrain-cost-report-v1', currency=ledger['currency'], input_sha256=sha(encode(canonical)),
                basis='caller_supplied_disjoint_token_counts_and_rate_cards', rate_unit='currency_per_million_tokens',
                decimal_places=12, summary=aggregate(rows), by_stage=by_stage, by_rate=by_rate, calls=rows,
                billing_verified=False, all_provider_calls_observed=False, provider_requests_sent=0,
                fees_taxes_discounts_included=False, currency_conversion_performed=False)


def delta(a, b, eligible):
    if not eligible:
        return dict(candidate_minus_baseline=None, relative_change=None, unavailable_reason='comparison_not_eligible')
    before, after = Fraction(a['known_subtotal']), Fraction(b['known_subtotal'])
    fraction = None if before == 0 else (after - before) / before
    return dict(candidate_minus_baseline=exact_money(after - before),
                relative_change=None if fraction is None else dict(numerator=str(fraction.numerator), denominator=str(fraction.denominator)),
                unavailable_reason=None, relative_change_unavailable_reason='zero_baseline' if fraction is None else None)


def oracle(root):
    reports, tasks, shared, model_sets, price_sets, identities_known, bindings = {}, {}, {}, {}, {}, {}, {}
    for side in SIDES:
        arm = root[side]
        ledger = arm['cost_input']
        reports[side] = cost_oracle(ledger)
        by_id = {c['call_id']: c for c in ledger['calls']}
        def subset(ids):
            return cost_oracle({**ledger, 'calls': [by_id[k] for k in ids]})['summary']
        tasks[side] = {t['task_id']: subset(t['call_ids']) for t in arm['tasks']}
        shared[side] = subset(arm['shared_call_ids'])
        model_sets[side], price_sets[side], identities_known[side] = set(), set(), True
        cards = {r['rate_id']: r for r in ledger['rates']}
        for call in ledger['calls']:
            if call['stage'] != 'main':
                continue
            card = cards.get(call['rate_id'])
            if card is None:
                identities_known[side] = False
                continue
            model_sets[side].add((card['provider'], card['model']))
            price_sets[side].add(tuple(None if card['per_million'][k] is None else Fraction(card['per_million'][k]) for k in BUCKETS))
        bindings[side] = {k: arm[k] for k in ('label', 'conditions_sha256', 'ledger_complete')}
        bindings[side].update(cost_input_sha256=reports[side]['input_sha256'], shared_call_ids=sorted(arm['shared_call_ids']),
                              tasks=sorted([{**t, 'call_ids': sorted(t['call_ids'])} for t in arm['tasks']], key=lambda t: t['task_id']))
    primary_known = all(identities_known[s] and len(model_sets[s]) == 1 for s in SIDES)
    same_model = primary_known and model_sets['baseline'] == model_sets['candidate']
    same_prices = same_model and all(len(price_sets[s]) == 1 for s in SIDES) and price_sets['baseline'] == price_sets['candidate']
    reasons = []
    if not all(root[s]['ledger_complete'] for s in SIDES): reasons.append('declared_coverage_incomplete')
    if not all(reports[s]['summary']['complete'] for s in SIDES): reasons.append('cost_components_unknown')
    if not primary_known: reasons.append('primary_model_unknown_or_multiple')
    elif not same_model: reasons.append('primary_model_mismatch')
    if same_model and not same_prices: reasons.append('primary_price_schedule_mismatch')
    eligible = not reasons
    paired = [{**{k: t[k] for k in ('task_id', 'task_sha256')},
               **{s: tasks[s][t['task_id']] for s in SIDES},
               'change': delta(tasks['baseline'][t['task_id']], tasks['candidate'][t['task_id']], eligible)}
              for t in sorted(root['baseline']['tasks'], key=lambda t: t['task_id'])]
    empty = cost_oracle(dict(schema='qbrain-cost-input-v1', currency=root['currency'], rates=[], calls=[]))['summary']
    stage_maps = {s: {t['stage']: t for t in reports[s]['by_stage']} for s in SIDES}
    stages = []
    for stage in sorted(set(stage_maps['baseline']) | set(stage_maps['candidate'])):
        a, b = [stage_maps[s].get(stage, empty) for s in SIDES]
        stages.append(dict(stage=stage, baseline=a, candidate=b, change=delta(a, b, eligible)))
    binding = {k: root[k] for k in ('schema', 'comparison_id', 'currency')}
    binding.update(bindings)
    return dict(schema='qbrain-cost-comparison-report-v1', comparison_id=root['comparison_id'], currency=root['currency'],
                input_sha256=sha(encode(binding)), comparison_eligible=eligible, unavailable_reasons=reasons,
                same_declared_primary_model=same_model, same_declared_primary_prices=same_prices, task_count=len(paired), binding=binding,
                **{s: dict(label=root[s]['label'], cost_report=reports[s]) for s in SIDES},
                change=delta(reports['baseline']['summary'], reports['candidate']['summary'], eligible), by_task=paired, by_stage=stages,
                shared={**shared, 'change': delta(shared['baseline'], shared['candidate'], eligible)},
                coverage_is_caller_declaration=True, conditions_authenticated=False, billing_verified=False,
                quality_verified=False, host_consumption_verified=False, all_provider_calls_observed=False,
                provider_requests_sent=0, fees_taxes_discounts_included=False, currency_conversion_performed=False)


def call(cid, quantity, stage='main', price='r', outcome='success', attempt=1):
    return dict(call_id=cid, rate_id=price, stage=stage, outcome=outcome, attempt=attempt,
                tokens=dict(zip(BUCKETS, [quantity, 0, 0, 20])))


def base():
    def arm(label, quantity):
        return dict(label=label, conditions_sha256='a'*64, ledger_complete=True,
                    cost_input=dict(schema='qbrain-cost-input-v1', currency='USD',
                                    rates=[dict(rate_id='r', provider='synthetic', model='model-v1', per_million=dict.fromkeys(BUCKETS, '1'))],
                                    calls=[call('c', quantity)]),
                    tasks=[dict(task_id='t', task_sha256='b'*64, call_ids=['c'])], shared_call_ids=[])
    return dict(schema='qbrain-cost-comparison-v1', comparison_id='synthetic', currency='USD',
                baseline=arm('without-context', 100), candidate=arm('with-context', 50))


def valid_cases():
    yield 'basic', base()
    x = base()
    x['candidate']['cost_input']['calls'].append(call('shared', 100, 'embedding'))
    x['candidate']['shared_call_ids'].append('shared')
    yield 'shared-reverses-main-savings', x
    x = copy.deepcopy(x)
    x['candidate']['cost_input']['calls'].append(call('retry', 100, outcome='failure', attempt=2))
    x['candidate']['tasks'][0]['call_ids'].append('retry')
    yield 'retry-and-shared', x
    x = copy.deepcopy(x)
    x['candidate']['cost_input']['calls'].reverse(); x['candidate']['tasks'][0]['call_ids'].reverse()
    yield 'permuted', x
    for side in SIDES:
        for state in ('coverage', 'model', 'price', 'missing-rate', 'unknown-rate', 'zero-rate', 'unknown-outcome'):
            x = base(); a = x[side]
            if state == 'coverage': a['ledger_complete'] = False
            elif state == 'model': a['cost_input']['rates'][0]['model'] = 'other'
            elif state == 'price': a['cost_input']['rates'][0]['per_million']['output'] = '2'
            elif state == 'missing-rate': a['cost_input']['rates'] = []
            elif state == 'unknown-rate': a['cost_input']['rates'][0]['per_million']['output'] = None
            elif state == 'zero-rate': a['cost_input']['rates'][0]['per_million']['output'] = '0'
            elif state == 'unknown-outcome': a['cost_input']['calls'][0]['outcome'] = 'unknown'
            yield side + '-' + state, x
        for bucket in BUCKETS:
            x = base(); x[side]['cost_input']['calls'][0]['tokens'][bucket] = None
            yield side + '-null-' + bucket, x
    for n in (0, 1, 10**9):
        x = base()
        for side in SIDES:
            x[side]['cost_input']['calls'][0]['tokens'] = dict.fromkeys(BUCKETS, 0)
            x[side]['cost_input']['rates'][0]['per_million'] = dict.fromkeys(BUCKETS, '10000')
        x['candidate']['cost_input']['calls'][0]['tokens']['input_uncached'] = n
        yield f'zero-base-{n}', x
        x = copy.deepcopy(x); x['baseline'], x['candidate'] = x['candidate'], x['baseline']
        yield f'zero-candidate-{n}', x
    x = base()
    for side in SIDES:
        x[side]['cost_input']['rates'][0]['per_million'] = dict.fromkeys(BUCKETS, None)
        x[side]['cost_input']['calls'][0]['tokens'] = dict.fromkeys(BUCKETS, 0)
    yield 'known-zero-unknown-price', x
    # Identical auxiliary model or main rate aliases must not imply extra primary identities.
    for mode in ('alias', 'multi-model', 'multi-price'):
        x = base(); a = x['candidate']; card = copy.deepcopy(a['cost_input']['rates'][0]); card['rate_id'] = 's'
        if mode == 'multi-model': card['model'] = 'second'
        if mode == 'multi-price': card['per_million']['output'] = '2'
        a['cost_input']['rates'].append(card); a['cost_input']['calls'].append(call('second', 1, price='s'))
        a['tasks'][0]['call_ids'].append('second')
        yield mode, x
    rng = random.Random(48109)
    for index in range(160):
        x = base(); price = {k: rng.choice(['0', '0.000001', '1', '2.345678', '7.000003']) for k in BUCKETS}
        count = rng.randrange(1, 7)
        for side in SIDES:
            a = x[side]; a['tasks'] = []; ledger = a['cost_input']; ledger['calls'] = []
            ledger['rates'][0]['per_million'] = price.copy()
            ledger['rates'].append(dict(rate_id='aux', provider='auxiliary', model='extra', per_million=dict.fromkeys(BUCKETS, '3.234567')))
            for tid in range(count):
                task = dict(task_id=f't{tid}', task_sha256=sha(f'common-task-{tid}'.encode()), call_ids=[])
                for j in range(rng.randrange(1, 4)):
                    cid = f'{tid}-{j}'; stage = 'main' if j == 0 else rng.choice(['main', 'embedding', 'summary', 'extraction', 'rerank', 'other'])
                    c = call(cid, 0, stage, 'r' if stage == 'main' else 'aux', rng.choice(['success', 'failure', 'unknown']), j+1)
                    c['tokens'] = {k: rng.randrange(0, 1000000) for k in BUCKETS}
                    if index >= 100 and rng.randrange(5) == 0: c['tokens'][rng.choice(BUCKETS)] = None
                    ledger['calls'].append(c); task['call_ids'].append(cid)
                a['tasks'].append(task)
            if index % 3 == 0:
                ledger['calls'].append(call('shared', rng.randrange(10000), 'embedding', 'aux'))
                a['shared_call_ids'].append('shared')
            if index >= 120: a['ledger_complete'] = index % 2 == 0
            rng.shuffle(ledger['rates']); rng.shuffle(ledger['calls']); rng.shuffle(a['tasks'])
        yield f'fraction-matrix-{index:03}', x
    # Exercise exact 128-task/512-call/64-card boundaries, all assignment slots present.
    x = base()
    for side in SIDES:
        a = x[side]; ledger = a['cost_input']; ledger['calls'] = []; a['tasks'] = []
        template = ledger['rates'][0]
        for i in range(1, 64): ledger['rates'].append({**template, 'rate_id': f'unused{i}'})
        for i in range(128):
            ids = []
            for j in range(4):
                cid = f'{i}-{j}'; ids.append(cid); ledger['calls'].append(call(cid, i+j, outcome='failure' if j else 'success', attempt=j+1))
            a['tasks'].append(dict(task_id=f't{i:03}', task_sha256=sha(str(i).encode()), call_ids=ids))
    yield 'max-manifest', x


def cases():
    for name, root in valid_cases():
        yield name, encode(root), ['cost', 'compare'], oracle(root)
    def bad(name, root, code):
        return name, encode(root), ['cost', 'compare'], {'error': {'code': code}}
    for side in SIDES:
        variations = [
            ('coverage-int', ('ledger_complete',), 1, 'comparison_coverage_flag'),
            ('empty-tasks', ('tasks',), [], 'comparison_task_count'),
            ('empty-refs', ('tasks', 0, 'call_ids'), [], 'comparison_call_ids'),
            ('duplicate-ref', ('tasks', 0, 'call_ids'), ['c', 'c'], 'comparison_call_reused'),
            ('missing-ref', ('tasks', 0, 'call_ids'), ['missing'], 'comparison_call_missing'),
            ('shared-reused', ('shared_call_ids',), ['c'], 'comparison_call_reused'),
            ('bad-digest', ('conditions_sha256',), 'G'*64, 'comparison_digest'),
            ('short-digest', ('conditions_sha256',), 'a'*63, 'comparison_digest'),
            ('bool-digest', ('conditions_sha256',), True, 'comparison_digest'),
            ('currency', ('cost_input','currency'), 'EUR', 'comparison_currency'),
            ('bool-token', ('cost_input','calls',0,'tokens','output'), True, 'cost_quantity'),
            ('negative-token', ('cost_input','calls',0,'tokens','output'), -1, 'cost_quantity'),
            ('float-token', ('cost_input','calls',0,'tokens','output'), 1.0, 'cost_quantity'),
            ('cap-token', ('cost_input','calls',0,'tokens','output'), 1000000001, 'cost_quantity'),
            ('no-main', ('cost_input','calls',0,'stage'), 'embedding', 'comparison_main_missing'),
            ('bad-stage', ('cost_input','calls',0,'stage'), 'invalid', 'cost_stage'),
            ('rate-exponent', ('cost_input','rates',0,'per_million','output'), '1e-3', 'cost_rate_decimal'),
            ('rate-precision', ('cost_input','rates',0,'per_million','output'), '1.1234567', 'cost_rate_decimal'),
            ('label-length', ('label',), 'a'*65, 'cost_identifier'),
            ('private-label', ('label',), 'secret body\n', 'cost_identifier'),
            ('boolean-attempt', ('cost_input','calls',0,'attempt'), True, 'cost_quantity'),
            ('zero-attempt', ('cost_input','calls',0,'attempt'), 0, 'cost_attempt'),
        ]
        for name, path, value, code in variations:
            x = base(); target = x[side]
            for k in path[:-1]: target = target[k]
            target[path[-1]] = value
            yield bad(side + '-' + name, x, code)
        x = base(); x[side]['tasks'].append(copy.deepcopy(x[side]['tasks'][0])); yield bad(side+'-duplicate-task', x, 'comparison_duplicate_task')
        x = base(); x[side]['cost_input']['calls'].append(call('unowned', 1)); yield bad(side+'-unowned', x, 'comparison_unassigned_call')
        x[side]['shared_call_ids'].append('unowned'); yield bad(side+'-shared-main', x, 'comparison_shared_main')
        x = base(); x[side]['tasks'] *= 129; yield bad(side+'-task-cap', x, 'comparison_task_count')
        x = base(); x[side]['cost_input']['rates'] *= 65; yield bad(side+'-rate-cap', x, 'cost_rate_count')
        x = base(); x[side]['cost_input']['calls'] *= 513; yield bad(side+'-call-cap', x, 'cost_call_count')
        x = base(); x[side]['tasks'][0]['call_ids'] *= 513; yield bad(side+'-ref-cap', x, 'comparison_call_ids')
        x = base(); x[side]['cost_input']['rates'][0]['per_million']['output'] = '1000000'; x[side]['cost_input']['calls'][0]['tokens']['output'] = 10**9
        yield bad(side+'-overflow', x, 'cost_overflow')
    for name, path, value, code in [
        ('conditions-mismatch', ('candidate','conditions_sha256'), 'c'*64, 'comparison_conditions_mismatch'),
        ('task-id-mismatch', ('candidate','tasks',0,'task_id'), 'other', 'comparison_task_set'),
        ('task-digest-mismatch', ('candidate','tasks',0,'task_sha256'), 'c'*64, 'comparison_task_mismatch'),
        ('labels-equal', ('candidate','label'), 'without-context', 'comparison_labels'),
        ('schema', ('schema',), 'wrong', 'comparison_schema'),
        ('extra-body', ('body',), 'PRIVATE_SHOULD_NOT_ECHO', 'cost_fields')]:
        x = base(); target = x
        for k in path[:-1]: target = target[k]
        target[path[-1]] = value
        yield bad(name, x, code)
    for side in SIDES:
        for field in base()[side]:
            x = base(); del x[side][field]; yield bad(f'{side}-missing-{field}', x, 'cost_fields')
    for field in base():
        x = base(); del x[field]; yield bad('missing-'+field, x, 'cost_fields')
    raw = encode(base())
    for name, data, args, code in [
        ('duplicate-root', b'{"schema":"wrong",'+raw[1:], ['cost','compare'], 'comparison_duplicate_key'),
        ('duplicate-inner', raw.replace(b'"attempt":1', b'"attempt":1,"attempt":2', 1), ['cost','compare'], 'comparison_duplicate_key'),
        ('bad-utf8', b'{"x":"\xff"}', ['cost','compare'], 'comparison_invalid_json'),
        ('nan', b'{"x":NaN}', ['cost','compare'], 'comparison_invalid_json'),
        ('truncated', raw[:-1], ['cost','compare'], 'comparison_invalid_json'),
        ('deep', b'['*34+b'0'+b']'*34, ['cost','compare'], 'comparison_invalid_json'),
        ('input-cap', b' '*1048577, ['cost','compare'], 'comparison_input_limit'),
        ('wrong-action', raw, ['cost','compare','extra'], 'comparison_invalid_action')]:
        yield name, data, args, {'error': {'code': code}}


def validate_case(expected, code, stdout, stderr):
    require(not stderr, 'unexpected process stderr')
    require(type(code) is int and code == (2 if 'error' in expected else 0), 'exit mismatch')
    actual = decode(stdout)
    require(encode(actual) == encode(expected), 'full independent result mismatch')


def run(binary, output):
    output.mkdir(parents=True, exist_ok=False); (output/'raw').mkdir()
    records = []
    with tempfile.TemporaryDirectory(prefix='qbrain-cost-comparison-') as temp:
        home = Path(temp)/'home'; home.mkdir(); (home/'sentinel').write_bytes(b'UNCHANGED')
        env = {k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
        env.update(HOME=str(home), USERPROFILE=str(home), APPDATA=str(home), LOCALAPPDATA=str(home))
        for index, (name, data, args, expected) in enumerate(cases()):
            response = subprocess.run([str(binary), *args], input=data, capture_output=True, timeout=20, cwd=temp, env=env)
            row = dict(name=name, args=args, exit=response.returncode, hashes={}, passed=True)
            for suffix, value in (('stdin',data), ('stdout',response.stdout), ('stderr',response.stderr)):
                (output/'raw'/f'{index:04d}.{suffix}').write_bytes(value); row['hashes'][suffix] = sha(value)
            try: validate_case(expected, response.returncode, response.stdout, response.stderr)
            except (ValueError, TypeError, KeyError, IndexError) as exc: row.update(passed=False, failure=str(exc))
            records.append(row)
        clean = sorted(p.name for p in home.iterdir()) == ['sentinel'] and (home/'sentinel').read_bytes() == b'UNCHANGED'
        require(clean, 'unexpected home mutation')
    report = dict(schema='qbrain-cost-comparison-process-v1', binary_sha256=sha(binary.read_bytes()),
                  script_sha256=sha(Path(__file__).read_bytes()), optimized=not __debug__, platform=os.name,
                  synthetic_only=True, home_unchanged=True, commands=len(records), passed=sum(r['passed'] for r in records),
                  failed=sum(not r['passed'] for r in records), records=records)
    (output/'report.json').write_bytes(encode(report)+b'\n')
    return report


def verify(binary, output):
    report = decode((output/'report.json').read_bytes())
    require(set(report) == {'schema','binary_sha256','script_sha256','optimized','platform','synthetic_only','home_unchanged','commands','passed','failed','records'}, 'report fields')
    require(report['schema'] == 'qbrain-cost-comparison-process-v1', 'report schema')
    require(report['binary_sha256'] == sha(binary.read_bytes()), 'binary identity')
    require(report['script_sha256'] == sha(Path(__file__).read_bytes()), 'script identity')
    expected_cases = list(cases())
    require(len({c[0] for c in expected_cases}) == len(expected_cases), 'unique cases')
    for k, v in [('commands',len(expected_cases)), ('passed',len(expected_cases)), ('failed',0)]:
        require(type(report[k]) is int and report[k] == v, 'inventory/count')
    require(report['platform'] in ('nt','posix') and type(report['optimized']) is bool, 'platform/mode')
    require(report['synthetic_only'] is True and report['home_unchanged'] is True, 'scope')
    require(len(report['records']) == len(expected_cases), 'row inventory')
    require({p.name for p in (output/'raw').iterdir()} == {f'{i:04d}.{s}' for i in range(len(expected_cases)) for s in ('stdin','stdout','stderr')}, 'file inventory')
    for i, ((name, data, args, expected), row) in enumerate(zip(expected_cases,report['records'])):
        require(set(row) == {'name','args','exit','hashes','passed'}, 'row fields')
        require(row['name'] == name and row['args'] == args and row['passed'] is True, 'case identity')
        require(set(row['hashes']) == {'stdin','stdout','stderr'}, 'hash fields')
        streams = {}
        for suffix in ('stdin','stdout','stderr'):
            path = output/'raw'/f'{i:04d}.{suffix}'
            require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 8388608, 'file type/size')
            streams[suffix] = path.read_bytes(); require(sha(streams[suffix]) == row['hashes'][suffix], 'stream hash')
        require(streams['stdin'] == data, 'regenerated request')
        validate_case(expected, row['exit'], streams['stdout'], streams['stderr'])
    return dict(passed=True, commands=len(expected_cases), new_process_execution=False)


def negatives(binary, output):
    verify(binary, output)
    original = decode((output/'report.json').read_bytes())
    kinds = ('schema','binary','script','bool-count','bool-exit','bool-task-count','wrong-delta','wrong-ratio',
             'zero-for-unknown','changed-scope','coverage','reorder','duplicate-json','nan','extra-raw','missing-raw',
             'raw-hash','rehash-input','extra-body','omitted-overhead')
    rejected = []
    with tempfile.TemporaryDirectory(prefix='qbrain-comparison-mutations-') as temp:
        target = Path(temp)/'copy'; shutil.copytree(output,target)
        outpath = target/'raw'/'0000.stdout'; outbytes = outpath.read_bytes()
        inpath = target/'raw'/'0000.stdin'; inbytes = inpath.read_bytes()
        for kind in kinds:
            report = copy.deepcopy(original); outpath.write_bytes(outbytes); inpath.write_bytes(inbytes)
            if kind == 'schema': report['schema'] = 'wrong'
            elif kind in ('binary','script'): report[kind+'_sha256'] = '0'*64
            elif kind == 'bool-count': report['failed'] = False
            elif kind == 'bool-exit': report['records'][0]['exit'] = False
            elif kind == 'coverage': report['records'].pop()
            elif kind == 'reorder': report['records'].reverse()
            elif kind == 'extra-raw': (target/'raw'/'extra').write_bytes(b'{}')
            elif kind == 'missing-raw': inpath.unlink()
            elif kind == 'rehash-input': inpath.write_bytes(b'{}'); report['records'][0]['hashes']['stdin'] = sha(b'{}')
            else:
                value = decode(outbytes)
                if kind == 'bool-task-count': value['task_count'] = True
                elif kind == 'wrong-delta': value['change']['candidate_minus_baseline'] = '0.000000000000'
                elif kind == 'wrong-ratio': value['change']['relative_change']['denominator'] = '11'
                elif kind == 'zero-for-unknown': value['shared']['change']['relative_change'] = {'numerator':'0','denominator':'1'}
                elif kind == 'changed-scope': value['billing_verified'] = True
                elif kind == 'extra-body': value['body'] = 'PRIVATE_MUST_NOT_APPEAR'
                elif kind == 'omitted-overhead': value['shared']['candidate']['calls'] = 1
                raw = encode(value)
                if kind == 'duplicate-json': raw = b'{"schema":"wrong",'+raw[1:]
                elif kind == 'nan': raw = b'{"x":NaN,'+raw[1:]
                elif kind == 'raw-hash': raw = b'{}'
                outpath.write_bytes(raw)
                if kind != 'raw-hash': report['records'][0]['hashes']['stdout'] = sha(raw)
            (target/'report.json').write_bytes(encode(report))
            try: verify(binary,target)
            except (ValueError, TypeError, KeyError, IndexError, OSError): rejected.append(kind)
            else: raise ValueError('accepted evidence mutation: '+kind)
            (target/'raw'/'extra').unlink(missing_ok=True)
    verify(binary,output)
    return rejected


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,required=True); parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--verify',action='store_true'); parser.add_argument('--negatives',action='store_true')
    args = parser.parse_args()
    try:
        binary = args.binary.resolve(strict=True)
        result = verify(binary,args.output) if args.verify or args.negatives else run(binary,args.output)
        if args.negatives: result['rejected_mutations'] = negatives(binary,args.output)
        print(json.dumps({k:v for k,v in result.items() if k != 'records'}))
        raise SystemExit(bool(result.get('failed',0)))
    except (ValueError, TypeError, KeyError, IndexError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({'error':type(error).__name__,'detail':str(error)})); raise SystemExit(1)
