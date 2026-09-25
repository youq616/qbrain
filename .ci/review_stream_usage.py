"""N48H separate outcome probes: independent synthetic streams and Fraction oracle.

No imports from the implementation or its original fixture/reconstruction helpers.
Run with --binary and --output; --readback rechecks recorded bytes without spawning.
A successful replay is not authenticated traffic, a provider bill or model usage.
"""
from __future__ import annotations
import argparse
import copy
from fractions import Fraction
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import tempfile

KEYS = ('input_uncached', 'input_cache_read', 'input_cache_write', 'output')
PRICES = ('1.125000', '0.125000', '2.500000', '3.250000')
MISSING = 'OMITTED'
BODY = 'PRIVATE_N48H_REVIEW_BODY'


def need(ok, label):
    if not ok:
        raise ValueError(label)


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def decode(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            need(key not in value, 'duplicate JSON key')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=unique)


def frame(value, nl='\n'):
    return 'data: ' + (value if isinstance(value, str) else encode(value).decode('utf-8')) + nl + nl


def response_event(phase, sequence, usage=MISSING):
    response = {'id': 'response-history', 'model': 'history-fixture', 'object': 'response',
                'status': 'in_progress' if phase == 'created' else phase}
    if usage != MISSING:
        response['usage'] = usage
    return {'type': 'response.' + phase, 'sequence_number': sequence, 'response': response}


def message_start(usage):
    return {'type': 'message_start', 'message': {'id': 'message-history', 'model': 'history-fixture',
            'type': 'message', 'role': 'assistant', 'content': [], 'stop_reason': None, 'usage': usage}}


