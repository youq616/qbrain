"""Finite new-fixture N49D wrapper controls; identical checks under python -O.

The inherited package_evidence is deliberately NOT run by these tiny controls:
its unchanged 1152 MiB reserve belongs to native CI. Both N49D packaging boundary
wrappers and the streaming consumer are exercised on newly generated tiny ZIPs.
"""
from __future__ import annotations
import copy
import base64
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch
import zipfile

import check_n49d_sources as guard
import run_n49d_qualification as q

RESULTS=[]
FAILURE_DETAIL=None


def check(ok, name):
    if not ok: raise ValueError(name)


def expect_failure(name, fn, message=None, *, record=True):
    try: fn()
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile) as error:
        check(message is None or message in str(error), name+': wrong failure boundary: '+str(error))
        if record:RESULTS.append(dict(name=name,passed=True))
        return
    raise ValueError('negative control unexpectedly passed: '+name)


def control(name, fn):
    fn(); RESULTS.append(dict(name=name,passed=True))


def timeout_proof(value,live,pid):
    check(live is True and value['root_pid']==pid and value['classification']=='timeout' and value['exit'] not in (None,0) and
          value['cleanup_error'] is None and all(value.get(key) is True for key in ('cleanup_ok','owned_tree_empty','readers_done','stable')),
          'timeout fixture boundary not proved')


def _timeout_failure_detail(result,raw,live,pid):
    fallback=dict(schema='qbrain-n49d-timeout-proof-v1',site='actual-bounded-timeout',complete=False,reason='detail-unavailable')
    try:
        value=result['ownership']
        predicates=dict(readiness_live_observed=live is True,root_pid_matches=value['root_pid']==pid,
            classification_is_timeout=value['classification']=='timeout',exit_is_nonzero_terminal=value['exit'] not in (None,0),
            cleanup_error_is_none=value['cleanup_error'] is None,
            **{key+'_is_true':value.get(key) is True for key in ('cleanup_ok','owned_tree_empty','readers_done','stable')})
        def string_detail(text,known):
            if text is None:return dict(category='none')
            check(type(text) is str,'detail text type');data=text.encode('utf-8')
            return dict(category=known.get(text,'other'),size=len(data),sha256=hashlib.sha256(data).hexdigest())
        def stream_detail(item):
            check(type(item) is dict and set(item)=={'size','sha256'},'detail stream fields')
            check(type(item['size']) is int and 0<=item['size']<=2048 and type(item['sha256']) is str and
                  q.re.fullmatch('[0-9a-f]{64}',item['sha256']) is not None,'detail stream types')
            return dict(item)
        exit_code=value['exit'];elapsed=value['elapsed_seconds']
        check(exit_code is None or (type(exit_code) is int and exit_code.bit_length()<=64),'detail exit type')
        check(type(elapsed) in (int,float) and math.isfinite(elapsed) and elapsed>=0,'detail elapsed type')
        check(type(raw) is bytes and type(value['classification']) is str,'detail input type')
        stage={key:stream_detail(result[key]) for key in ('stdout','stderr')}
        owned={key:stream_detail(value[key]) for key in ('stdout','stderr')}
        detail=dict(schema=fallback['schema'],site=fallback['site'],complete=True,predicates=predicates,exit=exit_code,
            classification=string_detail(value['classification'],{v:v for v in ('timeout','passed','stopped')}),
            cleanup_error=string_detail(value['cleanup_error'],{v:v.replace(' ','-') for v in
                ('private job termination failed','private job close failed','owned cleanup deadline exceeded','failed cleanup grace exceeded')}),
            elapsed_seconds=elapsed,timeout_seconds=3,record=dict(size=len(raw),sha256=hashlib.sha256(raw).hexdigest()),
            stage_streams=stage,ownership_streams=owned,streams_match={key:stage[key]==owned[key] for key in stage},
            streams_stable=value.get('stable') is True)
        return q._bounded_failure_detail(detail,fallback,4096)
    except BaseException:return fallback


def _actual_timeout_proof(result,raw,live,pid):
    global FAILURE_DETAIL
    try:timeout_proof(result['ownership'],live,pid)
    except ValueError as error:
        if str(error)=='timeout fixture boundary not proved' and FAILURE_DETAIL is None:
            FAILURE_DETAIL=dict(schema='qbrain-n49d-timeout-proof-v1',site='actual-bounded-timeout',complete=False,reason='detail-unavailable')
            try:FAILURE_DETAIL=_timeout_failure_detail(result,raw,live,pid)
            except BaseException:pass
        raise


def _selftest_failure(error):
    value=dict(passed=False,error=str(error),controls=RESULTS)
    if FAILURE_DETAIL is not None:value['failure_detail']=FAILURE_DETAIL
    return value


def identity(tree='2'*40):
    return dict(commit='1'*40,tree=tree,run_id='17',run_attempt='2',job_key='linux-cmake',job_label='linux-cmake')


def source_controls():
    header=b'#include "qbrain/search/hybrid.hpp"\n'
    first=b'void register_search_ops() {\n'
    search=b'  register_one(\n      "search", Scope::Read, [](OpContext& ctx) {'
    end=b'  register_one(\n      "think", Scope::Read, [](OpContext& ctx) {'
    before={guard.HANDLERS:header+first+search+b' old; });\n'+end+b' fixed; }\n',
            guard.SERVER:b'prefix\n    json arguments = params.contains("arguments") ? params["arguments"] : json::object();\nfixed tail\n',
            guard.LEDGER:b'| search | **implemented** | old note |\n', 'inherited.txt':b'constant\n'}
    after=dict(before)
    after[guard.HANDLERS]=before[guard.HANDLERS].replace(header,header+b'#include "qbrain/search/directory.hpp"\n').replace(b' old;',b' scoped;')
    inserted=(b'    if (name == "search" && arguments.is_object() && arguments.contains("uri") &&\n'
              b'        !arguments["uri"].is_string()) {\n'
              b'      return make_tool_argument_error(id, "uri", "string value required");\n'
              b'    }\n')
    after[guard.SERVER]=before[guard.SERVER].replace(b'fixed tail\n',inserted+b'fixed tail\n')
    after[guard.LEDGER]=b'| search | **implemented** | candidate note |\n'
    mapping=lambda values:{p:('100644',guard.blob(v)) for p,v in values.items()}
    def validate(values=after, **kwargs):
        return guard.validate_delta(mapping(before),mapping(values),before.__getitem__,values.__getitem__,require_complete=False,**kwargs)
    control('source-valid-regions',validate)
    expect_failure('wrong-base',lambda:validate(base_commit='0'*40))
    expect_failure('wrong-base-tree',lambda:validate(base_tree='0'*40))
    for name,path,data in [('changed-inherited','inherited.txt',b'changed'),('extra-file','extra.txt',b'new'),
                           ('outside-handler-region',guard.HANDLERS,after[guard.HANDLERS]+b'outside'),
                           ('outside-server-region',guard.SERVER,after[guard.SERVER]+b'outside')]:
        changed=dict(after);changed[path]=data
        expect_failure(name,lambda changed=changed:validate(changed))
    deleted=dict(after);del deleted['inherited.txt']
    expect_failure('deleted-inherited',lambda:validate(deleted))
    base_index=mapping(before)
    stage_row=lambda path,value,stage=0:(value[0]+' '+value[1]+' '+str(stage)+'\t'+path).encode()+b'\0'
    encoded=b''.join(stage_row(path,value) for path,value in base_index.items())
    control('stage-zero-index-valid',lambda:check(guard.stage_zero_index(encoded)==base_index,'index preservation'))
    staged=dict(base_index);staged['.ci/run_n49d_qualification.py']=('100644',guard.blob(b'new staged fixture'))
    control('staged-added-path-retained',lambda:check('.ci/run_n49d_qualification.py' in guard.precommit_index(base_index,staged,set()),'staged addition omitted'))
    expect_failure('unmerged-index-rejected',lambda:guard.stage_zero_index(stage_row('inherited.txt',base_index['inherited.txt'],2)), 'unmerged index entry')
    extra_index=dict(staged);extra_index['unexpected.txt']=('100644',guard.blob(b'extra'))
    expect_failure('staged-extra-path-rejected',lambda:guard.precommit_index(base_index,extra_index,set()), 'unreviewed staged/untracked added file')
    deleted_index=dict(base_index);del deleted_index['inherited.txt']
    expect_failure('staged-deletion-rejected',lambda:guard.precommit_index(base_index,deleted_index,set()), 'staged inherited file deleted')
    changed_mode=dict(base_index);changed_mode['inherited.txt']=('100755',base_index['inherited.txt'][1])
    expect_failure('staged-mode-change-rejected',lambda:guard.precommit_index(base_index,changed_mode,set()), 'staged inherited mode changed')
    changed_new_mode=dict(staged);changed_new_mode['.ci/run_n49d_qualification.py']=('100755',staged['.ci/run_n49d_qualification.py'][1])
    expect_failure('staged-new-mode-rejected',lambda:guard.precommit_index(base_index,changed_new_mode,set()), 'staged new file mode unsupported')
    changed_blob=dict(base_index);changed_blob['inherited.txt']=('100644',guard.blob(b'changed staged bytes'))
    expect_failure('staged-inherited-change-rejected',lambda:guard.precommit_index(base_index,changed_blob,set()), 'staged inherited identity changed')
    raw=b'one\ntwo\n'; oid=guard.blob(raw)
    control('canonical-bytes',lambda:check(guard.checkout_bytes(raw,oid)==raw,'canonical'))
    control('whole-file-windows-newlines',lambda:check(guard.checkout_bytes(raw.replace(b'\n',b'\r\n'),oid,True)==raw,'CRLF'))
    expect_failure('mixed-newlines',lambda:guard.checkout_bytes(b'one\r\ntwo\n',oid,True))
    expect_failure('changed-with-newlines',lambda:guard.checkout_bytes(b'one\r\nthree\r\n',oid,True))


def ancestry_controls():
    head='1'*40;tree='2'*40
    replies={('rev-parse','HEAD'):head,('rev-parse','HEAD^{tree}'):tree,
             ('rev-parse',guard.BASE+'^{tree}'):guard.BASE_TREE,
             ('rev-parse',guard.CORRECTION_PARENT+'^{tree}'):guard.CORRECTION_PARENT_TREE,
             ('show','-s','--format=%P',guard.CORRECTION_PARENT):guard.PREVIOUS_PARENT,
             ('rev-parse',guard.PREVIOUS_PARENT+'^{tree}'):guard.PREVIOUS_PARENT_TREE,
             ('show','-s','--format=%P',guard.PREVIOUS_PARENT):guard.EARLIER_PARENT,
             ('rev-parse',guard.EARLIER_PARENT+'^{tree}'):guard.EARLIER_PARENT_TREE,
             ('show','-s','--format=%P',guard.EARLIER_PARENT):guard.ORIGINAL_PARENT,
             ('rev-parse',guard.ORIGINAL_PARENT+'^{tree}'):guard.ORIGINAL_PARENT_TREE,
             ('show','-s','--format=%P',guard.ORIGINAL_PARENT):guard.BASE,
             ('show','-s','--format=%P',head):guard.CORRECTION_PARENT}
    def run(overrides=None,precommit=False,commit=head,expected_tree=tree):
        values=dict(replies);values.update(overrides or {});calls=[]
        def git(root,*args):
            calls.append(args)
            if args not in values:raise ValueError('unapproved ancestry query')
            if values[args] is None:raise subprocess.CalledProcessError(128,['git',*args])
            return (values[args]+'\n').encode()
        with patch.object(guard,'git',git):result=guard.check_ancestry(Path('.'),commit,expected_tree,precommit)
        check(len(calls)==(11 if precommit else 12),'unexpected ancestry query count')
        return result
    control('ancestry-exact-correction-chain',lambda:check(run()==(head,tree,guard.CORRECTION_PARENT,guard.CORRECTION_PARENT_TREE),'committed parent fields'))
    pre={('rev-parse','HEAD'):guard.CORRECTION_PARENT,('rev-parse','HEAD^{tree}'):guard.CORRECTION_PARENT_TREE}
    control('ancestry-precommit-exact-anchor',lambda:check(run(pre,True)==(guard.CORRECTION_PARENT,guard.CORRECTION_PARENT_TREE,guard.PREVIOUS_PARENT,guard.PREVIOUS_PARENT_TREE),'precommit actual parent fields'))
    def no_lazy_fetch():
        with patch.object(guard.subprocess,'check_output',return_value=b'fixture') as execute:
            check(guard.git(Path('.'),'rev-parse','HEAD')==b'fixture','git helper return')
        check(execute.call_args.kwargs['env']['GIT_NO_LAZY_FETCH']=='1','source query may lazy fetch')
    control('ancestry-git-explicit-no-lazy-fetch',no_lazy_fetch)
    expect_failure('ancestry-wrong-requested-commit',lambda:run(commit='3'*40),'candidate pin mismatch')
    expect_failure('ancestry-wrong-requested-tree',lambda:run(expected_tree='3'*40),'candidate pin mismatch')
    cases=[('wrong-head',('rev-parse','HEAD'),'3'*40,'candidate pin'),
           ('wrong-head-tree',('rev-parse','HEAD^{tree}'),'3'*40,'candidate pin'),
           ('sibling-base-parent',('show','-s','--format=%P',head),guard.BASE,'candidate parent'),
           ('missing-parent',('show','-s','--format=%P',head),'','candidate parent'),
           ('wrong-parent',('show','-s','--format=%P',head),'3'*40,'candidate parent'),
           ('extra-parent',('show','-s','--format=%P',head),guard.CORRECTION_PARENT+' '+guard.BASE,'candidate parent'),
           ('self-parent',('show','-s','--format=%P',head),head,'candidate parent'),
           ('wrong-anchor-tree',('rev-parse',guard.CORRECTION_PARENT+'^{tree}'),'3'*40,'correction parent tree'),
           ('wrong-anchor-parent',('show','-s','--format=%P',guard.CORRECTION_PARENT),'3'*40,'correction parent ancestry'),
           ('multiple-anchor-parents',('show','-s','--format=%P',guard.CORRECTION_PARENT),guard.BASE+' '+'3'*40,'correction parent ancestry'),
           ('wrong-previous-tree',('rev-parse',guard.PREVIOUS_PARENT+'^{tree}'),'3'*40,'previous parent tree'),
           ('wrong-previous-parent',('show','-s','--format=%P',guard.PREVIOUS_PARENT),'3'*40,'previous parent ancestry'),
           ('multiple-previous-parents',('show','-s','--format=%P',guard.PREVIOUS_PARENT),guard.BASE+' '+'3'*40,'previous parent ancestry'),
           ('wrong-earlier-tree',('rev-parse',guard.EARLIER_PARENT+'^{tree}'),'3'*40,'earlier parent tree'),
           ('wrong-earlier-parent',('show','-s','--format=%P',guard.EARLIER_PARENT),'3'*40,'earlier parent ancestry'),
           ('multiple-earlier-parents',('show','-s','--format=%P',guard.EARLIER_PARENT),guard.BASE+' '+'3'*40,'earlier parent ancestry'),
           ('wrong-original-tree',('rev-parse',guard.ORIGINAL_PARENT+'^{tree}'),'3'*40,'original parent tree'),
           ('wrong-original-parent',('show','-s','--format=%P',guard.ORIGINAL_PARENT),'3'*40,'original parent ancestry'),
           ('multiple-original-parents',('show','-s','--format=%P',guard.ORIGINAL_PARENT),guard.BASE+' '+'3'*40,'original parent ancestry'),
           ('wrong-base-tree',('rev-parse',guard.BASE+'^{tree}'),'3'*40,'base object')]
    for label,key,value,boundary in cases:
        expect_failure('ancestry-'+label,lambda key=key,value=value:run({key:value}),boundary)
    for label,changes in [('old-base',{('rev-parse','HEAD'):guard.BASE,('rev-parse','HEAD^{tree}'):guard.BASE_TREE}),
                          ('wrong-tree',{('rev-parse','HEAD^{tree}'):'3'*40}),('other-tip',{('rev-parse','HEAD'):'3'*40})]:
        expect_failure('ancestry-precommit-'+label,lambda changes=changes:run(pre|changes,True),'precommit requires exact correction parent/tree')
    expect_failure('ancestry-anchor-is-not-candidate',lambda:run(pre,commit=guard.CORRECTION_PARENT,expected_tree=guard.CORRECTION_PARENT_TREE),'candidate pin mismatch')
    for label,anchor,anchor_tree in [('previous',guard.PREVIOUS_PARENT,guard.PREVIOUS_PARENT_TREE),('earlier',guard.EARLIER_PARENT,guard.EARLIER_PARENT_TREE),('original',guard.ORIGINAL_PARENT,guard.ORIGINAL_PARENT_TREE),('base',guard.BASE,guard.BASE_TREE)]:
        tip={('rev-parse','HEAD'):anchor,('rev-parse','HEAD^{tree}'):anchor_tree}
        expect_failure('ancestry-'+label+'-is-not-candidate',lambda tip=tip,anchor=anchor,anchor_tree=anchor_tree:run(tip,commit=anchor,expected_tree=anchor_tree),'candidate pin mismatch')
        expect_failure('ancestry-precommit-reject-'+label,lambda tip=tip:run(tip,True),'precommit requires exact correction parent/tree')
    for label,key in [('missing-depth-base',('rev-parse',guard.BASE+'^{tree}')),('missing-anchor-object',('rev-parse',guard.CORRECTION_PARENT+'^{tree}')),('missing-anchor-parent-metadata',('show','-s','--format=%P',guard.CORRECTION_PARENT)),('missing-previous-object',('rev-parse',guard.PREVIOUS_PARENT+'^{tree}')),('missing-previous-parent-metadata',('show','-s','--format=%P',guard.PREVIOUS_PARENT)),('missing-earlier-object',('rev-parse',guard.EARLIER_PARENT+'^{tree}')),('missing-earlier-parent-metadata',('show','-s','--format=%P',guard.EARLIER_PARENT)),('missing-original-object',('rev-parse',guard.ORIGINAL_PARENT+'^{tree}')),('missing-original-parent-metadata',('show','-s','--format=%P',guard.ORIGINAL_PARENT))]:
        try:run({key:None})
        except subprocess.CalledProcessError as error:
            check(error.returncode==128 and error.cmd==['git',*key],'missing object boundary');RESULTS.append(dict(name='ancestry-'+label,passed=True))
        else:raise ValueError('missing ancestry object passed')
    parent={p:('100644',guard.blob(('parent '+p).encode())) for p in guard.ALLOW};candidate=dict(parent)
    for path in guard.CORRECTION_PATHS:candidate[path]=('100644',guard.blob(('correction '+path).encode()))
    control('correction-exact-four-paths',lambda:check(guard.validate_correction(parent,candidate)==sorted(guard.CORRECTION_PATHS),'correction inventory'))
    partial=dict(parent);path=sorted(guard.CORRECTION_PATHS)[0];partial[path]=candidate[path]
    control('correction-precommit-subset',lambda:check(guard.validate_correction(parent,partial,False)==[path],'correction subset'))
    expect_failure('correction-missing-final-member',lambda:guard.validate_correction(parent,partial),'required correction path missing')
    for label,changes,removed in [('production',{guard.HANDLERS:('100644','0'*40)},None),('documentation',{guard.LEDGER:('100644','0'*40)},None),
                                  ('extra',{'unexpected.txt':('100644','0'*40)},None),('deleted',{},path),('mode',{path:('100755',candidate[path][1])},None)]:
        changed=dict(candidate);changed.update(changes)
        if removed is not None:del changed[removed]
        expect_failure('correction-reject-'+label,lambda changed=changed:guard.validate_correction(parent,changed))
        expect_failure('correction-precommit-reject-'+label,lambda changed=changed:guard.validate_correction(parent,changed,False))
    workflow=Path(q.ROOT/'.github/workflows/n49d-mcp-directory-search.yml').read_bytes()
    def workflow_contract(raw,windows=False):
        canonical=guard.checkout_bytes(raw,'ee603f918c6b25ca43c03114ab5d76a99221d057',windows)
        check(canonical.count(b'          fetch-depth: 6\n')==1 and
              guard.sha(canonical.replace(b'          fetch-depth: 6\n',b'          fetch-depth: 5\n'))=='0da9b5e07c3d819b5ab09377a4f7845f3893de586a3e8cebba56d9ba0880a4e6','exact depth-six workflow contract')
        return canonical
    control('workflow-only-depth-six-change',lambda:workflow_contract(workflow,os.name=='nt'))
    canonical=workflow_contract(workflow,os.name=='nt')
    for label,old,new in [('old-depth',b'fetch-depth: 6',b'fetch-depth: 5'),('broad-depth',b'fetch-depth: 6',b'fetch-depth: 0'),
                          ('malformed-depth',b'fetch-depth: 6',b'fetch-depth: four'),('mutable-ref',b'ref: ${{ inputs.candidate || github.sha }}',b'ref: main'),
                          ('changed-trigger',b'feature/n49d-mcp-directory-search',b'main')]:
        changed=canonical.replace(old,new);check(changed!=canonical,'workflow mutation missed target')
        expect_failure('workflow-reject-'+label,lambda changed=changed:workflow_contract(changed),'checkout blob mismatch')


