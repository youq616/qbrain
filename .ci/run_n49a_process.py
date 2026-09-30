"""Run unchanged accepted-module/process regressions against one combined binary."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bin-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();bindir=a.bin_dir.resolve(strict=True);out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1];suffix='.exe' if os.name=='nt' else ''
    binary=bindir/('qbrain'+suffix);rows=[]
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','PG','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
    env.update(PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
    def run(name,argv):
        argv=list(map(str,argv));row=dict(name=name,argv=argv,status='started');rows.append(row)
        (out/'driver.json').write_text(json.dumps(rows,indent=2))
        with tempfile.TemporaryDirectory(prefix='n49a-driver-') as home, (out/(name+'.log')).open('wb') as log:
            isolated={**env,'HOME':home,'USERPROFILE':home,'APPDATA':home,'LOCALAPPDATA':home}
            r=subprocess.run(argv,cwd=root,env=isolated,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        row.update(status='completed',exit=r.returncode,log_sha256=hashlib.sha256((out/(name+'.log')).read_bytes()).hexdigest())
        (out/'driver.json').write_text(json.dumps(rows,indent=2))
        if r.returncode:raise RuntimeError('Combined process regression failed: '+name)
    run('combined-native',[bindir/('qbrain_verified_integration_tests'+suffix)])
    for mode in ('normal','optimized'):
        py=[sys.executable]+(['-O'] if mode=='optimized' else [])
        def script(name,*args):run(name+'-'+mode,py+[root/'.ci'/(name+'.py'),*args])
        script('test_context_invalidation','--binary',binary,'--output',out/('context-matrix-'+mode))
        extra=['--wire'] if os.name=='nt' else []
        script('test_logical_observation','--binary',binary,'--probe',bindir/('qbrain_logical_observation_http_tests'+suffix),
               '--output',out/('logical-'+mode),*extra)
        extra=['--http-binary',bindir/('qbrain_runtime_observation_http'+suffix)] if os.name=='nt' else []
        script('test_runtime_observation','--binary',binary,'--output',out/('runtime-'+mode),*extra)
        script('test_observation_semantics','--binary',binary,'--semantics-binary',bindir/('qbrain_observation_semantics_tests'+suffix),
               '--output',out/('semantics-'+mode))
        script('test_context_process','--binary',binary,'--report',out/('context-'+mode+'.json'))
        script('test_hooks','--binary',binary)
        script('test_memory_cycle','--binary',binary)
        if os.name=='nt':
            script('test_query_embedding_http','--binary',bindir/('qbrain_query_cache_http_tests'+suffix),'--output',out/('query-wire-'+mode))
            script('test_n49a_wire','--binary',bindir/('qbrain_verified_integration_tests'+suffix),'--output',out/('combined-wire-'+mode))
    if os.name=='nt':
        run('original-http',[sys.executable,root/'.ci/test_http_transport.py','--probe',bindir/'qbrain_http_probe.exe',
                             '--report',out/'original-http.json'])
    print(json.dumps(dict(passed=True,steps=len(rows),platform=os.name,
          binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),real_client_verified=False,paid_provider_calls=0)))

if __name__=='__main__':main()
