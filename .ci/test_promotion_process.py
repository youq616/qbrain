"""Real local promotion CLI/MCP/Hook fixtures; not authenticated host consumption."""
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
import time
from test_hook_fact_process import provenance

CORE_CASES=('empty_event_no_schema','complete_batch','whole_quote_no_truth_inference','replay_no_revision_drift',
 'mcp_write_default_denied','mcp_allowed_replay','mcp_source_denied','mcp_payload_rejected','mcp_unknown_field_rejected',
 'mcp_strict_event_type','six_tools_unchanged','equal_event_attached','forget_retains_other_support','retired_repeat_skipped',
 'missing_id_rejected','invalid_id_rejected','wrong_source_rejected','irrelevant_cli_flag_rejected','tampered_batch_atomic',
 'local_only','expired_target_renewal','renewal_preserves_old_expiry','renewal_replay_idempotent','prior_recall_compatible','no_inferred_relations','no_model_jobs')
HOOK_CASES=('default_no_capture_or_promotion','promotion_needs_capture','capture_only_no_facts','strict_boolean',
 'promotion_needs_local','brain_writeback_off_inert','automatic_current_event_promoted','no_current_quote_in_prior_recall','no_implicit_fact_recall',
 'following_start_recalls_fact','replayed_hook_is_duplicate','assistant_not_promoted','secret_not_captured',
 'failure_distinct_from_capture','failure_no_partial_fact','explicit_retry_after_failure','disabled_no_new_facts',
 'source_isolation','trace_contains_no_quote','no_model_consumption_claim','no_jobs')
EXPECTED_CHECKS=frozenset(['core:'+c for c in CORE_CASES]+[h+':'+c for h in ('claude','codex') for c in HOOK_CASES])
EXPECTED_COMMAND_COUNT=77  # Replaced after fixed-schedule execution; not inferred from submitted reports.
def enc(v):return json.dumps(v,ensure_ascii=False,separators=(',',':')).encode('utf-8')

