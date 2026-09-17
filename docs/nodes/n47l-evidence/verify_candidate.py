"""Offline N47L CI artifact readback; no product execution, network, or publication.

The caller downloads the named GitHub artifacts and supplies a reviewed metadata
snapshot plus its fixed SHA-256. This script authenticates bytes against those
pins; it does not authenticate a caller-created metadata snapshot against GitHub.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import math
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import zipfile

CAP = 128 * 1024 * 1024
REPOSITORY = 'youq616/qbrain'
GROUP_COUNT = 60
RUNS = {
    'n44': ('.github/workflows/n44-validation.yml',
            {'source', 'windows', 'windows-http-2022', 'portable', 'batch-sanitized'}),
    'n42': ('.github/workflows/n42-validation.yml', {'source', 'windows', 'portable'}),
}
ARTIFACTS = {
    'source': ('n44', 'qbrain-n44-source'),
    'windows': ('n44', 'qbrain-n44-windows-logs'),
    'package': ('n44', 'qbrain-n44-windows-development-package'),
    'server2022': ('n44', 'qbrain-n46f-server2022-http-evidence'),
    'portable': ('n44', 'qbrain-n44-portable-logs'),
    'sanitizer': ('n44', 'qbrain-n47g-sanitizer-evidence'),
    'n42-windows': ('n42', 'qbrain-n42-windows-logs'),
}
# Count and command schedules are owned by the authenticated source validators.
# This table only maps mandatory artifact members to their original validators.
MAPPING = (
    ('multiterm', 'validate_multiterm_report', 'multiterm', 'n47l'),
    ('hook-diagnostic', 'validate_hook_diagnostic_report', 'hook_diagnostic', 'n47k'),
    ('hook-trace', 'validate_hook_trace_report', 'hook_trace', 'n47j'),
    ('strict-json', 'validate_strict_json_report', 'strict_json', 'n47i'),
    ('candidate', 'validate_lifecycle_candidate_report', 'lifecycle_candidate', 'n47h'),
    ('batch', 'validate_lifecycle_batch_report', 'lifecycle_batch', 'n47g'),
    ('fact-lifecycle', 'validate_fact_lifecycle_report', 'lifecycle', 'n47f'),
    ('promotion', 'validate_promotion_report', 'promotion', 'n47e'),
    ('hook-fact', 'validate_hook_fact_report', 'hook_fact', 'n47d'),
    ('recall', 'validate_recall_report', 'recall', 'n47c'),
    ('conflict', 'validate_conflict_report', 'conflict', 'n47b'),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def is_sha(value, length=64):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{%d}' % length, value) is not None


def obj(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError('nonfinite JSON number')
    def finite_float(text):
        value = float(text)
        require(math.isfinite(value), 'nonfinite JSON float')
        return value
    result = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique,
                        parse_constant=nonfinite, parse_float=finite_float)
    require(isinstance(result, dict), 'JSON object required')
    return result


def read_file(path, cap=CAP):
    require(path.is_file() and not path.is_symlink(), 'regular file required: ' + str(path))
    with path.open('rb') as stream:
        raw = stream.read(cap + 1)
    require(len(raw) <= cap, 'file byte cap: ' + str(path))
    return raw


def unzip(raw):
    require(len(raw) <= CAP, 'archive byte cap')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        rows = archive.infolist()
        require(0 < len(rows) <= 3000 and sum(row.file_size for row in rows) <= CAP,
                'archive expansion cap')
        names = [row.orig_filename for row in rows]
        require(len(names) == len(set(names)), 'duplicate archive name')
        require(len(names) == len({name.rstrip('/').casefold() for name in names}),
                'archive path aliases on native Windows')
        files, modes = {}, {}
        for row in rows:
            name = row.orig_filename
            require(name == row.filename and not name.startswith('/') and
                    '\\' not in name and ':' not in name and
                    all(ord(c) >= 32 for c in name) and
                    all(part not in ('', '.', '..') for part in name.rstrip('/').split('/')),
                    'unsafe archive path')
            mode = row.external_attr >> 16
            kind = stat.S_IFMT(mode)
            require(not row.flag_bits & 1 and kind in (0, stat.S_IFREG, stat.S_IFDIR),
                    'encrypted or nonregular archive member')
            require(not (kind == stat.S_IFDIR and not row.is_dir()), 'directory mode mismatch')
            if not row.is_dir():
                files[name] = archive.read(row)  # zipfile also verifies each CRC.
                modes[name] = '100755' if mode & 0o111 else '100644'
        # Reject file/directory conflicts before writing any verified source file.
        for name in files:
            parts = name.split('/')
            require(all('/'.join(parts[:i]) not in files for i in range(1, len(parts))),
                    'archive file/directory collision')
        return files, modes, archive.comment


def source_tree(files, modes):
    root = {}
    def oid(kind, raw):
        return hashlib.sha1(kind + b' ' + str(len(raw)).encode() + b'\0' + raw).digest()
    for path, raw in files.items():
        node, parts = root, path.split('/')
        for part in parts[:-1]:
            node = node.setdefault(part, {})
            require(isinstance(node, dict), 'source path collision')
        require(parts[-1] not in node, 'source duplicate')
        node[parts[-1]] = (modes[path], raw)
    def tree(node):
        entries = []
        for name, value in node.items():
            key = name.encode('utf-8')
            directory = isinstance(value, dict)
            mode = b'40000' if directory else value[0].encode('ascii')
            digest = tree(value) if directory else oid(b'blob', value[1])
            entries.append((key + (b'/' if directory else b''), mode + b' ' + key + b'\0' + digest))
        return oid(b'tree', b''.join(row for _, row in sorted(entries)))
    return tree(root).hex()


def checkout_hashes(raw):
    # Git checkout on native Windows can apply LF -> CRLF. No other transform.
    return {sha(raw), sha(raw.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))}


def package_mapping(raw):
    """Read the packaging inventory without executing the packaging program."""
    program = ast.parse(raw.decode('utf-8-sig'))
    definitions = [node.value for node in program.body if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'files' for t in node.targets)]
    require(len(definitions) == 1 and isinstance(definitions[0], ast.Dict), 'literal package inventory required')
    result = {}
    for key, value in zip(definitions[0].keys, definitions[0].values):
        require(isinstance(key, ast.Constant) and isinstance(key.value, str) and key.value not in result,
                'invalid or duplicate package inventory key')
        if isinstance(value, ast.Name) and value.id == 'binary':
            origin = ('binary', '')
        else:
            require(isinstance(value, ast.BinOp) and isinstance(value.op, ast.Div) and
                    isinstance(value.left, ast.Name) and value.left.id in ('root', 'e') and
                    isinstance(value.right, ast.Constant) and isinstance(value.right.value, str),
                    'unsupported package inventory expression')
            origin = ('source' if value.left.id == 'root' else 'windows', value.right.value)
        result[key.value] = origin
    require(result and 'qbrain.exe' in result, 'missing source-defined package inventory')
    return result


def package_readme(raw):
    program = ast.parse(raw.decode('utf-8-sig'))
    values = [node.args[1].value for node in ast.walk(program)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and
              node.func.attr == 'writestr' and len(node.args) == 2 and
              isinstance(node.args[0], ast.Constant) and node.args[0].value == 'README-FIRST.txt' and
              isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str)]
    require(len(values) == 1, 'literal original package README required')
    return values[0].encode('utf-8')


def metadata_check(meta, source_sha, tree, run_ids):
    require(meta.get('schema_version') == 1 and type(meta['schema_version']) is int, 'metadata schema')
    require(meta.get('repository') == REPOSITORY, 'metadata repository')
    require(meta.get('source_commit') == source_sha and meta.get('source_tree') == tree, 'metadata source')
    require(set(meta.get('runs', {})) == set(RUNS), 'missing/extra workflow snapshot')
    for label, (path, mandatory) in RUNS.items():
        run = meta['runs'][label]
        require(type(run.get('id')) is int and run['id'] == run_ids[label] and
                run.get('head_sha') == source_sha and run.get('path') == path and
                run.get('repository') == REPOSITORY and run.get('head_repository') == REPOSITORY and
                run.get('status') == 'completed' and run.get('conclusion') == 'success' and
                run.get('event') in ('push', 'workflow_dispatch') and
                type(run.get('run_attempt')) is int and run['run_attempt'] > 0,
                'workflow source/status mismatch: ' + label)
        require(run.get('html_url') == f'https://github.com/{REPOSITORY}/actions/runs/{run_ids[label]}',
                'workflow URL mismatch: ' + label)
        jobs = run.get('jobs')
        require(isinstance(jobs, list) and type(run.get('jobs_total_count')) is int and
                run['jobs_total_count'] == len(jobs) and len({j.get('name') for j in jobs}) == len(jobs) and
                len({j.get('id') for j in jobs}) == len(jobs), 'missing/duplicate workflow jobs')
        named = {job['name']: job for job in jobs}
        require(mandatory <= set(named), 'mandatory jobs missing: ' + label)
        for name, job in named.items():
            require(type(job.get('id')) is int and job['id'] > 0 and job.get('run_id') == run_ids[label] and
                    job.get('status') == 'completed' and job.get('head_sha') == source_sha and
                    type(job.get('run_attempt')) is int and job['run_attempt'] == run['run_attempt'],
                    'incomplete/wrong workflow job source or attempt')
            if name in mandatory:
                require(job.get('conclusion') == 'success' and isinstance(job.get('steps'), list) and
                        job['steps'] and all(step.get('status') == 'completed' and
                        step.get('conclusion') == 'success' for step in job['steps']),
                        'mandatory job/step not successful: ' + label + '/' + name)
            else:
                require(label == 'n44' and name in ('publish-cjk-preview', 'publish-fact-preview') and
                        job.get('conclusion') == 'skipped', 'unexpected workflow job')
    require(set(meta.get('artifacts', {})) == set(ARTIFACTS), 'missing/extra artifact pins')
    require(len({row.get('id') for row in meta['artifacts'].values()}) == len(ARTIFACTS), 'duplicate artifact ID')
    for label, (run_label, name) in ARTIFACTS.items():
        item = meta['artifacts'][label]
        require(type(item.get('id')) is int and item['id'] > 0 and item.get('name') == name and
                item.get('run_id') == run_ids[run_label] and item.get('head_sha') == source_sha and
                item.get('expired') is False and is_sha(item.get('sha256')) and
                type(item.get('size_in_bytes')) is int and 0 < item['size_in_bytes'] <= CAP and
                item.get('file') == label + '.zip', 'artifact identity mismatch: ' + label)


def validator_worker(stage, inputs, output):
    """Run only under a fresh isolated Python process after archive verification."""
    import importlib
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(stage / '.ci'))
    data = obj(read_file(inputs))
    source_sha, tree, exe_sha = data['source_commit'], data['source_tree'], data['exe_sha256']
    reports = data['reports']
    summaries = {}
    def check_source(path, digest):
        require(is_sha(digest) and digest in checkout_hashes(read_file(stage / path)), 'report source hash: ' + path)
    def provenance(report, native, *, require_tree=False):
        require(report.get('source_commit') == source_sha and report.get('native_windows') is native,
                'report source/platform mismatch')
        if require_tree or 'source_tree' in report:
            require(report.get('source_tree') == tree, 'report source tree mismatch')
        if 'head_commit' in report:
            require(report['head_commit'] == source_sha, 'report HEAD mismatch')
    for platform in ('windows', 'server2022', 'portable', 'sanitizer'):
        native = platform in ('windows', 'server2022')
        rows = MAPPING[:6] if platform == 'sanitizer' else MAPPING
        archive, result = reports[platform], {}
        process_sha = exe_sha if native else archive['multiterm-process.json']['binary_sha256']
        require(is_sha(process_sha), 'production process binary hash')
        for prefix, module, script, test in rows:
            validator = importlib.import_module(module)
            unit = archive[prefix + '-unit.json']
            provenance(unit, native, require_tree=True)
            require(is_sha(unit.get('binary_sha256')), 'unit probe hash')
            check_source('tests/test_' + test + '.cpp', unit['test_sha256'])
            check_source('.ci/test_' + script + '_unit.py', unit['script_sha256'])
            result[prefix + '-unit'] = validator.validate_unit(unit, source_commit=source_sha,
                binary_sha256=unit['binary_sha256'], script_sha256=unit['script_sha256'],
                test_sha256=unit['test_sha256'], native=native)
            if platform != 'server2022':
                process = archive[prefix + '-process.json']
                provenance(process, native, require_tree=True)
                check_source('.ci/test_' + script + '_process.py', process['script_sha256'])
                result[prefix + '-process'] = validator.validate_process(process, source_commit=source_sha,
                    binary_sha256=process_sha, script_sha256=process['script_sha256'], native=native)
        if native:
            http = archive['http-lifecycle.json']
            result['http-lifecycle'] = importlib.import_module('validate_http_lifecycle').validate_report(
                http, source_commit=source_sha,
                probe_hashes={name: http['variants'][name]['sha256'] for name in ('legacy', 'per_call', 'current')})
            wire = archive['http-transport.json']
            provenance(wire, True)
            require(wire.get('result') == 'PASS' and type(wire.get('check_count')) is int and
                    wire['check_count'] == len(wire['checks']) == 81 and
                    all(isinstance(name, str) for name in wire['checks']) and
                    is_sha(wire.get('probe_sha256')),
                    'native HTTP report incomplete')
            result['http-transport'] = {'checks': wire['check_count']}
        if platform in ('windows', 'portable'):
            fact = importlib.import_module('validate_fact_report')
            unit = archive['fact-unit.json']; provenance(unit, native)
            require(is_sha(unit.get('binary_sha256')), 'fact unit probe hash')
            check_source('tests/test_n47a.cpp', unit['test_sha256'])
            names = re.findall(r'scenario\("([^"\r\n]+)"', (stage/'tests/test_n47a.cpp').read_text(encoding='utf-8'))
            result['fact-unit'] = fact.validate_unit_report(unit, source_commit=source_sha,
                binary_sha256=unit['binary_sha256'], test_sha256=unit['test_sha256'], expected_scenarios=names, native=native)
            process = archive['fact-process.json']; provenance(process, native)
            check_source('.ci/test_fact_process.py', process['script_sha256'])
            result['fact-process'] = fact.validate_report(process, source_commit=source_sha,
                binary_sha256=process_sha, script_sha256=process['script_sha256'], native=native)
            cjk = archive['cjk-recall.json']; provenance(cjk, native)
            check_source('.ci/test_cjk_recall.py', cjk['script_sha256'])
            result['cjk-process'] = {'checks': importlib.import_module('validate_cjk_report').validate_report(cjk,
                source_commit=source_sha, binary_sha256=process_sha, script_sha256=cjk['script_sha256'])}
            queue = archive['embedding-queue.json']; provenance(queue, native, require_tree=True)
            require(queue.get('result') == 'PASS' and queue.get('tracked_tree_clean') is True and
                    queue.get('real_provider_calls') is False and queue.get('production_queue_and_storage') is True and
                    type(queue.get('scenario_count')) is int and queue['scenario_count'] == len(queue['scenarios']) >= 40 and
                    len(set(queue['scenarios'])) == len(queue['scenarios']) and
                    type(queue.get('checks')) is int and queue['checks'] >= 776 and is_sha(queue.get('probe_sha256')),
                    'embedding queue report incomplete')
            for mode in ('automatic', 'generic'):
                for code in ('001', '002', '003', '004'):
                    require(any(name.startswith(f'{mode}: QB-QUEUE-{code}:') for name in queue['scenarios']), 'queue regression omitted')
            result['embedding-queue'] = {'scenarios': queue['scenario_count'], 'checks': queue['checks']}
            retrieval = archive['retrieval-benchmark.json']; provenance(retrieval, native, require_tree=True)
            require(retrieval.get('result') == 'PASS' and retrieval.get('tracked_tree_clean') is True and
                    retrieval.get('results_equal') is True and retrieval.get('hybrid_results_equal') is True and
                    retrieval.get('chunks_scanned') == retrieval.get('chunks') == 16000 and
                    type(retrieval.get('peak_retained_pages')) is int and
                    type(retrieval.get('limit')) is int and
                    0 < retrieval['peak_retained_pages'] <= retrieval['limit'] == 50 and
                    type(retrieval.get('native_test_checks')) is int and retrieval['native_test_checks'] > 100000 and
                    is_sha(retrieval.get('probe_sha256')), 'exact retrieval report incomplete')
            result['retrieval'] = {'checks': retrieval['native_test_checks']}
        summaries[platform] = result
    windows = reports['windows']
    for prefix, module, script in (
            ('promotion', 'validate_promotion_report', 'test_promotion_install.ps1'),
            ('hook-fact', 'validate_hook_fact_report', 'test_hook_fact_install.ps1')):
        for suffix, major in (('51', 5), ('7', 7)):
            report = windows[prefix + '-install' + suffix + '.json']
            check_source('.ci/' + script, report['script_sha256'])
            check_source('scripts/Install-QbrainMemory.ps1', report['installer_sha256'])
            summaries['windows'][prefix + '-install' + suffix] = importlib.import_module(module).validate_install(
                report, source_commit=source_sha, binary_sha256=exe_sha, script_sha256=report['script_sha256'],
                installer_sha256=report['installer_sha256'], shell_major=major)
    embedding = windows['embedding-transport.json']; provenance(embedding, True)
    require(embedding.get('result') == 'PASS' and type(embedding.get('check_count')) is int and
            embedding['check_count'] == len(embedding['checks']) >= 25 and
            embedding['probe_sha256'] == windows['http-transport.json']['probe_sha256'] and
            embedding.get('live_provider_verified') is False, 'embedding wire report mismatch')
    summaries['windows']['embedding-wire'] = {'checks': embedding['check_count']}
    native = importlib.import_module('validate_native_log')
    registry = (stage/'tests/test_main.cpp').read_text(encoding='utf-8')
    native_groups = {label: native.verified_groups(registry, text, GROUP_COUNT)
                     for label, text in data['native_logs'].items()}
    require(set(native_groups) == {'n44', 'n42'}, 'both native group logs required')
    link = importlib.import_module('test_msvc_link_manifest').validate_manifest(
        (stage/'scripts/build-cl.ps1').read_text(encoding='utf-8-sig'),
        (stage/'scripts/build-tests-cl.ps1').read_text(encoding='utf-8-sig'))
    # Do not run test/probe executables; their distinct hashes are report attestations.
    output.write_text(json.dumps({'report_summaries': summaries, 'native_groups': native_groups,
                                  'msvc_source_counts': link}), encoding='utf-8')


def verify(candidate, artifact_dir, metadata_path, metadata_sha, source_sha, tree, run_ids):
    checks = []
    def check(condition, label):
        require(condition, label)
        checks.append(label)
    check(is_sha(source_sha, 40) and is_sha(tree, 40) and is_sha(metadata_sha), 'valid input pins')
    meta_raw = read_file(metadata_path, 4 * 1024 * 1024)
    check(sha(meta_raw) == metadata_sha, 'fixed metadata SHA-256')
    meta = obj(meta_raw); metadata_check(meta, source_sha, tree, run_ids)
    checks.append('both candidate workflow snapshots and all artifact identities')
    archives = {}
    for label in ARTIFACTS:
        pin = meta['artifacts'][label]
        raw = read_file(artifact_dir/pin['file'])
        check(len(raw) == pin['size_in_bytes'] and sha(raw) == pin['sha256'], 'external artifact bytes: ' + label)
        archives[label] = unzip(raw)[0]
    check(set(archives['source']) == {'qbrain-source.zip'}, 'source wrapper members')
    source, modes, comment = unzip(archives['source']['qbrain-source.zip'])
    check(comment.decode('ascii') == source_sha and source_tree(source, modes) == tree, 'source commit comment and reconstructed Git tree')
    candidate = candidate.resolve()
    for path, raw in source.items():
        local = candidate/path
        check(local.resolve().is_relative_to(candidate) and sha(read_file(local)) in checkout_hashes(raw), 'local source checkout: ' + path)
    outer = archives['package']
    check(set(outer) == {'qbrain-windows-x64-development.zip', 'SHA256SUMS.txt'}, 'outer package inventory')
    package = outer['qbrain-windows-x64-development.zip']; package_sha = sha(package)
    check(outer['SHA256SUMS.txt'].decode('ascii').split() == [package_sha, 'qbrain-windows-x64-development.zip'], 'original package checksum')
    files = unzip(package)[0]
    manifest, validation = obj(files['MANIFEST.json']), obj(files['verification/validation.json'])
    mapping = package_mapping(source['.ci/package_n44_development.py'])
    check(set(files) == set(mapping) | {'MANIFEST.json', 'README-FIRST.txt'} and
          set(manifest.get('files', {})) == set(mapping), 'exact source-defined manifest inventory')
    check(files['README-FIRST.txt'] == package_readme(source['.ci/package_n44_development.py']),
          'original package README bytes')
    check({k: v for k, v in manifest.items() if k != 'files'} == validation, 'manifest and validation summary agree')
    exe_sha = sha(files['qbrain.exe'])
    for path, spec in manifest['files'].items():
        check(type(spec.get('bytes')) is int and spec['bytes'] == len(files[path]) and
              spec.get('sha256') == sha(files[path]), 'manifest file bytes: ' + path)
        origin, original = mapping[path]
        if origin == 'source':
            check(sha(files[path]) in checkout_hashes(source[original]), 'packaged source identity: ' + path)
        elif origin == 'windows':
            check(files[path] == archives['windows'][original], 'original Windows evidence bytes: ' + path)
        else:
            check(path == 'qbrain.exe', 'single product executable inventory')
    check(validation.get('result') == 'PASS' and validation.get('source_commit') == source_sha and
          validation.get('binary_sha256') == exe_sha and type(validation.get('registered_groups')) is int and
          validation['registered_groups'] == GROUP_COUNT, 'packaged source and native group summary')
    check(all(validation.get(key) is False for key in
              ('signed', 'real_host_model_consumption_verified', 'postgres_memory_context_verified')),
          'unverified signing, host and PG scope remains explicit')
    report_data = {platform: {name: obj(raw) for name, raw in archives[platform].items() if name.endswith('.json')}
                   for platform in ('windows', 'server2022', 'portable', 'sanitizer')}
    native_logs = {'n44': archives['windows']['regression.log'].decode('utf-8-sig'),
                   'n42': archives['n42-windows']['windows-tests.log'].decode('utf-8-sig')}
    n42_source = archives['n42-windows']['source.txt'].decode('utf-8-sig').strip()
    check(n42_source == 'Source commit: ' + source_sha, 'N42 native log source')
    for platform in ('server2022', 'sanitizer'):
        check(archives[platform]['source.txt'].decode('utf-8-sig').strip() == source_sha,
              'platform source record: ' + platform)
    check('Microsoft Windows NT 10.0.20348.' in archives['server2022']['platform.txt'].decode('utf-8-sig'),
          'Server 2022 operating system record')
    check('clang version' in archives['sanitizer']['compiler.txt'].decode('utf-8-sig') and
          'compiler identification is Clang' in archives['sanitizer']['configure.log'].decode('utf-8-sig'),
          'sanitizer Clang toolchain records')
    workflow = source['.github/workflows/n44-validation.yml'].decode('utf-8')
    sanitizer = workflow.split('\n  batch-sanitized:\n', 1)[1].split('\n  publish-', 1)[0]
    check(all(fragment in sanitizer for fragment in (
              "ASAN_OPTIONS: detect_leaks=1:halt_on_error=1", "UBSAN_OPTIONS: halt_on_error=1:print_stacktrace=1",
              "-DCMAKE_C_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer'",
              "-DCMAKE_CXX_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer'",
              "-DCMAKE_EXE_LINKER_FLAGS='-fsanitize=address,undefined'")),
          'authenticated sanitizer workflow keeps ASan, UBSan and leak detection')
    check(all('SKIP-PG' in text for text in native_logs.values()), 'PG integration explicitly skipped in both native logs')
    with tempfile.TemporaryDirectory(prefix='qbrain-n47l-evidence-') as temporary:
        temp = Path(temporary); stage = temp/'candidate'; stage.mkdir()
        for path, raw in source.items():
            target = stage/path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        inputs, output = temp/'inputs.json', temp/'validated-reports.json'
        inputs.write_text(json.dumps({'source_commit': source_sha, 'source_tree': tree, 'exe_sha256': exe_sha,
                                     'reports': report_data, 'native_logs': native_logs}), encoding='utf-8')
        # -I -S -B excludes working-directory, site and environment import hooks.
        child = subprocess.run([sys.executable, '-I', '-S', '-B', str(Path(__file__).resolve()),
                                '--_validate-reports', str(stage), str(inputs), str(output)],
                               cwd=temp, capture_output=True, timeout=90)
        require(child.returncode == 0, 'authenticated source validators failed: ' +
                child.stderr.decode('utf-8', errors='replace')[-4000:])
        summary = obj(read_file(output))
    checks.append('isolated original validators for all required old and new reports')
    checks.append('all 60 registered groups matched independently in N44 and N42')
    native = summary['report_summaries']['windows']
    for prefix, _, _, _ in MAPPING:
        key = prefix.replace('-', '_')
        unit, process = native[prefix+'-unit'], native[prefix+'-process']
        check(validation.get(key+'_scenarios') == unit['scenarios'] and
              validation.get(key+'_assertions') == unit['assertions'] and
              validation.get(key+'_process_checks') == process['checks'], 'actual report counts match package: ' + prefix)
    for prefix in ('promotion', 'hook-fact'):
        key = prefix.replace('-', '_') + '_install_checks_per_shell'
        check(type(validation.get(key)) is int and
              validation[key] == native[prefix+'-install51']['checks'] == native[prefix+'-install7']['checks'],
              'actual opt-in installer counts: ' + prefix)
    installer_counts = {}
    for name in ('install51.log', 'install7.log'):
        found = re.search(r'Native installer: (\d+) checks passed', archives['windows'][name].decode('utf-8-sig'))
        require(found is not None, 'installer summary missing: ' + name)
        installer_counts[name] = int(found[1])
    check(validation.get('installer_checks') == installer_counts and
          type(validation.get('additional_consent_checks_per_shell')) is int and
          validation['additional_consent_checks_per_shell'] == 16, 'native installer and consent summary counts')
    for key, actual in (
            ('fact_scenarios', native['fact-unit']['scenarios']),
            ('fact_unit_assertions', native['fact-unit']['assertions']),
            ('fact_process_checks', native['fact-process']['named_checks']),
            ('cjk_process_checks', native['cjk-process']['checks']),
            ('native_http_checks', native['http-transport']['checks']),
            ('retrieval_checks', native['retrieval']['checks']),
            ('embedding_wire_checks', native['embedding-wire']['checks']),
            ('queue_scenarios', native['embedding-queue']['scenarios']),
            ('queue_checks', native['embedding-queue']['checks'])):
        check(type(validation.get(key)) is int and validation[key] == actual, 'actual legacy count: ' + key)
    for name, text in (
            ('memory_cycle.log', '44 checks passed'), ('mcp_boundaries.log', '17 checks passed'),
            ('hooks.log', '69 passed'), ('context_process.log', '65 passed'), ('local-config.log', '6 checks passed'),
            ('install51.log', '69 checks passed'), ('install7.log', '69 checks passed'),
            ('transport51.log', '8 checks passed'), ('transport7.log', '8 checks passed'),
            ('consent51.log', '16 checks passed'), ('consent7.log', '16 checks passed'),
            ('embedding-search.log', 'N46D production search: 11 checks passed'),
            ('embedding-unit.log', 'N46D embedding contracts: 65 checks passed')):
        check(text in archives['windows'][name].decode('utf-8-sig'), 'retained native regression log: ' + name)
    check('N47C fact recall: 15 scenarios, 330 checks passed' in archives['sanitizer']['prior-recall.log'].decode('utf-8-sig'),
          'sanitizer retains original recall suite')
    return {'result': 'PASS', 'scope': 'Offline pinned CI artifact readback; no new native run or source-code approval',
            'repository': REPOSITORY, 'source_commit': source_sha, 'source_tree': tree,
            'metadata_sha256': metadata_sha, 'workflow_runs': run_ids,
            'source_file_count': len(source), 'check_count': len(checks), 'checks': checks,
            **summary, 'package': {'bytes': len(package), 'sha256': package_sha, 'manifest_files': len(mapping)},
            'exe': {'bytes': len(files['qbrain.exe']), 'sha256': exe_sha},
            'artifact_ids': {name: pin['id'] for name, pin in meta['artifacts'].items()},
            'probe_binaries_separately_downloaded': False, 'run_metadata_requeried_by_verifier': False,
            'product_executed_by_verifier': False, 'published_by_verifier': False,
            'signed': False, 'live_host_model_consumption_verified': False, 'postgres_integration_verified': False}


def main():
    # Worker results are intermediate data only; this branch cannot certify a candidate.
    if len(sys.argv) == 5 and sys.argv[1] == '--_validate-reports':
        validator_worker(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--metadata-sha256', required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--source-tree', required=True)
    parser.add_argument('--n44-run', type=int, required=True)
    parser.add_argument('--n42-run', type=int, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('report must be a new path')
    result = verify(args.source, args.artifacts, args.metadata, args.metadata_sha256,
                    args.source_sha, args.source_tree, {'n44': args.n44_run, 'n42': args.n42_run})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False); stream.write('\n')
    print(json.dumps({'result': result['result'], 'source_commit': result['source_commit'],
                      'checks': result['check_count'], 'N47L': result['report_summaries']['windows']['multiterm-process']}))


if __name__ == '__main__':
    main()
