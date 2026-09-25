"""Offline source-bound stream-import record replay; no process/provider calls.

Verifies raw hashes, deterministic coverage, independent final-object partition and
Decimal costs. This is content consistency, not authentication of arbitrary reports.
"""
from __future__ import annotations
import argparse,copy,json,hashlib,re
from pathlib import Path
from test_stream_usage import check_output
from test_token_cost import verify_math

def need(ok,reason):
    if not ok:raise ValueError(reason)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def enc(x):return json.dumps(x,ensure_ascii=False,separators=(',',':')).encode()
def decode(raw):
    need(len(raw)<=8*1024*1024,'readback_bound')
    def unique(pairs):
        out={}
        for k,v in pairs:need(k not in out,'duplicate_key');out[k]=v
        return out
    def invalid(_):raise ValueError('nonfinite')
    return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique,parse_constant=invalid)

NAMES='d15796dca9b7396e5ef37942ca2403619fceba213328a8e15581c8ec8023658a'
def verify(directory:Path,binary:bytes,script:bytes,report=None,overrides=None):
    r=decode((directory/'report.json').read_bytes()) if report is None else report
    need(r['schema']=='qbrain-n48h-process-v1' and r['binary_sha256']==sha(binary) and r['script_sha256']==sha(script),'component_identity')
    need(type(r['passed']) is int and r['passed']==187 and type(r['failed']) is int and r['failed']==0 and r['failure'] is None,'execution')
    need(r['platform'] in ('nt','posix') and type(r['provider_requests_sent']) is int and r['provider_requests_sent']==0 and r['real_response_used'] is False,'scope')
    need(len(r['checks'])==187 and all(set(c)=={'name','passed'} and c['passed'] is True for c in r['checks']),'check_fields')
    need(sha(enc([c['name'] for c in r['checks']]))==NAMES,'ordered_coverage')
    need(type(r['commands']) is int and r['commands']==len(r['records'])==171,'record_count')
    count=0;imports=0;pipes=0;failed=0
    for i,row in enumerate(r['records']):
        need(set(row)=={'case','args','exit','hashes','expected','error'} and type(row['exit']) is int,'record_fields')
        raw={}
        for ext in ('stdin','stdout','stderr'):
            key=f'{i:04d}.{ext}';b=overrides[key] if overrides and key in overrides else (directory/'raw'/key).read_bytes()
            need(row['hashes'][ext]==sha(b),'raw_hash');raw[ext]=b;count+=1
        need(raw['stderr']==b'','stderr');value=decode(raw['stdout'])
        if row['error'] is not None:
            need(row['exit']==2 and set(value)=={'error'} and set(value['error'])=={'code'} and re.fullmatch('[a-z0-9_]+',value['error']['code']),'error_result')
            need(row['error']=='ANY' or value=={'error':{'code':row['error']}},'specific_error');failed+=1
        else:
            need(row['exit']==0,'success_exit');root=decode(raw['stdin'])
            if row['args']==['cost','report']:verify_math(root,value);pipes+=1
            else:
                need(row['args']==['cost','import-stream'],'actual_command')
                check_output(root,row['expected'],value);imports+=1
    return {'result':'STREAM_RECORDS_VERIFIED','checks':187,'commands':171,'raw_streams':count,'imports':imports,'pipes':pipes,'rejections':failed,
        'new_process_execution':False,'real_provider_response':False}

def negatives(directory,binary,script):
    original=decode((directory/'report.json').read_bytes());rejected=[]
    for kind in ('count-bool','wrong-binary','wrong-script','missing-record','reordered-checks','real-provider-claim','bool-exit',
                 'changed-token','false-usage-complete','false-stream-valid','copied-content','wrong-event-count','wrong-origin','raw-tamper','duplicate-json'):
        r=copy.deepcopy(original);overrides={}
        if kind=='count-bool':r['passed']=True
        if kind=='wrong-binary':r['binary_sha256']='0'*64
        if kind=='wrong-script':r['script_sha256']='0'*64
        if kind=='missing-record':r['records'].pop()
        if kind=='reordered-checks':r['checks'].reverse()
        if kind=='real-provider-claim':r['real_response_used']=True
        if kind=='bool-exit':r['records'][0]['exit']=False
        if kind=='raw-tamper':overrides['0000.stdout']=b'{}\n'
        if kind=='duplicate-json':
            try:decode(b'{"a":1,"a":2}')
            except ValueError:rejected.append(kind);continue
            raise ValueError('accepted duplicate JSON')
        if kind in ('changed-token','false-usage-complete','false-stream-valid','copied-content','wrong-event-count','wrong-origin'):
            b=(directory/'raw/0000.stdout').read_bytes();v=decode(b)
            if kind=='changed-token':v['cost_input']['calls'][0]['tokens']['output']+=1
            if kind=='false-usage-complete':v['usage_complete']=not v['usage_complete']
            if kind=='false-stream-valid':v['stream_contract_validated']=False
            if kind=='copied-content':v['raw_content']='PRIVATE_BODY'
            if kind=='wrong-event-count':v['stream_observations'][0]['data_events']+=1
            if kind=='wrong-origin':v['stream_observations'][0]['sequence_origin']=1
            raw=enc(v)+b'\n';overrides['0000.stdout']=raw;r['records'][0]['hashes']['stdout']=sha(raw)
        try:verify(directory,binary,script,r,overrides)
        except (ValueError,KeyError,TypeError,AssertionError):rejected.append(kind)
        else:raise ValueError('accepted mutation '+kind)
    verify(directory,binary,script);return rejected
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('directory','binary','test'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--negatives',action='store_true');a=p.parse_args();b=a.binary.read_bytes();s=a.test.read_bytes();r=verify(a.directory,b,s)
    if a.negatives:r['rejected_mutations']=negatives(a.directory,b,s)
    print(json.dumps(r,sort_keys=True))
