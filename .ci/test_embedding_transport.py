"""Windows production embedding parser over loopback, never an external model."""
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

p=argparse.ArgumentParser()
p.add_argument('--probe',type=Path,required=True)
p.add_argument('--report',type=Path,required=True)
a=p.parse_args()
if os.name!='nt':
    raise SystemExit('Windows wire acceptance requires real WinHTTP')
checks=[]
requests=[]
class Fixture(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_POST(self):
        self.connection.settimeout(5)
        payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        requests.append(payload)
        mode=self.path.split('/')[1]
        count=len(payload['input'])
        body={'model':'fixture-model','data':[{'index':i,'embedding':[i+1,0.5,-0.25]} for i in range(count)]}
        if mode=='reorder': body['data'].reverse()
        elif mode=='duplicate': body['data'][-1]['index']=0
        elif mode=='missing': body['data'].pop()
        elif mode=='huge': body['data'][-1]['index']=2**64-1
        elif mode=='fraction': body['data'][-1]['index']=0.5
        elif mode=='model': body['model']='other-model'
        elif mode=='null': body['data'][-1]['embedding']=[None,1,1]
        elif mode=='zero': body['data'][-1]['embedding']=[0,0,0]
        elif mode=='overflow': body['data'][-1]['embedding']=[1e100,1,1]
        elif mode=='dimensions': body['data'][-1]['embedding']=[1,1]
        elif mode=='omitted-model': del body['model']
        data=json.dumps(body).encode()
        if mode=='malformed': data=b'{"PRIVATE_PROVIDER_TEXT":'
        if mode=='oversized-image':
            self.send_response(200);self.send_header('Content-Length',str(2*1024*1024+1));self.end_headers();return
        self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers()
        self.wfile.write(data)
server=ThreadingHTTPServer(('127.0.0.1',0),Fixture)
threading.Thread(target=server.serve_forever,daemon=True).start()
env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
probe=subprocess.Popen([str(a.probe.resolve())],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE,text=True,encoding='utf-8',env=env)
reader=ThreadPoolExecutor(max_workers=1)
def check(ok,label):
    if not ok: raise AssertionError(label)
    checks.append(label)
def call(mode,**extra):
    command=dict(base=f'http://127.0.0.1:{server.server_port}/{mode}',embedding=True,**extra)
    probe.stdin.write(json.dumps(command)+'\n');probe.stdin.flush()
    line=reader.submit(probe.stdout.readline).result(timeout=10)
    if not line: raise AssertionError('probe terminated')
    return json.loads(line)
try:
    r=call('reorder')
    check(r['ok'] and [v[0] for v in r['vectors']]==[1,2],'out-of-order vectors retain input identity')
    check(requests[-1]['encoding_format']=='float','explicit float response encoding requested')
    check(requests[-1]['dimensions']==3,'text dimension contract sent')
    for mode in ('duplicate','missing','huge','fraction','model','null','zero','overflow','dimensions','malformed'):
        r=call(mode)
        check(not r['ok'] and r['vectors']==[] and r['error']=='invalid embedding response',mode+' rejects entire batch without raw provider echo')
    check(call('omitted-model')['ok'],'model-less compatible gateway uses request label')
    for mode in ('reorder','model','zero','dimensions','malformed','oversized-image'):
        r=call(mode,image=True)
        # Images accept any consistent nonempty width, independent of text dimension config.
        success=mode in ('reorder','dimensions')
        check(r['ok']==success and r['unavailable']!=success,'image '+mode+' uses shared contract')
        if not success: check(r['vectors']==[[]] and 'PRIVATE_PROVIDER_TEXT' not in r['error'],'image failure contains no partial vector or response echo')
    before=len(requests)
    r=call('reorder',texts=['x']*2049)
    check(not r['ok'] and len(requests)==before,'oversized batch rejected before network')
    r=call('reorder',dimensions=16385)
    check(not r['ok'] and len(requests)==before,'invalid dimension request rejected before network')
    report=dict(result='PASS',native_windows=True,checks=checks,check_count=len(checks),
                source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                probe_sha256=hashlib.sha256(a.probe.read_bytes()).hexdigest(),
                platform=platform.platform(),live_provider_verified=False)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f'N46D native embedding transport: {len(checks)} checks passed')
finally:
    probe.stdin.close()
    try: probe.wait(timeout=5)
    except subprocess.TimeoutExpired: probe.kill();probe.wait(timeout=5)
    reader.shutdown(wait=True,cancel_futures=True)
    server.shutdown();server.server_close()
