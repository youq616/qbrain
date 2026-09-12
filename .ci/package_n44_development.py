"""Gate a development package on actual native logs, never modify tested PE bytes."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from validate_native_log import verified_groups
import tempfile
import zipfile

root=Path.cwd();e=root/'evidence'
def read(name): return (e/name).read_text(encoding='utf-8-sig')
# N46D requires all 47 named groups; retain the historical validator default.
expected=verified_groups((root/'tests/test_main.cpp').read_text(),read('regression.log'),expected_count=47)
with (e/'evidence-gate-tests.log').open('wb') as log:
    subprocess.run([sys.executable,'.ci/test_validate_native_log.py'],stdout=log,stderr=subprocess.STDOUT,check=True)
for file,text in [('memory_cycle.log','44 checks passed'),('mcp_boundaries.log','17 checks passed'),('hooks.log','69 passed'),('context_process.log','65 passed'),('transport51.log','8 checks passed'),('transport7.log','8 checks passed')]:
    assert text in read(file),(file,text)
installer={}
for name in ['install51.log','install7.log']:
    m=re.search(r'Native installer: (\d+) checks passed',read(name))
    assert m and int(m[1])>=60,name
    installer[name]=int(m[1])
# Additional opt-in/path-identity regressions use the same tested native binary.
for shell,name in [('powershell','consent51.log'),('pwsh','consent7.log')]:
    proc=subprocess.run([shell,'-NoProfile','-ExecutionPolicy','Bypass','-File','.ci/test_install_consent.ps1','-Binary','build/cl/qbrain.exe'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
    (e/name).write_bytes(proc.stdout)
    print(proc.stdout.decode('utf-8',errors='replace'))
    assert proc.returncode==0 and b'16 checks passed' in proc.stdout,name
commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
http_report=json.loads(read('http-transport.json'))
assert http_report['result']=='PASS' and http_report['native_windows'] is True
assert http_report['source_commit']==commit and http_report['check_count']>=50
assert http_report['check_count']==len(http_report['checks'])
assert 'Native WinHTTP:' in read('http-transport.log')
retrieval_report=json.loads(read('retrieval-benchmark.json'))
assert retrieval_report['result']=='PASS' and retrieval_report['native_windows'] is True
assert retrieval_report['source_commit']==commit and retrieval_report['results_equal'] is True
assert retrieval_report['tracked_tree_clean'] is True
assert retrieval_report['source_tree']==subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip()
assert retrieval_report['chunks_scanned']==retrieval_report['chunks']==16000
assert retrieval_report['peak_retained_pages']<=retrieval_report['limit']==50
assert retrieval_report['native_test_checks']>100000

embedding_report=json.loads(read('embedding-transport.json'))
assert embedding_report['result']=='PASS' and embedding_report['native_windows'] is True
assert embedding_report['source_commit']==commit and embedding_report['check_count']>=100
assert embedding_report['check_count']==len(embedding_report['checks'])
assert 'N46D native embedding:' in read('embedding-transport.log')
assert 'N46D embedding integrity:' in read('embedding-unit.log')

binary=root/'build/cl/qbrain.exe';digest=hashlib.sha256(binary.read_bytes()).hexdigest()
with (e/'local-config.log').open('wb') as log:
    subprocess.run([sys.executable,'.ci/test_local_config.py','--binary',str(binary)],stdout=log,stderr=subprocess.STDOUT,check=True)
report={'source_commit':commit,'binary_sha256':digest,'result':'PASS','registered_groups':len(expected),'installer_checks':installer,'additional_consent_checks_per_shell':16,'real_host_model_consumption_verified':False,'signed':False,'postgres_memory_context_verified':False,'native_http_checks':http_report['check_count'],'retrieval_checks':retrieval_report['native_test_checks'],'embedding_wire_checks':embedding_report['check_count']}
# Staged native startup without development DLL paths or real user state.
with tempfile.TemporaryDirectory(prefix='qbrain-package-smoke-') as t:
    home=Path(t); exe=home/'qbrain.exe';exe.write_bytes(binary.read_bytes())
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
    env.update(HOME=t,LOCALAPPDATA=t,USERPROFILE=t,PATH=os.environ['SystemRoot']+'\\System32')
    subprocess.run([str(exe),'init','--brain','package-smoke','--no-default'],cwd=home,env=env,capture_output=True,check=True,timeout=15)
    assert hashlib.sha256(exe.read_bytes()).hexdigest()==digest
(e/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
files={'EMBEDDING-INTEGRITY.md':root/'docs/integration/EMBEDDING-INTEGRITY.md','verification/embedding-transport.json':e/'embedding-transport.json','verification/retrieval-benchmark.json':e/'retrieval-benchmark.json','HTTP-TRANSPORT.md':root/'docs/integration/HTTP-TRANSPORT.md','qbrain.exe':binary,'LICENSE':root/'LICENSE','THIRD-PARTY-NOTICES.md':root/'THIRD-PARTY-NOTICES.md','WINDOWS-MEMORY.md':root/'docs/integration/WINDOWS-MEMORY.md','QUICKSTART.zh-CN.md':root/'docs/integration/QUICKSTART.zh-CN.md','scripts/Install-QbrainMemory.ps1':root/'scripts/Install-QbrainMemory.ps1','scripts/Invoke-QbrainJson.ps1':root/'scripts/Invoke-QbrainJson.ps1','verification/validation.json':e/'validation.json','verification/benchmark.json':e/'benchmark.json','verification/http-transport.json':e/'http-transport.json'}
manifest={**report,'files':{n:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for n,p in files.items()}}
out=root/'package';out.mkdir(exist_ok=True);archive=out/'qbrain-windows-x64-development.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for n,p in files.items():z.write(p,n)
    z.writestr('MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
    z.writestr('README-FIRST.txt','Development build, unsigned. See QUICKSTART.zh-CN.md, WINDOWS-MEMORY.md and verification. Hook fixtures are not live Agent/model acceptance. Back up existing databases. Do not use historical dist installers.\n')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for n,p in files.items():assert hashlib.sha256(z.read(n)).hexdigest()==manifest['files'][n]['sha256']
(out/'SHA256SUMS.txt').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
print(json.dumps(report))
