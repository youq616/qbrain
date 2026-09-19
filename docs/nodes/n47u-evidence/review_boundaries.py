"""Separate N47U black-box review. Public CLI setup; SQL snapshots are read-only.

Explicitly chosen executable, isolated synthetic data, no client/model calls.
Additional checks do not replace the fixed native CI suite. The real-clock expiry
fixture includes a readiness guard and never changes database timestamps by SQL.
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
import time


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encode(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def review(binary: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    checks, records = [], []

    def check(ok, name):
        checks.append({'name': name, 'passed': bool(ok)})
        if not ok:
            raise ValueError(name)

    try:
        with tempfile.TemporaryDirectory(prefix='n47u-review-') as tmp:
            root = Path(tmp) / 'independent 审核'; root.mkdir()
            env = {k: v for k, v in os.environ.items()
                   if not k.upper().startswith(('QBRAIN', 'OPENAI', 'ANTHROPIC', 'GH_TOKEN', 'GITHUB_TOKEN'))}
            env.update(HOME=str(root), USERPROFILE=str(root), LOCALAPPDATA=str(root), APPDATA=str(root))
            dbpath = (root if os.name == 'nt' else root / '.local/share') / 'Qbrain/brains/audit/brain.db'

            def call(args, payload=None, allowed=(0,)):
                request = b'' if payload is None else encode(payload)
                result = subprocess.run([str(binary), *args, '--brain', 'audit'], input=request,
                    cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
                record = {'argv': args, 'exit': result.returncode, 'stdin': request.decode(),
                          'stdout': result.stdout.decode('utf-8'), 'stderr': result.stderr.decode('utf-8')}
                records.append(record)
                if result.returncode not in allowed or result.stderr:
                    raise ValueError('command failure: ' + str(record))
                return result.returncode, result.stdout

            def jcall(args, payload=None, allowed=(0,)):
                code, raw = call(args, payload, allowed)
                return code, json.loads(raw)

            def state():
                with closing(sqlite3.connect(dbpath)) as db:
                    names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
                    values = {name: sorted(db.execute('SELECT * FROM "'+name+'"').fetchall(), key=repr) for name in names}
                    schema = db.execute('SELECT * FROM sqlite_master ORDER BY name').fetchall()
                backups = sorted((p.name, digest(p.read_bytes())) for p in dbpath.parent.glob('*.bak'))
                return digest(repr((values, schema, backups)).encode())

            def seed(fragment, expires=0):
                _, event = jcall(['memory', 'capture', '--manual'], {'session_id': 'independent-review',
                    'fragment_id': fragment, 'expires_at': expires,
                    'messages': [{'role': 'user', 'content': 'I prefer inspectable receipt history 审核。'}]})
                eid = event['event_id']
                jcall(['memory', 'extract', '--event', eid])
                _, memory = jcall(['memory', 'read', '--limit', '50'])
                # The public memory view intentionally deduplicates identical quotes.
                # Read the generated event's item identity without seeding or editing
                # SQL data; all capture/extraction/fact writes stay public CLI calls.
                with closing(sqlite3.connect(dbpath)) as db:
                    rows = db.execute('SELECT item_id,quote FROM memory_items WHERE event_id=?', (eid,)).fetchall()
                if len(rows) != 1 or not any(r['quote'] == rows[0][1] for r in memory['items']):
                    raise ValueError('captured evidence identity/quote not available')
                item = {'item_id': rows[0][0]}
                _, fact = jcall(['fact', 'create'], {'predicate': 'audit.preference', 'item_id': item['item_id']})
                return fact, eid, item['item_id']

            def uid(label):
                return digest(label.encode())

            def use(fact, label):
                _, receipt = jcall(['fact', 'report-use'], {'fact_id': fact['fact_id'],
                    'usage_id': uid(label), 'expected_revision': fact['revision']})
                return receipt

            def listing(fid, filter='all', limit=10, budget=8192, cursor=None):
                args = ['fact', 'usage-list', '--id', fid, '--state', filter,
                        '--limit', str(limit), '--max-bytes', str(budget)]
                if cursor:
                    args += ['--after-id', cursor[0], '--snapshot', cursor[1]]
                code, raw = call(args, allowed=(0, 1))
                value = json.loads(raw)
                if code == 0 and len(raw) > budget:
                    raise ValueError('serialized response exceeds selected byte budget')
                return code, value

            call(['init', '--no-default'])
            call(['config', 'set', 'memory.writeback', 'salient', '--local'])
            first, _, _ = seed('first')
            fid = first['fact_id']
            before = state()
            code, empty = listing(fid, 'withdrawn')
            check(code == 0 and empty['items'] == [] and not empty['has_more'] and not empty['initialized'],
                  'empty filtered set is terminal without initialization')
            check(state() == before, 'empty filtered read preserves tables schema and backups')
            original = {}
            for i in range(4):
                original[uid('old-'+str(i))] = use(first, 'old-'+str(i))
            _, _, support = seed('independent-support')
            _, current = jcall(['fact', 'attach'], {'fact_id': fid, 'item_id': support})
            for i in range(7):
                original[uid('new-'+str(i))] = use(current, 'new-'+str(i))
            revoked = {uid('old-0'), uid('new-0')}
            for rid in revoked:
                jcall(['fact', 'revoke-use'], {'fact_id': fid, 'usage_id': rid})
            expected = {'all': sorted(original), 'withdrawn': sorted(revoked),
                'historical': sorted(k for k, r in original.items() if r['fact_revision'] != current['revision'] and k not in revoked),
                'current': sorted(k for k, r in original.items() if r['fact_revision'] == current['revision'] and k not in revoked)}
            before = state()
            combinations = 0
            for filter, wanted in expected.items():
                for limit in (1, 3, 7, 50):
                    for budget in (512, 900, 1100, 32768):
                        code, page = listing(fid, filter, limit, budget)
                        if code:
                            if page['error']['code'] != 'fact_usage_byte_budget':
                                raise ValueError('unexpected page rejection')
                            combinations += 1
                            continue
                        seen, token, guard = [], page['snapshot'], 0
                        while True:
                            for row in page['items']:
                                old = original[row['usage_id']]
                                if row['reported_at'] != old['reported_at'] or row['fact_revision'] != old['fact_revision']:
                                    raise ValueError('receipt metadata drift')
                            seen += [r['usage_id'] for r in page['items']]
                            if not page['has_more']:
                                if page['next_after_id'] is not None:
                                    raise ValueError('terminal page has continuation')
                                break
                            guard += 1
                            if guard > len(wanted) or not page['items']:
                                raise ValueError('pagination not advancing')
                            code, page = listing(fid, filter, limit, budget, (page['next_after_id'], token))
                            if code or page['snapshot'] != token:
                                raise ValueError('unchanged set continuation failed')
                        if seen != wanted:
                            raise ValueError('page union differs from independently captured receipt IDs')
                        combinations += 1
            check(combinations == 64, '64 filter-limit-budget combinations preserve full ordered sets or explicitly reject budget')
            check(state() == before, 'all page matrices preserve tables schema and backup bytes')
            _, page = listing(fid, 'current', 1)
            cursor = (page['next_after_id'], page['snapshot'])
            # Change only a historical row, outside the selected current filter.
            jcall(['fact', 'revoke-use'], {'fact_id': fid, 'usage_id': uid('old-1')})
            code, out = listing(fid, 'current', 1, cursor=cursor)
            check(code == 1 and out['error']['code'] == 'fact_usage_snapshot_conflict',
                  'off-filter historical withdrawal invalidates current-filter cursor')
            _, page = listing(fid, 'current', 1)
            cursor = (page['next_after_id'], page['snapshot'])
            use(current, 'new-1')
            code, nxt = listing(fid, 'current', 50, 32768, cursor)
            check(code == 0 and nxt['snapshot'] == page['snapshot'], 'no-op duplicate with changed page size keeps snapshot')
            _, stable = listing(fid, limit=1)
            cursor = (stable['next_after_id'], stable['snapshot'])
            unrelated, _, _ = seed('unrelated', 0)
            use(unrelated, 'unrelated-use')
            code, after = listing(fid, limit=1, cursor=cursor)
            check(code == 0 and after['snapshot'] == stable['snapshot'], 'unrelated fact writes do not invalidate target cursor')
            _, _, new_support = seed('third-support')
            jcall(['fact', 'attach'], {'fact_id': fid, 'item_id': new_support})
            code, out = listing(fid, limit=1, cursor=cursor)
            check(code == 1 and out['error']['code'] == 'fact_usage_snapshot_conflict',
                  'support-only revision change invalidates old cursor')
            _, retired = jcall(['fact', 'read', '--id', unrelated['fact_id']])
            jcall(['fact', 'retract'], {'fact_id': unrelated['fact_id'], 'expected_revision': retired['items'][0]['revision']})
            before = state(); code, out = listing(unrelated['fact_id'])
            check(code == 1 and out['error']['code'] == 'fact_state_conflict', 'retired fact is not exposed by metadata listing')
            check(state() == before, 'retired read rejection does not mutate records')
            # Natural expiry through the public capture API, never SQL time edits.
            expires = int(time.time()) + 15
            expiring, event, _ = seed('natural-expiry', expires)
            use(expiring, 'expiry-1'); use(expiring, 'expiry-2')
            code, page = listing(expiring['fact_id'], limit=1)
            check(code == 0 and page['has_more'] and time.time() < expires - 2,
                  'natural expiry fixture is positively readable with preparation margin')
            cursor = (page['next_after_id'], page['snapshot']); before = state()
            while time.time() <= expires:
                time.sleep(0.05)
            code, out = listing(expiring['fact_id'], limit=1, cursor=cursor)
            check(code == 1 and out['error']['code'] == 'fact_not_found', 'expired fact cannot be exposed by previously valid continuation')
            check(state() == before, 'expired continuation rejection is read-only')
            jcall(['memory', 'forget', '--event', event])
            with closing(sqlite3.connect(dbpath)) as db:
                count = db.execute('SELECT COUNT(*) FROM memory_fact_usage WHERE fact_id=?', (expiring['fact_id'],)).fetchone()[0]
            check(count == 0, 'forgetting expired last support removes receipt data')
    except Exception as error:
        checks.append({'name': 'unexpected_exception', 'passed': False, 'error': type(error).__name__+': '+str(error)})
    result = {'schema': 'qbrain-n47u-separate-review-v1', 'binary_sha256': digest(binary.read_bytes()),
              'script_sha256': digest(Path(__file__).read_bytes()), 'platform': os.name,
              'passed': sum(r['passed'] for r in checks), 'failed': sum(not r['passed'] for r in checks),
              'checks': checks, 'commands': records, 'command_count': len(records),
              'model_calls': 0, 'live_client_verified': False,
              'scope': 'Public CLI boundary probes and read-only SQL state snapshots; not all concurrency schedules'}
    (output / 'review.json').write_bytes(encode(result)+b'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = review(args.binary.resolve(strict=True), args.output)
    print(json.dumps({k: v for k, v in result.items() if k not in ('checks', 'commands')}))
    raise SystemExit(1 if result['failed'] else 0)
