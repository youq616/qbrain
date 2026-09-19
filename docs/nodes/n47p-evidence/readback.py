"""Offline N47P raw-evidence review. Requires separately retrieved GitHub pins.
No product execution or online assertion. Source/ZIP hashes and every report's
scope are verified; this tool does not authenticate a caller-supplied metadata file.
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, re, sys, zipfile, io

SOURCE = '9feed7c74926d53a7b2a7b21391af02275799f51'
TREE = 'd396b6170866b83db89e54e26f44685ebcd5c276'
RUN = 35415626607
PACKAGE = 'ec681a4599bf1b2a90f3848f5bf65b6d6a32e37254f32392d0709c43080b356c'
EXE = 'c35fadde8c8356b7243bf0b34cfd5c836bda27bb46da87eddcc79c1031bf05b5'
PRIOR_BLOB = 'ff7042fa94b3d6a7b85e06572557fe575ad18c74'

def need(ok, why):
    if not ok: raise ValueError(why)

def sha(raw): return hashlib.sha256(raw).hexdigest()

def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    out = importlib.util.module_from_spec(spec); spec.loader.exec_module(out); return out

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--metadata',type=Path,required=True)
    p.add_argument('--package',type=Path,required=True)
    p.add_argument('--prior-installer',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    v=module(a.root/'docs/nodes/n47l-evidence/verify_candidate.py','unzip_helper')
    meta=v.obj(a.metadata.read_bytes())
    need(meta['source_commit']==SOURCE and meta['run_id']==RUN,'metadata run/source')
    archives={}
    for label,pin in meta['artifacts'].items():
        raw=(a.evidence/pin['file']).read_bytes()
        need(len(raw)==pin['bytes'] and sha(raw)==pin['sha256'],'artifact '+label)
        archives[label]=v.unzip(raw)[0]
    need(set(archives)=={'source','powershell','pwsh','full-native'},'artifact set')
    files,modes,comment=v.unzip(archives['source']['qbrain-source.zip'])
    need(comment.decode()==SOURCE and v.source_tree(files,modes)==TREE,'source tree')
    for path,raw in files.items(): need((a.root/path).read_bytes()==raw,'working copy '+path)
    package=a.package.read_bytes();need(sha(package)==PACKAGE,'public package')
    product=v.unzip(package)[0];exe=product['qbrain.exe'];need(sha(exe)==EXE,'EXE')
    prior=a.prior_installer.read_bytes()
    need(hashlib.sha1(b'blob '+str(len(prior)).encode()+b'\0'+prior).hexdigest()==PRIOR_BLOB,'prior source')
    snapshot=module(a.root/'.ci/check_installer_snapshot_report.py','snapshot_check')
    recovery=module(a.root/'.ci/check_recovery_report.py','recovery_check')
    native=module(a.root/'.ci/validate_native_log.py','native_check')
    sys.path.insert(0,str(a.root/'.ci'))
    install_validators={
        'test_hook_fact_install':module(a.root/'.ci/validate_hook_fact_report.py','fact_install_check'),
        'test_promotion_install':module(a.root/'.ci/validate_promotion_report.py','promotion_install_check')}

    def matched(raw,pin):
        variants=[raw,raw.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')]
        hits=[x for x in variants if sha(x)==pin.lower()]
        need(bool(hits),'checkout byte hash');return hits[0]
    outcomes={}
    for label,major in (('powershell',5),('pwsh',7)):
        z=archives[label]
        need(z['source.txt'].decode('utf-8-sig').strip()==SOURCE,'shell checkout source')
        parts={}
        for name,baseline in (('snapshot',False),('snapshot-prior',True)):
            report=v.obj(z[name+'.json'])
            inst=matched(prior if baseline else files['scripts/Install-QbrainMemory.ps1'],report['installer_sha256'])
            test=matched(files['.ci/test_installer_snapshot.ps1'],report['test_sha256'])
            parts[name]=snapshot.validate(report,inst,test,exe,SOURCE,major,baseline)
            lines=z[name+'.log'].decode('utf-8-sig').splitlines()
            for row in report['cases']:
                prefix=('PASS ' if row['passed'] else 'FAIL ')+row['name']
                need(sum(line==prefix or line.startswith(prefix+': ') for line in lines)==1,'snapshot log label')
        for name,baseline in (('recovery',False),('baseline',True)):
            report=v.obj(z[name+'.json'])
            raw=product['scripts/Install-QbrainMemory.ps1'] if baseline else files['scripts/Install-QbrainMemory.ps1']
            inst=matched(raw,report['installer_sha256'])
            need(int(report['powershell'].split('.')[0])==major,'recovery shell')
            parts[name]=recovery.validate(report,inst,exe,baseline)
            log=z[name+'.log'].decode('utf-8-sig')
            for row in report['cases']:
                prefix=('PASS ' if row['passed'] else 'FAIL ')+row['name']
                need(sum(line==prefix or line.startswith(prefix+': ') for line in log.splitlines())==1,'recovery log label')
        for name,count in (('test_install_hooks',69),('test_install_consent',16),('test_windows_transport',8)):
            log=z[name+'.log'].decode('utf-8-sig')
            hits=re.findall(r'^PASS (\d+) :',log,re.M)
            need(list(map(int,hits))==list(range(1,count+1)), 'original suite sequence '+name)
            parts[name]={'checks':count}
        for name,validator in install_validators.items():
            report=v.obj(z[name+'.json'])
            inst=matched(files['scripts/Install-QbrainMemory.ps1'],report['installer_sha256'])
            test=matched(files['.ci/'+name+'.ps1'],report['script_sha256'])
            parts[name]=validator.validate_install(report,source_commit=SOURCE,binary_sha256=EXE,
                script_sha256=sha(test),installer_sha256=sha(inst),shell_major=major)
        for name in ('snapshot-check-tests.log','snapshot-check-tests-optimized.log'):
            log=z[name].decode('utf-8-sig')
            need('Ran 5 tests' in log and '\nOK' in log and '\nFAILED' not in log,'report checker suite')
        outcomes[label]=parts
    groups=native.verified_groups(files['tests/test_main.cpp'].decode(),archives['full-native']['native.log'].decode('utf-8-sig'),60)
    need(archives['full-native']['source.txt'].decode('utf-8-sig').strip()==SOURCE,'native checkout')
    need('BUILD_OK' in archives['full-native']['native.log'].decode('utf-8-sig'),'fresh production build marker')
    need(archives['full-native']['native-groups.log'].decode('utf-8-sig').strip()=='60','native log validator receipt')
    out={'schema':'qbrain-n47p-readback-v1','source_commit':SOURCE,'tree':TREE,'source_files':len(files),
         'run_id':RUN,'metadata_sha256':sha(a.metadata.read_bytes()),'artifacts':meta['artifacts'],
         'native_registered_groups':groups,'native_pg_skipped':'SKIP-PG' in archives['full-native']['native.log'].decode('utf-8-sig'),
         'shells':outcomes,'new_product_execution':False,'limits':['Offline pins supplied from connector, not online authentication','Temporary test filesystem assertions were executed by CI; not observed after deletion','Not real client acceptance or cross-file atomicity']}
    a.report.write_text(json.dumps(out,indent=2)+'\n')
    print('Readback PASS:',SOURCE,len(files),'source files;',len(groups),'native groups')

if __name__=='__main__': main()
