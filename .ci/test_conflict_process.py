"""N47B actual CLI/MCP conflict inspection, using disposable synthetic data only."""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sqlite3
import sys
import tempfile

EXPECTED_CHECKS = frozenset({
    'lazy_view', 'no_read_migration', 'different_values_not_inferred', 'write_still_denied',
    'explicit_pair', 'canonical_dedup', 'complete_quotes', 'complete_provenance',
    'no_truth_promotion', 'stable_response', 'filter_first', 'filter_second', 'filter_predicate',
    'filters_intersect', 'foreign_source_empty', 'mcp_allowed_read', 'mcp_source_denied',
    'mcp_irrelevant_fields_rejected', 'mcp_strict_types', 'cli_history_rejected',
    'cli_duplicate_rejected', 'invalid_id_rejected', 'invalid_predicate_rejected',
    'six_tools_unchanged', 'old_facts_read_unchanged', 'whole_pair_budget', 'read_no_data_writes',
    'multiple_supports', 'one_support_forgotten', 'last_support_forgotten',
    'retraction_hides_pair', 'supersession_hides_pair', 'soft_delete_hides_pair',
    'restore_evidence_visible', 'tampering_hides_pair', 'hard_delete_hides_pair',
    'ordinary_memory_unchanged', 'no_model_jobs'
})
# Updated only after the complete fixed schedule has executed and been reviewed.
EXPECTED_COMMAND_COUNT = 75


