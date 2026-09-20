"""N47X fixed-artifact delivery. Read-only by default; --publish is explicit.

Never rebuild/overwrite/move a tag or delete a failed release automatically.
Uses the repository workflow token, not personal credentials or model providers.
"""
from __future__ import annotations
import argparse
import importlib
import os
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen
import n47x_verify as v

REPO='youq616/qbrain'
BRANCH='delivery/n47x-current-preview'
TAG='windows-current-preview-b810d689'
TITLE='Qbrain N47X — current-source Windows integrated preview'
JOBS={'source':105994308433,'native':105994308622}
REQUIRED={
    'source':{'Delivery source and package negatives'},
    'native':{'Fresh fixed-source native application and full original suite','Assemble twice and verify exact candidate files',
              'Extracted receipt features and original process regressions','Extracted model tools and actual engine to test-only HTTP pipeline',
              'Both native shells against extracted installer and old-to-new upgrade'},
}


def state_helpers():
    v.helpers()  # verifies the inherited archive helper before import
    path=Path(__file__).resolve().parents[1]/'delivery/publish_reviewed_n47o.py'
    v.need(v.sha(path.read_bytes())=='c01890e7b941cb25718e479d8f5ded0576210df709ad3b5fcdd96b713a6f263a','changed_publication_helper')
    h=importlib.import_module('publish_reviewed_n47o')
    h.TAG=TAG;h.SOURCE=v.PRODUCT_SOURCE;h.TITLE=TITLE
    return h


def validate_live(run, listing):
    v.need(isinstance(run,dict) and run.get('id')==v.RUN and run.get('head_sha')==v.DELIVERY
        and run.get('path')=='.github/workflows/n47x-validation.yml' and run.get('event')=='push'
        and type(run.get('run_attempt')) is int and run['run_attempt']==1
        and run.get('status')=='completed' and run.get('conclusion')=='success'
        and run.get('repository',{}).get('full_name')==REPO and run.get('head_repository',{}).get('full_name')==REPO,'live_run')
    rows=listing.get('jobs')
    v.need(type(listing.get('total_count')) is int and listing['total_count']==2
        and isinstance(rows,list) and len(rows)==2 and {x.get('name'):x.get('id') for x in rows}==JOBS,'live_jobs')
    for row in rows:
        v.need(row.get('run_id')==v.RUN and row.get('head_sha')==v.DELIVERY and type(row.get('run_attempt')) is int
            and row['run_attempt']==1 and row.get('status')=='completed' and row.get('conclusion')=='success','live_job_state')
        steps=row.get('steps')
        v.need(isinstance(steps,list) and len(steps)>0 and len({x.get('number') for x in steps})==len(steps)
            and REQUIRED[row['name']]<={x.get('name') for x in steps}
            and all(x.get('status')=='completed' and x.get('conclusion')=='success' for x in steps),'required_steps')
    return {'run':run,'jobs':listing}


def prepare(api, out):
    live=validate_live(api.api(f'actions/runs/{v.RUN}'),api.api(f'actions/runs/{v.RUN}/attempts/1/jobs?per_page=100'))
    for source,tree in [(v.DELIVERY,v.DELIVERY_TREE),(v.PRODUCT_SOURCE,v.PRODUCT_TREE)]:
        commit=api.api('git/commits/'+source)
        v.need(commit.get('sha')==source and commit.get('tree',{}).get('sha')==tree,'live_source_tree')
    pins=out/'artifacts';pins.mkdir()
    metadata={}
    for label,(ident,name,size,digest) in v.ARTIFACTS.items():
        row=api.api(f'actions/artifacts/{ident}')
        v.need(row.get('id')==ident and row.get('name')==name and row.get('expired') is False
            and row.get('size_in_bytes')==size and row.get('digest')=='sha256:'+digest
            and row.get('workflow_run',{}).get('id')==v.RUN and row['workflow_run'].get('head_sha')==v.DELIVERY,'live_artifact')
        raw=api.raw(f'actions/artifacts/{ident}/zip',binary=True)
        v.need(len(raw)==size and v.sha(raw)==digest,'artifact_download')
        (pins/(label+'.zip')).write_bytes(raw);metadata[label]=row
    archive=v.helpers()
    url=f'https://github.com/{REPO}/releases/download/windows-integrated-preview-9e9a92b0/qbrain-windows-x64-n47r-preview.zip'
    with urlopen(url,timeout=90) as response:old=response.read(8*1024*1024+1)
    v.need(v.sha(old)==v.OLD_ZIP,'original_baseline')
    old_files=archive.unzip(old)[0]
    (pins/'prior-installer.ps1').write_bytes(old_files['scripts/Install-QbrainMemory.ps1'])
    readback=v.verify(pins)
    native=archive.unzip((pins/'native.zip').read_bytes())[0]
    bundle=native['one/'+v.NAME]
    files=archive.unzip(bundle)[0]
    evidence={'original-artifacts/'+label+'.zip':(pins/(label+'.zip')).read_bytes() for label in v.ARTIFACTS}
    evidence['READBACK.json']=v.encode(readback)
    evidence['GITHUB-METADATA.json']=v.encode({'validation':live,'artifacts':metadata})
    # Reuse canonical deterministic ZIP assembly, no rebuild of the product.
    z=importlib.import_module('build_integrated_n47r')
    raw_evidence=z.make_zip(evidence)
    provenance={'schema':'qbrain-n47x-release-v1','repository':REPO,'tag':TAG,'product_source':v.PRODUCT_SOURCE,
        'product_tree':v.PRODUCT_TREE,'delivery_source':v.DELIVERY,'delivery_tree':v.DELIVERY_TREE,
        'accepted_run':v.RUN,'accepted_attempt':1,'bundle_sha256':v.ZIP_SHA,'bundle_bytes':v.ZIP_BYTES,
        'binary_sha256':v.EXE_SHA,'native_bundle_evidence':'VERIFIED','compiler_output_reproducible':False,
        'new_product_build':True,'signed':False,'stable_v1':False,'real_model_answers':'NOT_RUN',
        'real_client_consumption':'NOT_RUN','provider_cost':None,'live_pg':'SKIP-PG','open_issue':40,
        'evidence_sha256':v.sha(raw_evidence),'original_artifacts_included':True,
        'publisher_source':os.environ.get('GITHUB_SHA'),'publisher_run':os.environ.get('GITHUB_RUN_ID'),
        'manifest_scope':'Immutable internal manifest is construction-time status; external receipt binds later acceptance.',
        'reviewer':'Owner-authorized coordinator separate engineering self-review, not third-party certification'}
    assets={v.NAME:bundle,'START-HERE.zh-CN.md':files['START-HERE.zh-CN.md'],
        'PROVENANCE.json':v.encode(provenance),'VALIDATION-EVIDENCE.zip':raw_evidence}
    assets['SHA256SUMS.txt']=''.join(v.sha(b)+'  '+n+'\n' for n,b in assets.items()).encode()
    for name,raw in assets.items():(out/name).write_bytes(raw)
    (out/'READBACK.json').write_bytes(v.encode(readback))
    (out/'verification.json').write_bytes(v.encode({'result':'VERIFIED','published':False,
        'assets':{name:{'bytes':len(raw),'sha256':v.sha(raw)} for name,raw in assets.items()}}))
    return assets


