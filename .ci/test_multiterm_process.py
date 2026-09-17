"""N47L real CLI/MCP literal, conjunction and disjunction recall tests."""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

EXPECTED_CHECKS = frozenset(('lazy_multi_term_read', 'lazy_read_no_schema', 'default_stays_continuous_literal', 'explicit_literal_exact_default', 'all_terms_one_anchor', 'any_terms_union', 'mode_explicit_not_query_echo', 'stable_created_id_order', 'ASCII_whitespace_and_term_order', 'duplicates_not_duplicate_anchors', 'mixed_CJK_and_ASCII', 'whole_negation_and_real_evidence', 'no_inferred_truth', 'no_inferred_conflict', 'write_default_denied', 'archived_nonmatching_counterclaim_complete', 'explicit_conflict_retained', 'archive_suppresses_anchor', 'mcp_literal_matches_cli', 'mcp_all_terms_matches_cli', 'mcp_any_terms_matches_cli', 'mcp_foreign_source_denied', 'cli_foreign_source_isolated', 'predicate_intersection', 'matching_predicate', 'wrong_view_memories_rejects_match', 'wrong_view_facts_rejects_match', 'wrong_view_conflicts_rejects_match', 'wrong_view_lifecycle_rejects_match', 'wrong_view_lifecycle_candidates_rejects_match', 'wrong_view_lifecycle_batch_rejects_match', 'write_view_rejects_match', 'strict_match_null', 'strict_match_boolean', 'strict_match_number', 'strict_match_array', 'strict_match_object', 'strict_match_enum', 'strict_match_empty', 'mcp_query_required', 'cli_duplicate_mode', 'cli_wrong_action_mode', 'cli_invalid_mode', 'nine_terms_rejected', 'eight_repeated_terms_allowed', 'whitespace_counts_in_bytes', 'exact_1024_bytes', 'UTF8_not_character_cap', 'NUL_query_rejected', 'whole_sensitive_before_split', 'whole_assignment_before_split', 'nonASCII_whitespace_literal', 'wildcards_not_operators', 'six_tools_unchanged', 'old_fact_view', 'old_conflict_view', 'whole_group_byte_budget', 'reads_no_revisions_or_jobs', 'forget_counterclaim_updates_recall', 'no_cross_fact_AND_after_forget', 'old_ordinary_memory'))
EXPECTED_COMMAND_COUNT = 81  # Complete fixed command schedule, including rejected operations.


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def provenance(script):
    root = script.resolve().parents[1]
    result = {'source_commit': None, 'tracked_tree_clean': False}
    try:
        top = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=root, stderr=subprocess.DEVNULL, text=True).strip()
        if Path(top).resolve() != root or script.parent.name != '.ci': return result
        subprocess.run(['git', 'ls-files', '--error-unmatch', str(script.relative_to(root))], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, stderr=subprocess.DEVNULL, text=True).strip()
        clean = subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--'], cwd=root).returncode == 0
        result.update(head_commit=head, source_commit=head if clean else None, tracked_tree_clean=clean,
                      source_tree=subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=root, text=True).strip())
    except (OSError, subprocess.SubprocessError): pass
    return result


