"""N48I fixed-binary qualification plus unchanged cost/stream/application gates.

This orchestrator never edits old tests. A failed command stops the run, while
its exit, exact command and raw log remain available in driver.json and logs/.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    binary, baseline = args.binary.resolve(strict=True), args.baseline.resolve(strict=True)
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    (output/'logs').mkdir(); direct = output/'direct'; direct.mkdir()
    root = Path(__file__).resolve().parents[1]
    suffix = '.exe' if os.name == 'nt' else ''
    records = []
    def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
    identity = dict(binary_sha256=digest(binary), baseline_sha256=digest(baseline), script_sha256=digest(Path(__file__)), platform=os.name)
    env = {k:v for k,v in os.environ.items() if not k.upper().startswith(('QBRAIN','OPENAI','ANTHROPIC','OPENCODE'))}
    env.update(PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    def run(name, command):
        command = list(map(str, command))
        row = dict(name=name, argv=command, status='started'); records.append(row)
        (output/'driver.json').write_text(json.dumps({**identity,'steps':records},indent=2), encoding='utf-8')
        path = output/'logs'/(name+'.log')
        with path.open('wb') as log:
            result = subprocess.run(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=1200)
        row.update(status='completed', exit=result.returncode, log_sha256=digest(path))
        (output/'driver.json').write_text(json.dumps({**identity,'steps':records},indent=2), encoding='utf-8')
        if result.returncode: raise RuntimeError('Qualification failed: '+name)
    projects = {
        'cost_comparison': ['qbrain_cost_comparison_tests'],
        'cost': ['qbrain_cost_tests'],
        'usage_import': ['qbrain_usage_import_tests'],
        'stream_import': ['qbrain_stream_import_tests','qbrain_stream_history_tests'],
        'opencode': ['opencode_config_tests','opencode_audit_tests','opencode_reconcile_tests','opencode_write_races_tests'],
        'mcp_probe': ['qbrain_mcp_probe_peer','qbrain_mcp_probe_tests'],
    }
    for project, targets in projects.items():
        build = root/'build'/'n48i'/project
        run(project+'-configure', ['cmake','-S',root/'tests'/project,'-B',build,'-DCMAKE_BUILD_TYPE=Release'])
        run(project+'-build', ['cmake','--build',build,'--config','Release','--parallel','2'])
        run(project+'-ctest', ['ctest','--test-dir',build,'-C','Release','--output-on-failure'])
        bindir = build/'Release' if os.name == 'nt' else build
        for name in targets:
            shutil.copyfile(bindir/(name+suffix), direct/(name+suffix))
            (direct/(name+suffix)).chmod(0o755)
            if name not in ('qbrain_mcp_probe_peer','qbrain_mcp_probe_tests'):
                run(name+'-direct', [direct/(name+suffix)])
    for mode in ('normal','optimized'):
        py = [sys.executable] + (['-O'] if mode == 'optimized' else [])
        for name, script in [('comparison','test_cost_comparison'),('stream-history','test_stream_usage_history')]:
            dest = output/(name+'-'+mode)
            run(name+'-'+mode, py+[root/'.ci'/(script+'.py'),'--binary',binary,'--output',dest])
            run(name+'-'+mode+'-readback', py+[root/'.ci'/(script+'.py'),'--binary',binary,'--output',dest,'--negatives'])
        for name, test, checker in [('cost','test_token_cost','check_token_cost'),('import','test_provider_usage','check_provider_usage'),('stream','test_stream_usage','check_stream_usage')]:
            dest = output/(name+'-'+mode)
            run(name+'-'+mode, py+[root/'.ci'/(test+'.py'),'--binary',binary,'--output',dest])
            run(name+'-'+mode+'-readback', py+[root/'.ci'/(checker+'.py'),'--directory',dest,'--binary',binary,'--test',root/'.ci'/(test+'.py'),'--negatives'])
        dest = output/('stream-review-'+mode)
        run('stream-review-'+mode, py+[root/'.ci/review_stream_usage.py','--binary',binary,'--output',dest])
        run('stream-review-'+mode+'-readback', py+[root/'.ci/review_stream_usage.py','--binary',binary,'--output',dest,'--readback'])
    run('lifecycle', [sys.executable,root/'.ci/run_n48e_checks.py','--binary',binary,'--direct-dir',direct,'--output',output/'lifecycle'])
    run('retained', [sys.executable,root/'.ci/run_n48d_regressions.py','--binary',binary,'--baseline',baseline,'--output',output/'retained'])
    peer = direct/('qbrain_mcp_probe_peer'+suffix)
    run('mcp', [sys.executable,root/'.ci/test_mcp_probe.py','--binary',binary,'--peer',peer,'--output',output/'mcp'])
    run('mcp-readback', [sys.executable,root/'.ci/check_mcp_probe.py','--report',output/'mcp/report.json','--binary',binary,'--peer',peer,'--test',root/'.ci/test_mcp_probe.py','--negatives'])
    if digest(binary) != identity['binary_sha256'] or digest(baseline) != identity['baseline_sha256']:
        raise RuntimeError('Binary changed during qualification')
    print(json.dumps(dict(result='PASS',steps=len(records),**identity)))


if __name__ == '__main__':
    main()
