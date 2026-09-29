"""N48P actual CLI/MCP layered-context differential on isolated SQLite and real PG.
Synthetic only. Requires an explicit disposable named PostgreSQL database. No model.
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
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def need(ok,label):
    if not ok: raise ValueError(label)


def digest(raw): return hashlib.sha256(raw).hexdigest()


def main(binary,output,sqlite_only=False):
    output.mkdir(parents=True,exist_ok=False);(output/'raw').mkdir()
    rows=[];checks=[];results={}
    env_base={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
    def check(ok,label):
        checks.append(dict(name=label,passed=bool(ok)));need(ok,label)
    def execute(command,data=b'',env=None,cwd=None,expected=0,name='command',mcp=False):
        p=subprocess.run(list(map(str,command)),input=data,capture_output=True,env=env,cwd=cwd,timeout=30)
        hashes={}
        for suffix,raw in [('stdin',data),('stdout',p.stdout),('stderr',p.stderr)]:
            (output/'raw'/f'{len(rows):03d}.{suffix}').write_bytes(raw);hashes[suffix]=digest(raw)
        rows.append(dict(name=name,args=list(map(str,command)),exit=p.returncode,hashes=hashes))
        check(p.returncode==expected,name+' exit')
        if not mcp: check(p.stderr==b'',name+' stderr')
        else: check(b'[qbrain-serve] stdio MCP ready' in p.stderr and b'shutdown: stdin EOF' in p.stderr,name+' MCP shutdown')
        return p.stdout
    def sql_pg(query,read=False):
        if read: query="SELECT coalesce(json_agg(t),'[]'::json)::text FROM ("+query+") t"
        raw=execute(['psql','-X','-q','-A','-t','-v','ON_ERROR_STOP=1','-c',query],env=env_base,name='psql')
        return json.loads(raw) if read else None
    if not sqlite_only:
        need(os.environ.get('QBRAIN_PG_CONTEXT_TEST_DISPOSABLE')=='1','disposable flag required')
        need(os.environ.get('PGDATABASE')=='qbrain_n48p_process','test PGDATABASE required')
        dsn=os.environ.get('QBRAIN_PG_CONTEXT_PROCESS_DSN','');need(bool(dsn),'actual PG DSN required')
        check(sql_pg('SELECT current_database() AS name',True)==[{'name':'qbrain_n48p_process'}],'exact disposable DB')
        # Never reset arbitrary databases. The server-confirmed name is checked above.
        sql_pg('SET client_min_messages=WARNING; DROP TABLE IF EXISTS public.context_cache,public.context_module CASCADE; DROP FUNCTION IF EXISTS public.qbrain_context_invalidate_v1() CASCADE')
    with tempfile.TemporaryDirectory(prefix='qbrain-n48p-process-') as temp:
        for backend in (('sqlite',) if sqlite_only else ('sqlite','postgres')):
            home=Path(temp)/backend;home.mkdir()
            env={**env_base,'HOME':str(home),'USERPROFILE':str(home),'APPDATA':str(home),'LOCALAPPDATA':str(home)}
            if backend=='postgres':env['QBRAIN_PG_DSN']=dsn
            data_root=home if os.name=='nt' else home/'.local/share'
            dbpath=data_root/'Qbrain/brains/n48p/brain.db'
            def call(args,expected=0,parse=True):
                raw=execute([binary,*args,'--brain','n48p'],env=env,cwd=home,expected=expected,name=backend+':'+args[0])
                return json.loads(raw) if parse else raw
            def sql(q,read=False):
                if backend=='postgres':return sql_pg(q,read)
                with closing(sqlite3.connect(dbpath)) as db:
                    db.row_factory=sqlite3.Row;cursor=db.execute(q)
                    out=[dict(x) for x in cursor] if read else None;db.commit();return out
            def context(action='read',uri='qbrain://alpha/resources/docs/',extra=(),expected=0):
                return call(['context',action,'--source','alpha','--uri',uri,*extra],expected)
            call(['init','--no-default'],parse=False)
            if backend=='postgres':sql_pg('DELETE FROM public.pages; DELETE FROM public.config')
            for sid in ('alpha','beta'):sql("INSERT INTO sources(id,name) VALUES('"+sid+"','fixture') ON CONFLICT DO NOTHING")
            def config(k,v):sql("INSERT INTO config(key,value) VALUES('"+k+"','"+v+"') ON CONFLICT(key) DO UPDATE SET value=excluded.value")
            config('embed.auto','false');config('mcp.allowed_sources','alpha')
            original=('中文😀 quote "source"\r\n'*60)
            esc=lambda value:"'"+value.replace("'","''")+"'"
            for ident,source,text in ((100,'alpha',original),(200,'beta','BETA_SECRET')):
                sql("INSERT INTO pages(id,source_id,slug,title,body) "+('OVERRIDING SYSTEM VALUE ' if backend=='postgres' else '')+
                    "VALUES("+str(ident)+","+esc(source)+",'docs/a','Demo',"+esc(text)+")")
            observed={}
            observed['root']=call(['context','list','--source','alpha'])
            observed['missing']=context(extra=['--layer','L1'])
            check(observed['missing']['cache_status']=='missing' and observed['missing']['page_count']==1,'missing scoped preview')
            catalog="SELECT count(*) AS n FROM "+("information_schema.tables WHERE table_schema='public' AND table_name='context_cache'" if backend=='postgres' else "sqlite_master WHERE type='table' AND name='context_cache'")
            check(sql(catalog,True)==[{'n':0}],'read creates no cache schema')
            raw_parts=[];offset=0;revision='';pages=[]
            for i in range(100):
                args=['--layer','L2','--max-bytes','512']
                if offset:args+=['--offset',str(offset),'--revision',revision]
                page=context(uri='qbrain://alpha/resources/docs/a',extra=args);pages.append(page)
                check(len(encoded(page))<=512,'serialized byte cap')
                check(page['revision']==digest(original.encode('utf-8')),'independent raw revision')
                raw_parts.append(page['content']);revision=page['revision']
                if page['next_offset'] is None:break
                need(page['next_offset']>offset,'pagination progresses');offset=page['next_offset']
            check(''.join(raw_parts)==original,'UTF8 CRLF byte reconstruction');observed['pages']=pages
            observed['summary']=context('summary');observed['fresh']=context()
            check(observed['fresh']['cache_status']=='fresh','cached in next process')
            context('summary',extra=['--method','model'],expected=1)
            messages=[dict(jsonrpc='2.0',id=1,method='tools/call',params={'name':'context_read','arguments':{'source_id':'alpha','uri':'qbrain://alpha/resources/docs/'}}),
                      dict(jsonrpc='2.0',id=2,method='tools/call',params={'name':'context_read','arguments':{'source_id':'beta','uri':'qbrain://beta/resources/docs/'}}),
                      dict(jsonrpc='2.0',id=3,method='tools/call',params={'name':'context_write','arguments':{'source_id':'alpha','uri':'qbrain://alpha/resources/docs/'}})]
            raw=execute([binary,'serve','--tool-profile','memory','--brain','n48p'],b'\n'.join(encoded(m) for m in messages)+b'\n',env,home,name=backend+':MCP',mcp=True)
            replies=[json.loads(line) for line in raw.splitlines()]
            check(len(replies)==3 and not replies[0]['result'].get('isError',False),'actual authorized MCP context read')
            check('source_not_allowed' in json.dumps(replies[1]),'actual MCP source deny')
            check(replies[2]['result']['isError'] is True,'actual MCP write default deny')
            observed['mcp']=replies
            sql("UPDATE pages SET body='Changed 中文😀' WHERE id=100")
            check(sql("SELECT dirty,l0,l1,refs_json FROM context_cache WHERE source_id='alpha'",True)==[dict(dirty=1,l0='',l1='',refs_json='[]')],'raw cache content cleared')
            observed['stale']=context(extra=['--layer','L1'])
            check(observed['stale']['content']=='Demo\nChanged 中文😀\n','stale uses new evidence')
            observed['bad-cursor']=context(uri='qbrain://alpha/resources/docs/a',extra=['--layer','L2','--offset','1','--revision',revision],expected=1)
            check(observed['bad-cursor']=={'error':{'code':'stale_or_invalid_cursor'}},'stale cursor exact error')
            observed['wrong-source']=context(uri='qbrain://beta/resources/docs/',expected=1)
            context('summary');sql("DELETE FROM pages WHERE id=100")
            observed['deleted']=context(extra=['--layer','L1']);check(observed['deleted']['page_count']==0,'hard delete invalidates')
            if backend=='postgres':check(not dbpath.exists(),'PG never silently falls back to SQLite')
            check('BETA_SECRET' not in encoded(observed).decode(),'no other-source content')
            results[backend]=observed
    if not sqlite_only:check(encoded(results['sqlite'])==encoded(results['postgres']),'whole output cross-backend equality')
    report=dict(schema='qbrain-n48p-process-v1',passed=True,real_postgres=not sqlite_only,optimized=not __debug__,
                binary_sha256=digest(binary.read_bytes()),script_sha256=digest(Path(__file__).read_bytes()),
                commands=rows,checks=checks,command_count=len(rows),check_count=len(checks),observations=results,paid_model_calls=0)
    (output/'RESULT.json').write_bytes(encoded(report)+b'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('commands','checks','observations')}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--sqlite-only',action='store_true');a=p.parse_args()
    main(a.binary.resolve(strict=True),a.output.resolve(),a.sqlite_only)
