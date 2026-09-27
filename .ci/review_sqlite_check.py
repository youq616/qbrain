"""Separate N48N CLI review: rebuilt FTS vocabulary/positions and adversarial DDL.
No imports of product code, the qualification script, or its fixture helpers.
"""
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

IDS = ['sqlite_integrity', 'foreign_keys', 'core_inventory', 'page_relations',
       'fts_definition', 'fts_triggers', 'fts_content']


def need(ok, label):
    if not ok:
        raise ValueError(label)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(',', ':')) + '\n').encode()


def tokens(image):
    # Python 3.9 runners do not expose Connection.deserialize. Source is a private
    # immutable copy; expected index is rebuilt independently, wholly in memory.
    with closing(sqlite3.connect(image.resolve().as_uri() + '?mode=ro&immutable=1', uri=True)) as db, \
            closing(sqlite3.connect(':memory:')) as ref, closing(sqlite3.connect(':memory:')) as actual:
        db.backup(actual)
        ref.execute('CREATE VIRTUAL TABLE expected USING fts5(slug,title,body,tokenize="unicode61")')
        rows = actual.execute('SELECT id,slug,title,body FROM pages').fetchall()
        ref.executemany('INSERT INTO expected(rowid,slug,title,body) VALUES(?,?,?,?)', rows)
        actual.execute("CREATE VIRTUAL TABLE temp.av USING fts5vocab(main,pages_fts,instance)")
        ref.execute("CREATE VIRTUAL TABLE temp.ev USING fts5vocab(main,expected,instance)")
        a = actual.execute('SELECT term,doc,col,offset FROM av ORDER BY term,doc,col,offset').fetchall()
        b = ref.execute('SELECT term,doc,col,offset FROM ev ORDER BY term,doc,col,offset').fetchall()
        return dict(equal=a == b, actual=len(a), reference=len(b),
                    actual_sha256=sha(encoded(a)), reference_sha256=sha(encoded(b)))


def validate(raw, expected, wanted):
    value = json.loads(raw)
    need(value['schema'] == 'qbrain-database-check-v1', 'schema')
    need(type(value['checks']) is list and [x['id'] for x in value['checks']] == IDS, 'ordered checks')
    actual = {x['id']: x['status'] for x in value['checks']}
    for item in value['checks']:
        need(set(item) == {'id', 'status', 'issues'}, 'check keys')
        need(item['status'] in ['PASS', 'FAIL', 'NOT_RUN'], 'status')
        need(type(item['issues']) is list and bool(item['issues']) == (item['status'] == 'FAIL'), 'findings retained')
    need(value['result'] == ['CHECK_PASSED', 'CHECK_FAILED', 'ERROR'][expected], 'verdict')
    if expected == 0:
        need(all(v == 'PASS' for v in actual.values()), 'no skipped success')
    elif expected == 1:
        need('FAIL' in actual.values(), 'real failed check')
    else:
        need(type(value.get('error')) is dict, 'error is not success')
    for key, status in wanted.items():
        need(actual[key] == status, key + ' ' + status)
    for key in ['source_repaired', 'registry_changed', 'source_authenticated', 'all_application_invariants_verified']:
        need(value[key] is False, 'bounded claim ' + key)
    need(type(value['provider_requests_sent']) is int and value['provider_requests_sent'] == 0, 'no provider')
    need(value['sqlite_bookkeeping_may_create_sidecars'] is True, 'bookkeeping disclosure')
    need(b'REVIEW_PRIVATE_' not in raw, 'content not printed')
    return value


