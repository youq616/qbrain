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


def metadata_privacy_check(result, expected):
    labels=('windows-private-job','linux-stat-pidfd-subreaper','linux-children-pidfd-subreaper')
    check(type(result) is dict and type(expected) is str and expected in labels and
          type(result.get('process_backend')) is str and result['process_backend']==expected,
          'metadata backend mismatch')
    remainder=dict(result);del remainder['process_backend']
    check('private-' not in json.dumps(remainder),'metadata error leaked')


def privacy_assertion_controls():
    labels=('windows-private-job','linux-stat-pidfd-subreaper','linux-children-pidfd-subreaper')
    def run(label,result,expected,error=None):
        original=result;before=copy.deepcopy(result);serialized=json.dumps(result)
        nested=result.get('failure_detail') if type(result) is dict else None
        try:metadata_privacy_check(result,expected)
        except ValueError as caught:
            check(error is not None and str(caught)==error,'privacy control wrong failure: '+label)
        else:check(error is None,'privacy control unexpectedly passed: '+label)
        check(result is original and result==before and json.dumps(result)==serialized and
              (type(result) is not dict or result.get('failure_detail') is nested),'privacy input mutated: '+label)
        RESULTS.append(dict(name='privacy-assertion-'+label,passed=True))
    for label in labels:run('clean-'+label,dict(process_backend=label,failure_detail={'complete':False}),label)
    for sentinel in ('private-copy-fault','private-json-fault','windows-private-job'):
        for field in ('failure_detail','cleanup_error','capture_error'):
            result=dict(process_backend=labels[0],failure_detail={'complete':False})
            result[field]={'error':sentinel} if field=='failure_detail' else sentinel
            check(result['process_backend']==labels[0],'privacy leak input backend')
            run(sentinel+'-'+field,result,labels[0],'metadata error leaked')
    run('nested-backend',dict(process_backend=labels[0],failure_detail={'process_backend':labels[0]}),
        labels[0],'metadata error leaked')
    run('private-key',dict(process_backend=labels[0],failure_detail={'private-copy-fault':0}),
        labels[0],'metadata error leaked')
    run('moved-label',dict(failure_detail={'process_backend':labels[0]}),labels[0],'metadata backend mismatch')
    for index,value in enumerate((None,0,False,[],{},'WINDOWS-PRIVATE-JOB','x'+labels[0],labels[0]+'x','other',labels[1])):
        run('wrong-actual-'+str(index),dict(process_backend=value),labels[0],'metadata backend mismatch')
    for index,value in enumerate((None,0,False,[],{},'other',labels[1])):
        run('wrong-expected-'+str(index),dict(process_backend=labels[0]),value,'metadata backend mismatch')
    for index,value in enumerate((None,[],{},'text',1)):
        run('wrong-result-'+str(index),value,labels[0],'metadata backend mismatch')
    class Text(str):pass
    run('actual-string-subclass',dict(process_backend=Text(labels[0])),labels[0],'metadata backend mismatch')
    class Expected(str):
        def __eq__(self,other):raise AssertionError('custom equality reached')
    run('expected-string-subclass',dict(process_backend=labels[0]),Expected(labels[0]),'metadata backend mismatch')
    class Mapping(dict):
        def get(self,*args):raise AssertionError('custom lookup reached')
    run('mapping-subclass',Mapping(process_backend=labels[0]),labels[0],'metadata backend mismatch')


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
             ('show','-s','--format=%P',guard.CORRECTION_PARENT):guard.PREPARATION_PARENT,
             ('rev-parse',guard.PREPARATION_PARENT+'^{tree}'):guard.PREPARATION_PARENT_TREE,
             ('show','-s','--format=%P',guard.PREPARATION_PARENT):guard.LOCALIZATION_PARENT,
             ('rev-parse',guard.LOCALIZATION_PARENT+'^{tree}'):guard.LOCALIZATION_PARENT_TREE,
             ('show','-s','--format=%P',guard.LOCALIZATION_PARENT):guard.RETAINED_CORRECTION_PARENT,
             ('rev-parse',guard.RETAINED_CORRECTION_PARENT+'^{tree}'):guard.RETAINED_CORRECTION_PARENT_TREE,
             ('show','-s','--format=%P',guard.RETAINED_CORRECTION_PARENT):guard.SHAPE_PARENT,
             ('rev-parse',guard.SHAPE_PARENT+'^{tree}'):guard.SHAPE_PARENT_TREE,
             ('show','-s','--format=%P',guard.SHAPE_PARENT):guard.PROGRESS_PARENT,
             ('rev-parse',guard.PROGRESS_PARENT+'^{tree}'):guard.PROGRESS_PARENT_TREE,
             ('show','-s','--format=%P',guard.PROGRESS_PARENT):guard.CATCH_PARENT,
             ('rev-parse',guard.CATCH_PARENT+'^{tree}'):guard.CATCH_PARENT_TREE,
             ('show','-s','--format=%P',guard.CATCH_PARENT):guard.OBSERVABILITY_PARENT,
             ('rev-parse',guard.OBSERVABILITY_PARENT+'^{tree}'):guard.OBSERVABILITY_PARENT_TREE,
             ('show','-s','--format=%P',guard.OBSERVABILITY_PARENT):guard.ARRAY_PARENT,
             ('rev-parse',guard.ARRAY_PARENT+'^{tree}'):guard.ARRAY_PARENT_TREE,
             ('show','-s','--format=%P',guard.ARRAY_PARENT):guard.ARGUMENT_PARENT,
             ('rev-parse',guard.ARGUMENT_PARENT+'^{tree}'):guard.ARGUMENT_PARENT_TREE,
             ('show','-s','--format=%P',guard.ARGUMENT_PARENT):guard.STAT_PARENT,
             ('rev-parse',guard.STAT_PARENT+'^{tree}'):guard.STAT_PARENT_TREE,
             ('show','-s','--format=%P',guard.STAT_PARENT):guard.MARKER_PARENT,
             ('rev-parse',guard.MARKER_PARENT+'^{tree}'):guard.MARKER_PARENT_TREE,
             ('show','-s','--format=%P',guard.MARKER_PARENT):guard.EVIDENCE_PARENT,
             ('rev-parse',guard.EVIDENCE_PARENT+'^{tree}'):guard.EVIDENCE_PARENT_TREE,
             ('show','-s','--format=%P',guard.EVIDENCE_PARENT):guard.FIXTURE_PARENT,
             ('rev-parse',guard.FIXTURE_PARENT+'^{tree}'):guard.FIXTURE_PARENT_TREE,
             ('show','-s','--format=%P',guard.FIXTURE_PARENT):guard.PHASE_PARENT,
             ('rev-parse',guard.PHASE_PARENT+'^{tree}'):guard.PHASE_PARENT_TREE,
             ('show','-s','--format=%P',guard.PHASE_PARENT):guard.PRE_PHASE_PARENT,
             ('rev-parse',guard.PRE_PHASE_PARENT+'^{tree}'):guard.PRE_PHASE_PARENT_TREE,
             ('show','-s','--format=%P',guard.PRE_PHASE_PARENT):guard.LAST_CORRECTION_PARENT,
             ('rev-parse',guard.LAST_CORRECTION_PARENT+'^{tree}'):guard.LAST_CORRECTION_PARENT_TREE,
             ('show','-s','--format=%P',guard.LAST_CORRECTION_PARENT):guard.PRIOR_CORRECTION_PARENT,
             ('rev-parse',guard.PRIOR_CORRECTION_PARENT+'^{tree}'):guard.PRIOR_CORRECTION_PARENT_TREE,
             ('show','-s','--format=%P',guard.PRIOR_CORRECTION_PARENT):guard.INTERMEDIATE_PARENT,
             ('rev-parse',guard.INTERMEDIATE_PARENT+'^{tree}'):guard.INTERMEDIATE_PARENT_TREE,
             ('show','-s','--format=%P',guard.INTERMEDIATE_PARENT):guard.PREVIOUS_PARENT,
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
        check(len(calls)==(47 if precommit else 48),'unexpected ancestry query count')
        return result
    def fixed_pins():
        actual=[(guard.CORRECTION_PARENT,guard.CORRECTION_PARENT_TREE),
                (guard.PREPARATION_PARENT,guard.PREPARATION_PARENT_TREE),
                (guard.LOCALIZATION_PARENT,guard.LOCALIZATION_PARENT_TREE),
                (guard.RETAINED_CORRECTION_PARENT,guard.RETAINED_CORRECTION_PARENT_TREE),
                (guard.SHAPE_PARENT,guard.SHAPE_PARENT_TREE),
                (guard.PROGRESS_PARENT,guard.PROGRESS_PARENT_TREE),
                (guard.CATCH_PARENT,guard.CATCH_PARENT_TREE),
                (guard.OBSERVABILITY_PARENT,guard.OBSERVABILITY_PARENT_TREE),
                (guard.ARRAY_PARENT,guard.ARRAY_PARENT_TREE),
                (guard.ARGUMENT_PARENT,guard.ARGUMENT_PARENT_TREE),
                (guard.STAT_PARENT,guard.STAT_PARENT_TREE),
                (guard.MARKER_PARENT,guard.MARKER_PARENT_TREE),
                (guard.EVIDENCE_PARENT,guard.EVIDENCE_PARENT_TREE),
                (guard.FIXTURE_PARENT,guard.FIXTURE_PARENT_TREE),
                (guard.PHASE_PARENT,guard.PHASE_PARENT_TREE),
                (guard.PRE_PHASE_PARENT,guard.PRE_PHASE_PARENT_TREE),
                (guard.LAST_CORRECTION_PARENT,guard.LAST_CORRECTION_PARENT_TREE),
                (guard.PRIOR_CORRECTION_PARENT,guard.PRIOR_CORRECTION_PARENT_TREE),
                (guard.INTERMEDIATE_PARENT,guard.INTERMEDIATE_PARENT_TREE),
                (guard.PREVIOUS_PARENT,guard.PREVIOUS_PARENT_TREE),
                (guard.EARLIER_PARENT,guard.EARLIER_PARENT_TREE),
                (guard.ORIGINAL_PARENT,guard.ORIGINAL_PARENT_TREE),(guard.BASE,guard.BASE_TREE)]
        expected=[('2cb355812df2af5c77106056152d3d93e86784b9','cc8b95364155000a2d6f83a2a6cda7b7b8e484f4'),
                  ('d8c2e46f2e2d6b849904583ab4e430350e8c7fa5','dccb1da35da397a0bd8caa721f8096bc432a09fb'),
                  ('7f27168b01f020e8ddc38d4d5977e3ad354ff566','9060bfa1da3ea05aac0d9ff932ed4c903877caa0'),
                  ('d62321640f5074d0c4c6a735b72b4ae21d6d880b','a41a3adceca7289d0bf2999e2e291796a4043833'),
                  ('fb589a6991f57922db316be98a9aa70bdd4db182','52cf8c5f5399a814f04046c081651ba21ed64764'),
                  ('9ce038df175e64a15a7fdee5858510deb4ddac22','09b6a3f38de5976ff65b8be20460efb301e071e5'),
                  ('c84209ccda96f6374894ebce602d071a41e8aec7','0c91c6dc41ce552292e2922d31ca1edbdd6fee51'),
                  ('8da585fbb350780ead3f093b7dec1c328635e32d','4979ec12344e2985d3920d9dbc64d780450da23e'),
                  ('5f5538d5df89159af3e23429a14a311593af7a4c','c16a2de69289f525288c196afc54c7e465801b07'),
                  ('4a433a903975123585b501cc2a6d3a0a58af9a00','788470dc3aeb96ea9afb065815dec6aa31e9b73f'),
                  ('1a28a144c977c40eee92866d2387a2d98adf3cfa','dc9ee5c2a6752d03e442bd11b4fac618417d1488'),
                  ('ce0766d32ddab2d47beb5dfc75c32c38e4ce43ea','e8e82d07e41585e34c0493b63baa8e8fe838d251'),
                  ('610bf498d4b2b5cd45921d5f53d71bfacb5b3f4d','181ef0d4e867b669c8a9429f7f9f56ad5a6fdc72'),
                  ('7d6aa8dbb62b7d44af9629b5bdbd7ffcd54d6185','d8c451ae5421abcf709f5f709c243f3f97934a05'),
                  ('652849684fbb0758b861812dd13e68a0df819578','417b0f186646d6dd7906ed75a5d331cb64937333'),
                  ('a6c01c581eb77887ae33090b543a98bbd67477af','fe1250f174afa4eeb8241f4262d855487e1a6045'),
                  ('a62e648744ddeb23ca20b05421c70aab5c70ea95','194cbd3f6d486e72f10472234a907e3bf5c1f97e'),
                  ('f64b2eff3c46324f5a8d100748ec6b92ccd4981d','a37b9b96b50b876f0036ee15cebc6002a242775d'),
                  ('e44de25cc16f3a4154822d3147f20b21b1c69136','2de51cfb37eb7199a1acc5a1a6cd31bb9563efd3'),
                  ('adf7adfe5ef7cb2a7686161fffd8f00d1d6547c2','3f166c44c1267c64b1f890617e7062117a9790f5'),
                  ('ff61dde8150f30eec699a4e5c01554175ff37f98','d8895a9792cab41cc15d71f7c248fef794829787'),
                  ('0c99f74436682500caeaf0bf68a7bc42310d6a50','d91c1f258a704eed9fe899c1193df8d080ff2f56'),
                  ('cfe1ef58e244b51092c2248804b663b6c28913d7','75b69ad389630e51528ddb5536a27255203470df')]
        check(actual==expected and len({commit for commit,_ in actual})==23,'fixed twenty-four-commit lineage pins')
        for label,key,value,boundary in [
            ('tree',('rev-parse',guard.STAT_PARENT+'^{tree}'),'3'*40,'stat parent tree'),
            ('parent',('show','-s','--format=%P',guard.STAT_PARENT),'3'*40,'stat parent ancestry'),
            ('multi',('show','-s','--format=%P',guard.STAT_PARENT),guard.BASE+' '+'3'*40,'stat parent ancestry'),
            ('empty',('show','-s','--format=%P',guard.STAT_PARENT),'','stat parent ancestry')]:
            expect_failure('retained-stat-'+label,lambda key=key,value=value:run({key:value}),boundary,record=False)
        tip={('rev-parse','HEAD'):guard.STAT_PARENT,('rev-parse','HEAD^{tree}'):guard.STAT_PARENT_TREE}
        expect_failure('retained-stat-candidate',lambda:run(tip,commit=guard.STAT_PARENT,expected_tree=guard.STAT_PARENT_TREE),'candidate pin mismatch',record=False)
        expect_failure('retained-stat-precommit',lambda:run(tip,True),'precommit requires exact correction parent/tree',record=False)
        for key in [('rev-parse',guard.STAT_PARENT+'^{tree}'),('show','-s','--format=%P',guard.STAT_PARENT)]:
            try:run({key:None})
            except subprocess.CalledProcessError as error:
                check(error.returncode==128 and error.cmd==['git',*key],'retained stat missing object boundary')
            else:raise ValueError('missing retained stat metadata passed')
        for label,key,value,boundary in [
            ('tree',('rev-parse',guard.ARGUMENT_PARENT+'^{tree}'),'3'*40,'argument parent tree'),
            ('parent',('show','-s','--format=%P',guard.ARGUMENT_PARENT),'3'*40,'argument parent ancestry'),
            ('multi',('show','-s','--format=%P',guard.ARGUMENT_PARENT),guard.BASE+' '+'3'*40,'argument parent ancestry'),
            ('empty',('show','-s','--format=%P',guard.ARGUMENT_PARENT),'','argument parent ancestry')]:
            expect_failure('retained-argument-'+label,lambda key=key,value=value:run({key:value}),boundary,record=False)
        tip={('rev-parse','HEAD'):guard.ARGUMENT_PARENT,('rev-parse','HEAD^{tree}'):guard.ARGUMENT_PARENT_TREE}
        expect_failure('retained-argument-candidate',lambda:run(tip,commit=guard.ARGUMENT_PARENT,expected_tree=guard.ARGUMENT_PARENT_TREE),'candidate pin mismatch',record=False)
        expect_failure('retained-argument-precommit',lambda:run(tip,True),'precommit requires exact correction parent/tree',record=False)
        for key in [('rev-parse',guard.ARGUMENT_PARENT+'^{tree}'),('show','-s','--format=%P',guard.ARGUMENT_PARENT)]:
            try:run({key:None})
            except subprocess.CalledProcessError as error:
                check(error.returncode==128 and error.cmd==['git',*key],'retained argument missing object boundary')
            else:raise ValueError('missing retained argument metadata passed')
        for label,key,value,boundary in [
            ('tree',('rev-parse',guard.ARRAY_PARENT+'^{tree}'),'3'*40,'array parent tree'),
            ('parent',('show','-s','--format=%P',guard.ARRAY_PARENT),'3'*40,'array parent ancestry'),
            ('multi',('show','-s','--format=%P',guard.ARRAY_PARENT),guard.BASE+' '+'3'*40,'array parent ancestry'),
            ('empty',('show','-s','--format=%P',guard.ARRAY_PARENT),'','array parent ancestry')]:
            expect_failure('retained-array-'+label,lambda key=key,value=value:run({key:value}),boundary,record=False)
        tip={('rev-parse','HEAD'):guard.ARRAY_PARENT,('rev-parse','HEAD^{tree}'):guard.ARRAY_PARENT_TREE}
        expect_failure('retained-array-candidate',lambda:run(tip,commit=guard.ARRAY_PARENT,expected_tree=guard.ARRAY_PARENT_TREE),'candidate pin mismatch',record=False)
        expect_failure('retained-array-precommit',lambda:run(tip,True),'precommit requires exact correction parent/tree',record=False)
        for key in [('rev-parse',guard.ARRAY_PARENT+'^{tree}'),('show','-s','--format=%P',guard.ARRAY_PARENT)]:
            try:run({key:None})
            except subprocess.CalledProcessError as error:
                check(error.returncode==128 and error.cmd==['git',*key],'retained array missing object boundary')
            else:raise ValueError('missing retained array metadata passed')
        for label,key,value,boundary in [
            ('tree',('rev-parse',guard.OBSERVABILITY_PARENT+'^{tree}'),'3'*40,'observability parent tree'),
            ('parent',('show','-s','--format=%P',guard.OBSERVABILITY_PARENT),'3'*40,'observability parent ancestry'),
            ('multi',('show','-s','--format=%P',guard.OBSERVABILITY_PARENT),guard.BASE+' '+'3'*40,'observability parent ancestry'),
            ('empty',('show','-s','--format=%P',guard.OBSERVABILITY_PARENT),'','observability parent ancestry')]:
            expect_failure('retained-observability-'+label,lambda key=key,value=value:run({key:value}),boundary,record=False)
        tip={('rev-parse','HEAD'):guard.OBSERVABILITY_PARENT,('rev-parse','HEAD^{tree}'):guard.OBSERVABILITY_PARENT_TREE}
        expect_failure('retained-observability-candidate',lambda:run(tip,commit=guard.OBSERVABILITY_PARENT,expected_tree=guard.OBSERVABILITY_PARENT_TREE),'candidate pin mismatch',record=False)
        expect_failure('retained-observability-precommit',lambda:run(tip,True),'precommit requires exact correction parent/tree',record=False)
        for key in [('rev-parse',guard.OBSERVABILITY_PARENT+'^{tree}'),('show','-s','--format=%P',guard.OBSERVABILITY_PARENT)]:
            try:run({key:None})
            except subprocess.CalledProcessError as error:
                check(error.returncode==128 and error.cmd==['git',*key],'retained observability missing object boundary')
            else:raise ValueError('missing retained observability metadata passed')
        for label,key,value,boundary in [
            ('tree',('rev-parse',guard.CATCH_PARENT+'^{tree}'),'3'*40,'catch parent tree'),
            ('parent',('show','-s','--format=%P',guard.CATCH_PARENT),'3'*40,'catch parent ancestry'),
            ('multi',('show','-s','--format=%P',guard.CATCH_PARENT),guard.BASE+' '+'3'*40,'catch parent ancestry'),
            ('empty',('show','-s','--format=%P',guard.CATCH_PARENT),'','catch parent ancestry')]:
            expect_failure('retained-catch-'+label,lambda key=key,value=value:run({key:value}),boundary,record=False)
        tip={('rev-parse','HEAD'):guard.CATCH_PARENT,('rev-parse','HEAD^{tree}'):guard.CATCH_PARENT_TREE}
        expect_failure('retained-catch-candidate',lambda:run(tip,commit=guard.CATCH_PARENT,expected_tree=guard.CATCH_PARENT_TREE),'candidate pin mismatch',record=False)
        expect_failure('retained-catch-precommit',lambda:run(tip,True),'precommit requires exact correction parent/tree',record=False)
        for key in [('rev-parse',guard.CATCH_PARENT+'^{tree}'),('show','-s','--format=%P',guard.CATCH_PARENT)]:
            try:run({key:None})
            except subprocess.CalledProcessError as error:
                check(error.returncode==128 and error.cmd==['git',*key],'retained catch missing object boundary')
            else:raise ValueError('missing retained catch metadata passed')
        for label,key,value,boundary in [
            ('tree',('rev-parse',guard.PROGRESS_PARENT+'^{tree}'),'3'*40,'progress parent tree'),
            ('parent',('show','-s','--format=%P',guard.PROGRESS_PARENT),'3'*40,'progress parent ancestry'),
            ('multi',('show','-s','--format=%P',guard.PROGRESS_PARENT),guard.BASE+' '+'3'*40,'progress parent ancestry'),
            ('empty',('show','-s','--format=%P',guard.PROGRESS_PARENT),'','progress parent ancestry')]:
            expect_failure('retained-progress-'+label,lambda key=key,value=value:run({key:value}),boundary,record=False)
        tip={('rev-parse','HEAD'):guard.PROGRESS_PARENT,('rev-parse','HEAD^{tree}'):guard.PROGRESS_PARENT_TREE}
        expect_failure('retained-progress-candidate',lambda:run(tip,commit=guard.PROGRESS_PARENT,expected_tree=guard.PROGRESS_PARENT_TREE),'candidate pin mismatch',record=False)
        expect_failure('retained-progress-precommit',lambda:run(tip,True),'precommit requires exact correction parent/tree',record=False)
        for key in [('rev-parse',guard.PROGRESS_PARENT+'^{tree}'),('show','-s','--format=%P',guard.PROGRESS_PARENT)]:
            try:run({key:None})
            except subprocess.CalledProcessError as error:
                check(error.returncode==128 and error.cmd==['git',*key],'retained progress missing object boundary')
            else:raise ValueError('missing retained progress metadata passed')
        for label,key,value,boundary in [
            ('tree',('rev-parse',guard.SHAPE_PARENT+'^{tree}'),'3'*40,'shape parent tree'),
            ('parent',('show','-s','--format=%P',guard.SHAPE_PARENT),'3'*40,'shape parent ancestry'),
            ('multi',('show','-s','--format=%P',guard.SHAPE_PARENT),guard.BASE+' '+'3'*40,'shape parent ancestry'),
            ('empty',('show','-s','--format=%P',guard.SHAPE_PARENT),'','shape parent ancestry')]:
            expect_failure('retained-shape-'+label,lambda key=key,value=value:run({key:value}),boundary,record=False)
        tip={('rev-parse','HEAD'):guard.SHAPE_PARENT,('rev-parse','HEAD^{tree}'):guard.SHAPE_PARENT_TREE}
        expect_failure('retained-shape-candidate',lambda:run(tip,commit=guard.SHAPE_PARENT,expected_tree=guard.SHAPE_PARENT_TREE),'candidate pin mismatch',record=False)
        expect_failure('retained-shape-precommit',lambda:run(tip,True),'precommit requires exact correction parent/tree',record=False)
        for key in [('rev-parse',guard.SHAPE_PARENT+'^{tree}'),('show','-s','--format=%P',guard.SHAPE_PARENT)]:
            try:run({key:None})
            except subprocess.CalledProcessError as error:
                check(error.returncode==128 and error.cmd==['git',*key],'retained shape missing object boundary')
            else:raise ValueError('missing retained shape metadata passed')
        for label,key,value,boundary in [
            ('tree',('rev-parse',guard.RETAINED_CORRECTION_PARENT+'^{tree}'),'3'*40,'retained correction parent tree'),
            ('parent',('show','-s','--format=%P',guard.RETAINED_CORRECTION_PARENT),'3'*40,'retained correction parent ancestry'),
            ('multi',('show','-s','--format=%P',guard.RETAINED_CORRECTION_PARENT),guard.BASE+' '+'3'*40,'retained correction parent ancestry'),
            ('empty',('show','-s','--format=%P',guard.RETAINED_CORRECTION_PARENT),'','retained correction parent ancestry')]:
            expect_failure('retained-correction-'+label,lambda key=key,value=value:run({key:value}),boundary,record=False)
        tip={('rev-parse','HEAD'):guard.RETAINED_CORRECTION_PARENT,('rev-parse','HEAD^{tree}'):guard.RETAINED_CORRECTION_PARENT_TREE}
        expect_failure('retained-correction-candidate',lambda:run(tip,commit=guard.RETAINED_CORRECTION_PARENT,expected_tree=guard.RETAINED_CORRECTION_PARENT_TREE),'candidate pin mismatch',record=False)
        expect_failure('retained-correction-precommit',lambda:run(tip,True),'precommit requires exact correction parent/tree',record=False)
        for key in [('rev-parse',guard.RETAINED_CORRECTION_PARENT+'^{tree}'),('show','-s','--format=%P',guard.RETAINED_CORRECTION_PARENT)]:
            try:run({key:None})
            except subprocess.CalledProcessError as error:
                check(error.returncode==128 and error.cmd==['git',*key],'retained correction missing object boundary')
            else:raise ValueError('missing retained correction metadata passed')
        for label,key,value,boundary in [
            ('tree',('rev-parse',guard.LOCALIZATION_PARENT+'^{tree}'),'3'*40,'localization parent tree'),
            ('parent',('show','-s','--format=%P',guard.LOCALIZATION_PARENT),'3'*40,'localization parent ancestry'),
            ('multi',('show','-s','--format=%P',guard.LOCALIZATION_PARENT),guard.BASE+' '+'3'*40,'localization parent ancestry'),
            ('empty',('show','-s','--format=%P',guard.LOCALIZATION_PARENT),'','localization parent ancestry')]:
            expect_failure('retained-localization-'+label,lambda key=key,value=value:run({key:value}),boundary,record=False)
        tip={('rev-parse','HEAD'):guard.LOCALIZATION_PARENT,('rev-parse','HEAD^{tree}'):guard.LOCALIZATION_PARENT_TREE}
        expect_failure('retained-localization-candidate',lambda:run(tip,commit=guard.LOCALIZATION_PARENT,expected_tree=guard.LOCALIZATION_PARENT_TREE),'candidate pin mismatch',record=False)
        expect_failure('retained-localization-precommit',lambda:run(tip,True),'precommit requires exact correction parent/tree',record=False)
        for key in [('rev-parse',guard.LOCALIZATION_PARENT+'^{tree}'),('show','-s','--format=%P',guard.LOCALIZATION_PARENT)]:
            try:run({key:None})
            except subprocess.CalledProcessError as error:
                check(error.returncode==128 and error.cmd==['git',*key],'localization missing object boundary')
            else:raise ValueError('missing localization metadata passed')
        for label,key,value,boundary in [
            ('tree',('rev-parse',guard.PREPARATION_PARENT+'^{tree}'),'3'*40,'preparation parent tree'),
            ('parent',('show','-s','--format=%P',guard.PREPARATION_PARENT),'3'*40,'preparation parent ancestry'),
            ('multi',('show','-s','--format=%P',guard.PREPARATION_PARENT),guard.BASE+' '+'3'*40,'preparation parent ancestry'),
            ('empty',('show','-s','--format=%P',guard.PREPARATION_PARENT),'','preparation parent ancestry')]:
            expect_failure('retained-preparation-'+label,lambda key=key,value=value:run({key:value}),boundary,record=False)
        tip={('rev-parse','HEAD'):guard.PREPARATION_PARENT,('rev-parse','HEAD^{tree}'):guard.PREPARATION_PARENT_TREE}
        expect_failure('retained-preparation-candidate',lambda:run(tip,commit=guard.PREPARATION_PARENT,expected_tree=guard.PREPARATION_PARENT_TREE),'candidate pin mismatch',record=False)
        expect_failure('retained-preparation-precommit',lambda:run(tip,True),'precommit requires exact correction parent/tree',record=False)
        for key in [('rev-parse',guard.PREPARATION_PARENT+'^{tree}'),('show','-s','--format=%P',guard.PREPARATION_PARENT)]:
            try:run({key:None})
            except subprocess.CalledProcessError as error:
                check(error.returncode==128 and error.cmd==['git',*key],'retained preparation missing object boundary')
            else:raise ValueError('missing retained preparation metadata passed')
        local_preparation_candidate='2d3cf0dfafd03e0e4bbd302c995d523b3fcee04b'
        for parent in (guard.PREPARATION_PARENT,local_preparation_candidate):
            expect_failure('masked-getter-parent',lambda parent=parent:run({('show','-s','--format=%P',head):parent}),'candidate parent mismatch',record=False)
        tip={('rev-parse','HEAD'):local_preparation_candidate,('rev-parse','HEAD^{tree}'):guard.CORRECTION_PARENT_TREE,
             ('show','-s','--format=%P',local_preparation_candidate):guard.PREPARATION_PARENT}
        expect_failure('local-preparation-precommit',lambda:run(tip,True),'precommit requires exact correction parent/tree',record=False)
        expect_failure('local-preparation-candidate',lambda:run(tip,commit=local_preparation_candidate,expected_tree=guard.CORRECTION_PARENT_TREE),'candidate parent mismatch',record=False)
        local_published_tree='9a9591626169ac4d4234e22957d1ea13a58a8d5f'
        for parent in (guard.LOCALIZATION_PARENT,local_published_tree):
            expect_failure('prepared-text-parent',lambda parent=parent:run({('show','-s','--format=%P',head):parent}),'candidate parent mismatch',record=False)
        tip={('rev-parse','HEAD'):local_published_tree,('rev-parse','HEAD^{tree}'):guard.PREPARATION_PARENT_TREE,
             ('show','-s','--format=%P',local_published_tree):guard.LOCALIZATION_PARENT}
        expect_failure('published-tree-precommit',lambda:run(tip,True),'precommit requires exact correction parent/tree',record=False)
        expect_failure('published-tree-candidate',lambda:run(tip,commit=local_published_tree,expected_tree=guard.PREPARATION_PARENT_TREE),'candidate parent mismatch',record=False)
        local_same_tree='77da2ff12a26fc403ba4eeabcc84166d0baebc09'
        for label,parent in [('retained-correction',guard.RETAINED_CORRECTION_PARENT),('local-same-tree',local_same_tree)]:
            expect_failure('candidate-reject-'+label+'-parent',lambda parent=parent:run({('show','-s','--format=%P',head):parent}),'candidate parent mismatch',record=False)
        tip={('rev-parse','HEAD'):local_same_tree,('rev-parse','HEAD^{tree}'):guard.LOCALIZATION_PARENT_TREE,
             ('show','-s','--format=%P',local_same_tree):guard.RETAINED_CORRECTION_PARENT}
        expect_failure('local-same-tree-precommit',lambda:run(tip,True),'precommit requires exact correction parent/tree',record=False)
        expect_failure('local-same-tree-candidate',lambda:run(tip,commit=local_same_tree,expected_tree=guard.LOCALIZATION_PARENT_TREE),'candidate parent mismatch',record=False)
    control('ancestry-fixed-twenty-one-commit-pins',fixed_pins)
    control('ancestry-exact-correction-chain',lambda:check(run()==(head,tree,guard.CORRECTION_PARENT,guard.CORRECTION_PARENT_TREE),'committed parent fields'))
    pre={('rev-parse','HEAD'):guard.CORRECTION_PARENT,('rev-parse','HEAD^{tree}'):guard.CORRECTION_PARENT_TREE}
    control('ancestry-precommit-exact-anchor',lambda:check(run(pre,True)==(guard.CORRECTION_PARENT,guard.CORRECTION_PARENT_TREE,guard.PREPARATION_PARENT,guard.PREPARATION_PARENT_TREE),'precommit actual parent fields'))
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
           ('previous-anchor-parent',('show','-s','--format=%P',head),guard.FIXTURE_PARENT,'candidate parent'),
           ('wrong-anchor-tree',('rev-parse',guard.CORRECTION_PARENT+'^{tree}'),'3'*40,'correction parent tree'),
           ('wrong-anchor-parent',('show','-s','--format=%P',guard.CORRECTION_PARENT),'3'*40,'correction parent ancestry'),
           ('multiple-anchor-parents',('show','-s','--format=%P',guard.CORRECTION_PARENT),guard.BASE+' '+'3'*40,'correction parent ancestry'),
           ('missing-anchor-parent',('show','-s','--format=%P',guard.CORRECTION_PARENT),'','correction parent ancestry'),
           ('wrong-fixture-tree',('rev-parse',guard.FIXTURE_PARENT+'^{tree}'),'3'*40,'fixture parent tree'),
           ('wrong-fixture-parent',('show','-s','--format=%P',guard.FIXTURE_PARENT),'3'*40,'fixture parent ancestry'),
           ('multiple-fixture-parents',('show','-s','--format=%P',guard.FIXTURE_PARENT),guard.BASE+' '+'3'*40,'fixture parent ancestry'),
           ('missing-fixture-parent',('show','-s','--format=%P',guard.FIXTURE_PARENT),'','fixture parent ancestry'),
           ('wrong-phase-tree',('rev-parse',guard.PHASE_PARENT+'^{tree}'),'3'*40,'phase parent tree'),
           ('wrong-phase-parent',('show','-s','--format=%P',guard.PHASE_PARENT),'3'*40,'phase parent ancestry'),
           ('multiple-phase-parents',('show','-s','--format=%P',guard.PHASE_PARENT),guard.BASE+' '+'3'*40,'phase parent ancestry'),
           ('missing-phase-parent',('show','-s','--format=%P',guard.PHASE_PARENT),'','phase parent ancestry'),
           ('wrong-pre-phase-tree',('rev-parse',guard.PRE_PHASE_PARENT+'^{tree}'),'3'*40,'pre-phase parent tree'),
           ('wrong-pre-phase-parent',('show','-s','--format=%P',guard.PRE_PHASE_PARENT),'3'*40,'pre-phase parent ancestry'),
           ('multiple-pre-phase-parent',('show','-s','--format=%P',guard.PRE_PHASE_PARENT),guard.BASE+' '+'3'*40,'pre-phase parent ancestry'),
           ('wrong-last-correction-tree',('rev-parse',guard.LAST_CORRECTION_PARENT+'^{tree}'),'3'*40,'last correction parent tree'),
           ('wrong-last-correction-parent',('show','-s','--format=%P',guard.LAST_CORRECTION_PARENT),'3'*40,'last correction parent ancestry'),
           ('multiple-last-correction-parents',('show','-s','--format=%P',guard.LAST_CORRECTION_PARENT),guard.BASE+' '+'3'*40,'last correction parent ancestry'),
           ('wrong-prior-correction-tree',('rev-parse',guard.PRIOR_CORRECTION_PARENT+'^{tree}'),'3'*40,'prior correction parent tree'),
           ('wrong-prior-correction-parent',('show','-s','--format=%P',guard.PRIOR_CORRECTION_PARENT),'3'*40,'prior correction parent ancestry'),
           ('multiple-prior-correction-parents',('show','-s','--format=%P',guard.PRIOR_CORRECTION_PARENT),guard.BASE+' '+'3'*40,'prior correction parent ancestry'),
           ('sibling-candidate-parent',('show','-s','--format=%P',head),'199f50694e8e020932c99e821d0d3c67586582c5','candidate parent'),
           ('wrong-intermediate-tree',('rev-parse',guard.INTERMEDIATE_PARENT+'^{tree}'),'3'*40,'intermediate parent tree'),
           ('wrong-intermediate-parent',('show','-s','--format=%P',guard.INTERMEDIATE_PARENT),'3'*40,'intermediate parent ancestry'),
           ('multiple-intermediate-parents',('show','-s','--format=%P',guard.INTERMEDIATE_PARENT),guard.BASE+' '+'3'*40,'intermediate parent ancestry'),
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
                          ('same-tree-sibling',{('rev-parse','HEAD'):'199f50694e8e020932c99e821d0d3c67586582c5'}),('wrong-tree',{('rev-parse','HEAD^{tree}'):'3'*40}),('other-tip',{('rev-parse','HEAD'):'3'*40})]:
        expect_failure('ancestry-precommit-'+label,lambda changes=changes:run(pre|changes,True),'precommit requires exact correction parent/tree')
    expect_failure('ancestry-anchor-is-not-candidate',lambda:run(pre,commit=guard.CORRECTION_PARENT,expected_tree=guard.CORRECTION_PARENT_TREE),'candidate pin mismatch')
    for label,anchor,anchor_tree in [('fixture',guard.FIXTURE_PARENT,guard.FIXTURE_PARENT_TREE),('phase',guard.PHASE_PARENT,guard.PHASE_PARENT_TREE),('pre-phase',guard.PRE_PHASE_PARENT,guard.PRE_PHASE_PARENT_TREE),('last-correction',guard.LAST_CORRECTION_PARENT,guard.LAST_CORRECTION_PARENT_TREE),('prior-correction',guard.PRIOR_CORRECTION_PARENT,guard.PRIOR_CORRECTION_PARENT_TREE),('intermediate',guard.INTERMEDIATE_PARENT,guard.INTERMEDIATE_PARENT_TREE),('previous',guard.PREVIOUS_PARENT,guard.PREVIOUS_PARENT_TREE),('earlier',guard.EARLIER_PARENT,guard.EARLIER_PARENT_TREE),('original',guard.ORIGINAL_PARENT,guard.ORIGINAL_PARENT_TREE),('base',guard.BASE,guard.BASE_TREE)]:
        tip={('rev-parse','HEAD'):anchor,('rev-parse','HEAD^{tree}'):anchor_tree}
        expect_failure('ancestry-'+label+'-is-not-candidate',lambda tip=tip,anchor=anchor,anchor_tree=anchor_tree:run(tip,commit=anchor,expected_tree=anchor_tree),'candidate pin mismatch')
        expect_failure('ancestry-precommit-reject-'+label,lambda tip=tip:run(tip,True),'precommit requires exact correction parent/tree')
    for label,key in [('missing-fixture-object',('rev-parse',guard.FIXTURE_PARENT+'^{tree}')),('missing-fixture-parent-metadata',('show','-s','--format=%P',guard.FIXTURE_PARENT)),('missing-phase-object',('rev-parse',guard.PHASE_PARENT+'^{tree}')),('missing-phase-parent-metadata',('show','-s','--format=%P',guard.PHASE_PARENT)),('missing-pre-phase-object',('rev-parse',guard.PRE_PHASE_PARENT+'^{tree}')),('missing-pre-phase-parent',('show','-s','--format=%P',guard.PRE_PHASE_PARENT)),('missing-last-correction-object',('rev-parse',guard.LAST_CORRECTION_PARENT+'^{tree}')),('missing-last-correction-parent',('show','-s','--format=%P',guard.LAST_CORRECTION_PARENT)),('missing-prior-correction-object',('rev-parse',guard.PRIOR_CORRECTION_PARENT+'^{tree}')),('missing-prior-correction-parent',('show','-s','--format=%P',guard.PRIOR_CORRECTION_PARENT)),('missing-intermediate-object',('rev-parse',guard.INTERMEDIATE_PARENT+'^{tree}')),('missing-intermediate-parent',('show','-s','--format=%P',guard.INTERMEDIATE_PARENT)),('missing-depth-base',('rev-parse',guard.BASE+'^{tree}')),('missing-anchor-object',('rev-parse',guard.CORRECTION_PARENT+'^{tree}')),('missing-anchor-parent-metadata',('show','-s','--format=%P',guard.CORRECTION_PARENT)),('missing-previous-object',('rev-parse',guard.PREVIOUS_PARENT+'^{tree}')),('missing-previous-parent-metadata',('show','-s','--format=%P',guard.PREVIOUS_PARENT)),('missing-earlier-object',('rev-parse',guard.EARLIER_PARENT+'^{tree}')),('missing-earlier-parent-metadata',('show','-s','--format=%P',guard.EARLIER_PARENT)),('missing-original-object',('rev-parse',guard.ORIGINAL_PARENT+'^{tree}')),('missing-original-parent-metadata',('show','-s','--format=%P',guard.ORIGINAL_PARENT))]:
        try:run({key:None})
        except subprocess.CalledProcessError as error:
            check(error.returncode==128 and error.cmd==['git',*key],'missing object boundary');RESULTS.append(dict(name='ancestry-'+label,passed=True))
        else:raise ValueError('missing ancestry object passed')
    evidence_row=dict(name='ancestry-retained-evidence-edge',passed=False,trace=[]);RESULTS.append(evidence_row)
    for label,key,value,boundary in [
        ('tree',('rev-parse',guard.EVIDENCE_PARENT+'^{tree}'),'3'*40,'evidence parent tree'),
        ('parent',('show','-s','--format=%P',guard.EVIDENCE_PARENT),'3'*40,'evidence parent ancestry'),
        ('multi',('show','-s','--format=%P',guard.EVIDENCE_PARENT),guard.BASE+' '+'3'*40,'evidence parent ancestry'),
        ('empty',('show','-s','--format=%P',guard.EVIDENCE_PARENT),'','evidence parent ancestry')]:
        expect_failure('retained-'+label,lambda key=key,value=value:run({key:value}),boundary,record=False)
        evidence_row['trace'].append(label+'=reject')
    tip={('rev-parse','HEAD'):guard.EVIDENCE_PARENT,('rev-parse','HEAD^{tree}'):guard.EVIDENCE_PARENT_TREE}
    for label,call,boundary in [
        ('candidate',lambda:run(tip,commit=guard.EVIDENCE_PARENT,expected_tree=guard.EVIDENCE_PARENT_TREE),'candidate pin mismatch'),
        ('precommit',lambda:run(tip,True),'precommit requires exact correction parent/tree')]:
        expect_failure('retained-'+label,call,boundary,record=False);evidence_row['trace'].append(label+'=reject')
    for label,key in [('missing-tree',('rev-parse',guard.EVIDENCE_PARENT+'^{tree}')),
                      ('missing-parent',('show','-s','--format=%P',guard.EVIDENCE_PARENT))]:
        try:run({key:None})
        except subprocess.CalledProcessError as error:
            check(error.returncode==128 and error.cmd==['git',*key],'retained evidence missing object boundary')
            evidence_row['trace'].append(label+'=reject')
        else:raise ValueError('missing retained evidence metadata passed')
    evidence_row['passed']=True
    marker_row=dict(name='ancestry-retained-marker-edge',passed=False,trace=[]);RESULTS.append(marker_row)
    for label,key,value,boundary in [
        ('tree',('rev-parse',guard.MARKER_PARENT+'^{tree}'),'3'*40,'marker parent tree'),
        ('parent',('show','-s','--format=%P',guard.MARKER_PARENT),'3'*40,'marker parent ancestry'),
        ('multi',('show','-s','--format=%P',guard.MARKER_PARENT),guard.BASE+' '+'3'*40,'marker parent ancestry'),
        ('empty',('show','-s','--format=%P',guard.MARKER_PARENT),'','marker parent ancestry')]:
        expect_failure('retained-'+label,lambda key=key,value=value:run({key:value}),boundary,record=False)
        marker_row['trace'].append(label+'=reject')
    tip={('rev-parse','HEAD'):guard.MARKER_PARENT,('rev-parse','HEAD^{tree}'):guard.MARKER_PARENT_TREE}
    for label,call,boundary in [
        ('candidate',lambda:run(tip,commit=guard.MARKER_PARENT,expected_tree=guard.MARKER_PARENT_TREE),'candidate pin mismatch'),
        ('precommit',lambda:run(tip,True),'precommit requires exact correction parent/tree')]:
        expect_failure('retained-'+label,call,boundary,record=False);marker_row['trace'].append(label+'=reject')
    for label,key in [('missing-tree',('rev-parse',guard.MARKER_PARENT+'^{tree}')),
                      ('missing-parent',('show','-s','--format=%P',guard.MARKER_PARENT))]:
        try:run({key:None})
        except subprocess.CalledProcessError as error:
            check(error.returncode==128 and error.cmd==['git',*key],'retained marker missing object boundary')
            marker_row['trace'].append(label+'=reject')
        else:raise ValueError('missing retained marker metadata passed')
    marker_row['passed']=True
    parent={p:('100644',guard.blob(('parent '+p).encode())) for p in guard.ALLOW};candidate=dict(parent)
    for path in guard.CORRECTION_PATHS:candidate[path]=('100644',guard.blob(('correction '+path).encode()))
    def correction_scope():
        check(guard.validate_correction(parent,candidate)==sorted(guard.CORRECTION_PATHS),'correction inventory')
        check(guard.CORRECTION_PATHS==frozenset({'.ci/check_n49d_sources.py',
              '.ci/test_n49d_source_contract.py','.github/workflows/n49d-mcp-directory-search.yml'}) and
              len(guard.ALLOW)==18,'three correction/full18 scope')
        for path in ('scripts/build-cl.ps1','scripts/build-tests-cl.ps1','.ci/run_n49d_qualification.py'):
            changed=dict(candidate);changed[path]=('100644','0'*40)
            for complete in (False,True):
                expect_failure('correction-excluded-'+path+'-'+str(complete),
                    lambda changed=changed,complete=complete:guard.validate_correction(parent,changed,complete),
                    'unreviewed correction path',record=False)
    control('correction-exact-four-paths',correction_scope)
    partial=dict(parent);path=sorted(guard.CORRECTION_PATHS)[0];partial[path]=candidate[path]
    control('correction-precommit-subset',lambda:check(guard.validate_correction(parent,partial,False)==[path],'correction subset'))
    expect_failure('correction-missing-final-member',lambda:guard.validate_correction(parent,partial),'required correction path missing')
    for member in guard.CORRECTION_PATHS:
        omitted=dict(candidate);omitted[member]=parent[member]
        expect_failure('correction-missing-'+member,lambda omitted=omitted:guard.validate_correction(parent,omitted),'required correction path missing',record=False)
    for label,changes,removed in [('driver',{'.ci/test_mcp_directory_search.py':('100644','0'*40)},None),('production',{guard.HANDLERS:('100644','0'*40)},None),('documentation',{guard.LEDGER:('100644','0'*40)},None),
                                  ('extra',{'unexpected.txt':('100644','0'*40)},None),('deleted',{},path),('mode',{path:('100755',candidate[path][1])},None)]:
        changed=dict(candidate);changed.update(changes)
        if removed is not None:del changed[removed]
        expect_failure('correction-reject-'+label,lambda changed=changed:guard.validate_correction(parent,changed))
        expect_failure('correction-precommit-reject-'+label,lambda changed=changed:guard.validate_correction(parent,changed,False))
    workflow=Path(q.ROOT/'.github/workflows/n49d-mcp-directory-search.yml').read_bytes()
    def workflow_contract(raw,windows=False):
        latest=guard.checkout_bytes(raw,'6350634c7973c23d5c013a8710108d69779573db',windows)
        check(latest.count(b'          fetch-depth: 24\n')==1 and guard.sha(latest)=='5a8dc5530721ca8aa150abd59aa9043edbeaf9535e62249aab60ffb3b0f0b742','exact depth-twenty-four workflow contract')
        prepared=guard.checkout_bytes(latest.replace(b'          fetch-depth: 24\n',b'          fetch-depth: 23\n'),'44cef40bc3afaa4ed782596ba73ea85e2ce3c463')
        check(prepared.count(b'          fetch-depth: 23\n')==1 and guard.sha(prepared)=='5ef4fb7c35fb89b60753e0fde2b556781bc34e828ba950832bfa4610b8c37f70','exact depth-twenty-three workflow contract')
        current=guard.checkout_bytes(prepared.replace(b'          fetch-depth: 23\n',b'          fetch-depth: 22\n'),
            '742f7385b42503387a00b8cf542947d074de8525')
        check(current.count(b'          fetch-depth: 22\n')==1 and guard.sha(current)=='1aed1027fb370a00bb37ee9ee0dd11d513a8d1dfc05ee84ad5989c38f1d887ef','exact depth-twenty-two workflow contract')
        canonical=guard.checkout_bytes(current.replace(b'          fetch-depth: 22\n',b'          fetch-depth: 21\n'),
            'f45777266c503418f42b37e25a6620c80b8e322f')
        check(guard.sha(canonical)=='1719fc10bc560440435708b11384f3c554e49515b754fc36d599517cbd53f54c','retained depth-twenty-one workflow SHA-256')
        check(canonical.count(b'          fetch-depth: 21\n')==1 and
              guard.sha(canonical.replace(b'          fetch-depth: 21\n',b'          fetch-depth: 20\n'))=='301be8339321cc73db4647197fb37a60118672e79aab4aca95c93c07ee140d99','exact depth-twenty-one workflow contract')
        retained20=canonical.replace(b'          fetch-depth: 21\n',b'          fetch-depth: 20\n')
        check(guard.blob(retained20)=='0d56647552b0f7355904ca419269e77ee70ffea3' and
              guard.sha(retained20.replace(b'          fetch-depth: 20\n',b'          fetch-depth: 19\n'))=='95d52822559d6ea69b92c9ddea4775a3d8d3a74b8865cbe3ce3e7aadc751499b','retained depth-twenty workflow contract')
        retained19=canonical.replace(b'          fetch-depth: 21\n',b'          fetch-depth: 19\n')
        check(guard.blob(retained19)=='6581680b405e81f5d73eb338d8d93031fcbe2f29' and
              guard.sha(retained19.replace(b'          fetch-depth: 19\n',b'          fetch-depth: 18\n'))=='40d9491412522351a71fc1a8da75b8b769536afa5e0cf1dc42e143bef844e897','retained depth-nineteen workflow contract')
        retained=canonical.replace(b'          fetch-depth: 21\n',b'          fetch-depth: 18\n')
        check(guard.blob(retained)=='96780417862a9c1178abfc06942831a81d967640' and
              guard.sha(retained.replace(b'          fetch-depth: 18\n',b'          fetch-depth: 17\n'))=='ec4c0b4dc826d5388f3fad1e651c77e72baaa5d7a5946d9afdd8c1278f3f4332','retained depth-eighteen workflow contract')
        prior=canonical.replace(b'          fetch-depth: 21\n',b'          fetch-depth: 17\n')
        check(guard.blob(prior)=='9d9c23669fdddb16175919b7225b09bb74cb134a' and
              guard.sha(prior.replace(b'          fetch-depth: 17\n',b'          fetch-depth: 16\n'))=='fca153f784aa795c16f5dc44f04ef4ac361e2a1183f332d9f16eaa0e52b54237','exact retained depth-seventeen workflow contract')
        previous=canonical.replace(b'          fetch-depth: 21\n',b'          fetch-depth: 16\n')
        check(guard.blob(previous)=='570f57685ff0ca4d4961b4e6256c006076b7e133' and
              guard.sha(previous.replace(b'          fetch-depth: 16\n',b'          fetch-depth: 15\n'))=='7569e7a65178209597ee79dc4a4a07b90cf9e672a1dc51eb707ebbdb830d85d1','exact retained depth-sixteen workflow contract')
        previous=canonical.replace(b'          fetch-depth: 21\n',b'          fetch-depth: 15\n')
        check(guard.blob(previous)=='ab210bde14b8943cf3d2c90442c76f5c3774bfa5' and
              previous.count(b'          fetch-depth: 15\n')==1 and
              guard.sha(previous.replace(b'          fetch-depth: 15\n',b'          fetch-depth: 14\n'))=='132c502e899399b2a085555a0d5758030b439532ed898309434fe1d8d5a4beb4','exact retained depth-fifteen workflow contract')
        previous=canonical.replace(b'          fetch-depth: 21\n',b'          fetch-depth: 14\n')
        check(guard.blob(previous)=='103ea3d99c6f1977564008474e91e22c1c289f03' and
              previous.count(b'          fetch-depth: 14\n')==1 and
              guard.sha(previous.replace(b'          fetch-depth: 14\n',b'          fetch-depth: 13\n'))=='9f1d0514132a60435af03e84e904402f90c7ce732311720e50f38f9960013e3a','exact retained depth-fourteen workflow contract')
        return latest
    control('workflow-only-depth-twenty-one-change',lambda:workflow_contract(workflow,os.name=='nt'))
    canonical=workflow_contract(workflow,os.name=='nt')
    expect_failure('workflow-retained-depth-twenty-three',lambda:workflow_contract(canonical.replace(b'          fetch-depth: 24\n',b'          fetch-depth: 23\n')),'checkout blob mismatch',record=False)
    expect_failure('workflow-retained-depth-twenty-two',lambda:workflow_contract(canonical.replace(b'          fetch-depth: 24\n',b'          fetch-depth: 22\n')),'checkout blob mismatch',record=False)
    expect_failure('workflow-retained-depth-twenty-one',lambda:workflow_contract(canonical.replace(b'          fetch-depth: 24\n',b'          fetch-depth: 21\n')),'checkout blob mismatch',record=False)
    expect_failure('workflow-retained-depth-twenty',lambda:workflow_contract(canonical.replace(b'          fetch-depth: 24\n',b'          fetch-depth: 20\n')),'checkout blob mismatch',record=False)
    expect_failure('workflow-retained-depth-nineteen',lambda:workflow_contract(canonical.replace(b'          fetch-depth: 24\n',b'          fetch-depth: 19\n')),'checkout blob mismatch',record=False)
    expect_failure('workflow-retained-depth-eighteen',lambda:workflow_contract(canonical.replace(b'          fetch-depth: 24\n',b'          fetch-depth: 18\n')),'checkout blob mismatch',record=False)
    expect_failure('workflow-retained-depth-seventeen',lambda:workflow_contract(canonical.replace(b'          fetch-depth: 24\n',b'          fetch-depth: 17\n')),'checkout blob mismatch',record=False)
    expect_failure('workflow-retained-depth-sixteen',lambda:workflow_contract(canonical.replace(b'          fetch-depth: 24\n',b'          fetch-depth: 16\n')),'checkout blob mismatch',record=False)
    expect_failure('workflow-retained-depth-fifteen',lambda:workflow_contract(canonical.replace(b'          fetch-depth: 24\n',b'          fetch-depth: 15\n')),'checkout blob mismatch',record=False)
    expect_failure('workflow-retained-depth-fourteen',lambda:workflow_contract(canonical.replace(b'          fetch-depth: 24\n',b'          fetch-depth: 14\n')),'checkout blob mismatch',record=False)
    def retained_depth_thirteen_contract():
        previous=canonical.replace(b'          fetch-depth: 24\n',b'          fetch-depth: 13\n')
        check(guard.blob(previous)=='1c1b590dffbdcdb1fc06896788872a828b3b0291' and
              previous.count(b'          fetch-depth: 13\n')==1 and
              guard.sha(previous.replace(b'          fetch-depth: 13\n',b'          fetch-depth: 12\n'))=='9e8f255ee3534cd468b770eaaacf07dae17f804019dca1dc8babb57bd2ef948a','exact retained depth-thirteen workflow contract')
    control('workflow-only-depth-thirteen-change',retained_depth_thirteen_contract)
    def retained_depth_twelve_contract():
        previous=canonical.replace(b'          fetch-depth: 24\n',b'          fetch-depth: 12\n')
        check(guard.blob(previous)=='f1aa24556a0c2cb9b9b2a176cbdd09ac947224a1' and
              previous.count(b'          fetch-depth: 12\n')==1 and
              guard.sha(previous.replace(b'          fetch-depth: 12\n',b'          fetch-depth: 11\n'))=='401d38d79f89fedf309305af54f778bb000cef09f255215b4db34d268cd1497d','exact retained depth-twelve workflow contract')
    control('workflow-only-depth-twelve-change',retained_depth_twelve_contract)
    def retained_depth_eleven_contract():
        previous=canonical.replace(b'          fetch-depth: 24\n',b'          fetch-depth: 11\n')
        check(guard.blob(previous)=='5d5ad4346f87a24531a2f327b116d18e9d39c557' and
              previous.count(b'          fetch-depth: 11\n')==1 and
              guard.sha(previous.replace(b'          fetch-depth: 11\n',b'          fetch-depth: 10\n'))=='9cf5265dd2f90c275bff5ce2e4d8249bdd031ab342ba92ab74ad95eeef2e92f2','exact retained depth-eleven workflow contract')
    control('workflow-only-depth-eleven-change',retained_depth_eleven_contract)
    for label,old,new in [('old-depth',b'fetch-depth: 24',b'fetch-depth: 10'),('previous-depth',b'fetch-depth: 24',b'fetch-depth: 12'),('broad-depth',b'fetch-depth: 24',b'fetch-depth: 0'),
                          ('retained-depth',b'fetch-depth: 24',b'fetch-depth: 13'),
                          ('malformed-depth',b'fetch-depth: 24',b'fetch-depth: four'),('mutable-ref',b'ref: ${{ inputs.candidate || github.sha }}',b'ref: main'),
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
                tree=object.__new__(q._LinuxTree);q._initialize_linux_failure_detail(tree);tree.known={};tree.controller_pid=controller;calls=[]
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
            tree=object.__new__(q._LinuxTree);q._initialize_linux_failure_detail(tree);tree.known={};tree.controller_pid=controller
            with patch.object(tree,'parent_current',return_value=True),patch.object(q,'_linux_stat',side_effect=[before,after]),patch.object(q.os,'pidfd_open',return_value=999,create=True),patch.object(q.os,'close'):
                expect_failure('failure-detail-linux-early-'+label,lambda:tree.observe(child,controller),'ambiguous descendant ancestry' if label=='before-link' else 'start')
                check((tree.failure_detail['site']==q._LINUX_INITIAL_SITE and tree.failure_detail['complete']) if label=='before-link' else getattr(tree,'failure_detail',None) is None,'early Linux error detail boundary')
        tree=object.__new__(q._LinuxTree);q._initialize_linux_failure_detail(tree);tree.known={};tree.controller_pid=controller
        with patch.object(tree,'parent_current',return_value=True),patch.object(q,'_linux_stat',side_effect=[dict(start=1,ppid=controller),dict(start=2,ppid=controller)]),patch.object(q.os,'pidfd_open',return_value=999,create=True),patch.object(q.os,'close') as close,patch.object(q,'_linux_identity_detail',side_effect=RuntimeError('private-detail-error')):
            expect_failure('failure-detail-linux-builder-error-permanent',lambda:tree.observe(child,controller),'pidfd identity/ancestry mismatch')
            check(tree.failure_detail['complete'] is False and not tree.known and close.call_count==1,'Linux detail error changed cleanup')
        for label,value in [('list',[]),('extra',dict(q._linux_detail_unavailable(),raw='private-sentinel')),('bad-complete',dict(q._linux_detail_unavailable(),complete=1))]:
            check(q._copy_linux_failure_detail(value)==q._linux_detail_unavailable('unknown'),'malformed transferred detail accepted')
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
                def copy_detail(value,*origin):
                    if broken_detail=='copy':raise ValueError('private-copy-error')
                    return original_copy(value,*origin)
                with patch.object(q,'_linux_stat',fault),patch.object(q,'_linux_identity_detail',detail),patch.object(q,'_copy_linux_failure_detail',copy_detail):
                    expect_failure('failure-detail-real-recorder-mismatch-'+str(broken_detail),lambda:recorder.run('tiny',[sys.executable,'-c','import time;time.sleep(10)'],3),'pidfd identity/ancestry mismatch')
                row=json.loads((recorder.root/'stages/tiny/result.json').read_bytes());owned=row['ownership']
                check(len(injected)==1 and injected[0]==owned['root_pid'] and row['classification']=='pidfd identity/ancestry mismatch' and
                      owned['classification']=='pidfd identity/ancestry mismatch' and owned['failure_detail']['complete'] is (not broken_detail) and
                      all(owned[key] is True for key in ('cleanup_ok','owned_tree_empty','readers_done','stable')) and
                      q._ACTIVE_OWNER is None and not q._OWNER_LOCK.locked() and 'private-' not in json.dumps(owned),'failed comparison detail changed owned cleanup/outcome')
    finally:FAILURE_DETAIL=saved


def initial_parent_controls(root):
    """Exact observe/transfer models and genuine owner-bound injected failures."""
    from types import SimpleNamespace
    import test_mcp_directory_search as driver
    root.mkdir();controller=1<<34;parent=controller+1;child=controller+2
    initial=q._LINUX_INITIAL_SITE;later=q._LINUX_LATER_SITE
    unknown=q._linux_detail_unavailable('unknown')
    class Tree(q._LinuxTree):
        def __getattribute__(self,key):
            try:blocked=object.__getattribute__(self,'read_faults')
            except AttributeError:blocked=set()
            if key in blocked:raise RuntimeError('private-read-fault')
            return object.__getattribute__(self,key)
        def __setattr__(self,key,value):
            try:blocked=object.__getattribute__(self,'write_faults')
            except AttributeError:blocked=set()
            all_diagnostic=object.__getattribute__(self,'__dict__').get('block_all_diagnostic',False)
            if key in blocked or (all_diagnostic and (key.startswith('_failure_') or key=='failure_detail')):
                raise RuntimeError('private-store-fault')
            object.__setattr__(self,key,value)
        def active(self):self.cleanup_calls.append('active');return []
        def terminate(self):self.cleanup_calls.append('terminate')
        def close(self):
            self.cleanup_calls.append('close')
            if getattr(self,'close_fault',False):raise ValueError('fixture-close-failure')
    def make(known=None):
        tree=object.__new__(Tree);tree.known={} if known is None else known;tree.controller_pid=controller
        tree.read_faults=set();tree.write_faults=set();tree.cleanup_calls=[]
        q._initialize_linux_failure_detail(tree);return tree
    def observe(tree,site=initial,expected=controller,pin=None,before_parent=None):
        calls=[];reads=[dict(start=7,ppid=expected if site==later else (parent if before_parent is None else before_parent))]
        if site==later:reads.append(dict(start=8,ppid=expected))
        def parent_current(p,v):calls.append('parent');return True
        def stat(p):check(p==child,'foreign model target');calls.append('stat');return reads.pop(0)
        def opened(p,flags):check(p==child and flags==0,'foreign model pin');calls.append('open');return 999
        saved=copy.deepcopy(tree.known);error='ambiguous descendant ancestry' if site==initial else 'pidfd identity/ancestry mismatch'
        with patch.object(tree,'parent_current',parent_current),patch.object(q,'_linux_stat',stat),patch.object(q.os,'pidfd_open',opened,create=True),patch.object(q.os,'close') as closed,patch.object(q.os,'getpid',side_effect=AssertionError('extra process query')):
            try:tree.observe(child,expected,pin)
            except ValueError as caught:check(str(caught)==error,'original comparison error replaced')
            else:raise ValueError('initial relation unexpectedly admitted')
        check(calls==(['parent','stat','parent'] if site==initial else ['parent','stat','parent','open','stat','parent']) and
              closed.call_count==int(site==later) and tree.known==saved,'original observe process order/map changed')
        return tree
    def transfer(tree):
        target={};q._retain_linux_failure_detail(target,tree);return target.get('failure_detail')
    cases=[]
    for label,known,pin,expected,ppid in [
        ('new',{},None,controller,parent),
        ('known-equal',{child:dict(fd=0,start=7)},None,controller,parent),
        ('known-other',{child:dict(fd=313,start=8)},None,controller,parent),
        ('pinned-controller',{},dict(fd=314,start=9),parent,controller),
        ('pinned-other',{},dict(fd=314,start=9),parent,parent+9)]:
        if pin is not None:known[parent]=pin
        tree=observe(make(known),expected=expected,pin=pin,before_parent=ppid);value=transfer(tree)
        check(value['complete'] is True and value['candidate_was_already_known']==(child in known) and
              value['candidate_pin_recorded']==(child in known) and
              value['candidate_start_matches_before']==(known[child]['start']==7 if child in known else None) and
              value['parent_pin_present']==(pin is not None) and value['parent_pin_is_current_known']==(pin is not None) and
              value['before_parent_matches_controller']==(ppid==controller) and value['expected_parent_is_controller']==(expected==controller),
              'initial relation value')
        check(str(controller) not in json.dumps(value) and str(child) not in json.dumps(value),'initial raw identity leak')
        cases.append((label,value));RESULTS.append(dict(name='initial-relations-'+label,passed=True))
    # Pure conjunction: matching known child, current non-controller parent pin,
    # and a sampled PPID matching neither. These integers never reach the OS.
    from contextlib import ExitStack
    conjunction_child=dict(fd=313,start=7);conjunction_parent=dict(fd=314,start=9)
    conjunction_known={child:conjunction_child,parent:conjunction_parent}
    conjunction_saved=copy.deepcopy(conjunction_known);tree=make(conjunction_known)
    conjunction_facts=dict(before_parent_matches_expected=False,before_parent_matches_controller=False,
        expected_parent_is_controller=False,parent_pin_present=True,parent_pin_is_current_known=True,
        candidate_was_already_known=True,candidate_pin_recorded=True,candidate_start_matches_before=True,
        final_parent_check_returned_true=True,new_pidfd_acquired_in_observe=False)
    conjunction_expected=dict(schema='qbrain-n49d-linux-initial-parent-comparison-v1',site=initial,
        complete=True,reason='parent-mismatch',**conjunction_facts)
    with ExitStack() as blocked:
        # observe() installs its three scripted parent/stat/parent calls and its
        # own open/close checks. These outer guards cover transfer and all other
        # process operations, including optional errors swallowed by capture.
        forbidden=[blocked.enter_context(patch.object(target,name,
            side_effect=AssertionError('conjunction extra ownership operation'),create=True))
            for target,name in ((q,'_pidfd_exited'),(q,'_linux_children'),(q,'_linux_no_children'),
                (q,'_linux_stat'),(q.os,'pidfd_open'),(q.os,'close'),(q.os,'getpid'),
                (q.os,'getppid'),(q.os,'waitpid'),(q.os,'kill'),(q.os,'killpg'),
                (q.signal,'pidfd_send_signal'))]
        built=blocked.enter_context(patch.object(q,'_linux_initial_parent_detail',wraps=q._linux_initial_parent_detail))
        observe(tree,expected=parent,pin=conjunction_parent,before_parent=parent+9)
        first=tree.failure_detail;frozen=copy.deepcopy(first);value=transfer(tree)
        check(type(first) is dict and set(first)==set(conjunction_expected) and
              first['complete'] is True and
              all(type(first[key]) is str and first[key]==conjunction_expected[key] for key in ('schema','site','reason')) and
              all(type(first[key]) is bool and first[key] is expected for key,expected in conjunction_facts.items()),
              'known pinned conjunction ten facts')
        check(value==conjunction_expected and value is not first and
              all(type(value[key]) is bool and value[key] is expected for key,expected in conjunction_facts.items()),
              'known pinned conjunction transfer facts')
        check(built.call_count==1,'known pinned conjunction initial builder count')
        serialized=json.dumps(value,sort_keys=True)
        check(all(str(identity) not in serialized for identity in (controller,parent,child,parent+9,313,314)) and
              all(type(item) is bool or type(item) is str for item in value.values()),
              'known pinned conjunction raw model identity leak')
        # Repeat the same conjunction, then a different initial-parent failure.
        # Neither may rebuild or replace the complete first observation.
        observe(tree,expected=parent,pin=conjunction_parent,before_parent=parent+9)
        observe(tree)
        repeated=transfer(tree)
        check(tree.failure_detail is first and first==frozen and repeated==conjunction_expected and repeated is not first and
              built.call_count==1 and
              all(type(repeated[key]) is bool and repeated[key] is expected for key,expected in conjunction_facts.items()),
              'known pinned conjunction first capture replaced')
        check(tree.known is conjunction_known and tree.known==conjunction_saved and
              tree.known[child] is conjunction_child and tree.known[parent] is conjunction_parent and
              tree.cleanup_calls==[] and all(probe.call_count==0 for probe in forbidden),
              'known pinned conjunction process action or known map mutation')
    cases.append(('known-pinned-other',value))
    RESULTS.append(dict(name='initial-relations-known-pinned-other',passed=True))
    initial_value=cases[0][1]
    old_tree=observe(make(),later);later_value=transfer(old_tree)
    check(later_value==q._linux_identity_detail(dict(start=7,ppid=controller),dict(start=8,ppid=controller),controller,controller,None),'legacy output changed')
    for label,record in [('none',None),('list',[]),('fd-missing',dict(start=7)),('start-missing',dict(fd=1)),('fd-bool',dict(fd=True,start=7)),
                         ('fd-negative',dict(fd=-1,start=7)),('start-bool',dict(fd=0,start=True)),('start-text',dict(fd=0,start='private-start'))]:
        tree=observe(make({child:record}))
        check(transfer(tree)==q._linux_detail_unavailable(initial),'malformed known became new/complete')
        RESULTS.append(dict(name='initial-known-invalid-'+label,passed=True))
    for label,changes in [('known-null',dict(candidate_was_already_known=True,candidate_pin_recorded=True)),
                          ('new-start',dict(candidate_start_matches_before=False)),('known-unpinned',dict(candidate_was_already_known=True,candidate_start_matches_before=True)),
                          ('new-pinned',dict(candidate_pin_recorded=True)),('parent-without-pin',dict(parent_pin_is_current_known=True)),
                          ('before-true',dict(before_parent_matches_expected=True)),('check-false',dict(final_parent_check_returned_true=False)),
                          ('new-pin-true',dict(new_pidfd_acquired_in_observe=True)),('bool-int',dict(candidate_pin_recorded=0)),
                          ('extra',dict(private='private-value')),('complete-int',dict(complete=1)),('wrong-reason',dict(reason='private-value'))]:
        changed=dict(initial_value,**changes)
        check(q._copy_linux_failure_detail(changed,initial)==q._linux_detail_unavailable(initial),'invalid nullable/fixed shape copied')
        RESULTS.append(dict(name='initial-copy-invalid-'+label,passed=True))
    # Every optional read and pin type is still after the original rejection.
    for label,known,pin in [('parent-record',{parent:None},None),('pin-type',{},[]),('pin-fd',{},dict(fd=True,start=1))]:
        tree=observe(make(known),expected=parent,pin=pin,before_parent=controller)
        check(transfer(tree)==q._linux_detail_unavailable(initial),'malformed parent metadata passed')
        RESULTS.append(dict(name='initial-parent-invalid-'+label,passed=True))
    pin=dict(fd=1,start=7);tree=observe(make({parent:dict(pin)}),pin=pin)
    check(transfer(tree)['parent_pin_present'] and not transfer(tree)['parent_pin_is_current_known'],'parent pin equality mistaken for identity')
    RESULTS.append(dict(name='initial-parent-pin-identity',passed=True))

    for site in (initial,later):
        tree=observe(make(),site);first=tree.failure_detail;frozen=copy.deepcopy(first)
        for next_site in (initial,later):
            observe(tree,next_site)
            check(tree.failure_detail is first and transfer(tree)==frozen,'complete first observation overwritten')
        RESULTS.append(dict(name='initial-complete-immutable-'+site,passed=True))
        for label,payload in [('null',None),('malformed',[]),('oversized',dict(private='x'*2048))]:
            tree=observe(make(),site);tree.failure_detail=payload
            check(transfer(tree)==q._linux_detail_unavailable(site),'invalid matching-origin payload changed origin')
            RESULTS.append(dict(name='initial-payload-'+site+'-'+label,passed=True))
        tree=observe(make(),site);tree.read_faults={'failure_detail'}
        check(transfer(tree)==q._linux_detail_unavailable(site),'payload access lost trusted origin')
        RESULTS.append(dict(name='initial-payload-read-'+site,passed=True))
        tree=observe(make(),site);tree.read_faults={'_failure_origin'}
        observe(tree,initial);observe(tree,later)
        check(transfer(tree)==unknown,'origin read failure manufactured later data')
        RESULTS.append(dict(name='initial-read-fault-repeat-'+site,passed=True))
    for label,payload in cases[:2]:
        exact=len((json.dumps({'ownership':{'failure_detail':payload}},sort_keys=True,indent=2)+'\n').replace('\n','\r\n').encode())
        fallback=q._linux_detail_unavailable(initial)
        for delta in (-1,0,1):
            result=q._bounded_failure_detail(payload,fallback,exact+delta,ownership=True)
            check(result==(fallback if delta<0 else payload),'initial formatted byte boundary')
        RESULTS.append(dict(name='initial-exact-wrapper-cap-'+label,passed=True))
    for label,field in [('before-start','start'),('before-parent','ppid')]:
        tree=make()
        with patch.object(tree,'parent_current',return_value=True),patch.object(q,'_linux_stat',return_value=dict(start=True if field=='start' else 7,ppid=True if field=='ppid' else parent)),patch.object(q.os,'pidfd_open',side_effect=AssertionError('new query'),create=True):
            expect_failure('initial-invalid-'+label,lambda:tree.observe(child,controller),'ambiguous descendant ancestry',record=False)
        check(transfer(tree)==q._linux_detail_unavailable(initial),'before bool metadata became complete')
        RESULTS.append(dict(name='initial-invalid-'+label,passed=True))

    # Actual capture, followed by opposite-site payload substitution and transfer.
    for site,value in [(initial,later_value),(later,initial_value)]:
        tree=observe(make(),site);tree.failure_detail=value
        check(transfer(tree)==q._linux_detail_unavailable(site),'cross-site payload changed origin')
        RESULTS.append(dict(name='initial-cross-origin-'+site,passed=True))
    for label,value,expected in [('complete',later_value,later_value),('unavailable',q._linux_detail_unavailable(),q._linux_detail_unavailable()),
            ('initial-complete',initial_value,unknown),('initial-unavailable',q._linux_detail_unavailable(initial),unknown),
            ('invalid',{'private':17},unknown),('null',None,unknown)]:
        tree=make();del tree._failure_origin;del tree._failure_capture_cell;tree.failure_detail=value
        check(transfer(tree)==expected,'missing-marker legacy validation')
        RESULTS.append(dict(name='initial-marker-absent-'+label,passed=True))
    tree=make();check(transfer(tree) is None,'untouched metadata manufactured detail')
    RESULTS.append(dict(name='initial-untouched-field-free',passed=True))
    for label,marker in [('none',None),('unknown','unknown'),('malformed',{'private':17}),('boolean',False)]:
        tree=observe(make());tree._failure_origin=marker;tree.failure_detail=later_value
        check(transfer(tree)==unknown,'explicit bad marker accepted legacy')
        RESULTS.append(dict(name='initial-marker-'+label,passed=True))
    tree=observe(make());tree.read_faults={'_failure_origin'}
    check(transfer(tree)==unknown,'read failure inferred site')
    RESULTS.append(dict(name='initial-marker-read-failure',passed=True))
    tree=observe(make());tree.read_faults={'_failure_capture_consumed'}
    check(transfer(tree)==initial_value,'trusted origin unnecessarily read consumed state')
    RESULTS.append(dict(name='initial-origin-alone-authoritative',passed=True))

    for site in (initial,later):
        for fault in ('builder','payload','both'):
            tree=make()
            if fault in ('payload','both'):tree.write_faults={'failure_detail'}
            builder='_linux_initial_parent_detail' if site==initial else '_linux_identity_detail'
            with patch.object(q,builder,side_effect=ValueError('private-builder')) if fault in ('builder','both') else patch.object(q,builder,getattr(q,builder)):
                observe(tree,site)
            expected=q._linux_detail_unavailable(site);check(transfer(tree)==expected,'latched origin lost after payload fault')
            tree.write_faults=set()
            for next_site in (initial,later):observe(tree,next_site);check(transfer(tree)==expected,'payload recovered by later capture')
            RESULTS.append(dict(name='initial-latch-'+site+'-'+fault,passed=True))
    for fault in ('marker','marker-payload','consumed','all'):
        tree=make();tree.write_faults={'_failure_origin'}
        if fault in ('marker-payload','all'):tree.write_faults.add('failure_detail')
        if fault in ('consumed','all'):tree.write_faults.add('_failure_capture_consumed')
        observe(tree)
        observed=transfer(tree)
        if fault=='all':
            check(observed in (None,unknown),'total storage fault invented durable origin')
            observe(tree,later);check(transfer(tree) in (None,unknown),'persistent total fault invented observation')
        else:
            check(observed==unknown,'assignment failure lost unknown origin')
            tree.write_faults=set()
            for next_site in (initial,later):observe(tree,next_site);check(transfer(tree)==unknown,'recovered stores relabelled first event')
        RESULTS.append(dict(name='initial-latch-storage-'+fault,passed=True))
    tree=make();tree.read_faults={'failure_detail'};observe(tree)
    tree.read_faults=set()
    check(transfer(tree)==unknown,'existence-check failure reopened capture')
    observe(tree,later);check(transfer(tree)==unknown,'existence-check recovery relabelled first failure')
    RESULTS.append(dict(name='initial-latch-existence-failure',passed=True))
    for name in ('_failure_origin','_failure_capture_cell'):
        tree=object.__new__(Tree);tree.write_faults={name};q._initialize_linux_failure_detail(tree)
        check(transfer(tree)==unknown,'metadata init failure not unavailable')
        RESULTS.append(dict(name='initial-init-store-'+name,passed=True))
    class Refusing(dict):
        def __setitem__(self,key,value):raise OSError('private-target-write')
    q._retain_linux_failure_detail(Refusing(),observe(make()))
    RESULTS.append(dict(name='initial-fallback-write-contained',passed=True))

    # The original setter fault stays active through the one-way in-place step.
    metadata={'_failure_capture_consumed','_failure_origin','failure_detail'}
    for first_site,next_site in [(initial,initial),(initial,later),(later,initial),(later,later)]:
        for all_setters in (False,True):
            tree=make();cell=tree._failure_capture_cell;token=cell[0]
            check(type(cell) is list and len(cell)==1 and token[0] is tree,'cell not preallocated/owner-bound')
            tree.write_faults=set(metadata);tree.block_all_diagnostic=all_setters
            writes=[];builders=[];setter=Tree.__setattr__
            def tracked(self,key,value):
                if self is tree and (key.startswith('_failure_') or key=='failure_detail'):writes.append(key)
                return setter(self,key,value)
            def prohibited_builder(*args):builders.append(True);raise AssertionError('second builder')
            with patch.object(Tree,'__setattr__',tracked),patch.object(q,'_new_linux_failure_cell',side_effect=AssertionError('cell recreated')),patch.object(q,'_linux_initial_parent_detail',prohibited_builder),patch.object(q,'_linux_identity_detail',prohibited_builder):
                observe(tree,first_site)
                check(tree._failure_capture_cell is cell and cell==[],'setter faults prevented one-way consumption')
                first=transfer(tree);check(first==unknown,'failed optional stores invented first origin')
                count=len(writes);tree.write_faults=set();tree.block_all_diagnostic=False
                observe(tree,next_site)
                check(tree._failure_capture_cell is cell and cell==[] and not builders and len(writes)==count and
                      transfer(tree)==first and transfer(tree)==first,'recovered attribute stores relatch/refill/refresh')
                q._initialize_linux_failure_detail(tree)
                check(tree._failure_capture_cell is cell and cell==[] and len(writes)==count,'initializer reset consumed cell')
            RESULTS.append(dict(name='cell-store-recovery-'+str(all_setters)+'-'+first_site+'-'+next_site,passed=True))

    # Selected metadata getters must execute only after successful consumption.
    for site,key in [(initial,'controller_pid'),(initial,'known'),(later,'controller_pid'),(initial,'_failure_origin'),(initial,'failure_detail')]:
        tree=make();cell=tree._failure_capture_cell;getter=Tree.__getattribute__;seen=[];entered=[]
        original_consume=q._consume_linux_failure_cell
        def consume(value):
            result=original_consume(value)
            if value is tree:entered.append(result)
            return result
        def get(self,name):
            if self is tree and name==key and entered and not seen:
                seen.append((name,len(cell)))
                raise RuntimeError('private-cached-getter')
            return getter(self,name)
        with patch.object(Tree,'__getattribute__',get),patch.object(q,'_consume_linux_failure_cell',consume):
            observe(tree,site)
        expected=q._linux_detail_unavailable(site) if key in ('controller_pid','known') else unknown
        check(seen==[(key,0)] and entered==[True] and cell==[] and transfer(tree)==expected,'optional read preceded latch')
        observe(tree,later if site==initial else initial)
        check(tree._failure_capture_cell is cell and cell==[] and transfer(tree)==expected,'cached getter recovery relabelled origin')
        RESULTS.append(dict(name='cell-deferred-'+site+'-'+key,passed=True))

    def blank():
        tree=object.__new__(Tree);tree.known={};tree.controller_pid=controller
        tree.read_faults=set();tree.write_faults=set();tree.cleanup_calls=[];tree.block_all_diagnostic=False
        return tree
    for label,value in [('absent',q._LINUX_DETAIL_MISSING),('none',None),('tuple',()),('oversized',[None,None]),
                        ('foreign',[(object(),q._LINUX_DETAIL_UNLATCHED)]),('bad-token',[(None,None)])]:
        tree=make()
        if value is q._LINUX_DETAIL_MISSING:del tree._failure_capture_cell
        else:tree._failure_capture_cell=value
        with patch.object(q,'_new_linux_failure_cell',side_effect=AssertionError('lazy cell initialization')):
            observe(tree);first=transfer(tree);observe(tree,later);q._initialize_linux_failure_detail(tree)
        check(first==unknown and transfer(tree)==unknown and
              getattr(tree,'_failure_capture_cell',q._LINUX_DETAIL_MISSING) is value,'invalid cell reset or admitted capture')
        RESULTS.append(dict(name='cell-disabled-'+label,passed=True))
    class ListSubclass(list):pass
    tree=make();tree._failure_capture_cell=ListSubclass([(tree,q._LINUX_DETAIL_UNLATCHED)])
    observe(tree);check(transfer(tree)==unknown,'list subclass treated as trusted cell')
    RESULTS.append(dict(name='cell-disabled-subclass',passed=True))
    for label in ('allocate','install','origin-install'):
        tree=blank()
        if label=='install':tree.write_faults={'_failure_capture_cell'}
        if label=='origin-install':tree.write_faults={'_failure_origin'}
        with patch.object(q,'_new_linux_failure_cell',side_effect=MemoryError('private-allocation')) if label=='allocate' else patch.object(q,'_new_linux_failure_cell',q._new_linux_failure_cell):
            q._initialize_linux_failure_detail(tree)
        cell=getattr(tree,'_failure_capture_cell',q._LINUX_DETAIL_MISSING);tree.write_faults=set()
        with patch.object(q,'_new_linux_failure_cell',side_effect=AssertionError('initialization retried')):
            observe(tree);first=transfer(tree);observe(tree,later);q._initialize_linux_failure_detail(tree)
        check(first==unknown and transfer(tree)==unknown and getattr(tree,'_failure_capture_cell',q._LINUX_DETAIL_MISSING) is cell,'initialization fault recovered to fresh')
        RESULTS.append(dict(name='cell-initialization-'+label,passed=True))
    for label in ('access','consume-before','consume-after'):
        tree=make();cell=tree._failure_capture_cell;consume=q._consume_linux_failure_cell
        if label=='access':tree.read_faults={'_failure_capture_cell'}
        def broken(value):
            if label=='consume-after':consume(value)
            raise RuntimeError('private-consumption')
        with patch.object(q,'_consume_linux_failure_cell',broken) if label!='access' else patch.object(q,'_consume_linux_failure_cell',consume):
            observe(tree)
        tree.read_faults=set();first=transfer(tree)
        with patch.object(q,'_linux_initial_parent_detail',side_effect=AssertionError('disabled builder')),patch.object(q,'_linux_identity_detail',side_effect=AssertionError('disabled builder')):
            observe(tree,later)
        check(first==unknown and transfer(tree)==unknown and tree._failure_capture_cell is cell and cell==[],
              'surviving disabled state reopened capture')
        RESULTS.append(dict(name='cell-fault-recovery-'+label,passed=True))
    tree=make();tree.read_faults={'_failure_capture_cell'};tree.write_faults=set(metadata)|{'_failure_capture_cell'};tree.block_all_diagnostic=True
    observe(tree);check(transfer(tree)==unknown,'persistent all-state fault invented comparison')
    observe(tree,later);check(transfer(tree)==unknown,'persistent all-state fault replaced failure')
    RESULTS.append(dict(name='cell-total-unavailable-only-no-durability-claim',passed=True))


    # These use actual _end, Recorder and unchanged driver; OS ownership is modeled.
    def owner_model(label,tree,close_fault=False,copy_fault=False,serializer_fault=False):
        folder=root/('owner-'+label);folder.mkdir();paths=[folder/'stdout.bin',folder/'stderr.bin']
        for p in paths:p.write_bytes(b'fixture\n')
        owner=object.__new__(q.OwnedChild);owner.started=time.monotonic();owner.deadline=owner.started+3;owner.scan_deadline=owner.deadline
        owner.paths=paths;owner.proc=SimpleNamespace(pid=17,poll=lambda:0,stdout=None,stderr=None);owner.tree=tree;tree.proc=owner.proc
        tree.close_fault=close_fault;owner.result=None;owner.stable=False;owner.locked=True;owner.readers=[];owner.errors=[]
        owner.overflow=q.threading.Event();owner.job_diagnostic=None;released=[]
        original_copy=q._copy_linux_failure_detail;original_dumps=q.json.dumps
        def copied(*args):
            if copy_fault:raise ValueError('private-copy-fault')
            return original_copy(*args)
        def dumps(*args,**kwargs):
            if serializer_fault:raise ValueError('private-json-fault')
            return original_dumps(*args,**kwargs)
        with patch.object(q,'_copy_linux_failure_detail',copied),patch.object(q.json,'dumps',dumps),patch.object(q,'_ACTIVE_OWNER',owner),patch.object(q,'_OWNER_LOCK',SimpleNamespace(release=lambda:released.append(True))):
            result=owner._end('ambiguous descendant ancestry')
            frozen=copy.deepcopy(result)
            check(owner._end('replacement',True) is result and result==frozen,'owner cached failure changed')
        check(result['classification']=='ambiguous descendant ancestry' and result['exit']==0 and
              result['stable'] is (not close_fault) and owner.locked is close_fault and len(released)==int(not close_fault),'metadata changed lifecycle/release')
        expected_backend=('windows-private-job' if os.name=='nt' else
                          'linux-stat-pidfd-subreaper' if q._PROC_STAT_CHILD_ADAPTER else 'linux-children-pidfd-subreaper')
        metadata_privacy_check(result,expected_backend)
        return owner
    payloads=[('initial-new',initial,initial_value),('initial-known',initial,cases[1][1]),('later',later,later_value),
              ('initial-unavailable',initial,q._linux_detail_unavailable(initial)),('later-unavailable',later,q._linux_detail_unavailable()),
              ('unknown','unknown',unknown)]
    for label,site,payload in payloads:
        tree=observe(make(),initial if site=='unknown' else site);tree._failure_origin=site;tree.failure_detail=payload
        owner=owner_model(label,tree)
        check(owner.result['failure_detail']==payload,'actual owner transfer lost fields')
        record=q.Recorder(root/('record-'+label),identity(),['tiny'],dict(os.environ),root,stream_cap=2048)
        def cached_owner(argv,cwd,env,stdin,stdout,stderr,timeout,cap,*,completion_policy="strict-v1",deadline=None):
            check(completion_policy=="strict-v1" and type(deadline) in (int,float),"cached owner strict policy/deadline")
            Path(stdout).write_bytes(b'fixture\n');Path(stderr).write_bytes(b'fixture\n');return owner
        with patch.object(q,'OwnedChild',cached_owner):
            expect_failure('initial-recorder-'+label,lambda:record.run('tiny',['fixture'],3),'ambiguous descendant ancestry',record=False)
        row=json.loads((record.root/'stages/tiny/result.json').read_bytes())
        check(row['ownership']==owner.result and row['stdout']==owner.result['stdout'] and row['stderr']==owner.result['stderr'],'Recorder cached detail/streams changed')
        ev=driver.Evidence(root/('adapter-'+label));adapter=object.__new__(driver.OwnedProcess)
        adapter.owner=owner;adapter.proc=owner.proc;adapter.ev=ev;adapter.closed=False;adapter.record={'status':'running'};adapter.started=time.monotonic()
        adapter.stdout_path=ev.path('stdout.bin');adapter.stderr_path=ev.path('stderr.bin')
        for path in (adapter.stdout_path,adapter.stderr_path):path.write_bytes(b'fixture\n')
        expect_failure('initial-driver-'+label,lambda:adapter.wait(),'ambiguous descendant ancestry',record=False)
        before=copy.deepcopy(adapter.record);same=adapter.record
        expect_failure('initial-driver-repeat-'+label,lambda:adapter.wait(),'ambiguous descendant ancestry',record=False)
        check(adapter.record is same and adapter.record==before and adapter.record['ownership'] is owner.result,'adapter repeated failure changed evidence')
        for newline in ('\n','\r\n'):
            wrapper=(json.dumps({'ownership':{'failure_detail':payload}},sort_keys=True,indent=2)+'\n').replace('\n',newline).encode()
            stage=(json.dumps(row,sort_keys=True,indent=2)+'\n').replace('\n',newline).encode()
            check(len(wrapper)<=1024 and len(stage)<=16384,'actual initial wrapper/result cap')
            (record.root/'stages/tiny/result.json').write_bytes(stage)
            packet=q.failure_diagnostics(record.root,record.root/'failure.json',identity(),['tiny'],['tiny'],'ambiguous descendant ancestry')
            retained=packet['files']['stages/tiny/result.json']
            check(not retained['truncated'] and retained['retained_offset']==0 and retained['size']==len(stage) and
                  retained['sha256']==hashlib.sha256(stage).hexdigest() and base64.b64decode(retained['data'])==stage and
                  json.loads(base64.b64decode(retained['data']))['ownership']['failure_detail']==payload and
                  (record.root/'failure.json').stat().st_size<=262144,'actual initial retention changed/truncated')
        RESULTS.append(dict(name='initial-actual-caller-retention-'+label,passed=True))
    for site in (initial,later,'unknown'):
        for fault in ('copy','serialize','close'):
            tree=observe(make(),initial if site=='unknown' else site)
            if site=='unknown':tree._failure_origin='unknown'
            owner=owner_model(site+'-'+fault,tree,close_fault=fault=='close',copy_fault=fault=='copy',serializer_fault=fault=='serialize')
            expected=q._linux_detail_unavailable(site) if fault!='close' else transfer(tree)
            check(owner.result['failure_detail']==expected,'error transfer fallback origin')
            RESULTS.append(dict(name='initial-owner-fault-'+site+'-'+fault,passed=True))
    # Tiny real Linux roots: initial stat result only, not a natural race reproduction.
    if os.name!='nt':
        for kind in ('recorder','driver'):
            for fault in ('complete','copy','unknown'):
                folder=root/('real-'+kind+'-'+fault);injected=[];owners=[];read=q._linux_stat;copier=q._copy_linux_failure_detail
                def first_stat(pid,deadline=None):
                    value=read(pid,deadline);owner=q._ACTIVE_OWNER
                    if not injected and owner is not None and owner.proc is not None and pid==owner.proc.pid:
                        injected.append(pid);owners.append(owner)
                        return dict(value,ppid=value['ppid']+1)
                    return value
                real_capture=q._capture_linux_failure_detail
                def capture(tree,*args):
                    real_capture(tree,*args)
                    if fault=='unknown':tree._failure_origin='unknown'
                def copied(*args):
                    if fault=='copy':raise ValueError('private-injected-copy')
                    return copier(*args)
                row=None
                with patch.object(q,'_linux_stat',first_stat),patch.object(q,'_capture_linux_failure_detail',capture),patch.object(q,'_copy_linux_failure_detail',copied):
                    if kind=='recorder':
                        recorder=q.Recorder(folder,identity(),['tiny'],dict(os.environ),root,stream_cap=2048)
                        expect_failure('initial-real-'+kind+'-'+fault,lambda:recorder.run('tiny',[sys.executable,'-c','import time;time.sleep(10)'],3),'ambiguous descendant ancestry',record=False)
                        row=json.loads((folder/'stages/tiny/result.json').read_bytes())
                    else:
                        ev=driver.Evidence(folder)
                        expect_failure('initial-real-'+kind+'-'+fault,lambda:driver.OwnedProcess(ev,[sys.executable,'-c','import time;time.sleep(10)'],root,dict(os.environ),timeout=3),'ambiguous descendant ancestry',record=False)
                        row=ev.commands[-1]
                owned=row['ownership'];detail=owned['failure_detail'];owner=owners[0]
                check(len(injected)==1 and injected[0]==owned['root_pid'] and owned['classification']=='ambiguous descendant ancestry' and
                      owned['exit'] is not None and all(owned[k] is True for k in ('cleanup_ok','owned_tree_empty','readers_done','stable')) and
                      detail['complete'] is (fault=='complete') and detail['site']==('unknown' if fault=='unknown' else initial) and
                      not q._OWNER_LOCK.locked() and q._ACTIVE_OWNER is None,'genuine injected initial failure/cleanup')
                for key,path in zip(('stdout','stderr'),owner.paths):check(q.descriptor(path)==owned[key],'real initial stable stream hash')
                frozen=copy.deepcopy(owned);expect_failure('initial-real-repeat',lambda:owner.wait(),'ambiguous descendant ancestry',record=False)
                check(owner.result==frozen and 'private-' not in json.dumps(row),'real initial failure changed')
                RESULTS.append(dict(name='initial-real-'+kind+'-'+fault,passed=True))

        recorder=q.Recorder(root/'cell-init-neutral',identity(),['tiny'],dict(os.environ),root,stream_cap=2048)
        with patch.object(q,'_new_linux_failure_cell',side_effect=MemoryError('private-allocation')) as allocation:
            recorder.run('tiny',[sys.executable,'-c','print("cell init neutral")'],3)
        row=json.loads((recorder.root/'stages/tiny/result.json').read_bytes())
        check(allocation.call_count==1 and row['classification']=='passed' and row['ownership']['stable'] and
              'failure_detail' not in row['ownership'] and q._ACTIVE_OWNER is None and not q._OWNER_LOCK.locked(),
              'optional cell allocation changed successful ownership')
        RESULTS.append(dict(name='cell-real-constructor-neutral',passed=True))


def failure_detail_retention_controls(root):
    global FAILURE_DETAIL
    root.mkdir();saved=FAILURE_DETAIL
    try:
        record=_detail_fixture();record['ownership'].update(exit=None,cleanup_ok=False,stable=False)
        raw=json.dumps(record).encode();windows=_timeout_failure_detail(record,raw,True,17)
        linux=q._linux_identity_detail(dict(start=1,ppid=23),dict(start=2,ppid=24),23,22,{})
        names=['failure-detail-final-retention-'+platform+'-'+newline for platform in ('windows','linux') for newline in ('LF','CRLF')]
        names += ['failure-detail-final-retention-'+platform+'-'+newline for platform in
                  ('wrapper-maximum','wrapper-prefix','wrapper-fallback','file-maximum','file-unavailable') for newline in ('LF','CRLF')]
        final_controls=RESULTS+[dict(name=name,passed=True) for name in names]
        for platform,detail in [('windows',windows),('linux',linux)]:
            for newline in ('LF','CRLF'):
                case=root/(platform+'-'+newline);stage=case/'stages/tiny';stage.mkdir(parents=True)
                terminal=dict(record['ownership'],classification='nonzero child exit' if platform=='windows' else 'pidfd identity/ancestry mismatch')
                if platform=='linux':terminal['failure_detail']=detail
                FAILURE_DETAIL=detail if platform=='windows' else None
                failure=_selftest_failure(ValueError('timeout fixture boundary not proved'));failure['controls']=final_controls
                stderr=(render_selftest_failure(failure)+'\n') if platform=='windows' else 'tiny build diagnostic\n'
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
                if platform=='windows':check(failure_equal(expand_failure_v2(base64.b64decode(payload['files']['stages/tiny/stderr.bin']['data'])),failure),'retained full control facts changed')
                observed=retained['failure_detail'] if platform=='windows' else retained['ownership']['failure_detail']
                check(observed==detail and payload['passed'] is False and payload['status']=='failed-partial-diagnostics' and
                      (case/'failure.json').stat().st_size<=256*1024,'retained failure detail/outcome changed')
                RESULTS.append(dict(name='failure-detail-final-retention-'+platform+'-'+newline,passed=True))
        wrapper_retention_controls(root/'wrapper',final_controls)
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
    def model(mode='live',count=1,image_options=None):
        options=image_options or {};last_error=[5];buffers=[]
        now=[0.];calls=[];closed=[];waits=[];tree=object.__new__(q._WindowsTree)
        class ImageC(C):
            @staticmethod
            def get_last_error():return last_error[0]
            @staticmethod
            def sizeof(value):
                return 8 if options.get('fault')=='abi' and value is c.c_uint32 else c.sizeof(value)
        tree.c=ImageC();tree.w=SimpleNamespace(DWORD=c.c_uint32,BOOL=c.c_int32)
        tree.Accounting=Accounting;tree.ProcessList=q._windows_job_list_type(c)
        tree.job=123;tree.assigned=True;tree.proc=SimpleNamespace(pid=456)
        tree.last_accounting=dict(total=17,active=count,terminated=3)
        class ImageAPI:
            def __setattr__(self,key,value):
                if options.get('fault')=='binding':raise TypeError('private binding fixture')
                object.__setattr__(self,key,value)
            def __call__(self,handle,flags,buffer,length):
                calls.append(('image',handle,flags));buffers.append(buffer)
                check(flags==0 and len(buffer)==1024 and c.sizeof(buffer)==2048 and length._obj.value==1024,'image API buffer/flags')
                check(self.argtypes==[c.c_void_p,c.c_uint32,c.POINTER(c.c_uint16),c.POINTER(c.c_uint32)] and self.restype is c.c_int32,'image API ABI')
                check(('membership',handle,123) in calls and waits.count(handle)==2 and not any(x==('close',handle) for x in calls),'image not bound to observed open member')
                if options.get('fault')=='exception':raise OSError('PRIVATE_PATH_MUST_NOT_ESCAPE')
                if options.get('fault')=='value-exception':raise ValueError('PRIVATE_PATH_MUST_NOT_ESCAPE')
                last_error[0]=options.get('error',5)
                if options.get('fault')=='query':return 0
                if options.get('fault')=='return-type':return 'invalid'
                raw=options.get('path','C:\\private-prefix\\PyThOn.exe').encode('utf-16le','surrogatepass')
                units=[int.from_bytes(raw[i:i+2],'little') for i in range(0,len(raw),2)]
                for i,value in enumerate(units[:1024]):buffer[i]=value
                length._obj.value=options.get('count',len(units))
                if options.get('fault')=='no-nul' and length._obj.value<1024:buffer[length._obj.value]=65
                if options.get('fault')=='embedded-nul':buffer[0]=0
                if options.get('fault') in ('equal','overrun'):now[0]=.100 if options['fault']=='equal' else .101
                return 1
        api=ImageAPI()
        class Kernel:
            @property
            def QueryFullProcessImageNameW(self):
                calls.append(('image-binding',))
                if options.get('fault')=='missing':raise AttributeError('PRIVATE_SYMBOL')
                return api
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
                if mode in ('root','first-root'):out._obj.pids[0]=456
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
                if mode=='wide-errors' and handle!=0xffffffff-(count-1):last_error[0]=0xffffffff;return False
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
                return 0 if mode=='exited259' or (mode=='first-exited' and handle==0xffffffff) else 258
            def GetExitCodeProcess(self,handle,out):
                calls.append(('exit',handle));out._obj.value=7 if mode=='exit-inconsistent' else 259
                if mode=='exit-overrun':now[0]=.101
                return mode!='exit-error'
            def CloseHandle(self,handle):
                calls.append(('close',handle));closed.append(handle)
                check(all(not any(buffer) for buffer in buffers),'image buffer not wiped before close')
                if mode=='close-overrun':now[0]=.101
                if mode=='close-exception':raise OSError('fixture close')
                return mode!='close-error'
        tree.k=Kernel()
        sample_image=q._WindowsTree.sample_image;parse_image=q._windows_image_name;image_detail=q._image_sample
        def timed_sample(owner,handle,index,deadline):
            if options.get('fault')=='before':now[0]=deadline
            return sample_image(owner,handle,index,deadline)
        def timed_parse(*args):
            value=parse_image(*args)
            if options.get('fault')=='hash-overrun':now[0]=.101
            return value
        def timed_detail(*args,**kwargs):
            if options.get('fault')=='serialization-error' and args and args[0]=='sampled':
                with patch.object(q.json,'dumps',side_effect=ValueError('PRIVATE_SERIALIZATION')):return image_detail(*args,**kwargs)
            value=image_detail(*args,**kwargs)
            if options.get('fault')=='serialization-overrun' and value['status']=='sampled':now[0]=.101
            return value
        with patch.object(q.time,'monotonic',lambda:now[0]),patch.object(q._WindowsTree,'sample_image',timed_sample),patch.object(q,'_windows_image_name',timed_parse),patch.object(q,'_image_sample',timed_detail):
            value=tree.diagnostic(0 if mode=='expired' else options.get('cleanup_deadline',1))
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
    maximum=model('live',32,dict(path='C:/'+('x'*60+'.exe')))[0]
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
    return model



def windows_image_controls(root,model):
    """Actual selector, query/parser and caller models, not Windows execution."""
    import ctypes as c
    from types import SimpleNamespace
    root.mkdir()
    def sample(label,mode='live',count=1,options=None,status='sampled',queries=1,index=0,name='PyThOn.exe'):
        value,calls,closed=model(mode,count,options);row=value['image_sample']
        check(set(row)=={'member_index','status','basename','basename_sha256','race','win32'} and
              row['status']==status and row['member_index']==index and row['race']=='non_atomic','image schema/status '+label)
        check(sum(x[0]=='image' for x in calls)==queries and len(closed)==count,'image selection/closure '+label)
        if status=='sampled':
            check(row['basename']==name and row['basename_sha256']==hashlib.sha256(name.encode('utf-16le')).hexdigest() and row['win32'] is None,'exact image name/hash')
        elif status=='redacted_basename':
            check(row['basename'] is None and row['basename_sha256']==hashlib.sha256(name.encode('utf-16le')).hexdigest(),'redacted exact name hash')
        elif status not in ('query_failed','buffer_limit'):
            check(row['basename'] is row['basename_sha256'] is row['win32'] is None,'unavailable value leakage')
        check('private-prefix' not in json.dumps(value) and 'PRIVATE_' not in json.dumps(value),'private image metadata leaked')
        RESULTS.append(dict(name='image-model-'+label,passed=True));return value,calls
    sample('same-verified-handle')
    sample('first-root-skipped','first-root',2,index=1)
    sample('first-exited-skipped','first-exited',2,index=1)
    sample('first-only-32','live',32)
    for label,mode in [('root-ineligible','root'),('nonroot-signaled259-ineligible','exited259'),
                       ('unverified-ineligible','membership-error'),('nonmember-ineligible','nonmember'),
                       ('conflicting-state-ineligible','conflict'),('exit-race-ineligible','exit-between')]:
        sample(label,mode,status='not_selected',queries=0,index=None)
    empty,_,_=model('live',0)
    check(empty['image_sample']==q._image_sample(),'empty image selection');RESULTS.append(dict(name='image-model-empty',passed=True))
    for label,path,name in [('one-unit','A','A'),('long-path','x'*1012+'/PyThOn.exe','PyThOn.exe'),
                           ('safe64','C:/'+('a'*60+'.exe'),'a'*60+'.exe'),('drive','D:/private-prefix/tool.exe','tool.exe'),
                           ('unc',r'\\private-prefix\share\tool.exe','tool.exe'),('extended',r'\\?\C:\private-prefix\Tool.EXE','Tool.EXE')]:
        sample(label,options=dict(path=path),name=name)
    for label,name in [('over64','a'*61+'.exe'),('unicode','工具.exe'),('surrogate-pair','😀.exe'),
                       ('space','two words.exe'),('punctuation','a:b.exe'),('control','a\nb.exe')]:
        sample(label,options=dict(path='C:/private-prefix/'+name),status='redacted_basename',name=name)
    one=sample('case-upper',options=dict(path='C:/Tool.EXE'),name='Tool.EXE')[0]['image_sample']
    two=sample('case-lower',options=dict(path='Z:/tool.exe'),name='tool.exe')[0]['image_sample']
    check(one['basename_sha256']!=two['basename_sha256'],'name hash folded case')
    p1=sample('prefix-one',options=dict(path='C:/private-prefix/Tool.EXE'),name='Tool.EXE')[0]['image_sample']
    check(p1['basename_sha256']==one['basename_sha256'],'prefix included in name digest')
    for label,options in [('zero-count',dict(count=0)),('count1024',dict(count=1024)),('count-huge',dict(count=0xffffffff)),
                           ('no-nul',dict(fault='no-nul')),('embedded-nul',dict(fault='embedded-nul')),
                           ('empty-component',dict(path='C:/')),('dot',dict(path='C:/.')),('dotdot',dict(path='C:/..')),
                           ('lone-surrogate',dict(path='C:/\ud800.exe')),('return-type',dict(fault='return-type')),
                           ('bad-error-type',dict(fault='query',error=True)),('negative-error',dict(fault='query',error=-1))]:
        sample(label,options=options,status='invalid_result')
    for error in (0,5,6,87,122,0xffffffff):
        value,_=sample('api-error-'+str(error),count=2,options=dict(fault='query',error=error),
                       status='buffer_limit' if error==122 else 'query_failed')
        check(value['image_sample']['win32']==error,'image API error changed')
    sample('serialization-error-latched',count=2,options=dict(fault='serialization-error'),status='metadata_cap')
    for fault,queries in [('missing',0),('binding',0),('abi',0),('exception',1),('value-exception',1)]:
        sample(fault,count=2,options=dict(fault=fault),status='api_exception',queries=queries)
    for fault in ('before','equal','overrun','hash-overrun','serialization-overrun'):
        value,calls=sample(fault,options=dict(fault=fault),status='deadline',queries=0 if fault=='before' else 1)
        check(value['complete'] is False and calls[-1][0]=='close','late image continued observations')
    sample('narrow-original-cleanup',options=dict(cleanup_deadline=.050))
    value,calls=sample('narrow-original-expiry',options=dict(cleanup_deadline=.050,fault='before'),status='deadline',queries=0)
    check(not any(row[0]=='image-binding' for row in calls),'expired image binding accessed')
    for mode in ('close-error','close-exception'):
        value,calls=sample('image-'+mode,mode,2)
        check(value['handles_closed'] is False and value['complete'] is False and sum(row[0]=='image' for row in calls)==1,'close failure caused reselection')
    eligible=dict(root=False,wait_before=258,exit_code=259,wait_after=258)
    for field,value in [('root',0),('wait_before',True),('exit_code','259'),('wait_after',258.0),('error','fixed')]:
        row=dict(eligible);row[field]=value
        control('image-selector-exact-'+field,lambda row=row:check(not q._windows_image_eligible(row),'coerced image selector'))
    units=[65]+[0]*1023
    for label,count,values in [('bool-count',True,units),('short-buffer',1,[65,0]),('bool-unit',1,[True]+[0]*1023)]:
        expect_failure('image-parser-'+label,lambda count=count,values=values:q._windows_image_name(values,count),'invalid_result')
    for label,args in [('bool-index',dict(status='sampled',index=True,name='a',name_hash='a'*64)),
                       ('unknown-status',dict(status='PRIVATE_STATUS',index=0)),('bad-hash',dict(status='sampled',index=0,name='a',name_hash='PRIVATE_HASH')),
                       ('bad-error',dict(status='query_failed',index=0,win32=True)),('error122',dict(status='query_failed',index=0,win32=122)),
                       ('unexpected-name',dict(status='api_exception',index=0,name='PRIVATE_NAME'))]:
        control('image-fixed-detail-'+label,lambda args=args:check(q._image_sample(**args)['status']=='metadata_cap','invalid fixed image detail'))
    with patch.object(q.json,'dumps',side_effect=ValueError('PRIVATE_SERIALIZER')):
        check(q._image_sample('sampled',0,'a','a'*64)['status']=='metadata_cap','image serializer escaped')
    RESULTS.append(dict(name='image-detail-serialization-unavailable',passed=True))
    # New symbol and ABI validation are absent from the successful constructor path.
    for fault in ('missing','binding','abi'):
        touched=[];closed=[];lookups=[]
        class Function:
            def __init__(self,name):self.name=name
            def __call__(self,*args):
                touched.append(self.name)
                if self.name=='CloseHandle':closed.append(args[0])
                return 123 if self.name=='CreateJobObjectW' else 1
        class Kernel:
            def __init__(self):self.functions={}
            def __getattr__(self,name):
                if name=='QueryFullProcessImageNameW':
                    lookups.append(name)
                    if fault=='missing':raise AttributeError('missing fixture symbol')
                    if fault=='binding':
                        class BadBinding:
                            def __setattr__(self,key,value):raise TypeError('bad fixture binding')
                        return BadBinding()
                return self.functions.setdefault(name,Function(name))
        sizeof=c.sizeof
        def widths(value):return 8 if fault=='abi' and value is c.c_uint32 else sizeof(value)
        with patch.object(c,'WinDLL',return_value=Kernel(),create=True),patch.object(c,'sizeof',widths):
            tree=q._WindowsTree()
            owner=object.__new__(q.OwnedChild);owner.started=time.monotonic();owner.deadline=owner.started+3;owner.scan_deadline=owner.deadline
            owner.paths=[root/('constructor-'+fault+'-'+name) for name in ('stdout','stderr')]
            for path in owner.paths:path.write_bytes(b'')
            owner.proc=SimpleNamespace(pid=17,poll=lambda:0,stdout=None,stderr=None);tree.proc=owner.proc;owner.tree=tree
            owner.result=None;owner.stable=False;owner.locked=False;owner.readers=[];owner.errors=[];owner.overflow=q.threading.Event();owner.job_diagnostic=None
            result=owner._end()
        check(result['classification']=='passed' and result['stable'] and 'job_diagnostic' not in result and
              not lookups and 'QueryFullProcessImageNameW' not in touched and closed==[123],'constructor image dependency')
        sample('constructor-neutral-failed-path-'+fault,options=dict(fault=fault),status='api_exception',queries=0)
        RESULTS.append(dict(name='image-constructor-neutral-'+fault,passed=True))
    # Protected actual owner/Recorder propagation with no OS process in this model.
    original=q.OwnedChild
    for label,mode,count,options in [('visible','live',32,dict(path='C:/'+('x'*60+'.exe'))),
                                    ('wide-errors','wide-errors',32,None),
                                    ('query-failure','live',2,dict(fault='query',error=0xffffffff)),
                                    ('binding-failure','live',2,dict(fault='missing'))]:
        captured=[];r=q.Recorder(root/label,identity(),['tiny'],dict(os.environ),root,stream_cap=512)
        class Tree:
            def diagnostic(self,deadline):
                value,_,_=model(mode,count,options);return value
            def terminate(self):pass
            def active(self):return []
            def close(self):pass
        def owner_factory(argv,cwd,env,stdin,stdout,stderr,timeout,cap,**options):
            owner=object.__new__(original);owner.started=time.monotonic();owner.deadline=owner.started+timeout;owner.scan_deadline=owner.deadline
            owner.paths=[Path(stdout),Path(stderr)]
            for path in owner.paths:path.write_bytes(b'')
            owner.proc=SimpleNamespace(pid=17,poll=lambda:0,stdout=None,stderr=None);owner.tree=Tree();owner.readers=[]
            owner.result=None;owner.stable=False;owner.locked=False;owner.errors=[];owner.overflow=q.threading.Event();owner.job_diagnostic=None
            original._end(owner,'lingering-descendant');captured.append(owner);return owner
        with patch.object(q,'OwnedChild',owner_factory):
            expect_failure('image-recorder-'+label,lambda:r.run('tiny',[sys.executable,'-c','pass'],3),'lingering-descendant',record=False)
        raw=(r.root/'stages/tiny/result.json').read_bytes();record=json.loads(raw);owner=captured[0]
        check(record['classification']=='lingering-descendant' and record['ownership']==owner.result and
              owner.result['cleanup_ok'] and owner.result['stable'],'image owner/Recorder propagation')
        frozen=copy.deepcopy(owner.result);expect_failure('image-owner-repeat-'+label,lambda:owner.wait(),'lingering-descendant',record=False)
        check(owner.result==frozen,'image failure changed on repeated wait')
        field=record['ownership']['job_diagnostic'];sampled=field['image_sample']
        for newline in ('\n','\r\n'):
            image_bytes=(json.dumps(sampled,sort_keys=True,indent=2)+'\n').replace('\n',newline).encode()
            diagnostic_bytes=(json.dumps(field,sort_keys=True,indent=2)+'\n').replace('\n',newline).encode()
            stage_bytes=(json.dumps(record,sort_keys=True,indent=2)+'\n').replace('\n',newline).encode()
            check(len(image_bytes)<=512 and len(diagnostic_bytes)<=8192 and len(stage_bytes)<=16384,'image full layout cap')
        packet=q.failure_diagnostics(r.root,r.root/'failure.json',identity(),['tiny'],['tiny'],'lingering-descendant')
        retained=packet['files']['stages/tiny/result.json']
        check(not retained['truncated'] and base64.b64decode(retained['data'])==raw and packet['passed'] is False and
              (r.root/'failure.json').stat().st_size<=262144,'image complete failed packet retention')
        RESULTS.append(dict(name='image-actual-owner-recorder-retention-'+label,passed=True))


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
        check(not q._windows_image_eligible(dict(live,root=True)) and not q._windows_image_eligible(dict(exited,root=True)),
              'native pinned root image eligibility')
        RESULTS.append(dict(name='windows-genuine-root-signaled259-observation-and-root-ineligibility',passed=True))
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
                partial=q.failure_diagnostics(recorder.root,recorder.root/'failure.json',identity(),['tiny'],['tiny'],ValueError(expected))
            check(row['classification']==expected and partial['passed'] is False and
                  {k:v['status'] for k,v in partial['files'].items()}=={'stages/tiny/result.json':'unreadable','stages/tiny/stdout.bin':'missing','stages/tiny/stderr.bin':'missing'},'collector failure erased primary')
            RESULTS.append(dict(name='root-recorder-collector-unavailable',passed=True))


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
                sample=diagnostic.get('image_sample',{});index=sample.get('member_index')
                check(type(index) is int and 0<=index<len(diagnostic['members']) and diagnostic['members'][index]['pid']==pid and
                      sample.get('status')=='sampled' and sample.get('race')=='non_atomic' and
                      type(sample.get('basename')) is str and sample['basename'].casefold()==Path(sys.executable).name.casefold() and
                      sample.get('basename_sha256')==hashlib.sha256(sample['basename'].encode('utf-16le')).hexdigest(),
                      'descendant native Windows basename comparison/hash missing')
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
                with patch.object(q._WindowsTree,'sample_image',side_effect=ValueError('unexpected image query')) as image_query:
                    run(kind,'unrelated-sentinel','pass')
                check(sentinel.poll() is None and image_query.call_count==0,'private Windows job affected or queried unrelated sentinel')
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


def synthetic_windows_reports(root,ident,locations,bd):
    """Schema fixture only; none of these bytes are native execution."""
    import ntpath
    if ident['job_key']=='windows-msvc':
        objects=q.phase_seed('objects',ident);objects.update(state='ready',produced=[dict(name=n,**bd) for n in q.PRODUCTION_OBJECTS],
            consumed=list(q.CONSUMED_OBJECTS),production_executable=bd)
        q.write_phase(root/q.PHASE_REPORTS['objects'][0],'objects',objects,ident)
        build=q.phase_seed('build-context',ident);build.update(state='ready',vcvars=dict(path=q.path_identity('C:/fixture/vcvars'),file=bd),
            runtime_prefix=dict(present=False,identity=None),production_objects=q.descriptor(root/q.PHASE_REPORTS['objects'][0]),production_executable=bd,canonical_binary=bd)
        q.write_phase(root/q.PHASE_REPORTS['build-context'][0],'build-context',build,ident)
        run=q.phase_seed('run-context',ident);run.update(state='ready',build_context=q.descriptor(root/q.PHASE_REPORTS['build-context'][0]),
            canonical_binary=bd,context_matched=True,test_exit=0)
        q.write_phase(root/q.PHASE_REPORTS['run-context'][0],'run-context',run,ident)
    else:
        report=q.phase_seed('configure',ident);report.update(state='ready',source_location=q.path_identity(locations['source']),
            build_location=q.path_identity(locations['build']),overlay_location=q.path_identity(ntpath.join(locations['source'],'.ci','mcp_directory_search_targets.cmake')),
            generator='vs17-2022',checks=dict.fromkeys(q.CONFIGURE_CHECKS,True),files={n:bd for n in q.CONFIGURE_FILES})
        q.write_phase(root/q.PHASE_REPORTS['configure'][0],'configure',report,ident)
        for mode in ('normal','optimized'):q.dump(root/'reports'/('winhttp-'+mode+'.json'),dict(result='PASS',native_windows=True,
            checks=[True],check_count=1,source_commit=ident['commit'],probe_sha256=bd['sha256']))
    for mode in ('normal','optimized'):
        path=root/'reports'/('mcp_directory_search-'+mode)/'RESULT.json';report=json.loads(path.read_bytes())
        report['http']=dict(required=True,status='passed',profiles=['full','memory'],authentication='synthetic fixture')
        provider=dict(required=True,status='passed',profiles=['full','memory'],transports=['stdio','http'],
            negative_query_count=108,negative_request_count=0,positive_request_count=8,batches=[],requests=[])
        for profile in ('full','memory'):
            for transport in ('stdio','http'):
                prefix=profile+'-'+transport;positives=[]
                for slot in range(2):
                    index=len(provider['requests']);query=prefix+'-positive-'+str(slot)
                    wire=b'POST / HTTP/1.1\r\n\r\n'+json.dumps({'input':[query]}).encode();response=b'HTTP/1.1 200 OK\r\n\r\n{}'
                    capture=dict(query=query,status='completed')
                    for key,raw in [('request',wire),('response',response)]:
                        leaf='raw/provider-'+str(index)+'-'+key+'.bin';(path.parent/leaf).write_bytes(raw)
                        capture[key]=dict(path=leaf,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
                    provider['requests'].append(capture);positives.append(dict(query=query,record_index=index,provider_requests=1))
                provider['batches'].append(dict(profile=profile,transport=transport,status='passed',negative_query_count=27,negative_request_count=0,
                    negative_cases=[dict(query=prefix+'-negative-'+str(i),expected_error='synthetic',provider_requests=0) for i in range(27)],positive_controls=positives))
        report['provider_http']=provider;q.dump(path,report)


def tiny_bundle(root,job="linux-cmake"):
    """Synthetic complete approved-source/command fixture, not native execution."""
    root.mkdir();paths=sorted(guard.ALLOW);nodes={};rows={};inventory=b''
    for path in paths:
        data=(guard.checkout_bytes((q.ROOT/path).read_bytes(),guard.WRAPPERS[path],os.name=='nt') if path in guard.WRAPPERS else
              ('synthetic source fixture only: '+path+'\n').encode('utf-8'));oid=guard.blob(data)
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
    tree=tree_hash(nodes);ident=dict(identity(tree),job_key=job,job_label=job)
    source=dict(passed=True,commit=ident['commit'],tree=tree,base=guard.BASE,base_tree=guard.BASE_TREE,
                parent=guard.CORRECTION_PARENT,parent_tree=guard.CORRECTION_PARENT_TREE,correction_changed=sorted(guard.CORRECTION_PATHS),precommit=False,
                inventory_sha256=hashlib.sha256(inventory).hexdigest(),changed=paths,changed_files=rows,dependency_sha256={})
    q.dump(root/'reports/source-before.json',source);q.dump(root/'reports/source-after.json',source)
    (root/'source/tree-inventory.bin').write_bytes(inventory);q.dump(root/'source/dependencies.json',{})
    (root/'binaries').mkdir();binary=root/'binaries'/('qbrain.exe' if job.startswith('windows') else 'qbrain');binary.write_bytes(b'fixture binary only')
    bd=q.descriptor(binary);required=q.required_stages(ident['job_key'])
    locations=dict(source='/fixture/source',build='/fixture/build',output='/fixture/evidence',python='/fixture/python')
    if job.startswith('windows'):locations=dict(source='C:\\source',build='C:\\build',output='C:\\evidence',python='C:\\python.exe')
    specs=q.stage_contract(ident,locations)
    prod='C:\\source\\build\\cl\\qbrain.exe' if job=='windows-msvc' else 'C:\\build\\Debug\\qbrain.exe' if job.startswith('windows') else '/fixture/build/qbrain'
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
    if job.startswith('windows'):synthetic_windows_reports(root,ident,locations,bd)
    (root/'reports/ctest.xml').write_text('<testsuite>'+''.join('<testcase name="'+name+'"/>' for name in q.TESTS)+'</testsuite>')
    for name in required:
        spec=specs[name];folder=root/'stages'/name;folder.mkdir(parents=True)
        stdout=b'fixture-only\n'
        if name in ('direct-tests-run','canonical-run','canonical-groups'):
            names=q.re.findall(r'\{"([^"]+)",\s*test_\w+\}',(q.ROOT/'tests/test_main.cpp').read_text())
            log=''.join('[PASS] '+n+'\n' for n in names);groups=q.native_groups((q.ROOT/'tests/test_main.cpp').read_text(),log)
            stdout=json.dumps(groups).encode() if name=='canonical-groups' else log.encode()
        elif name=='ctest-inventory':stdout=json.dumps(dict(tests=[dict(name=n) for n in q.TESTS])).encode()
        elif name=='ctest-completeness':stdout=json.dumps(list(q.TESTS)).encode()
        elif name.startswith('selftest-'):stdout=json.dumps(dict(passed=True,python_optimized=name.endswith('optimized'),linux_reader_backend='native-children',controls=[dict(name=n,passed=True) for n in (sorted(q.WINDOWS_PHASE_CONTROL_NAMES) if job.startswith('windows') else ['fixture'])])).encode()
        (folder/'stdout.bin').write_bytes(stdout);(folder/'stderr.bin').write_bytes(b'')
        q.dump(folder/'result.json',dict(schema='qbrain-n49d-stage-v2',completion_policy=spec['completion_policy'],phase_window=None,
            stream_limit=8*q.MIB,runtime_options={},available_reports={p:q.descriptor(root/p) for p in spec['reports']},elapsed_seconds=.1,name=name,identity=ident,argv=spec['argv'],timeout_seconds=spec['timeout_seconds'],cwd=locations['source'],exit=0,classification='passed',ownership=dict(classification='passed',cleanup_ok=True,cleanup_error=None,owned_tree_empty=True,root_pid=17,
            process_backend='linux-children-pidfd-subreaper',elapsed_seconds=.01,stable=True,readers_done=True,exit=0,
            stdout=q.descriptor(folder/'stdout.bin'),stderr=q.descriptor(folder/'stderr.bin')),
            stdout=q.descriptor(folder/'stdout.bin'),stderr=q.descriptor(folder/'stderr.bin'),requested_reports=spec['reports'],reports={p:q.descriptor(root/p) for p in spec['reports']},
            binaries_before={p:bd for p in spec['binaries_before']},binaries_after={p:bd for p in spec['binaries_after']}))
    for name in required:
        path=root/'stages'/name/'result.json';row=json.loads(path.read_bytes())
        if job.startswith('windows'):row['ownership']['process_backend']='windows-private-job'
        if specs[name]['completion_policy']=='trusted-build-v1':
            owner=build_owner_fixture();owner.update(stdout=row['stdout'],stderr=row['stderr']);row['ownership']=owner
        if name in ('direct-tests-build','direct-tests-run'):
            start=0 if name=='direct-tests-build' else 200000
            row['phase_window']=dict(phase=name,start_us=start,effective_deadline_us=1200000000 if start==0 else 600200000,pair_budget_us=1800000000)
        q.dump(path,row)
    top_reports={}
    if job=='windows-msvc':
        pair=q.phase_seed('pair',ident);pair.update(state='complete',finalize_begin_us=400000,
            build=dict(stage='direct-tests-build',start_us=0,end_us=100000,effective_deadline_us=1200000000,result=q.descriptor(root/'stages/direct-tests-build/result.json')),
            run=dict(stage='direct-tests-run',start_us=200000,end_us=300000,effective_deadline_us=600200000,result=q.descriptor(root/'stages/direct-tests-run/result.json')))
        desc=q.write_phase(root/q.PHASE_REPORTS['pair'][0],'pair',pair,ident)
        top_reports[q.PHASE_REPORTS['pair'][0]]=dict(**desc,finalized_us=400001)
    binding=q.descriptor(root/'reports/source-before.json')
    q.dump(root/'qualification.json',dict(schema='qbrain-n49d-qualification-v2',passed=True,identity=ident,reports=top_reports,
        native_http='required-and-executed' if job.startswith('windows') else 'not-applicable-non-Windows-stub',acceptance='native evidence only; independent outcome acceptance pending',
        required=required,stages=required,locations=locations,
        source_before=binding,source_after=binding,binaries={p:bd for spec in specs.values() for p in spec['binaries_after']},
        retained_binaries={prod:dict(path='binaries/'+binary.name,**bd)}))
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
            stage_path='stages/'+label+'/result.json';stage=json.loads(packet[stage_path]);stage['reports'][report]=desc;stage['available_reports'][report]=desc
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
    def previous_anchor(binding,packet):
        binding['parent']=guard.LAST_CORRECTION_PARENT;binding['parent_tree']=guard.LAST_CORRECTION_PARENT_TREE
    packet=source_packet(previous_anchor);ancestry_packets.append(('prior-correction-pair',packet))
    expect_failure('producer-rehashed-prior-correction-pair',lambda:q.validate_recordings(packet.__getitem__,ident,files=packet),'source/candidate binding mismatch')
    packet=source_packet(lambda binding,packet:binding.update(correction_changed=sorted(frozenset(['.ci/check_n49d_sources.py', '.ci/run_n49d_qualification.py', '.ci/test_n49d_source_contract.py', '.github/workflows/n49d-mcp-directory-search.yml', 'scripts/build-cl.ps1', 'scripts/build-tests-cl.ps1', 'docs/nodes/N49D-PLAN.md', 'docs/nodes/N49D-PLAN-AUDIT.md', 'docs/nodes/N49D-HARD-AUDIT.md', 'docs/nodes/n49d-evidence/RESULT.json', 'docs/nodes/n49d-evidence/SOURCE-MANIFEST.json']))))
    ancestry_packets.append(('published-eleven-path-correction',packet))
    expect_failure('producer-rehashed-published-eleven-path-correction',lambda:q.validate_recordings(packet.__getitem__,ident,files=packet),'source/candidate binding mismatch')
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


def phase_identity(job='windows-msvc'):
    return dict(identity(),job_key=job,job_label=job)


def build_owner_fixture():
    d=dict(size=0,sha256=hashlib.sha256(b'').hexdigest())
    proof=dict(schema='qbrain-n49d-build-completion-v1',policy='trusted-build-v1',state='complete',reason=None,
        root_exit=0,root_observed_us=1,teardown_requested=False,termination_requested_us=None,termination_succeeded=None,
        empty_observed_us=2,close_attempted_us=3,close_returned_us=4,streams_finalized_us=5,success_deadline_us=3000000,
        close_attempted=True,close_returned=True,close_in_budget=True)
    return dict(classification='build-completed',exit=0,process_backend='windows-private-job',root_pid=17,
        owned_tree_empty=True,cleanup_ok=True,cleanup_error=None,stable=True,readers_done=True,elapsed_seconds=.001,
        stdout=d,stderr=d,build_completion=proof)


def phase_report_controls(root):
    root.mkdir();ident=phase_identity();source=root/'source';objects=source/'build/cl/obj';objects.mkdir(parents=True)
    for name in q.PRODUCTION_OBJECTS:(objects/name).write_bytes(('object '+name).encode())
    (objects.parent/'qbrain.exe').write_bytes(b'production fixture')
    (objects.parent/'qbrain_tests.exe').write_bytes(b'canonical fixture')
    generated=q.object_report(source,ident)
    build=q.phase_seed('build-context',ident);build.update(state='ready',vcvars=dict(path=q.path_identity('C:/vcvars'),file=dict(size=1,sha256='a'*64)),
        runtime_prefix=dict(present=False,identity=None),production_objects=dict(size=1,sha256='b'*64),
        production_executable=generated['production_executable'],canonical_binary=q.descriptor(objects.parent/'qbrain_tests.exe'))
    run=q.phase_seed('run-context',ident);run.update(state='ready',build_context=dict(size=1,sha256='c'*64),
        canonical_binary=build['canonical_binary'],context_matched=True,test_exit=0)
    samples={'objects':generated,'build-context':build,'run-context':run}
    for role,value in samples.items():
        for newline in ('LF','CRLF'):
            raw=q.canonical_phase_bytes(value)
            if newline=='CRLF':raw=raw.replace(b'\n',b'\r\n')
            control('phase-parser-valid-'+role+'-'+newline,lambda raw=raw,role=role,value=value:
                check(q.read_phase_bytes(raw,role,ident,True)==value,'phase parser roundtrip'))
        for state in ('prepared','failed'):
            partial=q.phase_seed(role,ident)
            if state=='failed':partial.update(state=state,failure=q.PHASE_FAILURES[role].split()[0])
            control('phase-parser-partial-'+role+'-'+state,lambda partial=partial,role=role:
                q.read_phase_bytes(q.canonical_phase_bytes(partial),role,ident))
            expect_failure('phase-partial-not-ready-'+role+'-'+state,
                lambda partial=partial,role=role:q.phase_report(role,partial,ident,True),'phase report not ready')
    valid=q.canonical_phase_bytes(run)
    cases={'duplicate':valid.replace(b'"mode":',b'"mode":"run-only","mode":'),
        'case-key':valid.replace(b'"mode":',b'"Mode":'),'unknown':valid.replace(b'{',b'{"extra":null,',1),
        'bom':b'\xef\xbb\xbf'+valid,'unicode':valid.replace(b'run-only',b'run-onl\xc3\xa9'),
        'escape':valid.replace(b'run-only',b'run\\u002donly'),'missing-newline':valid[:-1],
        'extra-newline':valid+b'\n','space':b' '+valid,'mixed-newline':valid[:-1]+b'\r\r\n',
        'key-order':json.dumps(run,separators=(',',':')).encode()+b'\n',
        'bool-int':valid.replace(b'"test_exit":0',b'"test_exit":false'),
        'float':valid.replace(b'"test_exit":0',b'"test_exit":0.0'),
        'exponent':valid.replace(b'"test_exit":0',b'"test_exit":0e0'),
        'negative':valid.replace(b'"test_exit":0',b'"test_exit":-1'),
        'large-int':valid.replace(b'"test_exit":0',b'"test_exit":9007199254740992'),
        'uppercase-hash':valid.replace(b'c'*64,b'C'*64),
        'case-schema':valid.replace(b'qbrain-n49d',b'QBRAIN-n49d'),
        'case-state':valid.replace(b'"ready"',b'"READY"'),
        'depth':b'['*7+b'0'+b']'*7+b'\n','containers':b'['+b','.join([b'{}']*257)+b']\n',
        'numeric-token':valid.replace(b'"test_exit":0',b'"test_exit":12345678901234567'),
        'string-token':valid.replace(b'"run-only"',b'"'+b'x'*129+b'"'),
        'cap':b'x'*2049,'case-collision':valid.replace(b'"mode":',b'"Mode":"run-only","mode":')}
    for label,raw in cases.items():
        expect_failure('phase-parser-reject-'+label,lambda raw=raw:q.read_phase_bytes(raw,'run-context',ident,True))
    for role,field,bad in [('objects','consumed',[]),('objects','produced',generated['produced'][:-1]),
        ('build-context','vcvars',None),('build-context','runtime_prefix',dict(present=False,identity=q.path_identity('x'))),
        ('run-context','context_matched',1),('run-context','test_exit',259)]:
        changed=copy.deepcopy(samples[role]);changed[field]=bad
        expect_failure('phase-semantic-'+role+'-'+field,lambda changed=changed,role=role:q.phase_report(role,changed,ident,True))
    original=(objects/q.CONSUMED_OBJECTS[0]).read_bytes();(objects/q.CONSUMED_OBJECTS[0]).write_bytes(b'changed')
    expect_failure('phase-real-object-mutation',lambda:q.object_report(source,ident,generated),'production object continuity mismatch')
    (objects/q.CONSUMED_OBJECTS[0]).write_bytes(original)
    control('phase-real-object-match',lambda:q.object_report(source,ident,generated))
    absent=objects/q.PRODUCTION_OBJECTS[0];saved=absent.read_bytes();absent.write_bytes(b'')
    expect_failure('phase-real-empty-object',lambda:q.object_report(source,ident),'fixed regular file required');absent.write_bytes(saved)
    # Actual BuildOnly observation promotion, with a real changed canonical leaf.
    from types import SimpleNamespace
    evidence=root/'evidence';rec=SimpleNamespace(root=evidence,cwd=source,identity=ident)
    q.write_phase(evidence/q.PHASE_REPORTS['objects'][0],'objects',generated,ident)
    build['production_objects']=q.descriptor(evidence/q.PHASE_REPORTS['objects'][0])
    for label,observed in [('matching',build['canonical_binary']),('missing',None),('changed',dict(size=1,sha256='d'*64))]:
        prepared=copy.deepcopy(build);prepared.update(state='prepared',canonical_binary=observed)
        q.write_phase(evidence/q.PHASE_REPORTS['build-context'][0],'build-context',prepared,ident)
        if label=='matching':
            q.finalize_test_build(rec,time.monotonic()+3)
            check(q._read_phase_file(rec,'build-context',True)['canonical_binary']==observed,'build promotion lost observation')
            RESULTS.append(dict(name='phase-actual-build-observation-matching',passed=True))
        else:expect_failure('phase-actual-build-observation-'+label,lambda:q.finalize_test_build(rec,time.monotonic()+3),
                            'copied binary observation '+('missing' if label=='missing' else 'mismatch'))
    prepared=copy.deepcopy(build);prepared['state']='prepared'
    q.write_phase(evidence/q.PHASE_REPORTS['build-context'][0],'build-context',prepared,ident)
    canonical=objects.parent/'qbrain_tests.exe';old=canonical.read_bytes();canonical.write_bytes(old+b' changed after observation')
    expect_failure('phase-actual-post-observation-file-change',lambda:q.finalize_test_build(rec,time.monotonic()+3),'copied binary observation mismatch')
    canonical.write_bytes(old)
    # The bounded readiness producer reads only newly generated tiny cache/project files.
    configured=root/'configured';configured.mkdir()
    locations=dict(source='C:\\source',build=str(configured),output='C:\\evidence',python='C:\\python.exe')
    cache_lines=['CMAKE_HOME_DIRECTORY:INTERNAL=C:\\source','CMAKE_CACHEFILE_DIR:INTERNAL='+str(configured),
        'CMAKE_PROJECT_NAME:STATIC=qbrain','CMAKE_GENERATOR:INTERNAL=Visual Studio 17 2022',
        'CMAKE_BUILD_TYPE:STRING=Debug','CMAKE_CONFIGURATION_TYPES:STRING=Debug;Release','QBRAIN_WITH_PG:BOOL=OFF',
        'CMAKE_PROJECT_qbrain_INCLUDE:FILEPATH=C:\\source\\.ci\\mcp_directory_search_targets.cmake']
    cache=('\n'.join(cache_lines)+'\n').encode()
    for name in q.CONFIGURE_FILES:(configured/name).write_bytes(cache if name=='CMakeCache.txt' else b'generated fixture')
    cmake=phase_identity('windows-cmake')
    ready=q.configure_report(locations,cmake)
    for newline in ('LF','CRLF'):
        raw=q.canonical_phase_bytes(ready);raw=raw if newline=='LF' else raw.replace(b'\n',b'\r\n')
        control('phase-configure-canonical-'+newline,lambda raw=raw:q.read_phase_bytes(raw,'configure',cmake,True))
    mutations={'duplicate':cache+cache_lines[0].encode()+b'\n','missing':b'\n'.join(cache.splitlines()[1:])+b'\n',
        'type':cache.replace(b'PROJECT_NAME:STATIC',b'PROJECT_NAME:BOOL'),
        'generator':cache.replace(b'Visual Studio 17 2022',b'Ninja'),'debug':cache.replace(b'BUILD_TYPE:STRING=Debug',b'BUILD_TYPE:STRING=Release'),
        'config-duplicate':cache.replace(b'Debug;Release',b'Debug;Debug'),'pg':cache.replace(b'BOOL=OFF',b'BOOL=ON'),
        'path':cache.replace(b'INTERNAL=C:\\source',b'INTERNAL=C:\\other'),'line-cap':cache+b'x'*16385+b'\n',
        'line-count':cache+b'\n'*4097}
    for label,raw in mutations.items():
        (configured/'CMakeCache.txt').write_bytes(raw)
        expect_failure('phase-configure-producer-'+label,lambda:q.configure_report(locations,cmake))
    (configured/'CMakeCache.txt').write_bytes(cache)
    target=configured/'qbrain.vcxproj';target.write_bytes(b'')
    expect_failure('phase-configure-empty-generated-file',lambda:q.configure_report(locations,cmake),'fixed regular file required')
    target.write_bytes(b'generated fixture')
    rec=SimpleNamespace(root=root/'configure-evidence',locations=locations,identity=cmake)
    q.write_phase(rec.root/q.PHASE_REPORTS['configure'][0],'configure',ready,cmake)
    control('phase-configure-handoff-match',lambda:q.prepare_cmake_build(rec,time.monotonic()+3))
    target.write_bytes(b'changed generated file')
    expect_failure('phase-configure-handoff-mutation',lambda:q.prepare_cmake_build(rec,time.monotonic()+3),'configure handoff changed')
    owner=build_owner_fixture();control('phase-owner-natural-proof',lambda:q.validate_build_proof(owner))
    terminated=copy.deepcopy(owner);terminated['build_completion'].update(teardown_requested=True,termination_requested_us=1,termination_succeeded=True)
    control('phase-owner-termination-proof',lambda:q.validate_build_proof(terminated))
    for field in q.BUILD_PROOF_KEYS:
        broken=copy.deepcopy(owner);del broken['build_completion'][field]
        expect_failure('phase-owner-missing-'+field,lambda broken=broken:q.validate_build_proof(broken),'build completion proof keys')
    for field,value in [('root_exit',False),('root_exit',259),('close_returned',False),('state','failed'),
                        ('success_deadline_us',5),('termination_succeeded',True),('root_observed_us',4),('empty_observed_us',4)]:
        broken=copy.deepcopy(owner);broken['build_completion'][field]=value
        expect_failure('phase-owner-false-'+field+'-'+str(value),lambda broken=broken:q.validate_build_proof(broken))
    for field,value in [('classification','passed'),('classification','stopped'),('exit',259),('owned_tree_empty',False),
                        ('process_backend','linux-children-pidfd-subreaper'),('root_pid',False),('job_diagnostic',{})]:
        broken=copy.deepcopy(owner);broken[field]=value
        expect_failure('phase-owner-substitute-'+field+'-'+str(value),lambda broken=broken:q.validate_build_proof(broken))
    return samples


def phase_pair_controls(root):
    from types import SimpleNamespace
    root.mkdir();ident=phase_identity();clock=[100.]
    def make(name):
        rec=SimpleNamespace(root=root/name,identity=ident,sealed={},qualification_reports={})
        return rec,q.DirectTestPair(rec)
    def complete(rec,pair):
        b=pair.phase('direct-tests-build');clock[0]+=1
        rec.sealed['direct-tests-build']=dict(result=dict(size=1,sha256='a'*64),ended=clock[0]);pair.sealed('direct-tests-build')
        r=pair.phase('direct-tests-run');clock[0]+=1
        rec.sealed['direct-tests-run']=dict(result=dict(size=1,sha256='b'*64),ended=clock[0]);pair.sealed('direct-tests-run')
        return b,r
    with patch.object(q.time,'monotonic',side_effect=lambda:clock[0]):
        rec,pair=make('valid');b,r=complete(rec,pair);binding=pair.finish()
        check(pair.finish() is binding and rec.qualification_reports[q.PHASE_REPORTS['pair'][0]] is binding,'pair cached binding')
        check(b['window']['start_us']==0 and b['window']['effective_deadline_us']==1200000000 and
              r['window']['effective_deadline_us']==601000000,'pair window budgets')
        RESULTS.append(dict(name='phase-pair-real-publication-and-cache',passed=True))
        for label,kind in [('equal','equal'),('after','after'),('write-error','write'),('readback-error','readback')]:
            clock[0]=100.;rec,pair=make(label);complete(rec,pair);real=q.write_phase;calls=[]
            def publish(*args,**kwargs):
                calls.append('write')
                if kind=='write':raise OSError('fixture publication failure')
                result=real(*args,**kwargs)
                if kind=='readback':raise OSError('fixture readback failure')
                clock[0]=pair.deadline+(0 if kind=='equal' else .01);return result
            with patch.object(q,'write_phase',publish):
                expected='pair-report-unavailable' if kind in ('write','readback') else 'pair-finalization-timeout'
                expect_failure('phase-pair-'+label,lambda:pair.finish(),expected)
                first=copy.deepcopy(pair.value);expect_failure('phase-pair-permanent-'+label,lambda:pair.finish(),expected)
            check(calls==['write'] and pair.result is None and pair.failure==expected and pair.value==first and
                  not rec.qualification_reports,'failed pair was renewed')
        clock[0]=100.;rec,pair=make('failed-build');pair.fail('build-failed')
        expect_failure('phase-pair-no-run-after-build-failure',lambda:pair.phase('direct-tests-run'),'pair already terminal')
        clock[0]=100.;rec,pair=make('handoff');b=pair.phase('direct-tests-build');clock[0]=1300
        rec.sealed['direct-tests-build']=dict(result=dict(size=1,sha256='a'*64),ended=1300)
        expect_failure('phase-build-equal-deadline',lambda:pair.sealed('direct-tests-build'),'pair phase sealing deadline')


def build_lifecycle_controls(root):
    """Actual owner methods with finite API models; Windows runs stay separate."""
    from types import SimpleNamespace
    root.mkdir();clock=[100.]
    def run(label,alive=False,exit_code=0,fault=None,method='build'):
        folder=root/label;folder.mkdir();events=[];state=dict(alive=alive,shifted=False)
        owner=object.__new__(q.OwnedChild)
        owner.started=100.;owner.deadline=103.;owner.scan_deadline=103.
        owner.completion_policy='strict-v1' if method=='strict' else 'trusted-build-v1'
        owner.paths=[folder/'stdout',folder/'stderr'];owner.readers=[];owner.errors=[];owner.overflow=q.threading.Event()
        owner.result=None;owner.stable=False;owner.locked=False;owner.job_diagnostic=None
        for path in owner.paths:path.write_bytes(b'fixture streams')
        owner.build_proof=None
        if method!='strict':
            owner.build_proof=dict.fromkeys(q.BUILD_PROOF_KEYS)
            owner.build_proof.update(schema='qbrain-n49d-build-completion-v1',policy='trusted-build-v1',state='failed',
                reason='root-unavailable',success_deadline_us=3000000,teardown_requested=False,
                close_attempted=False,close_returned=False,close_in_budget=False)
        def poll():
            events.append('poll')
            if fault=='poll':raise OSError('poll-fixture')
            if fault=='null-root':clock[0]+=.7;return None
            if fault in ('equal','after') and not state['shifted']:
                state['shifted']=True;clock[0]=103.+(.01 if fault=='after' else 0);events.append('poll-exhausted')
            return exit_code
        class Tree:
            def active(self):
                events.append('active')
                if fault=='accounting':raise OSError('accounting-fixture')
                return [17] if state['alive'] else []
            def terminate(self):
                events.append('terminate')
                if fault=='terminate':raise OSError('termination-fixture')
                state['alive']=False
                if fault=='termination-deadline':clock[0]=103.
            def close(self):
                events.append('close')
                if fault=='close':raise OSError('close-fixture')
                if fault=='late-close':clock[0]=103.
            def diagnostic(self,*args):events.append('diagnostic');raise AssertionError('build eligibility diagnostic')
        owner.proc=SimpleNamespace(pid=17,poll=poll,stdout=None,stderr=None);owner.tree=Tree()
        if fault=='output':owner.overflow.set()
        if fault=='reader':owner.errors=['reader-fixture']
        real=q.descriptor;validator=q.validate_build_proof
        def verify(value):
            result=validator(value)
            if fault in ('proof-equal','proof-after'):clock[0]=103.+(.01 if fault=='proof-after' else 0)
            return result
        def describe(path):
            events.append('hash')
            if fault=='hash':raise OSError('hash-fixture')
            if fault=='hash-deadline':clock[0]=103.
            return real(path)
        clock[0]=100.001
        with patch.object(q.time,'monotonic',side_effect=lambda:clock[0]),patch.object(q,'os',SimpleNamespace(name='nt')),patch.object(q,'descriptor',describe),patch.object(q,'validate_build_proof',verify):
            try:value=owner.wait() if method=='strict' else owner._end() if method=='late' else owner.complete_build()
            except q.OwnedChildError:value=owner.result
            check(value is owner.result and value is not None,'build terminal cache absent')
            first=copy.deepcopy(value);before=list(events)
            try:again=owner.wait() if method=='strict' else owner.complete_build()
            except q.OwnedChildError:again=owner.result
            check(again is value and value==first and events==before,'build repeat changed result')
            if method!='strict':
                expect_failure('build-repeat-wrong-strict',lambda:owner.wait(),'owned completion policy mismatch',record=False)
                expect_failure('build-repeat-wrong-http',lambda:owner.stop(),'owned completion policy mismatch',record=False)
                check(events==before,'wrong policy operated')
        if 'close' in events:check(not any(e in ('active','terminate','close','poll') for e in events[events.index('close')+1:]),'operation after close')
        if method!='strict':check('diagnostic' not in events,'build diagnostic eligibility query')
        return value,events
    for label,alive,method in [('natural',False,'build'),('child',True,'build'),('late-child',True,'late')]:
        value,events=run(label,alive,method=method);q.validate_build_proof(value)
        check(events.count('close')==1 and events.count('terminate')==int(alive) and
              value['build_completion']['teardown_requested'] is alive,'build natural/teardown facts')
        if alive:check(events.index('poll')<events.index('terminate')<events.index('close'),'build root order')
        RESULTS.append(dict(name='build-model-'+label,passed=True))
    value,_=run('strict',True,method='strict')
    check(value['classification']=='lingering-descendant' and 'build_completion' not in value,'strict became build')
    RESULTS.append(dict(name='build-strict-stays-strict',passed=True))
    for label,fault,alive,exit_code in [('nonzero',None,False,259),('poll','poll',False,0),('accounting','accounting',False,0),
        ('terminate','terminate',True,0),('termination-deadline','termination-deadline',True,0),('close','close',False,0),
        ('late-close','late-close',False,0),('hash','hash',False,0),('hash-deadline','hash-deadline',False,0),
        ('null-root','null-root',False,0),('equal','equal',False,0),('after','after',False,0),
        ('output','output',False,0),('reader','reader',False,0),('proof-equal','proof-equal',False,0),('proof-after','proof-after',False,0)]:
        value,events=run(label,alive,exit_code,fault);proof=value['build_completion']
        check(value['classification']!='build-completed' and proof['state']=='failed','failed build passed')
        check(proof['close_attempted']==('close' in events) and
              proof['close_returned']==('close' in events and fault!='close'),'failed close facts falsified')
        if label in ('hash','hash-deadline'):
            check(proof['root_exit']==0 and proof['close_attempted'] is True and proof['close_returned'] is True and
                  proof['close_in_budget'] is True,'observed close facts lost')
        if label=='termination-deadline':check(proof['termination_succeeded'] is True,'termination fact lost')
        if label in ('equal','after'):
            check(events[events.index('poll-exhausted')+1]=='terminate','expired build poll queried success tree')
        expect_failure('build-failed-proof-'+label,lambda value=value:q.validate_build_proof(value),'build proof incomplete')
        RESULTS.append(dict(name='build-failure-facts-'+label,passed=True))
    if os.name!='nt':
        case=root/'linux';case.mkdir()
        expect_failure('build-Linux-policy-denied',lambda:q.OwnedChild([sys.executable,'-c','pass'],case,dict(os.environ),
            subprocess.DEVNULL,case/'out',case/'err',3,1024,completion_policy='trusted-build-v1'),'unsupported owned completion policy')
        check(q._ACTIVE_OWNER is None and not q._OWNER_LOCK.locked(),'unsupported policy took ownership')


WRAPPER_SCHEMA='qbrain-n49d-windows-wrapper-failure-v5'
WRAPPER_PROGRESS_PATTERN=r'[NARF][NCAFIXRS][NCALMWF]'
WRAPPER_BUILD_REASONS=frozenset(('input-invalid','object-mismatch','compile-failed','binary-unavailable','storage','unknown'))
WRAPPER_PHASE04_ACTIONS=frozenset('%02d'%n for n in range(1,54))
WRAPPER_PHASE04_CATEGORIES=frozenset(('RT','MI','PB','IO','AR','OP','OT'))
WRAPPER_REASON=frozenset(('captured','owner-unavailable','owner-invalid','owner-ineligible','stream-unavailable',
    'stream-mismatch','marker-absent','marker-partial','marker-malformed','detail-unavailable','detail-limit'))
WRAPPER_MARKER_STATUS=frozenset(('valid-prefix','absent','owner-ineligible','stream-unavailable','stream-mismatch',
    'partial-line','malformed','unavailable'))
WRAPPER_CLASSIFICATIONS=frozenset(('passed','stopped','timeout','nonzero child exit','lingering-descendant',
    'cleanup-failed','capture-not-finalized','output-limit'))
WRAPPER_CLEANUP_CATEGORIES={'private job termination failed':'termination-failed',
    'private job close failed':'close-failed','owned cleanup deadline exceeded':'cleanup-deadline',
    'failed cleanup grace exceeded':'cleanup-grace'}
WRAPPER_CAPTURE_CATEGORIES=frozenset(('capture-deadline','reader-join-failed','reader-state-unavailable',
    'stdout-unavailable','stderr-unavailable','both-unavailable'))
WRAPPER_OWNER_KEYS=('classification','exit','elapsed_seconds','root_pid_recorded','cleanup_ok','owned_tree_empty',
    'readers_done','stable','cleanup_error','capture_error','stdout','stderr')


def _wrapper_markers(status='unavailable'):
    return dict(status=status,events=[],last_entered_phase=None,last_completed_phase=None,interrupted_phase=None,phase04_failure=None,build_phase_catch=None,build_progress=None,phase04_work=None)


def _wrapper_fallback():
    return dict(schema=WRAPPER_SCHEMA,site='windows-wrapper-controls',complete=False,reason='detail-unavailable',
        timeout_seconds=20,stream_limit=65536,owner=dict(status='unavailable',**{k:None for k in WRAPPER_OWNER_KEYS}),
        markers=_wrapper_markers())


def _wrapper_string(value,categories,nullable=False):
    if value is None and nullable:return dict(category='none',bytes=0,sha256=hashlib.sha256(b'').hexdigest())
    if type(value) is not str:return None
    try:raw=value.encode('utf-8')
    except UnicodeError:return None
    if len(raw)>65536:return None
    category=categories.get(value,'other') if type(categories) is dict else value if value in categories else 'other'
    return dict(category=category,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def _wrapper_stream(value):
    if (type(value) is not dict or set(value)!={'size','sha256'} or type(value['size']) is not int or
        not 0<=value['size']<=65536 or type(value['sha256']) is not str or
        q.re.fullmatch('[0-9a-f]{64}',value['sha256']) is None):return None
    return dict(size=value['size'],sha256=value['sha256'])


def _wrapper_marker_events(events,status='valid-prefix'):
    result=_wrapper_markers(status);expected=0;unfinished=None;cleanup=False
    for event in events:
        if type(event) is not str or q.re.fullmatch(r'(?:0[0-9]|1[0-9]):[BE]',event) is None:
            result['status']='malformed';break
        phase=int(event[:2]);edge=event[-1]
        if cleanup:
            legal=event=='19:E' and result['events'][-1]=='19:B'
        elif event=='19:B':
            legal=bool(result['events'])
            if legal:cleanup=True;result['interrupted_phase']=unfinished
        else:
            legal=phase<19 and event==('%02d:%s'%(expected//2,'B' if expected%2==0 else 'E'))
            if legal:expected+=1
        if not legal:result['status']='malformed';break
        result['events'].append(event)
        if edge=='B':result['last_entered_phase']=phase;unfinished=phase
        else:result['last_completed_phase']=phase;unfinished=None
    return result


def _wrapper_work_step(work,operation,edge,tick):
    # A finite phase04 prefix. Times are sampled before publication, in floor ms.
    start,began,done,ended,interrupted=work or [0,0,0,0,0]
    if tick<max(began,ended):return None
    if edge=='B':
        cleanup=(operation==41 and 3<=start<41 or operation==46 and 42<=start<46)
        if not (operation==start+1 and start==done or cleanup):return None
        if start!=done and not interrupted:interrupted=start
        return [operation,tick,done,ended,interrupted]
    if operation!=start or start==done:return None
    return [start,began,operation,tick,interrupted]


def _wrapper_work_valid(work):
    if type(work) is not list or len(work)!=5 or any(type(v) is not int for v in work):return False
    start,began,done,ended,interrupted=work
    if not (1<=start<=47 and 0<=done<=start and 0<=began<=20000 and 0<=ended<=20000):return False
    if (done==0 and ended!=0) or (began>ended if start==done else ended>began):return False
    if interrupted==0:
        return (done in (start-1,start) or start==41 and 3<=done<41 or start==46 and 42<=done<46)
    if 3<=interrupted<41:
        return (start==41 and done in (interrupted-1,41) or 42<=start<=47 and
                (done in (start-1,start) or start==46 and 41<=done<46))
    return 42<=interrupted<46 and (start==46 and done in (interrupted-1,46) or start==47 and done in (46,47))


def _wrapper_parse_markers(raw):
    check(type(raw) is bytes and len(raw)<=65536,'wrapper marker input cap')
    accepted=[];status='absent';failure=None;caught=None;progress=None;work=None
    phase04=['%02d:%s'%(p,e) for p in range(4) for e in ('B','E')]+['04:B']
    lines=raw.split(b'\n')
    for index,line in enumerate(lines):
        diagnostic=line.startswith(b'N49D_PHASE04_');build=line.startswith(b'N49D_BUILD_CATCH_')
        observed=line.startswith(b'N49D_BUILD_PROGRESS_');working=line.startswith(b'N49D_WORK_')
        if not diagnostic and not build and not observed and not working and not line.startswith(b'N49D_WRAPPER_'):continue
        if index==len(lines)-1:status='partial-line';break
        token=line[:-1] if line.endswith(b'\r') else line
        if working:
            match=q.re.fullmatch(rb'N49D_WORK_V1:(0[1-9]|[1-3][0-9]|4[0-7]):([BE]):([0-9]{5})',token)
            if match is None or accepted!=phase04 or failure is not None or caught is not None:
                status='malformed';break
            operation,edge,tick=match.groups();tick=int(tick)
            proposed=_wrapper_work_step(work,int(operation),edge.decode('ascii'),tick) if tick<=20000 else None
            if proposed is None:status='malformed';break
            work=proposed;continue
        if observed:
            match=q.re.fullmatch(('N49D_BUILD_PROGRESS_V1:'+WRAPPER_PROGRESS_PATTERN).encode(),token)
            if match is None or progress is not None or accepted!=phase04 or failure is None or failure['action']!='22':
                status='malformed';break
            progress=token[-3:].decode('ascii');continue
        if build:
            match=q.re.fullmatch(rb'N49D_BUILD_CATCH_V1:([a-z-]{1,18}):([A-Z]{2})',token)
            if match is None or caught is not None or failure is not None or accepted!=phase04:
                status='malformed';break
            reason,category=(part.decode('ascii') for part in match.groups())
            if reason not in WRAPPER_BUILD_REASONS or category not in WRAPPER_PHASE04_CATEGORIES:
                status='malformed';break
            caught=dict(reason=reason,category=category);continue
        if diagnostic:
            match=q.re.fullmatch(rb'N49D_PHASE04_V1:([0-9]{2}):([A-Z]{2})',token)
            if match is None or failure is not None or accepted!=phase04:
                status='malformed';break
            action,category=(part.decode('ascii') for part in match.groups())
            if (action not in WRAPPER_PHASE04_ACTIONS or category not in WRAPPER_PHASE04_CATEGORIES or
                caught is not None and action!='22'):
                status='malformed';break
            failure=dict(action=action,category=category);continue
        if q.re.fullmatch(rb'N49D_WRAPPER_V1:(?:0[0-9]|1[0-9]):[BE]',token) is None:
            status='malformed';break
        event=token[len(b'N49D_WRAPPER_V1:'):].decode('ascii')
        if (failure is not None or caught is not None) and event not in ('19:B','19:E'):
            status='malformed';break
        proposed=_wrapper_marker_events(accepted+[event])
        if proposed['status']=='malformed':status='malformed';break
        accepted.append(event);status='valid-prefix'
    result=_wrapper_marker_events(accepted,status)
    result['phase04_failure']=failure;result['build_phase_catch']=caught;result['build_progress']=progress;result['phase04_work']=work
    return result


def _wrapper_file_identity(value,cross_source=False):
    fields=(value.st_dev,value.st_ino,value.st_mode,value.st_size,value.st_mtime_ns,value.st_ctime_ns,
            getattr(value,'st_file_attributes',0))
    if not WRAPPER_FILE_WINDOWS:return fields
    birth=getattr(value,'st_birthtime_ns',None)
    check(type(birth) is int,'wrapper file birthtime unavailable')
    # CPython 3.12 path ctime is creation time; descriptor ctime is change time.
    # Use creation time across sources, retaining raw ctime within each source.
    return fields[:5]+(birth,)+fields[6:] if cross_source else fields+(birth,)


def _wrapper_regular(value):
    return stat.S_ISREG(value.st_mode) and not stat.S_ISLNK(value.st_mode) and not (
        getattr(value,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',1024))


def _wrapper_marker_file(root,descriptor):
    """Read only the fixed cached stderr leaf; never query or act on a process."""
    if descriptor['size']==0:
        return _wrapper_markers('absent' if descriptor['sha256']==hashlib.sha256(b'').hexdigest() else 'stream-mismatch')
    path=root/'stderr.bin'
    try:
        before=path.lstat()
        if not _wrapper_regular(before):return _wrapper_markers('stream-unavailable')
        flags=os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0)
        fd=os.open(path,flags)
        try:
            opened=os.fstat(fd)
            if not _wrapper_regular(opened) or _wrapper_file_identity(opened,True)!=_wrapper_file_identity(before,True):
                return _wrapper_markers('stream-mismatch')
            with os.fdopen(fd,'rb',buffering=0,closefd=False) as stream:raw=stream.read(65537)
            after=os.fstat(fd);path_after=path.lstat()
            if (len(raw)>65536 or len(raw)!=descriptor['size'] or hashlib.sha256(raw).hexdigest()!=descriptor['sha256'] or
                _wrapper_file_identity(after)!=_wrapper_file_identity(opened if WRAPPER_FILE_WINDOWS else before) or
                _wrapper_file_identity(path_after)!=_wrapper_file_identity(before) or not _wrapper_regular(path_after)):
                return _wrapper_markers('stream-mismatch')
        finally:os.close(fd)
        return _wrapper_parse_markers(raw)
    except (OSError,ValueError):return _wrapper_markers('stream-unavailable')


def _wrapper_failure_detail(owner,root):
    detail=_wrapper_fallback()
    if owner is None:detail['reason']='owner-unavailable';return detail
    cached=owner.result
    if type(cached) is not dict:detail['reason']='owner-unavailable';return detail
    facts=detail['owner'];facts['status']='available'
    def retain(key,value):
        facts[key]=value
        if value is None:facts['status']='partial'
    retain('classification',_wrapper_string(cached.get('classification'),WRAPPER_CLASSIFICATIONS))
    for key in ('cleanup_ok','owned_tree_empty','readers_done','stable'):
        retain(key,cached.get(key) if type(cached.get(key)) is bool else None)
    exit_code=cached.get('exit')
    if 'exit' not in cached or not (exit_code is None or type(exit_code) is int and -(2**63)<=exit_code<2**63):
        facts['status']='partial';exit_code=None
    facts['exit']=exit_code
    elapsed=cached.get('elapsed_seconds')
    retain('elapsed_seconds',elapsed if (type(elapsed) is float and math.isfinite(elapsed) and elapsed>=0) or (
        type(elapsed) is int and 0<=elapsed<2**63) else None)
    root_pid=cached.get('root_pid')
    retain('root_pid_recorded',False if 'root_pid' in cached and root_pid is None else True if (
        type(root_pid) is int and 0<root_pid<2**63) else None)
    retain('cleanup_error',_wrapper_string(cached['cleanup_error'],WRAPPER_CLEANUP_CATEGORIES,True)
        if 'cleanup_error' in cached else None)
    retain('capture_error',_wrapper_string(cached.get('capture_error'),WRAPPER_CAPTURE_CATEGORIES,True))
    for key in ('stdout','stderr'):retain(key,_wrapper_stream(cached.get(key)))
    if facts['status']!='available':detail['reason']='owner-invalid';return detail
    if not all(facts[key] is True for key in ('cleanup_ok','owned_tree_empty','readers_done','stable')):
        detail['reason']='owner-ineligible';detail['markers']=_wrapper_markers('owner-ineligible');return detail
    detail['markers']=_wrapper_marker_file(root,facts['stderr'])
    status=detail['markers']['status'];detail['complete']=status=='valid-prefix'
    detail['reason']={'valid-prefix':'captured','absent':'marker-absent','partial-line':'marker-partial',
        'malformed':'marker-malformed','stream-unavailable':'stream-unavailable','stream-mismatch':'stream-mismatch'}[status]
    return detail


def _validate_wrapper_detail(value):
    # Historical versions keep their exact keysets and meanings; observation is never inferred.
    legacy={'qbrain-n49d-windows-wrapper-failure-v1':{'phase04_failure','build_phase_catch','build_progress','phase04_work'},
            'qbrain-n49d-windows-wrapper-failure-v2':{'build_phase_catch','build_progress','phase04_work'},
            'qbrain-n49d-windows-wrapper-failure-v3':{'build_progress','phase04_work'},
            'qbrain-n49d-windows-wrapper-failure-v4':{'phase04_work'}}
    if type(value) is dict and type(value.get('schema')) is str and value['schema'] in legacy:
        missing=legacy[value['schema']];markers=value.get('markers')
        check(type(markers) is dict and set(markers)==set(_wrapper_markers())-missing,'wrapper legacy marker keys')
        converted=dict(value,schema=WRAPPER_SCHEMA,markers=dict(markers,**{key:None for key in missing}))
        _validate_wrapper_detail(converted);return value
    check(type(value) is dict and set(value)==set(_wrapper_fallback()),'wrapper detail keys')
    check(type(value['schema']) is str and value['schema']==WRAPPER_SCHEMA and
        type(value['site']) is str and value['site']=='windows-wrapper-controls' and
        type(value['complete']) is bool and type(value['reason']) is str and value['reason'] in WRAPPER_REASON and
        type(value['timeout_seconds']) is int and value['timeout_seconds']==20 and
        type(value['stream_limit']) is int and value['stream_limit']==65536,'wrapper detail constants')
    facts=value['owner'];markers=value['markers']
    check(type(facts) is dict and set(facts)=={'status',*WRAPPER_OWNER_KEYS} and
        type(facts['status']) is str and facts['status'] in ('available','partial','unavailable'),'wrapper owner keys')
    for key,categories in [('classification',WRAPPER_CLASSIFICATIONS),('cleanup_error',frozenset(WRAPPER_CLEANUP_CATEGORIES.values())|{'none'}),
                           ('capture_error',WRAPPER_CAPTURE_CATEGORIES|{'none'})]:
        summary=facts[key]
        if summary is None:continue
        check(type(summary) is dict and set(summary)=={'category','bytes','sha256'} and
            type(summary['category']) is str and summary['category'] in categories|{'other'} and
            type(summary['bytes']) is int and 0<=summary['bytes']<=65536 and
            type(summary['sha256']) is str and q.re.fullmatch('[0-9a-f]{64}',summary['sha256']) is not None,'wrapper string summary')
        if summary['category']=='none':check(summary['bytes']==0 and summary['sha256']==hashlib.sha256(b'').hexdigest(),'wrapper null summary')
    check(facts['exit'] is None or type(facts['exit']) is int and -(2**63)<=facts['exit']<2**63,'wrapper exit')
    elapsed=facts['elapsed_seconds']
    check(elapsed is None or type(elapsed) is float and math.isfinite(elapsed) and elapsed>=0 or
        type(elapsed) is int and 0<=elapsed<2**63,'wrapper elapsed')
    for key in ('root_pid_recorded','cleanup_ok','owned_tree_empty','readers_done','stable'):
        check(facts[key] is None or type(facts[key]) is bool,'wrapper boolean')
    for key in ('stdout','stderr'):check(facts[key] is None or _wrapper_stream(facts[key]) is not None,'wrapper descriptor')
    check(type(markers) is dict and set(markers)==set(_wrapper_markers()) and type(markers['status']) is str and
        markers['status'] in WRAPPER_MARKER_STATUS and type(markers['events']) is list and len(markers['events'])<=40,'wrapper markers')
    rebuilt=_wrapper_marker_events(markers['events'],markers['status'])
    failure=markers['phase04_failure']
    if failure is not None:
        check(type(failure) is dict and set(failure)=={'action','category'} and
            type(failure['action']) is str and failure['action'] in WRAPPER_PHASE04_ACTIONS and
            type(failure['category']) is str and failure['category'] in WRAPPER_PHASE04_CATEGORIES,'wrapper phase04 failure fields')
        prefix=['%02d:%s'%(p,e) for p in range(4) for e in ('B','E')]+['04:B']
        check(markers['events'][:9]==prefix and markers['events'][9:] in ([],['19:B'],['19:B','19:E']) and
            markers['status'] in ('valid-prefix','malformed','partial-line'),'wrapper phase04 failure origin')
        rebuilt['phase04_failure']=failure
    caught=markers['build_phase_catch']
    if caught is not None:
        check(type(caught) is dict and set(caught)=={'reason','category'} and
            type(caught['reason']) is str and caught['reason'] in WRAPPER_BUILD_REASONS and
            type(caught['category']) is str and caught['category'] in WRAPPER_PHASE04_CATEGORIES,'wrapper build catch fields')
        prefix=['%02d:%s'%(p,e) for p in range(4) for e in ('B','E')]+['04:B']
        check(markers['events'][:9]==prefix and markers['events'][9:] in ([],['19:B'],['19:B','19:E']) and
            markers['status'] in ('valid-prefix','malformed','partial-line') and
            (failure is None or failure['action']=='22'),'wrapper build catch origin')
        rebuilt['build_phase_catch']=caught
    progress=markers['build_progress']
    if progress is not None:
        check(type(progress) is str and q.re.fullmatch(WRAPPER_PROGRESS_PATTERN,progress) is not None,
            'wrapper build progress vocabulary')
        check(failure is not None and failure['action']=='22','wrapper build progress origin')
        rebuilt['build_progress']=progress
    work=markers['phase04_work']
    if work is not None:
        prefix=['%02d:%s'%(p,e) for p in range(4) for e in ('B','E')]+['04:B']
        check(_wrapper_work_valid(work) and markers['events'][:9]==prefix and
              markers['status'] in ('valid-prefix','malformed','partial-line'),'wrapper work facts')
        rebuilt['phase04_work']=work
    check(rebuilt==markers and (markers['status']!='valid-prefix'  or bool(markers['events'])),'wrapper marker facts')
    for key in ('last_entered_phase','last_completed_phase','interrupted_phase'):
        check(markers[key] is None or type(markers[key]) is int and 0<=markers[key]<=(18 if key=='interrupted_phase' else 19),'wrapper marker phase type')
    if facts['status']=='available':
        check(all(facts[k] is not None for k in WRAPPER_OWNER_KEYS if k!='exit'),'wrapper available fields')
    if facts['status']=='unavailable':check(all(facts[k] is None for k in WRAPPER_OWNER_KEYS),'wrapper unavailable fields')
    eligible=facts['status']=='available' and all(facts[k] is True for k in ('cleanup_ok','owned_tree_empty','readers_done','stable'))
    check(value['complete'] is (eligible and markers['status']=='valid-prefix'),'wrapper evidence completeness')
    check((value['reason']=='captured') is value['complete'],'wrapper captured reason')
    return value


def _capture_wrapper_failure(error,root):
    global FAILURE_DETAIL
    if FAILURE_DETAIL is not None:return
    FAILURE_DETAIL=_wrapper_fallback()
    try:
        candidate=_wrapper_failure_detail(error.owner,root)
        _validate_wrapper_detail(candidate)
        detached=q._bounded_failure_detail(candidate,FAILURE_DETAIL,4096)
        _validate_wrapper_detail(detached)
        check(failure_equal(detached,candidate),'wrapper detached detail changed')
        for ending in ('\n','\r\n'):
            raw=(json.dumps({'failure_detail':detached},sort_keys=True,indent=2,allow_nan=False)+'\n').replace('\n',ending).encode('utf-8')
            check(len(raw)<=4096,'wrapper enclosing detail cap')
        FAILURE_DETAIL=detached
    except BaseException:pass


def _run_windows_wrapper(root,script,wrapper):
    try:
        owner=q.OwnedChild(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),'-Wrapper',str(wrapper),'-Python',sys.executable],root,dict(os.environ),subprocess.DEVNULL,root/'stdout.bin',root/'stderr.bin',20,65536)
        owner.wait()
    except q.OwnedChildError as error:
        try:_capture_wrapper_failure(error,root)
        except BaseException:pass
        raise
    check((root/'stdout.bin').read_text().strip().endswith('WRAPPER_CONTROLS_OK'),'actual wrapper API controls incomplete')

def wrapper_phase04_controls():
    """S=source binding, P=all action/category pairs, N=negative grammar,
    C=actual cached-owner caller/capture, V=closed detail and typed roundtrip.
    These are nested checks, not replacement evidence for older controls.
    """
    from types import SimpleNamespace
    global FAILURE_DETAIL
    prefix=['%02d:%s'%(p,e) for p in range(4) for e in ('B','E')]+['04:B']
    phase=lambda events,ending:b''.join(b'N49D_WRAPPER_V1:'+e.encode()+ending for e in events)
    def expected(events,status='valid-prefix',failure=None):
        value=_wrapper_marker_events(events,status);value['phase04_failure']=failure;return value
    for ending in (b'\n',b'\r\n'):
        before=phase(prefix,ending);after=phase(['19:B','19:E'],ending)
        for action in sorted(WRAPPER_PHASE04_ACTIONS):
            for category in sorted(WRAPPER_PHASE04_CATEGORIES):
                token=('N49D_PHASE04_V1:'+action+':'+category).encode()+ending
                value=_wrapper_parse_markers(before+token+after)
                check(value==expected(prefix+['19:B','19:E'],failure=dict(action=action,category=category)),'phase04 action/category parser')
        good=b'N49D_PHASE04_V1:14:RT'+ending
        first=dict(action='14',category='RT')
        cases=[
            (b'', 'absent',[],None),
            (before+after,'valid-prefix',prefix+['19:B','19:E'],None),
            (before+good,'valid-prefix',prefix,first),
            (before+good+phase(['19:B'],ending),'valid-prefix',prefix+['19:B'],first),
            (before+good+good+after,'malformed',prefix,first),
            (before+b'N49D_PHASE04_V1:53:OT'+ending+good,'malformed',prefix,dict(action='53',category='OT')),
            (good+before,'malformed',[],None),
            (phase(prefix[:-1],ending)+good,'malformed',prefix[:-1],None),
            (before+phase(['04:E'],ending)+good,'malformed',prefix+['04:E'],None),
            (before+after+good,'malformed',prefix+['19:B','19:E'],None),
            (before+good+phase(['04:E'],ending),'malformed',prefix,first),
            (before+good[:-len(ending)],'partial-line',prefix,None),
            (before+good+good[:-len(ending)],'partial-line',prefix,first),
            (before+b'N49D_PHASE04_V2:14:RT'+ending,'malformed',prefix,None),
            (before+b'N49D_PHASE04_V1:54:RT'+ending,'malformed',prefix,None),
            (before+b'N49D_PHASE04_V1:00:RT'+ending,'malformed',prefix,None),
            (before+b'N49D_PHASE04_V1:14:ZZ'+ending,'malformed',prefix,None),
            (before+b'N49D_PHASE04_V1:14:rt'+ending,'malformed',prefix,None),
            (before+b'N49D_PHASE04_V1:1:RT'+ending,'malformed',prefix,None),
            (before+good[:-len(ending)]+b' private'+ending,'malformed',prefix,None),
            (before+b'N49D_PHASE04_BAD'+ending+good,'malformed',prefix,None),
            (before+b' '+good+after,'valid-prefix',prefix+['19:B','19:E'],None),
            (before+b'private\x00\xff'+ending+good+after,'valid-prefix',prefix+['19:B','19:E'],first)]
        for raw,status,events,failure in cases:
            observed=_wrapper_parse_markers(raw)
            check(observed==expected(events,status,failure) and 'private' not in json.dumps(observed),'phase04 negative marker facts')
    model=expected(prefix+['19:B','19:E'],failure=dict(action='14',category='RT'))
    cached=dict(_detail_fixture()['ownership'],classification='nonzero child exit')
    saved=FAILURE_DETAIL
    try:
        for constructor_failure in (False,True):
            for capture_failure in (False,True):
                FAILURE_DETAIL=None;calls=[]
                class Owner:
                    @property
                    def result(self):calls.append('result');return cached
                    def wait(self):calls.append('wait');raise primary
                owner=Owner();primary=q.OwnedChildError('phase04 primary',owner)
                def construct(*args,**kwargs):
                    calls.append('construct')
                    if constructor_failure:raise primary
                    return owner
                def markers(*args):
                    calls.append('markers')
                    if capture_failure:raise RuntimeError('private-capture')
                    return copy.deepcopy(model)
                with patch.object(q,'OwnedChild',side_effect=construct),patch(__name__+'._wrapper_marker_file',side_effect=markers):
                    try:_run_windows_wrapper(Path('/fixture'),Path('/fixture/script'),Path('/fixture/wrapper'))
                    except q.OwnedChildError as caught:check(caught is primary,'phase04 actual caller primary changed')
                    else:raise ValueError('phase04 actual caller passed')
                    expected_calls=['construct']+([] if constructor_failure else ['wait'])+['result','markers']
                    check(calls==expected_calls,'phase04 actual caller extra operations')
                    first=FAILURE_DETAIL;_capture_wrapper_failure(primary,Path('/fixture'))
                    check(FAILURE_DETAIL is first and calls==expected_calls,'phase04 capture retried')
                    check(first==_wrapper_fallback() if capture_failure else first['markers']==model,'phase04 cached-owner capture')
    finally:FAILURE_DETAIL=saved
    with patch(__name__+'._wrapper_marker_file',return_value=model):
        detail=_wrapper_failure_detail(SimpleNamespace(result=cached),Path('/fixture'))
    _validate_wrapper_detail(detail)
    mutations=[lambda d:d['markers']['phase04_failure'].update(raw='private'),
        lambda d:d['markers']['phase04_failure'].pop('category'),
        lambda d:d['markers']['phase04_failure'].update(action=True),
        lambda d:d['markers']['phase04_failure'].update(action='54'),
        lambda d:d['markers']['phase04_failure'].update(category='private'),
        lambda d:d['markers'].update(events=['00:B']),
        lambda d:d['markers'].update(status='unavailable'),
        lambda d:d.update(schema='qbrain-n49d-windows-wrapper-failure-v1')]
    for mutate in mutations:
        bad=copy.deepcopy(detail);mutate(bad)
        expect_failure('phase04-detail',lambda bad=bad:_validate_wrapper_detail(bad),record=False)
    prior=_wrapper_marker_events(['00:B','00:E','01:B','19:B','19:E'])
    with patch(__name__+'._wrapper_marker_file',return_value=prior):
        old_prefix=_wrapper_failure_detail(SimpleNamespace(result=cached),Path('/fixture'))
    legacy=copy.deepcopy(old_prefix);legacy['schema']='qbrain-n49d-windows-wrapper-failure-v1'
    legacy['markers'].pop('phase04_failure');legacy['markers'].pop('build_phase_catch');legacy['markers'].pop('build_progress');legacy['markers'].pop('phase04_work')
    for form,schema in ((legacy,WRAPPER_SCHEMA),(old_prefix,'qbrain-n49d-windows-wrapper-failure-v1'),
                        (detail,'qbrain-n49d-windows-wrapper-failure-v1')):
        relabeled=copy.deepcopy(form);relabeled['schema']=schema
        expect_failure('phase04-schema-relabel',lambda relabeled=relabeled:_validate_wrapper_detail(relabeled),record=False)
    for form in (legacy,old_prefix,detail):
        before=copy.deepcopy(form);check(_validate_wrapper_detail(form) is form,'phase04 validator mutated identity')
        value=dict(passed=False,error='phase04 primary',controls=[],failure_detail=form)
        for ending in ('\n','\r\n'):
            raw=(render_selftest_failure(value)+ending).encode()
            check(failure_equal(expand_failure_v2(raw),value) and failure_equal(form,before),'phase04 old/new typed inverse')
    saved=FAILURE_DETAIL;FAILURE_DETAIL=None
    try:
        primary=q.OwnedChildError('phase04 primary',None)
        with patch.object(q,'OwnedChild',side_effect=primary),patch(__name__+'._capture_wrapper_failure',side_effect=RuntimeError('private-initialization')):
            try:_run_windows_wrapper(Path('/fixture'),Path('/fixture/script'),Path('/fixture/wrapper'))
            except q.OwnedChildError as caught:check(caught is primary and FAILURE_DETAIL is None,'phase04 optional initializer replaced primary')
            else:raise ValueError('phase04 optional initializer passed')
    finally:FAILURE_DETAIL=saved


def wrapper_build_catch_controls(body):
    """I=static insertion/source controls, P=closed grammar, N=negative cases,
    C=one cached-owner read/capture, V=legacy/current validator and typed inverse.
    Native insertion/actual-call proof is a separate later Windows control gate.
    No field identifies a callee instruction or guesses a missing statement ID.
    """
    from types import SimpleNamespace
    global FAILURE_DETAIL
    wrapper=guard.checkout_bytes((q.ROOT/'scripts/build-tests-cl.ps1').read_bytes(),
        guard.WRAPPERS['scripts/build-tests-cl.ps1'],os.name=='nt').decode('utf-8')
    start=wrapper.index('function Invoke-QbrainBuildPhase {')
    end=wrapper.index('\n\nfunction Invoke-QbrainRunPhase',start);definition=wrapper[start:end]
    check(len(definition.encode())==2883 and hashlib.sha256(definition.encode()).hexdigest()==
        'a45daee87fa8b79c2767e9ca10f458bc41ad16f325a419a2ed71a30259f323f0','build catch real function pin')
    declared=q.re.findall(r'^ \$n49dBuildCatchInsertion="(.*)" # N49D_WRAPPER_INSTRUMENTATION$',body,q.re.M)
    check(len(declared)==1,'build catch single declared insertion')
    insertion=declared[0].replace('`n','\n').replace('`$','$')
    check(len(insertion.encode())==690 and hashlib.sha256(insertion.encode()).hexdigest()==
        'd36feb146dce5418b2056b23f491651fa2375bac6d8a5160d5d7cf0c916d55e3','build catch declared observer bytes')
    check(definition.count('  } catch {\n    if ($Result.ExitCode -eq 0)')==1,'build catch original boundary')
    offset=definition.index('  } catch {')+len('  } catch {')
    instrumented=definition[:offset]+insertion+definition[offset:]
    check(instrumented[:offset]+instrumented[offset+len(insertion):]==definition,'build catch exact stripping')
    prepared=body.split('   if(-not $n49dBuildCatchPrepared){ # N49D_WRAPPER_INSTRUMENTATION\n',1)[1].split('   } # N49D_WRAPPER_INSTRUMENTATION\n',1)[0]
    check(hashlib.sha256(prepared.encode()).hexdigest()==
        'fc2237bc22269beb370d8e7111822a2ace9ca1bb9c006b61bf5876e476c0c5cd','catch preparation source')
    for original,expected in ((definition,'jpj94ob3UiKitni+6o2d/hIqOUcr5S5qHtaE5izwCX4='),(definition.replace('\n','\r\n'),'w0pJ5FJMkkZ6vB+YQMmmwrF5VDfmvpJUrZ0ISq8IZMo=')):
        place=original.index('  } catch {')+len('  } catch {')
        prepared_text=original[:place]+insertion+original[place:]
        check(prepared_text[:place]+prepared_text[place+len(insertion):]==original,'catch oracle preservation')
        check(base64.b64encode(hashlib.sha256((original+'\0'+prepared_text).encode()).digest()).decode()==expected and
            body.count("'"+expected+"'")==1,'catch prepared byte oracle')
    setup=body.split(' $n49dBuildCatchSetup={ # N49D_WRAPPER_INSTRUMENTATION\n',1)[1].split(' $null=. $n49dBuildCatchSetup # N49D_WRAPPER_INSTRUMENTATION\n',1)[0]
    check(setup.index("throw 'Catch baseline body'")<setup.index('if(-not $n49dBuildCatchPrepared)')<
        setup.index('$n49dBuildCatchPrepared=$true')<setup.index('$n49dBuildCatchConstructed='),'catch preparation guard order')
    check('}catch{$n49dPhase04Action=$null;throw} # N49D_WRAPPER_INSTRUMENTATION\n' in body,
        'new catch control failure mislabeled as original phase04 action')
    shape_helper=body.split('function Test-N49DFunctionAst(',1)[1].split("try{$n49dBuildCatchProgress=[pscustomobject]",1)[0]
    check(hashlib.sha256(('function Test-N49DFunctionAst('+shape_helper).encode()).hexdigest()==
        '4d8fda630c25f1af6fd134258c178cfa7a5a8029d6f3596e0b80f6bb11b92525','strict function AST helper bytes')
    check(body.count("if(-not (Test-N49DFunctionAst $n49dBuildCatchRollback.Ast $n49dBuildCatchOriginalAst 'Invoke-QbrainBuildPhase')){throw 'Catch baseline body'}")==1,'shared actual AST guard site')
    check(body.count("if(-not (Test-N49DFunctionAst $n49dBuildCatchAfter.ScriptBlock.Ast $n49dBuildCatchParsed[0] 'Invoke-QbrainBuildPhase')){throw 'Catch installed body'}")==1,'shared actual AST guard site')
    shape_controls=body.split("  & { # N49D_WRAPPER_INSTRUMENTATION\n   $n49dShapeSites=",1)[1].split('  $n49dPairs=@{} # N49D_WRAPPER_INSTRUMENTATION\n',1)[0]
    check(hashlib.sha256(('  & { # N49D_WRAPPER_INSTRUMENTATION\n   $n49dShapeSites='+shape_controls).encode()).hexdigest()==
        '17cc57785ca0e262d76bb9444bfe59fe828bc8324fbebb3ced13e2d1b2963338','actual AST shape guard controls')
    prefix=['%02d:%s'%(p,e) for p in range(4) for e in ('B','E')]+['04:B']
    phase=lambda events,e:b''.join(b'N49D_WRAPPER_V1:'+v.encode()+e for v in events)
    def expected(events,status='valid-prefix',caught=None,failure=None):
        value=_wrapper_marker_events(events,status)
        value.update(build_phase_catch=caught,phase04_failure=failure);return value
    check(WRAPPER_BUILD_REASONS==frozenset(('input-invalid','object-mismatch','compile-failed',
        'binary-unavailable','storage','unknown')),'build catch reason vocabulary')
    for ending in (b'\n',b'\r\n'):
        before=phase(prefix,ending);after=phase(['19:B','19:E'],ending)
        outer=b'N49D_PHASE04_V1:22:RT'+ending
        for reason in sorted(WRAPPER_BUILD_REASONS):
            for category in sorted(WRAPPER_PHASE04_CATEGORIES):
                token=('N49D_BUILD_CATCH_V1:'+reason+':'+category).encode()+ending
                fact=dict(reason=reason,category=category)
                for suffix,failure in ((b'',None),(outer,dict(action='22',category='RT'))):
                    check(_wrapper_parse_markers(before+token+suffix+after)==expected(prefix+['19:B','19:E'],
                        caught=fact,failure=failure),'build catch independent original/outer fields')
        good=b'N49D_BUILD_CATCH_V1:compile-failed:IO'+ending
        first=dict(reason='compile-failed',category='IO')
        cases=[
            (b'', 'absent',[],None,None),
            (before+after,'valid-prefix',prefix+['19:B','19:E'],None,None),
            (before+good,'valid-prefix',prefix,first,None),
            (before+good+phase(['19:B'],ending),'valid-prefix',prefix+['19:B'],first,None),
            (good+before,'malformed',[],None,None),
            (phase(prefix[:-1],ending)+good,'malformed',prefix[:-1],None,None),
            (before+good+good,'malformed',prefix,first,None),
            (before+good+good[:-len(ending)],'partial-line',prefix,first,None),
            (before+good[:-len(ending)],'partial-line',prefix,None,None),
            (before+outer+good,'malformed',prefix,None,dict(action='22',category='RT')),
            (before+good+b'N49D_PHASE04_V1:23:RT'+ending,'malformed',prefix,first,None),
            (before+good+phase(['04:E'],ending),'malformed',prefix,first,None),
            (before+after+good,'malformed',prefix+['19:B','19:E'],None,None),
            (before+phase(['04:E'],ending)+good,'malformed',prefix+['04:E'],None,None),
            (before+b'N49D_BUILD_CATCH_V2:compile-failed:IO'+ending,'malformed',prefix,None,None),
            (before+b'N49D_BUILD_CATCH_V1:unknown-private:IO'+ending,'malformed',prefix,None,None),
            (before+b'N49D_BUILD_CATCH_V1:compile-failed:ZZ'+ending,'malformed',prefix,None,None),
            (before+b'N49D_BUILD_CATCH_V1:compile-failed:io'+ending,'malformed',prefix,None,None),
            (before+b'N49D_BUILD_CATCH_V1::IO'+ending,'malformed',prefix,None,None),
            (before+good[:-len(ending)]+b' private'+ending,'malformed',prefix,None,None),
            (before+b'N49D_BUILD_CATCH_BAD'+ending+good,'malformed',prefix,None,None),
            (before+b' '+good+after,'valid-prefix',prefix+['19:B','19:E'],None,None),
            (before+b'private\x00\xff'+ending+good+outer+after,'valid-prefix',prefix+['19:B','19:E'],first,dict(action='22',category='RT'))]
        for raw,status,events,caught,failure in cases:
            observed=_wrapper_parse_markers(raw)
            check(observed==expected(events,status,caught,failure) and 'private' not in json.dumps(observed),
                'build catch grammar/order/first-fact/privacy')
    model=expected(prefix+['19:B','19:E'],caught=dict(reason='compile-failed',category='IO'),
        failure=dict(action='22',category='RT'))
    cached=dict(_detail_fixture()['ownership'],classification='nonzero child exit')
    saved=FAILURE_DETAIL
    try:
        with tempfile.TemporaryDirectory(prefix='qbrain-build-catch-') as temporary:
            root=Path(temporary)
            raw=phase(prefix,b'\n')+b'N49D_BUILD_CATCH_V1:compile-failed:IO\nN49D_PHASE04_V1:22:RT\n'+phase(['19:B','19:E'],b'\n')
            (root/'stderr.bin').write_bytes(raw)
            cached['stderr']=dict(size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            reads=[];real_read=_wrapper_marker_file
            def read(*args):reads.append(args);return real_read(*args)
            class Owner:
                @property
                def result(self):return cached
                def wait(self):raise primary
            owner=Owner();primary=q.OwnedChildError('build catch primary',owner)
            for constructor_failure in (False,True):
                FAILURE_DETAIL=None;reads.clear();calls=[]
                def construct(*args,**kwargs):
                    calls.append('construct')
                    check(args[-2:]==(20,65536),'build catch owner limits changed')
                    if constructor_failure:raise primary
                    return owner
                with patch.object(q,'OwnedChild',side_effect=construct),patch(__name__+'._wrapper_marker_file',side_effect=read):
                    try:_run_windows_wrapper(root,root/'script.ps1',root/'wrapper.ps1')
                    except q.OwnedChildError as error:check(error is primary,'build catch actual owner primary changed')
                    else:raise ValueError('build catch actual owner unexpectedly passed')
                    check(calls==['construct'] and len(reads)==1 and FAILURE_DETAIL['markers']==model,'build catch single cached read path')
                    first=FAILURE_DETAIL;_capture_wrapper_failure(primary,root)
                    check(FAILURE_DETAIL is first and len(reads)==1,'build catch capture latch retried read')
            for target in ('_wrapper_fallback','_wrapper_failure_detail','_validate_wrapper_detail'):
                FAILURE_DETAIL=None
                with patch.object(q,'OwnedChild',side_effect=primary),patch(__name__+'.'+target,side_effect=RuntimeError('private-observer')):
                    try:_run_windows_wrapper(root,root/'script.ps1',root/'wrapper.ps1')
                    except q.OwnedChildError as error:check(error is primary,'build catch optional observer replaced owner error')
                    else:raise ValueError('build catch optional observer passed')
                check('private' not in json.dumps(FAILURE_DETAIL),'build catch optional observer leaked')
    finally:FAILURE_DETAIL=saved
    with patch(__name__+'._wrapper_marker_file',return_value=model):
        detail=_wrapper_failure_detail(SimpleNamespace(result=cached),Path('/fixture'))
    _validate_wrapper_detail(detail)
    for mutate in [lambda d:d['markers']['build_phase_catch'].update(raw='private'),
        lambda d:d['markers']['build_phase_catch'].pop('category'),
        lambda d:d['markers']['build_phase_catch'].update(reason=True),
        lambda d:d['markers']['build_phase_catch'].update(category='ZZ'),
        lambda d:d['markers']['build_phase_catch'].update(reason='private'),
        lambda d:d['markers'].update(events=['00:B']),
        lambda d:d['markers'].update(status='unavailable'),
        lambda d:d['markers']['phase04_failure'].update(action='23')]:
        bad=copy.deepcopy(detail);mutate(bad)
        expect_failure('build-catch-detail',lambda bad=bad:_validate_wrapper_detail(bad),record=False)
    # Genuine v1 and v2 shapes, with all old fields preserved; no relabeling inference.
    old=copy.deepcopy(detail);old['markers']['build_phase_catch']=None
    old['markers']['phase04_failure']=dict(action='53',category='OT')
    v2=copy.deepcopy(old);v2['schema']='qbrain-n49d-windows-wrapper-failure-v2';v2['markers'].pop('build_phase_catch');v2['markers'].pop('build_progress');v2['markers'].pop('phase04_work')
    v2null=copy.deepcopy(v2);v2null['markers']['phase04_failure']=None
    v1=copy.deepcopy(v2null);v1['schema']='qbrain-n49d-windows-wrapper-failure-v1';v1['markers'].pop('phase04_failure')
    v3=copy.deepcopy(detail);v3['schema']='qbrain-n49d-windows-wrapper-failure-v3';v3['markers'].pop('build_progress');v3['markers'].pop('phase04_work')
    v4=copy.deepcopy(detail);v4['schema']='qbrain-n49d-windows-wrapper-failure-v4';v4['markers'].pop('phase04_work')
    forms=(v1,v2null,v2,v3,v4,old,detail)
    for form in forms:
        before=copy.deepcopy(form);check(_validate_wrapper_detail(form) is form,'build catch validator identity')
        for schema in ('qbrain-n49d-windows-wrapper-failure-v1','qbrain-n49d-windows-wrapper-failure-v2','qbrain-n49d-windows-wrapper-failure-v3','qbrain-n49d-windows-wrapper-failure-v4',WRAPPER_SCHEMA):
            if schema==form['schema']:continue
            bad=copy.deepcopy(form);bad['schema']=schema
            expect_failure('build-catch-schema-relabel',lambda bad=bad:_validate_wrapper_detail(bad),record=False)
        for ending in ('\n','\r\n'):
            value=dict(passed=False,error='build catch primary',controls=[],failure_detail=form)
            raw=(render_selftest_failure(value)+ending).encode()
            check(failure_equal(expand_failure_v2(raw),value) and failure_equal(form,before),'build catch legacy/current typed inverse')
    # Both null and populated additions are forbidden under either historical label.
    for source in (old,detail):
        for schema in ('qbrain-n49d-windows-wrapper-failure-v1','qbrain-n49d-windows-wrapper-failure-v2'):
            bad=copy.deepcopy(source);bad['schema']=schema
            expect_failure('build-catch-old-extra-field',lambda bad=bad:_validate_wrapper_detail(bad),record=False)
    check(len(b'\nN49D_BUILD_CATCH_V1:binary-unavailable:OT\r\n')==44,'build catch emission bound')


def wrapper_build_progress_controls(body):
    """S/G/E=finite cached observations; P=grammar; C=cached capture; V=typed versions.
    Codes are last successful cache writes, never causal negatives or guarantees.
    Actual PowerShell functions/faults remain a later Windows-only gate.
    """
    from types import SimpleNamespace
    global FAILURE_DETAIL
    check(WRAPPER_PROGRESS_PATTERN==r'[NARF][NCAFIXRS][NCALMWF]','progress finite vocabulary')
    gate=q.re.search(r'^ \$n49dBuildCatchInsertion="(.*)" # N49D_WRAPPER_INSTRUMENTATION$',body,q.re.M).group(1)
    for expression in ("`$n49dPhase04Action -ceq '22'",'[object]::ReferenceEquals(`$MyInvocation.MyCommand,`$n49dBuildCatchCommand)',
                       '[object]::ReferenceEquals(`$MyInvocation.MyCommand.ScriptBlock,`$n49dBuildCatchBlock)'):
        check(gate.count(expression)==1,'progress original predicate evaluated once')
    check(gate.index("`$n49dPhase04Action -ceq '22'")<gate.index('[object]::ReferenceEquals(`$MyInvocation.MyCommand,')<
          gate.index('[object]::ReferenceEquals(`$MyInvocation.MyCommand.ScriptBlock,')<gate.index('Write-N49DBuildCatch'),'progress gate order')
    helper=body.split('function Write-N49DBuildProgress(',1)[1].split('Write-N49DWrapperMarker 0',1)[0]
    check(all(x not in helper for x in ('Get-Command','Get-Process','GetType','Exception','ReadAll','WriteAll','Start-Process')),
          'progress helper reads only cached finite fields')
    check(body.index(" Need ((Dispatch $bo) -eq 0) 'BuildOnly'")<body.index('function Invoke-N49DBuildCatchControl'),'progress live-before-controls')
    prefix=['%02d:%s'%(p,e) for p in range(4) for e in ('B','E')]+['04:B']
    phase=lambda events,ending:b''.join(b'N49D_WRAPPER_V1:'+v.encode()+ending for v in events)
    def facts(events,status='valid-prefix',failure=None,progress=None,caught=None):
        result=_wrapper_marker_events(events,status)
        result.update(phase04_failure=failure,build_progress=progress,build_phase_catch=caught);return result
    failure=dict(action='22',category='RT');caught=dict(reason='compile-failed',category='IO')
    for ending in (b'\n',b'\r\n'):
        before=phase(prefix,ending);after=phase(['19:B','19:E'],ending)
        outer=b'N49D_PHASE04_V1:22:RT'+ending;catch=b'N49D_BUILD_CATCH_V1:compile-failed:IO'+ending
        for setup in 'NARF':
            for gate in 'NCAFIXRS':
                for emitter in 'NCALMWF':
                    code=setup+gate+emitter;token=b'N49D_BUILD_PROGRESS_V1:'+code.encode()+ending
                    for observed,expect_caught in ((b'',None),(catch,caught)):
                        check(_wrapper_parse_markers(before+observed+outer+token+after)==facts(prefix+['19:B','19:E'],
                            failure=failure,progress=code,caught=expect_caught),'progress finite/stale combinations')
        token=b'N49D_BUILD_PROGRESS_V1:RIF'+ending
        cases=[(before+outer+after,'valid-prefix',prefix+['19:B','19:E'],failure,None),
            (before+token,'malformed',prefix,None,None),
            (before+outer+token+token,'malformed',prefix,failure,'RIF'),
            (before+outer+token+token[:-len(ending)],'partial-line',prefix,failure,'RIF'),
            (before+outer+token[:-len(ending)],'partial-line',prefix,failure,None),
            (before+outer+after+token,'malformed',prefix+['19:B','19:E'],failure,None),
            (before+b'N49D_PHASE04_V1:23:RT'+ending+token,'malformed',prefix,dict(action='23',category='RT'),None),
            (before+outer+token+phase(['04:E'],ending),'malformed',prefix,failure,'RIF'),
            (before+outer+token+catch,'malformed',prefix,failure,'RIF'),
            (before+outer+b'private\x00\xff'+ending+token+after,'valid-prefix',prefix+['19:B','19:E'],failure,'RIF')]
        for bad in (b'N49D_BUILD_PROGRESS_V2:RIF',b'N49D_BUILD_PROGRESS_V1:rif',b'N49D_BUILD_PROGRESS_V1:RIZ',
                    b'N49D_BUILD_PROGRESS_V1:RI',b'N49D_BUILD_PROGRESS_V1:RIFF',b'N49D_BUILD_PROGRESS_V1:RIF private',
                    b'N49D_BUILD_PROGRESS_BAD'):
            cases.append((before+outer+bad+ending,'malformed',prefix,failure,None))
        for raw,status,events,outer_fact,code in cases:
            observed=_wrapper_parse_markers(raw)
            check(observed==facts(events,status,outer_fact,code) and 'private' not in json.dumps(observed),'progress negative retention')
    model=facts(prefix+['19:B','19:E'],failure=failure,progress='RIF',caught=caught)
    cached=dict(_detail_fixture()['ownership'],classification='nonzero child exit')
    with patch(__name__+'._wrapper_marker_file',return_value=model):
        detail=_wrapper_failure_detail(SimpleNamespace(result=cached),Path('/fixture'))
    _validate_wrapper_detail(detail)
    for mutation in [lambda d:d['markers'].update(build_progress=True),lambda d:d['markers'].update(build_progress='private'),
        lambda d:d['markers'].update(build_progress='RIFX'),lambda d:d['markers'].pop('build_progress'),
        lambda d:d['markers'].update(phase04_failure=None),lambda d:d['markers']['phase04_failure'].update(action='23')]:
        bad=copy.deepcopy(detail);mutation(bad)
        expect_failure('build-progress-detail',lambda bad=bad:_validate_wrapper_detail(bad),record=False)
    forms=[detail]
    for version,missing in [('v4',('phase04_work',)),('v3',('build_progress','phase04_work')),('v2',('build_progress','build_phase_catch','phase04_work')),
                            ('v1',('build_progress','build_phase_catch','phase04_failure','phase04_work'))]:
        old=copy.deepcopy(detail);old['schema']='qbrain-n49d-windows-wrapper-failure-'+version
        for key in missing:old['markers'].pop(key)
        forms.append(old)
    null=copy.deepcopy(detail);null['markers']['build_progress']=None;forms.append(null)
    for form in forms:
        saved=copy.deepcopy(form);check(_validate_wrapper_detail(form) is form,'progress validator identity')
        for ending in ('\n','\r\n'):
            value=dict(passed=False,error='progress primary',controls=[],failure_detail=form)
            check(failure_equal(expand_failure_v2((render_selftest_failure(value)+ending).encode()),value) and
                  failure_equal(form,saved),'progress legacy/current typed inverse')
        for version in ('v1','v2','v3','v4','v5'):
            schema='qbrain-n49d-windows-wrapper-failure-'+version
            if schema==form['schema']:continue
            bad=copy.deepcopy(form);bad['schema']=schema
            expect_failure('progress-schema-relabel',lambda bad=bad:_validate_wrapper_detail(bad),record=False)
    saved=FAILURE_DETAIL
    try:
        with tempfile.TemporaryDirectory(prefix='qbrain-progress-') as temporary:
            root=Path(temporary);raw=phase(prefix,b'\n')+b'N49D_BUILD_CATCH_V1:compile-failed:IO\nN49D_PHASE04_V1:22:RT\nN49D_BUILD_PROGRESS_V1:RIF\n'+phase(['19:B','19:E'],b'\n')
            (root/'stderr.bin').write_bytes(raw);cached['stderr']=dict(size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            owner=SimpleNamespace(result=cached);primary=q.OwnedChildError('progress primary',owner);FAILURE_DETAIL=None
            real=_wrapper_marker_file
            with patch(__name__+'._wrapper_marker_file',wraps=real) as read,patch.object(q,'OwnedChild',side_effect=primary):
                try:_run_windows_wrapper(root,root/'script.ps1',root/'wrapper.ps1')
                except q.OwnedChildError as error:check(error is primary,'progress caller primary changed')
                else:raise ValueError('progress caller unexpectedly passed')
                first=FAILURE_DETAIL;_capture_wrapper_failure(primary,root)
                check(read.call_count==1 and FAILURE_DETAIL is first and first['markers']==model,'progress cached capture retried')
    finally:FAILURE_DETAIL=saved
    check(len(b'\nN49D_BUILD_PROGRESS_V1:RIF\r\n')==29,'progress token bound')


def wrapper_work_controls(body):
    """O/F/T/C/V: exact order, isolated faults, bounded time, cached capture, versions.
    No row is added. These are actual parser/capture controls; PowerShell emitter
    controls stay in the same unchanged twenty-second owner.
    """
    from types import SimpleNamespace
    global FAILURE_DETAIL
    prefix=['%02d:%s'%(p,e) for p in range(4) for e in ('B','E')]+['04:B']
    def phases(events,ending):return b''.join(b'N49D_WRAPPER_V1:'+e.encode()+ending for e in events)
    def token(operation,edge,tick,ending):return ('N49D_WORK_V1:%02d:%s:%05d'%(operation,edge,tick)).encode()+ending
    def facts(work,status='valid-prefix',events=prefix):
        value=_wrapper_marker_events(events,status);value['phase04_work']=work;return value
    for ending in (b'\n',b'\r\n'):
        head=phases(prefix,ending);raw=head;expected=None
        # Every actual source operation, each begin and observed-success end.
        for operation in range(1,48):
            for edge in ('B','E'):
                tick=min(20000,operation*499+(edge=='E'))
                raw+=token(operation,edge,tick,ending)
                expected=([operation,tick,operation-1,0 if operation==1 else min(20000,(operation-1)*499+1),0]
                          if edge=='B' else [operation,min(20000,operation*499),operation,tick,0])
                check(_wrapper_parse_markers(raw)==facts(expected) and _wrapper_work_valid(expected),'work valid timeout-like prefix')
        complete=prefix+['04:E']
        check(_wrapper_parse_markers(raw+phases(['04:E'],ending))==facts(expected,events=complete),'work completed phase retention')
        for interrupted,cleanup in [(n,41) for n in range(3,41)]+[(n,46) for n in range(42,46)]:
            before=head+b''.join(token(n,e,1,ending) for n in range(1,interrupted) for e in ('B','E'))+token(interrupted,'B',2,ending)
            for edge in ('B','E'):
                suffix=token(cleanup,'B',3,ending)+(token(cleanup,'E',4,ending) if edge=='E' else b'')
                want=[cleanup,3,cleanup if edge=='E' else interrupted-1,4 if edge=='E' else 1,interrupted]
                check(_wrapper_parse_markers(before+suffix)==facts(want) and _wrapper_work_valid(want),'work cleanup observed prefix')
        first=token(1,'B',123,ending);want=[1,123,0,0,0]
        malformed=[first,token(1,'E',122,ending),token(2,'B',124,ending),token(48,'B',123,ending),
                   token(1,'E',20001,ending),b'N49D_WORK_V2:01:E:00123'+ending,
                   b'N49D_WORK_V1:01:e:00123'+ending,b'N49D_WORK_V1:01:E:000123'+ending,
                   b'N49D_WORK_V1:01:E:00123 private'+ending,b'N49D_WORK_PRIVATE'+ending,
                   b'N49D_WORK_V1:'+b'x'*1000+ending]
        for suffix in malformed:
            check(_wrapper_parse_markers(head+first+suffix)==facts(want,'malformed'),'work malformed first-prefix retention')
        check(_wrapper_parse_markers(head+first+token(1,'E',124,ending)[:-len(ending)])==facts(want,'partial-line'),'work partial retention')
        check(_wrapper_parse_markers(head+first+b'private\x00\xff'+ending)==facts(want),'work private unrelated bytes')
        for before in (b'',phases(prefix[:-1],ending),head+phases(['04:E'],ending)):
            observed=_wrapper_parse_markers(before+first)
            check(observed['status']=='malformed' and observed['phase04_work'] is None,'work outside phase accepted')
        check(_wrapper_parse_markers(head+first+b'N49D_PHASE04_V1:22:IO'+ending+token(1,'E',124,ending))['status']=='malformed','work after failure accepted')
        expect_failure('work-oversize',lambda:_wrapper_parse_markers(b'x'*65537),record=False)
    cached=dict(_detail_fixture()['ownership'],classification='timeout')
    model=facts([16,12000,15,11999,0])
    with patch(__name__+'._wrapper_marker_file',return_value=model):
        detail=_wrapper_failure_detail(SimpleNamespace(result=cached),Path('/fixture'))
    _validate_wrapper_detail(detail)
    for bad in (True,[],[1,0,0,0],[True,0,0,0,0],[48,0,47,0,0],[1,-1,0,0,0],[1,20001,0,0,0],
                [2,1,0,0,0],[1,0,0,1,0],[1,2,1,1,0],[2,1,1,2,0],[47,0,47,0,47],[3,0,2,0,1]):
        changed=copy.deepcopy(detail);changed['markers']['phase04_work']=bad
        expect_failure('work-invalid-detail',lambda changed=changed:_validate_wrapper_detail(changed),record=False)
    for version,missing in [('v1',('phase04_failure','build_phase_catch','build_progress','phase04_work')),
                            ('v2',('build_phase_catch','build_progress','phase04_work')),
                            ('v3',('build_progress','phase04_work')),('v4',('phase04_work',)),('v5',())]:
        value=copy.deepcopy(detail);value['schema']='qbrain-n49d-windows-wrapper-failure-'+version
        for key in missing:value['markers'].pop(key)
        before=copy.deepcopy(value)
        check(_validate_wrapper_detail(value) is value,'work version identity')
        for ending in ('\n','\r\n'):
            failure=dict(passed=False,error='timeout',controls=[],failure_detail=value)
            check(failure_equal(expand_failure_v2((render_selftest_failure(failure)+ending).encode()),failure) and
                  failure_equal(value,before),'work historical/current typed inverse')
    saved=FAILURE_DETAIL
    try:
        with tempfile.TemporaryDirectory(prefix='qbrain-work-') as temporary:
            root=Path(temporary);raw=phases(prefix,b'\n')+b''.join(token(n,e,11999,b'\n') for n in range(1,16) for e in ('B','E'))+token(16,'B',12000,b'\n')
            (root/'stderr.bin').write_bytes(raw);cached['stderr']=dict(size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            for constructor_failure in (False,True):
                owner=SimpleNamespace(result=cached);primary=q.OwnedChildError('timeout',owner);FAILURE_DETAIL=None
                owner.wait=lambda:(_ for _ in ()).throw(primary)
                with patch.object(q,'OwnedChild',side_effect=primary if constructor_failure else lambda *a,**k:owner),patch(__name__+'._wrapper_marker_file',wraps=_wrapper_marker_file) as read:
                    try:_run_windows_wrapper(root,root/'script.ps1',root/'wrapper.ps1')
                    except q.OwnedChildError as caught:check(caught is primary,'work primary replaced')
                    else:raise ValueError('work failing owner passed')
                    first=FAILURE_DETAIL;_capture_wrapper_failure(primary,root)
                    check(read.call_count==1 and first is FAILURE_DETAIL and first['markers']==model,'work cached owner capture changed')
    finally:FAILURE_DETAIL=saved
    # Pin each literal mapping, source operation count and cached-writer path.
    check(body.count('function Write-N49DWork(')==1 and body.count('function New-N49DWorkState(')==1,'work helper inventory')
    helper=body.split('function Write-N49DWork(',1)[1].split('Write-N49DWrapperMarker 0',1)[0]
    check(all(word not in helper for word in ('Get-Command','Get-Process','Start-Process','ReadAll','WriteAll','[Console]::Error')),'work helper performs query or ignores cached writer')
    check('$State.Writer.WriteLine(' in helper and '$State.Writer.Flush()' in helper and "[Math]::Min([long]20000,$tick)" in helper,'work fixed emitter cap')
    direct=q.re.findall(r"Write-N49DWork \$n49dWork '([0-9]{2})' '([BE])'",body)
    check(direct==[('%02d'%n,e) for n in (1,2,3,40,41,42,43,44,45,46,47) for e in ('B','E')],'work fixed operation calls')
    pair_line=next(line for line in body.splitlines() if '$n49dWorkPair=switch ' in line)
    pairs=q.re.findall(r"'([^']+)'\{@\('([0-9]{2})','([0-9]{2})'\)\}",pair_line)
    cases=('success','native-throw','native-nonzero','early','arguments-escape','resolver-escape')
    check(pairs==[(case,'%02d'%(4+2*i),'%02d'%(5+2*i)) for i,case in enumerate(cases)],'work exact paired case mapping')
    fault_line=next(line for line in body.splitlines() if '$n49dWorkId=switch ' in line)
    faults=q.re.findall(r"'([^']+)'\{'([0-9]{2})'\}",fault_line)
    names=('getter','writer','flush','latch-read','latch-write','observer-constructor','invocation','stream-output',
           'initialization','constructor','activation-before','activation-after','gate-action','gate-redefinition',
           'gate-command','gate-block','progress-S','progress-G','progress-E','progress-S-setup','progress-G-action',
           'progress-G-command','progress-G-block','progress-unavailable')
    check(faults==[(name,'%02d'%(16+i)) for i,name in enumerate(names)] and len(direct)+4*len(pairs)+2*len(faults)==94,'work exact fault case mapping')
    check(len(b'\nN49D_WORK_V1:47:E:20000\r\n')==26 and 94*26==2444,'work emitter maximum bytes')


def wrapper_instrumentation_controls():
    import ast
    source=Path(__file__).read_text(encoding='utf-8')
    function=next(node for node in ast.parse(source).body if isinstance(node,ast.FunctionDef) and node.name=='windows_wrapper_controls')
    body=ast.literal_eval(next(node.value for node in function.body if isinstance(node,ast.Assign) and
        any(isinstance(target,ast.Name) and target.id=='body' for target in node.targets)))
    stripped=''.join(line for line in body.splitlines(keepends=True) if not line.endswith(' # N49D_WRAPPER_INSTRUMENTATION\n'))
    check(len(stripped.encode())==11623 and hashlib.sha256(stripped.encode()).hexdigest()==
        '706dbd9f63b4703ca16cba5d05a62ff7577bb6bc09656022f753a3fd29df92cc','wrapper underlying body changed')
    tokens=['N49D_WRAPPER_V1:%02d:%s'%(phase,edge) for phase in range(20) for edge in ('B','E')]
    check(len(tokens)==40 and sum(len(('\n'+token+'\r\n').encode('ascii')) for token in tokens)==920 and
        all(body.count("'"+token+"'")==1 for token in tokens),'wrapper fixed marker inventory/budget')
    check(tuple(sorted(WRAPPER_PHASE04_ACTIONS))==tuple('%02d'%n for n in range(1,54)) and
        WRAPPER_PHASE04_CATEGORIES==frozenset(('RT','MI','PB','IO','AR','OP','OT')),'phase04 closed enums')
    phase=body.split('Write-N49DWrapperMarker 8 # N49D_WRAPPER_INSTRUMENTATION\n',1)[1].split('Write-N49DWrapperMarker 9 # N49D_WRAPPER_INSTRUMENTATION\n',1)[0]
    selectors=q.re.findall(r"^ \$n49dPhase04Action='([0-9]{2})' # N49D_WRAPPER_INSTRUMENTATION$",phase,q.re.M)
    check(selectors==['%02d'%n for n in range(1,54)],'phase04 selector order')
    check('}catch{try{Write-N49DPhase04Failure $_ $n49dPhase04Action}catch{};try{Write-N49DBuildProgress $n49dPhase04Action $n49dBuildCatchProgress}catch{};throw} # N49D_WRAPPER_INSTRUMENTATION\n' in phase and
        ' $n49dPhase04PriorAction=$n49dPhase04Action # N49D_WRAPPER_INSTRUMENTATION\n' in phase and
        " $n49dPhase04Action='16' # N49D_WRAPPER_INSTRUMENTATION\n $manifest.consumed=$correctConsumed\n $n49dPhase04Action=$n49dPhase04PriorAction # N49D_WRAPPER_INSTRUMENTATION\n" in phase,'phase04 primary and restoration boundary')
    check(len(('\nN49D_PHASE04_V1:53:OT\r\n').encode())==24,'phase04 emission budget')
    writer_raw=guard.checkout_bytes((q.ROOT/'scripts/build-tests-cl.ps1').read_bytes(),guard.WRAPPERS['scripts/build-tests-cl.ps1'],os.name=='nt')
    writer_old=b'[IO.File]::Replace($temporary,$Path,$null)';writer_new=b'[IO.File]::Replace($temporary,$Path,[System.Management.Automation.Language.NullString]::Value)'
    check(writer_raw.count(writer_new)==1 and guard.blob(writer_raw.replace(writer_new,writer_old))=='fd674ec09cc9f3b2432290a5d66c98e6d92e4411','exact writer null-backup correction')
    expect_failure('writer-former-null-argument',lambda:guard.checkout_bytes(writer_raw.replace(writer_new,writer_old),guard.WRAPPERS['scripts/build-tests-cl.ps1']),'checkout blob mismatch',record=False)
    writer_controls=body.split(" & { # N49D_WRAPPER_INSTRUMENTATION\n  $n49dWriterDir=",1)[1].split("}catch{$n49dPhase04Action=$null;throw} # N49D_WRAPPER_INSTRUMENTATION\n",1)[0]
    writer_controls=''.join(line for line in writer_controls.splitlines(keepends=True) if 'Write-N49DWork $n49dWork' not in line)
    writer_controls=writer_controls.replace('  }finally{ # N49D_WRAPPER_INSTRUMENTATION\n   Remove-Item -LiteralPath $n49dWriterDir -Recurse -Force # N49D_WRAPPER_INSTRUMENTATION\n  } # N49D_WRAPPER_INSTRUMENTATION\n','  }finally{Remove-Item -LiteralPath $n49dWriterDir -Recurse -Force} # N49D_WRAPPER_INSTRUMENTATION\n')
    check(hashlib.sha256((' & { # N49D_WRAPPER_INSTRUMENTATION\n  $n49dWriterDir='+writer_controls).encode()).hexdigest()=='49e512b859a9beb737a086e8ea81d78648eee69a9871a4b5bf334ef23e046fd2','actual report writer controls')
    check(body.index("Need ((Dispatch $bo) -eq 0) 'BuildOnly'")<body.index('$n49dWriterDir='),'live BuildOnly precedes writer controls')
    wrapper_phase04_controls()
    wrapper_build_catch_controls(body)
    wrapper_build_progress_controls(body)
    wrapper_work_controls(body)
    RESULTS.append(dict(name='wrapper-fixed-markers-body',passed=True,phase04='SPNCV',catch='IPNCV',progress='SGEPCV',work='OFTCV'))


WRAPPER_FILE_FIELDS=('st_dev','st_ino','st_mode','st_size','st_mtime_ns','st_ctime_ns','st_file_attributes')
WRAPPER_FILE_FIELDS_V2=WRAPPER_FILE_FIELDS+('st_birthtime_ns',)
WRAPPER_FILE_SAMPLES=('before','opened','after','path_after')
WRAPPER_FILE_WINDOWS=os.name=='nt'
WRAPPER_FILE_BASES=('posix-ctime','windows-birthtime+ctime')


def _wrapper_file_boundary_fallback_v1():
    return dict(schema='qbrain-n49d-wrapper-file-boundary-v1',status='unavailable',
        samples=[dict(fields='UUUUUUU',regular=[None,None,None]) for _ in WRAPPER_FILE_SAMPLES],equal=['???????']*3)


def _wrapper_file_boundary_fallback(basis=None):
    return dict(schema='qbrain-n49d-wrapper-file-boundary-v2',status='unavailable',
        basis=WRAPPER_FILE_BASES[int(WRAPPER_FILE_WINDOWS)] if basis is None else basis,
        samples=[dict(fields='UUUUUUUU',regular=[None,None,None]) for _ in WRAPPER_FILE_SAMPLES],equal=['????????']*3)


def _wrapper_file_boundary_facts(samples):
    """Cached stat values only. Field states V=exact int, A=absent, M=malformed,
    U=unavailable. Regular bits: regular file, symbolic link, reparse flag.
    V2 adds birthtime at index 7 without relabeling raw ctime at index 5.
    Windows pairs are opened/before, after/opened, path_after/before; the first
    pair uses birthtime, and later pairs use raw ctime AND birthtime.
    POSIX pairs are opened/before, after/before, path_after/before; birthtime
    is observational only. 1=equal, 0=unequal, ?=unknown; absent attrs use 0.
    Captured means construction succeeded; A/M/U/?/null can still be present.
    """
    detail=_wrapper_file_boundary_fallback();detail['status']='captured';vectors=[]
    for index,name in enumerate(WRAPPER_FILE_SAMPLES):
        source=samples.get(name);states=[];values=[]
        for field in WRAPPER_FILE_FIELDS_V2:
            state='U';value=None
            if source is not None:
                try:
                    value=getattr(source,field);state='V' if type(value) is int else 'M'
                    if state!='V':value=None
                except AttributeError:
                    state='A';value=0 if field=='st_file_attributes' else None
                except BaseException:pass
            states.append(state);values.append(value)
        mode,attributes=values[2],values[6]
        detail['samples'][index]=dict(fields=''.join(states),regular=[
            None if mode is None else stat.S_ISREG(mode),None if mode is None else stat.S_ISLNK(mode),
            None if attributes is None else bool(attributes&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',1024))])
        vectors.append(values)
    pairs=((1,0),(2,1 if WRAPPER_FILE_WINDOWS else 0),(3,0))
    detail['equal']=[''.join('?' if a is None or b is None else '1' if a==b else '0'
        for a,b in zip(vectors[left],vectors[right])) for left,right in pairs]
    return detail


def _validate_wrapper_file_boundary_v1(detail):
    check(type(detail) is dict and set(detail)=={'schema','status','samples','equal'} and
        type(detail['schema']) is str and detail['schema']=='qbrain-n49d-wrapper-file-boundary-v1' and
        type(detail['status']) is str and detail['status'] in ('captured','unavailable'),'file boundary schema')
    check(type(detail['samples']) is list and len(detail['samples'])==4 and
        type(detail['equal']) is list and len(detail['equal'])==3,'file boundary dimensions')
    for sample in detail['samples']:
        check(type(sample) is dict and set(sample)=={'fields','regular'} and type(sample['fields']) is str and
            q.re.fullmatch('[VAMU]{7}',sample['fields']) is not None and type(sample['regular']) is list and
            len(sample['regular'])==3 and all(value is None or type(value) is bool for value in sample['regular']),
            'file boundary sample facts')
    check(all(type(mask) is str and q.re.fullmatch('[01?]{7}',mask) is not None for mask in detail['equal']),
          'file boundary equality masks')
    if detail['status']=='unavailable':check(failure_equal(detail,_wrapper_file_boundary_fallback_v1()),'file boundary unavailable facts')


def _validate_wrapper_file_boundary(detail):
    check(type(detail) is dict and type(detail.get('schema')) is str,'file boundary schema')
    if detail['schema']=='qbrain-n49d-wrapper-file-boundary-v1':
        return _validate_wrapper_file_boundary_v1(detail)
    check(set(detail)=={'schema','status','basis','samples','equal'} and
        detail['schema']=='qbrain-n49d-wrapper-file-boundary-v2' and
        type(detail['basis']) is str and detail['basis'] in WRAPPER_FILE_BASES and
        type(detail['status']) is str and detail['status'] in ('captured','unavailable'),'file boundary schema')
    check(type(detail['samples']) is list and len(detail['samples'])==4 and
        type(detail['equal']) is list and len(detail['equal'])==3,'file boundary dimensions')
    for sample in detail['samples']:
        check(type(sample) is dict and set(sample)=={'fields','regular'} and type(sample['fields']) is str and
            q.re.fullmatch('[VAMU]{8}',sample['fields']) is not None and type(sample['regular']) is list and
            len(sample['regular'])==3 and all(value is None or type(value) is bool for value in sample['regular']),
            'file boundary sample facts')
    check(all(type(mask) is str and q.re.fullmatch('[01?]{8}',mask) is not None for mask in detail['equal']),
          'file boundary equality masks')
    if detail['status']=='unavailable':
        check(failure_equal(detail,_wrapper_file_boundary_fallback(detail['basis'])),'file boundary unavailable facts')


def _capture_wrapper_file_boundary(row,samples,checks=''):
    try:
        if 'boundary' in row:return
        row['checks']=checks if type(checks) is str and len(checks)<=9 and all(c in 'boBpOAP?' for c in checks) else 'unavailable'
        row['boundary']=_wrapper_file_boundary_fallback()
        detail=_wrapper_file_boundary_facts(samples);_validate_wrapper_file_boundary(detail)
        for ending in ('\n','\r\n'):
            raw=(json.dumps({'boundary':detail,'checks':row['checks']},sort_keys=True,indent=2,allow_nan=False)+'\n').replace('\n',ending).encode()
            check(len(raw)<=1024,'wrapper file boundary detail cap')
        row['boundary']=detail
    except BaseException:pass


def _wrapper_file_boundary_maximum():
    from types import SimpleNamespace
    value=SimpleNamespace(**{field:0 for field in WRAPPER_FILE_FIELDS_V2})
    with patch(__name__+'.WRAPPER_FILE_WINDOWS',True):
        return _wrapper_file_boundary_facts({name:value for name in WRAPPER_FILE_SAMPLES})


def wrapper_stat_compat_controls():
    """Memory-only actual-reader models. W=stable Windows path/fd ctime split,
    F/P=isolated fd/path ctime drift; BOAP identify the four stat samples;
    0,1,2,3,4,6 are unchanged identity fields; b/m/t/f/s/n/i mean changed,
    missing, bool, float, string, None or int-subclass birthtime. p is POSIX
    with no birthtime; pBOAP mutate each POSIX ctime. Every trace token means
    all expected result, read bound, I/O order and close checks passed.
    """
    from contextlib import ExitStack
    from types import SimpleNamespace
    row=dict(name='wrapper-stat-compat',passed=False,trace=[]);RESULTS.append(row)
    line=b'N49D_WRAPPER_V1:00:B\n';root=Path('/fixture');leaf=root/'stderr.bin'
    descriptor=dict(size=len(line),sha256=hashlib.sha256(line).hexdigest())
    fields=dict(zip(WRAPPER_FILE_FIELDS_V2,(1,2,stat.S_IFREG|0o600,len(line),3,100,0,300)))
    class Integer(int):pass
    def blocked(*args,**kwargs):raise AssertionError('stat model performed native operation')
    def run(label,windows=True,slot=None,field=None,value=None,missing=False):
        samples=[SimpleNamespace(**fields) for _ in WRAPPER_FILE_SAMPLES]
        if windows:
            for index in (1,2):samples[index].st_ctime_ns=200
        else:
            for sample in samples:del sample.st_birthtime_ns
        if slot is not None:
            if missing:delattr(samples[slot],field)
            else:setattr(samples[slot],field,value)
        calls=[];reads=[];lstats=iter((samples[0],samples[3]));fstats=iter((samples[1],samples[2]))
        def lstat(path):
            check(path==leaf,'stat model path');calls.append('L');return next(lstats)
        def opened(path,flags):
            check(path==leaf and flags&getattr(os,'O_NOFOLLOW',0)==getattr(os,'O_NOFOLLOW',0) and
                flags&getattr(os,'O_NONBLOCK',0)==getattr(os,'O_NONBLOCK',0),'stat model open flags')
            calls.append('O');return 17
        def fstat(fd):check(fd==17,'stat model descriptor');calls.append('F');return next(fstats)
        class Reader:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,size):calls.append('R');reads.append(size);return line
        def fdopen(fd,*args,**kwargs):
            check(fd==17 and args==('rb',) and kwargs==dict(buffering=0,closefd=False),'stat model fdopen')
            return Reader()
        def close(fd):check(fd==17,'stat model close');calls.append('C')
        with ExitStack() as stack:
            stack.enter_context(patch(__name__+'.WRAPPER_FILE_WINDOWS',windows))
            for module,names in [(Path,('stat','open','read_bytes','write_bytes')),
                (os,('kill','waitpid','waitid','pidfd_open')),
                (q.subprocess,('Popen','run','check_output','call'))]:
                for name in names:
                    if hasattr(module,name):stack.enter_context(patch.object(module,name,side_effect=blocked))
            for module,name,fn in [(Path,'lstat',lstat),(os,'open',opened),(os,'fstat',fstat),
                                  (os,'fdopen',fdopen),(os,'close',close)]:
                stack.enter_context(patch.object(module,name,fn))
            actual=_wrapper_marker_file(root,descriptor)
            if label=='W':
                facts=_wrapper_file_boundary_facts(dict(zip(WRAPPER_FILE_SAMPLES,samples)))
                _validate_wrapper_file_boundary(facts)
                check(facts['basis']==WRAPPER_FILE_BASES[1] and
                    facts['equal']==['11111011','11111111','11111111'],'Windows raw diagnostic pair semantics')
            if label=='p':
                check(_wrapper_file_identity(samples[0])==tuple(fields[k] for k in WRAPPER_FILE_FIELDS),
                      'POSIX seven-field identity changed')
        malformed=windows and field=='st_birthtime_ns' and (missing or type(value) is not int)
        expected='valid-prefix' if slot is None else 'stream-unavailable' if malformed else 'stream-mismatch'
        early=slot in (0,1);trace='LOFC' if early else 'LOFRFLC'
        check(actual['status']==expected and ''.join(calls)==trace and reads==([] if early else [65537]) and
            calls.count('C')==1 and actual['events']==(['00:B'] if slot is None else []),
            'stat compatibility model: '+label)
        row['trace'].append(label)
    run('W')
    run('F',slot=2,field='st_ctime_ns',value=201)
    run('P',slot=3,field='st_ctime_ns',value=101)
    for slot,code in enumerate('BOAP'):
        for index in (0,1,2,3,4,6):
            field=WRAPPER_FILE_FIELDS[index]
            run(code+str(index),slot=slot,field=field,value=fields[field]+1)
        for code2,value,missing in [('b',301,False),('m',None,True),('t',True,False),('f',300.0,False),
                                   ('s','private',False),('n',None,False),('i',Integer(300),False)]:
            run(code+code2,slot=slot,field='st_birthtime_ns',value=value,missing=missing)
    run('p',False)
    for slot,code in enumerate('BOAP'):run('p'+code,False,slot,'st_ctime_ns',101)
    row['passed']=True


def wrapper_file_version_controls():
    """Legacy v1 facts remain seven raw fields/all pairs based on before.
    m/u=maximum/unavailable and L/C=LF/CRLF; k/r/d/e/b reject extra key,
    relabel, missing basis, wrong dimension or wrong basis. Tokens include
    the originating schema version; each recorded token retains a whole case.
    """
    row=dict(name='wrapper-file-versions',passed=False,trace=[]);RESULTS.append(row)
    maximum=_wrapper_file_boundary_fallback_v1();maximum['status']='captured'
    maximum['samples']=[dict(fields='VVVVVVV',regular=[False]*3) for _ in WRAPPER_FILE_SAMPLES]
    maximum['equal']=['1111111']*3
    for label,detail in [('m',maximum),('u',_wrapper_file_boundary_fallback_v1())]:
        _validate_wrapper_file_boundary_v1(detail);_validate_wrapper_file_boundary(detail)
        for suffix,ending in [('L','\n'),('C','\r\n')]:
            value=dict(passed=False,error='legacy boundary',controls=[
                dict(name='wrapper-bounded-file',passed=False,boundary=copy.deepcopy(detail),checks='boOBABPBp')])
            saved=copy.deepcopy(value);raw=(render_selftest_failure(value)+ending).encode()
            check(failure_equal(expand_failure_v2(raw),saved) and failure_equal(value,saved),
                  'legacy current renderer/inverse changed typed facts')
            row['trace'].append('1'+label+suffix)
    v2=_wrapper_file_boundary_maximum()
    cases=[('1k',dict(maximum,basis=WRAPPER_FILE_BASES[1])),
           ('1r',dict(maximum,schema=v2['schema'])),
           ('2r',dict(v2,schema=maximum['schema'])),
           ('2d',{k:v for k,v in v2.items() if k!='basis'}),
           ('2b',dict(v2,basis='ctime-fallback'))]
    for label,base,width in [('1e',maximum,8),('2e',v2,7)]:
        changed=copy.deepcopy(base);changed['samples'][0]['fields']='V'*width;cases.append((label,changed))
    for label,detail in cases:
        expect_failure('boundary-version-'+label,lambda detail=detail:_validate_wrapper_file_boundary(detail),record=False)
        value=dict(passed=False,error='version primary',controls=[
            dict(name='boundary',passed=False,boundary=detail)])
        out=json.loads(render_selftest_failure(value))
        check(out['schema']==FAILURE_UNAVAILABLE and out['error']=='version primary' and out['controls_available'] is False,
              'renderer accepted cross-version boundary')
        row['trace'].append(label)
    row['passed']=True


def wrapper_file_boundary_controls():
    """Finite memory-only controls; never execute a native file/process operation."""
    from contextlib import ExitStack
    from types import SimpleNamespace
    row=dict(name='wrapper-file-facts',passed=False,trace=[]);RESULTS.append(row)
    values=dict(zip(WRAPPER_FILE_FIELDS_V2,(1,2,stat.S_IFREG|0o600,21,3,4,0,5)))
    base=SimpleNamespace(**values);samples={name:base for name in WRAPPER_FILE_SAMPLES}
    def add(label):row['trace'].append(label+'=ok')
    def blocked(*args,**kwargs):raise AssertionError('file diagnostic performed I/O or process operation')
    with ExitStack() as stack:
        stack.enter_context(patch(__name__+'.WRAPPER_FILE_WINDOWS',False))
        for module,names in [(Path,('lstat','stat','open','read_bytes','write_bytes')),
            (os,('open','fstat','fdopen','close','kill','waitpid','waitid','pidfd_open')),
            (q.subprocess,('Popen','run','check_output','call'))]:
            for name in names:
                if hasattr(module,name):stack.enter_context(patch.object(module,name,side_effect=blocked))
        actual=_wrapper_file_boundary_facts(samples)
        check(actual['equal']==['11111111']*3 and all(item['fields']=='VVVVVVVV' and
            item['regular']==[True,False,False] for item in actual['samples']),'file diagnostic valid sample')
        add('equal')
        for slot,name in enumerate(WRAPPER_FILE_SAMPLES[1:]):
            for index,field in enumerate(WRAPPER_FILE_FIELDS_V2):
                changed=SimpleNamespace(**(values|{field:values[field]+1}));packet=dict(samples);packet[name]=changed
                facts=_wrapper_file_boundary_facts(packet);expected=['11111111']*3
                expected[slot]='1'*index+'0'+'1'*(7-index)
                check(facts['equal']==expected,'file diagnostic identity field comparison')
                if slot==0 and field!='st_birthtime_ns':
                    with patch.object(Path,'lstat',return_value=base),patch.object(os,'open',return_value=17),\
                         patch.object(os,'fstat',return_value=changed),patch.object(os,'close') as closed:
                        result=_wrapper_marker_file(Path('/fixture'),dict(size=21,sha256='0'*64))
                    check(result['status']=='stream-mismatch' and closed.call_args.args==(17,),
                          'file reader accepted changed identity field')
                row['trace'].append(str(slot)+str(index)+'='+expected[slot])
        for label,changes,bits in [('directory',{'st_mode':stat.S_IFDIR|0o700},[False,False,False]),
            ('link',{'st_mode':stat.S_IFLNK|0o700},[False,True,False]),
            ('reparse',{'st_file_attributes':1024},[True,False,True])]:
            changed=SimpleNamespace(**(values|changes));facts=_wrapper_file_boundary_facts(dict(samples,opened=changed))
            check(facts['samples'][1]['regular']==bits and not _wrapper_regular(changed),'file regular/reparse distinction')
            with patch.object(Path,'lstat',return_value=base),patch.object(os,'open',return_value=17),\
                 patch.object(os,'fstat',return_value=changed),patch.object(os,'close') as closed:
                result=_wrapper_marker_file(Path('/fixture'),dict(size=21,sha256='0'*64))
            check(result['status']=='stream-mismatch' and closed.call_count==1,'file reader regularity guard')
            add(label)
        for label,changes,state in [('missing',{},'A'),('bool',{'st_ino':True},'M'),('text',{'st_ino':'private'},'M')]:
            changed=dict(values);changed.pop('st_ino');changed.update(changes)
            facts=_wrapper_file_boundary_facts(dict(samples,opened=SimpleNamespace(**changed)))
            check(facts['samples'][1]['fields']=='V'+state+'VVVVVV' and facts['equal'][0]=='1?111111',
                  'file absent/malformed field distinction');add(label)
        changed=dict(values);changed.pop('st_file_attributes')
        facts=_wrapper_file_boundary_facts(dict(samples,opened=SimpleNamespace(**changed)))
        check(facts['samples'][1]['fields']=='VVVVVVAV' and facts['equal'][0]=='11111111' and
              facts['samples'][1]['regular']==[True,False,False],'file absent attributes default');add('attrs')
        class Unavailable:
            def __getattr__(self,name):raise RuntimeError('private-metadata')
        facts=_wrapper_file_boundary_facts(dict(samples,opened=Unavailable()))
        check(facts['samples'][1]==dict(fields='UUUUUUUU',regular=[None]*3) and facts['equal'][0]=='????????',
              'file unavailable metadata distinction');add('unavailable')
        empty=_wrapper_file_boundary_facts({})
        check(empty==dict(_wrapper_file_boundary_fallback(),status='captured'),'file unreached samples');add('unreached')
        target={};_capture_wrapper_file_boundary(target,samples);first=target['boundary'];saved=copy.deepcopy(first)
        with patch(__name__+'._wrapper_file_boundary_facts',side_effect=blocked):_capture_wrapper_file_boundary(target,{})
        check(target['boundary'] is first and failure_equal(first,saved),'file first boundary overwritten');add('first')
        for label,change in [('shape',lambda v:v.update(raw='private')),('mask',lambda v:v['equal'].__setitem__(0,'private')),
            ('bool',lambda v:v['samples'][0]['regular'].__setitem__(0,1)),('state',lambda v:v.update(status='other'))]:
            malformed=copy.deepcopy(saved);change(malformed);target={}
            with patch(__name__+'._wrapper_file_boundary_facts',return_value=malformed):_capture_wrapper_file_boundary(target,samples)
            check(target['boundary']==_wrapper_file_boundary_fallback(),'file malformed capture not unavailable');add('capture-'+label)
        target={}
        with patch.object(json,'dumps',side_effect=RuntimeError('private-serialize')):_capture_wrapper_file_boundary(target,samples)
        check(target['boundary']==_wrapper_file_boundary_fallback(),'file serializer capture not unavailable');add('serialize')
        primary=ValueError('wrapper file boundary: hash');target={}
        def unavailable(_):
            check(target.get('boundary')==_wrapper_file_boundary_fallback(),'file fallback installed too late')
            raise RuntimeError('private-capture')
        try:
            try:raise primary
            except ValueError:
                with patch(__name__+'._wrapper_file_boundary_facts',side_effect=unavailable):
                    _capture_wrapper_file_boundary(target,samples)
                raise
        except ValueError as error:check(error is primary,'file capture replaced primary error')
        check(target['boundary']==_wrapper_file_boundary_fallback(),'file capture unavailable fallback');add('fallback')
        for label,detail in [('maximum',_wrapper_file_boundary_maximum()),('fallback',_wrapper_file_boundary_fallback())]:
            for ending in ('\n','\r\n'):
                raw=(json.dumps({'boundary':detail},sort_keys=True,indent=2)+'\n').replace('\n',ending).encode()
                check(len(raw)<=1024 and b'private' not in raw,'file boundary byte/privacy cap')
            add(label+'-cap')
        primary=ValueError('wrapper file boundary: capture-initialization');target={}
        try:
            try:raise primary
            except ValueError:
                with patch(__name__+'._wrapper_file_boundary_fallback',side_effect=RuntimeError('private-fallback')):
                    _capture_wrapper_file_boundary(target,samples)
                raise
        except ValueError as error:
            check(error is primary and failure_equal(target,dict(checks='')) and 'private' not in json.dumps(target),
                  'file initial capture replaced primary or invented facts')
        add('initial-fallback')
    row['passed']=True
    return row


def _wrapper_retention_fixtures():
    from types import SimpleNamespace
    cached=dict(_detail_fixture()['ownership'],classification='capture-not-finalized',exit=-(2**63),
        elapsed_seconds=sys.float_info.max,root_pid=None,cleanup_error='private job termination failed',
        capture_error='reader-state-unavailable',stdout=dict(size=65536,sha256='f'*64),stderr=dict(size=65536,sha256='e'*64))
    events=['%02d:%s'%(phase,edge) for phase in range(20) for edge in ('B','E')]
    with patch(__name__+'._wrapper_marker_file',return_value=_wrapper_marker_events(events)):
        maximum=_wrapper_failure_detail(SimpleNamespace(result=cached),Path('/fixture'))
    maximum['markers']['phase04_work']=[47,20000,47,20000,40]
    prefix=_wrapper_marker_events(['%02d:%s'%(p,e) for p in range(4) for e in ('B','E')]+['04:B','19:B','19:E'])
    prefix['phase04_failure']=dict(action='22',category='OT')
    prefix['build_phase_catch']=dict(reason='binary-unavailable',category='OT')
    prefix['build_progress']='RIF'
    prefix['phase04_work']=[41,20000,39,20000,40]
    with patch(__name__+'._wrapper_marker_file',return_value=prefix):
        interrupted=_wrapper_failure_detail(SimpleNamespace(result=_detail_fixture()['ownership']),Path('/fixture'))
    fixtures={'wrapper-maximum':maximum,'wrapper-prefix':interrupted,'wrapper-fallback':_wrapper_fallback()}
    for name,value in fixtures.items():
        _validate_wrapper_detail(value)
        check(value['complete'] is (name!='wrapper-fallback'),'wrapper fixture completeness')
        detached=q._bounded_failure_detail(value,_wrapper_fallback(),4096)
        check(failure_equal(detached,value),'required wrapper fixture replaced by fallback')
        for ending in ('\n','\r\n'):
            raw=(json.dumps({'failure_detail':value},sort_keys=True,indent=2,allow_nan=False)+'\n').replace('\n',ending).encode()
            check(len(raw)<=4096,'maximum wrapper enclosing detail cap')
    return fixtures


def wrapper_retention_controls(root,final_controls):
    """Serial fixtures exercise the real renderer, inverse and unchanged collector."""
    stage=root/'stages/tiny';stage.mkdir(parents=True)
    terminal=_detail_fixture()['ownership'];terminal['classification']='nonzero child exit'
    rows_before=copy.deepcopy(final_controls);outcomes=[]
    fixtures=_wrapper_retention_fixtures()
    cases=[(label,detail,None) for label,detail in fixtures.items()]
    cases += [('file-maximum',fixtures['wrapper-maximum'],_wrapper_file_boundary_maximum()),
              ('file-unavailable',fixtures['wrapper-maximum'],_wrapper_file_boundary_fallback(WRAPPER_FILE_BASES[1]))]
    for label,detail,boundary in cases:
        for newline,ending in [('LF','\n'),('CRLF','\r\n')]:
            failure=dict(passed=False,error='timeout',controls=copy.deepcopy(final_controls),failure_detail=copy.deepcopy(detail))
            if boundary is not None:
                matches=[row for row in failure['controls'] if row['name']=='wrapper-bounded-file']
                check(len(matches)==1,'file boundary retention row inventory')
                matches[0].update(boundary=copy.deepcopy(boundary),checks='boOBAOPBp',passed=False)
                failure['error']='wrapper file boundary: reparse-before'
            before=copy.deepcopy(failure);raw=(render_selftest_failure(failure)+ending).encode()
            check(failure_equal(expand_failure_v2(raw),before) and failure_equal(failure,before),'wrapper failure renderer facts')
            (stage/'stderr.bin').write_bytes(raw);(stage/'stdout.bin').write_bytes(b'')
            row=dict(schema='qbrain-n49d-stage-v1',name='tiny',identity=identity(),ownership=terminal,
                classification='nonzero child exit',argv=['python','selftest'],cwd='/fixture',timeout_seconds=120,
                stream_limit=65536,exit=1,elapsed_seconds=20.0,requested_reports=[],available_reports={},
                binaries_before={},binaries_after={},runtime_options={},stdout=q.descriptor(stage/'stdout.bin'),stderr=q.descriptor(stage/'stderr.bin'))
            record=(json.dumps(row,sort_keys=True,indent=2)+'\n').replace('\n',ending).encode()
            check(len(raw)<=65536 and len(record)<=16384,'wrapper retained stream/record cap')
            (stage/'result.json').write_bytes(record)
            packet=q.failure_diagnostics(root,root/'failure.json',identity(),['tiny'],['tiny'],'timeout')
            for leaf,expected in [('stderr.bin',raw),('stdout.bin',b''),('result.json',record)]:
                retained=packet['files']['stages/tiny/'+leaf]
                check(retained['truncated'] is False and retained['retained_offset']==0 and retained['size']==len(expected) and
                    retained['sha256']==hashlib.sha256(expected).hexdigest() and base64.b64decode(retained['data'])==expected,'wrapper collector retained bytes')
            retained=base64.b64decode(packet['files']['stages/tiny/stderr.bin']['data'])
            check(failure_equal(expand_failure_v2(retained),before) and packet['passed'] is False and packet['error']=='timeout' and
                packet['status']=='failed-partial-diagnostics','wrapper collector changed original failure')
            encoded=(root/'failure.json').read_bytes();payload=sum(len(v.get('data','')) for v in packet['files'].values())
            check(len(encoded)<=262144 and len(encoded)+encoded.count(b'\n')<=262144 and
                len(encoded)-payload<=12288 and len(encoded)+encoded.count(b'\n')-payload<=12288,'wrapper collector dual-newline admission')
            outcomes.append(dict(name='failure-detail-final-retention-'+label+'-'+newline,passed=True))
    check(failure_equal(final_controls,rows_before),'wrapper final control roster mutated')
    RESULTS.extend(outcomes)


def wrapper_evidence_controls(root):
    """Finite cached-owner/marker models; one serial file, no process operations.

    Trace tokens retain every named case and its actual result. Fixed result codes
    are V=valid-prefix, A=absent, P=partial-line, M=malformed, U=stream-unavailable,
    X=stream-mismatch, I=owner-invalid, N=owner-unavailable, E=owner-ineligible,
    C=captured, F=detail-unavailable. Caller letters: C=construct,W=wait,G=result.
    File call letters: L=lstat,O=open,F=fstat,R=read,C=close.
    Failure-only checks: b/o/p=regular before/opened/path_after; B/O/A/P=
    identity before/opened/after/path_after. They observe existing pure calls.
    String-field prefixes: c=classification,u=cleanup_error,a=capture_error.
    """
    from contextlib import ExitStack
    global FAILURE_DETAIL
    saved=FAILURE_DETAIL;root.mkdir();leaf=root/'stderr.bin'
    codes={'valid-prefix':'V','absent':'A','partial-line':'P','malformed':'M',
        'stream-unavailable':'U','stream-mismatch':'X','owner-invalid':'I',
        'owner-unavailable':'N','owner-ineligible':'E','captured':'C','detail-unavailable':'F'}
    empty=hashlib.sha256(b'').hexdigest();line=b'N49D_WRAPPER_V1:00:B\n'
    phases=['%02d:%s'%(n,e) for n in range(20) for e in ('B','E')]
    def desc(raw):return dict(size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    def base():
        return dict(classification='timeout',exit=259,elapsed_seconds=20.0,root_pid=482731965,
            cleanup_ok=True,owned_tree_empty=True,readers_done=True,stable=True,
            cleanup_error=None,capture_error=None,stdout=desc(b''),stderr=desc(line))
    def group(name):
        row=dict(name='wrapper-'+name,passed=False,trace=[]);RESULTS.append(row);return row
    def record(row,label,outcome):row['trace'].append(label+'='+str(outcome))
    def finish(row):row['passed']=True
    class Owner:
        def __init__(self,value,trace=None,fault=None):self.value=value;self.trace=[] if trace is None else trace;self.fault=fault
        @property
        def result(self):
            self.trace.append('G')
            if self.fault is not None:
                check(failure_equal(FAILURE_DETAIL,_wrapper_fallback()),'wrapper fallback installed after cached-result getter')
                raise self.fault
            return self.value
        def wait(self):
            self.trace.append('W')
            if getattr(self,'failure',None) is not None:raise self.failure
        def __getattr__(self,key):
            if key in ('proc','tree','poll','active','terminate','close','kill','_end'):
                self.trace.append('!'+key);raise AssertionError('unexpected owner operation')
            raise AttributeError(key)
    class Text(str):pass
    class Integer(int):pass
    class Float(float):pass
    class Mapping(dict):pass
    class Sequence(list):pass
    missing=object()
    def marker_stub(path,item):
        check(path==root and item==desc(line),'wrapper model fixed stream path/descriptor')
        return _wrapper_marker_events(['00:B'])
    def no_open(*args,**kwargs):raise AssertionError('ineligible wrapper opened a stream')
    def build(value):
        owner=Owner(value)
        with patch(__name__+'._wrapper_marker_file',side_effect=marker_stub) as marker,patch.object(os,'open',side_effect=no_open):
            result=_wrapper_failure_detail(owner,root)
        check(owner.trace==['G'],'wrapper builder queried owner operations')
        _validate_wrapper_detail(result)
        return result,marker.call_count
    def put(value,key,item):
        if item is missing:value.pop(key,None)
        else:value[key]=item
    def assert_invalid(row,label,key,item):
        value=base();put(value,key,item);before=dict(value)
        result,opens=build(value);record(row,label,codes[result['reason']])
        check(result['reason']=='owner-invalid' and result['owner']['status']=='partial' and not result['complete'] and opens==0,
            'wrapper malformed owner accepted: '+label)
        check(result['owner'].get('root_pid_recorded' if key=='root_pid' else key) is None,
            'wrapper malformed field not null: '+label)
        check(set(value)==set(before) and all(value[k] is before[k] for k in value),'wrapper input mapping changed: '+label)
    def assert_detail_rejected(row,label,mutate):
        value=_wrapper_fallback();mutate(value)
        try:_validate_wrapper_detail(value)
        except (ValueError,TypeError,KeyError):record(row,label,'reject')
        else:raise ValueError('wrapper detail type accepted: '+label)
    try:
        # Actual caller: every ownership operation is modeled and counted.
        row=group('caller')
        for label,where,classification in [('timeout','wait','timeout'),('nonzero','wait','nonzero child exit'),
                                          ('constructor','constructor','cleanup-failed'),('ordinary','ordinary','timeout'),('success','success','passed')]:
            FAILURE_DETAIL=None;trace=[];value=base();value['classification']=classification
            owner=Owner(value,trace);primary=q.OwnedChildError('wrapper primary '+label,owner)
            if where=='ordinary':primary=RuntimeError('ordinary constructor primary')
            if where=='wait':owner.failure=primary
            def constructor(*args,**kwargs):
                trace.append('C')
                expected=['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(root/'fixture.ps1'),
                    '-Wrapper',str(root/'wrapper.ps1'),'-Python',sys.executable]
                check(args[0]==expected and args[1]==root and args[2]==dict(os.environ) and args[3] is subprocess.DEVNULL and
                    args[4:]==(root/'stdout.bin',leaf,20,65536) and not kwargs,'wrapper caller contract changed')
                if where in ('constructor','ordinary'):raise primary
                return owner
            with patch.object(q,'OwnedChild',side_effect=constructor),patch(__name__+'._wrapper_marker_file',side_effect=marker_stub),\
                 patch.object(Path,'read_text',return_value='unchanged\nWRAPPER_CONTROLS_OK\n') as output:
                try:_run_windows_wrapper(root,root/'fixture.ps1',root/'wrapper.ps1')
                except BaseException as caught:check(where!='success' and caught is primary,'wrapper replaced original caller exception')
                else:check(where=='success','wrapper converted failure to success')
                expected_trace={'wait':['C','W','G'],'constructor':['C','G'],'ordinary':['C'],'success':['C','W']}[where]
                check(trace==expected_trace,'wrapper caller repeated operations')
                check(output.call_count==(1 if where=='success' else 0),'wrapper stdout success semantics changed')
                if where in ('success','ordinary'):check(FAILURE_DETAIL is None,'wrapper fabricated constructor/success evidence')
                else:
                    check(FAILURE_DETAIL['complete'] is True and FAILURE_DETAIL['owner']['classification']['category']==classification,
                        'wrapper caller lost error.owner')
                    first=FAILURE_DETAIL;_capture_wrapper_failure(primary,root)
                    check(FAILURE_DETAIL is first and trace==expected_trace,'wrapper caller retried first capture')
            record(row,label,''.join(trace))
        # Failed suffix remains the same selected ordinary positive-check failure.
        FAILURE_DETAIL=None;owner=Owner(base());trace=owner.trace
        with patch.object(q,'OwnedChild',return_value=owner),patch.object(Path,'read_text',return_value='wrong suffix'):
            try:_run_windows_wrapper(root,root/'fixture.ps1',root/'wrapper.ps1')
            except ValueError as error:check(str(error)=='actual wrapper API controls incomplete','wrapper success suffix primary changed')
            else:raise ValueError('wrapper suffix negative passed')
        check(trace==['W'] and FAILURE_DETAIL is None,'wrapper suffix failure invoked diagnostic capture')
        record(row,'suffix','W');finish(row)

        row=group('latch')
        original_builder=_wrapper_failure_detail;original_validate=_validate_wrapper_detail
        complete,_=build(base());incomplete,_=build(None)
        for label,first_candidate in [('complete',complete),('incomplete',incomplete)]:
            FAILURE_DETAIL=None;candidate=copy.deepcopy(first_candidate);before=copy.deepcopy(candidate);owner=Owner(base())
            error=q.OwnedChildError('first primary',owner)
            with patch(__name__+'._wrapper_failure_detail',return_value=candidate) as builder:
                _capture_wrapper_failure(error,root);first=FAILURE_DETAIL
                check(failure_equal(first,candidate) and first is not candidate and first['owner'] is not candidate['owner'] and
                    first['markers']['events'] is not candidate['markers']['events'],'wrapper detail not detached')
                candidate['markers']['events'].append('private-copy-mutation')
                _capture_wrapper_failure(error,root)
                check(FAILURE_DETAIL is first and failure_equal(first,before) and builder.call_count==1 and owner.trace==[],
                    'wrapper first capture changed or retried')
            record(row,label,codes[first['reason']])
        class GetterError(q.OwnedChildError):
            def __init__(self,trace):ValueError.__init__(self,'first primary');self.trace=trace
            @property
            def owner(self):
                self.trace.append('owner')
                check(failure_equal(FAILURE_DETAIL,_wrapper_fallback()),'wrapper fallback installed after first getter')
                raise RuntimeError('private-owner-getter')
        for label in ('owner-getter','result-getter','builder','validation','copy','detachment','detached-change','detached-validation','serialization','encoding','limit'):
            FAILURE_DETAIL=None;calls=[];owner=Owner(base(),fault=RuntimeError('private-result-getter') if label=='result-getter' else None)
            error=GetterError(calls) if label=='owner-getter' else q.OwnedChildError('first primary',owner)
            candidate=copy.deepcopy(complete)
            with ExitStack() as stack:
                if label=='builder':builder=stack.enter_context(patch(__name__+'._wrapper_failure_detail',side_effect=RuntimeError('private-builder')))
                elif label not in ('owner-getter','result-getter'):
                    builder=stack.enter_context(patch(__name__+'._wrapper_failure_detail',return_value=candidate))
                else:builder=stack.enter_context(patch(__name__+'._wrapper_failure_detail',wraps=original_builder))
                if label=='validation':stack.enter_context(patch(__name__+'._validate_wrapper_detail',side_effect=ValueError('private-validator')))
                if label=='copy':stack.enter_context(patch.object(json,'loads',side_effect=ValueError('private-copy')))
                if label=='detachment':stack.enter_context(patch.object(q,'_bounded_failure_detail',side_effect=RuntimeError('private-detachment')))
                if label=='detached-change':
                    changed=copy.deepcopy(candidate);changed['owner']['exit']=0
                    stack.enter_context(patch.object(q,'_bounded_failure_detail',return_value=changed))
                if label=='detached-validation':
                    def validate_twice(value):
                        calls.append('validate')
                        if len(calls)==2:raise ValueError('private-detached-validator')
                        return original_validate(value)
                    stack.enter_context(patch(__name__+'._validate_wrapper_detail',side_effect=validate_twice))
                if label in ('serialization','encoding','limit'):
                    stack.enter_context(patch.object(q,'_bounded_failure_detail',side_effect=lambda *a,**k:copy.deepcopy(candidate)))
                    if label=='serialization':stack.enter_context(patch.object(json,'dumps',side_effect=ValueError('private-serializer')))
                    elif label=='limit':stack.enter_context(patch.object(json,'dumps',return_value='x'*4096))
                    else:
                        class BadEncoding(str):
                            def replace(self,*args,**kwargs):return self
                            def __add__(self,other):return self
                            def encode(self,*args,**kwargs):raise UnicodeError('private-encoding')
                        stack.enter_context(patch.object(json,'dumps',return_value=BadEncoding('private-encoding')))
                owner.failure=error
                caller=patch.object(q,'OwnedChild',return_value=owner) if label=='builder' else patch.object(q,'OwnedChild',side_effect=error)
                with caller:
                    try:_run_windows_wrapper(root,root/'fixture.ps1',root/'wrapper.ps1')
                    except BaseException as caught:check(caught is error,'wrapper optional fault replaced primary')
                    else:raise ValueError('wrapper optional fault converted failure to success')
                first=FAILURE_DETAIL;count=builder.call_count;prior=list(owner.trace);prior_calls=list(calls)
                check(failure_equal(first,_wrapper_fallback()),'wrapper optional fault lost fixed fallback: '+label)
                _capture_wrapper_failure(error,root)
                check(FAILURE_DETAIL is first and builder.call_count==count and owner.trace==prior and calls==prior_calls,
                    'wrapper optional fault retried: '+label)
            # Optional dependency recovery still cannot replace the first fallback.
            with patch(__name__+'._wrapper_failure_detail',return_value=complete) as recovered:
                _capture_wrapper_failure(q.OwnedChildError('later primary',Owner(base())),root)
                check(FAILURE_DETAIL is first and recovered.call_count==0,'wrapper recovered dependency relatched')
            check('!' not in ''.join(owner.trace),'wrapper optional fault queried owner')
            if label=='builder':check(owner.trace==['W'],'wrapper diagnostic failure repeated wait')
            record(row,label,'F'+str(count)+('W' if label=='builder' else ''))
        for label,existing in [('foreign',{'already':'selected'}),('complete',complete),('fallback',_wrapper_fallback())]:
            FAILURE_DETAIL=existing;calls=[];error=GetterError(calls)
            with patch(__name__+'._wrapper_failure_detail',side_effect=AssertionError('builder reached')) as builder:
                _capture_wrapper_failure(error,root)
            check(FAILURE_DETAIL is existing and calls==[] and not builder.called,'wrapper replaced existing context')
            record(row,'prior-'+label,'0')
        finish(row)

        row=group('owner-scalars')
        for label,value in [('none',None),('list',[]),('text','private-result'),('map-sub',Mapping(base()))]:
            result,opens=build(value);record(row,'result.'+label,codes[result['reason']])
            check(result['reason']=='owner-unavailable' and opens==0,'wrapper invalid cached result available')
        unavailable=_wrapper_failure_detail(None,root);_validate_wrapper_detail(unavailable)
        check(unavailable['reason']=='owner-unavailable','wrapper missing owner available');record(row,'owner.none','N')
        for label,value in [('none',None),('zero',0),('seven',7),('259',259),('negative',-1),('min',-(2**63)),('max',2**63-1)]:
            cached=base();cached['exit']=value;result,opens=build(cached)
            check(result['owner']['exit'] is value and result['complete'] and opens==1,'wrapper exit reclassified')
            record(row,'exit.'+label,'C')
        for label,value in [('miss',missing),('true',True),('false',False),('float',1.0),('text','1'),('sub',Integer(1)),('low',-(2**63)-1),('high',2**63)]:
            assert_invalid(row,'exit.'+label,'exit',value)
        for label,value in [('none',None),('one',1),('max',2**63-1)]:
            cached=base();cached['root_pid']=value;result,opens=build(cached)
            check(result['owner']['root_pid_recorded'] is (value is not None) and result['complete'] and opens==1,'wrapper root recorded mapping')
            record(row,'root.'+label,str(int(result['owner']['root_pid_recorded'])))
        for label,value in [('miss',missing),('true',True),('false',False),('zero',0),('neg',-1),('high',2**63),('float',1.0),('text','1'),('sub',Integer(1))]:
            assert_invalid(row,'root.'+label,'root_pid',value)
        for label,value in [('zero',0),('float',0.0),('minuszero',-0.0),('fraction',1.25),('max',2**63-1)]:
            cached=base();cached['elapsed_seconds']=value;result,opens=build(cached)
            check(failure_equal(result['owner']['elapsed_seconds'],value) and result['complete'] and opens==1,'wrapper elapsed changed')
            record(row,'time.'+label,'C')
        for label,value in [('miss',missing),('none',None),('bool',True),('neg',-1),('nan',float('nan')),('inf',float('inf')),('ninf',-float('inf')),
                            ('text','1'),('intsub',Integer(1)),('fltsub',Float(1)),('high',2**63)]:
            assert_invalid(row,'time.'+label,'elapsed_seconds',value)
        finish(row)
        for key in ('cleanup_ok','owned_tree_empty','readers_done','stable'):
            row=group('flag-'+key)
            for label,value in [('true',True),('false',False)]:
                cached=base();cached[key]=value;result,opens=build(cached);record(row,label,codes[result['reason']])
                check(result['owner'][key] is value and result['complete'] is value and opens==int(value),
                    'wrapper false cleanup fact became true')
            for label,value in [('miss',missing),('none',None),('zero',0),('one',1),('text','true')]:assert_invalid(row,label,key,value)
            finish(row)

        aliases={'classification':'c','cleanup_error':'u','capture_error':'a'}
        row=group('strings-privacy')
        sentinel='private-wrapper-path/C:/secret/argv=hidden ENV=secret process=482731965 \u79d8\u5bc6'
        for field,known in [('classification',{v:v for v in WRAPPER_CLASSIFICATIONS}),('cleanup_error',WRAPPER_CLEANUP_CATEGORIES),
                            ('capture_error',{v:v for v in WRAPPER_CAPTURE_CATEGORIES})]:
            for index,(text,category) in enumerate(sorted(known.items())):
                cached=base();cached[field]=text;result,opens=build(cached);summary=result['owner'][field]
                check(summary==dict(category=category,bytes=len(text.encode()),sha256=hashlib.sha256(text.encode()).hexdigest()) and result['complete'],
                    'wrapper known string summary changed')
                record(row,aliases[field]+str(index),'C')
            for label,text in [('private',sentinel),('empty',''),('exact','\u00e9'*32768)]:
                cached=base();cached[field]=text;cached.update(argv=sentinel,path=sentinel,environment=sentinel,members=[sentinel])
                before=copy.deepcopy(cached);result,opens=build(cached);summary=result['owner'][field]
                check(summary==dict(category='other',bytes=len(text.encode()),sha256=hashlib.sha256(text.encode()).hexdigest()) and result['complete'],
                    'wrapper unknown string not fully hashed')
                raw=json.dumps(result,sort_keys=True)
                check(sentinel not in raw and '482731965' not in raw and 'argv' not in raw and 'environment' not in raw and
                    failure_equal(cached,before),'wrapper private text leaked or input changed')
                record(row,aliases[field]+'.'+label,'C')
            for label,value in [('bool',True),('int',1),('map',{}),('sub',Text('timeout')),('unicode','\ud800'),('over','\u00e9'*32768+'x')]:
                assert_invalid(row,aliases[field]+'.'+label,field,value)
            if field=='classification':
                for label,value in [('miss',missing),('none',None)]:assert_invalid(row,'c.'+label,field,value)
            else:
                cached=base();cached[field]=None;result,opens=build(cached)
                check(result['owner'][field]==dict(category='none',bytes=0,sha256=empty) and result['complete'],'wrapper null error category')
                record(row,aliases[field]+'.none','C')
                if field=='cleanup_error':assert_invalid(row,'cleanup.miss',field,missing)
                else:
                    cached.pop(field);result,opens=build(cached)
                    check(result['owner'][field]==dict(category='none',bytes=0,sha256=empty) and result['complete'],'wrapper optional capture error missing')
                    record(row,'capture.miss','C')
        finish(row)
        for field in ('stdout','stderr'):
            row=group('descriptor-'+field)
            variants=[('miss',missing),('none',None),('sub',Mapping(desc(line))),('extra',dict(desc(line),path='private')),
                ('nosize',{'sha256':empty}),('nohash',{'size':0}),('bool',dict(size=True,sha256=empty)),('neg',dict(size=-1,sha256=empty)),
                ('over',dict(size=65537,sha256=empty)),('float',dict(size=0.0,sha256=empty)),('intsub',dict(size=Integer(0),sha256=empty)),
                ('upper',dict(size=0,sha256='A'*64)),('short',dict(size=0,sha256='0'*63)),('badhex',dict(size=0,sha256='g'*64)),
                ('hashsub',dict(size=0,sha256=Text(empty))),('hashnone',dict(size=0,sha256=None))]
            for label,value in variants:assert_invalid(row,label,field,value)
            for label,size in [('zero',0),('cap',65536)]:
                value=dict(size=size,sha256=empty);retained=_wrapper_stream(value)
                check(retained==value and retained is not value,'wrapper exact descriptor boundary')
                record(row,label,'valid')
            finish(row)

        row=group('detail-validation')
        mutations=[('top-sub',lambda v:None),('schema-sub',lambda v:v.update(schema=Text(WRAPPER_SCHEMA))),
            ('site-sub',lambda v:v.update(site=Text('windows-wrapper-controls'))),('schema',lambda v:v.update(schema='wrong')),
            ('site',lambda v:v.update(site='wrong')),('extra',lambda v:v.update(private='hidden')),('missing',lambda v:v.pop('owner')),
            ('complete',lambda v:v.update(complete=0)),('reason-sub',lambda v:v.update(reason=Text('detail-unavailable'))),
            ('reason',lambda v:v.update(reason='private')),('timeout',lambda v:v.update(timeout_seconds=20.0)),
            ('cap',lambda v:v.update(stream_limit=Integer(65536))),('owner-sub',lambda v:v.update(owner=Mapping(v['owner']))),
            ('status',lambda v:v['owner'].update(status=Text('unavailable'))),('owner-extra',lambda v:v['owner'].update(pid=123)),
            ('owner-miss',lambda v:v['owner'].pop('exit')),('unavailable-fact',lambda v:v['owner'].update(stable=True)),
            ('exit-bool',lambda v:v['owner'].update(exit=True,status='partial')),('elapsed-inf',lambda v:v['owner'].update(elapsed_seconds=float('inf'),status='partial')),
            ('bool-int',lambda v:v['owner'].update(cleanup_ok=1,status='partial')),('markers-sub',lambda v:v.update(markers=Mapping(v['markers']))),
            ('marker-status',lambda v:v['markers'].update(status=Text('unavailable'))),('events-sub',lambda v:v['markers'].update(events=Sequence())),
            ('event-sub',lambda v:v['markers'].update(events=[Text('00:B')])),('marker-extra',lambda v:v['markers'].update(raw='private')),
            ('marker-miss',lambda v:v['markers'].pop('status')),('phase-bool',lambda v:v.update(markers=dict(_wrapper_marker_events(['00:B','00:E','01:B'],'malformed'),last_entered_phase=True))),
            ('valid-empty',lambda v:v['markers'].update(status='valid-prefix')),('false-captured',lambda v:v.update(reason='captured'))]
        for label,mutate in mutations:
            if label=='top-sub':
                try:_validate_wrapper_detail(Mapping(_wrapper_fallback()))
                except ValueError:record(row,label,'reject')
                else:raise ValueError('wrapper detail mapping subclass accepted')
            else:assert_detail_rejected(row,label,mutate)
        for field in ('classification','cleanup_error','capture_error'):
            for label,summary in [('sub',Mapping(category='other',bytes=1,sha256=empty)),('keys',dict(category='other',bytes=1,sha256=empty,raw='private')),
                                  ('category',dict(category=Text('other'),bytes=1,sha256=empty)),('bytes',dict(category='other',bytes=True,sha256=empty)),
                                  ('hash',dict(category='other',bytes=1,sha256='A'*64)),('none',dict(category='none',bytes=1,sha256=empty))]:
                assert_detail_rejected(row,aliases[field]+'.'+label,lambda v,field=field,summary=summary:v['owner'].update({field:summary},status='partial'))
        finish(row)

        row=group('marker-prefixes')
        for ending in (b'\n',b'\r\n'):
            for count in range(1,41):
                events=phases[:count];raw=b''.join(b'N49D_WRAPPER_V1:'+event.encode()+ending for event in events)
                actual=_wrapper_parse_markers(raw);expected=_wrapper_marker_events(events)
                entered=(count-1)//2;completed=(count-2)//2 if count>=2 else None
                check(actual==expected and actual['status']=='valid-prefix' and actual['events']==events and
                    actual['last_entered_phase']==entered and actual['last_completed_phase']==completed and actual['interrupted_phase'] is None,
                    'wrapper valid marker prefix boundary')
                record(row,('L' if ending==b'\n' else 'C')+str(count),codes[actual['status']])
        check(sum(len(b'N49D_WRAPPER_V1:'+event.encode()+b'\r\n\r\n') for event in phases)<=2048,'wrapper emission byte bound')
        finish(row)
        row=group('marker-cleanup')
        for phase in range(19):
            for closed in (False,True):
                events=phases[:phase*2+1]+['19:B']+(['19:E'] if closed else [])
                raw=b''.join(b'N49D_WRAPPER_V1:'+event.encode()+b'\n' for event in events)
                actual=_wrapper_parse_markers(raw)
                check(actual['status']=='valid-prefix' and actual['events']==events and actual['interrupted_phase']==phase and
                    actual['last_entered_phase']==19 and actual['last_completed_phase']==(19 if closed else phase-1 if phase else None),
                    'wrapper unfinished phase cleanup transition')
                record(row,'%02d%s'%(phase,'E' if closed else 'B'),codes[actual['status']])
        # Cleanup may also follow each completed nonempty prefix.
        for phase in range(19):
            events=phases[:phase*2+2]+['19:B','19:E'];actual=_wrapper_parse_markers(b''.join(b'N49D_WRAPPER_V1:'+e.encode()+b'\n' for e in events))
            check(actual['status']=='valid-prefix' and actual['events']==events and actual['interrupted_phase'] is None and
                actual['last_entered_phase']==19 and actual['last_completed_phase']==19,'wrapper completed phase cleanup transition')
            record(row,'%02dC'%phase,codes[actual['status']])
        finish(row)
        row=group('marker-negatives')
        tagged=lambda events:b''.join(b'N49D_WRAPPER_V1:'+e+b'\n' for e in events)
        cases=[('empty',b'','absent',[]),('private',b'private-path\xff\x00 secret argv environment\n','absent',[]),
            ('unrelated-separators',b'private\rN49D_WRAPPER_V1:00:B\n','absent',[]),
            ('leading-space',b' N49D_WRAPPER_V1:00:B\n','absent',[]),('partial',line[:-1],'partial-line',[]),
            ('prefix-partial',line+b'N49D_WRAPPER_V1:00:E','partial-line',['00:B']),
            ('cr-only',line[:-1]+b'\r','partial-line',[]),('foreign',b'N49D_WRAPPER_V2:00:B\n','malformed',[]),
            ('family',b'N49D_WRAPPER_BAD\n','malformed',[]),('range',tagged([b'20:B']),'malformed',[]),
            ('edge',tagged([b'00:X']),'malformed',[]),('digits',tagged([b'0:B']),'malformed',[]),
            ('suffix',line[:-1]+b'x\n','malformed',[]),('duplicate',tagged([b'00:B',b'00:B']),'malformed',['00:B']),
            ('reverse',tagged([b'00:E']),'malformed',[]),('skip',tagged([b'00:B',b'01:B']),'malformed',['00:B']),
            ('cleanup-first',tagged([b'19:B']),'malformed',[]),('cleanup-end-first',tagged([b'00:B',b'19:E']),'malformed',['00:B']),
            ('after-cleanup',tagged([b'00:B',b'19:B',b'19:E',b'00:E']),'malformed',['00:B','19:B','19:E']),
            ('cleanup-repeat',tagged([b'00:B',b'19:B',b'19:B']),'malformed',['00:B','19:B']),
            ('no-recovery',line+b'N49D_WRAPPER_V2:00:E\n'+tagged([b'00:E',b'01:B']),'malformed',['00:B']),
            ('opaque-interleave',b'private\xff\n'+line+b'private\r\x0b\x0c\n'+tagged([b'00:E']),'valid-prefix',['00:B','00:E'])]
        for label,raw,status,events in cases:
            actual=_wrapper_parse_markers(raw);record(row,label,codes[actual['status']])
            check(actual==_wrapper_marker_events(events,status),'wrapper malformed marker recovery: '+label)
            check('private' not in json.dumps(actual),'wrapper marker private text leaked')
        for label,raw in [('sub',type('Bytes',(bytes,),{})(line)),('text',line.decode()),('over',b'x'*65537)]:
            try:_wrapper_parse_markers(raw)
            except ValueError:record(row,label,'reject')
            else:raise ValueError('wrapper parser input cap/type accepted')
        finish(row)

        wrapper_stat_compat_controls();wrapper_file_version_controls()
        file_facts=wrapper_file_boundary_controls()
        row=group('bounded-file')
        original_sha256=hashlib.sha256;original_identity=_wrapper_file_identity;original_regular=_wrapper_regular
        original_open=os.open;original_fstat=os.fstat;original_fdopen=os.fdopen;original_close=os.close;original_lstat=Path.lstat
        written=0;peak=0;symlink_bytes=0
        def write(raw):
            nonlocal written,peak
            leaf.write_bytes(raw);written+=len(raw);peak=max(peak,len(raw))
        class Meta:
            def __init__(self,value,change=None):
                for name in ('st_dev','st_ino','st_mode','st_size','st_mtime_ns','st_ctime_ns','st_file_attributes'):
                    setattr(self,name,getattr(value,name,0))
                if hasattr(value,'st_birthtime_ns'):self.st_birthtime_ns=value.st_birthtime_ns
                if change is not None:setattr(self,change[0],change[1])
        def file_case(label,descriptor,status,trace,digests,gates,read_length,fault=None):
            if WRAPPER_FILE_WINDOWS:gates=gates.replace('AB','AO')
            calls=[];counts={'lstat':0,'fstat':0};reads=[];hits=[];hashes=[];samples={};checks=[];read_lengths=[]
            def inject():hits.append(fault)
            def remember(name,value):samples[name]=value;return value
            def sha256(*args,**kwargs):
                hashes.append(True);return original_sha256(*args,**kwargs)
            def tag(value):
                return next((code for name,code in zip(WRAPPER_FILE_SAMPLES,'BOAP') if samples.get(name) is value),'?')
            def identity(value,*args):checks.append(tag(value));return original_identity(value,*args)
            def regular(value):checks.append(tag(value).lower());return original_regular(value)
            def lstat(path,*args,**kwargs):
                check(path==leaf,'wrapper accessed arbitrary stream path');calls.append('L');counts['lstat']+=1
                if fault=='lstat'+str(counts['lstat']):inject();raise OSError('private-lstat')
                value=original_lstat(path,*args,**kwargs)
                if fault=='reparse-before' and counts['lstat']==1:inject();value=Meta(value,('st_file_attributes',1024))
                if fault=='path-after' and counts['lstat']==2:inject();value=Meta(value,('st_ino',value.st_ino+1))
                if fault=='reparse-after' and counts['lstat']==2:inject();value=Meta(value,('st_file_attributes',1024))
                return remember('before' if counts['lstat']==1 else 'path_after',value)
            def opened(path,flags,*args,**kwargs):
                calls.append('O');check(path==leaf and flags&getattr(os,'O_NOFOLLOW',0)==getattr(os,'O_NOFOLLOW',0) and
                    flags&getattr(os,'O_NONBLOCK',0)==getattr(os,'O_NONBLOCK',0),'wrapper open flags/path')
                if fault=='open':inject();raise OSError('private-open')
                return original_open(path,flags,*args,**kwargs)
            def fstat(fd):
                calls.append('F');counts['fstat']+=1
                if fault=='fstat'+str(counts['fstat']):inject();raise OSError('private-fstat')
                value=original_fstat(fd)
                if fault=='fd-before' and counts['fstat']==1:inject();value=Meta(value,('st_ino',value.st_ino+1))
                if fault=='fd-after' and counts['fstat']==2:inject();value=Meta(value,('st_mtime_ns',value.st_mtime_ns+1))
                if fault=='fd-nonregular' and counts['fstat']==1:inject();value=Meta(value,('st_mode',stat.S_IFDIR|0o700))
                if fault=='fd-reparse' and counts['fstat']==1:inject();value=Meta(value,('st_file_attributes',1024))
                return remember('opened' if counts['fstat']==1 else 'after',value)
            class Reader:
                def __init__(self,stream):self.stream=stream
                def __enter__(self):self.stream.__enter__();return self
                def __exit__(self,*args):return self.stream.__exit__(*args)
                def read(self,size):
                    calls.append('R');reads.append(size);check(size==65537,'wrapper unbounded/repeated read')
                    if fault=='read':inject();raise OSError('private-read')
                    raw=self.stream.read(size);read_lengths.append(len(raw));return raw
            def fdopen(fd,*args,**kwargs):
                check(args==('rb',) and kwargs==dict(buffering=0,closefd=False),'wrapper unbuffered descriptor mode')
                if fault=='fdopen':inject();raise OSError('private-fdopen')
                return Reader(original_fdopen(fd,*args,**kwargs))
            def close(fd):calls.append('C');return original_close(fd)
            recorded=False
            try:
                with patch.object(Path,'lstat',lstat),patch.object(os,'open',opened),patch.object(os,'fstat',fstat),\
                     patch.object(os,'fdopen',fdopen),patch.object(os,'close',close),patch.object(hashlib,'sha256',sha256),\
                     patch(__name__+'._wrapper_file_identity',identity),patch(__name__+'._wrapper_regular',regular):
                    actual=_wrapper_marker_file(root,descriptor)
                record(row,label,codes[actual['status']]+':'+''.join(calls));recorded=True
                check(actual['status']==status and ''.join(calls)==trace and len(hashes)==digests and
                    hits==([fault] if fault is not None else []) and ''.join(checks)==gates and
                    read_lengths==([] if read_length is None else [read_length]),'wrapper file boundary: '+label)
                check(len(reads)<=1,'wrapper file repeated read')
                check(calls.count('C')==(calls.count('O')-(1 if fault=='open' else 0)),'wrapper file descriptor leak')
                if status!='valid-prefix':check(actual['events']==[],'wrapper failed stream trusted marker prefix')
                else:check(actual==_wrapper_marker_events(['00:B']),'wrapper bounded file marker outcome')
            except BaseException:
                try:
                    if not recorded:record(row,label,'?:'+''.join(calls))
                    _capture_wrapper_file_boundary(row,samples,''.join(checks))
                except BaseException:pass
                raise
        # Exercise this exact except path with detached facts and no native I/O.
        file_facts['passed']=False;real_row=row
        real_io=(original_open,original_fstat,original_fdopen,original_close,original_lstat)
        row=dict(name='detached-primary',passed=False,trace=[])
        primary=ValueError('wrapper file boundary: primary-model')
        try:
            original_open=original_fstat=original_fdopen=original_close=original_lstat=no_open
            try:
                with patch(__name__+'._wrapper_marker_file',side_effect=primary),\
                     patch(__name__+'._wrapper_file_boundary_fallback',side_effect=RuntimeError('private-fallback')):
                    file_case('primary-model',desc(line),'valid-prefix','LOFRFLC',1,'boOBABPBp',len(line))
            except ValueError as error:
                check(error is primary and failure_equal(row,dict(name='detached-primary',passed=False,
                    trace=['primary-model=?:'],checks='')) and 'private' not in json.dumps(row),'file case primary replaced or secondary facts invented')
            else:raise ValueError('file case primary did not escape')
        finally:
            original_open,original_fstat,original_fdopen,original_close,original_lstat=real_io
            row=real_row
        file_facts['trace'].append('primary-case=ok');file_facts['passed']=True
        exact=b'x'*(65536-len(line)-1)+b'\n'+line
        write(exact);file_case('cap',desc(exact),'valid-prefix','LOFRFLC',1,'boOBABPBp',65536)
        write(exact+b'x');file_case('over',desc(exact),'stream-mismatch','LOFRFLC',0,'boOB',65537)
        write(b'');file_case('empty',desc(b''),'absent','',1,'',None)
        file_case('empty-hash',dict(size=0,sha256='0'*64),'stream-mismatch','',1,'',None)
        leaf.unlink();file_case('missing',desc(line),'stream-unavailable','L',0,'',None)
        leaf.mkdir();file_case('directory',desc(line),'stream-unavailable','L',0,'b',None);leaf.rmdir()
        try:leaf.symlink_to('stderr.bin')
        except (OSError,NotImplementedError) as error:record(row,'symlink-native','unavailable:'+type(error).__name__)
        else:
            symlink_bytes=10
            try:file_case('symlink',desc(line),'stream-unavailable','L',0,'b',None)
            finally:leaf.unlink()
        if hasattr(os,'mkfifo'):
            os.mkfifo(leaf)
            try:file_case('fifo',desc(line),'stream-unavailable','L',0,'b',None)
            finally:leaf.unlink()
        else:record(row,'fifo-native','unavailable')
        write(line)
        file_case('hash',dict(size=len(line),sha256='0'*64),'stream-mismatch','LOFRFLC',1,'boOB',len(line))
        file_case('size',dict(size=len(line)-1,sha256=desc(line)['sha256']),'stream-mismatch','LOFRFLC',0,'boOB',len(line))
        for fault,status,trace,digests,gates,length in [
            ('reparse-before','stream-unavailable','L',0,'b',None),('open','stream-unavailable','LO',0,'b',None),
            ('lstat1','stream-unavailable','L',0,'',None),('lstat2','stream-unavailable','LOFRFLC',0,'boOB',len(line)),
            ('fstat1','stream-unavailable','LOFC',0,'b',None),('fstat2','stream-unavailable','LOFRFC',0,'boOB',len(line)),
            ('read','stream-unavailable','LOFRC',0,'boOB',None),('fdopen','stream-unavailable','LOFC',0,'boOB',None),
            ('fd-before','stream-mismatch','LOFC',0,'boOB',None),('fd-after','stream-mismatch','LOFRFLC',1,'boOBAB',len(line)),
            ('path-after','stream-mismatch','LOFRFLC',1,'boOBABPB',len(line)),('fd-nonregular','stream-mismatch','LOFC',0,'bo',None),
            ('fd-reparse','stream-mismatch','LOFC',0,'bo',None),('reparse-after','stream-mismatch','LOFRFLC',1,'boOBABPB',len(line))]:
            file_case(fault,desc(line),status,trace,digests,gates,length,fault)
        check(written==131094 and peak==65537 and written+symlink_bytes<=131104,'wrapper serial fixture write budget')
        record(row,'bytes',str(written)+'/'+str(peak)+'/'+str(symlink_bytes));finish(row)

        row=group('no-process-operations')
        value=base();value['stderr']=desc(line);owner=Owner(value);before=copy.deepcopy(value)
        with ExitStack() as stack:
            for module,names in [(q.subprocess,('Popen','run','check_output','call')),
                                 (os,('kill','waitpid','waitid','pidfd_open'))]:
                for name in names:
                    if hasattr(module,name):stack.enter_context(patch.object(module,name,side_effect=AssertionError('wrapper process operation '+name)))
            result=_wrapper_failure_detail(owner,root)
        check(result['complete'] and owner.trace==['G'] and failure_equal(value,before),'wrapper capture queried or mutated owner')
        record(row,'real-read','G')
        for key in ('cleanup_ok','owned_tree_empty','readers_done','stable'):
            value=base();value[key]=False;owner=Owner(value)
            with patch.object(os,'open',side_effect=no_open),patch.object(Path,'lstat',side_effect=AssertionError('ineligible stat')):
                result=_wrapper_failure_detail(owner,root)
            check(result['reason']=='owner-ineligible' and owner.trace==['G'],'wrapper ineligible capture queried stream/process')
            record(row,key,'G0')
        for label,mutate in [('missing-descriptor',lambda v:v.pop('stderr')),('invalid-descriptor',lambda v:v.update(stderr=dict(size=True,sha256=empty))),
                            ('invalid-root',lambda v:v.update(root_pid=True)),('missing-result',lambda v:None)]:
            value=base();mutate(value);owner=Owner(None if label=='missing-result' else value)
            with patch.object(os,'open',side_effect=no_open),patch.object(Path,'lstat',side_effect=AssertionError('invalid stat')):
                result=_wrapper_failure_detail(owner,root)
            check(result['reason'] in ('owner-invalid','owner-unavailable') and owner.trace==['G'],'wrapper invalid capture queried stream/process')
            record(row,label,'G0')
        finish(row)
    finally:FAILURE_DETAIL=saved


def windows_wrapper_controls(root):
    if os.name!='nt':return
    root.mkdir();wrapper=q.ROOT/'scripts/build-tests-cl.ps1'
    guard.checkout_bytes(wrapper.read_bytes(),guard.WRAPPERS['scripts/build-tests-cl.ps1'],True)
    body=r'''param([string]$Wrapper,[string]$Python)
$ErrorActionPreference='Stop'
function Need($c,$m){if(-not $c){throw $m}}
function Reject([scriptblock]$f){$bad=$false;try{& $f}catch{$bad=$true};Need $bad 'Expected rejection'}
function Bytes($s){return ,[Text.Encoding]::UTF8.GetBytes($s)}
function Write-N49DWrapperMarker([int]$Id){try{$lines=@('N49D_WRAPPER_V1:00:B','N49D_WRAPPER_V1:00:E','N49D_WRAPPER_V1:01:B','N49D_WRAPPER_V1:01:E','N49D_WRAPPER_V1:02:B','N49D_WRAPPER_V1:02:E','N49D_WRAPPER_V1:03:B','N49D_WRAPPER_V1:03:E','N49D_WRAPPER_V1:04:B','N49D_WRAPPER_V1:04:E','N49D_WRAPPER_V1:05:B','N49D_WRAPPER_V1:05:E','N49D_WRAPPER_V1:06:B','N49D_WRAPPER_V1:06:E','N49D_WRAPPER_V1:07:B','N49D_WRAPPER_V1:07:E','N49D_WRAPPER_V1:08:B','N49D_WRAPPER_V1:08:E','N49D_WRAPPER_V1:09:B','N49D_WRAPPER_V1:09:E','N49D_WRAPPER_V1:10:B','N49D_WRAPPER_V1:10:E','N49D_WRAPPER_V1:11:B','N49D_WRAPPER_V1:11:E','N49D_WRAPPER_V1:12:B','N49D_WRAPPER_V1:12:E','N49D_WRAPPER_V1:13:B','N49D_WRAPPER_V1:13:E','N49D_WRAPPER_V1:14:B','N49D_WRAPPER_V1:14:E','N49D_WRAPPER_V1:15:B','N49D_WRAPPER_V1:15:E','N49D_WRAPPER_V1:16:B','N49D_WRAPPER_V1:16:E','N49D_WRAPPER_V1:17:B','N49D_WRAPPER_V1:17:E','N49D_WRAPPER_V1:18:B','N49D_WRAPPER_V1:18:E','N49D_WRAPPER_V1:19:B','N49D_WRAPPER_V1:19:E');if($Id -ge 0 -and $Id -lt 40){[Console]::Error.WriteLine("`n"+$lines[$Id]);[Console]::Error.Flush()}}catch{}} # N49D_WRAPPER_INSTRUMENTATION
function Write-N49DPhase04Failure($Record,$Action){ # N49D_WRAPPER_INSTRUMENTATION
 try{ # N49D_WRAPPER_INSTRUMENTATION
  if($script:n49dPhase04Latched){return};$script:n49dPhase04Latched=$true # N49D_WRAPPER_INSTRUMENTATION
  if($Action -cnotmatch '^(0[1-9]|[1-4][0-9]|5[0-3])$'){return} # N49D_WRAPPER_INSTRUMENTATION
  $category=switch -Exact ($Record.Exception.GetType().FullName){ # N49D_WRAPPER_INSTRUMENTATION
   'System.Management.Automation.RuntimeException'{'RT'} # N49D_WRAPPER_INSTRUMENTATION
   'System.Management.Automation.MethodInvocationException'{'MI'} # N49D_WRAPPER_INSTRUMENTATION
   'System.Management.Automation.ParameterBindingException'{'PB'} # N49D_WRAPPER_INSTRUMENTATION
   'System.IO.IOException'{'IO'} # N49D_WRAPPER_INSTRUMENTATION
   'System.ArgumentException'{'AR'} # N49D_WRAPPER_INSTRUMENTATION
   'System.InvalidOperationException'{'OP'} # N49D_WRAPPER_INSTRUMENTATION
   default{'OT'} # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  [Console]::Error.WriteLine("`nN49D_PHASE04_V1:"+$Action+':'+$category);[Console]::Error.Flush() # N49D_WRAPPER_INSTRUMENTATION
 }catch{} # N49D_WRAPPER_INSTRUMENTATION
} # N49D_WRAPPER_INSTRUMENTATION
function Write-N49DBuildProgress($Action,$Progress){ # N49D_WRAPPER_INSTRUMENTATION
 try{ # N49D_WRAPPER_INSTRUMENTATION
  if($script:n49dBuildProgressLatched){return};$script:n49dBuildProgressLatched=$true # N49D_WRAPPER_INSTRUMENTATION
  if($Action -cne '22'){return} # N49D_WRAPPER_INSTRUMENTATION
  $s=$Progress.S;$g=$Progress.G;$e=$Progress.E # N49D_WRAPPER_INSTRUMENTATION
  if($s -isnot [string] -or $g -isnot [string] -or $e -isnot [string]){return} # N49D_WRAPPER_INSTRUMENTATION
  if($s -cnotmatch '^[NARF]$' -or $g -cnotmatch '^[NCAFIXRS]$' -or $e -cnotmatch '^[NCALMWF]$'){return} # N49D_WRAPPER_INSTRUMENTATION
  [Console]::Error.WriteLine("`nN49D_BUILD_PROGRESS_V1:"+$s+$g+$e);[Console]::Error.Flush() # N49D_WRAPPER_INSTRUMENTATION
 }catch{} # N49D_WRAPPER_INSTRUMENTATION
} # N49D_WRAPPER_INSTRUMENTATION
function New-N49DWorkState($Writer,[scriptblock]$ClockFactory){ # N49D_WRAPPER_INSTRUMENTATION
 try{return [pscustomobject]@{Writer=$Writer;Clock=(& $ClockFactory);Started=0;Ended=0;Tick=[long]0;Disabled=$false}}catch{return $null} # N49D_WRAPPER_INSTRUMENTATION
} # N49D_WRAPPER_INSTRUMENTATION
function Write-N49DWork($State,$Id,$Edge){ # N49D_WRAPPER_INSTRUMENTATION
 try{ # N49D_WRAPPER_INSTRUMENTATION
  if($null -eq $State -or $State.Disabled){return};$State.Disabled=$true # N49D_WRAPPER_INSTRUMENTATION
  if($Id -isnot [string] -or $Id -cnotmatch '^(0[1-9]|[1-3][0-9]|4[0-7])$' -or $Edge -cnotin @('B','E')){return} # N49D_WRAPPER_INSTRUMENTATION
  $operation=[int]$Id;$start=$State.Started;$done=$State.Ended # N49D_WRAPPER_INSTRUMENTATION
  if($Edge -ceq 'B'){if(-not (($operation -eq $start+1 -and $start -eq $done) -or ($operation -eq 41 -and $start -ge 3 -and $start -lt 41) -or ($operation -eq 46 -and $start -ge 42 -and $start -lt 46))){return}}elseif($operation -ne $start -or $start -eq $done){return} # N49D_WRAPPER_INSTRUMENTATION
  $tick=$State.Clock.ElapsedMilliseconds;if($tick -isnot [long] -or $tick -lt 0){return};$tick=[Math]::Min([long]20000,$tick) # N49D_WRAPPER_INSTRUMENTATION
  if($tick -lt $State.Tick){return};$State.Tick=$tick # N49D_WRAPPER_INSTRUMENTATION
  if($Edge -ceq 'B'){$State.Started=$operation}else{$State.Ended=$operation} # N49D_WRAPPER_INSTRUMENTATION
  $State.Writer.WriteLine("`nN49D_WORK_V1:"+$Id+':'+$Edge+':'+$tick.ToString('D5',[Globalization.CultureInfo]::InvariantCulture));$State.Writer.Flush() # N49D_WRAPPER_INSTRUMENTATION
  $State.Disabled=$false # N49D_WRAPPER_INSTRUMENTATION
 }catch{} # N49D_WRAPPER_INSTRUMENTATION
} # N49D_WRAPPER_INSTRUMENTATION
Write-N49DWrapperMarker 0 # N49D_WRAPPER_INSTRUMENTATION
$t=$null;$e=$null;$ast=[Management.Automation.Language.Parser]::ParseFile($Wrapper,[ref]$t,[ref]$e)
Need (-not $e.Count) 'Wrapper syntax'
$functions=@($ast.EndBlock.Statements|Where-Object{$_ -is [Management.Automation.Language.FunctionDefinitionAst]})
foreach($f in $functions){. ([scriptblock]::Create($f.Extent.Text))}
function Write-N49DBuildCatch($Record,$Reason,$State){ # N49D_WRAPPER_INSTRUMENTATION
 try{ # N49D_WRAPPER_INSTRUMENTATION
  try{$n49dBuildCatchProgress.E='C'}catch{} # N49D_WRAPPER_INSTRUMENTATION
  if($State.Latched){try{$n49dBuildCatchProgress.E='A'}catch{};return};$State.Latched=$true # N49D_WRAPPER_INSTRUMENTATION
  try{$n49dBuildCatchProgress.E='L'}catch{} # N49D_WRAPPER_INSTRUMENTATION
  $fixedReason=switch -CaseSensitive -Exact ($Reason){'input-invalid'{'input-invalid'}'object-mismatch'{'object-mismatch'}'compile-failed'{'compile-failed'}'binary-unavailable'{'binary-unavailable'}'storage'{'storage'}default{'unknown'}} # N49D_WRAPPER_INSTRUMENTATION
  $category=switch -CaseSensitive -Exact ($Record.Exception.GetType().FullName){ # N49D_WRAPPER_INSTRUMENTATION
   'System.Management.Automation.RuntimeException'{'RT'} # N49D_WRAPPER_INSTRUMENTATION
   'System.Management.Automation.MethodInvocationException'{'MI'} # N49D_WRAPPER_INSTRUMENTATION
   'System.Management.Automation.ParameterBindingException'{'PB'} # N49D_WRAPPER_INSTRUMENTATION
   'System.IO.IOException'{'IO'} # N49D_WRAPPER_INSTRUMENTATION
   'System.ArgumentException'{'AR'} # N49D_WRAPPER_INSTRUMENTATION
   'System.InvalidOperationException'{'OP'} # N49D_WRAPPER_INSTRUMENTATION
   default{'OT'} # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  try{$n49dBuildCatchProgress.E='M'}catch{} # N49D_WRAPPER_INSTRUMENTATION
  [Console]::Error.WriteLine("`nN49D_BUILD_CATCH_V1:"+$fixedReason+':'+$category) # N49D_WRAPPER_INSTRUMENTATION
  try{$n49dBuildCatchProgress.E='W'}catch{} # N49D_WRAPPER_INSTRUMENTATION
  [Console]::Error.Flush() # N49D_WRAPPER_INSTRUMENTATION
  try{$n49dBuildCatchProgress.E='F'}catch{} # N49D_WRAPPER_INSTRUMENTATION
 }catch{} # N49D_WRAPPER_INSTRUMENTATION
} # N49D_WRAPPER_INSTRUMENTATION
function Test-N49DFunctionAst($Observed,$Expected,[string]$Name){ # N49D_WRAPPER_INSTRUMENTATION
 if($Expected -isnot [Management.Automation.Language.FunctionDefinitionAst] -or $Expected.Name -cne $Name){return $false} # N49D_WRAPPER_INSTRUMENTATION
 if($Observed -is [Management.Automation.Language.FunctionDefinitionAst]){$definition=$Observed;$body=$Observed.Body} # N49D_WRAPPER_INSTRUMENTATION
 elseif($Observed -is [Management.Automation.Language.ScriptBlockAst]){$definition=$Observed.Parent;$body=$Observed} # N49D_WRAPPER_INSTRUMENTATION
 else{return $false} # N49D_WRAPPER_INSTRUMENTATION
 if($definition -isnot [Management.Automation.Language.FunctionDefinitionAst] -or $body -isnot [Management.Automation.Language.ScriptBlockAst]){return $false} # N49D_WRAPPER_INSTRUMENTATION
 return ($definition.Name -ceq $Name -and $definition.Extent.Text -ceq $Expected.Extent.Text -and $body.Extent.Text -ceq $Expected.Body.Extent.Text -and [object]::ReferenceEquals($definition.Body,$body) -and [object]::ReferenceEquals($body.Parent,$definition)) # N49D_WRAPPER_INSTRUMENTATION
} # N49D_WRAPPER_INSTRUMENTATION
try{$n49dBuildCatchProgress=[pscustomobject]@{S='N';G='N';E='N'}}catch{} # N49D_WRAPPER_INSTRUMENTATION
try{ # N49D_WRAPPER_INSTRUMENTATION
 try{$n49dBuildCatchProgress.S='A'}catch{} # N49D_WRAPPER_INSTRUMENTATION
 $n49dBuildCatchSelected=@($functions|Where-Object{$_.Name -ceq 'Invoke-QbrainBuildPhase'}) # N49D_WRAPPER_INSTRUMENTATION
 if($n49dBuildCatchSelected.Count -ne 1){throw 'Catch selection'} # N49D_WRAPPER_INSTRUMENTATION
 $n49dBuildCatchOriginalAst=$n49dBuildCatchSelected[0];$n49dBuildCatchOriginalText=$n49dBuildCatchOriginalAst.Extent.Text # N49D_WRAPPER_INSTRUMENTATION
 $n49dBuildCatchInsertion="`n    try { `$n49dBuildCatchRecord=`$_;try{`$n49dBuildCatchProgress.G='C'}catch{};if (`$n49dPhase04Action -ceq '22') { try{`$n49dBuildCatchProgress.G='A'}catch{};if ([object]::ReferenceEquals(`$MyInvocation.MyCommand,`$n49dBuildCatchCommand)) { try{`$n49dBuildCatchProgress.G='F'}catch{};if ([object]::ReferenceEquals(`$MyInvocation.MyCommand.ScriptBlock,`$n49dBuildCatchBlock)) { try{`$n49dBuildCatchProgress.G='I'}catch{};`$null=Write-N49DBuildCatch `$n49dBuildCatchRecord `$reason `$n49dBuildCatchState } else { try{`$n49dBuildCatchProgress.G='S'}catch{} } } else { try{`$n49dBuildCatchProgress.G='R'}catch{} } } else { try{`$n49dBuildCatchProgress.G='X'}catch{} } } catch {} # N49D_WRAPPER_INSTRUMENTATION" # N49D_WRAPPER_INSTRUMENTATION
 $n49dBuildCatchFactory={param([string]$DefinitionText) [scriptblock]::Create($DefinitionText)} # N49D_WRAPPER_INSTRUMENTATION
 $n49dBuildCatchMakeState={[pscustomobject]@{Latched=$false}} # N49D_WRAPPER_INSTRUMENTATION
 $n49dBuildCatchActivate={param([scriptblock]$Definition) . $Definition} # N49D_WRAPPER_INSTRUMENTATION
 $n49dBuildCatchPrepared=$false;$n49dBuildCatchPreparation=[pscustomobject]@{Count=0} # N49D_WRAPPER_INSTRUMENTATION
 $n49dBuildCatchSetup={ # N49D_WRAPPER_INSTRUMENTATION
  try{ # N49D_WRAPPER_INSTRUMENTATION
   try{$n49dBuildCatchProgress.S='A'}catch{} # N49D_WRAPPER_INSTRUMENTATION
   $n49dBuildCatchReady=$false;$n49dBuildCatchCommand=$null;$n49dBuildCatchBlock=$null;$n49dBuildCatchState=$null;$n49dBuildCatchRollback=$null # N49D_WRAPPER_INSTRUMENTATION
   $n49dBuildCatchBefore=Get-Command -Name Invoke-QbrainBuildPhase -CommandType Function -ErrorAction Stop # N49D_WRAPPER_INSTRUMENTATION
   $n49dBuildCatchRollback=$n49dBuildCatchBefore.ScriptBlock # N49D_WRAPPER_INSTRUMENTATION
   if(-not (Test-N49DFunctionAst $n49dBuildCatchRollback.Ast $n49dBuildCatchOriginalAst 'Invoke-QbrainBuildPhase')){throw 'Catch baseline body'} # N49D_WRAPPER_INSTRUMENTATION
   if(-not $n49dBuildCatchPrepared){ # N49D_WRAPPER_INSTRUMENTATION
    $n49dBuildCatchPreparation.Count++ # N49D_WRAPPER_INSTRUMENTATION
    $n49dBuildCatchOuter=@($n49dBuildCatchOriginalAst.Body.EndBlock.Statements|Where-Object{$_ -is [Management.Automation.Language.TryStatementAst]}) # N49D_WRAPPER_INSTRUMENTATION
    if($n49dBuildCatchOuter.Count -ne 1 -or $n49dBuildCatchOuter[0].CatchClauses.Count -ne 1 -or $null -eq $n49dBuildCatchOuter[0].Finally){throw 'Catch shape'} # N49D_WRAPPER_INSTRUMENTATION
    $n49dBuildCatchOuterBody=$n49dBuildCatchOuter[0].CatchClauses[0].Body # N49D_WRAPPER_INSTRUMENTATION
    if($n49dBuildCatchOuterBody.Statements.Count -ne 3 -or $n49dBuildCatchOuterBody.Statements[0].Extent.Text -cne 'if ($Result.ExitCode -eq 0) { $Result.ExitCode=1 }'){throw 'Catch first statement'} # N49D_WRAPPER_INSTRUMENTATION
    $n49dBuildCatchOffset=$n49dBuildCatchOuterBody.Extent.StartOffset-$n49dBuildCatchOriginalAst.Extent.StartOffset+1 # N49D_WRAPPER_INSTRUMENTATION
    if($n49dBuildCatchOriginalText[$n49dBuildCatchOffset-1] -cne '{'){throw 'Catch offset'} # N49D_WRAPPER_INSTRUMENTATION
    $n49dBuildCatchInstrumentedText=$n49dBuildCatchOriginalText.Insert($n49dBuildCatchOffset,$n49dBuildCatchInsertion) # N49D_WRAPPER_INSTRUMENTATION
    if($n49dBuildCatchInstrumentedText.Remove($n49dBuildCatchOffset,$n49dBuildCatchInsertion.Length) -cne $n49dBuildCatchOriginalText){throw 'Catch preservation'} # N49D_WRAPPER_INSTRUMENTATION
    $n49dBuildCatchPrepared=$true # N49D_WRAPPER_INSTRUMENTATION
   } # N49D_WRAPPER_INSTRUMENTATION
   $n49dBuildCatchConstructed=@(& $n49dBuildCatchFactory $n49dBuildCatchInstrumentedText) # N49D_WRAPPER_INSTRUMENTATION
   if($n49dBuildCatchConstructed.Count -ne 1 -or $n49dBuildCatchConstructed[0] -isnot [scriptblock]){throw 'Catch constructor result'} # N49D_WRAPPER_INSTRUMENTATION
   $n49dBuildCatchDefinition=$n49dBuildCatchConstructed[0] # N49D_WRAPPER_INSTRUMENTATION
   $n49dBuildCatchParsed=@($n49dBuildCatchDefinition.Ast.EndBlock.Statements) # N49D_WRAPPER_INSTRUMENTATION
   if($n49dBuildCatchParsed.Count -ne 1 -or $n49dBuildCatchParsed[0] -isnot [Management.Automation.Language.FunctionDefinitionAst] -or $n49dBuildCatchParsed[0].Name -cne 'Invoke-QbrainBuildPhase' -or $n49dBuildCatchParsed[0].Extent.Text -cne $n49dBuildCatchInstrumentedText){throw 'Catch compiled extent'} # N49D_WRAPPER_INSTRUMENTATION
   $n49dBuildCatchParsedTry=@($n49dBuildCatchParsed[0].Body.EndBlock.Statements|Where-Object{$_ -is [Management.Automation.Language.TryStatementAst]}) # N49D_WRAPPER_INSTRUMENTATION
   if($n49dBuildCatchParsedTry.Count -ne 1 -or $n49dBuildCatchParsedTry[0].CatchClauses.Count -ne 1 -or $n49dBuildCatchParsedTry[0].CatchClauses[0].Body.Statements.Count -ne 4 -or $n49dBuildCatchParsedTry[0].CatchClauses[0].Body.Statements[0] -isnot [Management.Automation.Language.TryStatementAst]){throw 'Catch inserted node'} # N49D_WRAPPER_INSTRUMENTATION
   $n49dBuildCatchStates=@(& $n49dBuildCatchMakeState) # N49D_WRAPPER_INSTRUMENTATION
   if($n49dBuildCatchStates.Count -ne 1 -or $n49dBuildCatchStates[0].GetType() -ne [Management.Automation.PSCustomObject] -or $n49dBuildCatchStates[0].Latched -isnot [bool] -or $n49dBuildCatchStates[0].Latched){throw 'Catch initial state'} # N49D_WRAPPER_INSTRUMENTATION
   $null=. $n49dBuildCatchActivate $n49dBuildCatchDefinition # N49D_WRAPPER_INSTRUMENTATION
   $n49dBuildCatchAfter=Get-Command -Name Invoke-QbrainBuildPhase -CommandType Function -ErrorAction Stop # N49D_WRAPPER_INSTRUMENTATION
   if(-not (Test-N49DFunctionAst $n49dBuildCatchAfter.ScriptBlock.Ast $n49dBuildCatchParsed[0] 'Invoke-QbrainBuildPhase')){throw 'Catch installed body'} # N49D_WRAPPER_INSTRUMENTATION
   $n49dBuildCatchCommand=$n49dBuildCatchAfter;$n49dBuildCatchBlock=$n49dBuildCatchAfter.ScriptBlock;$n49dBuildCatchState=$n49dBuildCatchStates[0];$n49dBuildCatchReady=$true # N49D_WRAPPER_INSTRUMENTATION
   try{$n49dBuildCatchProgress.S='R'}catch{} # N49D_WRAPPER_INSTRUMENTATION
  }catch{ # N49D_WRAPPER_INSTRUMENTATION
   try{$n49dBuildCatchProgress.S='F'}catch{} # N49D_WRAPPER_INSTRUMENTATION
   try{$n49dBuildCatchReady=$false;$n49dBuildCatchCommand=$null;$n49dBuildCatchBlock=$null;$n49dBuildCatchState=$null;if($null -ne $n49dBuildCatchRollback){Set-Item -LiteralPath Function:\Invoke-QbrainBuildPhase -Value $n49dBuildCatchRollback -Force -ErrorAction Stop}}catch{} # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
 } # N49D_WRAPPER_INSTRUMENTATION
 $null=. $n49dBuildCatchSetup # N49D_WRAPPER_INSTRUMENTATION
}catch{try{$n49dBuildCatchProgress.S='F'}catch{}} # N49D_WRAPPER_INSTRUMENTATION
# Probe the diagnostic helper in the same owned Windows invocation; never start a second process. # N49D_WRAPPER_INSTRUMENTATION
$n49dSavedWriter=[Console]::Error;$n49dMemory=[IO.StringWriter]::new() # N49D_WRAPPER_INSTRUMENTATION
try{ # N49D_WRAPPER_INSTRUMENTATION
 [Console]::SetError($n49dMemory) # N49D_WRAPPER_INSTRUMENTATION
 foreach($n49dFault in @('none','getter','writer','restore')){ # N49D_WRAPPER_INSTRUMENTATION
  $script:n49dPhase04Latched=$false;$n49dMemory.GetStringBuilder().Clear()|Out-Null # N49D_WRAPPER_INSTRUMENTATION
  $n49dOriginal=$null;$n49dSeen=$null;$n49dFinally=0;$n49dPhase04Action='14' # N49D_WRAPPER_INSTRUMENTATION
  try{ # N49D_WRAPPER_INSTRUMENTATION
   try{try{throw 'n49d-primary'}finally{ # N49D_WRAPPER_INSTRUMENTATION
    $n49dPhase04PriorAction=$n49dPhase04Action;$n49dPhase04Action='16' # N49D_WRAPPER_INSTRUMENTATION
    if($n49dFault -ceq 'restore'){throw 'n49d-restore'} # N49D_WRAPPER_INSTRUMENTATION
    $n49dPhase04Action=$n49dPhase04PriorAction # N49D_WRAPPER_INSTRUMENTATION
   }}catch{ # N49D_WRAPPER_INSTRUMENTATION
    $n49dOriginal=$_ # N49D_WRAPPER_INSTRUMENTATION
    try{ # N49D_WRAPPER_INSTRUMENTATION
     $n49dRecord=$_ # N49D_WRAPPER_INSTRUMENTATION
     if($n49dFault -ceq 'getter'){$n49dRecord=[pscustomobject]@{};$n49dRecord|Add-Member ScriptProperty Exception {throw 'private-getter'}} # N49D_WRAPPER_INSTRUMENTATION
     if($n49dFault -ceq 'writer'){$n49dClosed=[IO.StringWriter]::new();$n49dClosed.Dispose();[Console]::SetError($n49dClosed)} # N49D_WRAPPER_INSTRUMENTATION
     Write-N49DPhase04Failure $n49dRecord $n49dPhase04Action # N49D_WRAPPER_INSTRUMENTATION
    }catch{} # N49D_WRAPPER_INSTRUMENTATION
    throw # N49D_WRAPPER_INSTRUMENTATION
   } # N49D_WRAPPER_INSTRUMENTATION
  }catch{$n49dSeen=$_}finally{$n49dFinally++;[Console]::SetError($n49dMemory)} # N49D_WRAPPER_INSTRUMENTATION
  Need ([object]::ReferenceEquals($n49dSeen.Exception,$n49dOriginal.Exception) -and $n49dSeen.FullyQualifiedErrorId -ceq $n49dOriginal.FullyQualifiedErrorId -and $n49dFinally -eq 1) 'Phase04 diagnostic primary changed' # N49D_WRAPPER_INSTRUMENTATION
  $n49dExpected=if($n49dFault -ceq 'restore'){'16'}else{'14'} # N49D_WRAPPER_INSTRUMENTATION
  Need ($n49dPhase04Action -ceq $n49dExpected) 'Phase04 restoration action changed' # N49D_WRAPPER_INSTRUMENTATION
  $n49dText=$n49dMemory.ToString() # N49D_WRAPPER_INSTRUMENTATION
  if($n49dFault -in @('getter','writer')){Need ($n49dText.Length -eq 0) 'Phase04 optional capture leaked'}else{Need ($n49dText -ceq ("`nN49D_PHASE04_V1:"+$n49dExpected+":RT"+[Environment]::NewLine)) 'Phase04 diagnostic token changed'} # N49D_WRAPPER_INSTRUMENTATION
  Write-N49DPhase04Failure $n49dSeen '53' # N49D_WRAPPER_INSTRUMENTATION
  Need ($n49dMemory.ToString() -ceq $n49dText) 'Phase04 first failure overwritten' # N49D_WRAPPER_INSTRUMENTATION
 } # N49D_WRAPPER_INSTRUMENTATION
 $script:n49dPhase04Latched=$false;$n49dMemory.GetStringBuilder().Clear()|Out-Null # N49D_WRAPPER_INSTRUMENTATION
 Write-N49DPhase04Failure ([pscustomobject]@{Exception=[FormatException]::new('private-unknown')}) '53' # N49D_WRAPPER_INSTRUMENTATION
 Need ($n49dMemory.ToString() -ceq ("`nN49D_PHASE04_V1:53:OT"+[Environment]::NewLine)) 'Phase04 unknown category leaked' # N49D_WRAPPER_INSTRUMENTATION
 $script:n49dPhase04Latched=$false;$n49dMemory.GetStringBuilder().Clear()|Out-Null # N49D_WRAPPER_INSTRUMENTATION
 Write-N49DPhase04Failure ([pscustomobject]@{Exception=[Exception]::new('private')}) 'private' # N49D_WRAPPER_INSTRUMENTATION
 Need ($n49dMemory.ToString().Length -eq 0) 'Phase04 unknown action leaked' # N49D_WRAPPER_INSTRUMENTATION
}finally{[Console]::SetError($n49dSavedWriter);$n49dMemory.Dispose();$script:n49dPhase04Latched=$false} # N49D_WRAPPER_INSTRUMENTATION
Write-N49DWrapperMarker 1 # N49D_WRAPPER_INSTRUMENTATION
Write-N49DWrapperMarker 2 # N49D_WRAPPER_INSTRUMENTATION
$root=Join-Path ([IO.Path]::GetTempPath()) ('qbrain-phase-'+[guid]::NewGuid().ToString('N'))
$out=Join-Path $root 'build\cl';$obj=Join-Path $out 'obj';$reports=Join-Path $root 'reports'
$oldTemp=$env:TEMP;$oldTmp=$env:TMP;$oldShadow=$env:ERRORLEVEL
try{
 $null=New-Item -ItemType Directory -Path $obj,$reports;$env:TEMP=$root;$env:TMP=$root
 $vc=Join-Path $root 'vcvars.bat';[IO.File]::WriteAllText($vc,'@exit /b 0')
 $context=[pscustomobject]@{Root=$root;Out=$out;ObjDir=$obj;Vcvars=$vc;Sqlite=$root;Inc=$root;Third=$root;PgRoot=$root}
 $inputs=Get-QbrainTestInputs
 foreach($n in $inputs.Produced){[IO.File]::WriteAllBytes((Join-Path $obj ($n+'.obj')),[byte[]](111))}
 [IO.File]::WriteAllBytes((Join-Path $out 'qbrain.exe'),[byte[]](112));$binary=Join-Path $out 'qbrain_tests.exe'
 $script:resolved=0;$script:executed=0;$script:rebuilt=0;$script:batch=''
 $resolver={$script:resolved++;return $context}
 $production={param($c,$r);$script:rebuilt++;Need ($c.Root -ceq $root) 'Production forwarding';$r.ExitCode=0}
 $adapter={param($b,$r);$script:executed++;$script:batch=$b;if($b -match '(?m)^cl '){[IO.File]::WriteAllBytes($binary,[byte[]](116))};$r.ExitCode=0}
 function Dispatch($o,[scriptblock]$exec=$adapter,[object[]]$extra=@()){
  $r=[pscustomobject]@{ExitCode=0};Invoke-QbrainTestsDispatcher $o $extra $resolver $exec $production $r 2>$null;return $r.ExitCode
 }
Write-N49DWrapperMarker 3 # N49D_WRAPPER_INSTRUMENTATION
Write-N49DWrapperMarker 4 # N49D_WRAPPER_INSTRUMENTATION
 $invalid=@(@{BuildOnly=$true;RunOnly=$true},@{RunOnly=$true},@{RunOnly=$true;PhaseContext='x';RunReport='y';SkipProductionBuild=$true},
  @{RunOnly=$true;PhaseContext='x';RunReport='y';TestSources=@('z')},@{RunOnly=$true;PhaseContext='x';RunReport='y';ProductionManifest='z'},
  @{BuildOnly=$true},@{BuildOnly=$true;SkipProductionBuild=$true;ProductionManifest='x';PhaseContext='y';TestSources=@('z')},
  @{BuildOnly=$true;SkipProductionBuild=$true;ProductionManifest='x';PhaseContext='y';RunReport='z'},
  @{PhaseContext='x'},@{ProductionManifest='x'},@{RunReport='x'},@{Unknown='x'})
 foreach($o in $invalid){Reject {Dispatch $o}}
 Reject {Dispatch @{} $adapter @('unused')}
 Need (($script:resolved+$script:executed+$script:rebuilt) -eq 0) 'Invalid arguments reached adapters'
 Reject {& $Wrapper -BuildOnly -RunOnly}
 Reject {& $Wrapper -RunOnly -SkipProductionBuild -PhaseContext x -RunReport y}
 $unknownCall={param($target) & $target -UnexpectedFixtureArgument}
 $bindOnly=[scriptblock]::Create($ast.ParamBlock.Extent.Text+"`n"+'[pscustomobject]@{Options=$PSBoundParameters;RemainingArguments=$args}')
 $unknownBound=& $unknownCall $bindOnly
 Need ($unknownBound.Options.Count -eq 0) 'Unknown argument bound as an option'
 Need (@($unknownBound.RemainingArguments).Count -eq 1 -and $unknownBound.RemainingArguments[0] -ceq '-UnexpectedFixtureArgument') 'Unknown argument was not retained'
 Reject {Assert-QbrainPhaseArguments $unknownBound.Options $unknownBound.RemainingArguments}
 Reject {& $unknownCall $Wrapper}
Write-N49DWrapperMarker 5 # N49D_WRAPPER_INSTRUMENTATION
Write-N49DWrapperMarker 6 # N49D_WRAPPER_INSTRUMENTATION
 Need ((Dispatch @{TestSources=@('tests\extra.cpp')}) -eq 0) 'Combined'
 Need ($script:rebuilt -eq 1) 'Production rebuild';Need ($script:batch.Contains('tests\extra.cpp')) 'Source forwarding'
 foreach($s in $inputs.TestSources){Need ($script:batch.Contains((Join-Path $root $s))) 'Canonical closure'}
 $b=$script:batch.Replace("`r`n","`n");$last=-1
 foreach($token in @('call "','cd /d ','cl /nologo','link /nologo','copy /y','echo TESTS_BUILD_OK',"qbrain_tests.exe`nexit /b")){
  $position=$b.IndexOf($token,$last+1,[StringComparison]::Ordinal);Need ($position -gt $last) 'Batch order';$last=$position
 }
 $guard=($b.Split("`n")[2..3]) -join "`n"
 Need ($guard -ceq "if errorlevel 1 exit /b 1`nif not errorlevel 0 exit /b 1") 'Exact zero guards'
 foreach($line in $b.Split("`n")){if($line -match '^(call |cd /d |cl |link |copy )'){Need ($b.Contains($line+"`n"+$guard)) 'Immediate guards'}}
 Need ((Dispatch @{SkipProductionBuild=$true}) -eq 0 -and $script:rebuilt -eq 1) 'Combined skip'
Write-N49DWrapperMarker 7 # N49D_WRAPPER_INSTRUMENTATION
Write-N49DWrapperMarker 8 # N49D_WRAPPER_INSTRUMENTATION
try{$n49dWork=$null;$n49dWork=New-N49DWorkState ([Console]::Error) {[Diagnostics.Stopwatch]::StartNew()}}catch{} # N49D_WRAPPER_INSTRUMENTATION
try{Write-N49DWork $n49dWork '01' 'B'}catch{} # N49D_WRAPPER_INSTRUMENTATION
$script:n49dPhase04Latched=$false;$n49dPhase04Action='01' # N49D_WRAPPER_INSTRUMENTATION
try{ # N49D_WRAPPER_INSTRUMENTATION
 $n49dPhase04Action='01' # N49D_WRAPPER_INSTRUMENTATION
 $id=[pscustomobject]@{commit=('c'*40);tree=('d'*40);run_id='1';run_attempt='1';job_key='windows-msvc';job_label='windows-msvc'}
 $n49dPhase04Action='02' # N49D_WRAPPER_INSTRUMENTATION
 [string[]]$produced=@($inputs.Produced|ForEach-Object{$_+'.obj'})
 $n49dPhase04Action='03' # N49D_WRAPPER_INSTRUMENTATION
 [string[]]$consumed=@($inputs.Consumed|ForEach-Object{$_+'.obj'})
 $n49dPhase04Action='04' # N49D_WRAPPER_INSTRUMENTATION
 [Array]::Sort($produced,[StringComparer]::Ordinal)
 $n49dPhase04Action='05' # N49D_WRAPPER_INSTRUMENTATION
 [Array]::Sort($consumed,[StringComparer]::Ordinal)
 $n49dPhase04Action='06' # N49D_WRAPPER_INSTRUMENTATION
 $entries=@(foreach($n in $produced){$d=Get-QbrainFileDescriptor (Join-Path $obj $n);[pscustomobject]@{name=$n;size=$d.size;sha256=$d.sha256}})
 $n49dPhase04Action='07' # N49D_WRAPPER_INSTRUMENTATION
 $manifest=[pscustomobject]@{schema='qbrain-n49d-build-objects-v1';state='ready';identity=$id;produced=[object[]]$entries;consumed=(@() + $consumed);production_executable=(Get-QbrainFileDescriptor (Join-Path $out 'qbrain.exe'));failure=$null}
 $n49dPhase04Action='08' # N49D_WRAPPER_INSTRUMENTATION
 Need ($manifest.produced.GetType() -eq [object[]] -and $manifest.consumed.GetType() -eq [object[]]) 'Manifest object array types'
 $n49dPhase04Action='09' # N49D_WRAPPER_INSTRUMENTATION
 Need ($manifest.produced.Count -eq 53 -and $manifest.consumed.Count -eq 51) 'Manifest inventory counts'
 $n49dPhase04Action='10' # N49D_WRAPPER_INSTRUMENTATION
 for($i=0;$i -lt $consumed.Count;$i++){Need ($manifest.consumed[$i] -is [string] -and [StringComparer]::Ordinal.Equals($manifest.consumed[$i],$consumed[$i])) 'Manifest consumed order'}
 $n49dPhase04Action='11' # N49D_WRAPPER_INSTRUMENTATION
 $correctConsumed=$manifest.consumed
 try{
 $n49dPhase04Action='12' # N49D_WRAPPER_INSTRUMENTATION
 $manifest.consumed=$consumed
 $n49dPhase04Action='13' # N49D_WRAPPER_INSTRUMENTATION
 Need ($manifest.consumed.GetType() -eq [string[]] -and $manifest.consumed.Count -eq 51) 'Typed consumed negative shape'
 $n49dPhase04Action='14' # N49D_WRAPPER_INSTRUMENTATION
 Reject {Assert-QbrainPhaseReport $manifest objects}
 $n49dPhase04Action='15' # N49D_WRAPPER_INSTRUMENTATION
 Reject {$null=ConvertTo-QbrainCanonical $manifest}
 }finally{
 $n49dPhase04PriorAction=$n49dPhase04Action # N49D_WRAPPER_INSTRUMENTATION
 $n49dPhase04Action='16' # N49D_WRAPPER_INSTRUMENTATION
 $manifest.consumed=$correctConsumed
 $n49dPhase04Action=$n49dPhase04PriorAction # N49D_WRAPPER_INSTRUMENTATION
 }
 $n49dPhase04Action='17' # N49D_WRAPPER_INSTRUMENTATION
 $mp=Join-Path $reports 'direct-production-objects.json'
 $n49dPhase04Action='18' # N49D_WRAPPER_INSTRUMENTATION
 $bp=Join-Path $reports 'direct-tests-build-context.json'
 $n49dPhase04Action='19' # N49D_WRAPPER_INSTRUMENTATION
 $rp=Join-Path $reports 'direct-tests-run-context.json'
 $n49dPhase04Action='20' # N49D_WRAPPER_INSTRUMENTATION
 Write-QbrainPhaseReport $mp $manifest objects
 $n49dPhase04Action='21' # N49D_WRAPPER_INSTRUMENTATION
 $bo=@{BuildOnly=$true;SkipProductionBuild=$true;ProductionManifest=$mp;PhaseContext=$bp}
 try{Write-N49DWork $n49dWork '01' 'E'}catch{} # N49D_WRAPPER_INSTRUMENTATION
 try{Write-N49DWork $n49dWork '02' 'B'}catch{} # N49D_WRAPPER_INSTRUMENTATION
 $n49dPhase04Action='22' # N49D_WRAPPER_INSTRUMENTATION
 Need ((Dispatch $bo) -eq 0) 'BuildOnly'
 try{Write-N49DWork $n49dWork '02' 'E'}catch{} # N49D_WRAPPER_INSTRUMENTATION
 try{Write-N49DWork $n49dWork '03' 'B'}catch{} # N49D_WRAPPER_INSTRUMENTATION
try{ # N49D_WRAPPER_INSTRUMENTATION
 $n49dCatchOuterConsole=[Console]::Error # N49D_WRAPPER_INSTRUMENTATION
& { # N49D_WRAPPER_INSTRUMENTATION
 class N49DBuildCatchControlWriter : System.IO.StringWriter { # N49D_WRAPPER_INSTRUMENTATION
  [string]$Fault # N49D_WRAPPER_INSTRUMENTATION
  [int]$Writes=0 # N49D_WRAPPER_INSTRUMENTATION
  [int]$Flushes=0 # N49D_WRAPPER_INSTRUMENTATION
  N49DBuildCatchControlWriter([string]$fault){if($fault -ceq 'constructor'){throw [IO.IOException]::new('private-constructor')};$this.Fault=$fault} # N49D_WRAPPER_INSTRUMENTATION
  [void] WriteLine([string]$value){$this.Writes++;if($this.Fault -ceq 'writer'){throw [IO.IOException]::new('private-writer')};[void]$this.GetStringBuilder().Append($value);[void]$this.GetStringBuilder().Append([Environment]::NewLine)} # N49D_WRAPPER_INSTRUMENTATION
  [void] Flush(){$this.Flushes++;if($this.Fault -ceq 'flush'){throw [IO.IOException]::new('private-flush')}} # N49D_WRAPPER_INSTRUMENTATION
 } # N49D_WRAPPER_INSTRUMENTATION
 $n49dCatchSavedConsole=[Console]::Error;$n49dCatchCurrentWriter=$null # N49D_WRAPPER_INSTRUMENTATION
 $n49dCatchSavedCounters=@($script:resolved,$script:executed,$script:rebuilt,$script:batch) # N49D_WRAPPER_INSTRUMENTATION
 $n49dCatchHadReport=[IO.File]::Exists($bp);$n49dCatchSavedReport=if($n49dCatchHadReport){[IO.File]::ReadAllBytes($bp)}else{$null} # N49D_WRAPPER_INSTRUMENTATION
 $n49dCatchSavedBinary=[IO.File]::ReadAllBytes($binary) # N49D_WRAPPER_INSTRUMENTATION
 $n49dCatchBaseResolver=$resolver;$n49dCatchBaseAdapter=$adapter;$n49dCatchBaseEmitter=(Get-Command Write-N49DBuildCatch -CommandType Function -ErrorAction Stop).ScriptBlock # N49D_WRAPPER_INSTRUMENTATION
 $n49dCatchBaseFactory=$n49dBuildCatchFactory;$n49dCatchBaseStateMaker=$n49dBuildCatchMakeState;$n49dCatchBaseActivation=$n49dBuildCatchActivate # N49D_WRAPPER_INSTRUMENTATION
 $n49dCatchSetupFailures=@('initialization','constructor','activation-before','activation-after','progress-S-setup') # N49D_WRAPPER_INSTRUMENTATION
 function Reset-N49DBuildCatchFiles([bool]$RestoreLiveReport=$false){ # N49D_WRAPPER_INSTRUMENTATION
  if($RestoreLiveReport -and $n49dCatchHadReport){[IO.File]::WriteAllBytes($bp,$n49dCatchSavedReport)}else{[IO.File]::Delete($bp)} # N49D_WRAPPER_INSTRUMENTATION
  [IO.File]::WriteAllBytes($binary,$n49dCatchSavedBinary) # N49D_WRAPPER_INSTRUMENTATION
 } # N49D_WRAPPER_INSTRUMENTATION
 function Invoke-N49DBuildCatchControl([string]$Mode,[string]$Case,[string]$Fault='none'){ # N49D_WRAPPER_INSTRUMENTATION
  Reset-N49DBuildCatchFiles # N49D_WRAPPER_INSTRUMENTATION
  $script:resolved=0;$script:executed=0;$script:rebuilt=0;$script:batch='' # N49D_WRAPPER_INSTRUMENTATION
  $n49dCtl=[pscustomobject]@{Trace=[Collections.Generic.List[string]]::new();SourceRecord=$null;SourceException=$null;ObservedRecord=$null;ObservedException=$null;AfterRecord=$null;AfterException=$null;RecoveredRecord=$null;RecoveredException=$null;ObserverCalls=0;RunDirectory=$null} # N49D_WRAPPER_INSTRUMENTATION
  $n49dBuildCatchProgress=[pscustomobject]@{S='N';G='N';E='N'} # N49D_WRAPPER_INSTRUMENTATION
  $n49dProgressWrites=[Collections.Generic.List[string]]::new() # N49D_WRAPPER_INSTRUMENTATION
  if($Fault -cmatch '^progress-(S|G|E)(?:-|$)'){ # N49D_WRAPPER_INSTRUMENTATION
   $n49dProgressField=$Matches[1] # N49D_WRAPPER_INSTRUMENTATION
   $n49dBuildCatchProgress|Add-Member -Force -MemberType ScriptProperty -Name $n49dProgressField -Value {'N'} -SecondValue {param($value) $n49dProgressWrites.Add($n49dProgressField+':'+$value);throw 'private-progress-write'} # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  if($Fault -ceq 'progress-unavailable'){$n49dBuildCatchProgress=$null} # N49D_WRAPPER_INSTRUMENTATION
  $n49dPhase04Action='22';$n49dBuildCatchFactory=$n49dCatchBaseFactory;$n49dBuildCatchMakeState=$n49dCatchBaseStateMaker;$n49dBuildCatchActivate=$n49dCatchBaseActivation # N49D_WRAPPER_INSTRUMENTATION
  $null=. ([scriptblock]::Create($n49dBuildCatchOriginalText)) # N49D_WRAPPER_INSTRUMENTATION
  $n49dBuildCatchCommand=$null;$n49dBuildCatchBlock=$null;$n49dBuildCatchState=$null;$n49dBuildCatchReady=$false # N49D_WRAPPER_INSTRUMENTATION
  if($Mode -ceq 'instrumented'){ # N49D_WRAPPER_INSTRUMENTATION
   switch -Exact ($Fault){ # N49D_WRAPPER_INSTRUMENTATION
    'initialization'{$n49dBuildCatchMakeState={throw 'private-initialization'}} # N49D_WRAPPER_INSTRUMENTATION
    'progress-S-setup'{$n49dBuildCatchMakeState={throw 'private-initialization'}} # N49D_WRAPPER_INSTRUMENTATION
    'constructor'{$n49dBuildCatchFactory={param($text) throw 'private-constructor'}} # N49D_WRAPPER_INSTRUMENTATION
    'activation-before'{$n49dBuildCatchActivate={param($definition) throw 'private-activation'}} # N49D_WRAPPER_INSTRUMENTATION
    'activation-after'{$n49dBuildCatchActivate={param($definition) . $definition;throw 'private-activation'}} # N49D_WRAPPER_INSTRUMENTATION
   } # N49D_WRAPPER_INSTRUMENTATION
   $null=. $n49dBuildCatchSetup # N49D_WRAPPER_INSTRUMENTATION
   Need ($n49dBuildCatchPrepared -and $n49dBuildCatchPreparation.Count -eq 1 -and [object]::ReferenceEquals($n49dBuildCatchInstrumentedText,$n49dCatchPreparedText)) 'Catch warm preparation' # N49D_WRAPPER_INSTRUMENTATION
   if($Fault -cin $n49dCatchSetupFailures){ # N49D_WRAPPER_INSTRUMENTATION
    Need (-not $n49dBuildCatchReady -and $null -eq $n49dBuildCatchCommand -and (Test-N49DFunctionAst (Get-Command Invoke-QbrainBuildPhase -CommandType Function).ScriptBlock.Ast $n49dBuildCatchOriginalAst 'Invoke-QbrainBuildPhase')) 'Catch setup fallback changed function' # N49D_WRAPPER_INSTRUMENTATION
   }else{ # N49D_WRAPPER_INSTRUMENTATION
    Need ($n49dBuildCatchReady -and [object]::ReferenceEquals((Get-Command Invoke-QbrainBuildPhase -CommandType Function),$n49dBuildCatchCommand) -and [object]::ReferenceEquals((Get-Command Invoke-QbrainBuildPhase -CommandType Function).ScriptBlock,$n49dBuildCatchBlock)) 'Catch command identity unavailable' # N49D_WRAPPER_INSTRUMENTATION
   } # N49D_WRAPPER_INSTRUMENTATION
   if($Fault -cin @('gate-action','progress-G-action')){$n49dPhase04Action='21'} # N49D_WRAPPER_INSTRUMENTATION
   if($Fault -cin @('gate-command','progress-G-command')){$n49dBuildCatchCommand=$null} # N49D_WRAPPER_INSTRUMENTATION
   if($Fault -cin @('gate-block','progress-G-block')){$n49dBuildCatchBlock=$null} # N49D_WRAPPER_INSTRUMENTATION
   if($Fault -ceq 'gate-redefinition'){$null=. ([scriptblock]::Create($n49dBuildCatchInstrumentedText));Need (-not [object]::ReferenceEquals((Get-Command Invoke-QbrainBuildPhase -CommandType Function).ScriptBlock,$n49dBuildCatchBlock)) 'Catch separate definition identity'} # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  foreach($n49dOtherFunction in $functions){if($n49dOtherFunction.Name -cne 'Invoke-QbrainBuildPhase'){Need ((Test-N49DFunctionAst (Get-Command -Name $n49dOtherFunction.Name -CommandType Function -ErrorAction Stop).ScriptBlock.Ast $n49dOtherFunction $n49dOtherFunction.Name)) 'Catch other extracted function changed'}} # N49D_WRAPPER_INSTRUMENTATION
  function Write-N49DBuildCatch($Record,$Reason,$State){ # N49D_WRAPPER_INSTRUMENTATION
   $n49dCtl.ObserverCalls++;$n49dCtl.ObservedRecord=$Record;$n49dCtl.ObservedException=$Record.Exception # N49D_WRAPPER_INSTRUMENTATION
   try{ # N49D_WRAPPER_INSTRUMENTATION
    if($Fault -ceq 'invocation'){throw 'private-invocation'} # N49D_WRAPPER_INSTRUMENTATION
    if($Fault -ceq 'observer-constructor'){$null=[N49DBuildCatchControlWriter]::new('constructor')} # N49D_WRAPPER_INSTRUMENTATION
    if($Fault -ceq 'stream-output'){'private-success-stream'} # N49D_WRAPPER_INSTRUMENTATION
    $n49dObservedInput=$Record;$n49dObservedState=$State # N49D_WRAPPER_INSTRUMENTATION
    if($Fault -ceq 'getter'){$n49dObservedInput=[pscustomobject]@{};$n49dObservedInput|Add-Member -MemberType ScriptProperty -Name Exception -Value {throw 'private-getter'}} # N49D_WRAPPER_INSTRUMENTATION
    if($Fault -ceq 'latch-read'){$n49dObservedState=[pscustomobject]@{};$n49dObservedState|Add-Member -MemberType ScriptProperty -Name Latched -Value {throw 'private-latch-read'}} # N49D_WRAPPER_INSTRUMENTATION
    if($Fault -ceq 'latch-write'){$n49dObservedState=[pscustomobject]@{};$n49dObservedState|Add-Member -MemberType ScriptProperty -Name Latched -Value {$false} -SecondValue {throw 'private-latch-write'}} # N49D_WRAPPER_INSTRUMENTATION
    & $n49dCatchBaseEmitter $n49dObservedInput $Reason $n49dObservedState # N49D_WRAPPER_INSTRUMENTATION
   }finally{$n49dCtl.AfterRecord=$Record;$n49dCtl.AfterException=$Record.Exception} # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  function Write-Error { # N49D_WRAPPER_INSTRUMENTATION
   [CmdletBinding()]param([Parameter(Position=0)][string]$Message) # N49D_WRAPPER_INSTRUMENTATION
   if($Message -ceq 'Build phase failed.'){$n49dCtl.RecoveredRecord=$_;$n49dCtl.RecoveredException=$_.Exception} # N49D_WRAPPER_INSTRUMENTATION
   $n49dCtl.Trace.Add('error:'+$Message) # N49D_WRAPPER_INSTRUMENTATION
   Microsoft.PowerShell.Utility\Write-Error -Message $Message -ErrorAction Continue # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  $resolver={ # N49D_WRAPPER_INSTRUMENTATION
   $n49dCtl.Trace.Add('resolve') # N49D_WRAPPER_INSTRUMENTATION
   if($Case -ceq 'resolver-escape'){try{throw [IO.IOException]::new('private-resolver')}catch{$n49dCtl.SourceRecord=$_;$n49dCtl.SourceException=$_.Exception;throw}} # N49D_WRAPPER_INSTRUMENTATION
   & $n49dCatchBaseResolver # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  $n49dCatchExecutor={param($batch,$result) # N49D_WRAPPER_INSTRUMENTATION
   $n49dCtl.Trace.Add('native') # N49D_WRAPPER_INSTRUMENTATION
   $n49dRunMatch=[regex]::Match($batch,'(?m)^cd /d "([^"]+)"\r?$') # N49D_WRAPPER_INSTRUMENTATION
   Need ($n49dRunMatch.Success) 'Catch control run directory missing' # N49D_WRAPPER_INSTRUMENTATION
   $n49dCtl.RunDirectory=$n49dRunMatch.Groups[1].Value # N49D_WRAPPER_INSTRUMENTATION
   Need ([IO.Directory]::Exists($n49dCtl.RunDirectory)) 'Catch control run directory absent during adapter' # N49D_WRAPPER_INSTRUMENTATION
   & $n49dCatchBaseAdapter $batch $result # N49D_WRAPPER_INSTRUMENTATION
   if($Case -cin @('native-throw','native-nonzero')){ # N49D_WRAPPER_INSTRUMENTATION
    if($Case -ceq 'native-nonzero'){$result.ExitCode=73} # N49D_WRAPPER_INSTRUMENTATION
    try{throw [IO.IOException]::new('private-native')}catch{$n49dCtl.SourceRecord=$_;$n49dCtl.SourceException=$_.Exception;throw} # N49D_WRAPPER_INSTRUMENTATION
   } # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  $n49dCaseOptions=$bo.Clone() # N49D_WRAPPER_INSTRUMENTATION
  if($Case -ceq 'early'){$n49dCaseOptions.PhaseContext='relative-tests-build-context.json'} # N49D_WRAPPER_INSTRUMENTATION
  if($Case -ceq 'arguments-escape'){$n49dCaseOptions.RunOnly=$true} # N49D_WRAPPER_INSTRUMENTATION
  $n49dPriorRunDirs=@([IO.Directory]::GetDirectories($root,'qbrain-tests-cl-*')) # N49D_WRAPPER_INSTRUMENTATION
  Need ($n49dPriorRunDirs.Count -eq 0) 'Catch control initial run directory' # N49D_WRAPPER_INSTRUMENTATION
  $n49dWriterFault=if($Fault -cin @('writer','flush')){$Fault}else{'none'} # N49D_WRAPPER_INSTRUMENTATION
  $n49dCatchCurrentWriter=[N49DBuildCatchControlWriter]::new($n49dWriterFault) # N49D_WRAPPER_INSTRUMENTATION
  $n49dCaseWriter=$n49dCatchCurrentWriter;$n49dCasePriorConsole=[Console]::Error;$n49dOutput=@();$n49dEscaped=$null # N49D_WRAPPER_INSTRUMENTATION
  try{ # N49D_WRAPPER_INSTRUMENTATION
   [Console]::SetError($n49dCaseWriter) # N49D_WRAPPER_INSTRUMENTATION
   try{$n49dOutput=@(Dispatch $n49dCaseOptions $n49dCatchExecutor)}catch{$n49dEscaped=$_} # N49D_WRAPPER_INSTRUMENTATION
  }finally{[Console]::SetError($n49dCasePriorConsole)} # N49D_WRAPPER_INSTRUMENTATION
  Need ([object]::ReferenceEquals([Console]::Error,$n49dCasePriorConsole)) 'Catch case console restoration' # N49D_WRAPPER_INSTRUMENTATION
  $n49dAfterRunDirs=@([IO.Directory]::GetDirectories($root,'qbrain-tests-cl-*')) # N49D_WRAPPER_INSTRUMENTATION
  Need ($n49dAfterRunDirs.Count -eq 0 -and ($null -eq $n49dCtl.RunDirectory -or -not [IO.Directory]::Exists($n49dCtl.RunDirectory))) 'Catch control run directory leaked' # N49D_WRAPPER_INSTRUMENTATION
  $n49dExpectedCatch=$Mode -ceq 'instrumented' -and $Case -cin @('native-throw','native-nonzero','early') -and $Fault -cnotin ($n49dCatchSetupFailures+@('gate-action','gate-redefinition','gate-command','gate-block','progress-G-action','progress-G-command','progress-G-block')) # N49D_WRAPPER_INSTRUMENTATION
  Need ($n49dCtl.ObserverCalls -eq [int]$n49dExpectedCatch) 'Catch actual invocation gate changed' # N49D_WRAPPER_INSTRUMENTATION
  if($n49dExpectedCatch){ # N49D_WRAPPER_INSTRUMENTATION
   Need ([object]::ReferenceEquals($n49dCtl.ObservedRecord,$n49dCtl.AfterRecord) -and [object]::ReferenceEquals($n49dCtl.ObservedRecord,$n49dCtl.RecoveredRecord) -and [object]::ReferenceEquals($n49dCtl.ObservedException,$n49dCtl.AfterException) -and [object]::ReferenceEquals($n49dCtl.ObservedException,$n49dCtl.RecoveredException)) 'Catch original handled identity changed' # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  if($Case -cin @('native-throw','native-nonzero')){Need ([object]::ReferenceEquals($n49dCtl.SourceException,$n49dCtl.RecoveredException)) 'Catch native exception identity changed'} # N49D_WRAPPER_INSTRUMENTATION
  if($Case -ceq 'resolver-escape'){Need ([object]::ReferenceEquals($n49dCtl.SourceException,$n49dEscaped.Exception)) 'Catch escaping resolver identity changed'} # N49D_WRAPPER_INSTRUMENTATION
  $n49dExpectedToken='' # N49D_WRAPPER_INSTRUMENTATION
  if($n49dExpectedCatch -and $Fault -cin @('none','flush','stream-output','progress-S','progress-G','progress-E','progress-unavailable')){$n49dExpectedToken=if($Case -ceq 'early'){"`nN49D_BUILD_CATCH_V1:input-invalid:RT"+[Environment]::NewLine}else{"`nN49D_BUILD_CATCH_V1:compile-failed:IO"+[Environment]::NewLine}} # N49D_WRAPPER_INSTRUMENTATION
  Need ($n49dCaseWriter.ToString() -ceq $n49dExpectedToken) 'Catch fixed token or optional failure changed' # N49D_WRAPPER_INSTRUMENTATION
  if($n49dExpectedToken.Length){Need ($n49dCaseWriter.Writes -eq 1 -and $n49dCaseWriter.Flushes -eq 1) 'Catch write flush count'} # N49D_WRAPPER_INSTRUMENTATION
  if($Fault -ceq 'writer'){Need ($n49dCaseWriter.Writes -eq 1 -and $n49dCaseWriter.Flushes -eq 0) 'Catch writer isolation'} # N49D_WRAPPER_INSTRUMENTATION
  if($Mode -ceq 'instrumented'){ # N49D_WRAPPER_INSTRUMENTATION
   $n49dExpectedGate=if($Fault -cin $n49dCatchSetupFailures){'N'}elseif($Case -cin @('success','arguments-escape','resolver-escape')){'N'}elseif($Fault -cin @('gate-action','progress-G-action')){'X'}elseif($Fault -cin @('gate-command','gate-redefinition','progress-G-command')){'R'}elseif($Fault -cin @('gate-block','progress-G-block')){'S'}else{'I'} # N49D_WRAPPER_INSTRUMENTATION
   $n49dExpectedEmitter=if(-not $n49dExpectedCatch -or $Fault -cin @('invocation','observer-constructor')){'N'}elseif($Fault -cin @('latch-read','latch-write')){'C'}elseif($Fault -ceq 'getter'){'L'}elseif($Fault -ceq 'writer'){'M'}elseif($Fault -ceq 'flush'){'W'}else{'F'} # N49D_WRAPPER_INSTRUMENTATION
   if($Fault -cne 'progress-unavailable'){ # N49D_WRAPPER_INSTRUMENTATION
    if($Fault -cnotmatch '^progress-S'){Need ($n49dBuildCatchProgress.S -ceq $(if($Fault -cin $n49dCatchSetupFailures){'F'}else{'R'})) 'Progress setup observation'} # N49D_WRAPPER_INSTRUMENTATION
    if($Fault -ceq 'gate-redefinition'){Need ($n49dBuildCatchProgress.G -cin @('R','S')) 'Progress replacement gate rejection'}elseif($Fault -cnotmatch '^progress-G'){Need ($n49dBuildCatchProgress.G -ceq $n49dExpectedGate) 'Progress original reference gate'} # N49D_WRAPPER_INSTRUMENTATION
    if($Fault -cnotmatch '^progress-E'){Need ($n49dBuildCatchProgress.E -ceq $n49dExpectedEmitter) 'Progress emitter observation'} # N49D_WRAPPER_INSTRUMENTATION
   } # N49D_WRAPPER_INSTRUMENTATION
   $n49dExpectedWrites=switch -Exact ($Fault){'progress-S'{'S:A|S:R'}'progress-S-setup'{'S:A|S:F'}'progress-G'{'G:C|G:A|G:F|G:I'}'progress-G-action'{'G:C|G:X'}'progress-G-command'{'G:C|G:A|G:R'}'progress-G-block'{'G:C|G:A|G:F|G:S'}'progress-E'{'E:C|E:L|E:M|E:W|E:F'}default{$null}} # N49D_WRAPPER_INSTRUMENTATION
   if($null -ne $n49dExpectedWrites){Need (($n49dProgressWrites -join '|') -ceq $n49dExpectedWrites) 'Progress write failure sites or order'} # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  if($n49dExpectedCatch -and $Fault -cin @('none','flush','stream-output','progress-S','progress-G','progress-E','progress-unavailable')){ # N49D_WRAPPER_INSTRUMENTATION
   try{[Console]::SetError($n49dCaseWriter);$null=& $n49dCatchBaseEmitter $n49dCtl.ObservedRecord 'storage' $n49dBuildCatchState}finally{[Console]::SetError($n49dCasePriorConsole)} # N49D_WRAPPER_INSTRUMENTATION
   Need ([object]::ReferenceEquals([Console]::Error,$n49dCasePriorConsole)) 'Catch latch console restoration' # N49D_WRAPPER_INSTRUMENTATION
   Need ($n49dCaseWriter.ToString() -ceq $n49dExpectedToken -and $n49dCaseWriter.Writes -eq 1 -and $n49dCaseWriter.Flushes -eq 1) 'Catch latch allowed repeated output' # N49D_WRAPPER_INSTRUMENTATION
   if($Fault -cnotin @('progress-E','progress-unavailable')){Need ($n49dBuildCatchProgress.E -ceq 'A') 'Progress repeated entry not identified'} # N49D_WRAPPER_INSTRUMENTATION
   if($Fault -ceq 'progress-E'){Need (($n49dProgressWrites -join '|') -ceq 'E:C|E:L|E:M|E:W|E:F|E:C|E:A') 'Progress latch-hit write failure sites'} # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  $n49dReportBytes='';$n49dReportState='absent';$n49dReportFailure=$null # N49D_WRAPPER_INSTRUMENTATION
  if([IO.File]::Exists($bp)){$n49dReportBytes=[Convert]::ToBase64String([IO.File]::ReadAllBytes($bp));$n49dReportValue=Read-QbrainPhaseReport $bp build;$n49dReportState=$n49dReportValue.state;$n49dReportFailure=$n49dReportValue.failure} # N49D_WRAPPER_INSTRUMENTATION
  $n49dNormalizedBatch=$script:batch;if($null -ne $n49dCtl.RunDirectory){$n49dNormalizedBatch=$n49dNormalizedBatch.Replace($n49dCtl.RunDirectory,'<owned-run-directory>')} # N49D_WRAPPER_INSTRUMENTATION
  if($Case -cin @('arguments-escape','resolver-escape')){Need ($n49dOutput.Count -eq 0 -and $null -ne $n49dEscaped -and $script:executed -eq 0 -and $script:rebuilt -eq 0) 'Catch escape was normalized'}else{ # N49D_WRAPPER_INSTRUMENTATION
   $n49dExpectedCode=if($Case -ceq 'success'){0}elseif($Case -ceq 'native-nonzero'){73}else{1} # N49D_WRAPPER_INSTRUMENTATION
   Need ($n49dOutput.Count -eq 1 -and $n49dOutput[0] -is [int] -and $n49dOutput[0] -eq $n49dExpectedCode -and $null -eq $n49dEscaped -and $script:rebuilt -eq 0) 'Catch scalar status changed' # N49D_WRAPPER_INSTRUMENTATION
   if($Case -ceq 'early'){Need ($script:executed -eq 0 -and $n49dReportState -ceq 'absent') 'Catch early failure reached native adapter'} # N49D_WRAPPER_INSTRUMENTATION
   if($Case -ceq 'success'){Need ($script:executed -eq 1 -and $n49dReportState -ceq 'prepared' -and $null -eq $n49dReportFailure) 'Catch success report changed'} # N49D_WRAPPER_INSTRUMENTATION
   if($Case -cin @('native-throw','native-nonzero')){Need ($script:executed -eq 1 -and $n49dReportState -ceq 'failed' -and $n49dReportFailure -ceq 'compile-failed') 'Catch failure report changed'} # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  $n49dSignature=[pscustomobject]@{Count=$n49dOutput.Count;Code=if($n49dOutput.Count){$n49dOutput[0]}else{$null};Trace=($n49dCtl.Trace -join '|');Resolved=$script:resolved;Executed=$script:executed;Rebuilt=$script:rebuilt;Batch=$n49dNormalizedBatch;ReportBytes=$n49dReportBytes;ReportState=$n49dReportState;ReportFailure=$n49dReportFailure;BinaryBytes=[Convert]::ToBase64String([IO.File]::ReadAllBytes($binary));RunDirectories=$n49dAfterRunDirs.Count;EscapedType=if($null -ne $n49dEscaped){$n49dEscaped.Exception.GetType().FullName}else{$null};EscapedId=if($null -ne $n49dEscaped){$n49dEscaped.FullyQualifiedErrorId}else{$null}} # N49D_WRAPPER_INSTRUMENTATION
  $n49dCaseWriter.Dispose();$n49dCatchCurrentWriter=$null # N49D_WRAPPER_INSTRUMENTATION
  return $n49dSignature # N49D_WRAPPER_INSTRUMENTATION
 } # N49D_WRAPPER_INSTRUMENTATION
 function Assert-N49DBuildCatchPair($Before,$After){foreach($n49dField in @('Count','Code','Trace','Resolved','Executed','Rebuilt','Batch','ReportBytes','ReportState','ReportFailure','BinaryBytes','RunDirectories','EscapedType','EscapedId')){Need ($Before.$n49dField -ceq $After.$n49dField) 'Catch baseline equivalence changed'}} # N49D_WRAPPER_INSTRUMENTATION
 try{ # N49D_WRAPPER_INSTRUMENTATION
  Need $n49dBuildCatchReady 'Catch optional installation unavailable for controls' # N49D_WRAPPER_INSTRUMENTATION
  $n49dCatchPreparedText=$n49dBuildCatchInstrumentedText # N49D_WRAPPER_INSTRUMENTATION
  Need ($n49dBuildCatchPrepared -and $n49dBuildCatchPreparation.Count -eq 1) 'Catch cold preparation' # N49D_WRAPPER_INSTRUMENTATION
  $n49dPreparedDigest=[Security.Cryptography.SHA256]::Create() # N49D_WRAPPER_INSTRUMENTATION
  try{ # N49D_WRAPPER_INSTRUMENTATION
   $n49dPreparedOracle={param([string]$Original,[string]$Prepared) [Convert]::ToBase64String($n49dPreparedDigest.ComputeHash((Bytes ($Original+[char]0+$Prepared)))) -cin @('jpj94ob3UiKitni+6o2d/hIqOUcr5S5qHtaE5izwCX4=','w0pJ5FJMkkZ6vB+YQMmmwrF5VDfmvpJUrZ0ISq8IZMo=')} # N49D_WRAPPER_INSTRUMENTATION
   Need (& $n49dPreparedOracle $n49dBuildCatchOriginalText $n49dCatchPreparedText) 'Catch prepared bytes' # N49D_WRAPPER_INSTRUMENTATION
   & { # N49D_WRAPPER_INSTRUMENTATION
    $n49dPreparationSites=@($n49dBuildCatchSetup.Ast.FindAll({param($node) $node -is [Management.Automation.Language.IfStatementAst] -and $node.Extent.Text.StartsWith('if(-not $n49dBuildCatchPrepared){')},$true)) # N49D_WRAPPER_INSTRUMENTATION
    Need ($n49dPreparationSites.Count -eq 1) 'Catch preparation seam' # N49D_WRAPPER_INSTRUMENTATION
    $n49dPreparationControl=[scriptblock]::Create($n49dPreparationSites[0].Extent.Text) # N49D_WRAPPER_INSTRUMENTATION
    $n49dPreparationLF=$n49dBuildCatchOriginalText.Replace("`r`n","`n") # N49D_WRAPPER_INSTRUMENTATION
    foreach($n49dPreparationOriginal in @($n49dPreparationLF,$n49dPreparationLF.Replace("`n","`r`n"))){ # N49D_WRAPPER_INSTRUMENTATION
     $n49dBuildCatchOriginalText=$n49dPreparationOriginal;$n49dBuildCatchOriginalAst=([scriptblock]::Create($n49dPreparationOriginal)).Ast.EndBlock.Statements[0] # N49D_WRAPPER_INSTRUMENTATION
     $n49dBuildCatchPrepared=$false;$n49dBuildCatchPreparation=[pscustomobject]@{Count=0} # N49D_WRAPPER_INSTRUMENTATION
     $null=. $n49dPreparationControl # N49D_WRAPPER_INSTRUMENTATION
     Need ($n49dBuildCatchPrepared -and $n49dBuildCatchPreparation.Count -eq 1 -and (& $n49dPreparedOracle $n49dPreparationOriginal $n49dBuildCatchInstrumentedText)) 'Catch prepared form' # N49D_WRAPPER_INSTRUMENTATION
     $n49dPreparationSaved=$n49dBuildCatchInstrumentedText;$null=. $n49dPreparationControl # N49D_WRAPPER_INSTRUMENTATION
     Need ($n49dBuildCatchPreparation.Count -eq 1 -and [object]::ReferenceEquals($n49dPreparationSaved,$n49dBuildCatchInstrumentedText)) 'Catch prepared form warm' # N49D_WRAPPER_INSTRUMENTATION
     Need (-not (& $n49dPreparedOracle ($n49dPreparationOriginal+' ') $n49dPreparationSaved) -and -not (& $n49dPreparedOracle $n49dPreparationOriginal ($n49dPreparationSaved+' '))) 'Catch prepared form mutation' # N49D_WRAPPER_INSTRUMENTATION
    } # N49D_WRAPPER_INSTRUMENTATION
   } # N49D_WRAPPER_INSTRUMENTATION
  }finally{$n49dPreparedDigest.Dispose()} # N49D_WRAPPER_INSTRUMENTATION
  & { # N49D_WRAPPER_INSTRUMENTATION
   $null=. ([scriptblock]::Create($n49dBuildCatchOriginalText)) # N49D_WRAPPER_INSTRUMENTATION
   $n49dBuildCatchPrepared=$false;$n49dBuildCatchPreparation=[pscustomobject]@{Count=0} # N49D_WRAPPER_INSTRUMENTATION
   $n49dBuildCatchOriginalText='';$n49dBuildCatchInstrumentedText=$null;$n49dPrepareProbe=[pscustomobject]@{Factory=0} # N49D_WRAPPER_INSTRUMENTATION
   $n49dBuildCatchProgress=[pscustomobject]@{S='N';G='N';E='N'} # N49D_WRAPPER_INSTRUMENTATION
   $n49dBuildCatchFactory={param($text) $n49dPrepareProbe.Factory++;throw 'private-preparation-factory'} # N49D_WRAPPER_INSTRUMENTATION
   $null=. $n49dBuildCatchSetup # N49D_WRAPPER_INSTRUMENTATION
   Need (-not $n49dBuildCatchPrepared -and -not $n49dBuildCatchReady -and $null -eq $n49dBuildCatchInstrumentedText -and $n49dBuildCatchPreparation.Count -eq 1 -and $n49dPrepareProbe.Factory -eq 0 -and $n49dBuildCatchProgress.S -ceq 'F' -and (Test-N49DFunctionAst (Get-Command Invoke-QbrainBuildPhase -CommandType Function).ScriptBlock.Ast $n49dBuildCatchOriginalAst 'Invoke-QbrainBuildPhase')) 'Catch failed preparation' # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  Need ($n49dBuildCatchPrepared -and $n49dBuildCatchPreparation.Count -eq 1 -and [object]::ReferenceEquals($n49dBuildCatchInstrumentedText,$n49dCatchPreparedText) -and [object]::ReferenceEquals((Get-Command Invoke-QbrainBuildPhase -CommandType Function),$n49dBuildCatchCommand)) 'Catch preparation scope' # N49D_WRAPPER_INSTRUMENTATION
  Need $n49dCatchHadReport 'Catch controls live report absent' # N49D_WRAPPER_INSTRUMENTATION
  & { # N49D_WRAPPER_INSTRUMENTATION
   $n49dShapeSites=@($n49dBuildCatchSetup.Ast.FindAll({param($node) $node -is [Management.Automation.Language.IfStatementAst] -and $node.Extent.Text.StartsWith('if(-not (Test-N49DFunctionAst ')},$true)) # N49D_WRAPPER_INSTRUMENTATION
   Need ($n49dShapeSites.Count -eq 2) 'Shape guard inventory' # N49D_WRAPPER_INSTRUMENTATION
   $n49dShapeExpected=@($n49dBuildCatchOriginalAst,$n49dBuildCatchParsed[0]) # N49D_WRAPPER_INSTRUMENTATION
   for($n49dShapeSite=0;$n49dShapeSite -lt 2;$n49dShapeSite++){ # N49D_WRAPPER_INSTRUMENTATION
    $n49dShapeGuard=[scriptblock]::Create($n49dShapeSites[$n49dShapeSite].Extent.Text) # N49D_WRAPPER_INSTRUMENTATION
    $n49dShapeCanonical=$n49dShapeExpected[$n49dShapeSite];$n49dShapeText=$n49dShapeCanonical.Extent.Text # N49D_WRAPPER_INSTRUMENTATION
    $n49dBuildCatchOriginalAst=$n49dShapeCanonical;$n49dBuildCatchParsed=@($n49dShapeCanonical) # N49D_WRAPPER_INSTRUMENTATION
    $n49dShapeTokens=$null;$n49dShapeErrors=$null;$n49dShapeTree=[Management.Automation.Language.Parser]::ParseInput($n49dShapeText,[ref]$n49dShapeTokens,[ref]$n49dShapeErrors) # N49D_WRAPPER_INSTRUMENTATION
    Need ($n49dShapeTokens.Count -gt 0 -and $n49dShapeErrors.Count -eq 0 -and $n49dShapeTree -is [Management.Automation.Language.ScriptBlockAst]) 'Shape fresh parse failed' # N49D_WRAPPER_INSTRUMENTATION
    $n49dShapeDefinitions=@($n49dShapeTree.EndBlock.Statements) # N49D_WRAPPER_INSTRUMENTATION
    Need ($n49dShapeDefinitions.Count -eq 1 -and $n49dShapeDefinitions[0] -is [Management.Automation.Language.FunctionDefinitionAst] -and $n49dShapeDefinitions[0].Name -ceq 'Invoke-QbrainBuildPhase' -and $n49dShapeDefinitions[0].Extent.Text -ceq $n49dShapeText) 'Shape fresh definition mismatch' # N49D_WRAPPER_INSTRUMENTATION
    $n49dShapeCopy=$n49dShapeDefinitions[0] # N49D_WRAPPER_INSTRUMENTATION
    Need (-not [object]::ReferenceEquals($n49dShapeCopy,$n49dShapeCanonical) -and -not [object]::ReferenceEquals($n49dShapeCopy.Body,$n49dShapeCanonical.Body)) 'Shape independent parses required' # N49D_WRAPPER_INSTRUMENTATION
    $n49dShapeCases=[Collections.Generic.List[object]]::new() # N49D_WRAPPER_INSTRUMENTATION
    foreach($n49dShapeObserved in @($n49dShapeCopy,$n49dShapeCopy.Body)){$n49dShapeCases.Add(@($n49dShapeObserved,$true))} # N49D_WRAPPER_INSTRUMENTATION
    foreach($n49dShapeChanged in @( # N49D_WRAPPER_INSTRUMENTATION
     $n49dShapeText.Replace('function Invoke-QbrainBuildPhase {','function Invoke-RenamedBuildPhase {'), # N49D_WRAPPER_INSTRUMENTATION
     $n49dShapeText.Replace('function Invoke-QbrainBuildPhase {','function invoke-QbrainBuildPhase {'), # N49D_WRAPPER_INSTRUMENTATION
     $n49dShapeText.Replace('function Invoke-QbrainBuildPhase {','function Invoke-QbrainBuildPhase  {'), # N49D_WRAPPER_INSTRUMENTATION
     $n49dShapeText.Replace('param($Options,$Context,','param($DifferentOptions,$Context,'), # N49D_WRAPPER_INSTRUMENTATION
     $n49dShapeText.Replace("  `$report=`$null; `$reason='input-invalid'","  `$report=`$null; `$reason='storage'") # N49D_WRAPPER_INSTRUMENTATION
    )){ # N49D_WRAPPER_INSTRUMENTATION
     Need ($n49dShapeChanged -cne $n49dShapeText) 'Shape mutation absent' # N49D_WRAPPER_INSTRUMENTATION
     $n49dShapeBad=([scriptblock]::Create($n49dShapeChanged)).Ast.EndBlock.Statements[0] # N49D_WRAPPER_INSTRUMENTATION
     foreach($n49dShapeObserved in @($n49dShapeBad,$n49dShapeBad.Body)){$n49dShapeCases.Add(@($n49dShapeObserved,$false))} # N49D_WRAPPER_INSTRUMENTATION
    } # N49D_WRAPPER_INSTRUMENTATION
    $n49dShapeDetached=$n49dShapeCopy.Body.Copy() # N49D_WRAPPER_INSTRUMENTATION
    Need ($null -eq $n49dShapeDetached.Parent -and $n49dShapeDetached.Extent.Text -ceq $n49dShapeCanonical.Body.Extent.Text) 'Shape detached body fixture' # N49D_WRAPPER_INSTRUMENTATION
    foreach($n49dShapeObserved in @($n49dShapeDetached,$n49dShapeCopy.Body.EndBlock,$null,[pscustomobject]@{Extent=$n49dShapeCopy.Extent;Body=$n49dShapeCopy.Body;Name='Invoke-QbrainBuildPhase'})){$n49dShapeCases.Add(@($n49dShapeObserved,$false))} # N49D_WRAPPER_INSTRUMENTATION
    Need ($n49dShapeCases.Count -eq 16) 'Shape case inventory' # N49D_WRAPPER_INSTRUMENTATION
    foreach($n49dShapeCase in $n49dShapeCases){ # N49D_WRAPPER_INSTRUMENTATION
     $n49dShapeObserved=$n49dShapeCase[0];$n49dShapeWant=$n49dShapeCase[1] # N49D_WRAPPER_INSTRUMENTATION
     Need ((Test-N49DFunctionAst $n49dShapeObserved $n49dShapeCanonical 'Invoke-QbrainBuildPhase') -eq $n49dShapeWant) 'Shape helper decision' # N49D_WRAPPER_INSTRUMENTATION
     $n49dBuildCatchRollback=[pscustomobject]@{Ast=$n49dShapeObserved};$n49dBuildCatchAfter=[pscustomobject]@{ScriptBlock=$n49dBuildCatchRollback} # N49D_WRAPPER_INSTRUMENTATION
     $n49dShapeError=$null;$n49dShapeOutput=@();try{$n49dShapeOutput=@(& $n49dShapeGuard)}catch{$n49dShapeError=$_} # N49D_WRAPPER_INSTRUMENTATION
     Need ($n49dShapeOutput.Count -eq 0 -and (($null -eq $n49dShapeError) -eq $n49dShapeWant)) 'Shape actual guard decision' # N49D_WRAPPER_INSTRUMENTATION
     if(-not $n49dShapeWant){Need ($n49dShapeError.Exception.Message -ceq @('Catch baseline body','Catch installed body')[$n49dShapeSite]) 'Shape guard primary changed'} # N49D_WRAPPER_INSTRUMENTATION
    } # N49D_WRAPPER_INSTRUMENTATION
    foreach($n49dShapeBadExpected in @($null,$n49dShapeCopy.Body,([scriptblock]::Create($n49dShapeText.Replace('function Invoke-QbrainBuildPhase {','function Invoke-RenamedBuildPhase {'))).Ast.EndBlock.Statements[0])){ # N49D_WRAPPER_INSTRUMENTATION
     Need (-not (Test-N49DFunctionAst $n49dShapeCopy $n49dShapeBadExpected 'Invoke-QbrainBuildPhase') -and -not (Test-N49DFunctionAst $n49dShapeCopy.Body $n49dShapeBadExpected 'Invoke-QbrainBuildPhase')) 'Shape invalid expectation accepted' # N49D_WRAPPER_INSTRUMENTATION
    } # N49D_WRAPPER_INSTRUMENTATION
   } # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  try{Write-N49DWork $n49dWork '03' 'E'}catch{} # N49D_WRAPPER_INSTRUMENTATION
  $n49dPairs=@{} # N49D_WRAPPER_INSTRUMENTATION
  foreach($n49dCase in @('success','native-throw','native-nonzero','early','arguments-escape','resolver-escape')){ # N49D_WRAPPER_INSTRUMENTATION
   $n49dWorkPair=switch -Exact ($n49dCase){'success'{@('04','05')}'native-throw'{@('06','07')}'native-nonzero'{@('08','09')}'early'{@('10','11')}'arguments-escape'{@('12','13')}'resolver-escape'{@('14','15')}} # N49D_WRAPPER_INSTRUMENTATION
   try{Write-N49DWork $n49dWork $n49dWorkPair[0] 'B'}catch{} # N49D_WRAPPER_INSTRUMENTATION
   $n49dPairs[$n49dCase]=Invoke-N49DBuildCatchControl baseline $n49dCase # N49D_WRAPPER_INSTRUMENTATION
   try{Write-N49DWork $n49dWork $n49dWorkPair[0] 'E'}catch{} # N49D_WRAPPER_INSTRUMENTATION
   try{Write-N49DWork $n49dWork $n49dWorkPair[1] 'B'}catch{} # N49D_WRAPPER_INSTRUMENTATION
   $n49dInstrumented=Invoke-N49DBuildCatchControl instrumented $n49dCase # N49D_WRAPPER_INSTRUMENTATION
   Assert-N49DBuildCatchPair $n49dPairs[$n49dCase] $n49dInstrumented # N49D_WRAPPER_INSTRUMENTATION
   try{Write-N49DWork $n49dWork $n49dWorkPair[1] 'E'}catch{} # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  foreach($n49dFault in @('getter','writer','flush','latch-read','latch-write','observer-constructor','invocation','stream-output','initialization','constructor','activation-before','activation-after','gate-action','gate-redefinition','gate-command','gate-block','progress-S','progress-G','progress-E','progress-S-setup','progress-G-action','progress-G-command','progress-G-block','progress-unavailable')){ # N49D_WRAPPER_INSTRUMENTATION
   $n49dWorkId=switch -Exact ($n49dFault){'getter'{'16'}'writer'{'17'}'flush'{'18'}'latch-read'{'19'}'latch-write'{'20'}'observer-constructor'{'21'}'invocation'{'22'}'stream-output'{'23'}'initialization'{'24'}'constructor'{'25'}'activation-before'{'26'}'activation-after'{'27'}'gate-action'{'28'}'gate-redefinition'{'29'}'gate-command'{'30'}'gate-block'{'31'}'progress-S'{'32'}'progress-G'{'33'}'progress-E'{'34'}'progress-S-setup'{'35'}'progress-G-action'{'36'}'progress-G-command'{'37'}'progress-G-block'{'38'}'progress-unavailable'{'39'}} # N49D_WRAPPER_INSTRUMENTATION
   try{Write-N49DWork $n49dWork $n49dWorkId 'B'}catch{} # N49D_WRAPPER_INSTRUMENTATION
   $n49dInstrumented=Invoke-N49DBuildCatchControl instrumented native-throw $n49dFault # N49D_WRAPPER_INSTRUMENTATION
   Assert-N49DBuildCatchPair $n49dPairs['native-throw'] $n49dInstrumented # N49D_WRAPPER_INSTRUMENTATION
   try{Write-N49DWork $n49dWork $n49dWorkId 'E'}catch{} # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  try{Write-N49DWork $n49dWork '40' 'B'}catch{} # N49D_WRAPPER_INSTRUMENTATION
  & { # N49D_WRAPPER_INSTRUMENTATION
   function Write-N49DBuildCatch($Record,$Reason,$State){$n49dGateState.Emitted++;Need ([object]::ReferenceEquals($Record,$n49dGateState.Primary)) 'Progress gate changed record'} # N49D_WRAPPER_INSTRUMENTATION
   $n49dGateSource='function Invoke-N49DProgressGateControl($Probe){$MyInvocation=$Probe;try{throw [IO.IOException]::new(''private-gate-primary'')}catch{$n49dGateState.Primary=$_;'+$n49dBuildCatchInsertion+"`n"+';throw}finally{$n49dGateState.Finally++}}' # N49D_WRAPPER_INSTRUMENTATION
   $null=. ([scriptblock]::Create($n49dGateSource)) # N49D_WRAPPER_INSTRUMENTATION
   foreach($n49dGateFault in @('action','function-false','block-false','command-throw','block-throw','match')){ # N49D_WRAPPER_INSTRUMENTATION
    $n49dGateState=[pscustomobject]@{Primary=$null;Finally=0;Emitted=0;Trace=[Collections.Generic.List[string]]::new()} # N49D_WRAPPER_INSTRUMENTATION
    $n49dBuildCatchProgress=[pscustomobject]@{S='R';G='N';E='N'};$n49dBuildCatchState=[pscustomobject]@{Latched=$false};$reason='storage';$n49dPhase04Action='22' # N49D_WRAPPER_INSTRUMENTATION
    $n49dGateBlock={};$n49dGateCommand=[pscustomobject]@{};$n49dGateInvocation=[pscustomobject]@{} # N49D_WRAPPER_INSTRUMENTATION
    $n49dGateCommand|Add-Member -MemberType ScriptProperty -Name ScriptBlock -Value {$n49dGateState.Trace.Add('B');if($n49dGateFault -ceq 'block-throw'){throw 'private-block'};return $n49dGateBlock} # N49D_WRAPPER_INSTRUMENTATION
    $n49dGateInvocation|Add-Member -MemberType ScriptProperty -Name MyCommand -Value {$n49dGateState.Trace.Add('M');if($n49dGateFault -ceq 'command-throw'){throw 'private-command'};return $n49dGateCommand} # N49D_WRAPPER_INSTRUMENTATION
    $n49dBuildCatchCommand=$n49dGateCommand;$n49dBuildCatchBlock=$n49dGateBlock # N49D_WRAPPER_INSTRUMENTATION
    if($n49dGateFault -ceq 'action'){$n49dPhase04Action='21'} # N49D_WRAPPER_INSTRUMENTATION
    if($n49dGateFault -ceq 'function-false'){$n49dBuildCatchCommand=$null} # N49D_WRAPPER_INSTRUMENTATION
    if($n49dGateFault -ceq 'block-false'){$n49dBuildCatchBlock=$null} # N49D_WRAPPER_INSTRUMENTATION
    $n49dGateSeen=$null;try{Invoke-N49DProgressGateControl $n49dGateInvocation}catch{$n49dGateSeen=$_} # N49D_WRAPPER_INSTRUMENTATION
    Need ([object]::ReferenceEquals($n49dGateState.Primary,$n49dGateSeen) -and $n49dGateState.Finally -eq 1) 'Progress gate changed primary or finally' # N49D_WRAPPER_INSTRUMENTATION
    # PowerShell property-getter errors yield null; the original reference gates reject it. # N49D_WRAPPER_INSTRUMENTATION
    $n49dGateExpected=switch -Exact ($n49dGateFault){'action'{@('X','',0)}'function-false'{@('R','M',0)}'block-false'{@('S','MMB',0)}'command-throw'{@('R','M',0)}'block-throw'{@('S','MMB',0)}'match'{@('I','MMB',1)}} # N49D_WRAPPER_INSTRUMENTATION
    Need ($n49dBuildCatchProgress.G -ceq $n49dGateExpected[0] -and ($n49dGateState.Trace -join '') -ceq $n49dGateExpected[1] -and $n49dGateState.Emitted -eq $n49dGateExpected[2]) 'Progress reference short circuit or masked getter changed' # N49D_WRAPPER_INSTRUMENTATION
   } # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  foreach($n49dProgressFault in @('none','S','G','E','writer','flush','invalid','type','invocation','latch-write','action')){ # N49D_WRAPPER_INSTRUMENTATION
   $script:n49dPhase04Latched=$false;$script:n49dBuildProgressLatched=$false # N49D_WRAPPER_INSTRUMENTATION
   $n49dProgressProbe=[pscustomobject]@{S='R';G='I';E='F'};$n49dProgressReads=[Collections.Generic.List[string]]::new() # N49D_WRAPPER_INSTRUMENTATION
   foreach($n49dField in @('S','G','E')){ # N49D_WRAPPER_INSTRUMENTATION
    $n49dGetter=[scriptblock]::Create("`$n49dProgressReads.Add('$n49dField');if(`$n49dProgressFault -ceq '$n49dField'){throw 'private-progress-read'};return '$($n49dProgressProbe.$n49dField)'") # N49D_WRAPPER_INSTRUMENTATION
    $n49dProgressProbe|Add-Member -Force -MemberType ScriptProperty -Name $n49dField -Value $n49dGetter # N49D_WRAPPER_INSTRUMENTATION
   } # N49D_WRAPPER_INSTRUMENTATION
   if($n49dProgressFault -ceq 'invalid'){$n49dProgressProbe=[pscustomobject]@{S='private';G='I';E='F'}} # N49D_WRAPPER_INSTRUMENTATION
   if($n49dProgressFault -ceq 'type'){$n49dProgressProbe=[pscustomobject]@{S=$true;G='I';E='F'}} # N49D_WRAPPER_INSTRUMENTATION
   $n49dStatusPrimary=$null;$n49dStatusSeen=$null;$n49dStatusFinally=0 # N49D_WRAPPER_INSTRUMENTATION
   $n49dStatusWriter=[N49DBuildCatchControlWriter]::new('none');$n49dStatusConsole=[Console]::Error # N49D_WRAPPER_INSTRUMENTATION
   try{ # N49D_WRAPPER_INSTRUMENTATION
    [Console]::SetError($n49dStatusWriter) # N49D_WRAPPER_INSTRUMENTATION
    try{ # N49D_WRAPPER_INSTRUMENTATION
     try{throw [IO.IOException]::new('private-status-primary')}catch{ # N49D_WRAPPER_INSTRUMENTATION
      $n49dStatusPrimary=$_ # N49D_WRAPPER_INSTRUMENTATION
      try{Write-N49DPhase04Failure $_ '22'}catch{} # N49D_WRAPPER_INSTRUMENTATION
      if($n49dProgressFault -cin @('writer','flush')){$n49dStatusWriter.Fault=$n49dProgressFault} # N49D_WRAPPER_INSTRUMENTATION
      if($n49dProgressFault -ceq 'latch-write'){Set-Variable -Scope Script -Name n49dBuildProgressLatched -Value $false -Option ReadOnly} # N49D_WRAPPER_INSTRUMENTATION
      $n49dStatusAction=if($n49dProgressFault -ceq 'action'){'21'}else{'22'} # N49D_WRAPPER_INSTRUMENTATION
      try{if($n49dProgressFault -ceq 'invocation'){throw 'private-status-invocation'};Write-N49DBuildProgress $n49dStatusAction $n49dProgressProbe}catch{} # N49D_WRAPPER_INSTRUMENTATION
      throw # N49D_WRAPPER_INSTRUMENTATION
     } # N49D_WRAPPER_INSTRUMENTATION
    }catch{$n49dStatusSeen=$_}finally{$n49dStatusFinally++} # N49D_WRAPPER_INSTRUMENTATION
    Need ([object]::ReferenceEquals($n49dStatusPrimary,$n49dStatusSeen) -and $n49dStatusFinally -eq 1) 'Progress changed primary rethrow or cleanup' # N49D_WRAPPER_INSTRUMENTATION
    $n49dStatusExpected="`nN49D_PHASE04_V1:22:IO"+[Environment]::NewLine # N49D_WRAPPER_INSTRUMENTATION
    if($n49dProgressFault -cin @('none','flush')){$n49dStatusExpected+="`nN49D_BUILD_PROGRESS_V1:RIF"+[Environment]::NewLine} # N49D_WRAPPER_INSTRUMENTATION
    Need ($n49dStatusWriter.ToString() -ceq $n49dStatusExpected) 'Progress failure suppressed original marker or leaked' # N49D_WRAPPER_INSTRUMENTATION
    $n49dStatusWriteCount=if($n49dProgressFault -cin @('none','writer','flush')){2}else{1} # N49D_WRAPPER_INSTRUMENTATION
    $n49dStatusFlushCount=if($n49dProgressFault -cin @('none','flush')){2}else{1} # N49D_WRAPPER_INSTRUMENTATION
    Need ($n49dStatusWriter.Writes -eq $n49dStatusWriteCount -and $n49dStatusWriter.Flushes -eq $n49dStatusFlushCount) 'Progress write flush failure order' # N49D_WRAPPER_INSTRUMENTATION
    if($n49dProgressFault -ceq 'latch-write'){Remove-Variable -Scope Script -Name n49dBuildProgressLatched -Force;$script:n49dBuildProgressLatched=$true} # N49D_WRAPPER_INSTRUMENTATION
    if($n49dProgressFault -cne 'invocation'){ # N49D_WRAPPER_INSTRUMENTATION
     $n49dBeforeReads=$n49dProgressReads.Count;$n49dBeforeWrites=$n49dStatusWriter.Writes # N49D_WRAPPER_INSTRUMENTATION
     Write-N49DBuildProgress '22' $n49dProgressProbe # N49D_WRAPPER_INSTRUMENTATION
     Need ($n49dStatusWriter.Writes -eq $n49dBeforeWrites -and $n49dProgressReads.Count -eq $n49dBeforeReads) 'Progress first attempt retried' # N49D_WRAPPER_INSTRUMENTATION
    } # N49D_WRAPPER_INSTRUMENTATION
    # All cached fields are read once before null/type rejection, including masked getter errors. # N49D_WRAPPER_INSTRUMENTATION
    $n49dReadExpected=switch -Exact ($n49dProgressFault){'S'{'S|G|E'}'G'{'S|G|E'}'E'{'S|G|E'}'none'{'S|G|E'}'writer'{'S|G|E'}'flush'{'S|G|E'}default{''}} # N49D_WRAPPER_INSTRUMENTATION
    Need (($n49dProgressReads -join '|') -ceq $n49dReadExpected) 'Progress getter order or repeated access' # N49D_WRAPPER_INSTRUMENTATION
   }finally{ # N49D_WRAPPER_INSTRUMENTATION
    if($n49dProgressFault -ceq 'latch-write'){Remove-Variable -Scope Script -Name n49dBuildProgressLatched -Force -ErrorAction SilentlyContinue} # N49D_WRAPPER_INSTRUMENTATION
    $script:n49dPhase04Latched=$false;$script:n49dBuildProgressLatched=$false # N49D_WRAPPER_INSTRUMENTATION
    [Console]::SetError($n49dStatusConsole);$n49dStatusWriter.Dispose() # N49D_WRAPPER_INSTRUMENTATION
   } # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  $n49dCatchCurrentWriter=[N49DBuildCatchControlWriter]::new('none') # N49D_WRAPPER_INSTRUMENTATION
  try{ # N49D_WRAPPER_INSTRUMENTATION
   [Console]::SetError($n49dCatchCurrentWriter) # N49D_WRAPPER_INSTRUMENTATION
   $n49dVocabulary=@(@([Management.Automation.RuntimeException]::new('private'),'RT'),@([Management.Automation.MethodInvocationException]::new('private'),'MI'),@([Management.Automation.ParameterBindingException]::new('private'),'PB'),@([IO.IOException]::new('private'),'IO'),@([ArgumentException]::new('private'),'AR'),@([InvalidOperationException]::new('private'),'OP'),@([FormatException]::new('private'),'OT')) # N49D_WRAPPER_INSTRUMENTATION
   foreach($n49dVocabularyCase in $n49dVocabulary){ # N49D_WRAPPER_INSTRUMENTATION
    $n49dCatchCurrentWriter.GetStringBuilder().Clear()|Out-Null # N49D_WRAPPER_INSTRUMENTATION
    $null=& $n49dCatchBaseEmitter ([pscustomobject]@{Exception=$n49dVocabularyCase[0]}) 'unknown-private-reason' ([pscustomobject]@{Latched=$false}) # N49D_WRAPPER_INSTRUMENTATION
    Need ($n49dCatchCurrentWriter.ToString() -ceq ("`nN49D_BUILD_CATCH_V1:unknown:"+$n49dVocabularyCase[1]+[Environment]::NewLine)) 'Catch vocabulary changed' # N49D_WRAPPER_INSTRUMENTATION
   } # N49D_WRAPPER_INSTRUMENTATION
   foreach($n49dReasonCase in @('input-invalid','object-mismatch','compile-failed','binary-unavailable','storage','INPUT-INVALID')){ # N49D_WRAPPER_INSTRUMENTATION
    $n49dCatchCurrentWriter.GetStringBuilder().Clear()|Out-Null # N49D_WRAPPER_INSTRUMENTATION
    $null=& $n49dCatchBaseEmitter ([pscustomobject]@{Exception=[IO.IOException]::new('private')}) $n49dReasonCase ([pscustomobject]@{Latched=$false}) # N49D_WRAPPER_INSTRUMENTATION
    $n49dFixedReason=if($n49dReasonCase -ceq 'INPUT-INVALID'){'unknown'}else{$n49dReasonCase} # N49D_WRAPPER_INSTRUMENTATION
    Need ($n49dCatchCurrentWriter.ToString() -ceq ("`nN49D_BUILD_CATCH_V1:"+$n49dFixedReason+':IO'+[Environment]::NewLine)) 'Catch exact reason mapping changed' # N49D_WRAPPER_INSTRUMENTATION
   } # N49D_WRAPPER_INSTRUMENTATION
  }finally{[Console]::SetError($n49dCatchSavedConsole)} # N49D_WRAPPER_INSTRUMENTATION
  Need ([object]::ReferenceEquals([Console]::Error,$n49dCatchSavedConsole)) 'Catch vocabulary console restoration' # N49D_WRAPPER_INSTRUMENTATION
  & { # N49D_WRAPPER_INSTRUMENTATION
   $n49dWorkProbeWriter=[N49DBuildCatchControlWriter]::new('none') # N49D_WRAPPER_INSTRUMENTATION
   try{ # N49D_WRAPPER_INSTRUMENTATION
    $n49dWorkProbeClock=[pscustomobject]@{ElapsedMilliseconds=[long]20001} # N49D_WRAPPER_INSTRUMENTATION
    $n49dWorkProbe=New-N49DWorkState $n49dWorkProbeWriter {$n49dWorkProbeClock} # N49D_WRAPPER_INSTRUMENTATION
    $n49dWorkOtherWriter=[N49DBuildCatchControlWriter]::new('writer');$n49dWorkSavedConsole=[Console]::Error;[Console]::SetError($n49dWorkOtherWriter) # N49D_WRAPPER_INSTRUMENTATION
    $n49dWorkExpected='' # N49D_WRAPPER_INSTRUMENTATION
    for($n49dWorkOperation=1;$n49dWorkOperation -le 47;$n49dWorkOperation++){foreach($n49dWorkEdge in @('B','E')){ # N49D_WRAPPER_INSTRUMENTATION
     $n49dWorkToken=$n49dWorkOperation.ToString('D2',[Globalization.CultureInfo]::InvariantCulture) # N49D_WRAPPER_INSTRUMENTATION
     Write-N49DWork $n49dWorkProbe $n49dWorkToken $n49dWorkEdge # N49D_WRAPPER_INSTRUMENTATION
     $n49dWorkExpected+="`nN49D_WORK_V1:"+$n49dWorkToken+':'+$n49dWorkEdge+':20000'+[Environment]::NewLine # N49D_WRAPPER_INSTRUMENTATION
    }} # N49D_WRAPPER_INSTRUMENTATION
    Need ($n49dWorkProbeWriter.ToString() -ceq $n49dWorkExpected -and $n49dWorkProbeWriter.Writes -eq 94 -and $n49dWorkProbeWriter.Flushes -eq 94 -and $n49dWorkProbe.Started -eq 47 -and $n49dWorkProbe.Ended -eq 47) 'Work complete emitter order or saturation' # N49D_WRAPPER_INSTRUMENTATION
    Need ($n49dWorkOtherWriter.Writes -eq 0 -and $n49dWorkOtherWriter.Flushes -eq 0) 'Work used redirected error stream' # N49D_WRAPPER_INSTRUMENTATION
   }finally{[Console]::SetError($n49dWorkSavedConsole);$n49dWorkOtherWriter.Dispose();$n49dWorkProbeWriter.Dispose()} # N49D_WRAPPER_INSTRUMENTATION
   foreach($n49dWorkFault in @('none','writer','flush','clock','negative','type','constructor','invocation','latch-read','latch-write','duplicate','order','backward')){ # N49D_WRAPPER_INSTRUMENTATION
    $n49dWorkProbeWriter=[N49DBuildCatchControlWriter]::new($(if($n49dWorkFault -cin @('writer','flush')){$n49dWorkFault}else{'none'})) # N49D_WRAPPER_INSTRUMENTATION
    try{ # N49D_WRAPPER_INSTRUMENTATION
     $n49dWorkCounter=[pscustomobject]@{Reads=0};$n49dWorkAfter=0;$n49dWorkFinally=0;$n49dWorkPrimary=$null;$n49dWorkSeen=$null # N49D_WRAPPER_INSTRUMENTATION
     $n49dWorkProbeClock=[pscustomobject]@{};$n49dWorkProbeClock|Add-Member -MemberType ScriptProperty -Name ElapsedMilliseconds -Value {$n49dWorkCounter.Reads++;if($n49dWorkFault -ceq 'clock'){throw 'private-clock'};if($n49dWorkFault -ceq 'negative'){return [long]-1};if($n49dWorkFault -ceq 'type'){return 'private-clock'};if($n49dWorkFault -ceq 'backward' -and $n49dWorkCounter.Reads -gt 1){return [long]0};return [long]1} # N49D_WRAPPER_INSTRUMENTATION
     $n49dWorkProbe=New-N49DWorkState $n49dWorkProbeWriter {if($n49dWorkFault -ceq 'constructor'){throw 'private-constructor'};$n49dWorkProbeClock} # N49D_WRAPPER_INSTRUMENTATION
     if($n49dWorkFault -ceq 'latch-read'){$n49dWorkProbe|Add-Member -Force -MemberType ScriptProperty -Name Disabled -Value {throw 'private-latch-read'}} # N49D_WRAPPER_INSTRUMENTATION
     if($n49dWorkFault -ceq 'latch-write'){$n49dWorkProbe|Add-Member -Force -MemberType ScriptProperty -Name Disabled -Value {$false} -SecondValue {throw 'private-latch-write'}} # N49D_WRAPPER_INSTRUMENTATION
     try{try{throw [IO.IOException]::new('private-work-primary')}catch{ # N49D_WRAPPER_INSTRUMENTATION
      $n49dWorkPrimary=$_;try{if($n49dWorkFault -ceq 'invocation'){throw 'private-invocation'};Write-N49DWork $n49dWorkProbe '01' 'B'}catch{};$n49dWorkAfter++;throw # N49D_WRAPPER_INSTRUMENTATION
     }}catch{$n49dWorkSeen=$_}finally{$n49dWorkFinally++} # N49D_WRAPPER_INSTRUMENTATION
     Need ([object]::ReferenceEquals($n49dWorkPrimary,$n49dWorkSeen) -and $n49dWorkAfter -eq 1 -and $n49dWorkFinally -eq 1) 'Work observation changed primary or cleanup' # N49D_WRAPPER_INSTRUMENTATION
     if($n49dWorkFault -ceq 'duplicate'){Write-N49DWork $n49dWorkProbe '01' 'B'} # N49D_WRAPPER_INSTRUMENTATION
     if($n49dWorkFault -ceq 'order'){Write-N49DWork $n49dWorkProbe '02' 'B'} # N49D_WRAPPER_INSTRUMENTATION
     if($n49dWorkFault -ceq 'backward'){Write-N49DWork $n49dWorkProbe '01' 'E'} # N49D_WRAPPER_INSTRUMENTATION
     $n49dWorkWant=if($n49dWorkFault -cin @('none','flush','duplicate','order','backward')){"`nN49D_WORK_V1:01:B:00001"+[Environment]::NewLine}else{''} # N49D_WRAPPER_INSTRUMENTATION
     Need ($n49dWorkProbeWriter.ToString() -ceq $n49dWorkWant) 'Work failure token retention' # N49D_WRAPPER_INSTRUMENTATION
     $n49dWorkExpectedWrites=if($n49dWorkFault -cin @('none','writer','flush','duplicate','order','backward')){1}else{0};$n49dWorkExpectedFlushes=if($n49dWorkFault -cin @('none','flush','duplicate','order','backward')){1}else{0} # N49D_WRAPPER_INSTRUMENTATION
     $n49dWorkExpectedReads=if($n49dWorkFault -ceq 'backward'){2}elseif($n49dWorkFault -cin @('none','writer','flush','clock','negative','type','duplicate','order')){1}else{0} # N49D_WRAPPER_INSTRUMENTATION
     Need ($n49dWorkProbeWriter.Writes -eq $n49dWorkExpectedWrites -and $n49dWorkProbeWriter.Flushes -eq $n49dWorkExpectedFlushes -and $n49dWorkCounter.Reads -eq $n49dWorkExpectedReads) 'Work clock write flush order' # N49D_WRAPPER_INSTRUMENTATION
     if($n49dWorkFault -cnotin @('none','invocation')){ # N49D_WRAPPER_INSTRUMENTATION
      $n49dWorkWrites=$n49dWorkProbeWriter.Writes;$n49dWorkFlushes=$n49dWorkProbeWriter.Flushes;$n49dWorkPriorReads=$n49dWorkCounter.Reads # N49D_WRAPPER_INSTRUMENTATION
      Write-N49DWork $n49dWorkProbe '01' 'E' # N49D_WRAPPER_INSTRUMENTATION
      Need ($n49dWorkProbeWriter.Writes -eq $n49dWorkWrites -and $n49dWorkProbeWriter.Flushes -eq $n49dWorkFlushes -and $n49dWorkCounter.Reads -eq $n49dWorkPriorReads) 'Work failed first attempt retried' # N49D_WRAPPER_INSTRUMENTATION
     } # N49D_WRAPPER_INSTRUMENTATION
    }finally{$n49dWorkProbeWriter.Dispose()} # N49D_WRAPPER_INSTRUMENTATION
   } # N49D_WRAPPER_INSTRUMENTATION
   foreach($n49dWorkCleanup in @(@(3,41),@(42,46))){ # N49D_WRAPPER_INSTRUMENTATION
    $n49dWorkProbeWriter=[N49DBuildCatchControlWriter]::new('none') # N49D_WRAPPER_INSTRUMENTATION
    try{ # N49D_WRAPPER_INSTRUMENTATION
     $n49dWorkProbe=New-N49DWorkState $n49dWorkProbeWriter {[pscustomobject]@{ElapsedMilliseconds=[long]2}};$n49dWorkProbe.Started=$n49dWorkCleanup[0];$n49dWorkProbe.Ended=$n49dWorkCleanup[0]-1 # N49D_WRAPPER_INSTRUMENTATION
     $n49dWorkToken=$n49dWorkCleanup[1].ToString('D2',[Globalization.CultureInfo]::InvariantCulture);Write-N49DWork $n49dWorkProbe $n49dWorkToken 'B';Write-N49DWork $n49dWorkProbe $n49dWorkToken 'E' # N49D_WRAPPER_INSTRUMENTATION
     Need ($n49dWorkProbeWriter.Writes -eq 2 -and $n49dWorkProbeWriter.Flushes -eq 2 -and $n49dWorkProbe.Started -eq $n49dWorkCleanup[1] -and $n49dWorkProbe.Ended -eq $n49dWorkCleanup[1]) 'Work cleanup transition' # N49D_WRAPPER_INSTRUMENTATION
    }finally{$n49dWorkProbeWriter.Dispose()} # N49D_WRAPPER_INSTRUMENTATION
   } # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  try{Write-N49DWork $n49dWork '40' 'E'}catch{} # N49D_WRAPPER_INSTRUMENTATION
 }finally{ # N49D_WRAPPER_INSTRUMENTATION
  try{Write-N49DWork $n49dWork '41' 'B'}catch{} # N49D_WRAPPER_INSTRUMENTATION
  [Console]::SetError($n49dCatchSavedConsole) # N49D_WRAPPER_INSTRUMENTATION
  if($null -ne $n49dCatchCurrentWriter){$n49dCatchCurrentWriter.Dispose()} # N49D_WRAPPER_INSTRUMENTATION
  Reset-N49DBuildCatchFiles $true # N49D_WRAPPER_INSTRUMENTATION
  $script:resolved=$n49dCatchSavedCounters[0];$script:executed=$n49dCatchSavedCounters[1];$script:rebuilt=$n49dCatchSavedCounters[2];$script:batch=$n49dCatchSavedCounters[3] # N49D_WRAPPER_INSTRUMENTATION
 } # N49D_WRAPPER_INSTRUMENTATION
} # N49D_WRAPPER_INSTRUMENTATION
 Need ([object]::ReferenceEquals([Console]::Error,$n49dCatchOuterConsole)) 'Catch outer console restoration' # N49D_WRAPPER_INSTRUMENTATION
 try{Write-N49DWork $n49dWork '41' 'E'}catch{} # N49D_WRAPPER_INSTRUMENTATION
 try{Write-N49DWork $n49dWork '42' 'B'}catch{} # N49D_WRAPPER_INSTRUMENTATION
 & { # N49D_WRAPPER_INSTRUMENTATION
  $n49dWriterDir=Join-Path $root 'report-writer';$null=New-Item -ItemType Directory -Path $n49dWriterDir # N49D_WRAPPER_INSTRUMENTATION
  $n49dWriterPath=Join-Path $n49dWriterDir 'report.json';$n49dWriterTemp=$n49dWriterPath+'.tmp-'+$PID # N49D_WRAPPER_INSTRUMENTATION
  $n49dWriterValue=[pscustomobject]@{schema='qbrain-n49d-build-context-v1';state='prepared';identity=$id;mode='build-only';architecture='x64';cwd_role='build/cl';vcvars=$null;runtime_prefix=$null;production_objects=$null;production_executable=$null;canonical_binary=$null;failure=$null} # N49D_WRAPPER_INSTRUMENTATION
  function Assert-N49DWriterFile([string]$Expected){ # N49D_WRAPPER_INSTRUMENTATION
   Need ([Convert]::ToBase64String([IO.File]::ReadAllBytes($n49dWriterPath)) -ceq [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($Expected+"`n"))) 'Writer exact canonical bytes' # N49D_WRAPPER_INSTRUMENTATION
   Need ((ConvertTo-QbrainCanonical (Read-QbrainPhaseReport $n49dWriterPath build)) -ceq $Expected) 'Writer actual readback' # N49D_WRAPPER_INSTRUMENTATION
   $n49dWriterLeaves=@(Get-ChildItem -LiteralPath $n49dWriterDir -Force) # N49D_WRAPPER_INSTRUMENTATION
   Need ($n49dWriterLeaves.Count -eq 1 -and $n49dWriterLeaves[0].Name -ceq 'report.json' -and -not $n49dWriterLeaves[0].PSIsContainer -and -not [IO.File]::Exists($n49dWriterTemp)) 'Writer backup or temporary residue' # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  try{ # N49D_WRAPPER_INSTRUMENTATION
   Need (-not [IO.File]::Exists($n49dWriterPath)) 'Writer new file already exists' # N49D_WRAPPER_INSTRUMENTATION
   $n49dWriterFirst=ConvertTo-QbrainCanonical $n49dWriterValue # N49D_WRAPPER_INSTRUMENTATION
   $n49dWriterOutput=@(Write-QbrainPhaseReport $n49dWriterPath $n49dWriterValue build) # N49D_WRAPPER_INSTRUMENTATION
   Need ($n49dWriterOutput.Count -eq 0 -and (ConvertTo-QbrainCanonical $n49dWriterValue) -ceq $n49dWriterFirst) 'Writer create output or input mutation' # N49D_WRAPPER_INSTRUMENTATION
   Assert-N49DWriterFile $n49dWriterFirst # N49D_WRAPPER_INSTRUMENTATION
   try{Write-N49DWork $n49dWork '42' 'E'}catch{} # N49D_WRAPPER_INSTRUMENTATION
   try{Write-N49DWork $n49dWork '43' 'B'}catch{} # N49D_WRAPPER_INSTRUMENTATION
   $n49dWriterValue.state='failed';$n49dWriterValue.failure='storage';$n49dWriterSecond=ConvertTo-QbrainCanonical $n49dWriterValue # N49D_WRAPPER_INSTRUMENTATION
   Need ($n49dWriterFirst -cne $n49dWriterSecond -and [IO.File]::Exists($n49dWriterPath)) 'Writer replacement precondition' # N49D_WRAPPER_INSTRUMENTATION
   $n49dWriterOutput=@(Write-QbrainPhaseReport $n49dWriterPath $n49dWriterValue build) # N49D_WRAPPER_INSTRUMENTATION
   Need ($n49dWriterOutput.Count -eq 0 -and (ConvertTo-QbrainCanonical $n49dWriterValue) -ceq $n49dWriterSecond) 'Writer replace output or input mutation' # N49D_WRAPPER_INSTRUMENTATION
   Assert-N49DWriterFile $n49dWriterSecond # N49D_WRAPPER_INSTRUMENTATION
   try{Write-N49DWork $n49dWork '43' 'E'}catch{} # N49D_WRAPPER_INSTRUMENTATION
   try{Write-N49DWork $n49dWork '44' 'B'}catch{} # N49D_WRAPPER_INSTRUMENTATION
   $n49dWriterValue.state='prepared';$n49dWriterRejected=$null # N49D_WRAPPER_INSTRUMENTATION
   try{$null=Write-QbrainPhaseReport $n49dWriterPath $n49dWriterValue build}catch{$n49dWriterRejected=$_} # N49D_WRAPPER_INSTRUMENTATION
   Need ($null -ne $n49dWriterRejected -and $n49dWriterRejected.Exception.Message -ceq 'Unexpected failure.') 'Writer validation rejection changed' # N49D_WRAPPER_INSTRUMENTATION
   Assert-N49DWriterFile $n49dWriterSecond # N49D_WRAPPER_INSTRUMENTATION
   try{Write-N49DWork $n49dWork '44' 'E'}catch{} # N49D_WRAPPER_INSTRUMENTATION
   try{Write-N49DWork $n49dWork '45' 'B'}catch{} # N49D_WRAPPER_INSTRUMENTATION
   $n49dWriterValue.failure=$null;$n49dWriterRejected=$null # N49D_WRAPPER_INSTRUMENTATION
   $n49dWriterLock=[IO.File]::Open($n49dWriterPath,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::None) # N49D_WRAPPER_INSTRUMENTATION
   try{try{$null=Write-QbrainPhaseReport $n49dWriterPath $n49dWriterValue build}catch{$n49dWriterRejected=$_}}finally{$n49dWriterLock.Dispose()} # N49D_WRAPPER_INSTRUMENTATION
   Need ($null -ne $n49dWriterRejected -and $n49dWriterRejected.Exception -is [Management.Automation.MethodInvocationException] -and $n49dWriterRejected.Exception.InnerException -is [IO.IOException]) 'Writer replacement failure changed' # N49D_WRAPPER_INSTRUMENTATION
   Need ((ConvertTo-QbrainCanonical $n49dWriterValue) -ceq $n49dWriterFirst) 'Writer failure input mutation' # N49D_WRAPPER_INSTRUMENTATION
   Assert-N49DWriterFile $n49dWriterSecond # N49D_WRAPPER_INSTRUMENTATION
   try{Write-N49DWork $n49dWork '45' 'E'}catch{} # N49D_WRAPPER_INSTRUMENTATION
  }finally{ # N49D_WRAPPER_INSTRUMENTATION
   try{Write-N49DWork $n49dWork '46' 'B'}catch{} # N49D_WRAPPER_INSTRUMENTATION
   Remove-Item -LiteralPath $n49dWriterDir -Recurse -Force # N49D_WRAPPER_INSTRUMENTATION
  } # N49D_WRAPPER_INSTRUMENTATION
  try{Write-N49DWork $n49dWork '46' 'E'}catch{} # N49D_WRAPPER_INSTRUMENTATION
 } # N49D_WRAPPER_INSTRUMENTATION
}catch{$n49dPhase04Action=$null;throw} # N49D_WRAPPER_INSTRUMENTATION
 try{Write-N49DWork $n49dWork '47' 'B'}catch{} # N49D_WRAPPER_INSTRUMENTATION
 $n49dPhase04Action='23' # N49D_WRAPPER_INSTRUMENTATION
 Need ($script:batch -notmatch '(?m)^(qbrain_tests\.exe|".*qbrain_tests\.exe")\r?$') 'BuildOnly ran tests'
 $n49dPhase04Action='24' # N49D_WRAPPER_INSTRUMENTATION
 $build=Read-QbrainPhaseReport $bp build
 $n49dPhase04Action='25' # N49D_WRAPPER_INSTRUMENTATION
 Need ($build.state -ceq 'prepared' -and $null -ne $build.canonical_binary) 'Prepared binary missing'
 $n49dPhase04Action='26' # N49D_WRAPPER_INSTRUMENTATION
 $ro=@{RunOnly=$true;PhaseContext=$bp;RunReport=$rp}
 $n49dPhase04Action='27' # N49D_WRAPPER_INSTRUMENTATION
 $before=$script:executed
 $n49dPhase04Action='28' # N49D_WRAPPER_INSTRUMENTATION
 Need ((Dispatch $ro) -ne 0 -and $script:executed -eq $before) 'Prepared accepted'
 $n49dPhase04Action='29' # N49D_WRAPPER_INSTRUMENTATION
 Assert-QbrainEqual (Get-QbrainFileDescriptor $binary) $build.canonical_binary
 $n49dPhase04Action='30' # N49D_WRAPPER_INSTRUMENTATION
 $build.state='ready'
 $n49dPhase04Action='31' # N49D_WRAPPER_INSTRUMENTATION
 Write-QbrainPhaseReport $bp $build build
 $n49dPhase04Action='32' # N49D_WRAPPER_INSTRUMENTATION
 Need ((Dispatch $ro) -eq 0) 'RunOnly'
 $n49dPhase04Action='33' # N49D_WRAPPER_INSTRUMENTATION
 Need ($script:batch.Contains('"'+$binary+'"')) 'Absolute launch'
 $n49dPhase04Action='34' # N49D_WRAPPER_INSTRUMENTATION
 Need ($script:batch -notmatch '(?m)^(cl |link |copy |echo TESTS_BUILD_OK)') 'RunOnly build work'
 $n49dPhase04Action='35' # N49D_WRAPPER_INSTRUMENTATION
 Assert-QbrainProductionInputs $context $manifest
 $n49dPhase04Action='36' # N49D_WRAPPER_INSTRUMENTATION
 $body=($functions|Where-Object Name -eq Invoke-QbrainRunPhase).Extent.Text
 $n49dPhase04Action='37' # N49D_WRAPPER_INSTRUMENTATION
 Need ($body -notmatch 'New-Item|Remove-Item|New-QbrainTestsBatch|Get-QbrainTestInputs|ProductionBuilder') 'RunOnly object work'
 $n49dPhase04Action='38' # N49D_WRAPPER_INSTRUMENTATION
 $before=$script:executed
 $n49dPhase04Action='39' # N49D_WRAPPER_INSTRUMENTATION
 $saved=$build.vcvars.path.sha256
 $n49dPhase04Action='40' # N49D_WRAPPER_INSTRUMENTATION
 $build.vcvars.path.sha256='e'*64
 $n49dPhase04Action='41' # N49D_WRAPPER_INSTRUMENTATION
 Write-QbrainPhaseReport $bp $build build
 $n49dPhase04Action='42' # N49D_WRAPPER_INSTRUMENTATION
 Need ((Dispatch $ro) -ne 0 -and $script:executed -eq $before) 'Context mismatch ran'
 $n49dPhase04Action='43' # N49D_WRAPPER_INSTRUMENTATION
 $build.vcvars.path.sha256=$saved
 $n49dPhase04Action='44' # N49D_WRAPPER_INSTRUMENTATION
 Write-QbrainPhaseReport $bp $build build
 $n49dPhase04Action='45' # N49D_WRAPPER_INSTRUMENTATION
 [IO.File]::WriteAllBytes($binary,[byte[]](117))
 $n49dPhase04Action='46' # N49D_WRAPPER_INSTRUMENTATION
 Need ((Dispatch $ro) -ne 0 -and $script:executed -eq $before) 'Binary mismatch ran'
 $n49dPhase04Action='47' # N49D_WRAPPER_INSTRUMENTATION
 [IO.File]::WriteAllBytes($binary,[byte[]](116))
 $n49dPhase04Action='48' # N49D_WRAPPER_INSTRUMENTATION
 $op=Join-Path $obj $consumed[0]
 $n49dPhase04Action='49' # N49D_WRAPPER_INSTRUMENTATION
 [IO.File]::WriteAllBytes($op,[byte[]](118))
 $n49dPhase04Action='50' # N49D_WRAPPER_INSTRUMENTATION
 Need ((Dispatch $bo) -ne 0 -and $script:executed -eq $before) 'Object mismatch compiled'
 $n49dPhase04Action='51' # N49D_WRAPPER_INSTRUMENTATION
 [IO.File]::WriteAllBytes($op,[byte[]](111))
 $n49dPhase04Action='52' # N49D_WRAPPER_INSTRUMENTATION
 Write-QbrainPhaseReport $bp $build build
 $n49dPhase04Action='53' # N49D_WRAPPER_INSTRUMENTATION
 Need ((Dispatch $ro) -eq 0) 'Restored run'
 try{Write-N49DWork $n49dWork '47' 'E'}catch{} # N49D_WRAPPER_INSTRUMENTATION
}catch{try{Write-N49DPhase04Failure $_ $n49dPhase04Action}catch{};try{Write-N49DBuildProgress $n49dPhase04Action $n49dBuildCatchProgress}catch{};throw} # N49D_WRAPPER_INSTRUMENTATION
Write-N49DWrapperMarker 9 # N49D_WRAPPER_INSTRUMENTATION
Write-N49DWrapperMarker 10 # N49D_WRAPPER_INSTRUMENTATION
 $value=Read-QbrainPhaseReport $rp run;$lf=(ConvertTo-QbrainCanonical $value)+"`n"
 foreach($text in @($lf,$lf.Replace("`n","`r`n"))){$null=ConvertFrom-QbrainPhaseBytes (Bytes $text) run}
 $bad=@($lf.Replace('"mode":"run-only"','"mode":"run-only","mode":"run-only"'),
 $lf.Replace('"mode":"run-only"','"mode":"run-only","Mode":"run-only"'),$lf.Replace('"mode":"run-only",',''),
 $lf.Replace('"mode":"run-only"','"mode":"run-only","unknown":null'),$lf.Replace('"context_matched":true','"context_matched":null'),
 $lf.Replace('"state":"ready"','"state":"READY"'),$lf.Replace('c'*40,'C'*40),
 $lf.Replace($value.canonical_binary.sha256,$value.canonical_binary.sha256.ToUpperInvariant()),
 $lf.Replace('"run-only"','"run\u002donly"'),$lf+"`n",' '+$lf,
 ('['*7+'0'+']'*7+"`n"),('['+((@('{}')*257)-join ',')+']'+"`n"),
 $lf.Replace('"run-only"',('"'+('x'*129)+'"')),$lf.Replace('"run-only"','"rún-only"'))
 foreach($token in @('true','1.0','1e0','-1','9007199254740992','12345678901234567','"1"')){
  $bad+=$lf.Replace('"size":1}','"size":'+$token+'}')
 }
 foreach($text in $bad){Reject {$null=ConvertFrom-QbrainPhaseBytes (Bytes $text) run}}
 Reject {$null=ConvertFrom-QbrainPhaseBytes ([byte[]](239,187,191)+(Bytes $lf)) run}
 $empty=[pscustomobject]@{schema=$manifest.schema;state='prepared';identity=$id;produced=[object[]]@();consumed=[object[]]@();production_executable=$null;failure=$null}
 $null=ConvertFrom-QbrainPhaseBytes (Bytes ((ConvertTo-QbrainCanonical $empty)+"`n")) objects
 $empty.consumed=[object[]]@('x.obj');Reject {Assert-QbrainPhaseReport $empty objects}
Write-N49DWrapperMarker 11 # N49D_WRAPPER_INSTRUMENTATION
 $env:ERRORLEVEL='0';$marker=Join-Path $root 'later'
 foreach($status in @(0,7,259,-2147483648,-1)){
switch($status){0{Write-N49DWrapperMarker 12}7{Write-N49DWrapperMarker 16}259{Write-N49DWrapperMarker 20}-2147483648{Write-N49DWrapperMarker 24}-1{Write-N49DWrapperMarker 28}} # N49D_WRAPPER_INSTRUMENTATION
  $command='"'+$Python+'" -c "import os;os._exit('+[string]$status+')"';$result=[pscustomobject]@{ExitCode=0}
  Invoke-QbrainNativeBatch ("@echo off`r`n"+$command+"`r`nexit /b") $result
  Need (([long]$result.ExitCode -band 4294967295L) -eq ([long]$status -band 4294967295L)) 'Actual 32bit exit'
switch($status){0{Write-N49DWrapperMarker 13}7{Write-N49DWrapperMarker 17}259{Write-N49DWrapperMarker 21}-2147483648{Write-N49DWrapperMarker 25}-1{Write-N49DWrapperMarker 29}} # N49D_WRAPPER_INSTRUMENTATION
switch($status){0{Write-N49DWrapperMarker 14}7{Write-N49DWrapperMarker 18}259{Write-N49DWrapperMarker 22}-2147483648{Write-N49DWrapperMarker 26}-1{Write-N49DWrapperMarker 30}} # N49D_WRAPPER_INSTRUMENTATION
  Remove-Item $marker -ErrorAction SilentlyContinue;$result.ExitCode=0
  Invoke-QbrainNativeBatch ("@echo off`r`n"+$command+"`r`n"+$guard.Replace("`n","`r`n")+"`r`necho later>`"$marker`"`r`nexit /b") $result
  Need (($status -eq 0 -and $result.ExitCode -eq 0 -and (Test-Path $marker)) -or
   ($status -ne 0 -and $result.ExitCode -eq 1 -and -not (Test-Path $marker))) 'Later operation after rejection'
switch($status){0{Write-N49DWrapperMarker 15}7{Write-N49DWrapperMarker 19}259{Write-N49DWrapperMarker 23}-2147483648{Write-N49DWrapperMarker 27}-1{Write-N49DWrapperMarker 31}} # N49D_WRAPPER_INSTRUMENTATION
 }
Write-N49DWrapperMarker 32 # N49D_WRAPPER_INSTRUMENTATION
 $check="import os,sys;sys.exit(0 if os.getcwd()==sys.argv[1] and os.environ['PATH'].startswith(sys.argv[2]+';') and os.environ['QBRAIN_PHASE_FIXTURE']=='kept' else 91)"
 $result=[pscustomobject]@{ExitCode=0}
 Invoke-QbrainNativeBatch ("@echo off`r`ncd /d `"$out`"`r`n"+$guard+"`r`nset PATH=$root\bin;%PATH%`r`nset QBRAIN_PHASE_FIXTURE=kept`r`n`"$Python`" -c `"$check`" `"$out`" `"$root\bin`"`r`nexit /b") $result
 Need ($result.ExitCode -eq 0) 'Actual cwd/environment'
Write-N49DWrapperMarker 33 # N49D_WRAPPER_INSTRUMENTATION
 foreach($status in @(37,0)){
switch($status){37{Write-N49DWrapperMarker 34}0{Write-N49DWrapperMarker 36}} # N49D_WRAPPER_INSTRUMENTATION
  if(Test-Path $rp){Remove-Item $rp -Recurse -Force}
  $publishFailure={param($batch,$result)
   Invoke-QbrainNativeBatch ("@echo off`r`n`"$Python`" -c `"import os;os._exit($status)`"`r`nexit /b") $result
   Remove-Item $rp;$null=New-Item -ItemType Directory $rp
  }
  $observed=Dispatch $ro $publishFailure
  Need (($status -eq 37 -and $observed -eq 37) -or ($status -eq 0 -and $observed -ne 0)) 'Publication changed exit'
switch($status){37{Write-N49DWrapperMarker 35}0{Write-N49DWrapperMarker 37}} # N49D_WRAPPER_INSTRUMENTATION
 }
 'WRAPPER_CONTROLS_OK'
}finally{
Write-N49DWrapperMarker 38 # N49D_WRAPPER_INSTRUMENTATION
 $env:ERRORLEVEL=$oldShadow;$env:TEMP=$oldTemp;$env:TMP=$oldTmp
 if(Test-Path $root){Remove-Item -LiteralPath $root -Recurse -Force}
Write-N49DWrapperMarker 39 # N49D_WRAPPER_INSTRUMENTATION
}
'''
    script=root/'wrapper-controls.ps1';script.write_bytes(body.encode('utf-8-sig'))
    _run_windows_wrapper(root,script,wrapper)
    RESULTS.append(dict(name='windows-actual-wrapper-dispatch-parser-exit',passed=True))


def phase_packet_controls(root):
    root.mkdir()
    for job in ('windows-msvc','windows-cmake'):
        case=root/job;case.mkdir();evidence=case/'evidence';ident=tiny_bundle(evidence,job)
        original={p.relative_to(evidence).as_posix():p.read_bytes() for p in evidence.rglob('*') if p.is_file()}
        desc=lambda raw:dict(size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        def rebind(packet,bind_phase_results=True):
            result=json.loads(packet['qualification.json'])
            for name in result['required']:
                path='stages/'+name+'/result.json';row=json.loads(packet[path])
                for k in ('stdout','stderr'):
                    row[k]=desc(packet['stages/'+name+'/'+k+'.bin']);row['ownership'][k]=row[k]
                for p in row['reports']:
                    if p in packet:row['reports'][p]=desc(packet[p])
                row['available_reports']=copy.deepcopy(row['reports']);packet[path]=json.dumps(row,sort_keys=True).encode()
            pair=q.PHASE_REPORTS['pair'][0]
            if pair in packet:
                value=json.loads(packet[pair])
                if bind_phase_results:
                    for role in ('build','run'):
                        value[role]['result']=desc(packet['stages/direct-tests-'+role+'/result.json'])
                packet[pair]=q.canonical_phase_bytes(value)
                if pair in result['reports']:
                    result['reports'][pair].update(desc(packet[pair]))
            packet['qualification.json']=json.dumps(result,sort_keys=True).encode()
            return packet
        def materialize(packet):
            for path,raw in packet.items():(evidence/path).write_bytes(raw)
        called=[]
        def pack(src,staging,identity):
            called.append(True);staging=Path(staging);staging.mkdir();part=staging/'parts/00';part.mkdir(parents=True)
            archive=part/'evidence.part';raw=make_archive(Path(src),archive,identity);(part/'manifest.json').write_bytes(raw)
            return dict(passed=True,identity=identity,parts_root=str(staging/'parts'),part_count=1,
                manifest_sha256=hashlib.sha256(raw).hexdigest(),manifest_bytes=len(raw),archive_sha256=q.digest(archive),archive_size=archive.stat().st_size)
        control('phase-packet-valid-'+job,lambda:q.validate_recordings(original.__getitem__,ident,files=original))
        control('phase-package-valid-'+job,lambda:q.package(evidence,case/'package',ident,_generic_packager=pack))
        review=case/'review';review.mkdir();archive=case/'tiny.zip';raw=make_archive(evidence,archive,ident);outer=review/'valid.zip';wrap(archive,raw,outer)
        control('phase-consumer-valid-'+job,lambda:q.consume(outer,review,ident,hashlib.sha256(raw).hexdigest(),q.digest(outer)))
        build='direct-tests-build' if job=='windows-msvc' else 'build'
        cases=[
            ('policy','stages/'+build+'/result.json',lambda v:v.update(completion_policy='strict-v1'),'fixed stage completion policy'),
            ('http-stop','stages/'+build+'/result.json',lambda v:v['ownership'].update(classification='stopped'),'build owner facts'),
            ('nonzero','stages/'+build+'/result.json',lambda v:v['ownership'].update(exit=259),'build owner facts'),
            ('close-false','stages/'+build+'/result.json',lambda v:v['ownership']['build_completion'].update(close_returned=False),'build close proof'),
            ('order','stages/'+build+'/result.json',lambda v:v['ownership']['build_completion'].update(root_observed_us=6),'build event ordering'),
            ('deadline','stages/'+build+'/result.json',lambda v:v['ownership']['build_completion'].update(success_deadline_us=9999999999),'build success deadline extended'),
            ('argv','stages/'+build+'/result.json',lambda v:v.update(argv=['unreviewed']),'fixed stage command'),
            ('v1','stages/'+build+'/result.json',lambda v:v.update(schema='qbrain-n49d-stage-v1'),'stage schema'),
            ('extra','stages/'+build+'/result.json',lambda v:v.update(unreviewed=True),'stage success key inventory'),
            ('qualification-v1','qualification.json',lambda v:v.update(schema='qbrain-n49d-qualification-v1'),'qualification schema')]
        if job=='windows-msvc':
            cases += [
                ('strict-substitution','stages/direct-tests-run/result.json',lambda v:v.update(completion_policy='trusted-build-v1'),'fixed stage completion policy'),
                ('objects','reports/direct-production-objects.json',lambda v:v['consumed'].reverse(),'object inventory'),
                ('prepared','reports/direct-tests-build-context.json',lambda v:v.update(state='prepared'),'phase report not ready'),
                ('binary','reports/direct-tests-build-context.json',lambda v:v['canonical_binary'].update(sha256='e'*64),'phase canonical binding'),
                ('test-exit','reports/direct-tests-run-context.json',lambda v:v.update(test_exit=259),'run context success'),
                ('reverse','reports/direct-tests-pair.json',lambda v:v['run'].update(start_us=350000),'pair interval/deadline'),
                ('pair-budget','reports/direct-tests-pair.json',lambda v:v.update(pair_budget_us=1800000001),'pair fixed budget'),
                ('pair-role','reports/direct-tests-pair.json',lambda v:v['build'].update(stage='direct-production'),'pair stage role'),
                ('pair-ref','reports/direct-tests-pair.json',lambda v:v['build']['result'].update(sha256='f'*64),'pair sealed stage binding'),
                ('pair-missing','qualification.json',lambda v:v.update(reports={}),'qualification report inventory'),
                ('pair-late','qualification.json',lambda v:v['reports']['reports/direct-tests-pair.json'].update(finalized_us=1800000000),'pair publication binding/deadline'),
                ('phase-window','stages/direct-tests-run/result.json',lambda v:v['phase_window'].update(start_us=1),'pair phase window'),
                ('pair-cycle','stages/direct-tests-run/result.json',lambda v:(v['requested_reports'].append('reports/direct-tests-pair.json'),v['reports'].update({'reports/direct-tests-pair.json':{}})),'fixed required report inventory')]
        else:
            cases += [('generator','reports/configure-readiness.json',lambda v:v.update(generator='other'),'configure readiness facts'),
                ('readiness-false','reports/configure-readiness.json',lambda v:v['checks'].update(pg_off=False),'configure readiness facts'),
                ('configure-file','reports/configure-readiness.json',lambda v:v['files'].pop('qbrain.sln'),'report key inventory'),
                ('configure-location','reports/configure-readiness.json',lambda v:v['source_location'].update(sha256='e'*64),'configure location identity')]
        for label,path,mutate,boundary in cases:
            packet=dict(original);value=json.loads(packet[path]);mutate(value)
            packet[path]=q.canonical_phase_bytes(value) if path.startswith('reports/') else json.dumps(value).encode()
            rebind(packet,not path.endswith('direct-tests-pair.json'))
            tag=job+'-'+label
            expect_failure('phase-producer-'+tag,lambda:q.validate_recordings(packet.__getitem__,ident,files=packet),boundary)
            materialize(packet);before=len(called)
            expect_failure('phase-package-'+tag,lambda:q.package(evidence,case/'rejected',ident,_generic_packager=pack),boundary)
            check(len(called)==before,'invalid phase reached generic packager')
            raw=make_archive(evidence,archive,ident);bad=review/'bad.zip';wrap(archive,raw,bad)
            expect_failure('phase-consumer-'+tag,lambda:q.consume(bad,review,ident,hashlib.sha256(raw).hexdigest(),q.digest(bad)),boundary)
            materialize(original)
        if job=='windows-msvc':
            packet=dict(original);packet['stages/direct-tests-run/stdout.bin']=b'TESTS_BUILD_OK\n';rebind(packet)
            expect_failure('phase-old-build-log-not-canonical',lambda:q.validate_recordings(packet.__getitem__,ident,files=packet),'Native group evidence')
        for duplicate_path in ('qualification.json','stages/'+build+'/result.json'):
            packet=dict(original);packet[duplicate_path]=packet[duplicate_path].replace(b'{',b'{"schema":"duplicate",',1)
            expect_failure('phase-duplicate-'+job+'-'+duplicate_path,lambda:q.validate_recordings(packet.__getitem__,ident,files=packet),'duplicate JSON key')


FAILURE_V2='qbrain-n49d-source-controls-failure-v2'
FAILURE_LEGACY='qbrain-n49d-source-controls-failure-legacy-v1'
FAILURE_UNAVAILABLE='qbrain-n49d-source-controls-failure-unavailable-v1'


def ordinary_failure_value(value):
    kind=type(value)
    check(kind in (type(None),bool,str,int,float,list,dict),'failure ordinary JSON type')
    if kind is float:check(math.isfinite(value),'failure nonfinite number')
    elif kind is list:
        for item in value:ordinary_failure_value(item)
    elif kind is dict:
        check(all(type(k) is str for k in value),'failure key type')
        for item in value.values():ordinary_failure_value(item)


def failure_equal(a,b):
    if type(a) is not type(b):return False
    if type(a) is dict:return set(a)==set(b) and all(failure_equal(a[k],b[k]) for k in a)
    if type(a) is list:return len(a)==len(b) and all(failure_equal(x,y) for x,y in zip(a,b))
    if type(a) is float:return math.isfinite(a) and math.isfinite(b) and a.hex()==b.hex()
    return a==b


def validate_failure_facts(value):
    ordinary_failure_value(value)
    check(type(value) is dict and set(value) in ({'passed','error','controls'},{'passed','error','controls','failure_detail'}),
          'failure fact keys')
    check(value['passed'] is False and type(value['error']) is str and type(value['controls']) is list,'failure fact types')
    names=set()
    for row in value['controls']:
        check(type(row) is dict and {'name','passed'}<=set(row),'failure control row')
        check(type(row['name']) is str and bool(row['name']) and type(row['passed']) is bool,'failure control fields')
        check(row['name'] not in names,'duplicate failure control');names.add(row['name'])
        if 'boundary' in row:_validate_wrapper_file_boundary(row['boundary'])


def pack_failure_rows(rows):
    return [[row['name'],row['passed'],{k:v for k,v in row.items() if k not in ('name','passed')}]
            if set(row)-{'name','passed'} else [row['name'],row['passed']] for row in rows]


def expand_failure_v2(raw):
    check(type(raw) is bytes and len(raw)<=65536,'failure byte bound')
    value=q.json_unique(raw);ordinary_failure_value(value)
    check(type(value) is dict and value.get('schema')==FAILURE_V2,'failure v2 schema')
    check(set(value) in ({'schema','passed','error','controls'},{'schema','passed','error','controls','failure_detail'}),
          'failure v2 keys')
    check(type(value['controls']) is list,'failure encoded rows')
    rows=[]
    for row in value['controls']:
        check(type(row) is list and len(row) in (2,3),'failure pair/triple length')
        extras=row[2] if len(row)==3 else {}
        check(type(extras) is dict and (len(row)==2 or bool(extras)) and not {'name','passed'}&set(extras),'failure extra fields')
        rows.append(dict(name=row[0],passed=row[1],**extras))
    result={k:v for k,v in value.items() if k!='schema'};result['controls']=rows
    validate_failure_facts(result);return result


def failure_text(value):
    ordinary_failure_value(value)
    text=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
    check(len((text+'\n').encode())<=65536 and len((text+'\r\n').encode())<=65536,'failure representation limit')
    return text


def render_selftest_failure(value):
    check(type(value) is dict and type(value.get('error')) is str,'primary failure unavailable')
    primary=value['error'];validated=False;reason='control-encoding-unavailable'
    try:
        validate_failure_facts(value);validated=True
        packed=dict(value,schema=FAILURE_V2,controls=pack_failure_rows(value['controls']))
        text=failure_text(packed)
        check(failure_equal(expand_failure_v2((text+'\n').encode()),value),'failure full roundtrip')
        return text
    except Exception as error:
        if str(error)=='failure representation limit':reason='representation-limit'
    if validated:
        try:return failure_text(dict(value,schema=FAILURE_LEGACY))
        except Exception:reason='representation-limit'
    incomplete=dict(schema=FAILURE_UNAVAILABLE,passed=False,error=primary,controls_available=False,reason=reason,
                    failure_detail_status='absent' if 'failure_detail' not in value else 'unavailable')
    if 'failure_detail' in value:
        try:
            ordinary_failure_value(value['failure_detail'])
            json.dumps(value['failure_detail'],allow_nan=False)
            incomplete.update(failure_detail_status='retained',failure_detail=value['failure_detail'])
        except Exception:pass
    try:return failure_text(incomplete)
    except Exception:raise ValueError(primary) from None


def failed_envelope_controls():
    value=dict(passed=False,error='original primary',controls=[
        dict(name='first',passed=True),dict(name='second',passed=False,trace=dict(
            events=['root','close'],deadline=1.25,signed_zero=-0.0,complete=True))],failure_detail=None)
    before=copy.deepcopy(value);identities=(id(value['controls']),id(value['controls'][1]['trace']))
    raw=(render_selftest_failure(value)+'\n').encode()
    for newline in (b'\n',b'\r\n'):
        restored=expand_failure_v2(raw[:-1]+newline)
        check(failure_equal(restored,value),'failure reconstruction changed facts')
    check(failure_equal(value,before) and identities==(id(value['controls']),id(value['controls'][1]['trace'])),'failure renderer mutated input')
    absent=dict(value);del absent['failure_detail']
    check('failure_detail' not in expand_failure_v2((render_selftest_failure(absent)+'\n').encode()),'absent detail became null')
    check(not failure_equal(True,1) and not failure_equal(1,1.0) and not failure_equal(0.0,-0.0),'failure comparison coerced')
    for label,mutate in [
        ('duplicate',lambda v:v['controls'].append(copy.deepcopy(v['controls'][0]))),
        ('name',lambda v:v['controls'][0].update(name=1)),('status',lambda v:v['controls'][0].update(passed=1)),
        ('detail',lambda v:v.update(failure_detail=float('nan'))),('extra',lambda v:v['controls'][1].update(other=object())),
        ('keys',lambda v:v.update(extra=True))]:
        bad=copy.deepcopy(value);mutate(bad);out=json.loads(render_selftest_failure(bad))
        check(out['schema']==FAILURE_UNAVAILABLE and out['error']==value['error'] and out['passed'] is False and
              out['controls_available'] is False,'malformed facts passed encoding')
    with patch(__name__+'.pack_failure_rows',side_effect=ValueError('private-copy-fault')):
        legacy=json.loads(render_selftest_failure(value))
    check(legacy['schema']==FAILURE_LEGACY and failure_equal({k:v for k,v in legacy.items() if k!='schema'},value),'legacy fallback lost facts')
    expect_failure('failure-v2-rejects-legacy',lambda:expand_failure_v2(json.dumps(legacy).encode()),'failure v2 schema')
    unavailable=json.loads(render_selftest_failure(dict(value,controls=[None])))
    expect_failure('failure-v2-rejects-unavailable',lambda:expand_failure_v2(json.dumps(unavailable).encode()),'failure v2 schema')
    encoded=json.loads(raw)
    for label,row in [('length',[]),('empty-extra',['x',True,{}]),('collision',['x',True,{'name':'y'}]),('scalar','x')]:
        bad=dict(encoded,controls=[row])
        expect_failure('failure-v2-'+label,lambda bad=bad:expand_failure_v2(json.dumps(bad).encode()))
    duplicate=raw.replace(b'"error":',b'"error":"other","error":',1)
    expect_failure('failure-v2-duplicate-key',lambda:expand_failure_v2(duplicate),'duplicate JSON key')
    class Text(str):pass
    class Row(dict):pass
    for label,bad in [('subclass',dict(value,error=Text('primary'))),('row-subclass',dict(value,controls=[Row(name='x',passed=True)]))]:
        if label=='subclass':expect_failure('failure-'+label,lambda:render_selftest_failure(bad),'primary failure unavailable')
        else:check(json.loads(render_selftest_failure(bad))['schema']==FAILURE_UNAVAILABLE,'subclass encoded')
    huge=dict(value,error='x'*65536)
    expect_failure('failure-unrepresentable-primary',lambda:render_selftest_failure(huge),'x'*65536)
    RESULTS.append(dict(name='failure-v2-full-facts-roundtrip-fallback',passed=True))


def build_native_controls(root):
    if os.name!='nt':return
    root.mkdir();release=root/'sentinel-release'
    sentinel=subprocess.Popen([sys.executable,'-c',"import time;from pathlib import Path;p=Path("+repr(str(release))+");end=time.monotonic()+30\nwhile not p.exists() and time.monotonic()<end:time.sleep(.01)"],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for api in ('owner','recorder'):
            for style in ('inherited','redirected','late'):
                for policy in ('strict-v1','trusted-build-v1'):
                    folder=root/(api+'-'+style+'-'+policy);folder.mkdir();ready=folder/'ready'
                    child="import os,time;from pathlib import Path;Path("+repr(str(ready))+").write_text(str(os.getpid()));print('owned-ready',flush=True);time.sleep(10);print('late-write',flush=True)"
                    redirection=',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL' if style!='inherited' else ''
                    leader="import sys,subprocess,time;from pathlib import Path;subprocess.Popen([sys.executable,'-c',"+repr(child)+"]"+redirection+");end=time.monotonic()+1\nwhile not Path("+repr(str(ready))+").exists():\n if time.monotonic()>=end:raise SystemExit(8)\n time.sleep(.005)\nprint('root-ready',flush=True)"
                    argv=[sys.executable,'-c',leader];owners=[];entered=[];hidden=[]
                    real_owner=q.OwnedChild;real_active=q._WindowsTree.active;real_end=q.OwnedChild._end
                    def factory(*args,**kwargs):
                        owner=real_owner(*args,**kwargs);owners.append(owner);return owner
                    def active(tree):
                        value=real_active(tree)
                        if style=='late' and owners and tree is owners[0].tree and not entered and owners[0].proc.poll()==0 and value:
                            hidden.append(True);return []
                        return value
                    def end(owner,failure=None,intentional=False):
                        if style=='late' and not entered:
                            check(owner is owners[0] and failure is None and intentional is False and owner.proc.poll()==0 and
                                  not any(t.is_alive() for t in owner.readers) and hidden,'native late entry not proved')
                            entered.append(True)
                        return real_end(owner,failure,intentional)
                    with patch.object(q._WindowsTree,'active',active),patch.object(q.OwnedChild,'_end',end):
                        if api=='owner':
                            owner=factory(argv,folder,dict(os.environ),subprocess.DEVNULL,folder/'stdout',folder/'stderr',3,4096,completion_policy=policy)
                            try:owner.complete_build() if policy=='trusted-build-v1' else owner.wait()
                            except q.OwnedChildError:pass
                        else:
                            rec=q.Recorder(folder/'record',phase_identity(),['direct-production'],dict(os.environ),folder,4096)
                            rec.locations=dict(source=str(folder),build=str(folder/'build'),output=str(rec.root),python=sys.executable)
                            spec=dict(argv=argv,timeout_seconds=3,reports=[],binaries_before=[],binaries_after=[],completion_policy=policy)
                            with patch.object(q,'OwnedChild',factory),patch.object(q,'stage_contract',return_value={'direct-production':spec}),patch.object(q,'ROOT',folder):
                                try:rec.run('direct-production',argv,3)
                                except ValueError:pass
                            owner=owners[0]
                    value=owner.result
                    check(ready.is_file() and ready.read_text().isdigit() and sentinel.poll() is None,'native owned/sentinel readiness')
                    if policy=='trusted-build-v1':q.validate_build_proof(value)
                    else:check(value['classification']=='lingering-descendant','native strict policy changed')
                    check(value['exit']==0 and all(value[k] is True for k in ('cleanup_ok','owned_tree_empty','stable','readers_done')),'native teardown incomplete')
                    before=[q.descriptor(p) for p in owner.paths];time.sleep(.02)
                    check(before==[q.descriptor(p) for p in owner.paths],'native post-close output mutation')
                    RESULTS.append(dict(name='build-native-'+api+'-'+style+'-'+policy,passed=True))
    finally:
        release.write_text('release');check(sentinel.wait(timeout=3)==0,'unrelated sentinel did not exit independently')


def diagnostic_admission_controls(root,ident,originals):
    """Actual caller/collector; failed-stage and POSIX Windows-path models only."""
    import io,types
    from contextlib import redirect_stderr
    pair=dict(acceptance=False,failure='pair-finalization-timeout',report=None)
    boundary=lambda quotes:chr(0x1f600)*634+'\x01'+'"'*quotes+'x'*(389-quotes)
    errors=[
        ('ascii','x'*1024,None),
        ('below',boundary(3),12287),('equal',boundary(4),12288),
        ('over',boundary(5),12289),
        ('old-lf-admitted',chr(0x1f600)*647+'\x01'+'"'+'x'*375,12428),
        ('supplementary',chr(0x1f600)*1024,16569)]
    cases=[(name,error,meta,'fresh') for name,error,meta in errors]
    cases.extend((name,error,meta,'prior') for name,error,meta in errors[3:])
    cases.extend([('primary-storage',errors[4][1],12428,'primary-directory'),
                  ('collector-storage',errors[1][1],12287,'packet-directory')])
    real_contract=q.stage_contract;reference=None
    for name,error,metadata,state in cases:
        case=root/(name+'-'+state);source=case/'source';source.mkdir(parents=True)
        output=case/'output';destination=case/'n49d-diagnostics/failure.json'
        if state in ('prior','packet-directory'):
            destination.parent.mkdir()
            if state=='prior':destination.write_bytes(b'prior diagnostics\n')
            else:destination.mkdir()
        seen=[];inputs={}
        class FailedRecorder:
            def __init__(self,folder,identity,required,environment,cwd):
                self.root=folder;folder.mkdir();self.required=required;self.stages=[]
            def run(self,name,*args,**kwargs):
                check(name=='source-before' and not seen,'model native launch')
                seen.append(name);self.stages=self.required[:6]
                self.pair=types.SimpleNamespace(result=None,failure=pair['failure'],
                    value={'state':'complete'},diagnostic=lambda:dict(pair))
                for leaf,raw in originals.items():
                    if leaf=='stages/direct-tests-run/result.json':
                        value=json.loads(raw);value['ownership']['stable']=None
                        encoded=json.dumps(value).encode();raw=encoded+b' '*(len(raw)-len(encoded))
                    target=self.root/leaf;target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(raw);inputs[leaf]=raw
                if state=='primary-directory':(self.root/'failure.json').mkdir()
                raise ValueError(error)
        def launch_contract(identity,locations):
            actual=real_contract(identity,locations);modeled=copy.deepcopy(actual)
            if os.name!='nt':
                for position in (1,9):
                    modeled['source-before']['argv'][position]=actual['source-before']['argv'][position].replace('\\','/')
            restored=copy.deepcopy(modeled)
            for position in (1,9):restored['source-before']['argv'][position]=actual['source-before']['argv'][position]
            check(restored==actual,'platform model changed non-launch contract')
            return modeled
        args=types.SimpleNamespace(source=source,build=case/'build',output=output,
            package=case/'package',job='windows-msvc',commit=ident['commit'],tree=ident['tree'],
            run_id=ident['run_id'],run_attempt=ident['run_attempt'])
        captured=io.StringIO()
        with patch.object(q,'ROOT',source),patch.object(q,'os',types.SimpleNamespace(name='nt',environ={})),\
             patch.object(q,'Recorder',FailedRecorder),patch.object(q,'stage_contract',launch_contract),redirect_stderr(captured):
            code=q.run_job(args)
        text=captured.getvalue()
        check(code==1 and seen==['source-before'] and text.startswith(error+'\n') and text.count(error)==1,
              'actual caller replaced primary')
        check(not (output/'qualification.json').exists() and not args.package.exists(),'model qualified/package')
        primary=output/'failure.json'
        if state=='primary-directory':
            check(not primary.is_file() and 'incomplete-primary-record: ' in text,'missing primary record hidden')
        else:check(json.loads(primary.read_bytes())['error']==error,'primary record changed')
        rejected=metadata is not None and metadata>12288
        if rejected:
            reason='diagnostics metadata cap' if name=='supplementary' else 'diagnostics CRLF metadata cap'
            check('incomplete-diagnostics: '+reason+'\n' in text,'wrong real collector rejection')
            if state=='prior':check(destination.read_bytes()==b'prior diagnostics\n','rejection replaced prior packet')
            else:check(not destination.exists() and not destination.parent.exists(),'rejection created fresh destination')
        elif state=='packet-directory':
            check(destination.is_dir() and 'incomplete-diagnostics: ' in text,'collector storage failure hidden')
        else:
            check(text==error+'\n','admitted collection gained secondary failure')
            actual=destination.read_bytes();payload=json.loads(actual)
            check(set(payload['files'])==set(inputs),'admitted role inventory')
            for leaf,raw in inputs.items():
                row=payload['files'][leaf]
                check(base64.b64decode(row['data'])==raw and row['size']==len(raw)==row['retained_bytes'] and
                      row['sha256']==hashlib.sha256(raw).hexdigest() and row['retained_offset']==0 and
                      row['truncated'] is False and row['complete'] is False and row['status']=='stability-unknown',
                      'admitted selected facts changed')
            if reference is None:reference=copy.deepcopy(payload)
        expected=copy.deepcopy(reference)
        expected.update(error=error,error_size=len(error.encode()),error_sha256=hashlib.sha256(error.encode()).hexdigest())
        lf=json.dumps(expected,sort_keys=True,indent=2).encode();crlf=lf.replace(b'\n',b'\r\n')
        check(len(crlf)==len(lf)+lf.count(b'\n') and json.loads(lf)==json.loads(crlf),'newline identity')
        check(sum(len(row['data']) for row in expected['files'].values())==245776,'base64 role sum')
        if metadata is not None:check(len(crlf)-245776==metadata,'exact metadata boundary')
        if not rejected and state!='packet-directory':check(actual==lf,'admitted LF bytes changed')
        check(245776+12288==258064<262144,'conditional envelope bound')
        RESULTS.append(dict(name='diagnostic-admission-caller-'+name+'-'+state,passed=True))


def phase_retention_controls(root,export=None):
    root.mkdir();ident=phase_identity();ident.update(run_id='9'*20,run_attempt='8'*20)
    objects=dict(schema=q.PHASE_REPORTS['objects'][1],state='ready',identity=ident,
        produced=[dict(name=n,size=9007199254740991,sha256='f'*64) for n in q.PRODUCTION_OBJECTS],
        consumed=list(q.CONSUMED_OBJECTS),production_executable=dict(size=9007199254740991,sha256='f'*64),failure=None)
    reports={'objects':objects,'build-context':q.phase_seed('build-context',ident),
             'run-context':q.phase_seed('run-context',ident),'pair':q.phase_seed('pair',ident)}
    # Whole failed-report capacity fixtures preserve all fields; whitespace makes
    # them intentionally noncanonical and incapable of qualifying a job.
    originals={}
    for role,value in reports.items():
        path,_,cap=q.PHASE_REPORTS[role];raw=q.canonical_phase_bytes(value);raw=raw[:-1]+b' '*(cap-len(raw))+b'\n'
        dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);originals[path]=raw
    stage='direct-tests-run'
    for name in (stage,'direct-tests-build'):
        folder=root/'stages'/name;folder.mkdir(parents=True)
        row=dict(ownership=dict(stable=True),classification='failed',schema='retention-fixture')
        raw=json.dumps(row).encode();raw+=b' '*(16384-len(raw));(folder/'result.json').write_bytes(raw)
        originals['stages/'+name+'/result.json']=raw
    for name in ('stdout','stderr'):
        raw=bytes(range(256))*256;(root/'stages'/stage/(name+'.bin')).write_bytes(raw)
        originals['stages/'+stage+'/'+name+'.bin']=raw
    payload=q.failure_diagnostics(root,root/'actual.json',ident,[stage],q.required_stages('windows-msvc'),'x'*1024)
    check(set(payload['files'])==set(originals),'maximal failure role inventory')
    for name,raw in originals.items():
        row=payload['files'][name]
        check(base64.b64decode(row['data'])==raw and row['size']==len(raw) and not row['truncated'] and
              row['sha256']==hashlib.sha256(raw).hexdigest(),'maximal retained bytes changed')
    text=json.dumps(payload,sort_keys=True,indent=2)
    check(sum(len(v['data']) for v in payload['files'].values())==245776,'per-leaf base64 arithmetic')
    for label,newline in [('LF','\n'),('CRLF','\r\n')]:
        raw=text.replace('\n',newline).encode()
        check(len(raw)<=262144 and len(raw)-245776<=12288,'complete diagnostic envelope bound')
        check(json.loads(raw)==payload,'newline envelope semantics')
        if export is not None:
            export.mkdir(parents=True,exist_ok=True);(export/(label+'.json')).write_bytes(raw)
    RESULTS.append(dict(name='phase-maximal-LF-CRLF-retention',passed=True))
    for job in ('windows-msvc','windows-cmake'):
        for name in q.required_stages(job):
            prior,roles=q.diagnostic_roles(phase_identity(job),name)
            check(len(roles)<=4 and all(len(x)==3 for x in roles),'diagnostic role expansion')
            if job=='windows-msvc' and name=='canonical-groups':check(prior=='direct-tests-run' and roles==[(q.PHASE_REPORTS['pair'][0],4096,True)],'canonical diagnostic priority')
            if name.endswith(('-normal','-optimized')) and any(name.startswith(d+'-') for d in q.DRIVERS):
                expected=[('reports/'+name+'/RESULT.json',8192,False)] if name.startswith(('mcp_directory_search-','directory_search-')) else [('reports/'+name+'.json',8192,False)] if name.startswith(('context_process-','named_arguments-')) else []
                check(roles==expected and prior==('direct-tests-build' if job=='windows-msvc' else 'canonical-build'),'current driver report priority')
    result=root/'stages'/stage/'result.json';saved=result.read_bytes();result.write_bytes(b'{invalid')
    packet=q.failure_diagnostics(root,root/'malformed.json',ident,[stage],[], 'fixture')
    check(all(p in packet['files'] and base64.b64decode(packet['files'][p]['data'])==raw for p,raw in originals.items() if p.startswith('reports/')),'malformed result hid fixed reports')
    result.write_bytes(saved)
    path=root/q.PHASE_REPORTS['objects'][0];path.write_bytes(path.read_bytes()+b'x')
    packet=q.failure_diagnostics(root,root/'oversized.json',ident,[stage],[],'fixture')
    check(packet['files'][q.PHASE_REPORTS['objects'][0]]['status']=='oversized' and
          'data' not in packet['files'][q.PHASE_REPORTS['objects'][0]],'oversized report truncated into complete evidence')

    for job,table in [
        ('windows-msvc',{'direct-production':(None,['objects']),'direct-tests-build':('direct-production',['objects','build-context','pair']),
                         'direct-tests-run':('direct-tests-build',['objects','build-context','run-context','pair']),'canonical-groups':('direct-tests-run',['pair'])}),
        ('windows-cmake',{'configure':(None,['configure']),'build':('configure',['configure']),'canonical-build':('build',['configure']),
                          'ctest-inventory':('build',[]),'ctest-completeness':('build',[]),'canonical-run':('canonical-build',[]),'canonical-groups':('canonical-build',[])})]:
        for name,(prior,roles) in table.items():
            check(q.diagnostic_roles(phase_identity(job),name)==(prior,[(q.PHASE_REPORTS[r][0],q.PHASE_REPORTS[r][2],True) for r in roles]),'fixed diagnostic matrix')
    for name,prior,report in [('ctest-run','build','reports/ctest.xml'),('winhttp-normal','canonical-build','reports/winhttp-normal.json'),
                              ('source-after','canonical-build','reports/source-after.json')]:
        check(q.diagnostic_roles(phase_identity('windows-cmake'),name)==(prior,[(report,8192,False)]),'later diagnostic priority')
    check(q.diagnostic_roles(ident,'direct-tests-run',pair={'failure':'pair-finalization-timeout'})==
          ('direct-tests-build',[(q.PHASE_REPORTS[r][0],q.PHASE_REPORTS[r][2],True) for r in reports]),'pair diagnostic priority')
    RESULTS.append(dict(name='phase-fixed-failure-role-and-unavailable',passed=True))
    diagnostic_admission_controls(root/'admission',ident,originals)


def fixture_root_controls(root):
    data=b'canonical fixture root\n';leaf=root/'fixed-file-positive.bin';leaf.write_bytes(data)
    expected=dict(size=len(data),sha256=hashlib.sha256(data).hexdigest())
    control('fixed-file-canonical-root',lambda:check(q.fixed_file(root,leaf.name)==expected,
            'canonical regular-file descriptor'))
    def exact_rejection(label,callback,message):
        try:callback()
        except ValueError as error:check(str(error)==message,'fixed-file wrong rejection: '+label)
        else:raise ValueError('fixed-file negative unexpectedly passed: '+label)
        RESULTS.append(dict(name=label,passed=True))
    alias=root/'..'/root.name
    exact_rejection('fixed-file-lexical-root-alias',lambda:q.fixed_file(alias,leaf.name),'fixed root redirected')
    directory=root/'fixed-file-directory';directory.mkdir()
    exact_rejection('fixed-file-nonregular-leaf',lambda:q.fixed_file(root,directory.name),'fixed regular file required')


def main():
    with tempfile.TemporaryDirectory(prefix='n49d-tiny-controls-') as tmp:
        root=Path(tmp).resolve(strict=True);fixture_root_controls(root);source_controls();ancestry_controls();privacy_assertion_controls();audit_launch_controls();proc_reader_controls();absence_oracle_controls();disappearance_controls();image_model=windows_diagnostic_controls(root/'diagnostics');windows_image_controls(root/'images',image_model);failure_detail_controls(root/'failure-detail');initial_parent_controls(root/'initial-parent');(root/'recorder').mkdir();(root/'package').mkdir();recorder_controls(root/'recorder');package_consumer_controls(root/'package');root_terminal_controls(root/'root-terminal');root_terminal_native_controls(root/'root-native');lifecycle_controls(root/'lifecycle');windows_pinned_member_controls(root/'pinned');phase_report_controls(root/'phase-reports');phase_pair_controls(root/'phase-pair');build_lifecycle_controls(root/'build-model');build_native_controls(root/'build-native');wrapper_instrumentation_controls();wrapper_evidence_controls(root/'wrapper-model');windows_wrapper_controls(root/'wrapper-native');phase_packet_controls(root/'phase-packets');phase_retention_controls(root/'phase-retention');failed_envelope_controls();failure_detail_retention_controls(root/'failure-detail-retention')
    print(json.dumps(dict(passed=True,python_optimized=sys.flags.optimize>0,controls=RESULTS,
        linux_reader_backend=('stat-adapter' if q._PROC_STAT_CHILD_ADAPTER else 'native-children') if os.name!='nt' else 'not_applicable',
        n49d_package_wrapper_executed=True,generic_package_fixture_seam=True,inherited_packager_executed=False,inherited_packager_reason='unchanged 1152 MiB reserve; native CI only'),sort_keys=True))
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        print(render_selftest_failure(_selftest_failure(e)),file=sys.stderr);sys.exit(1)
