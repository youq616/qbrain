"""N47C actual query-directed fact recall, using disposable synthetic data only."""
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

EXPECTED_CHECKS = frozenset(('lazy_recall', 'no_read_schema', 'query_required', 'case_insensitive_ascii_match', 'complete_negated_quote', 'no_inferred_conflict', 'cjk_substring', 'no_implicit_token_split', 'write_default_denied', 'nonmatching_counterclaim_retained', 'explicit_unresolved_edge', 'paired_provenance_revision', 'no_truth_score', 'direct_scope_explicit', 'stable_recall', 'predicate_intersection', 'matching_predicate', 'source_isolation', 'mcp_recall_matches_cli', 'mcp_source_denied', 'mcp_irrelevant_fields', 'mcp_strict_types', 'mcp_missing_query', 'query_byte_cap_not_char_count', 'cli_history_rejected', 'cli_id_rejected', 'cli_duplicate_rejected', 'budget_rejected', 'six_tools_unchanged', 'old_fact_view', 'old_conflict_view', 'whole_neighborhood_budget', 'read_no_revisions_or_jobs', 'surviving_counter_support', 'last_counter_support_forget', 'retracted_counter_hidden', 'superseded_anchor_hidden', 'no_revival_after_replacement_forget', 'soft_delete_hides_anchor', 'restored_evidence_revalidated', 'tamper_hides_anchor', 'hard_delete_hides_anchor', 'ordinary_memory_unchanged', 'no_model_jobs'))
EXPECTED_COMMAND_COUNT = 71  # Fixed full CLI/MCP schedule, including expected failures.


