"""Offline readback of fixed N47R native artifacts, not a new Windows execution.

Pins are an explicit input. The publisher separately authenticates them against
GitHub. Source is tree-checked before loading its original report validators.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import stat
import sys
import tempfile
import zipfile

SOURCE = '9e9a92b0e0e68ee1b07deafc1085bb01849d08a7'
TREE = '957e322e3bbd9105574cf7ce9487fb07f4b78480'
RUN = 35428968503
BUNDLE_SHA = 'e7158949d805a0a25157bfb720561e4b21e80a433a6c7f031c60ee3bbaa746c5'
BUNDLE_BYTES = 4858530
NAME = 'qbrain-windows-x64-n47r-candidate.zip'
CAP = 128 * 1024 * 1024


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def obj(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            need(key not in value, 'duplicate JSON key')
            value[key] = item
        return value
    def nonfinite(_):
        raise ValueError('nonfinite JSON')
    value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique, parse_constant=nonfinite)
    need(isinstance(value, dict), 'expected object')
    return value


def unzip(raw):
    need(len(raw) <= CAP, 'archive byte cap')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        rows = z.infolist()
        need(0 < len(rows) <= 10000 and sum(r.file_size for r in rows) <= CAP, 'archive expansion cap')
        names, out, modes = set(), {}, {}
        for r in rows:
            name = r.orig_filename
            parts = name.rstrip('/').split('/')
            need(name == r.filename and not name.startswith('/') and '\\' not in name and ':' not in name
                 and all(c >= ' ' for c in name) and all(p not in ('', '.', '..') for p in parts), 'unsafe archive path')
            key = name.rstrip('/').casefold()
            need(key not in names, 'duplicate archive path'); names.add(key)
            mode = r.external_attr >> 16
            need(not r.flag_bits & 1 and stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR), 'nonregular/encrypted member')
            need(stat.S_IFMT(mode) != stat.S_IFDIR or r.is_dir(), 'directory type mismatch')
            if not r.is_dir():
                out[name] = z.read(r)
                modes[name] = '100755' if mode & 0o111 else '100644'
        file_names = {x.casefold() for x in out}
        for name in out:
            parts = name.split('/')
            need(all('/'.join(parts[:i]).casefold() not in file_names for i in range(1, len(parts))), 'file-directory collision')
        return out, modes, z.comment


def tree_hash(files, modes):
    def oid(kind, raw):
        return hashlib.sha1(kind + b' ' + str(len(raw)).encode() + b'\0' + raw).digest()
    root = {}
    for path, raw in files.items():
        node = root; parts = path.split('/')
        for part in parts[:-1]: node = node.setdefault(part, {})
        node[parts[-1]] = (modes[path], raw)
    def visit(node):
        rows = []
        for name, item in node.items():
            key = name.encode(); folder = isinstance(item, dict)
            mode = b'40000' if folder else item[0].encode()
            value = visit(item) if folder else oid(b'blob', item[1])
            rows.append((key + (b'/' if folder else b''), mode + b' ' + key + b'\0' + value))
        return oid(b'tree', b''.join(r[1] for r in sorted(rows)))
    return visit(root).hex()


def extract(files, target):
    target.mkdir(parents=True)
    for name, raw in files.items():
        path = target / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def checkout_bytes(raw, digest):
    for variant in (raw, raw.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')):
        if sha(variant) == digest.lower(): return variant
    raise ValueError('source/test byte identity mismatch')


def unit_log(raw, count):
    text = raw.decode('utf-8-sig').replace('\r\n', '\n')
    need(re.search(r'^Ran ' + str(count) + r' tests? in ', text, re.M) is not None
         and re.search(r'^OK$', text, re.M) is not None and '\nFAILED' not in text, 'unit test log failed/incomplete')


def windows_source_match(canonical, observed, modes, observed_modes):
    need(set(canonical) == set(observed) and modes == observed_modes, 'platform source membership/modes differ')
    converted = 0
    for name, raw in canonical.items():
        if observed[name] == raw:
            continue
        need(b'\x00' not in raw and b'\r' not in raw and observed[name] == raw.replace(b'\n', b'\r\n'), 'unexpected platform source transform: ' + name)
        # Historical ASCII-superset logs are not all UTF-8; exact byte
        # LF-to-CRLF equality is the constraint, not text decoding.
        converted += 1
    return converted


def verify(artifacts: Path, pins: dict, baseline: Path):
    need(pins.get('source_commit') == SOURCE and pins.get('source_tree') == TREE
         and type(pins.get('run_id')) is int and pins['run_id'] == RUN, 'fixed source/run pins mismatch')
    need(set(pins.get('artifacts', {})) == {'windows', 'linux', 'native'}, 'artifact coverage')
    archives = {}
    for label, pin in pins['artifacts'].items():
        need(pin.get('file') == label + '.zip', 'noncanonical artifact filename')
        raw = (artifacts / pin['file']).read_bytes()
        need(len(raw) == pin['bytes'] and sha(raw) == pin['sha256'], 'artifact byte identity: ' + label)
        archives[label] = unzip(raw)[0]
        need(archives[label]['source.txt'].decode('utf-8-sig').strip() == SOURCE, 'artifact checkout source')
    source, modes, comment = unzip(archives['linux']['qbrain-source.zip'])
    need(comment.decode() == SOURCE and tree_hash(source, modes) == TREE, 'source tree mismatch')
    windows_source, windows_modes, windows_comment = unzip(archives['windows']['qbrain-source.zip'])
    need(windows_comment.decode() == SOURCE, 'Windows archive commit marker')
    # git archive on the native runner exported working-tree CRLF bytes. The
    # independently tree-verified Linux archive remains the canonical authority.
    converted = windows_source_match(source, windows_source, modes, windows_modes)
    with tempfile.TemporaryDirectory(prefix='n47r-evidence-') as temp:
        root = Path(temp); src = root / 'source'; extract(source, src)
        sys.path.insert(0, str(src / '.ci'))
        builder = load(src / 'tools/delivery/build_integrated_n47r.py', 'n47r_pinned_builder')
        expected = builder.expected_files(baseline, src, src)
        raw_bundle = archives['windows']['one/' + NAME]
        need(len(raw_bundle) == BUNDLE_BYTES and sha(raw_bundle) == BUNDLE_SHA, 'candidate ZIP identity')
        bundle_result = builder.verify(raw_bundle, expected)
        for label in ('windows', 'linux'):
            z = archives[label]
            need(z['one/' + NAME] == z['two/' + NAME] == raw_bundle, 'different repeated/cross-platform bundle')
            for which in ('one', 'two'):
                need(obj(z[which + '/LOCAL-VERIFICATION.json']) == bundle_result, 'builder receipt mismatch')
                need(z[which + '/SHA256SUMS.txt'] == (BUNDLE_SHA + '  ' + NAME + '\n').encode(), 'bundle checksum receipt')
            for log in ('builder-tests.log', 'builder-tests-optimized.log'): unit_log(z[log], 22)
            for log in ('bundled-tools.log', 'bundled-tools-optimized.log'): unit_log(z[log], 24)
        bundled = root / 'bundle'; extract(expected, bundled)
        w = archives['windows']
        snapshot = load(src / '.ci/check_installer_snapshot_report.py', 'n47r_snapshot_check')
        recovery = load(src / '.ci/check_recovery_report.py', 'n47r_recovery_check')
        native = load(src / '.ci/validate_native_log.py', 'n47r_native_check')
        installers = {
            'test_hook_fact_install': load(src / '.ci/validate_hook_fact_report.py', 'n47r_fact_check'),
            'test_promotion_install': load(src / '.ci/validate_promotion_report.py', 'n47r_promotion_check'),
        }
        shell_results = {}
        installer = expected['scripts/Install-QbrainMemory.ps1']; exe = expected['qbrain.exe']
        for shell, major in (('powershell', 5), ('pwsh', 7)):
            snap = obj(w[f'snapshot-{shell}.json'])
            snap_test = checkout_bytes(source['.ci/test_installer_snapshot.ps1'], snap['test_sha256'])
            checked = snapshot.validate(snap, installer, snap_test, exe, SOURCE, major)
            rec = obj(w[f'recovery-{shell}.json'])
            need(int(rec['powershell'].split('.')[0]) == major, 'recovery shell mismatch')
            rec_checked = recovery.validate(rec, installer, exe)
            shell_results[shell] = {'snapshot': checked, 'recovery': rec_checked}
            for prefix, report in (('snapshot', snap), ('recovery', rec)):
                lines = w[f'{prefix}-{shell}.log'].decode('utf-8-sig').splitlines()
                need([s[5:] for s in lines if s.startswith('PASS ')] == [r['name'] for r in report['cases']], 'case logs differ')
            for name, count in (('test_install_hooks', 69), ('test_install_consent', 16), ('test_windows_transport', 8)):
                log = w[f'{name}-{shell}.log'].decode('utf-8-sig')
                need(list(map(int, re.findall(r'^PASS (\d+) :', log, re.M))) == list(range(1, count+1)), 'original sequence: ' + name)
                shell_results[shell][name] = count
            for name, validator in installers.items():
                report = obj(w[f'{name}-{shell}.json'])
                script = checkout_bytes(source['.ci/' + name + '.ps1'], report['script_sha256'])
                shell_results[shell][name] = validator.validate_install(report, source_commit=SOURCE,
                    binary_sha256=builder.EXE_SHA, script_sha256=sha(script), installer_sha256=builder.INSTALLER_CRLF, shell_major=major)
        sys.path.insert(0, str(bundled / 'tools/acceptance'))
        task_checker = load(bundled / 'tools/acceptance/check_memory_task_run.py', 'n47r_task_check')
        task_results = {}
        for host in ('claude', 'codex'):
            task_files = {p[len('tasks-'+host+'/'):]: raw for p, raw in w.items() if p.startswith('tasks-'+host+'/')}
            directory = root / ('tasks-' + host); extract(task_files, directory)
            result = task_checker.verify(directory, bundled / 'qbrain.exe')
            need(result == obj(w[f'tasks-{host}-readback.json']), 'task readback mismatch')
            need(result['source_commit'] is None, 'bundled tool is not a git checkout')
            task_results[host] = result
        native_log = archives['native']['native.log'].decode('utf-8-sig')
        groups = native.verified_groups(source['tests/test_main.cpp'].decode(), native_log, 60)
        need('BUILD_OK' in native_log, 'missing native production build')
        return {'schema': 'qbrain-n47r-native-readback-v1', 'result': 'NATIVE_BUNDLE_EVIDENCE_VERIFIED',
                'source_commit': SOURCE, 'source_tree': TREE, 'run_id': RUN, 'source_files': len(source),
                'bundle': bundle_result, 'windows_archive_exact_lf_to_crlf_files': converted, 'shells': shell_results, 'task_runs': task_results,
                'fresh_native_groups': groups, 'pg_skipped': 'SKIP-PG' in native_log,
                'new_local_windows_execution': False, 'real_client_verified': False,
                'limits': ['Offline pins require separately verified origin', 'Recorded Windows CI, not a local Windows execution',
                           'Synthetic installation and Hook scenarios, not authenticated model/client acceptance']}


UPGRADE_SOURCE = 'b7e1b60a40f421c13e494733efbf8ce0420f2aaa'
UPGRADE_TREE = '4b1a0405ceb9c88f0a219223910c7febc6a59119'
UPGRADE_RUN = 35429293475
UPGRADE_EXTRA = {'tools/delivery/test_n47r_upgrade.ps1', '.github/workflows/n47r-upgrade-validation.yml',
                 'docs/nodes/n47r-evidence/UPGRADE-REVIEW-PLAN.md'}


def upgrade_names():
    names = ['guide rejects wrong checksum before extraction', 'guide extracts exact native EXE',
             'guide extracts exact repaired installer', 'guide rejects existing extraction directory']
    for host in ('Claude', 'Codex'):
        labels = ['old installation found', 'old installation active', 'old stored evidence exists',
                  'new installation coherent', 'explicit upgrade consent retained', 'unrelated configuration preserved']
        labels += ['no duplicate ' + event for event in ('SessionStart', 'UserPromptSubmit', 'Stop', 'PreCompact', 'SessionEnd')]
        labels += ['MCP routed to new EXE location', 'new session preserves old fact identity and quotation',
                   'unspecified upgrade flags default off', 'uninstall disables without claiming consumption',
                   'uninstall keeps original brain evidence']
        names += [host + ' ' + text for text in labels]
    return names + ['global default configuration unchanged']


def upgrade_report(value, log, script, shell):
    need(value.get('schema') == 'qbrain-n47r-upgrade-v1' and value.get('result') == 'PASS'
         and value.get('source_commit') == UPGRADE_SOURCE and value.get('native_windows') is True
         and type(value.get('shell_major')) is int and value['shell_major'] == shell
         and value.get('real_client_verified') is False and type(value.get('count')) is int
         and value['count'] == 37, 'upgrade result/scope')
    need(value.get('candidate_sha256') == BUNDLE_SHA
         and value.get('baseline_sha256') == 'ec681a4599bf1b2a90f3848f5bf65b6d6a32e37254f32392d0709c43080b356c'
         and value.get('script_sha256') == sha(script), 'upgrade component identity')
    rows = value.get('checks')
    need(isinstance(rows, list) and len(rows) == 37 and all(isinstance(r, dict) for r in rows), 'upgrade coverage')
    need([r.get('name') for r in rows] == upgrade_names()
         and all(r.get('passed') is True for r in rows), 'upgrade checks')
    text = log.decode('utf-8-sig').replace('\r\n', '\n')
    observed = re.findall(r'^PASS (\d+) : (.+)$', text, re.M)
    need(observed == [(str(i), name) for i, name in enumerate(upgrade_names(), 1)], 'upgrade log sequence')
    return {'source_commit': UPGRADE_SOURCE, 'shell_major': shell, 'checks': 37,
            'candidate_sha256': BUNDLE_SHA, 'script_sha256': sha(script), 'real_client_verified': False}


def verify_upgrade(artifacts, pins, canonical_source, canonical_modes, bundle):
    need(pins.get('source_commit') == UPGRADE_SOURCE and pins.get('source_tree') == UPGRADE_TREE
         and type(pins.get('run_id')) is int and pins['run_id'] == UPGRADE_RUN, 'upgrade source/run pins')
    need(set(pins.get('artifacts', {})) == {'upgrade5', 'upgrade7'}, 'upgrade artifact coverage')
    results = {}
    for label, shell in (('upgrade5', 5), ('upgrade7', 7)):
        pin = pins['artifacts'][label]
        need(pin.get('file') == label + '.zip', 'upgrade artifact filename')
        raw = (artifacts / pin['file']).read_bytes()
        need(len(raw) == pin['bytes'] and sha(raw) == pin['sha256'], 'upgrade artifact digest')
        z, _, _ = unzip(raw)
        need(z['source.txt'].decode('utf-8-sig').strip() == UPGRADE_SOURCE, 'upgrade checkout')
        files, modes, comment = unzip(z['qbrain-source.zip'])
        need(comment.decode() == UPGRADE_SOURCE and set(files) == set(canonical_source) | UPGRADE_EXTRA,
             'upgrade source identity')
        windows_source_match(canonical_source, {k: files[k] for k in canonical_source}, canonical_modes,
                             {k: modes[k] for k in canonical_modes})
        combined = dict(canonical_source)
        for name in UPGRADE_EXTRA:
            combined[name] = files[name].replace(b'\r\n', b'\n')
        need(tree_hash(combined, modes) == UPGRADE_TREE, 'upgrade source tree')
        need(z['bundle/' + NAME] == bundle, 'upgrade bundle bytes')
        report = obj(z['upgrade.json'])
        results[label] = upgrade_report(report, z['upgrade.log'], files['tools/delivery/test_n47r_upgrade.ps1'], shell)
    return {'result': 'UPGRADE_EVIDENCE_VERIFIED', 'source_commit': UPGRADE_SOURCE,
            'source_tree': UPGRADE_TREE, 'run_id': UPGRADE_RUN, 'shells': results}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('artifacts', 'pins', 'baseline', 'report'): p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    result = verify(a.artifacts, obj(a.pins.read_bytes()), a.baseline)
    with a.report.open('x', encoding='utf-8') as out: json.dump(result, out, indent=2, ensure_ascii=False); out.write('\n')
    print('NATIVE_BUNDLE_EVIDENCE_VERIFIED:', len(result['fresh_native_groups']), 'native groups')


if __name__ == '__main__': main()
