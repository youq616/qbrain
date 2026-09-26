"""Execute the extracted N48K bundle, then bind qualification to unchanged ZIP bytes.

Windows only. All native work uses disposable homes, synthetic tasks, and explicit
installer test projects. No real signed-in client, provider or quality claim.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import package_n48k as p


def environments(original: dict, home: str):
    # Build discovery needs the runner's real Visual Studio profile. Runtime
    # probes remain isolated; the inherited driver isolates its own test data.
    toolchain = {k:v for k,v in original.items() if not k.upper().startswith(
        ('QBRAIN','OPENAI','ANTHROPIC','GH_TOKEN','GITHUB_TOKEN'))}
    toolchain.update(PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    runtime = {**toolchain, **dict.fromkeys(('HOME','USERPROFILE','APPDATA','LOCALAPPDATA'),home)}
    return toolchain, runtime


def execute(source: Path, bundle: Path, package: Path, old: Path, output: Path):
    p.z.need(os.name == 'nt', 'native Windows required')
    source, bundle, package, old = [x.resolve(strict=True) for x in (source, bundle, package, old)]
    output = output.absolute()
    output.mkdir(exist_ok=False)
    logs = output/'logs'; logs.mkdir()
    original = p.read(package, p.z.MAX_ARCHIVE)
    original_hash = p.z.sha(original)
    wanted = p.z.archive_files(original)
    p.z.need(wanted['MANIFEST.json'] == p.z.encoded(p.z.obj(wanted['MANIFEST.json'])), 'canonical manifest')
    p.z.need(p.z.obj(wanted['MANIFEST.json'])['product_source'] == p.SOURCE, 'product identity')
    rows = []

    def inventory():
        names = sorted(x.relative_to(bundle).as_posix() for x in bundle.rglob('*') if not x.is_dir())
        p.z.need(names == sorted(wanted), 'extracted inventory')
        for name, raw in wanted.items():
            p.z.need(p.read(bundle/name) == raw, 'extracted bytes changed')

    inventory()
    exe = bundle/'qbrain.exe'
    with tempfile.TemporaryDirectory(prefix='qbrain-n48k-home-') as home:
        build_env, env = environments(os.environ,home)

        def run(name, command, *, cwd=bundle, data=None, code=0, environment=None):
            argv = list(map(str, command))
            row = dict(name=name, argv=argv, status='started', environment_scope='toolchain_profile' if environment is not None else 'isolated_runtime'); rows.append(row)
            (output/'driver.json').write_bytes(p.z.encoded(dict(package_sha256=original_hash, steps=rows)))
            result = subprocess.run(argv, input=data, capture_output=True, cwd=cwd, env=env if environment is None else environment, timeout=1800)
            (logs/(name+'.stdout')).write_bytes(result.stdout)
            (logs/(name+'.stderr')).write_bytes(result.stderr)
            if data is not None: (logs/(name+'.stdin')).write_bytes(data)
            row.update(status='completed', exit=result.returncode, expected_exit=code,
                       stdout_sha256=p.z.sha(result.stdout), stderr_sha256=p.z.sha(result.stderr))
            (output/'driver.json').write_bytes(p.z.encoded(dict(package_sha256=original_hash, steps=rows)))
            p.z.need(result.returncode == code, 'bundle command failed: '+name)
            return result

        def suite(name, args, count):
            result = run(name, args)
            text = (result.stdout+result.stderr).decode('utf-8-sig')
            p.z.need(re.search(r'Ran '+str(count)+r' tests in ', text) is not None and
                     re.search(r'\nOK\s*$', text) is not None, 'test coverage: '+name)

        for mode in ('normal','optimized'):
            py = [sys.executable] + (['-O'] if mode == 'optimized' else [])
            suite('bridge-'+mode, py+[bundle/'tools/acceptance/test_model_cost.py','--binary',exe,
                  '--evidence',output/('bridge-'+mode)],27)
            test = py+['-m','unittest','-v','test_memory_tasks','test_memory_metrics','test_model_ab','test_model_projection','test_model_framing']
            result = run('acceptance-'+mode,test,cwd=bundle/'tools/acceptance')
            text = (result.stdout+result.stderr).decode('utf-8-sig')
            p.z.need(re.search(r'Ran 48 tests in ',text) is not None and re.search(r'\nOK\s*$',text), 'old acceptance inventory')

        # Exercise files as delivered, not copies in the source checkout.
        for name in p.EXAMPLES:
            if name == 'model-execution-rates.synthetic': continue
            action = 'import-stream' if name.startswith('stream-') else ('compare' if name.startswith('compare-') else 'import')
            error = {'stream-rejected-truncated':'stream_missing_terminal', 'compare-rejected-task':'comparison_task_mismatch'}.get(name)
            result = run(name, [exe,'cost',action],data=p.read(bundle/('examples/cost/'+name+'.json')),code=2 if error else 0)
            p.z.need(not result.stderr, 'example stderr')
            report = p.z.obj(result.stdout)
            if error:
                p.z.need(report == {'error':{'code':error}}, 'example rejection')
            elif action == 'compare':
                delta = {'compare-basic':'-0.000050000000', 'compare-shared-overhead':'0.000010000000',
                         'compare-failed-retry':'0.000070000000', 'compare-zero-baseline':'0.000001000000', 'compare-unknown':None}[name]
                p.z.need(report['change']['candidate_minus_baseline'] == delta, 'example exact delta')
            elif action == 'import-stream':
                p.z.need(report['cost_report']['summary']['total_estimate'] == (None if name=='stream-unknown-cache' else '0.000133000000'), 'example exact cost')
            else:
                p.z.need(report['schema'] == 'qbrain-usage-import-report-v1', 'import schema')

        installer = bundle/'scripts/Install-QbrainMemory.ps1'
        for shell in ('powershell','pwsh'):
            prefix = [shell,'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File']
            for test in ('test_installer_snapshot','test_installer_recovery'):
                report = output/(test+'-'+shell+'.json')
                run(test+'-'+shell,prefix+[source/'.ci'/(test+'.ps1'),'-Binary',exe,'-Installer',installer,'-Report',report])
            run('upgrade-'+shell,prefix+[Path(__file__).with_name('test_n48k_upgrade.ps1'),
                '-OldPackage',old,'-NewPackage',package,'-ExpectedNewSha256',original_hash,
                '-Report',output/('upgrade-'+shell+'.json')])
            record = p.z.obj(p.read(output/('upgrade-'+shell+'.json')))
            p.z.need(record['result']=='PASS' and record['shell_major']==(5 if shell=='powershell' else 7)
                     and record['new_zip_sha256']==original_hash and len(record['checks']) >= 50
                     and all(row['passed'] is True for row in record['checks']), 'upgrade report')
        # The unchanged driver compiles standalone tests before running its own
        # isolated fixtures. Do not hide Visual Studio's profile from CMake.
        run('retained-native', [sys.executable,source/'.ci/run_n48i_checks.py','--binary',exe,
            '--baseline',output.parent/'baseline/qbrain.exe','--output',output/'retained'],environment=build_env)
        inventory()
        p.z.need(p.read(package,p.z.MAX_ARCHIVE)==original,'ZIP changed during qualification')
    result = dict(schema='qbrain-n48k-bundle-qualification-v1', result='PASS',
        package_sha256=original_hash, package_bytes=len(original), members=len(wanted),
        binary_sha256=p.z.sha(wanted['qbrain.exe']), product_source=p.SOURCE, product_tree=p.TREE,
        steps=len(rows), native_platform='windows', shell_majors=[5,7], package_unchanged=True,
        extracted_inventory_unchanged=True, real_client_verified=False, real_model_quality_verified=False,
        signed=False, stable_v1=False, issue40_closed=False)
    (output/'QUALIFICATION.json').write_bytes(p.z.encoded(result))
    return result


if __name__ == '__main__':
    a = argparse.ArgumentParser(description=__doc__)
    for name in ('source','bundle','package','old','output'): a.add_argument('--'+name,type=Path,required=True)
    v = a.parse_args()
    print(p.z.encoded(execute(v.source,v.bundle,v.package,v.old,v.output)).decode(),end='')
