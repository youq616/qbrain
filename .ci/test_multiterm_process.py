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
FLAG_MODES = ('default', 'literal', 'all_terms', 'any_terms')
FLAG_ORDERS = ('query_first', 'options_first')
OTHER_FLAG_QUERIES = ('source', 'brain', 'history', 'limit', 'predicate')
VALUE_OPTIONS = ('query', 'match', 'source', 'brain', 'limit', 'predicate', 'max-bytes')
FLAG_QUOTE = 'I prefer literal --match --source --brain --history --limit --predicate tokens for this fixture.'
EXPECTED_CHECKS |= frozenset((
    'flag_seed_complete_evidence', 'flag_match_option_order_invariant', 'flag_reads_no_other_brain',
    *(f'flag_match_{order}_{mode}' for order in FLAG_ORDERS for mode in FLAG_MODES),
    *(f'flag_match_raw_literal_{order}' for order in FLAG_ORDERS),
    *(f'mcp_flag_match_{mode}' for mode in FLAG_MODES),
    *(f'flag_{flag}_{order}' for flag in OTHER_FLAG_QUERIES for order in FLAG_ORDERS),
    *(f'flag_{flag}_option_order' for flag in OTHER_FLAG_QUERIES),
    *(f'mcp_flag_{flag}' for flag in OTHER_FLAG_QUERIES),
    *(f'cli_missing_{option}_value' for option in VALUE_OPTIONS),
    *(f'cli_duplicate_{option}_after_flag_query' for option in VALUE_OPTIONS),
))


