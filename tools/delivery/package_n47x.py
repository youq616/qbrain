"""Package the fixed current product source. No network, installation or release.

Only ZIP assembly is reproducible; the compiler's binary bytes are not claimed
reproducible. Acceptance is an external receipt for the exact unchanged ZIP.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import re
import struct
import subprocess
import types

import build_integrated_n47r as z

SOURCE = 'b810d6898dcbbcd49bdbbed1d8473a3ac1c063e4'
TREE = '60dd02bc5bfe9c9298f5211d989237ac8262fbf7'
PRODUCT = 'qbrain-windows-x64-n47x-preview.zip'
TOOLS = ('check_memory_task_run', 'inspect_hook_context', 'integration_model_ab',
         'memory_task_contract', 'model_ab', 'run_memory_tasks', 'score_memory_tasks',
         'test_memory_metrics', 'test_memory_tasks', 'test_model_ab',
         'test_model_framing', 'test_model_projection')
GUIDES = ('INSTALLER-RECOVERY', 'TASK-EVALUATION', 'MODEL-COMPARISON', 'FACT-USAGE',
          'FACT-USAGE-AUDIT', 'CASE-SENSITIVE-PATHS', 'TRANSPORT-DIAGNOSTICS')
FILES = ('LICENSE', 'THIRD-PARTY-NOTICES.md', 'scripts/Install-QbrainMemory.ps1',
         'scripts/Invoke-QbrainJson.ps1') + tuple('tools/acceptance/'+s+'.py' for s in TOOLS) + tuple(
         'docs/integration/'+s+'.zh-CN.md' for s in GUIDES)


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE, timeout=45)


def source_files(root: Path) -> dict[str, bytes]:
    z.need(git(root, 'rev-parse', 'HEAD').decode().strip() == SOURCE, 'wrong product checkout')
    z.need(git(root, 'rev-parse', 'HEAD^{tree}').decode().strip() == TREE, 'wrong product tree')
    z.need(git(root, 'diff', '--name-only', 'HEAD') == b'', 'modified tracked product source')
    result = {}
    for name in FILES:
        raw = git(root, 'show', SOURCE+':'+name)
        # Git's canonical bytes are the authority, not the current line-ending policy.
        raw.decode('utf-8')
        z.need(b'\r' not in raw, 'unexpected canonical carriage return')
        result[name] = raw.replace(b'\n', b'\r\n') if name.endswith('.ps1') else raw
    return result


def pe64(raw: bytes) -> None:
    z.need(512 <= len(raw) <= z.MAX_FILE and raw[:2] == b'MZ', 'expected Windows executable')
    offset = struct.unpack_from('<I', raw, 60)[0]
    z.need(64 <= offset <= len(raw)-26 and raw[offset:offset+4] == b'PE\0\0', 'invalid PE header')
    z.need(struct.unpack_from('<H', raw, offset+4)[0] == 0x8664 and
           struct.unpack_from('<H', raw, offset+24)[0] == 0x20b, 'expected AMD64 PE32+')


def receipt(root: Path, binary: bytes, native_log: bytes) -> dict:
    # Load only the original validator from the already identity-checked Git source.
    module = types.ModuleType('fixed_native_validator')
    raw = git(root, 'show', SOURCE+':.ci/validate_native_log.py')
    exec(compile(raw, '<fixed-native-validator>', 'exec'), module.__dict__)
    registrations = git(root, 'show', SOURCE+':tests/test_main.cpp').decode()
    log = native_log.decode('utf-8-sig')
    groups = module.verified_groups(registrations, log, 60)
    z.need('BUILD_OK' in log, 'missing production build completion')
    return {'schema': 'qbrain-n47x-build-v1', 'source_commit': SOURCE, 'source_tree': TREE,
            'binary_sha256': z.sha(binary), 'native_log_sha256': z.sha(native_log),
            'native_groups': groups, 'live_pg_skipped': 'SKIP-PG' in log,
            'native_workflow_run': os.environ.get('GITHUB_RUN_ID'),
            'native_workflow_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
            'compiler_output_reproducible': False}


def expected(binary: bytes, files: dict[str, bytes], guide: bytes, provenance: dict) -> dict[str, bytes]:
    pe64(binary)
    z.need(set(files) == set(FILES), 'source membership')
    for name, raw in files.items():
        z.windows_path(name)
        z.need(isinstance(raw, bytes) and 0 < len(raw) <= z.MAX_FILE, 'source size/type')
    z.need(isinstance(provenance, dict) and provenance.get('schema') == 'qbrain-n47x-build-v1'
           and provenance.get('source_commit') == SOURCE and provenance.get('source_tree') == TREE
           and provenance.get('binary_sha256') == z.sha(binary), 'build identity')
    groups = provenance.get('native_groups')
    z.need(isinstance(groups, list) and len(groups) == 60 and len(set(groups)) == 60
           and all(isinstance(s, str) and re.fullmatch('[a-z0-9_]+', s) for s in groups), 'native group coverage')
    z.need(isinstance(guide, bytes) and 0 < len(guide) <= 32768, 'guide bounds')
    guide.decode('utf-8')
    contents = {**files, 'qbrain.exe': binary, 'START-HERE.zh-CN.md': guide,
                'BUILD-PROVENANCE.json': z.encoded(provenance)}
    manifest = {'schema': 'qbrain-n47x-package-v1', 'product_source': SOURCE,
                'product_tree': TREE, 'binary_sha256': z.sha(binary), 'files': z.inventory(contents),
                'status': 'BUILT_NOT_YET_ACCEPTED', 'native_bundle_tests': 'NOT_RUN',
                'signed': False, 'stable_v1': False,
                'status_scope': 'Construction time; later acceptance binds the unchanged ZIP hash.'}
    contents['MANIFEST.json'] = z.encoded(manifest)
    return contents


def verify(raw: bytes, wanted: dict[str, bytes]) -> dict:
    files = z.archive_files(raw)
    z.need(files == wanted, 'package differs from independently supplied source and binary')
    z.need(raw == z.make_zip(wanted), 'noncanonical ZIP metadata or trailing bytes')
    manifest = z.obj(files['MANIFEST.json'])
    z.need(manifest['files'] == z.inventory({k:v for k,v in files.items() if k != 'MANIFEST.json'}), 'manifest mismatch')
    return {'schema': 'qbrain-n47x-package-check-v1', 'result': 'PACKAGE_FILES_VERIFIED',
            'product_source': SOURCE, 'sha256': z.sha(raw), 'bytes': len(raw), 'members': len(files),
            'binary_sha256': z.sha(files['qbrain.exe']), 'new_product_execution': False}


def save(output: Path, wanted: dict[str, bytes]) -> dict:
    raw = z.make_zip(wanted); result = verify(raw, wanted)
    output.mkdir(parents=True, exist_ok=False)
    for name, value in ((PRODUCT, raw), ('PACKAGE-CHECK.json', z.encoded(result)),
                        ('SHA256SUMS.txt', (result['sha256']+'  '+PRODUCT+'\n').encode())):
        with (output/name).open('xb') as stream: stream.write(value)
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('source','binary','native-log','guide','output'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    try:
        files = source_files(a.source)
        binary = z.read(a.binary); log = z.read(a.native_log)
        result = save(a.output, expected(binary, files, z.read(a.guide), receipt(a.source, binary, log)))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(z.encoded({'result':'REJECTED','error_type':type(error).__name__}).decode()); return 2
    print(z.encoded(result).decode()); return 0


if __name__ == '__main__': raise SystemExit(main())
