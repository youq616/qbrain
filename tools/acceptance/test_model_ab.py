"""Native portable HTTP tests. Fixture responses are NOT actual model results."""
import copy
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import memory_task_contract as c
import model_ab as m
from test_memory_tasks import fixture


def response(body, *, usage=True, state='unknown', model='fixture-model'):
    task = c.decode(body['messages'][-1]['content'].encode())
    reply = {'case_id': task['case_id'], 'state': state, 'values': [], 'fact_ids': []}
    data = {'id': 'fixture-response', 'model': model, 'choices': [{'finish_reason': 'stop',
            'message': {'role': 'assistant', 'content': json.dumps(reply)}}]}
    if usage:
        data['usage'] = {'prompt_tokens': 11, 'completion_tokens': 7, 'total_tokens': 18}
    return c.encode(data)


@contextmanager
def server(fault=None):
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            raw = self.rfile.read(int(self.headers['Content-Length']))
            body = c.decode(raw)
            calls.append({'path': self.path, 'body': body, 'auth': self.headers.get('Authorization')})
            status = 302 if fault == 'redirect' else 429 if fault == 'rate_limit' else 200
            self.send_response(status)
            if fault == 'redirect': self.send_header('Location', '/followed')
            self.send_header('Content-Type', 'application/json')
            if fault == 'encoding': self.send_header('Content-Encoding', 'gzip')
            if fault == 'malformed': data = b'not json'
            elif fault == 'large': data = b' ' * (m.RESPONSE_CAP + 1)
            elif fault == 'truncated':
                value = c.decode(response(body)); value['choices'][0]['finish_reason'] = 'length'; data = c.encode(value)
            else: data = response(body, usage=fault != 'missing_usage', model='fixture-'+str(len(calls) % 2) if fault == 'drift' else 'fixture-model')
            self.send_header('Content-Length', str(len(data))); self.end_headers()
            try: self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError): pass
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True); thread.start()
    try: yield f'http://127.0.0.1:{httpd.server_port}/v1/chat/completions', calls
    finally: httpd.shutdown(); httpd.server_close(); thread.join(timeout=5)


class Setup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.inputs = self.root / 'input'; self.inputs.mkdir()
        key = None
        for mode in m.MODES:
            k, raw, _ = fixture(mode)
            (self.inputs / (mode + '.json')).write_bytes(raw)
            if key is None: key = k
            else: key['packet_sha256'].update(k['packet_sha256'])
        self.key_path = self.inputs / 'evaluator-key.DO-NOT-SEND-TO-MODEL.json'
        self.key_path.write_bytes(c.encode(key))
        self.key = key
    def plan(self, url='https://provider.example/v1/chat/completions', test=False):
        return m.prepare(self.inputs, url, 'model-version', test=test, timeout=3)
    def execute(self, plan, name='run', key_env=None):
        raw = c.encode(plan)
        return m.run(raw, self.root / name, approved_sha=c.digest(raw), approved_endpoint=plan['endpoint'], request_cap=100, key_env=key_env)