def encode(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')


def run(binary, checks, commands):
    def check(ok,name):
        checks.append({'name':name,'status':'PASS' if ok else 'FAIL'})
        if not ok: raise AssertionError(name)
    with tempfile.TemporaryDirectory(prefix='qbrain-recall-') as d:
        root=Path(d)/'召回 test 😀';root.mkdir()
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
        env.update(HOME=str(root),USERPROFILE=str(root),LOCALAPPDATA=str(root),APPDATA=str(root),TEMP=str(root),TMP=str(root))
        data=root if os.name=='nt' else root/'.local'/'share'
        db_path=data/'Qbrain'/'brains'/'recall-ci'/'brain.db'
        def invoke(args,raw=b'',expected=0):
            try:
                r=subprocess.run([str(binary),*args,'--brain','recall-ci'],input=raw,
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
        def recall(query='MT5',predicate=None,limit=10,budget=8192,source='alpha'):
            args=['--query',query,'--limit',str(limit),'--max-bytes',str(budget)]
            if predicate is not None:args += ['--predicate',predicate]
            return fact('recall',args=args,source=source)
        schema=sql('SELECT COUNT(*) FROM sqlite_master')
        r=recall()
        check(r['items']==[] and r['initialized'] is False,'lazy_recall')
        check(sql('SELECT COUNT(*) FROM sqlite_master')==schema,'no_read_schema')
        bad=fact('recall',expected=1)
        check(bad['error']['code']=='fact_invalid_query','query_required')
        e=seed('a','我偏好不使用 MT5，而选择命令行 QBRECALL。😀');f=seed('b','I prefer graphical menus without a terminal.')
        a,b=claim(e),claim(f)
        r=recall('mt5')
        check(len(r['items'])==1 and r['items'][0]['match_fact_id']==a['fact_id'],'case_insensitive_ascii_match')
        check(r['items'][0]['facts'][0]['object']==e['quote'],'complete_negated_quote')
        check(r['items'][0]['contradictions']==[] and len(r['items'][0]['facts'])==1,'no_inferred_conflict')
        check(recall('命令')['items'][0]['match_fact_id']==a['fact_id'],'cjk_substring')
        check(recall('命令 行')['items']==[],'no_implicit_token_split')
        deny=rpc('memory_write',{'source_id':'alpha','action':'fact_contradict','payload':encode({'fact_id':a['fact_id'],'other_id':b['fact_id']}).decode()})
        check(deny.get('isError') is True,'write_default_denied')
        link(a,b);r=recall();item=r['items'][0]
        check(len(item['facts'])==2 and item['facts'][1]['object']==f['quote'],'nonmatching_counterclaim_retained')
        check(item['conflict_state']=='recorded_conflict' and len(item['contradictions'])==1,'explicit_unresolved_edge')
        check({x['evidence'][0]['event_id'] for x in item['facts']}=={e['event'],f['event']} and all(x['revision']==2 for x in item['facts']),'paired_provenance_revision')
        check(all(x['confidence'] is None and x['untrusted_data'] is True for x in item['facts']),'no_truth_score')
        check(r['neighbors_recursively_expanded'] is False and r['conflict_scope']=='direct_active_assertions','direct_scope_explicit')
        check(recall()==r,'stable_recall')
        check(recall(predicate='other')['items']==[],'predicate_intersection')
        check(recall(predicate='interface.preference')==r,'matching_predicate')
        check(recall(source='beta')['items']==[],'source_isolation')
        reply=rpc('memory_read',{'source_id':'alpha','view':'recall','query':'MT5'})
        check(not reply.get('isError') and content(reply)==r,'mcp_recall_matches_cli')
        check(rpc('memory_read',{'source_id':'beta','view':'recall','query':'MT5'}).get('isError') is True,'mcp_source_denied')
        check(all(rpc('memory_read',{'source_id':'alpha','view':'recall','query':'MT5',**v}).get('isError') for v in
            [{'include_history':False},{'fact_id':a['fact_id']},{'event_id':e['event']}]),'mcp_irrelevant_fields')
        check(all(rpc('memory_read',{'source_id':'alpha','view':'recall',**v}).get('isError') for v in
            [{'query':True},{'query':'MT5','limit':True},{'query':'MT5','max_bytes':'8192'},{'query':'MT5','unknown':'value'}]),'mcp_strict_types')
        check(rpc('memory_read',{'source_id':'alpha','view':'recall'}).get('isError') is True,'mcp_missing_query')
        check(rpc('memory_read',{'source_id':'alpha','view':'recall','query':'界'*400}).get('isError') is True,'query_byte_cap_not_char_count')
        check(fact('recall',args=['--query','MT5','--history'],expected=1)['error']['code']=='invalid_cli_argument','cli_history_rejected')
        check(fact('recall',args=['--query','MT5','--id',a['fact_id']],expected=1)['error']['code']=='invalid_cli_argument','cli_id_rejected')
        check(fact('recall',args=['--query','MT5','--query','x'],expected=1)['error']['code']=='duplicate_argument','cli_duplicate_rejected')
        check(fact('recall',args=['--query','MT5','--max-bytes','511'],expected=1)['error']['code']=='invalid_read_budget','budget_rejected')
        check({t['name'] for t in rpc('',listing=True)['tools']}=={'search','memory_read','memory_write','context_read','context_write','get_page'},'six_tools_unchanged')
        check(fact('read',args=['--id',a['fact_id']])['items'][0]['object']==e['quote'],'old_fact_view')
        check(len(fact('conflicts')['items'])==1,'old_conflict_view')
        big=recall(budget=32768);small=recall(budget=len(encode(big))-1)
        check(small['items']==[] and small['truncated'] and len(encode(small))<=len(encode(big))-1,'whole_neighborhood_budget')
        before=sql('SELECT SUM(revision) FROM memory_facts')
        recall()
        check(sql('SELECT SUM(revision) FROM memory_facts')==before and sql('SELECT COUNT(*) FROM jobs')==0,'read_no_revisions_or_jobs')
        support=seed('support',f['quote']);fact('attach',{'fact_id':b['fact_id'],'item_id':support['item']})
        memory('forget',args=['--event',f['event']]);r=recall()
        check(len(r['items'][0]['facts'])==2 and r['items'][0]['facts'][1]['evidence_count']==1,'surviving_counter_support')
        memory('forget',args=['--event',support['event']]);r=recall()
        check(len(r['items'][0]['facts'])==1 and r['items'][0]['contradictions']==[],'last_counter_support_forget')
        g=seed('counter','I prefer a GUI.');c=claim(g);link(a,c)
        fact('retract',{'fact_id':c['fact_id'],'expected_revision':2})
        check(len(recall()['items'][0]['facts'])==1,'retracted_counter_hidden')
        h=seed('next','I prefer another workflow.');d=claim(h)
        revision=fact('read',args=['--id',a['fact_id']])['items'][0]['revision']
        fact('supersede',{'fact_id':a['fact_id'],'replacement_id':d['fact_id'],'expected_revision':revision})
        check(recall()['items']==[],'superseded_anchor_hidden')
        memory('forget',args=['--event',h['event']])
        check(recall()['items']==[],'no_revival_after_replacement_forget')
        live=seed('live','我偏好 LIVE查询。');live_fact=claim(live)
        page=sql('SELECT page_id FROM memory_events WHERE event_id=?',(live['event'],))
        sql("UPDATE pages SET deleted_at='deleted' WHERE id=?",(page,))
        check(recall('LIVE')['items']==[],'soft_delete_hides_anchor')
        sql('UPDATE pages SET deleted_at=NULL WHERE id=?',(page,))
        check(len(recall('LIVE')['items'])==1,'restored_evidence_revalidated')
        sql("UPDATE memory_fact_evidence SET quote_hash='forged' WHERE fact_id=?",(live_fact['fact_id'],))
        check(recall('LIVE')['items']==[],'tamper_hides_anchor')
        sql('UPDATE memory_fact_evidence SET quote_hash=? WHERE fact_id=?',(hashlib.sha256(live['quote'].encode()).hexdigest(),live_fact['fact_id']))
        sql('DELETE FROM pages WHERE id=?',(page,))
        check(recall('LIVE')['items']==[],'hard_delete_hides_anchor')
        good=seed('ordinary','我偏好保持原话语义。')
        check(memory('read',args=['--query','原话'])['items'][0]['quote']==good['quote'],'ordinary_memory_unchanged')
        check(sql('SELECT COUNT(*) FROM jobs')==0,'no_model_jobs')


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
