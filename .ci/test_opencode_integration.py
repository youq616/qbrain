"""Actual native Qbrain process/config lifecycle and generated stdio commands.
No OpenCode application or model is launched; this is configuration/protocol scope.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def sha(data):return hashlib.sha256(data).hexdigest()
def run(binary:Path,out:Path):
    out.mkdir(parents=True,exist_ok=False);checks=[];calls=[];failure=None
    def check(ok,label):
        checks.append({'name':label,'passed':bool(ok)})
        if not ok:raise AssertionError(label)
    try:
      with tempfile.TemporaryDirectory(prefix='opencode-module-') as temp:
        root=Path(temp)/'中文 space';root.mkdir()
        exe=root/('qbrain.exe' if os.name=='nt' else 'qbrain');shutil.copy2(binary,exe)
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENCODE','OPENAI','ANTHROPIC'))}
        env.update(HOME=str(root),USERPROFILE=str(root),LOCALAPPDATA=str(root),APPDATA=str(root))
        app=(root if os.name=='nt' else root/'.local/share')/'Qbrain'
        def process(args,expected=0,extra=None,raw=b'',parsed=True):
            p=subprocess.run([str(exe),*args],input=raw,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,
                env={**env,**(extra or {})},timeout=30)
            calls.append({'argv':args,'stdin':raw.decode(),'exit':p.returncode,'stdout':p.stdout.decode(),'stderr':p.stderr.decode()})
            if expected is not None and p.returncode!=expected:raise AssertionError(str((args,p.returncode,p.stdout[:500],p.stderr[:200])))
            return json.loads(p.stdout) if parsed else p
        def op(action,project,*options,expected=0,extra=None):
            return process(['opencode',action,'--project',str(project),*options],expected,extra)
        def args(fmt='v1',brain='opencode-fixture',write=False):
            return ['--format',fmt,'--binary',str(exe),'--brain',brain,*(['--allow-write'] if write else [])]
        def snapshot():
            return {str(p.relative_to(root)):sha(p.read_bytes()) for p in root.rglob('*') if p.is_file() and not p.is_symlink()}
        def install(project,fmt='v1',brain='opencode-fixture',write=False):
            options=args(fmt,brain,write);pre=op('preview',project,*options)
            return op('install',project,*options,'--approve-sha256',pre['plan_sha256'])
        def undo(project):
            pre=op('uninstall-preview',project)
            return op('uninstall',project,'--approve-sha256',pre['plan_sha256'])
        def definition(project,fmt):
            content=(project/'opencode.jsonc').read_text(encoding='utf-8-sig')
            name=op('status',project)['server_name']
            # Generated definitions are strict JSON, despite surrounding JSONC.
            start=content.index(json.dumps(name))+len(json.dumps(name));start=content.index(':',start)+1
            obj,_=json.JSONDecoder().raw_decode(content[start:].lstrip());return obj
        for fmt in ('v1','v2'):
            project=root/f'project-{fmt}';project.mkdir()
            before=snapshot();status=op('status',project)
            check(status['installed'] is False and snapshot()==before,fmt+' status is read-only before setup')
            options=args(fmt);pre=op('preview',project,*options)
            check(snapshot()==before and pre['write_enabled'] is False,fmt+' preview does not create config or state')
            rejected=op('install',project,*options,'--approve-sha256','0'*64,expected=1)
            check(rejected['error']['code']=='opencode_plan_conflict' and snapshot()==before,fmt+' wrong approval is nonmutating')
            done=op('install',project,*options,'--approve-sha256',pre['plan_sha256'])
            check(done['applied'] is True and op('status',project)['configuration_matches'] is True,fmt+' install and status')
            content=json.loads((project/'opencode.jsonc').read_text(encoding='utf-8'))
            entry=definition(project,fmt)
            calls.append({'kind':'generated-config','format':fmt,'configuration':(project/'opencode.jsonc').read_text(encoding='utf-8'),'definition':entry})
            servers=content['mcp'] if fmt=='v1' else content['mcp']['servers']
            check(len(servers)==1 and entry['type']=='local' and entry['command']==[str(exe),'serve','--brain','opencode-fixture','--tool-profile','memory'],fmt+' documented schema and argv')
            check(entry.get('enabled') is True if fmt=='v1' else entry.get('disabled') is False,fmt+' version-specific enable field')
            check(entry['environment']=={'QBRAIN_MCP_ALLOW_WRITE':'0'},fmt+' environment refuses ambient write permission')
            check(type(entry['timeout']) is int and entry['timeout']==10000 if fmt=='v1' else entry['timeout']=={'startup':10000,'catalog':10000},fmt+' independently verified versioned timeout shape')
            check(('disabled' not in entry) if fmt=='v1' else ('enabled' not in entry),fmt+' opposite version enablement absent')
            check(op('status',project)['effective_configuration_verified'] is False,fmt+' local registration does not certify host merged settings')
            before=snapshot();st=op('status',project,extra={'OPENCODE_CONFIG':'override-value-not-stored'})
            check(st['config_override_present'] is True and snapshot()==before,fmt+' status warns override without writing')
            (project/'opencode.json').write_text('{}');st=op('status',project)
            check(st['project_layer_conflict'] is True and st['configuration_matches'] is True,fmt+' status distinguishes own-file identity from layer conflict')
            (project/'opencode.json').unlink()
            same=snapshot();again=install(project,fmt)
            check(again['would_change'] is False and snapshot()==same,fmt+' identical install is a byte-preserving no-op')
            install(project,fmt,write=True);allowed=definition(project,fmt)
            check(allowed['command'][-1]=='--allow-write' and op('status',project)['write_enabled'] is True,fmt+' write requires explicit flag')
            install(project,fmt,write=False);check(op('status',project)['write_enabled'] is False,fmt+' reinstall without flag revokes opt-in')
            undo(project);check(not (project/'opencode.jsonc').exists() and op('status',project)['installed'] is False,fmt+' uninstall removes only newly-created config')
        # JSONC round-trip is exact, not deserialize/reformat.
        project=root/'existing';project.mkdir()
        original=b'\xef\xbb\xbf// keep comment\r\n{ "model":"preserve", "number":1234567890123456789, }\r\n'
        cfg=project/'opencode.jsonc';cfg.write_bytes(original)
        install(project);changed=cfg.read_bytes()
        check(changed.startswith(original[:original.index(b'}')]) and changed.endswith(original[original.index(b'}'):]),'JSONC/BOM/CRLF original bytes retained outside insertion')
        cfg.write_bytes(changed+b'// user edit\n');before=snapshot()
        check(op('status',project)['configuration_matches'] is False,'external edit is visible in status')
        check(op('uninstall-preview',project,expected=1)['error']['code']=='opencode_external_edit' and snapshot()==before,'external edit blocks overwrite')
        cfg.write_bytes(changed);undo(project);check(cfg.read_bytes()==original,'undo restores original exact byte image')
        pre=op('preview',project,*args());cfg.write_bytes(original+b'// later\n');before=snapshot()
        check(op('install',project,*args(),'--approve-sha256',pre['plan_sha256'],expected=1)['error']['code']=='opencode_plan_conflict' and snapshot()==before,'config change invalidates plan')
        cfg.write_bytes(original);pre=op('preview',project,*args())
        check(op('install',project,*args('v2'),'--approve-sha256',pre['plan_sha256'],expected=1)['error']['code']=='opencode_plan_conflict','format change invalidates plan')
        check(op('install',project,*args(write=True),'--approve-sha256',pre['plan_sha256'],expected=1)['error']['code']=='opencode_plan_conflict','permission change invalidates plan')
        check(op('install',project,*args(brain='different'),'--approve-sha256',pre['plan_sha256'],expected=1)['error']['code']=='opencode_plan_conflict','brain change invalidates plan')
        for raw in (b'',b' ',b'[]',b'{,}',b'{"a":1,"a":2}',b'{"mcp":{},"\\u006dcp":{}}',b'/* unterminated',b'//\xff\n{}',b'{}\x00suffix',b' '*65537):
            cfg.write_bytes(raw);before=snapshot()
            check('error' in op('preview',project,*args(),expected=1) and snapshot()==before,'malformed/bounded config rejected '+sha(raw)[:8])
        cfg.write_text('{}')
        for key in ('OPENCODE_CONFIG','OPENCODE_CONFIG_CONTENT','OPENCODE_CONFIG_DIR'):
            check(op('preview',project,*args(),extra={key:'explicit-override'},expected=1)['error']['code']=='opencode_override_present','custom config override refused '+key)
        (project/'opencode.json').write_text('{}')
        check(op('preview',project,*args(),expected=1)['error']['code']=='opencode_multiple_configs','two root config files refused')
        (project/'opencode.json').unlink();(project/'.opencode').mkdir();(project/'.opencode/opencode.jsonc').write_text('{}')
        check(op('preview',project,*args(),expected=1)['error']['code']=='opencode_layer_conflict','higher project config refused')
        (project/'.opencode/opencode.jsonc').unlink()
        for extra in (['--unknown','x'],['--brain','duplicate'],['--format','v3']):
            check('error' in op('preview',project,*args(),*extra,expected=1),'strict command options '+str(extra))
        check('error' in op('install',project,*args(),expected=1),'install always requires approval')
        check('error' in op('status',project,'--allow-write',expected=1),'status does not accept write option')
        check(op('recovery-preview',project,expected=1)['error']['code']=='opencode_no_recovery','recovery cannot fabricate a journal')
        # Same approved plan competes across independent processes. At most one
        # action changes config; a post-completion replan may safely be a no-op.
        race=root/'race';race.mkdir();pre=op('preview',race,*args())
        def contender(_):
            return subprocess.run([str(exe),'opencode','install','--project',str(race),*args(),'--approve-sha256',pre['plan_sha256']],
                cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
        with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(contender,range(4)))
        for p in rows:calls.append({'kind':'concurrent','exit':p.returncode,'stdout':p.stdout.decode(),'stderr':p.stderr.decode()})
        check(sum(p.returncode==0 for p in rows)==1 and op('status',race)['configuration_matches'] is True,'competing approved installs have one successful mutation')
        check(len(json.loads((race/'opencode.jsonc').read_text(encoding='utf-8'))['mcp'])==1,'competing installs never duplicate server entry');undo(race)
        # Execute generated argv/environment directly: real Qbrain protocol, not
        # OpenCode itself. Deliberately hostile ambient allow-write=1 is overridden.
        linked=root/'linked';linked.mkdir();install(linked)
        process(['init','--brain','opencode-fixture','--no-default'],parsed=False)
        process(['config','set','memory.writeback','salient','--local','--brain','opencode-fixture'],parsed=False)
        payload={'session_id':'synthetic-opencode','fragment_id':'first','messages':[{'role':'user','content':'I prefer explicit test data.'}]}
        messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{}},{'jsonrpc':'2.0','method':'notifications/initialized'},
            {'jsonrpc':'2.0','id':2,'method':'tools/list'},
            {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'memory_write','arguments':{'action':'capture','payload':json.dumps(payload)}}}]
        def protocol():
            entry=definition(linked,'v1');p=subprocess.run(entry['command'],input=b'\n'.join(json.dumps(m).encode() for m in messages)+b'\n',
                cwd=entry['cwd'],env={**env,'QBRAIN_MCP_ALLOW_WRITE':'1',**entry['environment']},stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
            calls.append({'kind':'generated-mcp','argv':entry['command'],'exit':p.returncode,'stdout':p.stdout.decode(),'stderr':p.stderr.decode()})
            if p.returncode:raise AssertionError('generated server failed')
            return [json.loads(row) for row in p.stdout.splitlines()]
        replies=protocol();tools={t['name'] for t in replies[1]['result']['tools']}
        check(tools=={'memory_read','memory_write','context_read','context_write','search','get_page'},'generated MCP exposes the exact six-tool profile')
        denied=json.loads(replies[2]['result']['content'][-1]['text'])
        check(replies[2]['result']['isError'] is True and denied['error']['code']=='write_denied','generated read-only server resists ambient write opt-in')
        install(linked,write=True);replies=protocol()
        check(replies[2]['result']['isError'] is False,'generated explicit write server reaches authorized capture')
        install(linked);replies=protocol();check(replies[2]['result']['isError'] is True,'reinstall to read-only removes previous write capability')
        undo(linked);check((app/'brains/opencode-fixture/brain.db').exists(),'uninstall preserves brain data')
        if os.name!='nt':
            target=root/'other.json';target.write_text('{}');cfg.unlink();cfg.symlink_to(target);before=target.read_bytes()
            check('error' in op('preview',project,*args(),expected=1) and target.read_bytes()==before,'symlink config target refused')
            cfg.unlink();os.link(target,cfg)
            check('error' in op('preview',project,*args(),expected=1) and target.read_bytes()==before,'hardlinked config target refused')
    except Exception as err:failure=type(err).__name__+': '+str(err)
    result={'schema':'qbrain-n48a-process-v1','binary_sha256':sha(binary.read_bytes()),'script_sha256':sha(Path(__file__).read_bytes()),
        'checks':checks,'calls':calls,'passed':sum(x['passed'] for x in checks),'failed':sum(not x['passed'] for x in checks)+int(failure is not None and all(x['passed'] for x in checks)),
        'failure':failure,'platform':os.name,'opencode_application_tested':False,'model_calls':0}
    (out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=run(a.binary.resolve(strict=True),a.output);print(json.dumps({k:v for k,v in r.items() if k not in ('checks','calls')},ensure_ascii=False));raise SystemExit(bool(r['failed']))
