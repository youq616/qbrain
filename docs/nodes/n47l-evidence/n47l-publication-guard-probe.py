"""Execute unresolved publication guards under an audit hook denying side effects."""
import argparse,ast,hashlib,json,os,subprocess,sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--template',type=Path,required=True)
parser.add_argument('--report',type=Path,required=True)
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
pins={}
for line in lines:
    if line.startswith('      ') and not line.startswith('       ') and ": '" in line:
        name,value=line.strip().split(': ',1);pins[name]=value.strip("'")
assert any('REPLACE' in value for value in pins.values()),'Use an unresolved template for this fail-closed test'
probe_env=dict(pins)
probe_env.update(PATH=os.environ['PATH'],GITHUB_REPOSITORY='youq616/qbrain',GITHUB_REF='refs/heads/delivery/n47l-reviewed-17e9a435',GITHUB_WORKSPACE='/does-not-exist',RUNNER_TEMP='/does-not-exist',GITHUB_RUN_ID='1',GITHUB_RUN_ATTEMPT='1',GITHUB_SHA='0'*40)
prelude='''import os,sys\ndef block(event,args):\n    if event.startswith("socket.") or event in ("subprocess.Popen","os.system","os.posix_spawn","os.rename","os.mkdir","os.remove","os.rmdir","os.symlink","os.link","os.chmod","os.chown","os.truncate"):\n        raise AssertionError("Forbidden side effect: "+event)\n    if event=="open":\n        mode,flags=args[1],args[2]\n        if (isinstance(mode,str) and any(c in mode for c in "awx+")) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):\n            raise AssertionError("Forbidden file mutation")\nsys.addaudithook(block)\n'''
results=[]
for index,block in enumerate(blocks):
    ast.parse(block)
    proc=subprocess.run([sys.executable,'-I','-S','-B','-c',prelude+block],env=probe_env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
    assert proc.returncode!=0 and 'Forbidden side effect' not in proc.stderr and 'Forbidden file mutation' not in proc.stderr
    if index==0:assert 'Unresolved publication pin: REVIEW_SHA' in proc.stderr
    else:assert 'REPLACE_EXACT_READBACK_CHECK_COUNT' in proc.stderr
    results.append({'block':index+1,'exit_code':proc.returncode,'last_error':proc.stderr.splitlines()[-1],'no_side_effect_attempt':True})
report={'template_sha256':hashlib.sha256(args.template.read_bytes()).hexdigest(),'python_blocks':len(blocks),'result':'PASS_UNRESOLVED_PINS_REFUSED','network_or_actual_publication':False,'results':results}
with args.report.open('x') as stream:stream.write(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