class Plans(Setup):
    def test_prepare_is_offline_and_complete(self):
        with patch.object(m, 'post', side_effect=AssertionError('network')):
            p = self.plan()
        self.assertEqual(len(p['rows']), 100)
        self.assertEqual(len({x['request_id'] for x in p['rows']}), 100)
        self.assertEqual({(x['case_id'], x['mode']) for x in p['rows']}, {(cid, mode) for cid in c.CASE_IDS for mode in m.MODES})
        packets = m.validate_plan(p)
        for row in p['rows']:
            raw = m.request_body(p, packets, row)
            body = c.decode(raw)
            self.assertEqual(len(body['messages']), 2)
            self.assertFalse(body['stream']); self.assertFalse(body['store'])
            self.assertNotIn('tools', body)
            self.assertNotIn(row['case_id'].encode(), raw)
            self.assertNotIn(b'evaluator-key', raw)
            self.assertNotIn(b'QBN47Q_fixture', raw)  # not in fixture contexts, only private key
        for i in range(0, 100, 2):
            self.assertEqual(p['rows'][i]['case_id'], p['rows'][i+1]['case_id'])
            self.assertNotEqual(p['rows'][i]['mode'], p['rows'][i+1]['mode'])
    def test_fresh_plan_order_and_ids(self):
        a, b = self.plan(), self.plan()
        self.assertNotEqual(a['plan_id'], b['plan_id']); self.assertNotEqual(a['rows'], b['rows'])
    def test_invalid_endpoint_forms(self):
        for url in ('http://provider.example/v1/chat/completions', 'https://name:pass@host/v1/chat/completions',
                    'https://host/v1/chat/completions?api_key=leak', 'https://host/v1/chat/completions#x',
                    'file:///v1/chat/completions', 'https://host:99999/v1/chat/completions',
                    'https://host/\nv1/chat/completions', 'https://host/%2fchat/completions', 'https://host\\evil/v1/chat/completions'):
            with self.subTest(url=url):
                with self.assertRaises(ValueError): m.endpoint(url, False)
        for url in ('http://localhost/v1/chat/completions', 'http://127.0.0.2/v1/chat/completions', 'http://evil/v1/chat/completions'):
            with self.assertRaises(ValueError): m.endpoint(url, True)
        m.endpoint('http://[::1]:8888/v1/chat/completions', True)
    def test_invalid_plan_and_controls(self):
        for field, value in (('max_completion_tokens', True), ('max_completion_tokens', 4097), ('timeout_seconds', 0),
                             ('timeout_seconds', 121), ('model', 'key\ninjection'), ('loopback_test', 1), ('token_field', 'bogus')):
            p = self.plan(); p[field] = value
            with self.subTest(field=field):
                with self.assertRaises(ValueError): m.validate_plan(p)
        p = self.plan(); p['rows'][0] = p['rows'][1]
        with self.assertRaises(ValueError): m.validate_plan(p)
        value = c.decode((self.inputs/'without-context.json').read_bytes())
        value['tasks'][0]['context'] = 'contaminated'
        (self.inputs/'without-context.json').write_bytes(c.encode(value))
        with self.assertRaises(ValueError): self.plan()
    def test_approval_checked_before_any_network_or_output(self):
        p = self.plan(); raw = c.encode(p)
        good = dict(approved_sha=c.digest(raw), approved_endpoint=p['endpoint'], request_cap=100)
        for field, bad in (('approved_sha', 'bad'), ('approved_endpoint', 'https://other/v1/chat/completions'), ('request_cap', 99), ('request_cap', True)):
            with patch.object(m, 'post', side_effect=AssertionError('must not call')):
                with self.assertRaises(ValueError): m.run(raw, self.root/'no', **{**good, field: bad})
            self.assertFalse((self.root/'no').exists())
    def test_missing_key_and_existing_output_never_send(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(m, 'post', side_effect=AssertionError):
            with self.assertRaises(ValueError): self.execute(self.plan(), key_env='QBRAIN_EVAL_KEY')
        with server() as (url, calls):
            p = self.plan(url, True); (self.root/'run').mkdir()
            (self.root/'run/old').write_text('keep')
            with self.assertRaises(FileExistsError): self.execute(p)
            self.assertEqual(calls, []); self.assertEqual((self.root/'run/old').read_text(), 'keep')
    def test_test_endpoint_refuses_credentials(self):
        p = self.plan('http://127.0.0.1:1/v1/chat/completions', True)
        with self.assertRaises(ValueError): self.execute(p, key_env='SECRET')
    def test_secret_collision_in_generated_body_rejected_before_disk(self):
        with patch.dict(os.environ, {'QBRAIN_EVAL_KEY': 'response_format'}), patch.object(m, 'post') as call:
            with self.assertRaises(ValueError): self.execute(self.plan(), key_env='QBRAIN_EVAL_KEY')
            call.assert_not_called()
            self.assertFalse((self.root/'run').exists())
    def test_tls_context_requires_certificate_and_host_verification(self):
        p = self.plan()
        with patch.object(m.http.client, 'HTTPSConnection') as connection:
            reply = connection.return_value.getresponse.return_value
            reply.status = 200; reply.getheader.return_value = 'identity'
            reply.read1.side_effect = [b'{}', b'']
            self.assertEqual(m.post(p, b'{}', 'fake-key-12345'), (200, b'{}'))
            ctx = connection.call_args.kwargs['context']
            self.assertTrue(ctx.check_hostname)
            self.assertEqual(ctx.verify_mode, m.ssl.CERT_REQUIRED)
            self.assertEqual(connection.call_args.args, ('provider.example', 443))
            connection.return_value.request.assert_called_once()
            connection.return_value.close.assert_called_once()
    def test_runtime_has_no_key_argument_in_execution_cli(self):
        cli = subprocess.run([sys.executable, m.__file__, 'execute', '--help'], capture_output=True)
        self.assertIn(b'--key-env', cli.stdout); self.assertNotIn(b'--key ', cli.stdout)


class ResponseTests(Setup):
    def test_bad_answers_and_usage(self):
        p = self.plan(); row = p['rows'][0]; body = c.decode(m.request_body(p, m.validate_plan(p), row))
        for change in ('choices', 'finish', 'role', 'tools', 'refusal', 'content', 'id', 'usage_bool', 'usage_total', 'model'):
            data = c.decode(response(body))
            if change == 'choices': data['choices'] *= 2
            if change == 'finish': data['choices'][0]['finish_reason'] = 'length'
            if change == 'role': data['choices'][0]['message']['role'] = 'user'
            if change == 'tools': data['choices'][0]['message']['tool_calls'] = [{}]
            if change == 'refusal': data['choices'][0]['message']['refusal'] = 'refused'
            if change == 'content': data['choices'][0]['message']['content'] = '```json {} ```'
            if change == 'id': data['choices'][0]['message']['content'] = '{}'
            if change == 'usage_bool': data['usage']['prompt_tokens'] = True
            if change == 'usage_total': data['usage']['total_tokens'] = 1
            if change == 'model': data['model'] = None
            with self.subTest(change=change):
                with self.assertRaises(ValueError): m.parse_response(c.encode(data), row)
    def test_echoed_key_raw_and_escaped_never_saved(self):
        key = 'sk-fake-secret-123456'
        cases = [json.dumps({'secret': key}).encode(), ('{"secret":"'+''.join('\\u%04x'%ord(x) for x in key)+'"}').encode(), b'not-json '+key.encode()]
        for raw in cases:
            saved, error = m.safe_response(raw, key)
            self.assertIsNotNone(error); self.assertNotIn(key.encode(), saved)
        with patch.dict(os.environ, {'QBRAIN_EVAL_KEY': key}), patch.object(m, 'post', return_value=(200, cases[1])):
            result = self.execute(self.plan(), key_env='QBRAIN_EVAL_KEY')
            self.assertEqual(result['attempted'], 1); self.assertEqual(result['completed'], 0)
            for file in (self.root/'run').rglob('*'):
                if file.is_file(): self.assertNotIn(key.encode(), file.read_bytes())
    def test_invalid_json_surrogates_duplicate_keys(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":"\\ud800"}', b'\xff'):
            saved, error = m.safe_response(raw, '')
            self.assertEqual(saved, b''); self.assertEqual(error, 'invalid_json')


class HttpIntegration(Setup):
    def test_hundred_real_http_calls_score_same_denominators(self):
        with server() as (url, calls):
            p = self.plan(url, True); result = self.execute(p)
        self.assertEqual(len(calls), 100); self.assertEqual(result['completed'], 100)
        self.assertTrue(all(x['auth'] is None for x in calls))
        self.assertTrue(all(x['path'] == '/v1/chat/completions' for x in calls))
        # Real execution process does not need or read the key; delete then score fails.
        score = m.score_run(self.root/'run', self.key_path)
        self.assertEqual(score['execution_kind'], 'LOOPBACK_TEST')
        self.assertTrue(score['complete_pair']); self.assertFalse(score['host_consumption_verified'])
        self.assertEqual(score['scores']['without-context']['correct'], 50)
        self.assertEqual(score['scores']['with-context']['correct'], 20)
        self.assertEqual(score['scores']['without-context']['answerable_resolution']['resolved'], 0)
        self.assertEqual(score['provider_reported_usage']['with-context']['input_tokens'], 550)
        self.assertIsNone(score['provider_reported_usage']['with-context']['cost_usd'])
    def test_redirect_no_follow_rate_limit_no_retry_and_bad_bytes_stop(self):
        for fault in ('redirect', 'rate_limit', 'malformed', 'large', 'encoding', 'truncated'):
            with self.subTest(fault=fault), server(fault) as (url, calls):
                p = self.plan(url, True); result = self.execute(p, fault)
                self.assertEqual(len(calls), 1); self.assertEqual(result['attempted'], 1)
                self.assertEqual(result['completed'], 0)
                score = m.score_run(self.root/fault, self.key_path)
                self.assertFalse(score['complete_pair']); self.assertIsNone(score['answerable_resolution_delta'])
                for mode in m.MODES:
                    self.assertEqual(score['scores'][mode]['total'], 50)
                    self.assertEqual(score['scores'][mode]['missing'], 50)
    def test_unknown_usage_stays_null(self):
        with server('missing_usage') as (url, _): self.execute(self.plan(url, True))
        score = m.score_run(self.root/'run', self.key_path)
        self.assertEqual(score['completed'], 100)
        self.assertIsNone(score['provider_reported_usage']['with-context']['input_tokens'])
    def test_model_drift_does_not_produce_comparable_delta(self):
        with server('drift') as (url, _): self.execute(self.plan(url, True))
        score = m.score_run(self.root/'run', self.key_path)
        self.assertTrue(score['complete_pair']); self.assertFalse(score['same_reported_model'])
        self.assertIsNone(score['answerable_resolution_delta'])
    def test_tampered_receipt_response_and_plan_rejected(self):
        with server() as (url, _): self.execute(self.plan(url, True))
        root = self.root/'run'
        for name in ('plan.json', 'run.json', '001/receipt.json', '001/request.json', '001/response.bin', '001/started.json'):
            path = root/name; old = path.read_bytes()
            path.write_bytes(b'{}')
            with self.subTest(name=name):
                with self.assertRaises((ValueError, KeyError)): m.score_run(root, self.key_path)
            path.write_bytes(old)
        self.assertTrue(m.score_run(root, self.key_path)['complete_pair'])
    def test_separate_cli_process_execute_without_accessing_key(self):
        with server() as (url, calls):
            p = self.plan(url, True); raw = c.encode(p); path = self.root/'plan.json'; path.write_bytes(raw)
            key_raw = self.key_path.read_bytes(); self.key_path.unlink()
            cli = subprocess.run([sys.executable, m.__file__, 'execute', '--plan', str(path),
                '--approve-sha256', c.digest(raw), '--approve-endpoint', url, '--approve-requests', '100',
                '--output', str(self.root/'cli-run')], capture_output=True, timeout=30)
            self.assertEqual(cli.returncode, 0, cli.stderr)
            self.assertEqual(len(calls), 100)
            self.key_path.write_bytes(key_raw)
        cli = subprocess.run([sys.executable, m.__file__, 'score', '--run', str(self.root/'cli-run'),
                              '--key', str(self.key_path), '--output', str(self.root/'score.json')], capture_output=True, timeout=30)
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertEqual(c.decode((self.root/'score.json').read_bytes())['execution_kind'], 'LOOPBACK_TEST')


if __name__ == '__main__': unittest.main(verbosity=2)
