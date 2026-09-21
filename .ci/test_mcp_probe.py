"""N48D real CLI/process evidence. Fake peers are synthetic, not actual agents.

Only temporary user homes/workspaces. No model keys are used: sentinel values
prove the child receives a minimal environment. Each exact command is recorded.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def run(binary: Path, peer: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    checks, records = [], []
    failure = None
    def check(ok: bool, name: str):
        checks.append({'name': name, 'passed': bool(ok)})
        if not ok:
            raise ValueError(name)
    try:
        with tempfile.TemporaryDirectory(prefix='n48d-suite-') as tmp:
            root=Path(tmp); home=root/'existing-home'; home.mkdir()
            temp=root/'workspaces'; temp.mkdir(); bins=root/'programs with spaces'; bins.mkdir()
            env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
            env.update(HOME=str(home),USERPROFILE=str(home),LOCALAPPDATA=str(home),APPDATA=str(home),
                TMPDIR=str(temp),TEMP=str(temp),TMP=str(temp),QBRAIN_MCP_ALLOW_WRITE='true',
                OPENAI_API_KEY='N48D_PRIVATE_PROVIDER_SENTINEL',ANTHROPIC_API_KEY='N48D_PRIVATE_PROVIDER_SENTINEL',
                QBRAIN_API_KEY='N48D_PRIVATE_PROVIDER_SENTINEL',QBRAIN_BRAIN='user-brain',N48D_PRIVATE_SENTINEL='do-not-inherit',
                PYTHONPATH='N48D_PRIVATE_PYTHONPATH')
            (home/'private.txt').write_text('untouched real-user stand-in')
            def snapshot():
                return sorted((str(p.relative_to(home)),sha(p.read_bytes())) for p in home.rglob('*') if p.is_file())
            initial=snapshot()
            def call(args, expected=0):
                begin=time.monotonic()
                p=subprocess.run([str(binary),'mcp-check',*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                    env=env,cwd=root,timeout=12)
                seconds=time.monotonic()-begin
                record={'args':args,'exit':p.returncode,'stdout':p.stdout.decode(),'stderr':p.stderr.decode(),'elapsed_seconds':seconds}
                records.append(record)
                if p.returncode!=expected or p.stderr:
                    raise ValueError('command failed: '+json.dumps(record))
                return json.loads(p.stdout)
            def prepare(exe,timeout=2000):
                return call(['preview','--binary',str(exe),'--timeout-ms',str(timeout)])
            def execute(exe,plan,expected=0,timeout=2000):
                return call(['run','--binary',str(exe),'--timeout-ms',str(timeout),'--approve-sha256',plan['approval_sha256']],expected)
            def copied(mode):
                path=bins/('peer-'+mode+('.exe' if os.name=='nt' else ''))
                shutil.copy2(peer,path);path.chmod(0o755);return path
            plan=prepare(binary,10000)
            check(not list(temp.iterdir()) and snapshot()==initial,'preview creates no workspace and leaves user home unchanged')
            check(plan==prepare(binary,10000),'unchanged preview is deterministic')
            check(plan['arguments']==['serve','--brain','probe','--tool-profile','memory'] and
                plan['environment_policy']=='private-home-minimal-env-write-disabled-v1','plan names fixed read-only command and isolation policy')
            result=execute(binary,plan,timeout=10000)
            check(result['result']=='ISOLATED_MCP_VERIFIED' and all(result[k] is True for k in
                ('process_started','initialize_verified','catalog_verified','ping_verified','clean_shutdown_verified',
                 'process_cleanup_verified','workspace_cleanup_verified')),'real Qbrain completes the actual MCP lifecycle and cleanup')
            check(result['tool_count']==6 and result['messages_received']==3 and result['exit_code']==0,'real Qbrain returns exact profile and three responses')
            check(result['tools_called']==0 and result['model_requests_sent']==0 and result['real_brain_supplied'] is False and
                result['host_consumption_verified'] is False and result['write_authorization_verified'] is False,'report separates transport success from model use or write authorization')
            check(snapshot()==initial and not list(temp.iterdir()),'real run leaves existing home untouched and removes its workspace')
            invalid=[([], 'missing-action'),(['bogus','--binary',str(binary)],'bad-action'),
                (['preview','--binary',str(binary),'--timeout-ms','1000x'],'integer'),
                (['preview','--binary',str(binary),'--timeout-ms','999'],'low-timeout'),
                (['preview','--binary',str(binary),'--timeout-ms','30001'],'high-timeout'),
                (['preview','--binary',str(binary),'--binary',str(binary)],'duplicate'),
                (['preview','--binary',str(binary),'--allow-write'],'extra'),
                (['preview','--binary',str(binary),'--approve-sha256','x'],'approval-on-preview'),
                (['run','--binary',str(binary)],'missing-approval'),
                (['preview','--binary','relative'],'relative'),
                (['preview','--binary',str(root/'missing')],'missing-file')]
            for args,label in invalid:
                value=call(args,2)
                check(set(value)=={'error'} and not list(temp.iterdir()),'invalid '+label+' refuses before workspace creation')
            changed=copied('good');old=prepare(changed)
            with changed.open('ab') as f:f.write(b'changed')
            value=execute(changed,old,2)
            check(value['error']['code']=='approval_mismatch' and not list(temp.iterdir()),'changed executable bytes invalidate old approval before spawn')
            intact=copied('good');old=prepare(intact)
            value=execute(intact,old,2,timeout=3000)
            check(value['error']['code']=='approval_mismatch' and not list(temp.iterdir()),'changed timeout invalidates old approval before spawn')
            bad=bins/('not-a-program.exe' if os.name=='nt' else 'not-a-program');bad.write_text('not executable format');bad.chmod(0o755)
            result=execute(bad,prepare(bad),1)
            check(result['code']=='process_start_error' and result['process_started'] is False,'OS startup failure is distinct from protocol failure')
            check(result['workspace_cleanup_verified'] and not list(temp.iterdir()),'startup failure retains no owned workspace')
            for mode in ('good','partial','logs','env'):
                exe=copied(mode);r=execute(exe,prepare(exe))
                check(r['result']=='ISOLATED_MCP_VERIFIED' and r['clean_shutdown_verified'],'synthetic '+mode+' has observed valid lifecycle')
                check(not list(temp.iterdir()) and snapshot()==initial,'synthetic '+mode+' cleans only its workspace')
                if mode=='logs':check(r['messages_received']==6,'bounded server logging is consumed without exposing its contents')
            faults={
                'wrong-version':'protocol_version_mismatch','wrong-server':'server_identity_mismatch',
                'missing-capability':'tools_capability_missing','wrong-id':'response_id_mismatch',
                'string-id':'response_id_mismatch','bool-id':'response_id_mismatch','server-error':'server_response_error',
                'missing-tool':'catalog_shape','duplicate-tool':'catalog_tool_identity','extra-tool':'catalog_shape',
                'wrong-schema':'catalog_schema','missing-routes':'catalog_required_routes_missing','paginated':'catalog_shape',
                'wrong-ping':'invalid_ping_result','trailing':'trailing_output','trailing-partial':'trailing_output',
                'invalid-utf8':'invalid_protocol_json','duplicate-json':'invalid_protocol_json','text-error':'invalid_protocol_json',
                'partial-eof':'incomplete_frame','empty-frame':'empty_frame','server-request':'unsolicited_message',
                'notification-flood':'message_limit','frame-flood':'frame_limit','stdout-flood':'stdout_limit',
                'stderr-flood':'stderr_limit','nonzero':'nonzero_exit',
                'no-read':'protocol_timeout','stall-init':'protocol_timeout','stall-catalog':'protocol_timeout',
                'stall-ping':'protocol_timeout','shutdown-stall':'protocol_timeout','held-pipe':'protocol_timeout'}
            for mode,code in faults.items():
                exe=copied(mode);r=execute(exe,prepare(exe,1000),1,1000)
                check(r['result']=='FAILED' and r['code']==code,'fault '+mode+' is classified without accepting a partial success')
                check(r['process_cleanup_verified'] and r['workspace_cleanup_verified'] and not list(temp.iterdir()),
                    'fault '+mode+' cleans its owned process/workspace')
                check(r['tools_called']==0 and r['model_requests_sent']==0,'fault '+mode+' never invokes tools or model requests')
            # Repeat after all abnormal paths, and use a Unicode program path.
            exe=bins/('校验😀.exe' if os.name=='nt' else '校验😀');shutil.copy2(binary,exe);exe.chmod(0o755)
            r=execute(exe,prepare(exe,10000),timeout=10000)
            check(r['result']=='ISOLATED_MCP_VERIFIED','real Qbrain still succeeds from a Unicode path after abnormal peers')
            check(snapshot()==initial and not list(temp.iterdir()),'all runs preserve user-home sentinel and leave no workspaces')
            reports=[json.loads(x['stdout']) for x in records if x['args'] and x['args'][0]=='run' and x['exit']!=2]
            for r in reports:
                text=json.dumps(r)
                check(len(text.encode())<=8192 and all(s not in text for s in
                    (str(home),str(bins),'PRIVATE_PROVIDER_SECRET_TEST','N48D_PRIVATE_PROVIDER_SENTINEL','do-not-inherit')),
                    'shareable runtime report has bounded fields and no raw child or local-path sentinel')
    except Exception as e:
        failure=type(e).__name__+': '+str(e)
    value={'schema':'qbrain-n48d-process-v1','binary_sha256':sha(binary.read_bytes()),'peer_sha256':sha(peer.read_bytes()),
        'script_sha256':sha(Path(__file__).read_bytes()),'checks':checks,'records':records,'failure':failure,
        'passed':sum(x['passed'] for x in checks),'failed':sum(not x['passed'] for x in checks)+int(failure is not None and all(x['passed'] for x in checks)),
        'commands':len(records),'platform':os.name,'real_opencode_loaded':False,'provider_calls_requested':0}
    (output/'report.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return value

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('binary','peer','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();r=run(a.binary.resolve(strict=True),a.peer.resolve(strict=True),a.output)
    print(json.dumps({k:v for k,v in r.items() if k not in ('checks','records')},ensure_ascii=False))
    raise SystemExit(bool(r['failed']))
