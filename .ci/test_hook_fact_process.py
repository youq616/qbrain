"""Real Hook subprocess fixtures. Not live Claude/Codex consumption or measured egress."""
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

HOSTS=('claude','codex')
CASES=('no_optional_schema_on_read','default_off_legacy_context','explicit_false_matches_default',
       'optin_recent_complete_groups','unified_envelope_budget','fact_raw_quote_suppressed',
       'prompt_retains_nonmatching_counterclaim','repeated_fact_context_is_refreshed',
       'ordinary_memory_dedup_preserved','tiny_budget_no_partial_or_raw_bypass','trace_has_no_quotes',
       'config_false_restores_legacy_path','strict_boolean_flag','wrong_project_no_context',
       'wrong_source_no_context','sensitive_prompt_no_context_or_capture','empty_prompt_no_enumeration',
       'stop_no_fact_context','compaction_refresh','enabled_false_inert','capture_independent_of_fact_optin',
       'retracted_quote_not_reintroduced','revoked_counterclaim_reflected','forgotten_anchor_absent',
       'no_fact_or_provider_jobs_created','no_model_consumption_claim')
EXPECTED_CHECKS=frozenset(h+':'+c for h in HOSTS for c in CASES)
EXPECTED_COMMAND_COUNT=72  # Fixed full native process schedule, all expected exit 0.

