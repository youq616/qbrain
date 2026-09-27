"""Separate N48N black-box oracle: rebuilt token/position index, not integrity-check.
Does not import product tests, reuse their fixtures, or write to any real brain.
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


def digest(raw): return hashlib.sha256(raw).hexdigest()
def encoded(obj): return (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()
def require(ok, message):
    if not ok: raise RuntimeError(message)

FTS = "CREATE VIRTUAL TABLE pages_fts USING fts5(slug,title,body,content='pages',content_rowid='id',tokenize='unicode61')"
AI = 'CREATE TRIGGER pages_ai AFTER INSERT ON pages BEGIN INSERT INTO pages_fts(rowid,slug,title,body) VALUES(new.id,new.slug,new.title,new.body); END'
AD = "CREATE TRIGGER pages_ad AFTER DELETE ON pages BEGIN INSERT INTO pages_fts(pages_fts,rowid,slug,title,body) VALUES('delete',old.id,old.slug,old.title,old.body); END"
AU = "CREATE TRIGGER pages_au AFTER UPDATE ON pages BEGIN INSERT INTO pages_fts(pages_fts,rowid,slug,title,body) VALUES('delete',old.id,old.slug,old.title,old.body); INSERT INTO pages_fts(rowid,slug,title,body) VALUES(new.id,new.slug,new.title,new.body); END"


def token_oracle(image):
    # Exact term, document, column and position tuples, not row counts. All work in RAM.
    with closing(sqlite3.connect(':memory:')) as actual, closing(sqlite3.connect(':memory:')) as reference:
        actual.deserialize(image)
        rows = actual.execute('SELECT id,slug,title,body FROM pages').fetchall()
        reference.execute('CREATE VIRTUAL TABLE expected USING fts5(slug,title,body,tokenize="unicode61")')
        reference.executemany('INSERT INTO expected(rowid,slug,title,body) VALUES(?,?,?,?)', rows)
        actual.execute("CREATE VIRTUAL TABLE temp.av USING fts5vocab(main,pages_fts,instance)")
        reference.execute("CREATE VIRTUAL TABLE temp.ev USING fts5vocab(main,expected,instance)")
        left = actual.execute('SELECT term,doc,col,offset FROM av ORDER BY term,doc,col,offset').fetchall()
        right = reference.execute('SELECT term,doc,col,offset FROM ev ORDER BY term,doc,col,offset').fetchall()
        return left == right, len(left), len(right)


def run(binary, out):
    out.mkdir(parents=True, exist_ok=False)
    results, commands = [], []
    error = None
    try:
        with tempfile.TemporaryDirectory(prefix='qbrain-independent-search-') as tmp:
            home = Path(tmp)
            env = {k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
            env.update(HOME=tmp, USERPROFILE=tmp, LOCALAPPDATA=tmp, APPDATA=tmp)
            matrix = [
                ('canonical', '', True, 'PASS'),
                ('positions', "DROP TRIGGER pages_au; UPDATE pages SET body='three two one' WHERE id=1;" + AU + ';', False, 'FAIL'),
                ('columns', "DROP TRIGGER pages_au; UPDATE pages SET title=body,body=title WHERE id=1;" + AU + ';', False, 'FAIL'),
                ('document-id', "DROP TRIGGER pages_au; UPDATE pages SET id=17 WHERE id=1;" + AU + ';', False, 'FAIL'),
                ('deleted-content', 'DROP TRIGGER pages_ad; DELETE FROM pages WHERE id=1;' + AD + ';', False, 'FAIL'),
                ('no-index', "INSERT INTO pages_fts(pages_fts) VALUES('delete-all');", False, 'FAIL'),
                ('phantom', "INSERT INTO pages_fts(rowid,slug,title,body) VALUES(123,'phantom','phantom','phantom');", False, 'FAIL'),
                ('missing-update', 'DROP TRIGGER pages_au;', True, 'FAIL'),
                ('missing-all', 'DROP TRIGGER pages_ai; DROP TRIGGER pages_ad; DROP TRIGGER pages_au;', True, 'FAIL'),
                ('conditional-trigger', 'DROP TRIGGER pages_ai; CREATE TRIGGER pages_ai AFTER INSERT ON pages WHEN 0 BEGIN INSERT INTO pages_fts(rowid,slug,title,body) VALUES(new.id,new.slug,new.title,new.body); END;', True, 'FAIL'),
                ('uppercase-extra', 'CREATE TRIGGER surprise AFTER UPDATE ON PAGES BEGIN SELECT 1; END;', True, 'FAIL'),
                ('empty', 'DELETE FROM pages;', True, 'PASS'),
                ('nul', "UPDATE pages SET body='one'||char(0)||'two';", True, 'PASS'),
                ('soft-delete', "UPDATE pages SET deleted_at='2026-09-27';", True, 'PASS'),
            ]
            for index, (name, mutation, expected_equal, verdict) in enumerate(matrix):
                file = home / (name + '.db')
                with closing(sqlite3.connect(file)) as db:
                    db.executescript("CREATE TABLE schema_version(version INTEGER PRIMARY KEY);INSERT INTO schema_version VALUES(1);CREATE TABLE sources(id TEXT PRIMARY KEY);INSERT INTO sources VALUES('default');CREATE TABLE pages(id INTEGER PRIMARY KEY,slug TEXT,title TEXT,body TEXT,source_id TEXT DEFAULT 'default',deleted_at TEXT);" + ';'.join((FTS, AI, AD, AU)) + ';')
                    db.executemany('INSERT INTO pages(id,slug,title,body) VALUES(?,?,?,?)', [(1,'private-first','title words','one two three'),(19,'private-second','中文 café','three two one'),(90000000,'private-third','title words','one one two')])
                    db.commit()
                    db.executescript(mutation)
                    db.commit()
                    require(db.execute('PRAGMA integrity_check').fetchall() == [('ok',)], name + ' structurally valid')
                image = file.read_bytes()
                equal, actual_n, reference_n = token_oracle(image)
                require(equal is expected_equal, name + ' independent oracle fixture')
                folder = out / name
                folder.mkdir()
                (folder / 'snapshot.sqlite3').write_bytes(image)
                manifest = {'schema':'qbrain-sqlite-backup-v1','engine':'sqlite','database':'snapshot.sqlite3','database_bytes':len(image),'database_sha256':digest(image),'qbrain_schema_version':1,'scope':'database_only_all_sources','encrypted':False,'sqlite_integrity_checked':True,'foreign_keys_checked':True,'source_authenticated':False}
                raw_manifest = encoded(manifest)
                (folder / 'manifest.json').write_bytes(raw_manifest)
                pin = digest(raw_manifest)
                reports = {}
                for action, expected in [('verify',0),('audit-search',0 if verdict == 'PASS' else 1)]:
                    p = subprocess.run([str(binary),'backup',action,'--backup',str(folder),'--expect-sha256',pin],input=b'',capture_output=True,env=env,cwd=home,timeout=30)
                    (folder / (action + '.stdout')).write_bytes(p.stdout)
                    (folder / (action + '.stderr')).write_bytes(p.stderr)
                    commands.append({'case':name,'action':action,'exit':p.returncode,'expected_exit':expected,'stdout_sha256':digest(p.stdout),'stderr_sha256':digest(p.stderr)})
                    require(p.returncode == expected and not p.stderr, name + ' native outcome: ' + p.stdout.decode(errors='replace'))
                    reports[action] = json.loads(p.stdout)
                    # Remove raw artifacts during the next command: backup inventory is EXACTLY two files.
                    (folder / (action + '.stdout')).rename(out / f'{index:02}-{action}.stdout')
                    (folder / (action + '.stderr')).rename(out / f'{index:02}-{action}.stderr')
                r = reports['audit-search']
                require(reports['verify']['result'] == 'VERIFIED', 'original verify')
                require(r['result'] == verdict and r['fts_content_consistent'] is expected_equal, name + ' oracle versus audit')
                require(r['application_semantics_verified'] is False and r['input_modified'] is False and r['repair_performed'] is False, name + ' no enlarged claims')
                require(r['database_sha256'] == digest(image) and r['manifest_sha256'] == pin, name + ' binding')
                require(b'private-' not in encoded(r) and str(home).encode() not in encoded(r), name + ' privacy')
                require((folder/'snapshot.sqlite3').read_bytes() == image and (folder/'manifest.json').read_bytes() == raw_manifest, name + ' input preservation')
                results.append({'case':name,'verdict':verdict,'tokens_equal':equal,'actual_token_positions':actual_n,'reference_token_positions':reference_n,'pin':pin})
    except Exception as exc:
        error = type(exc).__name__ + ': ' + str(exc)
    report = {'schema':'qbrain-search-audit-independent-v1','binary_sha256':digest(binary.read_bytes()),'reviewer_sha256':digest(Path(__file__).read_bytes()),'cases':results,'commands':commands,'error':error,'result':'PASS' if error is None else 'FAIL'}
    (out/'report.json').write_bytes(encoded(report))
    require(error is None, str(error))
    return {'result':'PASS','cases':len(results),'commands':len(commands)}


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--binary',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(run(args.binary.resolve(),args.output.resolve()),sort_keys=True))