def _detail_fixture():
    stream=dict(size=0,sha256=hashlib.sha256(b'').hexdigest())
    terminal=dict(root_pid=17,classification='timeout',exit=1,cleanup_error=None,cleanup_ok=True,
        owned_tree_empty=True,readers_done=True,stable=True,elapsed_seconds=3.01,stdout=dict(stream),stderr=dict(stream))
    return dict(ownership=terminal,stdout=dict(stream),stderr=dict(stream))


def failure_detail_controls(root):
    global FAILURE_DETAIL
    root.mkdir();saved=FAILURE_DETAIL
    def exercise(record,live=True,pid=17):
        return _actual_timeout_proof(record,json.dumps(record).encode(),live,pid)
    try:
        FAILURE_DETAIL=None;valid=_detail_fixture();exercise(valid)
        check(FAILURE_DETAIL is None,'successful timeout proof retained detail');RESULTS.append(dict(name='failure-detail-valid-proof-unchanged',passed=True))
        cases=[('readiness_live_observed',{},False,17),('root_pid_matches',{},True,18),
            ('classification_is_timeout',dict(classification='passed'),True,17),('exit_is_nonzero_terminal',dict(exit=0),True,17),
            ('cleanup_error_is_none',dict(cleanup_error='private job termination failed'),True,17)]
        cases += [(key+'_is_true',{key:False},True,17) for key in ('cleanup_ok','owned_tree_empty','readers_done','stable')]
        for key,changes,live,pid in cases:
            FAILURE_DETAIL=None;record=_detail_fixture();record['ownership'].update(changes)
            expect_failure('failure-detail-false-'+key,lambda:exercise(record,live,pid),'timeout fixture boundary not proved')
            check(FAILURE_DETAIL['complete'] is True and [k for k,v in FAILURE_DETAIL['predicates'].items() if not v]==[key],'false conjunct detail mismatch')
            check(FAILURE_DETAIL['record']==dict(size=len(json.dumps(record).encode()),sha256=hashlib.sha256(json.dumps(record).encode()).hexdigest()),'inner record descriptor mismatch')
        FAILURE_DETAIL=None;record=_detail_fixture();record['ownership'].update(exit=None,cleanup_ok=False,stable=False)
        expect_failure('failure-detail-multiple-false',lambda:exercise(record),'timeout fixture boundary not proved')
        check({k for k,v in FAILURE_DETAIL['predicates'].items() if not v}=={'exit_is_nonzero_terminal','cleanup_ok_is_true','stable_is_true'},'multiple false terms lost')
        first=FAILURE_DETAIL;before=copy.deepcopy(first);record=_detail_fixture();record['ownership']['exit']=0
        expect_failure('failure-detail-first-failure-immutable',lambda:exercise(record),'timeout fixture boundary not proved')
        check(FAILURE_DETAIL is first and FAILURE_DETAIL==before,'first detail overwritten')
        expect_failure('failure-detail-model-does-not-latch',lambda:timeout_proof(record['ownership'],True,17),'timeout fixture boundary not proved')
        check(FAILURE_DETAIL is first and FAILURE_DETAIL==before,'model overwrote actual detail')
        FAILURE_DETAIL=None;record=_detail_fixture();del record['ownership']['root_pid']
        expect_failure('failure-detail-earlier-keyerror',lambda:exercise(record),'root_pid');check(FAILURE_DETAIL is None,'earlier error relabelled')
        for label,field,value in [('boolean-exit','exit',True),('string-exit','exit','sentinel-secret'),('large-exit','exit',1<<20000),
                ('nan-elapsed','elapsed_seconds',float('nan')),('negative-elapsed','elapsed_seconds',-1),('string-elapsed','elapsed_seconds','sentinel-secret')]:
            record=_detail_fixture();record['ownership'][field]=value;FAILURE_DETAIL=None
            # These values add no new condition to the original proof.
            timeout_proof(record['ownership'],True,17)
            record['ownership']['cleanup_ok']=False
            expect_failure('failure-detail-incomplete-'+label,lambda record=record:_actual_timeout_proof(record,b'fixture raw',True,17),'timeout fixture boundary not proved')
            check(FAILURE_DETAIL['complete'] is False and 'sentinel-secret' not in json.dumps(FAILURE_DETAIL),'type failure changed/leaked evidence')
        FAILURE_DETAIL=None;record=_detail_fixture();record['ownership'].update(classification='private-classification-'+('x'*5000),cleanup_error='private-error-'+('y'*5000))
        expect_failure('failure-detail-unknown-string-redaction',lambda:exercise(record),'timeout fixture boundary not proved')
        check(FAILURE_DETAIL['complete'] is True and FAILURE_DETAIL['classification']['category']=='other' and
              FAILURE_DETAIL['cleanup_error']['category']=='other' and 'private-' not in json.dumps(FAILURE_DETAIL),'unknown detail leaked')
        complete=copy.deepcopy(FAILURE_DETAIL)
        for label,changes in [('malformed-stream',{'stdout':dict(size=True,sha256='x')}),('malformed-classification',{})]:
            FAILURE_DETAIL=None;record=_detail_fixture();record['ownership']['cleanup_ok']=False;record.update(changes)
            if label=='malformed-classification':record['ownership']['classification']=17
            expect_failure('failure-detail-'+label,lambda:exercise(record),'timeout fixture boundary not proved')
            check(FAILURE_DETAIL['complete'] is False,'malformed detail accepted')
        FAILURE_DETAIL=None;record=_detail_fixture();record['ownership']['exit']=0
        with patch.object(sys.modules[__name__],'_timeout_failure_detail',side_effect=RuntimeError('private-detail-error')):
            expect_failure('failure-detail-builder-exception-permanent',lambda:exercise(record),'timeout fixture boundary not proved')
        check(FAILURE_DETAIL['complete'] is False and 'private-detail-error' not in json.dumps(_selftest_failure(ValueError('timeout fixture boundary not proved'))),'builder error relabelled failure')
        fallback=dict(schema='fixture',complete=False)
        for ownership,value in [(False,complete),(True,q._linux_identity_detail(dict(start=1,ppid=23),dict(start=2,ppid=24),23,22,{}))]:
            wrapper={'failure_detail':value}
            if ownership:wrapper={'ownership':wrapper}
            size=len((json.dumps(wrapper,sort_keys=True,indent=2,allow_nan=False)+'\n').replace('\n','\r\n').encode())
            for delta in (-1,0,1):
                observed=q._bounded_failure_detail(value,fallback,size+delta,ownership)
                check(observed==(fallback if delta<0 else value),'actual formatted cap boundary')
                RESULTS.append(dict(name='failure-detail-cap-'+str(ownership)+'-'+str(delta),passed=True))
            detached=q._bounded_failure_detail(value,fallback,size,ownership);check(detached is not value,'detail not detached')
        with patch.object(q.json,'dumps',side_effect=ValueError('private-serialization-error')):
            check(q._bounded_failure_detail(complete,fallback,4096)==fallback,'serializer failure not incomplete')
        RESULTS.append(dict(name='failure-detail-serialization-failure',passed=True))
        # All below are Python-only relation models, including on Windows.
        controller=1<<32;parent=controller+1;child=controller+2
        for expected,pin in [(controller,None),(parent,dict(fd=313,start=123))]:
            for label,start,after_parent in [('matching',1,expected),('start',2,expected),('parent',1,controller+3),
                    ('both',2,controller+3),('controller-parent',1,controller)]:
                tree=object.__new__(q._LinuxTree);tree.known={};tree.controller_pid=controller;calls=[]
                def parent_current(p,v):calls.append(('parent',p,v is pin));return True
                def read(p):calls.append(('stat',p));return dict(start=1 if sum(c[0]=='stat' for c in calls)==1 else start,ppid=expected if sum(c[0]=='stat' for c in calls)==1 else after_parent)
                def opened(p,flags):calls.append(('open',p,flags));return 999
                with patch.object(tree,'parent_current',parent_current),patch.object(q,'_linux_stat',read),patch.object(q.os,'pidfd_open',opened,create=True),patch.object(q.os,'close') as close,patch.object(q.os,'getpid',side_effect=AssertionError('extra query')):
                    ok=start==1 and after_parent==expected
                    if ok:check(tree.observe(child,expected,pin)==dict(fd=999,start=1),'matching observe changed')
                    else:expect_failure('failure-detail-linux-'+str(pin is not None)+'-'+label,lambda:tree.observe(child,expected,pin),'pidfd identity/ancestry mismatch')
                    check(calls==[('parent',expected,True),('stat',child),('parent',expected,True),('open',child,0),('stat',child),('parent',expected,True)],'identity query sequence changed')
                    if ok:check(not close.called and getattr(tree,'failure_detail',None) is None,'successful observe detail');RESULTS.append(dict(name='failure-detail-linux-matching-'+str(pin is not None)+'-'+label,passed=True))
                    else:
                        check(close.call_args_list==[((999,),{})] and not tree.known,'failed pin admitted/close changed')
                        detail=tree.failure_detail
                        check(detail['complete'] is True and detail['same_start']==(start==1) and detail['after_parent_matches_expected']==(after_parent==expected) and
                            detail['before_parent_matches_expected'] is True and detail['after_parent_matches_controller']==(after_parent==controller) and
                            detail['before_after_parent_equal']==(expected==after_parent) and detail['expected_parent_is_controller']==(expected==controller) and
                            detail['parent_pin_present']==(pin is not None) and detail['candidate_was_already_known'] is False and
                            detail['final_parent_check_returned_true'] is True,'identity comparison detail mismatch')
                        check(str(controller) not in json.dumps(detail) and str(child) not in json.dumps(detail),'raw identity leaked')
                        first=tree.failure_detail;calls.clear()
                        expect_failure('failure-detail-linux-first-immutable-'+str(pin is not None)+'-'+label,lambda:tree.observe(child,expected,pin),'pidfd identity/ancestry mismatch')
                        check(tree.failure_detail is first,'Linux detail overwritten')
        for label,before,after in [('before-link',dict(start=1,ppid=parent),dict(start=2,ppid=parent)),('missing-after',dict(start=1,ppid=controller),dict(ppid=controller))]:
            tree=object.__new__(q._LinuxTree);tree.known={};tree.controller_pid=controller
            with patch.object(tree,'parent_current',return_value=True),patch.object(q,'_linux_stat',side_effect=[before,after]),patch.object(q.os,'pidfd_open',return_value=999,create=True),patch.object(q.os,'close'):
                expect_failure('failure-detail-linux-early-'+label,lambda:tree.observe(child,controller),'ambiguous descendant ancestry' if label=='before-link' else 'start')
                check(getattr(tree,'failure_detail',None) is None,'early Linux error manufactured detail')
        tree=object.__new__(q._LinuxTree);tree.known={};tree.controller_pid=controller
        with patch.object(tree,'parent_current',return_value=True),patch.object(q,'_linux_stat',side_effect=[dict(start=1,ppid=controller),dict(start=2,ppid=controller)]),patch.object(q.os,'pidfd_open',return_value=999,create=True),patch.object(q.os,'close') as close,patch.object(q,'_linux_identity_detail',side_effect=RuntimeError('private-detail-error')):
            expect_failure('failure-detail-linux-builder-error-permanent',lambda:tree.observe(child,controller),'pidfd identity/ancestry mismatch')
            check(tree.failure_detail['complete'] is False and not tree.known and close.call_count==1,'Linux detail error changed cleanup')
        for label,value in [('list',[]),('extra',dict(q._linux_detail_unavailable(),raw='private-sentinel')),('bad-complete',dict(q._linux_detail_unavailable(),complete=1))]:
            check(q._copy_linux_failure_detail(value)==q._linux_detail_unavailable(),'malformed transferred detail accepted')
            RESULTS.append(dict(name='failure-detail-linux-transfer-'+label,passed=True))
        # Genuine owned command/cleanup; a one-shot post-read comparison fault
        # is scoped to that exact owned root. All cleanup reads remain real.
        if os.name!='nt':
            for broken_detail in (False,True,'copy','malformed'):
                original_read=q._linux_stat;seen=[];injected=[]
                def fault(pid,deadline=None):
                    value=original_read(pid,deadline);owner=q._ACTIVE_OWNER
                    if not injected and owner is not None and owner.proc is not None and pid==owner.proc.pid:
                        seen.append(pid)
                        if len(seen)==2:injected.append(pid);return dict(value,start=value['start']+1)
                    return value
                recorder=q.Recorder(root/('propagation-'+str(broken_detail)),identity(),['tiny'],dict(os.environ),root,stream_cap=2048)
                original_detail=q._linux_identity_detail;original_copy=q._copy_linux_failure_detail
                def detail(*args):
                    if broken_detail is True:raise ValueError('private-detail-error')
                    if broken_detail=='malformed':return {'private-sentinel':17}
                    return original_detail(*args)
                def copy_detail(value):
                    if broken_detail=='copy':raise ValueError('private-copy-error')
                    return original_copy(value)
                with patch.object(q,'_linux_stat',fault),patch.object(q,'_linux_identity_detail',detail),patch.object(q,'_copy_linux_failure_detail',copy_detail):
                    expect_failure('failure-detail-real-recorder-mismatch-'+str(broken_detail),lambda:recorder.run('tiny',[sys.executable,'-c','import time;time.sleep(10)'],3),'pidfd identity/ancestry mismatch')
                row=json.loads((recorder.root/'stages/tiny/result.json').read_bytes());owned=row['ownership']
                check(len(injected)==1 and injected[0]==owned['root_pid'] and row['classification']=='pidfd identity/ancestry mismatch' and
                      owned['classification']=='pidfd identity/ancestry mismatch' and owned['failure_detail']['complete'] is (not broken_detail) and
                      all(owned[key] is True for key in ('cleanup_ok','owned_tree_empty','readers_done','stable')) and
                      q._ACTIVE_OWNER is None and not q._OWNER_LOCK.locked() and 'private-' not in json.dumps(owned),'failed comparison detail changed owned cleanup/outcome')
    finally:FAILURE_DETAIL=saved


def failure_detail_retention_controls(root):
    global FAILURE_DETAIL
    root.mkdir();saved=FAILURE_DETAIL
    try:
        record=_detail_fixture();record['ownership'].update(exit=None,cleanup_ok=False,stable=False)
        raw=json.dumps(record).encode();windows=_timeout_failure_detail(record,raw,True,17)
        linux=q._linux_identity_detail(dict(start=1,ppid=23),dict(start=2,ppid=24),23,22,{})
        names=['failure-detail-final-retention-'+platform+'-'+newline for platform in ('windows','linux') for newline in ('LF','CRLF')]
        final_controls=RESULTS+[dict(name=name,passed=True) for name in names]
        for platform,detail in [('windows',windows),('linux',linux)]:
            for newline in ('LF','CRLF'):
                case=root/(platform+'-'+newline);stage=case/'stages/tiny';stage.mkdir(parents=True)
                terminal=dict(record['ownership'],classification='nonzero child exit' if platform=='windows' else 'pidfd identity/ancestry mismatch')
                if platform=='linux':terminal['failure_detail']=detail
                FAILURE_DETAIL=detail if platform=='windows' else None
                failure=_selftest_failure(ValueError('timeout fixture boundary not proved'));failure['controls']=final_controls
                stderr=(json.dumps(failure)+'\n') if platform=='windows' else 'tiny build diagnostic\n'
                if newline=='CRLF':stderr=stderr.replace('\n','\r\n')
                (stage/'stderr.bin').write_bytes(stderr.encode());(stage/'stdout.bin').write_bytes(b'')
                row=dict(schema='qbrain-n49d-stage-v1',name='tiny',identity=identity(),ownership=terminal,
                    classification=terminal['classification'],argv=['cmake','--build','/fixture/build','--config','Debug','--target','qbrain',*q.TARGETS,'--parallel','2'],
                    cwd='/fixture',timeout_seconds=1800,stream_limit=8*q.MIB,exit=-9,elapsed_seconds=101.615,
                    requested_reports=[],available_reports={},binaries_before={},binaries_after={},runtime_options={},
                    stdout=q.descriptor(stage/'stdout.bin'),stderr=q.descriptor(stage/'stderr.bin'))
                data=json.dumps(row,sort_keys=True,indent=2)+'\n'
                if newline=='CRLF':data=data.replace('\n','\r\n')
                (stage/'result.json').write_bytes(data.encode());check(len(data.encode())<=16*1024 and len(stderr.encode())<=64*1024,'final retained leaf cap')
                payload=q.failure_diagnostics(case,case/'failure.json',identity(),['tiny'],['tiny'],ValueError(row['classification']))
                for leaf in ('stderr.bin','stdout.bin','result.json'):
                    entry=payload['files']['stages/tiny/'+leaf];actual=(stage/leaf).read_bytes()
                    check(entry['truncated'] is False and entry['retained_offset']==0 and base64.b64decode(entry['data'])==actual and
                          entry['size']==len(actual) and entry['sha256']==hashlib.sha256(actual).hexdigest(),'failure detail retention bytes/hash')
                retained=json.loads(base64.b64decode(payload['files']['stages/tiny/'+('stderr.bin' if platform=='windows' else 'result.json')]['data']))
                observed=retained['failure_detail'] if platform=='windows' else retained['ownership']['failure_detail']
                check(observed==detail and payload['passed'] is False and payload['status']=='failed-partial-diagnostics' and
                      (case/'failure.json').stat().st_size<=256*1024,'retained failure detail/outcome changed')
                RESULTS.append(dict(name='failure-detail-final-retention-'+platform+'-'+newline,passed=True))
    finally:FAILURE_DETAIL=saved