def run(binary,checks,commands):
    with tempfile.TemporaryDirectory(prefix='qbrain-promotion-') as d:
        root=Path(d)/'事实整理 space 😀';root.mkdir();project=root/'project';project.mkdir()
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
        env.update(HOME=str(root),USERPROFILE=str(root),APPDATA=str(root),LOCALAPPDATA=str(root),TEMP=str(root),TMP=str(root))
        data=root if os.name=='nt' else root/'.local'/'share'
        def invoke(args,p=None,expected=0,raw=None):
            try:r=subprocess.run([str(binary),*args],input=raw if raw is not None else (b'' if p is None else enc(p)),cwd=project,env=env,capture_output=True,timeout=30)
            except subprocess.TimeoutExpired:
                commands.append(dict(args=args[:2],exit_code=None,expected_exit=expected,timed_out=True));raise
            record=dict(args=args[:2],exit_code=r.returncode,expected_exit=expected);commands.append(record)
            if r.returncode!=expected:
                record['stderr_excerpt']=r.stderr.decode('utf-8',errors='replace').replace(str(root),'<fixture>')[:1024]
                raise AssertionError('unexpected child exit '+str(len(commands)))
            return r.stdout
        def check(ok,name):
            checks.append(dict(name=name,status='PASS' if ok else 'FAIL'))
            if not ok:raise AssertionError(name)
        def dbpath(brain):return data/'Qbrain'/'brains'/brain/'brain.db'
        def sql(brain,q,p=(),all_rows=False):
            with closing(sqlite3.connect(dbpath(brain),timeout=5)) as db:
                db.execute('PRAGMA foreign_keys=ON');rows=db.execute(q,p).fetchall();db.commit()
                return rows if all_rows else (rows[0][0] if rows else None)
        def init(brain):
            invoke(['init','--brain',brain]);sql(brain,"INSERT INTO sources(id,name) VALUES('alpha','alpha'),('beta','beta')")
            sql(brain,"INSERT INTO config(key,value) VALUES('memory.writeback','all'),('mcp.allowed_sources','alpha')")
        def cli(brain,args,p=None,expected=0):return json.loads(invoke([*args,'--brain',brain],p,expected))
        def seed(brain,tag,quotes,expires=0):
            event=cli(brain,['memory','capture','--source','alpha','--manual'],dict(session_id='promotion-core',fragment_id=tag,expires_at=expires,messages=[dict(role=role,content=q) for role,q in quotes]))['event_id']
            cli(brain,['memory','extract','--source','alpha','--event',event]);return event
        def promote(brain,event,expected=0,source='alpha'):return cli(brain,['fact','promote','--source',source,'--event',event],expected=expected)
        brain='promote-core';init(brain)
        e=seed(brain,'none',[('user','Hello without a supported marker.')]);r=promote(brain,e)
        check(r['counts']['total']==0 and sql(brain,"SELECT COUNT(*) FROM sqlite_master WHERE name='memory_facts'")==0,'core:empty_event_no_schema')
        quote='我偏好不用图形界面，而用命令行。😀'
        e=seed(brain,'first',[('user',quote),('user','I decided not to deploy.'),('assistant','I prefer assistant fiction.')]);r=promote(brain,e)
        check(r['counts']['created']==2 and r['counts']['total']==2,'core:complete_batch')
        facts=cli(brain,['fact','read','--source','alpha'])['items'];f=next(x for x in facts if x['object']==quote)
        check(f['confidence'] is None and f['predicate']=='memory.preference' and f['evidence'][0]['event_id']==e and quote not in json.dumps(r,ensure_ascii=False),'core:whole_quote_no_truth_inference')
        before=sql(brain,'SELECT fact_id,revision FROM memory_facts ORDER BY fact_id',all_rows=True);r=promote(brain,e)
        check(r['counts']['duplicate']==2 and sql(brain,'SELECT fact_id,revision FROM memory_facts ORDER BY fact_id',all_rows=True)==before,'core:replay_no_revision_drift')
        def rpc(args,write=False,listing=False):
            request=[dict(jsonrpc='2.0',id=0,method='initialize',params={}),dict(jsonrpc='2.0',method='notifications/initialized'),
             dict(jsonrpc='2.0',id=1,method='tools/list' if listing else 'tools/call',params={} if listing else dict(name='memory_write',arguments=args))]
            raw=b'\n'.join(enc(v) for v in request)+b'\n'
            response=invoke(['serve','--brain',brain,'--tool-profile','memory',*(['--allow-write'] if write else [])],raw=raw)
            return next(v['result'] for v in map(json.loads,response.decode('utf-8-sig').splitlines()) if v.get('id')==1)
        p=dict(action='fact_promote',source_id='alpha',event_id=e)
        check('write_denied' in str(rpc(p)),'core:mcp_write_default_denied')
        result=rpc(p,True);check(not result.get('isError') and json.loads(result['content'][-1]['text'])['counts']['duplicate']==2,'core:mcp_allowed_replay')
        check('source_not_allowed' in str(rpc({**p,'source_id':'beta'},True)),'core:mcp_source_denied')
        for extra,name in [({'payload':'{}'},'mcp_payload_rejected'),({'unexpected':'yes'},'mcp_unknown_field_rejected'),({'event_id':True},'mcp_strict_event_type')]:
            check(rpc({**p,**extra},True).get('isError') is True,'core:'+name)
        check({t['name'] for t in rpc({},listing=True)['tools']}=={'search','memory_read','memory_write','context_read','context_write','get_page'},'core:six_tools_unchanged')
        second=seed(brain,'second',[('user',quote)]);r=promote(brain,second)
        check(r['counts']['attached']==1 and r['items'][0]['fact_id']==f['fact_id'],'core:equal_event_attached')
        cli(brain,['memory','forget','--source','alpha','--event',e]);f=cli(brain,['fact','read','--source','alpha','--id',f['fact_id']])['items'][0]
        check(f['evidence_count']==1 and f['evidence'][0]['event_id']==second,'core:forget_retains_other_support')
        cli(brain,['fact','retract','--source','alpha'],dict(fact_id=f['fact_id'],expected_revision=f['revision']))
        third=seed(brain,'third',[('user',quote)]);r=promote(brain,third)
        check(r['counts']['skipped_retired']==1 and sql(brain,"SELECT COUNT(*) FROM memory_facts WHERE status='active'")==0,'core:retired_repeat_skipped')
        check(cli(brain,['fact','promote','--source','alpha'],expected=1)['error']['code']=='fact_invalid_id','core:missing_id_rejected')
        check(promote(brain,'bad',1)['error']['code']=='fact_invalid_id','core:invalid_id_rejected')
        check(promote(brain,third,1,'beta')['error']['code']=='fact_event_unavailable','core:wrong_source_rejected')
        check(cli(brain,['fact','promote','--event',third,'--stdin'],expected=1)['error']['code']=='invalid_cli_argument','core:irrelevant_cli_flag_rejected')
        damaged=seed(brain,'damaged',[('user','I prefer first valid.'),('user','I decided second valid.')]);sql(brain,"UPDATE memory_items SET quote='forged' WHERE event_id=? AND message_index=1",(damaged,))
        n=sql(brain,'SELECT COUNT(*) FROM memory_facts');r=promote(brain,damaged,1)
        check(r['error']['code']=='fact_evidence_unavailable' and sql(brain,'SELECT COUNT(*) FROM memory_facts')==n,'core:tampered_batch_atomic')
        sql(brain,"UPDATE memory_events SET method='model' WHERE event_id=?",(third,));check(promote(brain,third,1)['error']['code']=='fact_local_extraction_required','core:local_only')
        check(cli(brain,['fact','recall','--source','alpha','--query','命令行'])['items']==[],'core:prior_recall_compatible')
        check(sql(brain,'SELECT COUNT(*) FROM memory_fact_relations')==0,'core:no_inferred_relations');check(sql(brain,'SELECT COUNT(*) FROM jobs')==0,'core:no_model_jobs')
        until=int(time.time())+2;renew_quote='I prefer renewable current support without reviving expired support.'
        old=seed(brain,'renew-old',[('user',renew_quote)],until);old_fact=promote(brain,old)['items'][0]
        time.sleep(max(0,until+1-time.time()))
        current=seed(brain,'renew-fresh',[('user',renew_quote)]);renewed=promote(brain,current)
        now_fact=cli(brain,['fact','read','--source','alpha','--id',old_fact['fact_id']])['items'][0]
        check(renewed['counts']['attached']==1 and renewed['items'][0]['fact_id']==old_fact['fact_id'] and now_fact['revision']==2 and
              now_fact['evidence_count']==1 and now_fact['evidence'][0]['event_id']==current,'core:expired_target_renewal')
        expired=promote(brain,old,1)
        check(expired['error']['code']=='fact_event_unavailable' and sql(brain,'SELECT expires_at FROM memory_events WHERE event_id=?',(old,))==until,'core:renewal_preserves_old_expiry')
        check(promote(brain,current)['counts']['duplicate']==1 and sql(brain,'SELECT revision FROM memory_facts WHERE fact_id=?',(old_fact['fact_id'],))==2,'core:renewal_replay_idempotent')
        for host in ('claude','codex'):
            brain='promote-'+host;init(brain);settings=root/host;settings.mkdir();cfgpath=settings/'config.json'
            cfg=dict(version=1,host=host,project_root=str(project),brain_id=brain,source_id='alpha',enabled=True,capture=False,extraction='local',recall_bytes=8192,max_items=8)
            def config(**kwargs):cfg.update(kwargs);cfgpath.write_bytes(enc(cfg))
            def hook(kind='UserPromptSubmit',prompt=None,**extra):
                event=dict(hook_event_name=kind,session_id='session',cwd=str(project),**extra)
                if prompt is not None:event['prompt']=prompt
                raw=invoke(['hook','--config',str(cfgpath)],event)
                if len(raw)>8193 or len(raw.splitlines())!=1:raise AssertionError('bad Hook envelope')
                return json.loads(raw)
            def trace():return json.loads((settings/'last-trace.json').read_text(encoding='utf-8'))
            def count():return sql(brain,'SELECT COUNT(*) FROM memory_facts') if sql(brain,"SELECT COUNT(*) FROM sqlite_master WHERE name='memory_facts'") else 0
            config();check(hook(prompt='I prefer default inactive.')=={} and count()==0,host+':default_no_capture_or_promotion')
            config(fact_promotion=True);check(hook(prompt='I prefer no capture.')=={} and sql(brain,"SELECT COUNT(*) FROM sqlite_master WHERE name='memory_module'")==0,host+':promotion_needs_capture')
            config(capture=True,fact_promotion=False);hook(prompt='I prefer prior ordinary history.');check(count()==0,host+':capture_only_no_facts')
            n=sql(brain,'SELECT COUNT(*) FROM memory_events');config(fact_promotion='true');check(hook(prompt='I prefer invalid boolean.')=={} and sql(brain,'SELECT COUNT(*) FROM memory_events')==n,host+':strict_boolean')
            config(fact_promotion=True,extraction='deferred');check(hook(prompt='I prefer deferred invalid.')=={} and sql(brain,'SELECT COUNT(*) FROM memory_events')==n,host+':promotion_needs_local')
            config(extraction='local');sql(brain,"UPDATE config SET value='off' WHERE key='memory.writeback'")
            hook(prompt='I prefer blocked by brain policy.');check(count()==0 and trace()['fact_promotion_status']=='not_run',host+':brain_writeback_off_inert')
            sql(brain,"UPDATE config SET value='all' WHERE key='memory.writeback'");quote='I prefer needle '+host+' complete original choice.'
            out=hook(prompt=quote,turn_id='new');t=trace();check(count()==1 and t['fact_promotion_status']=='completed' and t['fact_promotion_counts']['created']==1,host+':automatic_current_event_promoted')
            check(quote not in json.dumps(out),host+':no_current_quote_in_prior_recall')
            out=hook('SessionStart');check(isinstance(json.loads(out['hookSpecificOutput']['additionalContext'].split('\n',1)[1]),list),host+':no_implicit_fact_recall')
            config(fact_recall=True);out=hook('SessionStart');context=json.loads(out['hookSpecificOutput']['additionalContext'].split('\n',1)[1]);check(len(context['fact_groups'])==1 and context['fact_groups'][0]['facts'][0]['object']==quote,host+':following_start_recalls_fact')
            hook(prompt=quote,turn_id='new');check(trace()['fact_promotion_counts']['duplicate']==1 and count()==1,host+':replayed_hook_is_duplicate')
            hook('Stop',last_assistant_message='I prefer assistant claim.');check(count()==1 and trace()['fact_promotion_status']=='not_run',host+':assistant_not_promoted')
            n=sql(brain,'SELECT COUNT(*) FROM memory_events');hook(prompt='password=synthetic-do-not-store');check(count()==1 and sql(brain,'SELECT COUNT(*) FROM memory_events')==n,host+':secret_not_captured')
            sql(brain,"CREATE TRIGGER promotion_failure BEFORE INSERT ON memory_facts BEGIN SELECT RAISE(ABORT,'injected');END")
            broken='I prefer injected failure '+host+'.';hook(prompt=broken,turn_id='failure');t=trace()
            check(t['extraction_status']=='extracted' and t['fact_promotion_status']=='failed',host+':failure_distinct_from_capture');check(count()==1,host+':failure_no_partial_fact')
            failed_event=sql(brain,'SELECT event_id FROM memory_items WHERE quote=?',(broken,));sql(brain,'DROP TRIGGER promotion_failure');check(promote(brain,failed_event)['counts']['created']==1,host+':explicit_retry_after_failure')
            config(fact_promotion=False);hook(prompt='I prefer disabled promotion.');check(count()==2,host+':disabled_no_new_facts')
            config(source_id='beta',capture=False);check(hook('SessionStart')=={},host+':source_isolation')
            t=trace();check(quote not in json.dumps(t) and broken not in json.dumps(t) and 'prompt' not in t,host+':trace_contains_no_quote')
            check(t['host_consumption_confirmed'] is False,host+':no_model_consumption_claim');check(sql(brain,'SELECT COUNT(*) FROM jobs')==0,host+':no_jobs')

