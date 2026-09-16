"""Real isolated batch CLI/MCP checks. No authenticated client or user data."""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from test_hook_fact_process import provenance

EXPECTED_CHECKS=frozenset(('empty_rejected','empty_no_schema','preview_metadata','preview_order','preview_not_applied',
 'preview_no_quotes','lifecycle_days_roundtrip','duplicate_key_mcp','preview_no_migration','default_preview_allowed','default_apply_denied','preview_cannot_apply',
 'preview_rejects_irrelevant','wrong_payload_type','legacy_read_unchanged','source_denied','foreign_unavailable',
 'duplicate_operation_key','duplicate_member_key','duplicate_id','oversize_payload','invalid_operation','invalid_revision',
 'cli_strict','six_tools','allowed_atomic_apply','both_archived','evidence_preserved','counterclaim_preserved',
 'no_op_no_revision','stale_last_atomic','restore_preview','injected_restore_rollback','preview_not_lease',
 'fresh_mixed_restore','restored_anchors','forget_not_revived','retired_not_restored','old_memory_read','no_hidden_jobs'))
EXPECTED_COMMAND_COUNT=54  # Fixed schedule: 40 checks, including expected negative exits.
def enc(v):return json.dumps(v,ensure_ascii=False,separators=(',',':')).encode('utf-8')

