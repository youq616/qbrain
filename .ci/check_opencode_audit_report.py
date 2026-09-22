"""N48B strict raw-report replay, no process launch or authenticity assertion.

Uses the source-owned primitive output contract, then independently reconciles
reported outcomes with options, failed checks and actual command exit statuses.
"""
from __future__ import annotations
import argparse,copy,hashlib,json
from pathlib import Path
from test_opencode_audit import validate, CHECKS


def need(ok,why):
    if not ok:raise ValueError(why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def decode(raw):
    need(len(raw)<=2*1024*1024,'record_bound')
    def pairs(rows):
        out={}
        for k,v in rows:
            need(k not in out,'duplicate_json_key');out[k]=v
        return out
    def nonfinite(_):raise ValueError('nonfinite_json')
    return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=nonfinite)


def output(value):
    validate(value)
    checks={x['check']:x['passed'] for x in value['checks']}
    format=value['registered_format'];write=value['registered_write_enabled']
    for field,actual,test in [('expected_format',format,'expected_format_matches'),
                              ('expected_write_enabled',write,'expected_access_matches')]:
        if value[field] is None or actual is None:need(checks[test] is None,'unobserved_expectation')
        else:need(checks[test] is (actual==value[field]),'inconsistent_expectation')
    if checks['ownership_valid'] is not True:need(format is None and write is None,'unvalidated_owner_details')
    else:need(format in (1,2) and type(write) is bool,'missing_owner_details')
    if checks['executable_exists'] is not True:
        need(checks['executable_matches'] is None and checks['executable_eligible'] is None,'missing_binary_details')
    if value['result']=='NOT_REGISTERED':
        need(checks['owned_registration_present'] is False and checks['no_pending_recovery'] is True
             and checks['observations_stable'] is True,'false_absence')
    if value['result']=='BLOCKED':
        need(checks['observations_stable'] is True and any(v is False for v in checks.values()),'unexplained_block')
    if value['result']=='UNVERIFIABLE':need(checks['paths_readable'] is False or checks['observations_stable'] is not True,'unexplained_unknown')
    return value['result']


def verify(r,binary,script):
    need(isinstance(r,dict) and set(r)=={'schema','binary_sha256','script_sha256','checks','records','passed','failed','failure','commands','platform','opencode_started','model_calls'},'report_fields')
    need(r['schema']=='qbrain-n48b-process-v1' and r['binary_sha256']==sha(binary) and r['script_sha256']==sha(script),'identity')
    need(r['platform'] in ('posix','nt'),'platform')
    expected=96 if r['platform']=='posix' else 93
    need(type(r['passed']) is int and r['passed']==expected and type(r['failed']) is int and r['failed']==0 and r['failure'] is None,'execution_result')
    need(r['opencode_started'] is False and type(r['model_calls']) is int and r['model_calls']==0,'scope')
    rows=r['checks'];need(isinstance(rows,list) and len(rows)==expected and all(isinstance(x,dict) and set(x)=={'name','passed'} and isinstance(x['name'],str) and x['passed'] is True for x in rows),'checks')
    names=[x['name'] for x in rows]
    need(len(names)==expected and names[-1]=='original JSONC remains exact after entire sequence','check_coverage')
    commands=r['records'];need(type(r['commands']) is int and r['commands']==len(commands)==(47 if r['platform']=='posix' else 46),'commands')
    audit_count=0;invalid_count=0;success=0;seen=set()
    for record in commands:
        need(isinstance(record,dict) and set(record)=={'args','exit','stdout','stderr'} and type(record['exit']) is int and record['stderr']=='','command_shape')
        args=record['args'];need(isinstance(args,list) and args and all(isinstance(x,str) for x in args),'args')
        value=decode(record['stdout'].encode())
        if args[0]!='audit':need(record['exit']==0,'legacy_command_failure');continue
        audit_count+=1
        if record['exit']==2:
            need(value=={'error':{'code':'opencode_audit_invalid_request'}},'invalid_arguments_result');invalid_count+=1;continue
        state=output(value);seen.add(state)
        need(record['exit']==(0 if state=='LOCAL_REGISTRATION_CHECKS_PASSED' else 1),'audit_exit')
        success+=record['exit']==0
        options=dict(zip(args[1::2],args[2::2]));need(len(options)*2==len(args)-1 and '--project' in options,'valid_options')
        need(value['expected_format']==({'v1':1,'v2':2}[options['--expect-format']] if '--expect-format' in options else None),'request_format')
        need(value['expected_write_enabled'] is ({'read-only':False,'read-write':True}[options['--expect-access']] if '--expect-access' in options else None),'request_access')
    need(audit_count==(36 if r['platform']=='posix' else 35) and invalid_count==8 and success==5,'audit_coverage')
    need(seen=={'BLOCKED','NOT_REGISTERED','LOCAL_REGISTRATION_CHECKS_PASSED'},'result_coverage')
    return {'result':'AUDIT_EVIDENCE_VERIFIED','checks':expected,'commands':len(commands),
        'audit_requests':audit_count,'healthy_audits':success,'binary_sha256':sha(binary),
        'new_product_execution':False,'opencode_started':False}


def negatives(r,binary,script):
    tested=[]
    for name in ('count','duplicate-key','false-host','wrong-binary','check-missing','exit-bool',
                 'raw-output-field','expected-version-lie','expected-access-lie','false-absence',
                 'unexpected-write','success-exit-failure','missing-raw-call','unobserved-format'):
        bad=copy.deepcopy(r)
        if name=='duplicate-key':
            try:decode(b'{"result":1,"result":2}')
            except ValueError:tested.append(name);continue
            raise ValueError('duplicate key accepted')
        if name=='count':bad['passed']=True
        if name=='false-host':bad['opencode_started']=True
        if name=='wrong-binary':bad['binary_sha256']='0'*64
        if name=='check-missing':bad['checks'].pop()
        if name=='exit-bool':bad['records'][0]['exit']=False
        if name=='missing-raw-call':bad['records'].pop()
        candidates=[x for x in bad['records'] if x['args'][0]=='audit' and x['exit']==0 and '--expect-format' in x['args']]
        record=candidates[0];v=decode(record['stdout'].encode())
        if name=='raw-output-field':v['secret']='not-allowed'
        if name=='expected-version-lie':v['registered_format']=2 if v['registered_format']==1 else 1
        if name=='expected-access-lie':v['registered_write_enabled']=not v['registered_write_enabled']
        if name=='false-absence':v['result']='NOT_REGISTERED';v['registered_bytes_verified']=False;record['exit']=1
        if name=='unexpected-write':v['read_only']=False
        if name=='success-exit-failure':record['exit']=1
        if name=='unobserved-format':v['registered_format']=None
        record['stdout']=json.dumps(v)
        try:verify(bad,binary,script)
        except (ValueError,KeyError,TypeError):tested.append(name)
        else:raise ValueError('accepted mutation '+name)
    verify(r,binary,script);return tested

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('report','binary','test'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--negatives',action='store_true');a=p.parse_args()
    r=decode(a.report.read_bytes());b=a.binary.read_bytes();s=a.test.read_bytes();result=verify(r,b,s)
    if a.negatives:result['negative_cases']=negatives(r,b,s)
    print(json.dumps(result,sort_keys=True))
