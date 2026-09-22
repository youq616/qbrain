"""Replay fixed N48F raw evidence and the independent Decimal reference.

Evidence consistency only; supplied usage is not authenticated provider billing.
"""
import argparse,copy,hashlib,json,re
from pathlib import Path
from test_token_cost import verify_math


def need(ok,code):
    if not ok:raise ValueError(code)
def sha(data):return hashlib.sha256(data).hexdigest()
def decode(data):
    need(len(data)<=2097152,'record_bound')
    def pairs(items):
        out={}
        for k,v in items:need(k not in out,'duplicate_key');out[k]=v
        return out
    def invalid(_):raise ValueError('nonfinite')
    return json.loads(data.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=invalid)


def verify(directory,binary,script):
    r=decode((directory/'report.json').read_bytes())
    need(r['schema']=='qbrain-n48f-process-v1' and r['binary_sha256']==sha(binary) and r['script_sha256']==sha(script),'component_identity')
    need(type(r['passed']) is int and r['passed']==149 and type(r['failed']) is int and r['failed']==0 and r['failure'] is None,'test_outcome')
    need(r['provider_calls']==0 and type(r['provider_calls']) is int and r['real_billing_verified'] is False,'scope')
    checks=r['checks'];need(len(checks)==149 and all(set(c)=={'name','passed'} and c['passed'] is True for c in checks),'checks')
    # Sequence is fixed from the reviewed test, not trusted from the report count.
    need(sha(json.dumps([c['name'] for c in checks],ensure_ascii=False,separators=(',',':')).encode())==CHECK_NAMES_SHA,'coverage')
    need(type(r['commands']) is int and r['commands']==len(r['records'])==148,'commands')
    positives=0;negatives=0
    for i,row in enumerate(r['records']):
        need(set(row)=={'index','argv','exit','stdin_sha256','stdout_sha256','stderr_sha256'} and type(row['index']) is int and row['index']==i,'record_identity')
        streams={}
        for label in ('stdin','stdout','stderr'):
            path=directory/'raw'/f'{i:04d}.{label}'
            need(path.is_file() and not path.is_symlink(),'raw_file')
            data=path.read_bytes();need(sha(data)==row[label+'_sha256'],'raw_digest');streams[label]=data
        need(streams['stderr']==b'' and type(row['exit']) is int and row['exit'] in (0,2),'command_outcome')
        out=decode(streams['stdout'])
        if row['exit']==0:
            need(row['argv']==['cost','report'],'positive_command')
            verify_math(decode(streams['stdin']),out);positives+=1
        else:
            need(set(out)=={'error'} and set(out['error'])=={'code'} and re.fullmatch('cost_[a-z_]+',out['error']['code']),'fixed_error')
            negatives+=1
    need(positives==92 and negatives==56,'positive_negative_coverage')
    need(len(list((directory/'raw').iterdir()))==444,'raw_coverage')
    return {'result':'COST_EVIDENCE_VERIFIED','checks':149,'commands':148,'raw_files':444,
        'decimal_reference_successes':positives,'refusals':negatives,'new_execution':False,'billing_verified':False}


def mutations(directory,binary,script):
    # In-memory arithmetic mutations use an actual successful result. Raw hashes
    # separately protect disk records. Do not rewrite original evidence in place.
    r=decode((directory/'report.json').read_bytes());row=next(x for x in r['records'] if x['exit']==0)
    prefix=directory/'raw'/f'{row["index"]:04d}'
    inp=decode(Path(str(prefix)+'.stdin').read_bytes());original=decode(Path(str(prefix)+'.stdout').read_bytes());cases=[]
    for name in ('total','subtotal','component','hidden-gap','fake-billing','fake-observation','fee-claim','stage-total','retry-count','unknown-token','currency','input-hash'):
        bad=copy.deepcopy(original)
        if name=='total':bad['summary']['total_estimate']='0.000000000000'
        if name=='subtotal':bad['summary']['known_subtotal']='1.000000000000'
        if name=='component':bad['calls'][0]['components']['output']['cost']='99.000000000000'
        if name=='hidden-gap':bad['calls'][0]['unknown_components']=1
        if name=='fake-billing':bad['billing_verified']=True
        if name=='fake-observation':bad['all_provider_calls_observed']=True
        if name=='fee-claim':bad['fees_taxes_discounts_included']=True
        if name=='stage-total':bad['by_stage'][0]['total_estimate']='1.000000000000'
        if name=='retry-count':bad['summary']['retry_calls']=1
        if name=='unknown-token':bad['summary']['tokens']['output']['total_tokens']=None
        if name=='currency':bad['currency']='EUR'
        if name=='input-hash':bad['input_sha256']='0'*64
        try:verify_math(inp,bad)
        except (ValueError,KeyError,TypeError):cases.append(name)
        else:raise ValueError('accepted mutation '+name)
    verify_math(inp,original);verify(directory,binary,script);return cases

# Filled from the named, reviewed test's first successful execution.
CHECK_NAMES_SHA='2949658dce1496c4eb0d2dc9592f989173f65f5e8f2493443e166d28668b2d6c'
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('directory','binary','test'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--negatives',action='store_true');a=p.parse_args()
    b=a.binary.read_bytes();s=a.test.read_bytes();result=verify(a.directory,b,s)
    if a.negatives:result['rejected_mutations']=mutations(a.directory,b,s)
    print(json.dumps(result,sort_keys=True))