def run(binary, output):
    output.mkdir(parents=True, exist_ok=False)
    (output / 'raw').mkdir()
    (output / 'fixtures').mkdir()
    cases, calls = [], []
    error = None
    try:
        with tempfile.TemporaryDirectory(prefix='qbrain-review-deep-') as tmp:
            root = Path(tmp)
            home = root / 'isolated home 中'
            home.mkdir()
            env = {k: v for k, v in os.environ.items() if not k.upper().startswith(('QBRAIN', 'OPENAI', 'ANTHROPIC', 'GH_TOKEN', 'GITHUB_TOKEN'))}
            env.update(HOME=str(home), USERPROFILE=str(home), LOCALAPPDATA=str(home), APPDATA=str(home))
            def command(name, args, expected, wanted=None):
                p = subprocess.run([str(binary), *map(str, args)], input=b'', capture_output=True,
                                   cwd=root, env=env, timeout=40)
                n = len(calls)
                for ext, data in [('stdout', p.stdout), ('stderr', p.stderr)]:
                    (output / 'raw' / f'{n:03}.{ext}').write_bytes(data)
                calls.append(dict(name=name, args=list(map(str, args)), exit=p.returncode,
                                  expected_exit=expected, wanted=wanted,
                                  stdout_sha256=sha(p.stdout), stderr_sha256=sha(p.stderr)))
                need(p.returncode == expected and not p.stderr, name + ': ' + p.stdout.decode(errors='replace'))
                if wanted is not None:
                    need(str(root).encode() not in p.stdout, 'path not printed')
                return validate(p.stdout, expected, wanted or {}) if wanted is not None else None
            command('product-init', ['init', '--brain', 'review'], 0)
            base = (home if os.name == 'nt' else home / '.local/share') / 'Qbrain'
            original = base / 'brains/review/brain.db'
            registry = (base / 'config.json').read_bytes()
            with closing(sqlite3.connect(original)) as db:
                db.execute('PRAGMA journal_mode=DELETE')
                db.executemany('INSERT INTO pages(slug,title,body) VALUES(?,?,?)', [
                    ('REVIEW_PRIVATE_a', 'title words', 'one two three'),
                    ('REVIEW_PRIVATE_b', '中文 café', 'three two one'),
                    ('REVIEW_PRIVATE_c', 'title words', 'one one two')])
                db.commit()
                ddl = dict(db.execute("SELECT name,sql FROM sqlite_schema WHERE name IN ('pages_ai','pages_ad','pages_au','pages_fts','pages')"))
                page_indexes = [row[0] for row in db.execute("SELECT sql FROM sqlite_schema WHERE type='index' AND tbl_name='pages' AND sql IS NOT NULL")]
            au, ad, ai = ddl['pages_au'], ddl['pages_ad'], ddl['pages_ai']
            # Remove both the table UNIQUE constraint and standalone unique index
            # in this disposable fixture, then retain the same inventory names.
            duplicate = ('CREATE TABLE saved_pages AS SELECT * FROM pages;DROP TABLE pages;' +
                         ddl['pages'].replace('UNIQUE(source_id, slug),', '') + ';' +
                         'INSERT INTO pages SELECT * FROM saved_pages;DROP TABLE saved_pages;' +
                         ';'.join(x.replace('CREATE UNIQUE INDEX', 'CREATE INDEX') for x in page_indexes) + ';' +
                         ';'.join((ai, ad, au)) + ';' +
                         "INSERT INTO pages(slug,title,body) VALUES('REVIEW_PRIVATE_a','duplicate','duplicate');")
            fts = lambda equal: {'fts_content': 'PASS' if equal else 'FAIL'}
            matrix = [
                ('pristine', '', 0, {}, True),
                ('positions', "DROP TRIGGER pages_au;UPDATE pages SET body='three two one' WHERE slug='REVIEW_PRIVATE_a';" + au + ';', 1, fts(False), False),
                ('column-swap', "DROP TRIGGER pages_au;UPDATE pages SET title=body,body=title WHERE slug='REVIEW_PRIVATE_a';" + au + ';', 1, fts(False), False),
                ('rowid-change', "DROP TRIGGER pages_au;UPDATE pages SET id=100001 WHERE slug='REVIEW_PRIVATE_a';" + au + ';', 1, fts(False), False),
                ('deleted-row', "DROP TRIGGER pages_ad;DELETE FROM pages WHERE slug='REVIEW_PRIVATE_a';" + ad + ';', 1, fts(False), False),
                ('index-empty', "INSERT INTO pages_fts(pages_fts) VALUES('delete-all');", 1, fts(False), False),
                ('phantom-row', "INSERT INTO pages_fts(rowid,slug,title,body) VALUES(44444,'ghost','ghost','ghost');", 1, fts(False), False),
                ('normalized-equal', "DROP TRIGGER pages_au;UPDATE pages SET body=upper(body);" + au + ';', 0, fts(True), True),
                ('nul-unicode', "UPDATE pages SET body='中文 café '||char(0)||' after 😀';", 0, fts(True), True),
                ('soft-delete', "UPDATE pages SET deleted_at='2026-09-27';", 0, fts(True), True),
                ('empty', 'DELETE FROM pages;', 0, fts(True), True),
                ('other-source', "INSERT INTO sources(id) VALUES('review-other');INSERT INTO pages(source_id,slug,title,body) VALUES('review-other','REVIEW_PRIVATE_a','more','other source');", 0, fts(True), True),
                ('missing-au', 'DROP TRIGGER pages_au;', 1, {'fts_triggers': 'FAIL', 'fts_content': 'PASS'}, True),
                ('conditional-ai', 'DROP TRIGGER pages_ai;' + ai.replace('ON pages', 'ON pages WHEN 0') + ';', 1, {'fts_triggers': 'FAIL', 'fts_content': 'PASS'}, True),
                ('comment-format', 'DROP TRIGGER pages_au;' + au.replace('AFTER UPDATE', 'after /* allowed comment */ update').replace('ON pages', 'ON PAGES') + ';', 0, {'fts_triggers': 'PASS'}, True),
                ('literal-case', 'DROP TRIGGER pages_ad;' + ad.replace("'delete'", "'DELETE'") + ';', 1, {'fts_triggers': 'FAIL'}, True),
                ('alternate-content', "CREATE TABLE 'pa ges' AS SELECT * FROM pages;DROP TABLE pages_fts;" + ddl['pages_fts'].replace("content='pages'", "content='pa ges'") + ';', 1, {'fts_definition': 'FAIL', 'fts_content': 'NOT_RUN'}, None),
                ('fts-table-impostor', 'DROP TABLE pages_fts;CREATE TABLE pages_fts(slug TEXT,title TEXT,body TEXT);', 1, {'fts_definition': 'FAIL', 'fts_content': 'NOT_RUN'}, None),
                ('orphan-no-fk', "DROP TABLE tags;CREATE TABLE tags(page_id INTEGER,tag TEXT,PRIMARY KEY(page_id,tag));INSERT INTO tags VALUES(987654,'private');", 1, {'foreign_keys': 'PASS', 'page_relations': 'FAIL'}, True),
                ('duplicate-slug', duplicate, 1, {'core_inventory': 'PASS', 'page_relations': 'FAIL'}, True),
                ('missing-column', 'ALTER TABLE raw_data RENAME COLUMN key TO other_key;', 1, {'core_inventory': 'FAIL', 'page_relations': 'NOT_RUN', 'fts_content': 'NOT_RUN'}, True),
                ('unsupported-version', 'INSERT INTO schema_version(version) VALUES(14);', 1, {'core_inventory': 'FAIL', 'fts_content': 'NOT_RUN'}, True),
            ]
            for name, sql, expected, wanted, equal in matrix:
                path = output / 'fixtures' / (name + '.db')
                shutil.copyfile(original, path)
                with closing(sqlite3.connect(path)) as db:
                    db.executescript(sql)
                    db.commit()
                    need(db.execute('PRAGMA integrity_check').fetchall() == [('ok',)], name + ' structural control')
                image = path.read_bytes()
                oracle = tokens(path) if equal is not None else None
                if oracle is not None:
                    need(oracle['equal'] is equal, name + ' independent vocabulary/position control')
                report = command(name, ['database', 'check', '--database', path], expected, wanted)
                need(path.read_bytes() == image and not Path(str(path) + '-wal').exists(), name + ' offline DELETE DB unchanged')
                cases.append(dict(name=name, expected=expected, wanted=wanted, oracle=oracle,
                                  database_sha256=sha(image), report_sha256=sha(encoded(report))))
            need((base / 'config.json').read_bytes() == registry, 'registry untouched')
    except Exception as exc:
        error = type(exc).__name__ + ': ' + str(exc)
    report = dict(schema='qbrain-database-independent-review-v1', result='PASS' if error is None else 'FAIL',
                  error=error, binary_sha256=sha(binary.read_bytes()), reviewer_sha256=sha(Path(__file__).read_bytes()),
                  cases=cases, commands=calls)
    (output / 'RESULT.json').write_bytes(encoded(report))
    need(error is None, str(error))
    return dict(result='PASS', cases=len(cases), commands=len(calls))


