"""Independent Windows loopback request oracle for combined cache/observer code."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a=p.parse_args()
    if os.name!='nt':
        raise RuntimeError('Actual WinHTTP qualification requires Windows')
    binary=a.binary.resolve(strict=True);out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    requests=[];lock=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_): pass
        def do_POST(self):
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=65536: self.send_error(400);return
            body=json.loads(self.rfile.read(size))
            with lock:requests.append(dict(path=self.path,body=body,authorization=self.headers.get('Authorization')))
            raw=json.dumps(dict(object='list',model=body['model'],data=[dict(object='embedding',index=0,embedding=[1,2,3])],
                                usage=dict(prompt_tokens=7,total_tokens=7))).encode()
            self.send_response(200);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','PG','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
    try:
        with tempfile.TemporaryDirectory(prefix='n49a-wire-') as home:
            env.update(HOME=home,USERPROFILE=home,APPDATA=home,LOCALAPPDATA=home)
            result=subprocess.run([str(binary),f'http://127.0.0.1:{server.server_port}'],env=env,cwd=home,
                                  capture_output=True,timeout=90)
    finally:
        server.shutdown();server.server_close();worker.join(timeout=5)
    (out/'stdout.json').write_bytes(result.stdout);(out/'stderr.txt').write_bytes(result.stderr)
    (out/'synthetic-requests.json').write_text(json.dumps(requests,indent=2))
    if result.returncode or result.stderr:raise RuntimeError('combined wire probe failed')
    report=json.loads(result.stdout)
    if report.get('passed') is not True:raise ValueError('probe did not pass')
    expected=dict(path='/embeddings',authorization='Bearer SYNTHETIC_KEY_MARKER',
        body=dict(model='SYNTHETIC_MODEL_MARKER',input=['SYNTHETIC_QUERY_MARKER'],encoding_format='float',dimensions=3))
    if requests != [expected,expected]:raise ValueError('actual request count/body differs from exact two misses')
    record=dict(passed=True,http_requests=len(requests),paid_provider_calls=0,
                binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),probe_checks=report['check_count'])
    (out/'RESULT.json').write_text(json.dumps(record,indent=2));print(json.dumps(record))

if __name__=='__main__':main()
