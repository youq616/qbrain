"""Bound the N48A process report to exact files and independently check versioned definitions.
This checks stored test evidence; it is not an OpenCode host run or an authenticity proof.
"""
from pathlib import Path
import argparse,copy,hashlib,json,re

def need(ok,message):
    if not ok:raise ValueError(message)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def decode(raw):
    need(len(raw)<=2*1024*1024,'report_bound')
    def unique(pairs):
        result={}
        for k,v in pairs:
            need(k not in result,'duplicate_key');result[k]=v
        return result
    def invalid(_):raise ValueError('nonfinite_json')
    return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique,parse_constant=invalid)
def verify(r,binary,script):
    need(r.get('schema')=='qbrain-n48a-process-v1' and r.get('failure') is None,'report_status')
    expected=70 if r.get('platform')=='posix' else 68 if r.get('platform')=='nt' else None
    need(type(r.get('passed')) is int and r['passed']==expected and type(r.get('failed')) is int and r['failed']==0,'counts')
    need(r.get('binary_sha256')==sha(binary) and r.get('script_sha256')==sha(script),'file_identity')
    need(r.get('opencode_application_tested') is False and type(r.get('model_calls')) is int and r['model_calls']==0,'scope')
    checks=r.get('checks');need(isinstance(checks,list) and len(checks)==expected,'coverage')
    need(all(isinstance(x,dict) and set(x)=={'name','passed'} and x['passed'] is True and isinstance(x['name'],str) for x in checks),'check_shape')
    need(len({x['name'] for x in checks})==expected,'unique_check_names')
    calls=r.get('calls');need(isinstance(calls,list),'calls')
    configs=[x for x in calls if x.get('kind')=='generated-config'];need([x.get('format') for x in configs]==['v1','v2'],'version_coverage')
    for rec in configs:
        doc=decode(rec['configuration'].encode());mcp=doc['mcp'];v1=rec['format']=='v1'
        servers=mcp if v1 else mcp['servers'];need(len(servers)==1,'server_count');name,definition=next(iter(servers.items()))
        need(re.fullmatch('qbrain_[0-9a-f]{24}',name) is not None and definition==rec['definition'],'definition_identity')
        need(set(definition)=={'type','command','cwd','environment','timeout','enabled' if v1 else 'disabled'},'definition_fields')
        need(definition['type']=='local' and isinstance(definition['cwd'],str),'local_process')
        need(definition['command'][1:]==['serve','--brain','opencode-fixture','--tool-profile','memory'],'readonly_command')
        need(definition['environment']=={'QBRAIN_MCP_ALLOW_WRITE':'0'},'ambient_write_denial')
        if v1:need(definition['enabled'] is True and type(definition['timeout']) is int and definition['timeout']==10000,'v1_schema')
        else:
            need(definition['disabled'] is False and isinstance(definition['timeout'],dict) and set(definition['timeout'])=={'startup','catalog'},'v2_schema')
            need(all(type(n) is int and n==10000 for n in definition['timeout'].values()),'v2_timeout')
    protocols=[x for x in calls if x.get('kind')=='generated-mcp'];need(len(protocols)==3,'protocol_coverage')
    for i,call in enumerate(protocols):
        need(type(call['exit']) is int and call['exit']==0,'protocol_exit')
        replies=[decode(x.encode()) for x in call['stdout'].splitlines()];need([x.get('id') for x in replies]==[1,2,3],'reply_identity')
        need({x['name'] for x in replies[1]['result']['tools']}=={'memory_read','memory_write','context_read','context_write','search','get_page'},'six_tools')
        result=replies[2]['result'];need(result['isError'] is (i!=1),'write_permission_outcome')
        if i!=1:need(decode(result['content'][-1]['text'].encode())['error']['code']=='write_denied','write_denied_code')
    races=[x for x in calls if x.get('kind')=='concurrent'];need(len(races)==4 and sum(x['exit']==0 for x in races)==1,'race_control')
    return {'result':'PROCESS_EVIDENCE_VERIFIED','checks':expected,'config_versions':2,'generated_mcp_sessions':3,'binary_sha256':sha(binary),'native_windows':r['platform']=='nt','new_product_execution':False,'opencode_application_tested':False}
def negatives(r,binary,script):
    cases=[]
    for label in ('bool_count','missing_check','duplicate_check','failed','wrong_binary','host_claim','model_claim','legacy_v2_timeout','permission_environment','argv','wrong_reply','missing_config'):
        bad=copy.deepcopy(r)
        if label=='bool_count':bad['passed']=True
        if label=='missing_check':bad['checks'].pop()
        if label=='duplicate_check':bad['checks'][-1]=bad['checks'][0]
        if label=='failed':bad['failure']='not passed'
        if label=='wrong_binary':bad['binary_sha256']='0'*64
        if label=='host_claim':bad['opencode_application_tested']=True
        if label=='model_claim':bad['model_calls']=1
        if label in ('legacy_v2_timeout','permission_environment','argv'):
            cfg=next(x for x in bad['calls'] if x.get('kind')=='generated-config' and x['format']=='v2')
            doc=json.loads(cfg['configuration']);definition=next(iter(doc['mcp']['servers'].values()))
            if label=='legacy_v2_timeout':definition['timeout']=10000
            if label=='permission_environment':definition['environment']['QBRAIN_MCP_ALLOW_WRITE']='1'
            if label=='argv':definition['command'].append('--allow-write')
            cfg['definition']=definition;cfg['configuration']=json.dumps(doc)
        if label=='wrong_reply':
            call=next(x for x in bad['calls'] if x.get('kind')=='generated-mcp');msgs=[json.loads(x) for x in call['stdout'].splitlines()];msgs[-1]['result']['isError']=False;call['stdout']='\n'.join(json.dumps(x) for x in msgs)
        if label=='missing_config':bad['calls']=[x for x in bad['calls'] if x.get('kind')!='generated-config']
        try:verify(bad,binary,script)
        except (ValueError,KeyError,TypeError) as e:cases.append({'name':label,'rejected':True,'reason':str(e)})
        else:raise ValueError('accepted mutation '+label)
    verify(r,binary,script);return cases
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);p.add_argument('--binary',type=Path,required=True);p.add_argument('--test',type=Path,required=True);p.add_argument('--negatives',action='store_true');a=p.parse_args()
    r=decode(a.report.read_bytes());binary=a.binary.read_bytes();script=a.test.read_bytes();result=verify(r,binary,script)
    if a.negatives:result['negatives']=negatives(r,binary,script)
    print(json.dumps(result,sort_keys=True))
