"""Native CLI/MCP CJK recall with disposable data; no Agent or model calls."""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sqlite3
import subprocess
import tempfile


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--source-commit')
    p.add_argument('--expected-binary-sha256')
    p.add_argument('--require-windows', action='store_true')
    a = p.parse_args()
    binary = a.binary.resolve(strict=True)
    if a.source_commit and not re.fullmatch(r'[0-9a-f]{40}', a.source_commit):
        p.error('source-commit must be a full lowercase SHA')
    actual_hash = hashlib.sha256(binary.read_bytes()).hexdigest()
    if a.expected_binary_sha256 and actual_hash != a.expected_binary_sha256:
        raise SystemExit('Executable SHA256 does not match; refusing execution')
    if a.require_windows and os.name != 'nt':
        raise SystemExit('Native Windows acceptance cannot use a portable executable')
    checks = []
    report = {'result': 'FAIL', 'source_commit': a.source_commit,
              'binary_sha256': actual_hash, 'native_windows': os.name == 'nt',
              'platform': platform.platform(), 'checks': checks,
              'real_agent_verified': False, 'live_provider_verified': False}

    def check(value, label):
        checks.append({'name': label, 'status': 'PASS' if value else 'FAIL'})
        if not value:
            raise AssertionError(label)
        print('PASS ' + label, flush=True)

    try:
        with tempfile.TemporaryDirectory(prefix='qbrain-cjk-') as d:
            root = Path(d)
            env = {k: v for k, v in os.environ.items()
                   if not k.upper().startswith(('QBRAIN', 'OPENAI', 'ANTHROPIC'))
                   and k.upper() not in {'HOME', 'LOCALAPPDATA', 'USERPROFILE', 'APPDATA'}}
            env.update(HOME=d, LOCALAPPDATA=d, USERPROFILE=d, APPDATA=d)

            def run(args, payload=None):
                raw = b'' if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
                result = subprocess.run([str(binary), *args], input=raw, env=env, cwd=root,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
                if result.returncode:
                    raise RuntimeError('Synthetic command failed: ' + args[0])
                return result.stdout.decode('utf-8')

            def cli(action, *args, payload=None):
                return json.loads(run(['memory', action, '--brain', 'cjk-a', '--source', 'alpha', *args], payload))

            run(['init', '--brain', 'cjk-a', '--no-default'])
            data = root if os.name == 'nt' else root / '.local' / 'share'
            dbpath = data / 'Qbrain/brains/cjk-a/brain.db'

            def sql(statement, args=()):
                with closing(sqlite3.connect(dbpath)) as db:
                    rows = db.execute(statement, args).fetchall()
                    db.commit()
                    return rows

            sql("INSERT INTO sources(id,name) VALUES('alpha','alpha'),('beta','beta')")
            sql("INSERT INTO config(key,value) VALUES('mcp.allowed_sources','alpha')")
            quote = '我偏好使用中文日志前缀，标记 QB_CJK_MARKER。'
            payload = {'session_id': 'synthetic-cjk', 'fragment_id': 'one',
                       'messages': [{'role': 'user', 'content': quote}]}
            event = cli('capture', '--manual', payload=payload)['event_id']
            check(cli('read', '--query', '日志前缀')['items'] == [], 'unextracted_archive_is_not_memory')
            cli('extract', '--event', event)
            for query in ('日志前缀', '日志', '中', 'QB_CJK_MARKER'):
                items = cli('read', '--query', query)['items']
                check(len(items) == 1 and items[0]['quote'] == quote, 'memory_literal_' + str(len(query)))
            check(cli('read', '--query', '中文 前缀')['items'] == [], 'memory_noncontiguous_query_not_invented')
            check(cli('read', '--query', '日誌前綴')['items'] == [], 'no_implicit_traditional_conversion')
            check(len(json.dumps(cli('read', '--max-bytes', '512'), ensure_ascii=False, separators=(',', ':')).encode()) <= 512,
                  'memory_output_budget')

            def search(query):
                return json.loads(run(['search', query, '--brain', 'cjk-a', '--no-vector', '--json']))

            check(any(x['slug'] == 'sessions/' + event for x in search('日志前缀')), 'search_recovers_continuous_chinese')

            def mcp(calls):
                messages = [{'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': {}},
                            {'jsonrpc': '2.0', 'method': 'notifications/initialized'}]
                messages += [{'jsonrpc': '2.0', 'id': i, 'method': 'tools/call',
                              'params': {'name': name, 'arguments': arguments}}
                             for i, (name, arguments) in enumerate(calls, 1)]
                wire = ('\n'.join(json.dumps(x, ensure_ascii=False) for x in messages) + '\n').encode('utf-8')
                proc = subprocess.run([str(binary), 'serve', '--brain', 'cjk-a', '--tool-profile', 'memory'],
                                      input=wire, env=env, cwd=root, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, timeout=30)
                if proc.returncode:
                    raise RuntimeError('Synthetic MCP process failed')
                rows = [json.loads(line) for line in proc.stdout.decode('utf-8').splitlines()]
                replies = {x['id']: x['result'] for x in rows if x.get('id', 0) != 0}
                return [replies[i] for i in range(1, len(calls)+1)]

            def body(reply):
                if reply.get('isError', False):
                    raise AssertionError('Unexpected MCP error')
                return json.loads(reply['content'][-1]['text'])

            for source in ('alpha', 'beta'):
                sql('INSERT INTO pages(source_id,slug,title,body) VALUES(?,?,?,?)',
                    (source, 'joined', 'fixture', '我偏好持续使用汉字检索目标'))
            sql('INSERT INTO pages(source_id,slug,title,body) VALUES(?,?,?,?)',
                ('alpha', 'exact', 'fixture', '汉字检索'))
            replies = mcp([
                ('memory_read', {'source_id': 'alpha', 'query': '日志前缀'}),
                ('search', {'source_id': 'alpha', 'query': '日志前缀', 'no_vector': True, 'mode': 'conservative'}),
                ('memory_read', {'source_id': 'beta', 'query': '日志前缀'}),
                ('search', {'source_id': 'beta', 'query': '汉字检索', 'no_vector': True}),
                ('search', {'source_id': 'alpha', 'query': '汉字检索', 'no_vector': True, 'mode': 'conservative'}),
            ])
            item = body(replies[0])['items'][0]
            check(item['event_id'] == event and item['quote'] == quote and item['method'] == 'explicit-markers-v1',
                  'mcp_memory_exact_quote_and_evidence')
            check(len(body(replies[1])) == 1 and body(replies[1])[0]['source_id'] == 'alpha', 'mcp_search_cjk_source')
            check(replies[2].get('isError') is True, 'mcp_memory_forbidden_source')
            check(replies[3].get('isError') is True, 'mcp_search_forbidden_source')
            joined = body(replies[4])
            check({x['slug'] for x in joined} == {'joined', 'exact'} and all(x['source_id'] == 'alpha' for x in joined),
                  'fts_nonzero_still_fills_missing_cjk')
            check(len({x['page_id'] for x in joined}) == len(joined), 'no_duplicate_hits')
            check(len(search('汉字检索')) == 3, 'cli_all_source_keeps_distinct_pages')
            check(not any(x['slug'] == 'joined' for x in search("汉字%' OR 1=1 --")), 'query_is_not_sql_or_wildcard')
            sql("UPDATE pages SET body='changed' WHERE source_id='alpha' AND slug='joined'")
            check(not any(x['slug'] == 'joined' and x['source_id'] == 'alpha' for x in search('汉字检索')), 'updates_immediately_visible')
            sql("UPDATE pages SET deleted_at='2026-01-01' WHERE source_id='beta' AND slug='joined'")
            check(not any(x['source_id'] == 'beta' for x in search('汉字检索')), 'deleted_cjk_page_excluded')
            sql('UPDATE memory_items SET expires_at=1 WHERE event_id=?', (event,))
            check(cli('read', '--query', '日志前缀')['items'] == [], 'expired_memory_excluded')
            sql('UPDATE memory_items SET expires_at=0 WHERE event_id=?', (event,))
            original = sql('SELECT p.body FROM pages p JOIN memory_events e ON e.page_id=p.id WHERE e.event_id=?', (event,))[0][0]
            sql('UPDATE pages SET body=? WHERE id=(SELECT page_id FROM memory_events WHERE event_id=?)', (original+' ', event))
            check(cli('read', '--query', '日志前缀')['items'] == [], 'tampered_evidence_excluded')
            sql('UPDATE pages SET body=? WHERE id=(SELECT page_id FROM memory_events WHERE event_id=?)', (original, event))
            check(len(cli('read', '--query', '日志前缀')['items']) == 1, 'exact_evidence_restored')
            cli('forget', '--event', event)
            check(cli('read', '--query', '日志前缀')['items'] == [], 'forgotten_memory_excluded')
            check(not search('日志前缀'), 'forgotten_archive_not_recovered_by_page_search')
            check(sql('SELECT count(*) FROM jobs')[0][0] == 0, 'no_embedding_jobs_or_paid_work_created')
            check(sql('PRAGMA integrity_check')[0][0] == 'ok', 'database_integrity')
            report['result'] = 'PASS'
    except Exception as error:
        report['error_type'] = type(error).__name__
        print('FAIL ' + type(error).__name__, flush=True)
    finally:
        report['check_count'] = len(checks)
        report['passed'] = sum(x['status'] == 'PASS' for x in checks)
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f"N46F real-process CJK: {report['passed']}/{len(checks)} checks passed", flush=True)
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
