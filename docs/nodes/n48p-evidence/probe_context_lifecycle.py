"""Independent N48P whole-program SQLite probes. No product/test helper imports.
Does not establish PostgreSQL or logged-in client consumption. Synthetic data only.
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


def encode(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(x):return hashlib.sha256(x).hexdigest()
def need(x,label):
    if not x:raise ValueError(label)

def main(binary,out):
    binary=binary.resolve(strict=True);out.mkdir(parents=True,exist_ok=False);(out/'raw').mkdir()
    records=[];checks=[]
    def check(x,label):checks.append(dict(name=label,passed=bool(x)));need(x,label)
    with tempfile.TemporaryDirectory(prefix='n48p-independent-') as tmp:
        home=Path(tmp)
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','PG','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
        env.update(HOME=tmp,USERPROFILE=tmp,LOCALAPPDATA=tmp,APPDATA=tmp)
        def call(args,code=0,parse=True):
            p=subprocess.run([str(binary),*args,'--brain','review'],capture_output=True,input=b'',env=env,cwd=home,timeout=20)
            row=dict(args=args,exit=p.returncode,hashes={})
            for key,raw in [('stdout',p.stdout),('stderr',p.stderr)]:
                (out/'raw'/f'{len(records):03d}.{key}').write_bytes(raw);row['hashes'][key]=digest(raw)
            records.append(row);check(p.returncode==code and p.stderr==b'','command exit/stderr')
            return json.loads(p.stdout) if parse else p.stdout
        call(['init','--no-default'],parse=False)
        path=(home if os.name=='nt' else home/'.local/share')/'Qbrain/brains/review/brain.db'
        def sql(query,values=(),read=False):
            with closing(sqlite3.connect(path)) as db:
                result=db.execute(query,values); rows=result.fetchall() if read else None;db.commit();return rows
        for source in ('alpha','beta'):sql('INSERT INTO sources(id,name) VALUES(?,?)',(source,'Synthetic'))
        sql("INSERT INTO config(key,value) VALUES('embed.auto','false') ON CONFLICT(key) DO UPDATE SET value=excluded.value")
        text='z 中文😀 "quoted"\\backslash\r\ne\u0301 Ω\n'*24
        for ident,slug,body,kind in [(1,'docs/raw',text,'note'),(2,'docs/hidden','PRIVATE_SKILL','skill'),
                                     (3,'docs/session','PRIVATE_SESSION','session_fragment'),(4,'docs-neighbor/raw','PRIVATE_NEIGHBOR','note')]:
            sql('INSERT INTO pages(id,source_id,slug,title,body,type) VALUES(?,?,?,?,?,?)',(ident,'alpha',slug,'Synthetic',body,kind))
        sql('INSERT INTO pages(id,source_id,slug,title,body) VALUES(5,?,?,?,?)',('beta','docs/raw','Beta','PRIVATE_BETA'))
        uri='qbrain://alpha/resources/docs/'
        def read(u=uri,layer='L1',extra=(),code=0):
            return call(['context','read','--source','alpha','--uri',u,'--layer',layer,*extra],code)
        def summary(u=uri,extra=(),code=0):return call(['context','summary','--source','alpha','--uri',u,*extra],code)
        preview=read();check(preview['page_count']==1 and all(t not in encode(preview).decode() for t in ['PRIVATE_SKILL','PRIVATE_SESSION','PRIVATE_NEIGHBOR','PRIVATE_BETA']),'namespace/source/prefix isolation')
        for space,marker in [('skills','PRIVATE_SKILL'),('memories','PRIVATE_SESSION')]:
            value=read(f'qbrain://alpha/{space}/docs/')
            check(value['page_count']==1 and marker in value['content'],'separate namespace')
        check(sql("SELECT count(*) FROM sqlite_master WHERE name='context_cache'",read=True)==[(0,)],'reads do not initialize cache')
        old_revision=digest(text.encode())
        for budget in (512,777,2048,32768):
            offset=0;parts=[]
            for _ in range(100):
                extra=['--max-bytes',str(budget)]
                if offset:extra+=['--offset',str(offset),'--revision',old_revision]
                r=read(uri+'raw','L2',extra)
                check(r['revision']==old_revision and r['offset']==offset and len(encode(r))<=budget,'budget/revision/cursor')
                part=r['content'].encode();check(text.encode()[offset:offset+len(part)]==part,'unmodified UTF8 bytes')
                parts.append(part)
                if r['next_offset'] is None:break
                check(type(r['next_offset']) is int and r['next_offset']==offset+len(part)>offset,'cursor advancement')
                offset=r['next_offset']
            check(b''.join(parts)==text.encode(),'complete body reconstruction')
        for extra in (['--offset','3','--revision',old_revision],['--offset','1'],['--revision','0'*64]):
            r=read(uri+'raw','L2',extra,1)
            check(r=={'error':{'code':'stale_or_invalid_cursor'}},'invalid scalar/revision rejected')
        for u,code in [(uri,'directory_requires_preview'),('qbrain://beta/resources/docs/raw','source_uri_mismatch')]:
            check(read(u,'L2',code=1)=={'error':{'code':code}},'raw boundary error')
        check(summary(extra=['--method','model'],code=1)=={'error':{'code':'external_summary_denied'}},'no unauthorized model summary')
        check(sql("SELECT count(*) FROM sqlite_master WHERE name='context_cache'",read=True)==[(0,)],'denial no optional DDL')
        summary();check(read()['cache_status']=='fresh','published cache fresh')
        with closing(sqlite3.connect(path)) as db:
            db.execute('BEGIN');db.execute("UPDATE pages SET body='UNCOMMITTED' WHERE id=1");db.rollback()
        check(read()['cache_status']=='fresh','rollback preserves cache')
        sql("UPDATE pages SET body='Changed exact 中文😀' WHERE id=1")
        check(sql("SELECT dirty,l0,l1,refs_json FROM context_cache WHERE source_id='alpha'",read=True)==[(1,'','','[]')],'invalidation clears derived contents')
        r=read();check(r['cache_status']=='stale' and 'Changed exact 中文😀' in r['content'],'recompute stale preview')
        check(read(uri+'raw','L2',['--offset','1','--revision',old_revision],1)=={'error':{'code':'stale_or_invalid_cursor'}},'old cursor rejected after change')
        summary()
        call(['context','summary','--source','beta','--uri','qbrain://beta/resources/docs/'])
        sql("UPDATE pages SET source_id='beta',slug='docs/moved' WHERE id=1")
        check(sql('SELECT source_id,dirty,l0,l1,refs_json FROM context_cache ORDER BY source_id',read=True)==[('alpha',1,'','','[]'),('beta',1,'','','[]')],'both moved sources invalidated')
        check(read()['page_count']==0,'moved content absent from old source')
        sql("UPDATE pages SET source_id='alpha',type='skill' WHERE id=1")
        check(read()['page_count']==0,'namespace move not leaked')
        sql("UPDATE pages SET type='note',deleted_at=CURRENT_TIMESTAMP WHERE id=1")
        check(read()['page_count']==0,'soft deleted content absent')
        sql('DELETE FROM pages WHERE id=1');check(read()['page_count']==0,'hard deleted content absent')
        # Max-page bounded preview, with a neighboring-prefix sentinel excluded.
        with closing(sqlite3.connect(path)) as db:
            db.executemany('INSERT INTO pages(id,source_id,slug,title,body) VALUES(?,?,?,?,?)',
                           [(100+i,'alpha',f'many/{i:03}','Small','body') for i in range(257)]);db.commit()
        r=read('qbrain://alpha/resources/many/','L1',['--max-bytes','512'])
        check(r['page_count']==256 and r['truncated'] is True and len(encode(r))<=512,'directory item/byte cap')
        check(all(x['page_id']<356 for x in r['refs']),'no 257th page ref')
        r=read('qbrain://alpha/resources/missing/')
        check(r['content']=='' and r['page_count']==0 and r['revision']==digest(b''),'empty source snapshot')
    report=dict(schema='qbrain-n48p-independent-process-v1',passed=True,commands=records,checks=checks,
                command_count=len(records),check_count=len(checks),binary_sha256=digest(binary.read_bytes()),
                script_sha256=digest(Path(__file__).read_bytes()),postgres_execution=False,model_requests_sent=0)
    (out/'RESULT.json').write_bytes(encode(report)+b'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('commands','checks')}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();main(a.binary,a.output)