def encode(v):return json.dumps(v,ensure_ascii=False,separators=(',',':')).encode('utf-8')
def provenance(script):
    root=script.resolve().parents[1]
    if not (root/'.git').exists():return {'source_commit':None,'tracked_tree_clean':False}
    try:
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,stderr=subprocess.PIPE,text=True).strip()
        clean=subprocess.run(['git','diff','--quiet','HEAD','--'],cwd=root,stderr=subprocess.PIPE).returncode==0
        return {'source_commit':head if clean else None,'head_commit':head,'tracked_tree_clean':clean,
                'source_tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=root,stderr=subprocess.PIPE,text=True).strip()}
    except (OSError,subprocess.SubprocessError):return {'source_commit':None,'tracked_tree_clean':False}

def run(binary,checks,commands):
    with tempfile.TemporaryDirectory(prefix='qbrain-hook-facts-') as d:
        root=Path(d)/'自动召回 space 😀';root.mkdir();project=root/'project';project.mkdir();outside=root/'outside';outside.mkdir()
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
        env.update(HOME=str(root),LOCALAPPDATA=str(root),USERPROFILE=str(root),APPDATA=str(root),TEMP=str(root),TMP=str(root))
        data=root if os.name=='nt' else root/'.local'/'share'
        for host in HOSTS:
            def check(ok,name):
                checks.append({'name':host+':'+name,'status':'PASS' if ok else 'FAIL'})
                if not ok:raise AssertionError(host+':'+name)
            brain='hook-facts-'+host;dbpath=data/'Qbrain'/'brains'/brain/'brain.db'
            settings=root/host;settings.mkdir();config=settings/'config.json'
            cfg=dict(version=1,host=host,project_root=str(project),brain_id=brain,source_id='alpha',enabled=True,
                     capture=False,extraction='local',recall_bytes=8192,max_items=8)
            def configure(**kwargs):cfg.update(kwargs);config.write_bytes(encode(cfg))
            def invoke(args,p=None,cwd=project):
                try:r=subprocess.run([str(binary),*args],input=b'' if p is None else encode(p),cwd=cwd,env=env,capture_output=True,timeout=30)
                except subprocess.TimeoutExpired:
                    commands.append({'args':args[:2],'exit_code':None,'expected_exit':0,'timed_out':True});raise
                commands.append({'args':args[:2],'exit_code':r.returncode,'expected_exit':0})
                if r.returncode:
                    commands[-1]['stderr_excerpt']=r.stderr.decode('utf-8',errors='replace').replace(str(root),'<fixture>')[:1024]
                    raise AssertionError('unexpected command exit')
                return r.stdout
            def cli(args,p=None):return json.loads(invoke([*args,'--brain',brain],p).decode('utf-8-sig'))
            def sql(q,params=()):
                with closing(sqlite3.connect(dbpath,timeout=5)) as db:
                    db.execute('PRAGMA foreign_keys=ON');rows=db.execute(q,params).fetchall();db.commit();return rows[0][0] if rows else None
            def hook(kind,session='test',prompt=None,cwd=project,**extra):
                e=dict(hook_event_name=kind,session_id=session,cwd=str(cwd),**extra)
                if prompt is not None:e['prompt']=prompt
                raw=invoke(['hook','--config',str(config)],e,cwd)
                if len(raw)>cfg['recall_bytes']+1 or len(raw.splitlines())!=1:raise AssertionError('invalid serialized Hook output')
                return json.loads(raw)
            def payload(out):return json.loads(out['hookSpecificOutput']['additionalContext'].split('\n',1)[1])
            def seed(tag,quote):
                e=cli(['memory','capture','--source','alpha','--manual'],dict(session_id='seed',fragment_id=tag,messages=[dict(role='user',content=quote)]))['event_id']
                cli(['memory','extract','--source','alpha','--event',e])
                return dict(event=e,item=sql('SELECT item_id FROM memory_items WHERE event_id=?',(e,)),quote=quote)
            def fact(action,p):return cli(['fact',action,'--source','alpha'],p)
            def claim(e):return fact('create',dict(item_id=e['item'],predicate='preference.editor'))
            invoke(['init','--brain',brain]);sql("INSERT INTO sources(id,name) VALUES('alpha','alpha'),('beta','beta')")
            sql("INSERT INTO config(key,value) VALUES('memory.writeback','salient')")
            configure(fact_recall=True);n=sql('SELECT COUNT(*) FROM sqlite_master');hook('SessionStart')
            check(sql('SELECT COUNT(*) FROM sqlite_master')==n and sql("SELECT COUNT(*) FROM sqlite_master WHERE name='memory_fact_module'")==0,'no_optional_schema_on_read')
            a=seed('a','我偏好 needle 命令行，不使用图形菜单。😀');b=seed('b','I prefer graphical menus without a terminal.')
            f,g=claim(a),claim(b);fact('contradict',dict(fact_id=f['fact_id'],other_id=g['fact_id']))
            duplicate=seed('dup',a['quote']);ordinary=seed('ordinary','I prefer needle unrelated history.')
            del cfg['fact_recall'];configure();before=hook('SessionStart',session='default')
            check(isinstance(payload(before),list),'default_off_legacy_context')
            configure(fact_recall=False);off=hook('SessionStart',session='false')
            check(off==before,'explicit_false_matches_default')
            configure(fact_recall=True);recent=hook('SessionStart',session='enabled');p=payload(recent)
            check(len(p['fact_groups'])==2 and all(len(i['facts'])==2 for i in p['fact_groups']),'optin_recent_complete_groups')
            check(len(encode(recent))<=8192 and not any(k in recent for k in ('decision','continue','permissionDecision')),'unified_envelope_budget')
            check(len(p['memories'])==1 and p['memories'][0]['quote']==ordinary['quote'],'fact_raw_quote_suppressed')
            prompt=hook('UserPromptSubmit',session='prompt',prompt='Please check needle');p=payload(prompt)
            check(len(p['fact_groups'])==1 and p['fact_groups'][0]['facts'][1]['object']==b['quote'],'prompt_retains_nonmatching_counterclaim')
            repeated=hook('UserPromptSubmit',session='prompt',prompt='Please check needle');p=payload(repeated)
            check(len(p['fact_groups'])==1 and len(p['fact_groups'][0]['facts'])==2,'repeated_fact_context_is_refreshed')
            check(p['memories']==[],'ordinary_memory_dedup_preserved')
            configure(recall_bytes=512);tiny=hook('UserPromptSubmit',session='tiny',prompt='needle');trace=json.loads((settings/'last-trace.json').read_text(encoding='utf-8'))
            check((tiny=={} or (payload(tiny)['fact_groups']==[] and payload(tiny)['memories']==[])) and trace['context_truncated'] is True,'tiny_budget_no_partial_or_raw_bypass')
            check(a['quote'] not in json.dumps(trace,ensure_ascii=False) and 'prompt' not in trace and trace['output_bytes']<=512,'trace_has_no_quotes')
            configure(fact_recall=False,recall_bytes=8192);check(hook('SessionStart',session='restore')==before,'config_false_restores_legacy_path')
            configure(fact_recall='true');check(hook('SessionStart',session='bad')=={},'strict_boolean_flag')
            configure(fact_recall=True);check(hook('SessionStart',session='outside',cwd=outside)=={},'wrong_project_no_context')
            configure(source_id='beta');check(hook('SessionStart',session='beta')=={},'wrong_source_no_context');configure(source_id='alpha')
            events=sql('SELECT COUNT(*) FROM memory_events');configure(capture=True)
            check(hook('UserPromptSubmit',session='secret',prompt='password=synthetic-do-not-store')=={} and sql('SELECT COUNT(*) FROM memory_events')==events,'sensitive_prompt_no_context_or_capture')
            configure(capture=False);check(hook('UserPromptSubmit',session='empty',prompt='')=={},'empty_prompt_no_enumeration')
            check(hook('Stop',last_assistant_message='I prefer an invented user claim.')=={},'stop_no_fact_context')
            hook('PreCompact',session='prompt');fresh=hook('UserPromptSubmit',session='prompt',prompt='needle')
            check(len(payload(fresh)['fact_groups'])==1 and len(payload(fresh)['memories'])==1,'compaction_refresh')
            configure(enabled=False);check(hook('SessionStart',session='disabled')=={},'enabled_false_inert');configure(enabled=True)
            configure(capture=True);hook('UserPromptSubmit',session='capture',prompt='I prefer brand new isolated capture.',turn_id='capture')
            check(sql('SELECT COUNT(*) FROM memory_events')==events+1 and sql('SELECT COUNT(*) FROM memory_facts')==2,'capture_independent_of_fact_optin');configure(capture=False)
            fact('retract',dict(fact_id=f['fact_id'],expected_revision=2));after=hook('UserPromptSubmit',session='retracted',prompt='needle')
            check(a['quote'] not in json.dumps(after,ensure_ascii=False),'retracted_quote_not_reintroduced')
            r=hook('SessionStart',session='counter');check(len(payload(r)['fact_groups'])==1 and len(payload(r)['fact_groups'][0]['facts'])==1,'revoked_counterclaim_reflected')
            cli(['memory','forget','--source','alpha','--event',a['event']]);cli(['memory','forget','--source','alpha','--event',duplicate['event']])
            check(a['quote'] not in json.dumps(hook('SessionStart',session='forgotten'),ensure_ascii=False),'forgotten_anchor_absent')
            check(sql('SELECT COUNT(*) FROM jobs')==0 and sql('SELECT COUNT(*) FROM memory_facts')==1,'no_fact_or_provider_jobs_created')
            trace=json.loads((settings/'last-trace.json').read_text(encoding='utf-8'));state=json.loads((settings/'recall-state.json').read_text(encoding='utf-8'))
            check(trace['host_consumption_confirmed'] is False and a['quote'] not in json.dumps(state,ensure_ascii=False) and b['quote'] not in json.dumps(state,ensure_ascii=False),'no_model_consumption_claim')

def main():
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--report',type=Path,required=True);args=p.parse_args()
    checks=[];commands=[];r={'result':'FAIL','checks':checks,'commands':commands,'native_windows':os.name=='nt','real_host_consumption_verified':False}
    script=Path(__file__).resolve()
    try:
        binary=args.binary.resolve(strict=True);r.update(binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(script.read_bytes()).hexdigest())
        run(binary,checks,commands)
        if len(checks)!=len(EXPECTED_CHECKS) or {c['name'] for c in checks}!=EXPECTED_CHECKS:raise AssertionError('case registry mismatch')
        r['result']='PASS'
    except Exception as e:
        r.update(error_type=type(e).__name__,error=str(e))
        if not any(c['status']=='FAIL' for c in checks):checks.append({'name':'execution_interrupted','status':'FAIL'})
    r.update(provenance(script));r['check_count']=len(checks);r['counts']={'total':len(checks),'pass':sum(c['status']=='PASS' for c in checks),'fail':sum(c['status']=='FAIL' for c in checks)}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'result':r['result'],'counts':r['counts'],'commands':len(commands),'error':r.get('error')},ensure_ascii=True));return 0 if r['result']=='PASS' else 1

if __name__=='__main__':
    for s in (sys.stdout,sys.stderr):
        if hasattr(s,'reconfigure'):s.reconfigure(encoding='utf-8',errors='replace')
    raise SystemExit(main())
