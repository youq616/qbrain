"""Fresh-process session-memory review on disposable SQLite brains.

Independent of test helpers. Tests only local explicit-user extraction, multiple
sources/brains, exact quotation, expiry, edited evidence, policy and tombstones.
This is NOT real client/model consumption or a PostgreSQL runtime test.
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


def enc(x):
    return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def sha(x):
    return hashlib.sha256(x).hexdigest()

def run(binary, output):
    output.mkdir(parents=True,exist_ok=False);(output/'raw').mkdir()
    checks=[];commands=[]
    def need(ok,label):
        checks.append(dict(name=label,passed=bool(ok)))
        if not ok:raise ValueError(label)
    result={}
    try:
        with tempfile.TemporaryDirectory(prefix='qbrain-independent-session-') as tmp:
            home=Path(tmp)/'脑库 space 😀';home.mkdir()
            env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
            env.update(HOME=str(home),USERPROFILE=str(home),LOCALAPPDATA=str(home),APPDATA=str(home))
            root=(home if os.name=='nt' else home/'.local/share')/'Qbrain'
            def invoke(brain, args, payload=None):
                data=b'' if payload is None else enc(payload)
                p=subprocess.run([str(binary),*args,'--brain',brain],input=data,capture_output=True,env=env,cwd=home,timeout=25)
                return dict(brain=brain,args=args,exit=p.returncode,stdin=data,stdout=p.stdout,stderr=p.stderr)
            def record(row, expected=0, parse=True):
                idx=len(commands);meta={k:row[k] for k in ('brain','args','exit')};meta['hashes']={}
                for ext in ('stdin','stdout','stderr'):
                    (output/'raw'/f'{idx:03d}.{ext}').write_bytes(row[ext]);meta['hashes'][ext]=sha(row[ext])
                commands.append(meta)
                need(row['exit']==expected,'exact process exit '+str(idx))
                need(row['stderr']==b'','empty stderr '+str(idx))
                return json.loads(row['stdout']) if parse else row['stdout']
            def cli(brain,action,payload=None,opts=(),source='alpha',expected=0):
                return record(invoke(brain,['memory',action,'--source',source,*opts],payload),expected)
            def sql(brain,statement,values=()):
                dbfile=root/'brains'/brain/'brain.db'
                with closing(sqlite3.connect(dbfile)) as db:
                    rows=db.execute(statement,values).fetchall();db.commit();return rows
            def config(brain,key,value):
                sql(brain,'INSERT INTO config(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value))
            for brain in ('primary','other'):
                record(invoke(brain,['init']),parse=False)
                for source in ('alpha','beta'):
                    sql(brain,'INSERT INTO sources(id,name) VALUES(?,?)',(source,source))
                config(brain,'memory.writeback','salient');config(brain,'embed.auto','false')
            def payload(fragment='original',expiry=None):
                p={'session_id':'first-session-独立','fragment_id':fragment,'messages':[
                    {'role':'user','content':'I prefer local C++ and do not permit automatic publication. 中文😀'},
                    {'role':'assistant','content':'I prefer ASSISTANT_FALSE_FACT.'},
                    {'role':'tool','content':'I decided TOOL_FALSE_FACT.'},
                    {'role':'unknown','content':'I prefer UNKNOWN_FALSE_FACT.'},
                    {'role':'user','content':'我决定保留完整原话，而不是模型推断。'}]}
                if expiry is not None:p['expires_at']=expiry
                return p
            p=payload()
            first=cli('primary','capture',p);eid=first['event_id']
            need(cli('primary','read')['items']==[],'archive is not extracted fact')
            need(cli('primary','extract',opts=['--event',eid])['item_count']==2,'only two complete user quotes')
            items=cli('primary','read')['items']
            need({r['quote'] for r in items}=={p['messages'][0]['content'],p['messages'][4]['content']},'exact quote set excludes assistant/tool/unknown')
            need(all(r['event_id']==eid and r['source_id']=='alpha' for r in items),'source identity in every item')
            need(cli('primary','read',source='beta')['items']==[],'other source isolated')
            need(cli('other','read')['items']==[],'other brain isolated')
            # Initialize this brain with a DIFFERENT event before testing a missing ID.
            # An uninitialized module correctly returns initialized=false, not an error.
            cli('other','capture',payload('other-only'))
            need(cli('other','status',opts=['--event',eid],expected=1)['error']['code']=='event_not_found','cross-brain event unavailable')
            # Every invocation is a new process; no in-memory cache can supply these rows.
            p2=payload('new-session');p2['session_id']='second-session-独立'
            second=cli('primary','capture',p2)['event_id'];cli('primary','extract',opts=['--event',second])
            need(len(cli('primary','read')['items'])==2,'cross-session exact quote deduplication')
            cli('primary','forget',opts=['--event',eid])
            after=cli('primary','read')['items'];need(len(after)==2 and all(r['event_id']==second for r in after),'forget one evidence retains independently attested copy')
            cli('primary','forget',opts=['--event',second])
            need(cli('primary','read')['items']==[],'forget all evidence removes recall')
            need(cli('primary','capture',p)['status']=='forgotten','same-fragment replay blocked by tombstone')
            need(cli('primary','extract',opts=['--event',eid],expected=1)['error']['code']=='event_forgotten','forgotten event cannot extract')
            need(sql('primary',"SELECT count(*) FROM memory_events WHERE status='forgotten'")[0][0]==2,'both tombstones persist in real DB')
            edited=cli('primary','capture',payload('edited'))['event_id']
            sql('primary',"UPDATE pages SET body='independently edited evidence' WHERE slug=?",('sessions/'+edited,))
            need(cli('primary','extract',opts=['--event',edited],expected=1)['error']['code']=='evidence_unavailable','edited body cannot ground memory')
            cli('primary','forget',opts=['--event',edited])
            need(sql('primary',"SELECT body FROM pages WHERE slug=?",('sessions/'+edited,))==[('independently edited evidence',)],'forget does not destroy externally edited page')
            expired=cli('primary','capture',payload('expired',1))['event_id']
            need(cli('primary','extract',opts=['--event',expired],expected=1)['error']['code']=='evidence_unavailable','expired statement excluded')
            far=cli('primary','capture',payload('far-future',253402300799))['event_id']
            cli('primary','extract',opts=['--event',far])
            need(all(r['expires_at']==253402300799 for r in cli('primary','read')['items']),'64-bit future expiry roundtrip')
            manual=payload('manual')
            config('primary','memory.writeback','off')
            need(cli('primary','capture',manual)['status']=='skipped','automatic off')
            mid=cli('primary','capture',manual,opts=['--manual'])['event_id']
            need(cli('primary','extract',opts=['--event',mid])['item_count']==2,'explicit manual save does not require auto capture')
            need(cli('primary','extract',opts=['--event',far],expected=1)['error']['code']=='writeback_off','off policy respected for automatic event')
            config('primary','memory.writeback','salient')
            model=cli('primary','capture',payload('model-denied'))['event_id']
            need(cli('primary','extract',opts=['--event',model,'--method','model'],expected=1)['error']['code']=='external_extraction_denied','model opt-in separate from save')
            need(sql('primary','SELECT attempts FROM memory_events WHERE event_id=?',(model,))==[(0,)],'denied model creates no attempt')
            secret=payload('secret');secret['messages'][0]['content']='api_key=synthetic-review-secret'
            need(cli('primary','capture',secret,expected=1)['error']['code']=='sensitive_material_rejected','obvious secret rejected')
            # New processes, no automatic retry on failure. Existing schema is already initialized.
            args=['memory','capture','--source','beta']
            with ThreadPoolExecutor(max_workers=4) as pool:
                concurrent=list(pool.map(lambda _:invoke('primary',args,payload('race')),range(8)))
            captures=[record(r) for r in concurrent]
            need(len({r['event_id'] for r in captures})==1 and sum(not r['duplicate'] for r in captures)==1,'eight no-retry concurrent captures have exactly one creator')
            need(sql('primary',"SELECT count(*) FROM memory_events WHERE source_id='beta'")==[(1,)],'one persisted concurrent source event')
            need(sql('primary','PRAGMA integrity_check')==[('ok',)],'storage structurally intact')
            # Retain a consistent synthetic snapshot, not the live database/WAL files.
            with closing(sqlite3.connect(root/'brains/primary/brain.db')) as src,closing(sqlite3.connect(output/'synthetic-final.db')) as dst:
                src.backup(dst)
            result.update(synthetic_snapshot_sha256=sha((output/'synthetic-final.db').read_bytes()))
        result.update(passed=True)
    except Exception as e:
        result.update(passed=False,error=type(e).__name__+': '+str(e))
    result.update(schema='qbrain-independent-session-review-v1',backend='sqlite',optimized=not __debug__,
        binary_sha256=sha(binary.read_bytes()),reviewer_sha256=sha(Path(__file__).read_bytes()),
        commands=commands,checks=checks,command_count=len(commands),check_count=len(checks),
        native_retries=0,model_requests_sent=0,real_client_consumption_verified=False,postgres_execution=False)
    (output/'RESULT.json').write_bytes(enc(result)+b'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('commands','checks')}))
    return 0 if result['passed'] else 1

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();raise SystemExit(run(a.binary.resolve(strict=True),a.output.resolve()))
