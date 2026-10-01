"""Static source-contract tests, independent of all runtime fixtures."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile
import check_n49c_sources as source_gate
from check_n49c_sources import ROOT, INVENTORY, ADDITIVE, contract, validate_inventory, clean_environment, run_clean, verify_frozen_checkout
from test_n49c_process import capture_command

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
        def changing_hash(path):
            nonlocal changed_input
            digest=original_hash(path)
            if Path(path)==evidence/'raw.bin' and not changed_input:
                changed_input=True;(evidence/'raw.bin').write_bytes(payload+b'changed')
            return digest
        try:
            source_gate.hash_file=changing_hash
            reject('evidence changed during capture',lambda:source_gate.package_evidence(evidence,root/'changing-input',identity,4096))
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
    print(json.dumps(dict(passed=True,checks=checks,check_count=len(checks))))

if __name__=='__main__':main()
