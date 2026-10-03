"""Fixed N49D native stages, bounded evidence recording and artifact consumption.

The generic inherited ZIP format is transport only, not historical qualification.
No historical source, phase, fixture or probe qualifier is imported or called.
"""
from __future__ import annotations

import argparse
import ast
import base64
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
import xml.etree.ElementTree as ET

import check_n49d_sources as source_guard

MIB = 1024 * 1024
LIMITS = dict(compressed=20*MIB, manifest=512*1024, raw=160*MIB, members=4096,
              outer=21*MIB-1, staging=110*MIB, text=6*MIB, reserve=150*MIB)
JOBS = ('linux-cmake', 'windows-cmake', 'windows-msvc', 'linux-sanitizers')
TARGETS = ('qbrain_mcp_directory_search_tests', 'qbrain_directory_search_tests',
           'qbrain_memory_tests', 'qbrain_context_tests', 'qbrain_http_tests',
           'qbrain_retrieval_tests', 'qbrain_embedding_tests', 'qbrain_embedding_queue_tests',
           'qbrain_cjk_tests', 'qbrain_recall_tests', 'qbrain_strict_json_tests', 'qbrain_multiterm_tests')
TESTS = ('qbrain_mcp_directory_search_unit', 'qbrain_directory_search_unit',
         'qbrain_memory_unit', 'qbrain_context_unit', 'qbrain_http_input_unit',
         'qbrain_retrieval_unit', 'qbrain_embedding_unit', 'qbrain_embedding_queue_unit',
         'qbrain_cjk_unit', 'qbrain_recall_unit', 'qbrain_strict_json_unit', 'qbrain_multiterm_unit')
DRIVERS = ('mcp_directory_search', 'directory_search', 'context_process', 'hooks', 'memory_cycle', 'named_arguments')
BLOCKED = re.compile(r'^(QBRAIN|PG|CURSOR|OPENAI|ANTHROPIC|GH_TOKEN|GITHUB_TOKEN|AWS_|AZURE_|GOOGLE_|GCP_|ZHIPU|GEMINI|COHERE|MISTRAL|DEEPSEEK|HF_|HUGGINGFACE|OPENROUTER|GIT_CONFIG_)|(?:^|_)(?:API_KEY|TOKEN|SECRET|PASSWORD|PASSWD|DSN|DATABASE_URL)(?:_|$)', re.I)
ROOT = Path(__file__).resolve().parents[1]
need = source_guard.need


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        while data := f.read(MIB):
            h.update(data)
    return h.hexdigest()


def dump(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def descriptor(path):
    p = Path(path)
    need(p.is_file() and not p.is_symlink(), 'required regular file missing')
    return dict(size=p.stat().st_size, sha256=digest(p))


def same_identity(value, expected):
    need(type(value) is dict and type(expected) is dict, 'identity object type')
    need(set(value)==set(expected)=={'commit','tree','run_id','run_attempt','job_key','job_label'},'candidate/job/run identity mismatch')
    need(all(type(v) is str and v for v in [*value.values(),*expected.values()]),'identity strings required')
    need(value==expected,'candidate/job/run identity mismatch')
    need(all(re.fullmatch('[0-9a-f]{40}', value[k]) for k in ('commit','tree')), 'invalid candidate identity')
    need(all(re.fullmatch('[0-9]{1,20}',value[k]) for k in ('run_id','run_attempt')), 'invalid run identity')
    need(value['job_key'] in JOBS and value['job_label'] == value['job_key'], 'unknown job')


# The five build roles are fixed here, never inferred from a command or image.
TRUSTED_BUILD = frozenset({('windows-cmake','configure'),('windows-cmake','build'),
    ('windows-cmake','canonical-build'),('windows-msvc','direct-production'),('windows-msvc','direct-tests-build')})
WINDOWS_PHASE_CONTROL_NAMES = {'windows-actual-wrapper-dispatch-parser-exit'} | {
    'build-native-'+a+'-'+b+'-'+c for a in ('owner','recorder') for b in ('inherited','redirected','late') for c in ('strict-v1','trusted-build-v1')}
PHASE_REPORTS = {
    'objects':('reports/direct-production-objects.json','qbrain-n49d-build-objects-v1',12*1024),
    'build-context':('reports/direct-tests-build-context.json','qbrain-n49d-build-context-v1',2*1024),
    'run-context':('reports/direct-tests-run-context.json','qbrain-n49d-run-context-v1',2*1024),
    'pair':('reports/direct-tests-pair.json','qbrain-n49d-build-test-pair-v1',4*1024),
    'configure':('reports/configure-readiness.json','qbrain-n49d-configure-readiness-v1',8*1024)}
PRODUCTION_OBJECTS = tuple(sorted(n+'.obj' for n in (
    'paths hash log string_util time_util database migrate pg_backend transaction_state types brain '
    'extract traverse analytics scan astlite packs lint store image_meta vector rrf hybrid directory rerank minions embedding_queue dream '
    'chunker markdown import http_client embed chat registry handlers memory_ops session_memory fact_store hook diagnostics context context_ops '
    'inbox_watch live_sync jsonrpc server auth http_server app commands main sqlite3').split()))
CONSUMED_OBJECTS = tuple(n for n in PRODUCTION_OBJECTS if n not in ('app.obj','main.obj'))
CONFIGURE_FILES = tuple(sorted(('CMakeCache.txt','qbrain.sln','qbrain.vcxproj','qbrain_tests.vcxproj','qbrain_http_probe.vcxproj',
                                *(t+'.vcxproj' for t in TARGETS))))
CONFIGURE_CHECKS = ('home_matches','build_matches','project_qbrain','generator_matches','debug_requested',
                    'debug_available','pg_off','overlay_matches','inputs_regular')
PHASE_KEYS = {
    'objects':'schema state identity produced consumed production_executable failure',
    'build-context':'schema state identity mode architecture cwd_role vcvars runtime_prefix production_objects production_executable canonical_binary failure',
    'run-context':'schema state identity mode build_context canonical_binary context_matched test_exit failure',
    'configure':'schema state identity source_location build_location overlay_location generator checks files failure',
    'pair':'schema state identity pair_budget_us build_budget_us run_budget_us build run finalize_begin_us failure'}
PHASE_FAILURES = {
    'objects':'missing-object object-type object-inventory object-changed binary-unavailable deadline storage',
    'build-context':'input-invalid context-mismatch object-mismatch compile-failed copy-failed binary-unavailable binary-mismatch deadline storage',
    'run-context':'input-invalid context-mismatch binary-mismatch launch-failed test-nonzero deadline storage',
    'configure':'cache-unavailable cache-limit cache-syntax cache-duplicate cache-value generated-input deadline storage',
    'pair':'build-failed run-failed handoff-failed pair-finalization-timeout pair-report-unavailable'}
BUILD_PROOF_KEYS = ('schema policy state reason root_exit root_observed_us teardown_requested termination_requested_us '
    'termination_succeeded empty_observed_us close_attempted_us close_returned_us streams_finalized_us success_deadline_us '
    'close_attempted close_returned close_in_budget').split()
BUILD_TIMES = ('root_observed_us','termination_requested_us','empty_observed_us','close_attempted_us',
               'close_returned_us','streams_finalized_us','success_deadline_us')


def exact_keys(value, keys, reason='report key inventory'):
    need(type(value) is dict and set(value)==set(keys.split() if type(keys) is str else keys),reason)


def uint(value):
    need(type(value) is int and 0<=value<=9007199254740991,'report unsigned integer')


def report_descriptor(value, path=False):
    exact_keys(value,'bytes sha256' if path else 'size sha256')
    number=value['bytes' if path else 'size'];uint(number)
    need(number>0 and (not path or number<=131072),'report descriptor size')
    need(type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['sha256']) is not None,'report descriptor digest')


def json_unique(raw):
    def pairs(rows):
        result={}
        for key,value in rows:
            need(key not in result,'duplicate JSON key');result[key]=value
        return result
    def constant(value):raise ValueError('nonstandard JSON number')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=constant)


