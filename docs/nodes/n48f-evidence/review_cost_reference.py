"""Independent Fraction-ledger review of the fixed N48F executable.
No product/reference imports, provider calls or persistent user data. Exact raw
requests/results are retained separately; this report is not a verified bill.
"""
from __future__ import annotations
import argparse, copy, hashlib, itertools, json, os, random, subprocess, tempfile
from fractions import Fraction
from pathlib import Path
B=('input_uncached','input_cache_read','input_cache_write','output')
S=('main','embedding','summary','extraction','rerank','other')
CAP=(1<<64)-1

def sha(x): return hashlib.sha256(x).hexdigest()
def wire(x): return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def fixed(x,places):
    scaled=x*10**places
    if scaled.denominator!=1: raise ValueError('nonterminating expected amount')
    v=scaled.numerator
    return str(v//10**places)+'.'+str(v%10**places).zfill(places)
def four(x): return dict.fromkeys(B,x)
def fixture():
    return {'schema':'qbrain-cost-input-v1','currency':'USD',
      'rates':[{'rate_id':'r','provider':'synthetic','model':'model','per_million':four('2.5')}],
      'calls':[{'call_id':'one','stage':'main','rate_id':'r','attempt':1,'outcome':'success','tokens':four(1)}]}

def reference(v):
    cards={c['rate_id']:c for c in v['rates']}; calls=sorted(v['calls'],key=lambda c:c['call_id']); output=[]
    def aggregate(rows):
        missing=sum(r['unknown_components'] for r in rows)
        known=sum((Fraction(r['known_subtotal']) for r in rows),Fraction(0))
        if known*10**12>CAP:raise OverflowError('cost_overflow')
        tokens={}
        for b in B:
            counts=[r['components'][b]['tokens'] for r in rows];unknown=counts.count(None)
            n=sum(x for x in counts if x is not None)
            tokens[b]={'known_tokens':n,'unknown_calls':unknown,'total_tokens':None if unknown else n}
        return {'calls':len(rows),'failed_calls':sum(r['outcome']=='failure' for r in rows),
          'unknown_outcome_calls':sum(r['outcome']=='unknown' for r in rows),'retry_calls':sum(r['attempt']>1 for r in rows),
          'known_subtotal':fixed(known,12),'total_estimate':None if missing else fixed(known,12),
          'complete':missing==0,'unknown_components':missing,'tokens':tokens}
    for call in calls:
        card=cards.get(call['rate_id']);components={};known=Fraction(0);unknown=0
        for b in B:
            count=call['tokens'][b];rate=card['per_million'][b] if card else None
            if count is None: amount=None;reason='usage_unknown'
            elif count==0: amount=Fraction(0);reason=None
            elif rate is None: amount=None;reason='rate_unknown' if card else 'rate_card_missing'
            else: amount=count*Fraction(rate)/1000000;reason=None
            if amount is None:unknown+=1
            else:
                if amount*10**12>CAP:raise OverflowError('cost_overflow')
                known+=amount
            components[b]={'tokens':count,'rate_per_million':None if rate is None else fixed(Fraction(rate),6),
              'cost':None if amount is None else fixed(amount,12),'missing':reason}
        if known*10**12>CAP:raise OverflowError('cost_overflow')
        output.append({k:call[k] for k in ('call_id','stage','rate_id','attempt','outcome')}|
          {'components':components,'known_subtotal':fixed(known,12),'total_estimate':None if unknown else fixed(known,12),
           'complete':unknown==0,'unknown_components':unknown})
    normalized=copy.deepcopy(v);normalized['rates'].sort(key=lambda c:c['rate_id']);normalized['calls'].sort(key=lambda c:c['call_id'])
    for c in normalized['rates']:c['per_million']={b:None if p is None else fixed(Fraction(p),6) for b,p in c['per_million'].items()}
    return {'schema':'qbrain-cost-report-v1','currency':v['currency'],'input_sha256':sha(wire(normalized)),
      'basis':'caller_supplied_disjoint_token_counts_and_rate_cards','rate_unit':'currency_per_million_tokens',
      'decimal_places':12,'summary':aggregate(output),
      'by_stage':[{'stage':s,**aggregate([r for r in output if r['stage']==s])} for s in sorted({r['stage'] for r in output})],
      'by_rate':[{'rate_id':key,'provider':cards[key]['provider'] if key in cards else None,
         'model':cards[key]['model'] if key in cards else None,**aggregate([r for r in output if r['rate_id']==key])}
         for key in sorted({r['rate_id'] for r in output})],
      'calls':output,'billing_verified':False,'all_provider_calls_observed':False,'provider_requests_sent':0,
      'fees_taxes_discounts_included':False,'currency_conversion_performed':False}

def validate(value,result):
    # Exact serialization comparison rejects bool-as-int, extra/missing fields,
    # altered rates/labels and inconsistent totals as well as arithmetic changes.
    if wire(result)!=wire(reference(value)):raise ValueError('full_reference_mismatch')

def run(binary,output):
    output.mkdir(parents=True,exist_ok=False);rawdir=output/'raw';rawdir.mkdir()
    checks=[];records=[];failure=None;counter=0
    def check(ok,label):
        checks.append({'name':label,'passed':bool(ok)})
        if not ok:raise ValueError(label)
    try:
      with tempfile.TemporaryDirectory(prefix='n48f-reference-') as temporary:
        root=Path(temporary);home=root/'home';home.mkdir();(home/'sentinel').write_bytes(b'DO_NOT_CHANGE')
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN','OPENCODE'))}
        env.update(HOME=str(home),USERPROFILE=str(home),LOCALAPPDATA=str(home),APPDATA=str(home),
            QBRAIN_BRAIN='must-not-open',OPENAI_API_KEY='SYNTHETIC_ONLY_NOT_USED')
        def files():return sorted((str(p.relative_to(root)),sha(p.read_bytes()) if p.is_file() else 'directory') for p in root.rglob('*'))
        initial=files()
        def execute(value,label,error=None):
            raw=value if isinstance(value,bytes) else wire(value)
            p=subprocess.run([str(binary),'cost','report'],input=raw,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,env=env,timeout=15)
            number=len(records);record={'case':label,'exit':p.returncode,'index':number}
            for kind,data in [('stdin',raw),('stdout',p.stdout),('stderr',p.stderr)]:
                (rawdir/f'{number:04d}.{kind}').write_bytes(data);record[kind+'_sha256']=sha(data)
            records.append(record)
            check(p.returncode==(2 if error else 0) and not p.stderr,label+'/exit')
            result=json.loads(p.stdout)
            if error:check(result=={'error':{'code':error}},label+'/refusal')
            else:
                validate(value,result);check(True,label+'/complete-reference')
            check(files()==initial,label+'/no-filesystem-mutation')
            return result
        basic=fixture();control=execute(basic,'control')
        # Exhaustive independent unknown-token and unknown-price masks.
        for tokens_mask in range(16):
            for rates_mask in range(16):
                v=fixture()
                v['calls'][0]['tokens']={b:None if tokens_mask&(1<<i) else (0 if i%2 else 7) for i,b in enumerate(B)}
                v['rates'][0]['per_million']={b:None if rates_mask&(1<<i) else ('0' if i%2 else '0.000001') for i,b in enumerate(B)}
                execute(v,f'unknown-mask-{tokens_mask}-{rates_mask}')
        for counts in itertools.product((None,0,9),repeat=4):
            v=fixture();v['rates']=[];v['calls'][0]['tokens']=dict(zip(B,counts));execute(v,'absent-card-'+str(counts))
        rng=random.Random(480622)
        for scenario in range(24):
            v=fixture();v['rates']=[];v['calls']=[]
            for i in range(8):v['rates'].append({'rate_id':f'r{i}','provider':f'p{i%3}','model':f'm{i%4}',
                'per_million':{b:rng.choice([None,'0','0.000001','0.123456','2.5','17.000001']) for b in B}})
            for i in range(32):v['calls'].append({'call_id':f'c{i}','stage':S[i%6],'rate_id':f'r{rng.randrange(10)}',
                'attempt':1+i%100,'outcome':('success','failure','unknown')[i%3],
                'tokens':{b:rng.choice([None,0,1,13,1000000]) for b in B}})
            original=execute(v,f'mixed-{scenario}');rng.shuffle(v['rates']);rng.shuffle(v['calls'])
            reordered=execute(v,f'mixed-reordered-{scenario}')
            check(wire(original)==wire(reordered),'canonical reorder '+str(scenario))
        maxv=fixture();maxv['rates']=[{'rate_id':f'r{i}','provider':'synthetic','model':'m','per_million':four('0.000001')} for i in range(64)]
        maxv['calls']=[{'call_id':f'c{i:03}','stage':S[i%6],'rate_id':f'r{i%64}','attempt':100,
            'outcome':'failure','tokens':four(1000000000)} for i in range(512)]
        result=execute(maxv,'max-512-calls-64-cards')
        check(result['summary']['total_estimate']=='2.048000000000','maximum-low-rate exact total')
        # Assemble uint64's exact scaled ceiling from separately legal components.
        ceiling=fixture();ceiling['rates']=[];ceiling['calls']=[]
        for i,(price,tokens) in enumerate([('1000000',18446744),('1',73709),('0.000001',551615)]):
            ceiling['rates'].append({'rate_id':f'r{i}','provider':'synthetic','model':'boundary','per_million':four(price)})
            ceiling['calls'].append({'call_id':f'c{i}','stage':S[i],'rate_id':f'r{i}','attempt':1,'outcome':'success',
                'tokens':dict(four(0),output=tokens)})
        result=execute(ceiling,'exact-u64-ceiling')
        check(result['summary']['total_estimate']=='18446744.073709551615','exact maximum no rounding')
        more=copy.deepcopy(ceiling);more['calls'].append({'call_id':'extra','stage':'other','rate_id':'r2','attempt':2,'outcome':'failure','tokens':dict(four(0),output=1)})
        execute(more,'one-unit-overflow','cost_overflow')
        missing=copy.deepcopy(ceiling);missing['calls'][0]['tokens']['input_uncached']=None
        result=execute(missing,'maximum-known-with-unknown')
        check(result['summary']['total_estimate'] is None and result['summary']['known_subtotal']=='18446744.073709551615','missing component does not erase exact known subtotal')
        for key in B:
            spelling=fixture();spelling['rates'][0]['per_million'][key]='2.500000'
            check(execute(spelling,'rate-spelling-'+key)==control,'trailing-zero rate spelling canonical '+key)
        empty=fixture();empty['rates']=[];empty['calls']=[];execute(empty,'no-records-is-not-a-billing-claim')
        # Escaped identical nested field names must not silently win.
        text=wire(fixture()).decode()
        execute(text.replace('"output":1','"output":1,"\\u006futput":2',1).encode(),'escaped-duplicate-bucket','cost_duplicate_key')
        extra=fixture();extra['calls'][0]['tokens']['cached_tokens']=3;execute(extra,'raw-provider-bucket-rejected','cost_fields')
        extra=fixture();extra['rates'][0]['per_million']['output']='1000000.000001';execute(extra,'rate-ceiling','cost_rate_range')
        # Entire expected reports must reject altered annotations, not only money.
        for mutation in ('rate','provider','model','basis','unit','extra','tokens-bool','count-bool','claim','id','subtotal'):
            bad=copy.deepcopy(control)
            if mutation=='rate':bad['calls'][0]['components']['output']['rate_per_million']='9.000000'
            if mutation=='provider':bad['by_rate'][0]['provider']='other'
            if mutation=='model':bad['by_rate'][0]['model']='other'
            if mutation=='basis':bad['basis']='actual_bill'
            if mutation=='unit':bad['rate_unit']='per_token'
            if mutation=='extra':bad['private_prompt']='unexpected'
            if mutation=='tokens-bool':bad['calls'][0]['components']['output']['tokens']=True
            if mutation=='count-bool':bad['summary']['calls']=True
            if mutation=='claim':bad['all_provider_calls_observed']=True
            if mutation=='id':bad['calls'][0]['rate_id']='unknown'
            if mutation=='subtotal':bad['summary']['known_subtotal']='0.000000000000'
            try:validate(basic,bad)
            except ValueError:check(True,'reject actual report mutation '+mutation)
            else:raise ValueError('mutation accepted: '+mutation)
        validate(basic,control);check(True,'original positive remains valid')
    except Exception as e:failure=type(e).__name__+': '+str(e)
    result={'schema':'qbrain-n48f-independent-review-v1','binary_sha256':sha(binary.read_bytes()),
      'script_sha256':sha(Path(__file__).read_bytes()),'checks':checks,'records':records,
      'passed':sum(c['passed'] for c in checks),'failed':sum(not c['passed'] for c in checks)+int(failure is not None and all(c['passed'] for c in checks)),
      'failure':failure,'commands':len(records),'platform':os.name,'provider_calls':0,'real_billing_verified':False,
      'scope':'Exact Python Fraction reference; explicit synthetic caller records, not supplier invoices'}
    (output/'review.json').write_bytes(wire(result)+b'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=run(a.binary.resolve(strict=True),a.output)
    print(json.dumps({k:v for k,v in r.items() if k not in ('checks','records')}))
    raise SystemExit(bool(r['failed']))