def command_specs():
    """Independent fixed oracle; real call sites supply their own semantic names.

    Patterns bind generated IDs across commands. Only the computed group budget
    and generated IDs vary; argv, request bodies and option order stay exact.
    """
    specs = []
    def add(name, args, stdin=(), append_brain=True):
        specs.append((name, [*args, *(['--brain', 'terms-ci'] if append_brain else [])], list(stdin)))
    def fact(name, action, args=(), payload=None, source='alpha'):
        add(name, ['fact', action, '--source', source, *args], () if payload is None else (payload,))
    def memory(name, action, args=(), payload=None):
        add(name, ['memory', action, '--source', 'alpha', *args], () if payload is None else (payload,))
    def seed(tag, quote):
        memory(f'seed-{tag}-capture', 'capture', ['--manual'],
               {'session_id':'multiterm-real-process', 'fragment_id':tag,
                'messages':[{'role':'user', 'content':quote}]})
        memory(f'seed-{tag}-extract', 'extract', ['--event', f'<id:event:{tag}>'])
        fact(f'seed-{tag}-create', 'create', payload={'item_id':f'<id:item:{tag}>', 'predicate':'interface.preference'})
    def recall(name, query='red blue', mode=None, budget='32768', predicate=None, source='alpha'):
        args = ['--query', query, '--limit', '50', '--max-bytes', budget]
        if mode is not None: args += ['--match', mode]
        if predicate is not None: args += ['--predicate', predicate]
        fact(name, 'recall', args, source=source)
    def rpc(name, tool, args=None, write=False, listing=False):
        add(name, ['serve', '--tool-profile', 'memory', *(['--allow-write'] if write else [])], [
            {'jsonrpc':'2.0', 'id':0, 'method':'initialize', 'params':{}},
            {'jsonrpc':'2.0', 'method':'notifications/initialized'},
            {'jsonrpc':'2.0', 'id':1, 'method':'tools/list' if listing else 'tools/call',
             'params':{} if listing else {'name':tool, 'arguments':args}}])
    add('init', ['init'])
    recall('lazy-all-terms', mode='all_terms')
    for tag, quote in (('a','我偏好不使用 red，而选择 blue 命令行。😀'), ('b','I prefer blue before red.'),
                       ('r','I prefer red alone.'), ('z','I prefer blue alone.'), ('c','I prefer graphical menus.')):
        seed(tag, quote)
    recall('continuous-default')
    recall('literal-byte-default')
    recall('literal-byte-explicit', mode='literal')
    recall('all-terms-anchors', mode='all_terms')
    recall('any-terms-anchors', mode='any_terms')
    recall('ascii-separators', ' blue\tred\r\n', 'all_terms')
    recall('repeated-terms', 'red red', 'any_terms')
    recall('mixed-script', '命令行 red', 'all_terms')
    rpc('write-default-denied', 'memory_write', {'source_id':'alpha', 'action':'fact_contradict',
        'payload':{'<json>':{'fact_id':'<id:fact:a>', 'other_id':'<id:fact:c>'}}})
    fact('record-conflict', 'contradict', payload={'fact_id':'<id:fact:a>', 'other_id':'<id:fact:c>'})
    fact('archive-counterclaim', 'archive', payload={'fact_id':'<id:fact:c>', 'expected_revision':2})
    recall('archived-counterclaim-recall', mode='all_terms')
    recall('archived-anchor-absent', 'graphical', 'any_terms')
    for mode in ('literal', 'all_terms', 'any_terms'):
        rpc(f'mcp-{mode}', 'memory_read', {'source_id':'alpha', 'view':'recall', 'query':'red blue',
            'match':mode, 'limit':50, 'max_bytes':32768})
        recall(f'cli-{mode}-parity', mode=mode)
    rpc('mcp-foreign-source', 'memory_read', {'source_id':'beta', 'view':'recall', 'query':'red blue', 'match':'any_terms'})
    recall('cli-foreign-source', mode='any_terms', source='beta')
    recall('predicate-mismatch', mode='all_terms', predicate='other')
    recall('predicate-match', mode='all_terms', predicate='interface.preference')
    for view in ('memories', 'facts', 'conflicts', 'lifecycle', 'lifecycle_candidates', 'lifecycle_batch'):
        rpc(f'wrong-view-{view}', 'memory_read', {'source_id':'alpha', 'view':view, 'match':'all_terms'})
    rpc('write-view-match', 'memory_write', {'source_id':'alpha', 'action':'forget',
        'event_id':'<id:event:a>', 'match':'any_terms'}, write=True)
    for label, value in (('null',None), ('boolean',True), ('number',1), ('array',[]), ('object',{}), ('enum','OR'), ('empty','')):
        rpc(f'strict-match-{label}', 'memory_read', {'source_id':'alpha', 'view':'recall', 'query':'red', 'match':value})
    rpc('mcp-query-required', 'memory_read', {'source_id':'alpha', 'view':'recall', 'match':'all_terms'})
    fact('cli-duplicate-mode', 'recall', ['--query','red','--match','all_terms','--match','any_terms'])
    fact('cli-wrong-action-mode', 'read', ['--match','all_terms'])
    recall('cli-invalid-mode', mode='invalid')
    recall('nine-terms', 'red '*9, 'all_terms')
    recall('eight-terms', 'red '*8, 'any_terms')
    recall('whitespace-over-budget', ' '*1024+'r', 'all_terms')
    recall('exact-byte-budget', ' '*1023+'r', 'all_terms')
    rpc('utf8-byte-budget', 'memory_read', {'source_id':'alpha', 'view':'recall', 'query':'界'*342, 'match':'all_terms'})
    rpc('nul-query', 'memory_read', {'source_id':'alpha', 'view':'recall', 'query':'red\0blue', 'match':'all_terms'})
    recall('whole-sensitive', 'Bearer harmlessFixture', 'all_terms')
    recall('whole-assignment', 'api key = harmlessFixture', 'any_terms')
    recall('nonascii-space', 'red\u00a0blue', 'any_terms')
    recall('literal-wildcards', '% _', 'all_terms')
    rpc('tool-list', '', listing=True)
    fact('old-fact-read', 'read', ['--id','<id:fact:a>'])
    fact('old-conflicts', 'conflicts')
    recall('full-group', '命令行 red', 'all_terms')
    recall('under-group-budget', '命令行 red', 'all_terms', budget='<group-budget>')
    recall('read-no-revisions', mode='all_terms')
    memory('forget-counterclaim', 'forget', ['--event','<id:event:c>'])
    recall('forgotten-counterclaim-recall', '命令行 red', 'all_terms')
    memory('forget-a', 'forget', ['--event','<id:event:a>'])
    memory('forget-b', 'forget', ['--event','<id:event:b>'])
    recall('no-cross-fact-all', mode='all_terms')
    recall('remaining-any', mode='any_terms')
    memory('old-memory-read', 'read', ['--query','red alone'])
    # New calls follow the original 81-call schedule without replacing any case.
    seed('flags', FLAG_QUOTE)
    fact('flag-seed-read', 'read', ['--id','<id:fact:flags>'])
    for order in FLAG_ORDERS:
        for mode in FLAG_MODES:
            opts = ['--source','alpha','--brain','terms-ci','--limit','50','--max-bytes','32768',
                    '--predicate','interface.preference', *([] if mode=='default' else ['--match',mode])]
            args = ['--query','--match',*opts] if order=='query_first' else [*opts,'--query','--match']
            add(f'flag-match-{order}-{mode}', ['fact','recall',*args], append_brain=False)
    for mode in FLAG_MODES:
        rpc(f'mcp-flag-match-{mode}', 'memory_read', {'source_id':'alpha','view':'recall','query':'--match',
            'limit':50,'max_bytes':32768,'predicate':'interface.preference', **({} if mode=='default' else {'match':mode})})
    for flag in OTHER_FLAG_QUERIES:
        for order in FLAG_ORDERS:
            opts = ['--source','alpha','--brain','terms-ci','--limit','50','--max-bytes','32768','--predicate','interface.preference']
            args = ['--query','--'+flag,*opts] if order=='query_first' else [*opts,'--query','--'+flag]
            add(f'flag-{flag}-{order}', ['fact','recall',*args], append_brain=False)
        rpc(f'mcp-flag-{flag}', 'memory_read', {'source_id':'alpha','view':'recall','query':'--'+flag,
            'limit':50,'max_bytes':32768,'predicate':'interface.preference'})
    required = {'brain':'terms-ci','source':'alpha','query':'--match'}
    option_values = {**required, 'match':'literal','limit':'50','predicate':'interface.preference','max-bytes':'32768'}
    for option in VALUE_OPTIONS:
        args = [piece for key, value in required.items() if key!=option for piece in ('--'+key,value)]
        add(f'missing-{option}-value', ['fact','recall',*args,'--'+option], append_brain=False)
    for option in VALUE_OPTIONS:
        args = [piece for key, value in required.items() if key!=option for piece in ('--'+key,value)]
        add(f'duplicate-{option}-after-flag-query', ['fact','recall',*args,
            '--'+option,option_values[option],'--'+option,option_values[option]], append_brain=False)
    return tuple(specs)


