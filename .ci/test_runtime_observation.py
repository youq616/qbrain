"""Real CLI capture and Windows loopback observations; no producer helper imports.
Only synthetic local data. Raw request/payload/credentials are not saved by this test.
"""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import closing
import argparse, hashlib, json, os, sqlite3, subprocess, tempfile, threading, time

SECRETS=(b'PRIVATE_KEY_SENTINEL',b'PRIVATE_MODEL_SENTINEL',b'PRIVATE_PROMPT_SENTINEL',b'PRIVATE_REPLY_SENTINEL',b'PRIVATE_ID_SENTINEL',b'PRIVATE_URL_SENTINEL')
def dumps(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def main(binary,output,http_binary):
    binary=binary.resolve(strict=True);output.mkdir(parents=True,exist_ok=False)
    records=[];checks=[];calls=[]
    def need(ok,name):
        checks.append(dict(name=name,passed=bool(ok)))
        if not ok:raise ValueError(name)
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','PG','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
    def run(args,home,expected=0,timeout=30):
        p=subprocess.run([str(binary),*map(str,args)],input=b'',capture_output=True,cwd=home,env=env,timeout=timeout)
        calls.append(dict(args_kind=str(args[0]),exit=p.returncode,stdout_sha256=hashlib.sha256(p.stdout).hexdigest(),stderr_sha256=hashlib.sha256(p.stderr).hexdigest()))
        need(p.returncode==expected,'CLI exit '+str(args[0]))
        return p
    with tempfile.TemporaryDirectory(prefix='n48w-isolated-') as t:
        home=Path(t);env.update(HOME=t,USERPROFILE=t,LOCALAPPDATA=t,APPDATA=t)
        capture=home/'capture'
        p=run(['observe','--output',capture,'--','help'],home)
        need(b'Additional command:' in p.stdout,'original command stdout preserved')
        r=json.loads((capture/'report.json').read_bytes());need(r['counts']['started']==0 and r['recording_complete'] is True,'zero HTTP calls explicitly observed')
        original={str(f.relative_to(capture)):f.read_bytes() for f in capture.rglob('*') if f.is_file()}
        run(['observe','--output',capture,'--','help'],home,2)
        need(original=={str(f.relative_to(capture)):f.read_bytes() for f in capture.rglob('*') if f.is_file()},'existing output never overwritten')
        run(['init','--no-default','--brain','n48w'],home)
        for key,value in [('embed.auto','false'),('embedding.base_url','invalid PRIVATE_URL_SENTINEL'),('embedding.api_key','PRIVATE_KEY_SENTINEL')]:
            run(['config','set',key,value,'--local','--brain','n48w'],home)
        sidecar=home/'invalid-attempt'
        run(['observe','--output',sidecar,'--','search','PRIVATE_PROMPT_SENTINEL','--brain','n48w'],home)
        r=json.loads((sidecar/'report.json').read_bytes())
        need(r['counts']['started']==1 and r['records'][0]['transport']=='invalid_request','registered search reaches shared real boundary')
        need(r['records'][0]['send_invoked'] is False and r['records'][0]['cost'] is None,'local validation not invented send or free cost')
        need(len(list((sidecar/'attempts').glob('*.json')))==2,'durable start and finish retained')
        for f in sidecar.rglob('*.json'):need(not any(s in f.read_bytes() for s in SECRETS),'no private sentinel in sidecar')
        assignments=home/'rates.json';assignments.write_bytes(dumps(dict(schema='qbrain-observation-rates-v1',currency='USD',rates=[],assignments=[dict(sequence=1,call_id='call1',attempt=1,stage='embedding',rate_id='unassigned')])))
        cost=json.loads(run(['observe','cost','--report',sidecar/'report.json','--assignments',assignments],home).stdout)
        need(cost['total_estimate'] is None and cost['observed_record_cost']['summary']['unknown_components']==4,'offline cost retains unknowns')
        # Zero final report after abrupt death is not equivalent to zero provider calls.
        if http_binary:
            entered=threading.Event();lock=threading.Lock()
            def usage(responses=False):
                return dict(input_tokens=100,output_tokens=20,total_tokens=120,input_tokens_details=dict(cached_tokens=30,cache_write_tokens=10)) if responses else dict(prompt_tokens=100,completion_tokens=20,total_tokens=120,prompt_tokens_details=dict(cached_tokens=30,cache_write_tokens=10))
            class Handler(BaseHTTPRequestHandler):
                def log_message(self,*_):pass
                def do_POST(self):
                    n=int(self.headers.get('Content-Length','0'))
                    if n>65536:self.send_error(413);return
                    body=json.loads(self.rfile.read(n));fixture=body.get('fixture','normal')
                    with lock:records.append(dict(api=self.path,fixture=fixture))
                    if fixture=='hold':entered.set();time.sleep(2)
                    if fixture=='timeout':time.sleep(0.4)
                    status=429 if fixture=='error' else 200
                    if self.path=='/embeddings':reply=dict(object='list',model='PRIVATE_MODEL_SENTINEL',data=[dict(object='embedding',index=0,embedding=[1.,2.,3.])],usage=dict(prompt_tokens=8,total_tokens=8))
                    elif self.path=='/rerank':reply=dict(results=[],usage=dict(tokens=88))
                    elif self.path=='/responses':reply=dict(object='response',status=fixture if fixture in ('failed','cancelled') else 'in_progress' if fixture=='pending' else 'completed',output_text='PRIVATE_REPLY_SENTINEL',id='PRIVATE_ID_SENTINEL',usage=usage(True))
                    else:reply=dict(object='chat.completion',choices=[dict(message=dict(content='PRIVATE_REPLY_SENTINEL'),finish_reason='stop')],model='PRIVATE_MODEL_SENTINEL',usage=usage())
                    if fixture=='error':reply=dict(error=dict(message='PRIVATE_REPLY_SENTINEL PRIVATE_KEY_SENTINEL'),usage=usage())
                    if fixture=='missing':reply.pop('usage',None)
                    data=dumps(reply)
                    if fixture=='duplicate':data=b'{"object":"chat.completion","usage":{},"usage":{}}'
                    if fixture=='invalid':data=b'PRIVATE_REPLY_SENTINEL invalid json'
                    if fixture=='oversize':data=b'x'*512
                    try:
                        self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)+(20 if fixture=='truncated' else 0)));self.end_headers();self.wfile.write(data)
                    except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
                    self.close_connection=True
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler);worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            url=f'http://127.0.0.1:{server.server_port}'
            try:
                target=home/'wire'
                p=subprocess.run([str(http_binary.resolve()),url,str(target)],capture_output=True,cwd=home,env=env,timeout=35)
                (output/'http-probe.stdout').write_bytes(p.stdout);(output/'http-probe.stderr').write_bytes(p.stderr)
                need(p.returncode==0,'real original model API probe')
                wire=json.loads((target/'report.json').read_bytes());rows=wire['records']
                need(len(rows)==16 and len(records)==15 and wire['recording_complete'] is True,'server request count versus boundary validation count')
                need([x['api'] for x in rows[:4]]==['chat','embeddings','responses','rerank'],'model APIs all observed at one boundary')
                need(rows[0]['usage']['tokens']==dict(input_uncached=60,input_cache_read=30,input_cache_write=10,output=20),'exact primary usage from actual response')
                need(rows[1]['usage']['input_inclusive']==8 and all(v is None for v in rows[1]['usage']['tokens'].values()),'embedding unknown partitions maintained')
                need([x['transport'] for x in rows[4:6]]==['http_error','http_error'],'two failed repeated requests not deduplicated')
                need(rows[7]['usage']['provider_state']=='failed' and rows[8]['usage']['provider_state']=='cancelled','terminal provider failure and cancellation usage retained')
                need(all(v is None for v in rows[9]['usage']['tokens'].values()),'pending body not final usage')
                need([x['usage']['state'] for x in rows[10:12]]==['invalid','invalid'],'duplicate and malformed body redacted')
                need([x['transport'] for x in rows[12:]]==['response_limit','timeout','transport_error','invalid_request'],'transport failure classifications')
                need(all(x['retry_relation'] is None for x in rows),'repeated request relation not guessed')
                for f in target.rglob('*.json'):need(not any(s in f.read_bytes() for s in SECRETS),'no private wire content in logs')
                (output/'wire-report.json').write_bytes((target/'report.json').read_bytes())
                killed=home/'killed';child=subprocess.Popen([str(http_binary.resolve()),url,str(killed),'hold'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=home,env=env)
                try:
                    need(entered.wait(8),'hold request reached local server')
                    child.kill();child.communicate(timeout=5)
                finally:
                    if child.poll() is None:child.kill();child.communicate(timeout=5)
                need((killed/'attempts/1.start.json').exists() and not (killed/'attempts/1.finish.json').exists() and not (killed/'report.json').exists(),'abrupt termination leaves unknown start not false final zero')
                (output/'killed-start.json').write_bytes((killed/'attempts/1.start.json').read_bytes())
            finally:server.shutdown();server.server_close();worker.join(timeout=5)
    result=dict(schema='qbrain-n48w-process-v1',passed=True,checks=checks,check_count=len(checks),cli_calls=calls,http_calls=records,real_http=bool(http_binary),paid_calls=0,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),optimized=not __debug__)
    (output/'RESULT.json').write_bytes(dumps(result)+b'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('checks','http_calls','cli_calls')}))
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--binary',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--http-binary',type=Path)
    a=parser.parse_args();main(a.binary,a.output,a.http_binary)
