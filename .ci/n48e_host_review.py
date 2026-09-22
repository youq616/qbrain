"""Fixed, credential-free OpenCode compatibility check; not a model evaluation.

--fetch downloads only pinned public/tool artifacts. --run supplies an explicit
minimal environment to disposable projects; no model prompts, auth or tools/call.
"""
from __future__ import annotations
import argparse, hashlib, io, json, os, re, subprocess, tarfile, tempfile, zipfile
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler, urlopen

SOURCE='e419acf60375e1a7a0794375c713f759b776aa0b'
VERSION='1.18.31'
PINS={
 'posix':dict(artifact=10644942504,size=18781884,archive='346c5f3560fce9c2762c367cde1b702010dd3953b3a5bee1ef23c8866a3ef18d',
   qbrain='c5844eef61407912f4b2113dbd18a94a5a00a2f4d206a9e437061f5e44aeb7da',host_name='opencode-linux-x64.tar.gz',
   host_size=60590585,host_archive='e9312be75ed803b7415fc2aeabda1f4fe938912a39673762dc0c38c0e11ebde4'),
 'nt':dict(artifact=10645630760,size=17820156,archive='9a0f9ee5965ff245b46b2041a5c36d2836fbc2dbc72a310993ff33d5b605accd',
   qbrain='4a90b7c50df446ba354691758a53fc8164fbe10fbf7d0fbb9e26f679b43232bf',host_name='opencode-windows-x64.zip',
   host_size=60718498,host_archive='0ecd7ffc7f26390ce7799e7bcd409e4f11c410144308a6a5b0fcdce63d871006')}

def need(ok,why):
 if not ok:raise ValueError(why)
