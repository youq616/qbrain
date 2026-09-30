"""Count actual Windows WinHTTP requests against a numeric-loopback synthetic provider.
No client account, no external network endpoint, no PostgreSQL or migration tests.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import threading

def main(binary, output):
    output.mkdir(parents=True, exist_ok=False)
    records = []
    lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            n = int(self.headers.get('Content-Length', '0'))
            if not 0 < n <= 65536:
                self.send_error(400); return
            body = json.loads(self.rfile.read(n))
            with lock:
                records.append(dict(path=self.path, body=body, authorization=self.headers.get('Authorization')))
            dim = body.get('dimensions', 3)
            vectors = [([0.0]*dim if text == 'bad' else [float(i+1) for i in range(dim)]) for text in body['input']]
            data = json.dumps(dict(object='list', model=body['model'], data=[dict(object='embedding', index=i, embedding=v) for i,v in enumerate(vectors)])).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    env = {k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','PG','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
    try:
        with tempfile.TemporaryDirectory(prefix='n48v-http-') as home:
            env.update(HOME=home, USERPROFILE=home, APPDATA=home, LOCALAPPDATA=home)
            result = subprocess.run([str(binary.resolve(strict=True)),f'http://127.0.0.1:{server.server_port}'],cwd=home,env=env,capture_output=True,timeout=90)
    finally:
        server.shutdown();server.server_close();worker.join(timeout=5)
    (output/'stdout.json').write_bytes(result.stdout);(output/'stderr.txt').write_bytes(result.stderr)
    (output/'requests.json').write_text(json.dumps(records,indent=2),encoding='utf8')
    if result.returncode != 0 or result.stderr:
        raise RuntimeError('native HTTP test failed; original output retained')
    expected_queries=['A','A','B','A','A','A','A','A','bad','bad','A','A','A','A']
    if [r['body']['input'] for r in records] != [[q] for q in expected_queries]:
        raise ValueError('independent actual request sequence mismatch')
    if [r['path'] for r in records] != ['/v1/embeddings']*11+['/v2/embeddings']*3:
        raise ValueError('endpoint sequence mismatch')
    if [r['authorization'] for r in records] != ['Bearer n48v-synthetic-only']*10+['Bearer n48v-rotated-synthetic']*4:
        raise ValueError('credential partition mismatch')
    if [r['body'].get('dimensions') for r in records] != [3]*12+[2]*2:
        raise ValueError('dimension partition mismatch')
    if [r['body']['model'] for r in records] != ['fixture-model']*13+['fixture-other']:
        raise ValueError('model partition mismatch')
    report=dict(schema='qbrain-n48v-http-observation-v1',passed=True,http_requests=len(records),provider='numeric_loopback_synthetic',paid_requests=0,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (output/'RESULT.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();main(args.binary,args.output)
