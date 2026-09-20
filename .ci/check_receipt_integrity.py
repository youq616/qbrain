"""Read back all N47Y raw streams. Consistency check, not a new product execution."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re

CHECK_NAMES_SHA = 'a0f9da55433427660366a935138521c65fb62f66b1141cf2e06ab820c34e8648'
BASELINE_SOURCE = 'ad31f404ba5ca94b15dc992bf9f219fa572ab167'

def need(ok, why):
    if not ok: raise ValueError(why)
def sha(raw): return hashlib.sha256(raw).hexdigest()
def read(path, cap=2*1024*1024):
    need(path.is_file() and not path.is_symlink(),'regular_file')
    with path.open('rb') as f: raw=f.read(cap+1)
    need(len(raw)<=cap,'byte_limit');return raw
def decode(raw):
    def pairs(values):
        out={}
        for k,v in values:
            need(k not in out,'duplicate_key');out[k]=v
        return out
    def nonfinite(_): raise ValueError('nonfinite_number')
    return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=nonfinite)

def validate(r, directory, binary, baseline, script):
    need(isinstance(r,dict) and r.get('schema')=='qbrain-n47y-integrity-v1','schema')
    need(type(r.get('passed')) is int and r['passed']==123 and type(r.get('failed')) is int and r['failed']==0
         and r.get('failure') is None,'result')
    need(r.get('real_client_verified') is False and type(r.get('provider_calls')) is int and r['provider_calls']==0,'scope')
    need(r.get('baseline_source') in (None,BASELINE_SOURCE),'baseline_source')
    need(r.get('binary_sha256')==sha(binary) and r.get('baseline_sha256')==sha(baseline)
         and r.get('test_sha256')==sha(script),'component_identity')
    checks=r.get('checks')
    need(isinstance(checks,list) and len(checks)==123 and all(isinstance(x,dict) and set(x)=={'name','passed'}
         and x['passed'] is True for x in checks),'checks')
    names=json.dumps([x['name'] for x in checks],ensure_ascii=False,separators=(',',':')).encode()
    need(sha(names)==CHECK_NAMES_SHA,'check_coverage')
    expected=[{'case':'baseline_blob_disagreement','summary_exit':0,'page_exit':1,'retry_exit':0,'retry_duplicate':False,'resulting_rows':4}]
    need(r.get('observations')==expected,'baseline_control')
    commands=r.get('commands')
    need(isinstance(commands,list) and len(commands)==156 and type(r.get('command_count')) is int and r['command_count']==156,'commands')
    rawdir=directory/'raw'
    wanted={f'{i:04}.{suffix}' for i in range(1,157) for suffix in ('stdin','stdout','stderr')}
    need(rawdir.is_dir() and not rawdir.is_symlink() and {p.name for p in rawdir.iterdir()}==wanted,'raw_coverage')
    exits={0:0,1:0}
    for i,c in enumerate(commands,1):
        need(isinstance(c,dict) and set(c)=={'index','argv','baseline','exit','stdin_sha256','stdout_sha256','stderr_sha256'},'command_fields')
        need(type(c['index']) is int and c['index']==i and type(c['baseline']) is bool and
             type(c['exit']) is int and c['exit'] in (0,1) and isinstance(c['argv'],list) and
             c['argv'] and all(isinstance(x,str) for x in c['argv']),'command_record')
        streams={}
        for suffix in ('stdin','stdout','stderr'):
            raw=read(rawdir/f'{i:04}.{suffix}');streams[suffix]=raw
            need(c[suffix+'_sha256']==sha(raw),'stream_identity')
        expected_stderr = (b'[qbrain-serve] stdio MCP ready brain=integrity write=disabled\n'
                           b'[qbrain-serve] shutdown: stdin EOF\n') if c['argv']==['serve','--tool-profile','memory'] else b''
        need(streams['stderr'].replace(b'\r\n',b'\n')==expected_stderr,'unexpected_stderr')
        if c['exit']==1:
            error=decode(streams['stdout'])
            need(isinstance(error,dict) and set(error)=={'error'} and isinstance(error['error'],dict)
                 and set(error['error'])=={'code'} and isinstance(error['error']['code'],str),'error_shape')
        exits[c['exit']]+=1
    need(exits=={0: 77, 1: 79},'exit_coverage')
    return {'result':'RECEIPT_INTEGRITY_EVIDENCE_VERIFIED','checks':123,'commands':156,'raw_streams':468,
            'binary_sha256':sha(binary),'baseline_sha256':sha(baseline),'test_sha256':sha(script),
            'new_product_execution':False,'real_client_verified':False}

def negatives(r, directory, binary, baseline, script):
    passed=[]
    for name in ('count','bool-count','missing','duplicate','false','binary','baseline','script','client','extra-check','command-index','command-exit','raw-hash','control'):
        bad=copy.deepcopy(r)
        if name=='count': bad['passed']=124
        if name=='bool-count': bad['passed']=True
        if name=='missing': bad['checks'].pop()
        if name=='duplicate': bad['checks'][-1]=bad['checks'][0]
        if name=='false': bad['checks'][0]['passed']=False
        if name=='binary': bad['binary_sha256']='0'*64
        if name=='baseline': bad['baseline_sha256']='0'*64
        if name=='script': bad['test_sha256']='0'*64
        if name=='client': bad['real_client_verified']=True
        if name=='extra-check': bad['checks'][0]['secret']='not allowed'
        if name=='command-index': bad['commands'][0]['index']=True
        if name=='command-exit': bad['commands'][0]['exit']=2
        if name=='raw-hash': bad['commands'][0]['stdout_sha256']='0'*64
        if name=='control': bad['observations'][0]['retry_duplicate']=True
        try: validate(bad,directory,binary,baseline,script)
        except ValueError as e: passed.append({'case':name,'rejected':True,'reason':str(e)})
        else: raise ValueError('accepted_mutation_'+name)
    validate(r,directory,binary,baseline,script)
    return passed

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('directory','binary','baseline','test'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--negative-tests',action='store_true');a=p.parse_args()
    r=decode(read(a.directory/'report.json'))
    # Native EXE bytes are bounded separately from small JSON streams.
    args=(r,a.directory,read(a.binary,32*1024*1024),read(a.baseline,32*1024*1024),read(a.test))
    result=validate(*args)
    if a.negative_tests: result['negative_tests']=negatives(*args)
    print(json.dumps(result,ensure_ascii=False))
