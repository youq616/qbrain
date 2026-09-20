"""Read back local/CI synthetic batch evidence; not a new product execution."""
from __future__ import annotations
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re

NAMES_SHA='40e1b13015b1a44ef8b9d3e077b3ec6fc23a53abb6ecb81cc56c76cd075466d6'
def need(ok,why):
    if not ok:raise ValueError(why)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(p,cap=2*1024*1024):
    need(p.is_file() and not p.is_symlink(),'regular_file')
    with p.open('rb') as f:raw=f.read(cap+1)
    need(len(raw)<=cap,'byte_limit');return raw
def decode(raw):
    def pairs(values):
        obj={}
        for k,v in values:
            need(k not in obj,'duplicate_key');obj[k]=v
        return obj
    def bad(_):raise ValueError('nonfinite')
    return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=bad)
def batch(value):
    need(isinstance(value,dict) and set(value)=={'view','operation','source_id','applied','atomic','snapshot','changed','would_change',
        'unchanged','items','origin','host_consumption_verified','fact_truth_verified','provider_calls'},'batch_fields')
    need(value['view']=='usage_batch' and value['operation'] in ('report','revoke'),'operation')
    need(value['origin']=='caller_reported' and value['host_consumption_verified'] is False and value['fact_truth_verified'] is False
        and type(value['provider_calls']) is int and value['provider_calls']==0,'scope')
    need(type(value['applied']) is bool and value['atomic'] is True,'atomic')
    need(isinstance(value['snapshot'],str) and re.fullmatch('[0-9a-f]{64}',value['snapshot']),'snapshot')
    items=value['items'];need(isinstance(items,list) and 1<=len(items)<=32,'items')
    ids=[];changed=0
    for item in items:
        need(isinstance(item,dict) and set(item)=={'fact_id','usage_id','fact_revision','action','will_change','reported_at','withdrawn_at'},'item_fields')
        for k in ('fact_id','usage_id'):need(isinstance(item[k],str) and re.fullmatch('[0-9a-f]{64}',item[k]),'identifier')
        ids.append(item['usage_id']);need(type(item['fact_revision']) is int and 1<=item['fact_revision']<2**31,'revision')
        actions=('report','already_reported') if value['operation']=='report' else ('revoke','already_withdrawn')
        need(item['action'] in actions and type(item['will_change']) is bool and item['will_change']==(item['action']==actions[0]),'effect')
        changed+=item['will_change']
        for k in ('reported_at','withdrawn_at'):need(item[k] is None or type(item[k]) is int and item[k]>=0,'time')
        if value['applied'] or item['action']!='report':need(type(item['reported_at']) is int,'report_time')
        if item['action']=='already_withdrawn' or value['applied'] and value['operation']=='revoke':
            need(type(item['withdrawn_at']) is int and item['withdrawn_at']>=item['reported_at'],'withdrawal_time')
    need(ids==sorted(ids) and len(ids)==len(set(ids)),'order')
    for k in ('changed','would_change','unchanged'):need(type(value[k]) is int,'count_type')
    need(value['would_change']==changed and value['unchanged']==len(items)-changed
        and value['changed']==(changed if value['applied'] else 0),'counts')
    return value