def run(binary, checks, commands):
    def check(ok, name):
        checks.append({'name': name, 'status': 'PASS' if ok else 'FAIL'})
        if not ok: raise AssertionError(name)
    with tempfile.TemporaryDirectory(prefix='qbrain-multiterm-') as d:
        root = Path(d)/'多词 test 😀'; root.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(('QBRAIN', 'OPENAI', 'ANTHROPIC'))}
        env.update(HOME=str(root), USERPROFILE=str(root), LOCALAPPDATA=str(root), APPDATA=str(root), TEMP=str(root), TMP=str(root))
        data = root if os.name == 'nt' else root/'.local'/'share'
        db_path = data/'Qbrain'/'brains'/'terms-ci'/'brain.db'
        def invoke(args, raw=b'', expected=0):
            try:
                p = subprocess.run([str(binary), *args, '--brain', 'terms-ci'], input=raw, cwd=root, env=env, capture_output=True, timeout=30)
            except subprocess.TimeoutExpired:
                commands.append({'args': args, 'exit_code': None, 'expected_exit': expected, 'timed_out': True})
                raise RuntimeError('command timeout')
            record = {'args': args, 'exit_code': p.returncode, 'expected_exit': expected}
            if p.returncode != expected: record['stderr_excerpt'] = p.stderr.decode('utf-8', errors='replace').replace(str(root), '<fixture>')[:1024]
            commands.append(record)
            if p.returncode != expected: raise AssertionError('unexpected command exit at '+str(len(commands)))
            return p.stdout
        def cli(args, payload=None, expected=0): return json.loads(invoke(args, b'' if payload is None else encode(payload), expected).decode('utf-8-sig'))
        def sql(text, values=()):
            with closing(sqlite3.connect(db_path, timeout=5)) as db:
                db.execute('PRAGMA foreign_keys=ON'); rows=db.execute(text, values).fetchall(); db.commit()
                return rows[0][0] if rows else None
        def fact(action, payload=None, args=(), source='alpha', expected=0): return cli(['fact', action, '--source', source, *args], payload, expected)
        def memory(action, payload=None, args=()): return cli(['memory', action, '--source', 'alpha', *args], payload)
        def seed(tag, quote):
            e = memory('capture', {'session_id': 'multiterm-real-process', 'fragment_id': tag, 'messages': [{'role': 'user', 'content': quote}]}, ['--manual'])['event_id']
            memory('extract', args=['--event', e])
            item = sql('SELECT item_id FROM memory_items WHERE event_id=?', (e,))
            f = fact('create', {'item_id': item, 'predicate': 'interface.preference'})
            return {'event': e, 'item': item, 'id': f['fact_id'], 'quote': quote}
        def recall(q='red blue', mode=None, budget=32768, limit=50, predicate=None, source='alpha', expected=0):
            args = ['--query', q, '--limit', str(limit), '--max-bytes', str(budget)]
            if mode is not None: args += ['--match', mode]
            if predicate is not None: args += ['--predicate', predicate]
            return fact('recall', args=args, source=source, expected=expected)
        def rpc(name, args=None, write=False, listing=False):
            messages = [{'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': {}},
                        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list' if listing else 'tools/call', 'params': {} if listing else {'name': name, 'arguments': args}}]
            raw = b'\n'.join(encode(x) for x in messages)+b'\n'
            output = invoke(['serve', '--tool-profile', 'memory', *(['--allow-write'] if write else [])], raw)
            return next(x['result'] for x in (json.loads(line) for line in output.decode('utf-8').splitlines()) if x.get('id') == 1)
        def content(r): return json.loads(r['content'][-1]['text'])
        def ids(r): return {i['match_fact_id'] for i in r['items']}
        invoke(['init'])
        sql("INSERT INTO sources(id,name) VALUES('alpha','alpha'),('beta','beta')")
        sql("INSERT INTO config(key,value) VALUES('memory.writeback','salient'),('mcp.allowed_sources','alpha')")
        before=sql('SELECT COUNT(*) FROM sqlite_master')
        lazy=recall(mode='all_terms')
        check(lazy['items']==[] and lazy['initialized'] is False and lazy['match_mode']=='all_terms', 'lazy_multi_term_read')
        check(sql('SELECT COUNT(*) FROM sqlite_master')==before, 'lazy_read_no_schema')
        a=seed('a', '我偏好不使用 red，而选择 blue 命令行。😀')
        b=seed('b', 'I prefer blue before red.')
        r=seed('r', 'I prefer red alone.')
        z=seed('z', 'I prefer blue alone.')
        counter=seed('c', 'I prefer graphical menus.')
        sql('UPDATE memory_facts SET created_at=100')
        check(recall()['items']==[], 'default_stays_continuous_literal')
        check(recall()==recall(mode='literal'), 'explicit_literal_exact_default')
        all_r=recall(mode='all_terms');any_r=recall(mode='any_terms')
        check(ids(all_r)=={a['id'],b['id']}, 'all_terms_one_anchor')
        check(ids(any_r)=={a['id'],b['id'],r['id'],z['id']}, 'any_terms_union')
        check(all_r['match_mode']=='all_terms' and any_r['match_mode']=='any_terms', 'mode_explicit_not_query_echo')
        check([i['match_fact_id'] for i in any_r['items']]==sorted(ids(any_r)), 'stable_created_id_order')
        check(all_r==recall(' blue\tred\r\n', mode='all_terms'), 'ASCII_whitespace_and_term_order')
        check(ids(recall('red red',mode='any_terms'))=={a['id'],b['id'],r['id']}, 'duplicates_not_duplicate_anchors')
        check(ids(recall('命令行 red',mode='all_terms'))=={a['id']}, 'mixed_CJK_and_ASCII')
        matched=next(i for i in all_r['items'] if i['match_fact_id']==a['id'])['facts'][0]
        check(matched['object']==a['quote'] and matched['evidence'][0]['item_id']==a['item'] and matched['evidence'][0]['event_id']==a['event'], 'whole_negation_and_real_evidence')
        check(all(i['facts'][0]['confidence'] is None for i in all_r['items']), 'no_inferred_truth')
        check(all(i['contradictions']==[] for i in all_r['items']), 'no_inferred_conflict')
        denial=rpc('memory_write',{'source_id':'alpha','action':'fact_contradict','payload':encode({'fact_id':a['id'],'other_id':counter['id']}).decode()})
        check(denial.get('isError') is True, 'write_default_denied')
        fact('contradict',{'fact_id':a['id'],'other_id':counter['id']})
        fact('archive',{'fact_id':counter['id'],'expected_revision':2})
        all_r=recall(mode='all_terms')
        item=next(i for i in all_r['items'] if i['match_fact_id']==a['id'])
        check(len(item['facts'])==2 and item['facts'][1]['object']==counter['quote'] and item['facts'][1]['revision']==3, 'archived_nonmatching_counterclaim_complete')
        check(item['conflict_state']=='recorded_conflict' and len(item['contradictions'])==1, 'explicit_conflict_retained')
        check(recall('graphical',mode='any_terms')['items']==[], 'archive_suppresses_anchor')
        for mode in ('literal','all_terms','any_terms'):
            response=rpc('memory_read',{'source_id':'alpha','view':'recall','query':'red blue','match':mode,'limit':50,'max_bytes':32768})
            check(not response.get('isError') and content(response)==recall(mode=mode), 'mcp_'+mode+'_matches_cli')
        check(rpc('memory_read',{'source_id':'beta','view':'recall','query':'red blue','match':'any_terms'}).get('isError') is True, 'mcp_foreign_source_denied')
        check(recall(mode='any_terms',source='beta')['items']==[], 'cli_foreign_source_isolated')
        check(recall(mode='all_terms',predicate='other')['items']==[], 'predicate_intersection')
        check(recall(mode='all_terms',predicate='interface.preference')==all_r, 'matching_predicate')
        for view in ('memories','facts','conflicts','lifecycle','lifecycle_candidates','lifecycle_batch'):
            check(rpc('memory_read',{'source_id':'alpha','view':view,'match':'all_terms'}).get('isError') is True, 'wrong_view_'+view+'_rejects_match')
        check(rpc('memory_write',{'source_id':'alpha','action':'forget','event_id':a['event'],'match':'any_terms'},write=True).get('isError') is True, 'write_view_rejects_match')
        for label,value in [('null',None),('boolean',True),('number',1),('array',[]),('object',{}),('enum','OR'),('empty','')]:
            check(rpc('memory_read',{'source_id':'alpha','view':'recall','query':'red','match':value}).get('isError') is True, 'strict_match_'+label)
        check(rpc('memory_read',{'source_id':'alpha','view':'recall','match':'all_terms'}).get('isError') is True, 'mcp_query_required')
        check(fact('recall',args=['--query','red','--match','all_terms','--match','any_terms'],expected=1)['error']['code']=='duplicate_argument','cli_duplicate_mode')
        check(fact('read',args=['--match','all_terms'],expected=1)['error']['code']=='invalid_cli_argument','cli_wrong_action_mode')
        check(recall(mode='invalid',expected=1)['error']['code']=='fact_invalid_match','cli_invalid_mode')
        check(recall('red '*9,mode='all_terms',expected=1)['error']['code']=='fact_invalid_query','nine_terms_rejected')
        check(ids(recall('red '*8,mode='any_terms'))=={a['id'],b['id'],r['id']},'eight_repeated_terms_allowed')
        check(recall(' '*1024+'r',mode='all_terms',expected=1)['error']['code']=='fact_invalid_query','whitespace_counts_in_bytes')
        check(recall(' '*1023+'r',mode='all_terms')['match_mode']=='all_terms','exact_1024_bytes')
        check(rpc('memory_read',{'source_id':'alpha','view':'recall','query':'界'*342,'match':'all_terms'}).get('isError') is True,'UTF8_not_character_cap')
        check(rpc('memory_read',{'source_id':'alpha','view':'recall','query':'red\0blue','match':'all_terms'}).get('isError') is True,'NUL_query_rejected')
        check(recall('Bearer harmlessFixture',mode='all_terms',expected=1)['error']['code']=='sensitive_material_rejected','whole_sensitive_before_split')
        check(recall('api key = harmlessFixture',mode='any_terms',expected=1)['error']['code']=='sensitive_material_rejected','whole_assignment_before_split')
        check(recall('red\u00a0blue',mode='any_terms')['items']==[],'nonASCII_whitespace_literal')
        check(recall('% _',mode='all_terms')['items']==[],'wildcards_not_operators')
        check({t['name'] for t in rpc('',listing=True)['tools']}=={'search','memory_read','memory_write','context_read','context_write','get_page'},'six_tools_unchanged')
        check(fact('read',args=['--id',a['id']])['items'][0]['object']==a['quote'],'old_fact_view')
        check(len(fact('conflicts')['items'])==1,'old_conflict_view')
        full=recall('命令行 red',mode='all_terms')
        small=recall('命令行 red',mode='all_terms',budget=len(encode(full))-1)
        check(len(full['items'][0]['facts'])==2 and small['items']==[] and small['truncated'] is True,'whole_group_byte_budget')
        before=sql('SELECT SUM(revision) FROM memory_facts');recall(mode='all_terms')
        check(sql('SELECT SUM(revision) FROM memory_facts')==before and sql('SELECT COUNT(*) FROM jobs')==0,'reads_no_revisions_or_jobs')
        memory('forget',args=['--event',counter['event']]);after=recall('命令行 red',mode='all_terms')
        check(len(after['items'][0]['facts'])==1 and after['items'][0]['contradictions']==[],'forget_counterclaim_updates_recall')
        memory('forget',args=['--event',a['event']]);memory('forget',args=['--event',b['event']])
        check(recall(mode='all_terms')['items']==[] and ids(recall(mode='any_terms'))=={r['id'],z['id']},'no_cross_fact_AND_after_forget')
        check(memory('read',args=['--query','red alone'])['items'][0]['quote']==r['quote'],'old_ordinary_memory')


def main():
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace')
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    checks=[];commands=[];r={'result':'FAIL','checks':checks,'commands':commands,'native_windows':os.name=='nt','scope':'synthetic real CLI/MCP; not signed-in host or measured provider egress'}
    try:
        binary=a.binary.resolve(strict=True);r.update(binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        run(binary,checks,commands)
        if len(commands)!=EXPECTED_COMMAND_COUNT or len(checks)!=len(EXPECTED_CHECKS) or {c['name'] for c in checks}!=EXPECTED_CHECKS:raise AssertionError('incomplete schedule')
        r['result']='PASS'
    except Exception as e:
        r.update(error_type=type(e).__name__,error=str(e))
        if not any(c['status']=='FAIL' for c in checks):checks.append({'name':'execution_interrupted','status':'FAIL'})
    r['counts']={'total':len(checks),'pass':sum(c['status']=='PASS' for c in checks),'fail':sum(c['status']=='FAIL' for c in checks)};r['check_count']=len(checks);r.update(provenance(Path(__file__)))
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'result':r['result'],'checks':r['counts'],'commands':len(commands)}));return 0 if r['result']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