def publish(api, assets, out, h):
    h.ensure_absent(api)
    if not h.tag_state(api,optional=True):
        api.api('git/refs',method='POST',body={'ref':'refs/tags/'+TAG,'sha':v.PRODUCT_SOURCE})
    h.tag_state(api)
    draft=api.api('releases',method='POST',body={'tag_name':TAG,'target_commitish':v.PRODUCT_SOURCE,'name':TITLE,
        'body':'N47X Windows 集成开发预览：从 b810d689 重新编译，包含模型对照工具、使用回执与审计、路径保护及桥接诊断。'
               '先读 START-HERE，核对同版 PROVENANCE、SHA256SUMS 和验收证据。未签名、非 latest；真实客户端/模型效果、PG及稳定v1未验收。'
               'Issue40根因未知，仍保留。\nZIP SHA-256: '+v.ZIP_SHA,
        'draft':True,'prerelease':True,'make_latest':'false'})
    ident=draft.get('id');v.need(type(ident) is int and ident>0,'draft_identity')
    h.release_state(draft,ident,{}, {},True)
    (out/'draft.json').write_bytes(v.encode(draft));pins={}
    for name,raw in assets.items():
        path=out/name;v.need(path.read_bytes()==raw,'local_asset_changed')
        pins[name]=h.asset_identity(api.upload(ident,path),name,raw)
        (out/'asset-pins.json').write_bytes(v.encode(pins))
    for is_draft in (True,False):
        state=api.api(f'releases/{ident}') if is_draft else api.api('releases/tags/'+TAG)
        h.release_state(state,ident,assets,pins,is_draft);h.tag_state(api)
        for name,pin in pins.items():v.need(api.raw(f'releases/assets/{pin["id"]}',binary=True)==assets[name],'release_bytes')
        h.release_state(api.api(f'releases/{ident}'),ident,assets,pins,is_draft);h.tag_state(api)
        if is_draft:api.api(f'releases/{ident}',method='PATCH',body={'draft':False,'prerelease':True,'make_latest':'false'})
    latest=api.api('releases/latest',optional=True)
    v.need(latest is None or latest.get('id')!=ident,'became_latest')
    result={'result':'PUBLISHED','release_id':ident,'tag':TAG,'source_commit':v.PRODUCT_SOURCE,
        'asset_pins':pins,'url':f'https://github.com/{REPO}/releases/tag/{TAG}',
        'downloaded_before_and_after_publication':True,'new_product_build':True,'signed':False,'stable_v1':False}
    (out/'publication.json').write_bytes(v.encode(result));return result


def public_readback(assets, receipt, out):
    v.need(receipt.get('result')=='PUBLISHED','not_published')
    observations=[]
    for name,raw in assets.items():
        url=f'https://github.com/{REPO}/releases/download/{TAG}/'+quote(name,safe='')
        with urlopen(url,timeout=120) as response:observed=response.read(128*1024*1024+1)
        v.need(observed==raw,'anonymous_download_mismatch')
        observations.append({'name':name,'bytes':len(raw),'sha256':v.sha(raw)})
    result={'result':'PUBLIC_BYTES_VERIFIED','authenticated':False,'release_id':receipt['release_id'],'assets':observations}
    (out/'public-readback.json').write_bytes(v.encode(result));return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--publish',action='store_true')
    args=parser.parse_args()
    v.need(os.environ.get('GITHUB_REPOSITORY')==REPO and os.environ.get('GITHUB_REF')=='refs/heads/'+BRANCH,'repository_branch')
    args.output.mkdir(parents=True,exist_ok=False)
    h=state_helpers();api=h.GitHub();assets=prepare(api,args.output)
    if args.publish:
        result=publish(api,assets,args.output,h);public_readback(assets,result,args.output)
    else:result={'result':'VERIFIED','published':False}
    print(v.encode(result).decode())


if __name__=='__main__':main()
