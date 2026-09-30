"""Verify combined ancestry, exact preserved modules and both native build closures."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = 'e0a27f829d970c24ed8c566023ada0911c0042b3'
HEADS = ['848ef980200b40101a1908fddfc0d829abc77d8d',
         'd57e6b32398fca4e59d80dcfab7c5af119dde2be',
         '1132c97fac1964f84eb593e91ace5bc774a3c98f']
PARENT = '0e3c12390ee0f7c2bd8ee9881b6630f4346038fd'
EXCLUDED = ['4fb5f7bcc4d5871b7eef409963806ba58b486ae1',
            '18abbe94dff60f85298b2743efc02839f869cd77',
            '8394e83aac484bf6c31fad421162d258fb8d2587',
            'd54308d61bc894f540885b9b317b899c560e58d2']

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def need(ok, message):
    if not ok:
        raise ValueError(message)

def quoted_array(text, name):
    match = re.search(r'\$' + re.escape(name) + r'\s*=\s*@\((.*?)\)', text, re.S)
    need(match is not None, 'missing static source array: ' + name)
    return re.findall(r'"([^"\r\n]+)"', match[1])

def main():
    ancestry = set(git('rev-list', 'HEAD').decode().splitlines())
    need(all(s in ancestry for s in [BASE, PARENT, *HEADS]), 'accepted head missing from genuine ancestry')
    need(not ancestry.intersection(EXCLUDED), 'excluded unique candidate is an ancestor')
    need(subprocess.run(['git', 'merge-base', '--is-ancestor', PARENT, HEADS[-1]], cwd=ROOT).returncode == 0,
         'runtime ancestor is not contained in logical candidate')
    inherited = {}
    checkout_conversions = []
    def same_checkout(path, raw):
        actual = (ROOT/path).read_bytes()
        if actual == raw:
            return True
        if b'\r\n' not in raw and actual == raw.replace(b'\n', b'\r\n'):
            checkout_conversions.append(path)
            return True
        return False
    for sha in HEADS:
        for path in git('diff', '--name-only', BASE, sha).decode().splitlines():
            blob = git('rev-parse', sha + ':' + path).decode().strip()
            need(path not in inherited or inherited[path] == blob, 'accepted modules overlap differently: ' + path)
            inherited[path] = blob
            need(same_checkout(path, git('cat-file', 'blob', blob)), 'inherited candidate bytes changed: ' + path)
    protected = ['CMakeLists.txt', 'scripts/build-cl.ps1', 'scripts/build-tests-cl.ps1',
                 'tests/test_main.cpp', '.ci/run_n48i_checks.py', '.ci/run_n48e_checks.py',
                 '.ci/run_n48d_regressions.py', '.ci/validate_native_log.py']
    for path in protected:
        need(same_checkout(path, git('show', BASE + ':' + path)), 'original gate changed: ' + path)
    additive = {'.ci/verified_integration_targets.cmake', '.ci/check_n49a_sources.py',
        '.ci/build_n49a_direct_tests.ps1', '.ci/run_n49a_process.py', '.ci/test_n49a_wire.py',
        '.github/workflows/n49a-integration.yml', 'tests/test_verified_integration.cpp',
        'docs/nodes/N49A-PLAN.md', 'docs/nodes/N49A-PLAN-AUDIT.md',
        'docs/nodes/N49A-LOCAL-RESULTS.md', 'docs/nodes/N49A-HARD-AUDIT.md'}
    changed = set(git('diff', '--name-only', BASE, 'HEAD').decode().splitlines())
    need(not (changed - set(inherited) - additive), 'unexpected source path changed')
    original = set(git('ls-tree', '-r', '--name-only', BASE).decode().splitlines())
    need(not additive.intersection(original), 'additive paths unexpectedly replace baseline files')
    cmake = (ROOT/'CMakeLists.txt').read_text()
    direct = (ROOT/'scripts/build-cl.ps1').read_text()
    tests = (ROOT/'scripts/build-tests-cl.ps1').read_text()
    sources = quoted_array(direct, 'productionSources')
    normalized = [s.replace('\\', '/') for s in sources]
    need(len(normalized) == len(set(normalized)), 'duplicate direct source')
    cmake_sources = set(re.findall(r'src/qbrain/[\w/]+\.cpp', cmake))
    need(set(normalized) == cmake_sources, 'CMake/direct production source mismatch')
    names = [Path(s).stem for s in normalized]
    need(len(names) == len(set(names)), 'direct object basename collision')
    production_objects = quoted_array(direct, 'prodObjNames')
    test_objects = quoted_array(tests, 'prodObjs')
    need(set(production_objects) == set(names) and len(production_objects) == len(names), 'production object omission')
    need(set(test_objects) == (set(names) - {'app', 'main'}) | {'sqlite3'}, 'canonical test object omission')
    canonical = re.search(r'add_executable\(qbrain_tests\s+(.*?)\)', cmake, re.S)
    need(canonical is not None, 'canonical CMake test source list missing')
    cmake_tests = set(re.findall(r'tests/[\w/]+\.cpp', canonical[1]))
    direct_tests = [s.replace('\\', '/') for s in quoted_array(tests, 'defaultTestSources')]
    need(set(direct_tests) == cmake_tests and len(direct_tests) == len(cmake_tests), 'canonical test source mismatch')
    registry = (ROOT/'tests/test_main.cpp').read_text()
    groups = re.findall(r'\{"([^"\r\n]+)",\s*test_\w+\}', registry)
    need(len(groups) == len(set(groups)) == 60, 'original 60 groups changed')
    report = dict(schema='qbrain-n49a-source-closure-v1', passed=True,
        head=git('rev-parse', 'HEAD').decode().strip(), tree=git('rev-parse', 'HEAD^{tree}').decode().strip(),
        baseline=BASE, accepted_heads=HEADS, runtime_ancestor=PARENT,
        excluded_unique_candidates=EXCLUDED, inherited_files=len(inherited),
        exact_lf_to_crlf_checkout_conversions=checkout_conversions,
        production_sources=sorted(normalized), production_object_count=len(production_objects),
        test_object_count=len(test_objects), canonical_test_sources=len(cmake_tests), registered_groups=len(groups),
        protected_sha256={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in protected})
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
