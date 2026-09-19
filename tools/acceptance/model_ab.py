"""N47S: offline plan -> explicit HTTP execution -> offline scoring.

Chat Completions wire format only. The execution process takes NO answer-key
argument. It has no redirects, retries, tools, sessions or implicit proxies.
Provider/model and invoice authenticity are not certified by local receipts.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import ssl
import sys
import time
from urllib.parse import urlsplit

import memory_task_contract as c
from run_memory_tasks import CONTEXT_PREFIX, parse_context

MODES = ('with-context', 'without-context')
COUNT = 2 * len(c.CASES)
CONTEXT_PROJECTION = 'opaque-session-ids-v1'
RESPONSE_CAP = 1024 * 1024
PROMPT = c.INSTRUCTIONS + ' 返回一个JSON对象，不要Markdown。case_id必须原样返回给定的不透明任务编号。'


def endpoint(value: str, test: bool) -> tuple[str, str, int, str]:
    c.require(isinstance(value, str) and value.isascii() and len(value) <= 512
              and all(33 <= ord(ch) < 127 for ch in value) and not re.search(r'[\\%]', value), 'invalid_endpoint')
    u = urlsplit(value)
    c.require(u.username is None and u.password is None and not u.query and not u.fragment
              and bool(u.hostname) and u.path.endswith('/chat/completions'), 'invalid_endpoint')
    if test:
        c.require(u.scheme == 'http' and u.hostname in ('127.0.0.1', '::1'), 'test_requires_numeric_loopback')
    else:
        c.require(u.scheme == 'https', 'https_required')
    port = u.port if u.port is not None else (443 if u.scheme == 'https' else 80)
    c.require(1 <= port <= 65535, 'invalid_port')
    return u.scheme, u.hostname, port, u.path


def schedule(plan_id: str) -> list[dict]:
    # Each pair is adjacent; pair order and condition order are randomized.
    order = sorted(c.CASE_IDS, key=lambda x: c.digest((plan_id + x).encode()))
    rows = []
    for cid in order:
        modes = MODES if int(c.digest((cid + plan_id).encode())[-1], 16) % 2 else MODES[::-1]
        for mode in modes:
            opaque = c.digest((plan_id + '/' + cid + '/' + mode).encode())[:32]
            rows.append({'case_id': cid, 'mode': mode, 'request_id': opaque})
    return rows


def projected_context(text: str, plan_id: str) -> str:
    """Hide synthetic session labels without editing quotes or evidence IDs.

    The original packet remains byte-exact in the plan. This model-facing
    metadata projection is explicit and versioned, not raw Hook-byte replay.
    """
    if not text:
        return ''
    _, payload = parse_context({'hookSpecificOutput': {
        'hookEventName': 'SessionStart', 'additionalContext': text}})

    def project(value):
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                if key == 'session_id':
                    c.require(isinstance(item, str) and 0 < len(item) <= 256, 'invalid_session_metadata')
                    result[key] = 'session-' + c.digest((plan_id + '\0' + item).encode())[:32]
                else:
                    result[key] = project(item)
            return result
        if isinstance(value, list):
            return [project(item) for item in value]
        return value

    return CONTEXT_PREFIX + c.encode(project(payload)).decode('utf-8')


def validate_plan(p: dict) -> dict[str, dict]:
    fields = {'schema', 'plan_id', 'run_id', 'endpoint', 'loopback_test', 'model',
              'max_completion_tokens', 'token_field', 'timeout_seconds', 'packet_text', 'rows', 'context_projection'}
    c.require(isinstance(p, dict) and set(p) == fields and p['schema'] == 'qbrain-model-plan-v2', 'plan_shape')
    for field in ('plan_id', 'run_id'):
        c.require(isinstance(p[field], str) and re.fullmatch('[0-9a-f]{32}', p[field]) is not None, 'plan_id')
    c.require(p['context_projection'] == CONTEXT_PROJECTION, 'context_projection')
    c.require(type(p['loopback_test']) is bool, 'transport_type')
    endpoint(p['endpoint'], p['loopback_test'])
    c.require(isinstance(p['model'], str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}', p['model']), 'model_id')
    c.require(type(p['max_completion_tokens']) is int and 128 <= p['max_completion_tokens'] <= 4096, 'token_limit')
    c.require(p['token_field'] in ('max_completion_tokens', 'max_tokens'), 'token_field')
    c.require(type(p['timeout_seconds']) is int and 1 <= p['timeout_seconds'] <= 120, 'timeout_limit')
    c.require(p['rows'] == schedule(p['plan_id']), 'request_schedule')
    c.require(isinstance(p['packet_text'], dict) and set(p['packet_text']) == set(MODES), 'packet_modes')
    packets = {}
    for mode in MODES:
        c.require(isinstance(p['packet_text'][mode], str), 'packet_text')
        raw = p['packet_text'][mode].encode('utf-8')
        packets[mode] = c.decode(raw)
        c.validate_packet(packets[mode], mode, p['run_id'])
        for task in packets[mode]['tasks']:
            projected_context(task['context'], p['plan_id'])
    return packets


def prepare(directory: Path, url: str, model: str, *, test=False, tokens=512,
            token_field='max_completion_tokens', timeout=60) -> dict:
    key = c.decode(c.read(directory / 'evaluator-key.DO-NOT-SEND-TO-MODEL.json'))
    texts = {}
    for mode in MODES:
        raw = c.read(directory / (mode + '.json'))
        texts[mode] = raw.decode('utf-8')
        template = {'schema': 'qbrain-memory-task-answers-v1', 'run_id': key['run_id'],
                    'packet_sha256': c.digest(raw), 'answers': [], 'usage': None}
        c.score(key, raw, template)  # all original binding/coverage checks, offline
    p = {'schema': 'qbrain-model-plan-v2', 'context_projection': CONTEXT_PROJECTION,
         'plan_id': secrets.token_hex(16), 'run_id': key['run_id'],
         'endpoint': url, 'loopback_test': test, 'model': model, 'max_completion_tokens': tokens,
         'token_field': token_field, 'timeout_seconds': timeout, 'packet_text': texts}
    p['rows'] = schedule(p['plan_id'])
    validate_plan(p)
    return p


def request_body(p: dict, packets: dict, row: dict) -> bytes:
    task = next(x for x in packets[row['mode']]['tasks'] if x['case_id'] == row['case_id'])
    blind_task = {**task, 'case_id': row['request_id'],
                  'context': projected_context(task['context'], p['plan_id'])}
    return c.encode({'model': p['model'], 'messages': [{'role': 'system', 'content': PROMPT},
                     {'role': 'user', 'content': c.encode(blind_task).decode()}],
                     'response_format': {'type': 'json_object'}, 'stream': False, 'store': False,
                     p['token_field']: p['max_completion_tokens']})


class TransferError(Exception):
    pass


def post(p: dict, body: bytes, key: str) -> tuple[int, bytes]:
    scheme, host, port, path = endpoint(p['endpoint'], p['loopback_test'])
    # http.client does not follow redirects or use env/OS proxy discovery.
    cls = http.client.HTTPSConnection if scheme == 'https' else http.client.HTTPConnection
    kwargs = {'timeout': p['timeout_seconds']}
    if scheme == 'https':
        kwargs['context'] = ssl.create_default_context()
    conn = cls(host, port, **kwargs)
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'Accept-Encoding': 'identity'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    deadline = time.monotonic() + p['timeout_seconds']
    try:
        conn.request('POST', path, body=body, headers=headers)
        response = conn.getresponse()
        if response.status != 200:
            # Do not persist/log arbitrary provider error text (may contain secrets).
            return response.status, b''
        if response.getheader('Content-Encoding', 'identity').lower() != 'identity':
            raise TransferError('encoded_response_rejected')
        headers_received = response.getheaders()
        lengths = [val for name, val in headers_received if name.lower() == 'content-length']
        transfers = [val for name, val in headers_received if name.lower() == 'transfer-encoding']
        if len(lengths) > 1 or len(transfers) > 1:
            raise TransferError('duplicate_message_framing')
        length = lengths[0] if lengths else None
        expected_length = None
        if length is not None:
            if re.fullmatch(r'[0-9]{1,10}', length) is None or int(length) > RESPONSE_CAP:
                raise TransferError('invalid_content_length')
            expected_length = int(length)
        transfer = transfers[0] if transfers else None
        if transfer is not None and (transfer.lower() != 'chunked' or length is not None):
            raise TransferError('ambiguous_transfer_framing')
        parts, total = [], 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransferError('response_timeout')
            if conn.sock is not None:
                conn.sock.settimeout(remaining)
            chunk = response.read1(min(65536, RESPONSE_CAP + 1 - total))
            if not chunk:
                break
            parts.append(chunk); total += len(chunk)
            if total > RESPONSE_CAP:
                raise TransferError('response_too_large')
        if expected_length is not None and total != expected_length:
            raise TransferError('incomplete_response_body')
        return response.status, b''.join(parts)
    except (OSError, http.client.HTTPException) as error:
        raise TransferError('network_error') from error
    finally:
        conn.close()


def safe_response(raw: bytes, key: str) -> tuple[bytes, str | None]:
    # Invalid JSON is represented by hash/size only; avoid persisting secrets in
    # malformed or unicode-escaped error bodies. Valid no-secret bytes stay exact.
    try:
        value = c.decode(raw)
        canonical = c.encode(value)
    except (ValueError, TypeError, UnicodeError):
        return b'', 'invalid_json'
    if key and key.encode() in canonical:
        return canonical.replace(key.encode(), b'[REDACTED]'), 'credential_echo'
    return raw, None


def parse_response(raw: bytes, row: dict) -> tuple[dict, dict]:
    value = c.decode(raw)
    c.require(isinstance(value, dict) and isinstance(value.get('model'), str)
              and 0 < len(value['model']) <= 256 and isinstance(value.get('id'), str)
              and 0 < len(value['id']) <= 256, 'response_identity')
    choices = value.get('choices')
    c.require(isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict), 'response_choices')
    choice = choices[0]; message = choice.get('message')
    c.require(choice.get('finish_reason') == 'stop' and isinstance(message, dict)
              and message.get('role') == 'assistant' and not message.get('tool_calls')
              and not message.get('function_call') and not message.get('refusal')
              and isinstance(message.get('content'), str), 'response_incomplete_or_refused')
    answer = c.decode(message['content'].encode())
    c.require(isinstance(answer, dict) and answer.get('case_id') == row['request_id'], 'answer_request_id')
    answer = {**answer, 'case_id': row['case_id']}
    c.answer(answer)
    usage = value.get('usage')
    counts = None
    if usage is not None:
        c.require(isinstance(usage, dict), 'usage_shape')
        for field in ('prompt_tokens', 'completion_tokens'):
            c.require(type(usage.get(field)) is int and 0 <= usage[field] <= 10**12, 'usage_value')
        if 'total_tokens' in usage:
            c.require(type(usage['total_tokens']) is int
                      and usage['total_tokens'] == usage['prompt_tokens'] + usage['completion_tokens'], 'usage_total')
        counts = {'input_tokens': usage['prompt_tokens'], 'output_tokens': usage['completion_tokens']}
    return answer, {'response_id': value['id'], 'reported_model': value['model'], 'usage': counts}


def run(plan_raw: bytes, output: Path, *, approved_sha: str, approved_endpoint: str,
        request_cap: int, key_env: str | None = None) -> dict:
    c.require(c.digest(plan_raw) == approved_sha, 'plan_digest_not_approved')
    p = c.decode(plan_raw); packets = validate_plan(p)
    c.require(approved_endpoint == p['endpoint'], 'endpoint_not_approved')
    c.require(type(request_cap) is int and request_cap == COUNT, 'approve_exact_request_count')
    key = ''
    if p['loopback_test']:
        c.require(key_env is None, 'test_transport_has_no_credentials')
    else:
        c.require(isinstance(key_env, str) and re.fullmatch('[A-Z][A-Z0-9_]{0,63}', key_env), 'key_env_required')
        key = os.environ.get(key_env, '')
        c.require(re.fullmatch(r'[A-Za-z0-9._~+/=-]{12,512}', key) is not None, 'credential_missing_or_invalid')
        c.require(key.encode() not in c.encode(p), 'credential_in_plan')
    bodies = [request_body(p, packets, row) for row in p['rows']]
    c.require(all(len(body) <= 65536 and (not key or key.encode() not in body) for body in bodies),
              'request_too_large_or_credential_in_body')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'plan.json').write_bytes(plan_raw)
    result = {'schema': 'qbrain-model-run-v1', 'plan_sha256': approved_sha,
              'execution_kind': 'LOOPBACK_TEST' if p['loopback_test'] else 'PROVIDER_ENDPOINT_RUN',
              'rows': [], 'result': 'INCOMPLETE', 'planned': COUNT, 'attempted': 0,
              'completed': 0, 'host_consumption_verified': False, 'provider_provenance_verified': False}
    stopped = False
    for i, row in enumerate(p['rows'], 1):
        record = {'index': i, **row, 'status': 'not_attempted'}
        result['rows'].append(record)
        if stopped:
            continue
        body = bodies[i - 1]
        folder = output / f'{i:03}'; folder.mkdir()
        (folder / 'request.json').write_bytes(body)
        record.update(status='started', request_sha256=c.digest(body))
        result['attempted'] += 1
        c.write_new(folder / 'started.json', {'plan_sha256': approved_sha, **record})
        start = time.monotonic()
        try:
            status, raw = post(p, body, key)
            record['http_status'] = status
            record['response_received_bytes'] = len(raw)
            record['response_received_sha256'] = c.digest(raw)
            safe, error = safe_response(raw, key) if status == 200 else (b'', 'http_error')
            record['response_saved_sha256'] = c.digest(safe)
            (folder / 'response.bin').write_bytes(safe)
            if error:
                record['status'] = error
            else:
                _, details = parse_response(safe, row)
                c.require(details['usage'] is None or details['usage']['output_tokens'] <= p['max_completion_tokens'],
                          'provider_exceeded_requested_output_cap')
                record.update(status='completed', **details)
                result['completed'] += 1
        except TransferError as error:
            record.update(status='transport_error', error_code=str(error))
        except (ValueError, TypeError, KeyError, UnicodeError):
            record['status'] = 'invalid_response'
        except KeyboardInterrupt:
            record['status'] = 'interrupted'
        record['elapsed_ms'] = round((time.monotonic() - start) * 1000, 3)
        c.write_new(folder / 'receipt.json', record)
        stopped = record['status'] != 'completed'
    if result['completed'] == COUNT:
        result['result'] = 'CALLS_COMPLETE'
    c.write_new(output / 'run.json', result)
    return result


def score_run(directory: Path, key_path: Path) -> dict:
    plan_raw = c.read(directory / 'plan.json'); p = c.decode(plan_raw)
    packets = validate_plan(p)
    report = c.decode(c.read(directory / 'run.json'))
    c.require(isinstance(report, dict) and report.get('schema') == 'qbrain-model-run-v1' and report.get('plan_sha256') == c.digest(plan_raw), 'run_binding')
    kind = 'LOOPBACK_TEST' if p['loopback_test'] else 'PROVIDER_ENDPOINT_RUN'
    c.require(report.get('execution_kind') == kind and report.get('planned') == COUNT
              and isinstance(report.get('rows'), list) and len(report['rows']) == COUNT, 'run_shape')
    answers = {mode: [] for mode in MODES}
    usages = {mode: [] for mode in MODES}; models = set()
    attempted = complete = 0; stopped = False
    for i, (expected, row) in enumerate(zip(p['rows'], report['rows']), 1):
        c.require(isinstance(row, dict) and type(row.get('index')) is int and row['index'] == i
                  and all(row.get(k) == val for k, val in expected.items()), 'receipt_order')
        if row.get('status') == 'not_attempted':
            c.require(stopped, 'unexpected_skipped_call')
            c.require(not (directory / f'{i:03}').exists(), 'skipped_call_has_files')
            continue
        c.require(not stopped, 'continued_after_failure')
        attempted += 1; folder = directory / f'{i:03}'
        c.require(c.decode(c.read(folder / 'receipt.json')) == row, 'receipt_changed')
        body = request_body(p, packets, expected)
        c.require(c.read(folder / 'request.json') == body and row['request_sha256'] == c.digest(body), 'request_changed')
        started = c.decode(c.read(folder / 'started.json'))
        c.require(started == {'plan_sha256': c.digest(plan_raw), 'index': i, **expected,
                              'status': 'started', 'request_sha256': c.digest(body)}, 'started_receipt')
        if row.get('status') != 'completed':
            c.require(row.get('status') in ('transport_error', 'invalid_response', 'credential_echo',
                      'invalid_json', 'http_error', 'interrupted'), 'unknown_failure')
            stopped = True
            continue
        raw = c.read(folder / 'response.bin')
        c.require(type(row.get('http_status')) is int and row['http_status'] == 200
                  and row.get('response_saved_sha256') == row.get('response_received_sha256') == c.digest(raw)
                  and row.get('response_received_bytes') == len(raw), 'response_changed')
        answer, detail = parse_response(raw, expected)
        c.require(detail['usage'] is None or detail['usage']['output_tokens'] <= p['max_completion_tokens'], 'provider_token_cap')
        c.require(all(row.get(k) == val for k, val in detail.items()), 'parsed_response_changed')
        answers[row['mode']].append(answer); usages[row['mode']].append(detail['usage'])
        models.add(detail['reported_model']); complete += 1
    c.require(type(report.get('attempted')) is int and report['attempted'] == attempted
              and type(report.get('completed')) is int and report['completed'] == complete
              and report.get('result') == ('CALLS_COMPLETE' if complete == COUNT else 'INCOMPLETE'), 'run_counts')
    key = c.decode(c.read(key_path))  # only offline scoring receives the answer key
    scores = {}
    for mode in MODES:
        raw = p['packet_text'][mode].encode()
        submitted = {'schema': 'qbrain-memory-task-answers-v1', 'run_id': p['run_id'],
                     'packet_sha256': c.digest(raw), 'answers': answers[mode], 'usage': None}
        scores[mode] = c.score(key, raw, submitted)
    usage_totals = {}
    for mode, values in usages.items():
        known = [x for x in values if x is not None]
        usage_totals[mode] = {'requests_with_usage': len(known),
            'input_tokens': sum(x['input_tokens'] for x in known) if len(known) == len(c.CASES) else None,
            'output_tokens': sum(x['output_tokens'] for x in known) if len(known) == len(c.CASES) else None,
            'cost_usd': None, 'billing_verified': False}
    comparable = complete == COUNT and len(models) == 1
    return {'schema': 'qbrain-model-comparison-v1', 'execution_kind': kind,
            'plan_sha256': c.digest(plan_raw), 'attempted': attempted, 'completed': complete,
            'complete_pair': complete == COUNT, 'same_reported_model': len(models) == 1,
            'reported_models': sorted(models), 'scores': scores, 'provider_reported_usage': usage_totals,
            'answerable_resolution_delta': scores[MODES[0]]['answerable_resolution']['rate'] - scores[MODES[1]]['answerable_resolution']['rate'] if comparable else None,
            'host_consumption_verified': False, 'provider_provenance_verified': False,
            'limits': ['API task answers, not automatic client Hook consumption',
                       'Loopback fixtures are not model results', 'Caller-selected endpoint/model and unsigned local receipts',
                       'Request/token caps are not dollar budgets; failed requests may be billed',
                       'Stateless request bodies cannot certify remote retention or session isolation']}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prepare_p = sub.add_parser('prepare')
    prepare_p.add_argument('--directory', type=Path, required=True)
    prepare_p.add_argument('--endpoint', required=True); prepare_p.add_argument('--model', required=True)
    prepare_p.add_argument('--output', type=Path, required=True)
    prepare_p.add_argument('--loopback-test', action='store_true')
    prepare_p.add_argument('--max-completion-tokens', type=int, default=512)
    prepare_p.add_argument('--token-field', choices=('max_completion_tokens', 'max_tokens'), default='max_completion_tokens')
    prepare_p.add_argument('--timeout', type=int, default=60)
    run_p = sub.add_parser('execute')
    run_p.add_argument('--plan', type=Path, required=True); run_p.add_argument('--approve-sha256', required=True)
    run_p.add_argument('--approve-endpoint', required=True); run_p.add_argument('--approve-requests', type=int, required=True)
    run_p.add_argument('--key-env'); run_p.add_argument('--output', type=Path, required=True)
    score_p = sub.add_parser('score')
    score_p.add_argument('--run', type=Path, required=True); score_p.add_argument('--key', type=Path, required=True)
    score_p.add_argument('--output', type=Path, required=True)
    a = parser.parse_args()
    try:
        if a.command == 'prepare':
            p = prepare(a.directory, a.endpoint, a.model, test=a.loopback_test, tokens=a.max_completion_tokens,
                        token_field=a.token_field, timeout=a.timeout)
            c.write_new(a.output, p)
            print(json.dumps({'result': 'OFFLINE_PLAN', 'requests': COUNT, 'plan_sha256': c.digest(c.encode(p)),
                              'output_token_setting_sum': COUNT * a.max_completion_tokens, 'cost_usd': None}))
            return 0
        if a.command == 'execute':
            r = run(c.read(a.plan), a.output, approved_sha=a.approve_sha256, approved_endpoint=a.approve_endpoint,
                    request_cap=a.approve_requests, key_env=a.key_env)
            print(json.dumps({k: r[k] for k in ('result', 'execution_kind', 'attempted', 'completed')}))
            return 0 if r['completed'] == COUNT else 1
        r = score_run(a.run, a.key); c.write_new(a.output, r)
        print(json.dumps({k: r[k] for k in ('execution_kind', 'complete_pair', 'completed', 'answerable_resolution_delta')}))
        return 0 if r['complete_pair'] else 1
    except (ValueError, OSError, TypeError, KeyError, UnicodeError):
        print('REJECTED: invalid input/authorization or output not new. No automatic retry.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
