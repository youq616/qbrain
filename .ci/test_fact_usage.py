"""N47T real-process explicit-use regression. Only disposable synthetic data.

SQL is used for snapshots and explicitly named permission/corruption/cap fixtures;
normal facts and evidence, use/revocation, and forgetting go through public APIs.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import threading


def sha(b): return hashlib.sha256(b).hexdigest()
def enc(v): return json.dumps(v, ensure_ascii=False, separators=(',', ':')).encode()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();exe=a.binary.resolve(strict=True)
    checks=[];commands=[];lock=threading.Lock()
    def need(ok,name):
        checks.append({'name':name,'passed':bool(ok)})
        if not ok:raise AssertionError(name)
    def identity(s):return sha(s.encode())
    try:
      with tempfile.TemporaryDirectory(prefix='n47t-use-') as temp:
        root=Path(temp)/'使用 space 😀';root.mkdir()
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
        env.update(HOME=str(root),USERPROFILE=str(root),LOCALAPPDATA=str(root),APPDATA=str(root))
        dataroot=(root if os.name=='nt' else root/'.local/share')/'Qbrain/brains'
        def dbpath(brain='use-ci'):return dataroot/brain/'brain.db'
        def sql(text,params=(),brain='use-ci'):
            with closing(sqlite3.connect(dbpath(brain),timeout=10)) as db:
                db.execute('PRAGMA foreign_keys=ON');r=db.execute(text,params).fetchall();db.commit();return r
        def snapshot():
            with closing(sqlite3.connect(dbpath())) as db:
                tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
                return sha(repr({t:sorted(db.execute('SELECT * FROM "'+t+'"').fetchall(),key=repr) for t in tables}).encode())
        def proc(argv,payload=None,code=0,brain='use-ci',parsed=True):
            body=payload if isinstance(payload,bytes) else b'' if payload is None else enc(payload)
            r=subprocess.run([str(exe),*argv,'--brain',brain],input=body,env=env,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
            with lock:commands.append({'argv':argv,'brain':brain,'exit':r.returncode,'expected_exit':code,'stdin_sha256':sha(body),'stdout_sha256':sha(r.stdout),'stderr_sha256':sha(r.stderr)})
            if r.returncode!=code:raise AssertionError(f'{argv}: exit {r.returncode}!={code}; {r.stdout[:500]!r} {r.stderr[:300]!r}')
            return json.loads(r.stdout) if parsed else r.stdout
        def fact(action,payload=None,extra=(),code=0,source='default',brain='use-ci'):
            return proc(['fact',action,'--source',source,*extra],payload,code,brain)
        def usage(fid,**kw):return fact('usage',extra=['--id',fid],**kw)
        def seed(fragment,quote='I prefer explicit usage receipts 中文😀.',source='default'):
            payload={'session_id':'use-fixture','fragment_id':fragment,'messages':[{'role':'user','content':quote}]}
            event=proc(['memory','capture','--source',source,'--manual'],payload)['event_id']
            proc(['memory','extract','--source',source,'--event',event])
            items=proc(['memory','read','--source',source,'--limit','50'])['items']
            item=next(x['item_id'] for x in items if x['event_id']==event)
            f=fact('create',{'predicate':'use.preference','item_id':item},source=source)
            return f,event,item
        def fields(f,uid):return {'fact_id':f['fact_id'],'usage_id':identity(uid),'expected_revision':f['revision']}
        def rpc(name,args,write=False):
            req=[{'jsonrpc':'2.0','id':0,'method':'initialize','params':{}},
                 {'jsonrpc':'2.0','method':'notifications/initialized'},
                 {'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':name,'arguments':args}}]
            raw=b'\n'.join(enc(x) for x in req)+b'\n'
            output=proc(['serve','--tool-profile','memory',*(['--allow-write'] if write else [])],raw,parsed=False)
            return next(json.loads(x)['result'] for x in output.splitlines() if json.loads(x).get('id')==1)
        def rpcbody(r):return json.loads(r['content'][-1]['text'])
        proc(['init','--no-default'],parsed=False)
        proc(['config','set','memory.writeback','salient','--local'],parsed=False)
        proc(['config','set','mcp.allowed_sources','default','--local'],parsed=False)
        before=snapshot()
        missing=usage('a'*64,code=1)
        need(missing['error']['code']=='fact_not_found' and snapshot()==before,'absent fact read never initializes optional schema')
        f,event,item=seed('first');fid=f['fact_id']
        second,_,_=seed('other','I prefer an independently chosen value.')
        before=snapshot();u=usage(fid)
        need(not u['initialized'] and u['stored_receipts']==0 and u['last_current_revision_use_at'] is None,'uninitialized usage is genuinely empty')
        need(before==snapshot(),'usage read does not initialize or mutate')
        payload=fields(f,'one')
        before=snapshot()
        for patch in ({'expected_revision':True},{'expected_revision':0},{'expected_revision':-1},{'expected_revision':1.5},{'expected_revision':'1'},
                      {'expected_revision':2147483648},{'usage_id':'BAD'},{'usage_id':'F'*64},{'fact_id':'bad'},{'unused':1}):
            out=fact('report-use',{**payload,**patch},code=1)
            need('error' in out,'reject malformed use '+str(patch))
        for field in payload:
            bad=dict(payload);bad.pop(field)
            need('error' in fact('report-use',bad,code=1),'reject missing '+field)
        duplicate=enc(payload)[:-1]+b',"expected_revision":1}'
        need(fact('report-use',duplicate,code=1)['error']['code']=='fact_duplicate_key','duplicate raw JSON keys rejected')
        need(fact('report-use',{**payload,'expected_revision':2},code=1)['error']['code']=='fact_revision_conflict','stale version rejected before initialization')
        need(before==snapshot() and not sql("SELECT name FROM sqlite_master WHERE name='memory_fact_usage'"),'invalid use requests preserve all application rows and schema')
        deny=rpc('memory_write',{'action':'fact_report_use','payload':enc(payload).decode()})
        need(deny.get('isError') is True and 'write_denied' in str(deny),'MCP report defaults to write denied')
        need(before==snapshot(),'denied MCP report cannot create schema')
        # Concurrent cold start also exercises optional schema creation races.
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(lambda _:fact('report-use',payload),range(4)))
        need(sum(not x['duplicate'] for x in results)==1 and all(x['status']=='reported' for x in results),'concurrent cold duplicate is recorded once')
        need(len({x['reported_at'] for x in results})==1,'retry preserves original receipt time')
        u=usage(fid)
        need(u['current_revision_use_count']==1 and u['stored_receipts']==1 and u['other_revision_use_count']==0,'one explicitly reported use')
        need(u['origin']=='caller_reported' and u['host_consumption_verified'] is False and u['fact_truth_verified'] is False and u['provider_calls']==0,'no use truth host or model claim')
        need(len(enc(u))<1024 and 'object' not in u and 'session_id' not in u,'bounded metadata only response')
        backups=list(dbpath().parent.glob('brain.db.pre-usage-v1-*.bak'))
        good_backup=False
        for b in backups:
            with closing(sqlite3.connect(b)) as db:
                good_backup |= db.execute("SELECT count(*) FROM sqlite_master WHERE name='memory_fact_usage_module'").fetchone()[0]==0
        need(good_backup,'first valid use backs up before new module')
        before=snapshot()
        need(fact('report-use',{**payload,'fact_id':second['fact_id']},code=1)['error']['code']=='fact_usage_id_conflict','same source receipt ID cannot target different fact')
        for bad in (['--id',fid,'--history'],['--id',fid,'--limit','10'],['--id',fid,'--id',fid],['--query','x']):
            need('error' in fact('usage',extra=bad,code=1),'strict usage CLI '+str(bad[::2]))
        need(before==snapshot(),'rejections preserve stored rows')
        fact_before=fact('read',extra=['--id',fid]);before=snapshot()
        for _ in range(3):
            usage(fid);fact('recall',extra=['--query','usage']);fact('lifecycle',extra=['--id',fid])
        need(before==snapshot(),'ordinary reads recall and lifecycle never report use')
        need(fact('read',extra=['--id',fid])==fact_before,'usage leaves complete original fact and revision unchanged')
        good=rpc('memory_write',{'action':'fact_report_use','payload':enc(fields(f,'mcp')).decode()},write=True)
        need(not good.get('isError') and rpcbody(good)['status']=='reported','authorized MCP can explicitly report use')
        got=rpc('memory_read',{'view':'usage','fact_id':fid})
        need(not got.get('isError') and rpcbody(got)['current_revision_use_count']==2,'authorized MCP usage read')
        need(rpc('memory_read',{'view':'usage','fact_id':fid,'limit':10}).get('isError') is True,'MCP rejects irrelevant usage options')
        # Explicit authorization/source fixture; no product evidence is seeded by SQL.
        sql("INSERT INTO sources(id,name) VALUES('other','other')")
        other,_,_=seed('source-other',source='other')
        need(rpc('memory_read',{'view':'usage','fact_id':fid,'source_id':'other'}).get('isError') is True,'MCP other source default denied')
        before=snapshot()
        need(fact('report-use',payload,source='other',code=1)['error']['code']=='fact_not_found','fact cannot be reported under foreign source')
        need(before==snapshot(),'foreign report preserves state')
        allowed=fact('report-use',{**payload,'fact_id':other['fact_id']},source='other')
        need(not allowed['duplicate'],'identical use IDs are independent across sources')
        tomb={'fact_id':fid,'usage_id':identity('one')}
        revoked=fact('revoke-use',tomb);again=fact('revoke-use',tomb)
        need(not revoked['duplicate'] and again['duplicate'] and revoked['withdrawn_at']==again['withdrawn_at'],'withdrawal idempotent timestamp')
        need(fact('report-use',payload,code=1)['error']['code']=='fact_usage_withdrawn','retry cannot resurrect withdrawn receipt')
        need(usage(fid)['current_revision_use_count']==1 and usage(fid)['withdrawn_count']==1,'withdrawn receipt excluded but retained')
        need(usage(other['fact_id'],source='other')['current_revision_use_count']==1,'withdrawal cannot affect same receipt in another source')
        need(rpc('memory_write',{'action':'fact_revoke_use','payload':enc({'fact_id':fid,'usage_id':identity('mcp')}).decode()}).get('isError') is True,'MCP revoke defaults to denied')
        # The actual Hook read path may write its own checkpoint, never a use receipt.
        cfg=root/'hook-use.json'
        cfg.write_bytes(enc({'version':1,'host':'claude','project_root':str(root),'brain_id':'use-ci',
            'source_id':'default','enabled':True,'capture':False,'extraction':'local','fact_recall':True,
            'fact_promotion':False,'recall_bytes':8192,'max_items':8}))
        count=usage(fid)['stored_receipts']
        hookbody={'hook_event_name':'SessionStart','session_id':'usage-read-only','cwd':str(root)}
        proc(['hook','--config',str(cfg)],hookbody)
        need(usage(fid)['stored_receipts']==count,'actual Hook output never records caller use')
        # Another exact quote creates an independent support, attached through CLI.
        support,evt2,item2=seed('support')
        attached=fact('attach',{'fact_id':fid,'item_id':item2})
        need(attached['revision']==2,'independent support advances existing revision')
        u=usage(fid)
        need(u['current_revision_use_count']==0 and u['other_revision_use_count']==1 and u['last_current_revision_use_at'] is None,'old revision use never becomes current')
        need(fact('report-use',fields(f,'stale'),code=1)['error']['code']=='fact_revision_conflict','use must bind current revision')
        fresh=fields(attached,'fresh');fact('report-use',fresh)
        archive=fact('archive',{'fact_id':fid,'expected_revision':attached['revision']})
        current=fact('read',extra=['--id',fid])['items'][0]
        need(fact('report-use',fields(current,'archived'),code=1)['error']['code']=='fact_usage_archived','archived fact cannot gain reported use')
        need(usage(fid)['archived'] is True,'archived usage summary labels archive')
        need(fact('revoke-use',{'fact_id':fid,'usage_id':fresh['usage_id']})['status']=='withdrawn','can withdraw after archiving or version changes')
        fact('restore',{'fact_id':fid,'expected_revision':current['revision']})
        current=fact('read',extra=['--id',fid])['items'][0]
        fact('report-use',fields(current,'before-forget'))
        proc(['memory','forget','--event',event])
        u=usage(fid)
        need(u['current_revision_use_count']==0 and u['other_revision_use_count']>=1,'forgetting one support advances revision without losing historical receipts')
        need(sql('SELECT count(*) FROM memory_fact_usage WHERE fact_id=?',(fid,))[0][0]>0,'remaining independent support retains receipts')
        proc(['memory','forget','--event',evt2])
        need(not sql('SELECT 1 FROM memory_facts WHERE fact_id=?',(fid,)) and not sql('SELECT 1 FROM memory_fact_usage WHERE fact_id=?',(fid,)),'last support forgetting cascades all use and withdrawn receipts')
        need(usage(fid,code=1)['error']['code']=='fact_not_found','forgotten fact has no usage readback')
        # Isolated explicit table-corruption fixtures, restoring each row afterward.
        target=second;tid=target['fact_id'];fact('report-use',fields(target,'corruption-control'))
        before=snapshot()
        sql('UPDATE memory_fact_usage_module SET version=1')
        with closing(sqlite3.connect(dbpath())) as db:
            db.execute('PRAGMA ignore_check_constraints=ON');db.execute('UPDATE memory_fact_usage_module SET version=2');db.commit()
        need(usage(tid,code=1)['error']['code']=='fact_usage_version_unsupported','unsupported module rejected')
        sql('UPDATE memory_fact_usage_module SET version=1')
        with closing(sqlite3.connect(dbpath())) as db:
            db.execute('PRAGMA ignore_check_constraints=ON');db.execute("UPDATE memory_fact_usage SET fact_revision='oops' WHERE fact_id=?",(tid,));db.commit()
        need(usage(tid,code=1)['error']['code']=='fact_usage_invalid_metadata','corrupt receipt type never becomes an invented count')
        sql('UPDATE memory_fact_usage SET fact_revision=1 WHERE fact_id=?',(tid,))
        need(snapshot()==before,'corruption fixtures restored exactly')
        # Named capacity fixture: no4096 real calls just to fill metadata storage.
        sql('DELETE FROM memory_fact_usage WHERE fact_id=?',(tid,))
        with closing(sqlite3.connect(dbpath())) as db:
            db.executemany('INSERT INTO memory_fact_usage(source_id,usage_id,fact_id,fact_revision,reported_at) VALUES(?,?,?,?,?)',
               [('default',identity('cap-'+str(i)),tid,1,1) for i in range(4096)]);db.commit()
        need(usage(tid)['stored_receipts']==4096,'bounded summary at explicit capacity')
        need(fact('report-use',fields(target,'cap-0'))['duplicate'],'duplicate at capacity does not consume space')
        before=snapshot()
        need(fact('report-use',fields(target,'over-cap'),code=1)['error']['code']=='fact_usage_capacity' and snapshot()==before,'over capacity rejected without eviction')
        fact('revoke-use',{'fact_id':tid,'usage_id':identity('cap-0')})
        need(fact('report-use',fields(target,'over-cap'),code=1)['error']['code']=='fact_usage_capacity','withdrawn tombstones still count toward capacity')
        # No metadata receipt may change fact status or revive retired claims.
        fact('retract',{'fact_id':tid,'expected_revision':1})
        need(fact('report-use',{**fields(target,'retired'),'expected_revision':2},code=1)['error']['code']=='fact_state_conflict','retired fact not revived by use report')
        need(fact('revoke-use',{'fact_id':tid,'usage_id':identity('cap-1')})['status']=='withdrawn','retired receipt still revocable')
        parallel,_,_=seed('parallel','I prefer concurrency without duplicate receipts.')
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda i:fact('report-use',fields(parallel,'parallel-'+str(i))),range(8)))
        need(all(not x['duplicate'] for x in results) and usage(parallel['fact_id'])['current_revision_use_count']==8,'concurrent distinct receipts are all counted')
        # Deliberate SQL I/O failure fixture tests whole write rollback and retry.
        sql("CREATE TRIGGER n47t_abort BEFORE INSERT ON memory_fact_usage BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        before=snapshot()
        need(fact('report-use',fields(parallel,'rollback'),code=1)['error']['code']=='memory_storage_error' and before==snapshot(),'failed insert rolls back without changing fact or use counts')
        sql('DROP TRIGGER n47t_abort')
        need(not fact('report-use',fields(parallel,'rollback'))['duplicate'],'failed receipt ID can be retried after genuine rollback')
        before=snapshot()
        sql('ALTER TABLE memory_fact_usage_module RENAME TO n47t_saved_module')
        need(usage(parallel['fact_id'],code=1)['error']['code']=='fact_usage_schema_conflict','orphan optional table is refused')
        sql('ALTER TABLE n47t_saved_module RENAME TO memory_fact_usage_module')
        sql('UPDATE memory_fact_usage SET fact_revision=99 WHERE fact_id=?',(parallel['fact_id'],))
        need(usage(parallel['fact_id'],code=1)['error']['code']=='fact_usage_invalid_metadata','future revision metadata rejected')
        sql('UPDATE memory_fact_usage SET fact_revision=1 WHERE fact_id=?',(parallel['fact_id'],))
        need(before==snapshot(),'adversarial schema and revision fixtures restored')
        need(sql('PRAGMA foreign_key_check')==[],'usage cascade has no foreign key violations')
        need(not sql("SELECT 1 FROM sqlite_master WHERE name='memory_fact_usage' AND sql LIKE '%session%'"),'receipt table stores no session or quote')
    except Exception as e:
        checks.append({'name':'unexpected_exception','passed':False,'error':str(e)})
    result={'schema':'qbrain-n47t-process-v1','binary_sha256':sha(exe.read_bytes()),'test_sha256':sha(Path(__file__).read_bytes()),
            'passed':sum(x['passed'] for x in checks),'failed':sum(not x['passed'] for x in checks),'checks':checks,'commands':commands,
            'command_count':len(commands),'real_client_tested':False,'provider_calls':0}
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('checks','commands')}))
    if result['failed']:
        print(json.dumps([x for x in checks if not x['passed']],ensure_ascii=False));raise SystemExit(1)
if __name__=='__main__':main()
