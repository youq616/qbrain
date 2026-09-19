"""N47U real-process audit pagination. Disposable synthetic roots only.

Ordinary setup uses public APIs; SQL only reads snapshots or explicitly injects
source/metadata/capacity fixtures. Raw command evidence is saved when requested.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile


def digest(raw): return hashlib.sha256(raw).hexdigest()
def encode(value): return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--raw-dir', type=Path)
    a = p.parse_args(); exe = a.binary.resolve(strict=True)
    checks, commands = [], []
    if a.raw_dir: a.raw_dir.mkdir(parents=True, exist_ok=False)
    def need(ok, name):
        checks.append({'name': name, 'passed': bool(ok)})
        if not ok: raise AssertionError(name)
    try:
        with tempfile.TemporaryDirectory(prefix='n47u-pages-') as tmp:
            root = Path(tmp) / '回执 space 😀'; root.mkdir()
            env = {k: v for k, v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
            env.update(HOME=str(root), USERPROFILE=str(root), LOCALAPPDATA=str(root), APPDATA=str(root))
            dbpath = (root if os.name == 'nt' else root / '.local/share') / 'Qbrain/brains/pages/brain.db'
            def sql(text, params=()):
                with closing(sqlite3.connect(dbpath)) as db:
                    db.execute('PRAGMA foreign_keys=ON')
                    rows = db.execute(text, params).fetchall(); db.commit(); return rows
            def snap():
                with closing(sqlite3.connect(dbpath)) as db:
                    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
                    data = [(t, sorted(db.execute('SELECT * FROM "'+t+'"').fetchall(),key=repr)) for t in tables]
                    schema = db.execute('SELECT * FROM sqlite_master ORDER BY name').fetchall()
                backups = sorted((x.name, digest(x.read_bytes())) for x in dbpath.parent.glob('*.bak'))
                return digest(repr((data,schema,backups)).encode())
            def call(argv, payload=None, code=0, json_out=True):
                data = payload if isinstance(payload,bytes) else b'' if payload is None else encode(payload)
                r = subprocess.run([str(exe),*argv,'--brain','pages'], input=data, env=env,cwd=root,
                                   stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
                index=len(commands)+1
                row={'index':index,'argv':argv,'exit':r.returncode,'expected_exit':code,
                     'stdin_sha256':digest(data),'stdout_sha256':digest(r.stdout),'stderr_sha256':digest(r.stderr),
                     'stdout_bytes':len(r.stdout)}
                commands.append(row)
                if a.raw_dir:
                    for suffix,raw in (('stdin',data),('stdout',r.stdout),('stderr',r.stderr)):
                        (a.raw_dir/f'{index:04}.{suffix}').write_bytes(raw)
                if r.returncode!=code: raise AssertionError(f'{argv} exit={r.returncode}, want={code}: {r.stdout[:300]!r} {r.stderr[:200]!r}')
                return json.loads(r.stdout) if json_out else r.stdout
            def fact(action, payload=None, extra=(), source='default',code=0):
                return call(['fact',action,'--source',source,*extra],payload,code)
            def listing(fid, *, state=None, limit=None, budget=None, after=None, token=None, source='default',code=0):
                extra=['--id',fid]
                for flag,val in (('--state',state),('--limit',limit),('--max-bytes',budget),('--after-id',after),('--snapshot',token)):
                    if val is not None: extra += [flag,str(val)]
                return fact('usage-list',extra=extra,source=source,code=code)
            def seed(fragment, quote='I prefer audited usage receipts 中文😀.',source='default'):
                event=call(['memory','capture','--source',source,'--manual'],
                    {'session_id':'audit','fragment_id':fragment,'messages':[{'role':'user','content':quote}]})['event_id']
                call(['memory','extract','--source',source,'--event',event])
                item=next(x for x in call(['memory','read','--source',source,'--limit','50'])['items'] if x['event_id']==event)
                value=fact('create',{'predicate':'audit.preference','item_id':item['item_id']},source=source)
                return value,event,item
            def uid(i): return f'{i:064x}'
            def use(f,i,source='default'):
                return fact('report-use',{'fact_id':f['fact_id'],'usage_id':uid(i),'expected_revision':f['revision']},source=source)
            def revoke(fid,i): return fact('revoke-use',{'fact_id':fid,'usage_id':uid(i)})
            def rpc(name,args,write=False):
                messages=[{'jsonrpc':'2.0','id':0,'method':'initialize','params':{}},
                    {'jsonrpc':'2.0','method':'notifications/initialized'},
                    {'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':name,'arguments':args}}]
                raw=call(['serve','--tool-profile','memory',*(['--allow-write'] if write else [])],
                         b'\n'.join(encode(x) for x in messages)+b'\n',json_out=False)
                return next(json.loads(s)['result'] for s in raw.splitlines() if json.loads(s).get('id')==1)
            call(['init','--no-default'],json_out=False)
            call(['config','set','memory.writeback','salient','--local'],json_out=False)
            call(['config','set','mcp.allowed_sources','default','--local'],json_out=False)
            before=snap()
            need(listing('a'*64,code=1)['error']['code']=='fact_not_found','unknown fact list denied')
            need(snap()==before,'unknown fact list never creates schema or backup')
            f,event,item=seed('first');fid=f['fact_id'];before=snap()
            empty=listing(fid)
            need(empty['items']==[] and not empty['initialized'] and not empty['has_more'] and empty['next_after_id'] is None,'empty receipt list is terminal and uninitialized')
            need(len(empty['snapshot'])==64 and empty['snapshot']==listing(fid)['snapshot'],'empty snapshot deterministic')
            need(snap()==before,'empty list leaves every table and backup unchanged')
            for i,bad in enumerate(({'limit':0},{'limit':51},{'limit':'1x'},{'limit':'true'}, {'budget':511},{'budget':32769},
                                    {'state':'active'},{'state':''},{'after':'a'*64},{'token':'b'*64},
                                    {'after':'x','token':'b'*64},{'after':'a'*64,'token':'bad'})):
                need('error' in listing(fid,code=1,**bad),f'argument preflight rejection {i+1:02}')
            for i,args in enumerate((['--id',fid,'--history'],['--id',fid,'--id',fid],['--id',fid,'--query','x'],['--id'],[])):
                need('error' in fact('usage-list',extra=args,code=1),f'strict CLI options {i+1:02}')
            need(snap()==before,'all invalid empty-list requests leave optional schema absent')
            receipts={}
            for i in range(1,5): receipts[uid(i)]=use(f,i)
            revoke(fid,2)
            support,event2,item2=seed('independent-support')
            f=fact('attach',{'fact_id':fid,'item_id':item2['item_id']})
            for i in range(5,11): receipts[uid(i)]=use(f,i)
            revoke(fid,7)
            before=snap();full=listing(fid,limit=50)
            wanted={'all':list(range(1,11)),'current':[5,6,8,9,10],'historical':[1,3,4],'withdrawn':[2,7]}
            need([r['usage_id'] for r in full['items']]==[uid(i) for i in wanted['all']],'complete list sorted by receipt ID')
            need(all(set(r)=={'usage_id','fact_revision','reported_at','withdrawn_at','state'} for r in full['items']),'rows are exact metadata-only fields')
            need(full['origin']=='caller_reported' and full['host_consumption_verified'] is False and full['fact_truth_verified'] is False and full['provider_calls']==0,'no verified truth or consumption claim')
            need(full['matched_receipts']==10 and full['fact_revision']==f['revision'] and not full['has_more'],'matching count and terminal state')
            for r in full['items']:
                old=receipts[r['usage_id']]
                if r['reported_at']!=old['reported_at'] or r['fact_revision']!=old['fact_revision']: raise AssertionError('receipt changed')
            need(True,'original receipt time and revision preserved')
            def paginate(state,limit,budget=None):
                page=listing(fid,state=state,limit=limit,budget=budget);rows=list(page['items']);token=page['snapshot'];n=1
                while page['has_more']:
                    if not page['items'] or n>20: raise AssertionError('non-advancing pagination')
                    page=listing(fid,state=state,limit=limit,budget=budget,after=page['next_after_id'],token=token)
                    if page['snapshot']!=token: raise AssertionError('unstable read snapshot')
                    rows+=page['items'];n+=1
                if page['next_after_id'] is not None: raise AssertionError('terminal cursor')
                return rows
            for state,ids in wanted.items():
                rows=paginate(state,2)
                need([r['usage_id'] for r in rows]==[uid(i) for i in ids],'complete filtered pagination '+state)
            need([r['usage_id'] for r in paginate('all',50,1100)]==[uid(i) for i in wanted['all']],'byte-limited pagination has no skipped or duplicated rows')
            need(snap()==before,'all audit pages leave rows schema backups and fact revisions unchanged')
            first=listing(fid,limit=1);page_bytes=commands[-1]['stdout_bytes']
            exact=listing(fid,limit=1,budget=page_bytes)
            need(exact==first and commands[-1]['stdout_bytes']==page_bytes,'exact byte budget includes CLI newline')
            need(listing(fid,limit=1,budget=page_bytes-1,code=1)['error']['code']=='fact_usage_byte_budget','one byte too small rejects instead of empty looping page')
            nextpage=listing(fid,after=first['next_after_id'],token=first['snapshot'],limit=50)
            need([r['usage_id'] for r in nextpage['items']]==[uid(i) for i in range(2,11)],'page-size changes preserve cursor meaning')
            terminal=listing(fid,after=uid(10),token=full['snapshot'])
            need(terminal['items']==[] and not terminal['has_more'] and terminal['next_after_id'] is None,'explicit end cursor returns terminal empty page')
            need(listing(fid,after=uid(123),token=full['snapshot'],code=1)['error']['code']=='fact_usage_cursor_invalid','unknown cursor rejected')
            current=listing(fid,state='current',limit=1)
            need(listing(fid,state='current',after=uid(1),token=current['snapshot'],code=1)['error']['code']=='fact_usage_cursor_invalid','cursor outside requested filter rejected')
            need(listing(fid,state='withdrawn',after=first['next_after_id'],token=first['snapshot'],code=1)['error']['code']=='fact_usage_snapshot_conflict','snapshot cannot cross filters')
            need(listing(support['fact_id'],after=first['next_after_id'],token=first['snapshot'],code=1)['error']['code']=='fact_usage_snapshot_conflict','snapshot cannot cross facts')
            sql("INSERT INTO sources(id,name) VALUES('other','other')")
            other,_,_=seed('other-source',source='other');use(other,1,source='other')
            need(listing(fid,source='other',code=1)['error']['code']=='fact_not_found','foreign-source fact cannot be listed')
            need(listing(other['fact_id'],source='other',after=uid(1),token=first['snapshot'],code=1)['error']['code']=='fact_usage_snapshot_conflict','snapshot cannot cross source scope')
            r=rpc('memory_read',{'view':'usage_receipts','fact_id':fid,'limit':2})
            need(not r.get('isError') and len(json.loads(r['content'][-1]['text'])['items'])==2,'read-only MCP lists receipt IDs')
            for i,extra in enumerate(({'receipt_state':'nonsense'},{'snapshot':'b'*64},{'query':'x'},{'limit':True},{'limit':1.5})):
                need(rpc('memory_read',{'view':'usage_receipts','fact_id':fid,**extra}).get('isError') is True,f'MCP invalid argument {i+1:02}')
            need(rpc('memory_read',{'view':'usage_receipts','fact_id':other['fact_id'],'source_id':'other'}).get('isError') is True,'MCP source authorization retained')
            need(rpc('memory_read',{'view':'usage','fact_id':fid,'snapshot':first['snapshot']}).get('isError') is True,'new cursor rejected by old summary view')
            needed={'fact_id':fid,'usage_id':uid(5)};before=snap()
            need(rpc('memory_write',{'action':'fact_revoke_use','payload':encode(needed).decode()}).get('isError') is True,'discovering a receipt does not authorize revocation')
            need(snap()==before,'denied withdrawal leaves receipt unchanged')
            saved=listing(fid,limit=2);revoke(fid,5)
            need(listing(fid,after=saved['next_after_id'],token=saved['snapshot'],code=1)['error']['code']=='fact_usage_snapshot_conflict','withdrawal invalidates continuation')
            need(next(r for r in listing(fid,limit=50)['items'] if r['usage_id']==uid(5))['state']=='withdrawn','discovered receipt can be explicitly withdrawn')
            saved=listing(fid,limit=2);use(f,0)
            need(listing(fid,after=saved['next_after_id'],token=saved['snapshot'],code=1)['error']['code']=='fact_usage_snapshot_conflict','new lower-sorted ID cannot be silently skipped')
            saved=listing(fid,limit=2);use(f,6)
            need(listing(fid,after=saved['next_after_id'],token=saved['snapshot'])['snapshot']==saved['snapshot'],'idempotent retry does not invalidate unchanged snapshot')
            # Deliberate corruption fixture targets rows outside the first page.
            for kind in ('future_revision','noninteger_time','invalid_id','blob_id'):
                row=sql('SELECT * FROM memory_fact_usage WHERE source_id=? AND usage_id=?',('default',uid(10)))[0]
                with closing(sqlite3.connect(dbpath)) as db:
                    db.execute('PRAGMA ignore_check_constraints=ON')
                    if kind=='future_revision': db.execute('UPDATE memory_fact_usage SET fact_revision=99 WHERE usage_id=? AND source_id=?',(uid(10),'default'))
                    if kind=='noninteger_time': db.execute("UPDATE memory_fact_usage SET reported_at='bad' WHERE usage_id=? AND source_id=?",(uid(10),'default'))
                    if kind=='invalid_id': db.execute("UPDATE memory_fact_usage SET usage_id='INVALID' WHERE usage_id=? AND source_id=?",(uid(10),'default'))
                    if kind=='blob_id': db.execute('UPDATE memory_fact_usage SET usage_id=? WHERE usage_id=? AND source_id=?',(uid(10).encode(),uid(10),'default'))
                    db.commit()
                need('error' in listing(fid,state='withdrawn',limit=1,code=1),'off-page and off-filter corruption rejected '+kind)
                sql('DELETE FROM memory_fact_usage WHERE fact_id=? AND source_id=? AND (usage_id=? OR usage_id=? OR usage_id=?)',(fid,'default',uid(10),'INVALID',uid(10).encode()))
                sql('INSERT INTO memory_fact_usage VALUES(?,?,?,?,?,?)',row)
            need(listing(fid,limit=50)['snapshot']==saved['snapshot'],'corruption fixtures restored exact snapshot')
            rows=sql('SELECT * FROM memory_fact_usage WHERE fact_id=? AND source_id=?',(fid,'default'))
            sql('DELETE FROM memory_fact_usage WHERE fact_id=? AND source_id=?',(fid,'default'))
            with closing(sqlite3.connect(dbpath)) as db:
                db.executemany('INSERT INTO memory_fact_usage VALUES(?,?,?,?,?,?)',[('default',uid(100+i),fid,f['revision'],1,None) for i in range(4096)]);db.commit()
            need(listing(fid,limit=1)['matched_receipts']==4096,'maximum permitted set remains bounded and pageable')
            sql('INSERT INTO memory_fact_usage VALUES(?,?,?,?,?,?)',('default',uid(9999),fid,f['revision'],1,None))
            need(listing(fid,limit=1,code=1)['error']['code']=='fact_usage_invalid_metadata','over-cap data rejected before partial page')
            sql('DELETE FROM memory_fact_usage WHERE fact_id=? AND source_id=?',(fid,'default'))
            with closing(sqlite3.connect(dbpath)) as db:
                db.executemany('INSERT INTO memory_fact_usage VALUES(?,?,?,?,?,?)',rows);db.commit()
            need(listing(fid,limit=50)['snapshot']==saved['snapshot'],'capacity fixture restored exact snapshot')
            saved=listing(fid,limit=2)
            fact('archive',{'fact_id':fid,'expected_revision':f['revision']})
            need(listing(fid)['archived'] is True,'archived fact still labels auditable metadata')
            need(listing(fid,after=saved['next_after_id'],token=saved['snapshot'],code=1)['error']['code']=='fact_usage_snapshot_conflict','archive or revision change invalidates cursor')
            call(['memory','forget','--event',event]);call(['memory','forget','--event',event2])
            need(listing(fid,code=1)['error']['code']=='fact_not_found','last support forget removes audit visibility')
            need(sql('SELECT COUNT(*) FROM memory_fact_usage WHERE fact_id=?',(fid,))[0][0]==0,'forgotten fact leaves no orphan audit records')
            need(sql('PRAGMA foreign_key_check')==[],'final foreign keys remain valid')
    except Exception as error:
        checks.append({'name':'unexpected_exception','passed':False,'error':str(error)})
    result={'schema':'qbrain-n47u-process-v1','binary_sha256':digest(exe.read_bytes()),
            'test_sha256':digest(Path(__file__).read_bytes()),'passed':sum(x['passed'] for x in checks),
            'failed':sum(not x['passed'] for x in checks),'checks':checks,'commands':commands,
            'command_count':len(commands),'real_client_tested':False,'provider_calls':0}
    a.report.parent.mkdir(parents=True,exist_ok=True)
    with a.report.open('x',encoding='utf-8') as out: json.dump(result,out,indent=2,ensure_ascii=False);out.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('checks','commands')}))
    if result['failed']:
        print(json.dumps([x for x in checks if not x['passed']],ensure_ascii=False));return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
