"""Independent N48R process review; only disposable synthetic data, no host login.
Uses real CLI/Hook processes and independent SQL/state observations. No producer imports.
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


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')


def decode(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError('duplicate JSON output')
            result[key] = value
        return result
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main(binary: Path, output: Path, postgres: bool):
    binary = binary.resolve(strict=True)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'raw').mkdir()
    commands, checks = [], []
    def check(ok, name):
        checks.append({'name': name, 'passed': bool(ok)})
        if not ok:
            raise ValueError(name)
    # Do not inherit any model credential or accidental user PostgreSQL defaults.
    base = {k: v for k, v in os.environ.items() if not k.upper().startswith(
        ('QBRAIN', 'PG', 'OPENAI', 'ANTHROPIC', 'GH_TOKEN', 'GITHUB_TOKEN'))}
    base['PGCLIENTENCODING'] = 'UTF8'
    port = os.environ.get('PGPORT', '')
    if postgres:
        check(os.environ.get('QBRAIN_N48R_REVIEW_DISPOSABLE') == '1' and
              port.isdigit() and 1 < int(port) < 65536, 'explicit disposable PG prerequisite')
    def invoke(args, env, cwd, payload=None, parsed=True):
        data = b'' if payload is None else encode(payload)
        result = subprocess.run(list(map(str, args)), input=data, capture_output=True,
                                env=env, cwd=cwd, timeout=30)
        row = {'args': list(map(str, args)), 'exit': result.returncode, 'hashes': {}}
        for name, raw in [('stdin', data), ('stdout', result.stdout), ('stderr', result.stderr)]:
            (output / 'raw' / f'{len(commands):03d}.{name}').write_bytes(raw)
            row['hashes'][name] = digest(raw)
        commands.append(row)
        check(result.returncode == 0 and result.stderr == b'', 'exact native exit and stderr')
        return decode(result.stdout) if parsed else result.stdout
    try:
        with tempfile.TemporaryDirectory(prefix='qbrain-n48r-independent-') as tmp:
            home = Path(tmp)
            project = home / 'project space'; project.mkdir()
            env = {**base, 'HOME': str(home), 'USERPROFILE': str(home),
                   'LOCALAPPDATA': str(home), 'APPDATA': str(home)}
            local = (home if os.name == 'nt' else home / '.local/share') / 'Qbrain/brains/review-hook/brain.db'
            def pg_env(name):
                dsn = f'host=127.0.0.1 port={port} dbname={name} user=qbrain_n48o password=n48r-review-synthetic connect_timeout=2'
                return {**env, 'QBRAIN_PG_DSN': dsn, 'PGHOST': '127.0.0.1', 'PGPORT': port,
                        'PGDATABASE': name, 'PGUSER': 'qbrain_n48o', 'PGPASSWORD': 'n48r-review-synthetic'}
            def cli(args, e, payload=None, parsed=True):
                return invoke([binary, *args, '--brain', 'review-hook'], e, project, payload, parsed)
            def sql(query, e, read=False):
                if 'QBRAIN_PG_DSN' in e:
                    if read:
                        query = "SELECT coalesce(json_agg(t),'[]'::json)::text FROM (" + query + ') t'
                    return invoke(['psql', '-X', '-q', '-A', '-t', '-v', 'ON_ERROR_STOP=1', '-c', query], e, project, parsed=read)
                with closing(sqlite3.connect(local)) as db, db:
                    db.row_factory = sqlite3.Row
                    cursor = db.execute(query)
                    return [dict(r) for r in cursor] if read else None
            def initialize(e):
                cli(['init', '--no-default'], e, parsed=False)
                sql("INSERT INTO sources(id,name) VALUES('alpha','fixture'),('beta','fixture') ON CONFLICT DO NOTHING", e)
                for key, value in [('embed.auto', 'false'), ('memory.writeback', 'salient')]:
                    sql("INSERT INTO config(key,value) VALUES('" + key + "','" + value + "') ON CONFLICT(key) DO UPDATE SET value=excluded.value", e)
            def seed(e, fragment, quote, source='alpha'):
                messages = [dict(role='user', content=quote)]
                body = dict(session_id='independent-seed', fragment_id=fragment, messages=messages)
                event = cli(['memory', 'capture', '--source', source, '--manual'], e, body)
                eid = digest(encode(['qbrain-memory-v1', source, 'independent-seed', fragment,
                                     digest(encode(dict(messages=messages, expires_at=0)))]))
                check(event['event_id'] == eid, 'independent event identity')
                cli(['memory', 'extract', '--source', source, '--event', eid], e)
                item = digest(eid.encode() + encode(dict(category='preference', message_index=0, quote=quote)))
                actual = sql("SELECT item_id,quote,message_index FROM memory_items WHERE event_id='" + eid + "'", e, True)
                check(actual == [dict(item_id=item, quote=quote, message_index=0)], 'independent full quote and support')
                return eid, item
            # Deliberately populate a local SQLite brain, even during PostgreSQL review.
            initialize(env)
            if postgres:
                seed(env, 'fallback', 'I prefer FALLBACK_ONLY_SENTINEL.')
            quote = 'I prefer marker native Unicode 中文😀 and C++.'
            ordinary = 'I prefer marker ordinary sessions.'
            mode = 'normal' if __debug__ else 'optimized'
            db_a, db_b = 'qbrain_n48r_review_' + mode + '_a', 'qbrain_n48r_review_' + mode + '_b'
            active = pg_env(db_a) if postgres else env
            config = home / 'hook-config.json'
            cfg = dict(version=1, enabled=True, host='claude', project_root=str(project),
                       brain_id='review-hook', source_id='alpha', capture=False, extraction='local',
                       recall_bytes=8192, max_items=8, fact_recall=False, fact_promotion=False)
            def hook(kind, e=active, session='same-session', **extra):
                config.write_bytes(encode(cfg))
                result = invoke([binary, 'hook', '--config', config], e, project,
                                dict(hook_event_name=kind, session_id=session, cwd=str(project), **extra))
                check(isinstance(result, dict) and len(encode(result)) <= cfg['recall_bytes'], 'bounded Hook JSON')
                return result
            def text(value):
                return value.get('hookSpecificOutput', {}).get('additionalContext', '')
            if postgres:
                check(sql('SELECT current_database() AS name', active, True) == [{'name': db_a}], 'dedicated PG A')
                check(hook('SessionStart') == {}, 'empty PG refuses despite populated fallback')
                check(sql("SELECT count(*) AS n FROM pg_catalog.pg_tables WHERE schemaname='public'", active, True) == [{'n': 0}], 'Hook never initializes empty PG')
                initialize(active)
            event, item = seed(active, 'same', quote)
            first = hook('UserPromptSubmit', prompt='marker')
            check(quote in text(first), 'first ordinary recall')
            check(hook('UserPromptSubmit', prompt='marker') == {}, 'same session dedup')
            if postgres:
                second = pg_env(db_b)
                check(sql('SELECT current_database() AS name', second, True) == [{'name': db_b}], 'dedicated PG B')
                initialize(second)
                check(seed(second, 'same', quote) == (event, item), 'same item identity across PG databases')
                check(quote in text(hook('UserPromptSubmit', e=second, prompt='marker')), 'effective database participates in dedup key')
                check(hook('UserPromptSubmit', e=active, prompt='marker') == {}, 'returning to first database keeps its dedup state')
                local_before = digest(local.read_bytes())
                broken = {**active, 'QBRAIN_PG_DSN': 'host=127.0.0.1 port=1 dbname=qbrain_n48r_review_a user=qbrain_n48o connect_timeout=1'}
                check(hook('SessionStart', e=broken, session='bad') == {}, 'unreachable PG does not fall back')
                sql('UPDATE public.schema_version SET version=99 WHERE version=13', active)
                check(hook('SessionStart', session='unknown-version') == {}, 'unknown core version refuses')
                sql('UPDATE public.schema_version SET version=13 WHERE version=99', active)
                wrong_scope = {**active, 'QBRAIN_PG_DSN': active['QBRAIN_PG_DSN'] + " options='-c search_path=pg_catalog'"}
                check(hook('SessionStart', e=wrong_scope, session='scope') == {}, 'non-public PG refuses')
                check(digest(local.read_bytes()) == local_before, 'failed PG leaves fallback DB bytes unchanged')
            hook('SessionEnd')
            check(quote in text(hook('UserPromptSubmit', prompt='marker')), 'SessionEnd resets dedup')
            fact = cli(['fact', 'create', '--source', 'alpha'], active, dict(predicate='tool.preference', item_id=item))
            fid = digest(encode(['qbrain-fact-v1', 'alpha', 'user', 'tool.preference', quote, item]))
            check(fact['fact_id'] == fid, 'independent fact identity')
            seed(active, 'ordinary', ordinary)
            seed(active, 'foreign', 'I prefer FOREIGN_ONLY_SENTINEL.', 'beta')
            cfg['fact_recall'] = True
            for host in ('claude', 'codex'):
                cfg['host'] = host
                full = hook('SessionStart', session=host)
                payload = decode(text(full).split('\n', 1)[1].encode())
                check(len(payload['fact_groups']) == 1 and len(payload['memories']) == 1 and
                      payload['memories'][0]['quote'] == ordinary and quote in text(full) and
                      'FOREIGN_ONLY_SENTINEL' not in text(full) and 'FALLBACK_ONLY_SENTINEL' not in text(full), 'scoped full two-lane output')
                for budget in (512, 1024, 8192):
                    cfg['recall_bytes'] = budget
                    bounded = hook('SessionStart', session='budget-' + str(budget))
                    check(not text(bounded) or text(bounded).startswith('Qbrain:'), 'no partial envelope')
                cfg['recall_bytes'] = 8192
            cli(['fact', 'retract', '--source', 'alpha'], active, dict(fact_id=fid, expected_revision=1))
            retired = hook('SessionStart', session='retired')
            check(quote not in text(retired) and ordinary in text(retired), 'withdrawn quote cannot return via legacy lane')
            cfg.update(capture=True, fact_promotion=True)
            captured = 'I prefer CAPTURE_REVIEW_MARKER.'
            hook('UserPromptSubmit', session='capture', turn_id='one', prompt=captured)
            items = cli(['fact', 'read', '--source', 'alpha'], active)['items']
            check(any(x['object'] == captured for x in items), 'read scope ended before capture and promotion')
            def counts():
                return sql('SELECT (SELECT count(*) FROM pages) AS p,(SELECT count(*) FROM memory_items) AS m,(SELECT count(*) FROM memory_facts) AS f', active, True)
            before = counts()
            sql("UPDATE config SET value='off' WHERE key='memory.writeback'", active)
            hook('UserPromptSubmit', session='off', turn_id='off', prompt='I prefer NOT_ALLOWED_MARKER.')
            check(counts() == before, 'shared off blocks installed capture')
            sql("UPDATE config SET value='salient' WHERE key='memory.writeback'", active)
            cfg.update(capture=False, fact_promotion=False)
            hook('UserPromptSubmit', session='no-permission', prompt='I prefer NOT_ALLOWED_MARKER.')
            check(counts() == before, 'local capture permission stays separate')
            for trace in home.glob('*trace*.json'):
                raw = trace.read_bytes(); value = decode(raw)
                check(value['host_consumption_confirmed'] is False and value['provider_calls'] == 0 and
                      len(raw) <= 4096 and all(word not in raw for word in
                      (quote.encode(), captured.encode(), b'password=', b'n48r-review-synthetic', b'FALLBACK_ONLY_SENTINEL')), 'trace is bounded metadata, not DSN or user text')
    except Exception:
        (output / 'PARTIAL.json').write_bytes(encode(dict(passed=False, commands=commands, checks=checks)) + b'\n')
        raise
    report = dict(schema='qbrain-n48r-independent-v1', passed=True, postgres_executed=postgres,
                  optimized=not __debug__, platform=os.name, binary_sha256=digest(binary.read_bytes()),
                  script_sha256=digest(Path(__file__).read_bytes()), command_count=len(commands),
                  check_count=len(checks), commands=commands, checks=checks,
                  real_host_consumption_verified=False, provider_requests_sent=0)
    (output / 'RESULT.json').write_bytes(encode(report) + b'\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('commands', 'checks')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--postgres', action='store_true')
    args = parser.parse_args()
    main(args.binary, args.output, args.postgres)
