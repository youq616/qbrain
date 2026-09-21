"""Independent Linux edge checks of the downloaded N48D executable.

Compile edge_peer.cpp separately with the verified repository's JSON headers.
No production code alteration, no provider request, no real user home.
"""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path

def digest(data):return hashlib.sha256(data).hexdigest()

def run(binary: Path,peer: Path,output: Path):
 if os.name!='posix':raise ValueError('This supplemental review is Linux-only.')
 output.mkdir(parents=True,exist_ok=False)
 checks=[];records=[];failed=None
 def check(ok,name):
  checks.append({'name':name,'passed':bool(ok)})
  if not ok:raise ValueError(name)
 try:
  with tempfile.TemporaryDirectory(prefix='n48d-final-edges-') as temp:
   root=Path(temp);home=root/'home';work=root/'work';bins=root/'bins'
   for p in (home,work,bins):p.mkdir()
   (home/'PRIVATE.txt').write_text('SYNTHETIC_HOME_SENTINEL')
   (work/'outside').mkdir();(work/'outside/KEEP.txt').write_text('EXTERNAL_TEST_SENTINEL')
   expected={'outside'}
   env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
   env.update(HOME=str(home),USERPROFILE=str(home),LOCALAPPDATA=str(home),APPDATA=str(home),TMPDIR=str(work),TEMP=str(work),TMP=str(work),
      OPENAI_API_KEY='SYNTHETIC_PROVIDER_SENTINEL',N48D_REVIEW_SENTINEL='SYNTHETIC_ENV_SENTINEL',QBRAIN_BRAIN='not-the-probe')
   def command(args,exitcode,pass_fds=()):
    p=subprocess.run([str(binary),'mcp-check',*args],cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=8,pass_fds=pass_fds)
    records.append({'args':args,'exit':p.returncode,'stdout':p.stdout.decode(),'stderr':p.stderr.decode()})
    check(p.returncode==exitcode and not p.stderr,'exact command outcome')
    return json.loads(p.stdout)
   cases=[('good',None),('early-eof','unexpected_eof'),('partial-tail','incomplete_frame'),('duplicate-escaped','invalid_protocol_json'),
      ('depth-limit','invalid_protocol_json'),('array','invalid_protocol_envelope'),('unsupported-notice','unsolicited_message'),
      ('server-request','unsolicited_message'),('stderr-limit',None),('stderr-over','stderr_limit'),('fd-close',None),('linked-child',None),
      ('messages16',None),('messages17','message_limit'),('total-limit',None),('total-over','stdout_limit'),('frame-limit',None),
      ('frame-over','frame_limit'),('missing-version','protocol_version_mismatch'),('float-id','response_id_mismatch'),('null-id','response_id_mismatch'),
      ('negative-id','response_id_mismatch'),('null-result','server_response_error'),('late-empty','trailing_output'),('late-nonzero','nonzero_exit')]
   for mode,error in cases:
    target=bins/('edge-'+mode);shutil.copy2(peer,target);target.chmod(0o755)
    plan=command(['preview','--binary',str(target),'--timeout-ms','1000'],0)
    fd=None
    try:
     if mode=='fd-close':
      fd=os.open(home/'PRIVATE.txt',os.O_RDONLY);os.dup2(fd,77)
     result=command(['run','--binary',str(target),'--timeout-ms','1000','--approve-sha256',plan['approval_sha256']],1 if error else 0,(77,) if mode=='fd-close' else ())
    finally:
     if fd is not None:os.close(77);os.close(fd)
    check(result['code']==(error or 'verified') and result['result']==('FAILED' if error else 'ISOLATED_MCP_VERIFIED'),'edge '+mode+' exact classification')
    check(result['process_cleanup_verified'] and result['workspace_cleanup_verified'] and {p.name for p in work.iterdir()}==expected,'edge '+mode+' owned cleanup')
    check(result['tools_called']==0 and result['model_requests_sent']==0 and result['host_consumption_verified'] is False,'edge '+mode+' scope')
    if mode=='early-eof':check(result['messages_received']==0,'EOF is not a received frame')
    if mode=='partial-tail':check(result['messages_received']==1,'partial tail adds no received frame')
    if mode=='messages16':check(result['messages_received']==16,'exact message cap succeeds')
    if mode=='messages17':check(result['messages_received']==16,'message cap rejects before consuming another frame')
    if mode=='total-limit':check(result['stdout_bytes']==262144,'exact cumulative stdout cap succeeds')
    if mode=='total-over':check(result['stdout_bytes']==262145,'one byte beyond stdout cap fails')
    if mode=='stderr-limit':check(result['stderr_bytes']==65536,'exact stderr cap is accepted')
    if mode=='stderr-over':check(result['stderr_bytes']==65537,'one byte beyond stderr cap fails')
    check((work/'outside/KEEP.txt').read_text()=='EXTERNAL_TEST_SENTINEL' and (home/'PRIVATE.txt').read_text()=='SYNTHETIC_HOME_SENTINEL','outside test data untouched')
    text=json.dumps(result)
    check(all(k not in text for k in ('SYNTHETIC_PROVIDER_SENTINEL','SYNTHETIC_HOME_SENTINEL','SYNTHETIC_DO_NOT_COPY',str(home),str(bins))),'bounded report excludes fixture body and paths')
   # Same executable, different path is a different approval. Link identities reject.
   one=bins/'edge-one';two=bins/'edge-two';shutil.copy2(peer,one);shutil.copy2(peer,two)
   plan=command(['preview','--binary',str(one)],0)
   result=command(['run','--binary',str(two),'--approve-sha256',plan['approval_sha256']],2)
   check(result=={'error':{'code':'approval_mismatch'}},'approval binds path as well as bytes')
   link=bins/'symbolic';link.symlink_to(one)
   result=command(['preview','--binary',str(link)],2)
   check(result=={'error':{'code':'path_link_refused'}},'symlink executable refuses')
   hard=bins/'hard';os.link(one,hard)
   result=command(['preview','--binary',str(one)],2)
   check(result=={'error':{'code':'binary_links_refused'}},'hardlinked executable refuses')
   check({p.name for p in work.iterdir()}==expected,'preflight errors leave no new workspace')
 except Exception as e:failed=type(e).__name__+': '+str(e)
 value={'schema':'qbrain-n48d-final-edge-review-v1','binary_sha256':digest(binary.read_bytes()),'peer_sha256':digest(peer.read_bytes()),
   'script_sha256':digest(Path(__file__).read_bytes()),'cases':25,'checks':checks,'records':records,'commands':len(records),
   'passed':sum(x['passed'] for x in checks),'failure':failed,'real_client_verified':False,'provider_calls':0,
   'scope':'Linux supplemental execution on exact CI binary; newly compiled independent fixture, not product'}
 (output/'review.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 return value

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('binary','peer','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();v=run(a.binary.resolve(strict=True),a.peer.resolve(strict=True),a.output)
 print(json.dumps({k:x for k,x in v.items() if k not in ('checks','records')}))
 raise SystemExit(1 if v['failure'] or not all(x['passed'] for x in v['checks']) else 0)
