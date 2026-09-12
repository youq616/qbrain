"""Real CLI and MCP model isolation, using an isolated migrated brain and mock.
No live model credentials, no production database, no claims of semantic quality.
"""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import struct
import subprocess
import tempfile

p = argparse.ArgumentParser()
p.add_argument('--binary', type=Path, required=True)
a = p.parse_args()
binary = a.binary.resolve(strict=True)
checks = 0

def check(ok, label):
    global checks
    if not ok:
        raise AssertionError(label)
    checks += 1

with tempfile.TemporaryDirectory(prefix='qbrain-n46d-') as temp:
    root = Path(temp)
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith(('QBRAIN', 'OPENAI', 'ANTHROPIC'))}
    env.update(HOME=temp, LOCALAPPDATA=temp, USERPROFILE=temp, QBRAIN_EMBED_MOCK='1')
    def run(args, data=b''):
        r = subprocess.run([str(binary), *args], input=data, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, env=env, cwd=root, timeout=20)
        if r.returncode:
            raise RuntimeError(r.stderr.decode('utf-8', errors='replace'))
        return r.stdout.decode('utf-8')
    run(['init', '--brain', 'n46d'])
    data_root = root if os.name == 'nt' else root / '.local' / 'share'
    db_path = data_root / 'Qbrain' / 'brains' / 'n46d' / 'brain.db'
    query = 'uniquequerywithoutlexicalmatch'
    vector = struct.pack('<3f', len(query) % 17 + 1, 1, 1)
    ids = {}
    with closing(sqlite3.connect(db_path)) as db:
        db.execute("INSERT INTO sources(id,name) VALUES('alpha','alpha'),('beta','beta')")
        db.execute("INSERT INTO config(key,value) VALUES('mcp.allowed_sources','alpha')")
        for slug, source, model, dim in [
            ('good','alpha','mock-embedding',3),('wrong-model','alpha','other-model',3),
            ('unknown','alpha',None,3),('empty-model','alpha','',3),
            ('wrong-dim','alpha','mock-embedding',9),('forbidden','beta','mock-embedding',3)]:
            c = db.execute('INSERT INTO pages(source_id,slug,title,body) VALUES(?,?,?,?)',
                           (source,slug,slug,'lexicalfallbackterm'))
            ids[slug] = c.lastrowid
            db.execute('INSERT INTO content_chunks(page_id,chunk_index,text,embedding,dim,model) VALUES(?,0,?,?,?,?)',
                       (c.lastrowid, 'vector evidence', vector, dim, model))
        db.commit()
        before = db.total_changes
    hits = json.loads(run(['search',query,'--brain','n46d','--json']))
    check({h['slug'] for h in hits} == {'good','forbidden'}, 'CLI all-source search still filters model/dim')
    hits = json.loads(run(['search','lexicalfallbackterm','--brain','n46d','--json','--no-vector']))
    check(any(h['slug']=='wrong-model' for h in hits), 'lexical search retains other-model pages')
    def mcp(name, args):
        messages = [dict(jsonrpc='2.0',id=0,method='initialize',params={}),
                    dict(jsonrpc='2.0',method='notifications/initialized'),
                    dict(jsonrpc='2.0',id=1,method='tools/call',params={'name':name,'arguments':args})]
        text = run(['serve','--brain','n46d'],
                   ('\n'.join(json.dumps(m) for m in messages)+'\n').encode())
        rows = [json.loads(line) for line in text.splitlines()]
        return next(row['result'] for row in rows if row.get('id')==1)
    reply = mcp('search',{'query':query,'source_id':'alpha'})
    check(not reply.get('isError',False), 'MCP search succeeds')
    hits = json.loads(reply['content'][-1]['text'])
    check(len(hits)==1 and hits[0]['slug']=='good', 'MCP strict model and allowed source')
    denied = mcp('search',{'query':query,'source_id':'beta'})
    check(denied.get('isError',False), 'model identity cannot override source denial')
    think = mcp('think',{'question':query,'source_id':'alpha'})
    check(not think.get('isError',False), 'think degrades without chat credentials')
    synthesis = json.loads(think['content'][-1]['text'])
    check(synthesis['hits']==1 and 'alpha/good' in synthesis['evidence'], 'think uses shared strict model filter')
    check('wrong-model' not in synthesis['evidence'], 'think evidence excludes foreign model')
    with closing(sqlite3.connect(db_path)) as db:
        count = db.execute('SELECT COUNT(*) FROM content_chunks').fetchone()[0]
        check(count==6, 'read paths do not delete old vectors')
        check(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]==0, 'read paths do not schedule paid re-embedding')
        db.execute('UPDATE pages SET deleted_at=? WHERE id=?', ('2026-09-12',ids['good']))
        db.commit()
    reply = mcp('search',{'query':query,'source_id':'alpha'})
    check(json.loads(reply['content'][-1]['text'])==[], 'deleted matching vector cannot resurface')
print(f'N46D production search: {checks} checks passed')
