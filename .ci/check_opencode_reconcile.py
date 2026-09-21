"""Offline N48C CLI evidence replay; does not execute OpenCode or certify origin.

Checks exact file identities, ordered coverage and every recorded result against
its actual command/options. Temporary fixture state assertions remain test-owned.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, re
from pathlib import Path
from check_opencode_evidence import decode
from check_opencode_audit_report import output as audit_output

NAMES_SHA='18edacd250ac925409ec433335f14246793e426857dbc05737ed79c0fc5ee5fa'
CALLS_SHA='b126529eabb57ab305dca0a07bf426e55fa3dd1aa98945f3febf7539a944316d'
PLAN_FIELDS={'schema','operation','plan_sha256','configuration_file','server_name','would_change','write_enabled','format','host_consumption_verified','model_calls'}

def need(ok, message):
    if not ok: raise ValueError(message)
def sha(raw): return hashlib.sha256(raw).hexdigest()
def compact(x): return json.dumps(x,ensure_ascii=False,separators=(',',':')).encode()
def identifier(s,n=64): return isinstance(s,str) and re.fullmatch('[0-9a-f]{'+str(n)+'}',s) is not None

def verify(report,binary,script):
    need(isinstance(report,dict) and set(report)=={'schema','binary_sha256','test_sha256','passed','failed','checks','calls','failure','platform','host_started','model_calls'},'report_fields')
    need(report['schema']=='qbrain-n48c-cli-v1' and report['failure'] is None,'result')
    need(type(report['passed']) is int and report['passed']==133 and type(report['failed']) is int and report['failed']==0,'counts')
    need(report['binary_sha256']==sha(binary) and report['test_sha256']==sha(script),'source_identity')
    need(report['platform'] in ('nt','posix') and report['host_started'] is False and type(report['model_calls']) is int and report['model_calls']==0,'scope')
    checks=report['checks'];need(isinstance(checks,list) and len(checks)==133,'coverage')
    need(all(isinstance(c,dict) and set(c)=={'name','passed'} and c['passed'] is True for c in checks),'check_results')
    need(sha(compact([c['name'] for c in checks]))==NAMES_SHA,'ordered_coverage')
    calls=report['calls'];need(isinstance(calls,list) and len(calls)==164,'raw_calls')
    settings={};plans=errors=audits=states=0
    actions={'preview':'install','install':'install','uninstall-preview':'uninstall','uninstall':'uninstall',
             'recovery-preview':'recover','recover':'recover','reconcile-preview':'reconcile','reconcile':'reconcile'}
    pattern=[]
    for call in calls:
        need(isinstance(call,dict) and set(call)=={'args','exit','stdout','stderr'},'call_fields')
        args=call['args'];need(isinstance(args,list) and len(args)>=4 and all(isinstance(x,str) for x in args),'args')
        need(args[0]=='opencode' and args[2]=='--project','route')
        need(type(call['exit']) is int and call['exit'] in (0,1) and call['stderr']=='','exit')
        raw=call['stdout'];need(isinstance(raw,str) and raw.endswith('\n') and len(raw.encode())<=4096 and 'DO-NOT-OUTPUT' not in raw,'bounded_private_output')
        value=decode(raw.encode());project=args[3];action=args[1];pattern.append((action,call['exit']))
        if call['exit']:
            need(isinstance(value,dict) and set(value)=={'error'} and isinstance(value['error'],dict) and set(value['error'])=={'code'}
                 and isinstance(value['error']['code'],str) and value['error']['code'].startswith('opencode_'),'error_shape')
            errors+=1;continue
        if action=='audit':
            need(audit_output(value)=='LOCAL_REGISTRATION_CHECKS_PASSED','registered_audit')
            need((value['registered_format'],value['registered_write_enabled'])==settings[project],'audit_settings')
            audits+=1;continue
        if action=='status':
            need(value['schema']=='qbrain-opencode-status-v1' and value['installed'] is True and value['configuration_matches'] is True
                 and value['host_consumption_verified'] is False and value['effective_configuration_verified'] is False,'status_scope')
            need((value['format'],value['write_enabled'])==settings[project],'status_settings');states+=1;continue
        need(action in actions and isinstance(value,dict),'plan_action')
        applying=action in ('install','uninstall','recover','reconcile')
        need(set(value)==PLAN_FIELDS|({'applied'} if applying else set()),'plan_fields')
        need(value['schema']=='qbrain-opencode-plan-v1' and value['operation']==actions[action],'plan_identity')
        need(identifier(value['plan_sha256']) and isinstance(value['server_name'],str) and value['server_name'].startswith('qbrain_') and identifier(value['server_name'][7:],24),'plan_ids')
        need(value['configuration_file']=='opencode.jsonc' and type(value['would_change']) is bool and value['host_consumption_verified'] is False
             and type(value['model_calls']) is int and value['model_calls']==0,'plan_scope')
        if applying:
            need(value['applied'] is True and '--approve-sha256' in args and value['plan_sha256']==args[args.index('--approve-sha256')+1],'approval')
        if actions[action]=='install':
            major={'v1':1,'v2':2}[args[args.index('--format')+1]];write='--allow-write' in args
            need(type(value['format']) is int and value['format']==major and value['write_enabled'] is write,'install_settings')
            if applying:settings[project]=(major,write)
        elif actions[action]=='reconcile':
            major,write=settings[project]
            need(type(value['format']) is int and value['format']==major and value['write_enabled'] is write,'reconcile_cannot_change_settings')
        else:need(value['format'] is None and value['write_enabled'] is None,'unobserved_settings')
        plans+=1
    need(sha(compact(pattern))==CALLS_SHA,'ordered_call_outcomes')
    need((plans,errors,audits,states)==(84,64,4,12),'semantic_coverage')
    return {'result':'RECONCILIATION_EVIDENCE_VERIFIED','checks':133,'calls':164,'plans':plans,'expected_errors':errors,
            'audit_results':audits,'status_results':states,'binary_sha256':sha(binary),'new_product_execution':False,'host_started':False}

def negatives(report,binary,script):
    results=[]
    for label in ('bool-count','missing-check','changed-check','wrong-binary','wrong-script','host-claim','missing-call','bool-exit',
                  'private-output','permission-change','format-change','wrong-plan','approval-mismatch','unexpected-field','error-as-success','audit-permission-lie'):
        r=copy.deepcopy(report)
        if label=='bool-count':r['passed']=True
        if label=='missing-check':r['checks'].pop()
        if label=='changed-check':r['checks'][0]['name']='invented'
        if label=='wrong-binary':r['binary_sha256']='0'*64
        if label=='wrong-script':r['test_sha256']='0'*64
        if label=='host-claim':r['host_started']=True
        if label=='missing-call':r['calls'].pop()
        if label=='bool-exit':r['calls'][0]['exit']=False
        if label=='error-as-success':next(c for c in r['calls'] if c['exit'])['exit']=0
        c=next(c for c in r['calls'] if c['args'][1]=='reconcile' and c['exit']==0)
        if label=='audit-permission-lie':c=next(c for c in r['calls'] if c['args'][1]=='audit')
        body=decode(c['stdout'].encode())
        if label=='private-output':body['private']='DO-NOT-OUTPUT'
        if label=='permission-change':body['write_enabled']=not body['write_enabled']
        if label=='format-change':body['format']=2 if body['format']==1 else 1
        if label=='wrong-plan':body['operation']='install'
        if label=='approval-mismatch':body['plan_sha256']='0'*64
        if label=='unexpected-field':body['new_setting']=True
        if label=='audit-permission-lie':body['registered_write_enabled']=not body['registered_write_enabled']
        c['stdout']=json.dumps(body)+'\n'
        try:verify(r,binary,script)
        except (ValueError,KeyError,TypeError) as error:results.append({'case':label,'rejected':True,'reason':str(error)})
        else:raise ValueError('mutation accepted: '+label)
    verify(report,binary,script)
    return results

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('report','binary','test'):parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--negatives',action='store_true');a=parser.parse_args()
    r=decode(a.report.read_bytes());b=a.binary.read_bytes();s=a.test.read_bytes();result=verify(r,b,s)
    if a.negatives:result['negative_cases']=negatives(r,b,s)
    print(json.dumps(result,sort_keys=True))
