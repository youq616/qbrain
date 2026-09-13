"""Real CLI/MCP evidence-fact lifecycle. Synthetic disposable brains; no provider."""
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
import sys
import tempfile
import threading
import re

EXPECTED_CHECKS = frozenset({
    'lazy_read', 'no_read_migration', 'no_unextracted_promotion', 'exact_quote_claim',
    'source_backing', 'backup_before_module', 'legacy_schema_preserved', 'idempotent_create',
    'no_positive_substring_inference', 'no_confidence_invention', 'foreign_source_rejected',
    'mcp_default_write_denied', 'mcp_source_denied', 'mcp_allowed_read',
    'mcp_allowed_create', 'mcp_strict_inputs', 'six_tools_unchanged',
    'read_budget', 'same_quote_support', 'different_quote_support_denied',
    'explicit_conflict', 'stale_revision_denied', 'supersession_history', 'mcp_history_boolean',
    'no_cycle', 'replacement_forget_no_revival', 'retraction_persists',
    'last_support_forget_purges', 'no_hidden_model_jobs', 'independent_processes',
    'parallel_idempotent_create', 'parallel_cold_start_rounds', 'tamper_suppression', 'ordinary_memory_unchanged'
})

RACE_ROUNDS = 32
EXPECTED_COMMAND_COUNT = 56 + 2 * (RACE_ROUNDS - 1)

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def encode(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')

def execute(binary: Path, checks: list[dict], commands: list[dict]) -> None:
    def check(ok: bool, name: str) -> None:
        checks.append({'name': name, 'status': 'PASS' if ok else 'FAIL'})
        if not ok:
            raise AssertionError(name)
    with tempfile.TemporaryDirectory(prefix='qbrain-n47a-') as temp:
        root = Path(temp) / '事实 space 😀'
        root.mkdir()
        env = {k: v for k, v in os.environ.items()
               if not k.upper().startswith(('QBRAIN', 'OPENAI', 'ANTHROPIC'))}
        env.update(HOME=str(root), LOCALAPPDATA=str(root), USERPROFILE=str(root), APPDATA=str(root))
        data = root if os.name == 'nt' else root / '.local' / 'share'
        db_path = data / 'Qbrain' / 'brains' / 'facts-ci' / 'brain.db'
        record_lock = threading.Lock()
        def record_result(args, r, expected):
            entry = {'args': args, 'exit_code': r.returncode, 'expected_exit': expected}
            if r.returncode != expected:
                # Disposable fixture only: no real credentials or user state.
                for key, raw in (('stdout_excerpt', r.stdout), ('stderr_excerpt', r.stderr)):
                    text = raw.decode('utf-8', errors='replace').replace(str(root), '<fixture>')
                    text = re.sub(r'(?i)(bearer\s+|(?:api[_-]?key|token|secret)\s*[=:]\s*)\S+',
                                  r'\1[REDACTED]', text)
                    entry[key] = text[:2048]
                entry['output_truncated'] = len(r.stdout)>2048 or len(r.stderr)>2048
            with record_lock:
                commands.append(entry)
                number = len(commands)
                if r.returncode != expected:
                    checks.append({'name': 'unexpected_process_exit_' + str(number), 'status': 'FAIL'})
            if r.returncode != expected:
                raise AssertionError('Unexpected command exit; see command ' + str(number))
        def process(args: list[str], payload=None, expected=0):
            raw = b'' if payload is None else encode(payload)
            r = subprocess.run([str(binary), *args, '--brain', 'facts-ci'], input=raw,
                cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            record_result(args, r, expected)
            return r.stdout.decode('utf-8-sig')
        def sql(query, params=(), rows=False):
            with closing(sqlite3.connect(db_path, timeout=5)) as db:
                db.execute('PRAGMA foreign_keys=ON')
                values = db.execute(query, params).fetchall()
                db.commit()
                return values if rows else (values[0][0] if values else None)
        def fact(action, p=None, opts=None, source='alpha', expected=0):
            return json.loads(process(['fact',action,'--source',source,*(opts or [])],p,expected))
        def memory(action, p=None, opts=None):
            return json.loads(process(['memory',action,'--source','alpha',*(opts or [])],p))
        def seed(fragment, quote='我偏好不使用 MT5，而使用命令行。😀'):
            p={'session_id':'facts-real-process','fragment_id':fragment,
               'messages':[{'role':'user','content':quote}]}
            event=memory('capture',p,['--manual'])['event_id']
            memory('extract',opts=['--event',event])
            return {'item':sql('SELECT item_id FROM memory_items WHERE event_id=?',(event,)),
                    'event':event,'quote':quote}
        def create(e, predicate='interface.preference', **kwargs):
            return fact('create',{'predicate':predicate,'item_id':e['item']},**kwargs)
        def read_one(f, history=False):
            r=fact('read',opts=['--id',f['fact_id'],*( ['--history'] if history else [])])
            return r['items'][0] if r['items'] else None
        def rpc(name, args=None, write=False, listing=False):
            requests=[{'jsonrpc':'2.0','id':0,'method':'initialize','params':{}},
                      {'jsonrpc':'2.0','method':'notifications/initialized'},
                      {'jsonrpc':'2.0','id':1,'method':'tools/list' if listing else 'tools/call',
                       'params':{} if listing else {'name':name,'arguments':args}}]
            raw=b'\n'.join(encode(x) for x in requests)+b'\n'
            argv=[str(binary),'serve','--brain','facts-ci','--tool-profile','memory']
            if write: argv.append('--allow-write')
            r=subprocess.run(argv,input=raw,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
            record_result(['serve',name], r, 0)
            return next(x['result'] for x in [json.loads(line) for line in r.stdout.decode('utf-8').splitlines()] if x.get('id')==1)
        def result(reply):
            return json.loads(reply['content'][-1]['text'])
        process(['init'])
        sql("INSERT INTO sources(id,name) VALUES('alpha','alpha'),('beta','beta')")
        sql("INSERT INTO config(key,value) VALUES('memory.writeback','salient'),('mcp.allowed_sources','alpha')")
        sql("INSERT INTO facts(entity_slug,object_text) VALUES('legacy','KEEP-LEGACY')")
        version=sql('SELECT MAX(version) FROM schema_version')
        before=sql('SELECT COUNT(*) FROM sqlite_master')
        initial=fact('read')
        check(initial['items']==[] and initial['initialized'] is False,'lazy_read')
        check(sql('SELECT COUNT(*) FROM sqlite_master')==before,'no_read_migration')
        raw={'session_id':'raw','fragment_id':'raw','messages':[{'role':'user','content':'I prefer raw.'}]}
        event=memory('capture',raw,['--manual'])['event_id']
        error=fact('create',{'predicate':'p','item_id':'a'*64},expected=1)
        check(error['error']['code']=='fact_evidence_unavailable','no_unextracted_promotion')
        first=seed('first'); f=create(first)
        r=read_one(f)
        check(r['object']==first['quote'] and r['subject']=='user' and r['status']=='active','exact_quote_claim')
        check(r['evidence'][0]['item_id']==first['item'] and r['evidence'][0]['event_id']==first['event']
              and r['source_id']=='alpha','source_backing')
        backups=list(db_path.parent.glob('brain.db.pre-facts-v1-*.bak'))
        with closing(sqlite3.connect(backups[0])) as old:
            backup_has_module=old.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='memory_fact_module'").fetchone()[0]
        check(bool(backups) and backup_has_module==0,'backup_before_module')
        check(sql('SELECT MAX(version) FROM schema_version')==version and
              sql("SELECT object_text FROM facts WHERE entity_slug='legacy'")=='KEEP-LEGACY','legacy_schema_preserved')
        check(create(first)['duplicate'] is True and sql('SELECT COUNT(*) FROM memory_facts')==1,'idempotent_create')
        bad=fact('create',{'predicate':'p','item_id':first['item'],'object':'MT5'},expected=1)
        check(bad['error']['code']=='fact_unexpected_argument' and '不使用 MT5' in r['object'],'no_positive_substring_inference')
        check(r['confidence'] is None and r['untrusted_data'] is True,'no_confidence_invention')
        denied=create(first,source='beta',expected=1)
        check(denied['error']['code']=='fact_evidence_unavailable','foreign_source_rejected')
        payload={'predicate':'mcp.preference','item_id':first['item']}
        deny=rpc('memory_write',{'source_id':'alpha','action':'fact_create','payload':encode(payload).decode()})
        check(deny.get('isError') is True and 'write_denied' in str(deny),'mcp_default_write_denied')
        deny=rpc('memory_read',{'source_id':'beta','view':'facts','fact_id':f['fact_id']})
        check(deny.get('isError') is True and 'source_not_allowed' in str(deny),'mcp_source_denied')
        reply=rpc('memory_read',{'source_id':'alpha','view':'facts','fact_id':f['fact_id']})
        check(not reply.get('isError') and result(reply)['items'][0]['object']==first['quote'],'mcp_allowed_read')
        reply=rpc('memory_write',{'source_id':'alpha','action':'fact_create','payload':encode(payload).decode()},write=True)
        mcp_fact=result(reply)
        check(not reply.get('isError') and read_one(mcp_fact)['predicate']=='mcp.preference','mcp_allowed_create')
        bad_args=[{'source_id':'alpha','view':'facts','include_history':'true'},
                  {'source_id':'alpha','view':'facts','limit':True},
                  {'source_id':'alpha','view':'facts','event_id':first['event']},
                  {'source_id':'alpha','view':'memories','fact_id':f['fact_id']}]
        check(all(rpc('memory_read',args).get('isError') is True for args in bad_args),'mcp_strict_inputs')
        listed=rpc('',listing=True)
        check({t['name'] for t in listed['tools']}=={'search','memory_read','memory_write','context_read','context_write','get_page'},'six_tools_unchanged')
        small=fact('read',opts=['--max-bytes','512'])
        check(len(encode(small))<=512 and small['truncated'] is True,'read_budget')
        support=seed('support'); attached=fact('attach',{'fact_id':f['fact_id'],'item_id':support['item']})
        check(attached['revision']==2 and read_one(f)['evidence_count']==2,'same_quote_support')
        other=seed('other','我偏好使用图形界面，而不是命令行。')
        bad=fact('attach',{'fact_id':f['fact_id'],'item_id':other['item']},expected=1)
        check(bad['error']['code']=='fact_quote_mismatch','different_quote_support_denied')
        newer=create(other)
        conflict=fact('contradict',{'fact_id':f['fact_id'],'other_id':newer['fact_id']})
        check(conflict['resolution']=='unresolved' and read_one(f)['status']=='active','explicit_conflict')
        bad=fact('supersede',{'fact_id':f['fact_id'],'replacement_id':newer['fact_id'],'expected_revision':1},expected=1)
        check(bad['error']['code']=='fact_revision_conflict','stale_revision_denied')
        changed=fact('supersede',{'fact_id':f['fact_id'],'replacement_id':newer['fact_id'],'expected_revision':3})
        check(changed['revision']==4 and read_one(f) is None and read_one(f,True)['object']==first['quote'],'supersession_history')
        active_rpc=rpc('memory_read',{'source_id':'alpha','view':'facts','fact_id':f['fact_id'],'include_history':False})
        history_rpc=rpc('memory_read',{'source_id':'alpha','view':'facts','fact_id':f['fact_id'],'include_history':True})
        check(not active_rpc.get('isError') and not history_rpc.get('isError') and
              result(active_rpc)['items']==[] and result(history_rpc)['items'][0]['status']=='superseded',
              'mcp_history_boolean')
        bad=fact('supersede',{'fact_id':newer['fact_id'],'replacement_id':f['fact_id'],'expected_revision':2},expected=1)
        check(bad['error']['code']=='fact_state_conflict','no_cycle')
        memory('forget',opts=['--event',other['event']])
        check(read_one(newer,True) is None and read_one(f) is None and read_one(f,True)['status']=='superseded','replacement_forget_no_revival')
        fact('retract',{'fact_id':f['fact_id'],'expected_revision':4})
        check(create(first)['status']=='retracted','retraction_persists')
        memory('forget',opts=['--event',first['event']]);memory('forget',opts=['--event',support['event']])
        check(sql('SELECT COUNT(*) FROM memory_facts')==0 and sql('SELECT COUNT(*) FROM memory_fact_relations')==0,'last_support_forget_purges')
        check(sql('SELECT COUNT(*) FROM jobs')==0 and sql('SELECT COUNT(*) FROM content_chunks')==0,'no_hidden_model_jobs')
        e=seed('parallel')
        # Fixed schedule, fresh processes and no held-open DB connection. Never
        # retry failed rounds or weaken the one-create/one-duplicate assertion.
        rounds = []
        with ThreadPoolExecutor(max_workers=2) as pool:
            for n in range(RACE_ROUNDS):
                start = threading.Barrier(2)
                def attempt(_):
                    start.wait(timeout=10)
                    return create(e, predicate='race.' + str(n))
                both = list(pool.map(attempt, range(2)))
                rounds.append(both[0]['fact_id']==both[1]['fact_id'] and
                              {b['duplicate'] for b in both}=={False,True})
        check(all(rounds), 'parallel_idempotent_create')
        check(len(rounds)==RACE_ROUNDS and sql('SELECT COUNT(*) FROM memory_facts')==RACE_ROUNDS,
              'parallel_cold_start_rounds')
        f=both[0]
        check(read_one(f)['object']==e['quote'],'independent_processes')
        sql("UPDATE memory_items SET quote='I prefer forged value' WHERE item_id=?",(e['item'],))
        check(read_one(f) is None,'tamper_suppression')
        good=seed('ordinary','我偏好保留完整原话。')
        check(memory('read',opts=['--query','完整原话'])['items'][0]['quote']==good['quote'],'ordinary_memory_unchanged')

def main() -> int:
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'): stream.reconfigure(encoding='utf-8',errors='replace')
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    args=p.parse_args();checks=[];commands=[];report={'result':'FAIL','checks':checks,'commands':commands}
    try:
        binary=args.binary.resolve(strict=True)
        report.update(binary_sha256=sha(binary.read_bytes()),script_sha256=sha(Path(__file__).read_bytes()),native_windows=os.name=='nt')
        execute(binary,checks,commands)
        if len(checks)!=len(EXPECTED_CHECKS) or {c['name'] for c in checks}!=EXPECTED_CHECKS:
            raise AssertionError('Missing or duplicated named check')
        report['result']='PASS'
    except Exception as e:
        report['error_type']=type(e).__name__;report['error']=str(e)
        if not any(c.get('status')=='FAIL' for c in checks):
            checks.append({'name':'execution_interrupted', 'status':'FAIL'})
    report['check_count']=len(checks)
    report['counts']={key:sum(c['status']==key.upper() for c in checks) for key in ('pass','fail')}
    report['counts']['total']=len(checks)
    root=Path(__file__).resolve().parents[1]
    try:
        report['head_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
        clean=subprocess.run(['git','diff','--quiet','HEAD','--'],cwd=root).returncode==0
        report['tracked_tree_clean']=clean;report['source_commit']=report['head_commit'] if clean else None
        report['source_tree']=subprocess.check_output(['git','write-tree'],cwd=root,text=True).strip()
    except (OSError,subprocess.SubprocessError):
        report.update(source_commit=None,tracked_tree_clean=False)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report['result']=='PASS' else 1

if __name__=='__main__':
    raise SystemExit(main())