def main():
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    script=Path(__file__).resolve();report=dict(result='FAIL',checks=[],commands=[],native_windows=os.name=='nt',scope='synthetic CLI/MCP/Hook; no authenticated client',real_host_consumption_verified=False)
    try:
        binary=a.binary.resolve(strict=True);report.update(binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(script.read_bytes()).hexdigest())
        run(binary,report['checks'],report['commands'])
        if len(report['checks'])!=len(EXPECTED_CHECKS) or {c['name'] for c in report['checks']}!=EXPECTED_CHECKS:raise AssertionError('missing/duplicate named check')
        if EXPECTED_COMMAND_COUNT and len(report['commands'])!=EXPECTED_COMMAND_COUNT:raise AssertionError('command schedule mismatch')
        report['result']='PASS'
    except Exception as e:
        report.update(error_type=type(e).__name__,error=str(e))
        if not any(c['status']=='FAIL' for c in report['checks']):report['checks'].append(dict(name='execution_interrupted',status='FAIL'))
    report['check_count']=len(report['checks']);report['counts']={s:sum(c['status']==s.upper() for c in report['checks']) for s in ('pass','fail')};report['counts']['total']=report['check_count']
    report.update(provenance(script));a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,ensure_ascii=False));return 0 if report['result']=='PASS' else 1
if __name__=='__main__':
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace')
    raise SystemExit(main())
