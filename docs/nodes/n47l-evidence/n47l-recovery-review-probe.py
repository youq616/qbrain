"""Independent offline execution of the recovery's actual ID-bound preflight and publication tail.

The actual API helper and tag/release/asset/provenance checks run unchanged. Only
subprocess transport is doubled; draft-by-tag always behaves as published-only.
"""
import argparse,ast,contextlib,copy,hashlib,io,json,os,re,subprocess,sys,tempfile,types,zipfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ('workflow','original','fixture','evidence','report'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args()
def blocks(path):
    lines=path.read_text().splitlines();out=[]
    for i,line in enumerate(lines):
        if line=='        run: |':
            rows=[]
            for row in lines[i+1:]:
                if row and not row.startswith('          '):break
                rows.append(row[10:] if row else '')
            out.append('\n'.join(rows)+'\n')
    assert len(out)==2;return out
workflow_initial_sha=hashlib.sha256(a.workflow.read_bytes()).hexdigest()
original=blocks(a.original);recovery=blocks(a.workflow);code=recovery[1]
assert original[0]==recovery[0]
start='# Repeat critical fixed pins inside the publication step before I/O.'
old_before=original[1][original[1].index(start):original[1].index("need(api('releases/tags/'+tag,optional=True) is None,'Release already exists")]
new_before=code[code.index(start):code.index("need(tag_source()==source,'Existing tag must already resolve")]
assert old_before==new_before
ci_start='# Requery the exact run attempts, all jobs and their steps.'
old_ci=original[1][original[1].index(ci_start):original[1].index('provenance={')]
new_ci=code[code.index(ci_start):code.index('expected_provenance={')]
assert old_ci==new_ci
prefix=code[:code.index(start)]
prefix_ast=ast.parse(prefix);prefix_ast.body=[n for n in prefix_ast.body if not isinstance(n,(ast.Import,ast.ImportFrom))]
preflight=code[code.index("need(tag_source()==source,'Existing tag must already resolve"):code.index(ci_start)]
tail=code[code.index('expected_provenance={'):]
for part in (preflight,tail):ast.parse(part)
env=dict(re.findall(r"(?m)^      ([A-Z_0-9]+): '([^'\r\n]*)'$",a.workflow.read_text()))
env.update(GITHUB_RUN_ID='987654321',GITHUB_RUN_ATTEMPT='1',GITHUB_SHA='a'*40)
fixtures={f.name:f.read_bytes() for f in a.fixture.iterdir() if f.is_file()}
assert set(fixtures)=={'qbrain-windows-x64-multiterm.zip','PROVENANCE.json','SHA256SUMS.txt'}
metadata=json.loads((a.evidence/'CI-METADATA.json').read_text());readback=json.loads((a.evidence/'READBACK.json').read_text())
cases=('control_published_only_tag_semantics','missing_draft','already_public','wrong_release_id','wrong_source_target','wrong_release_tag','changed_tag_late','new_asset_id','wrong_asset_digest','missing_asset_digest','duplicate_asset_id','extra_asset','missing_asset','corrupt_product_download','json_instead_of_binary','corrupt_provenance_download','corrupt_checksums_download','replace_asset_after_readback','wrong_initial_commit','initial_run_claims_success','api_error_before_patch','connection_error_after_committed_patch')
results=[]
for case in cases:
    with tempfile.TemporaryDirectory(prefix='n47l-recovery-review-') as td:
        root=Path(td);evidence=root/'evidence';evidence.mkdir()
        scope={'hashlib':hashlib,'io':io,'json':json,'os':types.SimpleNamespace(environ=dict(env)),'re':re,'subprocess':None,'sys':sys,'zipfile':zipfile,'Path':Path}
        exec(compile(prefix_ast,'actual-recovery-prefix','exec'),scope)
        pins=scope['asset_pins'];source=scope['source'];tag=scope['tag'];release_id=scope['release_id']
        for name,row in pins.items():assert len(fixtures[name])==row['size'] and 'sha256:'+hashlib.sha256(fixtures[name]).hexdigest()==row['digest']
        release={'id':release_id,'tag_name':tag,'target_commitish':source,'name':scope['title'],'draft':True,'prerelease':True,'published_at':None,'html_url':'https://github.com/youq616/qbrain/releases/tag/'+tag,'assets':[{'name':name,'state':'uploaded',**row} for name,row in pins.items()]}
        remote={'release':release,'tag':source,'mutations':[],'downloads':[],'calls':[],'draft_by_tag_attempts':0,'get_release_count':0}
        if case=='missing_draft':remote['release']=None
        if case=='already_public':release.update(draft=False,published_at='2026-09-17T00:00:00Z')
        if case=='wrong_release_id':release['id']+=1
        if case=='wrong_source_target':release['target_commitish']='b'*40
        if case=='wrong_release_tag':release['tag_name']='other-tag'
        if case=='new_asset_id':release['assets'][0]['id']+=1
        if case=='wrong_asset_digest':release['assets'][0]['digest']='sha256:'+'b'*64
        if case=='missing_asset_digest':del release['assets'][0]['digest']
        if case=='duplicate_asset_id':release['assets'][1]['id']=release['assets'][0]['id']
        if case=='extra_asset':release['assets'].append({'id':999,'name':'extra','state':'uploaded','size':1,'digest':'sha256:'+'b'*64})
        if case=='missing_asset':release['assets'].pop()
        initial={'id':scope['initial_run'],'head_sha':scope['initial_commit'],'run_attempt':1,'status':'completed','conclusion':'failure','path':'.github/workflows/publish-reviewed-n47l.yml','repository':{'full_name':'youq616/qbrain'},'head_repository':{'full_name':'youq616/qbrain'}}
        if case=='wrong_initial_commit':initial['head_sha']='c'*40
        if case=='initial_run_claims_success':initial['conclusion']='success'
        def response(argv,value):return subprocess.CompletedProcess(argv,0,json.dumps(copy.deepcopy(value)).encode(),b'')
        def error(argv,status=404):return subprocess.CompletedProcess(argv,1,json.dumps({'message':'Not Found' if status==404 else 'Server error','status':str(status)}).encode(),f'gh: HTTP failure (HTTP {status})'.encode())
        def run(argv,**kwargs):
            assert argv[:2]==['gh','api'],'Forbidden external command: '+repr(argv)
            prefix_url='repos/youq616/qbrain/';assert argv[2].startswith(prefix_url)
            endpoint=argv[2][len(prefix_url):];method=argv[argv.index('--method')+1] if '--method' in argv else 'GET'
            remote['calls'].append({'path':endpoint,'method':method})
            if endpoint.startswith('releases/assets/'):
                assert method=='GET' and '--header' in argv and argv[argv.index('--header')+1]=='Accept: application/octet-stream'
                ident=int(endpoint.rsplit('/',1)[1]);name=next(n for n,pin in pins.items() if pin['id']==ident)
                assert ident not in remote['downloads'];remote['downloads'].append(ident)
                raw=fixtures[name]
                if case=='json_instead_of_binary':raw=b'{"id":123,"metadata":true}'
                if (case=='corrupt_product_download' and name==scope['product']) or (case=='corrupt_provenance_download' and name=='PROVENANCE.json') or (case=='corrupt_checksums_download' and name=='SHA256SUMS.txt'):raw=b'X'*len(raw)
                kwargs['stdout'].write(raw)
                if len(remote['downloads'])==3:
                    if case=='replace_asset_after_readback':release['assets'][0]['id']+=1
                    if case=='changed_tag_late':remote['tag']='d'*40
                return subprocess.CompletedProcess(argv,0,b'',b'')
            assert method in ('GET','PATCH'),'Forbidden remote mutation: '+method
            if method=='PATCH':
                assert endpoint==f'releases/{release_id}' and json.loads(kwargs['input'])=={'draft':False,'prerelease':True,'make_latest':'false'}
                assert release['draft'] is True
                remote['mutations'].append({'method':method,'path':endpoint})
                release.update(draft=False,published_at='2026-09-17T00:00:00Z')
                if case=='connection_error_after_committed_patch':return error(argv,500)
                return response(argv,release)
            if endpoint=='git/ref/tags/'+tag:return response(argv,{'ref':'refs/tags/'+tag,'object':{'type':'commit','sha':remote['tag']}})
            if endpoint==f'actions/runs/{scope["initial_run"]}':return response(argv,initial)
            if endpoint==f'releases/{release_id}':
                remote['get_release_count']+=1
                if case=='api_error_before_patch' and len(remote['downloads'])==3:return error(argv,500)
                return error(argv) if remote['release'] is None else response(argv,release)
            if endpoint=='releases/tags/'+tag:
                if remote['release'] is None or release['draft']:
                    remote['draft_by_tag_attempts']+=1;return error(argv)
                return response(argv,release)
            if endpoint=='releases/latest':return error(argv)
            raise AssertionError('Unplanned endpoint: '+endpoint)
        def forbidden(*args,**kwargs):raise AssertionError('Forbidden CLI mutation/check_output')
        scope['subprocess']=types.SimpleNamespace(run=run,check_output=forbidden,PIPE=subprocess.PIPE)
        scope.update(metadata=metadata,native=readback['report_summaries']['windows'],raw=fixtures[scope['product']],temp=root,evidence=evidence)
        output=io.StringIO();failure=None
        try:
            with contextlib.redirect_stdout(output):
                exec(compile(preflight,'actual-recovery-preflight','exec'),scope)
                exec(compile(tail,'actual-recovery-tail','exec'),scope)
        except Exception as exc:failure=type(exc).__name__+': '+str(exc)
        expected_patch=case in ('control_published_only_tag_semantics','connection_error_after_committed_patch')
        assert len(remote['mutations'])==int(expected_patch),(case,remote['mutations'],failure)
        assert remote['draft_by_tag_attempts']==0,(case,'draft tag endpoint used')
        assert bool(failure)==(case!='control_published_only_tag_semantics'),(case,failure)
        receipt=json.loads(output.getvalue()) if output.getvalue() else None
        if receipt:
            assert receipt['result']=='PUBLISHED' and receipt['publication_mode']=='RECOVER_FIXED_DRAFT'
            assert receipt['delivery_run']==receipt['initial_delivery_run']==35233247840 and receipt['initial_delivery_conclusion']=='failure'
            assert receipt['delivery_commit']==receipt['initial_delivery_commit']=='2f254681c31fd493fa9cb5ab14ae089608f8a4ad'
            assert receipt['recovery_run']==987654321 and receipt['recovery_commit']=='a'*40 and receipt['original_assets_replaced'] is False
            assert receipt['original_provenance_sha256']=='6cc243b432dbb444f83f9983f4294d0a4c516edc2ad0180b9a2940cc810cd59a'
        results.append({'case':case,'failure':failure,'release_mutations':remote['mutations'],'asset_ids_downloaded':remote['downloads'],'draft_by_tag_attempts':remote['draft_by_tag_attempts'],'final_draft':None if remote['release'] is None else release['draft'],'receipt_result':None if receipt is None else receipt['result'],'original_provenance_preserved':True,'expected_outcome_observed':True})
assert hashlib.sha256(a.workflow.read_bytes()).hexdigest()==workflow_initial_sha,'Workflow changed during review execution'
report={'result':'PASS_RECOVERY_OFFLINE_CONTROL_SCOPED','workflow_sha256':hashlib.sha256(a.workflow.read_bytes()).hexdigest(),'original_workflow_sha256':hashlib.sha256(a.original.read_bytes()).hexdigest(),'case_count':len(results),'network_or_actual_publication':False,'scope':'Unchanged real API helpers plus ID-bound recovery preflight/tail; transport doubled. No fresh CI execution.','preserved_original_sections':{'first_pin_guard_byte_identical':True,'source_review_and_evidence_gates_byte_identical':True,'live_ci_seven_artifact_and_1094_verifier_segment_byte_identical':True},'fixture':{'product':'original authenticated CI inner ZIP','provenance_and_checksums':'reconstructed original bytes verified against live draft asset hashes; not fetched downloads'},'results':results}
with a.report.open('x') as f:f.write(json.dumps(report,indent=2)+'\n')
print(json.dumps({'result':report['result'],'cases':report['case_count'],'workflow_sha256':report['workflow_sha256']}))
