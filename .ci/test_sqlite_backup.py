"""N48M native CLI backup/restore tests with an independent SQLite row oracle.

Only disposable synthetic brains are used. No imports from product/test helpers.
Every actual command preserves stdin/stdout/stderr and its expected exit. Python
-O keeps all require checks. Saved SQLite snapshots can be inspected independently.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time

CAP = 256 * 1024 * 1024


def encode(v):
    return (json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def sha(raw): return hashlib.sha256(raw).hexdigest()


def need(ok, name):
    if not ok: raise ValueError(name)


def decode(raw):
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, 'duplicate JSON key'); out[k] = v
        return out
    def reject(v): raise ValueError('nonfinite JSON')
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs, parse_constant=reject)


def rows(db_file):
    # Backup artifacts are sealed, rollback-journal files, never a live WAL copy.
    con = sqlite3.connect(db_file)
    try:
        need(con.execute('PRAGMA integrity_check').fetchall() == [('ok',)], 'sqlite integrity')
        need(not con.execute('PRAGMA foreign_key_check').fetchall(), 'sqlite foreign keys')
        schema = con.execute('SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name').fetchall()
        tables = {}
        for name, in con.execute("SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name"):
            query = 'SELECT * FROM "' + name.replace('"', '""') + '"'
            values = [[{'blob_hex': x.hex()} if isinstance(x, bytes) else x for x in r] for r in con.execute(query)]
            tables[name] = sorted(values, key=encode)
        return dict(schema=schema, tables=tables)
    finally: con.close()


def run(binary, output):
    output.mkdir(parents=True, exist_ok=False); (output/'raw').mkdir()
    checks, commands, skipped = [], [], []
    def check(ok, name):
        checks.append(dict(name=name, passed=bool(ok))); need(ok, name)
    failure = None
    try:
        with tempfile.TemporaryDirectory(prefix='qbrain-backup-review-') as tmp:
            root = Path(tmp)/"backup space 中 😀 '"; root.mkdir()
            home = root/'home'; home.mkdir()
            env = {k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
            env.update(HOME=str(home), USERPROFILE=str(home), LOCALAPPDATA=str(home), APPDATA=str(home))
            def call(name, args, body=None, expected=0, json_output=True):
                payload = b'' if body is None else encode(body)
                response = subprocess.run([str(binary), *map(str,args)], input=payload, capture_output=True, env=env, cwd=root, timeout=30)
                index = len(commands); hashes = {}
                for ext, data in [('stdin',payload),('stdout',response.stdout),('stderr',response.stderr)]:
                    (output/'raw'/f'{index:03}.{ext}').write_bytes(data); hashes[ext] = sha(data)
                commands.append(dict(name=name, argv=list(map(str,args)), exit=response.returncode, expected_exit=expected, hashes=hashes))
                need(response.returncode == expected, name+' exit: '+response.stdout.decode(errors='replace')[:300])
                need(not response.stderr, name+' stderr')
                return decode(response.stdout) if json_output else response.stdout
            call('init', ['init','--brain','source'], json_output=False)
            def cli(name, args, body=None, brain='source'):
                return call(name,[*args,'--brain',brain],body)
            event = cli('capture',['memory','capture','--manual'],dict(session_id='before-backup',fragment_id='quote',messages=[dict(role='user',content='I prefer keeping synthetic backup receipt revisions intact.')]))
            cli('extract',['memory','extract','--event',event['event_id']])
            items = cli('memory-read',['memory','read'])['items']
            item = next(i for i in items if i['event_id'] == event['event_id'])
            fact = cli('fact-create',['fact','create'],dict(predicate='backup.preference',item_id=item['item_id']))
            fid, rev = fact['fact_id'], fact['revision']
            for uid in ('1'*64,'2'*64): cli('report-use-'+uid[0],['fact','report-use'],dict(fact_id=fid,usage_id=uid,expected_revision=rev))
            cli('revoke-use',['fact','revoke-use'],dict(fact_id=fid,usage_id='2'*64))
            before_fact = cli('fact-before',['fact','read','--id',fid])
            before_usage = cli('usage-before',['fact','usage-list','--id',fid,'--state','all','--limit','50'])
            check(len(before_usage['items']) == 2, 'active and withdrawn receipts exist before backup')
            data_root = home if os.name == 'nt' else home/'.local/share'
            qroot = data_root/'Qbrain'; source = qroot/'brains/source/brain.db'
            registry = (qroot/'config.json').read_bytes()
            # Keep a second SQLite writer alive; committed rows deliberately stay in WAL.
            writer = sqlite3.connect(source, isolation_level=None)
            writer.execute('PRAGMA journal_mode=WAL'); writer.execute('PRAGMA wal_autocheckpoint=0')
            writer.execute('CREATE TABLE n48m_blob(id INTEGER PRIMARY KEY, payload BLOB, generation INTEGER)')
            writer.execute('INSERT INTO n48m_blob VALUES(1,?,7)', (b'\x00\xff\x00PRIVATE_TEST_ONLY',))
            expected_rows = rows(source)
            before_db = source.read_bytes(); before_wal = Path(str(source)+'-wal').read_bytes()
            check(len(before_wal) > 0, 'real committed WAL frames present')
            writer.execute('BEGIN IMMEDIATE'); writer.execute('INSERT INTO n48m_blob VALUES(2,?,99)', (b'uncommitted',))
            backup = root/'backup'
            created = call('create', ['backup','create','--database',source,'--output',backup])
            digest = created['manifest_sha256']
            check(created['result'] == 'CREATED', 'backup created')
            check(source.read_bytes() == before_db and Path(str(source)+'-wal').read_bytes() == before_wal, 'source main and WAL byte preservation')
            writer.execute('ROLLBACK'); writer.close()
            check(set(p.name for p in backup.iterdir()) == {'snapshot.sqlite3','manifest.json'}, 'self-contained two-file inventory')
            check(sha((backup/'manifest.json').read_bytes()) == digest, 'external manifest SHA matches actual bytes')
            check(sha((backup/'snapshot.sqlite3').read_bytes()) == created['database_sha256'], 'database SHA matches actual bytes')
            check(encode(rows(backup/'snapshot.sqlite3')) == encode(expected_rows), 'all SQLite schema and row values match including WAL, BLOB, receipts')
            (output/'expected-rows.json').write_bytes(encode(expected_rows))
            shutil.copytree(backup,output/'snapshot')
            original = {p.name:p.read_bytes() for p in backup.iterdir()}
            verified = call('verify', ['backup','verify','--backup',backup,'--expect-sha256',digest])
            check(verified['result'] == 'VERIFIED' and original == {p.name:p.read_bytes() for p in backup.iterdir()}, 'verify leaves both files unchanged')
            recovered = qroot/'brains/recovered'
            call('restore', ['backup','restore','--backup',backup,'--expect-sha256',digest,'--output',recovered])
            check((recovered/'brain.db').read_bytes() == original['snapshot.sqlite3'], 'restored file byte-exact before opening app')
            check(encode(rows(recovered/'brain.db')) == encode(expected_rows), 'independent restored SQL rows all exact')
            shutil.copyfile(recovered/'brain.db',output/'restored.db')
            check((qroot/'config.json').read_bytes() == registry, 'restore never changes default registry')
            after_fact = cli('fact-after',['fact','read','--id',fid],brain='recovered')
            after_usage = cli('usage-after',['fact','usage-list','--id',fid,'--state','all','--limit','50'],brain='recovered')
            check(encode(after_fact) == encode(before_fact), 'actual Qbrain restored fact identical')
            check(encode(after_usage) == encode(before_usage), 'actual Qbrain active and revoked receipt timestamps/revisions identical')
            (output/'receipt-comparison.json').write_bytes(encode(dict(before=before_usage,after=after_usage)))
            cli('duplicate-restored',['fact','report-use'],dict(fact_id=fid,usage_id='1'*64,expected_revision=rev),brain='recovered')
            duplicate = cli('usage-after-duplicate',['fact','usage-list','--id',fid,'--state','all','--limit','50'],brain='recovered')
            check(encode(duplicate) == encode(before_usage), 'restored existing receipt remains idempotent')
            def reject(name, args, code=None):
                value = call(name,['backup',*args],expected=2)
                check(set(value) == {'error'} and set(value['error']) == {'code'}, name+' structured-only error')
                check(code is None or value['error']['code'] == code, name+' correct rejection')
                check(str(root).encode() not in encode(value) and b'PRIVATE' not in encode(value), name+' no path/body leak')
            reject('existing-backup',['create','--database',source,'--output',backup],'backup_output_exists')
            reject('existing-restore',['restore','--backup',backup,'--expect-sha256',digest,'--output',recovered],'backup_output_exists')
            reject('restore-inside',['restore','--backup',backup,'--expect-sha256',digest,'--output',backup/'inside'],'backup_output_inside_source')
            reject('wrong-digest',['verify','--backup',backup,'--expect-sha256','a'*64],'backup_manifest_digest')
            reject('missing-digest',['verify','--backup',backup],'backup_arguments')
            reject('unknown-option',['create','--database',source,'--output',root/'no','--overwrite','yes'],'backup_arguments')
            reject('duplicate-option',['create','--database',source,'--database',source,'--output',root/'no'],'backup_arguments')
            reject('missing-option-value',['create','--database'],'backup_arguments')
            reject('invalid-time',['create','--database',source,'--output',root/'no','--timeout-ms','1'],'backup_timeout_range')
            reject('not-exist',['create','--database',root/'missing.db','--output',root/'no'])
            reject('parent-traversal',['create','--database',root/'home/../home','--output',root/'no'],'backup_parent_path')
            huge = root/'huge';
            with huge.open('wb') as stream: stream.truncate(CAP+1)
            reject('database-cap',['create','--database',huge,'--output',root/'no'],'backup_size_limit')
            huge.unlink()
            # Tampering must fail even after editing the self-contained manifest;
            # a changed external trusted digest is a different trust decision.
            for mutation in ('byte','extra','missing','duplicate-json','bool-size','path','scope','sha','sidecar','bad-sqlite'):
                target = root/('tamper-'+mutation); shutil.copytree(backup,target)
                m = decode((target/'manifest.json').read_bytes()); expected = digest
                if mutation == 'byte':
                    image=bytearray((target/'snapshot.sqlite3').read_bytes());image[-1]^=1;(target/'snapshot.sqlite3').write_bytes(image)
                elif mutation == 'extra': (target/'extra').write_bytes(b'ignored?')
                elif mutation == 'missing': (target/'snapshot.sqlite3').unlink()
                elif mutation == 'duplicate-json':
                    raw=b'{"schema":"bad",'+(target/'manifest.json').read_bytes()[1:];(target/'manifest.json').write_bytes(raw);expected=sha(raw)
                elif mutation == 'sidecar': (target/'snapshot.sqlite3-wal').write_bytes(b'')
                elif mutation == 'bad-sqlite':
                    image=bytearray((target/'snapshot.sqlite3').read_bytes());image[:16]=b'not a database!!';(target/'snapshot.sqlite3').write_bytes(image)
                    m['database_sha256']=sha(image);(target/'manifest.json').write_bytes(encode(m));expected=sha(encode(m))
                else:
                    key,value={'bool-size':('database_bytes',True),'path':('database','../../brain.db'),'scope':('scope','full_brain'),'sha':('database_sha256','f'*64)}[mutation]
                    m[key]=value;(target/'manifest.json').write_bytes(encode(m));expected=sha(encode(m))
                reject('tamper-'+mutation,['restore','--backup',target,'--expect-sha256',expected,'--output',root/('reject-'+mutation)])
                check(not (root/('reject-'+mutation)).exists(), mutation+' rejected before restore directory creation')
            # Read locks and source transaction consistency, not automatic operation retries.
            with closing(sqlite3.connect(source,isolation_level=None)) as locked:
                locked.execute('PRAGMA journal_mode=DELETE'); locked.execute('BEGIN EXCLUSIVE')
                start=time.monotonic()
                reject('busy-lock',['create','--database',source,'--output',root/'locked-out','--timeout-ms','100'],'backup_timeout')
                check(time.monotonic()-start < 5, 'bounded busy rejection')
                locked.execute('ROLLBACK')
            stop=threading.Event(); ready=threading.Event(); state={'commits':0,'failure':None}
            def update():
                try:
                    con=sqlite3.connect(source,isolation_level=None,timeout=5);con.execute('PRAGMA journal_mode=WAL');con.execute('PRAGMA wal_autocheckpoint=0')
                    con.execute('CREATE TABLE concurrent_a(n INTEGER)');con.execute('INSERT INTO concurrent_a VALUES(0)')
                    con.execute('CREATE TABLE concurrent_b(n INTEGER)');con.execute('INSERT INTO concurrent_b VALUES(0)')
                    ready.set()
                    while not stop.is_set():
                        con.execute('BEGIN IMMEDIATE');con.execute('UPDATE concurrent_a SET n=n+1');con.execute('UPDATE concurrent_b SET n=n+1');con.execute('COMMIT');state['commits']+=1
                        time.sleep(.001)
                    con.close()
                except Exception as e: state['failure']=type(e).__name__;ready.set()
            thread=threading.Thread(target=update);thread.start();need(ready.wait(5),'writer readiness')
            try:
                for i in range(3):
                    folder=root/f'concurrent-{i}'
                    r=call(f'concurrent-{i}',['backup','create','--database',source,'--output',folder])
                    with closing(sqlite3.connect(folder/'snapshot.sqlite3')) as con:
                        a=con.execute('SELECT n FROM concurrent_a').fetchone()[0];b=con.execute('SELECT n FROM concurrent_b').fetchone()[0]
                    check(a==b,'concurrent snapshot preserves transaction boundary '+str(i))
            finally: stop.set();thread.join(10)
            check(state['failure'] is None and state['commits']>0 and not thread.is_alive(),'concurrent writer actually committed and stopped')
            # Hard links are supported on both native test platforms.
            hard=root/'hard.db';os.link(source,hard)
            try: reject('hardlink',['create','--database',hard,'--output',root/'hard-out'],'backup_hard_link')
            finally: hard.unlink()
            link=root/'symbolic.db'
            try: link.symlink_to(source)
            except OSError: skipped.append('symlink creation unavailable on runner')
            else:
                reject('symlink',['create','--database',link,'--output',root/'sym-out'],'backup_link_or_missing');link.unlink()
            if os.name == 'nt':
                reject('alternate-stream',['create','--database',str(source)+':stream','--output',root/'ads-out'],'backup_path')
                reject('unc',['create','--database',r'\\localhost\share\brain.db','--output',root/'unc-out'],'backup_path')
            check((qroot/'config.json').read_bytes()==registry,'all administrative commands preserve registry')
    except Exception as e:
        failure=type(e).__name__+': '+str(e)
    report=dict(schema='qbrain-sqlite-backup-process-v1', binary_sha256=sha(binary.read_bytes()),
                test_sha256=sha(Path(__file__).read_bytes()), platform=os.name, optimized=not __debug__,
                passed=failure is None, checks=checks, commands=commands, skipped=skipped, failure=failure,
                synthetic_only=True, application_backup_scope='database_only_all_sources')
    (output/'report.json').write_bytes(encode(report))
    need(failure is None,failure or 'failed')
    return report


def verify(binary, output):
    report=decode((output/'report.json').read_bytes())
    need(report['binary_sha256']==sha(binary.read_bytes()),'binary identity')
    need(report['test_sha256']==sha(Path(__file__).read_bytes()),'test identity')
    need(report['passed'] is True and report['failure'] is None,'run passed')
    need(report['synthetic_only'] is True,'scope')
    need(all(c['passed'] is True for c in report['checks']),'check failure')
    need(len(report['commands'])>=40 and len(report['checks'])>=80,'minimum inventory')
    expected={f'{i:03}.{s}' for i in range(len(report['commands'])) for s in ('stdin','stdout','stderr')}
    need({p.name for p in (output/'raw').iterdir()}==expected,'raw inventory')
    for i,row in enumerate(report['commands']):
        need(type(row['exit']) is int and type(row['expected_exit']) is int and row['exit']==row['expected_exit'],'command exit')
        for ext,h in row['hashes'].items(): need(sha((output/'raw'/f'{i:03}.{ext}').read_bytes())==h,'raw digest')
        need((output/'raw'/f'{i:03}.stderr').stat().st_size==0,'stderr not empty')
    expected_rows=(output/'expected-rows.json').read_bytes()
    need(encode(rows(output/'snapshot/snapshot.sqlite3'))==expected_rows,'snapshot rows')
    need(encode(rows(output/'restored.db'))==expected_rows,'restored rows')
    receipts=decode((output/'receipt-comparison.json').read_bytes())
    need(encode(receipts['before'])==encode(receipts['after']),'receipt restoration')
    return dict(passed=True,commands=len(report['commands']),checks=len(report['checks']),skipped=report['skipped'],
                new_native_execution=False,source_authenticated=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--verify',action='store_true')
    a=p.parse_args()
    try:
        r=verify(a.binary.resolve(strict=True),a.output) if a.verify else run(a.binary.resolve(strict=True),a.output)
        print(json.dumps({k:v for k,v in r.items() if k not in ('commands','checks')}))
    except Exception as e:
        print(json.dumps(dict(error=type(e).__name__,detail=str(e))));raise SystemExit(1)
