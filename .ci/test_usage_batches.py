"""N47Z real CLI/persistent MCP regression; isolated synthetic data only.

SQL writes are explicitly named corruption/capacity/competing-writer/ABORT fixtures.
Normal application records are produced by public commands. No actual model call.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import queue
import sqlite3
import subprocess
import tempfile
import threading
import time


def sha(raw): return hashlib.sha256(raw).hexdigest()
def enc(obj): return json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode()


def exercise(binary: Path, output: Path):
    output.mkdir(parents=True,exist_ok=False)
    rawdir=output/'raw';rawdir.mkdir()
    checks=[];records=[];lock=threading.Lock();failure=None
    def check(ok,name):
        checks.append({'name':name,'passed':bool(ok)})
        if not ok: raise ValueError(name)
    def record(kind,request,response,stderr=b'',code=0):
        with lock:
            index=len(records)+1
            row={'index':index,'kind':kind,'exit':code}
            for field,raw in [('request',request),('response',response),('stderr',stderr)]:
                (rawdir/f'{index:04}.{field}').write_bytes(raw)
                row[field+'_sha256']=sha(raw)
            records.append(row)
    servers=[]
    try:
      with tempfile.TemporaryDirectory(prefix='n47z-') as tmp:
        root=Path(tmp)/'batch 测试 space';root.mkdir()
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
        env.update(HOME=str(root),USERPROFILE=str(root),LOCALAPPDATA=str(root),APPDATA=str(root))
        dbpath=(root if os.name=='nt' else root/'.local/share')/'Qbrain/brains/batch/brain.db'
        def cli(args,payload=None,parse=True):
            inp=payload if isinstance(payload,bytes) else b'' if payload is None else enc(payload)
            p=subprocess.run([str(binary),*args,'--brain','batch'],input=inp,cwd=root,env=env,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
            record('cli',enc({'argv':args,'stdin':inp.decode()}),p.stdout,p.stderr,p.returncode)
            return p.returncode,json.loads(p.stdout) if parse else p.stdout
        def good(args,payload=None,parse=True):
            code,body=cli(args,payload,parse)
            if code: raise ValueError('setup/call rejected '+str(args)+': '+str(body))
            return body
        def sql(query,params=(),corrupt=False):
            with closing(sqlite3.connect(dbpath,timeout=10)) as db:
                db.execute('PRAGMA foreign_keys='+('OFF' if corrupt else 'ON'))
                if corrupt:db.execute('PRAGMA ignore_check_constraints=ON')
                rows=db.execute(query,params).fetchall();db.commit();return rows
        def state():
            with closing(sqlite3.connect(dbpath)) as db:
                names=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
                data={n:sorted(db.execute('SELECT * FROM "'+n+'"').fetchall(),key=repr) for n in names}
                schema=db.execute('SELECT * FROM sqlite_master ORDER BY name').fetchall()
            backups=sorted((p.name,sha(p.read_bytes())) for p in dbpath.parent.glob('*.bak'))
            return sha(repr((data,schema,backups)).encode())
        def seed(label,source='default',expires=0):
            event=good(['memory','capture','--manual','--source',source],{'session_id':'batch-fixture',
                'fragment_id':label,'expires_at':expires,'messages':[{'role':'user','content':'I prefer batch evidence '+label+'.'}]})
            good(['memory','extract','--event',event['event_id'],'--source',source])
            mem=good(['memory','read','--limit','50','--source',source])
            item=next(x for x in mem['items'] if x['event_id']==event['event_id'])
            fact=good(['fact','create','--source',source],{'predicate':'batch.preference','item_id':item['item_id']})
            return fact,event['event_id']
        def item(f,label,report=True):
            r={'fact_id':f['fact_id'],'usage_id':sha(label.encode())}
            if report:r['expected_revision']=f['revision']
            return r
        def spec(op,items):return {'operation':op,'items':items}
        def preview(p,source='default'):return good(['fact','usage-batch-preview','--source',source],p)
        def apply(p,token,source='default'):return good(['fact','usage-batch-apply','--source',source],{**p,'snapshot':token})
        def commit(p,source='default'):
            plan=preview(p,source);return apply(p,plan['snapshot'],source)
        def rejected(args,payload,label,expected=None):
            before=state();code,body=cli(args,payload)
            check(code==1 and isinstance(body,dict) and 'error' in body and
                (expected is None or body['error']['code']==expected) and before==state(),label)
            return body
        for args in (['init','--no-default'],['config','set','memory.writeback','salient','--local'],
                     ['config','set','mcp.allowed_sources','default','--local']):good(args,parse=False)
        facts=[seed('fact'+str(i))[0] for i in range(9)];a,b=facts[:2]
        one,two=item(a,'first'),item(b,'second');p=spec('report',[one,two]);before=state()
        plan=preview(p)
        check(plan['would_change']==2 and plan['changed']==0 and plan['applied'] is False,'preview exposes both intended changes')
        check(before==state() and not sql("SELECT name FROM sqlite_master WHERE name='memory_fact_usage'"),'first preview creates no module backup or rows')
        check(preview(spec('report',[two,one]))==plan,'input reordering preserves plan and snapshot')
        check(plan['origin']=='caller_reported' and plan['host_consumption_verified'] is False and
            plan['fact_truth_verified'] is False and plan['provider_calls']==0,'batch does not certify host use or truth')
        invalid=[None,[],{}, {'operation':'invalid','items':[one]}, {'operation':True,'items':[one]},
            {'operation':'report','items':[]},{'operation':'report','items':{}},
            {'operation':'report','items':[one]*33}, {**p,'apply':True},{**p,'snapshot':'a'*64},
            spec('report',[one,one]),spec('report',[{**one,'expected_revision':True}]),
            spec('report',[{**one,'expected_revision':1.0}]),spec('report',[{**one,'expected_revision':0}]),
            spec('report',[{**one,'expected_revision':2**31}]),spec('report',[{**one,'usage_id':'A'*64}]),
            spec('report',[{**one,'fact_id':'x'}]),spec('report',[{k:v for k,v in one.items() if k!='usage_id'}]),
            spec('report',[{**one,'extra':'x'}]),spec('revoke',[one]),spec('report',[1])]
        for i,bad in enumerate(invalid):rejected(['fact','usage-batch-preview'],enc(bad),'reject invalid request '+str(i))
        rejected(['fact','usage-batch-preview'],enc(p)[:-1]+b',"operation":"revoke"}','reject duplicate top-level JSON','fact_batch_duplicate_key')
        rejected(['fact','usage-batch-preview'],b' '*8193,'reject payload byte cap','fact_batch_payload_limit')
        rejected(['fact','usage-batch-apply'],p,'apply requires snapshot')
        rejected(['fact','usage-batch-apply'],{**p,'snapshot':'a'*64},'unapproved token rejected before initializer','fact_usage_batch_snapshot_conflict')
        rejected(['fact','usage-batch-preview'],spec('report',[one,{**two,'expected_revision':99}]),'invalid second revision never creates first row','fact_revision_conflict')
        rejected(['fact','usage-batch-preview'],spec('report',[one,{**two,'fact_id':'f'*64}]),'absent second fact never creates first row','fact_not_found')
        rejected(['fact','usage-batch-preview'],spec('report',[item(f,'nine'+str(i)) for i,f in enumerate(facts)]),'ninth fact rejected','fact_usage_batch_fact_limit')
        before_facts=sql('SELECT * FROM memory_facts ORDER BY fact_id')
        done=apply(p,plan['snapshot'])
        check(done['applied'] and done['atomic'] and done['changed']==2 and done['unchanged']==0,'two-fact batch commits together')
        check(len({i['reported_at'] for i in done['items']})==1,'one batch uses one report timestamp')
        check(before_facts==sql('SELECT * FROM memory_facts ORDER BY fact_id'),'batch does not modify facts or revisions')
        backups=list(dbpath.parent.glob('*.pre-usage-v1-*.bak'))
        with closing(sqlite3.connect(backups[0])) as db:
            valid_backup=db.execute("SELECT count(*) FROM sqlite_master WHERE name='memory_fact_usage'").fetchone()[0]==0
        check(len(backups)==1 and valid_backup,'first apply uses original pre-module backup')
        rejected(['fact','usage-batch-apply'],{**p,'snapshot':plan['snapshot']},'old post-change snapshot cannot silently replay','fact_usage_batch_snapshot_conflict')
        before=state();noop=preview(p);out=apply(p,noop['snapshot'])
        check(noop['would_change']==0 and out['changed']==0 and out['unchanged']==2 and before==state(),'fresh preview recognizes all reports as exact no-ops')
        mixed=spec('report',[one,item(a,'mixed')]);out=commit(mixed)
        check(out['changed']==1 and out['unchanged']==1,'mixed new and existing entries add only one')
        rejected(['fact','usage-batch-preview'],spec('report',[{**one,'fact_id':b['fact_id']}]),'cross-fact receipt collision rejected','fact_usage_id_conflict')
        rejected(['fact','usage-batch-preview'],spec('report',[one,{**one,'fact_id':b['fact_id']}]),'duplicate source-wide ID selection rejected','fact_usage_batch_duplicate_id')
        todo=spec('report',[item(a,'stale-a'),item(b,'stale-b')]);tok=preview(todo)['snapshot']
        good(['fact','report-use'],item(a,'off-selection'))
        rejected(['fact','usage-batch-apply'],{**todo,'snapshot':tok},'off-selection target change invalidates batch','fact_usage_batch_snapshot_conflict')
        tok=preview(todo)['snapshot']
        rejected(['fact','usage-batch-apply'],{**spec('report',[item(a,'different')]),'snapshot':tok},'selection substitution rejected','fact_usage_batch_snapshot_conflict')
        other=spec('report',[item(facts[8],'unrelated')]);commit(other)
        check(apply(todo,tok)['changed']==2,'unrelated fact change does not invalidate selected state')
        maximum=spec('report',[item(facts[2],'max'+str(i)) for i in range(32)])
        out=commit(maximum);check(out['changed']==32 and len(enc(out))+1<=16384,'32-entry report fits fixed response bound')
        check(commit(spec('report',[item(f,'eight'+str(i)) for i,f in enumerate(facts[:8])]))['changed']==8,'eight distinct facts accepted')
        # Source setup SQL changes only fixture permissions, not evidence.
        sql("INSERT INTO sources(id,name) VALUES('other','other')")
        foreign,_=seed('foreign','other')
        rejected(['fact','usage-batch-preview','--source','other'],p,'foreign fact/source rejected','fact_not_found')
        fitem={**one,'fact_id':foreign['fact_id'],'expected_revision':foreign['revision']}
        check(commit(spec('report',[fitem]),'other')['changed']==1,'identical usage ID stays independent across sources')
        # Deliberate off-selection row corruption; restore exact raw row values.
        healthy=sql('SELECT * FROM memory_fact_usage')
        def restore():
            with closing(sqlite3.connect(dbpath)) as db:
                db.execute('PRAGMA foreign_keys=OFF');db.execute('DELETE FROM memory_fact_usage')
                db.executemany('INSERT INTO memory_fact_usage VALUES(?,?,?,?,?,?)',healthy);db.commit()
        fresh=spec('report',[item(a,'after-corruption')]);token=preview(fresh)['snapshot']
        changes=[("usage_id=CAST(usage_id AS BLOB)",()),("fact_revision=?",(99,)),
            ("reported_at=?",(-1,)),("source_id=CAST(source_id AS BLOB)",()),("fact_id=CAST(fact_id AS BLOB)",())]
        for i,(change,values) in enumerate(changes):
            sql('UPDATE memory_fact_usage SET '+change+' WHERE source_id=? AND usage_id=?',(*values,'default',one['usage_id']),corrupt=True)
            rejected(['fact','usage-batch-preview'],fresh,'corruption preview rejects '+str(i))
            rejected(['fact','usage-batch-apply'],{**fresh,'snapshot':token},'corruption apply rejects '+str(i))
            restore()
        check(preview(fresh)['snapshot']==token,'exact restoration re-enables original state')
        # SQL trigger proves the first INSERT executed inside the transaction
        # before rejecting the second. RAISE(IGNORE) without first row yields a
        # distinct conflict code, so memory_storage_error is meaningful here.
        rollback=spec('report',[{**item(a,'rollback-first'),'usage_id':'a'*64},
                                {**item(b,'rollback-second'),'usage_id':'b'*64}])
        token=preview(rollback)['snapshot']
        sql("CREATE TRIGGER z_abort_insert BEFORE INSERT ON memory_fact_usage WHEN NEW.usage_id='"+'b'*64+"' BEGIN SELECT CASE WHEN EXISTS(SELECT 1 FROM memory_fact_usage WHERE usage_id='"+'a'*64+"') THEN RAISE(ABORT,'earlier_insert_seen') ELSE RAISE(IGNORE) END; END")
        rejected(['fact','usage-batch-apply'],{**rollback,'snapshot':token},'second insert ABORT rolls back first inserted row','memory_storage_error')
        sql('DROP TRIGGER z_abort_insert')
        check(apply(rollback,token)['changed']==2,'same approval works after fully rolled-back insertion')
        revoke=spec('revoke',[{k:v for k,v in x.items() if k!='expected_revision'} for x in rollback['items']]);token=preview(revoke)['snapshot']
        sql("CREATE TRIGGER z_abort_update BEFORE UPDATE OF withdrawn_at ON memory_fact_usage WHEN NEW.usage_id='"+'b'*64+"' BEGIN SELECT CASE WHEN EXISTS(SELECT 1 FROM memory_fact_usage WHERE usage_id='"+'a'*64+"' AND withdrawn_at IS NOT NULL) THEN RAISE(ABORT,'earlier_update_seen') ELSE RAISE(IGNORE) END; END")
        rejected(['fact','usage-batch-apply'],{**revoke,'snapshot':token},'second revoke ABORT rolls back first tombstone','memory_storage_error')
        sql('DROP TRIGGER z_abort_update');out=apply(revoke,token)
        check(out['changed']==2 and all(i['withdrawn_at']>=i['reported_at'] for i in out['items']),'batch revoke commits complete monotonic tombstones')
        before=state();check(commit(revoke)['changed']==0 and state()==before,'fresh repeated revoke is a timestamp-preserving no-op')
        rejected(['fact','usage-batch-preview'],rollback,'withdrawn IDs cannot be resurrected','fact_usage_withdrawn')
        # Capacity fixture has no new production shortcut.
        capfact=facts[7];saved=sql('SELECT * FROM memory_fact_usage WHERE fact_id=?',(capfact['fact_id'],))
        sql('DELETE FROM memory_fact_usage WHERE fact_id=?',(capfact['fact_id'],))
        with closing(sqlite3.connect(dbpath)) as db:
            db.executemany('INSERT INTO memory_fact_usage(source_id,usage_id,fact_id,fact_revision,reported_at) VALUES(?,?,?,?,?)',
                [('default',f'{i:064x}',capfact['fact_id'],capfact['revision'],1) for i in range(4095)]);db.commit()
        over=spec('report',[item(capfact,'cap-one'),item(capfact,'cap-two')])
        rejected(['fact','usage-batch-preview'],over,'collective additions exceed capacity before writing','fact_usage_capacity')
        check(commit(spec('report',[over['items'][0]]))['changed']==1,'one remaining capacity slot usable')
        rejected(['fact','usage-batch-preview'],spec('report',[over['items'][1]]),'full capacity refuses next new entry','fact_usage_capacity')
        with closing(sqlite3.connect(dbpath)) as db:
            db.execute('DELETE FROM memory_fact_usage WHERE fact_id=?',(capfact['fact_id'],))
            db.executemany('INSERT INTO memory_fact_usage VALUES(?,?,?,?,?,?)',saved);db.commit()
        # Real persistent MCP: initialization/advertisement and typed path, no fake host.
        class Server:
            def __init__(self,write):
                self.p=subprocess.Popen([str(binary),'serve','--brain','batch','--tool-profile','memory',*(['--allow-write'] if write else [])],
                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,cwd=root)
                self.lines=queue.Queue();self.err=[];self.n=0;servers.append(self)
                def drain():
                    for raw in self.p.stdout:self.lines.put(raw)
                    self.lines.put(None)
                def errors():
                    for raw in self.p.stderr:self.err.append(raw)
                self.t=threading.Thread(target=drain,daemon=True);self.t.start()
                self.et=threading.Thread(target=errors,daemon=True);self.et.start()
                self.recv(self.send('initialize',{}))
                self.p.stdin.write(enc({'jsonrpc':'2.0','method':'notifications/initialized'})+b'\n');self.p.stdin.flush()
            def send(self,method,params):
                self.n+=1;req={'jsonrpc':'2.0','id':self.n,'method':method,'params':params}
                self.p.stdin.write(enc(req)+b'\n');self.p.stdin.flush();return req
            def recv(self,req):
                raw=self.lines.get(timeout=10)
                if raw is None:raise ValueError('server exited')
                reply=json.loads(raw);record('mcp',enc(req),raw)
                if reply.get('id')!=req['id']:raise ValueError('response identity')
                return reply
            def call(self,tool,args):
                r=self.recv(self.send('tools/call',{'name':tool,'arguments':args}))['result']
                return r['isError'],json.loads(r['content'][-1]['text'])
            def batch(self,p,token=None):
                args={'view':'usage_batch','payload':enc(p).decode()} if token is None else {
                    'action':'fact_usage_batch','payload':enc({**p,'snapshot':token}).decode()}
                return self.call('memory_read' if token is None else 'memory_write',args)
            def stop(self):
                if self.p.poll() is None:
                    self.p.stdin.close()
                    try:self.p.wait(timeout=5)
                    except subprocess.TimeoutExpired:self.p.kill();self.p.wait(timeout=5)
                self.t.join(timeout=5);self.et.join(timeout=5)
                self.p.stdout.close();self.p.stderr.close()
        ro=Server(False);rw=Server(True);rw2=Server(True)
        tools=rw.recv(rw.send('tools/list',{}))['result']['tools']
        read_schema=next(t['inputSchema'] for t in tools if t['name']=='memory_read')
        write_schema=next(t['inputSchema'] for t in tools if t['name']=='memory_write')
        check(len(tools)==6 and 'usage_batch' in read_schema['properties']['view']['enum'] and
            'fact_usage_batch' in write_schema['properties']['action']['enum'],'existing six-tool MCP advertises batch operations')
        wire=spec('report',[item(a,'wire-a'),item(b,'wire-b')]);before=state()
        err,plan=ro.batch(wire)
        check(not err and plan==preview(wire) and state()==before,'read-only MCP preview equals CLI and does not mutate')
        err,out=ro.batch(wire,plan['snapshot'])
        check(err and out['error']['code']=='write_denied' and state()==before,'preview does not authorize MCP write')
        err,out=rw.batch(wire,plan['snapshot'])
        check(not err and out['changed']==2,'authorized MCP applies complete report batch')
        for args in ({'view':'usage_batch','payload':wire},{'view':'usage_batch','payload':enc(wire).decode(),'limit':3},
                     {'view':'usage_batch','payload':enc(wire).decode(),'unrecognized':'x'},
                     {'view':'usage_batch','payload':enc(wire).decode(),'source_id':'other'}):
            before=state();err,out=rw.call('memory_read',args)
            check(err and state()==before,'MCP refuses type/field/route/source '+str(len(checks)))
        withdraw=spec('revoke',[{k:v for k,v in i.items() if k!='expected_revision'} for i in wire['items']])
        err,plan=rw.batch(withdraw);err,out=rw.batch(withdraw,plan['snapshot'])
        check(not err and out['changed']==2,'authorized MCP applies complete revoke batch')
        race=spec('report',[item(a,'race-a'),item(b,'race-b')]);token=preview(race)['snapshot']
        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks=[pool.submit(s.batch,race,token) for s in (rw,rw2)];result=[t.result() for t in tasks]
        check(sum(not e for e,_ in result)==1 and all((not e and r['changed']==2) or
            (e and r['error']['code']=='fact_usage_batch_snapshot_conflict') for e,r in result),'concurrent same approval commits once and refuses stale contender')
        waiting=spec('report',[item(a,'waiting-a'),item(b,'waiting-b')]);token=preview(waiting)['snapshot']
        with closing(sqlite3.connect(dbpath,timeout=10)) as db:
            db.execute('BEGIN IMMEDIATE')
            req=rw.send('tools/call',{'name':'memory_write','arguments':{'action':'fact_usage_batch','payload':enc({**waiting,'snapshot':token}).decode()}})
            try:early=rw.lines.get(timeout=.2)
            except queue.Empty:early='waiting'
            check(early=='waiting','apply waits for competing writer rather than returning early')
            db.execute('INSERT INTO memory_fact_usage(source_id,usage_id,fact_id,fact_revision,reported_at) VALUES(?,?,?,?,?)',
                       ('default',sha(b'competing-writer'),a['fact_id'],a['revision'],int(time.time())))
            db.commit()
        before=state();r=rw.recv(req)['result'];body=json.loads(r['content'][-1]['text'])
        check(r['isError'] and body['error']['code']=='fact_usage_batch_snapshot_conflict' and state()==before,'state committed during lock wait invalidates entire batch')
        check(commit(waiting)['changed']==2,'fresh preview succeeds after competing writer')
        # Natural expiry is not simulated by altering database timestamps.
        expiry=int(time.time())+5;exp,ee=seed('expires',expires=expiry)
        old=item(exp,'expires-old');commit(spec('report',[old]));new=spec('report',[item(exp,'expires-new')])
        token=preview(new)['snapshot'];check(time.time()<expiry-1,'expiry fixture has positive preparation margin')
        while time.time()<=expiry:time.sleep(.03)
        rejected(['fact','usage-batch-apply'],{**new,'snapshot':token},'expired report cannot apply old approval','fact_not_found')
        revspec=spec('revoke',[{k:v for k,v in old.items() if k!='expected_revision'}])
        check(commit(revspec)['changed']==1,'expired supported receipt retains explicit batch withdrawal right')
        good(['memory','forget','--event',ee])
        check(not sql('SELECT 1 FROM memory_fact_usage WHERE fact_id=?',(exp['fact_id'],)),'last support forgetting cascades batch receipts and tombstones')
        # Retired and archived facts still preserve explicit withdrawal rights.
        for retire,idx in [('archive',4),('retract',5)]:
            f=facts[idx];entry=item(f,'retire-'+retire);commit(spec('report',[entry]))
            current=good(['fact','read','--id',f['fact_id']])['items'][0]
            good(['fact',retire],{'fact_id':f['fact_id'],'expected_revision':current['revision']})
            check(commit(spec('revoke',[{k:v for k,v in entry.items() if k!='expected_revision'}]))['changed']==1,'batch withdrawal survives '+retire)
        check(sql('PRAGMA foreign_key_check')==[],'no foreign key violations after all operations')
        for s in servers:s.stop()
        check(all(s.p.returncode==0 for s in servers),'persistent MCP processes close cleanly after success and failures')
    except Exception as e:
        failure=type(e).__name__+': '+str(e)
    finally:
        for s in servers:
            if s.p.poll() is None:s.stop()
    result={'schema':'qbrain-n47z-batch-tests-v1','binary_sha256':sha(binary.read_bytes()),
        'script_sha256':sha(Path(__file__).read_bytes()),'checks':checks,'commands':records,'command_count':len(records),
        'passed':sum(x['passed'] for x in checks),'failed':sum(not x['passed'] for x in checks)+int(failure is not None and all(x['passed'] for x in checks)),
        'failure':failure,'platform':os.name,'real_client_verified':False,'provider_calls':0}
    (output/'report.json').write_bytes(enc(result)+b'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=exercise(a.binary.resolve(strict=True),a.output)
    print(json.dumps({k:v for k,v in r.items() if k not in ('checks','commands')}))
    raise SystemExit(1 if r['failed'] else 0)
