"""Independent generated-usage/Fraction comparison against an explicit Qbrain.
Synthetic responses only. No price lookup, user brain, provider or model request.
The separately pinned N48F Fraction oracle is reused, not the importer/test mapper.
"""
from __future__ import annotations
import argparse,copy,hashlib,importlib.util,itertools,json,os,random,subprocess,tempfile
from pathlib import Path
B=('input_uncached','input_cache_read','input_cache_write','output')
FMTS=('openai_chat','openai_responses','anthropic_messages')
STAGES=('main','embedding','summary','extraction','rerank','other')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def enc(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def need(x,m):
 if not x:raise ValueError(m)
def load_oracle(source):
 p=source/'docs/nodes/n48f-evidence/review_cost_reference.py'
 need(sha(p.read_bytes())==ORACLE_SHA,'Fraction oracle changed')
 s=importlib.util.spec_from_file_location('prior_fraction_oracle',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
ORACLE_SHA='0c7d0af96b1c820cf624249fb4f99a2e673c38e1a7360a673a12e2b595c59aac'

def fixture(fmt,states=(3,3,3,3),n=0):
 anth=fmt=='anthropic_messages';provider='anthropic' if anth else 'openai'
 # States are: missing, explicit null, known zero, known positive.
 chosen=[None if x<2 else 0 if x==2 else a for x,a in zip(states,(37,7,11,19))]
 u={};known=dict(zip(B,chosen))
 def put(o,k,i):
  if states[i]:o[k]=chosen[i]
 if anth:
  for i,k in enumerate(('input_tokens','cache_read_input_tokens','cache_creation_input_tokens','output_tokens')):put(u,k,i)
  response={'id':f'response-{n}','model':'sample-model','type':'message','role':'assistant','stop_reason':'end_turn',
     'content':[{'type':'text','text':'PRIVATE_SYNTHETIC_TEXT'}],'usage':u}
 else:
  ri=fmt=='openai_responses';ik='input_tokens' if ri else 'prompt_tokens';ok='output_tokens' if ri else 'completion_tokens'
  dk='input_tokens_details' if ri else 'prompt_tokens_details';put(u,ik,0);put(u,ok,3);u[dk]={};put(u[dk],'cached_tokens',1);put(u[dk],'cache_write_tokens',2)
  if chosen[0] is not None and chosen[3] is not None:u['total_tokens']=chosen[0]+chosen[3]
  if ri:response={'id':f'response-{n}','model':'sample-model','object':'response','status':'completed','output':[{'text':'PRIVATE_SYNTHETIC_TEXT'}],'usage':u}
  else:response={'id':f'response-{n}','model':'sample-model','object':'chat.completion','choices':[{'finish_reason':'stop','message':{'content':'PRIVATE_SYNTHETIC_TEXT'}}],'usage':u}
  a,r,w,o=chosen
  if a==0:r=w=0
  known=dict(zip(B,(a-r-w if all(x is not None for x in (a,r,w)) else None,r,w,o)))
 card={'rate_id':'r','provider':provider,'model':'sample-model','per_million':dict(zip(B,('1.234567','0.125','2','3.000001')))}
 record={'call_id':f'call-{n:04}','stage':STAGES[n%6],'rate_id':'r','attempt':1+n%100,'outcome':('success','failure','unknown')[n%3],
    'format':fmt,'response':response}
 request={'schema':'qbrain-usage-import-v1','currency':'USD','rates':[card],'records':[record]}
 conflict=not anth and chosen[0] is not None and sum(v or 0 for v in chosen[1:3])>chosen[0]
 return request,known,'usage_inconsistent' if conflict else None

def run(binary,source,output):
 oracle=load_oracle(source);output.mkdir(parents=True,exist_ok=False);rawdir=output/'raw';rawdir.mkdir();checks=[];records=[];failure=None
 def check(x,label):
  checks.append({'case':label,'passed':bool(x)});need(x,label)
 try:
  with tempfile.TemporaryDirectory(prefix='n48g-independent-') as td:
   home=Path(td);(home/'private-sentinel').write_text('DO_NOT_TOUCH')
   env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','OPENCODE','GH_TOKEN','GITHUB_TOKEN'))}
   env.update(HOME=td,USERPROFILE=td,LOCALAPPDATA=td,APPDATA=td,QBRAIN_BRAIN='must-not-open',OPENAI_API_KEY='SYNTHETIC_NOT_A_KEY')
   def call(request,label,expected=None,error=None,action='import'):
    raw=request if isinstance(request,bytes) else enc(request)
    p=subprocess.run([str(binary),'cost',action],input=raw,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,cwd=home,timeout=10)
    index=len(records);record={'case':label,'index':index,'action':action,'exit':p.returncode}
    for k,b in (('stdin',raw),('stdout',p.stdout),('stderr',p.stderr)):(rawdir/f'{index:04d}.{k}').write_bytes(b);record[k+'_sha256']=sha(b)
    records.append(record);check(p.returncode==(2 if error else 0) and not p.stderr,label+'/exit');value=json.loads(p.stdout)
    if error:check(value=={'error':{'code':error}},label+'/expected-rejection');return value
    if action=='report':check(enc(value)==enc(oracle.reference(request)),label+'/Fraction-report');return value
    wanted=copy.deepcopy(value['cost_input']);wanted['calls']=[{**{k:r[k] for k in ('call_id','stage','rate_id','attempt','outcome')},'tokens':expected[r['call_id']]} for r in sorted(request['records'],key=lambda r:r['call_id'])]
    # Expected rates are normalized independently of result.
    from fractions import Fraction
    wanted['rates']=copy.deepcopy(sorted(request['rates'],key=lambda r:r['rate_id']))
    for c in wanted['rates']:c['per_million']={b:None if v is None else oracle.fixed(Fraction(v),6) for b,v in c['per_million'].items()}
    wanted['schema']='qbrain-cost-input-v1';wanted['currency']=request['currency']
    check(enc(value['cost_input'])==enc(wanted),label+'/generated-disjoint-counts')
    check(enc(value['cost_report'])==enc(oracle.reference(wanted)),label+'/full-Fraction-cost')
    check(value['usage_complete'] is all(v is not None for counts in expected.values() for v in counts.values()),label+'/unknowns')
    for m in value['mapping']:
     r=next(r for r in request['records'] if r['call_id']==m['call_id']);provider='anthropic' if r['format']=='anthropic_messages' else 'openai'
     check(m['format']==r['format'] and m['provider']==provider and m['response_reference_sha256']==sha((provider+'/'+r['response']['id']).encode()),label+'/identity')
    check(value['normalization_sha256']==sha(enc({'cost_input':wanted,'mapping':value['mapping']})),label+'/canonical-fingerprint')
    check(all(value[k] is False for k in ('source_authenticated','response_content_included','rate_applicability_verified','outcome_labels_verified','all_provider_calls_observed')) and value['provider_requests_sent']==0,label+'/scope')
    check(b'PRIVATE_SYNTHETIC' not in p.stdout,label+'/no-body-echo')
    return value
   for f in FMTS:
    for n,states in enumerate(itertools.product(range(4),repeat=4)):
     request,counts,error=fixture(f,states,n)
     if n%5==0:request['rates'][0]['per_million']['input_cache_write']=None
     if n%17==0:request['rates']=[]
     out=call(request,f+'-'+str(n),{request['records'][0]['call_id']:counts},error)
     if not error and n in (0,85,170,255):
      changed=copy.deepcopy(request);changed['records'][0]['response']['body_ignored']={'private':'PRIVATE_SYNTHETIC_DIFFERENT_中文😀'}
      other=call(changed,f+'-body-'+str(n),{request['records'][0]['call_id']:counts})
      check(enc(out)==enc(other),'response body does not affect normalized accounting')
      if n==255:
       piped=call(out['cost_input'],f+'-normalized-pipe',action='report');check(enc(piped)==enc(out['cost_report']),'cost report pipeline exact')
   rng=random.Random(48070922)
   for scenario in range(12):
    batch={'schema':'qbrain-usage-import-v1','currency':'USD','rates':[],'records':[]};expect={}
    for i in range(16):
     f=FMTS[i%3];r,c,_=fixture(f,(3,3,3,3),scenario*20+i);card=r['rates'][0];card['rate_id']=f'r{i}';record=r['records'][0];record['rate_id']=card['rate_id']
     card['per_million']={b:rng.choice([None,'0','0.000001','0.333333','2.5','100']) for b in B}
     batch['rates'].append(card);batch['records'].append(record);expect[record['call_id']]=c
    original=call(batch,'mixed-'+str(scenario),expect);rng.shuffle(batch['records']);rng.shuffle(batch['rates'])
    again=call(batch,'shuffled-'+str(scenario),expect);check(enc(original)==enc(again),'batch ordering invariance')
   r,c,_=fixture('openai_responses');x=copy.deepcopy(r['records'][0]);x['call_id']='different';r['records'].append(x)
   call(r,'repeated-response-with-another-call',error='usage_duplicate_response')
   # All allowed tool counters must be checked even after a fee-exclusion note.
   for first in (None,0,1):
    for second in (True,-1,'7'):
     r,c,_=fixture('anthropic_messages');r['records'][0]['response']['usage']['server_tool_use']={'web_fetch_requests':first,'web_search_requests':second}
     call(r,'excluded-tool-still-validated',error='usage_quantity')
   for f in FMTS[:2]:
    for subset in (1,999999999):
     r,c,_=fixture(f);u=r['records'][0]['response']['usage'];resp=f=='openai_responses'
     u['input_tokens' if resp else 'prompt_tokens']=None;u['output_tokens' if resp else 'completion_tokens']=0;u['total_tokens']=subset-1
     u['input_tokens_details' if resp else 'prompt_tokens_details']={'cached_tokens':subset,'cache_write_tokens':None}
     call(r,'known-cache-lower-bound',error='usage_inconsistent')
   for f in FMTS:
    r,c,_=fixture(f);raw=enc(r).replace(b'"PRIVATE_SYNTHETIC_TEXT"',b'{"hidden":1,"\\u0068idden":2}')
    call(raw,'ignored-content-duplicate-key',error='usage_duplicate_key')
   check([p.name for p in home.iterdir()]==['private-sentinel'] and (home/'private-sentinel').read_text()=='DO_NOT_TOUCH','all import/report calls are brain-free and nonmutating')
 except Exception as e:failure=type(e).__name__+': '+str(e)
 result={'schema':'qbrain-n48g-independent-review-v1','binary_sha256':sha(binary.read_bytes()),'script_sha256':sha(Path(__file__).read_bytes()),
    'oracle_sha256':ORACLE_SHA,'checks':checks,'records':records,'passed':sum(c['passed'] for c in checks),'failure':failure,
    'commands':len(records),'raw_streams':3*len(records),'provider_requests_sent':0,'real_billing_verified':False}
 (output/'review.json').write_bytes(enc(result)+b'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for k in ('binary','source','output'):p.add_argument('--'+k,type=Path,required=True)
 a=p.parse_args();r=run(a.binary.resolve(strict=True),a.source.resolve(strict=True),a.output)
 print(json.dumps({k:v for k,v in r.items() if k not in ('checks','records')},sort_keys=True));raise SystemExit(bool(r['failure']) or not all(c['passed'] for c in r['checks']))