def recorder_controls(root):
    ident=identity(); binary=root/'fixture.bin';binary.write_bytes(b'fixture-binary')
    def recorder(label, required=('tiny',)):
        return q.Recorder(root/label,ident,required,dict(os.environ),root,stream_cap=2048)
    good=recorder('record-valid')
    good.run('tiny',[sys.executable,'-c','print("tiny fixture")'],2,binaries=[binary])
    check('failure_detail' not in json.loads((good.root/'stages/tiny/result.json').read_bytes())['ownership'],'successful ownership retained failure detail')
    binding=dict(size=1,sha256='3'*64)
    good.finish(binding,binding)
    control('recorder-valid',lambda:q.validate_recordings(lambda p:(good.root/p).read_bytes(),ident,['tiny']))
    for label,command,timeout in [('nonzero-child',[sys.executable,'-c','raise SystemExit(7)'],2),
            ('output-budget',[sys.executable,'-c','print("x"*4096)'],2)]:
        r=recorder(label)
        expect_failure(label,lambda r=r,command=command,timeout=timeout:r.run('tiny',command,timeout))
        result=json.loads((r.root/'stages/tiny/result.json').read_text())
        check(result['classification']!='passed','child failure must remain failed')
    r=recorder('bounded-timeout');ready=r.root/'ready.pid';captured={};original_wait=q.OwnedChild.wait
    code='import os,time;from pathlib import Path\np=Path('+repr(str(ready))+');pending=p.with_suffix(".pending");pending.write_text(str(os.getpid()));pending.replace(p);print("ready",flush=True);time.sleep(10)'
    def wait_ready(owner,*args,**kwargs):
        try:
            check(all(path.resolve().is_relative_to(r.root.resolve()) for path in owner.paths),'timeout fixture path mismatch')
            while not ready.is_file():
                owner.check_budget();time.sleep(.005)
            owner.check_budget()
            check(ready.read_bytes()==str(owner.proc.pid).encode() and owner.proc.poll() is None and time.monotonic()<owner.deadline,'timeout fixture ready identity')
            captured.update(owner=owner,live=True,deadline=owner.deadline)
            return original_wait(owner,*args,**kwargs)
        except BaseException:
            if owner.result is None:owner.stop('timeout_fixture_setup_failed')
            raise
    with patch.object(q.OwnedChild,'wait',wait_ready):
        expect_failure('bounded-timeout',lambda:r.run('tiny',[sys.executable,'-c',code],3),'timeout',record=False)
    raw_result=(r.root/'stages/tiny/result.json').read_bytes();result=json.loads(raw_result);terminal=result['ownership']
    _actual_timeout_proof(result,raw_result,captured.get('live'),captured['owner'].proc.pid)
    check((r.root/'stages/tiny/stdout.bin').read_bytes().splitlines()==[b'ready'],'timeout fixture ready output missing')
    before=[q.descriptor(path) for path in captured['owner'].paths]
    check(before==[terminal['stdout'],terminal['stderr']],'timeout fixture stream binding')
    time.sleep(.03);check(before==[q.descriptor(path) for path in captured['owner'].paths],'timeout fixture output mutation')
    RESULTS.append(dict(name='bounded-timeout',passed=True))
    for label,value,live,pid in [('missing-ready',terminal,False,terminal['root_pid']),('foreign-ready',terminal,True,terminal['root_pid']+1),
                               ('early-setup',dict(terminal,classification='setup-failed'),True,terminal['root_pid']),
                               ('unproved-cleanup',dict(terminal,cleanup_ok=False),True,terminal['root_pid'])]:
        expect_failure('bounded-timeout-proof-'+label,lambda value=value,live=live,pid=pid:timeout_proof(value,live,pid),'boundary not proved')
    missing=recorder('missing-stage',('tiny','missing'))
    missing.run('tiny',[sys.executable,'-c','pass'],2)
    expect_failure('missing-stage',lambda:missing.finish(binding,binding))
    expect_failure('duplicate-stage',lambda:good.run('tiny',[sys.executable,'-c','pass'],2))
    data={p.relative_to(good.root).as_posix():p.read_bytes() for p in good.root.rglob('*') if p.is_file()}
    reported=recorder('requested-report');report=reported.root/'report.json'
    reported.run('tiny',[sys.executable,'-c','from pathlib import Path; Path('+repr(str(report))+').write_text("{}")'],2,reports=[report])
    reported.finish(binding,binding)
    omitted={p.relative_to(reported.root).as_posix():p.read_bytes() for p in reported.root.rglob('*') if p.is_file()}
    del omitted['report.json'];record=json.loads(omitted['stages/tiny/result.json']);record['reports']={};omitted['stages/tiny/result.json']=json.dumps(record).encode()
    expect_failure('genuine-requested-report-map-omission',lambda:q.validate_recordings(omitted.__getitem__,ident,['tiny']), 'requested report inventory mismatch')

    for name,path in [('missing-stdout','stages/tiny/stdout.bin'),('missing-stderr','stages/tiny/stderr.bin'),('missing-result-report','stages/tiny/result.json')]:
        incomplete=dict(data);del incomplete[path]
        expect_failure(name,lambda incomplete=incomplete:q.validate_recordings(incomplete.__getitem__,ident,['tiny']))
    swapped=copy.deepcopy(ident);swapped['commit']='4'*40
    expect_failure('swapped-candidate',lambda:q.validate_recordings(data.__getitem__,swapped,['tiny']))
    mutated=dict(data);stage=json.loads(mutated['stages/tiny/result.json']);stage['binaries_after'][str(binary)]['sha256']='f'*64
    mutated['stages/tiny/result.json']=json.dumps(stage).encode()
    expect_failure('swapped-binary',lambda:q.validate_recordings(mutated.__getitem__,ident,['tiny']))
    expect_failure('source-mutation-after-capture',lambda:good.finish(binding,dict(size=2,sha256='4'*64)))
    diagnostic=q.failure_diagnostics(good.root,root/'diagnostic.json',ident,['tiny'],['tiny'],'synthetic failure')
    saved=diagnostic['files']['stages/tiny/stdout.bin']
    check(base64.b64decode(saved['data'])==data['stages/tiny/stdout.bin'] and not saved['truncated'] and diagnostic['passed'] is False,
          'exact partial raw diagnostics')
    RESULTS.append(dict(name='failure-diagnostics-exact-bytes',passed=True))
    (good.root/'stages/tiny/stdout.bin').write_bytes(bytes(range(256))*300)
    diagnostic=q.failure_diagnostics(good.root,root/'diagnostic-bounded.json',ident,['tiny'],['tiny'],'synthetic bounded failure')
    saved=diagnostic['files']['stages/tiny/stdout.bin']
    check(saved['truncated'] and saved['size']==76800 and saved['retained_bytes']==65536 and
          saved['sha256']==q.digest(good.root/'stages/tiny/stdout.bin') and (root/'diagnostic-bounded.json').stat().st_size<=256*1024,
          'bounded partial diagnostics')
    RESULTS.append(dict(name='failure-diagnostics-bounded-truncation',passed=True))
    binary.write_bytes(b'changed')
    expect_failure('binary-mutation-after-capture',lambda:good.finish(binding,binding))


def audit_launch_controls():
    # Pure callbacks model CPython's payloads; this is not Windows execution.
    argv=['C:\\Program Files\\Python\\python.exe','space argument\\','embedded"quote','trailing\\','','\u4e2d\u6587']
    windows=subprocess.list2cmdline(argv)
    with patch.object(q,'_ACTIVE_OWNER',object()),patch.object(q,'_LAUNCH_THREAD',q.threading.get_ident()),patch.object(q,'_LAUNCH_ARGV',argv):
        with patch.object(q.os,'name','nt'):
            control('windows-audit-exact-quoted-command',lambda:q._audit_launch('subprocess.Popen',(argv[0],windows,None,None)))
            for index in range(len(argv)):
                changed=list(argv);changed[index]+='changed'
                expect_failure('windows-audit-changed-argument-'+str(index),lambda changed=changed:q._audit_launch('subprocess.Popen',(changed[0],subprocess.list2cmdline(changed),None,None)),'unmanaged process launch')
            expect_failure('windows-audit-wrong-payload-type',lambda:q._audit_launch('subprocess.Popen',(argv[0],argv,None,None)),'unmanaged process launch')
            with patch.object(q,'_LAUNCH_THREAD',-1):
                expect_failure('windows-audit-wrong-launch-thread',lambda:q._audit_launch('subprocess.Popen',(argv[0],windows,None,None)),'unmanaged process launch')
        with patch.object(q.os,'name','posix'):
            control('posix-audit-exact-argv',lambda:q._audit_launch('subprocess.Popen',(argv[0],argv,None,None)))
            expect_failure('posix-audit-command-string-rejected',lambda:q._audit_launch('subprocess.Popen',(argv[0],windows,None,None)),'unmanaged process launch')
            expect_failure('posix-audit-changed-command',lambda:q._audit_launch('subprocess.Popen',(argv[0],argv+['changed'],None,None)),'unmanaged process launch')


def proc_reader_controls():
    if os.name=='nt':return
    pid=os.getpid();model_pid=1<<32;model_other=model_pid+1
    # Unallocatable pid_t values keep mocked ancestry distinct from real fixtures.
    fields=['S',str(pid),'0','0','0','0','0','0','0','0','0','0','0','0','0','0','0','0','0','123']
    raw=lambda n,comm='unusual ) comm with spaces':str(n)+' ('+comm+') '+' '.join(fields)
    control('proc-stat-unusual-comm',lambda:check(q._parse_proc_stat(raw(model_pid),model_pid)['start']==123,'comm parsing'))
    expect_failure('proc-stat-pid-mismatch',lambda:q._parse_proc_stat(raw(model_pid),model_other),'PID/comm mismatch')
    expect_failure('proc-stat-malformed',lambda:q._parse_proc_stat(str(model_pid)+' (x) S 1',model_pid),'incomplete proc stat')
    with patch.object(q,'_PROC_RECORD_CAP',8):expect_failure('proc-stat-size-cap',lambda:q._parse_proc_stat(raw(model_pid),model_pid),'record cap')
    with tempfile.TemporaryDirectory(prefix='n49d-proc-read-') as tmp:
        path=Path(tmp)/'stat';text=raw(model_pid,comm='\u00e9');data=text.encode('utf-8');path.write_bytes(data)
        control('proc-read-multibyte-at-byte-cap',lambda:check(q._parse_proc_stat(q._proc_read(path,len(data)),model_pid)['start']==123,'multibyte byte boundary'))
        expect_failure('proc-read-multibyte-over-byte-cap',lambda:q._proc_read(path,len(text)),'proc record byte cap')
        with patch.object(q,'_PROC_RECORD_CAP',len(text)):
            expect_failure('proc-stat-multibyte-over-byte-cap',lambda:q._parse_proc_stat(text,model_pid),'record cap')
        path.write_bytes(b'\xff')
        expect_failure('proc-read-strict-decoding',lambda:q._proc_read(path,1),'decode')
        path.write_bytes(b'\xff\xff')
        expect_failure('proc-read-byte-cap-before-decoding',lambda:q._proc_read(path,1),'proc record byte cap')
    def read_missing(path,cap):
        if path.name=='children':raise FileNotFoundError(2,'missing interface')
        return raw(int(path.parent.name))
    with patch.object(q,'_PROC_STAT_CHILD_ADAPTER',None),patch.object(q,'_proc_read',read_missing),patch.object(q,'_proc_pids',lambda:iter([model_pid])):
        control('proc-self-ENOENT-adapter',lambda:check(q._linux_children(pid)==[model_pid] and q._PROC_STAT_CHILD_ADAPTER is True,'self adapter selection'))
    with patch.object(q,'_PROC_STAT_CHILD_ADAPTER',None),patch.object(q,'_proc_read',side_effect=PermissionError(13,'denied')):
        expect_failure('proc-access-denial-no-fallback',lambda:q._linux_children(pid),'denied')
        check(q._PROC_STAT_CHILD_ADAPTER is None,'denial selected fallback')
    with patch.object(q,'_PROC_STAT_CHILD_ADAPTER',False),patch.object(q,'_proc_read',side_effect=FileNotFoundError(2,'child disappeared')):
        expect_failure('proc-child-disappearance-no-route-switch',lambda:q._linux_children(model_pid),'child disappeared')
        check(q._PROC_STAT_CHILD_ADAPTER is False,'child race selected alternate interface')
    def vanished(n,deadline=None):
        if n==model_pid:raise FileNotFoundError(2,'disappeared')
        return dict(ppid=pid,start=123,state='S')
    with patch.object(q,'_PROC_STAT_CHILD_ADAPTER',True),patch.object(q,'_proc_pids',lambda:iter([model_pid,model_other])),patch.object(q,'_linux_stat',vanished):
        control('proc-normal-disappearance-race',lambda:check(q._linux_children(pid)==[model_other],'disappearing record'))
        with patch.object(q,'_PROC_ENTRY_CAP',1):expect_failure('proc-entry-cap',lambda:q._linux_children(pid),'inventory cap')
    with patch.object(q,'_PROC_STAT_CHILD_ADAPTER',True),patch.object(q,'_proc_pids',lambda:iter([model_pid])),patch.object(q,'_proc_read',side_effect=PermissionError(13,'stat denied')):
        expect_failure('proc-stat-denial-fails',lambda:q._linux_children(pid),'stat denied')
    with patch.object(q,'_PROC_STAT_CHILD_ADAPTER',True),patch.object(q,'_PROC_SCAN_SECONDS',0),patch.object(q,'_proc_pids',lambda:iter([model_pid])):
        expect_failure('proc-wall-time-cap',lambda:q._linux_children(pid),'deadline')
    for exited in (False,True):
        tree=object.__new__(q._LinuxTree);tree.known={}
        with patch.object(q,'_linux_stat',side_effect=[dict(ppid=pid,start=123,state='S'),FileNotFoundError(2,'gone')]),patch.object(os,'pidfd_open',return_value=999),patch.object(os,'close'),patch.object(q,'_pidfd_exited',return_value=exited):
            if exited:control('proc-disappearance-after-pidfd-exit',lambda:tree.observe(model_pid,pid))
            else:expect_failure('proc-live-pidfd-missing-record',lambda:tree.observe(model_pid,pid),'live pidfd lost identity record')
    for label,after in [('start',dict(ppid=pid,start=124,state='S')),('link',dict(ppid=pid+1,start=123,state='S'))]:
        tree=object.__new__(q._LinuxTree);tree.known={}
        with patch.object(q,'_linux_stat',side_effect=[dict(ppid=pid,start=123,state='S'),after]),patch.object(os,'pidfd_open',return_value=999),patch.object(os,'close') as close:
            expect_failure('proc-pidfd-'+label+'-mismatch',lambda:tree.observe(model_pid,pid),'pidfd identity/ancestry mismatch')
            check(not tree.known and close.call_args.args==(999,),'uncertain pidfd was admitted')


def absence_oracle_controls():
    if os.name=='nt':return
    call=lambda:q._linux_no_children(time.monotonic()+1)
    flags=os.WEXITED|os.WNOHANG|os.WNOWAIT|0x40000000
    with patch.object(os,'waitid',side_effect=ChildProcessError(errno.ECHILD,'fixture')) as query:
        control('oracle-exact-ECHILD',call)
        check(query.call_args.args==(os.P_ALL,0,flags),'oracle exact non-consuming flags')
    for label,value in [('none',None),('event',os.waitid_result((7,0,q.signal.SIGCHLD,7,os.CLD_EXITED))),('malformed',object())]:
        with patch.object(os,'waitid',return_value=value):
            expect_failure('oracle-reject-'+label,call,'kernel child absence not proved')
    for code in (errno.EINTR,errno.ESRCH,errno.EINVAL,errno.EPERM,errno.EACCES,errno.ENOSYS,errno.EIO):
        with patch.object(os,'waitid',side_effect=OSError(code,'fixture')):
            expect_failure('oracle-reject-errno-'+str(code),call,'kernel child absence not proved')
    with patch.object(os,'waitid',side_effect=ChildProcessError('no errno')):
        expect_failure('oracle-reject-untyped-child-error',call,'kernel child absence not proved')
    with patch.object(os,'waitid',None):
        expect_failure('oracle-missing-API',call,'oracle API unavailable')
    with patch.dict(os.__dict__):
        del os.WNOWAIT
        expect_failure('oracle-missing-required-flag',call,'oracle API unavailable')
    with patch.object(os,'waitid',side_effect=ChildProcessError(errno.ECHILD,'fixture')) as query:
        expect_failure('oracle-deadline-before',lambda:q._linux_no_children(time.monotonic()-1),'oracle deadline')
        check(not query.called,'expired oracle performed query')
        with patch.object(q.time,'monotonic',side_effect=[0,2]):
            expect_failure('oracle-deadline-after',lambda:q._linux_no_children(1),'oracle deadline')
        with patch.object(q.signal,'getsignal',side_effect=[q.signal.SIG_DFL,q.signal.SIG_IGN]):
            expect_failure('oracle-reaper-changed-after',call,'SIGCHLD changed')
    with patch.object(q.signal,'getsignal',return_value=q.signal.SIG_IGN),patch.object(os,'waitid') as query:
        expect_failure('oracle-incompatible-reaper-before',call,'incompatible SIGCHLD')
        check(not query.called,'incompatible reaper reached oracle')
    control('oracle-genuine-no-children',call)
    live=subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for attempt in range(2):expect_failure('oracle-genuine-live-nonconsuming-'+str(attempt),call,'kernel child absence not proved')
        check(live.poll() is None,'oracle consumed or terminated live sentinel')
    finally:live.terminate();live.wait(timeout=2)
    child=subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.buffer.read(1);raise SystemExit(7)'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    fd=os.pidfd_open(child.pid,0);raw=None
    try:
        q._linux_children(os.getpid())
        if q._PROC_STAT_CHILD_ADAPTER is False:raw=Path('/proc',str(child.pid),'stat').open('rb')
        child.stdin.write(b'x');child.stdin.close();deadline=time.monotonic()+2
        while not q._pidfd_exited(fd):
            check(time.monotonic()<deadline,'genuine child exit deadline');time.sleep(.005)
        for attempt in range(2):expect_failure('oracle-genuine-zombie-nonconsuming-'+str(attempt),call,'kernel child absence not proved')
        check(child.wait(timeout=2)==7,'oracle consumed fixture exit status')
        if raw is not None:
            def stale_stat():
                try:raw.read(4097)
                except OSError as error:check(error.errno==errno.ESRCH,'native stale-stat wrong errno');return
                raise ValueError('native stale-stat did not reject reaped process')
            control('native-proc-open-stat-after-reap-ESRCH',stale_stat)
    finally:
        if raw is not None:raw.close()
        os.close(fd)
        if child.poll() is None:child.kill()
        child.wait(timeout=2)
    control('oracle-genuine-empty-after-explicit-reap',call)


def disappearance_controls():
    if os.name=='nt':return
    own=os.getpid();model_parent=1<<32;model_child=model_parent+1
    # Pure model identities cannot collide with any real Linux pid_t.
    record=dict(ppid=own,start=123,state='S')
    def tree(known=None):
        value=object.__new__(q._LinuxTree);value.known={} if known is None else known;value.proc=None;return value
    for code in (errno.ENOENT,errno.ESRCH):
        gone=lambda:OSError(code,'fixture disappeared')
        value=tree()
        with patch.object(q,'_linux_stat',side_effect=gone()),patch.object(os,'pidfd_open') as opened:
            control('disappearance-pre-pin-'+str(code),lambda:check(value.observe(model_parent,own) is None,'explicit unpinned result'))
            check(not opened.called,'vanished unpinned PID opened')
        for exited in (False,True):
            value=tree({model_parent:dict(fd=999,start=123)})
            with patch.object(q,'_linux_stat',side_effect=gone()),patch.object(q,'_pidfd_exited',return_value=exited):
                action=lambda:check(value.observe(model_parent,own) is None,'known disappeared pin')
                if exited:control('disappearance-known-exited-'+str(code),action)
                else:expect_failure('disappearance-known-live-'+str(code),action,'live pidfd lost identity')
            value=tree()
            with patch.object(q,'_linux_stat',side_effect=[record,gone()]),patch.object(os,'pidfd_open',return_value=999),patch.object(os,'close') as closed,patch.object(q,'_pidfd_exited',return_value=exited):
                action=lambda:check(value.observe(model_parent,own) is None,'post-pin disappeared')
                if exited:control('disappearance-post-pin-exited-'+str(code),action)
                else:expect_failure('disappearance-post-pin-live-'+str(code),action,'live pidfd lost identity')
                check(not value.known and closed.call_count==1 and closed.call_args.args==(999,),'temporary pin close count')
        value=tree();visited=[]
        def unpinned_children(pid):visited.append(pid);return [model_parent] if pid==own else []
        with patch.object(q,'_linux_children',unpinned_children),patch.object(q,'_linux_stat',side_effect=gone()):
            control('unpinned-no-numeric-descent-'+str(code),lambda:check(value.active()==[] and visited==[own],'unpinned PID traversed'))
        for exited in (False,True):
            value=tree({model_parent:dict(fd=999,start=123)});reads=[];polls=[]
            def children(pid):
                reads.append(pid)
                if pid==own:return [model_parent]
                raise gone()
            def ready(fd):polls.append(fd);return exited if len(polls)>2 else False
            with patch.object(q,'_linux_children',children),patch.object(q,'_linux_stat',return_value=record),patch.object(q,'_pidfd_exited',ready):
                if exited:control('descendant-enumeration-exited-'+str(code),lambda:check(value.active()==[],'exited traversal'))
                else:expect_failure('descendant-enumeration-live-'+str(code),value.active,'live pidfd lost child inventory')
                check(reads==[own,model_parent],'enumeration control missed intended boundary')
        value=tree({model_parent:dict(fd=999,start=123)})
        with patch.object(q,'_linux_children',return_value=[]),patch.object(q,'_pidfd_exited',return_value=True),patch.object(q,'_linux_stat',side_effect=gone()),patch.object(os,'waitpid') as reaped:
            value.proc=type('Root',(),{'pid':model_child,'poll':lambda self:None})()
            control('exited-reap-record-disappearance-'+str(code),lambda:check(value.active()==[],'reap disappearance'))
            check(not reaped.called,'missing identity was reaped numerically')
        with patch.object(q,'_linux_children',return_value=[]),patch.object(q,'_pidfd_exited',return_value=False),patch.object(q,'_linux_stat',side_effect=gone()) as inspected,patch.object(os,'waitpid') as reaped:
            control('live-pin-never-entered-reap-'+str(code),lambda:check(value.active()==[model_parent],'live child treated as absent'))
            check(not inspected.called and not reaped.called,'live child entered exited-only reap path')
        pin=dict(fd=999,start=123);value=tree({model_parent:pin})
        for exited in (False,True):
            with patch.object(q,'_pidfd_exited',side_effect=[False,exited]),patch.object(q,'_linux_stat',side_effect=gone()):
                if exited:control('parent-record-exited-'+str(code),lambda:check(value.parent_current(model_parent,pin) is False,'exited parent retained'))
                else:expect_failure('parent-record-live-'+str(code),lambda:value.parent_current(model_parent,pin),'live parent pidfd lost identity')
    with patch.object(q,'_PROC_STAT_CHILD_ADAPTER',None),patch.object(q,'_proc_read',side_effect=ProcessLookupError(errno.ESRCH,'self disappeared')):
        expect_failure('self-ESRCH-never-selects-adapter',lambda:q._linux_children(own),'self disappeared')
        check(q._PROC_STAT_CHILD_ADAPTER is None,'self ESRCH selected fallback')
    for label,error in [('permission',PermissionError(errno.EACCES,'denied')),('unknown',OSError(errno.EIO,'I/O fixture')),('parse',ValueError('malformed fixture'))]:
        with patch.object(q,'_linux_stat',side_effect=error):
            expect_failure('observe-fails-'+label,lambda:tree().observe(model_parent,own))
    pin=dict(fd=999,start=123);value=tree({model_parent:pin})
    with patch.object(q,'_pidfd_exited',return_value=True),patch.object(os,'pidfd_open') as opened,patch.object(q.signal,'pidfd_send_signal') as signaled:
        control('queued-exited-parent-discard',lambda:check(value.observe(model_child,model_parent,pin) is None,'exited parent admitted child'))
        check(not opened.called and not signaled.called,'exited parent led to child pin/signal')
    with patch.object(q,'_pidfd_exited',return_value=False),patch.object(q,'_linux_stat',return_value=dict(record,start=124)),patch.object(os,'pidfd_open') as opened,patch.object(q.signal,'pidfd_send_signal') as signaled:
        expect_failure('queued-reused-parent-rejected',lambda:value.observe(model_child,model_parent,pin),'owned parent identity changed')
        check(not opened.called and not signaled.called,'reused parent led to child pin/signal')
    expect_failure('queued-parent-pin-replaced',lambda:value.observe(model_child,model_parent,dict(pin)),'queued parent pin mismatch')
    for phase,answers in [('before-pin',[True,False]),('after-pin',[True,True,False])]:
        with patch.object(value,'parent_current',side_effect=answers),patch.object(q,'_linux_stat',return_value=dict(record,ppid=model_parent)),patch.object(os,'pidfd_open',return_value=998) as opened,patch.object(os,'close') as closed:
            control('parent-exit-during-admission-'+phase,lambda:check(value.observe(model_child,model_parent,pin) is None,'exited parent admission'))
            check(model_child not in value.known and opened.call_count==(phase=='after-pin') and closed.call_count==(phase=='after-pin'),'admission temporary pin ownership')
    exited=[];visited=[]
    def changing_children(pid):
        visited.append(pid)
        if pid==own:return [model_parent]
        exited.append(True);return [model_child]
    with patch.object(q,'_linux_children',changing_children),patch.object(q,'_linux_stat',return_value=record),patch.object(q,'_pidfd_exited',side_effect=lambda fd:bool(exited)),patch.object(os,'pidfd_open') as opened:
        control('parent-exit-during-enumeration-discards-list',lambda:check(value.active()==[] and visited==[own,model_parent],'stale parent list descended'))
        check(not opened.called,'stale parent list pinned child')
    with patch.object(q,'_linux_stat',return_value=record),patch.object(os,'pidfd_open',return_value=998):
        control('true-adoption-admitted-separately',lambda:check(value.observe(model_child,own)==dict(fd=998,start=123),'true adopted route failed'))


