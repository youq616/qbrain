"""Actual combined CLI/Hook/observation checks; synthetic disposable inputs only."""
import argparse
from contextlib import closing
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import re
import sys
from check_n49c_sources import clean_environment

def encode(value):return json.dumps(value,ensure_ascii=False,sort_keys=True).encode('utf-8')
def sha(raw):return hashlib.sha256(raw).hexdigest()

def seed_fixture_sources(db):
    # sqlite3's transaction context commits/rolls back but does not close.
    with closing(sqlite3.connect(db)) as conn:
        with conn:
            for source in ('alpha','beta'):
                conn.execute('INSERT INTO sources(id,name) VALUES(?,?)',(source,source))

def capture_command(spec, result_path):
    """Capture fixed qualification argv without a shell, with exact byte streams."""
    prefix=Path(spec['prefix']).resolve();prefix.parent.mkdir(parents=True,exist_ok=True)
    executable=Path(spec['executable']).resolve(strict=True)
    shell=Path(spec['shell_executable']).resolve(strict=True)
    argv=[str(executable),*map(str,spec['arguments'])]
    binary=Path(spec['binary']).resolve(strict=True)
    record=dict(schema='qbrain-n49c-captured-row-v1',name=spec['name'],argv=argv,
        expected_exit=spec['expected_exit'],expected_shell_major=spec['expected_shell_major'],
        binary=str(binary),expected_binary_sha256=spec['binary_sha256'],passed=False,
        environment_policy='scrubbed-credentials-dsns-disposable-home-v1')
    def identity(path):
        p=Path(path).resolve()
        return dict(path=str(p),exists=p.is_file(),sha256=sha(p.read_bytes()) if p.is_file() else None,
            bytes=p.stat().st_size if p.is_file() else None)
    bound=[]
    flags={'-binary','--binary','-installer','--installer','-baselineinstaller','--prior','--test','--log','-report','--report'}
    for i,arg in enumerate(argv[:-1]):
        if arg.lower() in flags:bound.append(dict(flag=arg,before=identity(argv[i+1])))
    record['bound_files']=bound
    try:
        with tempfile.TemporaryDirectory(prefix='n49c-row-home-',ignore_cleanup_errors=True) as home:
            environment=clean_environment(os.environ,home)
            def version(program,label):
                powershell=program.stem.lower() in ('powershell','pwsh')
                args=[str(program),'-NoProfile','-NonInteractive','-Command','[Console]::Write($PSVersionTable.PSVersion.ToString())'] if powershell else [str(program),'--version']
                p=subprocess.run(args,env=environment,capture_output=True,timeout=30)
                for key,raw in [('stdout',p.stdout),('stderr',p.stderr)]:
                    Path(str(prefix)+'.'+label+'.'+key).write_bytes(raw)
                text=(p.stdout+p.stderr).decode('utf-8-sig').strip()
                match=re.fullmatch(r'(?:Python\s+)?(\d+\.\d+(?:\.\d+)*(?:[a-zA-Z0-9.+-]*)?)',text)
                if p.returncode or not match:raise ValueError('cannot verify actual executable version: '+label)
                return dict(executable=str(program),executable_sha256=sha(program.read_bytes()),
                    kind='powershell' if powershell else 'python',version=match[1],major=int(match[1].split('.')[0]),
                    probe_argv=args,probe_exit=p.returncode,stdout_sha256=sha(p.stdout),stderr_sha256=sha(p.stderr))
            record['program']=version(executable,'program-version')
            record['harness_shell']=record['program'] if executable==shell else version(shell,'harness-version')
            before=identity(binary);record['binary_before']=before
            out=Path(str(prefix)+'.stdout');err=Path(str(prefix)+'.stderr')
            with out.open('wb') as stdout,err.open('wb') as stderr:
                p=subprocess.run(argv,env=environment,cwd=spec.get('cwd'),stdout=stdout,stderr=stderr,timeout=600)
            record['actual_exit']=p.returncode
            record['binary_after']=identity(binary)
            record['stdout']=identity(out);record['stderr']=identity(err)
            merged=Path(str(prefix)+'.log');merged.write_bytes(out.read_bytes()+err.read_bytes())
            record['supplemental_log']={**identity(merged),'ordering':'stdout bytes then stderr bytes; not an interleaving claim'}
            for item in bound:item['after']=identity(item['before']['path'])
            reports=[r for r in bound if r['flag'].lower() in ('-report','--report')]
            record['reports']=reports
            reports_ok=all(r['after']['exists'] and (r['flag'].lower()!='--report' or r['before']['sha256']==r['after']['sha256']) for r in reports)
            input_files_ok=all(r['before']['exists'] and r['before']['sha256']==r['after']['sha256']
                for r in bound if r['flag'].lower()!='-report')
            record['passed']=bool(p.returncode==spec['expected_exit'] and reports_ok and input_files_ok and
                record['harness_shell']['major']==spec['expected_shell_major'] and
                before['sha256']==record['binary_after']['sha256']==spec['binary_sha256'])
    except Exception as error:
        record['error']=str(error);record['passed']=False
        for key in ('stdout','stderr'):
            path=Path(str(prefix)+'.'+key)
            if path.exists():record[key]=identity(path)
    Path(result_path).write_bytes(encode(record)+b'\n')
    return record

