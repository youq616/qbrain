"""N47Y native/portable corruption regressions. Disposable synthetic brains only.

Public CLI creates all ordinary evidence and receipts. SQL mutations are explicitly
named corruption/capacity/permission fixtures; no real user database is opened.
The optional baseline is executed only for a differential control, not as the fix.
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
import time

KINDS = ('usage_blob', 'fact_blob', 'source_blob', 'nul_suffix', 'oversize_id',
         'invalid_hex', 'bad_revision', 'future_revision', 'negative_time',
         'withdraw_before_report', 'revision_blob', 'time_blob', 'withdraw_blob', 'duplicate_alias')
ROUTES = ('summary', 'page', 'new_report', 'duplicate_report', 'revoke')
BASELINE_SOURCE = 'ad31f404ba5ca94b15dc992bf9f219fa572ab167'
BASELINES = {'7399af97dde5b97cc87667dc7e0e3fbdbf79b8b435fbfb62f01f2cb4cfd4e57e',
             '838955a0ad88779af08c53396b773d62b327cccd4f216a18379f0a76ffa4c9cf'}


def digest(raw): return hashlib.sha256(raw).hexdigest()
def encode(value): return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def exercise(binary: Path, baseline: Path, output: Path, baseline_source: Path | None = None) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    rawdir = output/'raw'; rawdir.mkdir()
    records, checks, observations = [], [], []
    lock = threading.Lock()
    def check(ok, name):
        checks.append({'name': name, 'passed': bool(ok)})
        if not ok: raise ValueError(name)
    failure = None
    try:
        if baseline_source is None:
            pinned = digest(baseline.read_bytes()) in BASELINES
        else:
            base = baseline_source.resolve(strict=True)
            head = subprocess.run(['git','-C',str(base),'rev-parse','HEAD'],capture_output=True,check=True).stdout.decode().strip()
            clean = subprocess.run(['git','-C',str(base),'diff','--quiet','HEAD']).returncode == 0
            pinned = head == BASELINE_SOURCE and clean and baseline.is_relative_to(base/'build')
        check(pinned, 'pinned baseline executable')
        with tempfile.TemporaryDirectory(prefix='n47y-') as temp:
            root = Path(temp)/'integrity 审核 space 😀'; root.mkdir()
            env = {k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
            env.update(HOME=str(root), USERPROFILE=str(root), LOCALAPPDATA=str(root), APPDATA=str(root))
            dbfile = (root if os.name == 'nt' else root/'.local/share')/'Qbrain/brains/integrity/brain.db'
            def call(args, payload=None, *, old=False):
                body = payload if isinstance(payload, bytes) else b'' if payload is None else encode(payload)
                p = subprocess.run([str(baseline if old else binary), *args, '--brain', 'integrity'],
                    input=body, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=root, timeout=30)
                with lock:
                    number=len(records)+1
                    for suffix, data in [('stdin',body),('stdout',p.stdout),('stderr',p.stderr)]:
                        (rawdir/f'{number:04}.{suffix}').write_bytes(data)
                    records.append({'index':number,'argv':args,'baseline':old,'exit':p.returncode,
                        'stdin_sha256':digest(body),'stdout_sha256':digest(p.stdout),'stderr_sha256':digest(p.stderr)})
                return p.returncode, p.stdout
            def jcall(args, payload=None, *, old=False):
                code, raw=call(args,payload,old=old)
                return code, json.loads(raw)
            def good(args, payload=None):
                code, obj=jcall(args,payload)
                if code: raise ValueError('unexpected command rejection: '+str(args)+': '+str(obj))
                return obj
            def sql(query, args=(), *, corrupt=False):
                with closing(sqlite3.connect(dbfile, timeout=10)) as d:
                    d.execute('PRAGMA foreign_keys='+('OFF' if corrupt else 'ON'))
                    if corrupt: d.execute('PRAGMA ignore_check_constraints=ON')
                    rows=d.execute(query,args).fetchall(); d.commit(); return rows
            def state():
                with closing(sqlite3.connect(dbfile)) as d:
                    names=[r[0] for r in d.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
                    tables={n:sorted(d.execute('SELECT * FROM "'+n+'"').fetchall(),key=repr) for n in names}
                    schema=d.execute('SELECT * FROM sqlite_master ORDER BY name').fetchall()
                backups=sorted((p.name,digest(p.read_bytes())) for p in dbfile.parent.glob('*.bak'))
                return digest(repr((tables,schema,backups)).encode())
            def receipt_rows(): return sql('SELECT * FROM memory_fact_usage ORDER BY source_id,usage_id')
            def restore(rows):
                with closing(sqlite3.connect(dbfile)) as d:
                    d.execute('PRAGMA foreign_keys=OFF');d.execute('DELETE FROM memory_fact_usage')
                    d.executemany('INSERT INTO memory_fact_usage VALUES(?,?,?,?,?,?)',rows);d.commit()
            def seed(label, source='default', expiry=0):
                e=good(['memory','capture','--source',source,'--manual'],{'session_id':'integrity',
                    'fragment_id':label,'expires_at':expiry,'messages':[{'role':'user','content':'I prefer integrity '+label+'.'}]})
                good(['memory','extract','--source',source,'--event',e['event_id']])
                items=good(['memory','read','--source',source,'--limit','50'])['items']
                item=next(x for x in items if x['event_id']==e['event_id'])
                f=good(['fact','create','--source',source],{'predicate':'integrity.preference','item_id':item['item_id']})
                return f,e['event_id']
            def uid(i): return f'{i:064x}'
            def payload(f,i): return {'fact_id':f['fact_id'],'usage_id':uid(i),'expected_revision':f['revision']}
            def use(f,i,source='default'): return good(['fact','report-use','--source',source],payload(f,i))
            def revoke(f,i): return good(['fact','revoke-use'],{'fact_id':f['fact_id'],'usage_id':uid(i)})
            def read(f, page=False): return ['fact','usage-list' if page else 'usage','--id',f['fact_id']]
            for args in (['init','--no-default'],['config','set','memory.writeback','salient','--local'],
                         ['config','set','mcp.allowed_sources','default','--local']):
                if call(args)[0]: raise ValueError('setup failed')
            a,ae=seed('A'); b,be=seed('B')
            initial=state()
            for page in (False,True):
                code,r=jcall(read(a,page));check(code==0 and not r['initialized'],'empty read '+str(page))
            check(state()==initial,'empty reads do not create schema or backups')
            use(a,1);use(a,2);revoke(a,2)
            good(['fact','archive'],{'fact_id':a['fact_id'],'expected_revision':a['revision']})
            a=good(['fact','read','--id',a['fact_id']])['items'][0]
            good(['fact','restore'],{'fact_id':a['fact_id'],'expected_revision':a['revision']})
            a=good(['fact','read','--id',a['fact_id']])['items'][0]
            use(a,3);use(b,10)
            sql("INSERT INTO sources(id,name) VALUES('other','other')")
            other,_=seed('other','other');use(other,3,'other')
            healthy=receipt_rows(); initial=state()
            compare=[read(a),*[read(a,True)+['--state',s,'--limit','2'] for s in ('all','current','historical','withdrawn')]]
            for i,args in enumerate(compare):
                check(call(args)==call(args,old=True),'valid read byte compatibility '+str(i))
            check(jcall(['fact','report-use'],payload(a,3))==jcall(['fact','report-use'],payload(a,3),old=True),'valid duplicate response compatibility')
            check(jcall(['fact','revoke-use'],{'fact_id':a['fact_id'],'usage_id':uid(2)})==
                  jcall(['fact','revoke-use'],{'fact_id':a['fact_id'],'usage_id':uid(2)},old=True),'valid withdrawn response compatibility')
            check(state()==initial,'valid compatibility calls are unchanged state')
            # Baseline negative control. Restore its attempted write before using the fix.
            sql('UPDATE memory_fact_usage SET usage_id=CAST(usage_id AS BLOB) WHERE source_id=? AND usage_id=?',('default',uid(3)),corrupt=True)
            old_summary=jcall(read(a),old=True);old_page=jcall(read(a,True),old=True)
            old_duplicate=jcall(['fact','report-use'],payload(a,3),old=True)
            count=sql('SELECT count(*) FROM memory_fact_usage WHERE source_id=? AND fact_id=?',('default',a['fact_id']))[0][0]
            observations.append({'case':'baseline_blob_disagreement','summary_exit':old_summary[0],'page_exit':old_page[0],
                'retry_exit':old_duplicate[0],'retry_duplicate':old_duplicate[1].get('duplicate'),'resulting_rows':count})
            check(old_summary[0]==0 and old_page[0]==1 and old_duplicate[0]==0 and old_duplicate[1]['duplicate'] is False and count==4,
                  'baseline reproduces inconsistent read and logical duplicate')
            restore(healthy);check(state()==initial,'baseline corruption and write restored')
            for kind in KINDS:
                if kind=='duplicate_alias':
                    row=next(r for r in healthy if r[0]=='default' and r[1]==uid(3));row=(row[0],row[1].encode(),*row[2:])
                    sql('INSERT INTO memory_fact_usage VALUES(?,?,?,?,?,?)',row,corrupt=True)
                else:
                    col,value={'usage_blob':('usage_id',uid(3).encode()),'fact_blob':('fact_id',a['fact_id'].encode()),
                        'source_blob':('source_id',b'default'),'nul_suffix':('usage_id',uid(3)+'\0hidden'),
                        'oversize_id':('usage_id','c'*65536),'invalid_hex':('usage_id','g'*64),
                        'bad_revision':('fact_revision','bad'),'future_revision':('fact_revision',a['revision']+9),
                        'negative_time':('reported_at',-1),'withdraw_before_report':('withdrawn_at',1),
                        'revision_blob':('fact_revision',b'1'),'time_blob':('reported_at',b'1'),
                        'withdraw_blob':('withdrawn_at',b'1')}[kind]
                    sql('UPDATE memory_fact_usage SET '+col+'=? WHERE source_id=? AND usage_id=?',(value,'default',uid(3)),corrupt=True)
                damaged=state()
                routes={'summary':(read(a),None),'page':(read(a,True)+['--state','withdrawn','--limit','1'],None),
                    'new_report':(['fact','report-use'],payload(a,4)), 'duplicate_report':(['fact','report-use'],payload(a,3)),
                    'revoke':(['fact','revoke-use'],{'fact_id':a['fact_id'],'usage_id':uid(1)})}
                for route,(args,body) in routes.items():
                    code,r=jcall(args,body)
                    check(code==1 and r.get('error',{}).get('code') in ('fact_usage_invalid_metadata','fact_invalid_id')
                          and state()==damaged,kind+'/'+route+' rejected without writes')
                restore(healthy);check(state()==initial,kind+'/restored')
            # The requested logical ID is also reserved when its damaged row belongs to another fact.
            sql('UPDATE memory_fact_usage SET usage_id=CAST(usage_id AS BLOB) WHERE source_id=? AND usage_id=?',('default',uid(10)),corrupt=True)
            damaged=state();code,r=jcall(['fact','report-use'],payload(a,10))
            check(code==1 and r['error']['code']=='fact_usage_invalid_metadata' and state()==damaged,'cross-fact BLOB ID reuse rejected')
            check(call(read(a))==call(read(a),old=True),'unrelated corrupted fact does not block summary')
            check(not use(a,4)['duplicate'],'unrelated corrupted fact does not block a different new ID')
            restore(healthy);check(state()==initial,'cross-fact fixture restored')
            # A different authorized source's malformed row must not become global denial.
            sql('UPDATE memory_fact_usage SET usage_id=CAST(usage_id AS BLOB) WHERE source_id=? AND usage_id=?',('other',uid(3)),corrupt=True)
            damaged=state()
            check(good(read(a))['stored_receipts']==3 and use(a,3)['duplicate'] and state()==damaged,'another source corruption stays isolated')
            restore(healthy)
            # Authorization must still precede writes and source-scoped data inspection.
            def rpc(tool,args,write=False):
                req=[{'jsonrpc':'2.0','id':0,'method':'initialize','params':{}},
                     {'jsonrpc':'2.0','method':'notifications/initialized'},
                     {'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':tool,'arguments':args}}]
                code,raw=call(['serve','--tool-profile','memory',*(['--allow-write'] if write else [])],
                    b'\n'.join(json.dumps(x).encode() for x in req)+b'\n')
                if code: raise ValueError('MCP process failure')
                return next(json.loads(line)['result'] for line in raw.splitlines() if json.loads(line).get('id')==1)
            before=state()
            check(rpc('memory_write',{'action':'fact_report_use','payload':json.dumps(payload(a,4))}).get('isError') is True,'MCP write remains default denied')
            check(rpc('memory_read',{'view':'usage','fact_id':other['fact_id'],'source_id':'other'}).get('isError') is True,'MCP source restriction retained')
            check(state()==before,'denied MCP operations are read-only')
            sql('UPDATE memory_fact_usage SET usage_id=CAST(usage_id AS BLOB) WHERE source_id=? AND usage_id=?',('default',uid(3)),corrupt=True)
            damaged=state()
            with ThreadPoolExecutor(max_workers=4) as pool:
                results=list(pool.map(lambda _:jcall(['fact','report-use'],payload(a,3)),range(4)))
            check(all(code==1 for code,r in results) and state()==damaged,'concurrent retries cannot duplicate damaged identity')
            restore(healthy)
            with ThreadPoolExecutor(max_workers=4) as pool:
                results=list(pool.map(lambda _:jcall(['fact','report-use'],payload(a,4)),range(4)))
            check(all(code==0 for code,r in results) and sum(not r['duplicate'] for code,r in results)==1,'healthy concurrent duplicate recorded once')
            restore(healthy)
            # Check query plans for the same bound-key predicates used by the shared reader.
            predicates = {
                'ordered_set': 'source_id=?1 AND fact_id=?2 ORDER BY usage_id LIMIT 4097',
                'source_alias': 'source_id=CAST(?1 AS BLOB) AND fact_id IN (?2,CAST(?2 AS BLOB)) LIMIT 1',
                'fact_alias': 'source_id=?1 AND fact_id=CAST(?2 AS BLOB) LIMIT 1',
                'receipt_id': 'source_id IN (?1,CAST(?1 AS BLOB)) AND usage_id IN (?2,CAST(?2 AS BLOB)) LIMIT 5'}
            for name,predicate in predicates.items():
                plan=sql('EXPLAIN QUERY PLAN SELECT usage_id FROM memory_fact_usage WHERE '+predicate,
                         ('default',uid(3) if name=='receipt_id' else a['fact_id']))
                details=' '.join(str(r[-1]) for r in plan)
                check('SEARCH memory_fact_usage USING' in details and 'SCAN memory_fact_usage' not in details
                      and 'TEMP B-TREE' not in details,'indexed no-sort lookup '+name)
            # Explicit capacity fixture; do not spend4096 external process calls to fill it.
            restore([r for r in healthy if r[2]!=a['fact_id']])
            with closing(sqlite3.connect(dbfile)) as d:
                d.executemany('INSERT INTO memory_fact_usage VALUES(?,?,?,?,?,?)',
                    [('default',uid(5000+i),a['fact_id'],a['revision'],1,None) for i in range(4096)]);d.commit()
            before=state()
            check(good(read(a))['stored_receipts']==4096 and use(a,5000)['duplicate'],'capacity4096 and duplicate remain valid')
            code,r=jcall(['fact','report-use'],payload(a,9999))
            check(code==1 and r['error']['code']=='fact_usage_capacity' and state()==before,'full capacity refuses without eviction')
            sql('INSERT INTO memory_fact_usage VALUES(?,?,?,?,?,?)',('default',uid(9999),a['fact_id'],a['revision'],1,None))
            before=state();code,r=jcall(['fact','revoke-use'],{'fact_id':a['fact_id'],'usage_id':uid(5000)})
            check(code==1 and r['error']['code']=='fact_usage_invalid_metadata' and state()==before,'over-cap corrupted set cannot be silently changed')
            restore(healthy);check(state()==initial,'capacity fixture restored')
            # Keep withdrawal possible when ordinary fact reads are no longer eligible.
            for status in ('archived','retired'):
                f,e=seed(status);use(f,100 if status=='archived' else 101)
                good(['fact','archive' if status=='archived' else 'retract'],{'fact_id':f['fact_id'],'expected_revision':f['revision']})
                check(revoke(f,100 if status=='archived' else 101)['status']=='withdrawn','valid '+status+' receipt remains revocable')
            expires=int(time.time())+10
            f,e=seed('expires',expiry=expires);use(f,102)
            check(time.time()<expires-2,'expiry fixture prepared before expiry')
            while time.time()<=expires: time.sleep(.05)
            code,r=jcall(read(f));check(code==1 and r['error']['code']=='fact_not_found','expired read remains denied')
            check(revoke(f,102)['status']=='withdrawn','valid expired receipt remains revocable')
            good(['memory','forget','--event',e])
            check(sql('SELECT COUNT(*) FROM memory_fact_usage WHERE fact_id=?',(f['fact_id'],))[0][0]==0,'forget still cascades expired receipts')
            check(sql('PRAGMA foreign_key_check')==[],'final database foreign keys valid')
    except Exception as error:
        failure=type(error).__name__+': '+str(error)
    result={'schema':'qbrain-n47y-integrity-v1','binary_sha256':digest(binary.read_bytes()),
        'baseline_sha256':digest(baseline.read_bytes()),'baseline_source':BASELINE_SOURCE if baseline_source else None,'test_sha256':digest(Path(__file__).read_bytes()),
        'checks':checks,'commands':records,'observations':observations,'passed':sum(x['passed'] for x in checks),
        'failed':sum(not x['passed'] for x in checks)+(1 if failure and not any(not x['passed'] for x in checks) else 0),
        'failure':failure,'command_count':len(records),'real_client_verified':False,'provider_calls':0}
    (output/'report.json').write_bytes(encode(result))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('binary','baseline','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--baseline-source',type=Path)
    a=p.parse_args();r=exercise(a.binary.resolve(strict=True),a.baseline.resolve(strict=True),a.output,a.baseline_source)
    print(json.dumps({k:v for k,v in r.items() if k not in ('checks','commands')},ensure_ascii=False))
    raise SystemExit(0 if r['failed']==0 else 1)
