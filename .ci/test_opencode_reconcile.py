"""N48C actual native CLI lifecycle; synthetic configs, no OpenCode/model launch.

Test-only journal images model interruption after known atomic writes. Separate
C++ tests interrupt the real writer dependency and exercise observed edit races.
"""
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
import shutil, subprocess, tempfile


def sha(raw): return hashlib.sha256(raw).hexdigest()
def enc(value): return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()


def run(binary: Path, output: Path):
    output.mkdir(parents=True,exist_ok=False);checks=[];calls=[];failure=None
    def check(ok,name):
        checks.append({'name':name,'passed':bool(ok)})
        if not ok:raise ValueError(name)
    try:
      with tempfile.TemporaryDirectory(prefix='n48c-cli-') as temporary:
        root=Path(temporary)/'project space 中文';root.mkdir()
        exe=root/('qbrain.exe' if os.name=='nt' else 'qbrain');shutil.copy2(binary,exe)
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENCODE','OPENAI','ANTHROPIC'))}
        env.update(HOME=str(root),LOCALAPPDATA=str(root),USERPROFILE=str(root),APPDATA=str(root))
        state_root=(root if os.name=='nt' else root/'.local/share')/'Qbrain'
        def snapshot():
            return sorted((str(p.relative_to(root)),sha(p.read_bytes()),p.stat().st_mode) for p in root.rglob('*') if p.is_file() and not p.is_symlink())
        def call(action,project,*args,code=0,extra=None):
            argv=['opencode',action,'--project',str(project),*args]
            r=subprocess.run([str(exe),*argv],stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,env={**env,**(extra or {})},timeout=30)
            calls.append({'args':argv,'exit':r.returncode,'stdout':r.stdout.decode(),'stderr':r.stderr.decode()})
            if r.returncode!=code or r.stderr:raise ValueError(str((argv,r.returncode,r.stdout[:400],r.stderr[:200])))
            value=json.loads(r.stdout)
            if len(r.stdout)>4096:raise ValueError('unbounded result')
            return value
        for major in (1,2):
          for allow in (False,True):
            project=root/f'v{major}-{allow}';project.mkdir();config=project/'opencode.jsonc'
            opts=['--binary',str(exe),'--brain','not-opened','--format','v'+str(major),*(['--allow-write'] if allow else [])]
            config.write_bytes(b'{"user":"before"}\n')
            plan=call('preview',project,*opts);call('install',project,*opts,'--approve-sha256',plan['plan_sha256'])
            status=call('status',project);name=status['server_name']
            owner_path=state_root/'integrations/opencode'/name[7:]/'owner.json';pending=owner_path.with_name('pending.json')
            prior=owner_path.read_bytes();old=json.loads(prior)
            definition=json.loads(config.read_bytes())['mcp'];definition=definition if major==1 else definition['servers'];definition=definition[name]
            original_config=config.read_bytes();before=snapshot();plan=call('reconcile-preview',project)
            check(plan['would_change'] is False and snapshot()==before,'exact ownership has nonmutating no-op preview')
            call('reconcile',project,'--approve-sha256',plan['plan_sha256']);check(snapshot()==before,'no-op reconciliation preserves all bytes and modes')
            head=b'\xef\xbb\xbf// user comment \xe4\xb8\xad\xe6\x96\x87\r\n{"user":"changed","mcp":'+(b'' if major==1 else b'{"servers":')
            middle=b'{"other":{"type":"remote","url":"https://never-called.invalid"},/*keep*/'
            tail=b'/*preserve trailing comment*/}'+(b'' if major==1 else b'}')+b',"provider":{"private":"DO-NOT-OUTPUT"},}\r\n'
            # Independently construct exact unowned bytes, not a production removal helper.
            managed=enc(name)+b':'+enc(definition)+b','
            edited=head+middle+managed+tail;baseline=head+middle+tail;config.write_bytes(edited)
            before=snapshot()
            check(call('preview',project,*opts,code=1)['error']['code']=='opencode_external_edit','ordinary install still refuses external edits')
            check(call('uninstall-preview',project,code=1)['error']['code']=='opencode_external_edit','ordinary uninstall still refuses external edits')
            plan=call('reconcile-preview',project)
            check(plan['would_change'] and plan['operation']=='reconcile' and plan['format']==major and plan['write_enabled'] is allow and snapshot()==before,'edited preview binds original format and access without writes')
            check('DO-NOT-OUTPUT' not in json.dumps(plan) and plan['model_calls']==0 and plan['host_consumption_verified'] is False,'preview does not reveal unrelated config content or claim host use')
            check(call('reconcile',project,'--approve-sha256','0'*64,code=1)['error']['code']=='opencode_plan_conflict' and snapshot()==before,'wrong approval leaves configuration and owner unchanged')
            config.write_bytes(edited+b'// later\n');later=snapshot()
            check(call('reconcile',project,'--approve-sha256',plan['plan_sha256'],code=1)['error']['code']=='opencode_plan_conflict' and snapshot()==later,'later external edit invalidates approved plan')
            config.write_bytes(edited)
            for field,value in [('command',['not-qbrain']),('environment',{'QBRAIN_MCP_ALLOW_WRITE':'1'}),('cwd','other'),('timeout',None),('disabled' if major==2 else 'enabled',allow)]:
                modified=dict(definition);modified[field]=value
                if modified==definition:modified[field]=None
                config.write_bytes(head+middle+enc(name)+b':'+enc(modified)+b','+tail);state=snapshot()
                check(call('reconcile-preview',project,code=1)['error']['code']=='opencode_managed_entry_changed' and snapshot()==state,'modified managed '+field+' is not adopted')
            config.write_bytes(edited);state=snapshot()
            for option in ('--allow-write','--format','--binary'):
                args=[option] if option=='--allow-write' else [option,'v2']
                check(call('reconcile-preview',project,*args,code=1)['error']['code']=='opencode_argument' and snapshot()==state,'reconcile rejects unrelated or privilege-changing option '+option)
            check(call('reconcile-preview',project,extra={'OPENCODE_CONFIG_CONTENT':'{}'},code=1)['error']['code']=='opencode_override_present' and snapshot()==state,'environment override refuses reconciliation')
            stage=config.with_name(config.name+'.qbrain-stage');stage.write_bytes(b'unknown');with_stage=snapshot()
            check(call('reconcile-preview',project,code=1)['error']['code']=='opencode_stage_conflict' and snapshot()==with_stage,'unknown stage is retained and refused');stage.unlink()
            data=exe.read_bytes();exe.write_bytes(data+b'identity change');changed=snapshot()
            check(call('reconcile-preview',project,code=1)['error']['code']=='opencode_binary_changed' and snapshot()==changed,'changed executable cannot be silently adopted');exe.write_bytes(data)
            plan=call('reconcile-preview',project);done=call('reconcile',project,'--approve-sha256',plan['plan_sha256'])
            check(done['applied'] is True and call('status',project)['configuration_matches'] is True,'explicit reconciliation completes coherently')
            after_config=config.read_bytes();after_owner=owner_path.read_bytes();new=json.loads(after_owner)
            check(bytes.fromhex(new['before'])==baseline,'owner stores exact current unowned bytes as undo baseline')
            check(new['format']==major and new['allow_write'] is allow and new['binary_sha256']==old['binary_sha256'],'reconciliation never changes version permission or executable identity')
            check(call('audit',project)['registered_bytes_verified'] is True,'existing local registration audit passes after reconciliation')
            journal={'schema':'qbrain-opencode-reconcile-journal-v2','project':old['project'].lower() if os.name=='nt' else old['project'],
              'config_name':'opencode.jsonc','changes':[{'slot':'config','before':edited.hex(),'after':after_config.hex()},
                {'slot':'state','before':prior.hex(),'after':after_owner.hex()}]}
            for progress in (0,1,2):
                config.write_bytes(after_config if progress>=1 else edited);owner_path.write_bytes(after_owner if progress==2 else prior);pending.write_bytes(enc(journal))
                initial=snapshot();rp=call('recovery-preview',project)
                check(snapshot()==initial,'recovery preview is read-only at durable boundary '+str(progress))
                call('recover',project,'--approve-sha256',rp['plan_sha256'])
                check(config.read_bytes()==edited and owner_path.read_bytes()==prior and not pending.exists(),'recovery restores exact external before image at boundary '+str(progress))
            plan=call('reconcile-preview',project);call('reconcile',project,'--approve-sha256',plan['plan_sha256'])
            state=snapshot();plan=call('reconcile-preview',project);call('reconcile',project,'--approve-sha256',plan['plan_sha256'])
            check(plan['would_change'] is False and snapshot()==state,'completed reconcile is stable on repeated no-op')
            newopts=['--binary',str(exe),'--brain','not-opened','--format','v'+str(major),*(['--allow-write'] if not allow else [])]
            plan=call('preview',project,*newopts);call('install',project,*newopts,'--approve-sha256',plan['plan_sha256'])
            check(call('status',project)['write_enabled'] is (not allow),'ordinary explicit permission update retains supported lifecycle')
            plan=call('uninstall-preview',project);call('uninstall',project,'--approve-sha256',plan['plan_sha256'])
            check(config.read_bytes()==baseline and not owner_path.exists(),'uninstall preserves all independently expected unowned bytes')
            state=snapshot();call('reconcile-preview',project,code=1);check(snapshot()==state,'missing ownership cannot be adopted')
        check(not (state_root/'brains').exists(),'configuration lifecycle never opens or creates a brain')
    except Exception as e:failure=type(e).__name__+': '+str(e)
    result={'schema':'qbrain-n48c-cli-v1','binary_sha256':sha(binary.read_bytes()),'test_sha256':sha(Path(__file__).read_bytes()),
        'passed':sum(x['passed'] for x in checks),'failed':sum(not x['passed'] for x in checks)+int(failure is not None and all(x['passed'] for x in checks)),
        'checks':checks,'calls':calls,'failure':failure,'platform':os.name,'host_started':False,'model_calls':0}
    (output/'report.json').write_bytes(enc(result)+b'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=run(a.binary.resolve(strict=True),a.output);print(json.dumps({k:v for k,v in r.items() if k not in ('checks','calls')}));raise SystemExit(bool(r['failed']))
