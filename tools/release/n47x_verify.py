"""Fixed N47X artifact readback. No network, model or native program execution.

Archive pins must be authenticated separately against the fixed Actions run.
Only source from tree-verified archives is loaded as the original test authority.
"""
from __future__ import annotations
import importlib
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile

DELIVERY = '9831f7ca15d11e868ad1b4fd10deabbb9a3cdca5'
DELIVERY_TREE = 'dbc6b165f6b75e849c5cbec098b2d2c855eab00a'
PRODUCT_SOURCE = 'b810d6898dcbbcd49bdbbed1d8473a3ac1c063e4'
PRODUCT_TREE = '60dd02bc5bfe9c9298f5211d989237ac8262fbf7'
RUN = 35479384581
NAME = 'qbrain-windows-x64-n47x-preview.zip'
ZIP_SHA = 'c517582c1ea0e0795e881155edd4d34288e3a002dc3bc7657dafcb96a1eb8b4d'
ZIP_BYTES = 4327611
EXE_SHA = '838955a0ad88779af08c53396b773d62b327cccd4f216a18379f0a76ffa4c9cf'
OLD_ZIP = 'e7158949d805a0a25157bfb720561e4b21e80a433a6c7f031c60ee3bbaa746c5'
OLD_INSTALLER = 'd802c230d2e5b0938b81baa115d5cf5b475aa855fce0df28f0305f00575fcc51'
ARTIFACTS = {
    'source': (10595267364, 'qbrain-n47x-source', 12181484, '4e398b190793651bd1b6a67034e4f3f064096ef08e6ccf080f0035506a6abe05'),
    'native': (10595995650, 'qbrain-n47x-native', 17887980, 'daeb64f9cd78a5975fa6920626cfbb1fb026dd494b59f08a3f9214a5f1f242f3'),
}
HELPER_SHA = 'e07daa3f5f14757ab661938397cc0c82d13f7090a316acf6953601c1265ab97d'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()


def helpers():
    path = Path(__file__).resolve().parents[1] / 'delivery'
    need(sha((path/'verify_n47r_evidence.py').read_bytes()) == HELPER_SHA, 'modified_archive_helper')
    sys.path.insert(0, str(path))
    return importlib.import_module('verify_n47r_evidence')


def upgrade(value, log, script, shell):
    need(isinstance(value, dict) and set(value) == {'schema','result','shell_major','checks','failure',
         'old_zip_sha256','new_zip_sha256','binary_sha256','script_sha256','real_client_verified'}, 'upgrade_shape')
    need(value['schema']=='qbrain-n47x-upgrade-v1' and value['result']=='PASS' and value['failure']==''
         and value['real_client_verified'] is False and type(value['shell_major']) is int
         and value['shell_major']==shell and shell in (5,7), 'upgrade_result')
    need(value['old_zip_sha256']==OLD_ZIP and value['new_zip_sha256']==ZIP_SHA
         and value['binary_sha256']==EXE_SHA and value['script_sha256']==sha(script), 'upgrade_identity')
    rows=value['checks']
    need(isinstance(rows,list) and len(rows)==49 and all(isinstance(x,dict) and set(x)=={'name','passed'}
         and isinstance(x['name'],str) and x['passed'] is True for x in rows), 'upgrade_checks')
    names=[x['name'] for x in rows]
    need(sha(encode(names))=='85dfde45a1c8d53f1351bb8613a460db124b55c3f7af0d1a19077349a7a20ced', 'upgrade_coverage')
    observed=re.findall(r'^PASS (\d+) : (.*)$',log.decode('utf-8-sig').replace('\r\n','\n'),re.M)
    need(observed==[(str(i),n) for i,n in enumerate(names,1)], 'upgrade_log_sequence')
    return {'checks':49,'shell_major':shell,'new_zip_sha256':ZIP_SHA,'real_client_verified':False}


