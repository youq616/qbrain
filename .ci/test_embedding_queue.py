"""Exercise production queues/storage/parser with a no-network provider on the host OS."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile

p=argparse.ArgumentParser()
p.add_argument('--binary',type=Path,required=True)
p.add_argument('--report',type=Path,required=True)
p.add_argument('--require-windows',action='store_true')
a=p.parse_args()
if a.require_windows and os.name!='nt':
    raise SystemExit('Windows queue acceptance requires a native Windows process')
binary=a.binary.resolve(strict=True)
env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
with tempfile.TemporaryDirectory(prefix='qbrain-queue-env-') as home:
    env.update(HOME=home,USERPROFILE=home,LOCALAPPDATA=home)
    result=subprocess.run([str(binary)],env=env,capture_output=True,text=True,
                          encoding='utf-8',timeout=180)
if result.returncode:
    raise SystemExit(result.stderr or 'Queue regression process failed')
report=json.loads(result.stdout)
assert report['result']=='PASS' and report['checks']>=776
assert report['scenario_count']==len(report['scenarios'])>=40
assert len(set(report['scenarios']))==report['scenario_count']
for mode in ('automatic','generic'):
    for code in ('001','002','003','004'):
        assert any(s.startswith(f'{mode}: QB-QUEUE-{code}:') for s in report['scenarios'])
assert report['production_queue_and_storage'] is True
assert report['real_provider_calls'] is False
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
clean=subprocess.run(['git','diff','--quiet','HEAD','--']).returncode==0
report.update(source_commit=head if clean else None,head_commit=head,
              tracked_tree_clean=clean,
              source_tree=subprocess.check_output(['git','write-tree'],text=True).strip(),
              native_windows=os.name=='nt',platform=platform.platform(),
              probe_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
a.report.parent.mkdir(parents=True,exist_ok=True)
a.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(f"N46D queue repairs: {report['scenario_count']} scenarios, {report['checks']} checks passed")
