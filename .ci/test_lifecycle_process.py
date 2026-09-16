"""Disposable real CLI/MCP/Hook lifecycle checks; no authenticated host claim."""
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

EXPECTED_CHECKS=frozenset(('lazy_read','restore_no_migration','archive_revision','unchanged_evidence','anchor_hidden',
 'inspect_archived','read_remains_explicit','stale_revision','idempotent_archive','default_write_denied',
 'allowed_restore','restored_recall','source_denied','foreign_fact_unavailable','strict_payload','strict_revision',
 'strict_read_type','strict_read_fields','strict_cli','six_tools','counterclaim_kept','conflicts_visible',
 'all_anchors_archived','hook_no_bypass','promotion_keeps_policy','restore_then_retire','retired_restore_denied',
 'forgotten_metadata_removed','advisory_stale','new_support_fresh','unknown_clock','budget_complete','read_only',
 'no_model_jobs','real_backup','legacy_version_preserved'))
EXPECTED_COMMAND_COUNT=58  # Fixed suite; expected negative exits are counted explicitly.

def enc(v):return json.dumps(v,ensure_ascii=False,separators=(',',':')).encode('utf-8')

def run(binary,checks,commands):
    with tempfile.TemporaryDirectory(prefix='qbrain-lifecycle-') as d:
        root=Path(d)/'生命周期 space 😀';root.mkdir();project=root/'project';project.mkdir()
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
        env.update(HOME=str(root),USERPROFILE=str(root),LOCALAPPDATA=str(root),APPDATA=str(root),TEMP=str(root),TMP=str(root))
        data=root if os.name=='nt' else root/'.local'/'share'
        dbpath=data/'Qbrain'/'brains'/'lifecycle-ci'/'brain.db'
        def invoke(args,p=None,expected=0,raw=None):
            record=dict(args=args[:2],expected_exit=expected)
            try:r=subprocess.run([str(binary),*args,'--brain','lifecycle-ci'],input=raw if raw is not None else (b'' if p is None else enc(p)),cwd=project,env=env,capture_output=True,timeout=30)
            except subprocess.TimeoutExpired:
                record.update(exit_code=None,timed_out=True);commands.append(record);raise
            record['exit_code']=r.returncode;commands.append(record)
            if r.returncode!=expected:
                record['stderr_excerpt']=r.stderr.decode('utf-8',errors='replace').replace(str(root),'<fixture>')[:1024]
                record['stdout_excerpt']=r.stdout.decode('utf-8',errors='replace').replace(str(root),'<fixture>')[:1024]
                raise AssertionError('Unexpected process exit '+str(len(commands)))
            return r.stdout
        def cli(args,p=None,expected=0):return json.loads(invoke(args,p,expected))
        def check(ok,name):
            checks.append(dict(name=name,status='PASS' if ok else 'FAIL'))
            if not ok:raise AssertionError(name)
        def sql(q,p=(),all_rows=False):
            with closing(sqlite3.connect(dbpath,timeout=5)) as db:
                db.execute('PRAGMA foreign_keys=ON');rows=db.execute(q,p).fetchall();db.commit()
                return rows if all_rows else (rows[0][0] if rows else None)
        def read(id):return cli(['fact','read','--source','alpha','--id',id])['items'][0]
        def inspect(id='',days=180,budget=8192):return cli(['fact','lifecycle','--source','alpha','--id',id,'--stale-after-days',str(days),'--max-bytes',str(budget)])
        def seed(tag,quote):
            event=cli(['memory','capture','--source','alpha','--manual'],dict(session_id='lifecycle-ci',fragment_id=tag,messages=[dict(role='user',content=quote)]))['event_id']
            cli(['memory','extract','--source','alpha','--event',event])
            f=cli(['fact','promote','--source','alpha','--event',event])['items'][0]
            return f,event
        def write(action,f,revision,expected=0):return cli(['fact',action,'--source','alpha'],dict(fact_id=f['fact_id'],expected_revision=revision),expected)
        def rpc(name,args,write=False,listing=False):
            request=[dict(jsonrpc='2.0',id=0,method='initialize',params={}),dict(jsonrpc='2.0',method='notifications/initialized'),dict(jsonrpc='2.0',id=1,method='tools/list' if listing else 'tools/call',params={} if listing else dict(name=name,arguments=args))]
            raw=b'\n'.join(enc(x) for x in request)+b'\n'
            output=invoke(['serve','--tool-profile','memory',*(['--allow-write'] if write else [])],raw=raw)
            return next(v['result'] for v in map(json.loads,output.decode('utf-8-sig').splitlines()) if v.get('id')==1)
        invoke(['init']);sql("INSERT INTO sources(id,name) VALUES('alpha','alpha'),('beta','beta')")
        sql("INSERT INTO config(key,value) VALUES('memory.writeback','all'),('mcp.allowed_sources','alpha')")
        version=sql('SELECT MAX(version) FROM schema_version')
        first=inspect();check(first['initialized'] is False and first['items']==[],'lazy_read')
        f,event=seed('one','我偏好使用命令行而非图形界面。😀')
        check(write('restore',f,1)['duplicate'] is True and sql("SELECT COUNT(*) FROM sqlite_master WHERE name='memory_fact_lifecycle_module'")==0,'restore_no_migration')
        before=read(f['fact_id']);arch=write('archive',f,1)
        check(arch['archived'] is True and arch['revision']==2,'archive_revision')
        after=read(f['fact_id']);check(after['evidence']==before['evidence'] and after['object']==before['object'] and after['status']=='active','unchanged_evidence')
        check(cli(['fact','recall','--source','alpha','--query','命令行'])['items']==[],'anchor_hidden')
        check(inspect(f['fact_id'])['items'][0]['lifecycle']['archived'] is True,'inspect_archived')
        check(after['object']==before['object'],'read_remains_explicit')
        check(write('restore',f,1,1)['error']['code']=='fact_revision_conflict','stale_revision')
        check(write('archive',f,2)['duplicate'] is True,'idempotent_archive')
        args=dict(source_id='alpha',action='fact_restore',payload=enc(dict(fact_id=f['fact_id'],expected_revision=2)).decode())
        check('write_denied' in str(rpc('memory_write',args)),'default_write_denied')
        response=rpc('memory_write',args,write=True)
        check(not response.get('isError') and json.loads(response['content'][-1]['text'])['revision']==3,'allowed_restore')
        check(cli(['fact','recall','--source','alpha','--query','命令行'])['items'][0]['match_fact_id']==f['fact_id'],'restored_recall')
        check('source_not_allowed' in str(rpc('memory_read',dict(source_id='beta',view='lifecycle',fact_id=f['fact_id']))),'source_denied')
        bad=cli(['fact','archive','--source','beta'],dict(fact_id=f['fact_id'],expected_revision=3),1)
        check(bad['error']['code']=='fact_not_found','foreign_fact_unavailable')
        bad=cli(['fact','archive','--source','alpha'],dict(fact_id=f['fact_id'],expected_revision=3,archived=False),1)
        check(bad['error']['code']=='fact_unexpected_argument','strict_payload')
        bad=cli(['fact','archive','--source','alpha'],dict(fact_id=f['fact_id'],expected_revision=True),1)
        check(bad['error']['code']=='fact_invalid_revision','strict_revision')
        check(rpc('memory_read',dict(source_id='alpha',view='lifecycle',stale_after_days=True)).get('isError') is True,'strict_read_type')
        invalid=[dict(view='lifecycle',query='bad'),dict(view='lifecycle',include_history=True),dict(view='facts',stale_after_days=1)]
        check(all(rpc('memory_read',dict(source_id='alpha',**p)).get('isError') is True for p in invalid),'strict_read_fields')
        bad=cli(['fact','lifecycle','--source','alpha','--history'],expected=1)
        check(bad['error']['code']=='invalid_cli_argument','strict_cli')
        check({t['name'] for t in rpc('',{},listing=True)['tools']}=={'search','memory_read','memory_write','context_read','context_write','get_page'},'six_tools')
        g,other=seed('two','我偏好图形界面而非终端。')
        cli(['fact','contradict','--source','alpha'],dict(fact_id=f['fact_id'],other_id=g['fact_id']))
        write('archive',g,2)
        group=cli(['fact','recall','--source','alpha','--query','命令行'])['items'][0]
        check({v['fact_id'] for v in group['facts']}=={f['fact_id'],g['fact_id']} and len(group['contradictions'])==1,'counterclaim_kept')
        check(len(cli(['fact','conflicts','--source','alpha'])['items'])==1,'conflicts_visible')
        write('archive',f,4)
        check(cli(['fact','recall','--source','alpha','--query','偏好'])['items']==[],'all_anchors_archived')
        config=root/'hook'/'config.json';config.parent.mkdir()
        config.write_bytes(enc(dict(version=1,host='claude',project_root=str(project),brain_id='lifecycle-ci',source_id='alpha',enabled=True,capture=False,extraction='local',fact_recall=True,recall_bytes=8192,max_items=8)))
        hook=invoke(['hook','--config',str(config)],dict(hook_event_name='SessionStart',session_id='archived-hook',cwd=str(project)))
        check('命令行' not in hook.decode('utf-8') and '图形界面' not in hook.decode('utf-8'),'hook_no_bypass')
        new,new_event=seed('fresh-equal',before['object'])
        check(new['fact_id']==f['fact_id'] and inspect(f['fact_id'])['items'][0]['lifecycle']['archived'] is True,'promotion_keeps_policy')
        write('restore',f,6);write('retract',f,7)
        check(cli(['fact','read','--source','alpha','--id',f['fact_id'],'--history'])['items'][0]['status']=='retracted','restore_then_retire')
        check(write('restore',f,8,1)['error']['code']=='fact_state_conflict','retired_restore_denied')
        cli(['memory','forget','--source','alpha','--event',other])
        check(sql('SELECT COUNT(*) FROM memory_fact_archive')==0,'forgotten_metadata_removed')
        h,ev=seed('age','I prefer advisory age, not truth scoring.')
        now=inspect(h['fact_id'])['evaluated_at'];sql('UPDATE memory_items SET created_at=? WHERE event_id=?',(now-86400,ev))
        check(inspect(h['fact_id'],days=1)['items'][0]['lifecycle']['age_state']=='stale','advisory_stale')
        seed('age-fresh','I prefer advisory age, not truth scoring.')
        check(inspect(h['fact_id'],days=1)['items'][0]['lifecycle']['age_state']=='fresh','new_support_fresh')
        sql('UPDATE memory_items SET created_at=9223372036854775807 WHERE event_id=?',(ev,))
        check(inspect(h['fact_id'])['items'][0]['lifecycle']['age_state']=='clock_anomaly','unknown_clock')
        limited=inspect(h['fact_id'],budget=512)
        check(len(enc(limited))<=512 and limited['truncated'] is True and limited['items']==[],'budget_complete')
        snapshot=sql('SELECT fact_id,revision,status FROM memory_facts ORDER BY fact_id',all_rows=True)
        inspect();inspect()
        check(sql('SELECT fact_id,revision,status FROM memory_facts ORDER BY fact_id',all_rows=True)==snapshot,'read_only')
        check(sql('SELECT COUNT(*) FROM jobs')==0,'no_model_jobs')
        backups=list(dbpath.parent.glob('brain.db.pre-lifecycle-v1-*.bak'))
        good=bool(backups)
        for backup in backups:
            with closing(sqlite3.connect(backup)) as db:
                good=good and db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='memory_fact_archive'").fetchone()[0]==0
        check(good,'real_backup');check(sql('SELECT MAX(version) FROM schema_version')==version,'legacy_version_preserved')

def main():
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    script=Path(__file__).resolve();checks=[];commands=[]
    report=dict(result='FAIL',native_windows=os.name=='nt',checks=checks,commands=commands,real_host_consumption_verified=False)
    try:
        binary=a.binary.resolve(strict=True);report.update(binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(script.read_bytes()).hexdigest())
        run(binary,checks,commands)
        if len(checks)!=len(EXPECTED_CHECKS) or {x['name'] for x in checks}!=EXPECTED_CHECKS:raise AssertionError('missing/duplicate checks')
        report['result']='PASS'
    except Exception as e:
        report.update(error_type=type(e).__name__,error=str(e))
        if not any(c['status']=='FAIL' for c in checks):checks.append(dict(name='execution_interrupted',status='FAIL'))
    report.update(check_count=len(checks),counts={'total':len(checks),'pass':sum(c['status']=='PASS' for c in checks),'fail':sum(c['status']=='FAIL' for c in checks)})
    report.update(provenance(script));a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
    return 0 if report['result']=='PASS' else 1

if __name__=='__main__':
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace')
    raise SystemExit(main())
