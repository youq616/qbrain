"""N46D: real Windows wrappers/WinHTTP/SQLite jobs, synthetic loopback only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import threading


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if os.name != 'nt':
        raise SystemExit('Embedding wire acceptance requires native Windows')
    records, checks = [], []
    lock = threading.Lock()
    private = 'PRIVATE-SENTINEL-provider-data'

    class Fixture(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *_):
            pass

        def do_POST(self):
            try:
                self.connection.settimeout(5)
                raw = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                body = json.loads(raw)
                with lock:
                    records.append((self.path, body, self.headers.get('Authorization')))
                case = self.path.split('/')[1]
                count = len(body['input'])
                data = [{'index': i, 'embedding': [i + 1, i + 2]}
                        for i in reversed(range(count))]
                status = 429 if case == 'http429' else 200
                if case == 'huge-index':
                    data[-1]['index'] = 2**64 - 1
                elif case == 'negative-index':
                    data[-1]['index'] = -1
                elif case == 'fractional-index':
                    data[-1]['index'] = 0.5
                elif case == 'duplicate-index':
                    data[-1]['index'] = data[0]['index']
                elif case == 'missing':
                    data.pop()
                elif case == 'extra':
                    data.append({'index': count, 'embedding': [1, 2]})
                elif case == 'mixed-dimensions':
                    data[-1]['embedding'] = [1]
                elif case == 'wrong-dimensions':
                    for item in data:
                        item['embedding'] = [1, 2, 3]
                elif case == 'zero':
                    data[-1]['embedding'] = [0, 0]
                elif case == 'overflow':
                    data[-1]['embedding'] = [1e100, 1]
                elif case == 'boolean':
                    data[-1]['embedding'] = [True, 1]
                elif case == 'private-component':
                    data[-1]['embedding'] = [1, private]
                elif case == 'no-index':
                    for item in data:
                        item.pop('index')
                response = json.dumps({'data': data, 'model': 'fixture-embedding'}).encode()
                if case in ('malformed', 'http429'):
                    response = ('{"' + private + '":').encode()
                elif case == 'deep':
                    response = b'{"unknown":' + b'[' * 128 + b'0' + b']' * 128 + b',' + response[1:]
                elif case == 'duplicate-key':
                    response = b'{"data":[],' + response[1:]
                if case in ('image-exact', 'image-plus1', 'chunked-image-plus1'):
                    length = 2 * 1024 * 1024 + (case != 'image-exact')
                    response += b' ' * (length - len(response))
                if case == 'text-plus1':
                    response += b' ' * (8 * 1024 * 1024 + 1 - len(response))
                self.send_response(status)
                self.send_header('Connection', 'close')
                if case.startswith('chunked'):
                    self.send_header('Transfer-Encoding', 'chunked')
                else:
                    self.send_header('Content-Length', str(len(response) + (100 if case == 'truncated' else 0)))
                self.end_headers()
                if case.startswith('chunked'):
                    for first in range(0, len(response), 16384):
                        chunk = response[first:first + 16384]
                        self.wfile.write(f'{len(chunk):x}\r\n'.encode() + chunk + b'\r\n')
                    self.wfile.write(b'0\r\n\r\n')
                else:
                    self.wfile.write(response)
                self.wfile.flush()
            except (ConnectionResetError, BrokenPipeError):
                # Oversize/invalid replies deliberately cancel the peer.
                pass
            finally:
                self.close_connection = True

    server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith(('QBRAIN', 'OPENAI', 'ANTHROPIC'))}
    reader = ThreadPoolExecutor(max_workers=1)
    stderr = tempfile.TemporaryFile()
    probe = subprocess.Popen([str(args.probe.resolve())], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=stderr, text=True,
                             encoding='utf-8', env=env)

    def check(ok, label):
        if not ok:
            raise AssertionError(label)
        checks.append(label)

    def call(case='valid', mode='text', **overrides):
        command = {'embed': mode, 'base': f'http://127.0.0.1:{server.server_port}/{case}'}
        command.update(overrides)
        probe.stdin.write(json.dumps(command, ensure_ascii=True) + '\n')
        probe.stdin.flush()
        line = reader.submit(probe.stdout.readline).result(timeout=15)
        if not line:
            raise AssertionError('embedding probe terminated')
        return json.loads(line)

    def reject(case, mode='text', **overrides):
        response = call(case, mode, **overrides)
        check(not response['ok'] and not any(response['vectors']) and response['error'],
              f'{mode}/{case}: all-or-nothing rejection')
        check(private not in response['error'] and 'fixture-token' not in response['error']
              and len(response['error']) < 200, f'{mode}/{case}: redacted error')
        if mode == 'image':
            check(response['unavailable'] and not response['no_credentials'],
                  f'image/{case}: structured degradation')
        return response

    try:
        response = call()
        check(response['ok'] and response['vectors'] == [[1, 2], [2, 3]], 'reordered text batch preserves input association')
        with lock:
            path, body, auth = records[-1]
        check(path == '/valid/embeddings' and body['encoding_format'] == 'float'
              and body['dimensions'] == 2 and body['input'] == ['中文 😀', 'second']
              and auth == 'Bearer fixture-token', 'exact text request format and Unicode')
        check(call(dimensions=0)['ok'], 'unspecified text dimensions inferred')
        response = call(mode='image')
        check(response['ok'] and response['vectors'] == [[1, 2]] and not response['unavailable'], 'valid image vector')
        with lock:
            body = records[-1][1]
        check(body['encoding_format'] == 'float' and 'dimensions' not in body
              and body['input'][0]['image_url']['url'].startswith('data:image/png;base64,'), 'image request encoding remains explicit')
        check(call('no-index', 'image')['ok'], 'legacy single-image missing index remains supported')
        for case in ('huge-index', 'negative-index', 'fractional-index', 'duplicate-index',
                     'missing', 'extra', 'mixed-dimensions', 'wrong-dimensions', 'zero',
                     'overflow', 'boolean', 'private-component', 'no-index', 'malformed',
                     'deep', 'duplicate-key', 'truncated', 'http429', 'text-plus1'):
            reject(case)
        for case in ('huge-index', 'negative-index', 'missing', 'extra', 'zero',
                     'overflow', 'private-component', 'malformed', 'truncated', 'http429',
                     'image-plus1', 'chunked-image-plus1'):
            reject(case, 'image')
        check(call('image-exact', 'image')['ok'], 'image exact 2 MiB response succeeds')
        check(call('image-plus1')['ok'], 'text can accept response beyond the image-specific cap')
        # All preflight failures must occur without contacting the server.
        before = len(records)
        for overrides in ({'dimensions': -1}, {'dimensions': 32769}, {'model': ''},
                          {'model': 'x' * 1025}, {'texts': ['']}, {'invalid_utf8': True},
                          {'texts': ['x'] * 2049}, {'texts': ['x'] * 33, 'dimensions': 32768},
                          {'repeat_bytes': 6 * 1024 * 1024, 'repeat_char': 1},
                          {'repeat_bytes': 32 * 1024 * 1024 + 1}):
            reject('valid', **overrides)
        reject('valid', 'image', image_bytes=24*1024*1024)
        reject('valid', 'image', image_bytes=32*1024*1024+1)
        check(call(texts=[])['ok'], 'empty text batch is a no-network no-op')
        check(not call(key='')['ok'], 'text without credentials fails locally')
        check(call(mode='image', key='')['no_credentials'], 'image without credentials degrades locally')
        check(len(records) == before, 'invalid requests, empty batches and missing credentials cause no network I/O')
        for case in ('huge-index', 'duplicate-index', 'missing', 'private-component'):
            response = call(case, 'job')
            check(response['status'] == 'failed' and response['done'] == 0
                  and response['vectors'] == [[], []], f'job/{case}: no partial persistence or false completion')
            check(private not in json.dumps(response['job_result']), f'job/{case}: persisted error redacted')
        response = call('valid', 'job')
        check(response['status'] == 'completed' and response['done'] == 2
              and response['vectors'] == [[1, 2], [2, 3]], 'valid job stores the correctly associated vectors')
        report = {'result': 'PASS', 'native_windows': True, 'checks': checks,
                  'check_count': len(checks), 'source_commit': subprocess.check_output(
                      ['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  'probe_sha256': hashlib.sha256(args.probe.read_bytes()).hexdigest(),
                  'platform': platform.platform(), 'live_provider_verified': False,
                  'model_provenance_verified': False}
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(f'N46D native embedding: {len(checks)} checks passed')
    finally:
        if probe.poll() is None:
            probe.kill()
        probe.wait(timeout=5)
        reader.shutdown(wait=True, cancel_futures=True)
        stderr.close()
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
