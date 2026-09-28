"""Independent N48O public-relation repair evidence reader; no SQL/executable runs.

Specific to cd4ca9ae's native scope driver. Recomputes public evidence identities,
exact entry-point coverage, all seven before/after states and the parent's observed
policy bypass. Original artifact authentication remains an external responsibility.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import zipfile

COMMIT = b'cd4ca9ae35d846b16738f8ed66dde88f1bf841b5'
DRIVER_BLOB = '473465441818d71f1c451bbcb11c9dab586dacfd'
TABLES = ('sources','pages','config','memory_module','memory_events','memory_items','memory_attempts')
QUOTES = ('I prefer exact public-scope evidence.',
          'I decided to retain only my complete statement.')
COLUMNS = {
 'sources': 'id name local_path config_json created_at last_sync_at',
 'pages': 'id source_id slug type title body frontmatter_json content_hash created_at updated_at deleted_at source_kind ingested_via ingested_at pages_ftv',
 'config': 'key value', 'memory_module': 'version',
 'memory_events': 'event_id source_id session_id fragment_id payload_hash page_id page_hash automatic capture_mode expires_at status method last_error lease_token lease_until attempts created_at',
 'memory_items': 'item_id event_id category quote message_index expires_at created_at',
 'memory_attempts': 'attempt_id event_id method status provider_attempts input_tokens output_tokens elapsed_ms created_at'}
CAP = 4*1024*1024

def need(ok, label):
    if not ok:raise ValueError(label)

def enc(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',', ':'),allow_nan=False).encode()

def sha(raw):return hashlib.sha256(raw).hexdigest()

def eq(actual,expected,label):need(enc(actual)==enc(expected),label)

def strict(raw):
    need(len(raw)<=CAP,'bounded JSON')
    def unique(pairs):
        out={}
        for k,v in pairs:
            need(k not in out,'duplicate JSON key');out[k]=v
        return out
    def invalid(_):raise ValueError('nonfinite JSON')
    value=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique,parse_constant=invalid)
    # Canonicalization rejects nonfinite numeric overflows and invalid Unicode too.
    enc(value)
    return value

def labels(parent=False):
    initial=['real-pg-backend','disposable-db','non-superuser']
    if parent:
        return initial+['legacy-current-schema-public','legacy-shadow-policy-accepted',
         'legacy-public-write-observed','legacy-public-policy-still-off','disposable-db','non-superuser']
    initial+=['fresh-no-optional-schema','preinit-shadow:exact-error','preinit-no-ddl',
              'unrelated-temp-allowed','public-off-respected','whole-user-evidence','scope-beta-isolation']
    for table in TABLES:
        initial += [table+':schema-alone-insufficient']
        initial += [table+':'+action+':exact-error' for action in ('read','status','capture','manual','extract','model','drain','forget')]
        initial += [table+':no-provider',table+':idle-on-refusal',table+':public-state-identical']
    return initial+['effective-public-first-allowed','caller-search-path-not-overwritten',
        'conflicting-temp-policy:exact-error','off-policy-state-preserved','provider-outside-write-transaction',
        'post-provider-context-recheck:exact-error','single-synthetic-callback','no-late-items-published',
        'post-provider-idle','post-provider-forget-wins','caller-transaction:exact-error','caller-still-active',
        'caller-rollback-retained','failed-caller-transaction:exact-error','failed-transaction-not-committed',
        'normal-recall-after-recovery','disposable-db','non-superuser']

def identity(fragment='normal'):
    messages=[{'role':'user','content':QUOTES[0]},
              {'role':'assistant','content':'I prefer untrusted assistant suggestions.'},
              {'role':'user','content':QUOTES[1]}]
    body=enc({'messages':messages,'expires_at':0})
    event=sha(enc(['qbrain-memory-v1','scope-alpha','scope-session',fragment,sha(body)]))
    return event,body

def state(snapshot):
    need(type(snapshot) is dict and set(snapshot)==set(TABLES),'all seven public tables')
    need(all(type(rows) is list and all(type(row) is dict for row in rows) for rows in snapshot.values()),'table row shapes')
    for table,columns in COLUMNS.items():
        need(all(set(row)==set(columns.split()) for row in snapshot[table]),'complete column set '+table)
    eq(snapshot['memory_module'],[{'version':1}],'module version exact integer')
    need(len(snapshot['memory_events'])==len(snapshot['pages'])==1,'one event and source page')
    event,body=identity()
    row=snapshot['memory_events'][0];page=snapshot['pages'][0]
    for k,v in {'event_id':event,'source_id':'scope-alpha','session_id':'scope-session','fragment_id':'normal',
      'payload_hash':sha(body),'automatic':1,'capture_mode':'salient','expires_at':0,'status':'extracted',
      'method':'explicit-markers-v1','last_error':'','lease_token':'','lease_until':0,'attempts':1}.items():
        eq(row[k],v,'fixed event '+k)
    need(type(row['created_at']) is int and row['created_at']>=0,'event creation time')
    need(type(row['page_id']) is int and type(page['id']) is int and row['page_id']==page['id'],'page identity')
    need(page['body'].encode()==body and page['source_id']=='scope-alpha' and page['slug']=='sessions/'+event,'exact evidence source')
    need(row['page_hash']==page['content_hash'] and page['deleted_at'] is None,'live page version bound')
    expected={}
    for idx,category,quote in [(0,'preference',QUOTES[0]),(2,'decision',QUOTES[1])]:
        key=sha(event.encode()+enc(dict(message_index=idx,category=category,quote=quote)))
        expected[key]=(idx,category,quote)
    need(len(snapshot['memory_items'])==2,'two complete user statements')
    actual=set()
    for item in snapshot['memory_items']:
        key=item['item_id'];need(key in expected and key not in actual,'item identity');actual.add(key)
        idx,category,quote=expected[key]
        for k,v in {'event_id':event,'message_index':idx,'category':category,'quote':quote,'expires_at':0}.items():
            eq(item[k],v,'whole user item '+k)
    need(len(snapshot['memory_attempts'])==1,'single completed attempt')
    attempt=snapshot['memory_attempts'][0]
    for k,v in {'event_id':event,'method':'local','status':'completed','provider_attempts':0,'input_tokens':0,'output_tokens':0}.items():
        eq(attempt[k],v,'attempt '+k)
    need(type(attempt['elapsed_ms']) is int and attempt['elapsed_ms']>=0,'local elapsed')
    config=snapshot['config'];need(len({r['key'] for r in config})==len(config),'unique policy keys')
    policies={r['key']:r['value'] for r in config}
    need(policies['memory.writeback']=='salient' and policies['embed.auto']=='false','public policy fixed')
    sources={r['id'] for r in snapshot['sources']}
    need({'scope-alpha','scope-beta'}<=sources,'both logical sources')

def verify(raw,parent=False):
    report=strict(raw)
    need(set(report)=={'schema','mode','passed','real_server','paid_provider_requests','checks','count','records'},'exact report fields')
    need(report['schema']=='qbrain-n48o-scope-review-v1','schema')
    need(report['mode']==('parent-characterization' if parent else 'fixed-regression'),'scope mode')
    need(report['passed'] is True and report['real_server'] is True,'original native completed')
    need(type(report['paid_provider_requests']) is int and report['paid_provider_requests']==0,'no paid calls')
    want=labels(parent)
    need(type(report['count']) is int and report['count']==len(report['checks'])==len(want),'exact assertion inventory')
    for item,name in zip(report['checks'],want):eq(item,dict(name=name,passed=True),'exact assertion '+name)
    if parent:
        need(len(report['records'])==1,'one observed parent counterexample')
        row=report['records'][0]
        need(set(row)=={'case','observed','public_policy','temporary_policy'},'parent fields')
        need(row['case']=='temporary-policy-shadow' and row['public_policy']=='off' and row['temporary_policy']=='salient','contradictory policies observed')
        event,_=identity('parent-policy')
        eq(row['observed'],dict(event_id=event,source_id='scope-alpha',status='archived',evidence_live=True,
              duplicate=False,attempts=0,archived=True,extracted=False,provider_requests=0),'observed old acceptance, not good behavior')
    else:
        need(len(report['records'])==7,'seven shadowed relations')
        first=None
        for row,table in zip(report['records'],TABLES):
            need(set(row)=={'case','before','after'} and row['case']==table,'exact relation order')
            eq(row['before'],row['after'],'all public values unchanged after refusals')
            state(row['before'])
            if first is None:first=row['before']
            eq(row['before'],first,'same frozen state across seven scenarios')
    return report

def negatives(raw,parent_raw=None):
    original=verify(raw);rejected=[]
    kinds=['bool-count','bool-zero','wrong-mode','false-server','missing-check','changed-check-label',
           'reordered-checks','missing-relation','duplicated-relation','changed-after','coordinated-quote',
           'coordinated-source','coordinated-status','coordinated-bool','coordinated-item-id','coordinated-missing-column','extra-field',
           'duplicate-json','nonfinite-json']
    for kind in kinds:
        r=copy.deepcopy(original)
        if kind=='bool-count':r['count']=True
        elif kind=='bool-zero':r['paid_provider_requests']=False
        elif kind=='wrong-mode':r['mode']='parent-characterization'
        elif kind=='false-server':r['real_server']=False
        elif kind=='missing-check':r['checks'].pop()
        elif kind=='changed-check-label':r['checks'][10]['name']='unverified'
        elif kind=='reordered-checks':r['checks'][0],r['checks'][1]=r['checks'][1],r['checks'][0]
        elif kind=='missing-relation':r['records'].pop()
        elif kind=='duplicated-relation':r['records'][1]=copy.deepcopy(r['records'][0])
        elif kind=='changed-after':r['records'][0]['after']['pages'][0]['body']='changed evidence'
        elif kind.startswith('coordinated-'):
            # Mutate BOTH before/after and every record, so equality alone cannot catch it.
            for row in r['records']:
                for key in ('before','after'):
                    s=row[key]
                    if kind=='coordinated-quote':s['memory_items'][0]['quote']='I prefer untrusted assistant suggestions.'
                    elif kind=='coordinated-source':s['memory_events'][0]['source_id']='scope-beta'
                    elif kind=='coordinated-status':s['memory_events'][0]['status']='forgotten'
                    elif kind=='coordinated-bool':s['memory_events'][0]['attempts']=True
                    elif kind=='coordinated-item-id':s['memory_items'][0]['item_id']='0'*64
                    elif kind=='coordinated-missing-column':del s['pages'][0]['updated_at']
        elif kind=='extra-field':r['real_client_verified']=True
        candidate=enc(r)
        if kind=='duplicate-json':candidate=b'{"passed":false,'+candidate[1:]
        elif kind=='nonfinite-json':candidate=b'{"unsafe":NaN,'+candidate[1:]
        try:verify(candidate)
        except (ValueError,KeyError,TypeError,IndexError):rejected.append(kind)
        else:raise ValueError('accepted mutation '+kind)
    if parent_raw is not None:
        for name in ('parent-policy-rewritten','parent-failure-hidden'):
            r=copy.deepcopy(verify(parent_raw,True))
            if name=='parent-policy-rewritten':r['records'][0]['public_policy']='salient'
            else:r['records'][0]['observed']['status']='skipped'
            try:verify(enc(r),True)
            except (ValueError,KeyError,TypeError,IndexError):rejected.append(name)
            else:raise ValueError('accepted mutation '+name)
    return rejected

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--negatives',action='store_true')
    args=parser.parse_args()
    try:
        destination=args.output.resolve()
        artifact_root=args.artifact.resolve()
        need(destination != artifact_root and artifact_root not in destination.parents, 'output must be outside original artifact')
        need(not args.output.exists(),'refuse output overwrite')
        with zipfile.ZipFile(args.artifact/'source.zip') as z:
            need(z.comment==COMMIT,'fixed repaired candidate')
            source=z.read('tests/test_pg_memory_scope.cpp').replace(b'\r\n',b'\n')
            need(hashlib.sha1(b'blob '+str(len(source)).encode()+b'\0'+source).hexdigest()==DRIVER_BLOB,'qualified scope driver source')
        raw=(args.artifact/'scope-result.json').read_bytes()
        r=verify(raw)
        parent=args.artifact/'parent-scope-result.json'
        prior=parent.read_bytes() if parent.exists() else None
        if prior is not None:verify(prior,True)
        value=dict(schema='qbrain-n48o-independent-scope-readback-v1',passed=True,
            fixed_commit=COMMIT.decode(),native_scope_checks=len(r['checks']),relations=7,
            full_before_after_snapshots=14,parent_characterization_checked=prior is not None,
            parent_scope_checks=9 if prior is not None else None,old_candidate_accepted_for_deployment=False,
            original_scope_result_sha256=sha(raw),parent_result_sha256=sha(prior) if prior is not None else None,
            reviewer_sha256=sha(Path(__file__).read_bytes()),new_postgresql_execution=False)
        if args.negatives:value['rejected_mutations']=negatives(raw,prior)
        with args.output.open('xb') as f:f.write(enc(value)+b'\n')
        print(json.dumps(value));return 0
    except (ValueError,KeyError,TypeError,IndexError,OSError,zipfile.BadZipFile,RecursionError) as e:
        print(json.dumps({'passed':False,'error':type(e).__name__,'detail':str(e)}));return 1

if __name__=='__main__':raise SystemExit(main())
