"""Independent N48H history/unknown-state CLI oracle. Synthetic, offline only.

No imports from the production parser or the earlier fixture/reference suites.
Exact arithmetic uses Fraction; assertions remain active under python -O.
Saved request/stdout/stderr bytes and binary/script identities are retained.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
from fractions import Fraction

KEYS = ('input_uncached', 'input_cache_read', 'input_cache_write', 'output')
PRICES = ('1.234567', '0.000003', '2.345678', '3.456789')
MARKER = 'SYNTHETIC_PRIVATE_BODY_NOT_FOR_OUTPUT'
ABSENT = 'absent'
FORMATS = ('openai_chat', 'openai_responses', 'anthropic_messages')


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, label):
    if not condition:
        raise ValueError(label)


def decoded(raw):
    require(len(raw) <= 8 * 1024 * 1024, 'JSON byte bound')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def invalid(_):
        raise ValueError('nonfinite JSON number')
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique, parse_constant=invalid)


def same(left, right):
    # Python equality aliases False/0 and True/1. JSON type equality must not.
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def event(value):
    if isinstance(value, str):
        return 'data: ' + value + '\n\n'
    name = value.get('type')
    return (('event: ' + name + '\n') if name else '') + 'data: ' + encoded(value).decode() + '\n\n'


def response_body(usage, status):
    return {'id': 'synthetic-response', 'model': 'synthetic-model', 'object': 'response',
            'status': status, 'usage': usage, 'output': [{'text': MARKER}]}


def frames(fmt, early, final, reset=False, origin=0, terminal='completed'):
    if fmt == 'openai_responses':
        states = [('response.created', response_body(early, 'in_progress'))]
        if reset:
            states.append(('response.in_progress', response_body(None, 'in_progress')))
        states.append(('response.' + terminal, response_body(final, terminal)))
        return [{'type': name, 'sequence_number': origin + i, 'response': body}
                for i, (name, body) in enumerate(states)]
    if fmt == 'anthropic_messages':
        result = [{'type': 'message_start', 'message': {
            'id': 'synthetic-message', 'model': 'synthetic-model', 'type': 'message',
            'role': 'assistant', 'content': [], 'usage': early}}]
        if reset:
            result.append({'type': 'message_delta', 'delta': {}, 'usage': None})
        return result + [{'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}, 'usage': final},
                         {'type': 'message_stop'}]
    base = {'id': 'synthetic-chat', 'object': 'chat.completion.chunk', 'model': 'synthetic-model'}
    return [{**base, 'choices': [{'index': 0, 'delta': {'content': MARKER}, 'finish_reason': 'stop'}]},
            {**base, 'choices': [], 'usage': final}, '[DONE]']


def envelope(fmt, data, outcome='success'):
    provider = 'anthropic' if fmt == 'anthropic_messages' else 'openai'
    return {'schema': 'qbrain-stream-import-v1', 'currency': 'USD', 'rates': [{
        'rate_id': 'synthetic-rate', 'provider': provider, 'model': 'synthetic-model',
        'per_million': dict(zip(KEYS, PRICES))}], 'records': [{
        'call_id': 'synthetic-call', 'stage': 'main', 'rate_id': 'synthetic-rate',
        'attempt': 1, 'outcome': outcome, 'format': fmt, 'stream': ''.join(map(event, data))}]}


def cases():
    # Total equality is an independent arithmetic constraint, not parser reconstruction.
    for bound, inp, out, null_total, reset in itertools.product(
            (None, 0, 1, 10, 100), (None, 0, 5, 100), (None, 0, 5, 100), (False, True), (False, True)):
        early = {'total_tokens': bound}
        final = {'input_tokens': inp, 'output_tokens': out,
                 'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0}}
        if null_total:
            final['total_tokens'] = None
        bad = bound is not None and inp is not None and out is not None and inp + out < bound
        name = f'responses-history-{bound}-{inp}-{out}-{null_total}-{reset}'
        yield name, envelope('openai_responses', frames('openai_responses', early, final, reset)), \
            None if bad else [inp, 0, 0, out], 'stream_usage_lower_bound' if bad else None
    for bound, value, long_ttl, reset in itertools.product((None, 0, 1, 10, 100), (0, 1, 5, 10, 99, 100, 101), (False, True), (False, True)):
        early = {'input_tokens': 10, 'cache_read_input_tokens': 0, 'cache_creation_input_tokens': bound, 'output_tokens': 0}
        final = {'output_tokens': 7, 'cache_creation_input_tokens': None,
                 'cache_creation': {'ephemeral_5m_input_tokens': 0 if long_ttl else value,
                                    'ephemeral_1h_input_tokens': value if long_ttl else 0}}
        bad = bound is not None and value < bound
        name = f'anthropic-history-{bound}-{value}-{long_ttl}-{reset}'
        yield name, envelope('anthropic_messages', frames('anthropic_messages', early, final, reset)), \
            None if bad else [None if reset else 10, None if reset else 0, value, 7], 'stream_usage_lower_bound' if bad else None
    # Distinguish absent, null and known independently for all four token fields.
    for fmt in FORMATS:
        for states in itertools.product((ABSENT, None, 'known'), repeat=4):
            values = [10, 2, 3, 7]
            known = [v if s == 'known' else None for s, v in zip(states, values)]
            usage = {}
            if fmt == 'anthropic_messages':
                keys = ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens', 'output_tokens')
                for key, state, value in zip(keys, states, values):
                    if state != ABSENT:
                        usage[key] = value if state == 'known' else None
                early = {k: v for k, v in usage.items() if k != 'output_tokens'}
                final = {k: v for k, v in usage.items() if k == 'output_tokens'}
                expected = known
            else:
                ip = 'prompt_tokens' if fmt == 'openai_chat' else 'input_tokens'
                op = 'completion_tokens' if fmt == 'openai_chat' else 'output_tokens'
                detail = ip.replace('_tokens', '_tokens_details')
                for key, idx in ((ip, 0), (op, 3)):
                    if states[idx] != ABSENT:
                        usage[key] = values[idx] if states[idx] == 'known' else None
                usage[detail] = {}
                for key, idx in (('cached_tokens', 1), ('cache_write_tokens', 2)):
                    if states[idx] != ABSENT:
                        usage[detail][key] = values[idx] if states[idx] == 'known' else None
                early, final = None, usage
                expected = [5 if all(s == 'known' for s in states[:3]) else None, known[1], known[2], known[3]]
            yield f'{fmt}-unknown-{states}', envelope(fmt, frames(fmt, early, final)), expected, None
    # Both permitted origins and all terminal statuses; failed usage remains billable.
    for origin, terminal in itertools.product((0, 1), ('completed', 'failed', 'incomplete')):
        outcome = 'failure' if terminal != 'completed' else 'success'
        final = {'input_tokens': 100, 'output_tokens': 7,
                 'input_tokens_details': {'cached_tokens': 2, 'cache_write_tokens': 3}}
        yield f'response-terminal-{origin}-{terminal}', envelope('openai_responses', frames('openai_responses', {'total_tokens': 100}, final, True, origin, terminal), outcome), [95, 2, 3, 7], None
    # A bad record in an otherwise valid batch must produce no partial report.
    good_usage = {'input_tokens': 10, 'output_tokens': 7, 'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0}}
    good = envelope('openai_responses', frames('openai_responses', None, good_usage))
    bad = envelope('openai_responses', frames('openai_responses', {'total_tokens': 100}, good_usage))['records'][0]
    bad['call_id'] = 'bad-call'
    bad['stream'] = bad['stream'].replace('synthetic-response', 'second-response')
    for first in (False, True):
        root = copy.deepcopy(good)
        root['records'].insert(0 if first else 1, bad)
        yield f'atomic-history-{first}', root, None, 'stream_usage_lower_bound'


def money(value):
    scaled = value * 10**12
    require(scaled.denominator == 1, 'nonterminating synthetic amount')
    n = scaled.numerator
    return f'{n // 10**12}.{n % 10**12:012d}'


def evaluate(root, expected, error, code, stdout, stderr):
    require(not stderr, 'unexpected stderr')
    require(type(code) is int, 'exit type')
    result = decoded(stdout)
    require(MARKER.encode() not in stdout, 'raw content disclosed')
    if error:
        require(code == 2 and same(result, {'error': {'code': error}}), 'expected atomic error ' + error)
        return
    require(code == 0, 'unexpected exit ' + str(code))
    require(result['schema'] == 'qbrain-stream-import-report-v1', 'schema')
    require(result['stream_contract_validated'] is True and result['response_content_validated'] is False, 'validation scope')
    for flag in ('source_authenticated', 'all_provider_calls_observed', 'outcome_labels_verified', 'rate_applicability_verified', 'response_content_included'):
        require(result[flag] is False, flag)
    require(same(result['provider_requests_sent'], 0), 'reported requests')
    tokens = dict(zip(KEYS, expected))
    require(same(result['cost_input']['calls'][0]['tokens'], tokens), 'final token partition')
    report = result['cost_report']
    require(all(len(items) == 1 for items in (result['cost_input']['calls'], result['mapping'], report['calls'], report['by_rate'], report['by_stage'])), 'single-call shape')
    call = report['calls'][0]
    total = Fraction(0)
    for key, count, rate in zip(KEYS, expected, PRICES):
        component = call['components'][key]
        amount = None if count is None else Fraction(rate) * count / 10**6
        require(same(component['tokens'], count) and component['rate_per_million'] == rate, 'component identity')
        require(component['cost'] == (None if amount is None else money(amount)), 'component cost')
        if amount is not None:
            total += amount
    missing = sum(v is None for v in expected)
    for group in (call, report['summary'], report['by_rate'][0], report['by_stage'][0]):
        require(group['known_subtotal'] == money(total), 'known subtotal')
        require(same(group['unknown_components'], missing) and group['complete'] is (missing == 0), 'unknown propagation')
        require(group['total_estimate'] == (None if missing else money(total)), 'complete estimate')
    require(result['usage_complete'] is (missing == 0), 'usage completeness')
    require(same(report['summary']['failed_calls'], int(root['records'][0]['outcome'] == 'failure')), 'failed attempt retained')


def run(binary, output):
    output.mkdir(parents=True, exist_ok=False)
    rawdir = output / 'raw'
    rawdir.mkdir()
    rows = []
    failures = []
    counts = {'accepted': 0, 'rejected': 0}
    with tempfile.TemporaryDirectory(prefix='qbrain-history-') as temp:
        home = Path(temp) / 'home'
        home.mkdir()
        (home / 'sentinel').write_bytes(b'UNCHANGED')
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(('QBRAIN', 'OPENAI', 'ANTHROPIC', 'GH_TOKEN', 'GITHUB_TOKEN'))}
        env.update(HOME=str(home), USERPROFILE=str(home), LOCALAPPDATA=str(home), APPDATA=str(home))
        for index, (name, root, expected, error) in enumerate(cases()):
            data = encoded(root)
            response = subprocess.run([str(binary), 'cost', 'import-stream'], input=data, capture_output=True, cwd=temp, env=env, timeout=10)
            row = {'case': name, 'exit': response.returncode, 'expected_tokens': expected, 'expected_error': error, 'hashes': {}}
            for suffix, value in (('stdin', data), ('stdout', response.stdout), ('stderr', response.stderr)):
                (rawdir / f'{index:04d}.{suffix}').write_bytes(value)
                row['hashes'][suffix] = digest(value)
            try:
                evaluate(root, expected, error, response.returncode, response.stdout, response.stderr)
                row['passed'] = True
            except (ValueError, KeyError, TypeError, IndexError) as exc:
                row['passed'] = False
                row['failure'] = str(exc)
                failures.append({'case': name, 'failure': str(exc)})
            counts['rejected' if error else 'accepted'] += 1
            rows.append(row)
        clean = sorted(x.name for x in home.iterdir()) == ['sentinel'] and (home / 'sentinel').read_bytes() == b'UNCHANGED'
    if not clean:
        failures.append({'case': 'brain-free', 'failure': 'unexpected home mutation'})
    report = {'schema': 'qbrain-n48h-history-process-v1', 'binary_sha256': digest(binary.read_bytes()),
              'script_sha256': digest(Path(__file__).read_bytes()), 'platform': os.name,
              'optimized': not __debug__, 'commands': len(rows), 'passed': sum(r['passed'] for r in rows),
              'failed': len(failures), 'expected_counts': counts, 'brain_free': clean,
              'synthetic_only': True, 'failures': failures, 'records': rows}
    (output / 'report.json').write_bytes(encoded(report) + b'\n')
    return report


def verify(binary, output):
    report = decoded((output / 'report.json').read_bytes())
    require(set(report) == {'schema', 'binary_sha256', 'script_sha256', 'platform', 'optimized',
            'commands', 'passed', 'failed', 'expected_counts', 'brain_free', 'synthetic_only', 'failures', 'records'}, 'report fields')
    require(report['schema'] == 'qbrain-n48h-history-process-v1', 'report schema')
    require(report['binary_sha256'] == digest(binary.read_bytes()), 'binary identity')
    require(report['script_sha256'] == digest(Path(__file__).read_bytes()), 'script identity')
    all_cases = list(cases())
    require(len({c[0] for c in all_cases}) == len(all_cases) == 711, 'case generator inventory')
    require(same(report['commands'], len(all_cases)) and len(report['records']) == len(all_cases), 'case inventory')
    require(same(report['failed'], 0) and same(report['passed'], len(all_cases)) and report['failures'] == [], 'recorded failures')
    counts = {'accepted': sum(c[3] is None for c in all_cases), 'rejected': sum(c[3] is not None for c in all_cases)}
    require(same(report['expected_counts'], counts), 'expected counts')
    require(report['platform'] in ('nt', 'posix') and type(report['optimized']) is bool, 'execution metadata')
    require(report['brain_free'] is True and report['synthetic_only'] is True, 'recorded scope')
    expected_files = {f'{index:04d}.{suffix}' for index in range(len(all_cases)) for suffix in ('stdin', 'stdout', 'stderr')}
    require({p.name for p in (output / 'raw').iterdir()} == expected_files, 'raw inventory')
    for index, ((name, root, expected, error), row) in enumerate(zip(all_cases, report['records'])):
        require(set(row) == {'case', 'exit', 'expected_tokens', 'expected_error', 'hashes', 'passed'}, 'record fields')
        require(row['case'] == name and row['passed'] is True and type(row['exit']) is int, 'case identity')
        require(same(row['expected_tokens'], expected) and row['expected_error'] == error, 'oracle identity')
        require(set(row['hashes']) == {'stdin', 'stdout', 'stderr'}, 'digest fields')
        data = {}
        for suffix in ('stdin', 'stdout', 'stderr'):
            path = output / 'raw' / f'{index:04d}.{suffix}'
            require(path.is_file() and not path.is_symlink(), 'raw file type')
            value = path.read_bytes()
            require(digest(value) == row['hashes'][suffix], 'raw digest')
            data[suffix] = value
        require(data['stdin'] == encoded(root), 'regenerated request')
        evaluate(root, expected, error, row['exit'], data['stdout'], data['stderr'])
    return {'schema': 'qbrain-n48h-history-readback-v1', 'passed': True, 'commands': len(all_cases),
            'new_process_execution': False, 'source_authenticated': False}


def negatives(binary, output):
    """Mutate a copied synthetic report, never the original evidence or product."""
    verify(binary, output)
    original = decoded((output / 'report.json').read_bytes())
    rejected = []
    kinds = ('schema', 'binary', 'script', 'bool-failed', 'bool-exit', 'bool-provider-count',
             'bool-token', 'bool-component', 'bool-oracle', 'duplicate-json', 'nonfinite-json',
             'coverage', 'reorder', 'scope', 'expected-counts', 'failure-list', 'extra-raw',
             'missing-raw', 'raw-hash', 'rehash-wrong-input', 'rehash-wrong-cost', 'body-leak')
    with tempfile.TemporaryDirectory(prefix='qbrain-history-mutations-') as temp:
        target = Path(temp) / 'copy'
        shutil.copytree(output, target)
        stdout_path = target / 'raw' / '0000.stdout'
        original_stdout = stdout_path.read_bytes()
        stdin_path = target / 'raw' / '0000.stdin'
        original_stdin = stdin_path.read_bytes()
        for kind in kinds:
            report = copy.deepcopy(original)
            stdout_path.write_bytes(original_stdout)
            stdin_path.write_bytes(original_stdin)
            if kind == 'schema': report['schema'] = 'wrong'
            elif kind in ('binary', 'script'): report[kind + '_sha256'] = '0' * 64
            elif kind == 'bool-failed': report['failed'] = False
            elif kind == 'bool-exit': report['records'][0]['exit'] = False
            elif kind == 'bool-oracle': report['records'][0]['expected_tokens'][1] = False
            elif kind == 'coverage': report['records'].pop()
            elif kind == 'reorder': report['records'].reverse()
            elif kind == 'scope': report['synthetic_only'] = False
            elif kind == 'expected-counts': report['expected_counts']['accepted'] += 1
            elif kind == 'failure-list': report['failures'].append({'case': 'hidden'})
            elif kind == 'extra-raw': (target / 'raw' / 'extra.stdout').write_bytes(b'{}')
            elif kind == 'missing-raw': stdin_path.unlink()
            elif kind == 'rehash-wrong-input':
                stdin_path.write_bytes(b'{}')
                report['records'][0]['hashes']['stdin'] = digest(b'{}')
            else:
                value = decoded(original_stdout)
                if kind == 'bool-provider-count': value['provider_requests_sent'] = False
                elif kind == 'bool-token': value['cost_input']['calls'][0]['tokens']['input_cache_read'] = False
                elif kind == 'bool-component': value['cost_report']['calls'][0]['components']['input_cache_read']['tokens'] = False
                elif kind == 'rehash-wrong-cost': value['cost_report']['summary']['known_subtotal'] = '9.000000000000'
                elif kind == 'body-leak': value['extra'] = MARKER
                raw = encoded(value)
                if kind == 'duplicate-json': raw = b'{"schema":"wrong",' + raw[1:]
                elif kind == 'nonfinite-json': raw = b'{"extra":NaN,' + raw[1:]
                elif kind == 'raw-hash': raw = b'{}'
                stdout_path.write_bytes(raw)
                if kind != 'raw-hash': report['records'][0]['hashes']['stdout'] = digest(raw)
            (target / 'report.json').write_bytes(encoded(report))
            try:
                verify(binary, target)
            except (ValueError, KeyError, TypeError, IndexError, OSError):
                rejected.append(kind)
            else:
                raise ValueError('accepted evidence mutation: ' + kind)
            (target / 'raw' / 'extra.stdout').unlink(missing_ok=True)
    verify(binary, output)
    return rejected


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--negatives', action='store_true', help='read back and reject 22 corrupted evidence variants')
    args = parser.parse_args()
    try:
        binary = args.binary.resolve(strict=True)
        result = verify(binary, args.output) if args.verify or args.negatives else run(binary, args.output)
        if args.negatives:
            result['rejected_mutations'] = negatives(binary, args.output)
        print(json.dumps({k: v for k, v in result.items() if k not in ('records', 'failures')}))
        raise SystemExit(bool(result.get('failed', 0)))
    except (OSError, ValueError, KeyError, TypeError, IndexError, subprocess.SubprocessError) as exc:
        print(json.dumps({'error': type(exc).__name__, 'detail': str(exc)}))
        raise SystemExit(1)