def message_delta(usage=MISSING, stop=False):
    value = {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'} if stop else {}}
    if usage != MISSING:
        value['usage'] = usage
    return value


def cases():
    results = []
    def add(label, fmt, frames, tokens=None, error=None, nl='\n'):
        record = {'call_id': 'review', 'stage': 'main', 'rate_id': 'review-rate', 'attempt': 1,
                  'outcome': 'success', 'format': fmt, 'stream': ''.join(frame(v, nl) for v in frames)}
        root = {'schema': 'qbrain-stream-import-v1', 'currency': 'USD', 'rates': [{
                'rate_id': 'review-rate', 'provider': 'anthropic' if fmt == 'anthropic_messages' else 'openai',
                'model': 'history-fixture', 'per_million': dict(zip(KEYS, PRICES))}], 'records': [record]}
        results.append((label, root, tokens, error))

    # Known historical total; only the FINAL pair can determine the current sum.
    states = (0, 3, 7, 20, None, MISSING)
    for old, inp, out, null_total, origin in itertools.product((0, 7, 20), states, states, (False, True), (0, 1)):
        final = {'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0}}
        for key, value in (('input_tokens', inp), ('output_tokens', out)):
            if value != MISSING:
                final[key] = value
        if null_total:
            final['total_tokens'] = None
        known_pair = type(inp) is int and type(out) is int
        error = 'stream_usage_lower_bound' if known_pair and inp + out < old else None
        tokens = [inp if type(inp) is int else None, 0, 0, out if type(out) is int else None]
        add(f'responses aggregate {old}/{inp}/{out}/{null_total}/{origin}', 'openai_responses',
            [response_event('created', origin, {'total_tokens': old}),
             response_event('completed', origin + 1, final)], tokens, error)

    # Forward historical bounds remain intact when a current component is null.
    for total in (0, 9, 10, 20):
        add(f'responses forward {total}', 'openai_responses', [
            response_event('created', 0, {'input_tokens': 10}),
            response_event('completed', 1, {'input_tokens': None, 'output_tokens': 0,
                'total_tokens': total, 'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0}})],
            [None, 0, 0, 0], 'stream_usage_lower_bound' if total < 10 else None)

    # An exact TTL sum is a second representation of the cumulative cache count.
    for old, now, ttl, mode in itertools.product((0, 7, 20), (0, 3, 7, 20), (0, 1), ('null', 'omitted', 'cleared')):
        initial = {'input_tokens': 11, 'cache_read_input_tokens': 0, 'cache_creation_input_tokens': old, 'output_tokens': 1}
        update = {'output_tokens': 9, 'cache_creation': {'ephemeral_5m_input_tokens': now if ttl == 0 else 0,
                  'ephemeral_1h_input_tokens': now if ttl == 1 else 0}}
        if mode == 'null':
            update['cache_creation_input_tokens'] = None
        frames = [message_start(initial)]
        if mode == 'cleared':
            frames.append(message_delta(None))
        frames += [message_delta(update, stop=True), {'type': 'message_stop'}]
        error = ('usage_inconsistent' if now != old else None) if mode == 'omitted' else ('stream_usage_lower_bound' if now < old else None)
        tokens = [None if mode == 'cleared' else 11, None if mode == 'cleared' else 0, now, 9]
        add(f'anthropic TTL {old}/{now}/{ttl}/{mode}', 'anthropic_messages', frames, tokens, error)

    # Sparse TTL updates must be checked after merging retained sibling fields.
    for now in (0, 6, 7, 8):
        initial = {'input_tokens': 11, 'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 7,
                   'cache_creation': {'ephemeral_5m_input_tokens': 7, 'ephemeral_1h_input_tokens': 0}, 'output_tokens': 1}
        update = {'cache_creation_input_tokens': None, 'cache_creation': {'ephemeral_5m_input_tokens': now}, 'output_tokens': 9}
        add(f'anthropic sparse TTL {now}', 'anthropic_messages', [message_start(initial), message_delta(update, True), {'type': 'message_stop'}],
            [11, 0, now, 9], 'stream_usage_decreased' if now < 7 else None)

    # Null clears the current value but not the historic monotonic lower bound.
    for mode, final in itertools.product(('field', 'whole'), (None, MISSING, 0, 7, 8, 9)):
        initial = {'input_tokens': 11, 'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0, 'output_tokens': 1}
        update = {} if final == MISSING else {'output_tokens': final}
        frames = [message_start(initial), message_delta({'output_tokens': 8}),
                  message_delta({'output_tokens': None} if mode == 'field' else None),
                  message_delta(update, True), {'type': 'message_stop'}]
        tokens = [11, 0, 0, final if type(final) is int else None] if mode == 'field' else [None, None, None, final if type(final) is int else None]
        add(f'anthropic null {mode}/{final}', 'anthropic_messages', frames, tokens,
            'stream_usage_decreased' if type(final) is int and final < 8 else None)

    # Independently created Chat frames: multi-choice output never multiplies usage.
    for count, nl, tail in itertools.product((1, 2, 32), ('\n', '\r', '\r\n'), (False, True)):
        chunk = {'id': 'chat-history', 'object': 'chat.completion.chunk', 'model': 'history-fixture'}
        choices = [{'index': i, 'delta': {'content': BODY}, 'finish_reason': 'stop'} for i in range(count)]
        frames = [{**chunk, 'choices': choices}]
        if tail:
            frames.append({**chunk, 'choices': [], 'usage': {'prompt_tokens': 11,
                'prompt_tokens_details': {'cached_tokens': 2, 'cache_write_tokens': 0}, 'completion_tokens': 9}})
        frames.append('[DONE]')
        add(f'chat independent {count}/{repr(nl)}/{tail}', 'openai_chat', frames, [9, 2, 0, 9] if tail else [None] * 4, nl=nl)

    # Reject an entire batch; a valid first row must not leak a partial cost report.
    good = copy.deepcopy(results[-1][1])
    bad = copy.deepcopy(good['records'][0]); bad['call_id'] = 'broken'; bad['stream'] = 'data: [DONE]\n\n'
    good['records'].append(bad)
    results.append(('batch atomic rejection', good, None, 'stream_chat_choices'))
    return results


def money(value):
    scaled = value * 10**12
    need(scaled.denominator == 1, 'reference precision')
    n = scaled.numerator
    return f'{n // 10**12}.{n % 10**12:012d}'


def check_result(case, exit_code, stdout, stderr):
    label, root, tokens, error = case
    need(stderr == b'', label + ': stderr')
    value = decode(stdout)
    if error:
        need(exit_code == 2 and value == {'error': {'code': error}}, label + ': rejection')
        return
    need(exit_code == 0 and value['schema'] == 'qbrain-stream-import-report-v1', label + ': success')
    need(BODY.encode() not in stdout, label + ': content leaked')
    need(value['stream_contract_validated'] is True and value['response_content_validated'] is False, label + ': scope')
    need(value['provider_requests_sent'] == 0 and value['source_authenticated'] is False, label + ': provenance')
    need(value['cost_input']['calls'][0]['tokens'] == dict(zip(KEYS, tokens)), label + ': token oracle')
    complete = all(v is not None for v in tokens)
    need(value['usage_complete'] is complete and value['mapping'][0]['usage_complete'] is complete, label + ': completeness')
    cost = value['cost_report']; call = cost['calls'][0]
    amounts = [None if n is None else Fraction(n) * Fraction(rate) / 1_000_000 for n, rate in zip(tokens, PRICES)]
    subtotal = money(sum((v for v in amounts if v is not None), Fraction(0)))
    total = subtotal if complete else None
    for summary in (cost['summary'], cost['by_rate'][0], cost['by_stage'][0], call):
        need(summary['known_subtotal'] == subtotal and summary['total_estimate'] == total, label + ': Fraction cost')
        need(summary['complete'] is complete and summary['unknown_components'] == tokens.count(None), label + ': unknown costs')
    for key, n, rate, amount in zip(KEYS, tokens, PRICES, amounts):
        component = call['components'][key]
        need(component['tokens'] == n and component['rate_per_million'] == rate, label + ': component identity')
        need(component['cost'] == (None if amount is None else money(amount)), label + ': component cost')


def run(binary, output, readback=False):
    suite = cases(); need(len({c[0] for c in suite}) == len(suite), 'unique cases')
    identity = {'binary_sha256': digest(binary.read_bytes()), 'script_sha256': digest(Path(__file__).read_bytes())}
    if readback:
        report = decode((output / 'report.json').read_bytes())
        need(report['identity'] == identity and report['cases'] == len(suite) and report['failed'] == 0, 'report identity/count')
        rows = report['records']; need(len(rows) == len(suite), 'row count')
    else:
        output.mkdir(parents=True, exist_ok=False); (output / 'raw').mkdir(); rows = []
    with tempfile.TemporaryDirectory(prefix='n48h-history-') as temp:
        home = Path(temp); (home / 'sentinel').write_bytes(b'KEEP')
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(('QBRAIN', 'OPENAI', 'ANTHROPIC', 'GH_TOKEN', 'GITHUB_TOKEN'))}
        env.update(HOME=temp, USERPROFILE=temp, LOCALAPPDATA=temp, APPDATA=temp)
        for index, case in enumerate(suite):
            request = encode(case[1]); stem = output / 'raw' / f'{index:04d}'
            if readback:
                need(Path(str(stem) + '.stdin').read_bytes() == request, 'deterministic input')
                stdout, stderr = [Path(str(stem) + '.' + suffix).read_bytes() for suffix in ('stdout', 'stderr')]
                code = rows[index]['exit']
                need(type(code) is int and rows[index]['label'] == case[0], 'row identity')
            else:
                process = subprocess.run([str(binary), 'cost', 'import-stream'], input=request, capture_output=True, env=env, cwd=home, timeout=10)
                stdout, stderr, code = process.stdout, process.stderr, process.returncode
                for suffix, data in (('stdin', request), ('stdout', stdout), ('stderr', stderr)):
                    Path(str(stem) + '.' + suffix).write_bytes(data)
                rows.append({'label': case[0], 'exit': code, 'hashes': [digest(v) for v in (request, stdout, stderr)]})
            need(rows[index]['hashes'] == [digest(v) for v in (request, stdout, stderr)], 'raw identity')
            check_result(case, code, stdout, stderr)
        need(sorted(p.name for p in home.iterdir()) == ['sentinel'] and (home / 'sentinel').read_bytes() == b'KEEP', 'brain-free run')
    result = {'schema': 'qbrain-n48h-history-review-v1', 'identity': identity, 'cases': len(suite), 'failed': 0,
              'accepted': sum(c[3] is None for c in suite), 'rejected': sum(c[3] is not None for c in suite),
              'oracle': 'independent_frames_and_Fraction', 'platform': os.name, 'records': rows}
    if not readback:
        (output / 'report.json').write_bytes(encode(result) + b'\n')
    return {k: v for k, v in result.items() if k != 'records'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--readback', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(args.binary.resolve(strict=True), args.output, args.readback), sort_keys=True))
