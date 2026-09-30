"""N48T: independent real-CLI and SQL mutation oracle; disposable SQLite only.
No imports from product or existing fixtures. All assertions remain active under -O.
The oracle derives invalidation from OLD/NEW row sets, not from implementation SQL.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import sqlite3
import subprocess
import tempfile


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    def pairs(items):
        obj = {}
        for k, v in items:
            if k in obj: raise ValueError('duplicate JSON key')
            obj[k] = v
        return obj
    def invalid(_): raise ValueError('nonfinite JSON')
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs, parse_constant=invalid)


def space(row):
    return {'skill': 'skills', 'session_fragment': 'memories'}.get(row['type'], 'resources')


def owns(cached, page):
    prefix = 'qbrain://' + page['source_id'] + '/' + space(page) + '/'
    # Prefix comes from the page identity; namespace/scope parsed separately.
    if cached['source_id'] != page['source_id'] or not cached['uri'].startswith(prefix): return False
    path = cached['uri'][len(prefix):]
    return page['slug'].startswith(path)


def main(binary, output, baseline_probe):
    binary = binary.resolve(strict=True)
    output.mkdir(parents=True, exist_ok=False); (output/'raw').mkdir()
    commands = []; cases = []; checks = 0
    def need(ok, label):
        nonlocal checks
        checks += 1
        if not ok: raise ValueError(label)
    env = {k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','PG','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
    try:
        with tempfile.TemporaryDirectory(prefix='n48t-scope-') as tmp:
            home = Path(tmp)
            env.update(HOME=tmp, USERPROFILE=tmp, APPDATA=tmp, LOCALAPPDATA=tmp)
            dbpath=(home if os.name=='nt' else home/'.local/share')/'Qbrain/brains/n48t/brain.db'
            def cli(*args):
                p=subprocess.run([str(binary),*args,'--brain','n48t'],capture_output=True,input=b'',cwd=tmp,env=env,timeout=20)
                i=len(commands); hashes={}
                for suffix,raw in [('stdout',p.stdout),('stderr',p.stderr)]:
                    (output/'raw'/f'{i:04}.{suffix}').write_bytes(raw);hashes[suffix]=sha(raw)
                commands.append(dict(args=list(args),exit=p.returncode,hashes=hashes))
                need(p.returncode==0 and p.stderr==b'', 'CLI rejected: '+str(args))
                return decode(p.stdout) if args[0]=='context' else None
            def sql(statement, params=(), read=False):
                with closing(sqlite3.connect(dbpath)) as db, db:
                    db.row_factory=sqlite3.Row
                    rows=db.execute(statement,params)
                    return [dict(x) for x in rows] if read else None
            def cache_rows(): return sql('SELECT * FROM context_cache ORDER BY source_id,uri', read=True)
            def pages(): return {r['id']:r for r in sql('SELECT id,source_id,slug,type,title,body,deleted_at FROM pages ORDER BY id',read=True)}
            cli('init','--no-default')
            for source in ('alpha','beta'): sql('INSERT INTO sources(id,name) VALUES(?,?)',(source,'fixture'))
            sql("INSERT INTO config(key,value) VALUES('embed.auto','false') ON CONFLICT(key) DO UPDATE SET value=excluded.value")
            seeds=[('alpha','docs/a','note'),('alpha','docs/sub/deep','note'),('alpha','other/a','note'),
                   ('alpha','docs-neighbor/a','note'),('alpha','a_b/a','note'),('alpha','axb/a','note'),
                   ('alpha','Case/a','note'),('alpha','case/a','note'),('alpha','中文😀/a','note'),
                   ('alpha','docs/tool','skill'),('alpha','docs/session','session_fragment'),('beta','docs/a','note')]
            for i,(src,slug,kind) in enumerate(seeds,1):
                sql('INSERT INTO pages(id,source_id,slug,type,title,body) VALUES(?,?,?,?,?,?)',(i,src,slug,kind,slug,'Original '+slug+' 中文😀\r\n'))
            cache_ids=[]
            for src in ('alpha','beta'):
                for kind in ('resources','skills','memories'):
                    for path in ('','docs/','docs/sub/','other/','empty/','a_b/','axb/','Case/','case/','中文😀/'):
                        uri='qbrain://'+src+'/'+kind+'/'+path
                        cli('context','summary','--source',src,'--uri',uri)
                        cache_ids.append((src,uri))
            original_rows=cache_rows(); original_pages=pages()
            sql('PRAGMA wal_checkpoint(TRUNCATE)',read=True)
            pristine=dbpath.read_bytes()
            rng=random.Random(480045)
            mutations=[('same-scope-body',"UPDATE pages SET body='new' WHERE id=1",()),
                       ('move-source',"UPDATE pages SET source_id='beta',slug='docs/moved' WHERE id=1",()),
                       ('move-namespace',"UPDATE pages SET type='skill' WHERE id=1",()),
                       ('move-slug',"UPDATE pages SET slug='other/moved' WHERE id=1",()),
                       ('delete',"DELETE FROM pages WHERE id=1",()),
                       ('soft-delete',"UPDATE pages SET deleted_at='2030-01-01' WHERE id=1",()),
                       ('new-empty-directory',"INSERT INTO pages(id,source_id,slug,title,body) VALUES(100,'alpha','empty/new','new','new')",()),
                       ('replace-cross-source',"INSERT OR REPLACE INTO pages(id,source_id,slug,type,title,body) VALUES(1,'beta','other/replaced','skill','replaced','new')",()),
                       ('replace-conflict-victim',"UPDATE OR REPLACE pages SET source_id='alpha',slug='docs/tool' WHERE id=3",())]
            for i in range(48):
                ident=rng.randrange(1,13)
                field,value=rng.choice([('type',rng.choice(['note','skill','session_fragment'])),
                    ('source_id',rng.choice(['alpha','beta'])),('slug',rng.choice(['docs/','other/','empty/','a_b/','Case/','中文😀/'])+f'random-{i}'),
                    ('deleted_at','2030-01-01'),('body','new '+str(i)+' 中文😀'),('title','title '+str(i))])
                if original_pages[ident][field]==value: field,value='body','forced change '+str(i)
                mutations.append((f'random-{i}',f'UPDATE pages SET {field}=? WHERE id=?',(value,ident)))
            for name,statement,params in mutations[:1] if baseline_probe else mutations:
                # No live connection or writer here; reset only our disposable DB.
                for suffix in ('-wal','-shm'):
                    Path(str(dbpath)+suffix).unlink(missing_ok=True)
                dbpath.write_bytes(pristine)
                try:
                    sql(statement,params)
                except sqlite3.IntegrityError:
                    need(pages()==original_pages and encode(cache_rows())==encode(original_rows),
                         'constraint failure must rollback rows and invalidation: '+name)
                    cases.append(dict(name=name,sql=statement,params=params,result='constraint_rejected_atomically'))
                    continue
                after_pages=pages(); actual=cache_rows()
                changed=[]
                for ident in sorted(original_pages.keys()|after_pages.keys()):
                    if original_pages.get(ident)!=after_pages.get(ident):
                        if ident in original_pages: changed.append(original_pages[ident])
                        if ident in after_pages: changed.append(after_pages[ident])
                affected=[]; unaffected=[]
                for before,after in zip(original_rows,actual):
                    if any(owns(before,r) for r in changed):
                        want={**before,'dirty':1,'l0':'','l1':'','refs_json':'[]'}
                        affected.append(before['uri']);need(encode(after)==encode(want),'affected complete cache mismatch: '+name)
                    else:
                        unaffected.append(before['uri']);need(encode(after)==encode(before),'unrelated cache invalidated: '+name)
                # Read a random affected cached URI and compare all selected evidence
                # identity, page count and untruncated L1 text against row data.
                src,uri=next((r['source_id'],r['uri']) for r in original_rows if r['uri'] in affected)
                r=cli('context','read','--source',src,'--uri',uri,'--layer','L1','--max-bytes','32768')
                cached={'source_id':src,'uri':uri}
                selected=sorted((x for x in after_pages.values() if x['deleted_at'] is None and owns(cached,x)),key=lambda x:(x['slug'].encode(),x['id']))[:256]
                revision=sha(''.join(sha(encode([x['id'],x['slug'],x['title'],x['body']])) for x in selected).encode())
                need(r['revision']==revision and r['page_count']==len(selected),'recomputed revision/count: '+name)
                need(r['content']==''.join(x['title']+'\n'+x['body']+'\n' for x in selected),'recomputed full preview: '+name)
                need(r['cache_status']=='stale' and r['provider_calls']==0,'no implicit provider/write: '+name)
                cases.append(dict(name=name,sql=statement,params=params,affected=affected,unaffected=unaffected,
                                  expected_revision=revision,cache_rows_sha256=sha(encode(actual))))
            report=dict(schema='qbrain-n48t-process-v1',passed=True,case_count=len(cases),check_count=checks,
                command_count=len(commands),binary_sha256=sha(binary.read_bytes()),script_sha256=sha(Path(__file__).read_bytes()),
                optimized=not __debug__,commands=commands,cases=cases,postgres_executed=False,provider_calls=0)
    except Exception as e:
        report=dict(schema='qbrain-n48t-process-v1',passed=False,error=str(e),cases=cases,commands=commands,
                    check_count=checks,binary_sha256=sha(binary.read_bytes()),script_sha256=sha(Path(__file__).read_bytes()))
        (output/'RESULT.json').write_bytes(encode(report)+b'\n')
        raise
    (output/'RESULT.json').write_bytes(encode(report)+b'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('cases','commands')}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--baseline-probe',action='store_true')
    a=p.parse_args();main(a.binary,a.output,a.baseline_probe)
