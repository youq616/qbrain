"""Independent N48O original-evidence verifier; stdlib, offline and read-only.

Recomputes the synthetic conversation identities and all lifecycle results without
importing the runtime or test_pg_memory.py. Saved PostgreSQL COPY data is parsed,
NEVER executed. --negatives changes only in-memory copies of evidence. This is
integrity/semantic replay, not new PostgreSQL execution or origin authentication.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import re
import zipfile
from pathlib import Path

PIN = {
 'linux': ('155c7b449637bd6811dd7056059bd9a1aeea1f7a1dd70c7280a21dfb7b644acc',
           '5008002869c6a7251df28697834d6001d3de1321ff7018f2d5c314e49032dc00'),
 'windows': ('46c3d4733ed430ee5464da41573d1a228c59c50ccd673c85afc393512e362ef6',
             'd119280a190d8a98aaab631efed26f98225c4aa1877c0bff18ad3145895d6679')}
SOURCE_PIN = {
 'linux': '3ce11ba908bab8583174a53e4fff217788f64a6ffdad74c8599b31a351e7f8c1',
 'windows': '4900d62f609e2d8242c5a0c00e89fb22dcf2c9aa6ad71839d723685571dfb442'}
NATIVE_PIN = {
 'linux': 'dc9f76438ffcec0f806d587d25ba1b97b7ae89879c53090306214c2d1a4fdc8b',
 'windows': 'bccfa1e2a1bb09842bdada33fe240001dcd3d002225eef667eea9b07b01ba63a'}
# Frozen repaired-candidate profiles. Historical ed79 replay is not deployment acceptance.
REPAIRED_PIN = {
 'linux': ('5767f3d7a883d14616a67497861afffdb3a50c8296a14065111bd893afd9a913',
           '5008002869c6a7251df28697834d6001d3de1321ff7018f2d5c314e49032dc00'),
 'windows': ('d4ebe3b74d769dbe3d2146da53b99ad21349419d16c8a1cb755028eff1cbc5ef',
             'd119280a190d8a98aaab631efed26f98225c4aa1877c0bff18ad3145895d6679')}
REPAIRED_SOURCE_PIN = {
 'linux': 'e0f11da5267086b6b6262b32b4fa4ea188acb8243e3b219cce7611d3c3048ac9',
 'windows': '26a7da902404439562dcec6f9a98850e66203b3a6539c8531526bd0d0e88672b'}
CAP = 8 * 1024 * 1024
QUOTES = ['我偏好中文，并使用 Windows。😀', 'I decided to keep CASE Café Ä --brain data.']

def need(ok, message):
    if not ok:
        raise ValueError(message)

def encode(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def sha(v):
    return hashlib.sha256(v).hexdigest()

def decode(raw):
    need(len(raw) <= CAP, 'JSON bound')
    def unique(pairs):
        out = {}
        for key, value in pairs:
            need(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    def invalid(_):
        raise ValueError('nonfinite JSON')
    value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique, parse_constant=invalid)
    pending = [(value, 0)]
    while pending:
        node, depth = pending.pop()
        need(depth <= 64, 'JSON depth')
        if isinstance(node, dict):pending.extend((v, depth+1) for v in node.values())
        elif isinstance(node, list):pending.extend((v, depth+1) for v in node)
    return value

def equal(actual, expected, label):
    need(encode(actual) == encode(expected), label)

def payload(fragment='literal-case'):
    return dict(session_id='测试 😀', fragment_id=fragment, messages=[
        dict(role='user', content=QUOTES[0]),
        dict(role='assistant', content='I prefer INVENTED assistant facts.'),
        dict(role='user', content=QUOTES[1])])

def event_id(fragment='literal-case'):
    p = payload(fragment)
    digest = sha(encode(dict(messages=p['messages'], expires_at=0)))
    return sha(encode(['qbrain-memory-v1', 'alpha', p['session_id'], fragment, digest]))

def summary(state='archived', duplicate=False, fragment='literal-case'):
    return dict(event_id=event_id(fragment), source_id='alpha', status=state,
                evidence_live=state != 'forgotten', duplicate=duplicate,
                attempts=0 if state == 'archived' else 1)

def captured(fragment='literal-case'):
    return dict(**summary(fragment=fragment), archived=True, extracted=False, provider_requests=0)

def extracted(fragment='literal-case'):
    return dict(**summary('extracted', fragment=fragment), item_count=2, error_code=None,
                method='explicit-markers-v1', provider_attempts=0, cost=None, cost_status='not_priced')

def expected_items(fragment='literal-case'):
    eid = event_id(fragment)
    items = []
    for idx, category, quote in [(0,'preference',QUOTES[0]), (2,'decision',QUOTES[1])]:
        candidate = dict(message_index=idx, category=category, quote=quote)
        items.append(dict(**candidate, item_id=sha(eid.encode()+encode(candidate)), event_id=eid,
                          session_id='测试 😀', source_id='alpha', expires_at=0,
                          method='explicit-markers-v1', evidence_slug='sessions/'+eid))
    return sorted(items, key=lambda x:x['item_id'])

def recalled(items, *, initialized=True, source='alpha', truncated=False):
    out = dict(initialized=initialized, items=items, source_id=source, truncated=truncated,
               truth_status='caller_attested_user_statement', untrusted_data=True)
    if initialized:
        out['candidate_limit'] = 200
    return out

def schedule():
    """Fixed product calls only; setup SQL is independently checked separately."""
    eid = event_id()
    rows = [('init', [], None, 'init'),
            ('read', [], None, recalled([], initialized=False)),
            ('capture', [], payload(), dict(archived=False, reason='writeback_off', status='skipped')),
            ('capture', [], payload(), captured()),
            ('capture', [], payload(), summary(duplicate=True))]
    wrong = payload(); wrong['messages'][0]['content'] = '我偏好别的内容'
    rows += [('capture', [], wrong, {'error':{'code':'fragment_conflict'}}),
             ('extract', ['--event',eid], None, extracted()),
             ('read', [], None, recalled(expected_items()))]
    # ASCII-only matching preserves the existing SQLite contract, not Unicode casefold.
    lower = lambda s:s.translate(str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'))
    for q in ['case','CAFÉ','café','ä','Ä','--brain',"' OR 1=1"]:
        items = [v for v in expected_items() if lower(q) in lower(v['quote'])]
        rows.append(('read',['--query',q],None,recalled(items)))
    rows += [('read', ['--source-override','beta'],None,recalled([],source='beta')),
             ('extract',['--event',eid],None,summary('extracted',True)),
             ('status',['--event',eid],None,'status'),
             ('read',['--max-bytes','512'],None,recalled([],truncated=True)),
             ('serve',[],None,'mcp'),
             ('status',['--event',eid],None,'status'),
             ('forget',['--event',eid],None,dict(event_id=eid,status='forgotten',replay_suppressed=True)),
             ('read',[],None,recalled([])),
             ('capture',[],payload(),summary('forgotten',True))]
    for i in range(3):
        rows.append(('capture',[],payload('drain-'+str(i)),captured('drain-'+str(i))))
    rows += [('drain',[],None,'drain'),
             ('drain',['--method','model'],None,dict(status='empty',events=[],limit=8,max_attempts=3,
                 provider_calls=0,cost=None,reason='external_extraction_denied'))]
    secret = payload('secret'); secret['messages'][0]['content'] = 'api_key=PRIVATE_SENTINEL'
    rows += [('capture',[],secret,{'error':{'code':'sensitive_material_rejected'}})]
    need(len(rows) == 30,'fixed product schedule size')
    return rows

def validate_stream(row, raw, *, expected_exit):
    need(type(row['exit']) is int and type(row['expected_exit']) is int,
         'exit must be integer, not bool')
    need(row['exit'] == row['expected_exit'] == expected_exit,'fixed expected exit')
    need(set(row['hashes']) == {'stdin','stdout','stderr'},'hash inventory')
    for ext in row['hashes']:
        need(sha(raw[ext]) == row['hashes'][ext],'raw hash '+ext)

def validate_product(records, backend):
    items_out = []
    for (row, raw), (action, opts, value, expected) in zip(records, schedule()):
        source = 'alpha'
        if opts == ['--source-override','beta']:
            source, opts = 'beta', []
        args = [action] if action in ('init','serve') else ['memory',action,'--source',source,*opts]
        args += ['--brain','n48o']
        need(row['command'][1:] == args,'exact command arguments')
        need(Path(row['command'][0].replace('\\','/')).name in ('qbrain','qbrain.exe'),'product basename')
        name = backend+':'+('MCP deny' if action=='serve' else 'init' if action=='init' else 'memory')
        need(row['name'] == name, 'product record identity')
        code = 1 if isinstance(expected,dict) and 'error' in expected else 0
        validate_stream(row,raw,expected_exit=code)
        if action=='serve':
            want_stderr = b'[qbrain-serve] stdio MCP ready brain=n48o write=disabled\n[qbrain-serve] shutdown: stdin EOF\n'
            need(raw['stderr'].replace(b'\r\n',b'\n') == want_stderr,'MCP exact lifecycle stderr')
            request = [dict(jsonrpc='2.0',id=0,method='initialize',params={'protocolVersion':'2024-11-05'}),
                       dict(jsonrpc='2.0',method='notifications/initialized'),
                       dict(jsonrpc='2.0',id=1,method='tools/call',params={'name':'memory_write',
                            'arguments':{'source_id':'alpha','action':'forget','event_id':event_id()}})]
            need(raw['stdin'] == b'\n'.join(encode(x) for x in request)+b'\n','MCP exact request')
            replies = [decode(x) for x in raw['stdout'].splitlines()]
            need(len(replies)==2,'MCP reply count')
            equal(replies[1],dict(id=1,jsonrpc='2.0',result=dict(content=[dict(type='text',text=encode(
                {'error':{'code':'write_denied','field':'operation','message':'MCP write operations require the --allow-write opt-in'}}).decode())],isError=True)), 'MCP permission denial')
            need(replies[0]['result']['protocolVersion']=='2024-11-05','protocol agreement')
            continue
        need(not raw['stderr'],'empty stderr')
        need(raw['stdin']==(b'' if value is None else encode(value)),'independent request regeneration')
        if expected=='init':
            need(bool(raw['stdout']),'initialization output')
            continue
        out = decode(raw['stdout'])
        if expected=='status':
            need(len(out['usage'])==1,'one extraction attempt')
            usage = out['usage'][0]
            need(type(usage['elapsed_ms']) is int and usage['elapsed_ms']>=0,'nonnegative elapsed')
            equal(usage,{**dict(method='local',status='completed',provider_attempts=0,input_tokens=0,
                        output_tokens=0,cost=None), 'elapsed_ms':usage['elapsed_ms']},'known local usage, unknown cost')
            equal({k:v for k,v in out.items() if k!='usage'},dict(**summary('extracted'),truncated=False),'status state')
        elif expected=='drain':
            events = out['events']
            equal(sorted(events,key=lambda x:x['event_id']),sorted([extracted('drain-'+str(i)) for i in range(3)],key=lambda x:x['event_id']),'all drained items')
            equal({k:v for k,v in out.items() if k!='events'},dict(status='processed',limit=8,max_attempts=3,provider_calls=0,cost=None),'drain bounds')
        else:
            equal(out,expected,'independent full lifecycle response')
        if action=='read' and not opts and source=='alpha' and out.get('items'):
            items_out.append(out['items'])
    return items_out

def parse_copy(raw):
    """Read data only from an original plain pg_dump. Never execute its SQL."""
    need(len(raw)<=CAP,'dump bound')
    lines = raw.decode('utf-8-sig').splitlines()
    data = {}; current=None; columns=[]
    escapes={'b':'\b','f':'\f','n':'\n','r':'\r','t':'\t','v':'\v','\\':'\\'}
    def cell(value):
        if value==r'\N':return None
        return re.sub(r'\\([bfnrtv\\])',lambda m:escapes[m[1]],value)
    for line in lines:
        if current is not None:
            if line == r'\.':
                current=None;continue
            fields = line.split('\t');need(len(fields)==len(columns),'COPY column width')
            data[current].append(dict(zip(columns,map(cell,fields))))
            continue
        match=re.fullmatch(r'COPY public\.([a-z_]+) \(([^)]+)\) FROM stdin;',line)
        if match:
            current=match[1];columns=match[2].split(', ')
            need(current not in data and len(columns)==len(set(columns)),'COPY table uniqueness')
            data[current]=[]
    need(current is None,'complete COPY')
    return data

def verify_dump(raw):
    db=parse_copy(raw)
    equal(db['memory_module'],[{'version':'1'}],'module version')
    events=db['memory_events'];need(len(events)==4,'four final events')
    expected_fragments={'literal-case','drain-0','drain-1','drain-2'}
    need({x['fragment_id'] for x in events}==expected_fragments,'final fragment coverage')
    pages={r['id']:r for r in db['pages']};need(len(pages)==3,'three live pages')
    expected_memories={}
    for e in events:
        fragment=e['fragment_id'];eid=event_id(fragment)
        need(e['event_id']==eid and e['source_id']=='alpha' and e['session_id']=='测试 😀','server event identity')
        body=encode(dict(messages=payload()['messages'],expires_at=0))
        need(e['payload_hash']==sha(body),'server payload hash')
        need(e['expires_at']=='0' and e['automatic']=='1' and e['capture_mode']=='salient','server policy/expiry')
        need(e['attempts']=='1' and e['lease_token']=='' and e['lease_until']=='0' and e['last_error']=='','server lease cleared')
        need(e['method']=='explicit-markers-v1','exact extraction method')
        if fragment=='literal-case':
            need(e['status']=='forgotten' and e['page_id'] is None,'server persistent tombstone')
        else:
            need(e['status']=='extracted' and e['page_id'] in pages,'live event page')
            p=pages[e['page_id']]
            need(p['body'].encode()==body and p['source_id']=='alpha' and p['slug']=='sessions/'+eid,'page exact evidence')
            need(p['content_hash']==e['page_hash'] and p['deleted_at'] is None,'page/evidence binding')
            for item in expected_items(fragment):expected_memories[item['item_id']]=item
    need(len(db['memory_items'])==len(expected_memories)==6,'six final whole quotes')
    seen=set()
    for item in db['memory_items']:
        expected=expected_memories.get(item['item_id']);need(expected is not None and item['item_id'] not in seen,'unique item identity')
        seen.add(item['item_id'])
        for key in ['event_id','category','quote']:
            need(item[key]==expected[key],'item content '+key)
        need(item['message_index']==str(expected['message_index']) and item['expires_at']=='0','item index and expiry')
    attempts=db['memory_attempts'];need(len(attempts)==4,'all attempt records retained')
    need({a['event_id'] for a in attempts}=={event_id(x) for x in expected_fragments},'attempt event coverage')
    for a in attempts:
        need(a['method']=='local' and a['status']=='completed','local completion')
        need(all(a[k]=='0' for k in ['provider_attempts','input_tokens','output_tokens']),'zero local provider counts')
        need(a['elapsed_ms'].isdigit(),'elapsed integral')
    need(len(db['jobs'])==0 and len(db['content_chunks'])==0,'no implicit embed work')
    return dict(events=4,tombstones=1,pages=3,items=6,attempts=4,dump_sql_executed=False)

def expected_sql():
    query = lambda q: "SELECT coalesce(json_agg(t),'[]'::json)::text FROM ("+q+") t"
    config = lambda k,v: "INSERT INTO config(key,value) VALUES('"+k+"','"+v+"') ON CONFLICT(key) DO UPDATE SET value=excluded.value"
    return [query('SELECT current_database() AS name'),
      'SET client_min_messages=WARNING; DROP TABLE IF EXISTS memory_attempts,memory_items,memory_events,memory_module CASCADE',
      'DELETE FROM pages; DELETE FROM config',
      "INSERT INTO sources(id,name) VALUES('alpha','synthetic') ON CONFLICT DO NOTHING",
      "INSERT INTO sources(id,name) VALUES('beta','synthetic') ON CONFLICT DO NOTHING",
      config('memory.writeback','off'),config('embed.auto','false'),config('memory.writeback','salient'),
      *[query('SELECT count(*) AS n FROM '+t) for t in ['memory_events','pages','memory_items','pages','memory_events','memory_events']],
      query("SELECT data_type AS type FROM information_schema.columns WHERE table_schema='public' AND table_name='memory_events' AND column_name='expires_at'")]

def verify_memory(report, streams, platform, mode):
    shape={'schema','passed','real_postgresql','optimized','binary_sha256','script_sha256','commands','checks','command_count','check_count','paid_provider_requests'}
    need(set(report)==shape,'report fields')
    need(report['schema']=='qbrain-n48o-process-v1' and report['passed'] is True and report['real_postgresql'] is True,'producer status')
    need(report['optimized'] is (mode=='optimized'),'mode identity')
    need((report['binary_sha256'],report['script_sha256'])==PIN[platform],'original component identities')
    for key,number in [('command_count',75),('check_count',213),('paid_provider_requests',0)]:
        need(type(report[key]) is int and report[key]==number,'exact typed count '+key)
    need(len(report['commands'])==75 and len(streams)==75,'all calls')
    need(len(report['checks'])==213 and all(set(c)=={'name','passed'} and isinstance(c['name'],str) and c['passed'] is True for c in report['checks']),'producer assertion status')
    records={s:[] for s in ['sqlite','postgres']}; sql_results=[]; sql_commands=[]
    for row,raw in zip(report['commands'],streams):
        need(set(row)=={'name','command','exit','expected_exit','hashes'},'record fields')
        need(set(raw)=={'stdin','stdout','stderr'},'stream inventory')
        if row['name']=='server SQL':
            validate_stream(row,raw,expected_exit=0)
            need(not raw['stdin'] and not raw['stderr'],'server SQL streams')
            need(row['command'][:7]==['psql','-X','-q','-A','-t','-v','ON_ERROR_STOP=1'] and len(row['command'])==9 and row['command'][7]=='-c','psql exact argv form')
            sql_commands.append(row['command'][8])
            if raw['stdout'].strip():sql_results.append(decode(raw['stdout']))
        else:
            backend=row['name'].partition(':')[0];need(backend in records,'backend record')
            records[backend].append((row,raw))
    need([len(records[s]) for s in records]==[30,30],'both backend full schedules')
    equal(sql_commands,expected_sql(),'exact non-executed SQL history')
    equal(sql_results,[[{'name':'qbrain_n48o_process'}],[{'n':1}],[{'n':1}],
        [{'n':0}],[{'n':0}],[{'n':1}],[{'n':4}],[{'type':'bigint'}]],'independent server query results')
    a=validate_product(records['sqlite'],'sqlite');b=validate_product(records['postgres'],'postgres')
    equal(a,b,'complete cross-backend item equality')
    # Bind the global interleaving, not just two independently rearrangeable lists.
    sql_positions={0,1,33,34,35,36,37,40,42,43,64,65,66,73,74}
    need({i for i,row in enumerate(report['commands']) if row['name']=='server SQL'}==sql_positions,'global SQL order')
    need(all(report['commands'][i]['name'].startswith('sqlite:') for i in range(2,32)),'SQLite first phase')
    return dict(calls=75,product_calls=60,server_sql_calls=15,producer_checks=213)

def load(directory):
    report=decode((directory/'RESULT.json').read_bytes())
    expected={f'{i:03}.{ext}' for i in range(75) for ext in ('stdin','stdout','stderr')}
    need({p.name for p in (directory/'raw').iterdir()}==expected,'exact raw file inventory')
    streams=[]
    for i in range(75):
        row={}
        for ext in ('stdin','stdout','stderr'):
            p=directory/'raw'/f'{i:03}.{ext}';need(p.is_file() and not p.is_symlink() and p.stat().st_size<=CAP,'regular bounded stream')
            row[ext]=p.read_bytes()
        streams.append(row)
    return report,streams

def negatives(original, streams, platform, mode, dump):
    kinds=['bool-count','bool-exit','bool-zero','missing-command','extra-field','wrong-binary','wrong-script',
           'wrong-mode','changed-input','wrong-source','assistant-as-fact','partial-quote','wrong-item-id',
           'wrong-event-id','post-forget-recall','forgotten-restored','wrong-model-cost','duplicate-json',
           'nonfinite-json','unexpected-stderr','false-MCP-allow','wrong-query-result','wrong-order','changed-dump','changed-sql']
    rejected=[]
    for kind in kinds:
        report=copy.deepcopy(original);raws=copy.deepcopy(streams)
        def replace(index, value, suffix='stdout'):
            raw=value if isinstance(value,bytes) else encode(value)+b'\n'
            raws[index][suffix]=raw;report['commands'][index]['hashes'][suffix]=sha(raw)
        if kind=='bool-count':report['command_count']=True
        elif kind=='bool-exit':report['commands'][41]['exit']=False
        elif kind=='extra-field':report['quality_verified']=True
        elif kind=='missing-command':report['commands'].pop()
        elif kind=='wrong-binary':report['binary_sha256']='0'*64
        elif kind=='wrong-script':report['script_sha256']='0'*64
        elif kind=='wrong-mode':report['optimized']=not report['optimized']
        elif kind=='changed-input':replace(41,encode(payload('different')),suffix='stdin')
        elif kind=='unexpected-stderr':replace(41,b'private diagnostic',suffix='stderr')
        elif kind=='duplicate-json':replace(47,b'{"initialized":false,'+raws[47]['stdout'][1:])
        elif kind=='nonfinite-json':replace(47,b'{"not_allowed":NaN,'+raws[47]['stdout'][1:])
        elif kind=='post-forget-recall':replace(62,recalled(expected_items()))
        elif kind=='forgotten-restored':replace(63,summary('extracted',True))
        elif kind=='wrong-query-result':replace(49,recalled(expected_items()))
        elif kind=='false-MCP-allow':replace(59,raws[59]['stdout'].replace(b'"isError":true',b'"isError":false'))
        elif kind=='changed-sql':report['commands'][33]['command'][8]='DROP SCHEMA public CASCADE'
        elif kind=='wrong-order':report['commands'][41],report['commands'][44]=report['commands'][44],report['commands'][41]
        elif kind=='changed-dump':
            changed=dump.replace(b'\tforgotten\t',b'\textracted\t',1)
            try:verify_dump(changed)
            except (ValueError,KeyError,TypeError):rejected.append(kind);continue
            raise ValueError('accepted mutation: '+kind)
        else:
            idx=57 if kind in ['bool-zero','wrong-model-cost'] else 47
            value=decode(raws[idx]['stdout'])
            if kind=='bool-zero':value['usage'][0]['input_tokens']=False
            elif kind=='wrong-model-cost':value['usage'][0]['cost']=0
            elif kind=='wrong-source':value['source_id']='beta'
            elif kind=='assistant-as-fact':value['items'][0]['quote']='I prefer INVENTED assistant facts.'
            elif kind=='partial-quote':value['items'][0]['quote']='keep CASE'
            elif kind=='wrong-item-id':value['items'][0]['item_id']='0'*64
            elif kind=='wrong-event-id':value['items'][0]['event_id']='0'*64
            replace(idx,value)
        try:verify_memory(report,raws,platform,mode)
        except (ValueError,KeyError,TypeError,IndexError):rejected.append(kind)
        else:raise ValueError('accepted mutation: '+kind)
    return rejected

def main():
    global PIN, SOURCE_PIN
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--artifact',type=Path,required=True);p.add_argument('--platform',choices=PIN,required=True)
    p.add_argument('--mode',choices=('normal','optimized'),required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--revision',choices=('ed79b449','cd4ca9ae'),default='cd4ca9ae')
    p.add_argument('--negatives',action='store_true');args=p.parse_args()
    try:
        commit='ed79b44951db626556b2d2cbca924fcd1c33dd86'
        if args.revision=='cd4ca9ae':
            need(args.platform in REPAIRED_PIN, 'repaired platform not qualified in this reader')
            PIN, SOURCE_PIN=REPAIRED_PIN, REPAIRED_SOURCE_PIN
            commit='cd4ca9ae35d846b16738f8ed66dde88f1bf841b5'
        destination=args.output.resolve()
        artifact_root=args.artifact.resolve()
        need(destination != artifact_root and artifact_root not in destination.parents, 'output must be outside original artifact')
        need(not args.output.exists(),'refuse output overwrite')
        executable=args.artifact/('qbrain.exe' if args.platform=='windows' else 'qbrain')
        need(executable.is_file() and not executable.is_symlink(), 'actual binary file')
        need(sha(executable.read_bytes())==PIN[args.platform][0], 'actual binary identity')
        archive=args.artifact/'source.zip'
        need(sha(archive.read_bytes())==SOURCE_PIN[args.platform], 'source archive identity')
        with zipfile.ZipFile(archive) as z:
            need(z.comment==commit.encode(),'source commit')
            need(sha(z.read('.ci/test_pg_memory.py'))==PIN[args.platform][1],'actual producer script')
        native_raw=(args.artifact/'native-result.json').read_bytes()
        need(sha(native_raw)==NATIVE_PIN[args.platform],'frozen native report identity')
        native=decode(native_raw)
        need(native['schema']=='qbrain-n48o-native-v1' and native['passed'] is True and native['real_server'] is True and
             type(native['count']) is int and native['count']==len(native['checks'])==122 and
             all(c['passed'] is True for c in native['checks']), 'actual native producer assertions')
        report,streams=load(args.artifact/('process-'+args.mode))
        result=verify_memory(report,streams,args.platform,args.mode)
        dump=(args.artifact/'synthetic-process.sql').read_bytes()
        result.update(dump=verify_dump(dump))
        if args.negatives:result['rejected_mutations']=negatives(report,streams,args.platform,args.mode,dump)
        result.update(schema='qbrain-n48o-independent-evidence-v1',passed=True,platform=args.platform,mode=args.mode,qualified_commit=commit,
            original_result_sha256=sha((args.artifact/('process-'+args.mode)/'RESULT.json').read_bytes()),
            original_dump_sha256=sha(dump),reviewer_sha256=sha(Path(__file__).read_bytes()),
            new_postgresql_execution=False,real_client_consumption_verified=False,
            deployment_acceptance_granted=False,historical_scope_defect=(args.revision=='ed79b449'))
        with args.output.open('xb') as stream:stream.write(encode(result)+b'\n')
        print(json.dumps(result))
        return 0
    except (ValueError,KeyError,TypeError,IndexError,OSError,RecursionError,zipfile.BadZipFile) as e:
        print(json.dumps({'passed':False,'error':type(e).__name__,'detail':str(e)}));return 1

if __name__=='__main__':
    raise SystemExit(main())