def run(binary,checks,commands):
 with tempfile.TemporaryDirectory(prefix='qbrain-batch-') as d:
  root=Path(d)/'批量 space 😀';root.mkdir();project=root/'project';project.mkdir()
  env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
  env.update(HOME=str(root),USERPROFILE=str(root),LOCALAPPDATA=str(root),APPDATA=str(root),TEMP=str(root),TMP=str(root))
  data=root if os.name=='nt' else root/'.local'/'share'
  dbpath=data/'Qbrain'/'brains'/'batch-ci'/'brain.db'
  def invoke(args,p=None,expected=0,raw=None):
   record={'args':args[:2],'expected_exit':expected}
   try:r=subprocess.run([str(binary),*args,'--brain','batch-ci'],input=raw if raw is not None else (b'' if p is None else enc(p)),cwd=project,env=env,capture_output=True,timeout=30)
   except subprocess.TimeoutExpired:
    record.update(exit_code=None,timed_out=True);commands.append(record);raise
   record['exit_code']=r.returncode;commands.append(record)
   if r.returncode!=expected:
    record['stderr_excerpt']=r.stderr.decode('utf-8',errors='replace').replace(str(root),'<fixture>')[:1024]
    record['stdout_excerpt']=r.stdout.decode('utf-8',errors='replace').replace(str(root),'<fixture>')[:1024]
    raise AssertionError('Unexpected exit at command '+str(len(commands)))
   return r.stdout
  def cli(args,p=None,expected=0,raw=None):return json.loads(invoke(args,p,expected,raw))
  def check(ok,name):
   checks.append({'name':name,'status':'PASS' if ok else 'FAIL'})
   if not ok:raise AssertionError(name)
  def sql(query,args=(),many=False):
   with closing(sqlite3.connect(dbpath,timeout=5)) as db:
    db.execute('PRAGMA foreign_keys=ON');rows=db.execute(query,args).fetchall();db.commit()
    return rows if many else (rows[0][0] if rows else None)
  def seed(tag,quote,source='alpha'):
   event=cli(['memory','capture','--source',source,'--manual'],{'session_id':'batch-real-process','fragment_id':tag,'messages':[{'role':'user','content':quote}]})['event_id']
   cli(['memory','extract','--source',source,'--event',event]);f=cli(['fact','promote','--source',source,'--event',event])['items'][0]
   return f['fact_id'],event
  def entry(id,rev):return {'fact_id':id,'expected_revision':rev}
  def req(op,*items):return {'operation':op,'items':list(items)}
  def batch(p,apply=False,expected=0,source='alpha',raw=None):return cli(['fact','batch-apply' if apply else 'batch-preview','--source',source],p,expected,raw)
  def rpc(name,args=None,write=False,listing=False):
   requests=[{'jsonrpc':'2.0','id':0,'method':'initialize','params':{}},{'jsonrpc':'2.0','method':'notifications/initialized'},{'jsonrpc':'2.0','id':1,'method':'tools/list' if listing else 'tools/call','params':{} if listing else {'name':name,'arguments':args}}]
   output=invoke(['serve','--tool-profile','memory',*(['--allow-write'] if write else [])],raw=b'\n'.join(enc(x) for x in requests)+b'\n')
   return next(x['result'] for x in map(json.loads,output.decode('utf-8-sig').splitlines()) if x.get('id')==1)
  def result(reply):return json.loads(reply['content'][-1]['text'])
  def read(id):return cli(['fact','read','--source','alpha','--id',id,'--history'])['items'][0]
  def policy():return sql('SELECT fact_id,revision FROM memory_facts WHERE source_id=\'alpha\' ORDER BY fact_id',many=True)
  invoke(['init']);sql("INSERT INTO sources(id,name) VALUES('alpha','alpha'),('beta','beta')")
  sql("INSERT INTO config(key,value) VALUES('memory.writeback','all'),('mcp.allowed_sources','alpha')")
  check(batch(req('archive'),expected=1)['error']['code']=='fact_batch_invalid_size','empty_rejected')
  check(sql("SELECT COUNT(*) FROM sqlite_master WHERE name='memory_fact_lifecycle_module'")==0,'empty_no_schema')
  qa='我偏好不用图形界面，而使用终端。😀';qz='我偏好使用图形界面。'
  a,ea=seed('a',qa);z,ez=seed('z',qz);foreign,_=seed('foreign','I prefer isolated.','beta')
  cli(['fact','contradict','--source','alpha'],{'fact_id':a,'other_id':z})
  p=req('archive',entry(z,2),entry(a,2));original=read(a);before=policy();preview=batch(p)
  check(preview['counts']=={'total':2,'change':2,'unchanged':0},'preview_metadata')
  check([x['fact_id'] for x in preview['items']]==[z,a],'preview_order')
  check(preview['result']=='PREVIEW' and preview['applied'] is False and policy()==before,'preview_not_applied')
  check(qa not in json.dumps(preview,ensure_ascii=False) and qz not in json.dumps(preview,ensure_ascii=False),'preview_no_quotes')
  check(preview['schema_preparation_required'] is True and sql("SELECT COUNT(*) FROM sqlite_master WHERE name='memory_fact_archive'")==0,'preview_no_migration')
  read_args={'source_id':'alpha','view':'lifecycle_batch','payload':enc(p).decode()}
  r=rpc('memory_read',read_args);check(not r.get('isError') and result(r)==preview,'default_preview_allowed')
  days=rpc('memory_read',{'source_id':'alpha','view':'lifecycle','fact_id':a,'stale_after_days':30})
  check(not days.get('isError') and result(days)['stale_after_days']==30,'lifecycle_days_roundtrip')
  write_args={'source_id':'alpha','action':'fact_lifecycle_batch','payload':enc(p).decode()}
  check('write_denied' in str(rpc('memory_write',write_args)),'default_apply_denied')
  bad={**p,'apply':True};check('fact_unexpected_argument' in str(rpc('memory_read',{**read_args,'payload':enc(bad).decode()})),'preview_cannot_apply')
  check(all(rpc('memory_read',{**read_args,key:value}).get('isError') is True for key,value in [('query','x'),('limit',1),('include_history',False),('event_id',ea)]),'preview_rejects_irrelevant')
  check(rpc('memory_read',{**read_args,'payload':p}).get('isError') is True,'wrong_payload_type')
  check(rpc('memory_read',{'source_id':'alpha','view':'memories','payload':enc(p).decode()}).get('isError') is True,'legacy_read_unchanged')
  check('source_not_allowed' in str(rpc('memory_read',{**read_args,'source_id':'beta'})),'source_denied')
  check(batch(req('archive',entry(foreign,1)),expected=1)['error']['code']=='fact_not_found','foreign_unavailable')
  raw=('{"operation":"restore","operation":"archive","items":'+json.dumps(p['items'])+'}').encode()
  check(batch(None,expected=1,raw=raw)['error']['code']=='fact_batch_duplicate_key' and batch(None,apply=True,expected=1,raw=raw)['error']['code']=='fact_batch_duplicate_key','duplicate_operation_key')
  raw=('{"operation":"archive","items":[{"fact_id":"'+a+'","fact_id":"'+z+'","expected_revision":2}]}').encode()
  check(batch(None,expected=1,raw=raw)['error']['code']=='fact_batch_duplicate_key','duplicate_member_key')
  check('fact_batch_duplicate_key' in str(rpc('memory_write',{**write_args,'payload':raw.decode()},write=True)),'duplicate_key_mcp')
  check(batch(req('archive',entry(a,2),entry(a,2)),expected=1)['error']['code']=='fact_batch_duplicate_id','duplicate_id')
  check(batch(None,expected=1,raw=b' '*8193+enc(p))['error']['code']=='fact_batch_payload_limit','oversize_payload')
  check(batch(req('forget',entry(a,2)),expected=1)['error']['code']=='fact_batch_invalid_operation','invalid_operation')
  check(batch(req('archive',entry(a,True)),expected=1)['error']['code']=='fact_invalid_revision','invalid_revision')
  check(cli(['fact','batch-preview','--source','alpha','--limit','1'],p,1)['error']['code']=='invalid_cli_argument','cli_strict')
  listed=rpc('',listing=True);check({t['name'] for t in listed['tools']}=={'search','memory_read','memory_write','context_read','context_write','get_page'},'six_tools')
  reply=rpc('memory_write',write_args,write=True);applied=result(reply)
  check(not reply.get('isError') and applied['applied'] is True and applied['counts']['change']==2,'allowed_atomic_apply')
  check(sql('SELECT COUNT(*) FROM memory_fact_archive')==2 and all(v==3 for _,v in policy()),'both_archived')
  now=read(a);check(now['evidence']==original['evidence'] and now['object']==original['object'] and now['status']=='active','evidence_preserved')
  cli(['fact','restore','--source','alpha'],entry(a,3))
  recalled=cli(['fact','recall','--source','alpha','--query','终端'])
  check(len(recalled['items'])==1 and len(recalled['items'][0]['facts'])==2,'counterclaim_preserved')
  cli(['fact','archive','--source','alpha'],entry(a,4))
  current=req('archive',entry(a,5),entry(z,3));check(batch(current,apply=True)['counts']['unchanged']==2 and policy()==sorted([(a,5),(z,3)]),'no_op_no_revision')
  stale=req('restore',entry(a,5),entry(z,2));check(batch(stale,apply=True,expected=1)['error']['code']=='fact_revision_conflict' and sql('SELECT COUNT(*) FROM memory_fact_archive')==2 and policy()==sorted([(a,5),(z,3)]),'stale_last_atomic')
  restore=req('restore',entry(a,5),entry(z,3));check(batch(restore)['counts']['change']==2,'restore_preview')
  sql("CREATE TRIGGER fail_batch BEFORE DELETE ON memory_fact_archive WHEN OLD.fact_id='"+z+"' BEGIN SELECT RAISE(ABORT,'synthetic'); END")
  check(batch(restore,apply=True,expected=1)['error']['code']=='memory_storage_error' and sql('SELECT COUNT(*) FROM memory_fact_archive')==2 and policy()==sorted([(a,5),(z,3)]),'injected_restore_rollback')
  sql('DROP TRIGGER fail_batch');cli(['fact','restore','--source','alpha'],entry(a,5))
  check(batch(restore,apply=True,expected=1)['error']['code']=='fact_revision_conflict' and policy()==sorted([(a,6),(z,3)]),'preview_not_lease')
  r=batch(req('restore',entry(a,6),entry(z,3)),apply=True)
  check(r['counts']=={'total':2,'change':1,'unchanged':1} and policy()==sorted([(a,6),(z,4)]),'fresh_mixed_restore')
  check(len(cli(['fact','recall','--source','alpha','--query','我偏好'])['items'])==2,'restored_anchors')
  cli(['memory','forget','--source','alpha','--event',ea])
  check(batch(req('archive',entry(z,4),entry(a,6)),apply=True,expected=1)['error']['code']=='fact_not_found' and sql('SELECT COUNT(*) FROM memory_fact_archive')==0,'forget_not_revived')
  cli(['fact','retract','--source','alpha'],entry(z,4))
  check(batch(req('restore',entry(z,5)),apply=True,expected=1)['error']['code']=='fact_state_conflict','retired_not_restored')
  check(cli(['memory','read','--source','alpha','--query','图形界面'])['items'][0]['quote']==qz,'old_memory_read')
  check(sql('SELECT COUNT(*) FROM jobs')==0,'no_hidden_jobs')

def main():
 for stream in (sys.stdout,sys.stderr):
  if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace')
 p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 checks=[];commands=[];report={'result':'FAIL','checks':checks,'commands':commands,'native_windows':os.name=='nt','real_host_consumption_verified':False}
 try:
  binary=a.binary.resolve(strict=True);report.update(binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
  run(binary,checks,commands)
  if len(checks)!=len(EXPECTED_CHECKS) or {c['name'] for c in checks}!=EXPECTED_CHECKS:raise AssertionError('missing or repeated named case')
  if len(commands)!=EXPECTED_COMMAND_COUNT:raise AssertionError('incomplete command schedule')
  report['result']='PASS'
 except Exception as e:
  report.update(error_type=type(e).__name__,error=str(e))
  if not any(c['status']=='FAIL' for c in checks):checks.append({'name':'execution_interrupted','status':'FAIL'})
 report['check_count']=len(checks);report['counts']={'total':len(checks),'pass':sum(c['status']=='PASS' for c in checks),'fail':sum(c['status']=='FAIL' for c in checks)}
 report.update(provenance(Path(__file__).resolve()));a.report.parent.mkdir(parents=True,exist_ok=True)
 a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
 return 0 if report['result']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
