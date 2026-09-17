"""Offline control/fault test of the unchanged template's publication tail."""
import ast,copy,contextlib,hashlib,io,json,tempfile
from pathlib import Path

path=Path('/workspace/scratch/8ee4dd18bee0/n47l-publish-template.yml')
lines=path.read_text().splitlines();blocks=[]
for index,line in enumerate(lines):
    if line=='        run: |':
        body=[]
        for row in lines[index+1:]:
            if row and not row.startswith('          '):break
            body.append(row[10:] if row else '')
        blocks.append('\n'.join(body)+'\n')
code=blocks[1]
program=ast.parse(code)
helpers=ast.Module(body=[node for node in program.body if isinstance(node,ast.FunctionDef) and node.name in {'need','sha','positive_int','read'}],type_ignores=[])
tail=code[code.index("need(api('releases/tags/'+tag,optional=True) is None,'Release appeared during verification") :]
results=[]
for tamper in (False,True):
    with tempfile.TemporaryDirectory(prefix='n47l-publication-offline-') as folder:
        root=Path(folder);release_dir=root/'release';release_dir.mkdir();evidence=root/'evidence';evidence.mkdir()
        product='qbrain-windows-x64-multiterm.zip';assets=[product,'PROVENANCE.json','SHA256SUMS.txt']
        initial={product:b'original fixed CI package bytes',assets[1]:b'{"source":"fixed"}\n',assets[2]:b'original fixed checksums\n'}
        for name,data in initial.items():(release_dir/name).write_bytes(data)
        remote={'release':None,'bytes':{},'patch_count':0}
        scope={'hashlib':hashlib,'Path':Path,'json':json,'cap':128*1024*1024,'repo':'youq616/qbrain','source':'17e9a435f94e45b3ca22d3da062ba4683c135c4b','tag':'multiterm-preview-17e9a435','title':'reviewed N47L','temp':root,'release_dir':release_dir,'evidence':evidence,'assets':assets,'product':product,'notes':'reviewed','provenance':{'package_sha256':hashlib.sha256(initial[product]).hexdigest()}}
        exec(compile(helpers,'template-helpers','exec'),scope)
        def tag_source():return scope['source']
        def api(endpoint,*,optional=False,method='GET',body=None):
            if endpoint=='releases/latest':return None
            if endpoint in ('releases/tags/'+scope['tag'],'releases/123'):
                if method=='PATCH':
                    remote['patch_count']+=1
                    remote['release'].update(draft=False,prerelease=True,published_at='2026-09-17T00:00:00Z')
                return copy.deepcopy(remote['release'])
            raise AssertionError('Unexpected API call: '+endpoint)
        def gh(*args):
            if args[:2]==('release','create'):
                remote['bytes']=dict(initial)
                remote['release']={'id':123,'draft':True,'prerelease':True,'tag_name':scope['tag'],'target_commitish':scope['source'],'name':scope['title'],'html_url':'https://github.com/youq616/qbrain/releases/tag/'+scope['tag'],'assets':[{'id':100+i,'name':name,'state':'uploaded','size':len(raw),'digest':'sha256:'+hashlib.sha256(raw).hexdigest()} for i,(name,raw) in enumerate(initial.items())]}
                return b''
            if args[:2]==('release','download'):
                download=Path(args[args.index('--dir')+1]);download.mkdir()
                for name,raw in remote['bytes'].items():(download/name).write_bytes(raw)
                if tamper:
                    remote['bytes'][product]=b'X'*len(initial[product])
                    row=remote['release']['assets'][0];row['id']=900;row['digest']='sha256:'+hashlib.sha256(remote['bytes'][product]).hexdigest()
                return b''
            raise AssertionError('Unexpected gh call')
        scope.update(tag_source=tag_source,api=api,gh=gh)
        output=io.StringIO()
        failure=None
        try:
            with contextlib.redirect_stdout(output):exec(compile(tail,'original-template-publication-tail','exec'),scope)
        except Exception as exc:failure=type(exc).__name__+': '+str(exc)
        result={'replacement_after_download':tamper,'failure':failure,'publication_patch_calls':remote['patch_count'],'published':bool(remote['release'] and not remote['release']['draft']),'original_package_sha256':hashlib.sha256(initial[product]).hexdigest(),'remote_package_sha256':hashlib.sha256(remote['bytes'].get(product,b'')).hexdigest(),'receipt_result':json.loads(output.getvalue()).get('result') if output.getvalue() else None}
        results.append(result)
report={'template_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'network_or_actual_publication':False,'results':results}
Path('/workspace/scratch/8ee4dd18bee0/n47l-publication-asset-probe.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
