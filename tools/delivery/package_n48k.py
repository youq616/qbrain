"""N48K fixed-source Windows integration bundle; build/verify offline, never publish.

The exact executable is not rewritten. ZIP assembly is deterministic, compiler
output is not claimed reproducible. Qualification binds the unchanged ZIP later.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import stat
import subprocess
import types
import zipfile

import build_integrated_n47r as z
from package_n47x import pe64

SOURCE = '24345f85e0c4962c93205a7fab0fbdb380a5ff09'
TREE = 'b9b5f8a50e34ca7b897c85b2490e0b61100ab756'
PRODUCT = 'qbrain-windows-x64-n48k-candidate.zip'
TOOLS = ('check_memory_task_run', 'inspect_hook_context', 'integration_model_ab',
         'memory_task_contract', 'model_ab', 'model_cost', 'run_memory_tasks',
         'score_memory_tasks', 'test_memory_metrics', 'test_memory_tasks',
         'test_model_ab', 'test_model_cost', 'test_model_framing', 'test_model_projection')
GUIDES = ('INSTALLER-RECOVERY', 'TASK-EVALUATION', 'MODEL-COMPARISON', 'FACT-USAGE',
          'FACT-USAGE-AUDIT', 'CASE-SENSITIVE-PATHS', 'TRANSPORT-DIAGNOSTICS',
          'RECEIPT-INTEGRITY', 'USAGE-BATCHES', 'ISOLATED-MCP-CHECK', 'OPENCODE-LIFECYCLE',
          'TOKEN-COST', 'PROVIDER-USAGE-IMPORT', 'STREAM-USAGE-IMPORT',
          'PAIRED-COST-COMPARISON', 'MODEL-EXECUTION-COST')
EXAMPLES = ('import-three-providers.synthetic', 'stream-openai_chat',
            'stream-openai_responses', 'stream-anthropic_messages',
            'stream-unknown-cache', 'stream-rejected-truncated', 'compare-basic',
            'compare-shared-overhead', 'compare-failed-retry', 'compare-unknown',
            'compare-rejected-task', 'compare-zero-baseline', 'model-execution-rates.synthetic')
FILES = ('LICENSE', 'THIRD-PARTY-NOTICES.md', 'scripts/Install-QbrainMemory.ps1',
         'scripts/Invoke-QbrainJson.ps1') + tuple('tools/acceptance/'+s+'.py' for s in TOOLS) + tuple(
         'docs/integration/'+s+'.zh-CN.md' for s in GUIDES) + tuple('examples/cost/'+s+'.json' for s in EXAMPLES)
PROVENANCE_FIELDS = {'schema', 'source_commit', 'source_tree', 'binary_sha256',
                     'native_log_sha256', 'native_groups', 'live_pg_skipped',
                     'compiler_output_reproducible'}


def regular(path: Path, directory=False) -> Path:
    # Refuse aliases before canonicalizing. This is not an adversarial OS sandbox.
    path = path.absolute()
    for component in (*reversed(path.parents), path):
        info = component.lstat()
        z.need(not stat.S_ISLNK(info.st_mode) and not (getattr(info, 'st_file_attributes', 0) & 0x400), 'link input')
    info = path.stat()
    z.need(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode), 'input type')
    return path


def read(path: Path, cap=z.MAX_FILE) -> bytes:
    regular(path)
    return z.read(path, cap)


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE, timeout=45)


def source_files(root: Path) -> dict[str, bytes]:
    regular(root, True)
    z.need(git(root, 'rev-parse', 'HEAD').decode().strip() == SOURCE, 'wrong product commit')
    z.need(git(root, 'rev-parse', 'HEAD^{tree}').decode().strip() == TREE, 'wrong product tree')
    z.need(git(root, 'diff', '--name-only', 'HEAD') == b'', 'dirty tracked product source')
    result = {}
    for name in FILES:
        regular(root / name)
        canonical = git(root, 'show', SOURCE+':'+name)
        canonical.decode('utf-8')
        z.need(b'\r' not in canonical and 0 < len(canonical) <= z.MAX_FILE, 'canonical source bytes')
        working = read(root / name)
        z.need(working in (canonical, canonical.replace(b'\n', b'\r\n')), 'working source mismatch')
        result[name] = canonical.replace(b'\n', b'\r\n') if name.endswith('.ps1') else canonical
    return result


def receipt(root: Path, binary: bytes, log: bytes) -> dict:
    # source_files must have checked the fixed product identity before this call.
    validator = types.ModuleType('fixed_native_validator')
    raw = git(root, 'show', SOURCE+':.ci/validate_native_log.py')
    exec(compile(raw, '<fixed-native-validator>', 'exec'), validator.__dict__)
    registry = git(root, 'show', SOURCE+':tests/test_main.cpp').decode()
    text = log.decode('utf-8-sig')
    groups = validator.verified_groups(registry, text, 60)
    z.need('BUILD_OK' in text, 'production build completion missing')
    return dict(schema='qbrain-n48k-build-v1', source_commit=SOURCE, source_tree=TREE,
                binary_sha256=z.sha(binary), native_log_sha256=z.sha(log), native_groups=groups,
                live_pg_skipped='SKIP-PG' in text, compiler_output_reproducible=False)


def expected(binary: bytes, files: dict[str, bytes], guide: bytes, build: dict) -> dict[str, bytes]:
    pe64(binary)
    z.need(set(files) == set(FILES), 'payload membership')
    for name, raw in files.items():
        z.windows_path(name)
        z.need(type(raw) is bytes and 0 < len(raw) <= z.MAX_FILE, 'payload bytes')
        raw.decode('utf-8')
    z.need(type(build) is dict and set(build) == PROVENANCE_FIELDS, 'build fields')
    z.need(build['schema'] == 'qbrain-n48k-build-v1' and build['source_commit'] == SOURCE and
           build['source_tree'] == TREE and build['binary_sha256'] == z.sha(binary), 'build identity')
    z.need(isinstance(build['native_log_sha256'], str) and re.fullmatch('[0-9a-f]{64}', build['native_log_sha256']), 'log identity')
    groups = build['native_groups']
    z.need(type(groups) is list and len(groups) == 60 and all(type(s) is str and re.fullmatch('[a-z0-9_]+', s) for s in groups)
           and len(set(groups)) == 60, 'native group inventory')
    z.need(type(build['live_pg_skipped']) is bool and build['compiler_output_reproducible'] is False, 'build scope')
    z.need(type(guide) is bytes and 0 < len(guide) <= 32768, 'guide bounds')
    guide.decode('utf-8')
    contents = {**files, 'qbrain.exe': binary, 'START-HERE.zh-CN.md': guide, 'BUILD-PROVENANCE.json': z.encoded(build)}
    contents['MANIFEST.json'] = z.encoded(dict(schema='qbrain-n48k-package-v1', product_source=SOURCE,
        product_tree=TREE, binary_sha256=z.sha(binary), files=z.inventory(contents),
        status='BUILT_NOT_YET_ACCEPTED', native_bundle_tests='NOT_RUN', signed=False, stable_v1=False,
        status_scope='Construction only. A later external receipt must bind this unchanged ZIP SHA256.'))
    return contents


def verify(raw: bytes, wanted: dict[str, bytes]) -> dict:
    actual = z.archive_files(raw)  # inspect names, types, limits BEFORE any extraction
    z.need(actual == wanted, 'package differs from independent build inputs')
    z.need(raw == z.make_zip(wanted), 'noncanonical ZIP container')
    manifest = z.obj(actual['MANIFEST.json'])
    z.need(manifest['files'] == z.inventory({k:v for k,v in actual.items() if k != 'MANIFEST.json'}), 'manifest mismatch')
    return dict(schema='qbrain-n48k-package-check-v1', result='PACKAGE_FILES_VERIFIED',
                product_source=SOURCE, product_tree=TREE, sha256=z.sha(raw), bytes=len(raw),
                members=len(actual), binary_sha256=z.sha(actual['qbrain.exe']), new_product_execution=False)


def save(output: Path, wanted: dict[str, bytes]) -> dict:
    regular(output.parent, True)
    raw = z.make_zip(wanted)
    result = verify(raw, wanted)
    output.mkdir(exist_ok=False)  # no overwrite; I/O interruption may leave partial output
    for name, body in ((PRODUCT, raw), ('PACKAGE-CHECK.json', z.encoded(result)),
                       ('SHA256SUMS.txt', (result['sha256']+'  '+PRODUCT+'\n').encode())):
        with (output/name).open('xb') as stream:
            stream.write(body)
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'binary', 'native-log', 'guide'):
        p.add_argument('--'+name, type=Path, required=True)
    selection = p.add_mutually_exclusive_group(required=True)
    selection.add_argument('--output', type=Path)
    selection.add_argument('--verify', type=Path)
    a = p.parse_args()
    try:
        files = source_files(a.source)
        binary, log, guide = read(a.binary), read(a.native_log), read(a.guide, 32768)
        wanted = expected(binary, files, guide, receipt(a.source, binary, log))
        # Catch ordinary concurrent input changes before output publication.
        z.need(source_files(a.source) == files and read(a.binary) == binary and
               read(a.native_log) == log and read(a.guide, 32768) == guide, 'build inputs changed')
        result = verify(read(a.verify, z.MAX_ARCHIVE), wanted) if a.verify else save(a.output, wanted)
        print(z.encoded(result).decode(), end='')
        return 0
    except (OSError, ValueError, KeyError, TypeError, struct_error, zipfile.BadZipFile, subprocess.SubprocessError):
        print('{"result":"REJECTED","error":"n48k_package_input_or_io"}')
        return 2


# PE header helpers can report struct.error for deliberately malformed fixtures.
from struct import error as struct_error
if __name__ == '__main__':
    raise SystemExit(main())
