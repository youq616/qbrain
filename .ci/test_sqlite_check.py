"""N48N actual CLI qualification; synthetic fixtures only, stdlib SQLite oracle.
Python -O retains every explicit requirement. Never import the product or old tests.
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
import threading
import time

IDS = ['sqlite_integrity','foreign_keys','core_inventory','page_relations','fts_definition','fts_triggers','fts_content']
CAP = 256*1024*1024

def need(ok, label):
    if not ok: raise ValueError(label)

def sha(data): return hashlib.sha256(data).hexdigest()

def encode(value): return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def decode(raw):
    def pairs(items):
        out = {}
        for key,value in items:
            need(key not in out,'duplicate key'); out[key] = value
        return out
    def reject(x): raise ValueError('nonfinite JSON')
    return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=reject)

def validate(value, expected, failed):
    required = {'schema','result','scope','snapshot','source_open_mode','source_repaired','registry_changed','provider_requests_sent','all_application_invariants_verified','source_authenticated','sqlite_bookkeeping_may_create_sidecars','checks'}
    need(required <= set(value) <= required|{'snapshot_bytes','error'},'report keys')
    need(value['schema']=='qbrain-database-check-v1','schema')
    need(value['scope']=='sqlite_storage_and_pages_fts','scope')
    need(value['snapshot']=='private_memory_committed_transaction','snapshot')
    need(value['source_open_mode']=='read_only','readonly')
    need(value['sqlite_bookkeeping_may_create_sidecars'] is True,'SQLite bookkeeping disclosed')
    for key in ['source_repaired','registry_changed','all_application_invariants_verified','source_authenticated']:
        need(value[key] is False,'false flag '+key)
    need(type(value['provider_requests_sent']) is int and value['provider_requests_sent']==0,'no provider')
    need([c['id'] for c in value['checks']]==IDS,'ordered check IDs')
    for c in value['checks']:
        need(set(c)=={'id','status','issues'} and c['status'] in ['PASS','FAIL','NOT_RUN'],'check shape')
        need(type(c['issues']) is list and all(type(i) is str for i in c['issues']),'issues')
        need(bool(c['issues'])==(c['status']=='FAIL'),'findings not erased')
    if 'snapshot_bytes' in value:
        need(type(value['snapshot_bytes']) is int and 0<value['snapshot_bytes']<=CAP,'snapshot size')
    wanted = ['CHECK_PASSED','CHECK_FAILED','ERROR'][expected]
    need(value['result']==wanted,'expected result '+wanted)
    if expected==0:
        need(all(c['status']=='PASS' for c in value['checks']) and 'error' not in value,'no skipped success')
    elif expected==1:
        need(any(c['status']=='FAIL' for c in value['checks']) and 'error' not in value,'failed result')
    else:
        need(type(value.get('error')) is dict and type(value['error'].get('code')) is str,'error shape')
        need(value['error']['code'].startswith('database_'),'stable error code')
    statuses={c['id']:c['status'] for c in value['checks']}
    for key,status in failed.items(): need(statuses[key]==status,'expected '+key+' '+status)

def file_state(path):
    return {suffix:sha(Path(str(path)+suffix).read_bytes()) for suffix in ['', '-wal'] if Path(str(path)+suffix).is_file()}

def source_preserved(before,after):
    # SQLite READONLY on an offline WAL database may create an EMPTY WAL plus SHM.
    # Existing main/WAL content must be identical; new nonempty WAL is never allowed.
    return all(after.get(k)==v for k,v in before.items()) and all(k in before or (k=='-wal' and v==sha(b'')) for k,v in after.items())

def run(binary,output):
    output.mkdir(parents=True,exist_ok=False); (output/'raw').mkdir(); (output/'fixtures').mkdir()
    commands=[]; checks=[]; skipped=[]; failure=None
    def check(ok,label):
        checks.append({'name':label,'passed':bool(ok)}); need(ok,label)
    try:
        with tempfile.TemporaryDirectory(prefix='qbrain-database-test-') as tmp:
            root=Path(tmp)/"space 中 😀 '";root.mkdir()
            home=root/'home';home.mkdir()
            env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
            env.update(HOME=str(home),USERPROFILE=str(home),LOCALAPPDATA=str(home),APPDATA=str(home))
            def call(name,args,expected=0,statuses=None,is_report=True,check_path=None):
                old=file_state(check_path) if check_path else None
                result=subprocess.run([str(binary),*map(str,args)],capture_output=True,input=b'',cwd=root,env=env,timeout=35)
                index=len(commands);hashes={}
                for ext,data in [('stdin',b''),('stdout',result.stdout),('stderr',result.stderr)]:
                    (output/'raw'/f'{index:03}.{ext}').write_bytes(data);hashes[ext]=sha(data)
                entry=dict(name=name,args=list(map(str,args)),expected_exit=expected,exit=result.returncode,hashes=hashes,is_report=is_report,expected_statuses=statuses or {})
                if check_path:
                    entry['source_before']=old;entry['source_after']=file_state(check_path)
                commands.append(entry)
                check(result.returncode==expected,name+' exit '+str(result.returncode)+': '+result.stdout.decode(errors='replace')[:240])
                check(not result.stderr,name+' empty stderr')
                if check_path: check(source_preserved(entry['source_before'],entry['source_after']),name+' existing main/WAL preserved; only empty new WAL permitted')
                if is_report:
                    value=decode(result.stdout); validate(value,expected,statuses or {})
                    check(not any(s in result.stdout for s in [b'PRIVATE_BODY_SENTINEL',b'SECRET_ENV_SENTINEL',str(root).encode()]),name+' privacy')
                    return value
                return result.stdout
            call('actual-init',['init','--brain','health'],is_report=False)
            data=home if os.name=='nt' else home/'.local/share'
            live=data/'Qbrain/brains/health/brain.db'
            check(live.is_file(),'real product database exists')
            with closing(sqlite3.connect(live)) as con:
                con.execute("INSERT INTO sources(id,name) VALUES('other','Synthetic')")
                con.execute("INSERT INTO pages(source_id,slug,title,body) VALUES('default','same-slug','Title','PRIVATE_BODY_SENTINEL originalindexedtoken')")
                con.execute("INSERT INTO pages(source_id,slug,title,body) VALUES('other','same-slug','其他','正文 中文 é 😀')")
                con.commit()
                with closing(sqlite3.connect(output/'fixtures/pristine.db')) as dest: con.backup(dest)
            pristine=output/'fixtures/pristine.db'
            registry=(data/'Qbrain/config.json').read_bytes()
            env.update(QBRAIN_PG_DSN='postgresql://SECRET_ENV_SENTINEL@invalid.invalid/no',OPENAI_API_KEY='SECRET_ENV_SENTINEL')
            def inspect(name,path,expected=0,statuses=None,timeout=None):
                args=['database','check','--database',path]
                if timeout is not None:args+=['--timeout-ms',str(timeout)]
                return call(name,args,expected,statuses,check_path=path)
            inspect('healthy-actual-product',live)
            def variant(name,sql):
                path=output/'fixtures'/f'{name}.db';shutil.copyfile(pristine,path)
                with closing(sqlite3.connect(path)) as con:con.executescript(sql)
                return path
            # Canonical triggers are restored after corruption: presence alone cannot detect drift.
            with closing(sqlite3.connect(pristine)) as con:
                trigger=con.execute("SELECT sql FROM sqlite_schema WHERE name='pages_au'").fetchone()[0]
            stale=variant('stale-index',"DROP TRIGGER pages_au;UPDATE pages SET body='differentcurrenttoken' WHERE source_id='default';"+trigger+';')
            with closing(sqlite3.connect(stale)) as con:
                check(con.execute('PRAGMA integrity_check').fetchall()==[('ok',)],'independent structural false-negative control')
                check(con.execute("SELECT count(*) FROM pages_fts WHERE pages_fts MATCH 'differentcurrenttoken'").fetchone()[0]==0,'independent missing retrieval')
            inspect('stale-with-canonical-triggers',stale,1,dict(sqlite_integrity='PASS',fts_triggers='PASS',fts_content='FAIL'))
            for name in ['pages_ai','pages_ad','pages_au']:
                path=variant('missing-'+name,'DROP TRIGGER '+name+';')
                inspect('missing-'+name,path,1,dict(fts_triggers='FAIL',fts_content='PASS'))
            path=variant('wrong-trigger',"DROP TRIGGER pages_ai;CREATE TRIGGER pages_ai AFTER INSERT ON pages BEGIN SELECT 1;END;")
            inspect('wrong-trigger-body',path,1,dict(fts_triggers='FAIL'))
            path=variant('fake-fts',"DROP TABLE pages_fts;CREATE TABLE pages_fts(pages_fts TEXT,rank INTEGER);")
            inspect('ordinary-table-impersonation',path,1,dict(fts_definition='FAIL',fts_content='NOT_RUN'))
            path=variant('wrong-tokenizer',"DROP TABLE pages_fts;CREATE VIRTUAL TABLE pages_fts USING fts5(slug,title,body,content='pages',content_rowid='id',tokenize='porter');INSERT INTO pages_fts(pages_fts) VALUES('rebuild');")
            inspect('unsupported-tokenizer',path,1,dict(fts_definition='FAIL',fts_content='NOT_RUN'))
            path=variant('fk',"PRAGMA foreign_keys=OFF;UPDATE pages SET source_id='absent' WHERE source_id='default';")
            inspect('foreign-key-orphan',path,1,dict(foreign_keys='FAIL',page_relations='FAIL'))
            path=variant('no-fk-orphan',"DROP TABLE tags;CREATE TABLE tags(page_id INTEGER,tag TEXT,PRIMARY KEY(page_id,tag));INSERT INTO tags VALUES(99999,'private');")
            inspect('orphan-without-fk-declaration',path,1,dict(foreign_keys='PASS',page_relations='FAIL'))
            for name,sql in [('missing-index','DROP INDEX idx_pages_type;'),('missing-table','DROP TABLE takes;'),('old-version','DELETE FROM schema_version WHERE version=13;'),('new-version','INSERT INTO schema_version(version) VALUES(14);'),('bad-version',"DROP TABLE schema_version;CREATE TABLE schema_version(version);INSERT INTO schema_version VALUES('future');")]:
                path=variant(name,sql);inspect(name,path,1,dict(core_inventory='FAIL',fts_content='NOT_RUN'))
            path=variant('blank-text',"INSERT INTO pages(source_id,slug,title,body) VALUES('default','blank','','');")
            inspect('empty-indexed-text',path)
            path=variant('extra-blob','CREATE TABLE extra_blob(payload BLOB);INSERT INTO extra_blob VALUES(zeroblob(17825792));')
            inspect('17MiB-BLOB',path)
            # Regenerate the real product schema in a fresh file so encoding is genuinely changed.
            with closing(sqlite3.connect(pristine)) as con:
                definitions=con.execute("SELECT type,name,sql FROM sqlite_schema WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 ELSE 2 END,name").fetchall()
            for size in [512,4096,8192,65536]:
                for encoding in ['UTF-8','UTF-16']:
                    path=output/'fixtures'/f'layout-{size}-{encoding}.db'
                    with closing(sqlite3.connect(path)) as con:
                        con.execute(f'PRAGMA page_size={size}');con.execute(f"PRAGMA encoding='{encoding}'")
                        for kind,name,sql in definitions:
                            if name.startswith('pages_fts_'): continue
                            con.execute(sql)
                        con.execute('INSERT INTO schema_version(version) VALUES(13)')
                        con.execute("INSERT INTO sources(id,name) VALUES('default','Synthetic')")
                        con.execute("INSERT INTO pages(source_id,slug,title,body) VALUES('default','layout','测试','é 中文 😀 originalindexedtoken')")
                        con.commit()
                        check(con.execute('PRAGMA page_size').fetchone()[0]==size,'actual page size '+str(size))
                        check(con.execute('PRAGMA encoding').fetchone()[0].startswith(encoding),'actual encoding '+encoding)
                    inspect(f'layout-{size}-{encoding}',path)
            # WAL source remains open; no raw live-WAL file is copied by the test.
            path=variant('wal','PRAGMA journal_mode=WAL;')
            with closing(sqlite3.connect(path)) as con:
                con.execute('PRAGMA journal_mode=WAL');con.execute('PRAGMA wal_autocheckpoint=0')
                con.execute("INSERT INTO pages(source_id,slug,title,body) VALUES('default','wal','committed','walcommitted')");con.commit()
                check(Path(str(path)+'-wal').stat().st_size>0,'actual committed WAL')
                con.execute('BEGIN IMMEDIATE');con.execute('DROP TRIGGER pages_au');con.execute("UPDATE pages SET body='uncommittedstale'")
                inspect('WAL-uncommitted-excluded',path)
                con.rollback()
                con.execute('DROP TRIGGER pages_au');con.execute("UPDATE pages SET body='committedstale'");con.execute(trigger);con.commit()
                inspect('WAL-committed-stale-included',path,1,dict(fts_triggers='PASS',fts_content='FAIL'))
            path=variant('locked','PRAGMA journal_mode=DELETE;')
            lock_before=file_state(path)
            with closing(sqlite3.connect(path)) as con:
                con.execute('BEGIN EXCLUSIVE')
                # Do not open/close another FD to this DB in the locking process:
                # POSIX close would release its process-wide fcntl locks.
                start=time.monotonic();r=call('exclusive-lock-timeout',['database','check','--database',path,'--timeout-ms','100'],2)
                check(r['error']['code']=='database_timeout','timeout distinguished from corruption')
                check(time.monotonic()-start<5,'bounded tested lock wait');con.rollback()
            check(source_preserved(lock_before,file_state(path)),'locked source preserved')
            path=output/'fixtures/invalid-header.db';path.write_bytes(b'PRIVATE_BODY_SENTINEL invalid SQLite')
            inspect('invalid-header',path,2)
            path=root/'oversized.db'
            with path.open('wb') as f:f.truncate(CAP+1)
            call('oversized-file',['database','check','--database',path],2)
            path.unlink()
            missing=root/'not-created.db';inspect('missing-file',missing,2);check(not missing.exists(),'missing DB not created')
            inspect('directory-as-file',root,2)
            for index,args in enumerate([[],['check'],['repair','--database',pristine],['check','--database',pristine,'--repair','1'],['check','--database',pristine,'--database',pristine],['check','--database',pristine,'--timeout-ms'],['check','--database',pristine,'--timeout-ms','0'],['check','--database',pristine,'--timeout-ms','99'],['check','--database',pristine,'--timeout-ms','120001'],['check','--database',pristine,'--timeout-ms','NaN'],['check','--database','file:other?mode=rw'],['check','--database','../other.db']]):
                call('invalid-args-'+str(index),['database',*args],2)
            # Windows runners use different volumes for checkout (D:) and TEMP (C:).
            # Hard links must share a volume: preserve the rejection probe, not skip it.
            hard=pristine.with_name('hard-link.db');os.link(pristine,hard)
            try: inspect('hard-link',hard,2)
            finally:hard.unlink()
            link=root/'linked.db'
            try:link.symlink_to(pristine)
            except OSError as exc:skipped.append('symlink unavailable: '+type(exc).__name__)
            else:inspect('symbolic-link',link,2);link.unlink()
            if os.name=='nt':
                for name,path in [('ads',str(pristine)+':stream'),('unc',r'\\invalid.invalid\brain.db')]:
                    call('windows-'+name,['database','check','--database',path],2)
            check((data/'Qbrain/config.json').read_bytes()==registry,'default registry unchanged by every diagnostic')
            check(not (home/'SECRET_ENV_SENTINEL').exists(),'environment configuration not consumed')
    except Exception as exc:
        failure=type(exc).__name__+': '+str(exc)
    result=dict(schema='qbrain-n48n-test-v1',passed=failure is None,failure=failure,binary_sha256=sha(binary.read_bytes()),script_sha256=sha(Path(__file__).read_bytes()),commands=commands,checks=checks,skipped=skipped)
    (output/'RESULT.json').write_bytes(encode(result))
    need(failure is None,failure)
    return dict(passed=True,commands=len(commands),checks=len(checks),skipped=skipped)

def verify(binary,output):
    r=decode((output/'RESULT.json').read_bytes())
    need(r['passed'] is True and r['failure'] is None,'completed report')
    need(r['binary_sha256']==sha(binary.read_bytes()),'binary identity')
    need(r['script_sha256']==sha(Path(__file__).read_bytes()),'script identity')
    need(len(r['commands'])>=46 and all(c['passed'] is True for c in r['checks']),'coverage/checks')
    mandatory=['actual-init', 'healthy-actual-product', 'stale-with-canonical-triggers', 'missing-pages_ai', 'missing-pages_ad', 'missing-pages_au', 'wrong-trigger-body', 'ordinary-table-impersonation', 'unsupported-tokenizer', 'foreign-key-orphan', 'orphan-without-fk-declaration', 'missing-index', 'missing-table', 'old-version', 'new-version', 'bad-version', 'empty-indexed-text', '17MiB-BLOB', 'layout-512-UTF-8', 'layout-512-UTF-16', 'layout-4096-UTF-8', 'layout-4096-UTF-16', 'layout-8192-UTF-8', 'layout-8192-UTF-16', 'layout-65536-UTF-8', 'layout-65536-UTF-16', 'WAL-uncommitted-excluded', 'WAL-committed-stale-included', 'exclusive-lock-timeout', 'invalid-header', 'oversized-file', 'missing-file', 'directory-as-file', 'invalid-args-0', 'invalid-args-1', 'invalid-args-2', 'invalid-args-3', 'invalid-args-4', 'invalid-args-5', 'invalid-args-6', 'invalid-args-7', 'invalid-args-8', 'invalid-args-9', 'invalid-args-10', 'invalid-args-11', 'hard-link']
    names=[c['name'] for c in r['commands']]
    need(len(names)==len(set(names)) and [n for n in names if n in mandatory]==mandatory,'complete ordered scenario coverage')
    need(set(names)<=set(mandatory)|{'symbolic-link','windows-ads','windows-unc'},'known scenarios only')
    for i,c in enumerate(r['commands']):
        for ext in ['stdin','stdout','stderr']:
            raw=(output/'raw'/f'{i:03}.{ext}').read_bytes()
            need(sha(raw)==c['hashes'][ext],'raw hash')
        need(c['exit']==c['expected_exit'],'exit')
        need(not (output/'raw'/f'{i:03}.stderr').read_bytes(),'empty stderr')
        if 'source_before' in c:need(source_preserved(c['source_before'],c['source_after']),'existing source content preserved')
        if c['is_report']:validate(decode((output/'raw'/f'{i:03}.stdout').read_bytes()),c['expected_exit'],c['expected_statuses'])
    with closing(sqlite3.connect(output/'fixtures/stale-index.db')) as con:
        need(con.execute('PRAGMA integrity_check').fetchall()==[('ok',)],'raw stale structure')
        need(con.execute("SELECT count(*) FROM pages WHERE body='differentcurrenttoken'").fetchone()[0]==1,'raw current body')
        need(con.execute("SELECT count(*) FROM pages_fts WHERE pages_fts MATCH 'differentcurrenttoken'").fetchone()[0]==0,'raw stale retrieval')
    return dict(passed=True,commands=len(r['commands']),checks=len(r['checks']),skipped=r['skipped'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--verify',action='store_true');a=p.parse_args()
    print(json.dumps((verify if a.verify else run)(a.binary.resolve(),a.output.resolve()),sort_keys=True))