def verify(directory: Path) -> dict:
    v=helpers()
    archives={}
    for label,(_,_,size,digest) in ARTIFACTS.items():
        raw=(directory/(label+'.zip')).read_bytes()
        need(len(raw)==size and sha(raw)==digest, 'artifact_identity_'+label)
        archives[label]=v.unzip(raw)[0]
        need(archives[label]['source.txt'].decode('utf-8-sig').strip()==DELIVERY, 'checkout_identity')
    source,modes,comment=v.unzip(archives['source']['delivery-source.zip'])
    need(comment.decode()==DELIVERY and v.tree_hash(source,modes)==DELIVERY_TREE, 'delivery_source_tree')
    native=archives['native']
    observed,om,oc=v.unzip(native['product-source.zip'])
    canonical={k:source[k] for k in observed}
    pm={k:modes[k] for k in observed}
    need(oc.decode()==PRODUCT_SOURCE and v.tree_hash(canonical,pm)==PRODUCT_TREE, 'product_source_tree')
    converted=v.windows_source_match(canonical,observed,pm,om)
    need(native['product-source.txt'].decode('utf-8-sig').strip()==PRODUCT_SOURCE,'product_checkout_identity')
    with tempfile.TemporaryDirectory(prefix='n47x-readback-') as tmp:
        root=Path(tmp); s=root/'source'; n=root/'native'
        v.extract(source,s);v.extract(native,n)
        sys.path[:0]=[str(s/'tools/delivery'),str(s/'.ci')]
        # All loaded validators have already been bound to the canonical source tree.
        def module(name):
            sys.modules.pop(name,None)
            return importlib.import_module(name)
        pkg=module('package_n47x');z=module('build_integrated_n47r')
        bundle=native['one/'+NAME]
        need(len(bundle)==ZIP_BYTES and sha(bundle)==ZIP_SHA and bundle==native['two/'+NAME], 'repeated_package_bytes')
        files=z.archive_files(bundle);binary=files['qbrain.exe']
        need(sha(binary)==EXE_SHA,'executable_identity')
        provenance=z.obj(files['BUILD-PROVENANCE.json'])
        registrations=canonical['tests/test_main.cpp'].decode()
        groups=module('validate_native_log').verified_groups(registrations,native['native.log'].decode('utf-8-sig'),60)
        need('BUILD_OK' in native['native.log'].decode('utf-8-sig'),'production_build_missing')
        need(provenance['native_groups']==groups and provenance['native_log_sha256']==sha(native['native.log'])
             and provenance['native_workflow_run']==str(RUN) and provenance['native_workflow_attempt']=='1'
             and provenance['compiler_output_reproducible'] is False, 'build_receipt')
        inputs={k:canonical[k].replace(b'\n',b'\r\n') if k.endswith('.ps1') else canonical[k] for k in pkg.FILES}
        # The separate Windows-checkout guide was packaged as CRLF. No arbitrary
        # normalization is permitted; source-owned application docs are Git/LF.
        guide=source['docs/integration/CURRENT-PREVIEW-N47X.zh-CN.md'].replace(b'\n',b'\r\n')
        wanted=pkg.expected(binary,inputs,guide,provenance)
        package=pkg.verify(bundle,wanted)
        for copy in ('one','two'):
            need(z.obj(native[copy+'/PACKAGE-CHECK.json'])==package,'package_receipt')
            need(native[copy+'/SHA256SUMS.txt']==(ZIP_SHA+'  '+NAME+'\n').encode(),'package_checksum')
        for log in ('tests.log','tests-optimized.log'):v.unit_log(archives['source'][log],12)
        v.unit_log(native['package-tests.log'],12)
        for log in ('model-tests.log','model-tests-optimized.log'):v.unit_log(native[log],48)
        extracted=root/'package';v.extract(files,extracted)
        def get(name):return v.obj(native[name+'.json'])
        def exact(name,digest):return v.checkout_bytes(canonical[name],digest)
        usage=module('check_fact_usage_report').validate(get('usage'),binary,exact('.ci/test_fact_usage.py',get('usage')['test_sha256']))
        pages=module('check_fact_usage_pages_report').validate(get('pages'),binary,exact('.ci/test_fact_usage_pages.py',get('pages')['test_sha256']),n/'page-raw')
        processes={}
        for name,mod,fun in [('test_fact_process','validate_fact_report','validate_report'),
            ('test_multiterm_process','validate_multiterm_report','validate_process'),
            ('test_hook_fact_process','validate_hook_fact_report','validate_process'),
            ('test_lifecycle_batch_process','validate_lifecycle_batch_report','validate_process')]:
            r=get(name)
            processes[name]=getattr(module(mod),fun)(r,source_commit=PRODUCT_SOURCE,binary_sha256=EXE_SHA,
                script_sha256=sha(exact('.ci/'+name+'.py',r['script_sha256'])),native=True)
        context=get('test_context_process')
        need(context['checks']==65 and context['provider_calls']==0 and context['provider_tokens'] is None,'context_summary')
        processes['context']={'checks':65,'scope':'source-owned summary and successful original CI; no raw command files'}
        for name,count in [('test_named_arguments',60),('test_search_arguments',226)]:
            r=get(name)
            need(type(r['passed']) is int and r['passed']==count and r['failed']==0 and len(r['checks'])==count
                 and all(x['passed'] is True for x in r['checks']) and r['binary_sha256']==EXE_SHA,'retained_arguments')
            if 'script_sha256' in r:exact('.ci/'+name+'.py',r['script_sha256'])
            processes[name]={'checks':count}
        for name,count in [('test_memory_cycle',44),('test_mcp_boundaries',17)]:
            need(len(re.findall(r'^PASS',native[name+'.log'].decode('utf-8-sig'),re.M))==count,'retained_log')
            processes[name]={'checks':count}
        # Hash-bound historical installer, used only by the original validator.
        prior=(directory/'prior-installer.ps1').read_bytes()
        need(sha(prior)==OLD_INSTALLER,'prior_installer_identity')
        shells={};installer=files['scripts/Install-QbrainMemory.ps1']
        for shell,major in [('powershell',5),('pwsh',7)]:
            r=get('snapshot-'+shell)
            out={'snapshot':module('check_installer_snapshot_report').validate(r,installer,exact('.ci/test_installer_snapshot.ps1',r['test_sha256']),binary,DELIVERY,major)}
            r=get('recovery-'+shell);need(int(r['powershell'].split('.')[0])==major,'recovery_shell')
            out['recovery']=module('check_recovery_report').validate(r,installer,binary)
            r=get('paths-'+shell)
            out['paths']=module('check_installer_case_paths').validate(r,installer,prior,exact('.ci/test_installer_case_paths.ps1',r['script_sha256']),binary,DELIVERY,major,native['paths-'+shell+'.log'])
            for name,mod in [('test_hook_fact_install','validate_hook_fact_report'),('test_promotion_install','validate_promotion_report')]:
                r=get(name+'-'+shell)
                out[name]=module(mod).validate_install(r,source_commit=DELIVERY,binary_sha256=EXE_SHA,
                    script_sha256=sha(exact('.ci/'+name+'.ps1',r['script_sha256'])),installer_sha256=sha(installer),shell_major=major)
            for name,count in [('test_install_hooks',69),('test_install_consent',16),('test_windows_transport',8)]:
                text=native[name+'-'+shell+'.log'].decode('utf-8-sig')
                need(list(map(int,re.findall(r'^PASS (\d+) :',text,re.M)))==list(range(1,count+1)),'installer_log')
                out[name]=count
            r=get('upgrade-'+shell)
            out['upgrade']=upgrade(r,native['upgrade-'+shell+'.log'],v.checkout_bytes(source['tools/delivery/test_n47x_upgrade.ps1'],r['script_sha256']),major)
            shells[shell]=out
        sys.path.insert(0,str(extracted/'tools/acceptance'))
        checker=module('check_memory_task_run');tasks={}
        for label,folder,path in [('claude','pipeline/engine','pipeline/engine-readback.json'),('codex','codex-tasks','codex-readback.json')]:
            result=checker.verify(n/folder,extracted/'qbrain.exe')
            need(result==v.obj(native[path]),'engine_file_readback');tasks[label]=result
        comparison=module('model_ab').score_run(n/'pipeline/http-run',n/'pipeline/engine/evaluator-key.DO-NOT-SEND-TO-MODEL.json')
        need(comparison==v.obj(native['pipeline/comparison.json']) and comparison['execution_kind']=='LOOPBACK_TEST'
             and comparison['completed']==100,'loopback_result')
        return {'schema':'qbrain-n47x-readback-v1','result':'NATIVE_PACKAGE_VERIFIED','delivery_source':DELIVERY,
            'delivery_tree':DELIVERY_TREE,'product_source':PRODUCT_SOURCE,'product_tree':PRODUCT_TREE,'run_id':RUN,
            'source_files':len(source),'product_files':len(canonical),'exact_crlf_files':converted,
            'package':package,'native_groups':groups,'usage':usage,'pages':pages,'processes':processes,
            'shells':shells,'tasks':tasks,'http_fixture_requests':100,'new_native_execution':False,
            'real_model_answers':'NOT_RUN','real_client_verified':False,'live_pg':'SKIP-PG'}
