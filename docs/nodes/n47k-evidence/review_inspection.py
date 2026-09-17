"""Independent fixture expectations for the fixed N47K local-only reader."""
import argparse,copy,hashlib,json,os,stat,subprocess,tempfile
from pathlib import Path
EVENTS=('SessionStart','UserPromptSubmit','Stop','PreCompact','SessionEnd')
SENTINEL='SYNTHETIC-PRIVATE-FIELD-NOT-TO-BE-EMITTED'
def encode(value):return json.dumps(value,separators=(',',':')).encode()
def run(binary):
 checks=[];commands=[]
 def check(ok,name):
  checks.append({'name':name,'status':'PASS' if ok else 'FAIL'})
  if not ok:raise AssertionError(name)
 with tempfile.TemporaryDirectory(prefix='n47k-outcome-reader-') as temp:
  root=Path(temp)
  env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
  env.update(HOME=temp,USERPROFILE=temp,LOCALAPPDATA=temp,APPDATA=temp,TEMP=temp,TMP=temp)
  def snapshot():
   result={}
   for p in root.rglob('*'):
    info=p.lstat();result[str(p.relative_to(root))]=(info.st_mode,info.st_size,info.st_mtime_ns,
        hashlib.sha256(p.read_bytes()).hexdigest() if stat.S_ISREG(info.st_mode) else None)
   return result
  for host in ('claude','codex'):
   folder=root/host;folder.mkdir();config=folder/'config.json'
   cfg={'version':1,'host':host,'enabled':False,'brain_id':SENTINEL,'project_root':str(root/'not-followed')}
   config.write_bytes(encode(cfg))
   def record(event):return {'format_version':2,'host':host,'event':event,'session_key':'c'*64,
     'completed_at_unix_ms':1700000000000,'status':'processed','phase':'complete',
     'provider_calls':0,'host_consumption_confirmed':False,'recall_count':16,'output_bytes':8192,
     'context_truncated':True,'fact_recall_enabled':True,'fact_promotion_enabled':True,
     'fact_promotion_status':'completed','fact_promotion_counts':{'created':32,'attached':0,'duplicate':0,'skipped_retired':0,'skipped_limit':0,'total':32}}
   def path(event='SessionStart'):return folder/f'trace-{host}-{event}.json'
   def invoke(label,extra=(),expected_exit=0):
    before=snapshot()
    result=subprocess.run([str(binary),'hook','diagnostics','--config',str(config),*extra],input=b'',env=env,cwd=root,capture_output=True,timeout=10)
    commands.append({'name':host+':'+label,'exit_code':result.returncode,'expected_exit':expected_exit})
    check(result.returncode==expected_exit and not result.stderr,host+':'+label+':exit-and-stderr')
    check(snapshot()==before,host+':'+label+':no-content-mtime-topology-change')
    check(SENTINEL.encode() not in result.stdout and temp.encode() not in result.stdout and len(result.stdout)<=32769,host+':'+label+':bounded-private-output')
    return json.loads(result.stdout)
   for e in EVENTS:path(e).write_bytes(encode(record(e)))
   r=invoke('all-canonical');check(r['counts']['present']==5 and r['config_enabled'] is False and
       r['record_authenticity_verified'] is False and r['host_consumption_confirmed'] is False and
       all(s['record']==record(s['event']) for s in r['slots']),host+':complete-canonical-equality')
   (folder/'last-trace.json').write_bytes(encode(record('SessionStart')))
   Path(str(path())+'.tmp').write_bytes(encode(record('SessionStart')))
   tests=[]
   for key,value in [('output_bytes',8193),('recall_count',17),('provider_calls',0.0),('host_consumption_confirmed',1),('phase','capture'),('private',SENTINEL)]:
    v=record('SessionStart');v[key]=value;tests.append((key,encode(v),'invalid'))
   v=record('SessionStart');v['fact_promotion_counts']['private']=SENTINEL;tests.append(('nested-field',encode(v),'invalid'))
   v=record('SessionStart');v['fact_promotion_counts']['total']=31;tests.append(('wrong-total',encode(v),'invalid'))
   canonical=encode(record('SessionStart'));tests.extend([
      ('duplicate-decoded-key',b'{"\\u0073tatus":"processed",'+canonical[1:],'invalid'),
      ('valid-prefix-extra',canonical+b'null','invalid'),
      ('raw-nul-suffix',canonical+b'\x00','invalid'),
      ('exact-record-cap',canonical+b' '*(4096-len(canonical)),'present'),
      ('over-record-cap',canonical+b' '*(4097-len(canonical)),'oversized')])
   for label,raw,expected in tests:
    path().write_bytes(raw);r=invoke(label,('--event','SessionStart'))
    check(r['counts'][expected]==1 and r['slots'][0]['state']==expected and
          ('record' in r['slots'][0])==(expected=='present'),host+':'+label+':independent-state')
   path().unlink();r=invoke('missing-no-fallback',('--event','SessionStart'))
   check(r['counts']['missing']==1,host+':no-last-or-temporary-fallback')
   path().symlink_to(folder/'last-trace.json');r=invoke('static-final-link',('--event','SessionStart'))
   check(r['counts']['unsafe_path']==1 and 'record' not in r['slots'][0],host+':link-not-read');path().unlink()
   os.mkfifo(path());r=invoke('nonregular-no-block',('--event','SessionStart'))
   check(r['counts']['unsafe_path']==1,host+':fifo-not-opened');path().unlink()
   path().write_bytes(canonical);r=invoke('session-mismatch',('--event','SessionStart','--session-key','d'*64))
   check(r['counts']['session_mismatch']==1 and 'record' not in r['slots'][0],host+':wrong-session-content-absent')
   config.write_bytes(encode(cfg)+b' '*(65536-len(encode(cfg))));r=invoke('exact-config-cap')
   check(r['counts']['present']==5,host+':exact-config-cap-accepted')
   config.write_bytes(config.read_bytes()+b' ');r=invoke('over-config-cap',expected_exit=2)
   check(r=={'result':'ERROR','error':{'code':'diagnostic_config_unavailable'}},host+':over-config-fixed-error')
 return {'result':'PASS','scope':'Independent synthetic CLI reader checks on Linux, not native Windows or live host acceptance',
   'source_commit_declared':'a23800df3709ac9ef73a51d150b64d2d20d7d21f','source_identity_method':'Externally pinned archive and exact tree, not runtime Git HEAD',
   'checks':checks,'check_count':len(checks),'commands':commands,'command_count':len(commands),
   'atime_changes_measured':False,'product_sources_modified':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 if a.report.exists():p.error('Use a new report')
 r=run(a.binary.resolve(strict=True));a.report.write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({k:r[k] for k in ('result','check_count','command_count')}))
if __name__=='__main__':main()