def verify(r,directory,binary,script):
    need(r.get('schema')=='qbrain-n47z-batch-tests-v1','schema')
    need(type(r.get('passed')) is int and r['passed']==89 and type(r.get('failed')) is int and r['failed']==0 and r.get('failure') is None,'result')
    need(r.get('binary_sha256')==sha(binary) and r.get('script_sha256')==sha(script),'identity')
    need(r.get('real_client_verified') is False and type(r.get('provider_calls')) is int and r['provider_calls']==0,'scope')
    checks=r.get('checks');need(isinstance(checks,list) and len(checks)==89 and
        all(set(c)=={'name','passed'} and c['passed'] is True for c in checks),'checks')
    need(sha(json.dumps([c['name'] for c in checks],ensure_ascii=False,separators=(',',':')).encode())==NAMES_SHA,'names')
    records=r.get('commands');need(isinstance(records,list) and len(records)==165 and type(r.get('command_count')) is int and r['command_count']==165,'record_count')
    rawdir=directory/'raw';need(rawdir.is_dir() and not rawdir.is_symlink(),'raw_directory')
    expected={f'{i:04}.{suffix}' for i in range(1,166) for suffix in ('request','response','stderr')}
    need({p.name for p in rawdir.iterdir()}==expected,'raw_coverage')
    output_count=0
    for i,row in enumerate(records,1):
        need(set(row)=={'index','kind','exit','request_sha256','response_sha256','stderr_sha256'} and type(row['index']) is int and row['index']==i,'record')
        need(row['kind'] in ('cli','mcp') and type(row['exit']) is int and row['exit'] in (0,1),'exit')
        raw={}
        for k in ('request','response','stderr'):
            raw[k]=read(rawdir/f'{i:04}.{k}');need(sha(raw[k])==row[k+'_sha256'],'stream_identity')
        request=decode(raw['request'])
        if row['kind']=='cli':
            need(raw['stderr']==b'','stderr')
            if request['argv'][0] in ('init','config'):
                need(row['exit']==0,'setup_exit');continue
            value=decode(raw['response'])
            if row['exit']==1:need('error' in value,'expected_rejection');continue
            if value.get('view')=='usage_batch':
                need(len(raw['response'])<=16384,'output_byte_cap');batch(value);output_count+=1
        else:
            reply=decode(raw['response']);need(reply.get('jsonrpc')=='2.0' and type(reply.get('id')) is int and reply['id']==request['id'],'rpc_identity')
            if request['method']!='tools/call':continue
            result=reply['result'];need(type(result.get('isError')) is bool,'rpc_shape')
            body=decode(result['content'][-1]['text'].encode())
            if result['isError']:need('error' in body,'rpc_error')
            elif body.get('view')=='usage_batch':batch(body);output_count+=1
    need(Counter(x['exit'] for x in records)=={0:115,1:50},'exit_coverage')
    need(Counter(x['kind'] for x in records)=={'cli':149,'mcp':16},'route_coverage')
    return {'result':'LOCAL_BATCH_EVIDENCE_VERIFIED','checks':89,'commands':165,'raw_streams':495,
        'successful_batch_responses':output_count,'new_product_execution':False,'real_client_verified':False}

def negatives(r,directory,binary,script):
    out=[]
    for label in ('bool_count','bad_count','missing_check','duplicate_check','false_check','wrong_binary','wrong_script',
                  'false_client','wrong_index','wrong_exit','wrong_stream','missing_record'):
        bad=copy.deepcopy(r)
        if label=='bool_count':bad['passed']=True
        if label=='bad_count':bad['passed']=90
        if label=='missing_check':bad['checks'].pop()
        if label=='duplicate_check':bad['checks'][-1]=bad['checks'][0]
        if label=='false_check':bad['checks'][0]['passed']=False
        if label=='wrong_binary':bad['binary_sha256']='0'*64
        if label=='wrong_script':bad['script_sha256']='0'*64
        if label=='false_client':bad['real_client_verified']=True
        if label=='wrong_index':bad['commands'][0]['index']=True
        if label=='wrong_exit':bad['commands'][0]['exit']=2
        if label=='wrong_stream':bad['commands'][0]['response_sha256']='0'*64
        if label=='missing_record':bad['commands'].pop()
        try:verify(bad,directory,binary,script)
        except ValueError as e:out.append({'case':label,'rejected':True,'reason':str(e)})
        else:raise ValueError('accepted mutation '+label)
    verify(r,directory,binary,script);return out

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('directory','binary','test'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--negatives',action='store_true');a=p.parse_args()
    r=decode(read(a.directory/'report.json'));binary=read(a.binary,32*1024*1024);script=read(a.test)
    result=verify(r,a.directory,binary,script)
    if a.negatives:result['negative_tests']=negatives(r,a.directory,binary,script)
    print(json.dumps(result,sort_keys=True))
