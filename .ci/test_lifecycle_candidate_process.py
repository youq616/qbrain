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

EXPECTED_CHECKS=frozenset(('archived_not_archive_candidate', 'bad_cursor', 'batch_payload_exact', 'budget_no_progress', 'budget_retry_retains_candidate', 'candidate_irrelevant_fields', 'candidate_never_authorizes_apply', 'candidate_read_only', 'candidate_strict_types', 'candidate_to_preview', 'cli_history', 'cli_source_isolated', 'current_metadata', 'duplicate_operation', 'empty_end', 'empty_no_migration', 'empty_read', 'explicit_apply', 'forget_not_restorable', 'future_not_stale', 'limit_33', 'mcp_cursor_roundtrip', 'mcp_default_read_allowed', 'mcp_restore_candidates', 'mcp_source_denied', 'mcp_stale_threshold', 'no_hidden_jobs', 'no_quote_copies', 'old_memory_unchanged', 'old_views_reject_new_fields', 'only_stale_live', 'operation_required', 'paged_static_inventory', 'predicate_filter', 'restore_candidates', 'restore_payload_apply', 'restore_unknown_age_allowed', 'six_tools', 'small_budget', 'stale_selection_rejected_atomically', 'stale_threshold_filter', 'tamper_not_suggested', 'unknown_not_stale'))
EXPECTED_COMMAND_COUNT=63  # Fixed schedule including six expected CLI failures.
def enc(v):return json.dumps(v,ensure_ascii=False,separators=(',',':')).encode('utf-8')

