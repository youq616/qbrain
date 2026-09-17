"""Real local diagnostic command, isolated Hook fixtures; no signed-in client."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from test_hook_fact_process import provenance

EVENTS=('SessionStart','UserPromptSubmit','Stop','PreCompact','SessionEnd')
CASES=('missing_not_success','no_brain_or_lock_created','complete_actual_records','prompt_not_echoed',
 'event_selection','matching_session','other_session_hidden','disabled_is_historical','other_host_ignored',
 'unknown_file_ignored','invalid_record_hidden','remaining_slots_visible','oversized_record','directory_refused',
 'duplicate_record_rejected','missing_no_legacy_fallback','no_database_open','forgotten_replay_visible',
 'forgotten_memory_absent','bad_config_fixed_error','bad_version_fixed_error','bad_event_rejected',
 'bad_session_rejected','duplicate_option_rejected','relative_path_rejected','missing_config_rejected',
 'restored_record_visible','no_mutations_during_inspection','bounded_output','consumption_never_inferred')
EXPECTED_CHECKS=frozenset(h+':'+n for h in ('claude','codex') for n in CASES)
CALLS=('empty','init','writeback','submit','stop','precompact','end','start','all','event','matching','mismatch',
 'disabled','otherhost','unknown','invalid','oversized','directory','duplicate','missing','no-db','lookup',
 'forget','replay','inspect-forgotten','absent','bad-config','bad-version','bad-event','bad-session','dup-option',
 'relative','missing-config','restored')
COMMAND_SCHEDULE=tuple(h+':'+n for h in ('claude','codex') for n in CALLS)
NEGATIVE=frozenset(h+':'+n for h in ('claude','codex') for n in
 ('bad-config','bad-version','bad-event','bad-session','dup-option','relative','missing-config'))
def encode(j):return json.dumps(j,ensure_ascii=False,separators=(',',':')).encode('utf-8')
def sha(b):return hashlib.sha256(b).hexdigest()

def run(binary,checks,commands):
 with tempfile.TemporaryDirectory(prefix='qbrain-diagnostics-') as d:
  root=Path(d)/'诊断 space';root.mkdir();project=root/'project';project.mkdir()
  env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
  env.update(HOME=str(root),USERPROFILE=str(root),LOCALAPPDATA=str(root),APPDATA=str(root),TEMP=str(root),TMP=str(root))
  data=root if os.name=='nt' else root/'.local'/'share'
  def snapshot():return {str(p.relative_to(root)):sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
  for host in ('claude','codex'):
   owned=root/host;owned.mkdir();config=owned/'config.json';brain='diag-'+host
   session='raw-session-DIAG-'+host;quote='I prefer N47K-PRIVATE-'+host+' for the test prefix.'
   cfg=dict(version=1,host=host,enabled=True,project_root=str(project),brain_id=brain,source_id='default',
     capture=True,extraction='local',fact_promotion=True,fact_recall=True,recall_bytes=8192,max_items=8)
   config.write_bytes(encode(cfg));unchanged=[];outputs=[]
   def ck(ok,name):
    checks.append(dict(name=host+':'+name,status='PASS' if ok else 'FAIL'))
    if not ok:raise AssertionError(host+':'+name)
   def invoke(name,args,payload=None,expected=0):
    try:r=subprocess.run([str(binary),*args],input=b'' if payload is None else encode(payload),cwd=project,env=env,capture_output=True,timeout=20)
    except subprocess.TimeoutExpired:
     commands.append(dict(name=host+':'+name,exit_code=None,expected_exit=expected,timed_out=True));raise
    commands.append(dict(name=host+':'+name,exit_code=r.returncode,expected_exit=expected))
    if r.returncode!=expected or r.stderr:raise AssertionError('unexpected process result: '+host+':'+name)
    return r.stdout
   def diag(name,extra=(),expected=0,args=None):
    before=snapshot();raw=invoke(name,['hook','diagnostics',*(args if args is not None else ['--config',str(config),*extra])],expected=expected)
    unchanged.append(before==snapshot());outputs.append(raw);return json.loads(raw)
   def hook(name,event,**fields):
    payload=dict(hook_event_name=event,session_id=session,cwd=str(project));payload.update(fields)
    return invoke(name,['hook','--config',str(config)],payload)
   def path(event='UserPromptSubmit'):return owned/f'trace-{host}-{event}.json'
   report=diag('empty');ck(report['result']=='INSPECTED' and report['counts']['missing']==5,'missing_not_success')
   ck(not (data/'Qbrain'/'brains'/brain).exists() and not (owned/'runtime.lock').exists(),'no_brain_or_lock_created')
   invoke('init',['init','--brain',brain,'--no-default'])
   invoke('writeback',['config','set','memory.writeback','salient','--local','--brain',brain])
   hook('submit','UserPromptSubmit',prompt=quote,turn_id='seed');submit=json.loads(path().read_bytes());submit_bytes=path().read_bytes()
   hook('stop','Stop',last_assistant_message='Confirmed.');hook('precompact','PreCompact');hook('end','SessionEnd')
   hook('start','SessionStart',session_id=session+'-new')
   r=diag('all');ck(r['counts']['present']==5 and tuple(x['event'] for x in r['slots'])==EVENTS and
      all(x['record']==json.loads(path(x['event']).read_bytes()) for x in r['slots']),'complete_actual_records')
   ck(quote.encode() not in encode(r) and session.encode() not in encode(r) and str(root).encode() not in encode(r),'prompt_not_echoed')
   r=diag('event',['--event','UserPromptSubmit']);ck(r['counts']['selected']==1 and r['slots'][0]['record']==submit,'event_selection')
   r=diag('matching',['--session-key',submit['session_key']]);ck(r['counts']['present']==4 and r['counts']['session_mismatch']==1,'matching_session')
   r=diag('mismatch',['--session-key','b'*64]);ck(r['counts']['session_mismatch']==5 and all('record' not in s for s in r['slots']),'other_session_hidden')
   cfg['enabled']=False;config.write_bytes(encode(cfg));r=diag('disabled')
   ck(r['config_enabled'] is False and r['counts']['present']==5,'disabled_is_historical');cfg['enabled']=True;config.write_bytes(encode(cfg))
   other='codex' if host=='claude' else 'claude';(owned/f'trace-{other}-SessionStart.json').write_text('SECRET-OTHER-HOST',encoding='utf-8')
   r=diag('otherhost');ck(r['counts']['selected']==5 and b'SECRET-OTHER-HOST' not in encode(r),'other_host_ignored')
   (owned/'trace-attacker-extra.json').write_text('SECRET-EXTRA',encoding='utf-8');r=diag('unknown')
   ck(r['counts']['selected']==5 and b'SECRET-EXTRA' not in encode(r),'unknown_file_ignored')
   bad=dict(submit,private='SECRET-INVALID');path().write_bytes(encode(bad));r=diag('invalid')
   ck(r['counts']['invalid']==1 and b'SECRET-INVALID' not in encode(r),'invalid_record_hidden')
   ck(r['counts']['present']==4,'remaining_slots_visible')
   path().write_bytes(b'x'*4097);r=diag('oversized');ck(r['counts']['oversized']==1,'oversized_record')
   path().unlink();path().mkdir();r=diag('directory');ck(r['counts']['unsafe_path']==1,'directory_refused');path().rmdir()
   path().write_bytes(b'{"status":"processed",'+submit_bytes[1:]);r=diag('duplicate');ck(r['counts']['invalid']==1,'duplicate_record_rejected')
   path().unlink();r=diag('missing',['--event','UserPromptSubmit']);ck(r['counts']['missing']==1 and 'record' not in r['slots'][0],'missing_no_legacy_fallback')
   path().write_bytes(submit_bytes)
   db=data/'Qbrain'/'brains'/brain/'brain.db';backup=db.with_suffix('.not-open');db.rename(backup)
   r=diag('no-db');ck(r['counts']['present']==5 and not db.exists(),'no_database_open');backup.rename(db)
   item=json.loads(invoke('lookup',['memory','read','--brain',brain,'--source','default','--query',quote]))['items'][0]
   invoke('forget',['memory','forget','--brain',brain,'--source','default','--event',item['event_id']])
   hook('replay','UserPromptSubmit',prompt=quote,turn_id='seed');r=diag('inspect-forgotten',['--event','UserPromptSubmit']);rec=r['slots'][0]['record']
   ck(r['counts']['present']==1 and rec['capture_status']=='forgotten' and rec['status']=='failed' and rec['phase']=='extract','forgotten_replay_visible')
   absent=json.loads(invoke('absent',['memory','read','--brain',brain,'--source','default','--query',quote]));ck(absent['items']==[],'forgotten_memory_absent')
   config.write_text('{"secret":"SECRET-CONFIG","version":1,"version":1}',encoding='utf-8')
   r=diag('bad-config',expected=2);ck(r=={'result':'ERROR','error':{'code':'diagnostic_config_invalid'}},'bad_config_fixed_error')
   cfg['version']=1.0;config.write_bytes(encode(cfg));r=diag('bad-version',expected=2);ck(r['error']['code']=='diagnostic_config_invalid','bad_version_fixed_error');cfg['version']=1;config.write_bytes(encode(cfg))
   r=diag('bad-event',['--event','../secret'],2);ck(r['error']['code']=='invalid_diagnostic_arguments','bad_event_rejected')
   r=diag('bad-session',['--session-key','SECRET-SESSION'],2);ck(r['error']['code']=='invalid_diagnostic_arguments','bad_session_rejected')
   r=diag('dup-option',['--event','Stop','--event','Stop'],2);ck(r['error']['code']=='invalid_diagnostic_arguments','duplicate_option_rejected')
   r=diag('relative',expected=2,args=['--config','../config.json']);ck(r['error']['code']=='invalid_diagnostic_arguments','relative_path_rejected')
   config.unlink();r=diag('missing-config',expected=2);ck(r['error']['code']=='diagnostic_config_unavailable','missing_config_rejected');config.write_bytes(encode(cfg))
   r=diag('restored');ck(r['counts']['present']==5,'restored_record_visible')
   ck(all(unchanged),'no_mutations_during_inspection')
   ck(all(len(o)<=32769 and len(o.splitlines())==1 for o in outputs),'bounded_output')
   ck(all(json.loads(o).get('host_consumption_confirmed',False) is False for o in outputs),'consumption_never_inferred')

def main():
 p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 checks=[];commands=[];s=Path(__file__).resolve();report=dict(result='FAIL',checks=checks,commands=commands,native_windows=os.name=='nt',real_host_consumption_verified=False)
 try:
  binary=a.binary.resolve(strict=True);report.update(binary_sha256=sha(binary.read_bytes()),script_sha256=sha(s.read_bytes()))
  run(binary,checks,commands)
  if {c['name'] for c in checks}!=EXPECTED_CHECKS or len(checks)!=len(EXPECTED_CHECKS) or tuple(c['name'] for c in commands)!=COMMAND_SCHEDULE:raise AssertionError('incomplete test schedule')
  report['result']='PASS'
 except Exception as e:
  report.update(error_type=type(e).__name__,error=str(e))
  if not any(x['status']=='FAIL' for x in checks):checks.append(dict(name='execution_interrupted',status='FAIL'))
 report.update(provenance(s));report['check_count']=len(checks);report['counts']={k:sum(c['status']==k.upper() for c in checks) for k in ('pass','fail')};report['counts']['total']=len(checks)
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(result=report['result'],checks=len(checks),commands=len(commands),error=report.get('error')),ensure_ascii=True))
 return 0 if report['result']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
