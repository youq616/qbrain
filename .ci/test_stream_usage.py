"""Real offline SSE CLI cases; synthetic data only and no provider/network calls.

Expected final objects are independently supplied, not reconstructed by product
logic. The unchanged N48G Python partition and N48F Decimal reference check costs.
"""
from __future__ import annotations
import argparse,copy,hashlib,itertools,json,os,subprocess,tempfile
from pathlib import Path
from test_provider_usage import fixture as nonstream_fixture, check_output as check_nonstream

FORMATS=('openai_chat','openai_responses','anthropic_messages')
def sha(b):return hashlib.sha256(b).hexdigest()
def enc(v):return json.dumps(v,ensure_ascii=False,separators=(',',':')).encode()
def need(b,n):
    if not b:raise ValueError(n)
def block(v,name='',nl='\n'):
    return (('event: '+name+nl) if name else '')+'data: '+(v if isinstance(v,str) else enc(v).decode())+nl+nl

def sequence(fmt, final=None, origin=0):
    final=copy.deepcopy(final or nonstream_fixture(fmt)['records'][0]['response'])
    rid,model=final['id'],final['model']
    if fmt=='openai_chat':
        base={'id':rid,'model':model,'object':'chat.completion.chunk'}
        vals=[{**base,'choices':[{'index':0,'delta':{'role':'assistant'},'finish_reason':None}],'usage':None},
              {**base,'choices':[{'index':0,'delta':{'content':'PRIVATE_STREAM_BODY'},'finish_reason':'stop'}]}]
        if final.get('usage') is not None:vals.append({**base,'choices':[],'usage':final['usage']})
        return [(v,'') for v in vals]+[('[DONE]','')],final
    if fmt=='openai_responses':
        start={**final,'status':'in_progress','usage':None,'output':[]}
        item={'id':'item0','type':'message'}
        vals=[('response.created',{'response':start}),('response.in_progress',{'response':start}),
              ('response.output_item.added',{'output_index':0,'item':item}),
              ('response.content_part.added',{'output_index':0,'item_id':'item0','content_index':0,'part':{'type':'output_text','text':''}}),
              ('response.output_text.delta',{'output_index':0,'item_id':'item0','content_index':0,'delta':'PRIVATE_STREAM_BODY'}),
              ('response.output_text.done',{'output_index':0,'item_id':'item0','content_index':0,'text':'PRIVATE_STREAM_BODY'}),
              ('response.content_part.done',{'output_index':0,'item_id':'item0','content_index':0,'part':{'type':'output_text','text':'PRIVATE_STREAM_BODY'}}),
              ('response.output_item.done',{'output_index':0,'item':item}),
              ('response.'+final['status'],{'response':final})]
        return [({'type':t,'sequence_number':i+origin,**v},t) for i,(t,v) in enumerate(vals)],final
    usage=copy.deepcopy(final.get('usage') or {});u=usage.get('output_tokens')
    first={k:v for k,v in usage.items() if k not in ('output_tokens','output_tokens_details')}
    first['output_tokens']=min(u,1) if isinstance(u,int) else 1
    start={**final,'content':[],'stop_reason':None,'usage':first}
    updates={k:v for k,v in usage.items() if k in ('output_tokens','output_tokens_details')}
    if 'output_tokens' not in updates:final.setdefault('usage',{})['output_tokens']=None
    vals=[{'type':'message_start','message':start},{'type':'content_block_start','index':0,'content_block':{'type':'text','text':''}},
          {'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text':'PRIVATE_STREAM_BODY'}},
          {'type':'content_block_stop','index':0},
          {'type':'message_delta','delta':{'stop_reason':None},'usage':{'output_tokens':max(1,u//2) if isinstance(u,int) and u>0 else (0 if u==0 else None)}},
          {'type':'message_delta','delta':{'stop_reason':final['stop_reason'],'stop_sequence':None},'usage':updates},
          {'type':'message_stop'}]
    # If final output was omitted, intermediate updates must not fabricate it.
    if 'output_tokens' not in usage:vals[4]['usage']={}
    return [(v,v['type']) for v in vals],final

def fixture(fmt='openai_chat',final=None,origin=0,nl='\n'):
    expected=nonstream_fixture(fmt)
    frames,r=sequence(fmt,final,origin);expected['records'][0]['response']=r
    record=copy.deepcopy(expected['records'][0]);record.pop('response');record['stream']=''.join(block(v,n,nl) for v,n in frames)
    root={**copy.deepcopy(expected),'schema':'qbrain-stream-import-v1','records':[record]}
    return root,expected

def check_output(root,expected,out):
    need(out.get('schema')=='qbrain-stream-import-report-v1','stream result schema')
    need(out.get('stream_contract_validated') is True and out.get('response_content_validated') is False,'stream scope')
    observations=out['stream_observations'];need(len(observations)==len(root['records']),'observation count')
    for r,o in zip(sorted(root['records'],key=lambda r:r['call_id']),observations):
        need(set(o)=={'call_id','format','data_events','terminal','usage_source','sequence_origin'},'observation allowlist')
        need(o['call_id']==r['call_id'] and o['format']==r['format'],'observation identity')
        blocks=r['stream'].lstrip('\ufeff').replace('\r\n','\n').replace('\r','\n').split('\n\n')
        data=['\n'.join(line[5:].removeprefix(' ') for line in b.split('\n') if line.startswith('data:')) for b in blocks if any(line.startswith('data:') for line in b.split('\n'))]
        need(type(o['data_events']) is int and o['data_events']==len(data)<=4096,'observed event count')
        origin=json.loads(data[0])['sequence_number'] if r['format']=='openai_responses' else None
        need(o['sequence_origin']==origin and (origin is None or type(o['sequence_origin']) is int),'sequence origin')
        source='cumulative_message_delta' if r['format']=='anthropic_messages' else 'terminal_response' if r['format']=='openai_responses' else ('final_chunk' if len(data)>1 and json.loads(data[-2]).get('choices')==[] else 'absent')
        need(o['usage_source']==source,'usage source')
        need(o['terminal'] in ('[DONE]','response.completed','response.failed','response.incomplete','message_stop'),'terminal')
    reduced=copy.deepcopy(out)
    for k in ('stream_contract_validated','response_content_validated','stream_observations'):reduced.pop(k)
    reduced['schema']='qbrain-usage-import-report-v1';check_nonstream(expected,reduced)
    need('PRIVATE_STREAM_BODY' not in enc(out).decode(),'no stream body output')

def run(binary:Path,output:Path):
    output.mkdir(parents=True,exist_ok=False);rawdir=output/'raw';rawdir.mkdir()
    rows=[];checks=[];failure=None
    def check(ok,name):
        checks.append({'name':name,'passed':bool(ok)});need(ok,name)
    try:
      with tempfile.TemporaryDirectory(prefix='n48h-sse-') as temp:
        home=Path(temp)/'home';home.mkdir();(home/'sentinel').write_bytes(b'KEEP')
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
        env.update(HOME=str(home),USERPROFILE=str(home),LOCALAPPDATA=str(home),APPDATA=str(home))
        def invoke(root,expected=None,error=None,label='case',args=('cost','import-stream')):
            raw=root if isinstance(root,bytes) else enc(root);idx=len(rows);prefix=f'{idx:04d}'
            p=subprocess.run([str(binary),*args],input=raw,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,cwd=temp,timeout=10)
            for suffix,data in (('stdin',raw),('stdout',p.stdout),('stderr',p.stderr)):(rawdir/(prefix+'.'+suffix)).write_bytes(data)
            row={'case':label,'args':list(args),'exit':p.returncode,'hashes':dict(zip(('stdin','stdout','stderr'),map(sha,(raw,p.stdout,p.stderr)))),
                 'expected':expected,'error':error};rows.append(row)
            value=json.loads(p.stdout)
            if error is not None:
                check(p.returncode==2 and not p.stderr and set(value)=={'error'} and (error=='ANY' or value=={'error':{'code':error}}),'reject '+label)
            else:
                check(p.returncode==0 and not p.stderr,'success '+label)
                if args[-1]=='import-stream':check_output(json.loads(root) if isinstance(root,bytes) else root,expected,value)
            return value
        # Independent final-object equivalence under all line encodings and BOM/comments.
        for fmt in FORMATS:
            for nl in ('\n','\r','\r\n'):
                root,exp=fixture(fmt,nl=nl);out=invoke(root,exp,label=fmt+' newline '+repr(nl))
                wrapped=copy.deepcopy(root);wrapped['records'][0]['stream']='\ufeff: heartbeat'+nl+nl+wrapped['records'][0]['stream']+': ending'+nl+nl
                other=invoke(wrapped,exp,label=fmt+' BOM comments '+repr(nl));check(out==other,'comments do not affect output '+fmt+repr(nl))
            root,exp=fixture(fmt);out=invoke(root,exp,label=fmt+' canonical')
            raw=copy.deepcopy(root);raw['records'][0]['stream']=raw['records'][0]['stream'].replace('PRIVATE_STREAM_BODY','A different private reply 中文')
            check(invoke(raw,exp,label=fmt+' changed content')==out,'content-independent mapping '+fmt)
            piped=invoke(out['cost_input'],label=fmt+' pipe',args=('cost','report'))
            check(piped==out['cost_report'],'unchanged exact report pipeline '+fmt)
            for mask in range(16):
                final=nonstream_fixture(fmt)['records'][0]['response'];u=final['usage'];u.pop('total_tokens',None);u.pop('cache_creation',None)
                u.pop('output_tokens_details',None);u.pop('completion_tokens_details',None)
                if fmt=='anthropic_messages':
                    for i,k in enumerate(('input_tokens','cache_read_input_tokens','cache_creation_input_tokens','output_tokens')):
                        if mask&(1<<i):u.pop(k,None)
                else:
                    inp='prompt_tokens' if fmt=='openai_chat' else 'input_tokens';outputk='completion_tokens' if fmt=='openai_chat' else 'output_tokens';details='prompt_tokens_details' if fmt=='openai_chat' else 'input_tokens_details'
                    for i,k in ((0,inp),(3,outputk)):
                        if mask&(1<<i):u[k]=None
                    for i,k in ((1,'cached_tokens'),(2,'cache_write_tokens')):
                        if mask&(1<<i):u[details][k]=None
                r,e=fixture(fmt,final);invoke(r,e,label=fmt+' missing-mask '+str(mask))
            r,e=fixture(fmt);r['rates']=[];e['rates']=[];invoke(r,e,label=fmt+' absent prices')
            for outcome in ('failure','unknown'):
                r,e=fixture(fmt);r['records'][0]['outcome']=outcome;e['records'][0]['outcome']=outcome;invoke(r,e,label=fmt+' '+outcome+' costs retained')
        r,e=fixture('openai_responses',origin=1);invoke(r,e,label='Responses origin one')
        for status in ('failed','incomplete'):
            f=nonstream_fixture('openai_responses')['records'][0]['response'];f['status']=status
            r,e=fixture('openai_responses',f);r['records'][0]['outcome']='failure';e['records'][0]['outcome']='failure';invoke(r,e,label='terminal '+status)
            r['records'][0]['outcome']='success';invoke(r,error='usage_outcome_conflict',label='terminal '+status+' success claim')
        # Complete Chat with no tail must remain unknown, not become free.
        f=nonstream_fixture('openai_chat')['records'][0]['response'];f['usage']=None
        r,e=fixture('openai_chat',f);invoke(r,e,label='Chat valid end with missing usage')
        # A multiline data block must join lines as SSE specifies, not merge events.
        r,e=fixture();r['records'][0]['stream']=r['records'][0]['stream'].replace(',"model"',',\ndata: "model"');invoke(r,e,label='multiline SSE data')
        for fmt in FORMATS:
            root,exp=fixture(fmt);body=root['records'][0]['stream'];frames,_=sequence(fmt)
            changes=[('missing last', ''.join(block(v,n) for v,n in frames[:-1]),'stream_missing_terminal'),
                ('after terminal',body+block(frames[0][0],frames[0][1]),'stream_after_terminal'),
                ('missing final blank',body[:-1],'stream_unterminated_event'),
                ('missing final newline',body[:-2],'stream_unterminated_line'),
                ('raw nul',body+'\0','stream_nul'),('unsupported sse field','retry: 10\n\n'+body,'stream_sse_field'),
                ('duplicate event field','event: x\nevent: x\ndata: {}\n\n'+body,'stream_event_name'),
                ('event no data','event: x\n\n'+body,'stream_event_without_data'),
                ('invalid event json','data: {\n\n'+body,'stream_event_json'),
                ('duplicate ignored key','data: {"ignored":{"a":1,"a":2}}\n\n'+body,'stream_duplicate_key')]
            for name,b,err in changes:
                r=copy.deepcopy(root);r['records'][0]['stream']=b;invoke(r,error=err,label=fmt+' '+name)
            r=copy.deepcopy(root);r['records'].append(copy.deepcopy(r['records'][0]));invoke(r,error='cost_duplicate_call',label=fmt+' duplicate call')
            r=copy.deepcopy(root);second=copy.deepcopy(r['records'][0]);second['call_id']='two';r['records'].append(second);invoke(r,error='usage_duplicate_response',label=fmt+' duplicate response')
            r=copy.deepcopy(root);r['rates'][0]['model']='wrong';invoke(r,error='usage_rate_model_mismatch',label=fmt+' wrong model')
        def mutate(fmt,name,fn,error='ANY'):
            frames,final=sequence(fmt);fn(frames);root,_=fixture(fmt);root['records'][0]['stream']=''.join(block(v,n) for v,n in frames);return invoke(root,error=error,label=fmt+' '+name)
        mutate('openai_chat','tail before finish',lambda v:v.__setitem__(slice(0,2),[v[0]]),'stream_chat_unfinished_choice')
        mutate('openai_chat','second usage tail',lambda v:v.insert(-1,copy.deepcopy(v[-2])),'stream_chat_after_usage')
        mutate('openai_chat','mixed identity',lambda v:v[1][0].__setitem__('id','another'),'stream_identity_changed')
        mutate('openai_chat','usage in content',lambda v:v[0][0].__setitem__('usage',{}),'stream_chat_usage_position')
        mutate('openai_chat','duplicate choice',lambda v:v[0][0]['choices'].append(copy.deepcopy(v[0][0]['choices'][0])),'stream_chat_duplicate_choice')
        mutate('openai_chat','unfinished choice',lambda v:v[1][0]['choices'][0].__setitem__('finish_reason',None),'stream_chat_unfinished_choice')
        for value in (-1,True,1.5,32):mutate('openai_chat','bad choice '+str(value),lambda v,x=value:v[0][0]['choices'][0].__setitem__('index',x),'cost_quantity')
        for value in (2,-1,True,0.5):mutate('openai_responses','bad origin '+str(value),lambda v,x=value:v[0][0].__setitem__('sequence_number',x))
        mutate('openai_responses','gap',lambda v:v[4][0].__setitem__('sequence_number',8),'stream_sequence')
        mutate('openai_responses','repeat',lambda v:v[4][0].__setitem__('sequence_number',3),'stream_sequence')
        mutate('openai_responses','terminal model changed',lambda v:v[-1][0]['response'].__setitem__('model','wrong'),'stream_identity_changed')
        mutate('openai_responses','unsupported event',lambda v:v.__setitem__(4,({**v[4][0],'type':'response.audio.delta'},'response.audio.delta')),'stream_event_unsupported')
        mutate('openai_responses','event mismatch',lambda v:v.__setitem__(4,(v[4][0],'response.output_text.done')),'stream_event_mismatch')
        mutate('anthropic_messages','open block at delta',lambda v:v.pop(3),'stream_unclosed_block')
        mutate('anthropic_messages','duplicate start',lambda v:v.insert(1,copy.deepcopy(v[0])),'stream_repeated_start')
        mutate('anthropic_messages','orphan delta',lambda v:v[2][0].__setitem__('index',1),'stream_block_index')
        mutate('anthropic_messages','wrong delta type',lambda v:v[2][0]['delta'].__setitem__('type','thinking_delta'),'stream_delta_type')
        mutate('anthropic_messages','fallback',lambda v:v[1][0]['content_block'].__setitem__('type','fallback'),'stream_content_unsupported')
        mutate('anthropic_messages','decreased cumulative',lambda v:(v[-2][0]['usage'].pop('output_tokens_details',None),v[-2][0]['usage'].__setitem__('output_tokens',2)),'stream_usage_decreased')
        # Explicit null must not erase numeric history and permit a later decrease.
        def erase_then_decrease(v):
            v.insert(-2,({'type':'message_delta','delta':{},'usage':{'output_tokens':None}},'message_delta'))
            v[-2][0]['usage'].pop('output_tokens_details',None);v[-2][0]['usage']['output_tokens']=2
        mutate('anthropic_messages','null cannot erase lower bound',erase_then_decrease,'stream_usage_decreased')
        # An explicit null cannot hide a contradiction with earlier lower bounds.
        def hidden_lower(v):
            v[0][0]['response']['usage']={'input_tokens':100,'input_tokens_details':{'cached_tokens':30,'cache_write_tokens':0},'output_tokens':1}
            v[-1][0]['response']['usage']={'input_tokens':None,'input_tokens_details':{'cached_tokens':None,'cache_write_tokens':None},'output_tokens':5,'total_tokens':20}
        mutate('openai_responses','earlier input contradicts later total',hidden_lower,'stream_usage_lower_bound')
        def hidden_cache(v):
            v[0][0]['response']['usage']={'input_tokens':None,'input_tokens_details':{'cached_tokens':30,'cache_write_tokens':None}}
            v[-1][0]['response']['usage']={'input_tokens':20,'input_tokens_details':{'cached_tokens':None,'cache_write_tokens':None},'output_tokens':5}
        mutate('openai_responses','earlier cache contradicts later input',hidden_cache,'stream_usage_lower_bound')
        r,e=fixture('anthropic_messages');frames,f=sequence('anthropic_messages')
        # Preserve TTL detail not sent again; replace (never add) the sent count.
        frames[0][0]['message']['usage']['cache_creation_input_tokens']=0
        frames[0][0]['message']['usage']['cache_creation']['ephemeral_5m_input_tokens']=0
        frames[-2][0]['usage']['cache_creation_input_tokens']=20
        frames[-2][0]['usage']['cache_creation']={'ephemeral_5m_input_tokens':20}
        r['records'][0]['stream']=''.join(block(v,n) for v,n in frames)
        invoke(r,e,label='Anthropic sparse TTL detail merge')
        r,e=fixture('anthropic_messages');frames,_=sequence('anthropic_messages');frames[-2][0]['usage']=None
        r['records'][0]['stream']=''.join(block(v,n) for v,n in frames);e['records'][0]['response']['usage']={}
        invoke(r,e,label='Anthropic null usage invalidates earlier complete totals')
        # Exact parser/body/record/envelope caps, then one over each.
        r,e=fixture();body=r['records'][0]['stream'];padding=524288-len(body.encode())-2
        r['records'][0]['stream']=body+':'+('x'*padding)+'\n';invoke(r,e,label='exact stream byte cap')
        r['records'][0]['stream']+='\n';invoke(r,error='stream_body_limit',label='stream one byte over')
        r,e=fixture();raw=enc(r);invoke(raw+b' '*(4194304-len(raw)),e,label='exact envelope cap')
        invoke(raw+b' '*(4194305-len(raw)),error='stream_input_limit',label='envelope one byte over')
        r,e=fixture();r['records']=[];e['records']=[]
        for i in range(32):
            f=nonstream_fixture('openai_chat')['records'][0]['response'];f['id']='resp-'+str(i);a,b=fixture('openai_chat',f)
            a['records'][0]['call_id']=b['records'][0]['call_id']='call'+str(i);r['records'].append(a['records'][0]);e['records'].append(b['records'][0])
        invoke(r,e,label='32 streams');r['records'].append(copy.deepcopy(r['records'][0]));invoke(r,error='stream_record_count',label='33 streams')
        r,e=fixture('anthropic_messages');body=r['records'][0]['stream']
        r['records'][0]['stream']=block({'type':'ping'},'ping')*(4096-7)+body
        invoke(r,e,label='4096 actual events')
        r['records'][0]['stream']=block({'type':'ping'},'ping')+r['records'][0]['stream']
        invoke(r,error='stream_event_count',label='4097 actual events')
        invoke(b'{} {}',error='stream_invalid_json',label='second document')
        invoke(b'{"schema":0,"schema":1}',error='stream_duplicate_key',label='outer duplicate')
        invoke(b'',error='stream_invalid_action',label='extra command flag',args=('cost','import-stream','--repair'))
        check(sorted(p.name for p in home.iterdir())==['sentinel'] and (home/'sentinel').read_bytes()==b'KEEP','brain-free entire run')
    except Exception as e:failure=type(e).__name__+': '+str(e)
    result={'schema':'qbrain-n48h-process-v1','binary_sha256':sha(binary.read_bytes()),'script_sha256':sha(Path(__file__).read_bytes()),
        'passed':sum(r['passed'] for r in checks),'failed':sum(not r['passed'] for r in checks)+int(failure is not None and all(r['passed'] for r in checks)),
        'failure':failure,'checks':checks,'commands':len(rows),'records':rows,'platform':os.name,'provider_requests_sent':0,'real_response_used':False}
    (output/'report.json').write_bytes(enc(result)+b'\n');return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=run(a.binary.resolve(strict=True),a.output);print(json.dumps({k:v for k,v in r.items() if k not in ('checks','records')}));raise SystemExit(bool(r['failed']))