def canonical_phase_bytes(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n').encode('ascii')


def phase_report(role,value,identity,ready=False):
    need(role in PHASE_REPORTS,'unknown phase report role')
    exact_keys(value,PHASE_KEYS[role]);same_identity(value['identity'],identity)
    need(value['schema']==PHASE_REPORTS[role][1] and type(value['state']) is str,'phase report schema')
    need(identity['job_key']==('windows-cmake' if role=='configure' else 'windows-msvc'),'phase report job')
    state=value['state'];complete='complete' if role=='pair' else 'ready'
    need(state in ('prepared','failed',complete),'phase report state')
    if ready:need(state==complete,'phase report not ready')
    need(value['failure'] is None if state!='failed' else
         type(value['failure']) is str and value['failure'] in PHASE_FAILURES[role].split(),'phase report failure reason')
    def optional(key,path=False):
        if value[key] is not None:report_descriptor(value[key],path)
    if role=='objects':
        need(type(value['produced']) is list and type(value['consumed']) is list,'object inventory arrays')
        if state=='ready':
            need(len(value['produced'])==53 and value['consumed']==list(CONSUMED_OBJECTS) and
                 all(type(n) is str for n in value['consumed']),'object inventory mismatch')
            for row,name in zip(value['produced'],PRODUCTION_OBJECTS):
                exact_keys(row,'name size sha256');need(type(row['name']) is str and row['name']==name,'object basename mismatch')
                report_descriptor({k:row[k] for k in ('size','sha256')})
            report_descriptor(value['production_executable'])
        else:need(value['produced']==[] and value['consumed']==[] and value['production_executable'] is None,'partial object inventory')
    elif role=='build-context':
        need(value['mode']=='build-only' and value['architecture']=='x64' and value['cwd_role']=='build/cl','build context constants')
        v=value['vcvars'];r=value['runtime_prefix']
        if v is not None:
            exact_keys(v,'path file');report_descriptor(v['path'],True);report_descriptor(v['file'])
        if r is not None:
            exact_keys(r,'present identity');need(type(r['present']) is bool,'runtime presence type')
            if r['present']:report_descriptor(r['identity'],True)
            else:need(r['identity'] is None,'runtime absence identity')
        for key in ('production_objects','production_executable','canonical_binary'):optional(key)
        if state=='ready':need(all(value[k] is not None for k in ('vcvars','runtime_prefix','production_objects','production_executable','canonical_binary')),'build observations missing')
    elif role=='run-context':
        need(value['mode']=='run-only','run context mode')
        optional('build_context');optional('canonical_binary')
        if state=='ready':
            need(value['build_context'] is not None and value['canonical_binary'] is not None and
                 value['context_matched'] is True and type(value['test_exit']) is int and value['test_exit']==0,'run context success')
        else:need(value['context_matched'] is None and value['test_exit'] is None,'partial run claims completion')
    elif role=='configure':
        for key in ('source_location','build_location','overlay_location'):optional(key,True)
        exact_keys(value['checks'],CONFIGURE_CHECKS)
        need(type(value['files']) is dict,'configure file inventory type')
        if state=='ready':
            need(all(value[k] is not None for k in ('source_location','build_location','overlay_location')) and
                 value['generator']=='vs17-2022' and all(v is True for v in value['checks'].values()),'configure readiness facts')
            exact_keys(value['files'],CONFIGURE_FILES)
            for v in value['files'].values():report_descriptor(v)
        else:
            need(value['generator'] is None and all(v is None for v in value['checks'].values()) and value['files']=={},'partial configure claims readiness')
    else:
        for key,expected in (('pair_budget_us',1800000000),('build_budget_us',1200000000),('run_budget_us',600000000)):
            need(type(value[key]) is int and value[key]==expected,'pair fixed budget')
        for key,name in (('build','direct-tests-build'),('run','direct-tests-run')):
            entry=value[key]
            if entry is not None:
                exact_keys(entry,'stage start_us end_us effective_deadline_us result')
                need(entry['stage']==name,'pair stage role')
                for field in ('start_us','end_us','effective_deadline_us'):uint(entry[field])
                report_descriptor(entry['result'])
        if state=='complete':
            b,r=value['build'],value['run'];uint(value['finalize_begin_us'])
            need(b is not None and r is not None and
                 0==b['start_us']<=b['end_us']<=r['start_us']<=r['end_us']<=value['finalize_begin_us']<1800000000 and
                 b['effective_deadline_us']==1200000000 and b['end_us']<1200000000 and
                 r['effective_deadline_us']==min(r['start_us']+600000000,1800000000) and
                 r['end_us']<r['effective_deadline_us'],'pair interval/deadline mismatch')
        else:
            need(value['finalize_begin_us'] is None,'partial pair completion time')
            if state=='prepared':need(value['build'] is None and value['run'] is None,'prepared pair stage claim')
    return value


def read_phase_bytes(raw,role,identity,ready=False):
    need(type(raw) is bytes and 0<len(raw)<=PHASE_REPORTS[role][2],'phase report byte cap')
    need(all(b<128 for b in raw) and b'\\' not in raw and not raw.startswith(b'\xef\xbb\xbf'),'phase report ASCII grammar')
    quoted=False;token=0;depth=0;containers=0
    for b in raw:
        if b==34:
            quoted=not quoted;token=0
        elif quoted:
            token+=1;need(token<=128 and b>=32,'phase string token bound')
        elif b in (123,91):
            depth+=1;containers+=1;need(depth<=6 and containers<=256,'phase structure bound')
        elif b in (125,93):depth-=1
    need(not quoted and depth==0,'phase structure incomplete')
    need(all(len(t)<=16 for t in re.findall(rb'(?<![A-Za-z0-9_"])[-+0-9.eE]+',re.sub(rb'"[^"]*"',b'""',raw))),'phase numeric token bound')
    value=phase_report(role,json_unique(raw),identity,ready)
    encoded=canonical_phase_bytes(value)
    need(raw in (encoded,encoded.replace(b'\n',b'\r\n')),'phase canonical bytes mismatch')
    return value


def write_phase(path,role,value,identity,deadline=None):
    phase_report(role,value,identity);raw=canonical_phase_bytes(value)
    read_phase_bytes(raw,role,identity)
    if deadline is not None:need(time.monotonic()<deadline,'timeout during phase publication')
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('wb') as stream:stream.write(raw)
    os.replace(temporary,path)
    back=path.read_bytes();need(back==raw,'phase publication changed')
    result=dict(size=len(back),sha256=hashlib.sha256(back).hexdigest())
    if deadline is not None:need(time.monotonic()<deadline,'timeout during phase publication')
    return result


def path_identity(value):
    raw=str(value).encode('utf-8');need(0<len(raw)<=131072,'path identity bound')
    return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def fixed_file(root,name,cap=None):
    root=Path(root);path=root/name
    need(root.resolve(strict=True)==root.absolute(),'fixed root redirected')
    need(path.is_relative_to(root),'fixed file root mismatch')
    for item in [root,*list(path.relative_to(root).parents)[:-1]]:
        current=item if item==root else root/item
        info=current.lstat();need(not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&0x400,'reparse file component')
    info=path.lstat()
    need(stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&0x400 and info.st_size>0,'fixed regular file required')
    need(cap is None or info.st_size<=cap,'fixed file byte cap')
    return descriptor(path)


def object_report(source,identity,expected=None):
    root=Path(source)/'build/cl';produced=[]
    for name in PRODUCTION_OBJECTS:produced.append(dict(name=name,**fixed_file(root,'obj/'+name)))
    value=dict(schema=PHASE_REPORTS['objects'][1],state='ready',identity=identity,produced=produced,
               consumed=list(CONSUMED_OBJECTS),production_executable=fixed_file(root,'qbrain.exe'),failure=None)
    phase_report('objects',value,identity,True)
    if expected is not None:
        phase_report('objects',expected,identity,True)
        before={r['name']:{k:r[k] for k in ('size','sha256')} for r in expected['produced']}
        need(value['production_executable']==expected['production_executable'] and
             all({k:r[k] for k in ('size','sha256')}==before[r['name']] for r in produced if r['name'] in CONSUMED_OBJECTS),'production object continuity mismatch')
    return value


def configure_report(locations,identity):
    import ntpath
    root=Path(locations['build']);fixed_file(root,'CMakeCache.txt',MIB)
    raw=(root/'CMakeCache.txt').read_bytes();need(len(raw)<=MIB,'configure cache byte cap')
    lines=raw.splitlines();need(len(lines)<=4096 and all(len(line)<=16*1024 for line in lines),'configure cache line cap')
    expected={'CMAKE_HOME_DIRECTORY':(('INTERNAL',),locations['source']),
        'CMAKE_CACHEFILE_DIR':(('INTERNAL',),locations['build']),'CMAKE_PROJECT_NAME':(('STATIC',),'qbrain'),
        'CMAKE_GENERATOR':(('INTERNAL',),'Visual Studio 17 2022'),'CMAKE_BUILD_TYPE':(('STRING','UNINITIALIZED'),'Debug'),
        'CMAKE_CONFIGURATION_TYPES':(('STRING',),None),'QBRAIN_WITH_PG':(('BOOL',),'OFF'),
        'CMAKE_PROJECT_qbrain_INCLUDE':(('FILEPATH','UNINITIALIZED'),ntpath.join(locations['source'],'.ci','mcp_directory_search_targets.cmake'))}
    seen={}
    for line in lines:
        if not line or line.startswith((b'#',b'//')):continue
        key=line.split(b':',1)[0].decode('utf-8',errors='strict')
        if key not in expected:continue
        need(key not in seen,'configure duplicate selected key')
        match=re.fullmatch(rb'([^:]+):([^=]+)=(.*)',line);need(match is not None,'configure selected cache syntax')
        kind,value=match[2].decode('ascii'),match[3].decode('utf-8')
        kinds,wanted=expected[key];need(kind in kinds,'configure selected cache type')
        if key=='CMAKE_CONFIGURATION_TYPES':
            parts=value.split(';');need(1<=len(parts)<=8 and len(set(parts))==len(parts) and parts.count('Debug')==1 and
                all(re.fullmatch('[A-Za-z0-9_+-]{1,32}',p) for p in parts),'configure selected cache value')
        elif key in ('CMAKE_HOME_DIRECTORY','CMAKE_CACHEFILE_DIR','CMAKE_PROJECT_qbrain_INCLUDE'):
            need(ntpath.isabs(value) and ntpath.normcase(ntpath.normpath(value))==ntpath.normcase(ntpath.normpath(wanted)),'configure selected cache path')
        else:need(value==wanted,'configure selected cache value')
        seen[key]=True
    need(set(seen)==set(expected),'configure missing selected key')
    value=dict(schema=PHASE_REPORTS['configure'][1],state='ready',identity=identity,
        source_location=path_identity(locations['source']),build_location=path_identity(locations['build']),
        overlay_location=path_identity(expected['CMAKE_PROJECT_qbrain_INCLUDE'][1]),generator='vs17-2022',
        checks=dict.fromkeys(CONFIGURE_CHECKS,True),files={n:fixed_file(root,n,MIB) for n in CONFIGURE_FILES},failure=None)
    return phase_report('configure',value,identity,True)


def validate_build_proof(owner):
    proof=owner.get('build_completion');exact_keys(proof,BUILD_PROOF_KEYS,'build completion proof keys')
    need(proof['schema']=='qbrain-n49d-build-completion-v1' and proof['policy']=='trusted-build-v1','build proof schema/policy')
    need(proof['state']=='complete' and proof['reason'] is None and type(proof['root_exit']) is int and proof['root_exit']==0,'build proof incomplete')
    for key in BUILD_TIMES:
        if key=='termination_requested_us' and not proof['teardown_requested']:continue
        uint(proof[key])
    need(type(proof['teardown_requested']) is bool,'build teardown type')
    need(all(proof[k] is True for k in ('close_attempted','close_returned','close_in_budget')),'build close proof')
    need(proof['root_observed_us']<=proof['empty_observed_us']<=proof['close_attempted_us']<=proof['close_returned_us']<=
         proof['streams_finalized_us']<proof['success_deadline_us'],'build event ordering')
    if proof['teardown_requested']:
        need(proof['termination_succeeded'] is True and proof['root_observed_us']<=proof['termination_requested_us']<=proof['empty_observed_us'],'build termination ordering')
    else:need(proof['termination_requested_us'] is None and proof['termination_succeeded'] is None,'natural completion termination claim')
    need(owner.get('classification')=='build-completed' and owner.get('process_backend')=='windows-private-job' and
         type(owner.get('root_pid')) is int and owner['root_pid']>0 and type(owner.get('exit')) is int and owner['exit']==0 and
         all(owner.get(k) is True for k in ('owned_tree_empty','cleanup_ok','readers_done','stable')) and owner.get('cleanup_error') is None,'build owner facts')
    need(not any(k in owner for k in ('stop_reason','failure_detail','capture_error','job_diagnostic')),'build success failure metadata')
    return proof


def generic_archive(root=ROOT):
    """AST-select unchanged generic primitives and their ORIGINAL constants."""
    path = Path(root) / '.ci/check_n49c_sources.py'
    raw = source_guard.checkout_bytes(path.read_bytes(), '45a9c078a261270f595642f2d4c0092ad3c74243', os.name == 'nt')
    names = {'need','hash_file','safe_member','evidence_identity','bounded_manifest',
             'ManifestBudgetExceeded','encode_manifest','BoundedArchive',
             'verify_evidence_archive','verify_evidence_parts','package_evidence'}
    constants = {'BLOCK','PART_BYTES','MAX_PARTS','MAX_ARCHIVE','MAX_RAW','MAX_MANIFEST','MIN_FREE','IDENTITY_KEYS'}
    nodes = []
    for node in ast.parse(raw.decode('utf-8')).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            nodes.append(node)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in constants:
            nodes.append(node)
    need({n.name for n in nodes if isinstance(n,(ast.FunctionDef,ast.ClassDef))} == names, 'primitive inventory mismatch')
    ns = dict(Path=Path,ROOT=Path(root),hashlib=hashlib,os=os,re=re,stat=stat,json=json,
              shutil=shutil,tempfile=tempfile,zipfile=zipfile)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
    need(ns['MIN_FREE'] == 1152*MIB and ns['MAX_ARCHIVE'] == 320*MIB, 'inherited limits must remain unchanged')
    return ns


def required_stages(job):
    need(job in JOBS, 'unknown job')
    result = ['source-before','selftest-normal','selftest-optimized']
    if job == 'windows-msvc':
        result += ['direct-production','direct-tests-build','direct-tests-run','canonical-groups']
    else:
        result += ['configure','build']
        if job == 'linux-sanitizers':
            result += ['sanitizer-flags','sanitize-mcp','sanitize-directory']
        else:
            result += ['ctest-inventory','ctest-run','ctest-completeness']
            if job == 'windows-cmake':
                result += ['canonical-build','canonical-run','canonical-groups']
    if job != 'linux-sanitizers':
        for mode in ('normal','optimized'):
            result += [f'{driver}-{mode}' for driver in DRIVERS]
            if job == 'windows-cmake':
                result += [f'winhttp-{mode}']
    return result + ['source-after']


def stage_contract(identity, locations):
    """Exact production argv, report inventory and deadlines; no shell fragments."""
    import ntpath, posixpath
    job=identity['job_key']; windows=job.startswith('windows'); path=ntpath if windows else posixpath
    need(set(locations)=={'source','build','output','python'}, 'fixed location inventory')
    need(all(isinstance(v,str) and path.isabs(v) for v in locations.values()), 'absolute stage locations required')
    source,build,output,python=(locations[k] for k in ('source','build','output','python'))
    need(re.fullmatch(r'python(?:[0-9]+(?:\.[0-9]+)*)?(?:\.exe)?',path.basename(python),re.I), 'Python executable identity')
    need(len({path.normcase(v) for v in (source,build,output)})==3, 'stage locations overlap')
    join=path.join; ci=lambda p:join(source,'.ci',p); report=lambda p:join(output,'reports',p)
    exe=lambda name:join(build,'Debug',name+'.exe') if windows else join(build,name)
    runner=ci('run_n49d_qualification.py'); specs={}
    def add(name,argv,timeout=600,reports=()):
        specs[name]=dict(argv=list(argv),timeout_seconds=timeout,reports=list(reports),completion_policy='trusted-build-v1' if (job,name) in TRUSTED_BUILD else 'strict-v1')
    for name in ('source-before','source-after'):
        add(name,[python,ci('check_n49d_sources.py'),'--source',source,'--commit',identity['commit'],'--tree',identity['tree'],'--report',report(name+'.json')],120,['reports/'+name+'.json'])
    for mode in ('normal','optimized'):
        add('selftest-'+mode,[python,*(['-O'] if mode=='optimized' else []),ci('test_n49d_source_contract.py')],120)
    if job=='windows-msvc':
        production=join(source,'build','cl','qbrain.exe')
        add('direct-production',['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File','scripts/build-cl.ps1'],1800,[PHASE_REPORTS['objects'][0]])
        add('direct-tests-build',['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File','scripts/build-tests-cl.ps1','-SkipProductionBuild','-BuildOnly','-ProductionManifest',report('direct-production-objects.json'),'-PhaseContext',report('direct-tests-build-context.json')],1200,[PHASE_REPORTS['build-context'][0]])
        add('direct-tests-run',['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File','scripts/build-tests-cl.ps1','-RunOnly','-PhaseContext',report('direct-tests-build-context.json'),'-RunReport',report('direct-tests-run-context.json')],600,[PHASE_REPORTS['run-context'][0]])
        native_log=join(output,'stages','direct-tests-run','stdout.bin')
    else:
        configure=['cmake','-S',source,'-B',build,'-DQBRAIN_WITH_PG=OFF','-DCMAKE_PROJECT_qbrain_INCLUDE='+ci('mcp_directory_search_targets.cmake'),'-DCMAKE_BUILD_TYPE=Debug']
        targets=['qbrain',*TARGETS];production=exe('qbrain')
        if job=='linux-sanitizers':
            configure+=['-DCMAKE_C_COMPILER=clang','-DCMAKE_CXX_COMPILER=clang++','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
                '-DCMAKE_C_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer','-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer',
                '-DCMAKE_C_FLAGS_DEBUG=-O1 -g0','-DCMAKE_CXX_FLAGS_DEBUG=-O1 -g0','-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined']
            targets=list(TARGETS[:2])
        elif job=='linux-cmake':configure+=['-DCMAKE_CXX_FLAGS_DEBUG=-O0 -g0','-DCMAKE_C_FLAGS_DEBUG=-O0 -g0']
        add('configure',configure,180,[PHASE_REPORTS['configure'][0]] if job=='windows-cmake' else [])
        add('build',['cmake','--build',build,'--config','Debug','--target',*targets,'--parallel','2'],1800)
        if job=='linux-sanitizers':
            add('sanitizer-flags',[python,runner,'verify-sanitizer','--build',build,'--report',report('sanitizer-effective.json')],120,['reports/sanitizer-effective.json'])
            for name,target in zip(('sanitize-mcp','sanitize-directory'),TARGETS[:2]):add(name,[exe(target)])
        else:
            regex='^('+'|'.join(TESTS)+')$';inventory=join(output,'stages','ctest-inventory','stdout.bin')
            add('ctest-inventory',['ctest','--test-dir',build,'-C','Debug','-R',regex,'--show-only=json-v1'],120)
            add('ctest-run',['ctest','--test-dir',build,'-C','Debug','-R',regex,'--output-on-failure','--output-junit',report('ctest.xml')],600,['reports/ctest.xml'])
            add('ctest-completeness',[python,runner,'verify-ctest','--inventory',inventory,'--junit',report('ctest.xml')],120)
            if windows:
                add('canonical-build',['cmake','--build',build,'--config','Debug','--target','qbrain_tests','qbrain_http_probe','--parallel','2'],1800)
                add('canonical-run',[exe('qbrain_tests')]);native_log=join(output,'stages','canonical-run','stdout.bin')
    if windows:add('canonical-groups',[python,runner,'verify-native','--registry',join(source,'tests','test_main.cpp'),'--log',native_log],120)
    if job!='linux-sanitizers':
        for mode in ('normal','optimized'):
            prefix=[python,*(['-O'] if mode=='optimized' else [])]
            for driver in DRIVERS:
                name=driver+'-'+mode;argv=prefix+[ci('test_'+driver+'.py'),'--binary',production];reports=[]
                if driver in ('mcp_directory_search','directory_search'):
                    argv+=['--output',report(name)];reports=['reports/'+name+'/RESULT.json']
                elif driver in ('context_process','named_arguments'):
                    argv+=['--report',report(name+'.json')];reports=['reports/'+name+'.json']
                add(name,argv,reports=reports)
            if job=='windows-cmake':
                name='winhttp-'+mode;add(name,prefix+[ci('test_http_transport.py'),'--probe',exe('qbrain_http_probe'),'--report',report(name+'.json')],reports=['reports/'+name+'.json'])
    selected=[exe(t) for t in (TARGETS[:2] if job=='linux-sanitizers' else ['qbrain',*TARGETS])]
    canonical=join(source,'build','cl','qbrain_tests.exe') if job=='windows-msvc' else exe('qbrain_tests')
    for name,spec in specs.items():
        before=[];after=[]
        if name=='build':after=selected
        elif name=='direct-production':after=[production]
        elif name=='direct-tests-build':before=[production];after=[production,canonical]
        elif name=='direct-tests-run':before=[production,canonical]
        elif name in ('ctest-inventory','ctest-run','ctest-completeness','sanitizer-flags','sanitize-mcp','sanitize-directory'):before=selected
        elif name=='canonical-build':before=selected;after=selected+[canonical,exe('qbrain_http_probe')]
        elif name in ('canonical-run','canonical-groups'):before=[canonical,production]
        elif any(name==driver+'-'+mode for driver in DRIVERS for mode in ('normal','optimized')):before=[production]
        elif name.startswith('winhttp-'):before=[production,exe('qbrain_http_probe')]
        spec['binaries_before']=sorted(before);spec['binaries_after']=sorted(after or before)
    all_binaries=sorted({p for spec in specs.values() for p in spec['binaries_after']})
    specs['source-after']['binaries_before']=all_binaries;specs['source-after']['binaries_after']=all_binaries
    need(set(specs)==set(required_stages(job)), 'fixed stage contract inventory')
    return specs


_OWNER_LOCK=threading.Lock()
_ACTIVE_OWNER=None
_AUDIT_INSTALLED=False
_LAUNCH_THREAD=None
_LAUNCH_ARGV=None


def _audit_launch(event,args):
    if _ACTIVE_OWNER is None:return
    if event in ('os.system','os.spawn','os.exec','os.startfile','os.startfile/2','pty.spawn'):
        raise ValueError('unmanaged process launch during owned lifetime')
    if event in ('subprocess.Popen','os.fork','os.forkpty','os.posix_spawn'):
        allowed=threading.get_ident()==_LAUNCH_THREAD
        if event=='subprocess.Popen' and os.name=='nt':
            allowed=allowed and isinstance(args[1],str) and args[1]==subprocess.list2cmdline(_LAUNCH_ARGV)
        elif event in ('subprocess.Popen','os.posix_spawn'):
            allowed=allowed and isinstance(args[1],(list,tuple)) and list(args[1])==_LAUNCH_ARGV
        need(allowed,'unmanaged process launch during owned lifetime')


_PROC_STAT_CHILD_ADAPTER=None
_PROC_ENTRY_CAP=16384
_PROC_RECORD_CAP=4096
_PROC_SCAN_SECONDS=.25


def _proc_read(path,cap):
    with path.open('rb') as source:raw=source.read(cap+1)
    need(len(raw)<=cap,'proc record byte cap')
    return raw.decode('utf-8',errors='strict')


def _parse_proc_stat(text,pid):
    need(len(text.encode('utf-8',errors='strict'))<=_PROC_RECORD_CAP,'proc stat record cap')
    left=text.find(' (');right=text.rfind(') ')
    need(left>0 and right>left and text[:left].isdecimal() and int(text[:left])==pid,'proc stat PID/comm mismatch')
    fields=text[right+2:].split()
    need(len(fields)>=20 and len(fields[0])==1,'incomplete proc stat record')
    try:ppid=int(fields[1]);start=int(fields[19])
    except ValueError as error:raise ValueError('invalid proc identity fields') from error
    need(ppid>=0 and start>0,'invalid proc identity values')
    return dict(state=fields[0],ppid=ppid,start=start)


def _proc_deadline():
    outer=getattr(_ACTIVE_OWNER,'scan_deadline',float('inf'))
    return min(outer,time.monotonic()+_PROC_SCAN_SECONDS)


def _linux_stat(pid,deadline=None):
    deadline=_proc_deadline() if deadline is None else deadline
    need(time.monotonic()<deadline,'proc read deadline')
    result=_parse_proc_stat(_proc_read(Path('/proc',str(pid),'stat'),_PROC_RECORD_CAP),pid)
    need(time.monotonic()<deadline,'proc read deadline')
    return result


def _proc_pids():
    return (int(entry.name) for entry in Path('/proc').iterdir() if entry.name.isdecimal())


def _linux_children(pid):
    global _PROC_STAT_CHILD_ADAPTER
    deadline=_proc_deadline()
    if _PROC_STAT_CHILD_ADAPTER is None:
        # Selection is a self-process capability preflight, never a child race
        # or a permission-denial fallback.
        try:_proc_read(Path('/proc',str(os.getpid()),'task',str(os.getpid()),'children'),65536)
        except FileNotFoundError:
            _linux_stat(os.getpid(),deadline);_PROC_STAT_CHILD_ADAPTER=True
        else:_PROC_STAT_CHILD_ADAPTER=False
    if not _PROC_STAT_CHILD_ADAPTER:
        raw=_proc_read(Path('/proc',str(pid),'task',str(pid),'children'),65536)
        need(time.monotonic()<deadline,'proc read deadline')
        return [int(v) for v in raw.split()]
    result=[];count=0
    for candidate in _proc_pids():
        count+=1;need(count<=_PROC_ENTRY_CAP,'bounded proc ancestry inventory cap')
        try:value=_linux_stat(candidate,deadline)
        except (FileNotFoundError,ProcessLookupError):continue
        if value['ppid']==pid:result.append(candidate)
    need(time.monotonic()<deadline,'proc scan deadline')
    return result


def _pidfd_exited(fd):
    import select
    poll=select.poll();poll.register(fd,select.POLLIN)
    events=poll.poll(0)
    need(not any(flags & (select.POLLERR|select.POLLNVAL) for _,flags in events),'pidfd readiness failure')
    return any(flags & select.POLLIN for _,flags in events)


_LINUX_WAIT_ALL_CHILDREN=0x40000000  # Linux __WALL includes clone and non-clone children.


def _linux_no_children(deadline):
    """Absence only: never consume a status or use an oracle-returned PID."""
    need(time.monotonic()<deadline,'no-child oracle deadline')
    need(signal.getsignal(signal.SIGCHLD)==signal.SIG_DFL,'incompatible SIGCHLD at no-child oracle')
    need(callable(getattr(os,'waitid',None)) and all(hasattr(os,key) for key in ('P_ALL','WEXITED','WNOHANG','WNOWAIT')),
         'required no-child oracle API unavailable')
    absent=False
    try:
        os.waitid(os.P_ALL,0,os.WEXITED|os.WNOHANG|os.WNOWAIT|_LINUX_WAIT_ALL_CHILDREN)
    except OSError as error:
        absent=error.errno==errno.ECHILD
    finally:
        need(time.monotonic()<deadline,'no-child oracle deadline')
        need(signal.getsignal(signal.SIGCHLD)==signal.SIG_DFL,'SIGCHLD changed at no-child oracle')
    need(absent,'kernel child absence not proved')


def _bounded_failure_detail(value, fallback, cap, ownership=False):
    """Detach fixed primitives and measure their actual pretty CRLF wrapper."""
    try:
        wrapper={'failure_detail':value}
        if ownership:wrapper={'ownership':wrapper}
        raw=(json.dumps(wrapper,sort_keys=True,indent=2,allow_nan=False)+'\n').replace('\n','\r\n').encode('utf-8')
        need(len(raw)<=cap,'failure detail cap')
        detached=json.loads(raw)
        return (detached['ownership'] if ownership else detached)['failure_detail']
    except BaseException:return dict(fallback)


# Private fixed metadata states, never process identities or exported attributes.
_LINUX_DETAIL_MISSING=object()
_LINUX_DETAIL_UNLATCHED=object()
_LINUX_INITIAL_SITE='observe-initial-parent'
_LINUX_LATER_SITE='observe-post-pidfd'


def _linux_detail_unavailable(origin=_LINUX_LATER_SITE):
    if origin==_LINUX_INITIAL_SITE:
        return dict(schema='qbrain-n49d-linux-initial-parent-comparison-v1',site=origin,complete=False,reason='detail-unavailable')
    if origin==_LINUX_LATER_SITE:
        return dict(schema='qbrain-n49d-linux-identity-comparison-v1',site=origin,complete=False,reason='detail-unavailable')
    return dict(schema='qbrain-n49d-linux-unknown-origin-v1',site='unknown',complete=False,reason='detail-unavailable')


def _validate_linux_failure_detail(value,origin):
    """Validation returns no fallback: legacy admission requires actual validity."""
    need(type(origin) is str and origin in (_LINUX_INITIAL_SITE,_LINUX_LATER_SITE),'detail origin')
    fallback=_linux_detail_unavailable(origin)
    need(type(value) is dict,'detail mapping type')
    need(all(type(value.get(key)) is str and value[key]==fallback[key] for key in ('schema','site')),'detail schema/site')
    if value.get('complete') is False:
        need(set(value)==set(fallback) and type(value.get('reason')) is str and value['reason']=='detail-unavailable','detail incomplete fields')
        return
    need(value.get('complete') is True,'detail complete type')
    if origin==_LINUX_INITIAL_SITE:
        fields={'before_parent_matches_expected','before_parent_matches_controller','expected_parent_is_controller',
            'parent_pin_present','parent_pin_is_current_known','candidate_was_already_known','candidate_pin_recorded',
            'candidate_start_matches_before','final_parent_check_returned_true','new_pidfd_acquired_in_observe'}
        need(set(value)==set(fallback)|fields and type(value['reason']) is str and value['reason']=='parent-mismatch' and
             all(type(value[key]) is bool for key in fields-{'candidate_start_matches_before'}),'initial detail fixed fields')
        known=value['candidate_was_already_known']
        need((known and value['candidate_pin_recorded'] is True and type(value['candidate_start_matches_before']) is bool) or
             (not known and value['candidate_pin_recorded'] is False and value['candidate_start_matches_before'] is None),
             'initial detail known/null relationship')
        need(value['before_parent_matches_expected'] is False and value['final_parent_check_returned_true'] is True and
             value['new_pidfd_acquired_in_observe'] is False and
             (value['parent_pin_present'] or not value['parent_pin_is_current_known']),'initial detail boundary fields')
    else:
        fields={'same_start','before_parent_matches_expected','after_parent_matches_expected','after_parent_matches_controller',
            'before_after_parent_equal','expected_parent_is_controller','parent_pin_present','candidate_was_already_known','final_parent_check_returned_true'}
        need(set(value)==set(fallback)|fields and type(value['reason']) is str and
             value['reason'] in ('start-mismatch','parent-mismatch','start-and-parent-mismatch') and
             all(type(value[key]) is bool for key in fields),'detail fixed fields')


def _copy_linux_failure_detail(value,origin=_LINUX_DETAIL_MISSING):
    fallback=_linux_detail_unavailable('unknown')
    try:
        if origin is _LINUX_DETAIL_MISSING:
            _validate_linux_failure_detail(value,_LINUX_LATER_SITE)
            origin=_LINUX_LATER_SITE
        need(type(origin) is str and origin in (_LINUX_INITIAL_SITE,_LINUX_LATER_SITE),'detail origin')
        fallback=_linux_detail_unavailable(origin)
        _validate_linux_failure_detail(value,origin)
        return _bounded_failure_detail(value,fallback,1024,ownership=True)
    except BaseException:return fallback


def _new_linux_failure_cell(tree):
    return [(tree,_LINUX_DETAIL_UNLATCHED)]


def _linux_failure_cell(tree):
    """Only the exact owner-bound built-in cell is eligible for consumption."""
    cell=getattr(tree,'_failure_capture_cell',_LINUX_DETAIL_MISSING)
    if cell is _LINUX_DETAIL_MISSING:return 'absent',None
    need(type(cell) is list and len(cell)<=1,'invalid diagnostic cell')
    if not cell:return 'consumed',cell
    token=cell[0]
    need(type(token) is tuple and len(token)==2 and token[0] is tree and token[1] is _LINUX_DETAIL_UNLATCHED,
         'foreign diagnostic token')
    return 'fresh',cell


def _poison_linux_failure_detail(tree):
    # A surviving unknown marker disables recovery without recreating the cell.
    try:tree._failure_origin='unknown'
    except BaseException:pass
    try:tree.failure_detail=_linux_detail_unavailable('unknown')
    except BaseException:pass


def _initialize_linux_failure_detail(tree):
    """Initialize once; failed creation/installation stays constructor-neutral."""
    try:
        if (getattr(tree,'_failure_capture_cell',_LINUX_DETAIL_MISSING) is not _LINUX_DETAIL_MISSING or
            getattr(tree,'_failure_origin',_LINUX_DETAIL_MISSING) is not _LINUX_DETAIL_MISSING or
            getattr(tree,'failure_detail',_LINUX_DETAIL_MISSING) is not _LINUX_DETAIL_MISSING):return
        cell=_new_linux_failure_cell(tree)
        need(type(cell) is list and len(cell)==1 and type(cell[0]) is tuple and
             len(cell[0])==2 and cell[0][0] is tree and cell[0][1] is _LINUX_DETAIL_UNLATCHED,'invalid initial diagnostic cell')
        tree._failure_capture_cell=cell
        tree._failure_origin=_LINUX_DETAIL_UNLATCHED
    except BaseException:
        try:
            state,cell=_linux_failure_cell(tree)
            if state=='fresh':cell.pop()
        except BaseException:pass
        _poison_linux_failure_detail(tree)


def _consume_linux_failure_cell(tree):
    state,cell=_linux_failure_cell(tree)
    if state=='consumed':return False
    need(state=='fresh','diagnostic cell unavailable')
    cell.pop()
    return True


def _capture_linux_failure_detail(tree,origin,builder):
    """Consume the preallocated cell before every optional metadata operation."""
    try:
        if not _consume_linux_failure_cell(tree):return
        if getattr(tree,'_failure_origin',_LINUX_DETAIL_MISSING) is not _LINUX_DETAIL_UNLATCHED:
            _poison_linux_failure_detail(tree);return
        if getattr(tree,'failure_detail',None) is not None:
            _poison_linux_failure_detail(tree);return
        try:tree._failure_origin=origin
        except BaseException:
            _poison_linux_failure_detail(tree);return
        try:tree.failure_detail=_linux_detail_unavailable(origin)
        except BaseException:pass
        try:tree.failure_detail=builder()
        except BaseException:pass
    except BaseException:
        _poison_linux_failure_detail(tree)


def _retain_linux_failure_detail(target,tree):
    """Bind optional payload to retained origin and authoritative cell state."""
    fallback=_linux_detail_unavailable('unknown')
    try:
        state,cell=_linux_failure_cell(tree)
        marker=getattr(tree,'_failure_origin',_LINUX_DETAIL_MISSING)
        if state=='consumed' and type(marker) is str and marker in (_LINUX_INITIAL_SITE,_LINUX_LATER_SITE):
            fallback=_linux_detail_unavailable(marker)
            target['failure_detail']=fallback
            value=getattr(tree,'failure_detail',None)
        elif (state=='absent' and marker is _LINUX_DETAIL_MISSING and
              getattr(tree,'_failure_capture_consumed',_LINUX_DETAIL_MISSING) is _LINUX_DETAIL_MISSING):
            value=getattr(tree,'failure_detail',_LINUX_DETAIL_MISSING)
            if value is _LINUX_DETAIL_MISSING:return
            target['failure_detail']=fallback
            _validate_linux_failure_detail(value,_LINUX_LATER_SITE)
            marker=_LINUX_LATER_SITE
            fallback=_linux_detail_unavailable(marker)
            target['failure_detail']=fallback
        elif state=='fresh' and marker is _LINUX_DETAIL_UNLATCHED:
            value=getattr(tree,'failure_detail',_LINUX_DETAIL_MISSING)
            if value is _LINUX_DETAIL_MISSING:return
            target['failure_detail']=fallback
            return
        else:
            target['failure_detail']=fallback
            return
        target['failure_detail']=_copy_linux_failure_detail(value,marker)
    except BaseException:
        try:target['failure_detail']=fallback
        except BaseException:pass


def _linux_initial_parent_detail(before,pid,parent,controller,parent_pin,known):
    fallback=_linux_detail_unavailable(_LINUX_INITIAL_SITE)
    try:
        need(type(before) is dict and type(known) is dict and
             all(type(v) is int for v in (before['start'],before['ppid'],pid,parent,controller)),'initial detail input types')
        def valid_pin(pin):
            need(type(pin) is dict and type(pin['fd']) is int and pin['fd']>=0 and type(pin['start']) is int,'initial detail pin types')
        if parent_pin is not None:valid_pin(parent_pin)
        if parent in known:valid_pin(known[parent])
        present=pid in known
        if present:valid_pin(known[pid])
        value=dict(schema=fallback['schema'],site=fallback['site'],complete=True,reason='parent-mismatch',
            before_parent_matches_expected=before['ppid']==parent,before_parent_matches_controller=before['ppid']==controller,
            expected_parent_is_controller=parent==controller,parent_pin_present=parent_pin is not None,
            parent_pin_is_current_known=parent_pin is not None and known.get(parent) is parent_pin,
            candidate_was_already_known=present,candidate_pin_recorded=present,
            candidate_start_matches_before=known[pid]['start']==before['start'] if present else None,
            final_parent_check_returned_true=True,new_pidfd_acquired_in_observe=False)
        return _copy_linux_failure_detail(value,_LINUX_INITIAL_SITE)
    except BaseException:return fallback


def _linux_identity_detail(before,after,parent,controller,parent_pin):
    fallback=_linux_detail_unavailable()
    try:
        need(all(type(v) is int for v in (before['start'],after['start'],before['ppid'],after['ppid'],parent,controller)), 'detail types')
        same=before['start']==after['start'];linked=after['ppid']==parent
        value=dict(schema=fallback['schema'],site=fallback['site'],complete=True,
            reason='parent-mismatch' if same else ('start-mismatch' if linked else 'start-and-parent-mismatch'),
            same_start=same,before_parent_matches_expected=before['ppid']==parent,
            after_parent_matches_expected=linked,after_parent_matches_controller=after['ppid']==controller,
            before_after_parent_equal=before['ppid']==after['ppid'],expected_parent_is_controller=parent==controller,
            parent_pin_present=parent_pin is not None,candidate_was_already_known=False,final_parent_check_returned_true=True)
        return _copy_linux_failure_detail(value,_LINUX_LATER_SITE)
    except BaseException:return fallback


class _LinuxTree:
    def __init__(self):
        import ctypes
        need(signal.getsignal(signal.SIGCHLD)==signal.SIG_DFL,'incompatible SIGCHLD reaper disposition')
        need(hasattr(os,'pidfd_open') and hasattr(signal,'pidfd_send_signal'),'pidfd ownership unavailable')
        self.controller_pid=os.getpid()
        need(not _linux_children(self.controller_pid),'unmanaged pre-existing child makes ownership ambiguous')
        _linux_no_children(_proc_deadline())
        self.libc=ctypes.CDLL(None,use_errno=True);self.previous=ctypes.c_int()
        need(self.libc.prctl(37,ctypes.byref(self.previous),0,0,0)==0,'cannot read subreaper state')
        need(self.libc.prctl(36,1,0,0,0)==0,'cannot enable runner-local subreaper')
        self.known={};self.proc=None;self.restored=False
        try:_initialize_linux_failure_detail(self)
        except BaseException:pass

    def attach(self,proc):
        self.proc=proc;self.observe(proc.pid,os.getpid())

    def parent_current(self,parent,pin):
        if parent==os.getpid():
            need(pin is None,'unexpected interpreter parent pin');return True
        need(pin is not None and self.known.get(parent) is pin,'queued parent pin mismatch')
        if _pidfd_exited(pin['fd']):return False
        try:current=_linux_stat(parent)
        except (FileNotFoundError,ProcessLookupError):
            need(_pidfd_exited(pin['fd']),'live parent pidfd lost identity record');return False
        if _pidfd_exited(pin['fd']):return False
        need(current['start']==pin['start'],'owned parent identity changed')
        return True

    def observe(self,pid,parent,parent_pin=None):
        if not self.parent_current(parent,parent_pin):return None
        try:before=_linux_stat(pid)
        except (FileNotFoundError,ProcessLookupError):
            if pid in self.known:need(_pidfd_exited(self.known[pid]['fd']),'live pidfd lost identity record')
            return None
        if not self.parent_current(parent,parent_pin):return None
        try:
            need(before['ppid']==parent,'ambiguous descendant ancestry')
        except ValueError as error:
            if str(error)=='ambiguous descendant ancestry':
                try:_capture_linux_failure_detail(self,_LINUX_INITIAL_SITE,lambda:_linux_initial_parent_detail(
                    before,pid,parent,self.controller_pid,parent_pin,self.known))
                except BaseException:pass
            raise
        if pid in self.known:
            need(self.known[pid]['start']==before['start'],'owned PID identity changed');return self.known[pid]
        try:fd=os.pidfd_open(pid,0)
        except ProcessLookupError:return None
        retained=False
        try:
            after=_linux_stat(pid)
            if not self.parent_current(parent,parent_pin):return None
            try:
                need(before['start']==after['start'] and after['ppid']==parent,'pidfd identity/ancestry mismatch')
            except ValueError as error:
                if str(error)=='pidfd identity/ancestry mismatch':
                    try:_capture_linux_failure_detail(self,_LINUX_LATER_SITE,lambda:_linux_identity_detail(
                        before,after,parent,self.controller_pid,parent_pin))
                    except BaseException:pass
                raise
            self.known[pid]=dict(fd=fd,start=after['start'])
            retained=True;return self.known[pid]
        except (FileNotFoundError,ProcessLookupError):
            need(_pidfd_exited(fd),'live pidfd lost identity record');return None
        finally:
            if not retained:os.close(fd)

    def active(self):
        # Only this interpreter's child lineage; exclusive launch audit is active.
        pending=[(pid,os.getpid(),None) for pid in _linux_children(os.getpid())];seen=set()
        while pending:
            pid,parent,parent_pin=pending.pop()
            if pid in seen:continue
            seen.add(pid);need(len(seen)<=1024,'owned child count cap')
            pin=self.observe(pid,parent,parent_pin)
            if pin is None or not self.parent_current(pid,pin):continue
            try:children=_linux_children(pid)
            except (FileNotFoundError,ProcessLookupError):
                need(_pidfd_exited(pin['fd']),'live pidfd lost child inventory');continue
            if self.parent_current(pid,pin):pending.extend((child,pid,pin) for child in children)
        alive=[]
        for pid,row in self.known.items():
            if not _pidfd_exited(row['fd']):alive.append(pid)
            elif self.proc is not None and pid!=self.proc.pid:
                try:
                    current=_linux_stat(pid)
                    need(current['start']==row['start'],'adopted child identity changed before reap')
                    need(signal.getsignal(signal.SIGCHLD)==signal.SIG_DFL,'SIGCHLD disposition changed during ownership')
                    if current['ppid']==os.getpid():os.waitpid(pid,os.WNOHANG)
                except (FileNotFoundError,ProcessLookupError,ChildProcessError):pass
        if self.proc is not None:self.proc.poll()
        return alive

    def terminate(self):
        self.active()
        for row in self.known.values():
            try:signal.pidfd_send_signal(row['fd'],signal.SIGKILL,None,0)
            except ProcessLookupError:pass

    def close(self):
        need(not self.active() and not _linux_children(os.getpid()),'owned children not reaped')
        _linux_no_children(_proc_deadline())
        need(self.libc.prctl(36,self.previous.value,0,0,0)==0,'cannot restore subreaper state')
        self.restored=True
        for row in self.known.values():os.close(row['fd'])
        self.known.clear()


def _windows_job_list_type(c):
    # Fixed Windows widths also make the off-platform API controls faithful.
    class ProcessList(c.Structure):
        _fields_=[('assigned',c.c_uint32),('listed',c.c_uint32),('pids',c.c_size_t*32)]
    return ProcessList


def _bounded_job_diagnostic(value):
    try:
        need(len((json.dumps(value,sort_keys=True,indent=2)+'\n').replace('\n',os.linesep).encode('utf-8'))<=8192,'metadata_cap')
        return value
    except BaseException:
        return dict(complete=False,observation='unknown',error='metadata_cap',members=[])



def _image_sample(status='not_selected',index=None,name=None,name_hash=None,win32=None):
    """Only six fixed redacted fields; malformed detail cannot affect ownership."""
    valid_index=type(index) is int and 0<=index<32
    fallback=dict(member_index=index if valid_index else None,status='metadata_cap',
                  basename=None,basename_sha256=None,race='non_atomic',win32=None)
    try:
        need(status in ('not_selected','sampled','redacted_basename','query_failed','buffer_limit',
                        'invalid_result','deadline','api_exception','metadata_cap'),'image status')
        need(index is None or valid_index,'image index')
        if status=='not_selected':need(index is None and name is None and name_hash is None and win32 is None,'image empty')
        elif status in ('sampled','redacted_basename'):
            need(valid_index and type(name_hash) is str and re.fullmatch('[0-9a-f]{64}',name_hash) and win32 is None,'image name hash')
            need((status=='sampled' and type(name) is str and re.fullmatch('[A-Za-z0-9_.-]{1,64}',name) and name not in ('.','..')) or
                 (status=='redacted_basename' and name is None),'image name')
        elif status in ('query_failed','buffer_limit'):
            need(valid_index and name is None and name_hash is None and type(win32) is int and 0<=win32<=0xffffffff and
                 ((win32==122)==(status=='buffer_limit')),'image error')
        else:need(name is None and name_hash is None and win32 is None,'image unavailable')
        value=dict(member_index=index,status=status,basename=name,basename_sha256=name_hash,race='non_atomic',win32=win32)
        need(len((json.dumps(value,sort_keys=True,indent=2)+'\n').replace('\n','\r\n').encode('utf-8'))<=512,'image cap')
        return value
    except BaseException:return fallback


def _windows_image_eligible(row):
    return (isinstance(row,dict) and row.get('root') is False and 'error' not in row and
            all(type(row.get(key)) is int and row[key]==value
                for key,value in (('wait_before',258),('exit_code',259),('wait_after',258))))


def _windows_image_name(units,count):
    need(type(count) is int and 1<=count<1024 and len(units)==1024,'invalid_result')
    need(units[count]==0 and all(type(x) is int and 0<x<=0xffff for x in units[:count]),'invalid_result')
    last=max((i for i in range(count) if units[i] in (47,92)),default=-1)
    raw=b''.join(x.to_bytes(2,'little') for x in units[last+1:count])
    name=raw.decode('utf-16le',errors='strict')
    need(name not in ('','.','..'),'invalid_result')
    name_hash=hashlib.sha256(raw).hexdigest()
    return name if re.fullmatch('[A-Za-z0-9_.-]{1,64}',name) else None,name_hash


class _WindowsTree:
    def __init__(self):
        import ctypes as c
        from ctypes import wintypes as w
        self.c=c;self.w=w;self.k=c.WinDLL('kernel32',use_last_error=True);self.proc=None;self.assigned=False
        self.last_accounting=None;self.ProcessList=_windows_job_list_type(c)
        need(c.sizeof(self.ProcessList)==8+32*c.sizeof(c.c_size_t),'private job list ABI mismatch')
        class Basic(c.Structure):
            _fields_=[('PerProcessUserTimeLimit',c.c_longlong),('PerJobUserTimeLimit',c.c_longlong),('LimitFlags',w.DWORD),('MinimumWorkingSetSize',c.c_size_t),('MaximumWorkingSetSize',c.c_size_t),('ActiveProcessLimit',w.DWORD),('Affinity',c.c_size_t),('PriorityClass',w.DWORD),('SchedulingClass',w.DWORD)]
        class IO(c.Structure):_fields_=[(n,c.c_ulonglong) for n in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
        class Extended(c.Structure):_fields_=[('BasicLimitInformation',Basic),('IoInfo',IO),('ProcessMemoryLimit',c.c_size_t),('JobMemoryLimit',c.c_size_t),('PeakProcessMemoryUsed',c.c_size_t),('PeakJobMemoryUsed',c.c_size_t)]
        class Accounting(c.Structure):_fields_=[('TotalUserTime',c.c_longlong),('TotalKernelTime',c.c_longlong),('ThisPeriodTotalUserTime',c.c_longlong),('ThisPeriodTotalKernelTime',c.c_longlong),('TotalPageFaultCount',w.DWORD),('TotalProcesses',w.DWORD),('ActiveProcesses',w.DWORD),('TotalTerminatedProcesses',w.DWORD)]
        class Thread(c.Structure):_fields_=[('dwSize',w.DWORD),('cntUsage',w.DWORD),('th32ThreadID',w.DWORD),('th32OwnerProcessID',w.DWORD),('tpBasePri',w.LONG),('tpDeltaPri',w.LONG),('dwFlags',w.DWORD)]
        self.Accounting=Accounting;self.Thread=Thread
        signatures={'CreateJobObjectW':([c.c_void_p,w.LPCWSTR],w.HANDLE),'SetInformationJobObject':([w.HANDLE,c.c_int,c.c_void_p,w.DWORD],w.BOOL),'SetHandleInformation':([w.HANDLE,w.DWORD,w.DWORD],w.BOOL),'CloseHandle':([w.HANDLE],w.BOOL),'OpenProcess':([w.DWORD,w.BOOL,w.DWORD],w.HANDLE),'AssignProcessToJobObject':([w.HANDLE,w.HANDLE],w.BOOL),'CreateToolhelp32Snapshot':([w.DWORD,w.DWORD],w.HANDLE),'Thread32First':([w.HANDLE,c.POINTER(Thread)],w.BOOL),'Thread32Next':([w.HANDLE,c.POINTER(Thread)],w.BOOL),'OpenThread':([w.DWORD,w.BOOL,w.DWORD],w.HANDLE),'ResumeThread':([w.HANDLE],w.DWORD),'GetProcessIdOfThread':([w.HANDLE],w.DWORD),'QueryInformationJobObject':([w.HANDLE,c.c_int,c.c_void_p,w.DWORD,c.c_void_p],w.BOOL),'TerminateJobObject':([w.HANDLE,w.UINT],w.BOOL)}
        for name,(args,ret) in signatures.items():getattr(self.k,name).argtypes=args;getattr(self.k,name).restype=ret
        for name,(args,ret) in {'IsProcessInJob':([w.HANDLE,w.HANDLE,c.POINTER(w.BOOL)],w.BOOL),
                'WaitForSingleObject':([w.HANDLE,w.DWORD],w.DWORD),
                'GetExitCodeProcess':([w.HANDLE,c.POINTER(w.DWORD)],w.BOOL)}.items():
            getattr(self.k,name).argtypes=args;getattr(self.k,name).restype=ret
        self.job=self.k.CreateJobObjectW(None,None);need(bool(self.job),'CreateJobObject failed')
        try:
            need(self.k.SetHandleInformation(self.job,1,0),'noninheritable job handle failed')
            info=Extended();info.BasicLimitInformation.LimitFlags=0x2000
            need(self.k.SetInformationJobObject(self.job,9,c.byref(info),c.sizeof(info)),'kill-on-close job policy failed')
        except BaseException:self.k.CloseHandle(self.job);self.job=None;raise

    def attach(self,proc):
        self.proc=proc;c=self.c;k=self.k
        process=k.OpenProcess(0x0100|0x0001,False,proc.pid);need(bool(process),'OpenProcess for private job failed')
        try:need(k.AssignProcessToJobObject(self.job,process),'private nested job assignment failed');self.assigned=True
        finally:need(k.CloseHandle(process),'owned process handle close failed')
        snapshot=k.CreateToolhelp32Snapshot(0x00000004,0)
        need(snapshot not in (None,c.c_void_p(-1).value),'thread snapshot failed')
        threads=[]
        try:
            entry=self.Thread();entry.dwSize=c.sizeof(entry);ok=k.Thread32First(snapshot,c.byref(entry))
            while ok:
                if entry.th32OwnerProcessID==proc.pid:threads.append(entry.th32ThreadID)
                entry.dwSize=c.sizeof(entry);c.set_last_error(0);ok=k.Thread32Next(snapshot,c.byref(entry))
            need(c.get_last_error()==18,'thread inventory API failure')
        finally:need(k.CloseHandle(snapshot),'thread snapshot close failed')
        need(len(threads)==1,'suspended primary thread inventory ambiguous')
        thread=k.OpenThread(0x0002|0x0800,False,threads[0]);need(bool(thread),'OpenThread failed')
        try:
            need(k.GetProcessIdOfThread(thread)==proc.pid,'opened thread is not owned primary thread')
            need(k.ResumeThread(thread)==1,'primary thread resume failed')
        finally:need(k.CloseHandle(thread),'primary thread handle close failed')

    def active(self):
        if not self.assigned:return [self.proc.pid] if self.proc is not None and self.proc.poll() is None else []
        value=self.Accounting();need(self.k.QueryInformationJobObject(self.job,1,self.c.byref(value),self.c.sizeof(value),None),'private job accounting failed')
        self.last_accounting=dict(total=value.TotalProcesses,active=value.ActiveProcesses,terminated=value.TotalTerminatedProcesses)
        return list(range(value.ActiveProcesses))

    def observe_member(self,handle,deadline):
        """Observe an already verified, pinned private-job member; never by PID."""
        row={};step='wait_before'
        try:
            need(time.monotonic()<deadline,'deadline')
            row['wait_before']=int(self.k.WaitForSingleObject(handle,0));error=int(self.c.get_last_error())
            need(time.monotonic()<deadline,'deadline')
            if row['wait_before'] not in (0,258):row.update(error=step,win32=error);return row
            step='exit_code';value=self.w.DWORD()
            need(time.monotonic()<deadline,'deadline')
            ok=self.k.GetExitCodeProcess(handle,self.c.byref(value));error=int(self.c.get_last_error())
            need(time.monotonic()<deadline,'deadline')
            if not ok:row.update(error=step,win32=error);return row
            row['exit_code']=int(value.value);step='wait_after'
            need(time.monotonic()<deadline,'deadline')
            row['wait_after']=int(self.k.WaitForSingleObject(handle,0));error=int(self.c.get_last_error())
            need(time.monotonic()<deadline,'deadline')
            if row['wait_after'] not in (0,258):row.update(error=step,win32=error)
            elif row['wait_before']==0 and row['wait_after']!=0:row['error']='conflicting_states'
            elif row['wait_after']==258 and row['exit_code']!=259:row['error']='conflicting_states'
        except BaseException as error:
            row['error']='deadline' if isinstance(error,ValueError) and str(error)=='deadline' else 'api_exception'
        return row


    def sample_image(self,handle,index,deadline):
        """One name query on the existing verified member handle, never a PID."""
        c=self.c;buffer=None;phase='binding';value=_image_sample('api_exception',index)
        try:
            need(time.monotonic()<deadline,'deadline')
            need(type(index) is int and 0<=index<32,'invalid_result')
            # Resolve and validate only inside this failure-only unavailable boundary.
            need(c.sizeof(c.c_void_p)==c.sizeof(c.c_size_t)==8 and
                 c.sizeof(c.c_uint16)==2 and c.sizeof(c.c_uint32)==c.sizeof(c.c_int32)==4,'image ABI')
            query=self.k.QueryFullProcessImageNameW
            query.argtypes=[c.c_void_p,c.c_uint32,c.POINTER(c.c_uint16),c.POINTER(c.c_uint32)]
            query.restype=c.c_int32
            buffer=(c.c_uint16*1024)();length=c.c_uint32(1024)
            need(time.monotonic()<deadline,'deadline')
            phase='query'
            ok=query(handle,0,buffer,c.byref(length))
            error=c.get_last_error() if not ok else None
            need(time.monotonic()<deadline,'deadline')
            phase='parse'
            need(type(ok) is int,'invalid_result')
            if not ok:
                need(type(error) is int and 0<=error<=0xffffffff,'invalid_result')
                value=_image_sample('buffer_limit' if error==122 else 'query_failed',index,win32=error)
            else:
                name,name_hash=_windows_image_name(list(buffer),length.value)
                need(time.monotonic()<deadline,'deadline')
                value=_image_sample('sampled' if name is not None else 'redacted_basename',index,name,name_hash)
            need(time.monotonic()<deadline,'deadline')
        except BaseException as error:
            status='deadline' if isinstance(error,ValueError) and str(error)=='deadline' else (
                'invalid_result' if phase=='parse' and isinstance(error,(UnicodeError,ValueError)) else 'api_exception')
            value=_image_sample(status,index)
        finally:
            if buffer is not None:
                try:c.memset(buffer,0,c.sizeof(buffer))
                except BaseException:value=_image_sample('api_exception',index)
        if time.monotonic()>=deadline:value=_image_sample('deadline',index)
        return value

    def diagnostic(self,cleanup_deadline):
        """One bounded observation, with no effect on the selected failure."""
        started=time.monotonic();deadline=min(cleanup_deadline,started+.100)
        value=dict(complete=False,observation='unknown',trigger=self.last_accounting,handles_closed=True,members=[],image_sample=_image_sample())
        image_selected=False
        step='accounting'
        try:
            need(self.assigned and bool(self.job),'invalid_job')
            need(time.monotonic()<deadline,'deadline')
            accounting=self.Accounting()
            ok=self.k.QueryInformationJobObject(self.job,1,self.c.byref(accounting),self.c.sizeof(accounting),None)
            error=int(self.c.get_last_error());need(time.monotonic()<deadline,'deadline')
            if not ok:value.update(error=step,win32=error);return _bounded_job_diagnostic(value)
            value['accounting']=dict(total=accounting.TotalProcesses,active=accounting.ActiveProcesses,terminated=accounting.TotalTerminatedProcesses)
            step='process_list';listing=self.ProcessList();length=self.w.DWORD()
            need(time.monotonic()<deadline,'deadline')
            ok=self.k.QueryInformationJobObject(self.job,3,self.c.byref(listing),self.c.sizeof(listing),self.c.byref(length))
            error=int(self.c.get_last_error());need(time.monotonic()<deadline,'deadline')
            value.update(assigned=int(listing.assigned),listed=int(listing.listed))
            if not ok:value.update(error=step,win32=error);return _bounded_job_diagnostic(value)
            need(0<=listing.listed==listing.assigned<=32 and
                 8+listing.listed*self.c.sizeof(self.c.c_size_t)<=length.value<=self.c.sizeof(listing),'invalid_list')
            pids=list(listing.pids[:listing.listed])
            need(len(set(pids))==len(pids) and all(0<pid<=0xffffffff for pid in pids),'invalid_list')
            for pid in pids:
                need(time.monotonic()<deadline,'deadline')
                row=dict(pid=int(pid));value['members'].append(row);handle=None
                try:
                    step='open';handle=self.k.OpenProcess(0x00101000,False,pid);error=int(self.c.get_last_error())
                    need(time.monotonic()<deadline,'deadline')
                    if not handle:row.update(error=step,win32=error);continue
                    step='membership';member=self.w.BOOL()
                    need(time.monotonic()<deadline,'deadline')
                    ok=self.k.IsProcessInJob(handle,self.job,self.c.byref(member));error=int(self.c.get_last_error())
                    need(time.monotonic()<deadline,'deadline')
                    if not ok:row.update(error=step,win32=error);continue
                    if not member.value:row['error']='membership_mismatch';continue
                    row['root']=pid==self.proc.pid
                    row.update(self.observe_member(handle,deadline))
                    if not image_selected and _windows_image_eligible(row):
                        image_selected=True
                        value['image_sample']=self.sample_image(handle,len(value['members'])-1,deadline)
                finally:
                    if handle:
                        try:
                            ok=self.k.CloseHandle(handle);error=int(self.c.get_last_error())
                            if not ok:row.update(error='close',win32=error);value['handles_closed']=False
                        except BaseException:row['error']='close_exception';value['handles_closed']=False
                        if time.monotonic()>=deadline:row['error']='deadline'
                need(time.monotonic()<deadline,'deadline')
            value['complete']=not any('error' in row for row in value['members'])
            if value['complete']:
                value['observation']='live_member_observed' if any(row['wait_before']==258 for row in value['members']) else 'no_live_member_observed_in_complete_snapshot'
        except BaseException as error:
            value['error']=str(error) if isinstance(error,ValueError) and str(error) in ('deadline','invalid_list','invalid_job') else 'api_exception'
            value['complete']=False;value['observation']='unknown'
        return _bounded_job_diagnostic(value)

    def terminate(self):
        if self.assigned:need(self.k.TerminateJobObject(self.job,1),'private job termination failed')
        elif self.proc is not None and self.proc.poll() is None:self.proc.kill()

    def close(self):
        need(not self.active(),'private job still has active members')
        if self.job:need(self.k.CloseHandle(self.job),'private job close failed');self.job=None


class OwnedChildError(ValueError):
    def __init__(self,message,owner):super().__init__(message);self.owner=owner


class OwnedChild:
    """One owned command, no overlapping/unmanaged launches in this interpreter."""
    def __init__(self,argv,cwd,env,stdin,stdout_path,stderr_path,timeout,stream_cap,*,completion_policy='strict-v1',deadline=None):
        global _ACTIVE_OWNER,_AUDIT_INSTALLED,_LAUNCH_THREAD,_LAUNCH_ARGV
        self.started=time.monotonic();self.deadline=min(self.started+timeout,deadline) if deadline is not None else self.started+timeout
        self.scan_deadline=self.deadline;self.proc=None;self.tree=None;self.completion_policy=completion_policy
        self.build_proof=None
        if completion_policy=='trusted-build-v1':
            self.build_proof=dict.fromkeys(BUILD_PROOF_KEYS)
            self.build_proof.update(schema='qbrain-n49d-build-completion-v1',policy=completion_policy,state='failed',
                reason='root-unavailable',success_deadline_us=max(0,int((self.deadline-self.started)*1000000)),
                teardown_requested=False,close_attempted=False,close_returned=False,close_in_budget=False)
        self.paths=[Path(stdout_path),Path(stderr_path)];self.stream_cap=stream_cap;self.result=None;self.stable=False
        self.readers=[];self.overflow=threading.Event();self.errors=[];self.locked=False;self.job_diagnostic=None
        for path in self.paths:path.parent.mkdir(parents=True,exist_ok=True);path.touch(exist_ok=False)
        try:
            need(timeout>0 and stream_cap>0,'invalid owned deadline/budget')
            need(completion_policy in ('strict-v1','trusted-build-v1') and
                 (completion_policy=='strict-v1' or os.name=='nt'),'unsupported owned completion policy')
            need(time.monotonic()<self.deadline,'timeout')
            need(threading.current_thread() is threading.main_thread(),'owned launch requires serial main-thread caller')
            need(_OWNER_LOCK.acquire(blocking=False),'concurrent owned process rejected');self.locked=True
            _ACTIVE_OWNER=self
            if not _AUDIT_INSTALLED:sys.addaudithook(_audit_launch);_AUDIT_INSTALLED=True
            self.tree=_WindowsTree() if os.name=='nt' else _LinuxTree()
            _LAUNCH_THREAD=threading.get_ident();_LAUNCH_ARGV=list(map(str,argv))
            try:
                self.proc=subprocess.Popen(_LAUNCH_ARGV,cwd=cwd,env=env,stdin=stdin,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                    close_fds=True,bufsize=0,start_new_session=os.name!='nt',creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP|0x00000004) if os.name=='nt' else 0)
            finally:_LAUNCH_THREAD=None;_LAUNCH_ARGV=None
            self.tree.proc=self.proc
            self.tree.attach(self.proc)
            for pipe,path in zip((self.proc.stdout,self.proc.stderr),self.paths):
                thread=threading.Thread(target=self._drain,args=(pipe,path),daemon=True);self.readers.append(thread);thread.start()
            self.check_budget()
        except BaseException as error:
            self._end(str(error));raise OwnedChildError(str(error),self) from error

    def _drain(self,pipe,path):
        try:
            with path.open('wb',buffering=0) as out:
                while data:=pipe.read(65536):
                    remaining=self.stream_cap-out.tell()
                    if len(data)>remaining:out.write(data[:max(0,remaining)]);self.overflow.set();break
                    out.write(data)
        except BaseException as error:self.errors.append(str(error));self.overflow.set()
        finally:pipe.close()

    def _diagnose_lingering(self,cleanup_deadline):
        if self.job_diagnostic is not None or not hasattr(self.tree,'diagnostic'):return
        self.job_diagnostic=dict(complete=False,observation='unknown',error='api_exception',members=[])
        try:self.job_diagnostic=_bounded_job_diagnostic(self.tree.diagnostic(cleanup_deadline))
        except BaseException:pass

    def _end(self,failure=None,intentional=False):
        global _ACTIVE_OWNER
        if self.result is not None:return self.result
        cleanup_deadline=time.monotonic()+2 if failure else self.deadline
        self.scan_deadline=cleanup_deadline;self.stable=False
        root_exit=None;no_root_failure=self.proc is None and bool(failure)
        build=getattr(self,'completion_policy','strict-v1')=='trusted-build-v1' and not intentional
        proof=getattr(self,'build_proof',None)
        if type(proof) is not dict:proof=None
        def observed(key,value=None):
            if proof is not None:
                proof[key]=max(0,int((time.monotonic()-self.started)*1000000)) if value is None else value
        def terminate():
            if proof is not None and proof.get('teardown_requested') is not True:
                observed('teardown_requested',True);observed('termination_requested_us')
            self.tree.terminate()
            if proof is not None:observed('termination_succeeded',True)
        close_attempted=False;close_returned=False;close_in_budget=False
        cleanup_ok=False;cleanup_error=None;capture_error=None
        streams={'stdout':None,'stderr':None}
        def budget(message):
            nonlocal failure
            if time.monotonic()>=cleanup_deadline:
                if not failure and time.monotonic()>=self.deadline:failure='timeout'
                raise ValueError(message)
        def cleanup():
            nonlocal root_exit,close_attempted,close_returned,close_in_budget,cleanup_deadline,failure
            budget('owned cleanup deadline exceeded')
            if self.tree is None:
                need(no_root_failure,'owned root/tree unavailable');return
            if failure or intentional:
                terminate();budget('owned cleanup deadline exceeded')
            while True:
                budget('owned cleanup deadline exceeded')
                if self.proc is not None and root_exit is None:
                    root_exit=self.proc.poll()
                    if root_exit is not None:
                        observed('root_exit',root_exit);observed('root_observed_us')
                budget('owned cleanup deadline exceeded')
                alive=self.tree.active();budget('owned cleanup deadline exceeded')
                need(self.proc is not None or no_root_failure,'owned root unavailable')
                if build and not failure:
                    need(root_exit is not None,'build root unavailable')
                    need(type(root_exit) is int and root_exit==0,'nonzero child exit')
                    if alive:
                        terminate();budget('owned cleanup deadline exceeded')
                        continue
                if alive and not failure and not intentional:
                    failure='lingering-descendant'
                    cleanup_deadline=min(cleanup_deadline,time.monotonic()+2);self.scan_deadline=cleanup_deadline
                    self._diagnose_lingering(cleanup_deadline)
                    raise ValueError(failure)
                if not alive and (root_exit is not None or no_root_failure):
                    observed('empty_observed_us');break
                if alive and (failure or intentional):
                    terminate();budget('owned cleanup deadline exceeded')
                time.sleep(min(.005,max(0,cleanup_deadline-time.monotonic())))
            budget('owned cleanup deadline exceeded')
            close_attempted=True;observed('close_attempted',True);observed('close_attempted_us')
            self.tree.close();close_returned=True;observed('close_returned',True);observed('close_returned_us')
            budget('owned cleanup deadline exceeded');close_in_budget=True;observed('close_in_budget',True)
        if failure=='lingering-descendant':self._diagnose_lingering(cleanup_deadline)
        try:
            if self.proc is not None and not self.readers:
                for pipe in (self.proc.stdout,self.proc.stderr):
                    if pipe is not None:pipe.close()
            cleanup();cleanup_ok=True
        except BaseException as error:
            cleanup_error=str(error);failure=failure or 'cleanup-failed'
            # A close attempt can partially release ownership. Never touch that
            # tree again; only pre-close errors permit this bounded fallback.
            if not close_attempted:
                try:cleanup();cleanup_ok=True
                except BaseException as retry_error:cleanup_error+='; '+str(retry_error)
        for thread in self.readers:
            try:
                budget('owned capture deadline exceeded')
                thread.join(max(0,cleanup_deadline-time.monotonic()))
                budget('owned capture deadline exceeded')
            except BaseException:
                capture_error='capture-deadline' if time.monotonic()>=cleanup_deadline else 'reader-join-failed'
        try:readers_done=not any(t.is_alive() for t in self.readers)
        except BaseException:readers_done=False;capture_error=capture_error or 'reader-state-unavailable'
        for key,path in zip(('stdout','stderr'),self.paths):
            if time.monotonic()>=cleanup_deadline:
                capture_error=capture_error or 'capture-deadline';continue
            try:
                streams[key]=descriptor(path)
                if time.monotonic()>=cleanup_deadline:capture_error=capture_error or 'capture-deadline'
            except BaseException:
                reason=key+'-unavailable'
                capture_error='both-unavailable' if capture_error=='stdout-unavailable' and key=='stderr' else (capture_error or reason)
        cleanup_ok=cleanup_ok and (self.tree is None or (close_returned and close_in_budget)) and readers_done and capture_error is None
        self.stable=cleanup_ok
        if not self.stable:failure=failure or ('timeout' if time.monotonic()>=self.deadline else 'capture-not-finalized')
        if self.overflow.is_set() or self.errors:failure=failure or 'output-limit'
        if not failure and time.monotonic()>=self.deadline:failure='timeout'
        if proof is not None and capture_error is None and readers_done:observed('streams_finalized_us')
        value=dict(classification=failure or ('stopped' if intentional else ('build-completed' if build else 'passed')),exit=root_exit,
            process_backend='windows-private-job' if os.name=='nt' else ('linux-stat-pidfd-subreaper' if _PROC_STAT_CHILD_ADAPTER else 'linux-children-pidfd-subreaper'),
            root_pid=self.proc.pid if self.proc else None,owned_tree_empty=cleanup_ok,
            cleanup_ok=cleanup_ok,cleanup_error=cleanup_error,stable=self.stable,readers_done=readers_done,
            elapsed_seconds=round(time.monotonic()-self.started,6),stdout=streams['stdout'],stderr=streams['stderr'])
        if capture_error is not None:value['capture_error']=capture_error
        if self.job_diagnostic is not None:value['job_diagnostic']=self.job_diagnostic
        if failure and isinstance(self.tree,_LinuxTree):
            try:_retain_linux_failure_detail(value,self.tree)
            except BaseException:
                try:value['failure_detail']=_linux_detail_unavailable('unknown')
                except BaseException:pass
        if time.monotonic()>=cleanup_deadline:
            failure=failure or 'timeout';self.stable=False;cleanup_ok=False
            value.update(classification=failure,owned_tree_empty=False,cleanup_ok=False,stable=False)
            value.setdefault('capture_error','capture-deadline')
        if proof is not None:
            if not failure and build:
                proof.update(state='complete',reason=None)
            else:
                reason=('deadline' if failure=='timeout' or time.monotonic()>=self.deadline else
                        'output-limit' if failure=='output-limit' else
                        'close-error' if close_attempted and not (close_returned and close_in_budget) else
                        'capture-error' if capture_error is not None else
                        'root-nonzero' if root_exit not in (None,0) else
                        'root-unavailable' if root_exit is None else 'ownership-error')
                proof.update(state='failed',reason=reason)
            value['build_completion']=dict(proof)
        if build and not failure:
            try:validate_build_proof(value)
            except Exception:
                failure='build-proof-incomplete';value['classification']=failure
                if type(value.get('build_completion')) is dict:value['build_completion'].update(state='failed',reason='evidence-error')
        if build and time.monotonic()>=cleanup_deadline:
            failure=failure or 'timeout';self.stable=False;cleanup_ok=False
            value.update(classification=failure,owned_tree_empty=False,cleanup_ok=False,stable=False)
            value.setdefault('capture_error','capture-deadline')
            if type(value.get('build_completion')) is dict:value['build_completion'].update(state='failed',reason='deadline')
        value['elapsed_seconds']=round(time.monotonic()-self.started,6)
        self.result=value
        if cleanup_ok and readers_done and self.locked:
            _ACTIVE_OWNER=None;self.locked=False;_OWNER_LOCK.release()
        return value

    def check_budget(self):
        failure='output-limit' if self.overflow.is_set() or self.errors else ('timeout' if time.monotonic()>=self.deadline else None)
        if failure:self._end(failure);raise OwnedChildError(failure,self)

    def wait(self,expected=0,timeout=None):
        need(getattr(self,'completion_policy','strict-v1')=='strict-v1','owned completion policy mismatch')
        return self._wait(expected,timeout,False)

    def complete_build(self):
        need(getattr(self,'completion_policy','strict-v1')=='trusted-build-v1' and os.name=='nt',
             'owned completion policy mismatch')
        return self._wait(0,None,True)

    def _wait(self,expected,timeout,build):
        classification='build-completed' if build else 'passed'
        if timeout is not None:self.deadline=min(self.deadline,self.started+timeout);self.scan_deadline=self.deadline
        if self.result is not None:
            if self.result['classification']!=classification:raise OwnedChildError(self.result['classification'],self)
            return self.result
        try:
            while True:
                self.check_budget();code=self.proc.poll()
                if build:self.check_budget()
                active=self.tree.active()
                if build:self.check_budget()
                if code is not None:
                    if active and not build:raise ValueError('lingering-descendant')
                    if code!=expected:raise ValueError('nonzero child exit')
                    if build:break
                    if not any(t.is_alive() for t in self.readers):break
                time.sleep(.005)
            value=self._end()
            if value['classification']!=classification:raise OwnedChildError(value['classification'],self)
            return value
        except BaseException as error:
            self._end('timeout' if str(error)!='lingering-descendant' and time.monotonic()>=self.deadline else str(error));raise OwnedChildError(self.result['classification'],self) from error

    def stop(self,reason='intentional_shutdown'):
        need(getattr(self,'completion_policy','strict-v1')=='strict-v1','owned completion policy mismatch')
        if self.result is not None:return self.result
        failure='timeout' if time.monotonic()>=self.deadline else None
        result=self._end(failure,intentional=True);result['stop_reason']=reason
        if result['classification']!='stopped':raise OwnedChildError(result['classification'],self)
        return result


class Recorder:
    def __init__(self, root, identity, required, environment, cwd, stream_cap=8*MIB):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=False)
        self.identity = identity; same_identity(identity, identity)
        self.required = list(required); need(len(set(required)) == len(required), 'duplicate required stage')
        self.environment = environment; self.cwd = Path(cwd); self.stream_cap = stream_cap
        self.stages = []; self.binary_pins = {};self.sealed={};self.qualification_reports={}

    def run(self, name, argv, timeout, binaries=(), produced=(), reports=(), check=None,prepare=None,finalize=None,phase=None):
        start=time.monotonic() if phase is None else phase['start']
        deadline=start+timeout if phase is None else phase['deadline']
        policy='strict-v1'
        if hasattr(self,'locations'):
            spec=stage_contract(self.identity,self.locations)[name]
            need(list(map(str,argv))==spec['argv'] and timeout==spec['timeout_seconds'] and
                 str(self.cwd)==self.locations['source'] and self.cwd.resolve()==ROOT and
                 [Path(p).relative_to(self.root).as_posix() for p in reports]==spec['reports'] and
                 sorted(map(str,binaries))==spec['binaries_before'] and
                 sorted(set(map(str,(*binaries,*produced))))==spec['binaries_after'],'recorder fixed stage selection')
            policy=spec['completion_policy']
            need((phase is not None)==(name in ('direct-tests-build','direct-tests-run')),'fixed phase window missing')
        need(name in self.required and name not in self.stages, 'unexpected/duplicate stage')
        folder = self.root / 'stages' / name; folder.mkdir(parents=True)
        self.stages.append(name)
        before={}
        result = dict(schema='qbrain-n49d-stage-v2',name=name,identity=self.identity,
                      completion_policy=policy,phase_window=None if phase is None else dict(phase['window']),
                      argv=[str(a) for a in argv],cwd=str(self.cwd),timeout_seconds=timeout,
                      stream_limit=self.stream_cap,exit=None,classification='incomplete',
                      requested_reports=[Path(p).relative_to(self.root).as_posix() for p in reports],
                      binaries_before=before,binaries_after={},runtime_options={k:self.environment[k] for k in ('ASAN_OPTIONS','UBSAN_OPTIONS') if k in self.environment})
        failure=None;child=None
        streams=[folder/'stdout.bin',folder/'stderr.bin']
        def fail(error):
            nonlocal failure,child
            failure=failure or str(error);result['classification']=failure
            if isinstance(error,OwnedChildError):child=error.owner
            if child is not None:
                result['ownership']=child.result;result['exit']=child.result.get('exit') if child.result else None
        def retain_failed():
            result.setdefault('ownership',None)
            terminal=result.get('ownership') or {}
            for key in ('stdout','stderr'):result.setdefault(key,terminal.get(key))
            result['available_reports']={**result.get('reports',{}),**result.get('available_reports',{})}
            self.failed_result=result
        try:
            if prepare:prepare(deadline)
            for p in binaries:before[str(p)]=descriptor(p)
            for p,value in before.items():
                need(self.binary_pins.setdefault(p,value)==value,'binary mutation before stage')
            need(time.monotonic()<deadline,'timeout during stage setup')
            child=OwnedChild(result['argv'],self.cwd,self.environment,subprocess.DEVNULL,*streams,deadline-time.monotonic(),self.stream_cap,
                             completion_policy=policy,deadline=deadline)
            terminal=child.complete_build() if policy=='trusted-build-v1' else child.wait()
            result['exit']=terminal['exit'];result['ownership']=terminal
            after=result['binaries_after']
            for p in list(binaries)+list(produced):after[str(p)]=descriptor(p)
            need(all(after[p] == value for p,value in before.items()), 'binary mutation during stage')
            for p,value in after.items():
                need(self.binary_pins.setdefault(p,value) == value, 'binary identity swapped')
            if finalize:finalize(deadline)
            result['reports']={}
            for p in reports:result['reports'][Path(p).relative_to(self.root).as_posix()]=descriptor(p)
            if check: check()
            need(time.monotonic()<deadline,'timeout during stage finalization')
            result['classification']='passed'
        except Exception as error:fail(error)
        if failure is None:
            try:
                result['available_reports']={}
                for p in reports:
                    if Path(p).is_file():result['available_reports'][Path(p).relative_to(self.root).as_posix()]=descriptor(p)
                result['stdout']=descriptor(streams[0]);result['stderr']=descriptor(streams[1])
                need(time.monotonic()<deadline,'timeout during evidence finalization')
            except Exception as error:fail(error)
        result['elapsed_seconds']=round(time.monotonic()-start,3)
        if failure is not None:retain_failed()
        try:
            dump(folder/'result.json',result)
            sealed=None
            if failure is None:
                raw=(folder/'result.json').read_bytes()
                need(json_unique(raw)==result,'sealed result changed')
                sealed=dict(size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            ended=time.monotonic()
            if failure is None and ended>=deadline:
                fail(ValueError('timeout during result write'));retain_failed();dump(folder/'result.json',result)
        except Exception as error:
            fail(error);retain_failed();result['evidence_error']='result-write-unavailable'
            raise ValueError(f'{name}: {failure}; result evidence unavailable') from error
        need(result['classification']=='passed',f'{name}: {failure}')
        self.sealed[name]=dict(result=sealed,ended=ended)
        return result

    def finish(self, source_before, source_after):
        need(self.stages == self.required, 'missing/duplicate/out-of-order required stage')
        need(source_before == source_after, 'source mutation after capture')
        for p,value in self.binary_pins.items():
            need(descriptor(p) == value, 'binary mutation after capture')
        result = dict(schema='qbrain-n49d-qualification-v2',passed=True,identity=self.identity,reports=self.qualification_reports,
                      required=self.required,stages=self.stages,binaries=self.binary_pins,locations=getattr(self,'locations',None),
                      source_before=source_before,source_after=source_after,
                      native_http='required-and-executed' if self.identity['job_key'].startswith('windows') else 'not-applicable-non-Windows-stub',
                      acceptance='native evidence only; independent outcome acceptance pending')
        dump(self.root/'qualification.json',result)
        validate_recordings(lambda p:(self.root/p).read_bytes(), self.identity, self.required)
        return result


def phase_seed(role,identity):
    value=dict.fromkeys(PHASE_KEYS[role].split())
    value.update(schema=PHASE_REPORTS[role][1],state='prepared',identity=identity)
    if role=='objects':value.update(produced=[],consumed=[])
    elif role=='build-context':value.update(mode='build-only',architecture='x64',cwd_role='build/cl')
    elif role=='run-context':value.update(mode='run-only')
    elif role=='configure':value.update(checks=dict.fromkeys(CONFIGURE_CHECKS),files={})
    else:value.update(pair_budget_us=1800000000,build_budget_us=1200000000,run_budget_us=600000000)
    return phase_report(role,value,identity)


class DirectTestPair:
    """One fixed build/run clock; only qualification may bind the final report."""
    def __init__(self,recorder):
        self.recorder=recorder;self.started=time.monotonic();self.deadline=self.started+1800
        self.path=recorder.root/PHASE_REPORTS['pair'][0]
        self.value=phase_seed('pair',recorder.identity);self.windows={};self.result=None;self.failure=None
        write_phase(self.path,'pair',self.value,recorder.identity,self.deadline)

    def phase(self,name):
        need(self.result is None and self.failure is None,'pair already terminal')
        need(name in ('direct-tests-build','direct-tests-run') and name not in self.windows,'pair phase order')
        if name=='direct-tests-build':
            need(not self.windows,'pair phase order');start=self.started;seconds=1200
        else:
            need(self.value['build'] is not None and list(self.windows)==['direct-tests-build'],'pair build not sealed')
            start=time.monotonic();seconds=600
        need(time.monotonic()<self.deadline,'pair handoff deadline')
        offset=int((start-self.started)*1000000)
        effective=min(offset+seconds*1000000,1800000000)
        phase=dict(start=start,deadline=min(start+seconds,self.deadline),
            window=dict(phase=name,start_us=offset,effective_deadline_us=effective,pair_budget_us=1800000000))
        self.windows[name]=phase
        return phase

    def sealed(self,name):
        phase=self.windows[name];sealed=self.recorder.sealed[name]
        need(sealed['ended']<phase['deadline'] and time.monotonic()<self.deadline,'pair phase sealing deadline')
        self.value['build' if name=='direct-tests-build' else 'run']=dict(
            stage=name,start_us=phase['window']['start_us'],end_us=int((sealed['ended']-self.started)*1000000),
            effective_deadline_us=phase['window']['effective_deadline_us'],result=sealed['result'])

    def fail(self,reason):
        if self.failure is None and self.result is None:self.failure=reason
        return self.failure

    def finish(self):
        if self.failure is not None:raise ValueError(self.failure)
        if self.result is not None:return self.result
        try:
            need(time.monotonic()<self.deadline,'pair-finalization-timeout')
            self.value.update(state='complete',finalize_begin_us=int((time.monotonic()-self.started)*1000000))
            phase_report('pair',self.value,self.recorder.identity,True)
            desc=write_phase(self.path,'pair',self.value,self.recorder.identity)
            ended=time.monotonic();need(ended<self.deadline,'pair-finalization-timeout')
            self.result=dict(**desc,finalized_us=int((ended-self.started)*1000000))
            self.recorder.qualification_reports[PHASE_REPORTS['pair'][0]]=self.result
            return self.result
        except BaseException as error:
            self.fail('pair-finalization-timeout' if time.monotonic()>=self.deadline or str(error)=='pair-finalization-timeout' else 'pair-report-unavailable')
            raise ValueError(self.failure) from error

    def diagnostic(self):
        return dict(acceptance=self.result is not None and self.failure is None,
                    failure=self.failure,report=self.result)


def _read_phase_file(recorder,role,ready=False):
    path=recorder.root/PHASE_REPORTS[role][0]
    with path.open('rb') as stream:raw=stream.read(PHASE_REPORTS[role][2]+1)
    return read_phase_bytes(raw,role,recorder.identity,ready)


def prepare_phase(recorder,role,deadline):
    write_phase(recorder.root/PHASE_REPORTS[role][0],role,phase_seed(role,recorder.identity),recorder.identity,deadline)


def finalize_production(recorder,deadline):
    value=object_report(recorder.cwd,recorder.identity)
    write_phase(recorder.root/PHASE_REPORTS['objects'][0],'objects',value,recorder.identity,deadline)


def prepare_test_build(recorder,deadline):
    value=_read_phase_file(recorder,'objects',True)
    object_report(recorder.cwd,recorder.identity,value)
    prepare_phase(recorder,'build-context',deadline)


def finalize_test_build(recorder,deadline):
    objects=_read_phase_file(recorder,'objects',True)
    object_report(recorder.cwd,recorder.identity,objects)
    value=_read_phase_file(recorder,'build-context')
    need(value['state']=='prepared' and value['canonical_binary'] is not None,'copied binary observation missing')
    need(value['production_objects']==descriptor(recorder.root/PHASE_REPORTS['objects'][0]) and
         value['production_executable']==objects['production_executable'],'build input observation mismatch')
    actual=fixed_file(recorder.cwd/'build/cl','qbrain_tests.exe')
    need(value['canonical_binary']==actual,'copied binary observation mismatch')
    value.update(state='ready',failure=None)
    write_phase(recorder.root/PHASE_REPORTS['build-context'][0],'build-context',value,recorder.identity,deadline)


def finalize_test_run(recorder,deadline):
    build=_read_phase_file(recorder,'build-context',True);run=_read_phase_file(recorder,'run-context',True)
    need(run['build_context']==descriptor(recorder.root/PHASE_REPORTS['build-context'][0]) and
         run['canonical_binary']==build['canonical_binary']==fixed_file(recorder.cwd/'build/cl','qbrain_tests.exe'),'run context/binary binding mismatch')
    need(time.monotonic()<deadline,'timeout during run context finalization')


def finalize_configure(recorder,deadline):
    value=configure_report(recorder.locations,recorder.identity)
    write_phase(recorder.root/PHASE_REPORTS['configure'][0],'configure',value,recorder.identity,deadline)


def prepare_cmake_build(recorder,deadline):
    value=_read_phase_file(recorder,'configure',True)
    need(value['files']=={n:fixed_file(recorder.locations['build'],n,MIB) for n in CONFIGURE_FILES},'configure handoff changed')
    need(time.monotonic()<deadline,'timeout during configure handoff')


def validate_semantics(read, expected, result):
    job=expected['job_key']
    for mode in ('normal','optimized'):
        checks=json.loads(read('stages/selftest-'+mode+'/stdout.bin'))
        need(checks.get('passed') is True and checks.get('python_optimized')==(mode=='optimized') and
             checks.get('controls') and all(c.get('passed') is True for c in checks['controls']), 'source controls semantic failure')
        if job.startswith('windows'):
            need(WINDOWS_PHASE_CONTROL_NAMES<={c.get('name') for c in checks['controls']},'native Windows phase controls required')
        if job.startswith('linux'):
            need(checks.get('linux_reader_backend')=='native-children','native Linux children-interface controls required')
    if job=='linux-sanitizers':
        effective=json.loads(read('reports/sanitizer-effective.json'));validate_sanitizer_flags(effective)
        for name in ('sanitize-mcp','sanitize-directory'):
            stage=json.loads(read('stages/'+name+'/result.json'))
            need(read('stages/'+name+'/stderr.bin')==b'' and stage.get('runtime_options')==effective['runtime_options'],
                 'sanitizer diagnostics/options mismatch')
        return
    if job!='windows-msvc':
        names=ctest_values(json.loads(read('stages/ctest-inventory/stdout.bin')),read('reports/ctest.xml'))
        need(json.loads(read('stages/ctest-completeness/stdout.bin'))==names,'CTest completeness semantic mismatch')
    if job.startswith('windows'):
        name='direct-tests-run' if job=='windows-msvc' else 'canonical-run'
        groups=native_groups((ROOT/'tests/test_main.cpp').read_text(encoding='utf-8'),read('stages/'+name+'/stdout.bin').decode('utf-8',errors='replace'))
        need(json.loads(read('stages/canonical-groups/stdout.bin'))==groups,'canonical group semantic mismatch')
    for mode in ('normal','optimized'):
        directory=json.loads(read('reports/directory_search-'+mode+'/RESULT.json'))
        need(directory.get('passed') is True and directory.get('checks') and all(c.get('passed') is True for c in directory['checks']) and
             directory.get('check_count')==len(directory['checks']) and directory.get('command_count')==len(directory.get('commands',[]))>0,
             'directory report semantic failure')
        context=json.loads(read('reports/context_process-'+mode+'.json'))
        need(context.get('format_version')==1 and isinstance(context.get('checks'),int) and context['checks']>0 and
             context.get('provider_calls')==0,'context report semantic failure')
        named=json.loads(read('reports/named_arguments-'+mode+'.json'))
        need(named.get('failed')==0 and named.get('checks') and all(c.get('passed') is True for c in named['checks']) and
             named.get('passed')==len(named['checks']) and named.get('command_count')==len(named.get('commands',[]))>0,
             'named-argument report semantic failure')
        stage=json.loads(read('stages/named_arguments-'+mode+'/result.json'))
        need(named.get('binary_sha256') in {v['sha256'] for v in stage['binaries_before'].values()},'named-argument binary mismatch')
        if job=='windows-cmake':
            report=json.loads(read('reports/winhttp-'+mode+'.json'))
            stage=json.loads(read('stages/winhttp-'+mode+'/result.json'))
            need(report.get('result')=='PASS' and report.get('native_windows') is True and report.get('checks') and
                 report.get('check_count')==len(report['checks']) and report.get('source_commit')==expected['commit'] and
                 report.get('probe_sha256') in {v['sha256'] for v in stage['binaries_before'].values()}, 'WinHTTP semantic failure')


def changed_source_members(paths):
    need(paths is not None,'complete evidence inventory required')
    names=list(paths)
    need(all(isinstance(p,str) for p in names),'invalid evidence path inventory')
    expected=['source/changed/'+p for p in sorted(source_guard.ALLOW)]
    need(sorted(p for p in names if p.startswith('source/changed/'))==expected,'fixed changed source leaf inventory mismatch')
    return expected


STAGE_SUCCESS_KEYS = ('schema name identity completion_policy phase_window argv cwd timeout_seconds stream_limit exit classification '
    'requested_reports binaries_before binaries_after runtime_options ownership reports available_reports stdout stderr elapsed_seconds').split()
QUALIFICATION_KEYS = ('schema passed identity reports required stages binaries locations source_before source_after native_http acceptance retained_binaries').split()
OWNER_SUCCESS_KEYS = ('classification exit process_backend root_pid owned_tree_empty cleanup_ok cleanup_error stable readers_done elapsed_seconds stdout stderr').split()


def validate_phase_evidence(read,result,stages):
    identity=result['identity'];job=identity['job_key'];locations=result['locations']
    exact_keys(result['reports'],[PHASE_REPORTS['pair'][0]] if job=='windows-msvc' else [],'qualification report inventory')
    def report(role):
        return read_phase_bytes(read(PHASE_REPORTS[role][0]),role,identity,True)
    if job=='windows-cmake':
        import ntpath
        value=report('configure')
        for key,text in (('source_location',locations['source']),('build_location',locations['build']),
                         ('overlay_location',ntpath.join(locations['source'],'.ci','mcp_directory_search_targets.cmake'))):
            need(value[key]==path_identity(text),'configure location identity mismatch')
    if job!='windows-msvc':return
    obj=report('objects');build=report('build-context');run=report('run-context');pair=report('pair')
    def described(path):
        raw=read(path);return dict(size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    need(build['production_objects']==described(PHASE_REPORTS['objects'][0]) and
         build['production_executable']==obj['production_executable'],'phase production binding mismatch')
    need(run['build_context']==described(PHASE_REPORTS['build-context'][0]) and
         run['canonical_binary']==build['canonical_binary'],'phase canonical binding mismatch')
    import ntpath
    production=ntpath.join(locations['source'],'build','cl','qbrain.exe')
    canonical=ntpath.join(locations['source'],'build','cl','qbrain_tests.exe')
    need(stages['direct-production']['binaries_after'][production]==obj['production_executable'] and
         stages['direct-tests-build']['binaries_before'][production]==obj['production_executable'] and
         stages['direct-tests-build']['binaries_after'][canonical]==build['canonical_binary'] and
         stages['direct-tests-run']['binaries_before'][canonical]==build['canonical_binary'],'phase artifact identity mismatch')
    binding=result['reports'][PHASE_REPORTS['pair'][0]];exact_keys(binding,'size sha256 finalized_us')
    report_descriptor({k:binding[k] for k in ('size','sha256')});uint(binding['finalized_us'])
    need({k:binding[k] for k in ('size','sha256')}==described(PHASE_REPORTS['pair'][0]) and
         pair['finalize_begin_us']<=binding['finalized_us']<1800000000,'pair publication binding/deadline')
    for key in ('build','run'):
        entry=pair[key];name=entry['stage'];stage=stages[name]
        need(entry['result']==described('stages/'+name+'/result.json'),'pair sealed stage binding mismatch')
        need(stage['phase_window']==dict(phase=name,start_us=entry['start_us'],
            effective_deadline_us=entry['effective_deadline_us'],pair_budget_us=1800000000),'pair phase window mismatch')


def validate_recordings(read, expected, required=None, *, files=None):
    """Same fail-closed recorder contract is checked before packaging and after download."""
    result = json_unique(read('qualification.json'))
    same_identity(result['identity'],expected)
    full_contract = required is None
    exact_keys(result,QUALIFICATION_KEYS if full_contract else set(QUALIFICATION_KEYS)-({'retained_binaries'} if 'retained_binaries' not in result else set()),'qualification key inventory')
    need(result['schema']=='qbrain-n49d-qualification-v2','qualification schema mismatch')
    required = required if required is not None else required_stages(expected['job_key'])
    need(result.get('passed') is True and result['required'] == required and result['stages'] == required,
         'missing/duplicate required stage')
    need(len(required) == len(set(required)), 'duplicate required stages')
    need(result['source_before'] == result['source_after'], 'source identity mutated')
    binary_pins = result['binaries']
    contracts=stage_contract(expected,result['locations']) if full_contract else None
    stage_records={}
    for name in required:
        folder = 'stages/'+name+'/'
        stage = json_unique(read(folder+'result.json'));stage_records[name]=stage
        exact_keys(stage,STAGE_SUCCESS_KEYS,'stage success key inventory')
        need(stage['schema']=='qbrain-n49d-stage-v2','stage schema mismatch')
        same_identity(stage['identity'], expected)
        need(stage['name'] == name and stage['classification'] == 'passed' and stage['exit'] == 0,
             'failed/incomplete stage')
        need(isinstance(stage['argv'],list) and bool(stage['argv']), 'stage command missing')
        requested=stage.get('requested_reports')
        need(isinstance(requested,list) and len(requested)==len(set(requested)) and
             set(stage.get('reports',{}))==set(requested),'requested report inventory mismatch')
        if contracts is not None:
            spec=contracts[name]
            ownership=stage.get('ownership',{})
            exact_keys(ownership,OWNER_SUCCESS_KEYS+(['build_completion'] if spec['completion_policy']=='trusted-build-v1' else []),'stage owner key inventory')
            need(stage['completion_policy']==spec['completion_policy'],'fixed stage completion policy mismatch')
            if spec['completion_policy']=='trusted-build-v1':
                proof=validate_build_proof(ownership)
                need(proof['success_deadline_us']<=spec['timeout_seconds']*1000000,'build success deadline extended')
            else:
                need(ownership.get('classification')=='passed' and ownership.get('cleanup_ok') is True and
                     ownership.get('stable') is True and ownership.get('readers_done') is True and
                     ownership.get('owned_tree_empty') is True and type(ownership.get('exit')) is int and ownership['exit']==0 and
                     ownership.get('cleanup_error') is None,'stage ownership proof missing')
            window=stage['phase_window']
            if name in ('direct-tests-build','direct-tests-run'):
                exact_keys(window,'phase start_us effective_deadline_us pair_budget_us')
                need(window['phase']==name and type(window['pair_budget_us']) is int and window['pair_budget_us']==1800000000,'stage pair window')
                uint(window['start_us']);uint(window['effective_deadline_us'])
            else:need(window is None,'unexpected stage phase window')
            need(ownership.get('stdout')==stage['stdout'] and ownership.get('stderr')==stage['stderr'], 'stage finalized stream binding mismatch')
            need(stage['argv']==spec['argv'] and stage['timeout_seconds']==spec['timeout_seconds'] and
                 stage['cwd']==result['locations']['source'], 'fixed stage command mismatch')
            need(requested==spec['reports'] and stage['available_reports']==stage['reports'], 'fixed required report inventory mismatch')
            need(type(stage['timeout_seconds']) is int and type(stage['stream_limit']) is int and stage['stream_limit']==8*MIB,'stage limits mismatch')
            need(type(stage['elapsed_seconds']) in (int,float) and 0<=stage['elapsed_seconds']<spec['timeout_seconds'],'stage elapsed deadline')
            need(sorted(stage['binaries_before'])==spec['binaries_before'] and sorted(stage['binaries_after'])==spec['binaries_after'], 'fixed binary inventory mismatch')
        for stream in ('stdout','stderr'):
            data = read(folder+stream+'.bin')
            need(dict(size=len(data),sha256=hashlib.sha256(data).hexdigest()) == stage[stream], 'raw stream missing/mutated')
        for path,value in stage.get('reports',{}).items():
            data = read(path)
            need(dict(size=len(data),sha256=hashlib.sha256(data).hexdigest()) == value, 'result report missing/mutated')
        for p,value in stage['binaries_before'].items():
            need(stage['binaries_after'].get(p) == value, 'stage binary changed')
        for p,value in stage['binaries_after'].items():
            need(binary_pins.get(p) == value, 'swapped binary identity')
    if full_contract:
        validate_phase_evidence(read,result,stage_records)
        validate_semantics(read,expected,result)
        if expected['job_key']!='linux-sanitizers':
            for mode in ('normal','optimized'):
                name='mcp_directory_search-'+mode
                report=json.loads(read('reports/'+name+'/RESULT.json'))
                need(report.get('schema')=='qbrain-n49d-mcp-directory-process-v1' and report.get('passed') is True and
                     report.get('status')=='passed' and report.get('python_optimized')==(mode=='optimized'), 'MCP process report incomplete')
                need(report.get('stdio')==dict(status='passed',profiles=['full','memory']), 'stdio profiles missing')
                prefix='reports/'+name+'/'
                def raw_descriptor(value):
                    path=value.get('path','')
                    need(path.startswith('raw/') and all(p not in ('','.','..') for p in path.split('/')), 'MCP raw path invalid')
                    data=read(prefix+path)
                    need(len(data)==value.get('bytes') and hashlib.sha256(data).hexdigest()==value.get('sha256'), 'MCP raw evidence mismatch')
                    return data
                need(report.get('commands') and report.get('command_count')==len(report['commands']), 'MCP command inventory incomplete')
                process_stage=json.loads(read('stages/'+name+'/result.json'))
                production=process_stage['argv'][process_stage['argv'].index('--binary')+1]
                for command in report['commands']:
                    need(command.get('argv') and command['argv'][0]==production, 'MCP command binary path mismatch')
                    need(command.get('status') in ('completed','server_stopped_after_checks') and
                         command.get('finalization_classification')!='timeout', 'MCP command finalization incomplete')
                    ownership=command.get('ownership',{})
                    need(command.get('stable') is True and ownership.get('stable') is True and ownership.get('cleanup_ok') is True and
                         ownership.get('readers_done') is True and ownership.get('classification') in ('passed','stopped'), 'MCP process ownership incomplete')
                    need(command.get('exit')==ownership.get('exit'), 'MCP command exit mismatch')
                    for key in ('stdin','stdout','stderr'):
                        raw_descriptor(command[key])
                        if key!='stdin':need(ownership.get(key)==dict(size=command[key]['bytes'],sha256=command[key]['sha256']), 'MCP stable stream binding mismatch')
                exchanges=report.get('exchanges',[])
                need(report.get('exchange_count')==len(exchanges), 'MCP exchange inventory mismatch')
                for exchange in exchanges:
                    need(exchange.get('status')=='completed', 'MCP exchange incomplete')
                    raw_descriptor(exchange['request']);raw_descriptor(exchange['response'])
                provider=report.get('provider_http',{})
                if expected['job_key'].startswith('windows'):
                    batches=provider.get('batches',[]);requests=provider.get('requests',[])
                    need(provider.get('required') is True and provider.get('status')=='passed' and
                         provider.get('profiles')==['full','memory'] and provider.get('transports')==['stdio','http'] and
                         {(b['profile'],b['transport']) for b in batches}=={(p,t) for p in ('full','memory') for t in ('stdio','http')} and len(batches)==4,
                         'native provider fixture missing')
                    negatives=[];positives=[]
                    for batch in batches:
                        need(batch.get('status')=='passed' and batch.get('negative_request_count')==0 and batch.get('negative_query_count')==27 and
                             len(batch.get('negative_cases',[]))==27 and len(batch.get('positive_controls',[]))==2,'provider batch incomplete')
                        need(all(c.get('provider_requests')==0 and c.get('expected_error') for c in batch['negative_cases']), 'provider rejection made request')
                        negatives.extend(c['query'] for c in batch['negative_cases']);positives.extend(batch['positive_controls'])
                    need(len(set(negatives))==108 and provider.get('negative_query_count')==108 and provider.get('negative_request_count')==0 and
                         provider.get('positive_request_count')==8 and len(requests)==len(positives)==8,'provider aggregate counts')
                    need(len({p['query'] for p in positives})==8,'provider positive queries not fresh')
                    for index,(positive,capture) in enumerate(zip(positives,requests)):
                        need(positive.get('record_index')==index and positive.get('provider_requests')==1 and positive['query']==capture.get('query') and
                             capture.get('status')=='completed' and positive['query'] not in negatives,'provider positive capture binding')
                        request_raw=raw_descriptor(capture['request']);response_raw=raw_descriptor(capture['response'])
                        need(json.loads(request_raw.split(b'\r\n\r\n',1)[1]).get('input')==[positive['query']] and
                             response_raw.startswith(b'HTTP/1.1 200 '),'provider wire capture mismatch')
                else:
                    need(provider.get('required') is False and provider.get('status')=='not_applicable' and
                         not any(k in provider for k in ('requests','batches','positive_request_count','negative_request_count')), 'Linux provider-network claim')
                http=report.get('http',{})
                if expected['job_key'].startswith('windows'):
                    need(http.get('required') is True and http.get('status')=='passed' and
                         http.get('profiles')==['full','memory'] and bool(http.get('authentication')), 'native authenticated HTTP missing')
                else:
                    need(http.get('required') is False and http.get('status')=='not_applicable' and 'profiles' not in http,
                         'Linux HTTP cannot claim native acceptance')
                stage=json.loads(read('stages/'+name+'/result.json'))
                need(report['binary_sha256'] in {v['sha256'] for v in stage['binaries_before'].values()}, 'MCP tested binary mismatch')
        before=read('reports/source-before.json'); after=read('reports/source-after.json')
        need(before==after and dict(size=len(before),sha256=hashlib.sha256(before).hexdigest())==result['source_before'],
             'source report changed after capture')
        binding=json.loads(before)
        need(binding.get('passed') is True and binding.get('commit')==expected['commit'] and
             binding.get('tree')==expected['tree'] and binding.get('base')==source_guard.BASE and
             binding.get('base_tree')==source_guard.BASE_TREE and binding.get('precommit') is False and
             binding.get('parent')==source_guard.CORRECTION_PARENT and
             binding.get('parent_tree')==source_guard.CORRECTION_PARENT_TREE and
             binding.get('correction_changed')==sorted(source_guard.CORRECTION_PATHS),
             'source/candidate binding mismatch')
        need(json.loads(read('source/dependencies.json'))==binding['dependency_sha256'], 'dependency manifest mismatch')
        inventory=read('source/tree-inventory.bin')
        need(hashlib.sha256(inventory).hexdigest()==binding['inventory_sha256'], 'tree inventory identity mismatch')
        tree=source_guard.generic_tree_reader(ROOT)(inventory,expected['tree'])
        approved=sorted(source_guard.ALLOW)
        need(binding.get('changed')==approved,'fixed changed source list mismatch')
        changed=binding.get('changed_files')
        need(isinstance(changed,dict) and sorted(changed)==approved,'fixed changed source map mismatch')
        changed_source_members(files)
        for path in approved:
            row=changed[path]
            data=read('source/changed/'+path)
            if path in source_guard.WRAPPERS:need(source_guard.blob(data)==source_guard.WRAPPERS[path],'source wrapper pin mismatch')
            need(row['mode']=='100644' and hashlib.sha256(data).hexdigest()==row['sha256'] and source_guard.blob(data)==row['blob'] and
                 tree.get(path)==(row['mode'],row['blob']), 'changed source bytes mismatch')
        retained=result['retained_binaries']
        expected_names=set(TARGETS[:2]) if expected['job_key']=='linux-sanitizers' else {'qbrain.exe' if expected['job_key'].startswith('windows') else 'qbrain'}
        need({Path(row['path']).name for row in retained.values()}==expected_names and len(retained)==len(expected_names), 'required binary bytes missing')
        for original,row in retained.items():
            need(row['path'].startswith('binaries/'), 'binary member location')
            value={k:row[k] for k in ('size','sha256')}
            need(binary_pins.get(original)==value, 'retained binary identity swapped')
            if hasattr(read,'describe'):
                observed=read.describe(row['path'])
            else:
                data=read(row['path']); observed=dict(size=len(data),sha256=hashlib.sha256(data).hexdigest())
            need(observed==value, 'retained binary bytes mutated')
    return result


def evidence_inventory(root, limits=LIMITS):
    paths=[]; size=0
    for p in sorted(Path(root).rglob('*')):
        need(not p.is_symlink(), 'evidence symlink')
        if p.is_dir(): continue
        need(p.is_file(), 'evidence nonregular member')
        size += p.stat().st_size; paths.append(p)
        need(size <= limits['raw'] and len(paths) <= limits['members'], 'raw/member cap exceeded')
    need(paths, 'empty evidence')
    return dict(raw_bytes=size,member_count=len(paths))


def validate_manifest(raw, identity, limits=LIMITS):
    need(0 < len(raw) <= limits['manifest'], 'N49D manifest cap')
    m=json.loads(raw); same_identity(m['identity'],identity)
    need(m['schema']=='qbrain-n49c-evidence-parts-v1','transport schema mismatch')
    rows=m['files']; need(isinstance(rows,list) and 0<len(rows)<=limits['members'],'N49D member cap')
    names=[r['path'] for r in rows]
    need(names==sorted(set(names)),'duplicate/unsorted evidence members')
    for row in rows:
        name=row['path']
        need(isinstance(name,str) and name and '\\' not in name and ':' not in name and
             all(p not in ('','.','..') for p in name.split('/')),'unsafe member')
        need(isinstance(row['size'],int) and 0<=row['size']<=limits['raw'] and stat.S_ISREG(row['mode']), 'member type/size')
        need(re.fullmatch('[0-9a-f]{64}',row['sha256']) is not None,'invalid leaf digest')
    need(sum(r['size'] for r in rows)==m['uncompressed_bytes']<=limits['raw'],'N49D raw cap')
    need(0<m['archive']['size']<=limits['compressed'],'N49D compressed cap')
    need(len(m['parts'])==1,'exactly one part00 required')
    part=m['parts'][0]
    need(part==dict(index=0,file='evidence.part',size=m['archive']['size'],sha256=m['archive']['sha256']), 'single part binding mismatch')
    return m


def package(root, staging, identity, limits=LIMITS, *, _generic_packager=None):
    before=evidence_inventory(root,limits)
    snapshots={p.relative_to(root).as_posix():descriptor(p) for p in Path(root).rglob('*') if p.is_file()}
    def read(p):return (Path(root)/p).read_bytes()
    read.describe=lambda p:descriptor(Path(root)/p)
    validate_recordings(read,identity,files=snapshots)
    # Keep every original inherited packager guard. CI has its required capacity.
    invoke=_generic_packager if _generic_packager is not None else generic_archive()['package_evidence']
    result=invoke(root,staging,identity)
    need(result.get('passed') is True and result.get('identity')==identity,'generic package result identity/status')
    manifest=Path(result['parts_root'])/'00'/'manifest.json'
    raw=manifest.read_bytes();m=validate_manifest(raw,identity,limits)
    need(result.get('manifest_sha256')==hashlib.sha256(raw).hexdigest() and result.get('manifest_bytes')==len(raw) and
         result.get('archive_sha256')==m['archive']['sha256'],'generic package result digest mismatch')
    part=manifest.parent/'evidence.part'
    need(descriptor(part)==m['archive'],'generic package part mismatch')
    need({r['path']:{k:r[k] for k in ('size','sha256')} for r in m['files']}==snapshots,'generic package leaf inventory mismatch')
    generic_archive()['verify_evidence_archive'](part,m)
    need({p.relative_to(root).as_posix():descriptor(p) for p in Path(root).rglob('*') if p.is_file()}==snapshots,'evidence mutated during package')
    need(evidence_inventory(root,limits)==before,'evidence changed during package')
    need(result['part_count']==1 and result['archive_size']==m['archive']['size'],'package part mismatch')
    result.update(before)
    result['required_binary_bytes']={p.name:p.stat().st_size for p in (Path(root)/'binaries').iterdir()}
    result['outer_zip_upper_bound']=result['archive_size']+result['manifest_bytes']+4096
    need(result['outer_zip_upper_bound']<=limits['outer'],'outer ZIP framing cap')
    return result


def staging_size(root):
    total=0
    for p in Path(root).rglob('*'):
        need(not p.is_symlink(),'review staging symlink')
        if p.is_file(): total+=p.stat().st_size
    return total


def review_text_bytes(root):
    # Only top-level downloaded ZIPs are download storage, everything else is
    # retained review material. This includes prior consumption reports.
    root=Path(root)
    return sum(p.stat().st_size for p in root.rglob('*') if p.is_file() and
               not (p.parent==root and p.suffix.lower()=='.zip'))


def review_selection(result, files):
    """Explicit text subset; every leaf and required report is validated first.

    Keep source identity/changed bytes, stage command/exit records, required
    reports (source-after is an already-verified duplicate), and raw output for
    selftests, CTest, canonical/native, sanitizer, and report-less legacy drivers.
    Other exact raw bytes remain in the retained, independently verified ZIP.
    """
    specs=stage_contract(result['identity'],result['locations'])
    names={'qualification.json','source/tree-inventory.bin','source/dependencies.json'}
    names.update(result['reports'])
    names.update(changed_source_members(r['path'] for r in files))
    for name,spec in specs.items():
        names.add('stages/'+name+'/result.json')
        names.update(p for p in spec['reports'] if p!='reports/source-after.json')
        if (name.startswith(('selftest-','sanitize-','hooks-','memory_cycle-')) or
                name in ('ctest-run','canonical-run','canonical-groups','direct-tests-build','direct-tests-run')):
            names.update('stages/'+name+'/'+stream+'.bin' for stream in ('stdout','stderr'))
    by_name={r['path']:r for r in files}
    need(names<=set(by_name),'required review selection missing')
    need(not any(n.startswith('binaries/') for n in names),'binary extraction prohibited')
    return [by_name[name] for name in sorted(names)]


def consume(outer, review_root, identity, manifest_sha256, artifact_sha256, limits=LIMITS):
    """Input must be the file from the supported GitHub download_file route."""
    outer=Path(outer); review_root=Path(review_root)
    same_identity(identity,identity)
    need(outer.is_file() and not outer.is_symlink() and 0<outer.stat().st_size<=limits['outer'], 'outer ZIP cap/type')
    need(digest(outer)==artifact_sha256.removeprefix('sha256:'),'independent GitHub artifact digest mismatch')
    review_root.mkdir(parents=True,exist_ok=True)
    need(outer.resolve().is_relative_to(review_root.resolve()), 'download must reside in aggregate review staging')
    retained_text=review_text_bytes(review_root)
    need(retained_text<=limits['text'],'aggregate retained-text cap')
    need(staging_size(review_root)+limits['compressed']+limits['text']-retained_text<=limits['staging'],'consumer staging cap')
    need(shutil.disk_usage(review_root).free>=limits['reserve']+limits['compressed']+limits['text'],'consumer reserve')
    with zipfile.ZipFile(outer) as z:
        need(sorted(z.namelist())==['evidence.part','manifest.json'],'missing/extra outer member')
        for info in z.infolist():
            mode=info.external_attr>>16
            need(not info.is_dir() and (not stat.S_IFMT(mode) or stat.S_ISREG(mode)) and not info.flag_bits&1,'unsafe outer member')
        info=z.getinfo('manifest.json'); need(0<info.file_size<=limits['manifest'],'outer manifest cap')
        raw=z.read(info); need(hashlib.sha256(raw).hexdigest()==manifest_sha256,'independent manifest digest mismatch')
        m=validate_manifest(raw,identity,limits)
        info=z.getinfo('evidence.part'); need(info.file_size==m['archive']['size'],'outer part size')
        with tempfile.TemporaryDirectory(prefix='n49d-review-',dir=review_root) as tmp:
            archive=Path(tmp)/'evidence.zip'; h=hashlib.sha256(); count=0
            with z.open(info) as src, archive.open('wb') as dst:
                while data:=src.read(MIB):
                    count+=len(data);need(count<=limits['compressed'],'part expansion cap');h.update(data);dst.write(data)
            need(count==m['archive']['size'] and h.hexdigest()==m['archive']['sha256'],'wrong part digest')
            generic_archive()['verify_evidence_archive'](archive,m)
            with zipfile.ZipFile(archive) as leaves:
                def read(name):
                    need(leaves.getinfo(name).file_size<=limits['text'],'review record cap')
                    return leaves.read(name)
                # The unchanged archive validator already streamed every member.
                leaf_descriptors={r['path']:{k:r[k] for k in ('size','sha256')} for r in m['files']}
                read.describe=lambda name:leaf_descriptors[name]
                result=validate_recordings(read,identity,files=[r['path'] for r in m['files']])
                selected=review_selection(result,m['files'])
                receipt=dict(passed=True,identity=identity,artifact_sha256=artifact_sha256,
                    manifest_sha256=manifest_sha256,archive_sha256=m['archive']['sha256'],
                    selected_review_members=[r['path'] for r in selected],all_archive_leaves_stream_verified=True,
                    all_required_semantic_reports_verified=True,binary_members=[r for r in m['files'] if r['path'].startswith('binaries/')])
                receipt_raw=(json.dumps(receipt,sort_keys=True,indent=2)+'\n').encode('utf-8')
                need(retained_text+sum(r['size'] for r in selected)+len(receipt_raw)<=limits['text'],'aggregate retained-text cap')
                target=review_root/(identity['job_key']+'-'+identity['run_id']+'-'+identity['run_attempt'])
                need(not target.exists(),'review destination exists');target.mkdir()
                for row in selected:
                    dest=target/row['path'];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(read(row['path']))
                (target/'consumption.json').write_bytes(receipt_raw)
    need(staging_size(review_root)<=limits['staging'] and review_text_bytes(review_root)<=limits['text'],'consumer final aggregate cap')
    return result


def native_groups(registry, output):
    path=ROOT/'.ci/validate_native_log.py'
    source_guard.checkout_bytes(path.read_bytes(),'352de0d8df857e2fb5b2e8a5783d49874d585447',os.name=='nt')
    ns={'re':re,'Counter':__import__('collections').Counter}
    nodes=[n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='verified_groups']
    need(len(nodes)==1,'native parser primitive missing')
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns)
    return ns['verified_groups'](registry,output,expected_count=60)


def verify_native(registry, output):
    return native_groups(Path(registry).read_text(encoding='utf-8'),Path(output).read_text(encoding='utf-8',errors='replace'))


def ctest_values(value, junit):
    names=[t['name'] for t in value['tests']]
    need(sorted(names)==sorted(TESTS) and len(names)==len(set(names)), 'selected CTest inventory mismatch')
    root=ET.fromstring(junit); cases=root.findall('.//testcase')
    need(sorted(t.attrib['name'] for t in cases)==sorted(TESTS),'actual CTest set mismatch')
    need(all(not list(t.findall('skipped')+t.findall('failure')+t.findall('error')) and
             t.attrib.get('status','run') not in ('notrun','disabled') for t in cases),'CTest skip/failure')
    return names


def verify_ctest(inventory, junit):
    return ctest_values(json.loads(Path(inventory).read_text(encoding='utf-8')),Path(junit).read_bytes())


def validate_sanitizer_flags(effective):
    import shlex
    need(effective.get('passed') is True and effective.get('compile_commands'),'sanitizer report incomplete')
    for row in effective['compile_commands']:
        args=row.get('arguments') or shlex.split(row['command'])
        need(not any(re.search(r'(^|[-/])D\s*NDEBUG(?:=|$)',a) or (a in ('-D','/D') and i+1<len(args) and re.match(r'NDEBUG(?:=|$)',args[i+1])) for i,a in enumerate(args)), 'NDEBUG in effective compilation')
        need('-fsanitize=address,undefined' in args and '-fno-omit-frame-pointer' in args and
             [a for a in args if re.fullmatch(r'-g.*',a)][-1:]==['-g0'] and
             [a for a in args if re.fullmatch(r'-O.*',a)][-1:]==['-O1'],'effective sanitizer flags missing')
    need(set(effective['link_commands'])==set(TARGETS[:2]) and all('-fsanitize=address,undefined' in c for c in effective['link_commands'].values()),'sanitizer link flags missing')
    need(effective['runtime_options']==dict(ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1'),'sanitizer runtime options missing')


def verify_sanitizer(build, output):
    import shlex
    rows=json.loads((build/'compile_commands.json').read_text(encoding='utf-8'))
    need(rows,'compile command inventory missing')
    selected=[]
    for row in rows:
        if any(t in row.get('command','') or t in row.get('output','') for t in TARGETS[2:]):
            continue
        args=row.get('arguments') or shlex.split(row['command'])
        need(not any(re.search(r'(^|[-/])D\s*NDEBUG(?:=|$)',a) or
                     (a in ('-D','/D') and i+1<len(args) and re.match(r'NDEBUG(?:=|$)',args[i+1]))
                     for i,a in enumerate(args)),'NDEBUG in effective compilation')
        need('-fsanitize=address,undefined' in args and '-fno-omit-frame-pointer' in args,'missing sanitizer instrumentation')
        need([a for a in args if re.fullmatch(r'-g.*',a)][-1:]==['-g0'],'effective debug symbols enabled')
        need([a for a in args if re.fullmatch(r'-O.*',a)][-1:]==['-O1'],'effective sanitizer optimization mismatch')
        selected.append(row)
    links={t:(build/'CMakeFiles'/(t+'.dir')/'link.txt').read_text(encoding='utf-8') for t in TARGETS[:2]}
    need(all('-fsanitize=address,undefined' in text for text in links.values()),'sanitizer link flags missing')
    dump(output,dict(passed=True,compile_commands=selected,link_commands=links,
        runtime_options=dict(ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')))


def run_job(args):
    source=args.source.resolve(strict=True); build=args.build.absolute(); output=args.output.absolute()
    need(source==ROOT,'qualification must use its own candidate source')
    need(args.job in JOBS and (os.name=='nt')==args.job.startswith('windows'),'job/platform mismatch')
    need(not output.exists() and not build.exists(),'fresh build/evidence directories required')
    need(source not in output.parents and source not in build.parents,'CMake build and evidence must be outside source')
    if args.job=='windows-msvc': need(not (source/'build/cl').exists(),'fresh direct-MSVC output required')
    identity=dict(commit=args.commit,tree=args.tree,run_id=args.run_id,run_attempt=args.run_attempt,job_key=args.job,job_label=args.job)
    same_identity(identity,identity)
    env={k:v for k,v in os.environ.items() if not BLOCKED.search(k)}
    env['PYTHONDONTWRITEBYTECODE']='1'
    env['PYTHONIOENCODING']='utf-8'
    if args.job=='linux-sanitizers':
        env.update(ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    recorder=Recorder(output,identity,required_stages(args.job),env,source)
    recorder.locations=dict(source=str(source),build=str(build),output=str(output),python=sys.executable)
    contracts=stage_contract(identity,recorder.locations)
    (output/'reports').mkdir();(output/'source').mkdir();(output/'binaries').mkdir()
    python=[sys.executable]; guard=source/'.ci/check_n49d_sources.py'
    source_reports=[output/'reports/source-before.json',output/'reports/source-after.json']
    guard_command=lambda report:python+[str(guard),'--source',str(source),'--commit',args.commit,'--tree',args.tree,'--report',str(report)]
    def stage(name,argv,timeout=600,**kw):
        spec=contracts[name]
        need(list(map(str,argv))==spec['argv'] and timeout==spec['timeout_seconds'] and
             [Path(p).relative_to(output).as_posix() for p in kw.get('reports',())]==spec['reports'], 'runner fixed contract drift')
        return recorder.run(name,argv,timeout,**kw)
    try:
        stage('source-before',guard_command(source_reports[0]),120,reports=[source_reports[0]])
        pre=json.loads(source_reports[0].read_text(encoding='utf-8'))
        (output/'source/tree-inventory.bin').write_bytes(source_guard.git(source,'ls-tree','-r','--full-tree','-z',args.commit))
        dump(output/'source/dependencies.json',pre['dependency_sha256'])
        for path in pre['changed']:
            dest=output/'source/changed'/path;dest.parent.mkdir(parents=True,exist_ok=True)
            # Preserve canonical candidate bytes; checkout may be verified CRLF.
            dest.write_bytes(source_guard.git(source,'show',args.commit+':'+path))
        for mode in ('normal','optimized'):
            stage('selftest-'+mode,python+(['-O'] if mode=='optimized' else [])+[str(source/'.ci/test_n49d_source_contract.py')],120)
        selected=[]; production=None
        if args.job=='windows-msvc':
            production=source/'build/cl/qbrain.exe'; canonical=source/'build/cl/qbrain_tests.exe'
            stage('direct-production',contracts['direct-production']['argv'],1800,produced=[production],
                  reports=[output/PHASE_REPORTS['objects'][0]],prepare=lambda d:prepare_phase(recorder,'objects',d),
                  finalize=lambda d:finalize_production(recorder,d))
            pair=DirectTestPair(recorder);recorder.pair=pair
            phase=pair.phase('direct-tests-build')
            stage('direct-tests-build',contracts['direct-tests-build']['argv'],1200,binaries=[production],produced=[canonical],
                  reports=[output/PHASE_REPORTS['build-context'][0]],prepare=lambda d:prepare_test_build(recorder,d),
                  finalize=lambda d:finalize_test_build(recorder,d),phase=phase)
            pair.sealed('direct-tests-build')
            phase=pair.phase('direct-tests-run')
            stage('direct-tests-run',contracts['direct-tests-run']['argv'],600,binaries=[production,canonical],
                  reports=[output/PHASE_REPORTS['run-context'][0]],prepare=lambda d:prepare_phase(recorder,'run-context',d),
                  finalize=lambda d:finalize_test_run(recorder,d),phase=phase)
            pair.sealed('direct-tests-run');pair.finish()
            stage('canonical-groups',contracts['canonical-groups']['argv'],120,binaries=[production,canonical])
        else:
            configure=['cmake','-S',str(source),'-B',str(build),'-DQBRAIN_WITH_PG=OFF',
                       '-DCMAKE_PROJECT_qbrain_INCLUDE='+str(source/'.ci/mcp_directory_search_targets.cmake'),'-DCMAKE_BUILD_TYPE=Debug']
            targets=['qbrain',*TARGETS]
            if args.job=='linux-sanitizers':
                configure += ['-DCMAKE_C_COMPILER=clang','-DCMAKE_CXX_COMPILER=clang++','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
                    '-DCMAKE_C_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer',
                    '-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer',
                    '-DCMAKE_C_FLAGS_DEBUG=-O1 -g0','-DCMAKE_CXX_FLAGS_DEBUG=-O1 -g0',
                    '-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined']
                targets=list(TARGETS[:2])
            elif args.job=='linux-cmake':
                configure += ['-DCMAKE_CXX_FLAGS_DEBUG=-O0 -g0','-DCMAKE_C_FLAGS_DEBUG=-O0 -g0']
            stage('configure',configure,180,**(dict(reports=[output/PHASE_REPORTS['configure'][0]],
                  prepare=lambda d:prepare_phase(recorder,'configure',d),finalize=lambda d:finalize_configure(recorder,d)) if args.job=='windows-cmake' else {}))
            exe=lambda target:build/('Debug' if os.name=='nt' else '')/(target+('.exe' if os.name=='nt' else ''))
            selected=[exe(target) for target in targets]
            stage('build',['cmake','--build',str(build),'--config','Debug','--target',*targets,'--parallel','2'],1800,produced=selected,
                  **(dict(prepare=lambda d:prepare_cmake_build(recorder,d)) if args.job=='windows-cmake' else {}))
            if args.job=='linux-sanitizers':
                effective=output/'reports/sanitizer-effective.json'
                stage('sanitizer-flags',python+[str(__file__),'verify-sanitizer','--build',str(build),'--report',str(effective)],120,binaries=selected,reports=[effective])
                for name,binary in zip(('sanitize-mcp','sanitize-directory'),selected):
                    stage(name,[str(binary)],binaries=selected,
                          check=lambda name=name:need((output/'stages'/name/'stderr.bin').stat().st_size==0,'sanitizer stderr nonempty'))
            else:
                production=exe('qbrain'); regex='^('+'|'.join(TESTS)+')$'
                stage('ctest-inventory',['ctest','--test-dir',str(build),'-C','Debug','-R',regex,'--show-only=json-v1'],120,binaries=selected)
                inventory=output/'stages/ctest-inventory/stdout.bin'
                need(sorted(t['name'] for t in json.loads(inventory.read_text())['tests'])==sorted(TESTS),'CTest inventory must match before run')
                junit=output/'reports/ctest.xml'
                stage('ctest-run',['ctest','--test-dir',str(build),'-C','Debug','-R',regex,'--output-on-failure','--output-junit',str(junit)],600,binaries=selected,reports=[junit])
                stage('ctest-completeness',python+[str(__file__),'verify-ctest','--inventory',str(inventory),'--junit',str(junit)],120,binaries=selected)
                if args.job=='windows-cmake':
                    canonical=exe('qbrain_tests');probe=exe('qbrain_http_probe')
                    stage('canonical-build',['cmake','--build',str(build),'--config','Debug','--target','qbrain_tests','qbrain_http_probe','--parallel','2'],1800,binaries=selected,produced=[canonical,probe])
                    stage('canonical-run',[str(canonical)],binaries=[canonical,production])
                    stage('canonical-groups',python+[str(__file__),'verify-native','--registry',str(source/'tests/test_main.cpp'),'--log',str(output/'stages/canonical-run/stdout.bin')],120,binaries=[canonical,production])
        if production:
            for mode in ('normal','optimized'):
                prefix=python+(['-O'] if mode=='optimized' else [])
                for driver in DRIVERS:
                    name=driver+'-'+mode; command=prefix+[str(source/'.ci'/('test_'+driver+'.py')),'--binary',str(production)]
                    reports=[]
                    if driver in ('mcp_directory_search','directory_search'):
                        destination=output/'reports'/name;command+=['--output',str(destination)];reports=[destination/'RESULT.json']
                    elif driver in ('context_process','named_arguments'):
                        destination=output/'reports'/(name+'.json');command+=['--report',str(destination)];reports=[destination]
                    stage(name,command,binaries=[production],reports=reports)
                if args.job=='windows-cmake':
                    report=output/'reports'/('winhttp-'+mode+'.json')
                    stage('winhttp-'+mode,prefix+[str(source/'.ci/test_http_transport.py'),'--probe',str(probe),'--report',str(report)],binaries=[production,probe],reports=[report])
        stage('source-after',guard_command(source_reports[1]),120,reports=[source_reports[1]],binaries=list(map(Path,recorder.binary_pins)))
        retained=[production] if production else selected
        for p in retained:
            need(descriptor(p)==recorder.binary_pins[str(p)],'tested binary changed before retention')
            shutil.copyfile(p,output/'binaries'/p.name)
        result=recorder.finish(descriptor(source_reports[0]),descriptor(source_reports[1]))
        result['retained_binaries']={str(p):dict(path='binaries/'+p.name,**descriptor(output/'binaries'/p.name)) for p in retained}
        dump(output/'qualification.json',result)
        def read(p):return (output/p).read_bytes()
        read.describe=lambda p:descriptor(output/p)
        validate_recordings(read,identity,files=[p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()])
        package_result=package(output,args.package,identity)
        dump(args.package/'PACKAGE.json',package_result)
        print(json.dumps(package_result,sort_keys=True))
        return 0
    except Exception as e:
        primary=str(e);print(primary,file=sys.stderr)
        pair=getattr(recorder,'pair',None)
        if pair is not None and pair.result is None:
            if pair.failure is None:
                pair.fail('build-failed' if pair.value['build'] is None else 'run-failed' if pair.value['run'] is None else 'handoff-failed')
            if pair.value['state']!='complete':
                pair.value.update(state='failed',failure=pair.failure,finalize_begin_us=None)
                try:write_phase(pair.path,'pair',pair.value,identity)
                except Exception:pass
        try:dump(output/'failure.json',dict(passed=False,identity=identity,error=primary,stages=recorder.stages))
        except Exception as error:print('incomplete-primary-record: '+str(error),file=sys.stderr)
        try:
            diagnostics=args.package.parent/'n49d-diagnostics'
            failure_diagnostics(output,diagnostics/'failure.json',identity,recorder.stages,recorder.required,primary,locations=recorder.locations,pair=None if pair is None else pair.diagnostic())
        except Exception as error:print('incomplete-diagnostics: '+str(error),file=sys.stderr)
        return 1


def diagnostic_roles(identity,name,locations=None,pair=None):
    """One fixed prior result; no prior raw log or caller-supplied report list."""
    job=identity['job_key'];prior=None;reports=[]
    if name not in required_stages(job):return prior,reports
    if locations is None:
        windows=job.startswith('windows')
        locations=dict(source='C:\\source' if windows else '/source',build='C:\\build' if windows else '/build',
                       output='C:\\output' if windows else '/output',python='C:\\python.exe' if windows else '/python')
    current=stage_contract(identity,locations)[name]['reports'][:2]
    tails=[(p,8*1024,False) for p in current]
    whole=lambda role:(PHASE_REPORTS[role][0],PHASE_REPORTS[role][2],True)
    if job=='windows-msvc':
        if pair is not None and pair.get('failure') in ('pair-finalization-timeout','pair-report-unavailable'):
            prior='direct-tests-build';reports=[whole(r) for r in ('objects','build-context','run-context','pair')]
        elif name=='direct-production':reports=[whole('objects')]
        elif name=='direct-tests-build':prior='direct-production';reports=[whole(r) for r in ('objects','build-context','pair')]
        elif name=='direct-tests-run':prior='direct-tests-build';reports=[whole(r) for r in ('objects','build-context','run-context','pair')]
        elif name=='canonical-groups':prior='direct-tests-run';reports=[whole('pair')]
        elif name=='source-after' or any(name==d+'-'+m for d in DRIVERS for m in ('normal','optimized')):
            prior='direct-tests-build';reports=tails
        else:reports=tails
    elif job=='windows-cmake':
        if name=='configure':reports=[whole('configure')]
        elif name=='build':prior='configure';reports=[whole('configure')]
        elif name=='canonical-build':prior='build';reports=[whole('configure')]
        elif name in ('ctest-inventory','ctest-run','ctest-completeness'):prior='build';reports=tails
        elif name in ('canonical-run','canonical-groups','source-after') or name.startswith('winhttp-') or any(name==d+'-'+m for d in DRIVERS for m in ('normal','optimized')):
            prior='canonical-build';reports=tails
        else:reports=tails
    else:reports=tails
    return prior,reports


def failure_diagnostics(root,destination,identity,stages,required,error,*,locations=None,pair=None):
    """Bounded partial evidence; missing critical reports remain explicit."""
    root=Path(root);files={};selected=[]
    if stages:
        name=stages[-1];folder='stages/'+name+'/'
        selected=[(folder+'stdout.bin',64*1024,False),(folder+'stderr.bin',64*1024,False),(folder+'result.json',16*1024,False)]
        prior,reports=diagnostic_roles(identity,name,locations,pair)
        if prior is not None:selected.append(('stages/'+prior+'/result.json',16*1024,False))
        selected+=reports
    stable=None
    if stages:
        try:stable=json_unique((root/'stages'/stages[-1]/'result.json').read_bytes()).get('ownership',{}).get('stable')
        except Exception:pass
    for name,cap,whole in selected:
        path=root/name
        if not path.is_file():
            files[name]=dict(status='missing',complete=False);continue
        try:
            full=descriptor(path)
            if whole and full['size']>cap:
                files[name]=dict(**full,status='oversized',complete=False);continue
            with path.open('rb') as stream:
                offset=0 if whole else max(0,full['size']-cap);stream.seek(offset);raw=stream.read(cap)
            after=descriptor(path)
            unchanged=full==after and len(raw)==min(cap,full['size'])
            status='available' if unchanged and stable is True else 'unstable' if not unchanged or stable is False else 'stability-unknown'
            files[name]=dict(**full,status=status,complete=whole and unchanged and stable is True,
                retained_offset=offset,retained_bytes=len(raw),truncated=offset!=0,
                encoding='base64',data=base64.b64encode(raw).decode('ascii'))
        except Exception:
            files[name]=dict(status='unreadable',complete=False)
    message=str(error);message_raw=message.encode('utf-8')
    payload=dict(passed=False,status='failed-partial-diagnostics',identity=identity,error=message[:1024],
        error_size=len(message_raw),error_sha256=hashlib.sha256(message_raw).hexdigest(),error_truncated=len(message)>1024,
        stages=stages,required=required,files=files)
    if pair is not None:payload['pair']=pair
    raw=json.dumps(payload,sort_keys=True,indent=2).encode('utf-8')
    encoded=sum(len(row.get('data','')) for row in files.values())
    need(len(raw)-encoded<=12*1024,'diagnostics metadata cap')
    need(len(raw)<=256*1024,'diagnostics cap')
    crlf_size=len(raw)+raw.count(b'\n')
    need(crlf_size-encoded<=12*1024,'diagnostics CRLF metadata cap')
    need(crlf_size<=256*1024,'diagnostics CRLF cap')
    Path(destination).parent.mkdir(parents=True,exist_ok=True);Path(destination).write_bytes(raw)
    return payload


def main(argv=None):
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='action',required=True)
    q=sub.add_parser('run');q.add_argument('--source',type=Path,default=ROOT)
    q.add_argument('--job',choices=JOBS,required=True);q.add_argument('--build',type=Path,required=True)
    q.add_argument('--output',type=Path,required=True);q.add_argument('--package',type=Path,required=True)
    for name in ('commit','tree','run-id','run-attempt'):q.add_argument('--'+name,required=True)
    q=sub.add_parser('consume');q.add_argument('--outer',type=Path,required=True);q.add_argument('--review-root',type=Path,required=True)
    q.add_argument('--identity',type=Path,required=True);q.add_argument('--manifest-sha256',required=True);q.add_argument('--artifact-sha256',required=True)
    q=sub.add_parser('verify-native');q.add_argument('--registry',type=Path,required=True);q.add_argument('--log',type=Path,required=True)
    q=sub.add_parser('verify-ctest');q.add_argument('--inventory',type=Path,required=True);q.add_argument('--junit',type=Path,required=True)
    q=sub.add_parser('verify-sanitizer');q.add_argument('--build',type=Path,required=True);q.add_argument('--report',type=Path,required=True)
    args=p.parse_args(argv)
    try:
        if args.action=='run':return run_job(args)
        if args.action=='consume':consume(args.outer,args.review_root,json.loads(args.identity.read_text()),args.manifest_sha256,args.artifact_sha256)
        elif args.action=='verify-native':print(json.dumps(verify_native(args.registry,args.log)))
        elif args.action=='verify-ctest':print(json.dumps(verify_ctest(args.inventory,args.junit)))
        elif args.action=='verify-sanitizer':verify_sanitizer(args.build,args.report)
        return 0
    except Exception as e:
        print(str(e),file=sys.stderr);return 1


if __name__=='__main__':sys.exit(main())
