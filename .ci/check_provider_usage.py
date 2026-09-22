"""Offline replay of immutable N48G synthetic command streams, not authenticity.

Reuse the independent Python partition/Decimal reference, then enforce command
order, exact exit/output, source byte identity and positive/negative coverage.
"""
from __future__ import annotations
import argparse,copy,json,re
from pathlib import Path
from test_provider_usage import check_output,sha

def need(ok,why):
    if not ok:raise ValueError(why)
def decode(raw):
    def pairs(items):
        result={}
        for k,v in items:need(k not in result,'duplicate_key');result[k]=v
        return result
    def invalid(_):raise ValueError('nonfinite')
    return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=invalid)
def verify(directory,binary,script):
    r=decode((directory/'report.json').read_bytes())
    need(set(r)=={'schema','binary_sha256','script_sha256','checks','records','commands','passed','failure','provider_requests_sent','real_provider_responses_verified'},'report_fields')
    need(r['schema']=='qbrain-n48g-process-v1' and r['binary_sha256']==sha(binary) and r['script_sha256']==sha(script),'identity')
    need(type(r['passed']) is int and r['passed']==231 and r['failure'] is None,'result')
    need(type(r['commands']) is int and r['commands']==230 and len(r['records'])==230,'command_coverage')
    need(type(r['provider_requests_sent']) is int and r['provider_requests_sent']==0 and r['real_provider_responses_verified'] is False,'scope')
    need(len(r['checks'])==231 and all(set(c)=={'name','passed'} and isinstance(c['name'],str) and c['passed'] is True for c in r['checks']),'checks')
    need(sha(json.dumps([c['name'] for c in r['checks']],separators=(',',':')).encode())=='5c838340b106f313e5c3202c6d4dceb6f29e48dc417c662c85b90ab3befbbbbe','ordered_checks')
    success=0;rejected=0;pipe=0;files=set()
    for index,rec in enumerate(r['records']):
        need(set(rec)=={'args','exit','expected_error','files'} and type(rec['exit']) is int,'command_fields')
        streams={}
        for ext in ('stdin','stdout','stderr'):
            info=rec['files'][ext];need(set(info)=={'name','sha256','bytes'} and info['name']==f'{index:04d}.{ext}','stream_name')
            data=(directory/'raw'/info['name']).read_bytes();files.add(info['name'])
            need(type(info['bytes']) is int and info['bytes']==len(data) and sha(data)==info['sha256'],'stream_bytes');streams[ext]=data
        need(streams['stderr']==b'','stderr')
        out=decode(streams['stdout']);err=rec['expected_error']
        if err is not None:
            need(isinstance(err,str) and re.fullmatch('(cost|usage)_[a-z_]+',err) and rec['exit']==2 and out=={'error':{'code':err}},'expected_error');rejected+=1
        elif rec['args']==['cost','report']:
            from test_token_cost import verify_math
            need(rec['exit']==0,'pipe_exit');verify_math(decode(streams['stdin']),out);pipe+=1
        else:
            need(rec['args']==['cost','import'] and rec['exit']==0,'success_command')
            check_output(decode(streams['stdin']),out);success+=1
    need({p.name for p in (directory/'raw').iterdir()}==files,'unexpected_or_missing_raw')
    need(success==176 and rejected==51 and pipe==3,'outcome_coverage')
    return {'result':'PROVIDER_USAGE_STREAMS_VERIFIED','checks':231,'commands':230,'raw_streams':690,
        'successful_imports':success,'rejections':rejected,'cost_pipelines':pipe,'new_execution':False,'provider_requests_sent':0}
def negative_outputs(directory):
    r=decode((directory/'report.json').read_bytes());i=next(i for i,x in enumerate(r['records']) if x['exit']==0 and x['args']==['cost','import'])
    raw=directory/'raw';request=decode((raw/f'{i:04d}.stdin').read_bytes());base=decode((raw/f'{i:04d}.stdout').read_bytes());checked=[]
    for label in ('cached-double-count','write-zero','reasoning-add','free-failed-call','wrong-total','false-authentication','leaked-body','wrong-reference','wrong-format','wrong-hash','missing-bucket','complete-lie'):
        out=copy.deepcopy(base)
        if label=='cached-double-count':out['cost_input']['calls'][0]['tokens']['input_uncached']=100
        if label=='write-zero':out['cost_input']['calls'][0]['tokens']['input_cache_write']=0
        if label=='reasoning-add':out['cost_input']['calls'][0]['tokens']['output']+=40
        if label=='free-failed-call':out['cost_report']['calls'][0]['known_subtotal']='0.000000000000'
        if label=='wrong-total':out['cost_report']['summary']['total_estimate']='0.000000000000'
        if label=='false-authentication':out['source_authenticated']=True
        if label=='leaked-body':out['raw_content']='PRIVATE_BODY_SENTINEL'
        if label=='wrong-reference':out['mapping'][0]['response_reference_sha256']='0'*64
        if label=='wrong-format':out['mapping'][0]['format']='anthropic_messages'
        if label=='wrong-hash':out['normalization_sha256']='0'*64
        if label=='missing-bucket':out['cost_input']['calls'][0]['tokens'].pop('output')
        if label=='complete-lie':out['usage_complete']=False
        try:check_output(request,out)
        except (ValueError,KeyError,TypeError):checked.append(label)
        else:raise ValueError('accepted mutation '+label)
    check_output(request,base);return checked
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('directory','binary','test'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--negatives',action='store_true');a=p.parse_args();out=verify(a.directory,a.binary.read_bytes(),a.test.read_bytes())
    if a.negatives:out['rejected_mutations']=negative_outputs(a.directory)
    print(json.dumps(out,sort_keys=True))
