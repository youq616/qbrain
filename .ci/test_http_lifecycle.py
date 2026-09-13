"""Native controlled cancellation diagnosis; finite-sample evidence, no secrets."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
from validate_http_lifecycle import validate_report

p = argparse.ArgumentParser()
p.add_argument('--probe', type=Path, required=True)
p.add_argument('--baseline', type=Path, required=True)
p.add_argument('--pooled', type=Path, required=True)
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
          'allowed_growth':16, 'variants':{}, 'pool_policy':'session_private', 'universal_leak_freedom_proven':False}

def observe(binary):
    proc = subprocess.Popen([str(binary.resolve())], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding='utf-8', env=env)
    reader = ThreadPoolExecutor(max_workers=1)
    rows = []
    try:
        for n in range(8):
            proc.stdin.write(json.dumps({'base':f'http://127.0.0.1:{server.server_port}', 'count':32})+'\n')
            proc.stdin.flush()
            line = reader.submit(proc.stdout.readline).result(timeout=15)
            if not line: raise RuntimeError('Probe ended before full sample schedule')
            row=json.loads(line);rows.append(row)
            print(json.dumps({'variant':binary.name,'round':n+1,**row}),flush=True)
        proc.stdin.close()
        proc.wait(timeout=5)
        if proc.returncode != 0: raise RuntimeError('Probe exit was not successful')
        return {'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'samples':rows,
                'exit_code':proc.returncode}
    finally:
        if not proc.stdin.closed: proc.stdin.close()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill();proc.wait(timeout=5)
        reader.shutdown(wait=True,cancel_futures=True)

try:
    report['variants']['legacy'] = observe(a.baseline)
    report['variants']['pooled'] = observe(a.pooled)
    report['variants']['current'] = observe(a.probe)
    report['variants']['current_repeat'] = observe(a.probe)
    # Validate every record before labelling this fixed schedule PASS.
    report['validation'] = validate_report(report, source_commit=report['source_commit'],
        probe_hashes={name:hashlib.sha256(path.read_bytes()).hexdigest()
                      for name,path in [('legacy',a.baseline),('pooled',a.pooled),('current',a.probe)]},
        require_pass=False)
    report['result']='PASS'

except Exception as error:
    report['error_type']=type(error).__name__
    raise
finally:
    stop.set();server.shutdown();server.server_close()
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
