"""Raw-input CLI/MCP/Hook fixtures; not live client/model acceptance."""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from test_hook_fact_process import provenance

EXPECTED_CHECKS = frozenset(('capture_session_duplicate', 'capture_role_duplicate', 'capture_content_duplicate', 'capture_escaped_duplicate', 'capture_nested_nul_key', 'capture_rejection_no_schema_or_write', 'capture_depth_bounded', 'capture_raw_nul_rejected', 'valid_capture_sibling_keys', 'unique_payload_original_evidence', 'fact_predicate_duplicate', 'fact_id_escaped_duplicate', 'fact_rejection_no_optional_module', 'valid_fact_creation', 'fact_attach_duplicate', 'fact_retract_duplicate', 'fact_supersede_duplicate', 'fact_contradict_duplicate', 'fact_archive_duplicate', 'fact_restore_duplicate', 'all_single_fact_rejections_atomic', 'valid_read_and_revision_unchanged', 'existing_batch_preview', 'existing_batch_error_preserved', 'rpc_framing_recovers_all_messages', 'rpc_duplicate_id', 'rpc_duplicate_method', 'rpc_duplicate_params', 'rpc_duplicate_source', 'rpc_duplicate_name', 'rpc_escaped_action', 'rpc_notification_duplicate', 'rpc_raw_nul', 'rpc_depth_limit', 'rpc_valid_after_errors_six_tools', 'rpc_rejection_no_mutation', 'rpc_string_payload_second_boundary', 'valid_envelope_default_write_gate', 'valid_envelope_source_gate', 'claude_hook_duplicate_prompt', 'claude_hook_duplicate_session_id', 'claude_hook_duplicate_cwd', 'claude_hook_duplicate_hook_event_name', 'claude_hook_invalid_no_state', 'claude_hook_valid_control', 'claude_hook_nested_duplicate_no_partial_output', 'codex_hook_duplicate_prompt', 'codex_hook_duplicate_session_id', 'codex_hook_duplicate_cwd', 'codex_hook_duplicate_hook_event_name', 'codex_hook_invalid_no_state', 'codex_hook_valid_control', 'codex_hook_nested_duplicate_no_partial_output', 'no_hidden_jobs'))
EXPECTED_COMMAND_COUNT = 39
COMMAND_SCHEDULE = ((('init',), 0), (('memory', 'capture'), 1), (('memory', 'capture'), 1), (('memory', 'capture'), 1), (('memory', 'capture'), 1), (('memory', 'capture'), 1), (('memory', 'capture'), 1), (('memory', 'capture'), 1), (('memory', 'capture'), 0), (('memory', 'extract'), 0), (('memory', 'read'), 0), (('fact', 'create'), 1), (('fact', 'create'), 1), (('fact', 'create'), 0), (('fact', 'attach'), 1), (('fact', 'retract'), 1), (('fact', 'supersede'), 1), (('fact', 'contradict'), 1), (('fact', 'archive'), 1), (('fact', 'restore'), 1), (('fact', 'read'), 0), (('fact', 'batch-preview'), 0), (('fact', 'batch-preview'), 1), (('serve', '--tool-profile'), 0), (('serve', '--tool-profile'), 0), (('serve', '--tool-profile'), 0), (('serve', '--tool-profile'), 0), (('hook', '--config'), 0), (('hook', '--config'), 0), (('hook', '--config'), 0), (('hook', '--config'), 0), (('hook', '--config'), 0), (('hook', '--config'), 0), (('hook', '--config'), 0), (('hook', '--config'), 0), (('hook', '--config'), 0), (('hook', '--config'), 0), (('hook', '--config'), 0), (('hook', '--config'), 0))