def encode(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')


def run(binary, checks, commands):
    def check(ok,name):
        checks.append({'name':name,'status':'PASS' if ok else 'FAIL'})
        if not ok: raise AssertionError(name)
    with tempfile.TemporaryDirectory(prefix='qbrain-conflict-') as d:
        root=Path(d)/'冲突 test 😀';root.mkdir()
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
        env.update(HOME=str(root),USERPROFILE=str(root),LOCALAPPDATA=str(root),APPDATA=str(root),TEMP=str(root),TMP=str(root))
        data=root if os.name=='nt' else root/'.local'/'share'
        db_path=data/'Qbrain'/'brains'/'conflicts-ci'/'brain.db'
        def invoke(args,raw=b'',expected=0):
            try:
                r=subprocess.run([str(binary),*args,'--brain','conflicts-ci'],input=raw,
                    cwd=root,env=env,capture_output=True,timeout=30)
            except subprocess.TimeoutExpired:
                commands.append({'args':args,'exit_code':None,'expected_exit':expected,'timed_out':True})
                raise RuntimeError('command deadline exceeded')
            record={'args':args,'exit_code':r.returncode,'expected_exit':expected}
            if r.returncode!=expected:
                record['stderr_excerpt']=r.stderr.decode('utf-8',errors='replace').replace(str(root),'<fixture>')[:2048]
            commands.append(record)
            if r.returncode!=expected:raise AssertionError('unexpected command exit: '+str(len(commands)))
            return r.stdout
        def cli(args,payload=None,expected=0):
            return json.loads(invoke(args,b'' if payload is None else encode(payload),expected).decode('utf-8-sig'))
        def sql(text,params=()):
            with closing(sqlite3.connect(db_path,timeout=5)) as db:
                db.execute('PRAGMA foreign_keys=ON');rows=db.execute(text,params).fetchall();db.commit()
                return rows[0][0] if rows else None
        def fact(action,p=None,args=(),source='alpha',expected=0):
            return cli(['fact',action,'--source',source,*args],p,expected)
        def memory(action,p=None,args=()):
            return cli(['memory',action,'--source','alpha',*args],p)
        def seed(tag,quote):
            e=memory('capture',{'session_id':'conflicts-real-process','fragment_id':tag,
                'messages':[{'role':'user','content':quote}]},['--manual'])['event_id']
            memory('extract',args=['--event',e])
            return {'event':e,'item':sql('SELECT item_id FROM memory_items WHERE event_id=?',(e,)),'quote':quote}
        def claim(e,pred='interface.preference'):
            return fact('create',{'item_id':e['item'],'predicate':pred})
        def link(a,b):
            return fact('contradict',{'fact_id':a['fact_id'],'other_id':b['fact_id']})
        def rpc(name,args=None,write=False,listing=False):
            messages=[{'jsonrpc':'2.0','id':0,'method':'initialize','params':{}},
                {'jsonrpc':'2.0','method':'notifications/initialized'},
                {'jsonrpc':'2.0','id':1,'method':'tools/list' if listing else 'tools/call',
                 'params':{} if listing else {'name':name,'arguments':args}}]
            raw=b'\n'.join(encode(m) for m in messages)+b'\n'
            r=invoke(['serve','--tool-profile','memory',*(['--allow-write'] if write else [])],raw)
            return next(x['result'] for x in (json.loads(line) for line in r.decode('utf-8').splitlines()) if x.get('id')==1)
        def content(r):return json.loads(r['content'][-1]['text'])
        def new_pair(tag):
            e=seed(tag+'a','我偏好命令行 '+tag+'。');f=seed(tag+'b','我偏好图形界面 '+tag+'。')
            a=claim(e,tag);b=claim(f,tag);link(a,b);return e,f,a,b
        invoke(['init'])
        sql("INSERT INTO sources(id,name) VALUES('alpha','alpha'),('beta','beta')")
        sql("INSERT INTO config(key,value) VALUES('memory.writeback','salient'),('mcp.allowed_sources','alpha')")
        schema=sql('SELECT COUNT(*) FROM sqlite_master')
        r=fact('conflicts')
        check(r['items']==[] and r['initialized'] is False,'lazy_view')
        check(sql('SELECT COUNT(*) FROM sqlite_master')==schema,'no_read_migration')
        e=seed('first','我偏好不使用 MT5，而使用命令行。😀');f=seed('second','我偏好不使用命令行，而使用图形界面。')
        a,b=claim(e),claim(f)
        check(fact('conflicts')['items']==[],'different_values_not_inferred')
        deny=rpc('memory_write',{'source_id':'alpha','action':'fact_contradict',
            'payload':encode({'fact_id':a['fact_id'],'other_id':b['fact_id']}).decode()})
        check(deny.get('isError') is True,'write_still_denied')
        link(a,b);r=fact('conflicts');pair=r['items'][0]
        check(len(r['items'])==1 and pair['relation']=='contradicts' and pair['resolution']=='unresolved','explicit_pair')
        check(link(b,a)['duplicate'] is True and pair['from_id']<pair['to_id'],'canonical_dedup')
        check(len(pair['facts'])==2 and {p['object'] for p in pair['facts']}=={e['quote'],f['quote']},'complete_quotes')
        check({p['evidence'][0]['event_id'] for p in pair['facts']}=={e['event'],f['event']} and
              all(p['source_id']=='alpha' and p['revision']==2 for p in pair['facts']),'complete_provenance')
        check(r['untrusted_data'] and r['semantics']=='explicit_contradictions_only' and
              all(p['confidence'] is None and p['untrusted_data'] for p in pair['facts']),'no_truth_promotion')
        check(fact('conflicts')==r,'stable_response')
        check(fact('conflicts',args=['--id',a['fact_id']])==r,'filter_first')
        check(fact('conflicts',args=['--id',b['fact_id']])==r,'filter_second')
        check(fact('conflicts',args=['--predicate','interface.preference'])==r,'filter_predicate')
        check(fact('conflicts',args=['--id',a['fact_id'],'--predicate','other'])['items']==[],'filters_intersect')
        check(fact('conflicts',source='beta')['items']==[],'foreign_source_empty')
        reply=rpc('memory_read',{'source_id':'alpha','view':'conflicts'})
        check(not reply.get('isError') and content(reply)==r,'mcp_allowed_read')
        check(rpc('memory_read',{'source_id':'beta','view':'conflicts'}).get('isError') is True,'mcp_source_denied')
        irrelevant=[{'include_history':False},{'query':''},{'event_id':e['event']}]
        check(all(rpc('memory_read',{'source_id':'alpha','view':'conflicts',**x}).get('isError') for x in irrelevant),'mcp_irrelevant_fields_rejected')
        bad_types=[{'limit':True},{'max_bytes':'8192'},{'fact_id':3},{'predicate':False}]
        check(all(rpc('memory_read',{'source_id':'alpha','view':'conflicts',**x}).get('isError') for x in bad_types),'mcp_strict_types')
        check(fact('conflicts',args=['--history'],expected=1)['error']['code']=='invalid_cli_argument','cli_history_rejected')
        check(fact('conflicts',args=['--limit','1','--limit','2'],expected=1)['error']['code']=='duplicate_argument','cli_duplicate_rejected')
        check(fact('conflicts',args=['--id',"x' OR 1=1"],expected=1)['error']['code']=='fact_invalid_id','invalid_id_rejected')
        check(fact('conflicts',args=['--predicate','中文'],expected=1)['error']['code']=='fact_invalid_predicate','invalid_predicate_rejected')
        tools=rpc('',listing=True)
        check({t['name'] for t in tools['tools']}=={'search','memory_read','memory_write','context_read','context_write','get_page'},'six_tools_unchanged')
        old=fact('read')
        check(len(old['items'])==2 and all(len(p['relations'])==1 for p in old['items']),'old_facts_read_unchanged')
        totals=sql('SELECT SUM(revision) FROM memory_facts');schema=sql('SELECT COUNT(*) FROM sqlite_master')
        small=fact('conflicts',args=['--max-bytes','512'])
        check(small['items']==[] and small['truncated'] and len(encode(small))<=512,'whole_pair_budget')
        check(sql('SELECT SUM(revision) FROM memory_facts')==totals and sql('SELECT COUNT(*) FROM sqlite_master')==schema,'read_no_data_writes')
        extra=seed('extra-support',e['quote']);fact('attach',{'fact_id':a['fact_id'],'item_id':extra['item']})
        r=fact('conflicts')
        check(sorted(p['evidence_count'] for p in r['items'][0]['facts'])==[1,2],'multiple_supports')
        memory('forget',args=['--event',e['event']])
        check(len(fact('conflicts')['items'])==1,'one_support_forgotten')
        memory('forget',args=['--event',extra['event']])
        check(fact('conflicts')['items']==[] and sql('SELECT COUNT(*) FROM memory_fact_relations')==0,'last_support_forgotten')
        x,y,c,d=new_pair('retract')
        fact('retract',{'fact_id':c['fact_id'],'expected_revision':2})
        check(fact('conflicts')['items']==[],'retraction_hides_pair')
        x,y,c,d=new_pair('replace')
        fact('supersede',{'fact_id':c['fact_id'],'replacement_id':d['fact_id'],'expected_revision':2})
        check(fact('conflicts')['items']==[],'supersession_hides_pair')
        x,y,c,d=new_pair('delete')
        page=sql('SELECT page_id FROM memory_events WHERE event_id=?',(x['event'],))
        sql("UPDATE pages SET deleted_at='deleted' WHERE id=?",(page,))
        check(fact('conflicts')['items']==[],'soft_delete_hides_pair')
        sql('UPDATE pages SET deleted_at=NULL WHERE id=?',(page,))
        check(len(fact('conflicts')['items'])==1,'restore_evidence_visible')
        sql("UPDATE memory_fact_evidence SET quote_hash='tampered' WHERE fact_id=?",(c['fact_id'],))
        check(fact('conflicts')['items']==[],'tampering_hides_pair')
        sql('UPDATE memory_fact_evidence SET quote_hash=? WHERE fact_id=?',(hashlib.sha256(x['quote'].encode()).hexdigest(),c['fact_id']))
        sql('DELETE FROM pages WHERE id=?',(page,))
        check(fact('conflicts')['items']==[],'hard_delete_hides_pair')
        good=seed('ordinary','我偏好保持原文读取语义。')
        check(memory('read',args=['--query','原文读取'])['items'][0]['quote']==good['quote'],'ordinary_memory_unchanged')
        check(sql('SELECT COUNT(*) FROM jobs')==0 and sql('SELECT COUNT(*) FROM content_chunks')==0,'no_model_jobs')


def provenance(script):
    script=script.resolve()
    root=script.parents[1]
    result={'source_commit':None,'tracked_tree_clean':False}
    try:
        top=subprocess.check_output(['git','rev-parse','--show-toplevel'],cwd=root,stderr=subprocess.DEVNULL,text=True).strip()
        if Path(top).resolve()!=root or script.parent.name!='.ci': return result
        subprocess.run(['git','ls-files','--error-unmatch',str(script.relative_to(root))],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
        clean=subprocess.run(['git','diff','--quiet','HEAD','--'],cwd=root).returncode==0
        result.update(head_commit=head,source_commit=head if clean else None,tracked_tree_clean=clean,
                      source_tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=root,text=True).strip())
    except (OSError,subprocess.SubprocessError): pass
    return result


def main():
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace')
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();checks=[];commands=[]
    r={'result':'FAIL','checks':checks,'commands':commands,'native_windows':os.name=='nt',
       'scope':'synthetic CLI/MCP process tests; not live Agent or measured provider egress'}
    try:
        binary=a.binary.resolve(strict=True)
        r.update(binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        run(binary,checks,commands)
        if len(commands)!=EXPECTED_COMMAND_COUNT or len(checks)!=len(EXPECTED_CHECKS) or {c['name'] for c in checks}!=EXPECTED_CHECKS:
            raise AssertionError('missing or duplicate scenario')
        r['result']='PASS'
    except Exception as e:
        r.update(error_type=type(e).__name__,error=str(e))
        if not any(c['status']=='FAIL' for c in checks):checks.append({'name':'execution_interrupted','status':'FAIL'})
    r['counts']={key:sum(c['status']==key.upper() for c in checks) for key in ('pass','fail')}
    r['counts']['total']=len(checks);r['check_count']=len(checks)
    r.update(provenance(Path(__file__)))
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'result':r['result'],'checks':r['counts'],'commands':len(commands),'report':str(a.report)}))
    return 0 if r['result']=='PASS' else 1


if __name__=='__main__':
    import sqlite3
    raise SystemExit(main())
