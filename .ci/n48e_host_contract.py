"""Real official V1 host acceptance, with explicitly limited V2 compatibility.

The preceding HOST-BOUNDARY-REVIEW preserves the failed broader expectation.
Reuse the exact fetched candidate and immutable upstream provenance; no network
or source modification is performed by this execution-only fixture.
"""
from pathlib import Path
import argparse, json, os, re, signal, socket, subprocess, tempfile
from n48e_host_check import need, sha, encoded, UPSTREAM_TAG


def run(inputs,output):
    output.mkdir(parents=True,exist_ok=False)
    records=[];checks=[];failure=None;completed=[];network={}
    provenance=json.loads((inputs/'PROVENANCE.json').read_bytes())
    qb=(inputs/'qbrain').resolve(strict=True);host=(inputs/'opencode').resolve(strict=True)
    def check(ok,name):
        checks.append({'name':name,'passed':bool(ok)})
        if not ok:raise ValueError(name)
    try:
        network={'interfaces':socket.if_nameindex(),'namespace':os.readlink('/proc/self/ns/net'),
                 'initial_namespace':os.readlink('/proc/1/ns/net')}
        check({name for _,name in network['interfaces']}=={'lo'} and network['namespace']!=network['initial_namespace'],'separate loopback-only network')
        check(sha(qb.read_bytes())==provenance['qbrain_sha256'] and sha(host.read_bytes())==provenance['opencode_sha256'],'exact approved binary identities')
        with tempfile.TemporaryDirectory(prefix='n48e-actual-host-') as tmp:
            root=Path(tmp);home=root/'home';home.mkdir()
            env={'PATH':'/usr/local/bin:/usr/bin:/bin','LANG':'C.UTF-8','HOME':str(home),'USERPROFILE':str(home),
                 'LOCALAPPDATA':str(home),'APPDATA':str(home),'XDG_CONFIG_HOME':str(home/'config'),
                 'XDG_DATA_HOME':str(home/'data'),'XDG_CACHE_HOME':str(home/'cache'),'XDG_STATE_HOME':str(home/'state'),
                 'OPENCODE_DISABLE_AUTOUPDATE':'1','OPENCODE_DISABLE_MODELS_FETCH':'1','OPENCODE_PURE':'1',
                 'OPENCODE_EXPERIMENTAL_DISABLE_FILEWATCHER':'1','NO_COLOR':'1','CI':'true'}
            def call(exe,args,cwd,code=0):
                p=subprocess.Popen([str(exe),*args],cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
                timeout=False
                try:stdout,stderr=p.communicate(timeout=45)
                except subprocess.TimeoutExpired:
                    timeout=True;os.killpg(p.pid,signal.SIGKILL);stdout,stderr=p.communicate()
                records.append({'exe':'opencode' if exe==host else 'qbrain','args':args,'cwd':str(cwd),'exit':p.returncode,
                                'stdout':stdout.decode(errors='replace'),'stderr':stderr.decode(errors='replace'),'timed_out':timeout})
                (output/'records.json').write_bytes(encoded(records))
                need(not timeout and p.returncode==code,'actual command result')
                return stdout.decode(),stderr.decode()
            check(call(host,['--version'],root)[0].strip()==UPSTREAM_TAG[1:],'actual upstream version')
            for fmt in ('v1','v2'):
                for write in (False,True):
                    label=fmt+('-write' if write else '-read');project=root/label;project.mkdir()
                    opts=['--project',str(project),'--binary',str(qb),'--brain','host-fixture','--format',fmt]+(['--allow-write'] if write else [])
                    def q(args):return json.loads(call(qb,['opencode',*args],root)[0])
                    plan=q(['preview',*opts]);q(['install',*opts,'--approve-sha256',plan['plan_sha256']])
                    name=plan['server_name'];cfg=project/'opencode.jsonc';before=cfg.read_bytes()
                    resolved=json.loads(call(host,['debug','config'],project)[0]);entry=resolved['mcp'][name]
                    expected=[str(qb),'serve','--brain','host-fixture','--tool-profile','memory']+(['--allow-write'] if write else [])
                    check(entry['command']==expected and entry.get('enabled') is True and entry['cwd']==str(project),label+' exact command and enablement loaded')
                    check(entry['environment']=={'QBRAIN_MCP_ALLOW_WRITE':'0'},label+' explicit environment preserved')
                    if fmt=='v1':check(entry.get('timeout')==10000,label+' native V1 timeout preserved')
                    else:check('timeout' not in entry,label+' V1 compatibility loses V2 timeout; not native V2 acceptance')
                    if cfg.read_bytes()!=before:
                        prior=json.loads(before);now=json.loads(cfg.read_bytes());now.pop('$schema',None)
                        check(now==prior,label+' actual host adds only schema')
                        check(q(['status','--project',str(project)])['configuration_matches'] is False,label+' host rewrite is reported as drift')
                        approval=q(['reconcile-preview','--project',str(project)])
                        q(['reconcile','--project',str(project),'--approve-sha256',approval['plan_sha256']])
                    text,err=call(host,['mcp','list'],project)
                    text=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',text+'\n'+err)
                    check(re.search(re.escape(name)+r'\s+connected\b',text) is not None,label+' official host connects generated server')
                    check(q(['status','--project',str(project)])['configuration_matches'] is True,label+' connection leaves registered bytes coherent')
                    un=q(['uninstall-preview','--project',str(project)])
                    q(['uninstall','--project',str(project),'--approve-sha256',un['plan_sha256']])
                    check(not cfg.exists() or name not in cfg.read_text(),label+' managed entry removed explicitly')
                    completed.append(label)
            check(completed==['v1-read','v1-write','v2-read','v2-write'],'four completed connection scenarios')
    except Exception as e:failure=type(e).__name__+': '+str(e)
    report={'schema':'qbrain-n48e-real-host-contract-v1','result':'V1_HOST_VERIFIED' if failure is None else 'FAIL',
            'failure':failure,'completed':completed,'checks':checks,'records':records,'provenance':provenance,
            'network_observation':network,'host_engine':'OpenCode V1 '+UPSTREAM_TAG,'v2_engine_tested':False,
            'v2_timeout_preserved':False,'v2_scope':'Compatibility loading only; startup/catalog timeout is dropped by V1',
            'model_prompts_sent':0,'tools_call_requested':0,'real_user_brain_supplied':False,'host_consumption_verified':False}
    (output/'report.json').write_bytes(encoded(report))
    print(json.dumps({k:v for k,v in report.items() if k not in ('checks','records','provenance')}))
    if failure:raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.inputs,a.output)
