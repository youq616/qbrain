"""Static source-contract tests, independent of all runtime fixtures."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
import check_n49c_sources as source_gate
from check_n49c_sources import ROOT, INVENTORY, ADDITIVE, contract, validate_inventory, clean_environment, run_clean, verify_frozen_checkout
from test_n49c_process import capture_command
import test_n49c_process as combined_driver

def repair_controls(checks):
    def reject(name,call):
        try:call()
        except (ValueError,OSError,KeyError):checks.append(name+' rejected')
        else:raise RuntimeError(name+' accepted')
    with tempfile.TemporaryDirectory(prefix='n49c-native-repair-controls-') as tmp:
        root=Path(tmp)
        # Git Bash is passed by the actual Actions shell on Windows; Linux uses
        # the running local Bash found for this portable control only.
        exe=os.environ.get('N49C_TEST_BASH')
        if not exe and sys.platform!='win32':exe=shutil.which('bash')
        if not exe:raise RuntimeError('observed test Bash executable required')
        exe=Path(exe).resolve(strict=True)
        version=subprocess.check_output([str(exe),'--noprofile','--norc','-c','printf "%s" "$BASH_VERSION"']).decode()
        scripts=root/'spaces and 非ASCII';scripts.mkdir();script=scripts/'argv 测试.sh'
        script.write_bytes('test -z "${QBRAIN_PG_TEST_DSN:-}"\ntest -z "${OPENAI_API_KEY:-}"\nprintf ok > "$0.ok"\n'.encode('utf-8'))
        hook=root/'ambient-hook.sh';hook.write_text('exit 97\n')
        shadow=root/'shadow';shadow.mkdir();(shadow/'bash').write_text('#!/bin/sh\nexit 98\n');(shadow/'bash').chmod(0o755)
        env={**os.environ,'PATH':str(shadow)+os.pathsep+os.environ.get('PATH',''),'BASH_ENV':str(hook),'ENV':str(hook),'QBRAIN_PG_TEST_DSN':'synthetic-only','OPENAI_API_KEY':'synthetic-only'}
        report=root/'shell.json'
        if source_gate.run_bound_bash(str(exe),script,version,report,environment=env):raise RuntimeError('bound portable Bash failed')
        row=json.loads(report.read_text())
        if Path(str(script)+'.ok').read_bytes()!=b'ok' or row['actual_bash_version']!=version or row['executable_sha256']!=source_gate.hash_file(exe):raise RuntimeError('shell binding/argv evidence missing')
        checks.append('absolute observed Bash ignores PATH shadow and ambient hooks with spaces Unicode argv')
        if source_gate.run_bound_bash('bash',script,version,root/'relative.json')==0:raise RuntimeError('relative Bash accepted')
        checks.append('relative Bash rejected')
        if source_gate.run_bound_bash(str(exe),script,version+'wrong',root/'version.json')==0:raise RuntimeError('wrong Bash version accepted')
        checks.append('exact Bash version mismatch rejected')
        repo=root/'crlf';repo.mkdir();env=clean_environment(os.environ,root/'home')
        def git(*a):return subprocess.check_output(['git',*a],cwd=repo,env=env,stderr=subprocess.DEVNULL).decode().strip()
        git('init');git('config','user.name','Synthetic');git('config','user.email','synthetic@example.invalid');git('config','core.autocrlf','false')
        file=repo/'a.txt';file.write_bytes(b'original\n');git('add','.');git('commit','-m','LF fixture');head=git('rev-parse','HEAD');tree=git('rev-parse','HEAD^{tree}')
        file.write_bytes(b'original\r\n');r=verify_frozen_checkout(repo,head,tree)
        if not r['passed'] or not r['raw_unconfigured_unstaged_diff'] or r['unstaged_diff']:raise RuntimeError('canonical CRLF contract failed')
        checks.append('canonical CRLF accepted with raw diff retained under isolated config')
        file.write_bytes(b'changed\r\n')
        if verify_frozen_checkout(repo,head,tree)['passed']:raise RuntimeError('substantive CRLF mutation accepted')
        checks.append('substantive CRLF mutation rejected')
        git('update-index','--assume-unchanged','a.txt')
        if verify_frozen_checkout(repo,head,tree)['passed']:raise RuntimeError('hidden byte mutation accepted')
        checks.append('assume-unchanged hidden byte mutation rejected')
        evidence=root/'input';evidence.mkdir();payload=b''.join(hashlib.sha256(str(i).encode()).digest() for i in range(450))
        (evidence/'raw.bin').write_bytes(payload);(evidence/'report.json').write_bytes(b'{"synthetic":true}\n')
        identity=dict(commit='1'*40,tree='2'*40,run_id='123',run_attempt='1',job_key='cmake',job_label='synthetic-job')
        result=source_gate.package_evidence(evidence,root/'stage',identity,4096)
        repeated=source_gate.package_evidence(evidence,root/'repeat',identity,4096)
        if result['manifest_sha256']!=repeated['manifest_sha256']:raise RuntimeError('nondeterministic packaging')
        parts=Path(result['parts_root']);anchor=result['manifest_sha256'];m=source_gate.verify_evidence_parts(parts,identity,anchor,4096)
        if len(m['files'])!=2 or m['uncompressed_bytes']!=len(payload)+19:raise RuntimeError('complete evidence inventory failed')
        checks.append('deterministic streamed complete evidence package reconstructed')
        reject('wrong independent commit',lambda:source_gate.verify_evidence_parts(parts,{**identity,'commit':'3'*40},anchor,4096))
        reject('wrong independent run job',lambda:source_gate.verify_evidence_parts(parts,{**identity,'job_label':'other'},anchor,4096))
        reject('wrong independent manifest digest',lambda:source_gate.verify_evidence_parts(parts,identity,'0'*64,4096))
        def modified(name,edit):
            dst=root/name;shutil.copytree(parts,dst);edit(dst);return dst
        bad=modified('modified-part',lambda p:(p/'00'/'evidence.part').write_bytes(b'bad'))
        reject('modified evidence part',lambda:source_gate.verify_evidence_parts(bad,identity,anchor,4096))
        bad=modified('missing-part',lambda p:shutil.rmtree(p/'00'))
        reject('missing evidence part',lambda:source_gate.verify_evidence_parts(bad,identity,anchor,4096))
        bad=modified('extra-part',lambda p:(p/'99').mkdir())
        reject('extra evidence part',lambda:source_gate.verify_evidence_parts(bad,identity,anchor,4096))
        def replace_manifests(p):
            for f in p.glob('*/manifest.json'):f.write_bytes(f.read_bytes()+b' ')
        bad=modified('uniform-manifest',replace_manifests)
        reject('uniform replaced manifest',lambda:source_gate.verify_evidence_parts(bad,identity,anchor,4096))
        bad=modified('wrong-member-hash',lambda p:None);changed=copy.deepcopy(m);changed['files'][0]['sha256']='0'*64
        replacement=(json.dumps(changed,sort_keys=True,indent=2)+'\n').encode()
        for f in bad.glob('*/manifest.json'):f.write_bytes(replacement)
        reject('archive member content mismatch',lambda:source_gate.verify_evidence_parts(bad,identity,hashlib.sha256(replacement).hexdigest(),4096))
        bad=modified('reordered',lambda p:None);a=(bad/'00'/'evidence.part').read_bytes();b=(bad/'01'/'evidence.part').read_bytes();(bad/'00'/'evidence.part').write_bytes(b);(bad/'01'/'evidence.part').write_bytes(a)
        reject('reordered evidence parts',lambda:source_gate.verify_evidence_parts(bad,identity,anchor,4096))
        reject('nested staging',lambda:source_gate.package_evidence(evidence,evidence/'stage',identity,4096))
        reject('part count bound',lambda:source_gate.package_evidence(evidence,root/'too-many',identity,8))
        old=source_gate.MAX_RAW
        try:
            source_gate.MAX_RAW=32
            reject('uncompressed bound',lambda:source_gate.package_evidence(evidence,root/'too-large',identity,4096))
        finally:source_gate.MAX_RAW=old
        old=source_gate.MAX_MANIFEST
        try:
            source_gate.MAX_MANIFEST=10
            reject('manifest size bound',lambda:source_gate.package_evidence(evidence,root/'large-manifest',identity,4096))
        finally:source_gate.MAX_MANIFEST=old
        original_hash=source_gate.hash_file;changed_input=False
        injection_target=evidence/'..'/evidence.name/'raw.bin'
        def changing_hash(path):
            nonlocal changed_input
            digest=original_hash(path)
            if Path(path).samefile(injection_target) and not changed_input:
                changed_input=True;injection_target.write_bytes(payload+b'changed')
            return digest
        try:
            source_gate.hash_file=changing_hash
            reject('evidence changed during capture',lambda:source_gate.package_evidence(evidence,root/'changing-input',identity,4096))
            if not changed_input:raise RuntimeError('required evidence mutation injector did not run')
            checks.append('mutation injector observed through distinct same-file path spelling')
        finally:
            source_gate.hash_file=original_hash;(evidence/'raw.bin').write_bytes(payload)
        disk=source_gate.shutil.disk_usage
        try:
            source_gate.shutil.disk_usage=lambda p:type('Usage',(),{'free':0})()
            reject('insufficient disk capacity',lambda:source_gate.package_evidence(evidence,root/'disk-full',identity,4096))
        finally:source_gate.shutil.disk_usage=disk
        records=[]
        for i,directory in enumerate(sorted(parts.iterdir())):
            archive=root/f'outer-{i}.zip'
            with zipfile.ZipFile(archive,'w') as z:
                for name in ('evidence.part','manifest.json'):z.write(directory/name,name)
            records.append(dict(index=i,name=identity['job_label']+f'-part{i:02d}',run_id='123',run_attempt='1',head_sha=identity['commit'],path=str(archive),sha256=source_gate.hash_file(archive)))
        source_gate.verify_downloaded_artifacts(records,identity,anchor,4096)
        checks.append('independently anchored outer artifact digests and provenance verified')
        disk=source_gate.shutil.disk_usage;temporary=source_gate.tempfile.TemporaryDirectory;member_open=source_gate.zipfile.ZipFile.open
        def forbidden_stage(*args,**kwargs):raise AssertionError('consumer created staging before capacity check')
        def forbidden_member(*args,**kwargs):raise AssertionError('consumer opened ZIP member before capacity check')
        try:
            source_gate.shutil.disk_usage=lambda p:type('Usage',(),{'free':0})()
            source_gate.tempfile.TemporaryDirectory=forbidden_stage;source_gate.zipfile.ZipFile.open=forbidden_member
            reject('consumer zero-space before staging or ZIP member access',lambda:source_gate.verify_downloaded_artifacts(records,identity,anchor,4096))
        finally:
            source_gate.shutil.disk_usage=disk;source_gate.tempfile.TemporaryDirectory=temporary;source_gate.zipfile.ZipFile.open=member_open
        old=source_gate.MAX_MANIFEST;native_open=source_gate.os.open
        def forbidden_manifest_open(*args,**kwargs):raise AssertionError('oversized manifest opened before rejection')
        try:
            source_gate.MAX_MANIFEST=8;source_gate.os.open=forbidden_manifest_open
            reject('oversized first manifest before open or read',lambda:source_gate.verify_evidence_parts(parts,identity,anchor,4096))
        finally:source_gate.MAX_MANIFEST=old;source_gate.os.open=native_open
        bad=modified('oversized-copy',lambda p:None);target=bad/'01'/'manifest.json';raw_manifest=target.read_bytes();target.write_bytes(raw_manifest+b' ')
        def forbid_oversized_copy(path,*args,**kwargs):
            if Path(path)==target:raise AssertionError('oversized manifest copy was opened')
            return native_open(path,*args,**kwargs)
        try:
            source_gate.MAX_MANIFEST=len(raw_manifest);source_gate.os.open=forbid_oversized_copy
            reject('oversized later manifest before open or read',lambda:source_gate.verify_evidence_parts(bad,identity,anchor,4096))
        finally:source_gate.MAX_MANIFEST=old;source_gate.os.open=native_open
        race=root/'racing-manifest.json';race.write_bytes(b'{}');original_lstat=Path.lstat;fdopen=source_gate.os.fdopen;triggered=False;reads=[]
        def racing_lstat(path,*args,**kwargs):
            nonlocal triggered
            result=original_lstat(path,*args,**kwargs)
            if path==race and not triggered:triggered=True;race.write_bytes(b'{} ')
            return result
        class ReadGuard:
            def __init__(self,f):self.f=f
            def __enter__(self):return self
            def __exit__(self,*args):return self.f.__exit__(*args)
            def fileno(self):return self.f.fileno()
            def read(self,n):reads.append(n);raise AssertionError('grown manifest read before fstat rejection')
        try:
            source_gate.MAX_MANIFEST=2;Path.lstat=racing_lstat;source_gate.os.fdopen=lambda *a,**kw:ReadGuard(fdopen(*a,**kw))
            reject('manifest growth between stat and open before byte read',lambda:source_gate.bounded_manifest(race))
            if not triggered or reads:raise RuntimeError('race pre-read control did not exercise rejection')
        finally:source_gate.MAX_MANIFEST=old;Path.lstat=original_lstat;source_gate.os.fdopen=fdopen
        changed=copy.deepcopy(records);changed[0]['sha256']='0'*64
        reject('wrong outer artifact digest',lambda:source_gate.verify_downloaded_artifacts(changed,identity,anchor,4096))
        changed=copy.deepcopy(records);changed[0]['head_sha']='4'*40
        reject('wrong outer artifact provenance',lambda:source_gate.verify_downloaded_artifacts(changed,identity,anchor,4096))
        real_connect=sqlite3.connect;owned=[]
        def tracked_connect(*args,**kwargs):
            conn=real_connect(*args,**kwargs);owned.append(conn);return conn
        def require_closed(conn):
            try:conn.execute('SELECT 1')
            except sqlite3.ProgrammingError:return
            raise RuntimeError('fixture seed connection remained usable')
        for failure in (False,True):
            database=root/('seed-error.db' if failure else 'seed-success.db')
            with combined_driver.closing(real_connect(database)) as setup:
                with setup:
                    setup.execute('CREATE TABLE sources(id TEXT PRIMARY KEY,name TEXT)')
                    if failure:setup.execute("INSERT INTO sources VALUES('beta','beta')")
            try:
                sqlite3.connect=tracked_connect
                try:combined_driver.seed_fixture_sources(database)
                except sqlite3.IntegrityError:
                    if not failure:raise
                else:
                    if failure:raise RuntimeError('expected seed transaction error missing')
            finally:sqlite3.connect=real_connect
            require_closed(owned[-1])
            with combined_driver.closing(real_connect(database)) as inspection:
                rows=inspection.execute('SELECT id FROM sources ORDER BY id').fetchall()
            expected_rows=[('beta',)] if failure else [('alpha',),('beta',)]
            if rows!=expected_rows:raise RuntimeError('seed commit/rollback semantics changed')
            database.unlink()
            checks.append('fixture seed connection closed and file removed after '+('rollback error' if failure else 'successful commit'))
        if len(owned)!=2:raise RuntimeError('seed ownership control did not observe both handles')
        failed_output=root/'failed-combined-process'
        try:combined_driver.main(Path(sys.executable),failed_output,False)
        except ValueError:pass
        else:raise RuntimeError('synthetic failing CLI unexpectedly accepted')
        partial=json.loads((failed_output/'PARTIAL.json').read_bytes())
        if partial['passed'] or not partial['commands'] or json.loads((failed_output/'synthetic-requests.json').read_bytes())!=[]:
            raise RuntimeError('failed combined process lost partial/request evidence')
        checks.append('failed combined process retains partial commands and synthetic request evidence')

def require_failed_capability(row, timeout):
    """Missing diagnostics must remain a hard failure, with the row preserved."""
    if not isinstance(row,dict) or not isinstance(row.get('program'),dict):
        raise RuntimeError('synthetic capability row missing program metadata: '+json.dumps(row))
    cap=row['program'].get('capability')
    if not isinstance(cap,dict):
        raise RuntimeError('synthetic capability row missing capability metadata: '+json.dumps(row))
    for key in ('stdout','stderr'):
        if not isinstance(cap.get(key),dict) or not isinstance(cap[key].get('path'),str):
            raise RuntimeError('synthetic capability row missing '+key+' identity: '+json.dumps(row))
    if row.get('passed') is not False or cap.get('passed') is not False:
        raise RuntimeError('synthetic capability failure was accepted')
    if Path(cap['stdout']['path']).read_bytes()!=b'PARTIAL\0\xff' or Path(cap['stderr']['path']).read_bytes()!=b'ERROR\0\xfe':
        raise RuntimeError('capability failure lost exact raw streams')
    if 'exit' not in cap:
        raise RuntimeError('capability failure missing explicit exit metadata')
    if timeout:
        valid=cap['exit'] is None and cap.get('timed_out') is True
    else:
        valid=type(cap['exit']) is int and cap['exit']==17 and ('timed_out' not in cap or cap['timed_out'] is False)
    if not valid:
        raise RuntimeError('capability failure exit/timeout metadata changed')
    return cap

def synthetic_capability_case(evidence, name, *, timeout=False, wrong_executable=False, before_row=False):
    """Use fake files only as identities; every attempted execution is intercepted."""
    root=evidence/name;root.mkdir(exist_ok=False)
    transcript=[];row=None;failure=None;spec=None;alias=None;resolved=None;fixture_hash=None;fixture_identities={}
    original_run=combined_driver.subprocess.run
    try:
        (root/'segment').mkdir()
        fake=root/'powershell.exe';fake.write_bytes(b'synthetic identity only; never executed')
        alias=root/'segment'/'..'/'powershell.exe'
        resolved=alias.resolve(strict=True);fixture_hash=hashlib.sha256(fake.read_bytes()).hexdigest()
        if alias==resolved or not alias.samefile(resolved):raise RuntimeError('synthetic alias control is not distinct and same-file')
        decoy=root/'pwsh.exe';decoy.write_bytes(b'different synthetic identity; never executed')
        marker=root/'binary.marker';marker.write_bytes(b'synthetic binary identity')
        executable=decoy if wrong_executable else alias
        spec=dict(name=name,executable=str(executable),shell_executable=str(executable),expected_shell_major=5,
            binary=str(marker),binary_sha256=hashlib.sha256(marker.read_bytes()).hexdigest(),expected_exit=0,
            prefix=str(root/'capture'),arguments=['-File','synthetic-never-executed.ps1'])
        fixture_identities={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in (fake,decoy,marker)}
        if before_row:del spec['binary']
        (root/'SPEC.json').write_text(json.dumps(spec,indent=2)+'\n')
        def backend(argv,**kwargs):
            # Retain the attempted call before any filesystem identity operation.
            event=dict(argv=[str(arg)[:32768] for arg in argv[:16]],argv_count=len(argv),
                argv_truncated=len(argv)>16 or any(len(str(arg))>32768 for arg in argv),
                fixture_spelling=str(alias),fixture_resolved=str(resolved),stage='intercepted')
            transcript.append(event)
            try:
                if event['argv_truncated']:raise AssertionError('synthetic intercepted argv exceeds diagnostic bound')
                event['stage']='same-file';observed=Path(argv[0]);same=observed.samefile(resolved);event['same_file']=same
                event['stage']='resolve';event['observed_resolved']=str(observed.resolve(strict=True))
                event['stage']='hash';event['fixture_sha256']=hashlib.sha256(resolved.read_bytes()).hexdigest()
                event['stage']='identity'
                if not same or event['fixture_sha256']!=fixture_hash:raise AssertionError('unexpected synthetic probe executable')
                if any(k.upper()=='PSMODULEPATH' for k in kwargs['env']):raise AssertionError('module path reached child probe')
                version=[str(observed),'-NoProfile','-NonInteractive','-Command','[Console]::Write($PSVersionTable.PSVersion.ToString())']
                if list(argv)==version:
                    event['stage']='version';return subprocess.CompletedProcess(argv,0,b'5.1.0.0',b'')
                expected=[str(observed),'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',
                    str((root/'capture.program-version.capability.ps1').resolve()),'-ProbePath',
                    str((root/'capture.program-version.capability.input').resolve())]
                if list(argv)!=expected:raise AssertionError('original test must not run after failed probe')
                event['stage']='injected-timeout' if timeout else 'injected-error'
                if timeout:raise subprocess.TimeoutExpired(argv,30,output=b'PARTIAL\x00\xff',stderr=b'ERROR\x00\xfe')
                return subprocess.CompletedProcess(argv,17,b'PARTIAL\x00\xff',b'ERROR\x00\xfe')
            except BaseException as error:
                event['exception']=dict(type=type(error).__name__,message=str(error));raise
        combined_driver.subprocess.run=backend
        row=capture_command(spec,root/'ROW.json')
        return row,transcript
    except BaseException as error:
        failure=dict(type=type(error).__name__,message=str(error));raise
    finally:
        combined_driver.subprocess.run=original_run
        record=dict(specification=spec,row=row,exception=failure,interceptions=transcript,
            fixture_spelling=str(alias),fixture_resolved=str(resolved),fixture_sha256=fixture_hash,
            fixture_after_sha256=None,fixture_identities=fixture_identities,fixture_after_identities={},
            postconditions_passed=False,file_inventory_complete=False,diagnostic_errors=[])
        def persist_control():
            raw=(json.dumps(record,indent=2)+'\n').encode('utf-8')
            (root/'CONTROL.json').write_bytes(raw)
            return dict(path='CONTROL.json',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        # Flush the already captured row/call/error before any optional read.
        persist_control()
        def diagnostic_error(stage,path,error):
            value=dict(stage=stage,path=str(path),type=type(error).__name__,message=str(error))
            record['diagnostic_errors'].append(value)
            return value
        if not fixture_identities:
            diagnostic_error('initial-fixture-identity',root,RuntimeError('initial fixture identities unavailable'))
        for path in fixture_identities:
            try:record['fixture_after_identities'][path]=hashlib.sha256(Path(path).read_bytes()).hexdigest()
            except Exception as error:
                record['fixture_after_identities'][path]=None
                diagnostic_error('post-fixture-hash',path,error)
        if resolved is not None:record['fixture_after_sha256']=record['fixture_after_identities'].get(str(resolved))
        record['postconditions_passed']=not record['diagnostic_errors'] and record['fixture_after_identities']==fixture_identities
        if not record['postconditions_passed'] and not record['diagnostic_errors']:
            diagnostic_error('post-fixture-identity',root,RuntimeError('synthetic fixture identity changed'))
        files=[];total=0
        try:paths=sorted(root.iterdir())
        except Exception as error:
            paths=[];diagnostic_error('inventory-list',root,error)
        if len(paths)>24:
            diagnostic_error('inventory-bound',root,RuntimeError('synthetic diagnostic file count exceeded'))
            paths=paths[:24]
        inventory_errors=len(record['diagnostic_errors'])
        for path in paths:
            if path.name in ('CONTROL.json','FILES.json'):continue
            item=dict(path=path.name,bytes=None,sha256=None)
            try:
                if not path.is_file():continue
                size=path.stat().st_size;item['bytes']=size
                if size>1024*1024-total:raise RuntimeError('synthetic diagnostic byte budget exceeded')
                total+=size;item['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            except Exception as error:item['inspection_error']=diagnostic_error('inventory-file',path,error)
            files.append(item)
        record['file_inventory_complete']=len(record['diagnostic_errors'])==inventory_errors and not any(x['stage'] in ('inventory-list','inventory-bound') for x in record['diagnostic_errors'])
        control=persist_control();files.append(control)
        (root/'FILES.json').write_text(json.dumps(files,indent=2)+'\n')
        if not record['postconditions_passed'] or not record['file_inventory_complete']:
            # A pending original exception still propagates unchanged. A captured
            # failed row is preserved verbatim and named in the hard failure.
            if failure is None:
                primary=row.get('error') if isinstance(row,dict) else None
                raise RuntimeError('synthetic diagnostic finalization failed; captured error='+str(primary)+'; see '+str(root/'CONTROL.json'))

def installer_export_controls(checks, evidence):
    def reject(name,call):
        try:call()
        except (ValueError,OSError):checks.append(name+' rejected')
        else:raise RuntimeError(name+' accepted')
    with tempfile.TemporaryDirectory(prefix='n49c-installer-export-controls-',dir=tempfile.gettempdir()) as tmp:
        root=Path(tmp)
        env={**os.environ,'PSModulePath':'synthetic-module-sentinel','PSMODULEPATH':'synthetic-module-sentinel','pSmOdUlEpAtH':'synthetic-module-sentinel','N49C_KEEP':'synthetic-required-value'}
        child="import os,sys;sys.exit(1 if any(k.upper()=='PSMODULEPATH' for k in os.environ) or os.environ.get('N49C_KEEP')!='synthetic-required-value' else 0)"
        if run_clean([sys.executable,'-c',child],env):raise RuntimeError('actual module-path-scrub child failed')
        checks.append('mixed-case PSModulePath absent in actual child with unrelated setting retained')
        digest=hashlib.sha256(b'synthetic').hexdigest()
        value=dict(powershell_version='5.1.0.0',pshome=str(root),command_name='Get-FileHash',command_type='Function',module_name='Microsoft.PowerShell.Utility',module_version='3.1.0.0',module_path=str(root/'synthetic-module.psm1'),sha256=digest)
        combined_driver.validate_powershell_capability(value,'5.1.0.0',digest)
        checks.append('synthetic PowerShell capability metadata validates independently held digest')
        for field,replacement in [('powershell_version','7.0.0'),('sha256','0'*64),('command_name','other'),('module_name','other')]:
            changed={**value,field:replacement}
            reject('capability '+field,lambda:combined_driver.validate_powershell_capability(changed,'5.1.0.0',digest))
        baseline_rows={}
        for timeout in (False,True):
            name='capability-timeout' if timeout else 'capability-error'
            row,transcript=synthetic_capability_case(evidence,name,timeout=timeout)
            baseline_rows[timeout]=row
            require_failed_capability(row,timeout)
            if [event['stage'] for event in transcript]!=['version','injected-timeout' if timeout else 'injected-error']:
                raise RuntimeError('synthetic capability failure injection was not observed: '+json.dumps(transcript))
            checks.append('synthetic '+name+' preserves exact raw streams and remains failed')
            checks.append('synthetic '+name+' uses same-file alias and observes both required probe calls')
        metadata_cases=[(True,'missing-exit','exit',None,True),(True,'non-null-exit','exit',0,False),
            (True,'missing-timeout','timed_out',None,True),(True,'string-timeout','timed_out','false',False),
            (True,'integer-timeout','timed_out',1,False),(True,'false-timeout','timed_out',False,False),
            (False,'missing-exit','exit',None,True),(False,'string-exit','exit','17',False),
            (False,'boolean-exit','exit',True,False),(False,'true-timeout','timed_out',True,False),
            (False,'string-timeout','timed_out','false',False),(False,'integer-timeout','timed_out',0,False),
            (False,'null-timeout','timed_out',None,False)]
        for timeout,label,field,value,remove in metadata_cases:
            changed=copy.deepcopy(baseline_rows[timeout]);cap=changed['program']['capability']
            if remove:cap.pop(field,None)
            else:cap[field]=value
            name=('timeout-' if timeout else 'error-')+label
            (evidence/(name+'.json')).write_text(json.dumps(changed,indent=2)+'\n')
            try:require_failed_capability(changed,timeout)
            except RuntimeError as error:
                if str(error) not in ('capability failure missing explicit exit metadata','capability failure exit/timeout metadata changed'):raise
                (evidence/(name+'.stderr')).write_text(str(error)+'\n')
            else:raise RuntimeError('malformed '+name+' metadata accepted')
            checks.append('malformed '+name+' metadata rejected with row retained')
        explicit_false=copy.deepcopy(baseline_rows[False]);explicit_false['program']['capability']['timed_out']=False
        require_failed_capability(explicit_false,False)
        checks.append('non-timeout explicit Boolean false remains accepted with integer exit17')
        for field in ('program','capability'):
            changed=copy.deepcopy(row)
            if field=='program':del changed['program']
            else:del changed['program']['capability']
            (evidence/('missing-'+field+'.json')).write_text(json.dumps(changed,indent=2)+'\n')
            try:require_failed_capability(changed,True)
            except RuntimeError as error:
                if 'missing '+field+' metadata' not in str(error):raise
                (evidence/('missing-'+field+'.stderr')).write_text(str(error)+'\n')
            else:raise RuntimeError('missing '+field+' metadata accepted')
            checks.append('missing '+field+' metadata fails descriptively with complete row retained')
        wrong,transcript=synthetic_capability_case(evidence,'unexpected-executable',wrong_executable=True)
        if wrong.get('passed') is not False or wrong.get('error')!='unexpected synthetic probe executable' or 'program' in wrong:
            raise RuntimeError('unexpected synthetic executable was not rejected before version metadata')
        if len(transcript)!=1 or transcript[0]['same_file'] or transcript[0]['stage']!='identity':raise RuntimeError('wrong executable injection not observed')
        checks.append('wrong executable rejected before version metadata with complete diagnostic row')
        target=(evidence/'identity-error'/'powershell.exe').resolve();injected=[];original_samefile=Path.samefile
        def fail_observed_identity(path,other):
            resolved_target=target.resolve(strict=True)
            if path==resolved_target and other==resolved_target:
                injected.append(dict(path=str(path),other=str(other)))
                raise OSError('synthetic observed identity stat failure')
            return original_samefile(path,other)
        try:
            Path.samefile=fail_observed_identity
            failed,transcript=synthetic_capability_case(evidence,'identity-error')
        finally:
            Path.samefile=original_samefile
            (evidence/'identity-error-injection.json').write_text(json.dumps(injected,indent=2)+'\n')
        retained=json.loads((evidence/'identity-error/CONTROL.json').read_bytes())
        if len(injected)!=1 or failed.get('passed') is not False or failed.get('error')!='synthetic observed identity stat failure':
            raise RuntimeError('early identity failure injection was not observed and rejected')
        if len(transcript)!=1 or retained['interceptions']!=transcript or transcript[0]['argv'][0]!=str(target.resolve(strict=True)) or transcript[0]['stage']!='same-file':
            raise RuntimeError('early identity failure lost intercepted argv/stage')
        if transcript[0].get('exception')!={'type':'OSError','message':'synthetic observed identity stat failure'} or transcript[0]['argv_truncated']:
            raise RuntimeError('early identity failure lost available exception or complete bounded argv')
        checks.append('early same-file exception retains every intercepted argv stage and exception')
        native_capture=capture_command;native_read=Path.read_bytes;read_failures=[]
        def capture_with_persistent_read_error(spec,result):
            target=Path(spec['executable']).resolve(strict=True)
            def failed_read(path):
                if path==target:
                    read_failures.append(dict(path=str(path),buffered_control=(evidence/'persistent-read-error/CONTROL.json').is_file()))
                    raise OSError('synthetic persistent fixture read failure')
                return native_read(path)
            Path.read_bytes=failed_read
            return native_capture(spec,result)
        try:
            globals()['capture_command']=capture_with_persistent_read_error
            try:synthetic_capability_case(evidence,'persistent-read-error')
            except RuntimeError as error:
                if 'synthetic diagnostic finalization failed; captured error=synthetic persistent fixture read failure' not in str(error):raise
                (evidence/'persistent-read-error.stderr').write_text(str(error)+'\n')
            else:raise RuntimeError('persistent fixture read error was accepted')
        finally:
            Path.read_bytes=native_read;globals()['capture_command']=native_capture
            (evidence/'persistent-read-injection.json').write_text(json.dumps(read_failures,indent=2)+'\n')
        retained=json.loads((evidence/'persistent-read-error/CONTROL.json').read_bytes())
        failed=json.loads((evidence/'persistent-read-error/ROW.json').read_bytes())
        inventory=json.loads((evidence/'persistent-read-error/FILES.json').read_bytes())
        if len(read_failures)<3 or read_failures[0]['buffered_control'] or not all(x['buffered_control'] for x in read_failures[1:]):
            raise RuntimeError('persistent read injection did not prove buffering before post/inventory reads')
        if failed.get('passed') is not False or failed.get('error')!='synthetic persistent fixture read failure' or retained['row']!=failed:
            raise RuntimeError('persistent read error lost the original failed row')
        if len(retained['interceptions'])!=1 or retained['interceptions'][0]['stage']!='hash' or retained['interceptions'][0].get('exception')!={'type':'OSError','message':'synthetic persistent fixture read failure'}:
            raise RuntimeError('persistent read failure lost intercepted argv/stage/exception')
        if retained['postconditions_passed'] or retained['file_inventory_complete'] or {x['stage'] for x in retained['diagnostic_errors']}!={'post-fixture-hash','inventory-file'}:
            raise RuntimeError('persistent read failure falsely completed diagnostic inspection')
        if not any(x['path']=='powershell.exe' and x.get('inspection_error') and x['sha256'] is None for x in inventory):
            raise RuntimeError('persistent inventory error was not retained')
        checks.append('persistent fixture read failure flushes complete row transcript before post-read and inventory errors')
        try:synthetic_capability_case(evidence,'before-row-error',before_row=True)
        except KeyError as error:
            if error.args!=('binary',):raise
        else:raise RuntimeError('pre-row error fixture unexpectedly accepted')
        early=json.loads((evidence/'before-row-error/CONTROL.json').read_bytes())
        if early['row'] is not None or early['exception']!={'type':'KeyError','message':"'binary'"} or early['interceptions']:
            raise RuntimeError('pre-row failure did not preserve complete available diagnostics')
        checks.append('pre-row failure retains specification fixture identities and exception without execution')
        fixtures=root/'fixtures';result=source_gate.materialize_prior_fixtures(ROOT,fixtures)
        source_gate.verify_prior_fixtures(fixtures,result['manifest_sha256'])
        bridge=fixtures/'Invoke-QbrainJson.ps1';raw=bridge.read_bytes()
        if not (fixtures/'P.ps1').is_file() or not (fixtures/'K.ps1').is_file() or b'\r' in raw or len(raw)!=4005:raise RuntimeError('pinned sibling layout/bytes mismatch')
        checks.append('both accepted prior fixtures have exact pinned raw sibling bridge')
        bridge.unlink();reject('missing prior companion',lambda:source_gate.verify_prior_fixtures(fixtures,result['manifest_sha256']));bridge.write_bytes(raw+b' ')
        reject('changed prior companion',lambda:source_gate.verify_prior_fixtures(fixtures,result['manifest_sha256']));bridge.write_bytes(raw)
        reject('mismatched historical companion pin',lambda:source_gate.pinned_fixture_blob(ROOT,source_gate.PRIOR_P,'scripts/Invoke-QbrainJson.ps1','0'*40,source_gate.PRIOR_BRIDGE_SHA256,4005))
        value={'files':[{'path':f'synthetic-{i:05d}','sha256':'a'*64} for i in range(24000)]}
        encoded=source_gate.encode_manifest(value)
        if not 2*source_gate.BLOCK<len(encoded)<source_gate.MAX_MANIFEST or json.loads(encoded)!=value:raise RuntimeError('expanded manifest lost entries')
        expanded_size=len(encoded)
        checks.append('manifest above former 2 MiB cap retains every synthetic entry')
        overhead=len(source_gate.encode_manifest({'x':''}));exact={'x':'a'*(source_gate.MAX_MANIFEST-overhead)}
        encoded=source_gate.encode_manifest(exact)
        if len(encoded)!=source_gate.MAX_MANIFEST:raise RuntimeError('exact manifest capacity failed')
        path=root/'maximum-manifest.json';path.write_bytes(encoded)
        if source_gate.bounded_manifest(path)!=encoded:raise RuntimeError('exact-cap bounded read failed')
        checks.append('exact 8 MiB manifest serialization and bounded read accepted')
        reject('one-byte-over manifest serialization',lambda:source_gate.encode_manifest({'x':exact['x']+'a'}))
        path.write_bytes(encoded+b' ');reject('one-byte-over manifest pre-read',lambda:source_gate.bounded_manifest(path));path.write_bytes(encoded)
        envelope=root/'maximum-envelope.zip'
        with zipfile.ZipFile(envelope,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=0) as z:
            with z.open('evidence.part','w') as out:
                for _ in range(20):out.write(b'x'*source_gate.BLOCK)
            z.write(path,'manifest.json')
        if envelope.stat().st_size>=32*source_gate.BLOCK:raise RuntimeError('maximum outer ZIP exceeds tool ceiling')
        envelope_size=envelope.stat().st_size
        checks.append('actual 20 plus 8 MiB outer ZIP remains below 32 MiB with framing')
        if source_gate.MIN_FREE!=3*source_gate.MAX_ARCHIVE+16*source_gate.MAX_MANIFEST+64*source_gate.BLOCK:raise RuntimeError('staging budget arithmetic mismatch')
        disk=source_gate.shutil.disk_usage;temporary=source_gate.tempfile.TemporaryDirectory
        def forbidden_stage(*a,**kw):raise AssertionError('staged below revised resource budget')
        try:
            source_gate.shutil.disk_usage=lambda p:type('Usage',(),{'free':source_gate.MIN_FREE-1})()
            source_gate.tempfile.TemporaryDirectory=forbidden_stage
            identity=dict(commit='1'*40,tree='2'*40,run_id='1',run_attempt='1',job_key='synthetic',job_label='synthetic')
            reject('consumer one byte below revised 1152 MiB budget',lambda:source_gate.verify_downloaded_artifacts([{}],identity,'0'*64))
            evidence=root/'tiny-evidence';evidence.mkdir();(evidence/'a').write_bytes(b'a')
            reject('producer one byte below revised 1152 MiB budget',lambda:source_gate.package_evidence(evidence,root/'no-capacity',identity))
        finally:source_gate.shutil.disk_usage=disk;source_gate.tempfile.TemporaryDirectory=temporary
        try:
            source_gate.shutil.disk_usage=lambda p:type('Usage',(),{'free':source_gate.MIN_FREE})()
            result=source_gate.package_evidence(evidence,root/'exact-capacity',identity)
            partroot=Path(result['parts_root']);downloaded=[]
            for index,directory in enumerate(sorted(partroot.iterdir())):
                archive=root/f'exact-budget-{index}.zip'
                with zipfile.ZipFile(archive,'w') as z:
                    for name in ('evidence.part','manifest.json'):z.write(directory/name,name)
                downloaded.append(dict(index=index,name='synthetic'+f'-part{index:02d}',run_id='1',run_attempt='1',head_sha='1'*40,path=str(archive),sha256=source_gate.hash_file(archive)))
            source_gate.verify_downloaded_artifacts(downloaded,identity,result['manifest_sha256'])
        finally:source_gate.shutil.disk_usage=disk
        checks.append('producer and consumer accept exact synthetic 1152 MiB budget')
        old=source_gate.MAX_MANIFEST
        try:
            source_gate.MAX_MANIFEST=10
            try:source_gate.package_evidence(evidence,root/'measured-overflow',identity)
            except source_gate.ManifestBudgetExceeded as error:
                d=error.diagnostics
                if d['manifest_attempted_bytes']<=d['manifest_limit_bytes'] or d['member_count']!=1 or d['part_count']!=1 or d['archive_size']<=0:raise RuntimeError('numeric overflow diagnostics incomplete')
            else:raise RuntimeError('overflow fixture unexpectedly accepted')
        finally:source_gate.MAX_MANIFEST=old
        checks.append('manifest overflow retains numeric bytes count archive and part diagnostics')
        return dict(expanded_manifest_bytes=expanded_size,expanded_manifest_entries=24000,exact_manifest_bytes=source_gate.MAX_MANIFEST,maximum_outer_zip_bytes=envelope_size,outer_tool_ceiling_bytes=32*source_gate.BLOCK,preflight_budget_bytes=source_gate.MIN_FREE)

def main(evidence):
    raw=(ROOT/INVENTORY).read_bytes()
    if b'\r\n' in raw: raw=raw.replace(b'\r\n', b'\n')
    _, expected=contract(raw)
    actual={**expected, **{p:('100644','0'*40) for p in ADDITIVE}}
    validate_inventory(expected,actual)
    checks=['valid exact inventory']
    for kind in ('missing','extra','blob','mode','additive-mode'):
        changed=copy.deepcopy(actual);path=next(iter(expected))
        if kind=='missing':del changed[path]
        elif kind=='extra':changed['unexpected.txt']=('100644','0'*40)
        elif kind=='blob':changed[path]=(changed[path][0],'0'*40)
        elif kind=='mode':changed[path]=('100755',changed[path][1])
        else:changed[next(iter(ADDITIVE))]=('100755','0'*40)
        try:validate_inventory(expected,changed)
        except ValueError:checks.append(kind+' rejected')
        else:raise RuntimeError(kind+' accepted')
    try:contract(raw+b' ')
    except ValueError:checks.append('inventory digest rejected')
    else:raise RuntimeError('changed inventory accepted')
    sentinel={**os.environ,'QBRAIN_PG_TEST_DSN':'synthetic-not-a-database','QBRAIN_PG_DSN':'synthetic-only',
        'PGPASSWORD':'synthetic-only','OPENAI_API_KEY':'synthetic-only','ANTHROPIC_API_KEY':'synthetic-only',
        'CUSTOM_PROVIDER_TOKEN':'synthetic-only','GIT_CONFIG_GLOBAL':'synthetic-only'}
    with tempfile.TemporaryDirectory(prefix='n49c-synthetic-final-gate-') as tmp:
        clean=clean_environment(sentinel,tmp)
        for key in ('QBRAIN_PG_TEST_DSN','QBRAIN_PG_DSN','PGPASSWORD','OPENAI_API_KEY','ANTHROPIC_API_KEY','CUSTOM_PROVIDER_TOKEN'):
            if key in clean:raise RuntimeError('environment sanitizer left sentinel key')
        if clean['HOME']!=tmp or clean['GIT_CONFIG_GLOBAL']!=os.devnull:raise RuntimeError('config isolation failed')
        child="import os,sys;keys=('QBRAIN_PG_TEST_DSN','QBRAIN_PG_DSN','PGPASSWORD','OPENAI_API_KEY','ANTHROPIC_API_KEY','CUSTOM_PROVIDER_TOKEN');sys.exit(1 if any(k in os.environ for k in keys) or os.environ.get('HOME')==sys.argv[1] else 0)"
        if run_clean([sys.executable,'-c',child,os.environ.get('HOME','')],sentinel):raise RuntimeError('actual sanitized child failed')
        checks.append('synthetic sentinel-only child environment scrubbed')
        repo=Path(tmp)/'repo';repo.mkdir()
        def git(*args):return subprocess.check_output(['git',*args],cwd=repo,env=clean,stderr=subprocess.DEVNULL).decode().strip()
        git('init');git('config','core.autocrlf','false');git('config','user.name','Synthetic Fixture');git('config','user.email','fixture@example.invalid')
        source=repo/'source.txt';source.write_bytes(b'original\n');git('add','source.txt');git('commit','-m','synthetic baseline')
        head=git('rev-parse','HEAD');tree=git('rev-parse','HEAD^{tree}')
        if not verify_frozen_checkout(repo,head,tree)['passed']:raise RuntimeError('clean synthetic tree rejected')
        checks.append('clean frozen identity accepted')
        source.write_bytes(b'changed\n')
        if verify_frozen_checkout(repo,head,tree)['passed']:raise RuntimeError('unstaged change accepted')
        checks.append('unstaged tracked mutation rejected')
        git('add','source.txt')
        if verify_frozen_checkout(repo,head,tree)['passed']:raise RuntimeError('staged change accepted')
        checks.append('staged mutation rejected despite clean worktree diff')
        git('commit','-m','synthetic changed tree')
        if verify_frozen_checkout(repo,head,tree)['passed']:raise RuntimeError('moved HEAD/tree accepted')
        checks.append('moved HEAD and tree rejected')
        newhead=git('rev-parse','HEAD');newtree=git('rev-parse','HEAD^{tree}')
        git('commit','--allow-empty','-m','synthetic same tree new commit')
        if verify_frozen_checkout(repo,newhead,newtree)['passed']:raise RuntimeError('moved HEAD same tree accepted')
        checks.append('moved HEAD with identical tree rejected')
        marker=Path(tmp)/'synthetic-binary-marker';marker.write_bytes(b'not an executable; identity fixture only')
        marker_hash=hashlib.sha256(marker.read_bytes()).hexdigest()
        report=Path(tmp)/'capture-report.json'
        spec=dict(name='raw-capture',executable=sys.executable,shell_executable=sys.executable,
            expected_shell_major=sys.version_info.major,binary=str(marker),binary_sha256=marker_hash,
            expected_exit=0,prefix=str(Path(tmp)/'raw-capture'),cwd=tmp,
            arguments=['-c',"import os,pathlib,sys;keys=('QBRAIN_PG_TEST_DSN','OPENAI_API_KEY');sys.exit(9) if any(k in os.environ for k in keys) else None;pathlib.Path(sys.argv[2]).write_bytes(b'{}');sys.stdout.buffer.write(b'OUT\\x00\\xff\\r\\n');sys.stderr.buffer.write(b'ERR\\x00\\xfe\\n')",'-Report',str(report)])
        old={k:os.environ.get(k) for k in ('QBRAIN_PG_TEST_DSN','OPENAI_API_KEY')}
        try:
            for key in old:os.environ[key]='synthetic-sentinel-only'
            row=capture_command(spec,Path(tmp)/'raw-row.json')
        finally:
            for key,value in old.items():
                if value is None:os.environ.pop(key,None)
                else:os.environ[key]=value
        if not row['passed'] or Path(row['stdout']['path']).read_bytes()!=b'OUT\0\xff\r\n' or Path(row['stderr']['path']).read_bytes()!=b'ERR\0\xfe\n':
            raise RuntimeError('separate raw-byte capture failed')
        if row['reports'][0]['after']['sha256']!=hashlib.sha256(b'{}').hexdigest() or not row['program']['version']:
            raise RuntimeError('version or report binding missing')
        checks.append('raw stdout stderr full program version and report digest bound')
        bad={**spec,'name':'postcondition','prefix':str(Path(tmp)/'postcondition'),
            'arguments':['-c',"import pathlib,sys;pathlib.Path(sys.argv[1]).write_bytes(b'changed')",str(marker)]}
        row=capture_command(bad,Path(tmp)/'postcondition-row.json')
        if row['passed'] or row.get('actual_exit')!=0:raise RuntimeError('exit0 binary corruption accepted')
        checks.append('successful child cannot hide binary postcondition failure')
        marker.write_bytes(b'not an executable; identity fixture only')
        missing={**spec,'name':'missing-report','prefix':str(Path(tmp)/'missing-report'),
            'arguments':['-c','pass','-Report',str(Path(tmp)/'absent-report.json')]}
        row=capture_command(missing,Path(tmp)/'missing-report-row.json')
        if row['passed'] or row.get('actual_exit')!=0:raise RuntimeError('exit0 missing report accepted')
        checks.append('successful child cannot omit required report')
    repair_controls(checks)
    measurements=installer_export_controls(checks,evidence)
    print(json.dumps(dict(passed=True,checks=checks,check_count=len(checks),installer_export_measurements=measurements,synthetic_evidence=str(evidence))))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--evidence',type=Path,help='New directory retaining synthetic probe evidence on success and failure')
    args=parser.parse_args()
    if args.evidence is None:evidence=Path(tempfile.mkdtemp(prefix='n49c-contract-evidence-')).resolve()
    else:
        evidence=args.evidence.resolve();evidence.mkdir(parents=True,exist_ok=False)
    print('Synthetic contract evidence: '+str(evidence),file=sys.stderr)
    main(evidence)
