"""Gate a development package on actual native logs, never modify tested PE bytes."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

root=Path.cwd();e=root/'evidence'
def read(name): return (e/name).read_text(encoding='utf-8-sig')
expected=re.findall(r'\{"([^"]+)",\s*test_\w+\}',(root/'tests/test_main.cpp').read_text())
passed=re.findall(r'\[PASS\] (\w+)',read('regression.log'))
assert len(expected)==44 and sorted(passed)==sorted(expected) and '[FAIL]' not in read('regression.log')
for file,text in [('memory_cycle.log','44 checks passed'),('mcp_boundaries.log','17 checks passed'),('hooks.log','69 passed'),('context_process.log','65 passed'),('transport51.log','8 checks passed'),('transport7.log','8 checks passed')]:
    assert text in read(file),(file,text)
installer={}
for name in ['install51.log','install7.log']:
    m=re.search(r'Native installer: (\d+) checks passed',read(name))
    assert m and int(m[1])>=60,name
    installer[name]=int(m[1])
commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
binary=root/'build/cl/qbrain.exe';digest=hashlib.sha256(binary.read_bytes()).hexdigest()
report={'source_commit':commit,'binary_sha256':digest,'result':'PASS','registered_groups':len(expected),'installer_checks':installer,'real_host_model_consumption_verified':False,'signed':False,'postgres_memory_context_verified':False}
(e/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
# Staged native startup without development DLL paths or real user state.
with tempfile.TemporaryDirectory(prefix='qbrain-package-smoke-') as t:
    home=Path(t); exe=home/'qbrain.exe';exe.write_bytes(binary.read_bytes())
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
    env.update(HOME=t,LOCALAPPDATA=t,USERPROFILE=t,PATH=os.environ['SystemRoot']+'\\System32')
    subprocess.run([str(exe),'init','--brain','package-smoke','--no-default'],cwd=home,env=env,capture_output=True,check=True,timeout=15)
    assert hashlib.sha256(exe.read_bytes()).hexdigest()==digest
files={'qbrain.exe':binary,'LICENSE':root/'LICENSE','WINDOWS-MEMORY.md':root/'docs/integration/WINDOWS-MEMORY.md','scripts/Install-QbrainMemory.ps1':root/'scripts/Install-QbrainMemory.ps1','scripts/Invoke-QbrainJson.ps1':root/'scripts/Invoke-QbrainJson.ps1','verification/validation.json':e/'validation.json','verification/benchmark.json':e/'benchmark.json'}
manifest={**report,'files':{n:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for n,p in files.items()}}
out=root/'package';out.mkdir(exist_ok=True);archive=out/'qbrain-windows-x64-development.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for n,p in files.items():z.write(p,n)
    z.writestr('MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
    z.writestr('README-FIRST.txt','Development build, unsigned. See WINDOWS-MEMORY.md and verification. Hook fixtures are not live Agent/model acceptance. Back up existing databases. Do not use historical dist installers.\n')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for n,p in files.items():assert hashlib.sha256(z.read(n)).hexdigest()==manifest['files'][n]['sha256']
(out/'SHA256SUMS.txt').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
print(json.dumps(report))
