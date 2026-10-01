"""Exact immutable input union and native build closure for N49C."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = 'docs/nodes/n49c-evidence/INPUT-INVENTORY.json'
PIN = '5e0e87d28d2acb2a2409682b9d9618fc2a6bf43bba2b2c2392f7a6ba4ba40b0e'
PARENTS = ['f5331d174b6dfb853fd5450c78a25ae2754681da', 'd54308d61bc894f540885b9b317b899c560e58d2', '8394e83aac484bf6c31fad421162d258fb8d2587']
EXCLUDED = {'4fb5f7bcc4d5871b7eef409963806ba58b486ae1', '18abbe94dff60f85298b2743efc02839f869cd77'}
ADDITIVE = {'.ci/check_n49c_sources.py', '.ci/test_n49c_source_contract.py',
 '.ci/client_retrieval_integration_targets.cmake', '.ci/build_n49c_direct_tests.ps1',
 '.ci/test_n49c_process.py', '.ci/run_n49c_installers.ps1',
 '.github/workflows/n49c-integration.yml', 'tests/test_client_retrieval_integration.cpp',
 'docs/nodes/N49C-PLAN.md', 'docs/nodes/N49C-PLAN-AUDIT.md',
 'docs/nodes/N49C-LOCAL-RESULTS.md', 'docs/nodes/N49C-HARD-AUDIT.md', INVENTORY,
 'docs/integration/CLIENT-RETRIEVAL-CANDIDATE.zh-CN.md'}

def need(ok, message):
    if not ok:
        raise ValueError(message)

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

BLOCKED_ENV = re.compile(r'^(QBRAIN|PG|CURSOR|OPENAI|ANTHROPIC|GH_TOKEN|GITHUB_TOKEN|AWS_|AZURE_|GOOGLE_|GCP_|ZHIPU|GEMINI|COHERE|MISTRAL|DEEPSEEK|HF_|HUGGINGFACE|OPENROUTER|GIT_CONFIG_)|(?:^|_)(?:API_KEY|TOKEN|SECRET|PASSWORD|PASSWD|DSN|DATABASE_URL)(?:_|$)', re.I)

def clean_environment(source, home):
    value={k:v for k,v in source.items() if not BLOCKED_ENV.search(k) and k.upper()!='PSMODULEPATH'}
    for key in ('BASH_ENV','ENV'):
        value.pop(key,None)
    for key in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME'):
        value[key]=str(home)
    value.update(PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_SYSTEM=os.devnull)
    return value

def run_clean(argv, environment=None):
    need(bool(argv),'clean execution command required')
    with tempfile.TemporaryDirectory(prefix='n49c-clean-home-') as home:
        return subprocess.run(argv,env=clean_environment(os.environ if environment is None else environment,home)).returncode

def verify_frozen_checkout(repository, expected_head, expected_tree):
    def read(*args):return subprocess.check_output(['git',*args],cwd=repository)
    failures=[]
    head=read('rev-parse','HEAD').decode().strip();tree=read('rev-parse','HEAD^{tree}').decode().strip()
    if head!=expected_head:failures.append('frozen HEAD changed')
    if tree!=expected_tree:failures.append('frozen tree changed')
    staged=read('diff','--cached','--raw').decode()
    diagnostic=read('diff','--raw').decode()
    unstaged=read('-c','core.autocrlf=true','diff','--raw').decode()
    if staged:failures.append('staged tracked changes')
    if unstaged:failures.append('unstaged tracked changes')
    conversions=[]
    # Always inspect the expected immutable tree, never a moved HEAD's definition.
    for row in read('ls-tree','-r','-z',expected_head).split(b'\0'):
        if not row:continue
        meta,path=row.split(b'\t',1);mode,kind,sha=meta.decode().split();path=path.decode()
        if kind!='blob':failures.append('non-blob tracked object: '+path);continue
        canonical=read('cat-file','blob',sha)
        try:actual=(Path(repository)/path).read_bytes()
        except OSError:failures.append('unreadable tracked file: '+path);continue
        if actual==canonical:continue
        if b'\r\n' not in canonical and actual==canonical.replace(b'\n',b'\r\n'):conversions.append(path)
        else:failures.append('tracked byte mismatch: '+path)
    return dict(passed=not failures,expected_head=expected_head,expected_tree=expected_tree,
        actual_head=head,actual_tree=tree,staged_diff=staged,unstaged_diff=unstaged,
        raw_unconfigured_unstaged_diff=diagnostic,unstaged_autocrlf='true',
        checkout_conversions=conversions,failures=failures)

BLOCK = 1024*1024
PART_BYTES = 20*BLOCK
MAX_PARTS = 16
MAX_ARCHIVE = PART_BYTES*MAX_PARTS
MAX_RAW = 2048*BLOCK
MAX_MANIFEST = 8*BLOCK
MIN_FREE = 1152*BLOCK
IDENTITY_KEYS = ('commit','tree','run_id','run_attempt','job_key','job_label')

def hash_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk:=f.read(BLOCK):h.update(chunk)
    return h.hexdigest()

def run_bound_bash(executable,script,version,report,observed=None,environment=None):
    report=Path(report);report.parent.mkdir(parents=True,exist_ok=True)
    result=dict(passed=False,observed=observed or {},received_executable=str(executable),received_script=str(script))
    try:
        need(Path(executable).is_absolute() and Path(script).is_absolute(),'absolute native shell and script paths required')
        exe=Path(executable).resolve(strict=True);script=Path(script).resolve(strict=True)
        need(exe.is_file() and script.is_file(),'native shell/script must be files')
        before=hash_file(exe);script_hash=hash_file(script)
        result.update(executable=str(exe),executable_sha256=before,script=str(script),script_sha256=script_hash,expected_bash_version=version)
        with tempfile.TemporaryDirectory(prefix='n49c-bash-home-') as home:
            env=clean_environment(os.environ if environment is None else environment,home)
            probes=[]
            for name,args in [('banner',['--version']),('exact',['-c','printf "%s" "$BASH_VERSION"'])]:
                argv=[str(exe),'--noprofile','--norc',*args]
                run=subprocess.run(argv,env=env,capture_output=True)
                streams={}
                for key,data in [('stdout',run.stdout),('stderr',run.stderr)]:
                    path=report.with_name(report.name+'.'+name+'.'+key);path.write_bytes(data)
                    streams[key]=dict(path=str(path),size=len(data),sha256=hashlib.sha256(data).hexdigest())
                probes.append(dict(name=name,argv=argv,exit=run.returncode,**streams))
                result['probes']=probes
                need(run.returncode==0 and not run.stderr,'Bash version probe failed')
                if name=='banner':result['full_version']=run.stdout.decode('utf-8',errors='strict')
                else:
                    result['actual_bash_version']=run.stdout.decode('utf-8',errors='strict')
                    need(result['actual_bash_version']==version,'observed Bash version mismatch')
            argv=[str(exe),'--noprofile','--norc','-euo','pipefail',str(script)]
            result['argv']=argv
            result['exit']=subprocess.run(argv,env=env).returncode
        result['executable_after_sha256']=hash_file(exe);result['script_after_sha256']=hash_file(script)
        need(result['executable_after_sha256']==before and result['script_after_sha256']==script_hash,'shell/script identity changed')
        result['passed']=result['exit']==0
    except Exception as exc:
        result['error']=str(exc)
    finally:report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return 0 if result['passed'] else 1

def safe_member(name):
    return isinstance(name,str) and bool(name) and '\\' not in name and not name.startswith('/') and all(x not in ('','.','..') for x in name.split('/')) and ':' not in name

def evidence_identity(identity):
    need(set(identity)==set(IDENTITY_KEYS),'complete independent evidence identity required')
    need(all(isinstance(identity[k],str) and identity[k] for k in IDENTITY_KEYS),'identity values required')
    need(all(re.fullmatch('[0-9a-f]{40}',identity[k]) for k in ('commit','tree')),'invalid source identity')
    need(identity['run_id'].isdigit() and identity['run_attempt'].isdigit(),'invalid run identity')

PHASE_IDS = ('checkout','source_identity','source_capture','cmake_build','ctests','sqlite_context',
 'n49a_process','contract_normal','contract_optimized','directory_normal','cursor_normal','combined_normal',
 'directory_optimized','cursor_optimized','combined_optimized','binary_capture','baseline_fixture','original55')
BOOTSTRAP_PHASES = PHASE_IDS[:2]
WINDOWS_PHASES = ('baseline_fixture','original55')
BINARY_PHASES = {'ctests','sqlite_context','n49a_process','directory_normal','cursor_normal','combined_normal',
 'directory_optimized','cursor_optimized','combined_optimized','binary_capture','original55'}

def phase_clock():
    return dict(utc_ns=time.time_ns(),monotonic_ns=time.monotonic_ns())

def phase_write(path,value):
    raw=(json.dumps(value,sort_keys=True,indent=2)+'\n').encode('utf-8')
    with Path(path).open('xb') as stream:
        stream.write(raw);stream.flush()
    return hashlib.sha256(raw).hexdigest()

def phase_file(path):
    path=Path(path).resolve(strict=True);before=path.stat()
    need(stat.S_ISREG(before.st_mode),'phase input must be a regular file')
    digest=hash_file(path);after=path.stat()
    need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
         (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'phase file changed while hashing')
    return dict(path=str(path),bytes=after.st_size,sha256=digest)

def phase_descriptor(value):
    need(isinstance(value,dict) and set(value)=={'path','bytes','sha256'},'complete phase file descriptor required')
    need(isinstance(value['path'],str) and Path(value['path']).is_absolute(),'absolute phase file path required')
    need(type(value['bytes']) is int and value['bytes']>=0,'phase file byte count must be an integer')
    need(isinstance(value['sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['sha256']) is not None,'phase file digest required')

def phase_timestamp(value):
    need(isinstance(value,dict) and set(value)=={'utc_ns','monotonic_ns'},'complete UTC and monotonic phase timestamps required')
    need(all(type(value[k]) is int for k in value),'phase timestamps must be integers')

def phase_streams(folder,result):
    files=[]
    for key in ('stdout','stderr'):
        need(key in result,'missing phase '+key+' descriptor')
        descriptor=result[key];phase_descriptor(descriptor)
        expected=Path(folder)/(key+'.raw')
        need(descriptor['path']==str(expected),'phase '+key+' path substitution')
        need(stat.S_ISREG(expected.lstat().st_mode) and expected.resolve(strict=True)==expected,'phase raw path must be an exact regular file')
        need(phase_file(expected)==descriptor,'phase retained '+key+' bytes changed')
        files.append(expected)
    need(not files[0].samefile(files[1]),'phase stdout and stderr must be distinct files')

def phase_check(identity,platform,phase=None):
    evidence_identity(identity)
    need(platform in ('Linux','Windows'),'unknown phase platform')
    label='qbrain-n49c-cmake-'+('windows-2022' if platform=='Windows' else 'ubuntu-24.04')
    need(identity['job_key']=='cmake' and identity['job_label']==label,'phase job/platform mismatch')
    if phase is not None:
        need(phase in PHASE_IDS and phase not in BOOTSTRAP_PHASES,'unknown command phase')
        need(platform=='Windows' or phase not in WINDOWS_PHASES,'Windows-only phase on another platform')

def phase_start(root,identity,platform,phase,script,binary=None):
    """Record metadata only. The native Actions step retains process ownership."""
    phase_check(identity,platform,phase)
    need((binary is not None)==(phase in BINARY_PHASES),'phase binary applicability mismatch')
    folder=Path(root).resolve()/phase;folder.mkdir(parents=True,exist_ok=False)
    started=dict(schema='n49c-phase-start-v1',identity=identity,platform=platform,phase=phase,
        status='started',clock=phase_clock(),script_path=str(script),binary_path=str(binary) if binary else None,
        process_ownership='native-actions-step; no independent descendant-cleanup claim')
    phase_write(folder/'STARTING.json',started)
    for name in ('stdout.raw','stderr.raw'):
        with (folder/name).open('xb'):pass
    print('N49C_PHASE_START '+phase,flush=True,file=sys.stderr)
    started.update(script=phase_file(script),binary=phase_file(binary) if binary else None)
    return phase_write(folder/'START.json',started)

def phase_finish(root,identity,platform,phase,start_sha,exit_code,produced_binary=None):
    phase_check(identity,platform,phase)
    need(type(exit_code) is int and 0<=exit_code<=255,'observed phase exit must be an integer shell status')
    folder=Path(root).resolve()/phase;folder.mkdir(parents=True,exist_ok=True)
    returned=dict(schema='n49c-phase-return-v1',identity=identity,platform=platform,phase=phase,
        observed_exit=exit_code,clock=phase_clock())
    # Save the real launcher return before reading/hashing optional evidence.
    return_sha=phase_write(folder/'RETURN.json',returned)
    result=dict(schema='n49c-phase-result-v1',identity=identity,platform=platform,phase=phase,
        observed_exit=exit_code,return_sha256=return_sha,start_sha256=start_sha,
        passed=False,record_complete=False,process_cleanup='runner-managed; not independently verified')
    try:
        raw=bounded_manifest(folder/'START.json')
        need(hashlib.sha256(raw).hexdigest()==start_sha,'phase start digest mismatch')
        started=json.loads(raw)
        need(started['identity']==identity and started['platform']==platform and started['phase']==phase,'phase start identity mismatch')
        need(started['schema']=='n49c-phase-start-v1' and started['status']=='started','phase start shape mismatch')
        phase_timestamp(started['clock']);phase_timestamp(returned['clock'])
        need(type(started['clock']['monotonic_ns']) is int and returned['clock']['monotonic_ns']>=started['clock']['monotonic_ns'],'phase monotonic clock mismatch')
        result['elapsed_ns']=returned['clock']['monotonic_ns']-started['clock']['monotonic_ns']
        for key in ('stdout','stderr'):result[key]=phase_file(folder/(key+'.raw'))
        phase_streams(folder,result);phase_descriptor(started['script'])
        result['script']=phase_file(started['script']['path'])
        need(result['script']==started['script'],'phase script changed')
        if started['binary'] is not None:
            phase_descriptor(started['binary'])
            result['binary']=phase_file(started['binary']['path'])
            need(result['binary']==started['binary'],'phase binary changed')
        need((produced_binary is not None)==(phase=='cmake_build'),'produced binary applicability mismatch')
        if produced_binary is not None:result['produced_binary']=phase_file(produced_binary)
        result['record_complete']=True;result['passed']=exit_code==0
    except Exception as error:result['error']=str(error)
    digest=phase_write(folder/'RESULT.json',result)
    print('N49C_PHASE_FINISH '+phase+' observed_exit='+str(exit_code)+' metadata_complete='+str(result['record_complete']).lower(),flush=True,file=sys.stderr)
    return result,digest

def phase_reconcile(root,identity,platform,actions,output):
    try:phase_check(identity,platform)
    except (ValueError,TypeError,AttributeError) as error:
        known={key:identity.get(key) or None for key in IDENTITY_KEYS}
        rows=[dict(phase=p,native=actions.get(p) if isinstance(actions,dict) else None,
            passed=False,status='bootstrap_identity_unavailable',observed_exit=None,clock=None) for p in PHASE_IDS]
        result=dict(schema='n49c-phase-ledger-v1',kind='bootstrap_failure',identity=known,
            identity_validated=False,unavailable_identity_fields=[k for k,v in known.items() if v is None],
            platform=platform,expected_ids=list(PHASE_IDS),rows=rows,passed=False,export_qualified=False,
            reconciliation_completed=False,
            failures=['strict source/run/job identity unavailable or invalid: '+str(error)])
        phase_write(output,result)
        return result
    need(isinstance(actions,dict) and len(actions)<=len(PHASE_IDS)+1,'bounded native step outcomes required')
    need(set(actions)<=set(PHASE_IDS)|{'phase_ledger'},'unknown native phase ID')
    root=Path(root).resolve();rows=[];failures=[];binary_hash=None;last_return=None
    if root.exists():
        extra=sorted(p.name for p in root.iterdir() if p.name not in PHASE_IDS)
        if extra:failures.append('unknown retained phase IDs: '+','.join(extra))
    for phase in PHASE_IDS:
        row=dict(phase=phase,passed=False,native=actions.get(phase),status='unqualified',observed_exit=None);rows.append(row)
        try:
            native=row['native']
            if platform=='Linux' and phase in WINDOWS_PHASES:
                need(isinstance(native,dict),'missing native outcome')
                need(native.get('outcome')=='skipped' and native.get('conclusion')=='skipped','Windows-only phase unexpectedly ran')
                need(not (root/phase).exists(),'unexpected Windows-only phase evidence')
                row.update(passed=True,status='not_applicable');continue
            if phase in BOOTSTRAP_PHASES:
                need(isinstance(native,dict),'missing native outcome')
                row.update(kind='bootstrap_actions_outcome',observed_exit=None,clock=None)
                need(not (root/phase).exists(),'unexpected bootstrap command record')
                need(native.get('outcome')=='success' and native.get('conclusion')=='success','bootstrap native outcome not successful')
                row.update(passed=True,status='native_success');continue
            folder=root/phase
            returned=None;return_raw=None
            if (folder/'RETURN.json').exists():
                return_raw=bounded_manifest(folder/'RETURN.json');returned=json.loads(return_raw)
                need(returned.get('schema')=='n49c-phase-return-v1','phase return schema mismatch')
                need(returned['identity']==identity and returned['phase']==phase and returned['platform']==platform,'phase return identity mismatch')
                need(type(returned.get('observed_exit')) is int and 0<=returned['observed_exit']<=255,'malformed phase observed exit')
                phase_timestamp(returned['clock'])
                row.update(observed_exit=returned['observed_exit'],return_sha256=hashlib.sha256(return_raw).hexdigest(),status='finalization_incomplete')
            need(isinstance(native,dict),'missing native outcome')
            if not (folder/'START.json').exists():
                row['status']='not_run' if native.get('outcome')=='skipped' else 'start_unavailable'
                raise ValueError('required phase start absent')
            start_raw=bounded_manifest(folder/'START.json');start=json.loads(start_raw)
            row['start_sha256']=hashlib.sha256(start_raw).hexdigest()
            need(native.get('outputs',{}).get('start_sha256')==row['start_sha256'],'native start digest mismatch')
            need(start['phase']==phase and start['identity']==identity and start['platform']==platform,'retained start identity mismatch')
            need(start.get('schema')=='n49c-phase-start-v1' and start.get('status')=='started','retained start schema mismatch')
            phase_timestamp(start['clock'])
            if returned is None:
                row.update(status='interrupted_or_unknown_completion',observed_exit=None)
                raise ValueError('phase started without a valid observed return')
            need((folder/'RESULT.json').exists(),'observed return retained; final phase metadata absent')
            raw=bounded_manifest(folder/'RESULT.json');result=json.loads(raw)
            need(returned.get('schema')=='n49c-phase-return-v1' and result.get('schema')=='n49c-phase-result-v1','phase return/result schema mismatch')
            row.update(result_sha256=hashlib.sha256(raw).hexdigest(),observed_exit=returned.get('observed_exit'))
            need(native.get('outputs',{}).get('result_sha256')==row['result_sha256'],'native result digest mismatch')
            need(result['return_sha256']==hashlib.sha256(return_raw).hexdigest(),'phase return digest mismatch')
            for value in (returned,result):
                need(value['identity']==identity and value['phase']==phase and value['platform']==platform,'phase return/result identity mismatch')
                need(type(value.get('observed_exit')) is int and value['observed_exit']==returned['observed_exit'],'malformed phase exit')
            need(result['start_sha256']==row['start_sha256'],'result start binding mismatch')
            start_clock=start['clock']['monotonic_ns'];return_clock=returned['clock']['monotonic_ns']
            need(type(start_clock) is int and type(return_clock) is int and type(result.get('elapsed_ns')) is int and return_clock>=start_clock and
                 result.get('elapsed_ns')==return_clock-start_clock,'phase clock/elapsed mismatch')
            need(last_return is None or start_clock>=last_return,'retained phases are not in the required order')
            need(native.get('outcome')=='success' and native.get('conclusion')=='success','native phase failed or incomplete')
            need(result['passed'] is True and result['record_complete'] is True and returned['observed_exit']==0,'phase failed or metadata incomplete')
            phase_streams(folder,result);phase_descriptor(start['script'])
            for key in ('script','binary','produced_binary'):
                if key in result:
                    phase_descriptor(result[key]);need(phase_file(result[key]['path'])==result[key],'phase retained '+key+' bytes changed')
            need(result['script']==start['script'],'phase script binding changed')
            need((start.get('binary') is not None)==(phase in BINARY_PHASES),'phase binary applicability changed')
            need(('binary' in result)==(phase in BINARY_PHASES) and ('produced_binary' in result)==(phase=='cmake_build'),'phase result binary applicability changed')
            if phase=='cmake_build':binary_hash=result['produced_binary']['sha256']
            if phase in BINARY_PHASES:
                phase_descriptor(start['binary'])
                need(binary_hash is not None and result['binary']==start['binary'] and result['binary']['sha256']==binary_hash,'different combined binary across phases')
            last_return=return_clock
            row.update(passed=True,status='completed')
        except Exception as error:
            row['error']=str(error);failures.append(phase+': '+str(error))
    try:
        source=root.parent
        need((source/'source.txt').read_text().strip()==identity['commit'],'source capture commit mismatch')
        need((source/'tree.txt').read_text().strip()==identity['tree'],'source capture tree mismatch')
        closure=json.loads(bounded_manifest(source/'source-closure.json'))
        need(closure.get('passed') is True and closure.get('head')==identity['commit'] and closure.get('inventory_sha256')==PIN,'bootstrap source closure missing/mismatched')
    except Exception as error:failures.append('bootstrap artifacts: '+str(error))
    result=dict(schema='n49c-phase-ledger-v1',identity=identity,platform=platform,
        expected_ids=list(PHASE_IDS),rows=rows,failures=failures,passed=not failures,
        export_qualified=False,reconciliation_completed=True,cleanup='native-actions-managed; no independent process-tree proof')
    phase_write(output,result)
    return result

def phase_actions(raw):
    need(isinstance(raw,str) and 0<len(raw.encode('utf-8'))<=65536,'bounded explicit native phase outcomes required')
    def unique(pairs):
        value={}
        for key,item in pairs:
            need(key not in value,'duplicate native phase metadata key')
            value[key]=item
        return value
    result=json.loads(raw,object_pairs_hook=unique)
    need(isinstance(result,dict),'native phase outcomes must be an object')
    return result

def bounded_manifest(path):
    """Bound type, allocation and reads before opening/copying any manifest bytes."""
    path=Path(path);before=path.lstat()
    need(stat.S_ISREG(before.st_mode) and 0<before.st_size<=MAX_MANIFEST,'manifest type/size limit')
    flags=os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0)
    with os.fdopen(os.open(path,flags),'rb') as f:
        opened=os.fstat(f.fileno())
        def snapshot(s):return (s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns)
        need(stat.S_ISREG(opened.st_mode) and 0<opened.st_size<=MAX_MANIFEST and snapshot(opened)==snapshot(before),'manifest changed before bounded read')
        chunks=[];count=0
        while count<opened.st_size:
            chunk=f.read(min(BLOCK,opened.st_size-count))
            need(bool(chunk),'manifest truncated during bounded read')
            count+=len(chunk);chunks.append(chunk)
        after=os.fstat(f.fileno());current=path.lstat()
        need(snapshot(after)==snapshot(opened)==snapshot(current),'manifest changed during bounded read')
    return b''.join(chunks)

class ManifestBudgetExceeded(ValueError):
    def __init__(self,attempted,limit):
        super().__init__('manifest limit exceeded')
        self.diagnostics=dict(manifest_attempted_bytes=attempted,manifest_limit_bytes=limit)

def encode_manifest(value):
    """Enforce the UTF-8 budget before growing the complete encoded buffer."""
    raw=bytearray()
    for text in json.JSONEncoder(sort_keys=True,indent=2).iterencode(value):
        for offset in range(0,len(text),BLOCK//4):
            chunk=text[offset:offset+BLOCK//4].encode('utf-8')
            if len(raw)+len(chunk)>MAX_MANIFEST:raise ManifestBudgetExceeded(len(raw)+len(chunk),MAX_MANIFEST)
            raw.extend(chunk)
    if len(raw)+1>MAX_MANIFEST:raise ManifestBudgetExceeded(len(raw)+1,MAX_MANIFEST)
    raw.extend(b'\n');return bytes(raw)

PRIOR_P = '3ebecf26946ae6ddd04fb018085ffc023b5fcab0'
PRIOR_K = '98b45d264696a23552ca14d12218555c57087528'
PRIOR_BRIDGE_BLOB = '8b3c4e6f04ce57dbf79cb245c94a5e5cd1a1125f'
PRIOR_BRIDGE_SHA256 = '00c2a059665f816adfe5e0a686606991046c92dc778b3c110437f697356855dc'

def pinned_fixture_blob(repository,commit,path,blob,digest,size):
    raw=subprocess.check_output(['git','show',commit+':'+path],cwd=repository)
    need(len(raw)==size and hashlib.sha256(raw).hexdigest()==digest,'fixture byte identity mismatch')
    need(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==blob,'fixture Git identity mismatch')
    return raw

def materialize_prior_fixtures(repository,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    need(not any(output.iterdir()),'fresh prior-fixture directory required')
    p=pinned_fixture_blob(repository,PRIOR_P,'scripts/Install-QbrainMemory.ps1','ff7042fa94b3d6a7b85e06572557fe575ad18c74','1b14e2b57f6de84a0f95f8876dd65b8df96479bf10e58e35a58fe0dec1ee4d74',14474)
    k=pinned_fixture_blob(repository,PRIOR_K,'scripts/Install-QbrainMemory.ps1','90bf59912a58203de600c2ecaf970c7c5a183236','bde21f5c1aabb7b517a1324f3fb076b482a5652387eaab26a1050bb0feb97dd2',14924)
    bridge_p=pinned_fixture_blob(repository,PRIOR_P,'scripts/Invoke-QbrainJson.ps1',PRIOR_BRIDGE_BLOB,PRIOR_BRIDGE_SHA256,4005)
    bridge_k=pinned_fixture_blob(repository,PRIOR_K,'scripts/Invoke-QbrainJson.ps1',PRIOR_BRIDGE_BLOB,PRIOR_BRIDGE_SHA256,4005)
    need(bridge_p==bridge_k and b'\r' not in bridge_p,'prior companion mismatch')
    need(b'\r' not in k,'K raw must be LF only')
    executed=k.replace(b'\n',b'\r\n')
    need(hashlib.sha256(executed).hexdigest()=='d802c230d2e5b0938b81baa115d5cf5b475aa855fce0df28f0305f00575fcc51','K executed identity mismatch')
    files={'P.ps1':p,'K.raw.ps1':k,'K.ps1':executed,'Invoke-QbrainJson.ps1':bridge_p}
    records={}
    for name,raw in files.items():
        (output/name).write_bytes(raw);records[name]=dict(size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    value=dict(schema='qbrain-n49c-prior-fixtures-v1',sources={'P':PRIOR_P,'K':PRIOR_K},bridge_blob=PRIOR_BRIDGE_BLOB,files=records)
    raw=encode_manifest(value);(output/'P-K-INPUTS.json').write_bytes(raw)
    result=dict(manifest_sha256=hashlib.sha256(raw).hexdigest(),files=records)
    verify_prior_fixtures(output,result['manifest_sha256']);return result

def verify_prior_fixtures(output,manifest_sha256):
    output=Path(output);raw=bounded_manifest(output/'P-K-INPUTS.json')
    need(hashlib.sha256(raw).hexdigest()==manifest_sha256,'prior fixture manifest changed')
    m=json.loads(raw)
    need(m['sources']=={'P':PRIOR_P,'K':PRIOR_K} and m['bridge_blob']==PRIOR_BRIDGE_BLOB,'prior fixture source mismatch')
    need(set(m['files'])=={'P.ps1','K.raw.ps1','K.ps1','Invoke-QbrainJson.ps1'},'prior fixture set mismatch')
    for name,row in m['files'].items():
        p=output/name;need(p.is_file() and not p.is_symlink(),'missing or invalid prior fixture')
        need(p.stat().st_size==row['size'] and hash_file(p)==row['sha256'],'prior fixture changed: '+name)
    need(m['files']['Invoke-QbrainJson.ps1']=={'size':4005,'sha256':PRIOR_BRIDGE_SHA256},'companion pin mismatch')
    return True

class BoundedArchive:
    def __init__(self,file,limit):self.file=file;self.limit=limit
    def write(self,data):
        need(self.file.tell()+len(data)<=self.limit,'compressed evidence limit exceeded')
        return self.file.write(data)
    def __getattr__(self,name):return getattr(self.file,name)

def verify_evidence_archive(archive,manifest):
    need(archive.stat().st_size==manifest['archive']['size']<=MAX_ARCHIVE,'archive size mismatch')
    need(hash_file(archive)==manifest['archive']['sha256'],'archive digest mismatch')
    rows=manifest['files'];need(isinstance(rows,list) and rows,'empty member inventory')
    names=[r['path'] for r in rows]
    need(names==sorted(set(names)) and all(safe_member(n) for n in names),'invalid member inventory')
    need(sum(r['size'] for r in rows)==manifest['uncompressed_bytes']<=MAX_RAW,'uncompressed limit/mapping mismatch')
    with zipfile.ZipFile(archive) as z:
        need(z.namelist()==names,'archive member inventory mismatch')
        for row,info in zip(rows,z.infolist()):
            need(info.file_size==row['size'] and 0<=row['size']<=MAX_RAW,'member size mismatch')
            need(stat.S_ISREG(info.external_attr>>16) and (info.external_attr>>16)==row['mode'],'member mode mismatch')
            h=hashlib.sha256();count=0
            with z.open(info) as f:
                while chunk:=f.read(BLOCK):
                    count+=len(chunk);need(count<=row['size'],'member expansion exceeded');h.update(chunk)
            need(count==row['size'] and h.hexdigest()==row['sha256'],'member content mismatch')

def verify_evidence_parts(root,expected,expected_manifest_sha256,part_bytes=PART_BYTES):
    evidence_identity(expected);root=Path(root).resolve(strict=True)
    need(shutil.disk_usage(root.parent).free>=MAX_ARCHIVE+64*BLOCK,'insufficient reconstruction capacity')
    raw=bounded_manifest(root/'00'/'manifest.json')
    need(len(raw)<=MAX_MANIFEST and hashlib.sha256(raw).hexdigest()==expected_manifest_sha256,'authoritative manifest mismatch')
    m=json.loads(raw)
    need(m.get('schema')=='qbrain-n49c-evidence-parts-v1' and m.get('identity')==expected,'independent evidence identity mismatch')
    parts=m['parts'];need(0<len(parts)<=MAX_PARTS,'invalid part count')
    expected_dirs=[f'{i:02d}' for i in range(len(parts))]
    need(sorted(p.name for p in root.iterdir())==expected_dirs,'missing or extra part directory')
    need(sum(p['size'] for p in parts)==m['archive']['size']<=MAX_ARCHIVE,'part aggregate size mismatch')
    with tempfile.TemporaryDirectory(prefix='n49c-reconstruct-',dir=root.parent) as tmp:
        archive=Path(tmp)/'evidence.zip';h=hashlib.sha256();total=0
        with archive.open('wb') as out:
            for i,row in enumerate(parts):
                directory=root/f'{i:02d}'
                need(row['index']==i and row['file']=='evidence.part','part order/name mismatch')
                need(sorted(p.name for p in directory.iterdir())==['evidence.part','manifest.json'],'unexpected part files')
                need(bounded_manifest(directory/'manifest.json')==raw,'manifest copies differ')
                p=directory/row['file'];need(p.is_file() and not p.is_symlink(),'invalid part type')
                need(p.stat().st_size==row['size'] and 0<row['size']<=part_bytes<=PART_BYTES,'part size mismatch')
                need(i==len(parts)-1 or row['size']==part_bytes,'short nonfinal part')
                ph=hashlib.sha256()
                with p.open('rb') as f:
                    while chunk:=f.read(BLOCK):
                        total+=len(chunk);need(total<=m['archive']['size'],'reconstruction overflow');out.write(chunk);ph.update(chunk);h.update(chunk)
                need(ph.hexdigest()==row['sha256'],'part digest mismatch')
        need(total==m['archive']['size'] and h.hexdigest()==m['archive']['sha256'],'concatenation mismatch')
        verify_evidence_archive(archive,m)
    return m

def package_evidence(evidence,staging,identity,part_bytes=PART_BYTES):
    evidence_identity(identity)
    evidence=Path(evidence).resolve(strict=True);staging=Path(staging).absolute()
    need(not staging.exists(),'staging must be new')
    staging.parent.mkdir(parents=True,exist_ok=True);staging=staging.parent.resolve()/staging.name
    need(evidence!=staging and evidence not in staging.parents and staging not in evidence.parents,'evidence and staging must be disjoint')
    source=ROOT.resolve();need(staging!=source and source not in staging.parents,'staging must be outside tracked source')
    need(shutil.disk_usage(staging.parent).free>=MIN_FREE,'insufficient evidence staging capacity')
    need(0<part_bytes<=PART_BYTES,'invalid part bound')
    rows=[];total=0
    for p in sorted(evidence.rglob('*'),key=lambda p:p.relative_to(evidence).as_posix()):
        need(not p.is_symlink(),'evidence symlink rejected')
        if p.is_dir():continue
        need(p.is_file(),'nonregular evidence rejected')
        s=p.stat();name=p.relative_to(evidence).as_posix();need(safe_member(name),'unsafe evidence path')
        total+=s.st_size;need(total<=MAX_RAW,'uncompressed evidence limit exceeded')
        rows.append(dict(path=name,size=s.st_size,mode=stat.S_IFREG|stat.S_IMODE(s.st_mode),sha256=hash_file(p),snapshot=(s.st_size,s.st_mtime_ns,s.st_ino,s.st_mode)))
    need(rows,'no evidence files')
    staging.mkdir();archive=staging/'evidence.zip';parts_root=staging/'parts';parts_root.mkdir()
    with archive.open('w+b') as raw:
        with zipfile.ZipFile(BoundedArchive(raw,MAX_ARCHIVE),'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for row in rows:
                p=evidence/row['path'];s=p.stat();need((s.st_size,s.st_mtime_ns,s.st_ino,s.st_mode)==row['snapshot'],'evidence changed before capture')
                info=zipfile.ZipInfo(row['path'],date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.create_system=3;info.external_attr=row['mode']<<16
                count=0;h=hashlib.sha256()
                with p.open('rb') as src,z.open(info,'w') as dst:
                    while chunk:=src.read(BLOCK):
                        count+=len(chunk);need(count<=row['size'],'evidence grew during capture');h.update(chunk);dst.write(chunk)
                s=p.stat();need((s.st_size,s.st_mtime_ns,s.st_ino,s.st_mode)==row['snapshot'] and count==row['size'] and h.hexdigest()==row['sha256'],'evidence changed during capture')
    current=[]
    for p in sorted(evidence.rglob('*'),key=lambda p:p.relative_to(evidence).as_posix()):
        need(not p.is_symlink(),'evidence became a symlink')
        if p.is_dir():continue
        need(p.is_file(),'evidence became nonregular');current.append(p.relative_to(evidence).as_posix())
    need(current==[r['path'] for r in rows],'evidence member set changed during capture')
    for row in rows:
        p=evidence/row['path'];s=p.stat()
        need((s.st_size,s.st_mtime_ns,s.st_ino,s.st_mode)==row['snapshot'] and hash_file(p)==row['sha256'],'evidence changed after capture')
    parts=[]
    with archive.open('rb') as src:
        while src.tell()<archive.stat().st_size:
            i=len(parts);need(i<MAX_PARTS,'part count limit exceeded');directory=parts_root/f'{i:02d}';directory.mkdir();p=directory/'evidence.part';count=0
            with p.open('wb') as dst:
                while count<part_bytes and (chunk:=src.read(min(BLOCK,part_bytes-count))):dst.write(chunk);count+=len(chunk)
            parts.append(dict(index=i,file=p.name,size=count,sha256=hash_file(p)))
    for row in rows:row.pop('snapshot')
    m=dict(schema='qbrain-n49c-evidence-parts-v1',identity=identity,archive=dict(size=archive.stat().st_size,sha256=hash_file(archive)),uncompressed_bytes=total,files=rows,parts=parts)
    try:raw=encode_manifest(m)
    except ManifestBudgetExceeded as error:
        error.diagnostics.update(member_count=len(rows),archive_size=archive.stat().st_size,part_count=len(parts))
        raise
    for i in range(len(parts)):(parts_root/f'{i:02d}'/'manifest.json').write_bytes(raw)
    digest=hashlib.sha256(raw).hexdigest();verify_evidence_parts(parts_root,identity,digest,part_bytes)
    return dict(passed=True,part_count=len(parts),manifest_sha256=digest,manifest_bytes=len(raw),manifest_limit_bytes=MAX_MANIFEST,member_count=len(rows),archive_sha256=m['archive']['sha256'],archive_size=m['archive']['size'],parts_root=str(parts_root),identity=identity)

def verify_downloaded_artifacts(records,expected,manifest_sha256,part_bytes=PART_BYTES):
    """Records/digests and expected identities must come from independent GitHub reads."""
    evidence_identity(expected);need(0<len(records)<=MAX_PARTS,'invalid downloaded artifact count')
    staging_parent=Path(tempfile.gettempdir()).resolve(strict=True)
    need(shutil.disk_usage(staging_parent).free>=MIN_FREE,'insufficient consumer staging capacity')
    with tempfile.TemporaryDirectory(prefix='n49c-download-verify-',dir=staging_parent) as tmp:
        root=Path(tmp)/'parts';root.mkdir()
        for i,row in enumerate(records):
            need(row['index']==i and row['name']==expected['job_label']+f'-part{i:02d}','artifact index/name mismatch')
            need(str(row['run_id'])==expected['run_id'] and str(row['run_attempt'])==expected['run_attempt'] and row['head_sha']==expected['commit'],'artifact workflow provenance mismatch')
            path=Path(row['path']);need(path.stat().st_size<32*BLOCK,'outer artifact exceeds materializer limit')
            need(hash_file(path)==row['sha256'],'independent GitHub artifact digest mismatch')
            directory=root/f'{i:02d}';directory.mkdir()
            with zipfile.ZipFile(path) as z:
                need(sorted(z.namelist())==['evidence.part','manifest.json'],'unexpected outer artifact members')
                for info in z.infolist():
                    limit=MAX_MANIFEST if info.filename=='manifest.json' else part_bytes
                    need(0<info.file_size<=limit and not stat.S_ISLNK(info.external_attr>>16),'outer artifact member limit/type')
                    count=0
                    with z.open(info) as src,(directory/info.filename).open('wb') as dst:
                        while chunk:=src.read(BLOCK):
                            count+=len(chunk);need(count<=info.file_size,'outer artifact expansion');dst.write(chunk)
                    need(count==info.file_size,'outer artifact member truncated')
        return verify_evidence_parts(root,expected,manifest_sha256,part_bytes)

def contract(raw):
    need(hashlib.sha256(raw).hexdigest() == PIN, 'unapproved inventory digest')
    data = json.loads(raw)
    expected = {r['path']: (r['mode'], r['sha']) for r in data['baseline_inventory']}
    for key in ('PR68', 'PR67'):
        for r in data['module_deltas_from_e0a'][key]:
            expected[r['path']] = (r['mode'], r['sha'])
    need(len(expected) == 1622, 'wrong inherited union count')
    need(not ADDITIVE.intersection(expected), 'additive file replaces inherited input')
    return data, expected

def validate_inventory(expected, actual):
    need(set(actual) == set(expected) | ADDITIVE, 'missing or unexpected tracked path')
    for path, record in expected.items():
        need(actual[path] == record, 'inherited blob/mode changed: ' + path)
    need(all(actual[p][0] == '100644' for p in ADDITIVE), 'unexpected additive mode')

def array(text, name):
    m = re.search(r'\$'+re.escape(name)+r'\s*=\s*@\((.*?)\)', text, re.S)
    need(m is not None, 'missing source array: '+name)
    return re.findall(r'"([^"\r\n]+)"', m[1])

def main(precommit=False):
    prefix = ':' if precommit else 'HEAD:'
    raw = git('show', prefix+INVENTORY)
    data, expected = contract(raw)
    actual = {}
    if precommit:
        for row in git('ls-files', '--stage', '-z').split(b'\0'):
            if not row: continue
            meta, path = row.split(b'\t', 1)
            mode, sha, stage = meta.decode().split()
            need(stage == '0', 'unmerged index entry')
            actual[path.decode()] = (mode, sha)
        need(git('rev-parse', 'HEAD').decode().strip() == PARENTS[0], 'wrong precommit first parent')
        merge = Path(git('rev-parse', '--git-path', 'MERGE_HEAD').decode().strip())
        if not merge.is_absolute(): merge = ROOT/merge
        need(merge.read_text().splitlines() == PARENTS[1:], 'wrong pending merge parents')
        ancestry = set().union(*(set(git('rev-list', s).decode().splitlines()) for s in PARENTS))
    else:
        for row in git('ls-tree', '-r', '-z', 'HEAD').split(b'\0'):
            if not row: continue
            meta, path = row.split(b'\t', 1)
            mode, kind, sha = meta.decode().split()
            need(kind == 'blob', 'unsupported tracked object')
            actual[path.decode()] = (mode, sha)
        ancestry = set(git('rev-list', 'HEAD').decode().splitlines())
        # Find the genuine initial integration commit without assuming a docs successor qualifies.
        rows = git('rev-list', '--parents', 'HEAD').decode().splitlines()
        need(any(r.split()[1:] == PARENTS for r in rows), 'ordered integration parents absent')
    need(set(PARENTS) <= ancestry and not (ancestry & EXCLUDED), 'accepted/excluded ancestry mismatch')
    need(git('rev-parse', '--is-shallow-repository').strip() == b'false', 'incomplete ancestry')
    for key in ('N49A', 'PR68', 'PR67'):
        source = data['sources'][key]
        need(git('rev-parse', source['commit']+'^{tree}').decode().strip() == source['tree'], 'input tree mismatch')
    validate_inventory(expected, actual)
    conversions = []
    for path, (_, sha) in actual.items():
        canonical = git('cat-file', 'blob', sha)
        checked = (ROOT/path).read_bytes()
        if checked != canonical:
            need(b'\r\n' not in canonical and checked == canonical.replace(b'\n', b'\r\n'), 'checkout mismatch: '+path)
            conversions.append(path)
    cmake = (ROOT/'CMakeLists.txt').read_text()
    direct = (ROOT/'scripts/build-cl.ps1').read_text()
    tests = (ROOT/'scripts/build-tests-cl.ps1').read_text()
    sources = [s.replace('\\', '/') for s in array(direct, 'productionSources')]
    cmake_sources = set(re.findall(r'src/qbrain/[\w/]+\.cpp', cmake))
    need(len(sources) == len(set(sources)) == 52 and set(sources) == cmake_sources, 'production source closure')
    names = [Path(s).stem for s in sources]
    need(len(names) == len(set(names)), 'object basename collision')
    prod = array(direct, 'prodObjNames'); test = array(tests, 'prodObjs')
    need(len(prod) == len(set(prod)) == 52 and set(prod) == set(names), 'production link closure')
    need(len(test) == len(set(test)) == 51 and set(test) == (set(names)-{'app','main'})|{'sqlite3'}, 'test link closure')
    block = re.search(r'add_executable\(qbrain_tests\s+(.*?)\)', cmake, re.S)
    need(block is not None, 'canonical tests missing')
    cs = set(re.findall(r'tests/[\w/]+\.cpp', block[1]))
    ds = [s.replace('\\','/') for s in array(tests,'defaultTestSources')]
    need(len(ds) == len(set(ds)) == 59 and set(ds) == cs, 'canonical test source closure')
    groups = re.findall(r'\{"([^"\r\n]+)",\s*test_\w+\}', (ROOT/'tests/test_main.cpp').read_text())
    need(len(groups) == len(set(groups)) == 60, 'original60 registry changed')
    print(json.dumps(dict(passed=True, phase='precommit' if precommit else 'frozen-source',
      head=git('rev-parse','HEAD').decode().strip(), inventory_sha256=PIN,
      inherited_files=len(expected), additive_files=len(ADDITIVE), production_sources=52,
      canonical_test_objects=51, canonical_test_sources=59, original_groups=60,
      checkout_conversions=conversions), indent=2))

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--precommit',action='store_true')
    p.add_argument('--repository',type=Path);p.add_argument('--final',action='store_true')
    p.add_argument('--expected-head');p.add_argument('--expected-tree');p.add_argument('--run-clean',action='store_true')
    p.add_argument('--run-clean-bash');p.add_argument('--bash-version');p.add_argument('--script',type=Path);p.add_argument('--shell-report',type=Path)
    p.add_argument('--observed-bash');p.add_argument('--observed-process-exe');p.add_argument('--observed-script');p.add_argument('--converter')
    p.add_argument('--package-evidence',type=Path);p.add_argument('--staging',type=Path);p.add_argument('--package-diagnostic',type=Path)
    p.add_argument('--run-id');p.add_argument('--run-attempt');p.add_argument('--job-key');p.add_argument('--job-label')
    p.add_argument('--verify-downloads',type=Path);p.add_argument('--manifest-sha256')
    p.add_argument('--phase-start');p.add_argument('--phase-finish');p.add_argument('--phase-ledger',type=Path)
    p.add_argument('--phase-root',type=Path);p.add_argument('--phase-platform');p.add_argument('--phase-script',type=Path)
    p.add_argument('--phase-binary',type=Path);p.add_argument('--phase-produced-binary',type=Path)
    p.add_argument('--phase-start-sha');p.add_argument('--phase-exit',type=int)
    p.add_argument('command',nargs=argparse.REMAINDER)
    args=p.parse_args()
    if args.repository:ROOT=args.repository.resolve(strict=True)
    if args.phase_start or args.phase_finish or args.phase_ledger:
        need(sum(bool(x) for x in (args.phase_start,args.phase_finish,args.phase_ledger))==1 and args.phase_root is not None,'one phase metadata operation and root required')
        identity=dict(commit=args.expected_head,tree=args.expected_tree,run_id=args.run_id,run_attempt=args.run_attempt,job_key=args.job_key,job_label=args.job_label)
        if args.phase_start:
            need(args.phase_script is not None,'phase script identity required')
            print(phase_start(args.phase_root,identity,args.phase_platform,args.phase_start,args.phase_script,args.phase_binary));raise SystemExit(0)
        if args.phase_finish:
            result,digest=phase_finish(args.phase_root,identity,args.phase_platform,args.phase_finish,args.phase_start_sha,args.phase_exit,args.phase_produced_binary)
            print(digest);raise SystemExit(0 if result['passed'] else 1)
        raw=os.environ.get('N49C_PHASE_OUTCOMES','')
        result=phase_reconcile(args.phase_root,identity,args.phase_platform,phase_actions(raw),args.phase_ledger)
        print(json.dumps(result));raise SystemExit(0 if result['passed'] else 1)
    if args.run_clean:
        command=args.command[1:] if args.command[:1]==['--'] else args.command
        raise SystemExit(run_clean(command))
    if args.run_clean_bash:
        need(args.script and args.shell_report and args.bash_version,'complete observed shell binding required')
        observed=dict(bash=args.observed_bash,process_exe=args.observed_process_exe,script=args.observed_script,converter=args.converter,conversion_exit=0 if args.converter else None)
        raise SystemExit(run_bound_bash(args.run_clean_bash,args.script,args.bash_version,args.shell_report,observed))
    if args.package_evidence or args.verify_downloads:
        identity=dict(commit=args.expected_head,tree=args.expected_tree,run_id=args.run_id,run_attempt=args.run_attempt,job_key=args.job_key,job_label=args.job_label)
        if args.verify_downloads:
            result=verify_downloaded_artifacts(json.loads(args.verify_downloads.read_text()),identity,args.manifest_sha256)
            print(json.dumps(dict(passed=True,archive=result['archive'],identity=result['identity'])));raise SystemExit(0)
        try:
            need(args.staging and args.package_diagnostic,'staging and failure diagnostic required')
            result=package_evidence(args.package_evidence,args.staging,identity)
            print(json.dumps(result,sort_keys=True))
            if os.environ.get('GITHUB_OUTPUT'):
                with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as f:
                    f.write('part_count='+str(result['part_count'])+'\nmanifest_sha256='+result['manifest_sha256']+'\n')
            raise SystemExit(0)
        except Exception as exc:
            result=dict(passed=False,error=str(exc),identity=identity,complete_evidence_export=False)
            result.update(getattr(exc,'diagnostics',{}))
            if args.package_diagnostic:
                args.package_diagnostic.parent.mkdir(parents=True,exist_ok=True)
                args.package_diagnostic.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(result,sort_keys=True));raise SystemExit(1)
    if args.final:
        need(bool(args.expected_head) and bool(args.expected_tree),'frozen source pins required')
        result=verify_frozen_checkout(ROOT,args.expected_head,args.expected_tree)
        print(json.dumps(result,indent=2));raise SystemExit(0 if result['passed'] else 1)
    main(args.precommit)
