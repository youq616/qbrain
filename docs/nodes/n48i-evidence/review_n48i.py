"""Post-implementation N48I black-box review, independent of the main test oracle.
Synthetic inputs only; invariants, exact uint64 boundaries and ownership changes.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, os, subprocess, tempfile
from pathlib import Path
from fractions import Fraction

K=('input_uncached','input_cache_read','input_cache_write','output')
def encode(x): return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def h(x): return hashlib.sha256(x).hexdigest()
def need(x, label):
    if not x: raise ValueError(label)
def base():
    def arm(label):
        return {'label':label,'ledger_complete':True,'conditions_sha256':'a'*64,
                'tasks':[{'task_id':'t1','task_sha256':'b'*64,'call_ids':['c1']}], 'shared_call_ids':[],
                'cost_input':{'schema':'qbrain-cost-input-v1','currency':'USD',
                  'rates':[{'rate_id':'r','provider':'synthetic','model':'same-primary','per_million':dict.fromkeys(K,'1')}],
                  'calls':[{'call_id':'c1','rate_id':'r','stage':'main','attempt':1,'outcome':'success','tokens':dict(zip(K,[10,0,0,5]))}]}}
    return {'schema':'qbrain-cost-comparison-v1','comparison_id':'review','currency':'USD','baseline':arm('base'),'candidate':arm('new')}

def main(binary,out):
    out.mkdir(parents=True,exist_ok=False); (out/'raw').mkdir()
    rows=[]; checks=0
    def check(ok,label):
        nonlocal checks
        need(ok,label); checks+=1
    with tempfile.TemporaryDirectory(prefix='qbrain-n48i-review-') as d:
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC'))}
        env.update(HOME=d,USERPROFILE=d,LOCALAPPDATA=d,APPDATA=d)
        def call(name,x,code=0):
            data=encode(x) if not isinstance(x,bytes) else x
            p=subprocess.run([str(binary),'cost','compare'],input=data,capture_output=True,env=env,cwd=d,timeout=20)
            n=len(rows); dig={}
            for suffix,raw in [('stdin',data),('stdout',p.stdout),('stderr',p.stderr)]:
                (out/'raw'/f'{n:03d}.{suffix}').write_bytes(raw); dig[suffix]=h(raw)
            rows.append({'name':name,'exit':p.returncode,'hashes':dig})
            check(p.returncode==code and not p.stderr,name+' exit/stderr')
            return json.loads(p.stdout)
        x=base(); r=call('equal',x)
        check(r['change']['candidate_minus_baseline']=='0.000000000000','equal zero')
        check(r['change']['relative_change']=={'numerator':'0','denominator':'1'},'zero reduced')
        x['candidate']['cost_input']['calls'][0]['outcome']='failure'
        r=call('failed-task-still-cost-only',x)
        check(r['quality_verified'] is False and r['comparison_eligible'] is True,'eligibility not quality')
        check(r['candidate']['cost_report']['summary']['failed_calls']==1,'failure counted')
        # All global and complete subset deltas must disappear with one unknown task.
        x=base()
        for side in ('baseline','candidate'):
            c=copy.deepcopy(x[side]['cost_input']['calls'][0]); c['call_id']='c2'
            x[side]['cost_input']['calls'].append(c)
            x[side]['tasks'].append({'task_id':'t2','task_sha256':'c'*64,'call_ids':['c2']})
        clean=call('two-tasks-complete',x)
        bad=copy.deepcopy(x); bad['candidate']['cost_input']['calls'][1]['tokens']['output']=None
        r=call('unknown-only-second-task',bad)
        check(r['by_task'][0]['candidate']['complete'] is True,'first task really complete')
        for g in [r['change'],r['shared']['change']]+[v['change'] for v in r['by_task']+r['by_stage']]:
            check(g['candidate_minus_baseline'] is None and g['relative_change'] is None,'no partial comparison')
        # Assignment changes bind the fingerprint even if equal costs leave totals fixed.
        swapped=copy.deepcopy(x)
        swapped['candidate']['tasks'][0]['call_ids'],swapped['candidate']['tasks'][1]['call_ids']=['c2'],['c1']
        r=call('ownership-fingerprint',swapped)
        check(r['input_sha256']!=clean['input_sha256'],'assignment bound')
        check(r['change']==clean['change'],'no arithmetic difference from equal reassignment')
        for side in ('baseline','candidate'):
            x[side]['tasks'].reverse(); x[side]['cost_input']['calls'].reverse()
        r=call('task-and-call-order-invariant',x)
        check(r==clean,'canonical arrays')
        # Same matching extra task prevents subset-only manifest validation.
        bad=copy.deepcopy(x); bad['candidate']['tasks'].pop()
        r=call('missing-submitted-task',bad,2)
        check(r=={'error':{'code':'comparison_unassigned_call'}},'unassigned preempts mismatch')
        # Exact maximum uint64 scaled amount, then one unit more.
        maximum=2**64-1; q,rem=divmod(maximum,10**9)
        price=f'{q//10**6}.{q%10**6:06d}'
        x=base()
        for side in ('baseline','candidate'):
            x[side]['cost_input']['rates'][0]['per_million'].update(input_uncached=price,output='0.000001')
            x[side]['cost_input']['calls'][0]['tokens']=dict.fromkeys(K,0)
        x['candidate']['cost_input']['calls'][0]['tokens'].update(input_uncached=10**9,output=rem)
        r=call('uint64-exact-maximum',x)
        check(r['change']['candidate_minus_baseline']=='18446744.073709551615','max exact decimal')
        check(r['change']['relative_change'] is None,'zero base undefined')
        x['baseline']['cost_input']['calls'][0]['tokens']['output']=1
        r=call('uint64-minus-one',x)
        check(r['change']['candidate_minus_baseline']=='18446744.073709551614','unsigned positive magnitude')
        check(r['change']['relative_change']=={'numerator':str(maximum-1),'denominator':'1'},'ratio not signed overflow')
        x['baseline'],x['candidate']=x['candidate'],x['baseline']
        r=call('uint64-minus-one-negative',x)
        check(r['change']['candidate_minus_baseline']=='-18446744.073709551614','unsigned negative magnitude')
        check(r['change']['relative_change']=={'numerator':'-'+str(maximum-1),'denominator':str(maximum)},'max denominator')
        x['baseline']['cost_input']['calls'][0]['tokens']['output']+=1
        r=call('uint64-one-over',x,2); check(r=={'error':{'code':'cost_overflow'}},'overflow rejected')
        # Unused cards differ without redefining primary price eligibility.
        x=base(); extra=copy.deepcopy(x['candidate']['cost_input']['rates'][0])
        extra.update(rate_id='unused',provider='different',model='not-used')
        x['candidate']['cost_input']['rates'].append(extra)
        r=call('unused-rate-not-primary',x); check(r['comparison_eligible'] is True,'ignore unused primary')
        # Missing rate card plus known zero costs still cannot establish primary identity.
        x=base()
        for side in ('baseline','candidate'):
            x[side]['cost_input']['calls'][0]['tokens']=dict.fromkeys(K,0)
            x[side]['cost_input']['rates']=[]
        r=call('zero-cost-but-primary-unknown',x)
        check(r['baseline']['cost_report']['summary']['complete'] is True,'zero cost known')
        check(r['unavailable_reasons']==['primary_model_unknown_or_multiple'],'identity required even free')
        # Independent one-pico variations, swaps and conservation; no imported oracle.
        for i in range(1,51):
            x=base()
            for side in ('baseline','candidate'):
                x[side]['cost_input']['rates'][0]['per_million']=dict.fromkeys(K,'0.000001')
                x[side]['cost_input']['calls'][0]['tokens']=dict.fromkeys(K,0)
            x['baseline']['cost_input']['calls'][0]['tokens']['input_uncached']=i*i+7
            x['candidate']['cost_input']['calls'][0]['tokens']['output']=i*3
            a,b=Fraction(i*i+7,10**12),Fraction(i*3,10**12)
            r=call(f'pico-{i}',x); frac=(b-a)/a
            check(Fraction(r['change']['candidate_minus_baseline'])==b-a,'pico difference')
            check(r['change']['relative_change']=={'numerator':str(frac.numerator),'denominator':str(frac.denominator)},'pico fraction')
            for side in ('baseline','candidate'):
                check(Fraction(r[side]['cost_report']['summary']['known_subtotal'])==sum(Fraction(t[side]['known_subtotal']) for t in r['by_task'])+Fraction(r['shared'][side]['known_subtotal']),'ownership conservation')
        # Root whitespace cap is inclusive; result independent of whitespace.
        raw=encode(base()); padded=raw+b' '*(1048576-len(raw))
        r=call('input-exact-one-mib',padded)
        check(r['comparison_eligible'] is True,'inclusive root cap')
        r=call('input-one-over-mib',padded+b' ',2)
        check(r=={'error':{'code':'comparison_input_limit'}},'one over root cap')
        check(not list(Path(d).iterdir()),'no local brain files')
    result={'schema':'qbrain-n48i-separate-review-v1','binary_sha256':h(binary.read_bytes()),'script_sha256':h(Path(__file__).read_bytes()),'calls':len(rows),'checks':checks,'passed':True,'records':rows,'synthetic_only':True,'real_quality_verified':False}
    (out/'RESULT.json').write_bytes(encode(result)+b'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='records'}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();main(a.binary.resolve(strict=True),a.output)