def verify(binary, output):
    r = json.loads((output / 'RESULT.json').read_bytes())
    need(r['result'] == 'PASS' and r['error'] is None, 'completed')
    need(r['binary_sha256'] == sha(binary.read_bytes()), 'binary identity')
    need(r['reviewer_sha256'] == sha(Path(__file__).read_bytes()), 'reviewer identity')
    need(len(r['cases']) == 22 and len(r['commands']) == 23, 'complete fixed matrix')
    names = ['pristine','positions','column-swap','rowid-change','deleted-row','index-empty','phantom-row','normalized-equal','nul-unicode','soft-delete','empty','other-source','missing-au','conditional-ai','comment-format','literal-case','alternate-content','fts-table-impostor','orphan-no-fk','duplicate-slug','missing-column','unsupported-version']
    need([c['name'] for c in r['commands'][1:]] == names and [c['name'] for c in r['cases']] == names, 'exact ordered cases')
    need(r['commands'][0]['name'] == 'product-init' and r['commands'][0]['exit'] == 0, 'actual init')
    for i, c in enumerate(r['commands']):
        raw = (output / 'raw' / f'{i:03}.stdout').read_bytes()
        need(sha(raw) == c['stdout_sha256'], 'raw stdout identity')
        stderr = (output / 'raw' / f'{i:03}.stderr').read_bytes()
        need(not stderr and sha(stderr) == c['stderr_sha256'], 'raw stderr')
        need(c['exit'] == c['expected_exit'], 'exit')
        if i:
            item = r['cases'][i-1]
            value = validate(raw, item['expected'], item['wanted'])
            need(sha(encoded(value)) == item['report_sha256'], 'report content')
            db = output / 'fixtures' / (item['name'] + '.db')
            need(sha(db.read_bytes()) == item['database_sha256'], 'fixture identity')
            if item['oracle'] is not None:
                need(tokens(db) == item['oracle'], 'independent raw vocabulary replay')
    return dict(result='PASS', cases=len(r['cases']), commands=len(r['commands']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    print(json.dumps((verify if args.verify else run)(args.binary.resolve(), args.output.resolve()), sort_keys=True))
