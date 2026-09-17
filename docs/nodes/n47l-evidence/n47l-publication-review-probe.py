"""Offline execution of the template's unchanged publication tail with REST/gh doubles.

Only remote operations are mocked. The actual release state checks, file readback,
asset binding and publication sequence are extracted from the supplied template.
No network, GitHub action or real release operation is performed.
"""
import argparse
import ast
import contextlib
import copy
import hashlib
import io
import json
import tempfile
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--template',type=Path,required=True)
parser.add_argument('--report',type=Path,required=True)
parser.add_argument('--expect',choices=('fixed','vulnerable'),default='fixed')
args=parser.parse_args()
lines=args.template.read_text().splitlines();blocks=[]
for index,line in enumerate(lines):
    if line=='        run: |':
        body=[]
        for row in lines[index+1:]:
            if row and not row.startswith('          '):break
            body.append(row[10:] if row else '')
        blocks.append('\n'.join(body)+'\n')
assert len(blocks)==2
code=blocks[1]
program=ast.parse(code)
helpers=ast.Module(body=[node for node in program.body if isinstance(node,ast.FunctionDef) and node.name in {'need','sha','positive_int','read'}],type_ignores=[])
tail=code[code.index("need(api('releases/tags/'+tag,optional=True) is None,'Release appeared during verification") :]
expected_init=code[code.index('expected_assets={}'):code.index("notes=(")] if 'expected_assets={}' in code else ''
cases=('existing_correct_tag','new_tag','replacement_after_download','same_bytes_new_asset_id','missing_digest','duplicate_asset_id','corrupt_download','preexisting_release','changed_tag_before_patch','api_error_before_patch','post_patch_api_error')
results=[]
for case in cases:
    with tempfile.TemporaryDirectory(prefix='n47l-publication-offline-') as folder:
        root=Path(folder);release_dir=root/'release';release_dir.mkdir();evidence=root/'evidence';evidence.mkdir()
        product='qbrain-windows-x64-multiterm.zip';assets=[product,'PROVENANCE.json','SHA256SUMS.txt']
        initial={product:b'original fixed CI package bytes',assets[1]:b'{"source":"fixed"}\n',assets[2]:b'original fixed checksums\n'}
        for name,data in initial.items():(release_dir/name).write_bytes(data)
        fixed_source='17e9a435f94e45b3ca22d3da062ba4683c135c4b'
        remote={'release':{'id':123,'draft':True} if case=='preexisting_release' else None,'bytes':{},'patch_count':0,'create_count':0,'tag':None if case=='new_tag' else fixed_source}
        scope={'hashlib':hashlib,'Path':Path,'json':json,'cap':128*1024*1024,'repo':'youq616/qbrain','source':fixed_source,'tag':'multiterm-preview-17e9a435','title':'reviewed N47L','temp':root,'release_dir':release_dir,'evidence':evidence,'assets':assets,'product':product,'notes':'reviewed','provenance':{'package_sha256':hashlib.sha256(initial[product]).hexdigest()}}
        exec(compile(helpers,'template-helpers','exec'),scope)
        if expected_init:exec(compile(expected_init,'template-expected-assets','exec'),scope)
        def tag_source():return remote['tag']
        def api(endpoint,*,optional=False,method='GET',body=None):
            if endpoint=='releases/latest':return None
            if endpoint=='git/refs' and method=='POST':
                assert remote['tag'] is None and body=={'ref':'refs/tags/'+scope['tag'],'sha':fixed_source}
                remote['tag']=body['sha'];return {'ref':body['ref'],'object':{'sha':body['sha']}}
            if endpoint in ('releases/tags/'+scope['tag'],'releases/123'):
                if endpoint=='releases/123' and method=='GET' and case=='api_error_before_patch':raise RuntimeError('Injected GET failure before publication')
                if method=='PATCH':
                    assert endpoint=='releases/123' and body=={'draft':False,'prerelease':True,'make_latest':'false'}
                    remote['patch_count']+=1;remote['release'].update(draft=False,prerelease=True,published_at='2026-09-17T00:00:00Z')
                    if case=='post_patch_api_error':raise RuntimeError('Injected connection failure after remote PATCH committed')
                return copy.deepcopy(remote['release'])
            raise AssertionError('Unexpected API call: '+endpoint)
        def gh(*argv):
            if argv[:2]==('release','create'):
                assert '--draft' in argv and '--verify-tag' in argv and '--prerelease' in argv and '--latest=false' in argv
                assert remote['release'] is None
                remote['create_count']+=1;remote['bytes']=dict(initial)
                remote['release']={'id':123,'draft':True,'prerelease':True,'tag_name':scope['tag'],'target_commitish':scope['source'],'name':scope['title'],'html_url':'https://github.com/youq616/qbrain/releases/tag/'+scope['tag'],'assets':[{'id':100+i,'name':name,'state':'uploaded','size':len(raw),'digest':'sha256:'+hashlib.sha256(raw).hexdigest()} for i,(name,raw) in enumerate(initial.items())]}
                if case=='missing_digest':del remote['release']['assets'][0]['digest']
                if case=='duplicate_asset_id':remote['release']['assets'][1]['id']=remote['release']['assets'][0]['id']
                return b''
            if argv[:2]==('release','download'):
                download=Path(argv[argv.index('--dir')+1]);download.mkdir()
                for name,raw in remote['bytes'].items():(download/name).write_bytes(raw)
                if case=='replacement_after_download':
                    remote['bytes'][product]=b'X'*len(initial[product]);row=remote['release']['assets'][0];row['id']=900;row['digest']='sha256:'+hashlib.sha256(remote['bytes'][product]).hexdigest()
                if case=='same_bytes_new_asset_id':remote['release']['assets'][0]['id']=900
                if case=='corrupt_download':(download/product).write_bytes(b'Y'*len(initial[product]))
                if case=='changed_tag_before_patch':remote['tag']='f'*40
                return b''
            raise AssertionError('Unexpected gh call')
        scope.update(tag_source=tag_source,api=api,gh=gh)
        output=io.StringIO();failure=None
        try:
            with contextlib.redirect_stdout(output):exec(compile(tail,'original-template-publication-tail','exec'),scope)
        except Exception as exc:failure=type(exc).__name__+': '+str(exc)
        published=bool(remote['release'] and remote['release']['draft'] is False)
        expected_publish=case in ('existing_correct_tag','new_tag') or case=='post_patch_api_error' or (args.expect=='vulnerable' and case in ('replacement_after_download','same_bytes_new_asset_id','missing_digest','duplicate_asset_id'))
        expected_failure=case=='post_patch_api_error' or not expected_publish
        assert published==expected_publish and bool(failure)==expected_failure,(case,failure,published)
        assert remote['patch_count']==int(expected_publish)
        if case not in ('post_patch_api_error','preexisting_release') and expected_failure:assert remote['release']['draft'] is True
        result={'case':case,'failure':failure,'publication_patch_calls':remote['patch_count'],'release_create_calls':remote['create_count'],'published':published,'retained_draft':bool(remote['release'] and remote['release']['draft'] is True),'original_package_sha256':hashlib.sha256(initial[product]).hexdigest(),'remote_package_sha256':hashlib.sha256(remote['bytes'].get(product,b'')).hexdigest(),'receipt_result':json.loads(output.getvalue()).get('result') if output.getvalue() else None,'expected_outcome_observed':True}
        results.append(result)
report={'template_sha256':hashlib.sha256(args.template.read_bytes()).hexdigest(),'network_or_actual_publication':False,'scope':'Original publication tail with offline remote-state doubles; no CI gates or live service executed','expectation':args.expect,'case_count':len(results),'result':'PASS_EXPECTED_OUTCOMES' if args.expect=='fixed' else 'REPRODUCED_INITIAL_DEFECT','results':results}
with args.report.open('x') as stream:stream.write(json.dumps(report,indent=2)+'\n')
print(json.dumps({'result':report['result'],'cases':report['case_count'],'template_sha256':report['template_sha256']}))
