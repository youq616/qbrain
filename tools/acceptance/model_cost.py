"""N48J: offline N47S execution receipts -> native token costs and paired report.

Explicit scope is scheduled MAIN requests only, not all pipeline costs. No HTTP
execution, answer key, credential access or price guessing. Original source is
read-only; export requires a new output directory and verify recomputes results.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

import model_ab as m
import memory_task_contract as c
import run_memory_tasks

SCOPE = 'scheduled_main_requests_only'
CAP = 8 * 1024 * 1024
TOTAL_CAP = 128 * 1024 * 1024
FAILED = {'transport_error', 'invalid_response', 'credential_echo', 'invalid_json', 'http_error', 'interrupted'}
BASE = {'index', 'case_id', 'mode', 'request_id', 'status'}
RECEIVED = {'http_status', 'response_received_bytes', 'response_received_sha256', 'response_saved_sha256'}
DETAILS = {'response_id', 'reported_model', 'usage'}
RUN_FIELDS = {'schema', 'plan_sha256', 'execution_kind', 'rows', 'result', 'planned', 'attempted', 'completed',
              'host_consumption_verified', 'provider_provenance_verified'}


class Reject(ValueError):
    """Stable, body/path-free input failure."""


def need(ok: bool, code: str) -> None:
    if not ok:
        raise Reject(code)


def encode(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def same(a, b) -> bool:
    return encode(a) == encode(b)  # do not alias bool with int


def decode(raw: bytes, cap: int = CAP):
    need(len(raw) <= cap, 'model_cost_file_limit')
    def unique(pairs):
        result = {}
        for k, v in pairs:
            need(k not in result, 'model_cost_duplicate_key')
            result[k] = v
        return result
    def invalid(_):
        raise Reject('model_cost_invalid_json')
    try:
        value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique, parse_constant=invalid)
        pending = [(value, 0)]
        while pending:
            item, depth = pending.pop()
            need(depth <= 48, 'model_cost_json_depth')
            if isinstance(item, dict):
                for k, v in item.items():
                    k.encode('utf-8')
                    pending.append((v, depth + 1))
            elif isinstance(item, list):
                pending.extend((v, depth + 1) for v in item)
            elif isinstance(item, str):
                item.encode('utf-8')
            elif isinstance(item, float):
                need(math.isfinite(item), 'model_cost_invalid_json')
        return value
    except (UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise Reject('model_cost_invalid_json') from exc


def shape(value, keys, code='model_cost_fields'):
    need(isinstance(value, dict) and set(value) == set(keys), code)


def digest(value) -> bool:
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def safe_path(path: Path, directory=False) -> Path:
    path = Path(os.path.abspath(path))
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not (getattr(info, 'st_file_attributes', 0) & 0x400), 'model_cost_link_input')
    info = path.stat()
    need(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode), 'model_cost_input_type')
    return path


def read(path: Path, cap: int) -> bytes:
    safe_path(path)
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_size <= cap, 'model_cost_file_limit')
        raw = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
    need(len(raw) <= cap and len(raw) == before.st_size and
         (before.st_size, before.st_mtime_ns, before.st_ino) == (after.st_size, after.st_mtime_ns, after.st_ino),
         'model_cost_source_changed')
    return raw


class Snapshot:
    def __init__(self, root: Path):
        self.root = safe_path(root, True)
        self.files: dict[str, bytes] = {}
        self.directories: dict[str, list[str]] = {}
        self.total = 0

    def directory(self, relative: str, expected):
        folder = safe_path(self.root / relative, True)
        names = sorted(p.name for p in folder.iterdir())
        need(names == sorted(expected), 'model_cost_file_inventory')
        self.directories[relative] = names

    def take(self, relative: str, cap: int):
        # All relative names are constructed in this module, not read from JSON.
        raw = read(self.root / relative, cap)
        self.total += len(raw)
        need(self.total <= TOTAL_CAP, 'model_cost_run_limit')
        self.files[relative] = raw
        return raw

    def recheck(self):
        for relative, expected in self.directories.items():
            self.directory(relative, expected)
        for relative, original in self.files.items():
            need(read(self.root / relative, len(original)) == original, 'model_cost_source_changed')

    def manifest(self):
        return {name: {'bytes': len(raw), 'sha256': sha(raw)} for name, raw in sorted(self.files.items())}


def validate_run(snapshot: Snapshot):
    plan_raw = snapshot.take('plan.json', CAP)
    plan = decode(plan_raw)
    packets = m.validate_plan(plan)
    run = decode(snapshot.take('run.json', 1048576), 1048576)
    shape(run, RUN_FIELDS)
    kind = 'LOOPBACK_TEST' if plan['loopback_test'] else 'PROVIDER_ENDPOINT_RUN'
    need(run['schema'] == 'qbrain-model-run-v1' and run['plan_sha256'] == sha(plan_raw), 'model_cost_run_binding')
    need(run['execution_kind'] == kind and type(run['planned']) is int and run['planned'] == m.COUNT,
         'model_cost_run_shape')
    need(run['host_consumption_verified'] is False and run['provider_provenance_verified'] is False, 'model_cost_scope_flag')
    need(isinstance(run['rows'], list) and len(run['rows']) == m.COUNT, 'model_cost_run_shape')
    attempted = completed = 0
    stopped = False
    responses = []
    root_names = ['plan.json', 'run.json']
    seen_responses = set()
    for index, (expected, row) in enumerate(zip(plan['rows'], run['rows']), 1):
        need(isinstance(row, dict) and type(row.get('index')) is int and row['index'] == index and
             all(same(row.get(k), v) for k, v in expected.items()), 'model_cost_row_order')
        status = row.get('status')
        need(isinstance(status, str), 'model_cost_row_status')
        if status == 'not_attempted':
            shape(row, BASE)
            need(stopped, 'model_cost_unexpected_skipped')
            responses.append(None)
            continue
        need(not stopped and status in FAILED | {'completed'}, 'model_cost_row_status')
        attempted += 1
        stopped = status != 'completed'
        required = BASE | {'request_sha256', 'elapsed_ms'}
        allowed = required | RECEIVED | (DETAILS if status == 'completed' else set()) | ({'error_code'} if status == 'transport_error' else set())
        need(required <= set(row) <= allowed and digest(row['request_sha256']), 'model_cost_receipt_fields')
        need(type(row['elapsed_ms']) in (float, int) and math.isfinite(row['elapsed_ms']) and row['elapsed_ms'] >= 0,
             'model_cost_elapsed')
        prefix = f'{index:03d}/'
        root_names.append(prefix[:-1])
        need(same(decode(snapshot.take(prefix + 'receipt.json', 65536)), row), 'model_cost_receipt_changed')
        body = m.request_body(plan, packets, expected)
        need(snapshot.take(prefix + 'request.json', 65536) == body and row['request_sha256'] == sha(body), 'model_cost_request_changed')
        started = decode(snapshot.take(prefix + 'started.json', 65536))
        need(same(started, {'plan_sha256': sha(plan_raw), 'index': index, **expected, 'status': 'started',
                            'request_sha256': sha(body)}), 'model_cost_started_changed')
        files = ['receipt.json', 'request.json', 'started.json']
        raw = None
        received = RECEIVED & set(row)
        if received:
            need('http_status' in row and type(row['http_status']) is int and 100 <= row['http_status'] <= 599,
                 'model_cost_response_metadata')
            need('response_received_bytes' in row and type(row['response_received_bytes']) is int and
                 0 <= row['response_received_bytes'] <= m.RESPONSE_CAP and digest(row.get('response_received_sha256')),
                 'model_cost_response_metadata')
            if 'response_saved_sha256' in row:
                need(digest(row['response_saved_sha256']), 'model_cost_response_metadata')
                raw = snapshot.take(prefix + 'response.bin', m.RESPONSE_CAP)
                files.append('response.bin')
                need(sha(raw) == row['response_saved_sha256'], 'model_cost_response_changed')
            else:
                need(status == 'interrupted', 'model_cost_response_metadata')
        snapshot.directory(prefix[:-1], files)
        if status == 'completed':
            shape(row, required | RECEIVED | DETAILS)
        if status in {'completed', 'invalid_response'} and raw is not None:
            need(row['http_status'] == 200 and sha(raw) == row['response_received_sha256'] and
                 len(raw) == row['response_received_bytes'], 'model_cost_response_changed')
            value = decode(raw, m.RESPONSE_CAP)
            if status == 'completed':
                _, detail = m.parse_response(raw, expected)
                need(all(same(row[k], v) for k, v in detail.items()) and
                     (detail['usage'] is None or detail['usage']['output_tokens'] <= plan['max_completion_tokens']),
                     'model_cost_response_details')
                completed += 1
            terminal = (isinstance(value, dict) and value.get('object') == 'chat.completion' and
                       isinstance(value.get('choices'), list) and bool(value['choices']) and
                       all(isinstance(item, dict) and isinstance(item.get('finish_reason'), str) and
                           bool(item['finish_reason']) for item in value['choices']))
            need(status != 'completed' or terminal, 'model_cost_unsupported_response')
            if terminal:
                need(isinstance(value.get('id'), str) and isinstance(value.get('model'), str), 'model_cost_response_identity')
                identity = value['id']
                need(identity not in seen_responses, 'model_cost_duplicate_response')
                seen_responses.add(identity)
                # Projection is explicit; body is neither required by N48G nor exported.
                responses.append({'id': identity, 'model': value['model'], 'object': value['object'],
                                  'choices': [{'finish_reason': item['finish_reason']} for item in value['choices']],
                                  **({'usage': value['usage']} if 'usage' in value else {})})
                continue
        elif status == 'completed':
            raise Reject('model_cost_response_missing')
        elif status in {'invalid_json', 'credential_echo', 'http_error'}:
            need(received == RECEIVED and raw is not None, 'model_cost_response_metadata')
            if status == 'http_error':
                need(row['http_status'] != 200 and raw == b'' and row['response_received_bytes'] == 0 and
                     row['response_received_sha256'] == sha(b''), 'model_cost_http_error')
            elif status == 'invalid_json':
                need(row['http_status'] == 200 and raw == b'', 'model_cost_redaction')
            else:
                need(row['http_status'] == 200, 'model_cost_redaction')
        elif status == 'transport_error':
            need(not received and row.get('error_code') in {'network_error', 'encoded_response_rejected',
                 'duplicate_message_framing', 'invalid_content_length', 'ambiguous_transfer_framing',
                 'response_timeout', 'response_too_large', 'incomplete_response_body'}, 'model_cost_transport_error')
        responses.append(None)  # observed failed attempt; never a guessed zero
    snapshot.directory('', root_names)
    need(type(run['attempted']) is int and type(run['completed']) is int and
         run['attempted'] == attempted and run['completed'] == completed and
         run['result'] == ('CALLS_COMPLETE' if completed == m.COUNT else 'INCOMPLETE'), 'model_cost_run_counts')
    return plan, packets, run, responses


class Native:
    def __init__(self, binary: Path):
        self.binary = safe_path(binary)
        self.identity = sha(read(self.binary, 128 * 1024 * 1024))
        self.calls = 0

    def invoke(self, action: str, value):
        raw = encode(value)
        limit = 262144 if action == 'report' else 1048576
        need(len(raw) <= limit, 'model_cost_native_input_limit')
        # No shell, credentials or network executor. Explicit trusted qbrain only.
        env = {k: os.environ[k] for k in os.environ if not k.upper().startswith(('QBRAIN', 'OPENAI', 'ANTHROPIC', 'GH_TOKEN', 'GITHUB_TOKEN'))}
        with tempfile.TemporaryDirectory(prefix='qbrain-model-cost-') as home:
            env.update(HOME=home, USERPROFILE=home, APPDATA=home, LOCALAPPDATA=home)
            with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
                p = subprocess.run([str(self.binary), 'cost', action], input=raw, stdout=stdout, stderr=stderr,
                                   env=env, cwd=home, timeout=60)
                need(stdout.tell() <= CAP and stderr.tell() == 0, 'model_cost_native_output')
                stdout.seek(0); result = decode(stdout.read(CAP + 1))
            need(not list(Path(home).iterdir()), 'model_cost_native_home_changed')
        self.calls += 1
        if p.returncode != 0:
            code = result.get('error', {}).get('code') if isinstance(result, dict) else None
            need(isinstance(code, str) and re.fullmatch('[a-z_]{1,80}', code), 'model_cost_native_failure')
            raise Reject('model_cost_native_' + code)
        return result

    def recheck(self):
        need(sha(read(self.binary, 128 * 1024 * 1024)) == self.identity, 'model_cost_binary_changed')


def analyze(run_dir: Path, rates_path: Path, binary: Path):
    snapshot = Snapshot(run_dir)
    plan, packets, run, responses = validate_run(snapshot)
    rates_path = safe_path(rates_path)
    rates_raw = read(rates_path, 262144)
    price = decode(rates_raw, 262144)
    shape(price, {'schema', 'currency', 'scope', 'rates'})
    need(price['schema'] == 'qbrain-model-cost-rates-v1' and price['scope'] == SCOPE, 'model_cost_price_scope')
    native = Native(binary)
    empty = {'schema': 'qbrain-cost-input-v1', 'currency': price['currency'], 'rates': price['rates'], 'calls': []}
    native.invoke('report', empty)  # validate every card using unchanged N48F
    model_rates = {}
    for card in price['rates']:
        need(card['provider'] == 'openai' and not card['rate_id'].startswith('n48j-unpriced-'), 'model_cost_rate_provider')
        need(card['model'] not in model_rates, 'model_cost_ambiguous_rate')
        model_rates[card['model']] = card['rate_id']
    record_groups = {mode: [] for mode in m.MODES}
    observations = []
    for row, response in zip(run['rows'], responses):
        observed = {'index': row['index'], 'task_id': row['case_id'], 'mode': row['mode'], 'status': row['status'],
                    'call_id': None, 'normalization': 'not_attempted'}
        if row['status'] != 'not_attempted':
            model = response['model'] if response is not None else plan['model']
            rid = model_rates.get(model, 'n48j-unpriced-' + sha(model.encode('utf-8'))[:32])
            record_groups[row['mode']].append({'call_id': row['request_id'], 'stage': 'main', 'rate_id': rid,
                'attempt': 1, 'outcome': 'success' if row['status'] == 'completed' else 'failure',
                'format': 'openai_chat', 'response': response})
            observed.update(call_id=row['request_id'], normalization='terminal_response_projection' if response is not None else 'unknown_failed_attempt')
        observations.append(observed)
    ledgers = {}
    for mode, records in record_groups.items():
        ledger = {**empty, 'calls': []}
        batch = []
        def flush():
            if batch:
                imported = native.invoke('import', {'schema': 'qbrain-usage-import-v1', 'currency': price['currency'],
                                                     'rates': price['rates'], 'records': batch})
                ledger['calls'].extend(imported['cost_input']['calls'])
        for record in records:
            candidate = {'schema': 'qbrain-usage-import-v1', 'currency': price['currency'], 'rates': price['rates'], 'records': batch + [record]}
            if batch and len(encode(candidate)) > 1048576:
                flush(); batch = []
            batch.append(record)
        flush()
        ledger['calls'].sort(key=lambda call: call['call_id'])
        ledgers[mode] = {'cost_input': ledger, 'cost_report': native.invoke('report', ledger)}
    # A common task binds the PAIR of source packets, not different request bodies.
    source_binding = {'plan_sha256': sha(snapshot.files['plan.json']), 'scope': SCOPE,
                      'packet_sha256': {mode: sha(plan['packet_text'][mode].encode('utf-8')) for mode in m.MODES}}
    conditions = sha(encode(source_binding))
    comparison_input = comparison = None
    if run['attempted'] == m.COUNT:
        comparison_input = {'schema': 'qbrain-cost-comparison-v1', 'comparison_id': 'model-run-' + plan['plan_id'], 'currency': price['currency']}
        for side, mode in (('baseline', 'without-context'), ('candidate', 'with-context')):
            rows = [row for row in run['rows'] if row['mode'] == mode]
            comparison_input[side] = {'label': mode, 'conditions_sha256': conditions,
                'ledger_complete': all(row['status'] == 'completed' for row in rows), 'cost_input': ledgers[mode]['cost_input'],
                'tasks': [{'task_id': row['case_id'], 'task_sha256': sha(encode({'source': source_binding, 'case_id': row['case_id']})),
                           'call_ids': [row['request_id']]} for row in sorted(rows, key=lambda row: row['case_id'])], 'shared_call_ids': []}
        comparison = native.invoke('compare', comparison_input)
    result = {'schema': 'qbrain-model-cost-report-v1', 'cost_scope': SCOPE,
              'execution_kind': run['execution_kind'], 'run_id': plan['run_id'], 'plan_sha256': sha(snapshot.files['plan.json']),
              'planned_requests': m.COUNT, 'attempted_requests': run['attempted'], 'completed_responses': run['completed'],
              'unattempted_requests': m.COUNT - run['attempted'], 'task_count_per_arm': len(c.CASES),
              'ledgers': ledgers, 'observations': observations, 'comparison': comparison,
              'comparison_unavailable_reason': 'unattempted_planned_requests' if comparison is None else None,
              'source_binding': source_binding, 'source_provenance_authenticated': False, 'billing_verified': False,
              'quality_verified': False, 'host_consumption_verified': False, 'full_pipeline_costs_included': False,
              'all_provider_calls_observed': False, 'provider_requests_sent_by_bridge': 0}
    components = {Path(module.__file__).name: sha(read(Path(module.__file__), CAP)) for module in (m, c, run_memory_tasks)}
    components[Path(__file__).name] = sha(read(Path(__file__), CAP))
    source = {'schema': 'qbrain-model-cost-source-v1', 'files': snapshot.manifest(), 'rates_sha256': sha(rates_raw),
              'binary_sha256': native.identity, 'tool_components': components, 'native_invocations': native.calls,
              'cost_scope': SCOPE, 'source_authenticated': False}
    snapshot.recheck()
    need(read(rates_path, 262144) == rates_raw, 'model_cost_rates_changed')
    native.recheck()
    outputs = {'analysis.json': encode(result), 'comparison-input.json': encode(comparison_input), 'source-manifest.json': encode(source)}
    need(all(len(raw) <= CAP for raw in outputs.values()), 'model_cost_output_limit')
    manifest = {'schema': 'qbrain-model-cost-bundle-v1', 'files': {name: {'bytes': len(raw), 'sha256': sha(raw)} for name, raw in outputs.items()}}
    outputs['MANIFEST.json'] = encode(manifest)
    return result, outputs


def execute(run_dir: Path, rates: Path, binary: Path, output: Path, verify=False):
    source = safe_path(run_dir, True)
    target = Path(os.path.abspath(output))
    safe_path(target.parent, True)
    need(target != source and source not in target.parents, 'model_cost_output_inside_source')
    if not verify:
        need(not target.exists() and not target.is_symlink(), 'model_cost_output_exists')
    result, outputs = analyze(source, rates, binary)
    if verify:
        safe_path(target, True)
        need(sorted(p.name for p in target.iterdir()) == sorted(outputs), 'model_cost_bundle_inventory')
        for name, raw in outputs.items():
            need(read(target / name, CAP) == raw, 'model_cost_bundle_changed')
    else:
        target.mkdir()  # never replace an existing directory; marker is written last
        for name, raw in outputs.items():
            with (target / name).open('xb') as stream:
                stream.write(raw)
    return {'result': 'VERIFIED' if verify else 'EXPORTED', 'cost_scope': SCOPE,
            'attempted_requests': result['attempted_requests'], 'completed_responses': result['completed_responses'],
            'comparison_eligible': bool(result['comparison'] and result['comparison']['comparison_eligible']),
            'execution_kind': result['execution_kind'], 'provider_requests_sent_by_bridge': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('export', 'verify'))
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--rates', type=Path, required=True)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    a = parser.parse_args()
    try:
        print(encode(execute(a.run, a.rates, a.binary, a.output, a.command == 'verify')).decode(), end='')
        return 0
    except Reject as exc:
        print(encode({'error': {'code': str(exc)}}).decode(), end='')
    except (OSError, ValueError, TypeError, KeyError, RecursionError, OverflowError, subprocess.SubprocessError):
        print('{"error":{"code":"model_cost_input_or_local_failure"}}')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