def main(binary, output, wire):
    binary=binary.resolve(strict=True);output.mkdir(parents=True,exist_ok=False)
    (output/'raw').mkdir();commands=[];checks=[];requests=[];server=None
    def need(ok,name):
        checks.append(dict(name=name,passed=bool(ok)))
        if not ok:raise ValueError(name)
    try:
        with tempfile.TemporaryDirectory(prefix='n49c-combined-') as tmp:
            home=Path(tmp);project=home/'project 中文';project.mkdir()
            env={**clean_environment(os.environ,tmp),'QBRAIN_EMBED_MOCK':'1'}
            def call(args,data=None,code=0):
                argv=[str(binary),*map(str,args)]
                raw=b'' if data is None else encode(data)
                p=subprocess.run(argv,input=raw,env=env,cwd=project,capture_output=True,timeout=45)
                index=len(commands);record=dict(argv=argv,exit=p.returncode)
                for key,value in [('stdin',raw),('stdout',p.stdout),('stderr',p.stderr)]:
                    (output/'raw'/f'{index:03}.{key}').write_bytes(value);record[key+'_sha256']=sha(value)
                commands.append(record);need(p.returncode==code,'exit '+str(index))
                return p
            def cli(args,data=None,code=0):return call([*args,'--brain','n49c'],data,code)
            cli(['init','--no-default']);cli(['config','set','embed.auto','false','--local'])
            cli(['config','set','memory.writeback','salient','--local'])
            db=(home if os.name=='nt' else home/'.local/share')/'Qbrain/brains/n49c/brain.db'
            seed_fixture_sources(db)
            for slug in ('docs/a','docs/b','neighbor/c'):
                cli(['put','--slug',slug,'--title','PRIVATE_N49C_NEEDLE','--body','PRIVATE_N49C_NEEDLE body'])
            directory='qbrain://default/resources/docs/'
            def observed(name,options,embeddings=0,http_count=0,code=0,rerank=False,chat=False):
                folder=home/name;before=len(requests)
                try:
                    p=call(['observe-model','--output',folder,'--','search','--query','PRIVATE_N49C_NEEDLE',
                        '--uri',directory,'--json',*options,'--brain','n49c'],code=code)
                finally:
                    if folder.exists():shutil.copytree(folder,output/('capture-'+name))
                logical=json.loads((folder/'logical.json').read_bytes());http=json.loads((folder/'http/report.json').read_bytes())
                entries=[r['entry'] for r in logical['records']]
                need(entries.count('embed_texts')==embeddings,name+' query embedding count')
                need(entries.count('apply_reranker')==int(rerank),name+' rerank entry count')
                need(entries.count('chat_complete')==int(chat),name+' chat entry count')
                need(len(http['records'])==http_count,name+' actual HTTP count')
                need(len(requests)-before==http_count,name+' independent wire count')
                need(len(logical['http_links'])==http_count,name+' link cardinality')
                for link in logical['http_links']:
                    need(link['association']=='innermost' and link['logical_sequence'] is not None,name+' HTTP belongs to actual logical entry')
                for record in logical['records']:
                    need(all(record[k] is None for k in ('tokens','price','cost','retry_relation')),name+' unknown billing fields')
                need(logical['total_estimate'] is None and http['total_estimate'] is None,name+' unknown total')
                for marker in (b'PRIVATE_N49C',b'SYNTHETIC_N49C_KEY',b'127.0.0.1'):
                    need(marker not in b''.join(f.read_bytes() for f in folder.rglob('*.json')),name+' private input absent from observation')
                call(['observe-model','verify','--logical',folder/'logical.json','--http',folder/'http/report.json'])
                if code==0:
                    hits=json.loads(p.stdout);need({r['slug'] for r in hits}=={'docs/a','docs/b'},name+' actual scoped results')
                return logical,http
            observed('no-vector',['--no-vector'])
            observed('conservative',['--mode','conservative'])
            observed('local-rerank',['--mode','conservative','--rerank'],rerank=True)
            observed('mock-vector',[],embeddings=1)
            old=directory;directory=directory.rstrip('/')
            observed('invalid-directory',[],code=2);directory=old

            # Full accepted Cursor adapter, then actual public context and directory reads.
            cfg=dict(version=1,enabled=True,host='cursor',project_root=str(project),brain_id='n49c',source_id='alpha',
                capture=False,extraction='local',recall_bytes=8192,max_items=8,fact_recall=False,fact_promotion=False)
            config=home/'cursor.json';quote='I prefer PRIVATE_N49C_CURSOR 中文 exactly.'
            def hook(kind,session='A',generation='A',**fields):
                config.write_bytes(encode(cfg))
                event=dict(hook_event_name=kind,conversation_id=session,generation_id=generation,
                    workspace_roots=[str(project)],is_background_agent=False,**fields)
                return json.loads(call(['hook','--config',config],event).stdout)
            def memories(source):return json.loads(cli(['search','--query','PRIVATE_N49C_CURSOR','--uri',f'qbrain://{source}/memories/','--no-vector','--json']).stdout)
            need(hook('beforeSubmitPrompt',prompt=quote)=={'continue':True},'Cursor default off stays nonblocking')
            need(memories('alpha')==[],'default off creates no searchable fragment')
            cfg['capture']=True
            need(hook('beforeSubmitPrompt',prompt=quote)=={'continue':True},'Cursor explicit capture succeeds')
            hits=memories('alpha');need(len(hits)==1 and hits[0]['source_id']=='alpha','Cursor fragment visible to scoped text search')
            need(memories('beta')==[],'Cursor fragment absent from foreign directory')
            uri='qbrain://alpha/memories/'+hits[0]['slug']
            context=json.loads(cli(['context','read','--source','alpha','--uri',uri,'--layer','L2','--max-bytes','8192']).stdout)
            need(quote in context['content'] and context['provider_calls']==0,'Cursor exact text reaches existing context API')
            recalled=hook('sessionStart',session='B')
            need('additional_context' in recalled and quote in recalled['additional_context'],'Cursor subsequent session gets existing context')
            items=json.loads(cli(['memory','read','--source','alpha']).stdout)['items']
            need(len(items)==1,'one committed captured item')
            cli(['memory','forget','--source','alpha','--event',items[0]['event_id']])
            need(memories('alpha')==[],'withdrawal removes owned directory evidence')
            need(hook('sessionStart',session='C')=={},'withdrawal also removes Cursor recall')

            if wire:
                need(os.name=='nt','real wire qualification requires Windows WinHTTP')
                env.pop('QBRAIN_EMBED_MOCK',None)
                response_status=[200]
                class Handler(BaseHTTPRequestHandler):
                    def log_message(self,*args):pass
                    def do_POST(self):
                        size=int(self.headers.get('Content-Length','0'))
                        if not 0<size<=65536:self.send_error(400);return
                        payload=json.loads(self.rfile.read(size));requests.append(dict(path=self.path,body=payload))
                        if self.path=='/embeddings':
                            value=dict(model=payload['model'],data=[dict(index=0,embedding=[1,2,3])])
                        else:value=dict(choices=[dict(message=dict(content='[1,0]'))])
                        raw=encode(value);self.send_response(response_status[0]);self.send_header('Content-Type','application/json')
                        self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
                server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
                thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
                base=f'http://127.0.0.1:{server.server_port}'
                for key,value in [('chat.base_url',base),('embedding.base_url',base),('chat.api_key','SYNTHETIC_N49C_KEY'),
                    ('embedding.api_key','SYNTHETIC_N49C_KEY'),('chat.model','synthetic-n49c'),('embedding.model','synthetic-n49c'),
                    ('embedding.dimensions','3'),('chat.endpoint','chat')]:
                    cli(['config','set',key,value,'--local'])
                observed('wire-embedding',[],embeddings=1,http_count=1)
                observed('wire-conservative-rerank',['--mode','conservative','--rerank','--rerank-llm'],http_count=1,rerank=True,chat=True)
                observed('wire-tokenmax',['--no-vector','--mode','tokenmax'],http_count=1,rerank=True,chat=True)
                response_status[0]=500
                logical,http=observed('wire-rerank-error',['--no-vector','--rerank','--rerank-llm'],http_count=1,rerank=True,chat=True)
                need(any(r['entry']=='chat_complete' and r['api_result_ok'] is False for r in logical['records']),'real rerank HTTP failure retained')
    except Exception as e:
        (output/'PARTIAL.json').write_bytes(encode(dict(passed=False,error=str(e),commands=commands,checks=checks)))
        raise
    finally:
        try:
            if server:server.shutdown();server.server_close()
        finally:
            (output/'synthetic-requests.json').write_bytes(encode(requests))
    report=dict(passed=True,schema='qbrain-n49c-process-v1',commands=commands,checks=checks,
        command_count=len(commands),check_count=len(checks),actual_http_requests=len(requests),wire_executed=wire,
        wire_not_run_reason=None if wire else 'Windows-only actual WinHTTP gate',binary_sha256=sha(binary.read_bytes()),
        script_sha256=sha(Path(__file__).read_bytes()),real_cursor=False,postgres_executed=False,paid_provider_calls=0)
    (output/'RESULT.json').write_bytes(encode(report))
    print(json.dumps({k:v for k,v in report.items() if k not in ('commands','checks')}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path);p.add_argument('--output',type=Path);p.add_argument('--wire',action='store_true')
    p.add_argument('--capture-spec',type=Path);p.add_argument('--capture-result',type=Path)
    a=p.parse_args()
    if a.capture_spec:
        if not a.capture_result:p.error('--capture-result required')
        row=capture_command(json.loads(a.capture_spec.read_text(encoding='utf-8-sig')),a.capture_result)
        print(json.dumps(dict(recorded=True,passed=row['passed'])))
    else:
        if not a.binary or not a.output:p.error('--binary and --output required')
        main(a.binary,a.output,a.wire)