def windows_diagnostic_controls(root):
    """Fixed-width API models; these do not claim Windows execution."""
    import ctypes as c
    from types import SimpleNamespace
    root.mkdir()
    class Accounting(c.Structure):
        _fields_=[(name,c.c_uint32) for name in ('TotalProcesses','ActiveProcesses','TotalTerminatedProcesses')]
    class C:
        def __getattr__(self,name):return getattr(c,name)
        @staticmethod
        def get_last_error():return 5
    def model(mode='live',count=1):
        now=[0.];calls=[];closed=[];waits=[];tree=object.__new__(q._WindowsTree)
        tree.c=C();tree.w=SimpleNamespace(DWORD=c.c_uint32,BOOL=c.c_int32)
        tree.Accounting=Accounting;tree.ProcessList=q._windows_job_list_type(c)
        tree.job=123;tree.assigned=True;tree.proc=SimpleNamespace(pid=456)
        tree.last_accounting=dict(total=17,active=count,terminated=3)
        class Kernel:
            def QueryInformationJobObject(self,job,kind,out,size,length):
                calls.append(('query',job,kind));check(job==123,'diagnostic queried another job')
                if mode=='query-exception':raise OSError('fixture API')
                if kind==1:
                    check(size==c.sizeof(Accounting),'accounting model size')
                    out._obj.TotalProcesses=0xffffffff;out._obj.ActiveProcesses=count;out._obj.TotalTerminatedProcesses=0xffffffff
                    return mode!='accounting-error'
                check(kind==3 and size==264,'fixed x64 process-list buffer')
                out._obj.assigned=count;out._obj.listed=count
                length._obj.value=size
                for i in range(min(count,32)):out._obj.pids[i]=0xffffffff-i
                if mode=='partial':out._obj.assigned=count+1
                if mode=='zero':out._obj.pids[0]=0
                if mode=='duplicate':out._obj.pids[1]=out._obj.pids[0]
                if mode=='pid-range':out._obj.pids[0]=0x100000000
                if mode=='short-length':length._obj.value=7
                if mode=='long-length':length._obj.value=size+1
                if mode=='list-overrun':now[0]=.101
                return mode!='more-data'
            def OpenProcess(self,rights,inherit,pid):
                calls.append(('open',rights,inherit,pid));check(rights==0x00101000 and inherit is False,'diagnostic process rights')
                if mode=='open-overrun':now[0]=.101
                return 0 if mode=='open-error' else pid
            def IsProcessInJob(self,handle,job,out):
                calls.append(('membership',handle,job));check(job==123,'wrong membership job')
                out._obj.value=mode!='nonmember'
                if mode=='membership-overrun':now[0]=.101
                return mode!='membership-error'
            def WaitForSingleObject(self,handle,milliseconds):
                calls.append(('wait',handle,milliseconds));check(milliseconds==0,'diagnostic positive wait')
                check(any(row==('membership',handle,123) for row in calls),'state before exact membership')
                check(mode not in ('nonmember','membership-error'),'unrelated state inspected')
                waits.append(handle);before=waits.count(handle)==1
                if mode=='wait-exception':raise OSError('fixture wait')
                if mode=='wait-failed':return 0xffffffff
                if mode=='wait-unexpected':return 128
                if mode=='wait-after-error' and not before:return 0xffffffff
                if mode=='wait-overrun':now[0]=.101
                if mode=='conflict':return 0 if before else 258
                if mode=='exit-between':return 258 if before else 0
                return 0 if mode=='exited259' else 258
            def GetExitCodeProcess(self,handle,out):
                calls.append(('exit',handle));out._obj.value=7 if mode=='exit-inconsistent' else 259
                if mode=='exit-overrun':now[0]=.101
                return mode!='exit-error'
            def CloseHandle(self,handle):
                calls.append(('close',handle));closed.append(handle)
                if mode=='close-overrun':now[0]=.101
                if mode=='close-exception':raise OSError('fixture close')
                return mode!='close-error'
        tree.k=Kernel()
        with patch.object(q.time,'monotonic',lambda:now[0]):value=tree.diagnostic(0 if mode=='expired' else 1)
        return value,calls,closed
    control('windows-diagnostic-fixed-width-ABI',lambda:check(c.sizeof(q._windows_job_list_type(c))==264 and c.sizeof(c.c_uint32)==4,'Windows ABI'))
    for label,mode,count in [('live','live',1),('exited-code-259','exited259',1),('exit-between-reads','exit-between',1),('empty-later-sample','live',0),('maximum-shape','live',32)]:
        value,calls,closed=model(mode,count)
        check(value['complete'] and len(value['members'])==count and len(closed)==count,'valid diagnostic model')
        check(value['trigger']==dict(total=17,active=count,terminated=3) and value['accounting']['total']==0xffffffff,'trigger accounting overwritten')
        check(value['observation']==('live_member_observed' if count and mode!='exited259' else 'no_live_member_observed_in_complete_snapshot'),'diagnostic observation')
        check(len((json.dumps(value,sort_keys=True,indent=2)+'\n').encode())<=8192,'formatted diagnostic field cap')
        RESULTS.append(dict(name='windows-diagnostic-model-'+label,passed=True))
    for mode,count in [('accounting-error',1),('query-exception',1),('more-data',1),('partial',1),('zero',1),('duplicate',2),('pid-range',1),('short-length',1),('long-length',1),('cap',33),('open-error',1),('membership-error',1),('nonmember',1),('wait-failed',1),('wait-unexpected',1),('wait-after-error',1),('wait-exception',1),('exit-error',1),('conflict',1),('exit-inconsistent',1),('close-error',1),('close-exception',1),('expired',1),('list-overrun',1),('open-overrun',1),('membership-overrun',1),('wait-overrun',1),('exit-overrun',1),('close-overrun',1)]:
        value,calls,closed=model(mode,count)
        check(value['complete'] is False and value['observation']=='unknown','invalid diagnostic model accepted: '+mode)
        opened=[row[-1] for row in calls if row[0]=='open' and mode!='open-error']
        check(closed==opened,'diagnostic close path: '+mode)
        check(value['handles_closed']==(mode not in ('close-error','close-exception')),'unproved diagnostic closure')
        check(len([row for row in calls if row[0]=='query' and row[2]==3])<=1,'diagnostic list retried')
        if mode in ('more-data','partial','zero','duplicate','pid-range','short-length','long-length','cap','expired'):
            check(not opened,'incomplete list examined members')
        if mode in ('membership-error','nonmember'):
            check(not any(row[0] in ('wait','exit') for row in calls),'unverified member state exported')
        RESULTS.append(dict(name='windows-diagnostic-model-'+mode,passed=True))
    control('windows-diagnostic-serialization-cap',lambda:check(q._bounded_job_diagnostic({'oversized':'x'*8192})['error']=='metadata_cap','diagnostic cap'))
    control('windows-diagnostic-serialization-error',lambda:check(q._bounded_job_diagnostic({'invalid':object()})['error']=='metadata_cap','diagnostic serializer failure'))
    # Use production JSON formatting at the actual nesting depth, then verify the
    # existing partial-evidence writer preserves the complete maximum-shape result.
    maximum=model('live',32)[0]
    ident=identity();stage=root/'stages/tiny';stage.mkdir(parents=True)
    raw=b'x'*(70*1024)
    for name in ('stdout.bin','stderr.bin'):(stage/name).write_bytes(raw)
    result=dict(schema='qbrain-n49d-stage-v1',name='direct-production',identity=ident,
                argv=['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File','scripts/build-cl.ps1'],
                cwd='D:\\a\\qbrain\\qbrain',classification='lingering-descendant',exit=0,timeout_seconds=1800,
                stream_limit=8*q.MIB,elapsed_seconds=1800.123456,requested_reports=[],available_reports={},
                binaries_before={},binaries_after={},runtime_options={},
                ownership=dict(classification='lingering-descendant',exit=0,process_backend='windows-private-job',root_pid=0xffffffff,
                    cleanup_ok=True,cleanup_error=None,owned_tree_empty=True,stable=True,readers_done=True,
                    elapsed_seconds=1800.123456,job_diagnostic=maximum,stdout=q.descriptor(stage/'stdout.bin'),stderr=q.descriptor(stage/'stderr.bin')),
                stdout=q.descriptor(stage/'stdout.bin'),stderr=q.descriptor(stage/'stderr.bin'))
    q.dump(stage/'result.json',result);check((stage/'result.json').stat().st_size<=16*1024,'maximum full result exceeds retained result cap')
    output=root/'diagnostics.json';packet=q.failure_diagnostics(root,output,ident,['tiny'],['tiny'],'lingering-descendant')
    retained=packet['files']['stages/tiny/result.json']
    check(not retained['truncated'] and base64.b64decode(retained['data'])==(stage/'result.json').read_bytes(),'diagnostic result truncation')
    check(output.stat().st_size<=256*1024 and packet['passed'] is False,'diagnostic artifact cap/status')
    for name in ('stdout.bin','stderr.bin'):
        row=packet['files']['stages/tiny/'+name]
        check(row['truncated'] and row['sha256']==hashlib.sha256(raw).hexdigest() and base64.b64decode(row['data'])==raw[-64*1024:],'raw failure stream changed')
    RESULTS.append(dict(name='windows-diagnostic-maximum-formatted-artifact-retention',passed=True))
    for mode in ('open-overrun','close-exception'):
        result['ownership']['job_diagnostic']=model(mode)[0]
        q.dump(stage/'result.json',result)
        packet=q.failure_diagnostics(root,output,ident,['tiny'],['tiny'],'lingering-descendant')
        row=packet['files']['stages/tiny/result.json'];retained=json.loads(base64.b64decode(row['data']))
        check(not row['truncated'] and retained==result and retained['ownership']['job_diagnostic']['complete'] is False,'diagnostic error retention')
        RESULTS.append(dict(name='windows-diagnostic-serialized-'+mode,passed=True))
    result['ownership']['job_diagnostic']=maximum
    windows_field=(json.dumps(maximum,sort_keys=True,indent=2)+'\n').replace('\n','\r\n').encode()
    windows_result=(json.dumps(result,sort_keys=True,indent=2)+'\n').replace('\n','\r\n').encode()
    check(len(windows_field)<=8192 and len(windows_result)<=16*1024,'Windows CRLF diagnostic retention caps')
    with patch.object(q.os,'linesep','\r\n'):
        check(q._bounded_job_diagnostic(maximum)==maximum,'Windows diagnostic metadata bound')
    RESULTS.append(dict(name='windows-diagnostic-Windows-JSON-layout-caps',passed=True))


def windows_pinned_member_controls(root):
    if os.name!='nt':return
    root.mkdir();ready=root/'ready';release=root/'release';handle=None;owner=None
    code='import sys,time;from pathlib import Path\nPath('+repr(str(ready))+').write_text("ready")\nend=time.monotonic()+4\nwhile not Path('+repr(str(release))+').is_file():\n if time.monotonic()>=end:raise SystemExit(8)\n time.sleep(.005)\nsys.exit(259)'
    try:
        owner=q.OwnedChild([sys.executable,'-c',code],root,dict(os.environ),subprocess.DEVNULL,root/'stdout.bin',root/'stderr.bin',5,512)
        tree=owner.tree;setup_deadline=owner.deadline
        while not ready.is_file():
            owner.check_budget();time.sleep(.005)
        listing=tree.ProcessList();length=tree.w.DWORD()
        check(tree.k.QueryInformationJobObject(tree.job,3,tree.c.byref(listing),tree.c.sizeof(listing),tree.c.byref(length)) and
              listing.assigned==listing.listed<=32 and owner.proc.pid in listing.pids[:listing.listed],'native fixture is not listed in exact job')
        handle=tree.k.OpenProcess(0x00101000,False,owner.proc.pid);check(bool(handle),'native pinned fixture open')
        member=tree.w.BOOL()
        check(tree.k.IsProcessInJob(handle,tree.job,tree.c.byref(member)) and member.value,'native pinned fixture membership')
        live=tree.observe_member(handle,min(setup_deadline,time.monotonic()+.1))
        check('error' not in live and live['wait_before']==live['wait_after']==258 and live['exit_code']==259,'native live pinned observation')
        release.write_text('exit')
        # Scheduling and exit coordination finish before the observation window.
        while owner.proc.poll() is None:
            owner.check_budget();time.sleep(.005)
        check(owner.proc.returncode==259 and tree.k.WaitForSingleObject(handle,0)==0,'native fixture did not exit 259')
        exited=tree.observe_member(handle,min(setup_deadline,time.monotonic()+.1))
        check('error' not in exited and exited['wait_before']==exited['wait_after']==0 and exited['exit_code']==259,'259 misclassified as alive')
        check(tree.k.CloseHandle(handle),'native pinned fixture close');handle=None
        terminal=owner.stop('pinned_fixture_complete')
        check(terminal['classification']=='stopped' and terminal['cleanup_ok'] and terminal['stable'],'native pinned fixture finalization')
        RESULTS.append(dict(name='windows-genuine-live-and-precoordinated-exited259-pinned-handle',passed=True))
    finally:
        if handle:check(owner.tree.k.CloseHandle(handle),'native fixture emergency handle close')
        if owner is not None and owner.result is None:owner.stop('pinned_fixture_failure')