COMMAND_SPECS = command_specs()
COMMAND_SCHEDULE = tuple(name for name, _, _ in COMMAND_SPECS)
COMMAND_ARGUMENTS = {name: args for name, args, _ in COMMAND_SPECS}
COMMAND_INPUTS = {name: stdin for name, _, stdin in COMMAND_SPECS}
NEGATIVE = frozenset(('cli-duplicate-mode', 'cli-wrong-action-mode', 'cli-invalid-mode', 'nine-terms',
    'whitespace-over-budget', 'whole-sensitive', 'whole-assignment',
    *(f'missing-{option}-value' for option in VALUE_OPTIONS),
    *(f'duplicate-{option}-after-flag-query' for option in VALUE_OPTIONS)))
EXPECTED_COMMAND_COUNT = len(COMMAND_SCHEDULE)


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
        def invoke(args, raw=b'', expected=0, *, label, append_brain=True):
            argv = [*args, *(['--brain', 'terms-ci'] if append_brain else [])]
            record = {'name':label, 'args':argv, 'stdin_json':[json.loads(line) for line in raw.splitlines()],
                      'exit_code':None, 'expected_exit':expected}
            try:
                p = subprocess.run([str(binary), *argv], input=raw, cwd=root, env=env, capture_output=True, timeout=30)
            except subprocess.TimeoutExpired:
                record['timed_out'] = True
                commands.append(record)
                raise RuntimeError('command timeout')
            record['exit_code'] = p.returncode
            if p.returncode != expected: record['stderr_excerpt'] = p.stderr.decode('utf-8', errors='replace').replace(str(root), '<fixture>')[:1024]
            commands.append(record)
            if p.returncode != expected: raise AssertionError('unexpected command exit at '+str(len(commands)))
            return p.stdout
        def cli(args, payload=None, expected=0, *, label):
            return json.loads(invoke(args, b'' if payload is None else encode(payload), expected, label=label).decode('utf-8-sig'))
        def sql(text, values=()):
            with closing(sqlite3.connect(db_path, timeout=5)) as db:
                db.execute('PRAGMA foreign_keys=ON'); rows=db.execute(text, values).fetchall(); db.commit()
                return rows[0][0] if rows else None
        def fact(action, payload=None, args=(), source='alpha', expected=0, *, label):
            return cli(['fact', action, '--source', source, *args], payload, expected, label=label)
        def memory(action, payload=None, args=(), *, label):
            return cli(['memory', action, '--source', 'alpha', *args], payload, label=label)
        def seed(tag, quote):
            e = memory('capture', {'session_id': 'multiterm-real-process', 'fragment_id': tag, 'messages': [{'role': 'user', 'content': quote}]}, ['--manual'], label=f'seed-{tag}-capture')['event_id']
            memory('extract', args=['--event', e], label=f'seed-{tag}-extract')
            item = sql('SELECT item_id FROM memory_items WHERE event_id=?', (e,))
            f = fact('create', {'item_id': item, 'predicate': 'interface.preference'}, label=f'seed-{tag}-create')
            return {'event': e, 'item': item, 'id': f['fact_id'], 'quote': quote}
        def recall(q='red blue', mode=None, budget=32768, limit=50, predicate=None, source='alpha', expected=0, *, label, raw_output=False):
            args = ['--query', q, '--limit', str(limit), '--max-bytes', str(budget)]
            if mode is not None: args += ['--match', mode]
            if predicate is not None: args += ['--predicate', predicate]
            output = invoke(['fact','recall','--source',source,*args], expected=expected, label=label)
            return output if raw_output else json.loads(output.decode('utf-8-sig'))
        def rpc(name, args=None, write=False, listing=False, *, label):
            messages = [{'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': {}},
                        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list' if listing else 'tools/call', 'params': {} if listing else {'name': name, 'arguments': args}}]
            raw = b'\n'.join(encode(x) for x in messages)+b'\n'
            output = invoke(['serve', '--tool-profile', 'memory', *(['--allow-write'] if write else [])], raw, label=label)
            return next(x['result'] for x in (json.loads(line) for line in output.decode('utf-8').splitlines()) if x.get('id') == 1)
        def content(r): return json.loads(r['content'][-1]['text'])
        def ids(r): return {i['match_fact_id'] for i in r['items']}
        invoke(['init'], label='init')
        sql("INSERT INTO sources(id,name) VALUES('alpha','alpha'),('beta','beta')")
        sql("INSERT INTO config(key,value) VALUES('memory.writeback','salient'),('mcp.allowed_sources','alpha')")
        before=sql('SELECT COUNT(*) FROM sqlite_master')
        lazy=recall(mode='all_terms', label='lazy-all-terms')
        check(lazy['items']==[] and lazy['initialized'] is False and lazy['match_mode']=='all_terms', 'lazy_multi_term_read')
        check(sql('SELECT COUNT(*) FROM sqlite_master')==before, 'lazy_read_no_schema')
        a=seed('a', '我偏好不使用 red，而选择 blue 命令行。😀')
        b=seed('b', 'I prefer blue before red.')
        r=seed('r', 'I prefer red alone.')
        z=seed('z', 'I prefer blue alone.')
        counter=seed('c', 'I prefer graphical menus.')
        sql('UPDATE memory_facts SET created_at=100')
        check(recall(label='continuous-default')['items']==[], 'default_stays_continuous_literal')
        check(recall(label='literal-byte-default',raw_output=True)==recall(mode='literal',label='literal-byte-explicit',raw_output=True), 'explicit_literal_exact_default')
        all_r=recall(mode='all_terms',label='all-terms-anchors');any_r=recall(mode='any_terms',label='any-terms-anchors')
        check(ids(all_r)=={a['id'],b['id']}, 'all_terms_one_anchor')
        check(ids(any_r)=={a['id'],b['id'],r['id'],z['id']}, 'any_terms_union')
        check(all_r['match_mode']=='all_terms' and any_r['match_mode']=='any_terms', 'mode_explicit_not_query_echo')
        check([i['match_fact_id'] for i in any_r['items']]==sorted(ids(any_r)), 'stable_created_id_order')
        check(all_r==recall(' blue\tred\r\n', mode='all_terms',label='ascii-separators'), 'ASCII_whitespace_and_term_order')
        check(ids(recall('red red',mode='any_terms',label='repeated-terms'))=={a['id'],b['id'],r['id']}, 'duplicates_not_duplicate_anchors')
        check(ids(recall('命令行 red',mode='all_terms',label='mixed-script'))=={a['id']}, 'mixed_CJK_and_ASCII')
        matched=next(i for i in all_r['items'] if i['match_fact_id']==a['id'])['facts'][0]
        check(matched['object']==a['quote'] and matched['evidence'][0]['item_id']==a['item'] and matched['evidence'][0]['event_id']==a['event'], 'whole_negation_and_real_evidence')
        check(all(i['facts'][0]['confidence'] is None for i in all_r['items']), 'no_inferred_truth')
        check(all(i['contradictions']==[] for i in all_r['items']), 'no_inferred_conflict')
        denial=rpc('memory_write',{'source_id':'alpha','action':'fact_contradict','payload':encode({'fact_id':a['id'],'other_id':counter['id']}).decode()},label='write-default-denied')
        check(denial.get('isError') is True, 'write_default_denied')
        fact('contradict',{'fact_id':a['id'],'other_id':counter['id']},label='record-conflict')
        fact('archive',{'fact_id':counter['id'],'expected_revision':2},label='archive-counterclaim')
        all_r=recall(mode='all_terms',label='archived-counterclaim-recall')
        item=next(i for i in all_r['items'] if i['match_fact_id']==a['id'])
        check(len(item['facts'])==2 and item['facts'][1]['object']==counter['quote'] and item['facts'][1]['revision']==3, 'archived_nonmatching_counterclaim_complete')
        check(item['conflict_state']=='recorded_conflict' and len(item['contradictions'])==1, 'explicit_conflict_retained')
        check(recall('graphical',mode='any_terms',label='archived-anchor-absent')['items']==[], 'archive_suppresses_anchor')
        for mode in ('literal','all_terms','any_terms'):
            response=rpc('memory_read',{'source_id':'alpha','view':'recall','query':'red blue','match':mode,'limit':50,'max_bytes':32768},label='mcp-'+mode)
            check(not response.get('isError') and content(response)==recall(mode=mode,label='cli-'+mode+'-parity'), 'mcp_'+mode+'_matches_cli')
        check(rpc('memory_read',{'source_id':'beta','view':'recall','query':'red blue','match':'any_terms'},label='mcp-foreign-source').get('isError') is True, 'mcp_foreign_source_denied')
        check(recall(mode='any_terms',source='beta',label='cli-foreign-source')['items']==[], 'cli_foreign_source_isolated')
        check(recall(mode='all_terms',predicate='other',label='predicate-mismatch')['items']==[], 'predicate_intersection')
        check(recall(mode='all_terms',predicate='interface.preference',label='predicate-match')==all_r, 'matching_predicate')
        for view in ('memories','facts','conflicts','lifecycle','lifecycle_candidates','lifecycle_batch'):
            check(rpc('memory_read',{'source_id':'alpha','view':view,'match':'all_terms'},label='wrong-view-'+view).get('isError') is True, 'wrong_view_'+view+'_rejects_match')
        check(rpc('memory_write',{'source_id':'alpha','action':'forget','event_id':a['event'],'match':'any_terms'},write=True,label='write-view-match').get('isError') is True, 'write_view_rejects_match')
        for label,value in [('null',None),('boolean',True),('number',1),('array',[]),('object',{}),('enum','OR'),('empty','')]:
            check(rpc('memory_read',{'source_id':'alpha','view':'recall','query':'red','match':value},label='strict-match-'+label).get('isError') is True, 'strict_match_'+label)
        check(rpc('memory_read',{'source_id':'alpha','view':'recall','match':'all_terms'},label='mcp-query-required').get('isError') is True, 'mcp_query_required')
        check(fact('recall',args=['--query','red','--match','all_terms','--match','any_terms'],expected=1,label='cli-duplicate-mode')['error']['code']=='duplicate_argument','cli_duplicate_mode')
        check(fact('read',args=['--match','all_terms'],expected=1,label='cli-wrong-action-mode')['error']['code']=='invalid_cli_argument','cli_wrong_action_mode')
        check(recall(mode='invalid',expected=1,label='cli-invalid-mode')['error']['code']=='fact_invalid_match','cli_invalid_mode')
        check(recall('red '*9,mode='all_terms',expected=1,label='nine-terms')['error']['code']=='fact_invalid_query','nine_terms_rejected')
        check(ids(recall('red '*8,mode='any_terms',label='eight-terms'))=={a['id'],b['id'],r['id']},'eight_repeated_terms_allowed')
        check(recall(' '*1024+'r',mode='all_terms',expected=1,label='whitespace-over-budget')['error']['code']=='fact_invalid_query','whitespace_counts_in_bytes')
        check(recall(' '*1023+'r',mode='all_terms',label='exact-byte-budget')['match_mode']=='all_terms','exact_1024_bytes')
        check(rpc('memory_read',{'source_id':'alpha','view':'recall','query':'界'*342,'match':'all_terms'},label='utf8-byte-budget').get('isError') is True,'UTF8_not_character_cap')
        check(rpc('memory_read',{'source_id':'alpha','view':'recall','query':'red\0blue','match':'all_terms'},label='nul-query').get('isError') is True,'NUL_query_rejected')
        check(recall('Bearer harmlessFixture',mode='all_terms',expected=1,label='whole-sensitive')['error']['code']=='sensitive_material_rejected','whole_sensitive_before_split')
        check(recall('api key = harmlessFixture',mode='any_terms',expected=1,label='whole-assignment')['error']['code']=='sensitive_material_rejected','whole_assignment_before_split')
        check(recall('red\u00a0blue',mode='any_terms',label='nonascii-space')['items']==[],'nonASCII_whitespace_literal')
        check(recall('% _',mode='all_terms',label='literal-wildcards')['items']==[],'wildcards_not_operators')
        check({t['name'] for t in rpc('',listing=True,label='tool-list')['tools']}=={'search','memory_read','memory_write','context_read','context_write','get_page'},'six_tools_unchanged')
        check(fact('read',args=['--id',a['id']],label='old-fact-read')['items'][0]['object']==a['quote'],'old_fact_view')
        check(len(fact('conflicts',label='old-conflicts')['items'])==1,'old_conflict_view')
        full=recall('命令行 red',mode='all_terms',label='full-group')
        small=recall('命令行 red',mode='all_terms',budget=len(encode(full))-1,label='under-group-budget')
        check(len(full['items'][0]['facts'])==2 and small['items']==[] and small['truncated'] is True,'whole_group_byte_budget')
        before=sql('SELECT SUM(revision) FROM memory_facts');recall(mode='all_terms',label='read-no-revisions')
        check(sql('SELECT SUM(revision) FROM memory_facts')==before and sql('SELECT COUNT(*) FROM jobs')==0,'reads_no_revisions_or_jobs')
        memory('forget',args=['--event',counter['event']],label='forget-counterclaim');after=recall('命令行 red',mode='all_terms',label='forgotten-counterclaim-recall')
        check(len(after['items'][0]['facts'])==1 and after['items'][0]['contradictions']==[],'forget_counterclaim_updates_recall')
        memory('forget',args=['--event',a['event']],label='forget-a');memory('forget',args=['--event',b['event']],label='forget-b')
        check(recall(mode='all_terms',label='no-cross-fact-all')['items']==[] and ids(recall(mode='any_terms',label='remaining-any'))=={r['id'],z['id']},'no_cross_fact_AND_after_forget')
        check(memory('read',args=['--query','red alone'],label='old-memory-read')['items'][0]['quote']==r['quote'],'old_ordinary_memory')

        # Literal values that spell option names must survive the strict parser.
        # A real captured/extracted fact makes an accidentally empty read fail.
        flag = seed('flags', FLAG_QUOTE)
        flag_fact = fact('read',args=['--id',flag['id']],label='flag-seed-read')['items'][0]
        flag_relations = flag_fact.pop('relations')  # Only the fact-read view adds this field.
        check(flag_fact['fact_id']==flag['id'] and flag_fact['object']==FLAG_QUOTE and
              flag_fact['source_id']=='alpha' and flag_fact['predicate']=='interface.preference' and
              flag_fact['evidence_count']==1 and flag_fact['evidence'][0]['item_id']==flag['item'] and
              flag_fact['evidence'][0]['event_id']==flag['event'] and flag_relations==[], 'flag_seed_complete_evidence')
        brain_root = data/'Qbrain'/'brains'
        brain_dirs_before = {str(p.relative_to(brain_root)) for p in brain_root.rglob('*') if p.is_dir()}
        def complete_flag(result, mode='default'):
            return (ids(result)=={flag['id']} and len(result['items'])==1 and
                    result['items'][0]['facts']==[flag_fact] and result['items'][0]['contradictions']==[] and
                    result.get('match_mode')==('literal_substring' if mode in ('default','literal') else mode))
        def flag_read(query, order, mode, label):
            options = ['--source','alpha','--brain','terms-ci','--limit','50','--max-bytes','32768',
                       '--predicate','interface.preference']
            if mode!='default': options += ['--match',mode]
            args = ['--query',query,*options] if order=='query_first' else [*options,'--query',query]
            return invoke(['fact','recall',*args],label=label,append_brain=False)
        flag_raw = {}
        for order in FLAG_ORDERS:
            for mode in FLAG_MODES:
                output = flag_read('--match',order,mode,f'flag-match-{order}-{mode}')
                flag_raw[order,mode] = output
                check(complete_flag(json.loads(output.decode('utf-8-sig')),mode),f'flag_match_{order}_{mode}')
            check(flag_raw[order,'default']==flag_raw[order,'literal'],f'flag_match_raw_literal_{order}')
        check(all(flag_raw['query_first',mode]==flag_raw['options_first',mode] for mode in FLAG_MODES),
              'flag_match_option_order_invariant')
        for mode in FLAG_MODES:
            args = {'source_id':'alpha','view':'recall','query':'--match','limit':50,'max_bytes':32768,
                    'predicate':'interface.preference'}
            if mode!='default': args['match'] = mode
            response = rpc('memory_read',args,label=f'mcp-flag-match-{mode}')
            check(not response.get('isError') and complete_flag(content(response),mode) and
                  content(response)==json.loads(flag_raw['query_first',mode].decode('utf-8-sig')),f'mcp_flag_match_{mode}')
        for token in OTHER_FLAG_QUERIES:
            outputs = []
            for order in FLAG_ORDERS:
                output = flag_read('--'+token,order,'default',f'flag-{token}-{order}')
                outputs.append(output)
                check(complete_flag(json.loads(output.decode('utf-8-sig'))),f'flag_{token}_{order}')
            check(outputs[0]==outputs[1],f'flag_{token}_option_order')
            response = rpc('memory_read',{'source_id':'alpha','view':'recall','query':'--'+token,
                'limit':50,'max_bytes':32768,'predicate':'interface.preference'},label=f'mcp-flag-{token}')
            check(not response.get('isError') and complete_flag(content(response)) and
                  content(response)==json.loads(outputs[0].decode('utf-8-sig')),f'mcp_flag_{token}')

        # Trailing value options remain invalid, and query text cannot hide a
        # duplicate real option. Put --brain explicitly before each trailing case.
        required = {'brain':'terms-ci','source':'alpha','query':'--match'}
        values = {**required,'match':'literal','limit':'50','predicate':'interface.preference','max-bytes':'32768'}
        for option in VALUE_OPTIONS:
            args = [part for key,value in required.items() if key!=option for part in ('--'+key,value)]
            output = invoke(['fact','recall',*args,'--'+option],expected=1,label=f'missing-{option}-value',append_brain=False)
            check(json.loads(output.decode('utf-8-sig'))['error']['code']=='invalid_cli_argument',f'cli_missing_{option}_value')
        for option in VALUE_OPTIONS:
            args = [part for key,value in required.items() if key!=option for part in ('--'+key,value)]
            output = invoke(['fact','recall',*args,'--'+option,values[option],'--'+option,values[option]],
                            expected=1,label=f'duplicate-{option}-after-flag-query',append_brain=False)
            check(json.loads(output.decode('utf-8-sig'))['error']['code']=='duplicate_argument',f'cli_duplicate_{option}_after_flag_query')
        check(brain_dirs_before=={str(p.relative_to(brain_root)) for p in brain_root.rglob('*') if p.is_dir()} and
              {p.parent.name for p in brain_root.rglob('brain.db')}=={'terms-ci'}, 'flag_reads_no_other_brain')


def main():
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace')
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    checks=[];commands=[];r={'result':'FAIL','checks':checks,'commands':commands,'native_windows':os.name=='nt','scope':'synthetic real CLI/MCP; not signed-in host or measured provider egress'}
    try:
        binary=a.binary.resolve(strict=True);r.update(binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        run(binary,checks,commands)
        from validate_multiterm_report import validate_commands
        validate_commands(commands)
        if len(checks)!=len(EXPECTED_CHECKS) or {c['name'] for c in checks}!=EXPECTED_CHECKS:raise AssertionError('incomplete schedule')
        r['result']='PASS'
    except Exception as e:
        r.update(error_type=type(e).__name__,error=str(e))
        if not any(c['status']=='FAIL' for c in checks):checks.append({'name':'execution_interrupted','status':'FAIL'})
    r['counts']={'total':len(checks),'pass':sum(c['status']=='PASS' for c in checks),'fail':sum(c['status']=='FAIL' for c in checks)};r['check_count']=len(checks);r.update(provenance(Path(__file__)))
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'result':r['result'],'checks':r['counts'],'commands':len(commands)}));return 0 if r['result']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
