"""N48O real native CLI + PostgreSQL/SQLite differential lifecycle. Synthetic only.
Requires an explicitly disposable qbrain_n48o_process DB. No provider requests.
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


def encoded(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def need(ok, label):
    if not ok:
        raise ValueError(label)


def main(binary, output):
    need(os.environ.get('QBRAIN_PG_MEMORY_TEST_DISPOSABLE') == '1', 'explicit disposable test flag required')
    need(os.environ.get('PGDATABASE') == 'qbrain_n48o_process', 'wrong test database')
    dsn = os.environ.get('QBRAIN_PG_PROCESS_TEST_DSN', '')
    need(bool(dsn), 'PG test DSN required; never a skipped pass')
    output.mkdir(parents=True, exist_ok=False)
    (output/'raw').mkdir()
    rows, checks, results = [], [], {}
    def check(ok, label):
        checks.append(dict(name=label, passed=bool(ok)))
        need(ok, label)
    env_base = {k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
    def execute(args, data=b'', env=None, cwd=None, expected=0, name='command'):
        p = subprocess.run(list(map(str,args)), input=data, capture_output=True, env=env, cwd=cwd, timeout=25)
        index = len(rows); hashes = {}
        for suffix, raw in [('stdin',data),('stdout',p.stdout),('stderr',p.stderr)]:
            (output/'raw'/f'{index:03d}.{suffix}').write_bytes(raw)
            hashes[suffix] = hashlib.sha256(raw).hexdigest()
        rows.append(dict(name=name, command=[str(x) for x in args], exit=p.returncode, expected_exit=expected, hashes=hashes))
        check(p.returncode == expected, name+' exit')
        check(not p.stderr, name+' stderr')
        return p.stdout
    def psql(sql, query=False):
        if query:
            sql = "SELECT coalesce(json_agg(t),'[]'::json)::text FROM ("+sql+") t"
        raw = execute(['psql','-X','-q','-A','-t','-v','ON_ERROR_STOP=1','-c',sql], env=env_base, name='server SQL')
        return json.loads(raw) if query else None
    check(psql('SELECT current_database() AS name',True)[0]['name']=='qbrain_n48o_process','real PG database confirmed')
    psql('SET client_min_messages=WARNING; DROP TABLE IF EXISTS memory_attempts,memory_items,memory_events,memory_module CASCADE')
    # NOTICE messages on drop of absent tables are hidden only for this disposable setup.
    with tempfile.TemporaryDirectory(prefix='qbrain-n48o-cli-') as temp:
        for backend in ('sqlite','postgres'):
            home=Path(temp)/backend;home.mkdir()
            env={**env_base,'HOME':str(home),'USERPROFILE':str(home),'LOCALAPPDATA':str(home),'APPDATA':str(home)}
            if backend=='postgres':env['QBRAIN_PG_DSN']=dsn
            data_root=home if os.name=='nt' else home/'.local/share'
            db_path=data_root/'Qbrain/brains/n48o/brain.db'
            def call(args, value=None, expected=0, parsed=True):
                raw=execute([binary,*args,'--brain','n48o'], b'' if value is None else encoded(value), env,home,expected,backend+':'+args[0])
                return json.loads(raw) if parsed else raw
            call(['init'],parsed=False)
            if backend=='postgres':psql('DELETE FROM pages; DELETE FROM config')
            def sql(q, query=False):
                if backend=='postgres':return psql(q,query)
                with closing(sqlite3.connect(db_path)) as db:
                    db.row_factory=sqlite3.Row
                    cursor=db.execute(q)
                    out=[dict(x) for x in cursor] if query else None
                    db.commit();return out
            def count(table):return sql('SELECT count(*) AS n FROM '+table,True)[0]['n']
            def config(k,v):sql("INSERT INTO config(key,value) VALUES('"+k+"','"+v+"') ON CONFLICT(key) DO UPDATE SET value=excluded.value")
            for sid in ('alpha','beta'):sql("INSERT INTO sources(id,name) VALUES('"+sid+"','synthetic') ON CONFLICT DO NOTHING")
            config('memory.writeback','off');config('embed.auto','false')
            def memory(action, value=None, opts=(), expected=0, source='alpha'):
                return call(['memory',action,'--source',source,*opts],value,expected)
            def payload(fragment='literal-case'):
                return dict(session_id='测试 😀',fragment_id=fragment,messages=[
                    dict(role='user',content='我偏好中文，并使用 Windows。😀'),
                    dict(role='assistant',content='I prefer INVENTED assistant facts.'),
                    dict(role='user',content='I decided to keep CASE Café Ä --brain data.')])
            check(memory('read')['initialized'] is False,backend+':read no init')
            check(memory('capture',payload())['status']=='skipped',backend+':off no archive')
            config('memory.writeback','salient')
            cap=memory('capture',payload());eid=cap['event_id']
            body=encoded(dict(messages=payload()['messages'],expires_at=0))
            digest=hashlib.sha256(body).hexdigest()
            expected_id=hashlib.sha256(encoded(['qbrain-memory-v1','alpha','测试 😀','literal-case',digest])).hexdigest()
            check(eid==expected_id,backend+':independent content identity')
            check(count('memory_events')==1 and count('pages')==1,backend+':one archived record')
            check(memory('capture',payload())['duplicate'] is True,backend+':restart dedup')
            wrong=payload();wrong['messages'][0]['content']='我偏好别的内容'
            check(memory('capture',wrong,expected=1)['error']['code']=='fragment_conflict',backend+':conflict no overwrite')
            check(memory('extract',opts=['--event',eid])['item_count']==2,backend+':extract two user quotes')
            items=memory('read')['items'];results[backend]=items
            for query,expected in [('case',1),('CAFÉ',0),('café',1),('ä',0),('Ä',1),('--brain',1),("' OR 1=1",0)]:
                check(len(memory('read',opts=['--query',query])['items'])==expected,backend+':literal '+query)
            check(memory('read',source='beta')['items']==[],backend+':source isolation')
            check(memory('extract',opts=['--event',eid])['duplicate'] is True,backend+':extract idempotence')
            check(memory('status',opts=['--event',eid])['usage'][0]['provider_attempts']==0,backend+':no provider calls')
            check(len(encoded(memory('read',opts=['--max-bytes','512'])))<=512,backend+':byte limit')
            # Forbidden MCP requests must not open a new permission path on PG.
            messages=[dict(jsonrpc='2.0',id=0,method='initialize',params={'protocolVersion':'2024-11-05'}),
                      dict(jsonrpc='2.0',method='notifications/initialized'),
                      dict(jsonrpc='2.0',id=1,method='tools/call',params={'name':'memory_write','arguments':{'source_id':'alpha','action':'forget','event_id':eid}})]
            raw=execute([binary,'serve','--brain','n48o'],b'\n'.join(encoded(x) for x in messages)+b'\n',env,home,name=backend+':MCP deny')
            replies=[json.loads(x) for x in raw.splitlines()]
            check(replies[-1]['result']['isError'] is True,backend+':MCP default deny')
            check(memory('status',opts=['--event',eid])['status']=='extracted',backend+':denied MCP no mutation')
            check(memory('forget',opts=['--event',eid])['status']=='forgotten',backend+':forget')
            check(memory('read')['items']==[],backend+':forgotten hidden')
            check(memory('capture',payload())['status']=='forgotten',backend+':no replay resurrection')
            check(count('memory_items')==0 and count('pages')==0,backend+':owned archive deleted')
            check(count('memory_events')==1,backend+':tombstone remains')
            for i in range(3):memory('capture',payload('drain-'+str(i)))
            check(len(memory('drain')['events'])==3,backend+':drain all three')
            check(memory('drain',opts=['--method','model'])['reason']=='external_extraction_denied',backend+':model consent denied')
            secret=payload('secret');secret['messages'][0]['content']='api_key=PRIVATE_SENTINEL'
            check(memory('capture',secret,expected=1)['error']['code']=='sensitive_material_rejected',backend+':sensitive text rejected')
            check(count('memory_events')==4,backend+':no secret persisted')
            if backend=='postgres':
                check(not db_path.exists(), 'PG never falls back to a SQLite database')
                check(not list(home.rglob('*.pre-memory-*')), 'PG descriptor never used as backup filename')
                check(sql("SELECT data_type AS type FROM information_schema.columns WHERE table_schema='public' AND table_name='memory_events' AND column_name='expires_at'",True)[0]['type']=='bigint','PG expiry actual bigint')
    check(encoded(results['sqlite'])==encoded(results['postgres']), 'exact cross-backend memory items and identities')
    result=dict(schema='qbrain-n48o-process-v1',passed=True,real_postgresql=True,optimized=not __debug__,
        binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        commands=rows,checks=checks,command_count=len(rows),check_count=len(checks),paid_provider_requests=0)
    (output/'RESULT.json').write_bytes(encoded(result)+b'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('commands','checks')}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    main(a.binary.resolve(strict=True),a.output.resolve())
