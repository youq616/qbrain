"""N48Q real public CLI/MCP facts and receipts on disposable PostgreSQL and SQLite.
No imported product/test oracle. SQL setup is fixed ASCII; user text travels via UTF8 stdin.
Every native request and response is retained, including attempted failures.
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


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def need(ok, label):
    if not ok:
        raise ValueError(label)


def decode(raw):
    def unique(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate output JSON')
            result[key] = value
        return result
    def invalid(_):
        raise ValueError('nonfinite output')
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique, parse_constant=invalid)


def main(binary: Path, output: Path, sqlite_only=False):
    binary = binary.resolve(strict=True)
    output.mkdir(parents=True, exist_ok=False)
    (output/'raw').mkdir()
    rows, checks, observations = [], [], {}
    env_base = {k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
    env_base['PGCLIENTENCODING'] = 'UTF8'
    dsn = os.environ.get('QBRAIN_PG_FACT_PROCESS_DSN', '')
    def check(ok, label):
        checks.append(dict(name=label, passed=bool(ok)))
        need(ok, label)
    def execute(args, data=b'', env=None, cwd=None, expected=0, name='command', mcp=False):
        response = subprocess.run(list(map(str,args)), input=data, capture_output=True, env=env, cwd=cwd, timeout=30)
        row = dict(name=name,args=list(map(str,args)),exit=response.returncode,hashes={})
        for suffix,raw in [('stdin',data),('stdout',response.stdout),('stderr',response.stderr)]:
            (output/'raw'/f'{len(rows):03d}.{suffix}').write_bytes(raw)
            row['hashes'][suffix] = digest(raw)
        rows.append(row)
        check(response.returncode == expected, name+' exact exit')
        wanted = (b'[qbrain-serve] stdio MCP ready brain=n48q write=disabled\n'
                  b'[qbrain-serve] shutdown: stdin EOF\n') if mcp else b''
        check(response.stderr.replace(b'\r\n', b'\n') == wanted, name+' exact stderr')
        return response.stdout
    def psql(query, read=False):
        if read:
            query = "SELECT coalesce(json_agg(t),'[]'::json)::text FROM ("+query+") t"
        raw = execute(['psql','-X','-q','-A','-t','-v','ON_ERROR_STOP=1','-c',query],env=env_base,name='psql')
        return decode(raw) if read else None
    if not sqlite_only:
        need(os.environ.get('QBRAIN_PG_FACT_TEST_DISPOSABLE') == '1' and dsn, 'explicit disposable PostgreSQL required')
        need(os.environ.get('PGDATABASE') == 'qbrain_n48q_process','fixed disposable process DB required')
        check(psql('SELECT current_database() AS name', True) == [{'name':'qbrain_n48q_process'}], 'actual disposable PostgreSQL')
        psql('SET client_min_messages=WARNING; DROP TABLE IF EXISTS public.memory_fact_usage,public.memory_fact_usage_module,'
              'public.memory_fact_archive,public.memory_fact_lifecycle_module,public.memory_fact_relations,public.memory_fact_evidence,'
              'public.memory_facts,public.memory_fact_module,public.memory_attempts,public.memory_items,public.memory_events,public.memory_module CASCADE;'
              'DROP FUNCTION IF EXISTS public.qbrain_fact_evidence_gc_v1() CASCADE')
    try:
        with tempfile.TemporaryDirectory(prefix='qbrain-n48q-cli-') as tmp:
            for backend in (('sqlite',) if sqlite_only else ('sqlite','postgres')):
                home = Path(tmp)/backend; home.mkdir()
                env = {**env_base,'HOME':str(home),'USERPROFILE':str(home),'LOCALAPPDATA':str(home),'APPDATA':str(home)}
                if backend == 'postgres': env['QBRAIN_PG_DSN'] = dsn
                path = (home if os.name == 'nt' else home/'.local/share')/'Qbrain/brains/n48q/brain.db'
                def call(args, payload=None, expected=0, parsed=True):
                    raw = execute([binary,*args,'--brain','n48q'],b'' if payload is None else encoded(payload),env,home,expected,backend+':'+args[0])
                    return decode(raw) if parsed else raw
                call(['init','--no-default'],parsed=False)
                if backend == 'postgres': psql('DELETE FROM public.pages; DELETE FROM public.config')
                def sql(query,read=False):
                    if backend == 'postgres': return psql(query,read)
                    with closing(sqlite3.connect(path)) as db:
                        db.row_factory = sqlite3.Row
                        cursor = db.execute(query)
                        result = [dict(row) for row in cursor] if read else None
                        db.commit(); return result
                for sid in ('alpha','beta'): sql("INSERT INTO sources(id,name) VALUES('"+sid+"','synthetic') ON CONFLICT DO NOTHING")
                for key,value in [('embed.auto','false'),('memory.writeback','salient'),('mcp.allowed_sources','alpha')]:
                    sql("INSERT INTO config(key,value) VALUES('"+key+"','"+value+"') ON CONFLICT(key) DO UPDATE SET value=excluded.value")
                def fact(action,payload=None,args=(),source='alpha',expected=0):
                    return call(['fact',action,'--source',source,*args],payload,expected)
                def memory(action,payload=None,args=(),expected=0):
                    return call(['memory',action,'--source','alpha',*args],payload,expected)
                def seed(fragment,text):
                    value = dict(session_id='n48q-independent',fragment_id=fragment,messages=[
                        dict(role='user',content=text),dict(role='assistant',content='I prefer ASSISTANT_POISON')])
                    event = memory('capture',value,args=['--manual'])
                    body = encoded(dict(messages=value['messages'],expires_at=0))
                    eid = digest(encoded(['qbrain-memory-v1','alpha',value['session_id'],fragment,digest(body)]))
                    check(event['event_id']==eid,'canonical independent event ID')
                    extraction = memory('extract',args=['--event',eid])
                    check(extraction['item_count']==1,'one explicit user statement')
                    items = memory('read')['items']
                    check(any(v['quote']==text and v['message_index']==0 for v in items),'exact recalled quote and user index')
                    candidate=dict(category='preference',message_index=0,quote=text)
                    item_id=digest(eid.encode()+encoded(candidate))
                    check(sql("SELECT item_id,quote,message_index FROM memory_items WHERE event_id='"+eid+"'",True)==[dict(item_id=item_id,quote=text,message_index=0)],'independent support identity despite read deduplication')
                    return eid,item_id,value
                check(fact('read')['initialized'] is False,'read without optional facts DDL')
                quote='I prefer CASE Windows C++ 中文😀; Café Ä --brain literal.\r\n'
                event,item,payload = seed('first',quote)
                _,support,_ = seed('second',quote)
                created = fact('create',dict(predicate='tool.preference',item_id=item))
                fid = digest(encoded(['qbrain-fact-v1','alpha','user','tool.preference',quote,item]))
                check(created['fact_id']==fid and created['revision']==1 and created['duplicate'] is False,'exact fact identity and revision')
                read = fact('read',args=['--id',fid])['items'][0]
                check(read['object']==quote and read['confidence'] is None and read['truth_status']=='caller_attested_user_statement','verbatim evidence not model confidence')
                check(fact('read',source='beta',args=['--id',fid])['items']==[],'cross-source read empty')
                check(fact('create',dict(predicate='tool.preference',item_id=item))['duplicate'] is True,'process restart create idempotence')
                check(fact('create',dict(predicate='tool.preference',item_id=item),source='beta',expected=1)['error']['code']=='fact_evidence_unavailable','cross-source write refused')
                for query,n in [('case',1),('café',1),('CAFÉ',0),('ä',0),('Ä',1),('--brain',1),("%' OR 1=1",0)]:
                    check(len(fact('recall',args=['--query',query])['items'])==n,'literal matching '+query)
                uid=digest(b'original-use')
                claim=dict(fact_id=fid,usage_id=uid,expected_revision=1)
                first=fact('report-use',claim)
                check(first['duplicate'] is False and first['host_consumption_verified'] is False,'explicit unverified receipt')
                check(fact('report-use',claim)['duplicate'] is True,'receipt idempotence')
                current=fact('usage',args=['--id',fid])
                check(current['current_revision_use_count']==1 and current['stored_receipts']==1,'complete current receipt count')
                check(fact('attach',dict(fact_id=fid,item_id=support))['revision']==2,'support changes revision')
                check(fact('usage',args=['--id',fid])['other_revision_use_count']==1,'past revision use not current')
                check(fact('report-use',claim,expected=1)['error']['code']=='fact_revision_conflict','old revision refused')
                check(fact('revoke-use',dict(fact_id=fid,usage_id=uid))['status']=='withdrawn','explicit receipt withdrawal')
                preview_input=dict(operation='report',items=[dict(fact_id=fid,usage_id=digest(x),expected_revision=2) for x in (b'batch-a',b'batch-b')])
                preview=fact('usage-batch-preview',preview_input)
                check(preview['would_change']==2 and preview['applied'] is False,'batch preview no write')
                check(fact('usage',args=['--id',fid])['stored_receipts']==1,'preview did not insert')
                batch={**preview_input,'snapshot':preview['snapshot']}
                check(fact('usage-batch-apply',batch)['changed']==2,'atomic two-receipt apply')
                check(fact('usage-batch-apply',batch,expected=1)['error']['code']=='fact_usage_batch_snapshot_conflict','same snapshot cannot be reused')
                page=fact('usage-list',args=['--id',fid,'--limit','1','--max-bytes','2048'])
                seen=[]
                for _ in range(5):
                    seen.extend(page['items'])
                    if page['next_after_id'] is None:break
                    page=fact('usage-list',args=['--id',fid,'--limit','1','--max-bytes','2048','--after-id',page['next_after_id'],'--snapshot',page['snapshot']])
                check(len(seen)==3 and len({x['usage_id'] for x in seen})==3,'complete stable receipt pagination')
                check(fact('archive',dict(fact_id=fid,expected_revision=2))['archived'] is True,'explicit archive')
                check(fact('recall',args=['--query','Windows'])['items']==[],'archived fact absent from recall')
                check(fact('read',args=['--id',fid])['items'][0]['revision']==3,'explicit read still inspects archived fact')
                check(fact('restore',dict(fact_id=fid,expected_revision=3))['archived'] is False,'explicit restore')
                observed=fact('usage',args=['--id',fid])
                check(observed['stored_receipts']==3 and observed['withdrawn_count']==1 and observed['other_revision_use_count']==2,'history survives archive restore')
                # Three requests exercise the original allowed-source and default-write gates.
                messages=[dict(jsonrpc='2.0',id=1,method='tools/call',params=dict(name='memory_read',arguments=dict(source_id='alpha',view='facts',fact_id=fid))),
                          dict(jsonrpc='2.0',id=2,method='tools/call',params=dict(name='memory_read',arguments=dict(source_id='beta',view='facts'))),
                          dict(jsonrpc='2.0',id=3,method='tools/call',params=dict(name='memory_write',arguments=dict(source_id='alpha',action='fact_retract',payload=dict(fact_id=fid,expected_revision=4))))]
                raw=execute([binary,'serve','--brain','n48q'],b'\n'.join(encoded(m) for m in messages)+b'\n',env,home,name=backend+':MCP',mcp=True)
                replies=[decode(line) for line in raw.splitlines()]
                check(replies[0]['result']['isError'] is False and replies[1]['result']['isError'] is True and replies[2]['result']['isError'] is True,'MCP allowed read/source refusal/default write refusal')
                check(fact('read',args=['--id',fid])['items'][0]['status']=='active','denied MCP no mutation')
                check(memory('forget',args=['--event',event])['status']=='forgotten','first support forgotten')
                remaining=fact('read',args=['--id',fid])['items'][0]
                check(remaining['revision']==5 and remaining['evidence_count']==1,'independent support survives')
                check(memory('capture',payload,args=['--manual'])['status']=='forgotten','no forgotten replay resurrection')
                # Source reset must delete fact copies and all receipt history via FKs/cleanup.
                event2=remaining['evidence'][0]['event_id']
                memory('forget',args=['--event',event2])
                check(fact('read',args=['--id',fid,'--history'])['items']==[],'last supporting statement removes historic text')
                check(sql('SELECT count(*) AS n FROM memory_facts',True)==[{'n':0}] and sql('SELECT count(*) AS n FROM memory_fact_usage',True)==[{'n':0}],'physical fact and receipt cleanup')
                if backend=='postgres':
                    check(not path.exists(),'no PG fallback SQLite DB')
                    check(sql("SELECT data_type AS type FROM information_schema.columns WHERE table_schema='public' AND table_name='memory_facts' AND column_name='revision'",True)==[{'type':'bigint'}],'actual BIGINT schema')
                observations[backend]=dict(fact_id=fid,quote=read['object'],confidence=read['confidence'],
                    receipt_counts={k:observed[k] for k in ('stored_receipts','withdrawn_count','other_revision_use_count')},
                    final_fact_count=0,retained_independent_support=remaining['evidence_count'],replay='forgotten')
        if not sqlite_only:check(encoded(observations['sqlite'])==encoded(observations['postgres']),'cross-backend deterministic semantic equality')
        result=True
    except Exception:
        (output/'PARTIAL.json').write_bytes(encoded(dict(passed=False,commands=rows,checks=checks))+b'\n')
        raise
    report=dict(schema='qbrain-n48q-process-v1',passed=result,postgres_executed=not sqlite_only,
                binary_sha256=digest(binary.read_bytes()),script_sha256=digest(Path(__file__).read_bytes()),
                optimized=not __debug__,commands=rows,checks=checks,observations=observations,
                command_count=len(rows),check_count=len(checks),provider_requests_sent=0)
    (output/'RESULT.json').write_bytes(encoded(report)+b'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('commands','checks','observations')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--sqlite-only',action='store_true')
    args=p.parse_args();main(args.binary,args.output,args.sqlite_only)
