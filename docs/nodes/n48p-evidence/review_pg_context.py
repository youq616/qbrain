"""Independent N48P saved-output audit. Does not import producer/product modules.
No SQL/EXE execution: fixed synthetic text, hashes and protocol are reconstructed.
Command path identity and producer assertions are not server/source attestation.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path

BODY = '中文😀 quote "source"\r\n' * 60
CHANGED = 'Changed 中文😀'
URI = 'qbrain://alpha/resources/docs/'
BUCKETS = ('stdin', 'stdout', 'stderr')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def enc(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dec(raw):
    need(len(raw) <= 8 * 1024 * 1024, 'json size')
    def unique(items):
        result = {}
        for k, v in items:
            need(k not in result, 'duplicate key')
            result[k] = v
        return result
    def invalid(_):
        raise ValueError('nonfinite number')
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique, parse_constant=invalid)


def eq(a, b, label):
    need(enc(a) == enc(b), label)


def prefix(text, cap, mark=False):
    raw = text.encode('utf8')
    if len(raw) <= cap:
        return text
    # Independent Unicode scalar truncation; synthetic inputs are already valid UTF8.
    if mark and cap >= 11:
        return raw[:cap - 11].decode('utf8', errors='ignore') + '[truncated]'
    return raw[:cap].decode('utf8', errors='ignore')


def preview(body, cache, layer='L1', title='Demo', page_id=100, slug='docs/a', model=False):
    refs = [] if body is None else [dict(uri='qbrain://alpha/resources/' + slug, page_id=page_id, title=title)]
    signature = sha(b'' if body is None else sha(enc([page_id, slug, title, body])).encode())
    l1 = '' if body is None else title + '\n' + prefix(body, 512, True) + '\n'
    content = l1 if layer == 'L1' else prefix(l1, 400, True)
    if model:
        content = 'Synthetic summary; not authoritative.' if layer == 'L1' else 'Generated 中文'
    return dict(uri=URI, source_id='alpha', layer=layer, method='model' if model else 'extractive',
                cache_status=cache, revision=signature, content=content, refs=refs,
                page_count=0 if body is None else 1, truncated=False, untrusted_data=True, provider_calls=0)


def summary(count=1, model=False):
    return dict(uri=URI, status='cached', method='model' if model else 'extractive',
                provider_calls=int(model), input_tokens=21 if model else None,
                output_tokens=8 if model else None, cost=None, page_count=count, truncated=False)


def check_pages(pages, body):
    offset = 0
    need(type(pages) is list and bool(pages), 'pages array')
    for p in pages:
        need(type(p) is dict and type(p.get('offset')) is int and p['offset'] == offset, 'page cursor')
        content = p.get('content'); need(type(content) is str and bool(content), 'page content')
        raw = content.encode('utf8'); end = offset + len(raw)
        need(body.encode('utf8')[offset:end] == raw, 'exact source bytes')
        expected = dict(uri=URI+'a', source_id='alpha', page_id=100, layer='L2', revision=sha(body.encode()),
                        offset=offset, next_offset=end if end < len(body.encode()) else None,
                        provider_calls=0, untrusted_data=True, method='raw', content=content,
                        truncated=end < len(body.encode()))
        eq(p, expected, 'complete L2 metadata')
        need(end <= len(body.encode()) and len(enc(p)) <= 512, 'page bounds')
        offset = end
    need(offset == len(body.encode()), 'complete raw coverage')


def mcp_messages():
    return [dict(jsonrpc='2.0', id=1, method='tools/call', params=dict(name='context_read', arguments=dict(source_id='alpha', uri=URI))),
            dict(jsonrpc='2.0', id=2, method='tools/call', params=dict(name='context_read', arguments=dict(source_id='beta', uri='qbrain://beta/resources/docs/'))),
            dict(jsonrpc='2.0', id=3, method='tools/call', params=dict(name='context_write', arguments=dict(source_id='alpha', uri=URI)))]


def mcp_replies(fresh):
    values = [fresh, {'error':dict(code='source_not_allowed', field='source_id', message='source_id is not authorized for remote access')},
              {'error':dict(code='write_denied', field='operation', message='MCP write operations require the --allow-write opt-in')}]
    return [dict(id=i+1, jsonrpc='2.0', result=dict(content=[dict(text=enc(v).decode(), type='text')], isError=i != 0))
            for i, v in enumerate(values)]


def observation_expected(pages):
    check_pages(pages, BODY)
    fresh = preview(BODY, 'fresh', 'L0')
    return {'root': dict(uri='qbrain://alpha/', entries=['memories/','resources/','skills/'], untrusted_data=True, provider_calls=0),
            'missing':preview(BODY,'missing'), 'pages':pages, 'summary':summary(), 'fresh':fresh,
            'mcp':mcp_replies(fresh), 'stale':preview(CHANGED,'stale'),
            'bad-cursor':{'error':{'code':'stale_or_invalid_cursor'}},
            'wrong-source':{'error':{'code':'source_uri_mismatch'}}, 'deleted':preview(None,'stale')}


def expected_sql():
    def query(q): return "SELECT coalesce(json_agg(t),'[]'::json)::text FROM ("+q+") t"
    def text(v): return "pg_catalog.convert_from(pg_catalog.decode('"+v.encode().hex()+"','hex'),'UTF8')"
    steps=[(query('SELECT current_database() AS name'), [{'name':'qbrain_n48p_process'}]),
        ('SET client_min_messages=WARNING; DROP TABLE IF EXISTS public.context_cache,public.context_module CASCADE; DROP FUNCTION IF EXISTS public.qbrain_context_invalidate_v1() CASCADE', None),
        ('DELETE FROM public.pages; DELETE FROM public.config',None)]
    for sid in ('alpha','beta'):
        steps.append(("INSERT INTO sources(id,name) VALUES('"+sid+"','fixture') ON CONFLICT DO NOTHING",None))
    for key,value in [('embed.auto','false'),('mcp.allowed_sources','alpha')]:
        steps.append(("INSERT INTO config(key,value) VALUES('"+key+"','"+value+"') ON CONFLICT(key) DO UPDATE SET value=excluded.value",None))
    for ident,source,body in [(100,'alpha',BODY),(200,'beta','BETA_SECRET')]:
        steps.append((f"INSERT INTO pages(id,source_id,slug,title,body) OVERRIDING SYSTEM VALUE VALUES({ident},{text(source)},'docs/a','Demo',{text(body)})",None))
    steps.extend([(query("SELECT count(*) AS n FROM information_schema.tables WHERE table_schema='public' AND table_name='context_cache'"),[{'n':0}]),
        ("UPDATE pages SET body="+text(CHANGED)+" WHERE id=100",None),
        (query("SELECT dirty,l0,l1,refs_json FROM context_cache WHERE source_id='alpha'"),[dict(dirty=1,l0='',l1='',refs_json='[]')]),
        ('DELETE FROM pages WHERE id=100',None)])
    return steps


def schedule(obs):
    ctx = ['context','read','--source','alpha','--uri',URI]
    summ = ['context','summary','--source','alpha','--uri',URI]
    rows=[(['init','--no-default'],None,b'',0),
          (['context','list','--source','alpha'],obs['root'],b'',0),
          (ctx+['--layer','L1'],obs['missing'],b'',0)]
    for p in obs['pages']:
        args=['context','read','--source','alpha','--uri',URI+'a','--layer','L2','--max-bytes','512']
        if p['offset']:
            args+=['--offset',str(p['offset']),'--revision',sha(BODY.encode())]
        rows.append((args,p,b'',0))
    rows += [(summ,obs['summary'],b'',0),(ctx,obs['fresh'],b'',0),
             (summ+['--method','model'],{'error':{'code':'external_summary_denied'}},b'',1),
             (['serve','--tool-profile','memory'],obs['mcp'],b'\n'.join(enc(x) for x in mcp_messages())+b'\n',0),
             (ctx+['--layer','L1'],obs['stale'],b'',0),
             (['context','read','--source','alpha','--uri',URI+'a','--layer','L2','--offset','1','--revision',sha(BODY.encode())],obs['bad-cursor'],b'',1),
             (['context','read','--source','alpha','--uri','qbrain://beta/resources/docs/'],obs['wrong-source'],b'',1),
             (summ,summary(),b'',0),(ctx+['--layer','L1'],obs['deleted'],b'',0)]
    return rows


def audit(report, streams, binary_sha, script_sha, optimized):
    need(set(report)=={'schema','passed','real_postgres','optimized','binary_sha256','script_sha256','commands','checks',
                       'command_count','check_count','observations','paid_model_calls'}, 'report keys')
    need(report['schema']=='qbrain-n48p-process-v1' and report['passed'] is True and report['real_postgres'] is True, 'completed real PG record')
    need(report['optimized'] is optimized and report['binary_sha256']==binary_sha and report['script_sha256']==script_sha, 'external identity')
    for key,count in [('command_count',55),('check_count',173),('paid_model_calls',0)]:
        need(type(report[key]) is int and report[key]==count, 'exact count '+key)
    need(len(report['commands'])==55 and len(streams)==55 and len(report['checks'])==173, 'fixed inventory')
    need(all(set(c)=={'name','passed'} and isinstance(c['name'],str) and c['passed'] is True for c in report['checks']), 'producer check shape')
    need(set(report['observations'])=={'sqlite','postgres'}, 'two backend observations')
    obs=observation_expected(report['observations']['sqlite']['pages'])
    for backend in ('sqlite','postgres'):
        eq(report['observations'][backend],obs,'independent full observation '+backend)
    phases={x:iter(schedule(obs)) for x in ('sqlite','postgres')}
    counts=dict(sqlite=0,postgres=0,sql=0)
    sql=iter(expected_sql())
    for i,(r,raw) in enumerate(zip(report['commands'],streams)):
        need(set(r)=={'name','args','exit','hashes'} and set(r['hashes'])==set(BUCKETS), 'record fields')
        need(set(raw)==set(BUCKETS), 'stream fields')
        for key in BUCKETS: need(sha(raw[key])==r['hashes'][key], 'stream hash')
        need(type(r['exit']) is int, 'typed exit')
        if r['name']=='psql':
            query,expected=next(sql); counts['sql']+=1
            eq(r['args'],['psql','-X','-q','-A','-t','-v','ON_ERROR_STOP=1','-c',query],'exact fixture SQL')
            need(r['exit']==0 and raw['stdin']==raw['stderr']==b'', 'SQL outcome')
            need(raw['stdout']==b'' if expected is None else enc(dec(raw['stdout']))==enc(expected),'SQL result')
            continue
        backend=r['name'].split(':')[0]; need(backend in phases,'backend label')
        args,expected,stdin,exit_code=next(phases[backend]); counts[backend]+=1
        eq(r['args'][1:],args+['--brain','n48p'],'exact product arguments')
        need(r['args'][0].replace('\\','/').split('/')[-1] in ('qbrain','qbrain.exe'), 'program name')
        need(raw['stdin']==stdin and r['exit']==exit_code,'exact input and exit')
        if args[0]=='init':
            need(bool(raw['stdout']) and raw['stderr']==b'', 'initialization outcome')
        elif args[0]=='serve':
            eq([dec(line) for line in raw['stdout'].splitlines()],expected,'MCP results')
            need(b'[qbrain-serve] stdio MCP ready' in raw['stderr'] and b'shutdown: stdin EOF' in raw['stderr'],'MCP lifecycle')
        else:
            need(raw['stderr']==b'', 'no diagnostic leak')
            eq(dec(raw['stdout']),expected,'recomputed output '+str(i))
    need(counts==dict(sqlite=21,postgres=21,sql=13), 'schedule counts')
    # Interleaving is fixed: no read is accepted before its corresponding mutation.
    eq([x['name'] for x in report['commands']],
       ['psql']*2 + ['sqlite:init']+['sqlite:context']*14+['sqlite:MCP']+['sqlite:context']*5+
       ['postgres:init']+['psql']*7+['postgres:context']*2+['psql']+['postgres:context']*12+
       ['postgres:MCP']+['psql']*2+['postgres:context']*4+['psql','postgres:context'], 'complete ordering')
    return dict(commands=55,product_commands=42,psql_commands=13,raw_pages_per_backend=len(obs['pages']),passed=True)


def load(directory):
    r=dec((directory/'RESULT.json').read_bytes())
    need({p.name for p in (directory/'raw').iterdir()}=={f'{i:03}.{k}' for i in range(55) for k in BUCKETS}, 'raw inventory')
    raw=[]
    for i in range(55):
        item={}
        for key in BUCKETS:
            path=directory/'raw'/f'{i:03}.{key}'
            need(path.is_file() and not path.is_symlink() and path.stat().st_size<=8388608,'regular bounded file')
            item[key]=path.read_bytes()
        raw.append(item)
    return r,raw


def mutations(r,raw,binary_sha,script_sha,optimized):
    names=('bool-count','wrong-binary','wrong-script','wrong-mode','false-pg','missing-command','reorder',
           'wrong-args','bool-exit','wrong-source','wrong-revision','wrong-offset','changed-text','stale-green',
           'rehashed-raw','duplicate-json','nan','false-MCP-write','wrong-SQL','uncleared-cache','extra-report','leaked-content')
    rejected=[]
    for name in names:
        a,b=copy.deepcopy(r),copy.deepcopy(raw)
        if name=='bool-count':a['paid_model_calls']=False
        elif name=='wrong-binary':a['binary_sha256']='0'*64
        elif name=='wrong-script':a['script_sha256']='0'*64
        elif name=='wrong-mode':a['optimized']=not optimized
        elif name=='false-pg':a['real_postgres']=False
        elif name=='missing-command':a['commands'].pop()
        elif name=='reorder':a['commands'][18],a['commands'][19]=a['commands'][19],a['commands'][18];b[18],b[19]=b[19],b[18]
        elif name=='wrong-args':a['commands'][4]['args'][5]='beta'
        elif name=='bool-exit':a['commands'][4]['exit']=False
        elif name=='wrong-source':a['observations']['postgres']['missing']['source_id']='beta'
        elif name=='wrong-revision':a['observations']['sqlite']['pages'][0]['revision']='0'*64
        elif name=='wrong-offset':a['observations']['sqlite']['pages'][1]['offset']+=1
        elif name=='changed-text':a['observations']['sqlite']['pages'][0]['content']='INVENTED'
        elif name=='stale-green':a['observations']['sqlite']['stale']['cache_status']='fresh'
        elif name=='false-MCP-write':a['observations']['postgres']['mcp'][2]['result']['isError']=False
        elif name=='wrong-SQL':a['commands'][47]['args'][-1]='DELETE FROM pages'
        elif name=='extra-report':a['extra']='unvalidated'
        else:
            idx=48 if name=='uncleared-cache' else 4
            out=dec(b[idx]['stdout'])
            if name=='uncleared-cache':out[0]['l1']='OLD PRIVATE CACHE'
            elif name=='leaked-content':out['content']='BETA_SECRET'
            elif name=='rehashed-raw':out['content']='FAKE PREVIEW'
            new=enc(out)
            if name=='duplicate-json':new=b'{"schema":0,"schema":1,'+new[1:]
            if name=='nan':new=b'{"extra":NaN,'+new[1:]
            b[idx]['stdout']=new;a['commands'][idx]['hashes']['stdout']=sha(new)
        try:audit(a,b,binary_sha,script_sha,optimized)
        except (ValueError,KeyError,TypeError,IndexError,StopIteration):rejected.append(name)
        else:raise ValueError('accepted mutation '+name)
    return rejected


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--binary-sha256',required=True);p.add_argument('--script-sha256',required=True)
    p.add_argument('--optimized',action='store_true');p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();r,raw=load(args.directory)
    result=audit(r,raw,args.binary_sha256,args.script_sha256,args.optimized)
    result.update(schema='qbrain-n48p-independent-context-readback-v1',
                  rejected_mutations=mutations(r,raw,args.binary_sha256,args.script_sha256,args.optimized),
                  reviewer_sha256=sha(Path(__file__).read_bytes()),producer_report_sha256=sha((args.directory/'RESULT.json').read_bytes()),
                  new_postgresql_execution=False)
    with args.output.open('xb') as f:f.write(enc(result)+b'\n')
    print(json.dumps(result))

if __name__=='__main__':
    main()
