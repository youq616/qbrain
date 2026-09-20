"""Independent N47Y boundary review using real CLI and authorized stdio MCP.

Only disposable synthetic brains are used. Public APIs create valid data; SQL
writes are named corruption/restore fixtures and a controlled competing writer.
No network, provider, user database or production test hook. Output is immutable.
"""
from __future__ import annotations
import argparse
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


def digest(data): return hashlib.sha256(data).hexdigest()
def encode(obj): return (json.dumps(obj, ensure_ascii=False, sort_keys=True) + '\n').encode()


def run(binary: Path, output: Path):
    output.mkdir(parents=True, exist_ok=False)
    checks, records, failure = [], [], None
    def check(ok, name):
        checks.append({'name': name, 'passed': bool(ok)})
        if not ok: raise ValueError(name)
    try:
      with tempfile.TemporaryDirectory(prefix='n47y-boundary-') as temporary:
        root = Path(temporary) / 'synthetic 审核'; root.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(
            ('QBRAIN', 'OPENAI', 'ANTHROPIC', 'GH_TOKEN', 'GITHUB_TOKEN'))}
        env.update(HOME=str(root), USERPROFILE=str(root), LOCALAPPDATA=str(root), APPDATA=str(root))
        dbpath = (root if os.name == 'nt' else root / '.local/share') / 'Qbrain/brains/boundary/brain.db'
        def cli(args, payload=None, parse=True):
            inp = b'' if payload is None else encode(payload)
            p = subprocess.run([str(binary), *args, '--brain', 'boundary'], input=inp,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=root, timeout=30)
            records.append({'kind':'cli','args':args,'input':inp.decode(),'stdout':p.stdout.decode(),
                'stderr':p.stderr.decode(),'exit':p.returncode})
            if p.returncode or p.stderr: raise ValueError('CLI setup failed')
            return json.loads(p.stdout) if parse else p.stdout
        def state():
            with closing(sqlite3.connect(dbpath)) as db:
                names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
                rows = {name: sorted(db.execute('SELECT * FROM "'+name+'"').fetchall(),key=repr) for name in names}
                schema = db.execute('SELECT * FROM sqlite_master ORDER BY name').fetchall()
            backups = sorted((p.name,digest(p.read_bytes())) for p in dbpath.parent.glob('*.bak'))
            return digest(repr((rows,schema,backups)).encode())
        cli(['init','--no-default'], parse=False)
        cli(['config','set','memory.writeback','salient','--local'], parse=False)
        cli(['config','set','mcp.allowed_sources','default','--local'], parse=False)
        event = cli(['memory','capture','--manual'], {'session_id':'independent-boundary',
            'fragment_id':'one','messages':[{'role':'user','content':'I prefer integrity boundary evidence.'}]})
        cli(['memory','extract','--event',event['event_id']])
        item = next(x for x in cli(['memory','read'])['items'] if x['event_id']==event['event_id'])
        fact = cli(['fact','create'], {'predicate':'review.preference','item_id':item['item_id']})
        uid = '1'*64; new_uid = '2'*64
        report = {'fact_id':fact['fact_id'],'usage_id':uid,'expected_revision':fact['revision']}
        cli(['fact','report-use'],report)
        with closing(sqlite3.connect(dbpath)) as db:
            healthy = db.execute('SELECT * FROM memory_fact_usage').fetchall()
        def restore():
            with closing(sqlite3.connect(dbpath)) as db:
                db.execute('DELETE FROM memory_fact_usage')
                db.executemany('INSERT INTO memory_fact_usage VALUES(?,?,?,?,?,?)',healthy)
                db.commit()
        initial = state()
        # Keep an established server process alive so transaction probes do not
        # confuse inherited database-open/migration behavior with the new route.
        process = subprocess.Popen([str(binary),'serve','--brain','boundary','--tool-profile','memory','--allow-write'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,cwd=root)
        lines = queue.Queue(); stderr = []
        def reader():
            try:
                for line in process.stdout: lines.put(line)
            finally: lines.put(None)
        def errors():
            for line in process.stderr: stderr.append(line)
        thread = threading.Thread(target=reader,daemon=True); thread.start()
        errthread = threading.Thread(target=errors,daemon=True); errthread.start()
        serial = 0
        def send(method, params):
            nonlocal serial
            serial += 1
            req = {'jsonrpc':'2.0','id':serial,'method':method,'params':params}
            process.stdin.write(encode(req)); process.stdin.flush()
            return req
        def receive(req):
            raw = lines.get(timeout=10)
            if raw is None: raise ValueError('MCP exited before response')
            value = json.loads(raw)
            if value.get('id') != req['id']: raise ValueError('MCP response identity')
            records.append({'kind':'mcp','request':req,'response':value})
            return value
        def invoke(tool,args): return receive(send('tools/call',{'name':tool,'arguments':args}))
        def result(value):
            r = value['result']; content = r['content']
            body = json.loads(content[-1]['text'])
            return r.get('isError') is True, body
        routes = {
            'summary':('memory_read',{'view':'usage','fact_id':fact['fact_id']}),
            'page':('memory_read',{'view':'usage_receipts','fact_id':fact['fact_id'],'receipt_state':'withdrawn','limit':1}),
            'new_report':('memory_write',{'action':'fact_report_use','payload':json.dumps({**report,'usage_id':new_uid})}),
            'duplicate_report':('memory_write',{'action':'fact_report_use','payload':json.dumps(report)}),
            'revoke':('memory_write',{'action':'fact_revoke_use','payload':json.dumps({'fact_id':fact['fact_id'],'usage_id':uid})})}
        try:
            receive(send('initialize',{}))
            process.stdin.write(encode({'jsonrpc':'2.0','method':'notifications/initialized'}));process.stdin.flush()
            err, body = result(invoke(*routes['summary']))
            check(not err and body['stored_receipts']==1,'authorized MCP can read valid receipt set')
            err, body = result(invoke(*routes['duplicate_report']))
            check(not err and body['duplicate'] is True and state()==initial,'authorized MCP valid retry is read-identical')
            tools = receive(send('tools/list',{}))['result']['tools']
            schema = next(t['inputSchema'] for t in tools if t['name']=='memory_read')
            check(schema['properties']['receipt_state']['type']=='string' and
                schema['properties']['snapshot']['type']=='string',
                'MCP advertises receipt filter and snapshot as strings')
            for selected in ('all','current','historical','withdrawn'):
                err,body=result(invoke('memory_read',{'view':'usage_receipts','fact_id':fact['fact_id'],
                    'receipt_state':selected,'limit':1}))
                check(not err and body['receipt_state']==selected and
                    [i['usage_id'] for i in body['items']]==([uid] if selected in ('all','current') else []) and
                    state()==initial,'healthy MCP filter '+selected+' matches selected IDs without mutation')
            # All seven nonempty combinations across source/usage/fact storage
            # classes. SQLite corruption is explicit; the application cannot make
            # these fixture writes. Five public execution paths must agree.
            for mask in range(1,8):
                row = list(healthy[0])
                for col in range(3):
                    if mask & (1<<col): row[col] = row[col].encode()
                with closing(sqlite3.connect(dbpath)) as db:
                    db.execute('PRAGMA foreign_keys=OFF')
                    db.execute('DELETE FROM memory_fact_usage')
                    db.execute('INSERT INTO memory_fact_usage VALUES(?,?,?,?,?,?)',row);db.commit()
                damaged = state()
                for name, route in routes.items():
                    err, body = result(invoke(*route))
                    check(err and body=={'error':{'code':'fact_usage_invalid_metadata'}} and state()==damaged,
                        f'alias-{mask:03b}/{name}: reject without row schema or backup change')
                restore();check(state()==initial,f'alias-{mask:03b}/restore: exact healthy state')
            # A new caller may request an otherwise valid ID attached to a damaged
            # off-target scope; all TEXT/BLOB source+ID combinations must be found.
            # Covered above for target rows and by the original cross-fact regression.
            for name in ('new_report','duplicate_report','revoke'):
                with closing(sqlite3.connect(dbpath,timeout=10)) as writer:
                    writer.execute('PRAGMA foreign_keys=OFF')
                    writer.execute('BEGIN IMMEDIATE')
                    req = send('tools/call',{'name':routes[name][0],'arguments':routes[name][1]})
                    try:
                        premature = lines.get(timeout=.20)
                    except queue.Empty:
                        premature = 'waiting'
                    check(premature=='waiting',name+'/writer-lock: operation has no early result')
                    writer.execute('UPDATE memory_fact_usage SET usage_id=CAST(usage_id AS BLOB)')
                    writer.commit()
                damaged=state()
                err, body=result(receive(req))
                check(err and body=={'error':{'code':'fact_usage_invalid_metadata'}} and state()==damaged,
                    name+'/writer-release: newly committed corruption rejected without write')
                restore()
                err, body=result(invoke(*routes['duplicate_report']))
                check(not err and body['duplicate'] is True and state()==initial,
                    name+'/recovery: server remains usable after restored fixture')
            # A statement-level simulated write failure must not persist a tombstone.
            with closing(sqlite3.connect(dbpath)) as db:
                db.execute("CREATE TRIGGER boundary_abort BEFORE UPDATE OF withdrawn_at ON memory_fact_usage BEGIN SELECT RAISE(ABORT,'fixture'); END")
                db.commit()
            before=state();err,body=result(invoke(*routes['revoke']))
            check(err and body=={'error':{'code':'memory_storage_error'}} and state()==before,
                'revoke-abort: rollback preserves receipt and all other rows')
            with closing(sqlite3.connect(dbpath)) as db:
                db.execute('DROP TRIGGER boundary_abort');db.commit()
            err,body=result(invoke(*routes['revoke']))
            check(not err and body['status']=='withdrawn' and body['duplicate'] is False,
                'revoke-after-abort: original receipt still withdrawable')
            err,body=result(invoke(*routes['duplicate_report']))
            check(err and body=={'error':{'code':'fact_usage_withdrawn'}},
                'post-revoke retry never resurrects a valid tombstone')
            for rid in (new_uid,'3'*64):
                err,body=result(invoke('memory_write',{'action':'fact_report_use',
                    'payload':json.dumps({**report,'usage_id':rid})}))
                if err or body['duplicate']: raise ValueError('pagination setup rejected')
            base={'view':'usage_receipts','fact_id':fact['fact_id'],'receipt_state':'all','limit':1}
            before=state();err,page=result(invoke('memory_read',base))
            check(not err and page['has_more'] and page['items'][0]['usage_id']==uid,
                'healthy MCP first page yields an actual continuation')
            token=page['snapshot'];seen=[uid]
            while page['has_more']:
                err,page=result(invoke('memory_read',{**base,'after_id':page['next_after_id'],'snapshot':token}))
                if err or page['snapshot']!=token or not page['items']: raise ValueError('MCP continuation failure')
                seen.extend(x['usage_id'] for x in page['items'])
                if len(seen)>3: raise ValueError('non-advancing continuation')
            check(seen==[uid,new_uid,'3'*64] and page['next_after_id'] is None and state()==before,
                'healthy MCP snapshot continuation returns the exact complete ID set read-only')
            invalid=[('filter-boolean',{**base,'receipt_state':True},'invalid_argument'),
                ('snapshot-boolean',{**base,'after_id':uid,'snapshot':True},'invalid_argument'),
                ('snapshot-integer',{**base,'after_id':uid,'snapshot':7},'invalid_argument'),
                ('unknown-field',{**base,'unrecognized':'x'},'invalid_argument'),
                ('invalid-filter',{**base,'receipt_state':'bogus'},'fact_usage_invalid_filter'),
                ('missing-pair',{**base,'after_id':uid},'fact_usage_cursor_pair_required'),
                ('wrong-snapshot',{**base,'after_id':uid,'snapshot':'f'*64},'fact_usage_snapshot_conflict'),
                ('wrong-view',{'view':'usage','fact_id':fact['fact_id'],'receipt_state':'all'},'fact_unexpected_argument')]
            for name,args,code in invalid:
                err,body=result(invoke('memory_read',args))
                check(err and body.get('error',{}).get('code')==code and state()==before,
                    'MCP rejects '+name+' without loosening validation or writing')
        finally:
            if process.poll() is None:
                process.stdin.close()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: process.kill();process.wait(timeout=5)
            thread.join(timeout=5);errthread.join(timeout=5)
            if process.stdin and not process.stdin.closed: process.stdin.close()
            process.stdout.close();process.stderr.close()
            records.append({'kind':'mcp-exit','exit':process.returncode,'stderr':b''.join(stderr).decode()})
        check(process.returncode==0,'server shutdown exits cleanly after all boundary probes')
    except Exception as error:
        failure=type(error).__name__+': '+str(error)
    outcome={'schema':'qbrain-n47y-boundary-v1','binary_sha256':digest(binary.read_bytes()),
        'script_sha256':digest(Path(__file__).read_bytes()),'checks':checks,'records':records,
        'passed':sum(c['passed'] for c in checks),'failed':sum(not c['passed'] for c in checks)+int(bool(failure) and all(c['passed'] for c in checks)),
        'failure':failure,'platform':os.name,'real_client_verified':False,'provider_calls':0,
        'scope':'controlled writer-lock schedules, not proof of every concurrent schedule; authorized stdio MCP, not a real model'}
    (output/'review.json').write_bytes(encode(outcome))
    return outcome


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=run(a.binary.resolve(strict=True),a.output)
    print(json.dumps({k:v for k,v in r.items() if k not in ('checks','records')}))
    raise SystemExit(1 if r['failed'] else 0)
