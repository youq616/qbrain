"""Actual import CLI with an independently written partition/Decimal reference.

Synthetic provider-shaped objects only. Records are saved for offline replay.
No network, credentials, tokenization or real user brain is used.
"""
from __future__ import annotations
import argparse,copy,hashlib,itertools,json,os,random,subprocess,tempfile
from pathlib import Path
from test_token_cost import verify_math
B=('input_uncached','input_cache_read','input_cache_write','output')
FORMATS=('openai_chat','openai_responses','anthropic_messages')
def need(ok,message):
    if not ok:raise ValueError(message)
def encode(x):return json.dumps(x,ensure_ascii=False,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def response(fmt,uid='remote-1'):
    usage={'input_tokens':100,'input_tokens_details':{'cached_tokens':30,'cache_write_tokens':20},
        'output_tokens':50,'output_tokens_details':{'reasoning_tokens':40},'total_tokens':150}
    if fmt=='openai_chat':
        usage={'prompt_tokens':100,'prompt_tokens_details':usage['input_tokens_details'],
            'completion_tokens':50,'completion_tokens_details':usage['output_tokens_details'],'total_tokens':150}
        return {'id':uid,'model':'example','object':'chat.completion','choices':[{'finish_reason':'stop','message':{'content':'PRIVATE_BODY_SENTINEL'}}],'usage':usage}
    if fmt=='anthropic_messages':
        return {'id':uid,'model':'example','type':'message','role':'assistant','stop_reason':'end_turn',
            'content':[{'type':'text','text':'PRIVATE_BODY_SENTINEL'}],
            'usage':{'input_tokens':50,'cache_read_input_tokens':30,'cache_creation_input_tokens':20,'output_tokens':50,
                'output_tokens_details':{'thinking_tokens':40},'cache_creation':{'ephemeral_5m_input_tokens':20,'ephemeral_1h_input_tokens':0}}}
    return {'id':uid,'model':'example','object':'response','status':'completed','output':[{'text':'PRIVATE_BODY_SENTINEL'}],'usage':usage}
def fixture(fmt='openai_responses'):
    return {'schema':'qbrain-usage-import-v1','currency':'USD','rates':[{'rate_id':'r','provider':'anthropic' if fmt=='anthropic_messages' else 'openai',
        'model':'example','per_million':dict(zip(B,('1','0.1','2','3')))}],
        'records':[{'call_id':'one','stage':'main','rate_id':'r','attempt':1,'outcome':'success','format':fmt,'response':response(fmt)}]}
def reference(root):
    calls=[]
    for rec in sorted(root['records'],key=lambda r:r['call_id']):
        raw=rec['response'];u=raw.get('usage') if isinstance(raw,dict) else None
        counts=dict.fromkeys(B,None)
        if u is not None:
            if rec['format']=='anthropic_messages':
                vals=[u.get(k) for k in ('input_tokens','cache_read_input_tokens','cache_creation_input_tokens','output_tokens')]
                ttl=u.get('cache_creation')
                if ttl is not None:vals[2]=ttl['ephemeral_5m_input_tokens']+ttl['ephemeral_1h_input_tokens']
                counts=dict(zip(B,vals))
            else:
                resp=rec['format']=='openai_responses'
                whole=u.get('input_tokens' if resp else 'prompt_tokens');out=u.get('output_tokens' if resp else 'completion_tokens')
                detail=u.get('input_tokens_details' if resp else 'prompt_tokens_details') or {}
                read,write=detail.get('cached_tokens'),detail.get('cache_write_tokens')
                if whole==0:read=write=0
                ordinary=None if any(n is None for n in (whole,read,write)) else whole-read-write
                counts=dict(zip(B,(ordinary,read,write,out)))
        calls.append({**{k:rec[k] for k in ('call_id','stage','rate_id','attempt','outcome')},'tokens':counts})
    rates=copy.deepcopy(root['rates']);rates.sort(key=lambda x:x['rate_id'])
    from decimal import Decimal
    for r in rates:r['per_million']={k:None if v is None else format(Decimal(v),'.6f') for k,v in r['per_million'].items()}
    return {'schema':'qbrain-cost-input-v1','currency':root['currency'],'rates':rates,'calls':calls}
def check_output(root,result):
    need(set(result)=={'schema','normalization_sha256','cost_input','cost_report','mapping','usage_complete','provider_requests_sent','source_authenticated',
        'response_content_included','rate_applicability_verified','outcome_labels_verified','all_provider_calls_observed'},'output fields')
    expected=reference(root);need(result['cost_input']==expected,'independent provider partition')
    verify_math(expected,result['cost_report'])
    need(result['schema']=='qbrain-usage-import-report-v1','output schema')
    for k in ('source_authenticated','response_content_included','rate_applicability_verified','outcome_labels_verified','all_provider_calls_observed'):
        need(result[k] is False,'unverified scope')
    need(type(result['provider_requests_sent']) is int and result['provider_requests_sent']==0,'no provider call')
    need([m['call_id'] for m in result['mapping']]==[c['call_id'] for c in expected['calls']],'mapping order')
    for rec,m,c in zip(sorted(root['records'],key=lambda r:r['call_id']),result['mapping'],expected['calls']):
        provider='anthropic' if rec['format']=='anthropic_messages' else 'openai'
        need(set(m)=={'call_id','format','provider','response_reference_sha256','usage_complete','notes'},'mapping fields')
        need(m['format']==rec['format'] and m['provider']==provider,'format binding')
        raw=rec['response'];ident=sha((provider+'/'+raw['id']).encode()) if isinstance(raw,dict) and 'id' in raw else None
        need(m['response_reference_sha256']==ident,'response reference hash')
        need(m['usage_complete'] is all(n is not None for n in c['tokens'].values()),'missing usage visibility')
        need(isinstance(m['notes'],list) and len(set(m['notes']))==len(m['notes']),'notes unique')
    need(result['usage_complete'] is all(m['usage_complete'] for m in result['mapping']),'aggregate completeness')
    need(result['normalization_sha256']==sha(json.dumps({'cost_input':expected,'mapping':result['mapping']},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()),'normalized identity')
    need('PRIVATE_BODY_SENTINEL' not in json.dumps(result),'content leak')
def run(binary,output):
    output.mkdir(parents=True,exist_ok=False);rawdir=output/'raw';rawdir.mkdir();records=[];checks=[];failure=None
    def check(ok,name):
        checks.append({'name':name,'passed':bool(ok)});need(ok,name)
    with tempfile.TemporaryDirectory(prefix='n48g-test-') as tmp:
        home=Path(tmp);sentinel=home/'keep.txt';sentinel.write_text('PRIVATE_HOME_SENTINEL')
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
        env.update(HOME=tmp,USERPROFILE=tmp,LOCALAPPDATA=tmp,APPDATA=tmp,QBRAIN_BRAIN='MUST-NOT-OPEN',OPENAI_API_KEY='PRIVATE_ENV_SENTINEL')
        def invoke(x,error=None,args=('cost','import'),raw=None):
            data=encode(x) if raw is None else raw;no=len(records)
            p=subprocess.run([str(binary),*args],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=home,env=env,timeout=10)
            record={'args':list(args),'exit':p.returncode,'expected_error':error,'files':{}}
            for ext,value in [('stdin',data),('stdout',p.stdout),('stderr',p.stderr)]:
                name=f'{no:04d}.{ext}';(rawdir/name).write_bytes(value);record['files'][ext]={'name':name,'sha256':sha(value),'bytes':len(value)}
            records.append(record)
            need(not p.stderr,'unexpected stderr');value=json.loads(p.stdout)
            if error:
                need(p.returncode==2 and value=={'error':{'code':error}},'wrong rejection '+str(value));return value
            need(p.returncode==0,'unexpected failure '+str(value))
            if args==('cost','import'):check_output(x,value)
            return value
        try:
            for fmt in FORMATS:
                x=fixture(fmt);r=invoke(x);check(r['cost_report']['summary']['total_estimate']=='0.000243000000',fmt+' exact reference amount')
                check(invoke(r['cost_input'],args=('cost','report'))==r['cost_report'],fmt+' pipe to unchanged report')
                y=copy.deepcopy(x);y['records'][0]['response']['private_metadata']={'text':'PRIVATE_BODY_SENTINEL_CHANGED'}
                check(invoke(y)==r,fmt+' ignored body does not change hash or output')
            # Missing, explicit-null and zero partitions; do not fabricate cache use.
            for fmt in FORMATS:
                for missing in (False,True):
                    for bits in itertools.product((False,True),repeat=4):
                        x=fixture(fmt);u=x['records'][0]['response']['usage']
                        if fmt=='anthropic_messages':u.pop('cache_creation');u.pop('output_tokens_details');targets=[(u,k) for k in ('input_tokens','cache_read_input_tokens','cache_creation_input_tokens','output_tokens')]
                        else:
                            resp=fmt=='openai_responses';u.pop('output_tokens_details' if resp else 'completion_tokens_details')
                            d=u['input_tokens_details' if resp else 'prompt_tokens_details'];targets=[(u,'input_tokens' if resp else 'prompt_tokens'),(d,'cached_tokens'),(d,'cache_write_tokens'),(u,'output_tokens' if resp else 'completion_tokens')]
                        for bit,(obj,key) in zip(bits,targets):
                            if bit:
                                if missing:obj.pop(key)
                                else:obj[key]=None
                        r=invoke(x);check(r['usage_complete'] is (not any(bits)),f'{fmt} unknown subset {missing}/{bits}')
            rng=random.Random(4807)
            for i in range(60):
                fmt=FORMATS[i%3];x=fixture(fmt);u=x['records'][0]['response']['usage'];a,b,c,o=[rng.randrange(1000000) for _ in range(4)]
                if fmt=='anthropic_messages':u.update(input_tokens=a,cache_read_input_tokens=b,cache_creation_input_tokens=c,output_tokens=o);u['cache_creation']['ephemeral_5m_input_tokens']=c;u['output_tokens_details']['thinking_tokens']=o//2
                else:
                    resp=fmt=='openai_responses';u.update({('input_tokens' if resp else 'prompt_tokens'):a+b+c,('output_tokens' if resp else 'completion_tokens'):o,'total_tokens':a+b+c+o})
                    u['input_tokens_details' if resp else 'prompt_tokens_details'].update(cached_tokens=b,cache_write_tokens=c)
                    u['output_tokens_details' if resp else 'completion_tokens_details']['reasoning_tokens']=o//2
                check(invoke(x)['usage_complete'] is True,'random disjoint token conservation '+str(i))
            # Preserve failures/retries/missing-price information and isolate identifiers.
            x=fixture();x['records'][0].update(outcome='failure',attempt=2);x['records'][0]['response']['status']='failed';r=invoke(x)
            check(r['cost_report']['summary']['failed_calls']==1 and r['cost_report']['summary']['retry_calls']==1 and r['cost_report']['summary']['complete'],'failure attempt retains charges')
            for raw in (None,{'error':{'message':'PRIVATE_BODY_SENTINEL'}},{'type':'error','error':{'message':'PRIVATE_BODY_SENTINEL'}}):
                x=fixture();x['records'][0].update(outcome='failure',response=raw);r=invoke(x)
                check(r['cost_report']['summary']['total_estimate'] is None,'missing/error response stays unknown')
            for mode in ('missing','null','empty'):
                x=fixture()
                if mode=='missing':x['records'][0]['response'].pop('usage')
                else:x['records'][0]['response']['usage']=None if mode=='null' else {}
                check(invoke(x)['usage_complete'] is False,'absent usage '+mode)
            x=fixture();x['rates']=[];check(invoke(x)['cost_report']['summary']['complete'] is False,'missing rate card remains unknown')
            x=fixture();x['rates'][0]['per_million']['output']=None;check(invoke(x)['cost_report']['summary']['complete'] is False,'null rate remains unknown')
            x=fixture();x['records'][0]['response']['usage']={'input_tokens':0,'output_tokens':0,'total_tokens':0};check(invoke(x)['usage_complete'] is True,'zero total proves cache zeros')
            x=fixture('anthropic_messages');u=x['records'][0]['response']['usage'];u['server_tool_use']={'web_search_requests':1,'web_fetch_requests':0}
            check('server_tool_fees_excluded' in invoke(x)['mapping'][0]['notes'],'tool fees explicitly excluded')
            x=fixture('anthropic_messages');u=x['records'][0]['response']['usage'];u['cache_creation']={'ephemeral_5m_input_tokens':0,'ephemeral_1h_input_tokens':20}
            check('cache_write_ttl_1h' in invoke(x)['mapping'][0]['notes'],'single one-hour TTL metadata')
            for first in (1,None):
                x=fixture('anthropic_messages')
                x['records'][0]['response']['usage']['server_tool_use']={'web_fetch_requests':first,'web_search_requests':'invalid'}
                invoke(x,'usage_quantity');check(True,'all tool counters validated after excluded fees '+str(first))
            # Contract refusals; every negative is independently labelled.
            def bad(path,value,code,fmt='openai_responses'):
                x=fixture(fmt);obj=x
                for key in path[:-1]:obj=obj[key]
                obj[path[-1]]=value;invoke(x,code);check(True,'reject '+code+' '+str(path))
            for value in (True,False,-1,1.0,'1',[],{},1000000001):bad(['records',0,'response','usage','input_tokens'],value,'usage_quantity')
            for key,value in [('cached_tokens',90),('cache_write_tokens',80)]:bad(['records',0,'response','usage','input_tokens_details',key],value,'usage_inconsistent')
            for kind in ('cache-minimum','reasoning-minimum'):
                x=fixture();u=x['records'][0]['response']['usage']
                if kind=='cache-minimum':u.update(input_tokens=None,output_tokens=0,output_tokens_details={},total_tokens=5)
                else:u.update(input_tokens=0,input_tokens_details={},output_tokens=None,total_tokens=5)
                invoke(x,'usage_inconsistent');check(True,'partial counts impose '+kind)
            bad(['records',0,'response','usage','total_tokens'],149,'usage_inconsistent')
            bad(['records',0,'response','usage','output_tokens_details','reasoning_tokens'],51,'usage_inconsistent')
            bad(['records',0,'response','usage','output_tokens_details','audio_tokens'],1,'usage_audio_unsupported')
            bad(['records',0,'response','usage','input_tokens_details','audio_tokens'],None,'usage_audio_unsupported')
            bad(['records',0,'response','usage','unexpected'],1,'usage_fields')
            bad(['records',0,'response','usage'],[],'usage_object')
            bad(['records',0,'response','usage','input_tokens_details'],1,'usage_detail_object')
            for value in ('queued','in_progress',None):bad(['records',0,'response','status'],value,'usage_response_nonterminal')
            bad(['records',0,'response','status'],'incomplete','usage_outcome_conflict')
            bad(['records',0,'response','object'],'response.completed','usage_response_kind')
            bad(['records',0,'response','object'],'chat.completion.chunk','usage_response_kind','openai_chat')
            bad(['records',0,'response','choices'],[],'usage_response_nonterminal','openai_chat')
            bad(['records',0,'response','stop_reason'],None,'usage_response_nonterminal','anthropic_messages')
            bad(['records',0,'response','type'],'message_start','usage_response_kind','anthropic_messages')
            bad(['records',0,'response','usage','cache_creation'],{'ephemeral_5m_input_tokens':10,'ephemeral_1h_input_tokens':10},'usage_mixed_cache_ttl','anthropic_messages')
            bad(['records',0,'response','usage','cache_creation'],{'ephemeral_5m_input_tokens':20},'usage_cache_ttl_incomplete','anthropic_messages')
            bad(['records',0,'response','usage','iterations'],[{'input_tokens':7}],'usage_iterations_unsupported','anthropic_messages')
            bad(['rates',0,'provider'],'other','usage_rate_provider_mismatch')
            bad(['rates',0,'model'],'other','usage_rate_model_mismatch')
            bad(['records',0,'response'],None,'usage_response_missing')
            bad(['records',0,'response'],[],'usage_response_object')
            bad(['records',0,'response','id'],'\nSECRET','usage_response_identity')
            bad(['records',0,'attempt'],0,'cost_attempt')
            bad(['records',0,'stage'],'bogus','cost_stage')
            bad(['records',0,'outcome'],'bogus','cost_outcome')
            bad(['records',0,'format'],'gemini','usage_format')
            x=fixture();e=copy.deepcopy(x['records'][0]);e['call_id']='two';e['attempt']=2;x['records'].append(e);invoke(x,'usage_duplicate_response');check(True,'same response cannot bill a retry twice')
            x['records'][1]['response']['id']='another';x['records'][1]['call_id']='one';invoke(x,'cost_duplicate_call');check(True,'duplicate call ID refused')
            raw=encode(fixture()).replace(b'"PRIVATE_BODY_SENTINEL"',b'{"key":1,"\\u006bey":2}')
            invoke(None,'usage_duplicate_key',raw=raw);check(True,'duplicate key in ignored content still rejects')
            for data,error in [(b'{}{}','usage_invalid_json'),(b'\xff','usage_invalid_json'),(b' '*1048577,'usage_input_limit')]:
                invoke(None,error,raw=data);check(True,'parse/input boundary '+error)
            x=fixture();x['records'][0]['response']['output']=['x'*262144];invoke(x,'usage_response_limit');check(True,'one response bound')
            x=fixture();x['records']=[]
            for i in range(128):
                e=fixture()['records'][0];e['call_id']=f'call-{i:03}';e['response']['id']=f'resp-{i}';x['records'].append(e)
            r=invoke(x);check(r['cost_report']['summary']['calls']==128,'128 record maximum')
            y=copy.deepcopy(x);rng.shuffle(y['records']);check(invoke(y)==r,'input reordering canonical')
            x['records'].append(fixture()['records'][0]);invoke(x,'usage_record_count');check(True,'129 records refuse')
            invoke(fixture(),'usage_invalid_action',args=('cost','import','--brain','default'));check(True,'brain option cannot redirect import')
            check(sorted(p.name for p in home.iterdir())==['keep.txt'] and sentinel.read_text()=='PRIVATE_HOME_SENTINEL','all commands preserve user home and do not open a brain')
        except Exception as exc:failure=type(exc).__name__+': '+str(exc)
    report={'schema':'qbrain-n48g-process-v1','binary_sha256':sha(binary.read_bytes()),'script_sha256':sha(Path(__file__).read_bytes()),
        'checks':checks,'records':records,'commands':len(records),'passed':sum(c['passed'] for c in checks),'failure':failure,
        'provider_requests_sent':0,'real_provider_responses_verified':False}
    (output/'report.json').write_bytes(encode(report)+b'\n');return report
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=run(a.binary.resolve(strict=True),a.output)
    print(json.dumps({k:v for k,v in r.items() if k not in ('checks','records')}))
    raise SystemExit(1 if r['failure'] or not all(x['passed'] for x in r['checks']) else 0)
