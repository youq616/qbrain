"""Independent, offline replay of fixed N48E real-host records.

No host/model execution. This checks content consistency against separately pinned
source, binaries and command order; it does not authenticate arbitrary reports.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, re
from pathlib import Path
SOURCE='e419acf60375e1a7a0794375c713f759b776aa0b'
NAMES='ad2cedd1c8e39a37ab68809aef68cbbb0713beaef11d3838ea40a34e084c337a'
HOST={'posix':'f9dab32248695e9ebd56b16a1921798fd85112cf5a69c7dfd0cabc1e17be4a11','nt':'0242a0dc705af67c90882b456a36b619883c1c786aad8fe071a1bc64e5d1d440'}
FIELDS={'schema','source','platform','host_version','qbrain_sha256','host_sha256','script_sha256','checks','records','passed','failure','result','formats','engine','native_v2_engine','v2_on_v1_timeout_preserved','model_prompts_sent','tools_call_requested','real_user_data_supplied','model_consumption_verified'}
def need(ok,why):
 if not ok:raise ValueError(why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def compact(x):return json.dumps(x,ensure_ascii=False,separators=(',',':')).encode()
def decode(raw):
 need(len(raw)<2*1024*1024,'report_bound')
 def pairs(rows):
  result={}
  for k,v in rows:need(k not in result,'duplicate_key');result[k]=v
  return result
 def fail(_):raise ValueError('nonfinite')
 return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=fail)
def obj(s):return decode(s.encode())
def plain(s):return re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',s)
def verify(r,binary,script):
 need(isinstance(r,dict) and set(r)==FIELDS,'report_fields')
 need(r['schema']=='qbrain-n48e-pinned-host-review-v1' and r['source']==SOURCE,'source')
 need(r['platform'] in HOST and r['qbrain_sha256']==sha(binary) and r['host_sha256']==HOST[r['platform']] and r['script_sha256']==sha(script),'component_identity')
 need(r['host_version']=='1.18.31' and r['result']=='PASS' and r['failure'] is None and type(r['passed']) is int and r['passed']==75,'result')
 need(r['native_v2_engine']=='NOT_RUN' and r['v2_on_v1_timeout_preserved'] is False and r['engine']=='OpenCode V1; V2 input compatibility only','v2_scope')
 for k in ('model_prompts_sent','tools_call_requested'):need(type(r[k]) is int and r[k]==0,'calls_scope')
 need(r['real_user_data_supplied'] is False and r['model_consumption_verified'] is False and r['formats']==['v1','v2'],'scope')
 need(len(r['checks'])==75 and all(set(x)=={'name','passed'} and x['passed'] is True for x in r['checks']),'checks')
 need(sha(compact([x['name'] for x in r['checks']]))==NAMES,'ordered_checks')
 rows=r['records'];need(isinstance(rows,list) and len(rows)==63,'record_count')
 first=rows[0];need(first['program'] in ('opencode','opencode.exe') and first['args']==['--version'] and first['exit']==0 and first['stdout'].strip()=='1.18.31','version_output')
 actions=['preview','install','status','debug','list','change','status','uninstall-preview','reconcile-preview','reconcile','debug','list','preview','install','status','debug','list','preview','install','status','debug','list','reconcile-preview','reconcile','status','debug','list','uninstall-preview','uninstall','debug','list']
 for fmt,start in [('v1',1),('v2',32)]:
  major=1 if fmt=='v1' else 2;part=rows[start:start+31];plans={};settings=None;name=None;project=None;exe=None
  debug_count=0;list_count=0
  for i,(rec,action) in enumerate(zip(part,actions)):
   if action=='change':
    need(set(rec)=={'kind','format','before','after'} and rec['kind']=='host-config-change' and rec['format']==fmt,'change_record')
    before=rec['before'];after=rec['after']
    expected=re.sub(r'^\s*\{','{\n  "$schema": "https://opencode.ai/config.json",',before,count=1)
    need('"$schema"' not in before and after==expected,'exact_schema_insertion');continue
   need(set(rec)=={'program','args','exit','stdout','stderr'} and type(rec['exit']) is int and rec['exit']==(1 if i==7 else 0),'command_exit')
   args=rec['args'];need(isinstance(args,list) and all(isinstance(x,str) for x in args),'argument_types')
   if action in ('debug','list'):
    need(rec['program']==first['program'] and args==(['debug','config'] if action=='debug' else ['mcp','list']),'host_command')
    if action=='debug':
     debug_count+=1;value=obj(rec['stdout']);servers=value.get('mcp',{})
     if i==29:need(not servers,'uninstalled_config');continue
     need(set(servers)=={name},'single_managed_server');s=servers[name]
     expected={'type':'local','command':[exe,'serve','--brain','host-'+fmt,'--tool-profile','memory']+(['--allow-write'] if settings else []),'cwd':project,'environment':{'QBRAIN_MCP_ALLOW_WRITE':'0'},'enabled':True}
     if fmt=='v1':expected['timeout']=10000
     need(s==expected and s['enabled'] is True and (fmt!='v1' or type(s['timeout']) is int),'resolved_server_definition')
    else:
     list_count+=1;text=plain(rec['stdout']+'\n'+rec['stderr'])
     if i==30:need('No MCP servers configured' in text,'uninstalled_host_list')
     else:need(re.search(re.escape(name)+r'\s+connected\b',text) is not None and '1 server(s)' in text,'actual_connected_text')
    continue
   need(rec['program'] in ('qbrain','qbrain.exe') and args[:2]==['opencode',action] and '--project' in args,'qbrain_command')
   p=args[args.index('--project')+1];need(project is None or p==project,'project_identity');project=p
   value=obj(rec['stdout'])
   if action=='status':
    need(value['schema']=='qbrain-opencode-status-v1' and value['installed'] is True and value['recovery_required'] is False,'status')
    need(value['configuration_matches'] is (i!=6) and value['format']==major and type(value['format']) is int and value['write_enabled'] is settings,'status_values')
    need(value['host_consumption_verified'] is False and value['effective_configuration_verified'] is False,'status_scope');continue
   if i==7:
    need(value=={'error':{'code':'opencode_external_edit'}},'drift_refused');continue
   operation={'preview':'install','install':'install','reconcile-preview':'reconcile','reconcile':'reconcile','uninstall-preview':'uninstall','uninstall':'uninstall'}[action]
   need(value['schema']=='qbrain-opencode-plan-v1' and value['operation']==operation and value['model_calls']==0 and value['host_consumption_verified'] is False,'plan')
   need(re.fullmatch('qbrain_[0-9a-f]{24}',value['server_name']) and (name is None or name==value['server_name']),'server_identity');name=value['server_name']
   if operation=='install':
    requested='--allow-write' in args
    need(args[args.index('--format')+1]==fmt and args[args.index('--brain')+1]=='host-'+fmt,'selected_format_brain')
    exe=args[args.index('--binary')+1]
    need(value['write_enabled'] is requested and type(value['format']) is int and value['format']==major,'requested_permissions')
    if action=='install':settings=requested
   if action in ('preview','reconcile-preview','uninstall-preview'):plans[operation]=value['plan_sha256']
   else:
    need('--approve-sha256' in args and args[args.index('--approve-sha256')+1]==value['plan_sha256']==plans[operation] and value['applied'] is True,'explicit_approval')
   if operation=='reconcile':need(value['write_enabled'] is settings and value['format']==major,'reconcile_preserves_permissions')
  need((debug_count,list_count)==(6,6),'host_coverage')
 return {'result':'PINNED_HOST_RECORDS_VERIFIED','checks':75,'record_count':63,'host_commands':25,'qbrain_commands':36,'observed_schema_edits':2,'connected_checks':10,'native_v2_engine':'NOT_RUN','v2_timeout_on_v1_preserved':False,'model_consumption_verified':False,'new_host_execution':False}
def negatives(r,binary,script):
 cases=[]
 for label in ('bool-count','wrong-binary','wrong-script','version','missing-record','host-scope','v2-claim','v2-timeout-claim','check-order','write-command','timeout-boolean','missing-timeout','extra-schema-edit','disconnected','post-uninstall-server','approval','unexpected-host-command'):
  bad=copy.deepcopy(r)
  if label=='bool-count':bad['passed']=True
  if label=='wrong-binary':bad['qbrain_sha256']='0'*64
  if label=='wrong-script':bad['script_sha256']='0'*64
  if label=='version':bad['records'][0]['stdout']='2.0.0\n'
  if label=='missing-record':bad['records'].pop()
  if label=='host-scope':bad['model_consumption_verified']=True
  if label=='v2-claim':bad['native_v2_engine']='PASS'
  if label=='v2-timeout-claim':bad['v2_on_v1_timeout_preserved']=True
  if label=='check-order':bad['checks'].reverse()
  if label in ('write-command','timeout-boolean','missing-timeout'):
   rec=bad['records'][4];v=obj(rec['stdout']);s=next(iter(v['mcp'].values()))
   if label=='write-command':s['command'].append('--allow-write')
   if label=='timeout-boolean':s['timeout']=True
   if label=='missing-timeout':s.pop('timeout')
   rec['stdout']=json.dumps(v)
  if label=='extra-schema-edit':bad['records'][6]['after']+=' // extra undocumented edit'
  if label=='disconnected':bad['records'][5]['stdout']=bad['records'][5]['stdout'].replace('connected','disconnected')
  if label=='post-uninstall-server':bad['records'][30]['stdout']='{"mcp":{"unexpected":{}}}'
  if label=='approval':bad['records'][2]['args'][-1]='0'*64
  if label=='unexpected-host-command':bad['records'][5]['args']=['run','model prompt']
  try:verify(bad,binary,script)
  except (ValueError,KeyError,TypeError):cases.append({'case':label,'rejected':True})
  else:raise ValueError('accepted mutation '+label)
 verify(r,binary,script);return cases
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for k in ('report','binary','script'):p.add_argument('--'+k,type=Path,required=True)
 p.add_argument('--negatives',action='store_true');a=p.parse_args();r=decode(a.report.read_bytes());b=a.binary.read_bytes();s=a.script.read_bytes();out=verify(r,b,s)
 if a.negatives:out['negative_cases']=negatives(r,b,s)
 print(json.dumps(out,sort_keys=True))
