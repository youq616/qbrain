"""Separate public-CLI lifecycle review. Synthetic files, no host or model use.
The reference parser accepts only this fixture's exact known comment token, not
arbitrary JSONC. Production parsing code is never imported.
"""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, tempfile
from pathlib import Path
COMMENT='/* N48E reviewed comment: keep 中文 */'

def sha(raw):return hashlib.sha256(raw).hexdigest()
def parse(raw):return json.loads(raw.decode('utf-8-sig').replace(COMMENT,''))
def run(binary:Path,output:Path):
 output.mkdir(parents=True,exist_ok=False);checks=[];records=[];failure=None;completed=0
 def check(ok,name):
  checks.append({'name':name,'passed':bool(ok)})
  if not ok:raise ValueError(name)
 try:
  with tempfile.TemporaryDirectory(prefix='n48e-sequences-') as t:
   root=Path(t);home=root/'home';other=root/'other-home';home.mkdir();other.mkdir()
   (home/'KEEP.txt').write_text('SYNTHETIC_PRIVATE_SENTINEL')
   env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENCODE','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
   def for_home(p):return {**env,**{k:str(p) for k in ('HOME','USERPROFILE','LOCALAPPDATA','APPDATA')}}
   def snap():
    return sorted((str(p.relative_to(root)), 'directory' if p.is_dir() else sha(p.read_bytes())) for p in root.rglob('*'))
   def call(args,code=0,h=home):
    p=subprocess.run([str(binary),'opencode',*args],cwd=root,env=for_home(h),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
    records.append({'args':args,'home_label':h.name,'exit':p.returncode,'stdout':p.stdout.decode(),'stderr':p.stderr.decode()})
    if p.returncode!=code or p.stderr:raise ValueError('unexpected CLI outcome: '+str(records[-1]))
    return json.loads(p.stdout)
   for major in (1,2):
    for style in range(3):
     case=f'v{major}-style{style}';project=root/case;project.mkdir();neighbor=root/(case+'-other');neighbor.mkdir()
     peer={'type':'local','command':['NEVER_EXECUTED_FIXTURE'],'enabled':False} if major==1 else {'type':'local','command':['NEVER_EXECUTED_FIXTURE'],'disabled':True}
     ref={'note':'keep \\" and Unicode 中文 😀','mcp':{'external_peer':peer} if major==1 else {'servers':{'external_peer':peer}}}
     raw=(json.dumps(ref,ensure_ascii=False,indent=2)+'\n').encode()
     if style:raw=raw.replace(b'{',('{\n'+COMMENT+'\n').encode(),1)
     if style==2:raw=b'\xef\xbb\xbf'+raw.replace(b'\n',b'\r\n')
     config=project/('opencode.json' if style==0 else 'opencode.jsonc');config.write_bytes(raw)
     target=['--project',str(project)];access=style!=1
     opts=target+['--binary',str(binary),'--brain','sequence-fixture','--format',f'v{major}']+(['--allow-write'] if access else [])
     before=snap();plan=call(['preview',*opts]);check(snap()==before,case+' preview does not write')
     other_opts=['--project',str(neighbor),*opts[2:]]
     bad=call(['install',*other_opts,'--approve-sha256',plan['plan_sha256']],1)
     check(bad=={'error':{'code':'opencode_plan_conflict'}} and snap()==before,case+' approval cannot cross projects')
     bad=call(['install',*opts,'--approve-sha256',plan['plan_sha256']],1,other)
     check(bad=={'error':{'code':'opencode_plan_conflict'}} and snap()==before,case+' approval cannot cross data homes')
     changed=opts[:-1] if access else opts+['--allow-write']
     bad=call(['install',*changed,'--approve-sha256',plan['plan_sha256']],1)
     check(bad=={'error':{'code':'opencode_plan_conflict'}} and snap()==before,case+' approval cannot change access')
     applied=call(['install',*opts,'--approve-sha256',plan['plan_sha256']]);name=plan['server_name']
     def definitions(expected_access):
      doc=parse(config.read_bytes());servers=doc['mcp'] if major==1 else doc['mcp']['servers']
      expected={'type':'local','command':[str(binary),'serve','--brain','sequence-fixture','--tool-profile','memory']+(['--allow-write'] if expected_access else []),'cwd':str(project),'environment':{'QBRAIN_MCP_ALLOW_WRITE':'0'},'timeout':10000 if major==1 else {'startup':10000,'catalog':10000},'enabled' if major==1 else 'disabled':major==1}
      check(servers[name]==expected,case+' exact independent owned definition')
      del servers[name];check(doc==ref,case+' all unrelated semantic data retained')
     check(applied['applied'] is True and applied['write_enabled'] is access,case+' explicit approved install')
     definitions(access)
     # Two independent external edits; neither changes the owned definition.
     def external(key,value):
      data=config.read_bytes();addition=json.dumps(key)+':'+json.dumps(value,ensure_ascii=False)+','
      config.write_bytes(data.replace(b'{',b'{'+addition.encode(),1));ref[key]=value
     external('external_note','adopt and preserve 中文');before=snap()
     bad=call(['uninstall-preview',*target],1)
     check(bad=={'error':{'code':'opencode_external_edit'}} and snap()==before,case+' ordinary uninstall refuses external edit')
     reconciliation=call(['reconcile-preview',*target]);check(snap()==before,case+' reconciliation preview does not write')
     pristine=config.read_bytes();config.write_bytes(pristine.replace(b'"--tool-profile"',b'"--unapproved-option"',1));before_bad=snap()
     bad=call(['reconcile-preview',*target],1)
     check(bad=={'error':{'code':'opencode_managed_entry_changed'}} and snap()==before_bad,case+' changed owned definition cannot be adopted')
     config.write_bytes(pristine);external('later_editor',style);before=snap()
     bad=call(['reconcile',*target,'--approve-sha256',reconciliation['plan_sha256']],1)
     check(bad=={'error':{'code':'opencode_plan_conflict'}} and snap()==before,case+' second editor invalidates earlier approval')
     reconciliation=call(['reconcile-preview',*target]);call(['reconcile',*target,'--approve-sha256',reconciliation['plan_sha256']]);definitions(access)
     before=snap();again=call(['reconcile-preview',*target]);call(['reconcile',*target,'--approve-sha256',again['plan_sha256']])
     check(again['would_change'] is False and snap()==before,case+' repeated reconciliation is an exact no-op')
     # Omission on later installation means read-only, not inherited permission.
     readonly=[x for x in opts if x!='--allow-write'];p=call(['preview',*readonly]);call(['install',*readonly,'--approve-sha256',p['plan_sha256']]);definitions(False)
     before=snap();a=call(['audit',*target,'--expect-format',f'v{major}','--expect-access','read-only'])
     check(a['result']=='LOCAL_REGISTRATION_CHECKS_PASSED' and a['registered_write_enabled'] is False and snap()==before,case+' read-only audit after deliberate permission reset')
     state_root=home/'.local/share/Qbrain/integrations/opencode';owner=next(state_root.rglob('owner.json'))
     # Select by exact project, never by incidental traversal order.
     owners=[p for p in state_root.rglob('owner.json') if json.loads(p.read_bytes())['project']==str(project)]
     check(len(owners)==1,case+' exactly one owner for project');owner=owners[0]
     before_image=bytes.fromhex(json.loads(owner.read_bytes())['before'])
     check(parse(before_image)==ref,case+' new uninstall baseline agrees with independent expected document')
     p=call(['uninstall-preview',*target]);call(['uninstall',*target,'--approve-sha256',p['plan_sha256']])
     check(config.read_bytes()==before_image and parse(config.read_bytes())==ref and not owner.exists(),case+' uninstall preserves adopted baseline bytes and removes only ownership')
     if style:check(COMMENT.encode() in config.read_bytes(),case+' unrelated comment survives')
     if style==2:check(config.read_bytes().startswith(b'\xef\xbb\xbf') and b'\r\n' in config.read_bytes(),case+' BOM and original CRLF survive')
     before=snap();s=call(['status',*target]);check(s['installed'] is False and snap()==before,case+' uninstalled status is read-only')
     completed+=1
   check((home/'KEEP.txt').read_text()=='SYNTHETIC_PRIVATE_SENTINEL', 'pre-existing home sentinel unchanged')
 except Exception as e:failure=type(e).__name__+': '+str(e)
 value={'schema':'qbrain-n48e-lifecycle-sequence-review-v1','binary_sha256':sha(binary.read_bytes()),'script_sha256':sha(Path(__file__).read_bytes()),'scenarios':completed,'checks':checks,'commands':len(records),'records':records,'passed':sum(x['passed'] for x in checks),'failure':failure,'platform':os.name,'new_host_execution':False,'model_calls':0,'user_data_used':False}
 (output/'review.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 return value
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=run(a.binary.resolve(strict=True),a.output)
 print(json.dumps({k:v for k,v in r.items() if k not in ('records','checks')},ensure_ascii=False));raise SystemExit(bool(r['failure']))
