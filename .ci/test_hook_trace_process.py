"""Real isolated Hook processes. No real client, model credentials or user history."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from test_hook_fact_process import provenance

CASES=('automatic_pipeline_recorded','last_matches_event','no_original_text','promotion_survives_stop_end',
       'compatibility_tracks_end','new_session_correlation','context_unchanged','secret_not_recorded',
       'malformed_inert','disabled_inert','outside_inert','unknown_event_inert','processing_failure_recorded',
       'failure_has_no_input','recovery_after_failure','state_failure_preserves_context','state_failure_phase',
       'slot_failure_preserves_context','slot_failure_other_file_succeeds','latest_failure_preserves_context',
       'latest_failure_event_file_succeeds','both_diagnostics_nonblocking','fixed_retention','all_slots_bounded',
       'corrupt_brain_failure_recorded','session_key_not_raw','no_consumption_claim','host_slots_isolated')
EXPECTED_CHECKS=frozenset(h+':'+c for h in ('claude','codex') for c in CASES)
CALLS=('init','writeback','submit','stop','end','start','secret','malformed','disabled','outside','unknown',
       'oversize','recover','state-failure','slot-failure','last-failure','both-failure','precompact',
       'refresh-start','refresh-submit',*(f'repeat-end-{i}' for i in range(12)),'open-failure')
COMMAND_SCHEDULE=tuple(h+':'+c for h in ('claude','codex') for c in CALLS)
EXPECTED_COMMAND_COUNT=len(COMMAND_SCHEDULE)

def enc(value):return json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')
def sha(value):return hashlib.sha256(value).hexdigest()

def run(binary,checks,commands):
    with tempfile.TemporaryDirectory(prefix='qbrain-trace-') as d:
        root=Path(d)/'诊断 space 😀';root.mkdir();project=root/'project';project.mkdir();outside=root/'outside';outside.mkdir()
        owned=root/'owned';owned.mkdir()
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
        env.update(HOME=str(root),USERPROFILE=str(root),LOCALAPPDATA=str(root),APPDATA=str(root),TEMP=str(root),TMP=str(root))
        data=root if os.name=='nt' else root/'.local'/'share'
        def check(ok,name):
            checks.append(dict(name=name,status='PASS' if ok else 'FAIL'))
            if not ok:raise AssertionError(name)
        def files():return {p.name:p.read_bytes() for p in owned.iterdir() if p.is_file() and (p.name.startswith('trace-') or p.name=='last-trace.json')}
        def load(path):return json.loads(path.read_text(encoding='utf-8'))
        for host in ('claude','codex'):
            brain='trace-'+host;session='raw-session-N47J-'+host;cfgpath=owned/(host+'-config.json')
            quote='I prefer N47J-'+host+'-private-marker as my logging prefix.'
            cfg=dict(version=1,host=host,project_root=str(project),brain_id=brain,source_id='default',enabled=True,
                     capture=True,extraction='local',fact_promotion=True,fact_recall=True,recall_bytes=8192,max_items=8)
            def config(**options):cfg.update(options);cfgpath.write_bytes(enc(cfg))
            def invoke(label,args,raw=b'',cwd=project):
                try:r=subprocess.run([str(binary),*args],cwd=cwd,env=env,input=raw,capture_output=True,timeout=20)
                except subprocess.TimeoutExpired:
                    commands.append(dict(name=host+':'+label,exit_code=None,expected_exit=0,timed_out=True));raise
                commands.append(dict(name=host+':'+label,exit_code=r.returncode,expected_exit=0))
                if r.returncode or r.stderr:raise AssertionError('unexpected process output: '+host+':'+label)
                return r.stdout
            def hook(label,event='UserPromptSubmit',cwd=project,raw=None,**fields):
                obj=dict(hook_event_name=event,session_id=session,cwd=str(cwd));obj.update(fields)
                out=invoke(label,['hook','--config',str(cfgpath)],enc(obj) if raw is None else raw,cwd)
                if len(out)>8193 or len(out.splitlines())!=1:raise AssertionError('unbounded Hook output')
                return json.loads(out)
            def slot(event='UserPromptSubmit'):return owned/f'trace-{host}-{event}.json'
            def ck(ok,name):check(ok,host+':'+name)
            def block(path):
                if path.exists():path.unlink()
                path.mkdir()
            def unblock(path):
                path.rmdir();temp=Path(str(path)+'.tmp')
                if temp.is_file():temp.unlink()
            invoke('init',['init','--brain',brain,'--no-default'])
            invoke('writeback',['config','set','memory.writeback','salient','--local','--brain',brain])
            config();other_before={k:v for k,v in files().items() if k.startswith('trace-') and not k.startswith('trace-'+host+'-')}
            hook('submit',prompt=quote,turn_id='first');submitted=slot().read_bytes();first=json.loads(submitted)
            ck(first['status']=='processed' and first['phase']=='complete' and first['capture_status']=='archived' and
               first['extraction_status']=='extracted' and first['fact_promotion_status']=='completed' and
               first['fact_promotion_counts']['created']==1,'automatic_pipeline_recorded')
            ck(submitted==(owned/'last-trace.json').read_bytes(),'last_matches_event')
            ck(all(x not in submitted.decode() for x in (quote,session,str(root),brain)),'no_original_text')
            hook('stop','Stop',last_assistant_message='Confirmed.');hook('end','SessionEnd')
            ck(slot().read_bytes()==submitted,'promotion_survives_stop_end')
            ck(load(owned/'last-trace.json')['event']=='SessionEnd' and slot('Stop').exists(),'compatibility_tracks_end')
            out=hook('start','SessionStart',session_id=session+'-new');started=load(slot('SessionStart'))
            ck(started['session_key']!=first['session_key'] and started['completed_at_unix_ms']>=first['completed_at_unix_ms'],'new_session_correlation')
            ck(quote in out.get('hookSpecificOutput',{}).get('additionalContext','') and started['output_bytes']==len(enc(out)),'context_unchanged')
            hook('secret',prompt='password=N47J-SENSITIVE-NEVER-TRACE');text=slot().read_text(encoding='utf-8')
            ck('N47J-SENSITIVE' not in text and 'password' not in text and load(slot())['status']=='processed','secret_not_recorded')
            before=files();raw=enc(dict(cwd=str(project),session_id=session,hook_event_name='Stop'))
            raw=raw[:-1]+b',"hook_event_name":"UserPromptSubmit"}'
            ck(hook('malformed',raw=raw)=={} and files()==before,'malformed_inert')
            config(enabled=False);ck(hook('disabled','SessionStart')=={} and files()==before,'disabled_inert');config(enabled=True)
            ck(hook('outside','SessionStart',cwd=outside)=={} and files()==before,'outside_inert')
            ck(hook('unknown','../unexpected')=={} and files()==before,'unknown_event_inert')
            oversized='I prefer '+('Z'*65536);hook('oversize',prompt=oversized,turn_id='too-long')
            failed=load(slot());ck(failed['status']=='failed' and failed['phase']=='capture','processing_failure_recorded')
            ck('ZZZZ' not in slot().read_text(encoding='utf-8') and 'exception' not in failed,'failure_has_no_input')
            hook('recover',prompt=quote,turn_id='recovery');ck(load(slot())['status']=='processed','recovery_after_failure')
            config(capture=False,fact_promotion=False)
            state_tmp=owned/'recall-state.json.tmp';state_tmp.mkdir()
            out=hook('state-failure','SessionStart');state_tmp.rmdir()
            ck(quote in out.get('hookSpecificOutput',{}).get('additionalContext',''),'state_failure_preserves_context')
            ck(load(slot('SessionStart'))['status']=='failed' and load(slot('SessionStart'))['phase']=='state','state_failure_phase')
            target=slot('SessionStart');latest=owned/'last-trace.json';block(target)
            out=hook('slot-failure','SessionStart')
            ck(quote in out.get('hookSpecificOutput',{}).get('additionalContext',''),'slot_failure_preserves_context')
            ck(load(latest)['status']=='processed' and load(latest)['event']=='SessionStart','slot_failure_other_file_succeeds');unblock(target)
            block(latest);out=hook('last-failure','SessionStart')
            ck(quote in out.get('hookSpecificOutput',{}).get('additionalContext',''),'latest_failure_preserves_context')
            ck(load(target)['status']=='processed','latest_failure_event_file_succeeds');unblock(latest)
            block(target);block(latest);out=hook('both-failure','SessionStart')
            ck(quote in out.get('hookSpecificOutput',{}).get('additionalContext',''),'both_diagnostics_nonblocking');unblock(target);unblock(latest)
            hook('precompact','PreCompact');hook('refresh-start','SessionStart');hook('refresh-submit',prompt='check prefix')
            for i in range(12):hook(f'repeat-end-{i}','SessionEnd',session_id=f'{session}-{i}')
            expected={f'trace-{host}-{e}.json' for e in ('SessionStart','UserPromptSubmit','Stop','PreCompact','SessionEnd')}
            found={p.name for p in owned.glob(f'trace-{host}-*.json')};ck(found==expected,'fixed_retention')
            ck(all(p.stat().st_size<=4096 and load(p)['format_version']==2 for p in owned.glob(f'trace-{host}-*.json')),'all_slots_bounded')
            db=data/'Qbrain'/'brains'/brain/'brain.db';saved=db.read_bytes()
            db.write_bytes(b'not-a-sqlite-database')
            out=hook('open-failure','SessionStart');db.write_bytes(saved)
            ck(out=={} and load(target)['status']=='failed' and load(target)['phase']=='open','corrupt_brain_failure_recorded')
            expected_key=sha((host+'\n'+brain+'\ndefault\n'+session).encode())
            ck(first['session_key']==expected_key and session not in json.dumps(files(),default=str),'session_key_not_raw')
            ck(all(load(owned/n)['host_consumption_confirmed'] is False for n in expected),'no_consumption_claim')
            ck(all(files().get(n)==value for n,value in other_before.items()),'host_slots_isolated')

def main():
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    checks=[];commands=[];script=Path(__file__).resolve();r=dict(result='FAIL',checks=checks,commands=commands,native_windows=os.name=='nt',real_host_consumption_verified=False)
    try:
        binary=a.binary.resolve(strict=True);r.update(binary_sha256=sha(binary.read_bytes()),script_sha256=sha(script.read_bytes()))
        run(binary,checks,commands)
        if len(checks)!=len(EXPECTED_CHECKS) or {x['name'] for x in checks}!=EXPECTED_CHECKS or tuple(x['name'] for x in commands)!=COMMAND_SCHEDULE:raise AssertionError('incomplete schedule')
        r['result']='PASS'
    except Exception as e:
        r.update(error_type=type(e).__name__,error=str(e))
        if not any(c['status']=='FAIL' for c in checks):checks.append(dict(name='execution_interrupted',status='FAIL'))
    r.update(provenance(script));r['check_count']=len(checks);r['counts']={k:sum(c['status']==k.upper() for c in checks) for k in ('pass','fail')};r['counts']['total']=len(checks)
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'result':r['result'],'counts':r['counts'],'commands':len(commands),'error':r.get('error')},ensure_ascii=True))
    return 0 if r['result']=='PASS' else 1
if __name__=='__main__':
    for s in (sys.stdout,sys.stderr):
        if hasattr(s,'reconfigure'):s.reconfigure(encoding='utf-8',errors='replace')
    raise SystemExit(main())
