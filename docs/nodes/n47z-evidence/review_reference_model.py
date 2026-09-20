"""Independent reference-ledger review of fixed N47Z via real persistent MCP.

Only public API writes into disposable data. SQL is read-only for nonmutation
snapshots. No external network/client/model and no production test switch.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import queue
import random
import sqlite3
import subprocess
import tempfile
import threading


def sha(raw): return hashlib.sha256(raw).hexdigest()
def enc(value): return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()


def run(binary: Path, output: Path):
    output.mkdir(parents=True,exist_ok=False)
    checks=[]; records=[]; failure=None; rounds=0; ledger={}; facts=[]; child=None
    def check(ok,name):
        checks.append({'name':name,'passed':bool(ok)})
        if not ok: raise ValueError(name)
    try:
      with tempfile.TemporaryDirectory(prefix='n47z-reference-') as temp:
        root=Path(temp); rng=random.Random(47026)
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','GITHUB_TOKEN','GH_TOKEN'))}
        env.update(HOME=temp,LOCALAPPDATA=temp,USERPROFILE=temp,APPDATA=temp)
        dbpath=(root if os.name=='nt' else root/'.local/share')/'Qbrain/brains/reference/brain.db'
        def snapshot():
            with closing(sqlite3.connect(dbpath)) as db:
                tables=[x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
                rows={n:sorted(db.execute('SELECT * FROM "'+n+'"').fetchall(),key=repr) for n in tables}
                schema=db.execute('SELECT * FROM sqlite_master ORDER BY name').fetchall()
            backups=sorted((p.name,sha(p.read_bytes())) for p in dbpath.parent.glob('*.bak'))
            return sha(repr((rows,schema,backups)).encode())
        def cli(args,body=None,parsed=True):
            raw=b'' if body is None else enc(body)
            p=subprocess.run([str(binary),*args,'--brain','reference'],input=raw,cwd=root,env=env,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
            records.append({'kind':'cli','args':args,'stdin':raw.decode(),'stdout':p.stdout.decode(),'stderr':p.stderr.decode(),'exit':p.returncode})
            if p.returncode or p.stderr: raise ValueError('public setup failed')
            return json.loads(p.stdout) if parsed else p.stdout
        cli(['init','--no-default'],parsed=False)
        cli(['config','set','memory.writeback','salient','--local'],parsed=False)
        cli(['config','set','mcp.allowed_sources','default','--local'],parsed=False)
        for i in range(8):
            ev=cli(['memory','capture','--manual'],{'session_id':'reference-run','fragment_id':str(i),
                'messages':[{'role':'user','content':'I prefer independently checked batch '+str(i)+' 中文.'}]})
            cli(['memory','extract','--event',ev['event_id']])
            mem=cli(['memory','read','--limit','50'])
            item=next(x for x in mem['items'] if x['event_id']==ev['event_id'])
            facts.append(cli(['fact','create'],{'predicate':'reference.preference','item_id':item['item_id']}))
        child=subprocess.Popen([str(binary),'serve','--brain','reference','--tool-profile','memory','--allow-write'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,env=env)
        replies=queue.Queue();errors=[];seq=0
        def reader():
            for line in child.stdout: replies.put(line)
            replies.put(None)
        def errreader():
            for line in child.stderr: errors.append(line)
        t=threading.Thread(target=reader,daemon=True);e=threading.Thread(target=errreader,daemon=True);t.start();e.start()
        def rpc(method,args):
            nonlocal seq
            seq+=1;req={'jsonrpc':'2.0','id':seq,'method':method,'params':args}
            child.stdin.write(enc(req));child.stdin.flush();raw=replies.get(timeout=15)
            if raw is None:raise ValueError('server ended')
            reply=json.loads(raw)
            if reply.get('id')!=seq:raise ValueError('response identity')
            records.append({'kind':'mcp','request':req,'response':reply})
            return reply['result']
        def call(name,args,expected_error=None):
            result=rpc('tools/call',{'name':name,'arguments':args})
            value=json.loads(result['content'][-1]['text'])
            if expected_error is not None:
                check(result['isError'] is True and value.get('error',{}).get('code')==expected_error,'expected rejection '+expected_error)
            elif result['isError']:raise ValueError('unexpected rejection '+str(value))
            return value
        rpc('initialize',{})
        child.stdin.write(enc({'jsonrpc':'2.0','method':'notifications/initialized'}));child.stdin.flush()
        def batch(spec,token=None,error=None):
            if token is None:return call('memory_read',{'view':'usage_batch','payload':enc(spec).decode()},error)
            return call('memory_write',{'action':'fact_usage_batch','payload':enc({**spec,'snapshot':token}).decode()},error)
        for round_no in range(24):
            operation='report' if round_no%3!=2 else 'revoke'
            items=[]
            if operation=='report':
                live=[v for v in ledger.values() if v['withdrawn_at'] is None]
                count=32 if round_no in (0,12) else rng.choice((1,4,8,16,32))
                old=rng.sample(live,min(len(live),count//2))
                items=[{'fact_id':v['fact_id'],'usage_id':v['usage_id'],'expected_revision':v['fact_revision']} for v in old]
                for i in range(count-len(items)):
                    f=facts[i%8] if round_no==0 else rng.choice(facts)
                    items.append({'fact_id':f['fact_id'],'usage_id':sha(f'{round_no}/{i}'.encode()),'expected_revision':f['revision']})
            else:
                old=rng.sample(list(ledger.values()),min(len(ledger),rng.choice((1,8,16,32))))
                items=[{'fact_id':v['fact_id'],'usage_id':v['usage_id']} for v in old]
            rng.shuffle(items);spec={'operation':operation,'items':items};before=snapshot();plan=batch(spec)
            check(snapshot()==before,'round '+str(round_no)+' preview is read-only')
            shuffled=list(items);rng.shuffle(shuffled)
            check(batch({'operation':operation,'items':shuffled})==plan,'round '+str(round_no)+' input order invariant')
            check(plan['atomic'] is True and plan['applied'] is False and plan['changed']==0,'preview flags')
            changes=0
            for decision in plan['items']:
                old=ledger.get(decision['usage_id'])
                expected=(old is None) if operation=='report' else old['withdrawn_at'] is None
                check(decision['will_change'] is expected,'reference agrees with planned change')
                changes+=expected
            check(plan['would_change']==changes and plan['unchanged']==len(items)-changes,'reference planned counts')
            applied=batch(spec,plan['snapshot'])
            check(applied['changed']==changes and applied['atomic'] is True and applied['applied'] is True,'atomic result counts')
            for decision in applied['items']:
                rid=decision['usage_id'];old=ledger.get(rid)
                if operation=='report' and old is None:
                    check(type(decision['reported_at']) is int and decision['withdrawn_at'] is None,'new receipt time')
                    ledger[rid]={k:decision[k] for k in ('fact_id','usage_id','fact_revision','reported_at','withdrawn_at')}
                else:
                    check(decision['reported_at']==old['reported_at'] and decision['fact_revision']==old['fact_revision'] and decision['fact_id']==old['fact_id'],'no retargeted receipt or timestamp')
                    if operation=='revoke' and old['withdrawn_at'] is None:
                        check(type(decision['withdrawn_at']) is int and decision['withdrawn_at']>=old['reported_at'],'withdrawal time')
                        old['withdrawn_at']=decision['withdrawn_at']
                    else:check(decision['withdrawn_at']==old['withdrawn_at'],'no-op keeps exact withdrawal time')
            now=snapshot()
            if changes:
                batch(spec,plan['snapshot'],'fact_usage_batch_snapshot_conflict')
                check(snapshot()==now,'stale apply preserves complete state')
            fresh=batch(spec);noop=batch(spec,fresh['snapshot'])
            check(fresh['would_change']==0 and noop['changed']==0 and snapshot()==now,'fresh repreview/apply is an exact no-op')
            for f in facts:
                selected=sorted((v for v in ledger.values() if v['fact_id']==f['fact_id']),key=lambda x:x['usage_id'])
                summary=call('memory_read',{'view':'usage','fact_id':f['fact_id']})
                n=sum(v['withdrawn_at'] is None for v in selected)
                check(summary['stored_receipts']==len(selected) and summary['current_revision_use_count']==n and summary['other_revision_use_count']==0 and summary['withdrawn_count']==len(selected)-n,'summary equals reference ledger')
                got=[];cursor=None;token=None
                while True:
                    args={'view':'usage_receipts','fact_id':f['fact_id'],'receipt_state':'all','limit':7,'max_bytes':32768}
                    if cursor:args.update(after_id=cursor,snapshot=token)
                    page=call('memory_read',args)
                    if token is None:token=page['snapshot']
                    check(page['snapshot']==token and page['origin']=='caller_reported' and page['host_consumption_verified'] is False,'page scope and snapshot')
                    got.extend(page['items'])
                    if not page['has_more']:break
                    check(bool(page['items']) and page['next_after_id']!=cursor and len(got)<=len(selected),'page advances')
                    cursor=page['next_after_id']
                expected=[{**{k:v[k] for k in ('usage_id','fact_revision','reported_at','withdrawn_at')},'state':'current' if v['withdrawn_at'] is None else 'withdrawn'} for v in selected]
                check(got==expected,'complete paged IDs and timestamps equal reference ledger')
            check(snapshot()==now,'all readback queries are nonmutating')
            rounds+=1
        child.stdin.close();child.wait(timeout=5);t.join(timeout=5);e.join(timeout=5)
        records.append({'kind':'exit','code':child.returncode,'stderr':b''.join(errors).decode()})
        check(child.returncode==0,'persistent MCP server exits normally')
    except Exception as exc:failure=type(exc).__name__+': '+str(exc)
    finally:
        if child is not None:
            if child.poll() is None:child.kill();child.wait(timeout=5)
            for stream in (child.stdin,child.stdout,child.stderr):
                if stream is not None and not stream.closed:stream.close()
    result={'schema':'qbrain-n47z-reference-review-v1','binary_sha256':sha(binary.read_bytes()),'script_sha256':sha(Path(__file__).read_bytes()),
        'rounds':rounds,'facts':len(facts),'receipts':len(ledger),'checks':checks,'records':records,'failure':failure,
        'passed':sum(x['passed'] for x in checks),'failed':sum(not x['passed'] for x in checks)+int(failure is not None and all(x['passed'] for x in checks)),
        'cli_calls':sum(x['kind']=='cli' for x in records),'mcp_requests':sum(x['kind']=='mcp' for x in records),'platform':os.name,
        'real_client_verified':False,'provider_calls':0,'limits':['public-API reference model; no SQL data writes','sequential schedules only','local Linux execution, not new Windows evidence']}
    (output/'review.json').write_bytes(enc(result))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=run(a.binary.resolve(strict=True),a.output)
    print(json.dumps({k:v for k,v in r.items() if k not in ('checks','records')},ensure_ascii=False))
    raise SystemExit(bool(r['failed']))