def root_terminal_controls(root):
    """Finite cleanup models; no process/handle is allocated by these models."""
    import test_mcp_directory_search as driver
    root.mkdir();empty=dict(size=0,sha256=hashlib.sha256(b'').hexdigest())
    def model(label,polls=(1,),active=([],),primary='timeout',intentional=False,close='ok',
              poll_cost=0,active_cost=0,join='ok',capture='ok',proc=True,tree=True):
        folder=root/label;folder.mkdir();paths=[folder/'stdout.bin',folder/'stderr.bin']
        for path in paths:path.write_bytes(b'')
        now=[0.];calls=[];returned=[];poll_values=list(polls);active_values=list(active);release=[];closed=[False]
        def next_value(values):return values.pop(0) if len(values)>1 else values[0]
        class Proc:
            pid=17;stdout=None;stderr=None
            def poll(self):
                calls.append('poll');now[0]+=poll_cost;value=next_value(poll_values)
                if isinstance(value,BaseException):raise value
                if value is not None:returned.append(value)
                calls.append('poll-completed');return value
        class Tree:
            def active(self):
                check(not closed[0],'tree queried after close attempt');calls.append('active');now[0]+=active_cost
                value=next_value(active_values)
                if isinstance(value,BaseException):raise value
                return value
            def terminate(self):check(not closed[0],'tree terminated after close attempt');calls.append('terminate')
            def close(self):
                check(not closed[0],'ownership close repeated');closed[0]=True;calls.append('close')
                if close in ('oracle-reject','oracle-success'):
                    from types import SimpleNamespace
                    real=object.__new__(q._LinuxTree);real.known={17:dict(fd=999,start=1)};real.previous=SimpleNamespace(value=0);real.restored=False
                    def live():calls.append('close-active');return []
                    def children(pid):calls.append('close-children');return []
                    def prctl(*args):calls.append('restore');return 0
                    def released(fd):check(fd==999,'model fd changed');calls.append('fd-close')
                    def waitid(*args):
                        calls.append('close-oracle')
                        if close=='oracle-success':raise ChildProcessError(errno.ECHILD,'model no children')
                        return None
                    real.active=live;real.libc=SimpleNamespace(prctl=prctl)
                    with patch.object(q,'_linux_children',children),patch.object(q.os,'getpid',return_value=17),patch.object(q.os,'waitid',waitid,create=True),patch.object(q.os,'close',released),patch.object(q.signal,'getsignal',return_value=q.signal.SIG_DFL):
                        q._LinuxTree.close(real)
                    return
                if close in ('throw','partial'):raise ValueError('close-'+close)
                if close in ('equal','late'):now[0]=2 if close=='equal' else 2.1
        class Reader:
            def join(self,timeout):
                calls.append('join');check(0<=timeout<=2 if primary else timeout<=10,'reader received new grace')
                if join=='throw':raise ValueError('reader-fixture')
                if join=='late':now[0]=2.1
            def is_alive(self):return False
        class Lock:
            def release(self):release.append(True)
        owner=object.__new__(q.OwnedChild);owner.started=0;owner.deadline=10;owner.scan_deadline=10
        owner.proc=Proc() if proc else None;owner.tree=Tree() if tree else None;owner.paths=paths;owner.readers=[Reader()] if proc else []
        owner.result=None;owner.stable=False;owner.locked=True;owner.job_diagnostic=None;owner.errors=[];owner.overflow=q.threading.Event()
        original_descriptor=q.descriptor
        def descriptor(path):
            calls.append('hash-'+Path(path).name)
            if capture=='both' or (capture=='stdout' and Path(path)==paths[0]):raise OSError('capture-fixture')
            value=original_descriptor(path)
            if capture=='late':now[0]=2.1
            return value
        with patch.object(q.time,'monotonic',lambda:now[0]),patch.object(q.time,'sleep',lambda seconds:now.__setitem__(0,now[0]+seconds)),patch.object(q,'descriptor',descriptor),patch.object(q,'_OWNER_LOCK',Lock()),patch.object(q,'_ACTIVE_OWNER',owner):
            result=owner._end(primary,intentional);saved=copy.deepcopy(result);count=len(calls)
            check(owner._end('replacement',True) is result and result==saved and len(calls)==count,'cached finalization changed')
            if result['classification']!='passed':
                expect_failure('root-model-repeat-'+label,lambda:owner.wait(),result['classification'])
                check(owner.stop() is result and result==saved and len(calls)==count,'repeat cleanup changed record')
            else:check(owner.wait() is result and len(calls)==count,'passed repeat repolled')
            check(result['exit']==(returned[0] if returned else None),'synthetic or discarded root exit')
            check(len(release)==int(result['cleanup_ok'] and result['readers_done']),'owner release disagrees with proof')
            if 'close' in calls:check(not any(v in ('poll','active','terminate','close') for v in calls[calls.index('close')+1:]),'operations after close attempt')
        RESULTS.append(dict(name='root-model-'+label,passed=True));return owner,result,calls
    owner,value,calls=model('empty-before-root',polls=(None,None,7))
    check(value['exit']==7 and value['classification']=='timeout' and value['stable'] and calls.count('poll')==3,'empty tree bypassed root')
    owner,value,calls=model('root-before-empty',active=([1],[1],[]))
    check(value['stable'] and calls.count('poll')==1 and calls.count('active')==3,'root exit cache/job barrier')
    for code in (0,7,259):
        owner,value,calls=model('terminal-'+str(code),polls=(code,),primary=None)
        check(value['classification']=='passed' and value['exit']==code and value['stable'],'terminal value rejected')
    for primary in ('timeout','preselected-fixture',None):
        deadline=2 if primary else 10
        for terminal in (None,7):
            for overrun in (0,.1):
                label='post-poll-'+str(primary)+'-'+str(terminal)+'-'+str(overrun)
                owner,value,calls=model(label,polls=(terminal,),primary=primary,poll_cost=deadline+overrun)
                marker=calls.index('poll-completed')
                check(not any(v in ('poll','active','terminate','close') for v in calls[marker+1:]) and
                      calls[:marker].count('terminate')==int(bool(primary)) and owner.scan_deadline==deadline and
                      value['classification']==(primary or 'timeout') and value['exit']==terminal and
                      'owned cleanup deadline exceeded' in value['cleanup_error'] and not value['cleanup_ok'] and not value['stable'] and owner.locked,
                      'exhausted poll crossed into another operation or changed failure/deadline')
    owner,value,calls=model('post-poll-just-before',poll_cost=1.999)
    check(value['cleanup_ok'] and calls.index('poll-completed')<calls.index('active')<calls.index('close'),'eligible next observation rejected')
    if os.name!='nt':
        owner,value,calls=model('actual-linux-close-oracle-reject',polls=(0,),primary=None,close='oracle-reject')
        check(value['classification']=='cleanup-failed' and value['cleanup_error']=='kernel child absence not proved' and
              not value['cleanup_ok'] and not value['stable'] and owner.locked and calls.count('close')==1 and
              calls.count('close-oracle')==1 and 'restore' not in calls and 'fd-close' not in calls,'real close oracle rejection retried/released')
        owner,value,calls=model('actual-linux-close-oracle-success',polls=(0,),primary=None,close='oracle-success')
        check(value['classification']=='passed' and value['cleanup_ok'] and not owner.locked and
              calls.count('close')==calls.count('close-oracle')==calls.count('restore')==calls.count('fd-close')==1 and
              calls.index('close-oracle')<calls.index('restore')<calls.index('fd-close'),'real close oracle release ordering')
    owner,value,calls=model('intentional',primary=None,intentional=True)
    check(value['classification']=='stopped' and value['stable'],'intentional stop changed')
    for label,kwargs in [('pending',dict(polls=(None,))),('poll-error',dict(polls=(OSError('poll-fixture'),))),
                         ('active-error',dict(active=(OSError('active-fixture'),))),('poll-deadline',dict(poll_cost=2)),
                         ('active-deadline',dict(active_cost=2)),('close-equal',dict(close='equal')),('close-late',dict(close='late')),
                         ('close-throw',dict(close='throw')),('close-partial',dict(close='partial')),
                         ('join-throw',dict(join='throw')),('join-late',dict(join='late')),('hash-late',dict(capture='late'))]:
        owner,value,calls=model(label,**kwargs)
        check(value['classification']=='timeout' and not value['cleanup_ok'] and not value['stable'] and owner.locked,'incomplete cleanup released/passed')
        if label.startswith('close-'):check(calls.count('close')==1,'close attempt missing/repeated')
    for label,kwargs in [('poll-recovered',dict(polls=(OSError('poll-fixture'),None,1))),('active-recovered',dict(active=(OSError('active-fixture'),[])))]:
        owner,value,calls=model(label,**kwargs)
        check(value['classification']=='timeout' and value['cleanup_ok'] and value['cleanup_error'] and calls.count('close')==1,'pre-close fallback lost failure')
    owner,value,calls=model('no-root-failed',proc=False)
    check(value['exit'] is None and value['root_pid'] is None and value['cleanup_ok'] and 'poll' not in calls,'failed no-root setup')
    owner,value,calls=model('no-root-no-tree',proc=False,tree=False)
    check(value['cleanup_ok'] and value['exit'] is None,'failed pre-tree setup')
    for label,kwargs in [('missing-root-success',dict(proc=False,primary=None)),('root-without-tree',dict(tree=False))]:
        owner,value,calls=model(label,**kwargs);check(value['classification']!='passed' and not value['cleanup_ok'] and owner.locked,'impossible ownership passed')
    for unavailable in ('stdout','both'):
        owner,value,calls=model('descriptor-'+unavailable,capture=unavailable)
        check(value['stdout'] is None and value['stderr']==(None if unavailable=='both' else empty) and value['exit']==1 and
              value['classification']=='timeout' and value['capture_error']==('both-unavailable' if unavailable=='both' else 'stdout-unavailable'),'failed descriptor shape')
        recorder=q.Recorder(root/('recorder-'+unavailable),identity(),['tiny'],dict(os.environ),root)
        def failed_owner(*args,**kwargs):raise q.OwnedChildError('timeout',owner)
        with patch.object(q,'OwnedChild',failed_owner),patch.object(q,'descriptor',side_effect=AssertionError('failed-path rehash')):
            expect_failure('root-recorder-partial-'+unavailable,lambda:recorder.run('tiny',['fixture'],3,reports=[recorder.root/'report.json']),'timeout')
        row=json.loads((recorder.root/'stages/tiny/result.json').read_bytes())
        check(row['ownership']==value and row['stdout'] is None and row['stderr']==value['stderr'] and row['available_reports']=={},'Recorder lost failed cached metadata')
        ev=driver.Evidence(root/('driver-'+unavailable));child=object.__new__(driver.OwnedProcess)
        child.owner=owner;child.proc=owner.proc;child.ev=ev;child.closed=False;child.record={'status':'running'};child.started=time.monotonic()
        child.stdout_path=owner.paths[0];child.stderr_path=owner.paths[1]
        # The unchanged adapter uses relative evidence paths; use its own tiny files.
        child.stdout_path=ev.path('stdout.bin');child.stderr_path=ev.path('stderr.bin')
        child.stdout_path.write_bytes(b'');child.stderr_path.write_bytes(b'')
        with patch.object(ev,'file',side_effect=AssertionError('unstable driver hash')):
            expect_failure('root-driver-partial-'+unavailable,lambda:child.wait(),'timeout')
        check(child.record['ownership'] is value and child.record['stable'] is False and child.record['stdout']['stable'] is False,'driver partial route changed')
        check(value==owner.result,'adapter changed frozen ownership')
        unavailable_child=copy.copy(child);unavailable_child.closed=False;unavailable_child.record={'status':'running'}
        with patch.object(Path,'is_file',side_effect=OSError('presence-fixture')):
            expect_failure('root-driver-presence-unavailable-'+unavailable,lambda:unavailable_child.wait(),'presence-fixture')
        check(owner.result is value and value['classification']=='timeout' and unavailable_child.record['ownership'] is value and
              unavailable_child.record['stable'] is False,'storage absence erased primary owner failure')
    owner,value,calls=model('report-owner',polls=(0,),primary=None)
    for label in ('report-check','stream-finalizer','write','collector','setup'):
        recorder=q.Recorder(root/('recorder-'+label),identity(),['tiny'],dict(os.environ),root);report=recorder.root/'report.json';report.write_text('{}')
        counts=[];original_descriptor=q.descriptor
        def describe(path):
            counts.append(str(path))
            if Path(path)==report:return original_descriptor(path)
            if label=='stream-finalizer':raise OSError('stream-finalizer-fixture')
            return dict(empty)
        def factory(*args,**kwargs):
            if label=='setup':raise OSError('setup-fixture')
            return owner
        def checking():
            if label in ('report-check','write','collector'):raise ValueError('primary-fixture')
        expected='setup-fixture' if label=='setup' else ('stream-finalizer-fixture' if label=='stream-finalizer' else 'primary-fixture')
        real_dump=q.dump
        def dumping(path,data):
            if label=='write':raise OSError('write-fixture')
            return real_dump(path,data)
        with patch.object(q,'OwnedChild',factory),patch.object(q,'descriptor',describe),patch.object(q,'dump',dumping):
            expect_failure('root-recorder-'+label,lambda:recorder.run('tiny',['fixture'],3,reports=[report],check=checking),expected)
        row=recorder.failed_result
        check(row['classification']==expected and row['ownership']==(None if label=='setup' else value),'failed Recorder primary/owner changed')
        if label in ('report-check','write','collector'):
            check(counts==[str(report)] and row['available_reports']==row['reports'],'failed report was rehashed or lost')
        if label=='setup':check(counts==[] and row['stdout'] is None and row['stderr'] is None,'setup failure invented capture')
        if label=='write':check(row['evidence_error']=='result-write-unavailable' and not (recorder.root/'stages/tiny/result.json').exists(),'write failure claimed record')
        if label=='collector':
            with patch.object(q,'descriptor',side_effect=OSError('collector-fixture')):
                expect_failure('root-recorder-collector-unavailable',lambda:q.failure_diagnostics(recorder.root,recorder.root/'failure.json',identity(),['tiny'],['tiny'],ValueError(expected)),'collector-fixture')
            check(row['classification']==expected and not (recorder.root/'failure.json').exists(),'collector failure erased primary')


def root_terminal_native_controls(root):
    """Real caller APIs; conservative withheld observations are fixture hooks."""
    import test_mcp_directory_search as driver
    root.mkdir();backend=q._WindowsTree if os.name=='nt' else q._LinuxTree
    for kind in ('recorder','driver'):
        for mode in ('root-delayed','job-delayed','pre-close-error','poll-error'):
            folder=root/(kind+'-'+mode);captured=[];ending=[];withheld=[];errors=[];closed=[]
            original_init=q.OwnedChild.__init__;original_end=q.OwnedChild._end;original_active=backend.active;original_close=backend.close
            def setup(owner,*args,**kwargs):
                original_init(owner,*args,**kwargs);captured.append(owner);poll=owner.proc.poll
                def observed_poll():
                    value=poll()
                    if ending and not closed and mode=='poll-error' and not errors:
                        errors.append('poll');raise OSError('root-poll-fixture')
                    if ending and not closed and mode in ('root-delayed','pre-close-error') and value is not None and len(withheld)<2:
                        withheld.append('terminal');return None
                    return value
                owner.proc.poll=observed_poll
            def end(owner,*args,**kwargs):ending.append(owner);return original_end(owner,*args,**kwargs)
            def active(tree):
                value=original_active(tree)
                if captured and tree is captured[0].tree and ending and not closed:
                    if mode=='pre-close-error' and not errors:errors.append('active');raise OSError('root-active-fixture')
                    if mode=='job-delayed' and not value and len(withheld)<2:
                        withheld.append('empty');return [0]  # conservative accounting only, never used as a PID
                return value
            def close(tree):
                check(captured and tree is captured[0].tree and captured[0].proc.returncode is not None,'close before actual terminal root')
                check(mode not in ('root-delayed','job-delayed','pre-close-error') or len(withheld)==2,'close bypassed withheld observation')
                check(not closed,'real close repeated');closed.append(True);return original_close(tree)
            code='import time;print("ready",flush=True)'+(';time.sleep(10)' if mode=='job-delayed' else '')
            expected='timeout' if mode=='job-delayed' else ('cleanup-failed' if mode in ('pre-close-error','poll-error') else None)
            with patch.object(q.OwnedChild,'__init__',setup),patch.object(q.OwnedChild,'_end',end),patch.object(backend,'active',active),patch.object(backend,'close',close):
                if kind=='recorder':
                    recorder=q.Recorder(folder,identity(),['tiny'],dict(os.environ),root,stream_cap=2048)
                    call=lambda:recorder.run('tiny',[sys.executable,'-c',code],3)
                    if expected:expect_failure('root-real-'+kind+'-'+mode,call,expected,record=False)
                    else:call()
                    record=json.loads((folder/'stages/tiny/result.json').read_bytes())
                else:
                    ev=driver.Evidence(folder);child=driver.OwnedProcess(ev,[sys.executable,'-c',code],root,dict(os.environ),timeout=3)
                    if expected:expect_failure('root-real-'+kind+'-'+mode,lambda:child.wait(),expected,record=False)
                    else:child.wait()
                    record=child.record
            check(len(captured)==1 and closed==[True],'real owner boundary not exercised');owner=captured[0];terminal=record['ownership']
            check(terminal['exit']==owner.proc.returncode and terminal['exit'] is not None and
                  terminal['classification']==(expected or 'passed') and all(terminal[k] is True for k in ('cleanup_ok','owned_tree_empty','readers_done','stable')),'real root finalization proof')
            if mode in ('pre-close-error','poll-error'):check(terminal['cleanup_error']==('root-active-fixture' if mode=='pre-close-error' else 'root-poll-fixture'),'pre-close error lost')
            if mode=='job-delayed':check(terminal['exit']!=0,'genuine timeout exited normally')
            before=[q.descriptor(path) for path in owner.paths];check(before==[terminal['stdout'],terminal['stderr']],'real stable descriptor binding')
            check(owner.paths[0].read_bytes().splitlines()==[b'ready'],'real child ready output')
            frozen=copy.deepcopy(owner.result);time.sleep(.03);check(before==[q.descriptor(path) for path in owner.paths],'real output mutation')
            if expected:expect_failure('root-real-repeat-'+kind+'-'+mode,lambda:owner.wait(),expected,record=False)
            else:owner.wait()
            check(owner.result==frozen and q._ACTIVE_OWNER is None and not q._OWNER_LOCK.locked(),'real immutable completion/release')
            RESULTS.append(dict(name='root-real-'+kind+'-'+mode,passed=True))
    if os.name=='nt':
        recorder=q.Recorder(root/'recorder-259',identity(),['tiny'],dict(os.environ),root)
        expect_failure('root-native-259-recorder-nonzero',lambda:recorder.run('tiny',[sys.executable,'-c','raise SystemExit(259)'],3),'nonzero child exit')
        value=recorder.failed_result['ownership'];check(value['exit']==259 and value['cleanup_ok'] and value['stable'],'signaled 259 was not terminal')
        ev=driver.Evidence(root/'driver-259');child=driver.OwnedProcess(ev,[sys.executable,'-c','raise SystemExit(259)'],root,dict(os.environ),timeout=3)
        child.wait(expected=259);check(child.record['ownership']['exit']==259 and child.record['status']=='completed','expected 259 not accepted')
        RESULTS.append(dict(name='root-native-259-driver-expected',passed=True))