def run(binary,checks,commands):
 with tempfile.TemporaryDirectory(prefix='qbrain-candidates-') as d:
  root=Path(d)/'批量 space 😀';root.mkdir();project=root/'project';project.mkdir()
  env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
  env.update(HOME=str(root),USERPROFILE=str(root),LOCALAPPDATA=str(root),APPDATA=str(root),TEMP=str(root),TMP=str(root))
  data=root if os.name=='nt' else root/'.local'/'share'
  dbpath=data/'Qbrain'/'brains'/'candidates-ci'/'brain.db'
  def invoke(args,p=None,expected=0,raw=None):
   record={'args':args[:2],'expected_exit':expected}
   try:r=subprocess.run([str(binary),*args,'--brain','candidates-ci'],input=raw if raw is not None else (b'' if p is None else enc(p)),cwd=project,env=env,capture_output=True,timeout=30)
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
   event=cli(['memory','capture','--source',source,'--manual'],{'session_id':'candidates-real-process','fragment_id':tag,'messages':[{'role':'user','content':quote}]})['event_id']
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
  def candidates(op='archive',opts=None,expected=0,source='alpha'):
   return cli(['fact','candidates','--source',source,'--operation',op,*(opts or [])],expected=expected)
  invoke(['init']);sql("INSERT INTO sources(id,name) VALUES('alpha','alpha'),('beta','beta')")
  sql("INSERT INTO config(key,value) VALUES('memory.writeback','all'),('mcp.allowed_sources','alpha')")
  empty=candidates()
  check(empty['items']==[] and empty['batch_payload'] is None and empty['initialized'] is False,'empty_read')
  check(empty['has_more'] is False and empty['next_after_id'] is None,'empty_end')
  check(sql("SELECT COUNT(*) FROM sqlite_master WHERE name='memory_fact_archive'")==0,'empty_no_migration')
  qa='我偏好本项目的日志前缀为候选甲。😀';qz='我偏好本项目的日志前缀为候选乙。';qf='我偏好隔离项目的日志前缀为候选丙。'
  a,ea=seed('old',qa);z,ez=seed('new',qz);foreign,ef=seed('foreign',qf,'beta')
  # Synthetic fixture time only: these are not real aged user sessions.
  sql("UPDATE memory_items SET created_at=CAST(strftime('%s','now') AS INTEGER)-200*86400 WHERE event_id IN (?,?)",(ea,ef))
  tables=sql('SELECT COUNT(*) FROM sqlite_master');before=policy();r=candidates()
  check([x['fact_id'] for x in r['items']]==[a],'only_stale_live')
  check(r['items'][0]['age']['age_state']=='stale' and r['items'][0]['expected_revision']==1,'current_metadata')
  check(all(text not in json.dumps(r,ensure_ascii=False) for text in (qa,qz,qf)) and all('object' not in x and 'evidence' not in x for x in r['items']),'no_quote_copies')
  check(r['batch_payload']==req('archive',entry(a,1)),'batch_payload_exact')
  check(policy()==before and sql('SELECT COUNT(*) FROM sqlite_master')==tables,'candidate_read_only')
  read_args={'source_id':'alpha','view':'lifecycle_candidates','operation':'archive'}
  rr=rpc('memory_read',read_args);decoded=result(rr)
  check(not rr.get('isError') and decoded['batch_payload']==r['batch_payload'] and decoded['items'][0]['age']['latest_valid_support_created_at']==r['items'][0]['age']['latest_valid_support_created_at'] and decoded['items'][0]['age']['age_seconds']==decoded['evaluated_at']-decoded['items'][0]['age']['latest_valid_support_created_at'],'mcp_default_read_allowed')
  check('source_not_allowed' in str(rpc('memory_read',{**read_args,'source_id':'beta'})),'mcp_source_denied')
  check([x['fact_id'] for x in candidates(source='beta')['items']]==[foreign],'cli_source_isolated')
  check(candidates(opts=['--predicate','memory.decision'])['items']==[],'predicate_filter')
  check(candidates(opts=['--stale-after-days','365'])['items']==[],'stale_threshold_filter')
  threshold=rpc('memory_read',{**read_args,'stale_after_days':365});check(not threshold.get('isError') and result(threshold)['items']==[],'mcp_stale_threshold')
  check(all(rpc('memory_read',{**read_args,k:v}).get('isError') is True for k,v in [('payload','{}'),('event_id',ea),('fact_id',a),('query','我偏好'),('include_history',False)]),'candidate_irrelevant_fields')
  check(all(rpc('memory_read',{**read_args,k:v}).get('isError') is True for k,v in [('limit',True),('after_id',{}),('operation',1),('stale_after_days','180')]),'candidate_strict_types')
  check(all(rpc('memory_read',{'source_id':'alpha','view':view,'operation':'archive','after_id':a}).get('isError') is True for view in ('memories','facts','conflicts','recall','lifecycle','lifecycle_batch')),'old_views_reject_new_fields')
  check('fact_batch_invalid_operation' in str(rpc('memory_read',{'source_id':'alpha','view':'lifecycle_candidates'})),'operation_required')
  for args,label in [(['--after-id','x'],'bad_cursor'),(['--limit','33'],'limit_33'),(['--max-bytes','511'],'small_budget'),(['--history'],'cli_history'),(['--operation','restore'],'duplicate_operation')]:
   bad=candidates(opts=args,expected=1);check('error' in bad,label)
  listed=rpc('',listing=True);check({t['name'] for t in listed['tools']}=={'search','memory_read','memory_write','context_read','context_write','get_page'},'six_tools')
  payload=r['batch_payload'];pv=batch(payload);check(pv['applied'] is False and pv['counts']['change']==1,'candidate_to_preview')
  write_args={'source_id':'alpha','action':'fact_lifecycle_batch','payload':enc(payload).decode()}
  check('write_denied' in str(rpc('memory_write',write_args)),'candidate_never_authorizes_apply')
  stale_before=candidates(opts=['--max-bytes','768']);check(stale_before['items']==[] and stale_before['has_more'] is True and stale_before['next_after_id']=='' and stale_before['progressed'] is False,'budget_no_progress')
  check([x['fact_id'] for x in candidates(opts=['--after-id',stale_before['next_after_id'],'--max-bytes','8192'])['items']]==[a],'budget_retry_retains_candidate')
  rp=rpc('memory_write',write_args,write=True);check(not rp.get('isError') and result(rp)['applied'] is True,'explicit_apply')
  check(candidates()['items']==[],'archived_not_archive_candidate')
  restore=candidates('restore');check([x['fact_id'] for x in restore['items']]==[a] and restore['items'][0]['expected_revision']==2,'restore_candidates')
  rr=rpc('memory_read',{**read_args,'operation':'restore'});check(not rr.get('isError') and result(rr)['batch_payload']==restore['batch_payload'],'mcp_restore_candidates')
  sql("UPDATE memory_items SET created_at='bad-time' WHERE event_id=?",(ea,))
  check(candidates('restore')['items'][0]['age']['age_state']=='unknown','restore_unknown_age_allowed')
  check(batch(restore['batch_payload'],apply=True)['applied'] is True,'restore_payload_apply')
  check(candidates()['items']==[],'unknown_not_stale')
  sql("UPDATE memory_items SET created_at=CAST(strftime('%s','now') AS INTEGER)+86400 WHERE event_id=?",(ea,))
  check(candidates()['items']==[],'future_not_stale')
  sql("UPDATE memory_items SET created_at=CAST(strftime('%s','now') AS INTEGER)-200*86400 WHERE event_id IN (?,?)",(ea,ez))
  first=candidates(opts=['--limit','1']);second=candidates(opts=['--limit','1','--after-id',first['next_after_id']])
  check([x['fact_id'] for x in first['items']+second['items']]==sorted([a,z]) and second['next_after_id'] is None,'paged_static_inventory')
  rr=rpc('memory_read',{**read_args,'limit':1,'after_id':first['next_after_id']});check(not rr.get('isError') and [x['fact_id'] for x in result(rr)['items']]==[second['items'][0]['fact_id']],'mcp_cursor_roundtrip')
  old_selection=candidates()['batch_payload'];cli(['fact','archive','--source','alpha'],entry(a,3))
  check(batch(old_selection,apply=True,expected=1)['error']['code']=='fact_revision_conflict' and read(z)['revision']==1,'stale_selection_rejected_atomically')
  cli(['memory','forget','--source','alpha','--event',ea]);check(candidates('restore')['items']==[],'forget_not_restorable')
  sql("UPDATE memory_items SET quote='forged' WHERE event_id=?",(ez,));check(candidates()['items']==[],'tamper_not_suggested')
  sql('UPDATE memory_items SET quote=? WHERE event_id=?',(qz,ez));check(cli(['memory','read','--source','alpha','--query','候选乙'])['items'][0]['quote']==qz,'old_memory_unchanged')
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
