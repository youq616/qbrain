"""Exact immutable input union and native build closure for N49C."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = 'docs/nodes/n49c-evidence/INPUT-INVENTORY.json'
PIN = '5e0e87d28d2acb2a2409682b9d9618fc2a6bf43bba2b2c2392f7a6ba4ba40b0e'
PARENTS = ['f5331d174b6dfb853fd5450c78a25ae2754681da', 'd54308d61bc894f540885b9b317b899c560e58d2', '8394e83aac484bf6c31fad421162d258fb8d2587']
EXCLUDED = {'4fb5f7bcc4d5871b7eef409963806ba58b486ae1', '18abbe94dff60f85298b2743efc02839f869cd77'}
ADDITIVE = {'.ci/check_n49c_sources.py', '.ci/test_n49c_source_contract.py',
 '.ci/client_retrieval_integration_targets.cmake', '.ci/build_n49c_direct_tests.ps1',
 '.ci/test_n49c_process.py', '.ci/run_n49c_installers.ps1',
 '.github/workflows/n49c-integration.yml', 'tests/test_client_retrieval_integration.cpp',
 'docs/nodes/N49C-PLAN.md', 'docs/nodes/N49C-PLAN-AUDIT.md',
 'docs/nodes/N49C-LOCAL-RESULTS.md', 'docs/nodes/N49C-HARD-AUDIT.md', INVENTORY,
 'docs/integration/CLIENT-RETRIEVAL-CANDIDATE.zh-CN.md'}

def need(ok, message):
    if not ok:
        raise ValueError(message)

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

BLOCKED_ENV = re.compile(r'^(QBRAIN|PG|CURSOR|OPENAI|ANTHROPIC|GH_TOKEN|GITHUB_TOKEN|AWS_|AZURE_|GOOGLE_|GCP_|ZHIPU|GEMINI|COHERE|MISTRAL|DEEPSEEK|HF_|HUGGINGFACE|OPENROUTER|GIT_CONFIG_)|(?:^|_)(?:API_KEY|TOKEN|SECRET|PASSWORD|PASSWD|DSN|DATABASE_URL)(?:_|$)', re.I)

def clean_environment(source, home):
    value={k:v for k,v in source.items() if not BLOCKED_ENV.search(k)}
    for key in ('HOME','USERPROFILE','APPDATA','LOCALAPPDATA','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME'):
        value[key]=str(home)
    value.update(PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_SYSTEM=os.devnull)
    return value

def run_clean(argv, environment=None):
    need(bool(argv),'clean execution command required')
    with tempfile.TemporaryDirectory(prefix='n49c-clean-home-') as home:
        return subprocess.run(argv,env=clean_environment(os.environ if environment is None else environment,home)).returncode

def verify_frozen_checkout(repository, expected_head, expected_tree):
    def read(*args):return subprocess.check_output(['git',*args],cwd=repository)
    failures=[]
    head=read('rev-parse','HEAD').decode().strip();tree=read('rev-parse','HEAD^{tree}').decode().strip()
    if head!=expected_head:failures.append('frozen HEAD changed')
    if tree!=expected_tree:failures.append('frozen tree changed')
    staged=read('diff','--cached','--raw').decode();unstaged=read('diff','--raw').decode()
    if staged:failures.append('staged tracked changes')
    if unstaged:failures.append('unstaged tracked changes')
    conversions=[]
    # Always inspect the expected immutable tree, never a moved HEAD's definition.
    for row in read('ls-tree','-r','-z',expected_head).split(b'\0'):
        if not row:continue
        meta,path=row.split(b'\t',1);mode,kind,sha=meta.decode().split();path=path.decode()
        if kind!='blob':failures.append('non-blob tracked object: '+path);continue
        canonical=read('cat-file','blob',sha)
        try:actual=(Path(repository)/path).read_bytes()
        except OSError:failures.append('unreadable tracked file: '+path);continue
        if actual==canonical:continue
        if b'\r\n' not in canonical and actual==canonical.replace(b'\n',b'\r\n'):conversions.append(path)
        else:failures.append('tracked byte mismatch: '+path)
    return dict(passed=not failures,expected_head=expected_head,expected_tree=expected_tree,
        actual_head=head,actual_tree=tree,staged_diff=staged,unstaged_diff=unstaged,
        checkout_conversions=conversions,failures=failures)

def contract(raw):
    need(hashlib.sha256(raw).hexdigest() == PIN, 'unapproved inventory digest')
    data = json.loads(raw)
    expected = {r['path']: (r['mode'], r['sha']) for r in data['baseline_inventory']}
    for key in ('PR68', 'PR67'):
        for r in data['module_deltas_from_e0a'][key]:
            expected[r['path']] = (r['mode'], r['sha'])
    need(len(expected) == 1622, 'wrong inherited union count')
    need(not ADDITIVE.intersection(expected), 'additive file replaces inherited input')
    return data, expected

def validate_inventory(expected, actual):
    need(set(actual) == set(expected) | ADDITIVE, 'missing or unexpected tracked path')
    for path, record in expected.items():
        need(actual[path] == record, 'inherited blob/mode changed: ' + path)
    need(all(actual[p][0] == '100644' for p in ADDITIVE), 'unexpected additive mode')

def array(text, name):
    m = re.search(r'\$'+re.escape(name)+r'\s*=\s*@\((.*?)\)', text, re.S)
    need(m is not None, 'missing source array: '+name)
    return re.findall(r'"([^"\r\n]+)"', m[1])

def main(precommit=False):
    prefix = ':' if precommit else 'HEAD:'
    raw = git('show', prefix+INVENTORY)
    data, expected = contract(raw)
    actual = {}
    if precommit:
        for row in git('ls-files', '--stage', '-z').split(b'\0'):
            if not row: continue
            meta, path = row.split(b'\t', 1)
            mode, sha, stage = meta.decode().split()
            need(stage == '0', 'unmerged index entry')
            actual[path.decode()] = (mode, sha)
        need(git('rev-parse', 'HEAD').decode().strip() == PARENTS[0], 'wrong precommit first parent')
        merge = Path(git('rev-parse', '--git-path', 'MERGE_HEAD').decode().strip())
        if not merge.is_absolute(): merge = ROOT/merge
        need(merge.read_text().splitlines() == PARENTS[1:], 'wrong pending merge parents')
        ancestry = set().union(*(set(git('rev-list', s).decode().splitlines()) for s in PARENTS))
    else:
        for row in git('ls-tree', '-r', '-z', 'HEAD').split(b'\0'):
            if not row: continue
            meta, path = row.split(b'\t', 1)
            mode, kind, sha = meta.decode().split()
            need(kind == 'blob', 'unsupported tracked object')
            actual[path.decode()] = (mode, sha)
        ancestry = set(git('rev-list', 'HEAD').decode().splitlines())
        # Find the genuine initial integration commit without assuming a docs successor qualifies.
        rows = git('rev-list', '--parents', 'HEAD').decode().splitlines()
        need(any(r.split()[1:] == PARENTS for r in rows), 'ordered integration parents absent')
    need(set(PARENTS) <= ancestry and not (ancestry & EXCLUDED), 'accepted/excluded ancestry mismatch')
    need(git('rev-parse', '--is-shallow-repository').strip() == b'false', 'incomplete ancestry')
    for key in ('N49A', 'PR68', 'PR67'):
        source = data['sources'][key]
        need(git('rev-parse', source['commit']+'^{tree}').decode().strip() == source['tree'], 'input tree mismatch')
    validate_inventory(expected, actual)
    conversions = []
    for path, (_, sha) in actual.items():
        canonical = git('cat-file', 'blob', sha)
        checked = (ROOT/path).read_bytes()
        if checked != canonical:
            need(b'\r\n' not in canonical and checked == canonical.replace(b'\n', b'\r\n'), 'checkout mismatch: '+path)
            conversions.append(path)
    cmake = (ROOT/'CMakeLists.txt').read_text()
    direct = (ROOT/'scripts/build-cl.ps1').read_text()
    tests = (ROOT/'scripts/build-tests-cl.ps1').read_text()
    sources = [s.replace('\\', '/') for s in array(direct, 'productionSources')]
    cmake_sources = set(re.findall(r'src/qbrain/[\w/]+\.cpp', cmake))
    need(len(sources) == len(set(sources)) == 52 and set(sources) == cmake_sources, 'production source closure')
    names = [Path(s).stem for s in sources]
    need(len(names) == len(set(names)), 'object basename collision')
    prod = array(direct, 'prodObjNames'); test = array(tests, 'prodObjs')
    need(len(prod) == len(set(prod)) == 52 and set(prod) == set(names), 'production link closure')
    need(len(test) == len(set(test)) == 51 and set(test) == (set(names)-{'app','main'})|{'sqlite3'}, 'test link closure')
    block = re.search(r'add_executable\(qbrain_tests\s+(.*?)\)', cmake, re.S)
    need(block is not None, 'canonical tests missing')
    cs = set(re.findall(r'tests/[\w/]+\.cpp', block[1]))
    ds = [s.replace('\\','/') for s in array(tests,'defaultTestSources')]
    need(len(ds) == len(set(ds)) == 59 and set(ds) == cs, 'canonical test source closure')
    groups = re.findall(r'\{"([^"\r\n]+)",\s*test_\w+\}', (ROOT/'tests/test_main.cpp').read_text())
    need(len(groups) == len(set(groups)) == 60, 'original60 registry changed')
    print(json.dumps(dict(passed=True, phase='precommit' if precommit else 'frozen-source',
      head=git('rev-parse','HEAD').decode().strip(), inventory_sha256=PIN,
      inherited_files=len(expected), additive_files=len(ADDITIVE), production_sources=52,
      canonical_test_objects=51, canonical_test_sources=59, original_groups=60,
      checkout_conversions=conversions), indent=2))

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--precommit',action='store_true')
    p.add_argument('--repository',type=Path);p.add_argument('--final',action='store_true')
    p.add_argument('--expected-head');p.add_argument('--expected-tree');p.add_argument('--run-clean',action='store_true')
    p.add_argument('command',nargs=argparse.REMAINDER)
    args=p.parse_args()
    if args.repository:ROOT=args.repository.resolve(strict=True)
    if args.run_clean:
        command=args.command[1:] if args.command[:1]==['--'] else args.command
        raise SystemExit(run_clean(command))
    if args.final:
        need(bool(args.expected_head) and bool(args.expected_tree),'frozen source pins required')
        result=verify_frozen_checkout(ROOT,args.expected_head,args.expected_tree)
        print(json.dumps(result,indent=2));raise SystemExit(0 if result['passed'] else 1)
    main(args.precommit)