def lifecycle_controls(root):
    """Real tiny process trees through Recorder and the process-driver adapter."""
    import test_mcp_directory_search as driver
    root.mkdir();ident=identity();records=[]
    backend=q._WindowsTree if os.name=='nt' else q._LinuxTree
    def run(kind,label,code,timeout=1,check_after=None):
        directory=root/(kind+'-'+label)
        if kind=='recorder':
            recorder=q.Recorder(directory,ident,['tiny'],dict(os.environ),root,stream_cap=512)
            try:value=recorder.run('tiny',[sys.executable,'-c',code],timeout,check=check_after)
            finally:
                result_path=directory/'stages/tiny/result.json'
                if result_path.is_file():records.append(json.loads(result_path.read_bytes()))
            return value,directory/'stages/tiny/stdout.bin'
        ev=driver.Evidence(directory)
        with patch.object(driver,'STREAM_CAP',512):
            child=driver.OwnedProcess(ev,[sys.executable,'-c',code],root,dict(os.environ),timeout=timeout)
            try:child.wait()
            finally:records.append(child.record)
        return child.record,child.stdout_path
    for kind in ('recorder','driver'):
        control(kind+'-owned-ordinary-success',lambda kind=kind:run(kind,'valid','print("valid")'))
        check('job_diagnostic' not in records[-1]['ownership'],'successful command acquired failure diagnostic')
        for branch in ('wait','late'):
            for issue in ('exception','partial','overrun'):
                label='diagnostic-'+branch+'-'+issue;ready=root/(kind+'-'+label+'.pid')
                child='import os,time;from pathlib import Path;p=Path('+repr(str(ready))+');s=p.with_suffix(".pending");s.write_text(str(os.getpid()));s.replace(p);time.sleep(5)'
                code='import subprocess,sys,time;from pathlib import Path\np=subprocess.Popen([sys.executable,"-c",'+repr(child)+'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\nend=time.monotonic()+3\nwhile not Path('+repr(str(ready))+').is_file():\n if time.monotonic()>=end:raise SystemExit(7)\n time.sleep(.005)\n'
                active=backend.active;terminate=backend.terminate;original_wait=q.OwnedChild.wait;original_end=q.OwnedChild._end
                hidden=[];observed=[];terminated=[];owners=[];ending=[]
                def delayed_active(tree):
                    alive=active(tree);owner=q._ACTIVE_OWNER
                    if branch=='late' and alive and not ending and tree.proc.poll() is not None:
                        if not hidden:hidden.append(True)
                        return []
                    return alive
                def enter_end(owner,*args,**kwargs):
                    ending.append(True);return original_end(owner,*args,**kwargs)
                def capture_owner(owner,*args,**kwargs):
                    owners.append(owner);return original_wait(owner,*args,**kwargs)
                def observe(tree,deadline):
                    observed.append(deadline);check(deadline==q._ACTIVE_OWNER.scan_deadline,'diagnostic reset original cleanup deadline')
                    if issue=='exception':raise OSError('injected diagnostic API failure')
                    if issue=='overrun':time.sleep(.12)
                    q._ACTIVE_OWNER.deadline=min(q._ACTIVE_OWNER.deadline,time.monotonic())
                    return dict(complete=False,observation='unknown',error='deadline' if issue=='overrun' else 'process_list',members=[])
                def terminate_record(tree):
                    terminated.append(q._ACTIVE_OWNER.scan_deadline);return terminate(tree)
                with patch.object(backend,'active',delayed_active),patch.object(backend,'diagnostic',observe,create=True),patch.object(backend,'terminate',terminate_record),patch.object(q.OwnedChild,'wait',capture_owner),patch.object(q.OwnedChild,'_end',enter_end):
                    expect_failure(kind+'-'+label,lambda:run(kind,label,code,5),'lingering-descendant',record=False)
                terminal=records[-1]['ownership']
                check(ready.is_file() and len(observed)==1 and terminated and all(value==observed[0] for value in terminated),'diagnostic boundary/deadline not preserved')
                check(branch!='late' or hidden,'late diagnostic boundary not reached')
                check(terminal['classification']=='lingering-descendant' and terminal['cleanup_ok'] and terminal['stable'] and terminal['job_diagnostic']['complete'] is False,'diagnostic changed failure or cleanup')
                expect_failure(kind+'-'+label+'-repeat',lambda:owners[0].wait(),'lingering-descendant')
                check(len(observed)==1,'failure snapshot repeated')
                before=[q.descriptor(path) for path in owners[0].paths];time.sleep(.02)
                check(before==[q.descriptor(path) for path in owners[0].paths],'diagnostic failure output changed')
                RESULTS.append(dict(name=kind+'-'+label+'-original-deadline-cleaned-stable',passed=True))
        if os.name=='nt':
            for redirect in (False,True):
                label='native-job-redirected' if redirect else 'native-job-inherited';ready=root/(kind+'-'+label+'.pid')
                child='import os,time;from pathlib import Path;p=Path('+repr(str(ready))+');s=p.with_suffix(".pending");s.write_text(str(os.getpid()));s.replace(p);time.sleep(5)'
                options=',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL' if redirect else ''
                code='import subprocess,sys,time;from pathlib import Path\np=subprocess.Popen([sys.executable,"-c",'+repr(child)+']'+options+')\nend=time.monotonic()+3\nwhile not Path('+repr(str(ready))+').is_file():\n if time.monotonic()>=end:raise SystemExit(7)\n time.sleep(.005)\n'
                expect_failure(kind+'-'+label,lambda:run(kind,label,code,5),'lingering-descendant',record=False)
                terminal=records[-1]['ownership'];diagnostic=terminal['job_diagnostic']
                check(ready.is_file() and diagnostic['complete'] and diagnostic['observation']=='live_member_observed','native diagnostic fixture boundary')
                check(any(row['pid']==int(ready.read_text()) and row['root'] is False and row['wait_before']==258 for row in diagnostic['members']),'real private-job child not observed alive')
                check(terminal['cleanup_ok'] and terminal['owned_tree_empty'] and terminal['readers_done'] and terminal['stable'],'native diagnostic cleanup')
                stdout=root/(kind+'-'+label)/('stages/tiny/stdout.bin' if kind=='recorder' else 'raw/0002-stdout.bin')
                before=q.descriptor(stdout);time.sleep(.03);check(before==q.descriptor(stdout),'native diagnostic post-cleanup mutation')
                RESULTS.append(dict(name=kind+'-'+label+'-genuine-stable',passed=True))
        churn='import subprocess,sys\nfor wave in range(2):\n children=[subprocess.Popen([sys.executable,"-c","pass"]) for _ in range(4)]\n for child in children:\n  if child.wait()!=0:raise SystemExit(9)\nprint("churn complete")'
        control(kind+'-genuine-bounded-child-churn',lambda kind=kind:run(kind,'churn',churn,3))
        if os.name!='nt':
            pidfile=root/(kind+'-hidden-adoptee.pid');marker=root/(kind+'-observed-adoptee.pid')
            original_children=q._linux_children;original_oracle=q._linux_no_children
            def omission(publication,observed_marker,reader,owner_lookup,pin_child):
                state=dict(conceal=True,owner=None,proc=None,tree=None,root_pin=None,selected=None,pin=None,steps=[])
                def read(pid):
                    try:
                        children=reader(pid)
                        if not state['conceal']:return children
                        owner=owner_lookup()
                        if state['owner'] is None:
                            if owner is None or owner.proc is None or owner.tree is None or pid!=owner.proc.pid:return children
                            check(owner.tree.proc is owner.proc and owner.proc.pid in owner.tree.known,'fixture root not pinned')
                            state.update(owner=owner,proc=owner.proc,tree=owner.tree,root_pin=owner.tree.known[owner.proc.pid])
                        check(owner is state['owner'] and owner.proc is state['proc'] and owner.tree is state['tree'] and
                              owner.tree.proc is state['proc'] and owner.tree.known.get(state['proc'].pid) is state['root_pin'],
                              'fixture owner/root identity changed')
                        if publication.is_file():
                            selected=state['selected']
                            check(selected is not None and publication.stat().st_size<=10 and publication.read_bytes()==str(selected).encode(),'fixture atomic handoff mismatch')
                            if 'publication' not in state['steps']:
                                state['steps'].append('publication');state['pin']=pin_child(selected)
                            return [child for child in children if child!=selected]
                        check(state['proc'].returncode is None,'fixture atomic handoff missing')
                        if pid!=state['proc'].pid:return children
                        check(len(children)<=1,'fixture has multiple children')
                        if not children:return children
                        selected=children[0]
                        check(type(selected) is int and 0<selected<=0x7fffffff and selected not in (pid,os.getpid()),'fixture child PID invalid')
                        check(state['selected'] in (None,selected),'fixture child identity changed')
                        if state['selected'] is None:
                            state['selected']=selected;state['steps'].append('observed')
                            check(not observed_marker.exists(),'fixture marker already exists')
                            pending=observed_marker.with_suffix('.pending');pending.write_bytes(str(selected).encode());pending.replace(observed_marker)
                            state['steps'].append('marker')
                        return []
                    except BaseException:
                        state['conceal']=False
                        raise
                return read,state
            # Finite checks of this exact fixture reader never touch model PIDs.
            from types import SimpleNamespace
            for fault in ('unrelated','empty','multiple','changed','owner','root','invalid','missing','malformed','mismatch','matching'):
                folder=root/(kind+'-handoff-'+fault);folder.mkdir();pub=folder/'published';mark=folder/'observed'
                model_root=0x40000000+(os.getpid()&0xffff);model_child=model_root+1
                proc=SimpleNamespace(pid=model_root,returncode=None);pin={};tree=SimpleNamespace(proc=proc,known={model_root:pin})
                owner=SimpleNamespace(proc=proc,tree=tree);current=[owner];values={model_root:[model_child],os.getpid():[model_root,model_child+2],model_root+3:[model_child+4]};pinned=[]
                read,state=omission(pub,mark,lambda pid:list(values.get(pid,[])),lambda:current[0],lambda pid:pinned.append(pid) or 123)
                if fault=='unrelated':
                    current[0]=None;check(read(os.getpid())==values[os.getpid()],'fixture preflight changed');current[0]=owner
                    check(read(os.getpid())==values[os.getpid()] and read(model_root+3)==values[model_root+3] and not mark.exists(),'fixture unrelated enumeration changed')
                elif fault=='empty':
                    values[model_root]=[];check(read(model_root)==[] and not mark.exists(),'empty fixture created marker')
                elif fault in ('multiple','invalid'):
                    values[model_root]=[model_child,model_child+1] if fault=='multiple' else [0]
                    expect_failure(kind+'-handoff-'+fault,lambda:read(model_root),'fixture',record=False)
                    check(not state['conceal'] and read(model_root)==values[model_root] and not mark.exists(),'bad initial fixture remained hidden')
                else:
                    check(read(model_root)==[] and mark.read_bytes()==str(model_child).encode(),'fixture pre-publication observation absent')
                    check(read(os.getpid())==values[os.getpid()] and read(model_root+3)==values[model_root+3],'fixture hid unrelated pre-handoff list')
                    if fault=='changed':values[model_root]=[model_child+1]
                    elif fault=='owner':current[0]=SimpleNamespace(proc=proc,tree=tree)
                    elif fault=='root':owner.proc=SimpleNamespace(pid=model_root,returncode=None)
                    elif fault=='missing':proc.returncode=0
                    elif fault=='malformed':pub.write_bytes(b'invalid')
                    elif fault=='mismatch':pub.write_bytes(str(model_child+1).encode())
                    elif fault=='matching':
                        pub.write_bytes(str(model_child).encode());values[os.getpid()]=[model_child,model_child+2]
                        check(read(os.getpid())==[model_child+2] and pinned==[model_child] and state['steps']==['observed','marker','publication'],'fixture selected handoff')
                    if fault!='matching':
                        expect_failure(kind+'-handoff-'+fault,lambda:read(model_root),'fixture',record=False)
                        check(not state['conceal'] and read(model_root)==values[model_root] and not pinned,'bad handoff remained hidden')
                RESULTS.append(dict(name=kind+'-handoff-'+fault+'-finite-boundary',passed=True))
            omit_fixture,state=omission(pidfile,marker,original_children,lambda:q._ACTIVE_OWNER,lambda pid:os.pidfd_open(pid,0))
            def seam_proof(owner,tree,alive,inside,closing,ready,terminal,adopted,live,in_budget):
                check(inside is owner and owner is state['owner'] and tree is state['tree'] and owner.proc is state['proc'] and
                      tree.proc is state['proc'] and tree.known.get(state['proc'].pid) is state['root_pin'] and
                      not closing and not alive and ready and terminal==0 and terminal is not None and adopted and live and in_budget,
                      'fixture pre-close seam not proved')
            def reject_oracle(fixture,oracle,live):
                try:
                    oracle()
                except ValueError as error:
                    if str(error)!='kernel child absence not proved':raise
                    check(live(),'fixture selected child exited during oracle')
                    fixture['steps'].append('oracle');fixture['conceal']=False;fixture['steps'].append('reveal')
                    raise
                else:raise ValueError('fixture oracle unexpectedly succeeded')
                finally:fixture['conceal']=False
            # These finite seam predicates never inspect a model PID or handle.
            actual_state=state
            model_proc=SimpleNamespace(pid=1,returncode=0);model_pin={};model_tree=SimpleNamespace(proc=model_proc,known={1:model_pin})
            model_owner=SimpleNamespace(proc=model_proc,tree=model_tree)
            state=dict(owner=model_owner,proc=model_proc,tree=model_tree,root_pin=model_pin)
            try:
                base=[model_owner,model_tree,[],model_owner,False,True,0,True,True,True]
                for fault,index,value in [('foreign-owner',0,SimpleNamespace(proc=model_proc)),('foreign-tree',1,SimpleNamespace(proc=model_proc)),
                        ('outside-end',3,None),('prior-close',4,True),('missing-handoff',5,False),('root-pending',6,None),('root-nonzero',6,7),
                        ('nonempty-scan',2,[1]),('unadopted',7,False),('selected-exited',8,False),('deadline',9,False)]:
                    args=list(base);args[index]=value
                    expect_failure(kind+'-preclose-seam-'+fault,lambda args=args:seam_proof(*args),'fixture pre-close seam not proved')
                control(kind+'-preclose-seam-valid',lambda:seam_proof(*base))
                for fault,error,live in [('expected',ValueError('kernel child absence not proved'),True),('wrong-error',ValueError('oracle deadline'),True),
                        ('success',None,True),('exited-after',ValueError('kernel child absence not proved'),False)]:
                    sample=dict(conceal=True,steps=['observed','marker','publication'])
                    def oracle(error=error):
                        if error is not None:raise error
                    expected='kernel child absence not proved' if fault=='expected' else ('oracle deadline' if fault=='wrong-error' else 'fixture')
                    expect_failure(kind+'-preclose-oracle-'+fault,lambda:reject_oracle(sample,oracle,lambda:live),expected)
                    check(sample['conceal'] is False and sample['steps']==(['observed','marker','publication','oracle','reveal'] if fault=='expected' else ['observed','marker','publication']),
                          'wrong oracle result earned fixture proof or remained hidden')
            finally:state=actual_state
            actual_active=q._LinuxTree.active;actual_close=q._LinuxTree.close;actual_end=q.OwnedChild._end
            phase=dict(inside=None,close=False,fired=False,deadline=None);events=[]
            def inside_end(owner,*args,**kwargs):
                if owner.result is not None:return actual_end(owner,*args,**kwargs)
                phase['inside']=owner
                try:return actual_end(owner,*args,**kwargs)
                finally:phase['inside']=None
            def preclose_active(tree):
                alive=actual_active(tree)
                if phase['inside'] is None or not state['conceal'] or phase['fired']:return alive
                try:
                    owner=q._ACTIVE_OWNER;selected=state['selected'];pin=state['pin']
                    live=pin is not None and not q._pidfd_exited(pin)
                    adopted=live and original_children(os.getpid())==[selected] and q._linux_stat(selected)['ppid']==os.getpid() and not q._pidfd_exited(pin)
                    seam_proof(owner,tree,alive,phase['inside'],phase['close'],state['steps']==['observed','marker','publication'],
                        state['proc'].returncode if state['proc'] is not None else None,adopted,live,time.monotonic()<owner.scan_deadline)
                    phase['fired']=True;phase['deadline']=owner.scan_deadline;events.append('pre-close-oracle')
                    return reject_oracle(state,lambda:original_oracle(owner.scan_deadline),lambda:not q._pidfd_exited(pin))
                except BaseException:state['conceal']=False;raise
            def final_close(tree):
                check(phase['fired'] and tree is state['tree'] and phase['inside'] is state['owner'] and not phase['close'] and
                      not state['conceal'] and state['owner'].scan_deadline==phase['deadline'],'fixture final close boundary')
                phase['close']=True;events.append('close');return actual_close(tree)
            def traced_oracle(deadline):
                if phase['close']:
                    phase['close_oracle_deadline']=deadline
                    check(state['owner'].scan_deadline==phase['deadline'] and time.monotonic()<deadline<=phase['deadline'],
                          'fixture close oracle exceeded original cleanup deadline')
                    result=original_oracle(deadline);events.append('close-oracle');return result
                check(state['owner'] is None and not phase['fired'],'fixture unexpected oracle location')
                result=original_oracle(deadline);events.append('preflight');return result
            code='import subprocess,sys,time;from pathlib import Path\np=subprocess.Popen([sys.executable,"-c","import time;time.sleep(5)"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\nm=Path('+repr(str(marker))+');end=time.monotonic()+1\nwhile not m.is_file():\n if time.monotonic()>=end:raise SystemExit(8)\n time.sleep(.005)\nif m.read_bytes()!=str(p.pid).encode():raise SystemExit(9)\npub=Path('+repr(str(pidfile))+');pending=pub.with_suffix(".pending");pending.write_bytes(str(p.pid).encode());pending.replace(pub);print("leader",flush=True)'
            started=time.monotonic()
            try:
                with patch.object(q,'_linux_children',omit_fixture),patch.object(q,'_linux_no_children',traced_oracle),patch.object(q._LinuxTree,'active',preclose_active),patch.object(q._LinuxTree,'close',final_close),patch.object(q.OwnedChild,'_end',inside_end):
                    expect_failure(kind+'-oracle-detects-omitted-adoptee',lambda kind=kind:run(kind,'omitted-adoptee',code,2),'cleanup-failed',record=False)
                ownership=records[-1]['ownership']
                check(state['steps']==['observed','marker','publication','oracle','reveal'] and state['pin'] is not None and q._pidfd_exited(state['pin']),'oracle did not prove ordered fixture cleanup')
                check(ownership['classification']=='cleanup-failed' and ownership['cleanup_error']=='kernel child absence not proved' and ownership['exit']==0 and
                      ownership['cleanup_ok'] and ownership['owned_tree_empty'] and ownership['readers_done'] and ownership['stable'] and
                      events==['preflight','pre-close-oracle','close','close-oracle'] and time.monotonic()<started+5 and
                      q._ACTIVE_OWNER is None and not q._OWNER_LOCK.locked(),'pre-close oracle failure lost permanent safe cleanup')
                frozen=copy.deepcopy(state['owner'].result)
                expect_failure(kind+'-preclose-oracle-repeat-failed',lambda:state['owner'].wait(),'cleanup-failed',record=False)
                check(state['owner'].result==frozen and events==['preflight','pre-close-oracle','close','close-oracle'],'pre-close result changed or closed twice')
                stdout=root/(kind+'-omitted-adoptee')/('stages/tiny/stdout.bin' if kind=='recorder' else 'raw/0002-stdout.bin')
                before=q.descriptor(stdout);time.sleep(.03);check(before==q.descriptor(stdout),'post-cleanup output mutation')
                q._linux_no_children(time.monotonic()+1)
                RESULTS.append(dict(name=kind+'-preclose-oracle-detects-omitted-adoptee',passed=True))
                RESULTS.append(dict(name=kind+'-preclose-oracle-failure-cleaned-stable-permanent',passed=True,
                    trace=dict(steps=list(state['steps']),events=list(events),cleanup_deadline=phase['deadline'],
                               close_oracle_deadline=phase['close_oracle_deadline'],final_absence=True)))
            finally:
                if state['pin'] is not None:os.close(state['pin'])
        def descendant_fixture(label,redirect,detached):
            ready=root/(kind+'-'+label+'.pid');confirmed=root/(kind+'-'+label+'.confirmed');release=root/(kind+'-'+label+'.release')
            child='import os,sys,time;from pathlib import Path\np=Path('+repr(str(ready))+');release=Path('+repr(str(release))+');end=time.monotonic()+10\ns=p.with_suffix(".pending");s.write_text(str(os.getpid()));s.replace(p)\nwhile not release.is_file():\n if time.monotonic()>=end:raise SystemExit(8)\n time.sleep(.005)\nif release.read_bytes()!=str(os.getpid()).encode():raise SystemExit(9)\ntime.sleep(.1);print("late descendant",flush=True)'
            options=',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL' if redirect else ''
            if detached:options+=',creationflags=subprocess.CREATE_NEW_PROCESS_GROUP' if os.name=='nt' else ',start_new_session=True'
            code='import subprocess,sys,time;from pathlib import Path\np=subprocess.Popen([sys.executable,"-c",'+repr(child)+']'+options+')\nready=Path('+repr(str(ready))+');end=time.monotonic()+1\nwhile not ready.is_file():\n if time.monotonic()>=end:raise SystemExit(7)\n time.sleep(.005)\nif ready.read_bytes()!=str(p.pid).encode():raise SystemExit(9)\nc=Path('+repr(str(confirmed))+');s=c.with_suffix(".confirmed-pending");s.write_text(str(p.pid));s.replace(c);print("leader",p.pid,flush=True)'
            return code,ready,confirmed,release
        def descendant_proof(terminal,ready,confirmed,stdout,late=False):
            check(0<len(ready)<=10 and ready.isdigit() and ready==confirmed,'descendant readiness mismatch')
            pid=int(ready)
            check(0<pid<=0xffffffff and ready==str(pid).encode() and pid!=terminal['root_pid'] and
                  stdout.splitlines()==[b'leader '+ready],'descendant ready identity mismatch')
            check(terminal['classification']=='lingering-descendant' and terminal['exit']==0 and
                  terminal['cleanup_error']==('lingering-descendant' if late else None) and
                  all(terminal.get(key) is True for key in ('cleanup_ok','owned_tree_empty','readers_done','stable')),
                  'descendant exact failure/cleanup not proved')
            if os.name=='nt':
                diagnostic=terminal.get('job_diagnostic',{})
                check(diagnostic.get('complete') is True and diagnostic.get('handles_closed') is True and
                      any(row.get('pid')==pid and row.get('root') is False and row.get('wait_before')==258 and 'error' not in row
                          for row in diagnostic.get('members',[])),'descendant native live-member proof missing')
            return pid
        for label,redirect,detached in [('inherited-pipe',False,False),('silent-redirected',True,False),('detached-writer',False,True)]:
            code,ready,confirmed,release=descendant_fixture(label,redirect,detached);started=time.monotonic()
            expect_failure(kind+'-'+label,lambda kind=kind,label=label,code=code:run(kind,label,code,3),'lingering-descendant',record=False)
            terminal=records[-1]['ownership'];folder=root/(kind+'-'+label)
            stdout=folder/('stages/tiny/stdout.bin' if kind=='recorder' else 'raw/0002-stdout.bin')
            stderr=folder/('stages/tiny/stderr.bin' if kind=='recorder' else 'raw/0003-stderr.bin')
            pid=descendant_proof(terminal,ready.read_bytes(),confirmed.read_bytes(),stdout.read_bytes())
            check(time.monotonic()<started+10,'descendant could expire naturally before cleanup proof')
            before=[q.descriptor(path) for path in (stdout,stderr)]
            check(before==[terminal['stdout'],terminal['stderr']],'descendant stream binding')
            release.write_text(str(pid));time.sleep(.55)
            check([q.descriptor(path) for path in (stdout,stderr)]==before,kind+' descendant changed finalized output')
            RESULTS.append(dict(name=kind+'-'+label,passed=True))
            RESULTS.append(dict(name=kind+'-'+label+'-stable-hash',passed=True))
        for fault,raw,confirmation,output,value in [('missing',b'',b'',stdout.read_bytes(),terminal),
                ('malformed',b'bad',b'bad',stdout.read_bytes(),terminal),('mismatched',ready.read_bytes(),b'0',stdout.read_bytes(),terminal),
                ('foreign',b'1',b'1',stdout.read_bytes(),terminal),('earlier-timeout',ready.read_bytes(),confirmed.read_bytes(),stdout.read_bytes(),dict(terminal,classification='timeout')),
                ('unproved-cleanup',ready.read_bytes(),confirmed.read_bytes(),stdout.read_bytes(),dict(terminal,cleanup_ok=False))]:
            expect_failure(kind+'-descendant-proof-'+fault,lambda raw=raw,confirmation=confirmation,output=output,value=value:descendant_proof(value,raw,confirmation,output),'descendant')
        active=backend.active;original_end=q.OwnedChild._end;hidden=[];entered=[];exposed=[];owners=[];phase=['wait']
        late_directory=root/(kind+'-late-finalization')
        def late_entry_proof(failure,intentional,exit,readers,markers):
            check(failure is None and intentional is False and exit==0 and readers and markers,'late fixture entry proof')
        def late_active(tree):
            value=active(tree)
            owner=q._ACTIVE_OWNER
            if value and owner is not None and tree is owner.tree and tree.proc.poll()==0 and all(path.resolve().is_relative_to(late_directory.resolve()) for path in owner.paths):
                if phase[0]=='wait':
                    if not hidden:hidden.append(owner)
                    return []
                if phase[0]=='end' and not exposed:exposed.append(owner)
            return value
        def enter_late(owner,failure=None,intentional=False):
            if owner.result is None:
                try:late_entry_proof(failure,intentional,owner.proc.poll(),not any(reader.is_alive() for reader in owner.readers),hidden==[owner])
                except BaseException:
                    phase[0]='failed';original_end(owner,'fixture_late_entry_failed');raise
                phase[0]='end'
                entered.append(owner);owners.append(owner)
            return original_end(owner,failure,intentional)
        code,ready,confirmed,release=descendant_fixture('late-finalization',True,False);started=time.monotonic()
        with patch.object(backend,'active',late_active),patch.object(q.OwnedChild,'_end',enter_late):
            expect_failure(kind+'-late-finalization-descendant',lambda:run(kind,'late-finalization',code,3),'lingering-descendant',record=False)
        check(len(owners)==1 and hidden==entered==exposed==owners,'late fixture missing ordered transition')
        owner=owners[0];terminal=records[-1]['ownership']
        pid=descendant_proof(terminal,ready.read_bytes(),confirmed.read_bytes(),owner.paths[0].read_bytes(),True)
        check(time.monotonic()<started+10,'late descendant could expire naturally')
        before=[q.descriptor(path) for path in owner.paths];check(before==[terminal['stdout'],terminal['stderr']],'late stream binding')
        release.write_text(str(pid));time.sleep(.55);check(before==[q.descriptor(path) for path in owner.paths],'late finalized stream mutated')
        expect_failure(kind+'-late-repeat-remains-failed',lambda:owner.wait(),'lingering-descendant',record=False)
        RESULTS.append(dict(name=kind+'-late-finalization-descendant',passed=True))
        for label,args in [('timeout',('timeout',False,0,True,True)),('intentional',(None,True,0,True,True)),
                           ('leader-error',(None,False,7,True,True)),('missing-readers',(None,False,0,False,True)),('missing-transition',(None,False,0,True,False))]:
            expect_failure(kind+'-late-proof-'+label,lambda args=args:late_entry_proof(*args),'entry proof')
        expect_failure(kind+'-owned-overflow',lambda kind=kind:run(kind,'overflow','print("x"*1024)'))
        original_drain=q.OwnedChild._drain;original_wait=q.OwnedChild.wait
        go=q.threading.Event();lock=q.threading.Lock();drain=dict(owner=None,eofs={},holds={},errors=[],proved=False)
        drain_directory=root/(kind+'-drain')
        def eof_proof(eofs,paths,deadline,exit):
            check(exit==0 and set(eofs)==set(paths) and len(eofs)==2 and all(value['at']<deadline for value in eofs.values()),'drain EOF proof')
        def hold_proof(holds,paths,deadline):
            check(set(holds)==set(paths) and len(holds)==2 and all(value['begin']<deadline<value['end'] for value in holds.values()),'drain hold proof')
        def slow_drain(owner,pipe,path):
            try:
                original_drain(owner,pipe,path)
                with lock:
                    check(all(p.resolve().is_relative_to(drain_directory.resolve()) for p in owner.paths) and path in owner.paths,'drain fixture owner/path mismatch')
                    check(drain['owner'] is None or drain['owner'] is owner,'drain fixture owner changed')
                    drain['owner']=owner
                    check(path not in drain['eofs'],'duplicate drain EOF')
                    drain['eofs'][path]=dict(at=time.monotonic(),descriptor=q.descriptor(path))
                while not go.is_set():
                    remaining=owner.deadline-time.monotonic();check(remaining>0,'drain setup deadline')
                    go.wait(min(.01,remaining))
                check(drain['proved'],'drain setup proof missing')
                now=time.monotonic();remaining=owner.deadline-now;check(0<remaining<=3,'drain hold missed deadline')
                with lock:drain['holds'][path]=dict(begin=now)
                time.sleep(remaining+.03)
                with lock:drain['holds'][path]['end']=time.monotonic()
            except BaseException:
                with lock:drain['errors'].append('fixture drain proof failed')
                owner.errors.append('fixture drain proof failed');owner.overflow.set();go.set()
            finally:pipe.close()
        def begin_drain_wait(owner,*args,**kwargs):
            try:
                while True:
                    owner.check_budget();code=owner.proc.poll()
                    with lock:
                        check(not drain['errors'],'drain reader setup failed')
                        check(code in (None,0),'drain leader failed')
                        if code==0 and len(drain['eofs'])==2:
                            check(drain['owner'] is owner,'drain main owner mismatch')
                            eof_proof(drain['eofs'],owner.paths,owner.deadline,code)
                            check(time.monotonic()<owner.deadline,'drain setup exhausted deadline')
                            drain['deadline']=owner.deadline;drain['proved']=True;break
                    time.sleep(.005)
                go.set();return original_wait(owner,*args,**kwargs)
            except BaseException:
                go.set()
                if owner.result is None:owner.stop('drain_fixture_setup_failed')
                raise
        with patch.object(q.OwnedChild,'_drain',slow_drain),patch.object(q.OwnedChild,'wait',begin_drain_wait):
            expect_failure(kind+'-deadline-through-drain',lambda kind=kind:run(kind,'drain','print("EOF",flush=True)',3),'timeout',record=False)
        owner=drain['owner'];terminal=records[-1]['ownership']
        check(drain['proved'] and not drain['errors'],'drain did not reach intended EOF/hold boundary')
        eof_proof(drain['eofs'],owner.paths,drain['deadline'],terminal['exit']);hold_proof(drain['holds'],owner.paths,drain['deadline'])
        check(owner.deadline==drain['deadline'] and terminal['classification']=='timeout' and terminal['cleanup_error'] is None and
              all(terminal.get(key) is True for key in ('cleanup_ok','owned_tree_empty','readers_done','stable')),'drain exact timeout/cleanup proof')
        before=[q.descriptor(path) for path in owner.paths]
        check(before==[terminal['stdout'],terminal['stderr']]==[drain['eofs'][path]['descriptor'] for path in owner.paths],'drain EOF stream binding')
        check(owner.paths[0].read_bytes().splitlines()==[b'EOF'] and owner.paths[1].read_bytes()==b'','drain real output/EOF missing')
        time.sleep(.03);check(before==[q.descriptor(path) for path in owner.paths],'drain post-timeout mutation')
        expect_failure(kind+'-drain-repeat-remains-failed',lambda:owner.wait(),'timeout',record=False)
        RESULTS.append(dict(name=kind+'-deadline-through-drain',passed=True))
        for label in ('missing','late','foreign','leader-error'):
            wrong=copy.deepcopy(drain['eofs']);code=0
            if label=='missing':wrong.pop(owner.paths[0])
            elif label=='late':wrong[owner.paths[0]]['at']=drain['deadline']
            elif label=='foreign':wrong[root/'foreign-output']=wrong.pop(owner.paths[0])
            else:code=7
            expect_failure(kind+'-drain-proof-'+label,lambda wrong=wrong,code=code:eof_proof(wrong,owner.paths,drain['deadline'],code),'drain EOF proof')
        for label in ('missing','before-expiry'):
            wrong=copy.deepcopy(drain['holds'])
            if label=='missing':wrong.pop(owner.paths[0])
            else:wrong[owner.paths[0]]['end']=drain['deadline']
            expect_failure(kind+'-drain-hold-proof-'+label,lambda wrong=wrong:hold_proof(wrong,owner.paths,drain['deadline']),'drain hold proof')
        for when in ('before','after'):
            attach=backend.attach
            def broken_attach(tree,proc,when=when):
                if when=='after':attach(tree,proc)
                raise ValueError('injected ownership '+when)
            with patch.object(backend,'attach',broken_attach):
                expect_failure(kind+'-ownership-api-'+when,lambda kind=kind,when=when:run(kind,'api-'+when,'import time;time.sleep(1)'), 'injected ownership '+when)
        for delayed in (False,True):
            terminate=backend.terminate;original_wait=q.OwnedChild.wait;original_init=q.OwnedChild.__init__
            calls=[];started=[];owners=[]
            def broken_terminate(tree):
                terminate(tree)
                if not calls:calls.append(True);raise ValueError('injected cleanup API failure')
            def expire_after_start(owner,*args,**kwargs):
                check(owner.proc is not None and owner.proc.poll() is None,'cleanup fixture has no live owned child')
                started.append(True);owners.append(owner)
                owner.deadline=min(owner.deadline,time.monotonic());owner.scan_deadline=owner.deadline
                return original_wait(owner,*args,**kwargs)
            def setup(owner,*args,**kwargs):
                if delayed:time.sleep(.1)
                original_init(owner,*args,**kwargs)
            label='cleanup-delayed' if delayed else 'cleanup'
            with patch.object(backend,'terminate',broken_terminate),patch.object(q.OwnedChild,'wait',expire_after_start),patch.object(q.OwnedChild,'__init__',setup):
                expect_failure(kind+'-'+label+'-remains-failed',lambda:run(kind,label,'import time;time.sleep(5)',3),'timeout',record=False)
            check(calls==[True] and started==[True],'cleanup fixture did not reach intended real termination')
            terminal=records[-1]['ownership']
            check(terminal['classification']=='timeout' and terminal['cleanup_error']=='injected cleanup API failure' and
                  terminal['cleanup_ok'] and terminal['owned_tree_empty'] and terminal['readers_done'] and terminal['stable'],
                  'cleanup fixture terminal proof')
            expect_failure(kind+'-'+label+'-repeat-stays-failed',lambda:owners[0].wait(),'timeout')
            before=[q.descriptor(path) for path in owners[0].paths];time.sleep(.03)
            check(before==[q.descriptor(path) for path in owners[0].paths],'cleanup fixture output changed')
            RESULTS.append(dict(name=kind+'-'+label+'-reached-cleaned-stable',passed=True))
        final_directory=root/(kind+'-slow-finalizer');captured={};markers=[];original_wait=q.OwnedChild.wait
        def owner_proof(terminal):
            check(terminal.get('classification')=='passed' and terminal.get('exit')==0 and
                  all(terminal.get(key) is True for key in ('owned_tree_empty','cleanup_ok','readers_done','stable')),
                  'finalizer setup owner did not pass')
        def capture_passed(owner,*args,**kwargs):
            terminal=original_wait(owner,*args,**kwargs);owner_proof(terminal)
            check(not captured and not any(reader.is_alive() for reader in owner.readers) and
                  all(path.resolve().is_relative_to(final_directory.resolve()) for path in owner.paths),'finalizer owner/path mismatch')
            captured.update(owner=owner,deadline=owner.deadline,descriptors=[q.descriptor(path) for path in owner.paths])
            check(captured['descriptors']==[terminal['stdout'],terminal['stderr']],'finalizer setup stream binding')
            markers.append('owner-passed');return terminal
        def cross_finalization_deadline():
            check(markers==['owner-passed'] and captured,'finalizer hook missing passed owner')
            owner=captured['owner'];owner_proof(owner.result)
            check(owner.deadline==captured['deadline'] and not any(reader.is_alive() for reader in owner.readers),'finalizer owner changed')
            remaining=captured['deadline']-time.monotonic();check(0<remaining<=3,'finalizer setup exhausted real deadline')
            markers.append('finalization-entered');time.sleep(remaining+.03)
            check(time.monotonic()>captured['deadline'],'finalizer did not cross actual deadline')
            markers.append('deadline-crossed')
        def marker_proof(events):
            check(events==['owner-passed','finalization-entered','deadline-crossed'],'finalizer missing ordered markers')
        if kind=='recorder':
            recorder=q.Recorder(final_directory,ident,['tiny'],dict(os.environ),root,stream_cap=512)
            with patch.object(q.OwnedChild,'wait',capture_passed):
                expect_failure('recorder-slow-finalizer',lambda:recorder.run('tiny',[sys.executable,'-c','pass'],3,check=cross_finalization_deadline),
                               'timeout during stage finalization',record=False)
            record_path=final_directory/'stages/tiny/result.json';saved=record_path.read_bytes();outer=json.loads(saved)
            check(outer['classification']=='timeout during stage finalization','wrong Recorder finalization failure')
            binding=dict(size=1,sha256='1'*64)
            expect_failure('recorder-finalizer-record-rejected',lambda:recorder.finish(binding,binding),'failed/incomplete stage',record=False)
            expect_failure('recorder-finalizer-duplicate-rejected',lambda:recorder.run('tiny',[sys.executable,'-c','pass'],3),'unexpected/duplicate stage',record=False)
            check(record_path.read_bytes()==saved,'Recorder overwrote failed finalization evidence')
        else:
            ev=driver.Evidence(final_directory);original_file=driver.Evidence.file
            def slow_file(evidence,path):
                value=original_file(evidence,path)
                if captured and markers==['owner-passed']:
                    check(evidence is ev and Path(path).resolve()==captured['owner'].paths[0].resolve(),'driver finalizer owner/path mismatch')
                    cross_finalization_deadline()
                return value
            with patch.object(q.OwnedChild,'wait',capture_passed),patch.object(driver.Evidence,'file',slow_file),patch.object(driver,'STREAM_CAP',512):
                child=driver.OwnedProcess(ev,[sys.executable,'-c','pass'],root,dict(os.environ),timeout=3)
                try:child.wait()
                except TimeoutError as error:check(str(error)=='process evidence finalization exceeded whole deadline','wrong driver deadline error')
                else:raise ValueError('driver finalization unexpectedly passed')
            outer=child.record
            check(outer['status']=='failed_finalization_deadline' and outer['finalization_classification']=='timeout','wrong driver finalization failure')
            saved=copy.deepcopy(outer)
            try:child.wait()
            except TimeoutError as error:check(str(error)=='process evidence finalization exceeded whole deadline','wrong repeated driver deadline error')
            else:raise ValueError('repeated driver finalization unexpectedly passed')
            check(child.record is outer and
                  {key:value for key,value in child.record.items() if key!='elapsed_seconds'}==
                  {key:value for key,value in saved.items() if key!='elapsed_seconds'},'driver replaced failed finalization evidence')
            times=[saved['elapsed_seconds'],child.record['elapsed_seconds']]
            check(all(type(value) in (int,float) and math.isfinite(value) and value>=0 for value in times) and times[1]>=times[0],
                  'driver repeated failure elapsed time invalid')
        marker_proof(markers);owner_proof(captured['owner'].result);owner_proof(outer['ownership'])
        check(captured['owner'].deadline==captured['deadline'],'finalizer fixture mutated real deadline')
        check([q.descriptor(path) for path in captured['owner'].paths]==captured['descriptors'],'finalizer raw stream changed')
        time.sleep(.03);check([q.descriptor(path) for path in captured['owner'].paths]==captured['descriptors'],'finalizer post-failure mutation')
        RESULTS.append(dict(name=kind+'-slow-finalizer',passed=True))
        RESULTS.append(dict(name=kind+'-finalizer-failure-permanent-stable',passed=True))
        bad=dict(captured['owner'].result,classification='timeout')
        expect_failure(kind+'-finalizer-rejects-early-owner-failure',lambda:owner_proof(bad),'setup owner did not pass')
        expect_failure(kind+'-finalizer-rejects-missing-hook',lambda:marker_proof(['owner-passed']),'missing ordered markers')
    # Unmanaged siblings make startup reject; never signal that sentinel.
    sentinel=subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        if os.name!='nt':
            for kind in ('recorder','driver'):
                expect_failure(kind+'-unrelated-sentinel-rejected',lambda kind=kind:run(kind,'sentinel','pass'),'unmanaged pre-existing child')
                check(sentinel.poll() is None,'unrelated sentinel was terminated')
                with patch.object(q,'_linux_children',return_value=[]):
                    expect_failure(kind+'-omitted-sentinel-oracle-rejected',lambda kind=kind:run(kind,'omitted-sentinel','pass'),'kernel child absence not proved')
                check(sentinel.poll() is None,'oracle consumed or terminated omitted sentinel')
        else:
            for kind in ('recorder','driver'):
                run(kind,'unrelated-sentinel','pass')
                check(sentinel.poll() is None,'private Windows job affected unrelated sentinel')
                RESULTS.append(dict(name=kind+'-unrelated-sentinel-survives-private-job',passed=True))
    finally:sentinel.terminate();sentinel.wait(timeout=2)
    if os.name!='nt':
        previous=q.signal.getsignal(q.signal.SIGCHLD)
        q.signal.signal(q.signal.SIGCHLD,q.signal.SIG_IGN)
        try:
            for kind in ('recorder','driver'):
                expect_failure(kind+'-incompatible-reaper-rejected',lambda kind=kind:run(kind,'SIGCHLD','pass'),'incompatible SIGCHLD')
        finally:q.signal.signal(q.signal.SIGCHLD,previous)
    # One active owner blocks both nested helper creation and unmanaged Popen.
    ev=driver.Evidence(root/'intentional-stop')
    server=driver.OwnedProcess(ev,[sys.executable,'-c','import time;print("ready",flush=True);time.sleep(10)'],root,dict(os.environ),timeout=2)
    try:
        expect_failure('concurrent-owner-rejected',lambda:run('recorder','concurrent','pass'),'concurrent owned process rejected')
        expect_failure('unmanaged-launch-rejected',lambda:subprocess.Popen([sys.executable,'-c','pass']),'unmanaged process launch')
        expect_failure('unmanaged-system-launch-rejected',lambda:os.system('exit 0'),'unmanaged process launch')
        server.stop('server_stopped_after_checks')
        check(server.record['ownership']['classification']=='stopped' and server.record['stable'],'intentional server stop failed')
        RESULTS.append(dict(name='driver-intentional-stop',passed=True))
    finally:
        if not server.closed:server.stop('cleanup')
    # A finite Recorder command can itself exercise a serial intentional fixture stop.
    code='import sys,os,subprocess;from pathlib import Path;sys.path.insert(0,'+repr(str(Path(q.__file__).parent))+');from run_n49d_qualification import OwnedChild;p=Path('+repr(str(root))+');c=OwnedChild([sys.executable,"-c","import time;time.sleep(10)"],p,dict(os.environ),subprocess.DEVNULL,p/"inner-out",p/"inner-err",2,512);r=c.stop();raise SystemExit(0 if r["classification"]=="stopped" and r["stable"] else 9)'
    control('recorder-intentional-stop-in-owned-command',lambda:run('recorder','intentional',code,3))


