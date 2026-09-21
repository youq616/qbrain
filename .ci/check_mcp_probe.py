"""Offline replay of N48D records; no execution or arbitrary-evidence authenticity.

Fixed metadata invariants plus exact command coverage, approval relations and
actual-result checks. No imports of product implementation or fixture peer logic.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,re
from pathlib import Path

FIELDS={'schema','result','code','phase','approval_sha256','binary_sha256','process_started',
 'initialize_verified','catalog_verified','ping_verified','clean_shutdown_verified','catalog_sha256',
 'tool_count','messages_received','stdout_bytes','stderr_bytes','exit_code','process_cleanup_verified',
 'workspace_cleanup_verified','workspace_cleanup_error','elapsed_ms','tools_called','model_requests_sent','real_brain_supplied',
 'opencode_started','host_consumption_verified','write_authorization_verified','os_security_sandbox'}
BOOLS={'process_started','initialize_verified','catalog_verified','ping_verified','clean_shutdown_verified',
       'process_cleanup_verified','workspace_cleanup_verified','real_brain_supplied','opencode_started',
       'host_consumption_verified','write_authorization_verified','os_security_sandbox'}
CODES={'verified','process_start_error','protocol_version_mismatch','server_identity_mismatch','tools_capability_missing',
 'response_id_mismatch','server_response_error','catalog_shape','catalog_tool_identity','catalog_tool_shape','catalog_schema',
 'catalog_required_routes_missing','invalid_ping_result','trailing_output','invalid_protocol_json','incomplete_frame',
 'empty_frame','unsolicited_message','message_limit','frame_limit','stdout_limit','stderr_limit','nonzero_exit','protocol_timeout'}

def need(ok,why):
    if not ok:raise ValueError(why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def encode(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def decode(raw):
    need(len(raw)<4*1024*1024,'record_bound')
    def unique(rows):
        obj={}
        for k,v in rows:need(k not in obj,'duplicate_key');obj[k]=v
        return obj
    def reject(_):raise ValueError('nonfinite')
    return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique,parse_constant=reject)

def check_result(r):
    need(isinstance(r,dict) and set(r)==FIELDS,'result_fields')
    need(r['schema']=='qbrain-mcp-check-result-v1' and r['result'] in ('FAILED','ISOLATED_MCP_VERIFIED') and r['code'] in CODES,'result_identity')
    need(r['phase'] in ('preflight','workspace','start','initialize','catalog','ping','shutdown','complete'),'phase')
    for k in BOOLS:need(type(r[k]) is bool,'boolean')
    for k in ('approval_sha256','binary_sha256'):need(isinstance(r[k],str) and re.fullmatch('[0-9a-f]{64}',r[k]),'digest')
    for k,cap in (('messages_received',16),('stdout_bytes',262145),('stderr_bytes',65537),('tool_count',6),('elapsed_ms',120000)):
        need(type(r[k]) is int and 0<=r[k]<=cap,'counter')
    for k in ('tools_called','model_requests_sent'):need(type(r[k]) is int and r[k]==0,'unrequested_calls')
    for k in ('real_brain_supplied','opencode_started','host_consumption_verified','write_authorization_verified','os_security_sandbox'):
        need(r[k] is False,'false_scope')
    need(r['exit_code'] is None or type(r['exit_code']) is int,'exit_type')
    need(r['workspace_cleanup_error'] is None or (type(r['workspace_cleanup_error']) is int and r['workspace_cleanup_error']>0),'cleanup_error_type')
    if r['workspace_cleanup_verified']:need(r['workspace_cleanup_error'] is None,'successful_cleanup_error')
    if r['stdout_bytes']==0:need(r['messages_received']==0,'unreceived_message_count')
    if r['catalog_verified']:
        need(r['initialize_verified'] and r['tool_count']==6 and isinstance(r['catalog_sha256'],str) and re.fullmatch('[0-9a-f]{64}',r['catalog_sha256']),'catalog_evidence')
    else:need(r['catalog_sha256'] is None and r['tool_count']==0,'unverified_catalog')
    if r['ping_verified']:need(r['catalog_verified'],'phase_order')
    if r['clean_shutdown_verified']:need(r['ping_verified'] and r['exit_code']==0,'shutdown_order')
    if r['result']=='ISOLATED_MCP_VERIFIED':
        need(r['code']=='verified' and r['phase']=='complete' and r['messages_received']>=3 and all(r[k] for k in
            ('process_started','initialize_verified','catalog_verified','ping_verified','clean_shutdown_verified','process_cleanup_verified','workspace_cleanup_verified')),'false_success')
    else:need(r['code']!='verified','false_failure')


def verify(r,binary,peer,script):
    need(r.get('schema')=='qbrain-n48d-process-v1' and r.get('binary_sha256')==sha(binary) and r.get('peer_sha256')==sha(peer) and r.get('script_sha256')==sha(script),'component_identity')
    need(type(r.get('passed')) is int and r['passed']==172 and type(r.get('failed')) is int and r['failed']==0 and r.get('failure') is None,'execution')
    need(r.get('real_opencode_loaded') is False and type(r.get('provider_calls_requested')) is int and r['provider_calls_requested']==0,'execution_scope')
    need(len(r['checks'])==172 and all(set(x)=={'name','passed'} and isinstance(x['name'],str) and x['passed'] is True for x in r['checks']),'check_coverage')
    need(sha(encode([x['name'] for x in r['checks']]))=='0ec7e946c31942a5ad127aa477565e264830e6731ef2bba8ac321758dfbc5b4e','ordered_check_coverage')
    need(type(r['commands']) is int and r['commands']==len(r['records'])==96,'record_coverage')
    plans={};runs=0;passed=0;cases=set()
    for rec in r['records']:
        need(set(rec)=={'args','exit','stdout','stderr','elapsed_seconds'} and rec['stderr']=='' and type(rec['exit']) is int,'record_shape')
        need(type(rec['elapsed_seconds']) in (int,float) and 0<=rec['elapsed_seconds']<12,'subprocess_time')
        args=rec['args'];need(isinstance(args,list) and all(isinstance(x,str) for x in args),'argument_types')
        out=decode(rec['stdout'].encode())
        if rec['exit']==2:
            need(set(out)=={'error'} and set(out['error'])=={'code'} and re.fullmatch('[a-z_]+',out['error']['code']),'preflight_error');continue
        opts=dict(zip(args[1::2],args[2::2]));need(args[0] in ('preview','run') and len(opts)*2==len(args)-1,'command')
        if args[0]=='preview':
            need(rec['exit']==0 and out['schema']=='qbrain-mcp-check-plan-v1','preview')
            p=copy.deepcopy(out);ident=p.pop('approval_sha256');need(sha(encode(p))==ident,'preview_hash');plans[ident]=p
            need(out['arguments']==['serve','--brain','probe','--tool-profile','memory'] and out['tools_called']==0 and
                out['os_security_sandbox'] is False,'preview_scope')
        else:
            runs+=1;check_result(out);ident=opts['--approve-sha256'];need(ident in plans and out['approval_sha256']==ident,'approval_precedes_execution')
            plan=plans[ident];need(out['binary_sha256']==plan['binary']['sha256'] and opts['--binary']==plan['binary']['path'] and int(opts['--timeout-ms'])==plan['timeout_ms'],'approved_target')
            need(rec['exit']==(0 if out['result']=='ISOLATED_MCP_VERIFIED' else 1),'result_exit')
            passed+=rec['exit']==0;cases.add(out['code'])
    need(runs==40 and passed==6,'runtime_coverage')
    need({'protocol_timeout','trailing_output','stderr_limit','stdout_limit','frame_limit','response_id_mismatch'}<=cases,'negative_coverage')
    return {'result':'MCP_CHECK_RECORDS_VERIFIED','checks':172,'commands':96,'runtime_results':runs,'successes':passed,
            'new_process_execution':False,'real_agent_loaded':False}


def negatives(r,binary,peer,script):
    done=[]
    for name in ('bad-hash','count-bool','missing-record','false-host','secret-field','fake-success','bool-exit','unreceived-frame',
                 'tool-invocation','changed-approval','catalog-count','duplicate-key','check-order','cleanup-error-bool'):
        bad=copy.deepcopy(r)
        if name=='duplicate-key':
            try:decode(b'{"a":1,"a":2}')
            except ValueError:done.append(name);continue
            raise ValueError('duplicate accepted')
        if name=='bad-hash':bad['binary_sha256']='0'*64
        if name=='count-bool':bad['passed']=True
        if name=='missing-record':bad['records'].pop()
        if name=='check-order':bad['checks'].reverse()
        row=next(x for x in bad['records'] if x['args'][0]=='run' and x['exit']==0)
        value=json.loads(row['stdout'])
        if name=='false-host':value['host_consumption_verified']=True
        if name=='secret-field':value['stderr']='private'
        if name=='fake-success':value['clean_shutdown_verified']=False
        if name=='bool-exit':value['exit_code']=False
        if name=='unreceived-frame':value['stdout_bytes']=0;value['messages_received']=1
        if name=='tool-invocation':value['tools_called']=1
        if name=='changed-approval':value['approval_sha256']='0'*64
        if name=='catalog-count':value['tool_count']=5
        if name=='cleanup-error-bool':value['workspace_cleanup_error']=True
        row['stdout']=json.dumps(value)
        try:verify(bad,binary,peer,script)
        except (ValueError,KeyError,TypeError):done.append(name)
        else:raise ValueError('accepted mutation '+name)
    verify(r,binary,peer,script);return done

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('report','binary','peer','test'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--negatives',action='store_true');a=p.parse_args()
    r=decode(a.report.read_bytes());b=a.binary.read_bytes();peer=a.peer.read_bytes();s=a.test.read_bytes();out=verify(r,b,peer,s)
    if a.negatives:out['rejected_mutations']=negatives(r,b,peer,s)
    print(json.dumps(out,sort_keys=True))
