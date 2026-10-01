"""Static source-contract tests, independent of all runtime fixtures."""
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

def installer_export_controls(checks):
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
        fake=root/'powershell.exe';fake.write_bytes(b'synthetic identity only; never executed')
        marker=root/'binary.marker';marker.write_bytes(b'synthetic binary identity')
        original_run=combined_driver.subprocess.run
        for timeout in (False,True):
            name='capability-timeout' if timeout else 'capability-error'
            def backend(argv,**kwargs):
                if Path(argv[0])!=fake:raise AssertionError('unexpected synthetic probe executable')
                if any(k.upper()=='PSMODULEPATH' for k in kwargs['env']):raise AssertionError('module path reached child probe')
                if '-Command' in argv:return subprocess.CompletedProcess(argv,0,b'5.1.0.0',b'')
                if '-File' not in argv or not any(str(a).endswith('.capability.ps1') for a in argv):raise AssertionError('original test must not run after failed probe')
                if timeout:raise subprocess.TimeoutExpired(argv,30,output=b'PARTIAL\x00\xff',stderr=b'ERROR\x00\xfe')
                return subprocess.CompletedProcess(argv,17,b'PARTIAL\x00\xff',b'ERROR\x00\xfe')
            spec=dict(name=name,executable=str(fake),shell_executable=str(fake),expected_shell_major=5,binary=str(marker),binary_sha256=hashlib.sha256(marker.read_bytes()).hexdigest(),expected_exit=0,prefix=str(root/name),arguments=['-File','synthetic-never-executed.ps1'])
            try:
                combined_driver.subprocess.run=backend;row=capture_command(spec,root/(name+'.json'))
            finally:combined_driver.subprocess.run=original_run
            cap=row['program']['capability']
            if row['passed'] or cap['passed'] or Path(cap['stdout']['path']).read_bytes()!=b'PARTIAL\0\xff' or Path(cap['stderr']['path']).read_bytes()!=b'ERROR\0\xfe':raise RuntimeError('capability failure lost raw streams')
            if timeout and not cap.get('timed_out'):raise RuntimeError('probe timeout status missing')
            checks.append('synthetic '+name+' preserves exact raw streams and remains failed')
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

def main():
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
    measurements=installer_export_controls(checks)
    print(json.dumps(dict(passed=True,checks=checks,check_count=len(checks),installer_export_measurements=measurements)))

if __name__=='__main__':main()