def tiny_bundle(root):
    """Synthetic complete approved-source/command fixture, not native execution."""
    root.mkdir();paths=sorted(guard.ALLOW);nodes={};rows={};inventory=b''
    for path in paths:
        data=('synthetic source fixture only: '+path+'\n').encode('utf-8');oid=guard.blob(data)
        dest=root/'source/changed'/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        rows[path]=dict(mode='100644',blob=oid,sha256=hashlib.sha256(data).hexdigest())
        inventory+=b'100644 blob '+oid.encode()+b'\t'+path.encode()+b'\0'
        node=nodes;parts=path.split('/')
        for part in parts[:-1]:node=node.setdefault(part,{})
        node[parts[-1]]=oid
    def tree_hash(node):
        body=b''
        for name,value in sorted(node.items(),key=lambda row:row[0]+('/' if isinstance(row[1],dict) else '')):
            directory=isinstance(value,dict)
            body+=(b'40000' if directory else b'100644')+b' '+name.encode()+b'\0'+bytes.fromhex(tree_hash(value) if directory else value)
        return hashlib.sha1(b'tree '+str(len(body)).encode()+b'\0'+body).hexdigest()
    tree=tree_hash(nodes);ident=identity(tree)
    source=dict(passed=True,commit=ident['commit'],tree=tree,base=guard.BASE,base_tree=guard.BASE_TREE,
                parent=guard.CORRECTION_PARENT,parent_tree=guard.CORRECTION_PARENT_TREE,correction_changed=sorted(guard.CORRECTION_PATHS),precommit=False,
                inventory_sha256=hashlib.sha256(inventory).hexdigest(),changed=paths,changed_files=rows,dependency_sha256={})
    q.dump(root/'reports/source-before.json',source);q.dump(root/'reports/source-after.json',source)
    (root/'source/tree-inventory.bin').write_bytes(inventory);q.dump(root/'source/dependencies.json',{})
    (root/'binaries').mkdir();binary=root/'binaries/qbrain';binary.write_bytes(b'fixture binary only')
    bd=q.descriptor(binary);required=q.required_stages(ident['job_key'])
    locations=dict(source='/fixture/source',build='/fixture/build',output='/fixture/evidence',python='/fixture/python')
    specs=q.stage_contract(ident,locations);prod='/fixture/build/qbrain'
    for mode in ('normal','optimized'):
        mcp=root/'reports'/('mcp_directory_search-'+mode);(mcp/'raw').mkdir(parents=True)
        (mcp/'raw/fixture.bin').write_bytes(b'fixture')
        blob=dict(path='raw/fixture.bin',bytes=7,sha256=hashlib.sha256(b'fixture').hexdigest())
        owned=dict(classification='passed',cleanup_ok=True,stable=True,readers_done=True,exit=0,stdout=dict(size=7,sha256=blob['sha256']),stderr=dict(size=7,sha256=blob['sha256']))
        q.dump(mcp/'RESULT.json',dict(
            schema='qbrain-n49d-mcp-directory-process-v1',passed=True,status='passed',python_optimized=mode=='optimized',
            binary_sha256=bd['sha256'],stdio=dict(status='passed',profiles=['full','memory']),
            http=dict(required=False,status='not_applicable'),provider_http=dict(required=False,status='not_applicable'),
            command_count=1,commands=[dict(argv=[prod,'fixture-only'],status='completed',exit=0,stable=True,ownership=owned,stdin=blob,stdout=blob,stderr=blob)],exchange_count=0,exchanges=[]))
        q.dump(root/'reports'/('directory_search-'+mode)/'RESULT.json',dict(passed=True,checks=[dict(passed=True)],check_count=1,commands=[dict(fixture=True)],command_count=1))
        q.dump(root/'reports'/('context_process-'+mode+'.json'),dict(format_version=1,checks=1,provider_calls=0))
        q.dump(root/'reports'/('named_arguments-'+mode+'.json'),dict(passed=1,failed=0,checks=[dict(passed=True)],commands=[dict(fixture=True)],command_count=1,binary_sha256=bd['sha256']))
    (root/'reports/ctest.xml').write_text('<testsuite>'+''.join('<testcase name="'+name+'"/>' for name in q.TESTS)+'</testsuite>')
    for name in required:
        spec=specs[name];folder=root/'stages'/name;folder.mkdir(parents=True)
        stdout=b'fixture-only\n'
        if name=='ctest-inventory':stdout=json.dumps(dict(tests=[dict(name=n) for n in q.TESTS])).encode()
        elif name=='ctest-completeness':stdout=json.dumps(list(q.TESTS)).encode()
        elif name.startswith('selftest-'):stdout=json.dumps(dict(passed=True,python_optimized=name.endswith('optimized'),linux_reader_backend='native-children',controls=[dict(name='fixture',passed=True)])).encode()
        (folder/'stdout.bin').write_bytes(stdout);(folder/'stderr.bin').write_bytes(b'')
        q.dump(folder/'result.json',dict(name=name,identity=ident,argv=spec['argv'],timeout_seconds=spec['timeout_seconds'],cwd=locations['source'],exit=0,classification='passed',ownership=dict(classification='passed',cleanup_ok=True,stable=True,readers_done=True,exit=0,stdout=q.descriptor(folder/'stdout.bin'),stderr=q.descriptor(folder/'stderr.bin')),
            stdout=q.descriptor(folder/'stdout.bin'),stderr=q.descriptor(folder/'stderr.bin'),requested_reports=spec['reports'],reports={p:q.descriptor(root/p) for p in spec['reports']},
            binaries_before={p:bd for p in spec['binaries_before']},binaries_after={p:bd for p in spec['binaries_after']}))
    binding=q.descriptor(root/'reports/source-before.json')
    q.dump(root/'qualification.json',dict(passed=True,identity=ident,required=required,stages=required,locations=locations,
        source_before=binding,source_after=binding,binaries={p:bd for spec in specs.values() for p in spec['binaries_after']},
        retained_binaries={prod:dict(path='binaries/qbrain',**bd)}))
    return ident


