"""Native WinHTTP wire tests. Local synthetic data only; never a live provider test."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import platform
import subprocess
import threading
import time
from urllib.parse import urlsplit

parser = argparse.ArgumentParser()
parser.add_argument('--probe', type=Path, required=True)
parser.add_argument('--report', type=Path)
args = parser.parse_args()
if os.name != 'nt':
    raise SystemExit('Native HTTP acceptance requires Windows; refusing to label a stub PASS')

requests = []
lock = threading.Lock()
stop = threading.Event()
peer_resets = 0
payload = json.dumps({'text': '原生 Windows 😀', 'ok': True}, ensure_ascii=False).encode()
secret_marker = b'fixture-private-provider-error-not-a-secret'


class Fixture(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *_):
        pass

    def handle(self):
        global peer_resets
        try:
            super().handle()
        except (ConnectionResetError, BrokenPipeError):
            # Deliberate client cancellation may reset the socket while the
            # base handler is waiting for another keep-alive request. Count
            # that expected condition instead of flooding the fixture's pipe.
            # Other exceptions and all client-result assertions stay visible.
            with lock:
                peer_resets += 1
            self.close_connection = True

    def do_POST(self):
        try:
            self.connection.settimeout(5)
            body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            with lock:
                requests.append((self.server.server_port, self.path, self.headers.get('Authorization'), body))
            mode = urlsplit(self.path).path.rsplit('/', 1)[-1]
            if '/chat-timeout/' in self.path:
                mode = 'slow-headers'
            elif '/chat-error/' in self.path:
                mode = 'error'
            elif '/chat-truncated/' in self.path:
                mode = 'truncated'
            if mode == 'slow-headers':
                stop.wait(1.5)
            if mode == 'redirect':
                self.send_response(307)
                self.send_header('Location', f'http://127.0.0.1:{sink.server_port}/sink')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            if mode == 'redirect-local':
                self.send_response(302)
                self.send_header('Location', '/sink')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            if mode in ('error', 'auth'):
                self.send_response(429 if mode == 'error' else 401)
                if mode == 'auth':
                    self.send_header('WWW-Authenticate', 'Negotiate')
                self.send_header('Content-Length', str(len(secret_marker)))
                self.end_headers()
                self.wfile.write(secret_marker)
                return
            if mode == 'chat':  # unused direct path; explicit fixture endpoint below
                data = payload
            elif mode == 'completions' or '/chat-truncated/' in self.path:
                data = b'{"choices":[{"message":{"content":"native fixture completion"}}]}'
            elif mode == 'empty':
                data = b''
            elif mode in ('exact', 'chunked-exact'):
                data = b'x' * 1024
            elif mode in ('overflow', 'chunked-overflow'):
                data = b'x' * 1025
            else:
                data = payload
            self.send_response(200)
            if mode.startswith('chunked') or mode in ('trickle', 'stall-body', 'broken-chunk'):
                self.send_header('Transfer-Encoding', 'chunked')
            elif mode == 'oversized-length':
                self.send_header('Content-Length', str(2**63))
            elif mode == 'truncated':
                # The prefix is itself valid JSON: it must NOT be accepted by chat.
                self.send_header('Content-Length', str(len(data) + 100))
            elif mode == 'no-length':
                self.send_header('Connection', 'close')
            else:
                self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            if mode == 'oversized-length':
                stop.wait(1.5)
            elif mode == 'stall-body':
                stop.wait(1.5)
            elif mode == 'trickle':
                for _ in range(60):
                    self.wfile.write(b'1\r\nx\r\n')
                    self.wfile.flush()
                    if stop.wait(.05):
                        break
                self.wfile.write(b'0\r\n\r\n')
            elif mode == 'broken-chunk':
                self.wfile.write(b'10\r\n{}')
                self.wfile.flush()
                self.close_connection = True
            elif mode.startswith('chunked'):
                for offset in range(0, len(data), 97):
                    chunk = data[offset:offset + 97]
                    self.wfile.write(f'{len(chunk):x}\r\n'.encode() + chunk + b'\r\n')
                self.wfile.write(b'0\r\n\r\n')
            else:
                self.wfile.write(data)
                self.wfile.flush()
                if mode in ('truncated', 'no-length'):
                    self.close_connection = True
        except (OSError, ValueError):
            # Cancellation/oversize rejection deliberately closes the peer.
            self.close_connection = True


class FixtureServer(ThreadingHTTPServer):
    request_queue_size = 128
    daemon_threads = True


server = FixtureServer(('127.0.0.1', 0), Fixture)
sink = FixtureServer(('127.0.0.1', 0), Fixture)
for fixture in (server, sink):
    threading.Thread(target=fixture.serve_forever, daemon=True).start()
base = f'http://127.0.0.1:{server.server_port}'
env = {k: v for k, v in os.environ.items()
       if not k.upper().startswith(('QBRAIN', 'OPENAI', 'ANTHROPIC'))}
probe = subprocess.Popen([str(args.probe.resolve())], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, encoding='utf-8', env=env)
reader = ThreadPoolExecutor(max_workers=1)
checks = []
timing = {}


def call(**command):
    probe.stdin.write(json.dumps(command, ensure_ascii=True) + '\n')
    probe.stdin.flush()
    # A hang is a failure, not a skipped check or an indefinitely blocked runner.
    line = reader.submit(probe.stdout.readline).result(timeout=15)
    if not line:
        raise AssertionError('native probe terminated unexpectedly')
    return json.loads(line)


def request(path='/ok', **kwargs):
    return call(base=base, path=path, **kwargs)


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    checks.append(label)


def rejected(response, kind, label):
    check(response['failure'] == kind and response['status'] == 0
          and response['body'] == '' and response['error'], label)


try:
    normal = request(body='{"message":"中文 😀"}')
    check(normal['status'] == 200 and normal['failure'] == 0
          and normal['body'].encode('utf-8') == payload, 'Unicode response exact bytes')
    with lock:
        check(requests[-1][1:] == ('/ok', 'Bearer fixture-token', '{"message":"中文 😀"}'.encode()),
              'request path, bearer and Unicode body preserved')
    for prefix, path in [('', 'ok'), ('/', '/ok'), ('/v1', '/ok'), ('/v1/', 'ok')]:
        response = call(base=base + prefix, path=path)
        check(response['status'] == 200, f'path join {prefix!r} {path!r}')
        with lock:
            check(requests[-1][1] == ('/v1/ok' if 'v1' in prefix else '/ok'),
                  f'no duplicate path separator {prefix!r} {path!r}')
    check(request('/empty', cap=1)['body'] == '', 'zero-length body')
    one = request('/exact', cap=1024)
    check(one['status'] == 200 and len(one['body']) == 1024, 'exact declared cap succeeds')
    one = request('/chunked-exact', cap=1024)
    check(one['status'] == 200 and len(one['body']) == 1024, 'exact streamed cap succeeds')
    rejected(request('/overflow'), 4, 'declared over-cap rejected')
    rejected(request('/chunked-overflow'), 4, 'streamed over-cap rejected')
    response = request('/oversized-length')
    rejected(response, 4, 'huge Content-Length rejected without allocation')
    check(response['elapsed_ms'] < 1200, 'huge declaration rejected before body stall')
    response = request('/no-length')
    check(response['status'] == 200 and response['body'].encode() == payload,
          'close-delimited complete response accepted')
    for path in ('/truncated', '/broken-chunk'):
        response = request(path)
        check(response['failure'] != 0 and response['status'] == 0 and not response['body'],
              f'{path} never accepted as partial success')
    for path in ('/slow-headers', '/stall-body', '/trickle'):
        response = request(path, timeout=250)
        rejected(response, 3, f'{path} deadline failure')
        timing[path] = response['elapsed_ms']
        check(150 <= response['elapsed_ms'] < 1200, f'{path} total deadline, with scheduling tolerance')
    for path, status in [('/error', 429), ('/auth', 401), ('/redirect', 307), ('/redirect-local', 302)]:
        response = request(path)
        check(response['status'] == status and response['failure'] == 5,
              f'{path} HTTP failure classification')
        check(response['body'] == '' and response['error'] == f'HTTP {status}',
              f'{path} no private response echo')
    with lock:
        check(not any(x[0] == sink.server_port or x[1] == '/sink' for x in requests),
              'neither cross-origin nor same-origin redirect followed')
        check(sum(x[1] == '/auth' for x in requests) == 1,
              'no automatic authentication resubmission')
        before = len(requests)
    for overrides in ({'token': 'unit\r\nX-Injected: yes'}, {'path': '//elsewhere'},
                      {'base': base + '/?key=private'}, {'base': base.replace('://', '://user:pass@')},
                      {'timeout': 0}, {'cap': 0}):
        command = dict(base=base, path='/ok')
        command.update(overrides)
        rejected(call(**command), 1, f'invalid request blocked: {next(iter(overrides))}')
    with lock:
        check(len(requests) == before, 'invalid input makes no network request')
    # Long-lived process: cancellation must not leave stack-backed receive buffers
    # dangling or accumulate request/connection/session handles across iterations.
    batch = [{'base': base, 'path': '/stall-body', 'timeout': 40} for _ in range(32)]
    first = call(batch=batch, handle_settle_ms=2000)
    second = call(batch=batch, handle_settle_ms=2000)
    handle_samples = {
        'at_250ms': [first['process_handles_at_250ms'], second['process_handles_at_250ms']],
        'after_fixed_2000ms': [first['process_handles'], second['process_handles']],
        'allowed_growth': 16,
    }
    # Preserve both the historical sample point and the settled observation,
    # even when the leak assertion below fails. Never retry until a green sample.
    print(json.dumps({'cancellation_handle_samples': handle_samples}), flush=True)
    check(all(r['failure'] == 3 and not r['body'] for r in first['results'] + second['results']),
          '64 repeated cancellations complete safely')
    check(second['process_handles'] <= first['process_handles'] + 16,
          'request handles do not grow with repeated cancellations')
    mixed = call(batch=[{'base': base, 'path': '/stall-body' if n % 2 else '/ok',
                         'timeout': 250} for n in range(12)], parallel=True)
    check(all(r['failure'] == (3 if n % 2 else 0) for n, r in enumerate(mixed['results'])),
          'concurrent deadlines remain isolated from successful requests')
    check(request()['status'] == 200, 'successful request after cancellation stress')
    chat = call(base=base, chat=True)
    check(chat['ok'] and chat['body'] == 'native fixture completion', 'production chat accepts complete response')
    chat = call(base=base + '/chat-timeout', chat=True, timeout=250)
    check(not chat['ok'] and chat['chat_failure'] == 3 and not chat['body'],
          'chat uses explicit timeout classification')
    chat = call(base=base + '/chat-error', chat=True)
    check(not chat['ok'] and chat['error'] == 'HTTP 429' and not chat['body'],
          'chat preserves redacted HTTP failure')
    chat = call(base=base + '/chat-truncated', chat=True)
    check(not chat['ok'] and not chat['body'], 'chat never consumes incomplete 2xx response')
    report = {'result': 'PASS', 'native_windows': True, 'checks': checks,
              'check_count': len(checks), 'timings_ms': timing,
              'handle_counts': [first['process_handles'], second['process_handles']],
              'handle_samples': handle_samples, 'expected_peer_resets': peer_resets,
              'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'probe_sha256': hashlib.sha256(args.probe.read_bytes()).hexdigest(),
              'platform': platform.platform(), 'live_provider_verified': False,
              'logged_in_win11_agent_verified': False}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f"Native WinHTTP: {len(checks)} checks passed")
    print(json.dumps({'timings_ms': timing, 'handle_counts': report['handle_counts']}))
finally:
    stop.set()
    if probe.poll() is None:
        probe.stdin.close()
        try:
            probe.wait(timeout=5)
        except subprocess.TimeoutExpired:
            probe.kill()
            probe.wait(timeout=5)
    reader.shutdown(wait=True, cancel_futures=True)
    for fixture in (server, sink):
        fixture.shutdown()
        fixture.server_close()
