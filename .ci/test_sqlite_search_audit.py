"""N48N actual CLI tests. Synthetic databases only; no assertion disabled by -O."""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n').encode()


def need(ok, message):
    if not ok:
        raise ValueError(message)


def run(binary, output):
    output.mkdir(parents=True, exist_ok=False)
    (output / 'raw').mkdir()
    commands, checks, cases = [], [], []
    def check(ok, label):
        checks.append({'label': label, 'passed': bool(ok)})
        need(ok, label)
    error = None
    try:
        with tempfile.TemporaryDirectory(prefix='qbrain-audit-search-') as tmp:
            root = Path(tmp) / "中 😀 space '"
            root.mkdir()
            home = root / 'home'
            home.mkdir()
            env = {k: v for k, v in os.environ.items() if not k.upper().startswith(('QBRAIN', 'OPENAI', 'ANTHROPIC', 'GH_TOKEN', 'GITHUB_TOKEN'))}
            env.update(HOME=str(home), USERPROFILE=str(home), LOCALAPPDATA=str(home), APPDATA=str(home))
            def call(label, args, expected=0, parse=True):
                result = subprocess.run([str(binary), *map(str, args)], input=b'', capture_output=True, env=env, cwd=root, timeout=40)
                hashes = {}
                for suffix, raw in [('stdout', result.stdout), ('stderr', result.stderr)]:
                    (output / 'raw' / f'{len(commands):03}.{suffix}').write_bytes(raw)
                    hashes[suffix] = sha(raw)
                commands.append({'label': label, 'args': list(map(str, args)), 'exit': result.returncode, 'expected_exit': expected, 'hashes': hashes})
                need(result.returncode == expected, label + ': ' + result.stdout.decode(errors='replace')[:400])
                need(not result.stderr, label + ' stderr')
                return json.loads(result.stdout) if parse else result.stdout
            call('init', ['init', '--brain', 'fixture'], parse=False)
            data = home if os.name == 'nt' else home / '.local/share'
            qroot = data / 'Qbrain'
            base = qroot / 'brains/fixture/brain.db'
            before_registry = (qroot / 'config.json').read_bytes()
            with closing(sqlite3.connect(base)) as db:
                db.execute('PRAGMA journal_mode=DELETE')
                defs = dict(db.execute("SELECT name,sql FROM sqlite_schema WHERE name IN ('pages_ai','pages_ad','pages_au')"))
                db.execute("INSERT INTO pages(slug,title,body) VALUES('PRIVATE_SLUG','PRIVATE_TITLE','alpha beta café 中文')")
                db.commit()
            scenarios = [
                ('normal', '', 'PASS', True),
                ('empty', 'DELETE FROM pages;', 'PASS', True),
                ('soft-delete', "UPDATE pages SET deleted_at='2026-01-01';", 'PASS', True),
                ('unicode-nul', "UPDATE pages SET body='中文 😀 café '||char(0)||' after';", 'PASS', True),
                ('large-row', "UPDATE pages SET body=replace(hex(zeroblob(1048576)),'0','a ');", 'PASS', True),
                ('other-source', "INSERT INTO sources(id) VALUES('other'); INSERT INTO pages(source_id,slug,body) VALUES('other','PRIVATE_SLUG','other source content');", 'PASS', True),
                ('missing-index', "INSERT INTO pages_fts(pages_fts) VALUES('delete-all');", 'FAIL', False),
                ('stale-body', "DROP TRIGGER pages_au;UPDATE pages SET body='changed';" + defs['pages_au'] + ';', 'FAIL', False),
                ('stale-title', "DROP TRIGGER pages_au;UPDATE pages SET title='changed';" + defs['pages_au'] + ';', 'FAIL', False),
                ('stale-slug', "DROP TRIGGER pages_au;UPDATE pages SET slug='changed';" + defs['pages_au'] + ';', 'FAIL', False),
                ('phantom-index', "INSERT INTO pages_fts(rowid,slug,title,body) VALUES(999,'ghost','ghost','ghost');", 'FAIL', False),
                ('missing-ai', 'DROP TRIGGER pages_ai;', 'FAIL', True),
                ('missing-ad', 'DROP TRIGGER pages_ad;', 'FAIL', True),
                ('noop-au', 'DROP TRIGGER pages_au;CREATE TRIGGER pages_au AFTER UPDATE ON pages BEGIN SELECT 1; END;', 'FAIL', True),
                ('extra-trigger', 'CREATE TRIGGER extra AFTER INSERT ON pages BEGIN SELECT 1; END;', 'FAIL', True),
                ('other-tokenizer', "DROP TABLE pages_fts;CREATE VIRTUAL TABLE pages_fts USING fts5(slug,title,body,content='pages',content_rowid='id',tokenize='porter');", 'UNSUPPORTED', None),
                ('quoted-content', "CREATE TABLE 'pa ges' AS SELECT * FROM pages;DROP TABLE pages_fts;CREATE VIRTUAL TABLE pages_fts USING fts5(slug,title,body,content='pa ges',content_rowid='id',tokenize='unicode61');", 'UNSUPPORTED', None),
            ]
            for name, mutation, status, consistent in scenarios:
                folder = root / name
                folder.mkdir()
                live = folder / 'brain.db'
                shutil.copyfile(base, live)
                with closing(sqlite3.connect(live)) as db:
                    db.executescript(mutation)
                    db.commit()
                    check(db.execute('PRAGMA integrity_check').fetchall() == [('ok',)], name + ' ordinary SQLite check still passes')
                backup = folder / 'backup'
                created = call(name + '-create', ['backup', 'create', '--database', live, '--output', backup])
                pin = created['manifest_sha256']
                original = {p.name: p.read_bytes() for p in backup.iterdir()}
                verified = call(name + '-verify', ['backup', 'verify', '--backup', backup, '--expect-sha256', pin])
                check(verified['result'] == 'VERIFIED', name + ' old verify succeeds')
                code = {'PASS': 0, 'FAIL': 1, 'UNSUPPORTED': 2}[status]
                report = call(name + '-audit', ['backup', 'audit-search', '--backup', backup, '--expect-sha256', pin], expected=code)
                check(report['result'] == status and report['fts_content_consistent'] is consistent, name + ' correct verdict')
                check(report['application_semantics_verified'] is False and report['repair_performed'] is False, name + ' limited claims')
                check(report['manifest_sha256'] == pin and report['database_sha256'] == sha(original['snapshot.sqlite3']), name + ' bound to input')
                check(b'PRIVATE_' not in encode(report) and str(root).encode() not in encode(report), name + ' no contents or paths')
                check(original == {p.name: p.read_bytes() for p in backup.iterdir()}, name + ' exact input preservation')
                shutil.copytree(backup, output / name)
                (output / name / 'audit.json').write_bytes(encode(report))
                cases.append({'name': name, 'result': status, 'fts_content_consistent': consistent, 'pin': pin})
            good = root / 'normal/backup'
            pin = cases[0]['pin']
            def reject(label, args, code):
                result = call(label, ['backup', 'audit-search', *args], expected=2)
                check(result == {'error': {'code': code}}, label + ' exact structured error')
            normal = ['--backup', good, '--expect-sha256', pin]
            reject('bad-pin', ['--backup', good, '--expect-sha256', '0' * 64], 'backup_manifest_digest')
            reject('missing-pin', ['--backup', good], 'search_audit_arguments')
            reject('duplicate', [*normal, '--backup', good], 'search_audit_arguments')
            reject('unknown', [*normal, '--repair', 'true'], 'search_audit_arguments')
            reject('orphan-arg', [*normal, '--timeout-ms'], 'search_audit_arguments')
            reject('bad-time', [*normal, '--timeout-ms', '99'], 'backup_timeout_range')
            reject('bad-time-text', [*normal, '--timeout-ms', '1e4'], 'backup_timeout_range')
            reject('parent-path', ['--backup', good / '..', '--expect-sha256', pin], 'backup_parent_path')
            (good / 'snapshot.sqlite3-wal').write_bytes(b'')
            reject('sidecar', normal, 'backup_inventory')
            (good / 'snapshot.sqlite3-wal').unlink()
            check((qroot / 'config.json').read_bytes() == before_registry, 'registry unchanged')
    except Exception as exc:
        error = type(exc).__name__ + ': ' + str(exc)
    report = {'schema': 'qbrain-search-audit-process-v1', 'binary_sha256': sha(binary.read_bytes()), 'test_sha256': sha(Path(__file__).read_bytes()), 'commands': commands, 'checks': checks, 'cases': cases, 'error': error, 'result': 'PASS' if error is None else 'FAIL'}
    (output / 'report.json').write_bytes(encode(report))
    need(error is None, str(error))
    return {'result': 'PASS', 'commands': len(commands), 'checks': len(checks), 'cases': len(cases)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.binary.resolve(), args.output.resolve()), sort_keys=True))
