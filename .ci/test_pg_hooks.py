"""N48R actual Hook processes on disposable SQLite/PostgreSQL; synthetic host events.
No logged-in host/model-consumption claim. Never read an owner's DB or credentials.
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


def enc(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')
def sha(v): return hashlib.sha256(v).hexdigest()
def need(v,label):
    if not v: raise ValueError(label)
def dec(v):
    def pairs(rows):
        out={}
        for key,value in rows:
            need(key not in out,'duplicate JSON key');out[key]=value
        return out
    return json.loads(v.decode('utf-8-sig'),object_pairs_hook=pairs)

def main(binary,out,sqlite_only):
    binary=binary.resolve(strict=True);out.mkdir(parents=True,exist_ok=False);(out/'raw').mkdir()
    rows=[];checks=[];observations={}
    base_env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
    base_env['PGCLIENTENCODING']='UTF8'
    dsn=os.environ.get('QBRAIN_PG_HOOK_PROCESS_DSN','')
    def check(ok,label): checks.append({'name':label,'passed':bool(ok)});need(ok,label)
    def invoke(args,data=b'',env=None,cwd=None,code=0,parse=True):
        p=subprocess.run(list(map(str,args)),input=data,capture_output=True,env=env,cwd=cwd,timeout=25)
        row={'args':list(map(str,args)),'exit':p.returncode,'hashes':{}}
        for key,val in [('stdin',data),('stdout',p.stdout),('stderr',p.stderr)]:
            (out/'raw'/f'{len(rows):03d}.{key}').write_bytes(val);row['hashes'][key]=sha(val)
        rows.append(row);check(p.returncode==code and p.stderr==b'','exact exit and empty stderr')
        return dec(p.stdout) if parse else p.stdout
    def pgsql(query,env,read=False):
        if read:query="SELECT coalesce(json_agg(t),'[]'::json)::text FROM ("+query+") t"
        return invoke(['psql','-X','-q','-A','-t','-v','ON_ERROR_STOP=1','-c',query],env=env,parse=read)
    if not sqlite_only:
        need(dsn and os.environ.get('QBRAIN_PG_HOOK_TEST_DISPOSABLE')=='1','explicit disposable PG required')
        need(os.environ.get('PGDATABASE')=='qbrain_n48r_process','dedicated Hook process DB')
        check(pgsql('SELECT current_database() AS name',base_env,True)==[{'name':'qbrain_n48r_process'}],'actual test database')
    try:
        with tempfile.TemporaryDirectory(prefix='qbrain-pg-hooks-') as tmp:
            for backend in (('sqlite',) if sqlite_only else ('sqlite','postgres')):
                home=Path(tmp)/backend;home.mkdir();project=home/'中文 project 😀';project.mkdir();outside=home/'outside';outside.mkdir()
                env={**base_env,'HOME':str(home),'USERPROFILE':str(home),'LOCALAPPDATA':str(home),'APPDATA':str(home)}
                if backend=='postgres':env['QBRAIN_PG_DSN']=dsn
                dbpath=(home if os.name=='nt' else home/'.local/share')/'Qbrain/brains/hook-pg-test/brain.db'
                def cli(args,payload=None,code=0,parse=True):
                    return invoke([binary,*args,'--brain','hook-pg-test'],b'' if payload is None else enc(payload),env,project,code,parse)
                cli(['init','--no-default'],parse=False)
                def sql(query,read=False):
                    if backend=='postgres':return pgsql(query,env,read)
                    with closing(sqlite3.connect(dbpath)) as db:
                        db.row_factory=sqlite3.Row;cursor=db.execute(query);value=[dict(x) for x in cursor] if read else None;db.commit();return value
                if backend=='postgres':
                    sql('SET client_min_messages=WARNING; DROP TABLE IF EXISTS public.memory_fact_usage,public.memory_fact_usage_module,public.memory_fact_archive,public.memory_fact_lifecycle_module,public.memory_fact_relations,public.memory_fact_evidence,public.memory_facts,public.memory_fact_module,public.memory_attempts,public.memory_items,public.memory_events,public.memory_module CASCADE; DROP FUNCTION IF EXISTS public.qbrain_fact_evidence_gc_v1() CASCADE')
                sql('DELETE FROM pages;')
                for sid in ('alpha','beta'):sql("INSERT INTO sources(id,name) VALUES('"+sid+"','fixture') ON CONFLICT DO NOTHING")
                for key,val in [('embed.auto','false'),('memory.writeback','salient')]:
                    sql("INSERT INTO config(key,value) VALUES('"+key+"','"+val+"') ON CONFLICT(key) DO UPDATE SET value=excluded.value")
                def seed(fragment,quote,source='alpha'):
                    data=dict(session_id='hook-seed',fragment_id=fragment,messages=[dict(role='user',content=quote)])
                    event=cli(['memory','capture','--source',source,'--manual'],data)['event_id']
                    cli(['memory','extract','--source',source,'--event',event])
                    items=cli(['memory','read','--source',source])['items'];return event,next(x['item_id'] for x in items if x['quote']==quote)
                # New DB on each mode/host run: deleted pages cascade previous test rows.
                quote='I prefer needle PostgreSQL 中文😀.';ordinary='I prefer needle native laptops.'
                _,item=seed('fact',quote);seed('ordinary',ordinary);seed('foreign','I prefer FOREIGN_POISON.','beta')
                fact=cli(['fact','create','--source','alpha'],dict(predicate='tool.preference',item_id=item))
                def facts():return cli(['fact','read','--source','alpha'])['items']
                def counts():
                    return sql("SELECT (SELECT count(*) FROM pages) AS pages,(SELECT count(*) FROM memory_events) AS events,(SELECT count(*) FROM memory_items) AS items,(SELECT count(*) FROM memory_facts) AS facts",True)
                host_observations=[]
                for host in ('claude','codex'):
                    folder=home/host;folder.mkdir();config=folder/'config.json'
                    cfg=dict(version=1,host=host,project_root=str(project),brain_id='hook-pg-test',source_id='alpha',enabled=True,capture=False,extraction='local',recall_bytes=4096,max_items=8,fact_recall=True,fact_promotion=False)
                    def save():config.write_bytes(enc(cfg))
                    save()
                    def event(kind,session='same-session',cwd=None,custom_env=None,**extra):
                        where=cwd or project
                        value=invoke([binary,'hook','--config',config],enc(dict(hook_event_name=kind,session_id=session,cwd=str(where),**extra)),custom_env or env,where)
                        check(len(enc(value))<=cfg['recall_bytes'] and isinstance(value,dict),'one bounded JSON Hook output')
                        return value
                    def content(value):return value.get('hookSpecificOutput',{}).get('additionalContext','')
                    before=counts();r=event('SessionStart')
                    check(quote in content(r) and ordinary in content(r),'fact and ordinary memory arrive through actual Hook')
                    check('FOREIGN_POISON' not in content(r),'cross-source not injected')
                    check(counts()==before,'read-only Hook creates no application rows')
                    parsed=dec(content(r).split('\n',1)[1].encode());check(len(parsed['fact_groups'])==1 and len(parsed['memories'])==1,'two lanes without duplicate quote')
                    r=event('UserPromptSubmit',prompt='needle PostgreSQL laptops')
                    check(quote in content(r) and ordinary not in content(r),'session legacy dedup retains fact groups')
                    event('PreCompact');r=event('UserPromptSubmit',prompt='needle PostgreSQL laptops')
                    check(ordinary in content(r),'compaction permits refreshed legacy recall')
                    cfg['fact_recall']=False;save();r=event('SessionStart',session='legacy-only')
                    check(quote in content(r) and ordinary in content(r),'legacy-only PG Hook path')
                    cfg['fact_recall']=True;cfg['capture']=True;cfg['fact_promotion']=True;save()
                    newquote='I prefer hook capture '+host+' synthetic.'
                    event('UserPromptSubmit',session='capture-'+host,prompt=newquote,turn_id='one')
                    check(any(x['object']==newquote for x in facts()),'automatic capture extract and explicit promotion')
                    before=counts();event('UserPromptSubmit',session='capture-'+host,prompt=newquote,turn_id='one')
                    check(counts()==before,'Hook retry remains idempotent across processes')
                    sql("UPDATE config SET value='off' WHERE key='memory.writeback'");before=counts()
                    event('UserPromptSubmit',session='off',prompt='I prefer DO_NOT_ARCHIVE.',turn_id='off')
                    check(counts()==before,'shared policy off never bypassed')
                    sql("UPDATE config SET value='salient' WHERE key='memory.writeback'")
                    cfg['capture']=False;cfg['fact_promotion']=False;save();before=counts()
                    event('UserPromptSubmit',session='no-capture',prompt='I prefer NOT_INSTALLED_CAPTURE.')
                    check(counts()==before,'per-install capture remains separate permission')
                    cfg['capture']=True;save();event('Stop',last_assistant_message='I prefer ASSISTANT_POISON.')
                    check(all('ASSISTANT_POISON' not in x['object'] for x in facts()),'assistant never promoted')
                    before=counts();check(event('UserPromptSubmit',prompt='password=DO_NOT_STORE_SECRET')=={},'secret refused')
                    check(counts()==before,'no sensitive capture')
                    check(event('SessionStart',cwd=outside)=={},'outside project fails open with empty output')
                    cfg['source_id']='missing';save();check(event('SessionStart')=={},'unknown source fails closed for data');cfg['source_id']='alpha';save()
                    trace=dec((folder/'last-trace.json').read_bytes());check(trace['host_consumption_confirmed'] is False,'Hook trace does not claim model consumption')
                    traces=b''.join(x.read_bytes() for x in folder.glob('*trace*.json'));check(newquote.encode() not in traces and b'DO_NOT_STORE_SECRET' not in traces,'trace contains no raw prompt')
                    # Clean synthetic per-host promoted statement before comparing next host.
                    for x in facts():
                        if x['object']==newquote:
                            for support in x['evidence']:cli(['memory','forget','--source','alpha','--event',support['event_id']])
                    host_observations.append(dict(host=host,fact_quote=quote,ordinary_quote=ordinary,scoped=True))
                cli(['fact','retract','--source','alpha'],dict(fact_id=fact['fact_id'],expected_revision=1))
                r=event('SessionStart',session='after-retraction');check(quote not in content(r) and ordinary in content(r),'retracted fact not revived by ordinary lane')
                if backend=='postgres':
                    check(not dbpath.exists(),'no PostgreSQL fallback brain.db')
                    empty=os.environ.get('QBRAIN_PG_HOOK_EMPTY_DSN','');need(empty,'explicit empty test DB required')
                    r=event('SessionStart',custom_env={**env,'QBRAIN_PG_DSN':empty},session='empty-server')
                    check(r=={},'uninitialized PG server not created by Hook')
                    check(pgsql("SELECT count(*) AS n FROM pg_catalog.pg_tables WHERE schemaname='public'",{**env,'PGDATABASE':'qbrain_n48r_empty'},True)==[{'n':0}],'empty PG schema preserved')
                    check(not dbpath.exists(),'failed PostgreSQL does not fall back to SQLite')
                observations[backend]=host_observations
            if not sqlite_only:check(observations['sqlite']==observations['postgres'],'both backend host semantics agree')
    except Exception:
        (out/'PARTIAL.json').write_bytes(enc(dict(passed=False,commands=rows,checks=checks)));raise
    report=dict(schema='qbrain-pg-hook-process-v1',passed=True,postgres_executed=not sqlite_only,optimized=not __debug__,binary_sha256=sha(binary.read_bytes()),script_sha256=sha(Path(__file__).read_bytes()),command_count=len(rows),check_count=len(checks),commands=rows,checks=checks,observations=observations,real_host_consumption_verified=False)
    (out/'RESULT.json').write_bytes(enc(report)+b'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('commands','checks','observations')}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--sqlite-only',action='store_true')
    a=p.parse_args();main(a.binary,a.output,a.sqlite_only)
