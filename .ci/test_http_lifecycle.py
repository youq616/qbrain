"""Fixed native cancellation diagnosis; numeric synthetic data only, no secrets."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import threading
from validate_http_lifecycle import validate_report

p = argparse.ArgumentParser()
p.add_argument('--probe', type=Path, required=True)
p.add_argument('--baseline', type=Path, required=True)
p.add_argument('--per-call', type=Path, required=True)
p.add_argument('--report', type=Path, required=True)
a = p.parse_args()
if os.name != 'nt':
    raise SystemExit('Native Windows required; a stub is not acceptance')
stop = threading.Event()
class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 128
class Fixture(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *_): pass
    def handle(self):
        try: super().handle()
        except (OSError, ValueError): self.close_connection = True
    def do_POST(self):
        self.connection.settimeout(3)
        self.rfile.read(int(self.headers.get('Content-Length', '0')))
        self.send_response(200)
        self.send_header('Transfer-Encoding', 'chunked')
        self.end_headers()
        stop.wait(1.5)
        self.close_connection = True
server = Server(('127.0.0.1', 0), Fixture)
threading.Thread(target=server.serve_forever, daemon=True).start()
env = {k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
report = {'result':'FAIL', 'native_windows':True, 'rounds_per_variant':8, 'requests_per_round':32,
          'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
          'allowed_growth':16, 'variants':{}, 'session_policy':'shared_immutable_request_timeouts',
          'platform':platform.platform(), 'universal_leak_freedom_proven':False}

def observe(binary, label):
    proc = subprocess.Popen([str(binary.resolve())], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding='utf-8', env=env)
    reader = ThreadPoolExecutor(max_workers=1)
    result = {'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(), 'samples':[], 'exit_code':None}
    report['variants'][label] = result  # Retain partial evidence if a child fails.
    def call(command):
        proc.stdin.write(json.dumps(command)+'\n');proc.stdin.flush()
        line = reader.submit(proc.stdout.readline).result(timeout=15)
        if not line: raise RuntimeError('Probe ended before the complete schedule')
        return json.loads(line)
    try:
        for n in range(8):
            row = call({'base':f'http://127.0.0.1:{server.server_port}', 'count':32})
            result['samples'].append(row)
            print(json.dumps({'variant':label,'round':n+1,**row}),flush=True)
        result['shutdown'] = call({'count':0, 'release_session':True})
        print(json.dumps({'variant':label,'shutdown':result['shutdown']}),flush=True)
        proc.stdin.close();proc.wait(timeout=5)
        result['exit_code'] = proc.returncode
        if proc.returncode != 0: raise RuntimeError('Probe exit was not successful')
    finally:
        if not proc.stdin.closed: proc.stdin.close()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill();proc.wait(timeout=5)
        reader.shutdown(wait=True,cancel_futures=True)

try:
    for label, path in [('legacy',a.baseline),('per_call',a.per_call),('current',a.probe),('current_repeat',a.probe)]:
        observe(path, label)
    report['validation'] = validate_report(report, source_commit=report['source_commit'],
        probe_hashes={name:hashlib.sha256(path.read_bytes()).hexdigest()
                      for name,path in [('legacy',a.baseline),('per_call',a.per_call),('current',a.probe)]},
        require_pass=False)
    report['result']='PASS'
except Exception as error:
    report['error_type']=type(error).__name__
    raise
finally:
    stop.set();server.shutdown();server.server_close()
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
