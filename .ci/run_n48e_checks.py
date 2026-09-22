"""Run all unchanged local OpenCode suites on the combined native product."""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--direct-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();binary=a.binary.resolve(strict=True);direct=a.direct_dir.resolve(strict=True)
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1];records=[]
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENCODE','OPENAI','ANTHROPIC'))}
    env.update(PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
    def run(name,argv):
        p=subprocess.run(list(map(str,argv)),cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
        for label,data in [('stdout',p.stdout),('stderr',p.stderr)]: (out/(name+'.'+label)).write_bytes(data)
        records.append({'name':name,'argv':list(map(str,argv)),'exit':p.returncode,
                        'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()})
        (out/'driver.json').write_text(json.dumps({'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'steps':records},indent=2))
        if p.returncode:raise RuntimeError('Test failed: '+name)
        return p.stdout
    counts={}
    for name in ('config','audit','reconcile','write_races'):
        exe=direct/('opencode_'+name+'_tests'+('.exe' if os.name=='nt' else ''))
        value=json.loads(run('direct-'+name,[exe]));counts[name]=value['checks']
        if value['result']!='PASS':raise ValueError('Direct test failure')
    for name,checker in [('integration','evidence'),('audit','audit_report'),('reconcile','reconcile')]:
        for mode in ('normal','optimized'):
            py=[sys.executable]+(['-O'] if mode=='optimized' else [])
            dest=out/(name+'-'+mode)
            run(name+'-'+mode,py+[root/f'.ci/test_opencode_{name}.py','--binary',binary,'--output',dest])
            run(name+'-'+mode+'-readback',py+[root/f'.ci/check_opencode_{checker}.py','--report',dest/'report.json',
                '--binary',binary,'--test',root/f'.ci/test_opencode_{name}.py','--negatives'])
    print(json.dumps({'result':'OPENCODE_LIFECYCLE_CHECKS_PASSED','direct_checks':counts,'steps':len(records),
                      'actual_host_loaded':False,'new_test_assertions':False}))

if __name__=='__main__':main()
