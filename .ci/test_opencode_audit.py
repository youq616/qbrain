"""N48B actual native qbrain CLI, isolated fixtures; no OpenCode or model launch."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

CHECKS=('paths_readable','configuration_unambiguous','no_ancestor_configuration',
 'no_environment_override','no_pending_recovery','no_staging_conflict',
 'owned_registration_present','ownership_valid','configuration_matches',
 'executable_exists','executable_matches','executable_eligible',
 'expected_format_matches','expected_access_matches','observations_stable')
FIELDS={'schema','result','checks','registered_format','registered_write_enabled','expected_format',
 'expected_write_enabled','registered_bytes_verified','process_started','model_calls',
 'effective_configuration_verified','host_consumption_verified','global_configuration_inspected',
 'remote_configuration_inspected','read_only','observation_scope','limitations'}

def sha(raw): return hashlib.sha256(raw).hexdigest()
def encoded(value): return (json.dumps(value,ensure_ascii=False,sort_keys=True)+'\n').encode()

def validate(value):
    def need(ok):
        if not ok: raise ValueError('audit_contract_rejected')
    need(isinstance(value,dict) and set(value)==FIELDS)
    need(value['schema']=='qbrain-opencode-audit-v1')
    need(value['result'] in ('UNVERIFIABLE','NOT_REGISTERED','BLOCKED','LOCAL_REGISTRATION_CHECKS_PASSED'))
    rows=value['checks'];need(isinstance(rows,list) and len(rows)==15)
    need([r.get('check') for r in rows]==list(CHECKS))
    need(all(set(r)=={'check','passed'} and (r['passed'] is None or type(r['passed']) is bool) for r in rows))
    for name in ('process_started','effective_configuration_verified','host_consumption_verified',
                 'global_configuration_inspected','remote_configuration_inspected'):
        need(value[name] is False)
    need(value['read_only'] is True and type(value['model_calls']) is int and value['model_calls']==0)
    need(type(value['registered_bytes_verified']) is bool)
    for name in ('registered_format','expected_format'):
        need(value[name] is None or (type(value[name]) is int and value[name] in (1,2)))
    for name in ('registered_write_enabled','expected_write_enabled'):
        need(value[name] is None or type(value[name]) is bool)
    need(value['observation_scope']=='project_registration_and_ancestor_presence')
    need(value['limitations']==['Not a host load, model call or effective-config verification',
        'Before/after read agreement is not a lock, permanent snapshot or ABA defense',
        'Executable eligibility is not a PE/signature/authenticity check',
        'No automatic recovery, cleanup, permission change or global-config inspection'])
    if value['result']=='LOCAL_REGISTRATION_CHECKS_PASSED':
        need(value['registered_bytes_verified'] is True)
        need(value['registered_format'] in (1,2) and type(value['registered_write_enabled']) is bool)
        for i,row in enumerate(rows):
            if i==12 and value['expected_format'] is None: need(row['passed'] is None)
            elif i==13 and value['expected_write_enabled'] is None: need(row['passed'] is None)
            else: need(row['passed'] is True)
    else: need(value['registered_bytes_verified'] is False)
    need(len(encoded(value))<=8192)
    return True


def run(binary:Path,output:Path):
    output.mkdir(parents=True,exist_ok=False)
    records=[];checks=[];failure=None
    def check(ok,name):
        checks.append({'name':name,'passed':bool(ok)})
        if not ok:raise ValueError(name)
    try:
      with tempfile.TemporaryDirectory(prefix='n48b-cli-') as temp:
        root=Path(temp); project=root/'private-project-中文';project.mkdir()
        home=root/'home';home.mkdir(); config=project/'opencode.jsonc'
        registered=root/('private-executable.exe' if os.name=='nt' else 'private-executable')
        shutil.copyfile(binary,registered);registered.chmod(0o700);original_binary=registered.read_bytes()
        original=b'\xef\xbb\xbf// PRIVATE-AUDIT-SENTINEL\n{"mcp":{},"provider":{"secret":"PRIVATE-AUDIT-SENTINEL"},}\n'
        config.write_bytes(original)
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENCODE','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
        env.update(HOME=str(home),USERPROFILE=str(home),LOCALAPPDATA=str(home),APPDATA=str(home))
        def snapshot():
            rows=[]
            for path in sorted(root.rglob('*')):
                s=path.lstat()
                item=[str(path.relative_to(root)),stat.S_IFMT(s.st_mode),stat.S_IMODE(s.st_mode),s.st_nlink]
                if path.is_symlink():item.append(os.readlink(path))
                elif path.is_file():item.append(sha(path.read_bytes()))
                rows.append(item)
            return sha(encoded(rows))
        def call(args,code=0):
            p=subprocess.run([str(binary),'opencode',*args],cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
            records.append({'args':args,'exit':p.returncode,'stdout':p.stdout.decode('utf-8'),'stderr':p.stderr.decode('utf-8')})
            if p.returncode!=code or p.stderr:raise ValueError('unexpected command result')
            return json.loads(p.stdout)
        def audit(extra=(),code=1):
            before=snapshot();r=call(['audit','--project',str(project),*extra],code)
            check(snapshot()==before,'audit preserves every fixture file and mode')
            validate(r)
            raw=encoded(r)
            check(all(x not in raw for x in (b'PRIVATE-AUDIT-SENTINEL',str(root).encode(),b'private-project',b'private-executable')),'output excludes original content and paths')
            return r
        def result(label,r,value):check(r['result']==value,label)
        def item(r,name):return next(x['passed'] for x in r['checks'] if x['check']==name)
        result('unregistered report',audit(),'NOT_REGISTERED')
        def install(version,write):
            args=['--project',str(project),'--binary',str(registered),'--brain','audit-test','--format',version]
            if write:args+=['--allow-write']
            plan=call(['preview',*args]);call(['install',*args,'--approve-sha256',plan['plan_sha256']])
        for version in ('v1','v2'):
            for write in (False,True):
                install(version,write)
                positive=audit(['--expect-format',version,'--expect-access','read-write' if write else 'read-only'],0)
                result('valid selected mode',positive,'LOCAL_REGISTRATION_CHECKS_PASSED')
                mismatch=audit(['--expect-format','v2' if version=='v1' else 'v1','--expect-access','read-only' if write else 'read-write'])
                check(item(mismatch,'expected_format_matches') is False and item(mismatch,'expected_access_matches') is False,'expectations check but never grant permission')
        good_config=config.read_bytes()
        data=(home if os.name=='nt' else home/'.local/share')/'Qbrain/integrations/opencode'
        owners=list(data.glob('*/owner.json'));check(len(owners)==1,'one project owner')
        owner=owners[0];good_owner=owner.read_bytes()
        registered.write_bytes(b'not-the-approved-program')
        status=call(['status','--project',str(project)])
        check(status['configuration_matches'] is True,'old status only certifies config bytes')
        r=audit();check(item(r,'executable_matches') is False,'audit independently catches replaced EXE')
        registered.write_bytes(original_binary)
        renamed=root/'saved-program';registered.rename(renamed)
        r=audit();check(item(r,'executable_exists') is False,'missing binary caught')
        renamed.rename(registered)
        if os.name!='nt':
            registered.chmod(0o600);check(item(audit(),'executable_eligible') is False,'execute mode checked without starting process');registered.chmod(0o700)
        config.write_bytes(good_config+b'// external change\n')
        check(item(audit(),'configuration_matches') is False,'external config edit blocked');config.write_bytes(good_config)
        owner.write_bytes(b'{"duplicate":1,"duplicate":2}')
        check(item(audit(),'ownership_valid') is False,'duplicate key owner rejected');owner.write_bytes(good_owner)
        for name in ('opencode.json','.opencode/opencode.json','.opencode/opencode.jsonc'):
            other=project/name;other.parent.mkdir(parents=True,exist_ok=True);other.write_text('{}')
            check(item(audit(),'configuration_unambiguous') is False,'project layer reported');other.unlink()
        ancestor=root/'opencode.json';ancestor.write_bytes(b'PRIVATE-AUDIT-SENTINEL'*10000)
        check(item(audit(),'no_ancestor_configuration') is False,'ancestor detection does not require parsing content');ancestor.unlink()
        for name in ('OPENCODE_CONFIG','OPENCODE_CONFIG_CONTENT','OPENCODE_CONFIG_DIR'):
            env[name]='PRIVATE-AUDIT-SENTINEL/not-read.json'
            check(item(audit(),'no_environment_override') is False,'environment values neither read as files nor leaked');del env[name]
        for target in (project/'opencode.json.qbrain-stage',project/'opencode.jsonc.qbrain-stage',owner.with_name('owner.json.qbrain-stage'),owner.with_name('pending.json.qbrain-stage')):
            target.write_bytes(b'PRIVATE-AUDIT-SENTINEL incomplete')
            check(item(audit(),'no_staging_conflict') is False,'stage refused and retained');target.unlink()
        pending=owner.with_name('pending.json');pending.write_text('{bad PRIVATE-AUDIT-SENTINEL')
        check(item(audit(),'no_pending_recovery') is False,'journal never replayed by audit');pending.unlink()
        before=snapshot()
        for args in ([],['--project'],['--project',str(project),'--project',str(project)],['--project',str(project),'--allow-write'],
          ['--project',str(project),'--expect-format','v3'],['--project',str(project),'--expect-access','true'],
          ['--project',str(project),'--approve-sha256','0'*64],['--project',str(project),'--brain','secret']):
            r=call(['audit',*args],2)
            check(r=={'error':{'code':'opencode_audit_invalid_request'}} and snapshot()==before,'invalid arguments fail without mutation or echo')
        control=audit(code=0);result('restored healthy control',control,'LOCAL_REGISTRATION_CHECKS_PASSED')
        mutations=[]
        for name in ('extra-field','bad-schema','raw-error','false-host','write-claim','bool-counter','check-missing','check-order','typed-check','false-ready','version-type','positive-with-failure'):
            bad=json.loads(json.dumps(control))
            if name=='extra-field':bad['path']='private'
            if name=='bad-schema':bad['schema']='wrong'
            if name=='raw-error':bad['limitations'].append('private error')
            if name=='false-host':bad['host_consumption_verified']=True
            if name=='write-claim':bad['read_only']=False
            if name=='bool-counter':bad['model_calls']=True
            if name=='check-missing':bad['checks'].pop()
            if name=='check-order':bad['checks'].reverse()
            if name=='typed-check':bad['checks'][0]['passed']=1
            if name=='false-ready':bad['registered_bytes_verified']=False
            if name=='version-type':bad['registered_format']=True
            if name=='positive-with-failure':bad['checks'][8]['passed']=False
            try:validate(bad)
            except ValueError:mutations.append(name)
            else:raise ValueError('bad audit accepted '+name)
        check(len(mutations)==12 and validate(control),'twelve actual report mutations rejected with restored control')
        plan=call(['uninstall-preview','--project',str(project)]);call(['uninstall','--project',str(project),'--approve-sha256',plan['plan_sha256']])
        result('uninstalled audit',audit(),'NOT_REGISTERED')
        check(config.read_bytes()==original,'original JSONC remains exact after entire sequence')
    except Exception as exc:failure=type(exc).__name__+': '+str(exc)
    report={'schema':'qbrain-n48b-process-v1','binary_sha256':sha(binary.read_bytes()),'script_sha256':sha(Path(__file__).read_bytes()),
      'checks':checks,'records':records,'passed':sum(x['passed'] for x in checks),'failed':sum(not x['passed'] for x in checks)+int(failure is not None and all(x['passed'] for x in checks)),
      'failure':failure,'commands':len(records),'platform':os.name,'opencode_started':False,'model_calls':0}
    (output/'report.json').write_bytes(encoded(report))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=run(a.binary.resolve(strict=True),a.output)
    print(json.dumps({k:v for k,v in r.items() if k not in ('checks','records')}))
    raise SystemExit(1 if r['failed'] else 0)
