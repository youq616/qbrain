"""Fixed-sample, Windows-only observation. Not a replacement acceptance gate."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import threading

p=argparse.ArgumentParser()
p.add_argument('--probe',required=True,type=Path)
p.add_argument('--report',required=True,type=Path)
a=p.parse_args()
if os.name!='nt': raise SystemExit('Native Windows required')
stop=threading.Event()
class Fixture(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*_): pass
    def handle(self):
        try: super().handle()
        except (ConnectionResetError,BrokenPipeError): self.close_connection=True
    def do_POST(self):
        try:
            self.connection.settimeout(5)
            self.rfile.read(int(self.headers.get('Content-Length','0')))
            self.send_response(200)
            self.send_header('Transfer-Encoding','chunked')
            self.end_headers()
            stop.wait(1.5)
        except (ConnectionResetError,BrokenPipeError): self.close_connection=True
server=ThreadingHTTPServer(('127.0.0.1',0),Fixture)
server.daemon_threads=True
threading.Thread(target=server.serve_forever,daemon=True).start()
try:
    run=subprocess.run([str(a.probe.resolve()),f'http://127.0.0.1:{server.server_port}'],
                       capture_output=True,text=True,encoding='utf-8',timeout=90)
    print(run.stderr,end='')
    report=json.loads(run.stdout)
    report.update(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                  probe_sha256=hashlib.sha256(a.probe.read_bytes()).hexdigest(),exit_code=run.returncode)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'initial':report['initial'],'final':report['after_fixed_30s'],
                      'owned_lifetimes_released':report['owned_lifetimes_released']}))
    raise SystemExit(run.returncode)
finally:
    stop.set();server.shutdown();server.server_close()
