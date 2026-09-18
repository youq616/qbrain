"""Run N47M review against pinned original CI executables, never a rebuild.

The dedicated workflow has contents:read/actions:read only. Download authentication
is handled by gh, never sent to a model/provider or printed. Only synthetic data
is used by the child probes. Pin values must come from authenticated CI readback.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

REPO='youq616/qbrain'


def gh_json(endpoint):
    return json.loads(subprocess.run(['gh','api',endpoint],check=True,capture_output=True).stdout)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pins',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    pins=json.loads(args.pins.read_text(encoding='utf-8'))
    if sys.platform!='win32':raise RuntimeError('native Windows required')
    root=Path(__file__).resolve().parents[3]
    spec=importlib.util.spec_from_file_location('verified_zip',root/'docs/nodes/n47l-evidence/verify_candidate.py')
    v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
    v.require(set(pins)=={'candidate','baseline'}, 'exact candidate/baseline pin set required')
    for pin in pins.values():
        v.require(all(type(pin[k]) is int and 0 < pin[k] <= v.CAP for k in ('artifact_bytes','exe_bytes')), 'bounded binary sizes')
        v.require(all(v.is_sha(pin[k]) for k in ('artifact_sha256','package_sha256','exe_sha256')) and v.is_sha(pin['source_commit'],40), 'fixed digest shapes')
    args.output.mkdir(parents=True,exist_ok=True)
    source=subprocess.run(['git','rev-parse','HEAD'],cwd=root,check=True,capture_output=True).stdout.decode().strip()
    (args.output/'review-source.txt').write_text(source+'\n',encoding='utf-8')
    receipts={}
    with tempfile.TemporaryDirectory(prefix='qbrain-native-review-') as tmp:
        temp=Path(tmp);exes={}
        for label,pin in pins.items():
            endpoint=f'repos/{REPO}/actions/artifacts/{pin["artifact_id"]}'
            meta=gh_json(endpoint);run=gh_json(f'repos/{REPO}/actions/runs/{pin["run_id"]}')
            v.require(run['head_sha']==pin['source_commit'] and run['status']=='completed' and run['conclusion']=='success', 'pinned binary provenance')
            v.require(meta['id']==pin['artifact_id'] and meta['workflow_run']['id']==pin['run_id'] and meta['workflow_run']['head_sha']==pin['source_commit'], 'pinned binary provenance')
            v.require(meta['name']=='qbrain-n44-windows-development-package' and not meta['expired'], 'pinned binary provenance')
            v.require(meta['size_in_bytes']==pin['artifact_bytes'] and meta['digest']=='sha256:'+pin['artifact_sha256'], 'pinned binary provenance')
            archive=temp/(label+'.zip')
            with archive.open('wb') as target:
                subprocess.run(['gh','api',endpoint+'/zip'],check=True,stdout=target)
            raw=archive.read_bytes()
            v.require(len(raw)==pin['artifact_bytes'] and v.sha(raw)==pin['artifact_sha256'], 'original artifact/package identity')
            outer=v.unzip(raw)[0]
            v.require(set(outer)=={'qbrain-windows-x64-development.zip','SHA256SUMS.txt'}, 'pinned binary provenance')
            product=outer['qbrain-windows-x64-development.zip']
            v.require(v.sha(product)==pin['package_sha256'], 'original artifact/package identity')
            v.require(outer['SHA256SUMS.txt'].decode().split()==[v.sha(product),'qbrain-windows-x64-development.zip'], 'pinned binary provenance')
            files=v.unzip(product)[0];exe=files['qbrain.exe'];manifest=v.obj(files['MANIFEST.json'])
            v.require(manifest['source_commit']==pin['source_commit'] and manifest['binary_sha256']==pin['exe_sha256'], 'pinned binary provenance')
            v.require(len(exe)==pin['exe_bytes'] and v.sha(exe)==pin['exe_sha256'], 'pinned binary provenance')
            v.require(manifest['files']['qbrain.exe']=={'bytes':len(exe),'sha256':v.sha(exe)}, 'pinned binary provenance')
            exes[label]=temp/(label+'.exe');exes[label].write_bytes(exe)
            receipts[label]={'pins':pin,'artifact':meta,'run':{k:run[k] for k in ('id','head_sha','status','conclusion','run_attempt')},'actual_exe_sha256':v.sha(exe)}
        (args.output/'binary-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n',encoding='utf-8')
        child_env=os.environ.copy();child_env.pop('GH_TOKEN',None);child_env.pop('GITHUB_TOKEN',None)
        subprocess.run([sys.executable,str(Path(__file__).with_name('independent_parser_probe.py')),
            '--binary',str(exes['candidate']),'--baseline',str(exes['baseline']),
            '--report',str(args.output/'independent-probe.json')],check=True,env=child_env)
        subprocess.run([sys.executable,str(root/'.ci/test_named_arguments.py'),
            '--binary',str(exes['candidate']),'--baseline',str(exes['baseline']),
            '--source-commit',pins['candidate']['source_commit'],'--report',str(args.output/'named-arguments.json')],check=True,env=child_env)
    hashes={str(f.relative_to(args.output)):v.sha(f.read_bytes()) for f in args.output.rglob('*') if f.is_file()}
    (args.output/'SHA256.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
