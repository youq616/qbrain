"""Independent subprocess/report checks for N48X; no product helpers imported.
All credentials/prompts are fixed canaries in disposable homes and numeric loopback.
The new sidecars, not original application stdout or legacy logs, have a privacy contract.
"""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse, copy, hashlib, json, os, signal, subprocess, tempfile, threading, time

def digest(raw): return hashlib.sha256(raw).hexdigest()
def encode(obj): return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
def decode(raw):
    def pairs(items):
        obj={}
        for k,v in items:
            if k in obj: raise ValueError('duplicate JSON')
            obj[k]=v
        return obj
    def invalid(_): raise ValueError('nonfinite')
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs, parse_constant=invalid)

def main(binary, probe, output, wire):
    binary=binary.resolve(strict=True);probe=probe.resolve(strict=True)
    output.mkdir(parents=True,exist_ok=False);(output/'raw').mkdir()
    commands=[];checks=[]
    def need(ok,label):
        checks.append(dict(name=label,passed=bool(ok)))
        if not ok:raise ValueError(label)
    def save_process(args,p,stdout,stderr):
        i=len(commands); hashes={}
        for name,raw in [('stdout',stdout),('stderr',stderr)]:
            (output/'raw'/f'{i:03}.{name}').write_bytes(raw);hashes[name]=digest(raw)
        commands.append(dict(args=[str(x) for x in args],exit=p.returncode,hashes=hashes))
    clean={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','PG','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
    try:
        with tempfile.TemporaryDirectory(prefix='n48x-process-') as tmp:
            home=Path(tmp);env={**clean,'HOME':tmp,'USERPROFILE':tmp,'LOCALAPPDATA':tmp,'APPDATA':tmp}
            def call(exe,args,code=0):
                args=[str(exe),*map(str,args)]
                p=subprocess.run(args,env=env,cwd=tmp,capture_output=True,timeout=45)
                save_process(args,p,p.stdout,p.stderr)
                need(p.returncode==code,'native exit '+str(len(commands)-1))
                return p
            def observed(name,args,exe=probe,code=0):
                folder=home/name
                p=call(exe,['observe-model','--output',folder,'--',*args],code)
                return p,folder
            def inspect(folder):
                logical=decode((folder/'logical.json').read_bytes())
                http=decode((folder/'http/report.json').read_bytes())
                summary=decode((folder/'report.json').read_bytes())
                retained=logical['counts']['retained'];finished=0
                for i,record in enumerate(logical['records'],1):
                    need(record['sequence']==i,'logical sequence')
                    start=decode((folder/'calls'/f'{i}.start.json').read_bytes())
                    need(start['entry']==record['entry'] and start['return_state']=='pending','start identity')
                    if record['return_state']!='pending':
                        need(decode((folder/'calls'/f'{i}.finish.json').read_bytes())==record,'finish binds full logical record')
                        finished+=1
                    need(all(record[k] is None for k in ('tokens','price','cost','retry_relation')),'no logical billed quantity')
                    need(record['parent_sequence'] is None or record['parent_sequence']<i,'ordered parent')
                need(len(logical['records'])==retained,'retained inventory')
                need(finished<=logical['counts']['finished'],'finished inventory')
                need(len(http['records'])==len(logical['http_links']),'link cardinality')
                for i,link in enumerate(logical['http_links'],1):
                    need(link['http_sequence']==i and decode((folder/'links'/f'{i}.json').read_bytes())==link,'persisted real HTTP sequence')
                    e=http['records'][i-1]
                    need(decode((folder/'http/attempts'/f'{i}.start.json').read_bytes())['sequence']==i,'HTTP start')
                    if e['complete']:need(decode((folder/'http/attempts'/f'{i}.finish.json').read_bytes())==e,'HTTP finish identity')
                for report in (logical,http,summary):
                    need(all(report[k] is None for k in ('process_exit','stdout_complete','stderr_complete','total_estimate')),'unobserved process and cost stay null')
                joined=b''.join(p.read_bytes() for p in folder.rglob('*.json'))
                for secret in (b'PRIVATE_',b'http://127.',b'Bearer ',b'prompt_tokens"',b'missing chat API key'):
                    need(secret not in joined,'sidecar no private canary/raw payload')
                target=output/name_for(folder)
                # Preserve the entire synthetic sidecar, not only producer assertions.
                import shutil
                shutil.copytree(folder,target)
                return logical,http,summary
            def name_for(folder):return 'capture-'+folder.name
            plain=call(binary,['help'])
            wrapped,folder=observed('help',['help'],binary)
            need((plain.stdout,plain.stderr)==(wrapped.stdout,wrapped.stderr),'plain versus wrapped help unchanged')
            l,h,summary=inspect(folder)
            need(l['counts']['started']==0 and h['counts']['started']==0 and summary['recording_complete'],'help is no invented model invocation')
            p,folder=observed('local',['local'])
            l,h,summary=inspect(folder)
            need([r['entry'] for r in l['records']]==['chat_complete','embed_texts','embed_texts','embed_texts'],'actual entry coverage')
            need([r['path'] for r in l['records']]==['missing_credentials','missing_credentials','invalid_input','local_mock'],'preflight/mock attribution')
            need([r['api_result_ok'] for r in l['records']]==[False,False,False,True] and h['counts']['started']==0,'local outcomes not HTTP')
            verified=call(binary,['observe-model','verify','--logical',folder/'logical.json','--http',folder/'http/report.json'])
            need(decode(verified.stdout)==summary,'paired verification exact')
            for i,mutation in enumerate(('price','parent','private','process','count','links','schema','bool')):
                bad=copy.deepcopy(l)
                if mutation=='price':bad['records'][0]['cost']=0
                elif mutation=='parent':bad['records'][0]['parent_sequence']=1
                elif mutation=='private':bad['records'][0]['prompt']='PRIVATE_IGNORED'
                elif mutation=='process':bad['process_exit']=0
                elif mutation=='count':bad['counts']['finished']=99
                elif mutation=='links':bad['http_links']=[dict(http_sequence=1,logical_sequence=1,association='innermost')]
                elif mutation=='schema':bad['schema']='qbrain-runtime-observation-v2'
                elif mutation=='bool':bad['records'][0]['api_result_ok']='false'
                path=home/f'bad-{i}.json';path.write_bytes(encode(bad))
                rejected=call(binary,['observe-model','verify','--logical',path,'--http',folder/'http/report.json'],2)
                need(not rejected.stdout and b'PRIVATE_IGNORED' not in rejected.stderr,'forged report rejects without private echo')
            p,folder=observed('exception',['exception'],code=2);l,h,summary=inspect(folder)
            need(l['records'][0]['return_state']=='exception' and l['dispatch_state']=='exception' and l['dispatch_return'] is None,'exception lifecycle no fabricated dispatch return')
            need(b'PRIVATE_EXCEPTION' not in p.stderr,'exception redaction')
            p,folder=observed('overflow',['many'],code=2);l,h,summary=inspect(folder)
            need(l['counts']==dict(started=520,finished=520,retained=512,dropped=8,pending=0,record_errors=0),'cap exact completed and dropped')
            # The native text-mode stdout uses CRLF on Windows and LF on POSIX.
            # Keep the full byte assertion; do not strip or normalize captured output.
            need(h['counts']['started']==0 and summary['recording_complete'] is False and p.stdout==(b'all-api-results-success\r\n' if os.name=='nt' else b'all-api-results-success\n'),'cap loss not failed or billed mock')
            sentinel=home/'occupied';sentinel.mkdir();(sentinel/'keep').write_bytes(b'unchanged')
            call(binary,['observe-model','--output',sentinel,'--','help'],2)
            need(list(p.name for p in sentinel.iterdir())==['keep'] and (sentinel/'keep').read_bytes()==b'unchanged','existing destination never overwritten')
            # Real no-reader pipe, closed before spawning. Do not alter SIGPIPE.
            exits=[]
            for observed_mode in (False,True):
                args=[str(binary)]
                folder=home/'closed'
                if observed_mode:args+=['observe-model','--output',str(folder),'--']
                args+=['help']
                rd,wr=os.pipe();os.close(rd)
                try:
                    p=subprocess.Popen(args,cwd=tmp,env=env,stdout=wr,stderr=subprocess.PIPE,restore_signals=True)
                finally:os.close(wr)
                _,err=p.communicate(timeout=20);save_process(args,p,b'',err);exits.append(p.returncode)
            need(exits[0]==exits[1],'observed closed output behavior unchanged')
            if os.name!='nt':need(exits==[-signal.SIGPIPE,-signal.SIGPIPE],'actual POSIX SIGPIPE preserved')
            l,h,summary=inspect(folder)
            need(l['dispatch_return']==0 and l['process_exit'] is None,'report not final output completion')
            # Kill a real child only after its logical start record is actually present.
            folder=home/'killed';args=[str(probe),'observe-model','--output',str(folder),'--','hold']
            p=subprocess.Popen(args,cwd=tmp,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                deadline=time.monotonic()+10
                while not (folder/'calls/1.start.json').exists() and p.poll() is None and time.monotonic()<deadline:time.sleep(.02)
                need((folder/'calls/1.start.json').exists(),'start persisted before abrupt kill')
            finally:
                if p.poll() is None:p.kill()
                out,err=p.communicate(timeout=10);save_process(args,p,out,err)
            need(p.returncode!=0 and not (folder/'calls/1.finish.json').exists() and not (folder/'report.json').exists(),'abrupt exit stays unfinished unknown')
            import shutil
            shutil.copytree(folder,output/'capture-killed')
            if wire:
                records=[]
                class Handler(BaseHTTPRequestHandler):
                    def log_message(self,*_):pass
                    def do_POST(self):
                        length=int(self.headers.get('Content-Length','0'))
                        if not 0<length<1048576:self.send_error(400);return
                        body=decode(self.rfile.read(length))
                        route=self.path;case='normal';status=200
                        if route=='/embeddings':
                            inputs=body['input']
                            if inputs and isinstance(inputs[0],dict):status=503;case='image-unavailable';response={'error':'PRIVATE_ERROR_MARKER'}
                            elif inputs==['malformed']:case='malformed';response={'object':'list','model':body['model'],'data':[]}
                            else:response={'object':'list','model':body['model'],'data':[{'index':i,'embedding':[1.,2.,3.]} for i in range(len(inputs))]}
                        elif route=='/responses':
                            case='pending';response={'object':'response','status':'in_progress','error':{'message':'PRIVATE_ERROR_MARKER'},
                              'output_text':'PRIVATE_REPLY_MARKER','usage':{'input_tokens':10,'output_tokens':2,'total_tokens':12,'input_tokens_details':{'cached_tokens':0,'cache_write_tokens':0}}}
                        elif route=='/rerank':response={'results':[{'index':0,'relevance_score':1.0}]}
                        elif route=='/chat/completions':response={'object':'chat.completion','choices':[{'message':{'content':'[0]'}}],
                              'usage':{'prompt_tokens':10,'completion_tokens':2,'total_tokens':12,'prompt_tokens_details':{'cached_tokens':0,'cache_write_tokens':0}}}
                        else:response={}
                        records.append(dict(route=route,case=case,status=status))
                        payload=encode(response);self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
                server=ThreadingHTTPServer(('127.0.0.1',0),Handler);worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
                try:p,folder=observed('wire',['wire',f'http://127.0.0.1:{server.server_port}'])
                finally:server.shutdown();server.server_close();worker.join(timeout=5)
                (output/'wire-server.json').write_bytes(encode(records)+b'\n')
                l,h,summary=inspect(folder)
                need(len(records)==12 and h['counts']['started']==12 and l['counts']['started']==17,'logical and server inventories distinct')
                need([x['route'] for x in records]==['/embeddings','/chat/completions','/responses','/embeddings','/rerank','/chat/completions','/embeddings','/embeddings','/embeddings','/direct','/embeddings','/chat/completions'],'independent exact server request sequence')
                links=l['http_links']
                need([x['logical_sequence'] for x in links]==[5,6,7,8,9,11,12,13,14,None,16,17],'exact innermost call link sequence')
                need(l['records'][10]['parent_sequence']==10 and l['records'][15]['parent_sequence']==15 and l['records'][16]['parent_sequence']==15,'nested rerank/callback parent identity')
                need(h['records'][2]['usage']['provider_state']=='pending' and all(x is None for x in h['records'][2]['usage']['tokens'].values()) and l['records'][6]['api_result_ok'] is True,'API bool not provider completion or billable usage')
                need(l['records'][7]['fallback_taken'] is True and l['records'][13]['api_result_ok'] is False,'HTTP result and local fallback parse failure retained')
                need(summary['linked_retained_http']==11 and summary['unattributed_retained_http']==1,'direct HTTP unattributed rather than invented logical call')
                need(links[6]['http_sequence']!=links[7]['http_sequence'],'repeated call attempts never deduplicated')
    except Exception as e:
        (output/'PARTIAL.json').write_bytes(encode(dict(passed=False,error=str(e),commands=commands,checks=checks))+b'\n')
        raise
    result=dict(schema='qbrain-n48x-process-v1',passed=True,optimized=not __debug__,platform=os.name,
        commands=commands,checks=checks,command_count=len(commands),check_count=len(checks),
        actual_loopback_requests=12 if wire else 0,paid_provider_requests=0,
        binary_sha256=digest(binary.read_bytes()),probe_sha256=digest(probe.read_bytes()),script_sha256=digest(Path(__file__).read_bytes()))
    (output/'RESULT.json').write_bytes(encode(result)+b'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('commands','checks')}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True)
    p.add_argument('--probe',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--wire',action='store_true')
    a=p.parse_args();main(a.binary,a.probe,a.output,a.wire)
