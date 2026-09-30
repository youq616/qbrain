"""Read-only independent review of the fixed N48S Windows candidate evidence.

No producer imports, SQL, native execution or network. Source/ZIP hashes establish
identity, not authentic model use. Expected trees and package identity are fixed
from separately retrieved GitHub records; this is not a generic release signer.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

PRODUCT_COMMIT = 'e0a27f829d970c24ed8c566023ada0911c0042b3'
PRODUCT_TREE = '534c86deabf43e30d3b2533cd3bf1f0728cf8400'
CANDIDATE = '9f9c34017cbc3c2ab787f145059e847f7b2cb8c3'
CANDIDATE_TREE = 'd904b2401c2dbe671f4257ffb49ce2da72e2ac57'
PACKAGE = 'qbrain-windows-x64-n48s-candidate.zip'
PACKAGE_SHA = 'a326ed8e031903935e860a37b8a44f5eaa170a0c7becc697afe23c9b609c332c'
OLD_SHA = 'c517582c1ea0e0795e881155edd4d34288e3a002dc3bc7657dafcb96a1eb8b4d'
BINARY_SHA = 'c65f3e8e9e08d7ccf43c245193829af9334f0dfa19f00c447a713a0a243d879d'
CAP = 128 * 1024 * 1024

class Rejected(ValueError):
    pass

def need(value, reason):
    if not value:
        raise Rejected(reason)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()

def same(left, right, label):
    need(canonical(left) == canonical(right), label)  # JSON bool is not integer zero/one.

def decode(raw):
    need(len(raw) <= 16 * 1024 * 1024, 'json_limit')
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    def invalid(_):
        raise Rejected('nonfinite_json')
    try:
        value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs, parse_constant=invalid)
        canonical(value)  # rejects nonfinite exponent values and invalid Unicode
        return value
    except (UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise Rejected('invalid_json') from exc

class Reader:
    def __init__(self, root):
        self.root = Path(root).absolute()
        self.cache = {}
        self.overrides = {}  # Only used by the independent mutation tests.

    def raw(self, name):
        p = PurePosixPath(name)
        need(not p.is_absolute() and '..' not in p.parts and '\\' not in name, 'unsafe_relative_path')
        if name in self.overrides:
            return self.overrides[name]
        if name not in self.cache:
            path = self.root.joinpath(*p.parts)
            for part in (*reversed(path.parents), path):
                info = part.lstat()
                need(not stat.S_ISLNK(info.st_mode) and not (getattr(info, 'st_file_attributes', 0) & 0x400), 'link_input')
            need(path.is_file() and path.stat().st_size <= CAP, 'file_type_or_size')
            self.cache[name] = path.read_bytes()
        return self.cache[name]

    def obj(self, name):
        return decode(self.raw(name))

    def recheck(self):
        for name, raw in self.cache.items():
            path = self.root / name
            info = path.lstat()
            need(stat.S_ISREG(info.st_mode) and not (getattr(info, 'st_file_attributes', 0) & 0x400)
                 and path.read_bytes() == raw, 'evidence_changed_during_review')

def archive(raw):
    need(len(raw) <= CAP, 'archive_limit')
    files, modes = {}, {}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = set()
        total = 0
        for item in z.infolist():
            name = item.filename
            need(name not in names, 'duplicate_zip_member'); names.add(name)
            p = PurePosixPath(name)
            need(not p.is_absolute() and '..' not in p.parts and '\\' not in name and '\0' not in name, 'unsafe_zip_path')
            if item.is_dir():
                continue
            need((item.external_attr >> 16) & 0o170000 in (0, 0o100000), 'zip_file_type')
            need(not item.flag_bits & 1 and item.file_size <= CAP, 'zip_entry_limit')
            total += item.file_size; need(total <= 512 * 1024 * 1024, 'zip_total_limit')
            files[name] = z.read(item)
            modes[name] = '100755' if (item.external_attr >> 16) & 0o111 else '100644'
        return files, modes, z.comment

def git_hash(kind, raw):
    return hashlib.sha1(kind.encode() + b' ' + str(len(raw)).encode() + b'\0' + raw).digest()

def git_tree(files, modes):
    root = {}
    for name, raw in files.items():
        parts = name.split('/'); target = root
        for part in parts[:-1]:
            target = target.setdefault(part, {})
            need(type(target) is dict, 'tree_path_collision')
        need(parts[-1] not in target, 'tree_duplicate')
        target[parts[-1]] = (modes[name], git_hash('blob', raw))
    def node(tree):
        raw = b''
        for name, item in sorted(tree.items(), key=lambda x: (x[0] + ('/' if type(x[1]) is dict else '')).encode()):
            mode, h = ('40000', node(item)) if type(item) is dict else item
            raw += mode.encode() + b' ' + name.encode() + b'\0' + h
        return git_hash('tree', raw)
    return node(root).hex()

def source_match(actual, modes, canonical_files, canonical_modes):
    need(set(actual) == set(canonical_files) and modes == canonical_modes, 'source_inventory')
    converted = 0
    for name, expected in canonical_files.items():
        if actual[name] == expected:
            continue
        need(b'\r' not in expected and actual[name] == expected.replace(b'\n', b'\r\n'), 'source_bytes:' + name)
        converted += 1
    return converted

def pe_imports(raw):
    """Independent field reader for the supplied PE; not a full Windows loader."""
    def number(pos, width=4):
        need(0 <= pos <= len(raw) - width, 'pe_bounds')
        return int.from_bytes(raw[pos:pos+width], 'little')
    need(raw[:2] == b'MZ', 'pe_dos')
    pe = number(60); need(raw[pe:pe+4] == b'PE\0\0', 'pe_signature')
    need(number(pe+4, 2) == 0x8664 and number(pe+24, 2) == 0x20b, 'pe_architecture')
    count, optional = number(pe+6, 2), number(pe+20, 2)
    need(0 < count <= 96 and optional >= 240, 'pe_sections')
    section = pe + 24 + optional
    mapping = [(number(section+40*i+12), number(section+40*i+16), number(section+40*i+20)) for i in range(count)]
    def location(rva, size):
        found = [offset+rva-start for start, extent, offset in mapping if start <= rva and rva+size <= start+extent]
        need(len(found) == 1 and found[0] + size <= len(raw), 'pe_rva')
        return found[0]
    def table(index, width, field):
        d = pe+24+112+index*8; address, size = number(d), number(d+4)
        need(address and width <= size <= width*128 and size % width == 0, 'pe_directory')
        p = location(address, size); names = []
        for row in range(size//width):
            data = raw[p+row*width:p+(row+1)*width]
            if data == b'\0'*width:
                need(not any(raw[p+(row+1)*width:p+size]), 'pe_trailing')
                return sorted(names)
            if index == 13:
                need(number(p+row*width) == 1, 'pe_delay_attributes')
            nrva = number(p+row*width+field); n = location(nrva, 1)
            end = raw.find(b'\0', n, n+128)
            need(end > n and location(nrva, end-n+1) == n, 'pe_name')
            name = raw[n:end].decode('ascii').lower()
            need(re.fullmatch(r'[a-z0-9_-]+\.dll', name) and name not in names, 'pe_dll')
            names.append(name)
        raise Rejected('pe_no_terminator')
    return {'eager': table(1, 20, 12), 'delayed': table(13, 32, 4), 'machine': 'AMD64', 'format': 'PE32+',
            'scope': 'direct_import_tables_only', 'postgres_dependencies_bundled': False}

TOOLS = ('check_memory_task_run inspect_hook_context integration_model_ab memory_task_contract model_ab model_cost '
         'model_evaluation run_memory_tasks score_memory_tasks test_memory_metrics test_memory_tasks test_model_ab '
         'test_model_cost test_model_evaluation test_model_framing test_model_projection').split()
GUIDES = ('INSTALLER-RECOVERY TASK-EVALUATION MODEL-COMPARISON FACT-USAGE FACT-USAGE-AUDIT CASE-SENSITIVE-PATHS '
          'TRANSPORT-DIAGNOSTICS RECEIPT-INTEGRITY USAGE-BATCHES ISOLATED-MCP-CHECK OPENCODE-LIFECYCLE TOKEN-COST '
          'PROVIDER-USAGE-IMPORT STREAM-USAGE-IMPORT PAIRED-COST-COMPARISON MODEL-EXECUTION-COST MODEL-QUALITY-COST '
          'SQLITE-BACKUP SQLITE-CHECK POSTGRES-SESSION-MEMORY POSTGRES-LAYERED-CONTEXT POSTGRES-STRUCTURED-FACTS POSTGRES-HOOKS').split()
EXAMPLES = ('import-three-providers.synthetic stream-openai_chat stream-openai_responses stream-anthropic_messages '
            'stream-unknown-cache stream-rejected-truncated compare-basic compare-shared-overhead compare-failed-retry '
            'compare-unknown compare-rejected-task compare-zero-baseline model-execution-rates.synthetic').split()
PAYLOAD = {'LICENSE', 'THIRD-PARTY-NOTICES.md', 'scripts/Install-QbrainMemory.ps1', 'scripts/Invoke-QbrainJson.ps1',
           'examples/context/pg-context.synthetic.txt'} | {'tools/acceptance/'+n+'.py' for n in TOOLS} | {
           'docs/integration/'+n+'.zh-CN.md' for n in GUIDES} | {'examples/cost/'+n+'.json' for n in EXAMPLES}

def stages():
    names = ['system-only-init', 'system-only-cost']
    for mode in ('normal', 'optimized'):
        names += [x+'-'+mode for x in ('evaluation', 'cost-bridge', 'old-acceptance', 'sqlite_backup',
                  'sqlite_backup-verify', 'sqlite_check', 'sqlite_check-verify', 'postgres-hooks')]
    for shell in ('powershell', 'pwsh'):
        names += [x+'-'+shell for x in ('test_installer_snapshot', 'test_installer_recovery', 'upgrade', 'existing-receipts')]
    return names + ['retained55']

# This reader targets one archived run, not arbitrary CI runner layouts. These
# paths were read from artifact 11079172490 after matching its GitHub-published
# SHA256 a9234464dae34718308d2e5723e3b309b57e76bec02528e24435d9c3fd1c1e2c.
# Do not derive the executable, interpreter or expected arguments from the
# mutable driver record being checked. A new run needs separately reviewed pins.
WINDOWS_ROOT = r'D:\a\qbrain\qbrain'
WINDOWS_PYTHON = r'C:\hostedtoolcache\windows\Python\3.12.10\x64\python.exe'

def expected_commands():
    """Reconstruct the 27 argv contracts from the fixed qualification source.

    This intentionally duplicates the contract without importing/executing the
    producer. Exact list equality rejects unrelated launchers, wrong script roots,
    reordered/duplicate/extra flags, unbound destinations and altered -c payloads.
    """
    def path(relative):
        return WINDOWS_ROOT + '\\' + relative.replace('/', '\\')
    exe = path('under-test/qbrain.exe')
    bundle = 'under-test/'
    product = 'product/'
    output = 'evidence/qualification/'
    baseline = output + 'baseline/'
    commands = {'system-only-init': [exe, 'init', '--no-default', '--brain', 'n48s-system-only'],
                'system-only-cost': [exe, 'cost', 'compare']}
    for mode in ('normal', 'optimized'):
        py = [WINDOWS_PYTHON] + (['-O'] if mode == 'optimized' else [])
        for stage, script in [('evaluation', 'test_model_evaluation.py'),
                              ('cost-bridge', 'test_model_cost.py')]:
            name = stage + '-' + mode
            commands[name] = py + [path(bundle+'tools/acceptance/'+script), '--binary', exe,
                                   '--evidence', path(output+name)]
        commands['old-acceptance-'+mode] = py + ['-m', 'unittest', '-v', 'test_memory_tasks',
             'test_memory_metrics', 'test_model_ab', 'test_model_projection', 'test_model_framing']
        for test in ('sqlite_backup', 'sqlite_check'):
            args = py + [path(product+'.ci/test_'+test+'.py'), '--binary', exe,
                         '--output', path(output+test+'-'+mode)]
            commands[test+'-'+mode] = args
            commands[test+'-verify-'+mode] = args + ['--verify']
        commands['postgres-hooks-'+mode] = py + [path(product+'.ci/test_pg_hooks.py'),
             '--binary', exe, '--output', path(output+'postgres-hooks-'+mode)]
    preservation_code = (
        'import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);'
        'import test_n48k_existing_receipts as t;t.NEW_SHA=sys.argv[2];'
        'r=t.exercise(*[Path(x) for x in sys.argv[3:7]],sys.argv[7],Path(sys.argv[8]));'
        "print(t.encode({k:v for k,v in r.items() if k not in ('checks','calls')}).decode())")
    for shell in ('powershell', 'pwsh'):
        prefix = [shell, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File']
        for test in ('test_installer_snapshot', 'test_installer_recovery'):
            commands[test+'-'+shell] = prefix + [path(product+'.ci/'+test+'.ps1'), '-Binary',
                exe, '-Installer', path(bundle+'scripts/Install-QbrainMemory.ps1'),
                '-Report', path(output+test+'-'+shell+'.json')]
        commands['upgrade-'+shell] = prefix + [path(output+'test_n48s_upgrade.ps1'),
            '-OldPackage', path('evidence/old-n47x.zip'), '-NewPackage', path('evidence/one/'+PACKAGE),
            '-ExpectedNewSha256', PACKAGE_SHA, '-Report', path(output+'upgrade-'+shell+'.json')]
        commands['existing-receipts-'+shell] = [WINDOWS_PYTHON, '-c', preservation_code,
            path(product+'.ci'), PACKAGE_SHA, path(baseline+'qbrain.exe'), exe,
            path(baseline+'scripts/Install-QbrainMemory.ps1'),
            path(bundle+'scripts/Install-QbrainMemory.ps1'), shell,
            path(output+'existing-receipts-'+shell)]
    commands['retained55'] = [WINDOWS_PYTHON, path(product+'.ci/run_n48i_checks.py'),
        '--binary', exe, '--baseline', path(baseline+'qbrain.exe'), '--output', path(output+'retained')]
    same(list(commands), stages(), 'expected_command_inventory')
    return commands

def assert_checks(value, key, count):
    rows = value[key]
    need(type(rows) is list and len(rows) == count, 'check_inventory')
    need(all(type(r) is dict and set(r) == {'name', 'passed'} and type(r['name']) is str and r['passed'] is True for r in rows), 'check_failed_or_untyped')

def raw_commands(reader, relative, report, key, count):
    rows = report[key]; need(type(rows) is list and len(rows) == count, 'command_inventory')
    for index, row in enumerate(rows):
        need(type(row['exit']) is int, 'command_exit_type')
        need(type(row.get('expected_exit', 0)) is int and row['exit'] == row.get('expected_exit', 0), 'command_exit')
        need(set(row['hashes']) == {'stdin', 'stdout', 'stderr'}, 'stream_inventory')
        for ext, expected in row['hashes'].items():
            need(sha(reader.raw(f'{relative}/raw/{index:03d}.{ext}')) == expected, 'raw_stream_hash')

def review(reader, canonical_source):
    all_files, all_modes, comment = archive(canonical_source)
    need(comment.decode() == CANDIDATE and git_tree(all_files, all_modes) == CANDIDATE_TREE, 'candidate_tree')
    src, modes, comment = archive(reader.raw('source.zip'))
    need(comment.decode() == CANDIDATE and reader.raw('source.txt').decode('utf-8-sig').strip() == CANDIDATE, 'candidate_commit')
    source_crlf = source_match(src, modes, all_files, all_modes)
    prod, pmodes, pcomment = archive(reader.raw('product-source.zip'))
    need(set(prod) <= set(all_files) and pcomment.decode() == PRODUCT_COMMIT, 'product_source')
    canonical_product = {n: all_files[n] for n in prod}
    need(git_tree(canonical_product, pmodes) == PRODUCT_TREE, 'product_tree')
    product_crlf = source_match(prod, pmodes, canonical_product, {n: all_modes[n] for n in prod})
    raw = reader.raw('one/'+PACKAGE)
    need(sha(raw) == PACKAGE_SHA and raw == reader.raw('two/'+PACKAGE), 'package_identity_or_repeatability')
    payload, _, _ = archive(raw)
    need(set(payload) == PAYLOAD | {'qbrain.exe', 'MANIFEST.json', 'BUILD-PROVENANCE.json', 'START-HERE.zh-CN.md'}, 'package_membership')
    for name in PAYLOAD:
        expected = canonical_product[name]
        if name.endswith('.ps1'):
            need(b'\r' not in expected, 'script_encoding'); expected = expected.replace(b'\n', b'\r\n')
        need(payload[name] == expected, 'payload_source:'+name)
    need(payload['START-HERE.zh-CN.md'] == src['docs/integration/WINDOWS-CANDIDATE-N48S.zh-CN.md'], 'guide_source')
    binary = payload['qbrain.exe']; need(sha(binary) == BINARY_SHA, 'binary_identity')
    deps = pe_imports(binary)
    same(deps['eager'], ['kernel32.dll','ole32.dll','shell32.dll','winhttp.dll','ws2_32.dll'], 'eager_imports')
    same(deps['delayed'], ['libpq.dll'], 'delayed_imports')
    manifest = decode(payload['MANIFEST.json']); build = decode(payload['BUILD-PROVENANCE.json'])
    inventory = {n: {'bytes': len(v), 'sha256': sha(v)} for n, v in payload.items() if n != 'MANIFEST.json'}
    same(manifest, dict(schema='qbrain-n48s-package-v1', product_source=PRODUCT_COMMIT, product_tree=PRODUCT_TREE,
         files=inventory, binary_sha256=BINARY_SHA, dependencies=deps, signed=False, stable=False,
         status='BUILT_NOT_YET_ACCEPTED', real_client_consumption_verified=False, full_project_complete=False), 'manifest')
    registry = canonical_product['tests/test_main.cpp'].decode()
    groups = re.findall(r'\{"([^"\r\n]+)",\s*test_\w+\}', registry)
    log = reader.raw('native.log').decode('utf-8-sig')
    actual_groups = re.findall(r'^\[PASS\] (\w+)\s*$', log, re.MULTILINE)
    need(len(groups) == len(set(groups)) == 60 and Counter(actual_groups) == Counter(groups) and '[FAIL]' not in log and 'BUILD_OK' in log, 'native_registry')
    same(build, dict(schema='qbrain-n48s-build-v1', product_source=PRODUCT_COMMIT, product_tree=PRODUCT_TREE,
         binary_sha256=BINARY_SHA, native_log_sha256=sha(reader.raw('native.log')), native_groups=groups,
         dependencies=deps, compiler_reproducibility_verified=False), 'build_record')
    acceptance = reader.obj('qualification/ACCEPTANCE.json')
    same(acceptance, dict(schema='qbrain-n48s-acceptance-v1', result='PASS_BOUNDED_WINDOWS_CANDIDATE',
         package_sha256=PACKAGE_SHA, package_bytes=len(raw), binary_sha256=BINARY_SHA,
         product_source=PRODUCT_COMMIT, product_tree=PRODUCT_TREE, stages=27, dependencies=deps,
         native_platform='windows', powershell_majors=[5,7], postgres_tests_executed=True,
         package_unchanged=True, extracted_inventory_unchanged=True, real_client_consumption_verified=False,
         real_model_quality_verified=False, stable_release=False, signed=False, issue40_closed=False,
         full_project_complete=False), 'external_acceptance')
    driver = reader.obj('qualification/driver.json')
    need(set(driver) == {'package_sha256', 'steps'} and driver['package_sha256'] == PACKAGE_SHA, 'driver_identity')
    same([r['name'] for r in driver['steps']], stages(), 'stage_order')
    expected_argv = expected_commands()
    for row in driver['steps']:
        need(row['status'] == 'completed' and type(row['exit']) is int and row['exit'] == 0 and type(row['expected_exit']) is int and row['expected_exit'] == 0, 'stage_status')
        args = row['argv']
        need(type(args) is list and all(type(s) is str for s in args), 'stage_argv')
        same(args, expected_argv[row['name']], 'stage_command_binding:'+row['name'])
        for ext in ('stdout','stderr'):
            need(sha(reader.raw('qualification/logs/'+row['name']+'.'+ext)) == row[ext+'_sha256'], 'stage_log_hash')

    need(reader.raw('qualification/logs/system-only-cost.stdin') == payload['examples/cost/compare-basic.json'], 'cost_input')
    cost = reader.obj('qualification/logs/system-only-cost.stdout')
    same(cost['change'], dict(candidate_minus_baseline='-0.000050000000', relative_change={'numerator':'-5','denominator':'12'},
         relative_change_unavailable_reason=None, unavailable_reason=None), 'cost_output')
    for mode in ('normal','optimized'):
        for suite, count in [('evaluation',28),('cost-bridge',27),('old-acceptance',48)]:
            text = (reader.raw(f'qualification/logs/{suite}-{mode}.stdout')+reader.raw(f'qualification/logs/{suite}-{mode}.stderr')).decode('utf-8-sig')
            need(re.search(r'Ran '+str(count)+r' tests in ',text) and re.search(r'\nOK\s*$',text), 'suite_result')
        for suite, filename, commands, checks, test in [
            ('sqlite_backup','report.json',47,112,'test_sqlite_backup.py'),
            ('sqlite_check','RESULT.json',49,204,'test_sqlite_check.py'),
            ('postgres-hooks','RESULT.json',127,262,'test_pg_hooks.py')]:
            rel = f'qualification/{suite}-{mode}'; report = reader.obj(rel+'/'+filename)
            need(report['passed'] is True and report['binary_sha256'] == BINARY_SHA, 'process_identity')
            need(report.get('skipped',[]) == [] and report.get('failure') is None, 'process_failure_or_skip')
            key = 'test_sha256' if suite == 'sqlite_backup' else 'script_sha256'
            need(report[key] == sha(prod['.ci/'+test]), 'executed_script_identity')
            assert_checks(report,'checks',checks); raw_commands(reader,rel,report,'commands',commands)
            if suite == 'postgres-hooks':
                need(report['postgres_executed'] is True and report['real_host_consumption_verified'] is False and report['optimized'] is (mode == 'optimized'), 'postgres_scope')
    old_raw = reader.raw('old-n47x.zip'); need(sha(old_raw) == OLD_SHA, 'old_package')
    old, _, _ = archive(old_raw); old_binary_sha = sha(old['qbrain.exe'])
    binding = reader.obj('qualification/upgrade-template-binding.json')
    template = prod['tools/delivery/test_n48k_upgrade.ps1']; prior = b'24345f85e0c4962c93205a7fab0fbdb380a5ff09'
    need(template.count(prior) == 1, 'template_count')
    executed = template.replace(prior, PRODUCT_COMMIT.encode())
    need(reader.raw('qualification/test_n48s_upgrade.ps1') == executed, 'upgrade_assertions_changed')
    same(binding,dict(original_sha256=sha(template),executed_sha256=sha(executed),
         replacement='product SHA only; every existing assertion unchanged',before=prior.decode(),after=PRODUCT_COMMIT), 'upgrade_binding')
    for shell, major in [('powershell',5),('pwsh',7)]:
        for suite, count in [('test_installer_snapshot',24),('test_installer_recovery',60),('upgrade',50)]:
            r = reader.obj(f'qualification/{suite}-{shell}.json')
            need(r['binary_sha256'].lower() == BINARY_SHA, 'installer_binary')
            assert_checks(r,'checks' if suite == 'upgrade' else 'cases',count)
            if suite != 'upgrade':
                need(r['passed'] == count and type(r['passed']) is int and type(r['failed']) is int and r['failed'] == 0, 'installer_counts')
                need(r['installer_sha256'].lower() == sha(payload['scripts/Install-QbrainMemory.ps1']), 'installer_identity')
            else:
                need(r['result'] == 'PASS' and r['failure'] == '' and r['new_zip_sha256'].lower() == PACKAGE_SHA and r['script_sha256'].lower() == sha(executed) and r['real_client_verified'] is False, 'upgrade_result')
        rel = 'qualification/existing-receipts-'+shell; r = reader.obj(rel+'/RESULT.json')
        need(r['result'] == 'PASS' and r['failure'] is None and r['native_windows'] is True and r['installer_executed'] is True and r['real_client_verified'] is False and type(r['shell_major']) is int and r['shell_major'] == major, 'preservation_scope')
        need(r['package_sha256'] == PACKAGE_SHA and r['old_zip_sha256'] == OLD_SHA and r['binary_sha256'] == BINARY_SHA and r['old_binary_sha256'] == old_binary_sha and r['script_sha256'] == sha(prod['.ci/test_n48k_existing_receipts.py']), 'preservation_identity')
        assert_checks(r,'checks',79); raw_commands(reader,rel,r,'calls',98)
        starts = [i for i, call in enumerate(r['calls']) if call['name'] == 'cli-fact-read']
        need(len(starts) == 12, 'snapshot_command_groups')
        groups_iter = iter(starts)
        for host in ('Claude','Codex'):
            for phase in ('before','upgrade','rollback','reupgrade','uninstall','after-duplicate'):
                first = next(groups_iter)
                snapshot = {}
                for offset, key in enumerate(('fact','summary','all','current','withdrawn')):
                    call = r['calls'][first+offset]
                    argv = call['argv']
                    expected_action = 'read' if key == 'fact' else ('usage' if key == 'summary' else 'usage-list')
                    same(argv[1:3], ['fact',expected_action], 'snapshot_command_action')
                    need('--brain' in argv and argv[argv.index('--brain')+1] == 'preexisting-'+host.lower(), 'snapshot_command_brain')
                    if offset >= 2:
                        need('--state' in argv and argv[argv.index('--state')+1] == key, 'snapshot_command_state')
                    snapshot[key] = reader.obj(f'{rel}/raw/{first+offset:03d}.stdout')
                same(snapshot,reader.obj(rel+'/'+host+'-'+phase+'.json'),'snapshot_raw_binding')
            before = reader.obj(rel+'/'+host+'-before.json')
            same(sorted(before),['all','current','fact','summary','withdrawn'], 'snapshot_fields')
            same([v['usage_id'] for v in before['all']['items']],['1'*64,'2'*64], 'both_old_receipts')
            same([v['usage_id'] for v in before['current']['items']],['1'*64], 'active_old_receipt')
            same([v['usage_id'] for v in before['withdrawn']['items']],['2'*64], 'revoked_old_receipt')
            for phase in ('upgrade','rollback','reupgrade','uninstall','after-duplicate'):
                same(reader.obj(rel+'/'+host+'-'+phase+'.json'), before, 'preserved_complete_snapshot')
    retained = reader.obj('qualification/retained/driver.json')
    need(retained['binary_sha256'] == BINARY_SHA and retained['baseline_sha256'] == old_binary_sha and retained['script_sha256'] == sha(prod['.ci/run_n48i_checks.py']), 'retained_identity')
    retained_names = []
    for project, targets in [
        ('cost_comparison',['qbrain_cost_comparison_tests']), ('cost',['qbrain_cost_tests']),
        ('usage_import',['qbrain_usage_import_tests']),
        ('stream_import',['qbrain_stream_import_tests','qbrain_stream_history_tests']),
        ('opencode',['opencode_config_tests','opencode_audit_tests','opencode_reconcile_tests','opencode_write_races_tests']),
        ('mcp_probe',[])]:
        retained_names += [project+'-'+s for s in ('configure','build','ctest')]
        retained_names += [t+'-direct' for t in targets]
    for mode in ('normal','optimized'):
        for name in ('comparison','stream-history','cost','import','stream','stream-review'):
            retained_names += [name+'-'+mode, name+'-'+mode+'-readback']
    retained_names += ['lifecycle','retained','mcp','mcp-readback']
    same([r['name'] for r in retained['steps']], retained_names, 'retained_inventory')
    for row in retained['steps']:
        need(row['status'] == 'completed' and type(row['exit']) is int and row['exit'] == 0, 'retained_status')
        need(re.fullmatch('[a-zA-Z0-9_-]+',row['name']) is not None, 'retained_log_name')
        need(sha(reader.raw('qualification/retained/logs/'+row['name']+'.log')) == row['log_sha256'], 'retained_log_hash')
    return dict(schema='qbrain-n48s-independent-outcome-v1', result='PASS_FIXED_ARTIFACT_TOP_LEVEL_READBACK',
                product_commit=PRODUCT_COMMIT, product_tree=PRODUCT_TREE, candidate=CANDIDATE,
                package_sha256=PACKAGE_SHA, binary_sha256=BINARY_SHA, package_members=len(payload),
                candidate_files=len(all_files), product_files=len(prod), windows_candidate_crlf=source_crlf,
                windows_product_crlf=product_crlf, qualification_stages=27, retained_driver_steps=55,
                original_native_groups=60, complete_preservation_snapshots=24, files_read=len(reader.cache),
                dependencies=deps, new_windows_execution=False, new_postgresql_execution=False,
                real_client_consumption_verified=False, full_project_complete=False,
                qualification_command_binding='all_27_top_level_stage_commands_only',
                nested_command_binding_verified=False, descendant_execution_verified=False)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--canonical-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        source_reader = Reader(args.canonical_source.parent)
        reader = Reader(args.evidence)
        need(not args.output.absolute().is_relative_to(reader.root), 'output_inside_evidence')
        result = review(reader, source_reader.raw(args.canonical_source.name))
        reader.recheck(); source_reader.recheck()
        result['reviewer_sha256'] = sha(Path(__file__).read_bytes())
        with args.output.open('xb') as stream:
            stream.write(canonical(result) + b'\n')
        print(canonical(result).decode())
        return 0
    except (ValueError, OSError, KeyError, TypeError, IndexError, zipfile.BadZipFile) as error:
        print(canonical({'result':'REJECTED','error':str(error) if isinstance(error,Rejected) else type(error).__name__}).decode())
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
