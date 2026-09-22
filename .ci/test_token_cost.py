"""Actual cost CLI with independent Decimal reference and immutable raw streams.

Rates and all data are synthetic. No provider requests, real keys or user brain.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, os, random, subprocess, tempfile
from decimal import Decimal, localcontext
from pathlib import Path

BUCKETS=('input_uncached','input_cache_read','input_cache_write','output')
STAGES=('main','embedding','summary','extraction','rerank','other')

def require(ok, reason):
    if not ok: raise ValueError(reason)

def sha(raw): return hashlib.sha256(raw).hexdigest()
def encode(x): return json.dumps(x,ensure_ascii=False,separators=(',',':')).encode()
def four(value): return dict.fromkeys(BUCKETS,value)
def fixture():
    return {'schema':'qbrain-cost-input-v1','currency':'USD',
        'rates':[{'rate_id':'demo','provider':'synthetic','model':'example','per_million':four('2.5')}],
        'calls':[{'call_id':'one','stage':'main','rate_id':'demo','attempt':1,'outcome':'success','tokens':four(1)}]}

def reference(value):
    # Independent decimal math, not the C++ fixed-point algorithm or imports.
    with localcontext() as ctx:
        ctx.prec=60
        rates={r['rate_id']:r for r in value['rates']};rows=[]
        for c in sorted(value['calls'],key=lambda c:c['call_id']):
            r=rates.get(c['rate_id']);costs={};missing={}
            for b in BUCKETS:
                n=c['tokens'][b];p=r['per_million'][b] if r else None
                if n is None:costs[b]=None;missing[b]='usage_unknown'
                elif n==0:costs[b]=Decimal(0);missing[b]=None
                elif p is None:costs[b]=None;missing[b]='rate_unknown' if r else 'rate_card_missing'
                else:costs[b]=Decimal(n)*Decimal(p)/Decimal(1000000);missing[b]=None
            known=sum((v for v in costs.values() if v is not None),Decimal(0))
            rows.append((c,costs,missing,known))
        return rows

def verify_math(value,result):
    rows=reference(value)
    require(result['schema']=='qbrain-cost-report-v1', "decimal_reference_40")
    require(result['currency']==value['currency'] and result['decimal_places']==12, "decimal_reference_41")
    require(result['billing_verified'] is False and result['all_provider_calls_observed'] is False, "decimal_reference_42")
    require(result['provider_requests_sent']==0 and result['fees_taxes_discounts_included'] is False, "decimal_reference_43")
    require(result['currency_conversion_performed'] is False, "decimal_reference_44")
    require(len(result['calls'])==len(rows), "decimal_reference_45")
    for (c,costs,missing,known),out in zip(rows,result['calls']):
        require(all(out[k]==c[k] for k in ('call_id','stage','rate_id','attempt','outcome')), "decimal_reference_47")
        unknown=sum(x is None for x in costs.values())
        require(out['complete'] is (unknown==0) and out['unknown_components']==unknown, "decimal_reference_49")
        require(out['known_subtotal']==format(known,'.12f'), "decimal_reference_50")
        require(out['total_estimate']==(None if unknown else format(known,'.12f')), "decimal_reference_51")
        for b in BUCKETS:
            require(out['components'][b]['tokens']==c['tokens'][b], "decimal_reference_53")
            require(out['components'][b]['missing']==missing[b], "decimal_reference_54")
            require(out['components'][b]['cost']==(None if costs[b] is None else format(costs[b],'.12f')), "decimal_reference_55")
    def group(r,subset):
        known=sum((x[3] for x in subset),Decimal(0));unknown=sum(sum(v is None for v in x[1].values()) for x in subset)
        require(r['calls']==len(subset) and r['known_subtotal']==format(known,'.12f'), "decimal_reference_58")
        require(r['unknown_components']==unknown and r['complete'] is (unknown==0), "decimal_reference_59")
        require(r['total_estimate']==(None if unknown else format(known,'.12f')), "decimal_reference_60")
        require(r['failed_calls']==sum(x[0]['outcome']=='failure' for x in subset), "decimal_reference_61")
        require(r['unknown_outcome_calls']==sum(x[0]['outcome']=='unknown' for x in subset), "decimal_reference_62")
        require(r['retry_calls']==sum(x[0]['attempt']>1 for x in subset), "decimal_reference_63")
        for b in BUCKETS:
            counts=[x[0]['tokens'][b] for x in subset];n=sum(v for v in counts if v is not None);u=counts.count(None)
            require(r['tokens'][b]=={'known_tokens':n,'unknown_calls':u,'total_tokens':None if u else n}, "decimal_reference_66")
    group(result['summary'],rows)
    for field,key in [('by_stage','stage'),('by_rate','rate_id')]:
        groups=sorted({x[0][key] for x in rows})
        require([g[key] for g in result[field]]==groups, "decimal_reference_70")
        for g in result[field]:group(g,[x for x in rows if x[0][key]==g[key]])
    canonical=copy.deepcopy(value)
    canonical['rates'].sort(key=lambda r:r['rate_id']);canonical['calls'].sort(key=lambda r:r['call_id'])
    for r in canonical['rates']:
        r['per_million']={b:None if p is None else format(Decimal(p),'.6f') for b,p in r['per_million'].items()}
    expected=sha(json.dumps(canonical,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
    require(result['input_sha256']==expected, "decimal_reference_77")


def run(binary,output):
    output.mkdir(parents=True,exist_ok=False);rawdir=output/'raw';rawdir.mkdir()
    records=[];checks=[];failure=None
    def check(ok,name):
        checks.append({'name':name,'passed':bool(ok)})
        if not ok:raise ValueError(name)
    try:
      with tempfile.TemporaryDirectory(prefix='n48f-cost-') as t:
        root=Path(t);home=root/'fake-home';home.mkdir()
        (home/'keep.txt').write_text('SYNTHETIC_USER_DATA')
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN','OPENCODE'))}
        env.update(HOME=str(home),USERPROFILE=str(home),LOCALAPPDATA=str(home),APPDATA=str(home),
            QBRAIN_BRAIN='must-not-open',OPENAI_API_KEY='SYNTHETIC_UNREAD_KEY')
        def snap():return sorted((str(p.relative_to(home)),sha(p.read_bytes())) for p in home.rglob('*') if p.is_file()),sorted(str(p.relative_to(home)) for p in home.rglob('*') if p.is_dir())
        initial=snap()
        def call(value,code=0,error=None,args=None):
            inp=value if isinstance(value,bytes) else encode(value)
            argv=['cost','report'] if args is None else args
            p=subprocess.run([str(binary),*argv],input=inp,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,env=env,timeout=20)
            index=len(records);record={'index':index,'argv':argv,'exit':p.returncode}
            for key,data in [('stdin',inp),('stdout',p.stdout),('stderr',p.stderr)]:
                (rawdir/f'{index:04d}.{key}').write_bytes(data);record[key+'_sha256']=sha(data)
            records.append(record)
            if p.returncode!=code or p.stderr:raise ValueError('unexpected command status '+str(record))
            out=json.loads(p.stdout)
            if error is not None and out!={'error':{'code':error}}:raise ValueError('wrong error '+str(out))
            if len(p.stdout)>2097152:raise ValueError('response bound')
            if snap()!=initial:raise ValueError('user home changed')
            return out
        base=fixture();r=call(base);verify_math(base,r);check(r['summary']['total_estimate']=='0.000010000000','hand-calculated four bucket sum')
        j=fixture();j['calls'][0]['tokens']={'input_uncached':1000,'input_cache_read':800,'input_cache_write':200,'output':50}
        j['rates'][0]['per_million']={'input_uncached':'2','input_cache_read':'0.2','input_cache_write':'2.5','output':'10'}
        out=call(j);verify_math(j,out);check(out['summary']['total_estimate']=='0.003160000000','cache read/write are disjoint not double counted')
        for mode in ('null_tokens','null_rates','missing_card','all_zero','free_unknown','empty'):
            j=fixture()
            if mode=='null_tokens':j['calls'][0]['tokens']['output']=None
            if mode=='null_rates':j['rates'][0]['per_million']['output']=None
            if mode=='missing_card':j['rates']=[]
            if mode=='all_zero':j['calls'][0]['tokens']=four(0);j['rates']=[]
            if mode=='free_unknown':j['rates'][0]['per_million']=four('0');j['calls'][0]['tokens']=four(None)
            if mode=='empty':j['calls']=[];j['rates']=[]
            verify_math(j,call(j));check(True,'explicit missing/zero semantics '+mode)
        j=fixture();j['calls']=[{**j['calls'][0],'call_id':'c'+str(i),'stage':s,'attempt':i%3+1,'outcome':'failure' if i%2 else 'unknown'} for i,s in enumerate(STAGES)]
        out=call(j);verify_math(j,out);check(out['summary']['calls']==6 and out['summary']['retry_calls']==4,'all stages outcomes and retry attempts retained')
        j=fixture();j['rates'][0]['per_million']=four('0.000001');out=call(j)
        check(out['summary']['total_estimate']=='0.000000000004','smallest supported per-token amount remains exact')
        j=fixture();j['rates']=[]
        for i in range(64):j['rates'].append({'rate_id':'rate'+str(i),'provider':'synthetic','model':'tier'+str(i),'per_million':four('1.234567')})
        j['calls']=[{**base['calls'][0],'call_id':'call'+str(i),'rate_id':'rate'+str(i%64),'stage':STAGES[i%6],'tokens':four(17)} for i in range(512)]
        out=call(j);verify_math(j,out);check(out['summary']['calls']==512 and len(out['by_rate'])==64,'maximum calls and cards reconcile')
        limit_calls=copy.deepcopy(j);limit_calls['calls'].append({**base['calls'][0],'call_id':'extra'})
        call(limit_calls,2,'cost_call_count');check(True,'513 calls refused')
        limit_rates=copy.deepcopy(j);limit_rates['rates'].append({**j['rates'][0],'rate_id':'extra'})
        call(limit_rates,2,'cost_rate_count');check(True,'65 rate cards refused')
        raw=encode(base)
        check(call(raw+b' '*(262144-len(raw)))==r,'exact raw byte limit accepted')
        call(raw+b' '*(262145-len(raw)),2,'cost_input_limit');check(True,'one excess byte refused')
        # Independent deterministic matrix; random counts/prices cannot depend on product.
        rng=random.Random(48006)
        for case in range(40):
            j=fixture();j['currency']=('USD','EUR','CNY')[case%3]
            for b in BUCKETS:j['rates'][0]['per_million'][b]=None if rng.randrange(6)==0 else f'{rng.randrange(100)}.{rng.randrange(1000000):06d}'
            j['rates'].append({'rate_id':'other','provider':'demo','model':'cache-ttl','per_million':four('0.123456')})
            j['calls']=[]
            for i in range(1+case%23):
                j['calls'].append({'call_id':f'r{case}-{i}','stage':rng.choice(STAGES),'rate_id':rng.choice(['demo','other','absent']),
                    'attempt':rng.randrange(1,6),'outcome':rng.choice(['success','failure','unknown']),
                    'tokens':{b:rng.choice([None,0,rng.randrange(10000001)]) for b in BUCKETS}})
            out=call(j);verify_math(j,out);check(True,f'Decimal ledger exact case {case}')
            rng.shuffle(j['rates']);rng.shuffle(j['calls'])
            check(call(j)==out,f'canonical order invariant case {case}')
        negatives=[]
        for field in ('schema','currency','rates','calls'):
            j=fixture();del j[field];negatives.append(('missing-root-'+field,j,'cost_fields'))
        j=fixture();j['prompt']='SHOULD_NOT_ECHO';negatives.append(('extra-prompt',j,'cost_fields'))
        j=fixture();j['calls'][0]['response']='SHOULD_NOT_ECHO';negatives.append(('extra-response',j,'cost_fields'))
        for value in [True,1.0,-1,1000000001,'3',[],{}]:
            j=fixture();j['calls'][0]['tokens']['output']=value;negatives.append(('token-'+repr(value),j,'cost_quantity'))
        for value in [True,1.2,-2,'-1','1e3','01','1.','+1','.5','1.1234567','1\n']:
            j=fixture();j['rates'][0]['per_million']['output']=value;negatives.append(('price-'+repr(value),j,'cost_rate_decimal'))
        j=fixture();j['rates'][0]['per_million']['output']='1000000.000001';negatives.append(('price-too-high',j,'cost_rate_range'))
        for value in [True,'usd','US','USDD','美金']:
            j=fixture();j['currency']=value;negatives.append(('currency-'+repr(value),j,'cost_currency'))
        for value in ['', 'a'*65,'a b','a\x00b','中文']:
            j=fixture();j['calls'][0]['call_id']=value;negatives.append(('id-'+repr(value),j,'cost_identifier'))
        j=fixture();j['calls'].append(j['calls'][0].copy());negatives.append(('duplicate-call',j,'cost_duplicate_call'))
        j=fixture();j['rates'].append(j['rates'][0].copy());negatives.append(('duplicate-rate',j,'cost_duplicate_rate'))
        for label,key,value,error in [('attempt-zero','attempt',0,'cost_attempt'),('attempt-max','attempt',101,'cost_quantity'),
            ('unknown-stage','stage','future','cost_stage'),('unknown-outcome','outcome','cancelled','cost_outcome')]:
            j=fixture();j['calls'][0][key]=value;negatives.append((label,j,error))
        j=fixture();j['rates'][0]['per_million']=four('1000000');j['calls'][0]['tokens']=four(1000000000)
        negatives.append(('multiply-overflow',j,'cost_overflow'))
        j=fixture();j['rates'][0]['per_million']=four('10000');j['calls'][0]['tokens']=four(0);j['calls'][0]['tokens']['output']=1000000000
        j['calls'].append({**j['calls'][0],'call_id':'next'});negatives.append(('aggregate-overflow',j,'cost_overflow'))
        for name,value,err in negatives:
            call(value,2,err);check(True,'reject '+name)
        for name,raw,err in [('duplicate-key',b'{"x":1,"x":2}','cost_duplicate_key'),('escaped-key',b'{"x":1,"\\u0078":2}','cost_duplicate_key'),
            ('invalid-utf8',b'\xff','cost_invalid_json'),('null-byte',b'{}\x00','cost_invalid_json'),('nan',b'{"x":NaN}','cost_invalid_json'),
            ('empty',b'','cost_invalid_json'),('deep',b'['*40+b'0'+b']'*40,'cost_invalid_json')]:
            call(raw,2,err);check(True,'raw refusal '+name)
        for args in (['cost'],['cost','unknown'],['cost','report','--brain','should-not-open']):
            call(base,2,'cost_invalid_action',args);check(True,'unexpected option refused '+str(args))
        check(snap()==initial,'all valid and invalid commands leave existing home and directories unchanged')
    except Exception as e:failure=type(e).__name__+': '+str(e)
    out={'schema':'qbrain-n48f-process-v1','binary_sha256':sha(binary.read_bytes()),'script_sha256':sha(Path(__file__).read_bytes()),
        'platform':os.name,'passed':sum(x['passed'] for x in checks),'failed':sum(not x['passed'] for x in checks)+int(failure is not None and all(x['passed'] for x in checks)),
        'failure':failure,'commands':len(records),'checks':checks,'records':records,'provider_calls':0,'real_billing_verified':False}
    (output/'report.json').write_bytes(json.dumps(out,ensure_ascii=False,indent=2).encode()+b'\n')
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=run(a.binary.resolve(strict=True),a.output.resolve())
    print(json.dumps({k:v for k,v in r.items() if k not in ('records','checks')}))
    raise SystemExit(bool(r['failed']))
