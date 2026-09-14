"""Offline readback of one pinned N47A candidate; never installs, runs or publishes it.

Artifact hashes anchor both source and historical execution evidence. This checks
that evidence, not a new Windows test or an independent-agent review.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile

SOURCE = 'cccdacb61e63c29f8b9eaba1c38fbeed3e23e54b'
TREE = 'a15a91f7172622e2c8021403d84e63bf36f59147'
RUN = 34788803379
PINS = {
    'source': ('c9d8bd58d57c35b5689cea9daf4a4d7a3e53acc8d6494b8d10cdcada67b93f74', 10327229128),
    'windows': ('7da43c3b3ccda87820760f2824763af78ca3ac94cc7c56edef8447e1a9463d86', 10328096068),
    'portable': ('0d13bb0cfbcde47179dc8ce544949d0bd7c6672ab66134490910e71746553f2b', 10327438297),
    'server2022': ('a5cdcb11155d4bcdeea302234e3f088782a0e33cf4d61ac7d91bd01da62b3c5e', 10327154281),
    'package': ('1e63c74411baa955a265064dffe7675da189d6277e01ec70198a827dbc7c0816', 10328305619),
}
CAP = 128 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.ci'))
from validate_fact_report import validate_report as validate_facts, validate_unit_report
from validate_native_log import verified_groups
from validate_http_lifecycle import validate_report as validate_lifecycle
from validate_cjk_report import validate_report as validate_cjk


def require(ok, label):
    if not ok:
        raise ValueError(label)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_object(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def invalid(_):
        raise ValueError('Non-finite JSON number')
    result = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique, parse_constant=invalid)
    require(isinstance(result, dict), 'Expected JSON object')
    return result


def unzip(raw):
    require(len(raw) <= CAP, 'Compressed archive exceeds cap')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        require(0 < len(infos) <= 1500, 'Invalid member count')
        require(sum(i.file_size for i in infos) <= CAP, 'Uncompressed archive exceeds cap')
        names = set()
        result = {}
        for info in infos:
            name = info.orig_filename
            require(name == info.filename, 'Archive name was normalized or truncated')
            require(name not in names, 'Duplicate archive member')
            names.add(name)
            parts = name.rstrip('/').split('/')
            require(not name.startswith('/') and '\\' not in name and ':' not in name and
                    '\x00' not in name and all(x not in ('', '.', '..') for x in parts),
                    'Unsafe archive member')
            require(not info.flag_bits & 1, 'Encrypted archive member')
            kind = stat.S_IFMT(info.external_attr >> 16)
            require(kind in (0, stat.S_IFREG, stat.S_IFDIR), 'Non-regular member')
            if not info.is_dir():
                result[name] = archive.read(info)  # CRC checked; no paths extracted.
        return result


def pinned(path, name):
    with path.open('rb') as stream:
        raw = stream.read(CAP + 1)
    require(sha(raw) == PINS[name][0], 'Wrong artifact: ' + name)
    return unzip(raw)


def git_tree(files):
    """Reconstruct this all-100644 source tree, including directories, in memory."""
    root = {}
    def oid(kind, data):
        return hashlib.sha1(kind + b' ' + str(len(data)).encode() + b'\0' + data).digest()
    for name, data in files.items():
        node = root
        parts = PurePosixPath(name).parts
        for part in parts[:-1]:
            node = node.setdefault(part, {})
            require(isinstance(node, dict), 'Source file/directory collision')
        require(parts[-1] not in node, 'Duplicate source path')
        node[parts[-1]] = data
    def tree(node):
        entries = []
        for name, value in node.items():
            directory = isinstance(value, dict)
            key = name.encode('utf-8')
            mode = b'40000' if directory else b'100644'
            digest = tree(value) if directory else oid(b'blob', value)
            entries.append((key + (b'/' if directory else b''), mode + b' ' + key + b'\0' + digest))
        return oid(b'tree', b''.join(row for _, row in sorted(entries)))
    return tree(root).hex()


def checkout_bytes(raw, expected_hash):
    # Git archives use LF; native actions/checkout may use CRLF. No other changes.
    for value in (raw, raw.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')):
        if sha(value) == expected_hash:
            return value
    raise ValueError('Test/script bytes do not match source checkout')


def verify_inventory(files):
    manifest = json_object(files['MANIFEST.json'])
    inventory = manifest.get('files')
    require(isinstance(inventory, dict), 'Missing inventory')
    require(set(files) == set(inventory) | {'MANIFEST.json', 'README-FIRST.txt'}, 'Inventory mismatch')
    for name, meta in inventory.items():
        require(isinstance(meta, dict) and type(meta.get('bytes')) is int and
                meta['bytes'] == len(files[name]) and meta.get('sha256') == sha(files[name]),
                'Member hash/size mismatch: ' + name)
    return manifest


def verify_fact_evidence(files, source, original):
    unit = json_object(files['verification/fact-unit.json'])
    process = json_object(files['verification/fact-process.json'])
    require(files['verification/fact-unit.json'] == original['fact-unit.json'], 'Unit report differs from original logs')
    require(files['verification/fact-process.json'] == original['fact-process.json'], 'Process report differs from original logs')
    original_unit = json_object(original['fact-unit.json'])
    test = checkout_bytes(source['tests/test_n47a.cpp'], unit['test_sha256'])
    names = re.findall(r'scenario\("([^"\r\n]+)"', test.decode('utf-8'))
    unit_result = validate_unit_report(unit, source_commit=SOURCE,
        binary_sha256=original_unit['binary_sha256'], test_sha256=sha(test), expected_scenarios=names)
    script = files['verification/test_fact_process.py']
    checkout_bytes(source['.ci/test_fact_process.py'], sha(script))
    process_result = validate_facts(process, source_commit=SOURCE,
        binary_sha256=sha(files['qbrain.exe']), script_sha256=sha(script))
    require(process.get('source_tree') == TREE, 'Wrong fact process tree')
    return {'unit': unit_result, 'process': process_result,
            'probe_sha256_from_original_pinned_log': original_unit['binary_sha256'],
            'probe_binary_independently_downloaded': False}


def run(artifacts_dir):
    checks = []
    def checked(condition, label):
        require(condition, label)
        checks.append(label)
    artifacts = {}
    for name in PINS:
        artifacts[name] = pinned(artifacts_dir / (name + '.zip'), name)
        checks.append('Pinned artifact, bounded members and CRC: ' + name)
    source = unzip(artifacts['source']['qbrain-source.zip'])
    checked(len(source) == 702 and git_tree(source) == TREE, 'Exact 702-file Git source tree')
    for path in ('.ci/validate_fact_report.py', '.ci/test_fact_process.py',
                 '.ci/validate_native_log.py', '.ci/validate_http_lifecycle.py', '.ci/validate_cjk_report.py'):
        checked((ROOT/path).read_bytes() == source[path], 'Validator equals pinned candidate: ' + path)
    outer = artifacts['package']
    checked(set(outer) == {'qbrain-windows-x64-development.zip', 'SHA256SUMS.txt'}, 'Exact outer package members')
    raw = outer['qbrain-windows-x64-development.zip']
    checked(outer['SHA256SUMS.txt'].decode('ascii').split() ==
            [sha(raw), 'qbrain-windows-x64-development.zip'], 'Inner ZIP checksum')
    files = unzip(raw)
    manifest = verify_inventory(files)
    checks.extend('Inventory size/hash: ' + name for name in manifest['files'])
    logs = artifacts['windows']
    for name in files:
        if name.startswith('verification/') and name.endswith('.json'):
            checked(files[name] == logs[name.split('/')[-1]], 'Packaged report equals original native artifact: ' + name)
    validation = json_object(files['verification/validation.json'])
    for title, report in [('manifest', manifest), ('validation', validation)]:
        checked(report['source_commit'] == SOURCE and report['result'] == 'PASS' and
                report['binary_sha256'] == sha(files['qbrain.exe']) and
                type(report['registered_groups']) is int and report['registered_groups'] == 49,
                'Product provenance and exact 49 groups: ' + title)
        checked(report['signed'] is False and report['real_host_model_consumption_verified'] is False and
                report['postgres_memory_context_verified'] is False, 'Unverified scope not promoted: ' + title)
    groups = verified_groups(source['tests/test_main.cpp'].decode('utf-8'), logs['regression.log'].decode('utf-8-sig'), 49)
    checks.append('Exact native registry matched to original regression log')
    checked('SKIP' in logs['regression.log'].decode('utf-8-sig') and
            'PG' in logs['regression.log'].decode('utf-8-sig'), 'PG skip remains explicit')
    facts = verify_fact_evidence(files, source, logs)
    checks.append('Complete fact-unit and process reports independently revalidated')
    checked(validation['fact_scenarios'] == facts['unit']['scenarios'] == 15 and
            validation['fact_unit_assertions'] == facts['unit']['assertions'] == 380 and
            validation['fact_process_checks'] == facts['process']['named_checks'] == 34 and
            facts['process']['commands'] == 118, 'Fact counts agree across native manifest and reports')
    lifecycle = {}
    for platform, original in [('windows', logs), ('server2022', artifacts['server2022'])]:
        r = json_object(original['http-lifecycle.json'])
        lifecycle[platform] = validate_lifecycle(r, source_commit=SOURCE,
            probe_hashes={n:r['variants'][n]['sha256'] for n in ('legacy', 'per_call', 'current')})
        checks.append('Full fixed cancellation schedule and shutdown: ' + platform)
        r = json_object(original['http-transport.json'])
        checked(r['source_commit'] == SOURCE and r['native_windows'] is True and
                r['result'] == 'PASS' and r['check_count'] == len(r['checks']) == 81,
                '81 native wire checks: ' + platform)
    cjk = json_object(files['verification/cjk-recall.json'])
    script = files['verification/test_cjk_recall.py']
    checkout_bytes(source['.ci/test_cjk_recall.py'], sha(script))
    validate_cjk(cjk, source_commit=SOURCE, binary_sha256=sha(files['qbrain.exe']), script_sha256=sha(script))
    checks.append('All source-bound CJK names, counts and command exits')
    for name, expression in [('memory_cycle.log','44 checks passed'),('mcp_boundaries.log','17 checks passed'),
            ('hooks.log','69 passed'),('context_process.log','65 passed'),('local-config.log','6 checks passed'),
            ('embedding-search.log','11 checks passed'),('embedding-unit.log','65 checks passed'),
            ('embedding-transport.log','26 checks passed'),('embedding-queue.log','40 scenarios, 776 checks passed'),
            ('fact-unit.log','15 scenarios, 380 checks passed'),('cjk-unit.log','72 checks passed'),
            ('install51.log','69 checks passed'),('install7.log','69 checks passed'),
            ('transport51.log','8 checks passed'),('transport7.log','8 checks passed'),
            ('consent51.log','16 checks passed'),('consent7.log','16 checks passed')]:
        checked(expression in logs[name].decode('utf-8-sig'), 'Retained native regression log: ' + name)
    for delivered, original in [('scripts/Install-QbrainMemory.ps1','scripts/Install-QbrainMemory.ps1'),
            ('scripts/Invoke-QbrainJson.ps1','scripts/Invoke-QbrainJson.ps1'),
            ('EVIDENCE-FACTS.zh-CN.md','docs/integration/EVIDENCE-FACTS.zh-CN.md')]:
        checkout_bytes(source[original], sha(files[delivered]))
        checks.append('Source or exact CRLF checkout bytes: ' + delivered)
    portable = artifacts['portable']
    unit = json_object(portable['fact-unit.json'])
    process = json_object(portable['fact-process.json'])
    names = re.findall(r'scenario\("([^"\r\n]+)"', source['tests/test_n47a.cpp'].decode('utf-8'))
    validate_unit_report(unit, source_commit=SOURCE, binary_sha256=unit['binary_sha256'],
                         test_sha256=sha(source['tests/test_n47a.cpp']), expected_scenarios=names, native=False)
    validate_facts(process, source_commit=SOURCE, binary_sha256=process['binary_sha256'],
                   script_sha256=sha(source['.ci/test_fact_process.py']), native=False)
    checked(unit['native_windows'] is False and process['native_windows'] is False,
            'Portable evidence remains separate from Windows')
    return {'result':'PASS', 'scope':'Offline readback, not new runtime execution or independent review',
        'repository':'youq616/qbrain', 'source_commit':SOURCE, 'source_tree':TREE, 'workflow_run_id':RUN,
        'checks':checks, 'check_count':len(checks), 'source_files':len(source), 'registered_groups':groups,
        'fact_evidence':facts, 'http_lifecycle':lifecycle,
        'artifact_pins':{k:{'id':v[1], 'sha256':v[0]} for k,v in PINS.items()},
        'package':{'bytes':len(raw),'sha256':sha(raw)},
        'executable':{'bytes':len(files['qbrain.exe']),'sha256':sha(files['qbrain.exe'])},
        'raw_subagent_reports_received':False, 'independent_review_claimed_for_this_checker':False,
        'product_executed_here':False, 'release_published':False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--artifacts-dir', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args()
    # Refuse overwriting an old result before doing any work.
    if args.report.exists():
        p.error('Use a new report path')
    try:
        result = run(args.artifacts_dir)
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile) as error:
        result = {'result':'FAIL','error_type':type(error).__name__,
                  'scope':'Offline candidate readback failed; no release or execution occurred'}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    print(json.dumps({'result':result['result'],'check_count':result.get('check_count',0),
                      'report':str(args.report)}, ensure_ascii=True))
    return 0 if result['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
