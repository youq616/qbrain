"""Offline supplemental MCP record checks, not a new client/engine execution.

Use the matching exact EXE/test files. This verifies supplied content and cannot
observe destroyed test databases or authenticate a caller's self-reported results.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path


def require(ok, why):
    if not ok:
        raise ValueError(why)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def names():
    rows=['authorized MCP can read valid receipt set','authorized MCP valid retry is read-identical',
          'MCP advertises receipt filter and snapshot as strings']
    rows += ['healthy MCP filter '+s+' matches selected IDs without mutation' for s in ('all','current','historical','withdrawn')]
    for mask in range(1,8):
        rows += [f'alias-{mask:03b}/{r}: reject without row schema or backup change' for r in ('summary','page','new_report','duplicate_report','revoke')]
        rows += [f'alias-{mask:03b}/restore: exact healthy state']
    for r in ('new_report','duplicate_report','revoke'):
        rows += [r+'/writer-lock: operation has no early result',r+'/writer-release: newly committed corruption rejected without write',
                 r+'/recovery: server remains usable after restored fixture']
    rows += ['revoke-abort: rollback preserves receipt and all other rows','revoke-after-abort: original receipt still withdrawable',
             'post-revoke retry never resurrects a valid tombstone','healthy MCP first page yields an actual continuation',
             'healthy MCP snapshot continuation returns the exact complete ID set read-only']
    rows += ['MCP rejects '+n+' without loosening validation or writing' for n in ('filter-boolean','snapshot-boolean','snapshot-integer','unknown-field',
              'invalid-filter','missing-pair','wrong-snapshot','wrong-view')]
    return rows+['server shutdown exits cleanly after all boundary probes']


def verify(r, binary, script):
    require(isinstance(r,dict) and r.get('schema')=='qbrain-n47y-boundary-v1','schema')
    require(type(r.get('passed')) is int and r['passed']==72 and type(r.get('failed')) is int and r['failed']==0 and r.get('failure') is None,'result')
    require(r.get('binary_sha256')==digest(binary) and r.get('script_sha256')==digest(script),'identity')
    require(r.get('real_client_verified') is False and type(r.get('provider_calls')) is int and r['provider_calls']==0,'scope')
    require(r.get('checks')==[{'name':n,'passed':True} for n in names()] and all(x['passed'] is True for x in r['checks']),'coverage')
    records=r.get('records');require(isinstance(records,list) and len(records)==74,'records')
    require([x.get('kind') for x in records]==['cli']*8+['mcp']*65+['mcp-exit'],'record_order')
    require(all(type(x.get('exit')) is int and x['exit']==0 and x.get('stderr')=='' for x in records[:8]),'cli_setup')
    require(type(records[-1].get('exit')) is int and records[-1]['exit']==0,'exit')
    calls={}
    for i,row in enumerate(records[8:-1],1):
        q,p=row['request'],row['response']
        require(type(q.get('id')) is int and q['id']==i and type(p.get('id')) is int and p['id']==i
                and q.get('jsonrpc')=='2.0' and p.get('jsonrpc')=='2.0','rpc_identity')
        require('error' not in p and isinstance(p.get('result'),dict),'rpc_envelope')
        if i in (1,4):
            require(q['method']==('initialize' if i==1 else 'tools/list'),'control_method')
            if i==4:
                tools=p['result']['tools'];schema=next(t['inputSchema'] for t in tools if t['name']=='memory_read')
                require(all(schema['properties'][k]['type']=='string' for k in ('receipt_state','snapshot')),'advertisement')
            continue
        require(q['method']=='tools/call' and type(p['result'].get('isError')) is bool,'rpc_result')
        body=json.loads(p['result']['content'][-1]['text']);calls[i]=(q['params']['arguments'],p['result']['isError'],body)
    expected_errors={i:'fact_usage_invalid_metadata' for i in list(range(9,44))+[44,46,48]}
    expected_errors.update({50:'memory_storage_error',52:'fact_usage_withdrawn',**{i:'invalid_argument' for i in range(58,62)},
        62:'fact_usage_invalid_filter',63:'fact_usage_cursor_pair_required',64:'fact_usage_snapshot_conflict',65:'fact_unexpected_argument'})
    for i,(args,error,body) in calls.items():
        require(error==(i in expected_errors),'expected_outcome')
        if error: require(body.get('error',{}).get('code')==expected_errors[i],'error_code')
    for i in (3,45,47,49):require(calls[i][2].get('duplicate') is True,'duplicate_result')
    for i in (51,53,54):require(calls[i][2].get('duplicate') is False,'first_write_result')
    require(calls[51][2].get('status')=='withdrawn','withdrawal_result')
    uid='1'*64
    for i,selected in zip(range(5,9),('all','current','historical','withdrawn')):
        args,_,page=calls[i]
        require(args['receipt_state']==page['receipt_state']==selected and page['has_more'] is False,'filter')
        require([x['usage_id'] for x in page['items']]==([uid] if i in (5,6) else []),'filtered_ids')
    token=calls[55][2]['snapshot'];last=None
    for i,rid in zip((55,56,57),('1'*64,'2'*64,'3'*64)):
        args,_,page=calls[i]
        require(page['snapshot']==token and page['matched_receipts']==3 and page['receipt_state']=='all'
            and page['has_more'] is (i!=57) and page['next_after_id']==(rid if i!=57 else None),'page_metadata')
        require(len(page['items'])==1 and page['items'][0]['usage_id']==rid
                and page['items'][0]['state']==('withdrawn' if i==55 else 'current'),'page_contents')
        if last is not None:require(args['after_id']==last and args['snapshot']==token,'cursor_pair')
        last=rid
    for i in (5,6,7,8,55,56,57):
        require(calls[i][2]['origin']=='caller_reported' and calls[i][2]['host_consumption_verified'] is False,'page_scope')
    return {'result':'MCP_BOUNDARY_RECORDS_VERIFIED','checks':72,'cli_calls':8,'mcp_requests':65,
            'valid_pages':7,'corrupt_set_rejections':38,'new_product_execution':False,'real_client_verified':False}


def negatives(r, binary, script):
    out=[]
    for label in ('count','bool-count','missing-check','case-order','script','true-client','rpc-id','wrong-error','page-id','wrong-token','retry-as-new','false-exit'):
        bad=copy.deepcopy(r)
        if label=='count':bad['passed']=73
        if label=='bool-count':bad['passed']=True
        if label=='missing-check':bad['checks'].pop()
        if label=='case-order':bad['checks'].reverse()
        if label=='script':bad['script_sha256']='0'*64
        if label=='true-client':bad['real_client_verified']=True
        if label=='rpc-id':bad['records'][8]['response']['id']=2
        if label in ('wrong-error','page-id','wrong-token','retry-as-new'):
            index={'wrong-error':9,'page-id':56,'wrong-token':56,'retry-as-new':3}[label]
            record=bad['records'][index+7]['response']['result'];body=json.loads(record['content'][-1]['text'])
            if label=='wrong-error':body['error']['code']='fact_not_found'
            if label=='page-id':body['items'][0]['usage_id']='9'*64
            if label=='wrong-token':body['snapshot']='9'*64
            if label=='retry-as-new':body['duplicate']=False
            record['content'][-1]['text']=json.dumps(body)
        if label=='false-exit':bad['records'][-1]['exit']=False
        try:verify(bad,binary,script)
        except (ValueError,KeyError,TypeError) as e:out.append({'case':label,'rejected':True,'error':str(e)})
        else:raise ValueError('mutation accepted: '+label)
    verify(r,binary,script)
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('report','binary','test'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--negatives',action='store_true');a=p.parse_args()
    report=json.loads(a.report.read_bytes());binary=a.binary.read_bytes();script=a.test.read_bytes()
    result=verify(report,binary,script)
    if a.negatives:result['negatives']=negatives(report,binary,script)
    print(json.dumps(result,sort_keys=True))
