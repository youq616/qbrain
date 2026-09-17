"""Offline, fixed N47J delivery readback. Never runs the product or publishes."""
from __future__ import annotations
import argparse
import hashlib
import importlib
import io
import json
from pathlib import Path
import re
import stat
import sys
import zipfile

SOURCE='2ec0c3daaa6d324bcc9f16a1ebacc88c63abe561'
TREE='37cfb0d5bd1df6501f0a42fe19d253e0e9e8b431'
RUN=35163779907
PINS={
 'source':(10473718781,'cff29f23d0b45fd721b8243d0c3840956a999cb70d50d82ee0f6d409c742a995'),
 'windows':(10474317394,'78381d0751738d2615a8c78fb8c925997f711cf226c67ebbefefa510f4a3d575'),
 'package':(10474292376,'3ec1a966b75d098fdc36222393652b6b702b53bf2db41196ea4b8e8fece80106'),
 'server2022':(10474240965,'d7291259587855742e8b0fa8974fba45ca6a8a93bc45e78f05fa1d6b27de9556'),
 'sanitizer':(10474195693,'6f4d8c5d352ffe58fa893a7f741a4d4fd59c64be18193336d3a3f5f67b80de10'),
 'portable':(10474018065,'46e4dcbec356cfb4a6d4db3538e1a45e7d5aa40cb9b117315c108685fbadebde')}
PACKAGE_SHA='778ddfde895a3f6a48b8b7d007d8a94f2b93a41639054b8c920687438444d0df'
EXE_SHA='6b99988be2b87aa5434f0e0da10d063da92ef596cda93a97739309259e91f694'
CAP=128*1024*1024
MAPPING=(
 ('hook-trace','validate_hook_trace_report','hook_trace','n47j',9,169,66,80),
 ('strict-json','validate_strict_json_report','strict_json','n47i',11,95,54,39),
 ('candidate','validate_lifecycle_candidate_report','lifecycle_candidate','n47h',17,647,43,63),
 ('batch','validate_lifecycle_batch_report','lifecycle_batch','n47g',15,259,40,54),
 ('fact-lifecycle','validate_fact_lifecycle_report','lifecycle','n47f',17,180,36,58),
 ('promotion','validate_promotion_report','promotion','n47e',18,237,68,77),
 ('hook-fact','validate_hook_fact_report','hook_fact','n47d',13,229,52,72),
 ('recall','validate_recall_report','recall','n47c',15,330,44,71),
 ('conflict','validate_conflict_report','conflict','n47b',13,346,38,75))

def require(ok, message):
    if not ok: raise ValueError(message)

def sha(raw): return hashlib.sha256(raw).hexdigest()

def obj(raw):
    def unique(pairs):
        d={}
        for k,v in pairs:
            require(k not in d,'duplicate JSON key');d[k]=v
        return d
    def bad_number(_):raise ValueError('nonfinite JSON')
    d=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique,parse_constant=bad_number)
    require(isinstance(d,dict),'not a JSON object');return d

def unzip(raw):
    require(len(raw)<=CAP,'archive byte cap')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        rows=z.infolist()
        require(0<len(rows)<=2000 and sum(i.file_size for i in rows)<=CAP,'archive expansion cap')
        require(len(rows)==len({i.orig_filename for i in rows}),'duplicate archive name')
        for i in rows:
            n=i.orig_filename
            require(n==i.filename and not n.startswith('/') and '\\' not in n and ':' not in n and
                    all(x not in ('','.','..') for x in n.rstrip('/').split('/')),'unsafe archive name')
            require(not i.flag_bits&1 and stat.S_IFMT(i.external_attr>>16) in
                    (0,stat.S_IFREG,stat.S_IFDIR),'nonregular/encrypted member')
        return {i.filename:z.read(i) for i in rows if not i.is_dir()}

def source_tree(files):
    root={}
    def oid(kind,raw):return hashlib.sha1(kind+b' '+str(len(raw)).encode()+b'\0'+raw).digest()
    for path,raw in files.items():
        node=root;parts=path.split('/')
        for part in parts[:-1]:
            node=node.setdefault(part,{})
            require(isinstance(node,dict),'source path collision')
        require(parts[-1] not in node,'source duplicate');node[parts[-1]]=raw
    def tree(node):
        entries=[]
        for name,value in node.items():
            directory=isinstance(value,dict);key=name.encode('utf-8')
            entries.append((key+(b'/' if directory else b''),
                (b'40000' if directory else b'100644')+b' '+key+b'\0'+
                (tree(value) if directory else oid(b'blob',value))))
        return oid(b'tree',b''.join(row for _,row in sorted(entries)))
    return tree(root).hex()