def sha(b):return hashlib.sha256(b).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def fetch(url,expected_size,digest,token=None):
 # Authorization is used only for api.github.com and never forwarded to signed storage.
 if token:
  need(urlparse(url).hostname=='api.github.com','token_destination')
  class StopRedirect(HTTPRedirectHandler):
   def redirect_request(self,*args,**kwargs):return None
  request=Request(url,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
  try:response=build_opener(StopRedirect()).open(request,timeout=90)
  except HTTPError as e:
   need(e.code in (301,302,303,307,308),'artifact_api_failure')
   location=e.headers.get('Location','');need(urlparse(location).scheme=='https','redirect_scheme')
   response=urlopen(location,timeout=90)
 else:response=urlopen(url,timeout=90)
 with response:raw=response.read(expected_size+1)
 need(len(raw)==expected_size and sha(raw)==digest,'download_identity');return raw

def extract_host(raw,name):
 wanted='opencode.exe' if os.name=='nt' else 'opencode'
 members=[]
 if name.endswith('.zip'):
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   for m in z.infolist():
    p=PurePosixPath(m.filename);need(not p.is_absolute() and '..' not in p.parts and '\\' not in m.filename,'archive_path')
    if not m.is_dir() and p.name==wanted:
     need(m.file_size<=512*1024*1024 and (m.external_attr>>16)&0o170000 in (0,0o100000),'host_member_type')
     members.append(z.read(m))
 else:
  with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as z:
   for m in z:
    p=PurePosixPath(m.name);need(not p.is_absolute() and '..' not in p.parts,'archive_path')
    if p.name==wanted:
     need(m.isfile() and m.size<=512*1024*1024,'host_member_type');members.append(z.extractfile(m).read())
 need(len(members)==1,'host_member_count');return members[0]

def prepare(out):
 pin=PINS[os.name];out.mkdir(parents=True,exist_ok=False)
 raw=fetch(f'https://api.github.com/repos/youq616/qbrain/actions/artifacts/{pin["artifact"]}/zip',pin['size'],pin['archive'],os.environ.get('GH_TOKEN'))
 suffix='.exe' if os.name=='nt' else ''
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  need(len([x for x in z.namelist() if x=='qbrain'+suffix])==1,'qbrain_member_count')
  need(z.read('source.txt').decode('utf-8-sig').strip()==SOURCE,'candidate_source');q=z.read('qbrain'+suffix)
 need(sha(q)==pin['qbrain'],'qbrain_hash')
 host_archive=fetch(f'https://github.com/anomalyco/opencode/releases/download/v{VERSION}/'+pin['host_name'],pin['host_size'],pin['host_archive'])
 h=extract_host(host_archive,pin['host_name'])
 for name,data in [('qbrain'+suffix,q),('opencode'+suffix,h)]:
  (out/name).write_bytes(data);(out/name).chmod(0o755)
 save(out/'pins.json',dict(source=SOURCE,platform=os.name,upstream_version=VERSION,**pin,host_binary_sha256=sha(h)))

def clean_text(text):return re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',text)
def connected(text,name):
 plain=clean_text(text)
 return bool(re.search(re.escape(name)+r'\s+connected\b',plain)) and '1 server(s)' in plain

def run(inputs,out):
 pin=json.loads((inputs/'pins.json').read_bytes());need(pin['source']==SOURCE and pin['platform']==os.name,'input_pin')
 suffix='.exe' if os.name=='nt' else '';q=(inputs/('qbrain'+suffix)).resolve();host=(inputs/('opencode'+suffix)).resolve()
 need(sha(q.read_bytes())==PINS[os.name]['qbrain'] and sha(host.read_bytes())==pin['host_binary_sha256'],'input_bytes')
 out.mkdir(parents=True,exist_ok=False);checks=[];records=[];failure=None
 def check(ok,name):
  checks.append(dict(name=name,passed=bool(ok)))
  if not ok:raise ValueError(name)
 try:
  with tempfile.TemporaryDirectory(prefix='n48e-real-host-') as tmp:
   root=Path(tmp);home=root/'isolated-home';home.mkdir()
   env={k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR','COMSPEC','PATH','PATHEXT')}
   for k in ('HOME','USERPROFILE','LOCALAPPDATA','APPDATA'):env[k]=str(home)
   for k,folder in [('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data'),('XDG_CACHE_HOME','cache'),('XDG_STATE_HOME','state'),('TEMP','tmp'),('TMP','tmp'),('TMPDIR','tmp')]:
    (home/folder).mkdir(exist_ok=True);env[k]=str(home/folder)
   env.update(CI='true',NO_COLOR='1',TERM='dumb',OPENCODE_PURE='true',OPENCODE_DISABLE_DEFAULT_PLUGINS='true',
      OPENCODE_DISABLE_EXTERNAL_SKILLS='true',OPENCODE_DISABLE_CLAUDE_CODE='true',OPENCODE_DISABLE_LSP_DOWNLOAD='true',
      OPENCODE_DISABLE_AUTOUPDATE='true',OPENCODE_DISABLE_MODELS_FETCH='true')
   def call(exe,args,cwd,parsed=False,expected=0):
    try:p=subprocess.run([str(exe),*args],cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45)
    except subprocess.TimeoutExpired as e:
     records.append(dict(program=exe.name,args=args,timeout=True,stdout=(e.stdout or b'').decode('utf-8','replace'),stderr=(e.stderr or b'').decode('utf-8','replace')))
     raise ValueError('host_command_timeout')
    text=p.stdout.decode('utf-8-sig');err=p.stderr.decode('utf-8-sig')
    records.append(dict(program=exe.name,args=args,exit=p.returncode,stdout=text,stderr=err))
    need(p.returncode==expected,'command_exit_'+exe.stem)
    return json.loads(text) if parsed else text+'\n'+err
   ver=call(host,['--version'],root);check(ver.strip()==VERSION,'actual host version equals pinned release')
   for fmt in ('v1','v2'):
    project=root/('project-'+fmt);project.mkdir();cfg=project/'opencode.jsonc'
    original=b'{\n // synthetic empty project\n}\n';cfg.write_bytes(original)
    def plan_install(write):
     args=['--project',str(project),'--format',fmt,'--binary',str(q),'--brain','host-'+fmt]
     if write:args+=['--allow-write']
     before=cfg.read_bytes();p=call(q,['opencode','preview',*args],project,True)
     check(cfg.read_bytes()==before,fmt+' preview preserves config')
     call(q,['opencode','install',*args,'--approve-sha256',p['plan_sha256']],project,True)
    def inspect(write,label):
     before=cfg.read_bytes();status=call(q,['opencode','status','--project',str(project)],project,True)
     check(status['installed'] is True and status['configuration_matches'] is True and status['write_enabled'] is write,label+' managed state')
     name=status['server_name'];resolved=call(host,['debug','config'],project,True)
     entries=resolved.get('mcp',{});check(set(entries)=={name},label+' host resolves exact single server')
     server=entries[name];argv=[str(q),'serve','--brain','host-'+fmt,'--tool-profile','memory']+(['--allow-write'] if write else [])
     check(server['command']==argv and server.get('cwd')==str(project) and server.get('environment',{}).get('QBRAIN_MCP_ALLOW_WRITE')=='0' and server.get('enabled') is True,label+' host preserves command cwd and explicit access')
     if fmt=='v1':check(type(server.get('timeout')) is int and server['timeout']==10000,label+' V1 resolved timeout')
     else:check('timeout' not in server,label+' V2-on-V1 timeout omission is explicitly recorded, not accepted as equivalent')
     text=call(host,['mcp','list'],project);check(connected(text,name),label+' actual host reports connected')
     after=cfg.read_bytes()
     if after!=before:
      # Official1.18.31 adds a missing $schema during load. Do not mask this
      # external edit, or pretend the registration remains byte-current.
      records.append(dict(kind='host-config-change',format=fmt,before=before.decode(),after=after.decode()))
      expected=re.sub(rb'^\s*\{',b'{\n  "$schema": "https://opencode.ai/config.json",',before,count=1)
      check(b'"$schema"' not in before and after==expected,label+' actual host adds only the documented schema annotation')
      drift=call(q,['opencode','status','--project',str(project)],project,True)
      check(drift['configuration_matches'] is False,label+' external host edit is not silently trusted')
      rejected=call(q,['opencode','uninstall-preview','--project',str(project)],project,True,expected=1)
      check(rejected=={'error':{'code':'opencode_external_edit'}} and cfg.read_bytes()==after,label+' normal uninstall refuses to overwrite host edit')
      repair=call(q,['opencode','reconcile-preview','--project',str(project)],project,True)
      call(q,['opencode','reconcile','--project',str(project),'--approve-sha256',repair['plan_sha256']],project,True)
      stable=cfg.read_bytes()
      check(b'"$schema": "https://opencode.ai/config.json"' in stable,label+' explicit reconciliation preserves host annotation')
      call(host,['debug','config'],project,True)
      check(connected(call(host,['mcp','list'],project),name),label+' actual connection survives reconciliation')
      check(cfg.read_bytes()==stable,label+' subsequent host reads preserve reconciled JSONC')
     else:check(after==before,label+' host leaves managed JSONC unchanged')
    for write,label in [(False,'initial read-only'),(True,'explicit write'),(False,'omitted flag restores read-only')]:
     plan_install(write);inspect(write,fmt+' '+label)
    edited=b'// synthetic external edit retained\n'+cfg.read_bytes();cfg.write_bytes(edited)
    p=call(q,['opencode','reconcile-preview','--project',str(project)],project,True)
    call(q,['opencode','reconcile','--project',str(project),'--approve-sha256',p['plan_sha256']],project,True)
    check(cfg.read_bytes().startswith(b'// synthetic external edit retained'),fmt+' reconciliation retains external comment')
    inspect(False,fmt+' reconciled read-only')
    p=call(q,['opencode','uninstall-preview','--project',str(project)],project,True)
    call(q,['opencode','uninstall','--project',str(project),'--approve-sha256',p['plan_sha256']],project,True)
    final=cfg.read_bytes();check(final.startswith(b'// synthetic external edit retained'),fmt+' uninstall preserves adopted edit')
    resolved=call(host,['debug','config'],project,True);check(not resolved.get('mcp'),fmt+' host resolves no managed server after uninstall')
    text=call(host,['mcp','list'],project);check('No MCP servers configured' in clean_text(text),fmt+' host confirms empty MCP list after uninstall')
    check(cfg.read_bytes()==final,fmt+' final host read does not rewrite config')
 except Exception as e:failure=type(e).__name__+': '+str(e)
 result=dict(schema='qbrain-n48e-pinned-host-review-v1',source=SOURCE,platform=os.name,host_version=VERSION,
   qbrain_sha256=sha(q.read_bytes()),host_sha256=sha(host.read_bytes()),script_sha256=sha(Path(__file__).read_bytes()),
   checks=checks,records=records,passed=sum(x['passed'] for x in checks),failure=failure,
   result='PASS' if failure is None else 'FAIL',formats=['v1','v2'],engine='OpenCode V1; V2 input compatibility only',
   native_v2_engine='NOT_RUN',v2_on_v1_timeout_preserved=False,model_prompts_sent=0,tools_call_requested=0,real_user_data_supplied=False,model_consumption_verified=False)
 save(out/'report.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ('checks','records')}))
 return result

def offline_tests():
 need(connected('x connected\n1 server(s)','x'),'connected_positive')
 for s in ('x disconnected\n1 server(s)','x not connected\n1 server(s)','other connected\n1 server(s)','x connected\n2 server(s)'):
  need(not connected(s,'x'),'connected_negative')
 print('OFFLINE_HOST_CHECKER_TESTS_PASSED 5')

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--fetch',type=Path);p.add_argument('--inputs',type=Path);p.add_argument('--output',type=Path);p.add_argument('--offline-tests',action='store_true');a=p.parse_args()
 if a.offline_tests:offline_tests()
 elif a.fetch:prepare(a.fetch)
 else:
  need(a.inputs is not None and a.output is not None,'arguments')
  r=run(a.inputs,a.output);raise SystemExit(0 if r['result']=='PASS' else 1)
