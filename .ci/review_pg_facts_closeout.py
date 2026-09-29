"""Independent N48Q process review. Synthetic data; no product/test helper imports.

Run separately on SQLite or a strictly named disposable PostgreSQL database.
All assertions use explicit checks, including under python -O. Raw executions and
failure reports survive. Receipt reports do not prove model or host consumption.
"""
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
import tempfile


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(value):
    return hashlib.sha256(value).hexdigest()


def decoded(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('duplicate JSON key')
            value[key] = item
        return value
    def invalid(_):
        raise ValueError('nonfinite JSON')
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique, parse_constant=invalid)


def run(binary: Path, output: Path, backend: str):
    binary = binary.resolve(strict=True)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'raw').mkdir()
    records, checks = [], []
    original_binary = sha(binary.read_bytes())
    report = {'schema': 'qbrain-n48q-closeout-process-v1', 'passed': False,
              'backend': backend, 'optimized': not __debug__, 'platform': os.name,
              'binary_sha256': original_binary, 'script_sha256': sha(Path(__file__).read_bytes()),
              'provider_requests_sent': 0, 'synthetic_only': True,
              'host_consumption_verified': False, 'records': records, 'checks': checks}

    def check(condition, label):
        checks.append({'name': label, 'passed': bool(condition)})
        if not condition:
            raise ValueError(label)

    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith(('QBRAIN', 'OPENAI', 'ANTHROPIC', 'GH_TOKEN', 'GITHUB_TOKEN'))}
    env['PGCLIENTENCODING'] = 'UTF8'
    if backend == 'postgres':
        check(os.environ.get('QBRAIN_N48Q_REVIEW_DISPOSABLE') == '1', 'explicit disposable authorization')
        check(env.get('PGHOST') == '127.0.0.1' and env.get('PGDATABASE') in
              ('qbrain_n48q_review_normal', 'qbrain_n48q_review_optimized'), 'fixed loopback test database')
        dsn = os.environ.get('QBRAIN_N48Q_REVIEW_DSN', '')
        check(bool(dsn), 'explicit test DSN')
    else:
        dsn = ''

    def record(name, args, data, response, expected=0, parse=True):
        row = {'name': name, 'args': list(map(str, args)), 'exit': response.returncode, 'hashes': {}}
        index = len(records)
        records.append(row)
        for suffix, raw in [('stdin', data), ('stdout', response.stdout), ('stderr', response.stderr)]:
            (output / 'raw' / f'{index:04d}.{suffix}').write_bytes(raw)
            row['hashes'][suffix] = sha(raw)
        check(type(response.returncode) is int and response.returncode == expected, name + ': exact exit')
        check(response.stderr == b'', name + ': empty stderr')
        return decoded(response.stdout) if parse else response.stdout

    try:
        with tempfile.TemporaryDirectory(prefix='qbrain-n48q-closeout-') as tmp:
            home = Path(tmp)
            env.update(HOME=tmp, USERPROFILE=tmp, LOCALAPPDATA=tmp, APPDATA=tmp)
            if backend == 'postgres':
                env['QBRAIN_PG_DSN'] = dsn
            path = (home if os.name == 'nt' else home / '.local/share') / 'Qbrain/brains/qreview/brain.db'

            def call(args, payload=None, expected=0, parse=True):
                command = [str(binary), *args, '--brain', 'qreview']
                data = b'' if payload is None else encoded(payload)
                result = subprocess.run(command, input=data, capture_output=True, env=env, cwd=home, timeout=45)
                return record('product', command, data, result, expected, parse)

            def sql(query, read=False):
                if backend == 'postgres':
                    query = ("SELECT coalesce(json_agg(t),'[]'::json)::text FROM (" + query + ') t') if read else query
                    command = ['psql', '-X', '-q', '-A', '-t', '-v', 'ON_ERROR_STOP=1', '-c', query]
                    result = subprocess.run(command, input=b'', capture_output=True, env=env, cwd=home, timeout=45)
                    return record('psql', command, b'', result, 0, read)
                with closing(sqlite3.connect(path)) as db:
                    db.row_factory = sqlite3.Row
                    cursor = db.execute(query)
                    value = [dict(row) for row in cursor] if read else None
                    db.commit()
                    return value

            if backend == 'postgres':
                check(sql('SELECT current_database() AS db', True) == [{'db': env['PGDATABASE']}], 'connected to exact disposable DB')
            call(['init', '--no-default'], parse=False)
            for source in ('alpha', 'beta'):
                sql("INSERT INTO sources(id,name) VALUES('" + source + "','synthetic-review') ON CONFLICT DO NOTHING")
            for key, value in [('embed.auto', 'false'), ('memory.writeback', 'salient')]:
                sql("INSERT INTO config(key,value) VALUES('" + key + "','" + value + "') ON CONFLICT(key) DO UPDATE SET value=excluded.value")

            def fact(action, payload=None, args=(), expected=0, source='alpha'):
                return call(['fact', action, '--source', source, *args], payload, expected)

            def memory(action, payload=None, args=()):
                return call(['memory', action, '--source', 'alpha', *args], payload)

            def seed(fragment, quote):
                payload = {'session_id': 'independent-closeout', 'fragment_id': fragment,
                           'messages': [{'role': 'user', 'content': quote},
                                        {'role': 'assistant', 'content': 'I prefer ASSISTANT_ONLY_POISON'}]}
                capture = memory('capture', payload, ['--manual'])
                identity = sha(encoded(['qbrain-memory-v1', 'alpha', payload['session_id'], fragment,
                                       sha(encoded({'messages': payload['messages'], 'expires_at': 0}))]))
                check(capture['event_id'] == identity, 'independently derived event ID')
                extracted = memory('extract', args=['--event', identity])
                check(extracted['item_count'] == 1, 'only explicit user evidence extracted')
                item = sha(identity.encode() + encoded({'category': 'preference', 'message_index': 0, 'quote': quote}))
                return identity, item, payload

            def current(fid):
                return fact('read', args=['--id', fid])['items'][0]

            def receipts():
                return sql('SELECT source_id,usage_id,fact_id,fact_revision,reported_at,withdrawn_at FROM memory_fact_usage ORDER BY source_id,usage_id', True)

            check(fact('read')['initialized'] is False, 'read does not create fact schema')
            quote = 'I prefer native C++ Windows 中文😀 review.\r\n'
            event1, item1, payload1 = seed('one', quote)
            event2, item2, _ = seed('two', quote)
            event3, item3, _ = seed('three', 'I prefer a separate database.')
            first = fact('create', {'item_id': item1, 'predicate': 'tool.preference'})
            fid = sha(encoded(['qbrain-fact-v1', 'alpha', 'user', 'tool.preference', quote, item1]))
            check(first['fact_id'] == fid and first['revision'] == 1, 'independently derived fact identity')
            check(fact('create', {'item_id': item1, 'predicate': 'tool.preference'})['duplicate'] is True, 'idempotent fact creation')
            other = fact('create', {'item_id': item3, 'predicate': 'tool.preference'})['fact_id']
            row = current(fid)
            check(row['object'] == quote and row['confidence'] is None and row['untrusted_data'] is True and
                  row['truth_status'] == 'caller_attested_user_statement', 'original evidence and honest confidence')
            check(fact('read', args=['--id', fid], source='beta')['items'] == [], 'cross-source fact read denied')
            denied = fact('create', {'item_id': item1, 'predicate': 'tool.preference'}, source='beta', expected=1)
            check(denied == {'error': {'code': 'fact_evidence_unavailable'}}, 'cross-source evidence cannot create fact')

            uid = sha(b'first-receipt')
            claim = {'fact_id': fid, 'usage_id': uid, 'expected_revision': 1}
            first_use = fact('report-use', claim)
            check(first_use['duplicate'] is False and first_use['host_consumption_verified'] is False, 'receipt not host proof')
            race_uid = sha(b'concurrent-same-id')
            race_claim = {'fact_id': fid, 'usage_id': race_uid, 'expected_revision': 1}
            command = [str(binary), 'fact', 'report-use', '--source', 'alpha', '--brain', 'qreview']
            data = encoded(race_claim)
            def simultaneous(_):
                return subprocess.run(command, input=data, capture_output=True, env=env, cwd=home, timeout=45)
            with ThreadPoolExecutor(max_workers=4) as pool:
                responses = list(pool.map(simultaneous, range(4)))
            replies = [record('concurrent-receipt', command, data, response) for response in responses]
            check(sum(reply['duplicate'] is False for reply in replies) == 1 and
                  sum(reply['duplicate'] is True for reply in replies) == 3, 'four writers create exactly one new receipt')
            check(len(receipts()) == 2, 'two complete receipt rows after duplicate writers')
            page = fact('usage-list', args=['--id', fid, '--limit', '1', '--max-bytes', '2048'])
            check(len(page['items']) == 1 and page['next_after_id'] is not None, 'bounded multi-page receipt list')

            batch = {'operation': 'report', 'items': [
                {'fact_id': fid, 'usage_id': sha(b'batch-first'), 'expected_revision': 1},
                {'fact_id': other, 'usage_id': sha(b'batch-other'), 'expected_revision': 1}]}
            before = receipts()
            preview = fact('usage-batch-preview', batch)
            check(preview['would_change'] == 2 and preview['applied'] is False and receipts() == before, 'multi-fact preview is read-only')
            check(fact('attach', {'fact_id': fid, 'item_id': item2})['revision'] == 2, 'new independent support changes revision')
            failed = fact('usage-batch-apply', {**batch, 'snapshot': preview['snapshot']}, expected=1)
            check(failed == {'error': {'code': 'fact_revision_conflict'}} and receipts() == before, 'stale multi-fact batch rejected without partial writes')
            stale_page = fact('usage-list', args=['--id', fid, '--limit', '1', '--max-bytes', '2048',
                              '--after-id', page['next_after_id'], '--snapshot', page['snapshot']], expected=1)
            check(isinstance(stale_page.get('error', {}).get('code'), str) and
                  stale_page['error']['code'].startswith('fact_usage_'), 'old receipt snapshot fails closed')
            usage = fact('usage', args=['--id', fid])
            check(usage['current_revision_use_count'] == 0 and usage['other_revision_use_count'] == 2, 'old revision receipts are historical')

            batch['items'][0]['expected_revision'] = 2
            preview = fact('usage-batch-preview', batch)
            applied = fact('usage-batch-apply', {**batch, 'snapshot': preview['snapshot']})
            check(applied['changed'] == 2 and applied['applied'] is True and applied['atomic'] is True, 'fresh multi-fact batch commits both rows')
            after = receipts()
            repeated = fact('usage-batch-apply', {**batch, 'snapshot': preview['snapshot']}, expected=1)
            check(repeated == {'error': {'code': 'fact_usage_batch_snapshot_conflict'}} and receipts() == after, 'spent batch snapshot cannot reapply')
            live_uid = batch['items'][0]['usage_id']
            withdrawal = fact('revoke-use', {'fact_id': fid, 'usage_id': live_uid})
            check(withdrawal['status'] == 'withdrawn', 'explicit receipt withdrawal')
            withdrawn_rows = receipts()
            reactivation = fact('report-use', {'fact_id': fid, 'usage_id': live_uid, 'expected_revision': 2}, expected=1)
            check(reactivation == {'error': {'code': 'fact_usage_withdrawn'}} and receipts() == withdrawn_rows, 'withdrawn receipt cannot be resurrected')

            check(fact('archive', {'fact_id': fid, 'expected_revision': 2})['archived'] is True, 'archive is explicit')
            check(fact('recall', args=['--query', 'native C++'])['items'] == [], 'archived fact not recalled')
            check(current(fid)['revision'] == 3, 'archived fact remains explicitly inspectable')
            check(fact('restore', {'fact_id': fid, 'expected_revision': 3})['archived'] is False, 'restore is explicit')
            check(receipts() == withdrawn_rows, 'archive restore does not rewrite receipt history')
            memory('forget', args=['--event', event1])
            survivor = current(fid)
            check(survivor['revision'] == 5 and survivor['evidence_count'] == 1 and survivor['object'] == quote,
                  'independent support survives with new revision')
            check(receipts() == withdrawn_rows, 'support change does not rewrite historical receipts')
            check(memory('capture', payload1, ['--manual'])['status'] == 'forgotten', 'forgotten event replay remains tombstoned')
            memory('forget', args=['--event', event2])
            check(fact('read', args=['--id', fid, '--history'])['items'] == [], 'last support erases historical fact copy')
            for table in ('memory_facts', 'memory_fact_evidence', 'memory_fact_archive', 'memory_fact_usage'):
                check(sql("SELECT count(*) AS n FROM " + table + " WHERE fact_id='" + fid + "'", True) == [{'n': 0}],
                      'physical cleanup ' + table)
            check(current(other)['revision'] == 1 and len(receipts()) == 1 and receipts()[0]['fact_id'] == other,
                  'unrelated supported fact and receipt preserved')
            memory('forget', args=['--event', event3])
            check(sql('SELECT count(*) AS n FROM memory_facts', True) == [{'n': 0}] and receipts() == [], 'final derived state empty')
            if backend == 'postgres':
                check(not path.exists(), 'no fallback SQLite database')
            check(sha(binary.read_bytes()) == original_binary, 'binary unchanged during review')
            report['passed'] = True
    except BaseException as exc:
        report['failure'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        report['command_count'] = len(records)
        report['check_count'] = len(checks)
        (output / 'RESULT.json').write_bytes(encoded(report) + b'\n')
        print(json.dumps({key: value for key, value in report.items() if key not in ('records', 'checks')}, ensure_ascii=False))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--backend', choices=('sqlite', 'postgres'), required=True)
    args = parser.parse_args()
    run(args.binary, args.output, args.backend)