def verify(candidate,artifacts):
    checks=[]
    def check(ok,label):require(ok,label);checks.append(label)
    archives={}
    for name,(_,digest) in PINS.items():
        with (artifacts/(name+'.zip')).open('rb') as stream:raw=stream.read(CAP+1)
        check(sha(raw)==digest,'external artifact hash: '+name)
        archives[name]=unzip(raw)
    source=unzip(archives['source']['qbrain-source.zip'])
    check(len(source)==848 and source_tree(source)==TREE,'exact 848-file source tree')
    # Imports below execute only these byte-verified original validator scripts.
    check(all((candidate/p).read_bytes()==raw for p,raw in source.items()),'candidate equals complete pinned source')
    def checkout(path,digest):
        raw=source[path]
        check(digest in (sha(raw),sha(raw.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))),'source checkout: '+path)
    outer=archives['package']
    check(set(outer)=={'qbrain-windows-x64-development.zip','SHA256SUMS.txt'},'outer package members')
    raw=outer['qbrain-windows-x64-development.zip']
    check(len(raw)==2071649 and sha(raw)==PACKAGE_SHA,'original package identity')
    check(outer['SHA256SUMS.txt'].decode('ascii').split()==[PACKAGE_SHA,'qbrain-windows-x64-development.zip'],'outer checksum')
    files=unzip(raw);m=obj(files['MANIFEST.json']);v=obj(files['verification/validation.json'])
    check(set(files)==set(m['files'])|{'MANIFEST.json','README-FIRST.txt'},'complete inventory')
    for path,meta in m['files'].items():
        check(type(meta.get('bytes')) is int and meta['bytes']==len(files[path]) and meta['sha256']==sha(files[path]),'file hash/size: '+path)
        if path.startswith('verification/') and path.endswith('.json'):
            check(files[path]==archives['windows'][Path(path).name],'original native report bytes: '+path)
    check(len(files['qbrain.exe'])==4038656 and sha(files['qbrain.exe'])==EXE_SHA,'product executable identity')
    for r in (m,v):
        check(r['result']=='PASS' and r['source_commit']==SOURCE and r['binary_sha256']==EXE_SHA and
              type(r['registered_groups']) is int and r['registered_groups']==58,'manifest source and 58 groups')
        check(r['signed'] is False and r['real_host_model_consumption_verified'] is False and
              r['postgres_memory_context_verified'] is False,'unverified scope remains unverified')
    sys.path.insert(0,str((candidate/'.ci').resolve()))
    from validate_native_log import verified_groups
    from validate_http_lifecycle import validate_report as http
    from validate_fact_report import validate_unit_report as fu,validate_report as fp
    from validate_cjk_report import validate_report as cjk
    groups=verified_groups(source['tests/test_main.cpp'].decode('utf-8'),archives['windows']['regression.log'].decode('utf-8-sig'),58)
    checks.append('all native registry names matched')
    check('SKIP-PG' in archives['windows']['regression.log'].decode('utf-8-sig'),'real PG cases remain skipped')
    summaries={}
    for platform in ('windows','server2022','portable','sanitizer'):
        native=platform in ('windows','server2022');logs=archives[platform];summaries[platform]={}
        rows=MAPPING if platform!='sanitizer' else MAPPING[:4]
        # Every listed unit is mandatory; every process is mandatory outside Server2022.
        for prefix,module,script,test,scenarios,assertions,pcs,commands in rows:
            mod=importlib.import_module(module);u=obj(logs[prefix+'-unit.json'])
            checkout('tests/test_'+test+'.cpp',u['test_sha256']);checkout('.ci/test_'+script+'_unit.py',u['script_sha256'])
            result=mod.validate_unit(u,source_commit=SOURCE,binary_sha256=u['binary_sha256'],script_sha256=u['script_sha256'],test_sha256=u['test_sha256'],native=native)
            check(result=={'scenarios':scenarios,'assertions':assertions} and u.get('source_tree')==TREE and
                  u.get('native_windows') is native,'full unit evidence: '+platform+'/'+prefix)
            summaries[platform][prefix+'-unit']=result
            if platform!='server2022':
                p=obj(logs[prefix+'-process.json']);checkout('.ci/test_'+script+'_process.py',p['script_sha256'])
                result=mod.validate_process(p,source_commit=SOURCE,binary_sha256=EXE_SHA if native else p['binary_sha256'],script_sha256=p['script_sha256'],native=native)
                check(result=={'checks':pcs,'commands':commands} and p.get('source_tree')==TREE and
                      p.get('native_windows') is native,'full process evidence: '+platform+'/'+prefix)
                summaries[platform][prefix+'-process']=result
        if native:
            h=obj(logs['http-lifecycle.json'])
            summaries[platform]['http-lifecycle']=http(h,source_commit=SOURCE,probe_hashes={n:h['variants'][n]['sha256'] for n in ('legacy','per_call','current')})
            checks.append('full fixed HTTP lifecycle and shutdown: '+platform)
            h=obj(logs['http-transport.json'])
            check(h['result']=='PASS' and h['source_commit']==SOURCE and h['native_windows'] is True and
                  h['check_count']==len(h['checks'])==81,'native HTTP wire: '+platform)
        if platform in ('windows','portable'):
            u=obj(logs['fact-unit.json']);checkout('tests/test_n47a.cpp',u['test_sha256'])
            names=re.findall(r'scenario\("([^"\r\n]+)"',source['tests/test_n47a.cpp'].decode('utf-8'))
            fu(u,source_commit=SOURCE,binary_sha256=u['binary_sha256'],test_sha256=u['test_sha256'],expected_scenarios=names,native=native)
            p=obj(logs['fact-process.json']);checkout('.ci/test_fact_process.py',p['script_sha256'])
            fp(p,source_commit=SOURCE,binary_sha256=EXE_SHA if native else p['binary_sha256'],script_sha256=p['script_sha256'],native=native)
            checks.append('full old fact evidence: '+platform)
            p=obj(logs['cjk-recall.json']);checkout('.ci/test_cjk_recall.py',p['script_sha256'])
            cjk(p,source_commit=SOURCE,binary_sha256=EXE_SHA if native else p['binary_sha256'],script_sha256=p['script_sha256'])
            checks.append('full CJK evidence: '+platform)
    for prefix,module,script in [('promotion','validate_promotion_report','test_promotion_install.ps1'),('hook-fact','validate_hook_fact_report','test_hook_fact_install.ps1')]:
        for suffix,major in [('51',5),('7',7)]:
            r=obj(archives['windows'][prefix+'-install'+suffix+'.json'])
            checkout('.ci/'+script,r['script_sha256']);checkout('scripts/Install-QbrainMemory.ps1',r['installer_sha256'])
            importlib.import_module(module).validate_install(r,source_commit=SOURCE,binary_sha256=EXE_SHA,script_sha256=r['script_sha256'],installer_sha256=r['installer_sha256'],shell_major=major)
            checks.append('full opt-in installer report: '+prefix+suffix)
    for path in ('scripts/Install-QbrainMemory.ps1','scripts/Invoke-QbrainJson.ps1'):
        checkout(path,sha(files[path]))
    checkout('docs/integration/HOOK-DIAGNOSTIC-CHECKPOINTS.zh-CN.md',sha(files['HOOK-DIAGNOSTIC-CHECKPOINTS.zh-CN.md']))
    for name,text in [('memory_cycle.log','44 checks passed'),('mcp_boundaries.log','17 checks passed'),('hooks.log','69 passed'),('context_process.log','65 passed'),('local-config.log','6 checks passed'),('install51.log','69 checks passed'),('install7.log','69 checks passed'),('transport51.log','8 checks passed'),('transport7.log','8 checks passed'),('consent51.log','16 checks passed'),('consent7.log','16 checks passed')]:
        check(text in archives['windows'][name].decode('utf-8-sig'),'retained native log: '+name)
    return {'result':'PASS','scope':'Fixed artifact readback; not new native execution or host consumption',
        'source_commit':SOURCE,'source_tree':TREE,'product_run':RUN,'check_count':len(checks),'checks':checks,
        'native_registered_groups':len(groups),'report_summaries':summaries,
        'package':{'bytes':2071649,'sha256':PACKAGE_SHA},'exe':{'bytes':4038656,'sha256':EXE_SHA},
        'probe_binaries_separately_downloaded':False,'signed':False,'product_executed_by_verifier':False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--artifacts',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('report must be a new path')
    r=verify(a.source,a.artifacts)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    with a.report.open('x',encoding='utf-8') as out:json.dump(r,out,indent=2,ensure_ascii=False);out.write('\n')
    print(json.dumps({'result':r['result'],'source_commit':SOURCE,'checks':r['check_count']}))

if __name__=='__main__':main()
