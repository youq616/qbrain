"""Static source-contract tests, independent of all runtime fixtures."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from check_n49c_sources import ROOT, INVENTORY, ADDITIVE, contract, validate_inventory, clean_environment, run_clean, verify_frozen_checkout
from test_n49c_process import capture_command

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
    print(json.dumps(dict(passed=True,checks=checks,check_count=len(checks))))

if __name__=='__main__':main()