def make_archive(evidence, archive, ident):
    rows=[]
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(evidence.rglob('*'),key=lambda p:p.relative_to(evidence).as_posix()):
            if not p.is_file():continue
            name=p.relative_to(evidence).as_posix();info=zipfile.ZipInfo(name);info.create_system=3
            info.external_attr=(stat.S_IFREG|0o644)<<16;info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,p.read_bytes());rows.append(dict(path=name,mode=stat.S_IFREG|0o644,**q.descriptor(p)))
    desc=q.descriptor(archive)
    manifest=dict(schema='qbrain-n49c-evidence-parts-v1',identity=ident,files=rows,
                  uncompressed_bytes=sum(r['size'] for r in rows),archive=desc,
                  parts=[dict(index=0,file='evidence.part',**desc)])
    return json.dumps(manifest,sort_keys=True).encode()


def wrap(archive, raw, outer, extra=None, omit=None):
    with zipfile.ZipFile(outer,'w',zipfile.ZIP_STORED) as z:
        for name,data in [('manifest.json',raw),('evidence.part',archive.read_bytes())]:
            if name!=omit:z.writestr(name,data)
        if extra:z.writestr(extra,b'x')


def package_consumer_controls(root):
    from pathlib import PureWindowsPath
    order_root=root/'order-fixture';order_root.mkdir()
    order_names=['docs/Z.txt','docs/a.txt','docs/n49d-evidence/RESULT.json','docs/N49D-PLAN.md','prefix-file.txt','prefix/child.txt','\u6587\u6863/\u9875.txt']
    for name in order_names:
        path=order_root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'tiny ordering fixture')
    windows_names=[PureWindowsPath(name) for name in order_names]
    check([p.as_posix() for p in sorted(windows_names)]!=sorted(order_names),'case-folding control is not discriminating')
    control('windows-canonical-relative-POSIX-order-model',lambda:check([p.as_posix() for p in sorted(windows_names,key=lambda p:p.as_posix())]==sorted(order_names),'canonical Windows path key'))
    order_archive=root/'order.zip';order_manifest=make_archive(order_root,order_archive,identity())
    control('actual-mixed-case-prefix-unicode-archive-order',lambda:check([r['path'] for r in q.validate_manifest(order_manifest,identity())['files']]==sorted(order_names),'actual archive canonical order'))
    with zipfile.ZipFile(order_archive) as archive:
        check(archive.namelist()==sorted(order_names),'ZIP and manifest order disagree')
    evidence=root/'evidence';ident=tiny_bundle(evidence)
    archive=root/'tiny.zip';raw=make_archive(evidence,archive,ident);outer=root/'outer.zip';wrap(archive,raw,outer)
    data={p.relative_to(evidence).as_posix():p.read_bytes() for p in evidence.rglob('*') if p.is_file()}
    control('full-fixed-command-report-contract-valid',lambda:q.validate_recordings(data.__getitem__,ident,files=data))
    for name,report_path in [('ctest-run','reports/ctest.xml'),('directory_search-normal','reports/directory_search-normal/RESULT.json'),
                             ('context_process-normal','reports/context_process-normal.json'),('named_arguments-normal','reports/named_arguments-normal.json')]:
        omitted=dict(data);del omitted[report_path];path='stages/'+name+'/result.json';stage=json.loads(omitted[path]);stage['reports']={};stage['requested_reports']=[];omitted[path]=json.dumps(stage).encode()
        expect_failure('full-contract-omitted-'+name,lambda omitted=omitted:q.validate_recordings(omitted.__getitem__,ident,files=omitted),'fixed required report inventory mismatch')
    wrong=dict(data);path='stages/selftest-normal/result.json';stage=json.loads(wrong[path]);stage['argv']=['fixture-only'];wrong[path]=json.dumps(stage).encode()
    expect_failure('full-contract-changed-command',lambda:q.validate_recordings(wrong.__getitem__,ident,files=wrong),'fixed stage command mismatch')
    wrong=dict(data);path='stages/selftest-normal/stdout.bin';report=json.loads(wrong[path]);report['linux_reader_backend']='stat-adapter';wrong[path]=json.dumps(report).encode()
    path='stages/selftest-normal/result.json';stage=json.loads(wrong[path]);desc=dict(size=len(wrong['stages/selftest-normal/stdout.bin']),sha256=hashlib.sha256(wrong['stages/selftest-normal/stdout.bin']).hexdigest());stage['stdout']=desc;stage['ownership']['stdout']=desc;wrong[path]=json.dumps(stage).encode()
    expect_failure('full-contract-native-Linux-reader-required',lambda:q.validate_recordings(wrong.__getitem__,ident,files=wrong),'native Linux children-interface controls required')
    source_path='.ci/run_n49d_qualification.py';source_leaf='source/changed/'+source_path
    def source_packet(change):
        packet=dict(data);binding=json.loads(packet['reports/source-before.json']);change(binding,packet)
        binding_raw=json.dumps(binding,sort_keys=True).encode();desc=dict(size=len(binding_raw),sha256=hashlib.sha256(binding_raw).hexdigest())
        # Rebind every recorded report descriptor, so negatives reach source semantics.
        for label in ('source-before','source-after'):
            report='reports/'+label+'.json';packet[report]=binding_raw
            stage_path='stages/'+label+'/result.json';stage=json.loads(packet[stage_path]);stage['reports'][report]=desc
            packet[stage_path]=json.dumps(stage).encode()
        result=json.loads(packet['qualification.json']);result['source_before']=desc;result['source_after']=desc
        packet['qualification.json']=json.dumps(result).encode()
        return packet
    ancestry_packets=[]
    for field in ('parent','parent_tree','correction_changed'):
        for mode in ('wrong','omitted'):
            def mutate(binding,packet,field=field,mode=mode):
                if mode=='omitted':binding.pop(field)
                else:binding[field]=[] if field=='correction_changed' else '0'*40
            packet=source_packet(mutate);label=field+'-'+mode;ancestry_packets.append((label,packet))
            expect_failure('producer-rehashed-'+label,lambda packet=packet:q.validate_recordings(packet.__getitem__,ident,files=packet),'source/candidate binding mismatch')
    omitted_source=source_packet(lambda binding,packet:(binding['changed_files'].pop(source_path),packet.pop(source_leaf)))
    expect_failure('full-source-omitted-leaf-and-map-rehashed',lambda:q.validate_recordings(omitted_source.__getitem__,ident,files=omitted_source),'fixed changed source map mismatch')
    cases=[
        ('omitted-list-map-leaf',lambda b,p:(b['changed'].remove(source_path),b['changed_files'].pop(source_path),p.pop(source_leaf)),'list'),
        ('mismatched-list',lambda b,p:b['changed'].remove(source_path),'list'),
        ('mismatched-map',lambda b,p:b['changed_files'].pop(source_path),'map'),
        ('duplicate-list',lambda b,p:b['changed'].append(source_path),'list'),
        ('unsorted-list',lambda b,p:b['changed'].reverse(),'list'),
        ('unexpected-list',lambda b,p:b['changed'].append('unexpected.txt'),'list'),
        ('unexpected-map',lambda b,p:b['changed_files'].update({'unexpected.txt':b['changed_files'][source_path]}),'map'),
        ('missing-leaf',lambda b,p:p.pop(source_leaf),'leaf inventory'),
        ('unexpected-leaf',lambda b,p:p.update({'source/changed/unexpected.txt':b'unexpected'}),'leaf inventory'),
        ('altered-bytes',lambda b,p:p.update({source_leaf:b'changed source bytes'}),'bytes'),
        ('altered-mode',lambda b,p:b['changed_files'][source_path].update(mode='100755'),'bytes'),
        ('altered-blob',lambda b,p:b['changed_files'][source_path].update(blob='0'*40),'bytes'),
        ('altered-hash',lambda b,p:b['changed_files'][source_path].update(sha256='0'*64),'bytes'),
        ('altered-bytes-and-map',lambda b,p:(p.update({source_leaf:b'changed source bytes'}),b['changed_files'][source_path].update(blob=guard.blob(b'changed source bytes'),sha256=hashlib.sha256(b'changed source bytes').hexdigest())),'bytes')]
    for label,change,boundary in cases:
        packet=source_packet(change)
        expect_failure('full-source-'+label+'-rehashed',lambda packet=packet:q.validate_recordings(packet.__getitem__,ident,files=packet),'changed source '+boundary)
    expect_failure('full-source-duplicate-leaf-inventory',lambda:q.validate_recordings(data.__getitem__,ident,files=list(data)+[source_leaf]),'fixed changed source leaf inventory mismatch')
    expect_failure('full-source-absent-leaf-inventory',lambda:q.validate_recordings(data.__getitem__,ident),'complete evidence inventory required')
    calls=[]
    def tiny_packager(src,staging,expected):
        calls.append(str(staging));staging=Path(staging);staging.mkdir();zip_path=staging/'tiny.zip'
        manifest=make_archive(Path(src),zip_path,expected);part=staging/'parts/00';part.mkdir(parents=True)
        (part/'evidence.part').write_bytes(zip_path.read_bytes());(part/'manifest.json').write_bytes(manifest)
        return dict(passed=True,identity=expected,parts_root=str(staging/'parts'),part_count=1,
            archive_size=zip_path.stat().st_size,archive_sha256=q.digest(zip_path),manifest_bytes=len(manifest),manifest_sha256=hashlib.sha256(manifest).hexdigest())
    control('actual-package-wrapper-valid-injected-generic',lambda:q.package(evidence,root/'package-valid',ident,_generic_packager=tiny_packager))
    check(len(calls)==1,'actual package wrapper must invoke generic seam once')
    def rejected_packager(*args):raise ValueError('injected generic package failure')
    expect_failure('actual-package-wrapper-generic-failure',lambda:q.package(evidence,root/'package-generic-failure',ident,_generic_packager=rejected_packager),'injected generic package failure')
    expect_failure('actual-package-wrapper-post-compressed-cap',lambda:q.package(evidence,root/'package-compressed-cap',ident,dict(q.LIMITS,compressed=1),_generic_packager=tiny_packager),'N49D compressed cap')
    def wrong_result(src,staging,expected):
        result=tiny_packager(src,staging,expected);result['manifest_sha256']='0'*64;return result
    expect_failure('actual-package-wrapper-result-binding',lambda:q.package(evidence,root/'package-wrong-result',ident,_generic_packager=wrong_result),'generic package result digest mismatch')
    before_calls=len(calls)
    expect_failure('actual-package-wrapper-pre-raw-cap',lambda:q.package(evidence,root/'package-raw-cap',ident,dict(q.LIMITS,raw=1),_generic_packager=tiny_packager),'raw/member cap exceeded')
    check(len(calls)==before_calls,'raw cap must reject before generic invocation')

    control('package-preflight-valid',lambda:q.evidence_inventory(evidence))
    control('package-postflight-valid',lambda:q.validate_manifest(raw,ident))
    control('unchanged-archive-validator-valid',lambda:q.generic_archive()['verify_evidence_archive'](archive,json.loads(raw)))
    review=root/'review';review.mkdir();outer.rename(review/outer.name);outer=review/outer.name
    limits=dict(q.LIMITS,reserve=0,compressed=128*1024,text=256*1024,staging=1024*1024,outer=256*1024)
    sha=hashlib.sha256(raw).hexdigest()
    control('consumer-valid',lambda:q.consume(outer,review,ident,sha,q.digest(outer),limits))
    result=json.loads(data['qualification.json']);manifest=json.loads(raw);selection=q.review_selection(result,manifest['files'])
    selected={r['path'] for r in selection}
    check('reports/source-after.json' not in selected and 'stages/source-before/stdout.bin' not in selected and
          'reports/mcp_directory_search-normal/RESULT.json' in selected and not any(p.startswith('binaries/') for p in selected) and
          {p for p in selected if p.startswith('source/changed/')}=={'source/changed/'+p for p in guard.ALLOW}, 'explicit materialized review subset')
    RESULTS.append(dict(name='explicit-review-selection-valid',passed=True))
    expect_failure('review-selection-missing-mandatory',lambda:q.review_selection(result,[r for r in manifest['files'] if r['path']!='source/dependencies.json']), 'required review selection missing')
    source_row=next(r for r in manifest['files'] if r['path']==source_leaf)
    expect_failure('review-selection-missing-source',lambda:q.review_selection(result,[r for r in manifest['files'] if r['path']!=source_leaf]),'fixed changed source leaf inventory mismatch')
    expect_failure('review-selection-duplicate-source',lambda:q.review_selection(result,manifest['files']+[source_row]),'fixed changed source leaf inventory mismatch')
    expect_failure('review-selection-unexpected-source',lambda:q.review_selection(result,manifest['files']+[dict(source_row,path='source/changed/unexpected.txt')]),'fixed changed source leaf inventory mismatch')
    omitted_root=root/'source-omission-evidence';omitted_root.mkdir()
    for name,value in omitted_source.items():
        dest=omitted_root/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(value)
    expect_failure('actual-package-omitted-source-and-map',lambda:q.package(omitted_root,root/'source-omission-package',ident,_generic_packager=tiny_packager),'fixed changed source map mismatch')
    omitted_archive=root/'source-omission.zip';omitted_manifest=make_archive(omitted_root,omitted_archive,ident)
    omitted_review=root/'source-omission-review';omitted_review.mkdir();omitted_outer=omitted_review/'download.zip';wrap(omitted_archive,omitted_manifest,omitted_outer)
    expect_failure('consumer-omitted-source-and-map-rehashed',lambda:q.consume(omitted_outer,omitted_review,ident,hashlib.sha256(omitted_manifest).hexdigest(),q.digest(omitted_outer),limits),'fixed changed source map mismatch')
    for label,packet in ancestry_packets:
        invalid=root/('ancestry-'+label);invalid.mkdir();src=invalid/'evidence';src.mkdir()
        for name,value in packet.items():
            dest=src/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(value)
        before_calls=len(calls)
        expect_failure('package-rehashed-'+label,lambda src=src,invalid=invalid:q.package(src,invalid/'package',ident,_generic_packager=tiny_packager),'source/candidate binding mismatch')
        check(len(calls)==before_calls,'invalid ancestry reached generic packager')
        packed=invalid/'inner.zip';packed_manifest=make_archive(src,packed,ident);review_dir=invalid/'review';review_dir.mkdir();download=review_dir/'download.zip';wrap(packed,packed_manifest,download)
        expect_failure('consumer-rehashed-'+label,lambda download=download,review_dir=review_dir,packed_manifest=packed_manifest:q.consume(download,review_dir,ident,hashlib.sha256(packed_manifest).hexdigest(),q.digest(download),limits),'source/candidate binding mismatch')
    cap_root=root/'selection-cap';cap_root.mkdir();cap_outer=cap_root/'download.zip';cap_outer.write_bytes(outer.read_bytes())
    expect_failure('review-selection-cumulative-size-cap',lambda:q.consume(cap_outer,cap_root,ident,sha,q.digest(cap_outer),dict(limits,text=sum(r['size'] for r in selection)-1)), 'aggregate retained-text cap')
    raw_path=evidence/'reports/mcp_directory_search-normal/raw/fixture.bin';old_raw=raw_path.read_bytes();raw_path.write_bytes(b'changed')
    changed_archive=root/'unselected-raw.zip';changed_manifest=make_archive(evidence,changed_archive,ident);changed_outer=review/'unselected-raw.zip';wrap(changed_archive,changed_manifest,changed_outer)
    expect_failure('unselected-raw-still-semantically-checked',lambda:q.consume(changed_outer,review,ident,hashlib.sha256(changed_manifest).hexdigest(),q.digest(changed_outer),limits), 'MCP raw evidence mismatch')
    raw_path.write_bytes(old_raw)

    expect_failure('out-of-root-unaccounted-download',lambda:q.consume(outer,root/'unaccounted',ident,sha,q.digest(outer),limits),'download must reside in aggregate review staging')
    expect_failure('cumulative-retained-text-cap',lambda:q.consume(outer,review,ident,sha,q.digest(outer),
        dict(limits,text=q.review_text_bytes(review)-1)),'aggregate retained-text cap')
    expect_failure('cumulative-staging-cap',lambda:q.consume(outer,review,ident,sha,q.digest(outer),
        dict(limits,staging=q.staging_size(review)+limits['compressed']+limits['text']-q.review_text_bytes(review)-1)),'consumer staging cap')

    for name,key,value in [('manifest-cap','manifest',len(raw)-1),('member-count-cap','members',1),
                           ('raw-size-cap','raw',1),('compressed-size-cap','compressed',1)]:
        cap=dict(q.LIMITS);cap[key]=value
        expect_failure(name,lambda cap=cap:q.validate_manifest(raw,ident,cap))
    for name,key in [('package-input-raw-cap','raw'),('package-input-member-cap','members')]:
        cap=dict(q.LIMITS);cap[key]=1
        expect_failure(name,lambda cap=cap:q.evidence_inventory(evidence,cap))
    expect_failure('consumer-staging-cap',lambda:q.consume(outer,review,ident,sha,q.digest(outer),dict(limits,staging=1)),'consumer staging cap')
    for name,kwargs in [('missing-outer-member',dict(omit='evidence.part')),('extra-outer-member',dict(extra='extra'))]:
        bad=review/(name+'.zip');wrap(archive,raw,bad,**kwargs)
        expect_failure(name,lambda bad=bad:q.consume(bad,review,ident,sha,q.digest(bad),limits),'missing/extra outer member')
    expect_failure('wrong-manifest-hash',lambda:q.consume(outer,review,ident,'0'*64,q.digest(outer),limits),'independent manifest digest mismatch')
    expect_failure('wrong-artifact-hash',lambda:q.consume(outer,review,ident,sha,'0'*64,limits),'independent GitHub artifact digest mismatch')
    broken=root/'broken.zip';broken.write_bytes(bytes([archive.read_bytes()[0]^1])+archive.read_bytes()[1:]);bad=review/'wrong-part.zip';wrap(broken,raw,bad)
    expect_failure('wrong-part-hash',lambda:q.consume(bad,review,ident,sha,q.digest(bad),limits),'wrong part digest')
    for name,key,value in [('wrong-job','job_key','windows-cmake'),('wrong-run-attempt','run_attempt','3'),('wrong-candidate','commit','5'*40)]:
        badident=dict(ident);badident[key]=value
        if key=='job_key':badident['job_label']=value
        expect_failure(name,lambda badident=badident,name=name:q.consume(outer,review,badident,sha,q.digest(outer),limits),'candidate/job/run identity mismatch')
    # Mutated bytes remain rejected even when the outer and leaf transport hashes are regenerated.
    (evidence/'binaries/qbrain').write_bytes(b'mutated binary')
    altered=root/'altered.zip';altered_raw=make_archive(evidence,altered,ident);altered_outer=review/'altered-outer.zip';wrap(altered,altered_raw,altered_outer)
    expect_failure('consumer-mutated-binary',lambda:q.consume(altered_outer,review,ident,
        hashlib.sha256(altered_raw).hexdigest(),q.digest(altered_outer),limits),'retained binary bytes mutated')
    # Verify the public consumer CLI returns a failing process status as well.
    ident_file=root/'identity.json';q.dump(ident_file,ident)
    process=subprocess.run([sys.executable,str(Path(q.__file__)),'consume','--outer',str(outer),'--review-root',str(review),
        '--identity',str(ident_file),'--manifest-sha256','0'*64,'--artifact-sha256',q.digest(outer)],capture_output=True,timeout=10)
    check(process.returncode!=0,'consumer CLI failure status');RESULTS.append(dict(name='consumer-nonzero-return',passed=True))


def main():
    with tempfile.TemporaryDirectory(prefix='n49d-tiny-controls-') as tmp:
        root=Path(tmp);source_controls();ancestry_controls();audit_launch_controls();proc_reader_controls();absence_oracle_controls();disappearance_controls();windows_diagnostic_controls(root/'diagnostics');failure_detail_controls(root/'failure-detail');(root/'recorder').mkdir();(root/'package').mkdir();recorder_controls(root/'recorder');package_consumer_controls(root/'package');root_terminal_controls(root/'root-terminal');root_terminal_native_controls(root/'root-native');lifecycle_controls(root/'lifecycle');windows_pinned_member_controls(root/'pinned');failure_detail_retention_controls(root/'failure-detail-retention')
    print(json.dumps(dict(passed=True,python_optimized=sys.flags.optimize>0,controls=RESULTS,
        linux_reader_backend=('stat-adapter' if q._PROC_STAT_CHILD_ADAPTER else 'native-children') if os.name!='nt' else 'not_applicable',
        n49d_package_wrapper_executed=True,generic_package_fixture_seam=True,inherited_packager_executed=False,inherited_packager_reason='unchanged 1152 MiB reserve; native CI only'),sort_keys=True))
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        print(json.dumps(_selftest_failure(e)),file=sys.stderr);sys.exit(1)
