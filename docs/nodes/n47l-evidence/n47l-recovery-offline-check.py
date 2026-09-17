"""Exercise the real fixed-draft recovery tail with offline API/asset fixtures.

The product fixture is the original CI inner ZIP. PROVENANCE/SHA256SUMS fixtures
were reconstructed from the original workflow and matched to observed draft
size/digest pins; they are not claimed as downloads from the release.
"""
import argparse
import ast
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from unittest.mock import patch


def blocks(text):
    lines=text.splitlines();found=[]
    for index,line in enumerate(lines):
        if line=='        run: |':
            body=[]
            for row in lines[index+1:]:
                if row and not row.startswith('          '):break
                body.append(row[10:] if row else '')
            found.append('\n'.join(body)+'\n')
    assert len(found)==2
    return found


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workflow',type=Path,required=True);p.add_argument('--original',type=Path,required=True)
    p.add_argument('--fixture',type=Path,required=True);p.add_argument('--metadata',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);args=p.parse_args()
    if args.report.exists():p.error('report must be a new path')
    data=args.workflow.read_bytes();text=data.decode();original=args.original.read_text();code=blocks(text)[1]
    tree=ast.parse(code);init=[]
    for node in tree.body:
        if isinstance(node,ast.FunctionDef):break
        init.append(node)
    helpers=[n for n in tree.body if isinstance(n,ast.FunctionDef) and
             n.name in {'need','sha','positive_int','unique','obj','read','asset_metadata','release_metadata'}]
    expected=next(n for n in tree.body if isinstance(n,ast.Assign) and
                  any(isinstance(t,ast.Name) and t.id=='expected_provenance' for t in n.targets))
    tail=code[code.index('# Re-read the same draft immediately before downloading its fixed IDs.'):]
    for begin,old_end,new_end in (
            ('          # Repeat critical fixed pins',"          need(api('releases/tags/'+tag,optional=True) is None,'Release already exists; no overwrite is allowed')",
             "          need(tag_source()==source,'Existing tag must already resolve to the exact candidate')"),
            ('          # Requery the exact run attempts','          provenance={','          expected_provenance={')):
        assert original[original.index(begin):original.index(old_end)]==text[text.index(begin):text.index(new_end)]
    mutations=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and
               n.func.id=='api' and any(k.arg=='method' and isinstance(k.value,ast.Constant) and k.value.value!='GET' for k in n.keywords)]
    assert len(mutations)==1 and next(k.value.value for k in mutations[0].keywords if k.arg=='method')=='PATCH'
    env={m[1]:m[2] for line in text.splitlines() if (m:=re.fullmatch(r"      ([A-Z_0-9]+): '([^']*)'",line))}
    env.update(GITHUB_RUN_ID='900000001',GITHUB_RUN_ATTEMPT='1',GITHUB_SHA='a'*40)
    with patch.dict(os.environ,env,clear=True):exec(compile(blocks(text)[0],'recovery-pin-guard','exec'),{})
    cases=('control','wrong_release_id','missing_draft','already_public','wrong_source','wrong_tag','missing_asset',
           'new_asset_id_same_bytes','duplicate_asset_id','missing_digest','download_json','wrong_download_bytes',
           'replaced_after_download','changed_tag_before_patch','published_before_patch','wrong_ci_inner_bytes')
    results=[]
    for case in cases:
        with tempfile.TemporaryDirectory(prefix='n47l-recovery-offline-') as folder,patch.dict(os.environ,env,clear=True):
            root=Path(folder);evidence=root/'evidence';evidence.mkdir();scope={}
            exec(compile(ast.Module(body=init+helpers,type_ignores=[]),'actual-recovery-initializers','exec'),scope)
            original_bytes={name:(args.fixture/name).read_bytes() for name in scope['assets']}
            for name,raw in original_bytes.items():
                pin=scope['asset_pins'][name]
                assert len(raw)==pin['size'] and 'sha256:'+hashlib.sha256(raw).hexdigest()==pin['digest']
            old_provenance=json.loads(original_bytes['PROVENANCE.json'])
            scope.update(temp=root,evidence=evidence,raw=original_bytes[scope['product']],
                         metadata=json.loads(args.metadata.read_text()),
                         native={'multiterm-unit':old_provenance['multiterm_unit'],'multiterm-process':old_provenance['multiterm_process']})
            exec(compile(ast.Module(body=[expected],type_ignores=[]),'actual-original-provenance-expectation','exec'),scope)
            assert scope['expected_provenance']==old_provenance
            release={'id':scope['release_id'],'draft':True,'prerelease':True,'published_at':None,'tag_name':scope['tag'],
                     'target_commitish':scope['source'],'name':scope['title'],'html_url':'https://github.com/youq616/qbrain/releases/tag/'+scope['tag'],
                     'assets':[dict(name=name,state='uploaded',**pin) for name,pin in scope['asset_pins'].items()]}
            remote={'release':release,'downloads':0,'patches':0,'calls':[]}
            if case=='wrong_release_id':release['id']+=1
            if case=='already_public':release.update(draft=False,published_at='2026-09-17T00:00:00Z')
            if case=='wrong_source':release['target_commitish']='b'*40
            if case=='wrong_tag':release['tag_name']='wrong-tag'
            if case=='missing_asset':release['assets'].pop()
            if case=='new_asset_id_same_bytes':release['assets'][0]['id']+=1
            if case=='duplicate_asset_id':release['assets'][1]['id']=release['assets'][0]['id']
            if case=='missing_digest':release['assets'][0].pop('digest')
            if case=='wrong_ci_inner_bytes':scope['raw']=scope['raw']+b'changed'
            def api(endpoint,*,optional=False,method='GET',body=None):
                remote['calls'].append([method,endpoint])
                if endpoint=='releases/latest':return {'id':1}
                if endpoint=='releases/tags/'+scope['tag']:
                    if release['draft']:raise RuntimeError('The by-tag endpoint does not return draft releases')
                    return copy.deepcopy(release)
                assert endpoint=='releases/'+str(scope['release_id'])
                if case=='missing_draft':raise RuntimeError('Fixed draft ID was not found')
                if method=='PATCH':
                    assert body=={'draft':False,'prerelease':True,'make_latest':'false'}
                    remote['patches']+=1;release.update(draft=False,published_at='2026-09-17T00:00:00Z')
                else:assert method=='GET'
                return copy.deepcopy(release)
            def download(command,*,stdout,stderr,check,timeout):
                assert command[:2]==['gh','api'] and command[-2:]==['--header','Accept: application/octet-stream']
                ident=int(command[2].rsplit('/',1)[1])
                assert command[2]=='repos/youq616/qbrain/releases/assets/'+str(ident)
                name=next(name for name,pin in scope['asset_pins'].items() if pin['id']==ident)
                raw=original_bytes[name]
                if case=='download_json' and name==scope['product']:raw=b'{"metadata":"not asset bytes"}'
                if case=='wrong_download_bytes' and name==scope['product']:raw=b'X'*len(raw)
                stdout.write(raw);remote['downloads']+=1
                if remote['downloads']==3:
                    if case=='replaced_after_download':release['assets'][0]['id']+=1
                    if case=='published_before_patch':release.update(draft=False,published_at='2026-09-17T00:00:00Z')
                return subprocess.CompletedProcess(command,0)
            def tag_source():return 'b'*40 if case=='changed_tag_before_patch' and remote['downloads']==3 else scope['source']
            scope.update(api=api,tag_source=tag_source)
            output=io.StringIO();error=None
            try:
                with patch.object(subprocess,'run',side_effect=download),contextlib.redirect_stdout(output):
                    exec(compile(tail,'actual-fixed-draft-recovery-tail','exec'),scope)
            except Exception as exc:error=type(exc).__name__+': '+str(exc)
            if case=='control':
                assert error is None,error
                receipt=json.loads(output.getvalue())
                assert remote['patches']==1 and receipt['delivery_run']==35233247840 and receipt['recovery_run']==900000001
                assert receipt['delivery_commit']=='2f254681c31fd493fa9cb5ab14ae089608f8a4ad' and receipt['original_assets_replaced'] is False
                assert receipt['initial_delivery_conclusion']=='failure' and receipt['asset_pins']==scope['asset_pins']
                for name,raw in original_bytes.items():assert (evidence/'release-assets'/name).read_bytes()==raw
            else:assert error is not None and remote['patches']==0,(case,error,remote['patches'])
            results.append({'case':case,'result':'PASS','recovery_patch_calls':remote['patches'],'downloads':remote['downloads'],
                            'expected_rejection':error,'api_calls':remote['calls']})
    report={'result':'PASS_OFFLINE','workflow_sha256':hashlib.sha256(data).hexdigest(),
            'scope':'Actual extracted recovery tail with mocked by-ID API and octet-stream assets; original CI gates byte-compared only, not re-executed',
            'fixture_provenance':'Original CI product bytes; reconstructed original PROVENANCE/checksums matching authenticated draft size/digests',
            'network_or_actual_publication':False,'original_gate_blocks_unchanged':True,'cases':len(results),'results':results}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    with args.report.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps({key:report[key] for key in ('result','workflow_sha256','cases')}))


if __name__=='__main__':main()
