"""N48K review regression: PRE-UPGRADE receipts survive upgrade/rollback/uninstall.

Synthetic, disposable brains only. Uses the exact already-qualified ZIP, not a
rebuilt or edited product. Every request/response and preservation snapshot stays
in the new evidence directory. Windows CI runs each native PowerShell separately.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

OLD_SHA = 'c517582c1ea0e0795e881155edd4d34288e3a002dc3bc7657dafcb96a1eb8b4d'
NEW_SHA = '58d56b7bd7c9a662514e41d20bacb88c68c92bbe3fc380496a09331bf1f5cafa'

def encode(v): return (json.dumps(v, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
def sha(raw): return hashlib.sha256(raw).hexdigest()
def need(ok, label):
    if not ok: raise ValueError(label)

def exercise(old, new, old_installer, installer, shell, output):
    output.mkdir(parents=True, exist_ok=False)
    (output/'raw').mkdir()
    checks, calls = [], []
    failure = None
    result = dict(schema='qbrain-n48k-existing-receipts-v1', native_windows=os.name == 'nt',
        shell=shell, old_binary_sha256=sha(old.read_bytes()), binary_sha256=sha(new.read_bytes()),
        script_sha256=sha(Path(__file__).read_bytes()), old_zip_sha256=OLD_SHA if shell else None, package_sha256=NEW_SHA if shell else None,
        installer_executed=shell is not None, real_client_verified=False, new_product_build=False)
    def check(ok,label):
        checks.append(dict(name=label,passed=bool(ok))); need(ok,label)
    try:
        with tempfile.TemporaryDirectory(prefix='n48k-old-receipts-') as temporary:
            root=Path(temporary)/"preserve space \u4e2d \U0001f600 '"; root.mkdir()
            home=root/'home'; home.mkdir()
            env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
            env.update(HOME=str(home),USERPROFILE=str(home),LOCALAPPDATA=str(home),APPDATA=str(home),PYTHONDONTWRITEBYTECODE='1')
            def run(name,args,body=None,cwd=root):
                raw=b'' if body is None else encode(body)
                child=env.copy()
                if shell=='powershell': child={k:v for k,v in child.items() if k.upper()!='PSMODULEPATH'}
                p=subprocess.run(list(map(str,args)),input=raw,capture_output=True,cwd=cwd,env=child,timeout=90)
                index=len(calls); hashes={}
                for suffix,data in [('stdin',raw),('stdout',p.stdout),('stderr',p.stderr)]:
                    (output/'raw'/f'{index:03d}.{suffix}').write_bytes(data); hashes[suffix]=sha(data)
                calls.append(dict(name=name,argv=list(map(str,args)),exit=p.returncode,hashes=hashes))
                need(p.returncode==0,'command failed: '+name)
                return p.stdout
            def cli(binary,args,body=None):
                raw = run('cli-'+args[0]+'-'+(args[1] if len(args)>1 else ''),[binary,*args],body)
                return None if args[0]=='init' else json.loads(raw.decode('utf-8-sig'))
            if shell:
                major=json.loads(run('shell-version',[shell,'-NoProfile','-NonInteractive','-Command','$PSVersionTable.PSVersion.Major | ConvertTo-Json']).decode('utf-8-sig'))
                check(type(major) is int and major=={'powershell':5,'pwsh':7}[shell],'native shell version')
                result['shell_major']=major
            cli(old,['init','--brain','default-to-preserve'])
            data=home if os.name=='nt' else home/'.local/share'
            global_config=data/'Qbrain/config.json'; original_default=global_config.read_bytes()
            for host in ['Claude','Codex']:
                project=root/(host+' project'); project.mkdir()
                settings=project/('.claude/settings.local.json' if host=='Claude' else '.codex/hooks.json')
                settings.parent.mkdir();settings.write_bytes(encode(dict(user_setting='preserve-user',hooks={})))
                mcp=project/('.mcp.json' if host=='Claude' else '.codex/config.toml')
                mcp.write_text('{"user_setting":"preserve-mcp","mcpServers":{}}' if host=='Claude' else "# preserve-mcp\nmodel = 'fixture'\n",encoding='utf-8')
                brain='preexisting-'+host.lower()
                def install(path,binary,action='Install'):
                    if not shell:return
                    args=[shell,'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',path,
                          '-Action',action,'-HostName',host,'-ProjectPath',project]
                    if action=='Install':args+=['-BrainId',brain,'-Binary',binary]
                    run(host+'-'+action,args,cwd=project)
                install(old_installer,old)
                cli(old,['init','--brain',brain,'--no-default'])
                def bcli(binary,args,body=None):return cli(binary,[*args,'--brain',brain],body)
                event=bcli(old,['memory','capture','--manual'],dict(session_id='before-upgrade',fragment_id='old-fact',messages=[dict(role='user',content='I prefer preserved receipt evidence.')]))
                bcli(old,['memory','extract','--event',event['event_id']])
                items=bcli(old,['memory','read'])['items']; item=next(i for i in items if i['event_id']==event['event_id'])
                fact=bcli(old,['fact','create'],dict(predicate='preexisting.preference',item_id=item['item_id']))
                fid,revision=fact['fact_id'],fact['revision']
                active,withdrawn='1'*64,'2'*64
                for uid in (active,withdrawn):bcli(old,['fact','report-use'],dict(fact_id=fid,usage_id=uid,expected_revision=revision))
                bcli(old,['fact','revoke-use'],dict(fact_id=fid,usage_id=withdrawn))
                def snapshot(binary,stage):
                    value={'fact':bcli(binary,['fact','read','--id',fid]),'summary':bcli(binary,['fact','usage','--id',fid])}
                    for state in ['all','current','withdrawn']:
                        value[state]=bcli(binary,['fact','usage-list','--id',fid,'--state',state,'--limit','50'])
                    (output/(host+'-'+stage+'.json')).write_bytes(encode(value));return value
                before=snapshot(old,'before')
                check([i['usage_id'] for i in before['all']['items']]==[active,withdrawn],host+' old EXE creates both receipts')
                check([i['usage_id'] for i in before['current']['items']]==[active],host+' old current receipt exists')
                check([i['usage_id'] for i in before['withdrawn']['items']]==[withdrawn],host+' old tombstone exists')
                for phase,inst,binary,action in [('upgrade',installer,new,'Install'),('rollback',old_installer,old,'Install'),
                                               ('reupgrade',installer,new,'Install'),('uninstall',installer,new,'Uninstall')]:
                    install(inst,binary,action)
                    after=snapshot(binary,phase)
                    for key in before:check(encode(before[key])==encode(after[key]),host+' '+phase+' preserves '+key)
                    check(global_config.read_bytes()==original_default,host+' '+phase+' preserves default brain')
                    check(json.loads(settings.read_text(encoding='utf-8-sig'))['user_setting']=='preserve-user' and 'preserve-mcp' in mcp.read_text(encoding='utf-8-sig'),host+' '+phase+' preserves user config')
                    if shell:
                        raw=run(host+'-'+phase+'-status',[shell,'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',inst,'-Action','Status','-HostName',host,'-ProjectPath',project])
                        status=json.loads(raw.decode('utf-8-sig'))
                        check(status['installed'] is (action!='Uninstall'),host+' '+phase+' installation state')
                        if action!='Uninstall':check(status['configuration_matches'] is True,host+' '+phase+' configuration matches')
                # Verify duplicate use of the original receipt remains idempotent.
                bcli(new,['fact','report-use'],dict(fact_id=fid,usage_id=active,expected_revision=revision))
                after=snapshot(new,'after-duplicate')
                check(encode(before)==encode(after),host+' duplicate old receipt creates no new usage')
    except Exception as exc:
        failure=type(exc).__name__+': '+str(exc)
    result.update(result='PASS' if failure is None else 'FAIL',checks=checks,calls=calls,failure=failure)
    (output/'RESULT.json').write_bytes(encode(result))
    need(failure is None,failure or 'failed')
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('old-package','package','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--shell',choices=['powershell','pwsh'],required=True)
    a=parser.parse_args();need(os.name=='nt','native Windows required')
    oldraw=a.old_package.read_bytes();newraw=a.package.read_bytes()
    need(sha(oldraw)==OLD_SHA and sha(newraw)==NEW_SHA,'pinned packages required')
    with tempfile.TemporaryDirectory(prefix='n48k-preservation-packages-') as tmp:
        oldroot,newroot=Path(tmp)/'old',Path(tmp)/'new'
        # Only the externally pinned immutable original archives are extracted.
        with zipfile.ZipFile(a.old_package) as z:z.extractall(oldroot)
        with zipfile.ZipFile(a.package) as z:z.extractall(newroot)
        r=exercise(oldroot/'qbrain.exe',newroot/'qbrain.exe',oldroot/'scripts/Install-QbrainMemory.ps1',newroot/'scripts/Install-QbrainMemory.ps1',a.shell,a.output.resolve())
        print(encode({k:v for k,v in r.items() if k not in ('calls','checks')}).decode(),end='')
if __name__=='__main__':main()
