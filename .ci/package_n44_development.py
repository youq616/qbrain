"""Gate a development package on actual native logs, never modify tested PE bytes."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from validate_native_log import verified_groups
from validate_recall_report import validate_process as validate_recall, validate_unit as validate_recall_unit
from validate_conflict_report import validate_process as validate_conflicts, validate_unit as validate_conflict_unit
from validate_fact_report import validate_report as validate_facts, validate_unit_report
from validate_cjk_report import validate_report
from validate_http_lifecycle import validate_report as validate_lifecycle
import tempfile
import zipfile

root=Path.cwd();e=root/'evidence'
def read(name): return (e/name).read_text(encoding='utf-8-sig')
# N47C requires all 51 named groups; retain the historical validator default.
expected=verified_groups((root/'tests/test_main.cpp').read_text(encoding='utf-8'),read('regression.log'),expected_count=51)
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
assert http_report['source_commit']==commit and http_report['check_count']>=81
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
assert embedding_report['source_commit']==commit and embedding_report['check_count']>=25
assert embedding_report['check_count']==len(embedding_report['checks'])
assert 'N46D production search: 11 checks passed' in read('embedding-search.log')
assert 'N46D embedding contracts: 65 checks passed' in read('embedding-unit.log')
assert embedding_report['probe_sha256']==hashlib.sha256((root/'build/http/Release/qbrain_http_probe.exe').read_bytes()).hexdigest()

queue_report=json.loads(read('embedding-queue.json'))
assert queue_report['result']=='PASS' and queue_report['native_windows'] is True
assert queue_report['source_commit']==commit and queue_report['tracked_tree_clean'] is True
assert queue_report['source_tree']==retrieval_report['source_tree']
assert queue_report['scenario_count']==len(queue_report['scenarios'])>=40
assert queue_report['checks']>=776 and queue_report['real_provider_calls'] is False
assert queue_report['probe_sha256']==hashlib.sha256((root/'build/http/Release/qbrain_embedding_queue_tests.exe').read_bytes()).hexdigest()
for mode in ('automatic','generic'):
    for code in ('001','002','003','004'):
        assert any(s.startswith(f'{mode}: QB-QUEUE-{code}:') for s in queue_report['scenarios'])

binary=root/'build/cl/qbrain.exe';digest=hashlib.sha256(binary.read_bytes()).hexdigest()
recall_unit=json.loads(read('recall-unit.json'))
validate_recall_unit(recall_unit,source_commit=commit,
    binary_sha256=hashlib.sha256((root/'build/http/Release/qbrain_recall_tests.exe').read_bytes()).hexdigest(),
    script_sha256=hashlib.sha256((root/'.ci/test_recall_unit.py').read_bytes()).hexdigest(),
    test_sha256=hashlib.sha256((root/'tests/test_n47c.cpp').read_bytes()).hexdigest())
recall_process=json.loads(read('recall-process.json'))
validate_recall(recall_process,source_commit=commit,binary_sha256=digest,
    script_sha256=hashlib.sha256((root/'.ci/test_recall_process.py').read_bytes()).hexdigest())
with (e/'recall-report-gate-tests.log').open('wb') as log:
    subprocess.run([sys.executable,'.ci/test_recall_report.py'],stdout=log,stderr=subprocess.STDOUT,check=True)
conflict_unit=json.loads(read('conflict-unit.json'))
validate_conflict_unit(conflict_unit,source_commit=commit,
    binary_sha256=hashlib.sha256((root/'build/http/Release/qbrain_conflict_tests.exe').read_bytes()).hexdigest(),
    script_sha256=hashlib.sha256((root/'.ci/test_conflict_unit.py').read_bytes()).hexdigest(),
    test_sha256=hashlib.sha256((root/'tests/test_n47b.cpp').read_bytes()).hexdigest())
conflict_process=json.loads(read('conflict-process.json'))
validate_conflicts(conflict_process,source_commit=commit,binary_sha256=digest,
    script_sha256=hashlib.sha256((root/'.ci/test_conflict_process.py').read_bytes()).hexdigest())
with (e/'conflict-report-gate-tests.log').open('wb') as log:
    subprocess.run([sys.executable,'.ci/test_conflict_report.py'],stdout=log,stderr=subprocess.STDOUT,check=True)

fact_report=json.loads(read('fact-process.json'))
validate_facts(fact_report, source_commit=commit, binary_sha256=digest,
               script_sha256=hashlib.sha256((root/'.ci/test_fact_process.py').read_bytes()).hexdigest())
fact_unit=json.loads(read('fact-unit.json'))
validate_unit_report(fact_unit,source_commit=commit,
    binary_sha256=hashlib.sha256((root/'build/http/Release/qbrain_fact_tests.exe').read_bytes()).hexdigest(),
    test_sha256=hashlib.sha256((root/'tests/test_n47a.cpp').read_bytes()).hexdigest(),
    expected_scenarios=re.findall(r'scenario\("([^"\r\n]+)"',(root/'tests/test_n47a.cpp').read_text(encoding='utf-8')))
with (e/'fact-report-gate-tests.log').open('wb') as log:
    subprocess.run([sys.executable,'.ci/test_fact_report.py'],stdout=log,stderr=subprocess.STDOUT,check=True)
cjk_report=json.loads(read('cjk-recall.json'))
assert cjk_report['native_windows'] is True
validate_report(cjk_report, source_commit=commit, binary_sha256=digest,
                script_sha256=hashlib.sha256((root/'.ci/test_cjk_recall.py').read_bytes()).hexdigest())
with (e/'cjk-report-gate-tests.log').open('wb') as log:
    subprocess.run([sys.executable,'.ci/test_cjk_report.py'], stdout=log, stderr=subprocess.STDOUT, check=True)
lifetime_report=json.loads(read('http-lifecycle.json'))
validate_lifecycle(lifetime_report, source_commit=commit,
    probe_hashes={name:hashlib.sha256((root/f'build/http-lifecycle/Release/qbrain_http_lifecycle_{name}.exe').read_bytes()).hexdigest()
                  for name in ('legacy','per_call','current')})
with (e/'lifecycle-report-gate.log').open('wb') as log:
    subprocess.run([sys.executable,'.ci/test_http_lifecycle_report.py'],stdout=log,stderr=subprocess.STDOUT,check=True)

with (e/'local-config.log').open('wb') as log:
    subprocess.run([sys.executable,'.ci/test_local_config.py','--binary',str(binary)],stdout=log,stderr=subprocess.STDOUT,check=True)
report={'source_commit':commit,'binary_sha256':digest,'result':'PASS','registered_groups':len(expected),'installer_checks':installer,'additional_consent_checks_per_shell':16,'real_host_model_consumption_verified':False,'signed':False,'postgres_memory_context_verified':False,'native_http_checks':http_report['check_count'],'retrieval_checks':retrieval_report['native_test_checks'],'embedding_wire_checks':embedding_report['check_count'],'queue_scenarios':queue_report['scenario_count'],'queue_checks':queue_report['checks'],'cjk_process_checks':cjk_report['check_count'],'fact_process_checks':fact_report['check_count'],'fact_scenarios':fact_unit['scenario_count'],'fact_unit_assertions':fact_unit['checks']}
# Staged native startup without development DLL paths or real user state.
with tempfile.TemporaryDirectory(prefix='qbrain-package-smoke-') as t:
    home=Path(t); exe=home/'qbrain.exe';exe.write_bytes(binary.read_bytes())
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
    env.update(HOME=t,LOCALAPPDATA=t,USERPROFILE=t,PATH=os.environ['SystemRoot']+'\\System32')
    subprocess.run([str(exe),'init','--brain','package-smoke','--no-default'],cwd=home,env=env,capture_output=True,check=True,timeout=15)
    assert hashlib.sha256(exe.read_bytes()).hexdigest()==digest
report.update(recall_scenarios=recall_unit['scenario_count'],recall_assertions=recall_unit['checks'],recall_process_checks=recall_process['check_count'])
report.update(conflict_scenarios=conflict_unit['scenario_count'],conflict_assertions=conflict_unit['checks'],conflict_process_checks=conflict_process['check_count'])
(e/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
files={'FACT-RECALL.zh-CN.md':root/'docs/integration/FACT-RECALL.zh-CN.md','verification/test_recall_process.py':root/'.ci/test_recall_process.py','verification/recall-process.json':e/'recall-process.json','verification/recall-unit.json':e/'recall-unit.json','CONFLICT-INSPECTION.zh-CN.md':root/'docs/integration/CONFLICT-INSPECTION.zh-CN.md','verification/test_conflict_process.py':root/'.ci/test_conflict_process.py','verification/conflict-process.json':e/'conflict-process.json','verification/conflict-unit.json':e/'conflict-unit.json','EVIDENCE-FACTS.zh-CN.md':root/'docs/integration/EVIDENCE-FACTS.zh-CN.md','verification/test_fact_process.py':root/'.ci/test_fact_process.py','verification/fact-process.json':e/'fact-process.json','verification/fact-unit.json':e/'fact-unit.json','verification/http-lifecycle.json':e/'http-lifecycle.json','CJK-RECALL.zh-CN.md':root/'docs/integration/CJK-RECALL.zh-CN.md','verification/test_cjk_recall.py':root/'.ci/test_cjk_recall.py','verification/cjk-recall.json':e/'cjk-recall.json','verification/embedding-queue.json':e/'embedding-queue.json','EMBEDDING-QUEUE.md':root/'docs/integration/EMBEDDING-QUEUE.md','verification/embedding-transport.json':e/'embedding-transport.json','EMBEDDING-CONTRACTS.md':root/'docs/integration/EMBEDDING-CONTRACTS.md','verification/retrieval-benchmark.json':e/'retrieval-benchmark.json','HTTP-TRANSPORT.md':root/'docs/integration/HTTP-TRANSPORT.md','qbrain.exe':binary,'LICENSE':root/'LICENSE','THIRD-PARTY-NOTICES.md':root/'THIRD-PARTY-NOTICES.md','WINDOWS-MEMORY.md':root/'docs/integration/WINDOWS-MEMORY.md','QUICKSTART.zh-CN.md':root/'docs/integration/QUICKSTART.zh-CN.md','scripts/Install-QbrainMemory.ps1':root/'scripts/Install-QbrainMemory.ps1','scripts/Invoke-QbrainJson.ps1':root/'scripts/Invoke-QbrainJson.ps1','verification/validation.json':e/'validation.json','verification/benchmark.json':e/'benchmark.json','verification/http-transport.json':e/'http-transport.json'}
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
