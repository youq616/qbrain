"""Check N47U results against exact binary/test bytes and all saved raw streams.
Local consistency only; source/run authenticity is established separately.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re

NAMES_SHA='923f49f47eab87091a85bb69dac83a22a0b480bc37335f8b1942b9114465108f'


def need(ok,why):
    if not ok: raise ValueError(why)
def sha(raw): return hashlib.sha256(raw).hexdigest()
def decode(raw):
    def unique(pairs):
        d={}
        for k,v in pairs:
            need(k not in d,'duplicate_json_key');d[k]=v
        return d
    def nonfinite(_): raise ValueError('nonfinite_json')
    return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique,parse_constant=nonfinite)
def hex64(s): return isinstance(s,str) and re.fullmatch('[0-9a-f]{64}',s) is not None


def validate(report,binary,test,raw_dir):
    need(isinstance(report,dict) and report.get('schema')=='qbrain-n47u-process-v1','schema')
    need(type(report.get('passed')) is int and report['passed']==71 and type(report.get('failed')) is int and report['failed']==0,'result')
    need(report.get('real_client_tested') is False and type(report.get('provider_calls')) is int and report['provider_calls']==0,'scope')
    need(report.get('binary_sha256')==sha(binary) and report.get('test_sha256')==sha(test),'byte_identity')
    checks=report.get('checks')
    need(isinstance(checks,list) and len(checks)==71 and all(isinstance(r,dict) and r.get('passed') is True for r in checks),'checks')
    names=json.dumps([r.get('name') for r in checks],ensure_ascii=False,separators=(',',':')).encode()
    need(sha(names)==NAMES_SHA,'check_coverage')
    commands=report.get('commands')
    need(isinstance(commands,list) and len(commands)==111 and type(report.get('command_count')) is int and report['command_count']==111,'command_coverage')
    expected_files={f'{i:04}.{s}' for i in range(1,112) for s in ('stdin','stdout','stderr')}
    need({p.name for p in raw_dir.iterdir()}==expected_files,'raw_file_coverage')
    pages=0
    for index,row in enumerate(commands,1):
        need(isinstance(row,dict) and type(row.get('index')) is int and row['index']==index,'command_index')
        argv=row.get('argv')
        need(isinstance(argv,list) and all(isinstance(x,str) for x in argv) and bool(argv),'argv')
        need(type(row.get('exit')) is int and type(row.get('expected_exit')) is int and row['exit']==row['expected_exit'] and row['exit'] in (0,1),'command_exit')
        streams={s:(raw_dir/f'{index:04}.{s}').read_bytes() for s in ('stdin','stdout','stderr')}
        need(all(row.get(s+'_sha256')==sha(raw) for s,raw in streams.items()),'stream_hash')
        need(type(row.get('stdout_bytes')) is int and row['stdout_bytes']==len(streams['stdout']),'output_bytes')
        if argv[:1]==['serve']:
            expected_stderr=b'[qbrain-serve] stdio MCP ready brain=pages write=disabled\n[qbrain-serve] shutdown: stdin EOF\n'
            need(streams['stderr'].replace(b'\r\n',b'\n')==expected_stderr,'unexpected_mcp_stderr')
        else:
            need(streams['stderr']==b'','unexpected_stderr')
        if argv[:2]!=['fact','usage-list']: continue
        value=decode(streams['stdout'])
        if row['exit']:
            need(isinstance(value,dict) and set(value)=={'error'} and isinstance(value['error'].get('code'),str),'rejection_shape')
            continue
        options=dict(zip(argv[2::2],argv[3::2]))
        need(len(argv)%2==0,'option_positions')
        need(len(streams['stdout'])<=int(options.get('--max-bytes',8192)),'output_budget')
        need(value.get('view')=='usage_receipts' and value.get('source_id')==options['--source'] and value.get('fact_id')==options['--id'],'page_scope')
        need(value.get('origin')=='caller_reported' and value.get('host_consumption_verified') is False and value.get('fact_truth_verified') is False and value.get('provider_calls')==0,'page_claims')
        need(type(value.get('fact_revision')) is int and value['fact_revision']>=1 and hex64(value.get('snapshot')),'page_identity')
        need(type(value.get('has_more')) is bool and type(value.get('initialized')) is bool and type(value.get('archived')) is bool,'page_flags')
        need(type(value.get('matched_receipts')) is int and 0<=value['matched_receipts']<=4096,'matched_count')
        state=options.get('--state','all');need(value.get('receipt_state')==state,'page_filter')
        items=value.get('items')
        need(isinstance(items,list) and len(items)<=int(options.get('--limit',10)) and len(items)<=value['matched_receipts'],'page_items')
        ids=[]
        for r in items:
            need(isinstance(r,dict) and set(r)=={'usage_id','fact_revision','reported_at','withdrawn_at','state'},'row_fields')
            need(hex64(r['usage_id']) and type(r['fact_revision']) is int and 1<=r['fact_revision']<=value['fact_revision'],'row_identity')
            need(type(r['reported_at']) is int and r['reported_at']>=0,'row_time')
            withdrawn=r['withdrawn_at']
            need(withdrawn is None or type(withdrawn) is int and withdrawn>=r['reported_at'],'row_withdrawal')
            wanted='withdrawn' if withdrawn is not None else 'current' if r['fact_revision']==value['fact_revision'] else 'historical'
            need(r['state']==wanted and (state=='all' or state==wanted),'row_filter')
            ids.append(r['usage_id'])
        need(ids==sorted(set(ids)) and all(x>options.get('--after-id','') for x in ids),'row_order')
        need(value.get('next_after_id')==(ids[-1] if value['has_more'] and ids else None),'next_cursor')
        need(not value['has_more'] or bool(ids),'cursor_progress')
        if '--snapshot' in options: need(value['snapshot']==options['--snapshot'],'continued_snapshot')
        pages+=1
    return {'result':'USAGE_PAGES_EVIDENCE_VERIFIED','checks':71,'commands':111,'raw_streams':333,
            'pages_checked':pages,'binary_sha256':sha(binary),'test_sha256':sha(test),
            'new_product_execution':False,'external_consumption_verified':False}


def negatives(report,binary,test,raw):
    rejected=[]
    for fault in ('count','boolean_count','scope','binary','test','missing_check','duplicate_check','false_check',
                  'missing_command','wrong_index','wrong_exit','boolean_exit','stream_hash','byte_count'):
        r=copy.deepcopy(report)
        if fault=='count':r['passed']=70
        if fault=='boolean_count':r['failed']=False
        if fault=='scope':r['real_client_tested']=True
        if fault=='binary':r['binary_sha256']='0'*64
        if fault=='test':r['test_sha256']='0'*64
        if fault=='missing_check':r['checks'].pop()
        if fault=='duplicate_check':r['checks'][-1]=r['checks'][0]
        if fault=='false_check':r['checks'][0]['passed']=False
        if fault=='missing_command':r['commands'].pop()
        if fault=='wrong_index':r['commands'][0]['index']=2
        if fault=='wrong_exit':r['commands'][0]['exit']=1
        if fault=='boolean_exit':r['commands'][0]['exit']=False
        if fault=='stream_hash':r['commands'][0]['stdout_sha256']='0'*64
        if fault=='byte_count':r['commands'][0]['stdout_bytes']+=1
        try:validate(r,binary,test,raw)
        except ValueError:rejected.append(fault)
        else:raise ValueError('mutation_accepted:'+fault)
    return {'negative_cases':len(rejected),'rejected':rejected}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('report','binary','test','raw-dir'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--negative-tests',action='store_true');a=p.parse_args()
    args=(decode(a.report.read_bytes()),a.binary.read_bytes(),a.test.read_bytes(),a.raw_dir)
    result=validate(*args)
    if a.negative_tests:result['negative_tests']=negatives(*args)
    print(json.dumps(result))