def enc(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')

def run(binary, checks, commands):
    def check(ok,name):
        checks.append({'name':name,'status':'PASS' if ok else 'FAIL'})
        if not ok: raise AssertionError(name)
    with tempfile.TemporaryDirectory(prefix='qbrain-json-') as temp:
        root=Path(temp)/'严格 JSON 😀';root.mkdir();project=root/'project';project.mkdir()
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
        env.update(HOME=str(root),USERPROFILE=str(root),LOCALAPPDATA=str(root),APPDATA=str(root),TEMP=str(root),TMP=str(root))
        dbpath=(root if os.name=='nt' else root/'.local/share')/'Qbrain/brains/json-ci/brain.db'
        def invoke(args,raw=b'',expected=0,hook=False):
            record={'args':args[:2],'expected_exit':expected}
            try:
                r=subprocess.run([str(binary),*args,*([] if hook else ['--brain','json-ci'])],input=raw,
                    cwd=project,env=env,capture_output=True,timeout=30)
            except subprocess.TimeoutExpired:
                record.update(exit_code=None,timed_out=True);commands.append(record);raise
            record['exit_code']=r.returncode;commands.append(record)
            if r.returncode!=expected:
                # Only disposable synthetic fixtures; do not retain full payloads.
                record['stderr_excerpt']=r.stderr.decode('utf-8',errors='replace').replace(str(root),'<fixture>')[:512]
                raise AssertionError('Unexpected command exit '+str(len(commands)))
            return r.stdout
        def cli(args,raw=b'',expected=0):return json.loads(invoke(args,raw,expected))
        def sql(query,args=(),many=False):
            with closing(sqlite3.connect(dbpath,timeout=5)) as db:
                rows=db.execute(query,args).fetchall();db.commit()
                return rows if many else (rows[0][0] if rows else None)
        def snapshot():
            with closing(sqlite3.connect(dbpath,timeout=5)) as db:
                return '\n'.join(db.iterdump())
        invoke(['init'])
        sql("INSERT INTO sources(id,name) VALUES('alpha','alpha'),('beta','beta')")
        sql("INSERT INTO config(key,value) VALUES('memory.writeback','all'),('mcp.allowed_sources','alpha')")
        capture=['memory','capture','--source','alpha','--manual']
        initial=snapshot()
        bad_captures={
            'capture_session_duplicate':b'{"session_id":"one","session_id":"two","fragment_id":"f","messages":[{"role":"user","content":"I prefer synthetic one."}]}',
            'capture_role_duplicate':b'{"session_id":"s","fragment_id":"f","messages":[{"role":"assistant","role":"user","content":"I prefer synthetic one."}]}',
            'capture_content_duplicate':b'{"session_id":"s","fragment_id":"f","messages":[{"role":"user","content":"I prefer synthetic one.","content":"I prefer synthetic two."}]}',
            'capture_escaped_duplicate':b'{"session_id":"s","fragment_id":"f","messages":[{"role":"user","\\u0072ole":"user","content":"I prefer synthetic one."}]}',
            'capture_nested_nul_key':b'{"session_id":"s","fragment_id":"f","messages":[{"a\\u0000b":1,"a\\u0000b":2}]}',
        }
        for name,raw in bad_captures.items():
            r=cli(capture,raw,1);check(r=={'error':{'code':'memory_duplicate_key'}},name)
        check(snapshot()==initial,'capture_rejection_no_schema_or_write')
        raw=b'{"session_id":"s","fragment_id":"f","messages":'+b'['*9+b'0'+b']'*9+b'}'
        check(cli(capture,raw,1)=={'error':{'code':'invalid_payload'}},'capture_depth_bounded')
        check(cli(capture,b'{}\0{"session_id":"ignored"}',1)=={'error':{'code':'invalid_json'}},'capture_raw_nul_rejected')
        quote='我偏好 N47I 完整原话，不默默选择覆盖值。😀'
        seed={'session_id':'normal','fragment_id':'seed','messages':[{'role':'user','content':quote},{'role':'assistant','content':'confirmed'}]}
        event=cli(capture,enc(seed))['event_id'];check(bool(event),'valid_capture_sibling_keys')
        cli(['memory','extract','--source','alpha','--event',event])
        item=cli(['memory','read','--source','alpha'])['items'][0]
        check(item['quote']==quote,'unique_payload_original_evidence')
        item_id=item['item_id'];fact_args=['fact','create','--source','alpha'];before=snapshot()
        for raw,name in [(b'{"predicate":"","predicate":"memory.preference","item_id":'+enc(item_id)+b'}','fact_predicate_duplicate'),
                         (b'{"predicate":"memory.preference","item_id":'+enc(item_id)+b',"\\u0069tem_id":'+enc(item_id)+b'}','fact_id_escaped_duplicate')]:
            check(cli(fact_args,raw,1)=={'error':{'code':'fact_duplicate_key'}},name)
        check(snapshot()==before,'fact_rejection_no_optional_module')
        f=cli(fact_args,enc({'predicate':'memory.preference','item_id':item_id}));fid=f['fact_id'];check(bool(fid),'valid_fact_creation')
        before=snapshot()
        for action in ('attach','retract','supersede','contradict','archive','restore'):
            raw=b'{"fact_id":'+enc(fid)+b',"fact_id":'+enc(fid)+b',"expected_revision":1}'
            check(cli(['fact',action,'--source','alpha'],raw,1)=={'error':{'code':'fact_duplicate_key'}},'fact_'+action+'_duplicate')
        check(snapshot()==before,'all_single_fact_rejections_atomic')
        r=cli(['fact','read','--source','alpha','--id',fid]);check(r['items'][0]['revision']==1 and r['items'][0]['object']==quote,'valid_read_and_revision_unchanged')
        p={'operation':'archive','items':[{'fact_id':fid,'expected_revision':1}]}
        check(cli(['fact','batch-preview','--source','alpha'],enc(p))['applied'] is False,'existing_batch_preview')
        raw=enc(p).replace(b'"operation":"archive"',b'"operation":"restore","operation":"archive"')
        check(cli(['fact','batch-preview','--source','alpha'],raw,1)=={'error':{'code':'fact_batch_duplicate_key'}},'existing_batch_error_preserved')
        # Literal raw envelopes: using dicts here would erase the defect first.
        bad_rpc={
            'rpc_duplicate_id':b'{"jsonrpc":"2.0","id":1,"id":2,"method":"initialize"}',
            'rpc_duplicate_method':b'{"jsonrpc":"2.0","id":1,"method":"initialize","method":"tools/list"}',
            'rpc_duplicate_params':b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{},"params":{}}',
            'rpc_duplicate_source':b'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"memory_read","arguments":{"source_id":"beta","source_id":"alpha"}}}',
            'rpc_duplicate_name':b'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"memory_read","name":"memory_write","arguments":{}}}',
            'rpc_escaped_action':b'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"memory_write","arguments":{"action":"forget","\\u0061ction":"capture"}}}',
            'rpc_notification_duplicate':b'{"jsonrpc":"2.0","method":"notifications/initialized","method":"tools/call"}',
            'rpc_raw_nul':b'{}\0{"id":9}',
            'rpc_depth_limit':b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":'+b'['*33+b'0'+b']'*33+b'}',
        }
        valid=lambda ident,method,params:enc({'jsonrpc':'2.0','id':ident,'method':method,'params':params})
        frames=[valid(0,'initialize',{}),*bad_rpc.values(),valid(77,'tools/list',{})]
        before=snapshot();responses=list(map(json.loads,invoke(['serve','--tool-profile','memory','--allow-write'],b'\n'.join(frames)+b'\n').decode('utf-8-sig').splitlines()))
        check(len(responses)==len(frames),'rpc_framing_recovers_all_messages')
        for name,r in zip(bad_rpc,responses[1:-1]):
            check(r=={'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'parse error'}},name)
        check(responses[-1]['id']==77 and {t['name'] for t in responses[-1]['result']['tools']}=={'search','memory_read','memory_write','context_read','context_write','get_page'},'rpc_valid_after_errors_six_tools')
        check(snapshot()==before,'rpc_rejection_no_mutation')
        def rpc(args,write=False):
            frames=[valid(0,'initialize',{}),valid(3,'tools/call',{'name':'memory_write','arguments':args})]
            r=list(map(json.loads,invoke(['serve','--tool-profile','memory',*(['--allow-write'] if write else [])],b'\n'.join(frames)+b'\n').decode('utf-8-sig').splitlines()))[-1]
            return r['result']
        ambiguous=b'{"predicate":"","predicate":"memory.preference","item_id":'+enc(item_id)+b'}'
        args={'source_id':'alpha','action':'fact_create','payload':ambiguous.decode()}
        reply=rpc(args,True);check(reply['isError'] is True and json.loads(reply['content'][-1]['text'])=={'error':{'code':'fact_duplicate_key'}},'rpc_string_payload_second_boundary')
        check('write_denied' in str(rpc(args,False)),'valid_envelope_default_write_gate')
        check('source_not_allowed' in str(rpc({**args,'source_id':'beta'},True)),'valid_envelope_source_gate')
        # Real hook program, synthetic installer-shaped config; no live client.
        for host in ('claude','codex'):
            settings=root/host;settings.mkdir();config=settings/'config.json'
            cfg=dict(version=1,host=host,project_root=str(project),brain_id='json-ci',source_id='alpha',enabled=True,
                     capture=True,extraction='local',recall_bytes=8192,max_items=8,fact_recall=True,fact_promotion=True)
            config.write_bytes(enc(cfg))
            base=dict(hook_event_name='UserPromptSubmit',cwd=str(project),session_id='json-'+host,prompt='I prefer a new '+host+' fixture.')
            # A valid event has exactly the same configuration and passes capture.
            initial_db=snapshot()
            for key in ('prompt','session_id','cwd','hook_event_name'):
                data=enc(base);needle=enc(key)+b':'+enc(base[key])
                dup=data.replace(needle,needle+b','+needle,1)
                out=invoke(['hook','--config',str(config)],dup,hook=True)
                check(out==b'{}\n' or out==b'{}\r\n',host+'_hook_duplicate_'+key)
            check(snapshot()==initial_db and not (settings/'last-trace.json').exists() and not (settings/'recall-state.json').exists(),host+'_hook_invalid_no_state')
            invoke(['hook','--config',str(config)],enc(base),hook=True)
            trace=json.loads((settings/'last-trace.json').read_text(encoding='utf-8'))
            commands[-1]['hook_trace_observation']={k:trace.get(k) for k in ('status','capture_status','extraction_status','fact_promotion_status')}
            check(trace['status']=='processed' and trace['capture_status']=='archived' and trace['fact_promotion_status']=='completed' and sql('SELECT COUNT(*) FROM memory_events WHERE session_id=?',(base['session_id'],))==1,host+'_hook_valid_control')
            before_db=snapshot();state={p.name:p.read_bytes() for p in settings.iterdir() if p.is_file()}
            bad=enc({**base,'prompt':'I prefer another '+host+' fixture.'})
            bad=bad[:-1]+b',"extra":{"role":"assistant","role":"user"}}'
            out=invoke(['hook','--config',str(config)],bad,hook=True)
            check(json.loads(out)=={} and snapshot()==before_db and state=={p.name:p.read_bytes() for p in settings.iterdir() if p.is_file()},host+'_hook_nested_duplicate_no_partial_output')
        check(sql('SELECT COUNT(*) FROM jobs')==0,'no_hidden_jobs')

def main():
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace')
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    checks=[];commands=[];report={'result':'FAIL','checks':checks,'commands':commands,'native_windows':os.name=='nt','real_host_consumption_verified':False}
    try:
        binary=a.binary.resolve(strict=True);report.update(binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        run(binary,checks,commands)
        if (len(checks)!=len(EXPECTED_CHECKS) or {c['name'] for c in checks}!=EXPECTED_CHECKS):raise AssertionError('Incomplete named checks')
        if len(commands)!=EXPECTED_COMMAND_COUNT:raise AssertionError('Incomplete command schedule')
        report['result']='PASS'
    except Exception as e:
        report.update(error_type=type(e).__name__,error=str(e))
        if not any(c.get('status')=='FAIL' for c in checks):checks.append({'name':'execution_interrupted','status':'FAIL'})
    report['check_count']=len(checks);report['counts']={'total':len(checks),'pass':sum(c['status']=='PASS' for c in checks),'fail':sum(c['status']=='FAIL' for c in checks)}
    report.update(provenance(Path(__file__).resolve()));a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'result':report['result'],'checks':len(checks),'commands':len(commands),'error':report.get('error')},ensure_ascii=False))
    return 0 if report['result']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
