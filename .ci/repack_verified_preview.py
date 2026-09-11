"""Repack only documentation around an exact CI-verified development binary.

Network-free and fail-closed. Does not extract or execute the supplied archive.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

CODE = '5ee79dfd5ab2512f024fefc9054bd3da12d64f1f'
DOCS = '14a7708a69ef7ec475d7278a6e0043da75e30b0f'
RUN = 34616855167
ORIGINAL_ZIP_SHA = 'f0cd29eb823b0523ed3fe785b08624e043ec30a17aa44785af9762aef09fd1d9'
EXE_SHA = '3bd43e8a099d9b4136aa0b96bd941fed7366a320a09b8bd253a0f272194ecdf8'
DOC_GIT_SHA = 'f36e16a0799492f1f39ae3a4babe388ea9cfe4c3'
EVIDENCE_SHA = '9b2a45187495d04dd3b32f6d2d2cec00bc6d8436e3d621b9acf4c035801d744d'
ORIGINAL_FILES = frozenset({
    'qbrain.exe', 'LICENSE', 'THIRD-PARTY-NOTICES.md', 'WINDOWS-MEMORY.md',
    'QUICKSTART.zh-CN.md', 'scripts/Install-QbrainMemory.ps1',
    'scripts/Invoke-QbrainJson.ps1', 'verification/validation.json',
    'verification/benchmark.json', 'MANIFEST.json', 'README-FIRST.txt'})
DOC_NAME = 'WINDOWS-MEMORY.md'
README = ('Windows x64 unsigned development preview. Read QUICKSTART.zh-CN.md.\n'
          'Executable and script bytes are identical to native run 34616855167.\n'
          'WINDOWS-MEMORY.md corrects model-timeout documentation only.\n'
          'See verification/PROVENANCE.json and original-manifest.json.\n'
          'Do not use historical dist installers or infer full gbrain parity.\n').encode('utf-8')

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def repack(original: Path, document: Path, evidence: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError('Refusing to overwrite an existing delivery')
    data = original.read_bytes()
    if digest(data) != ORIGINAL_ZIP_SHA:
        raise ValueError('Original CI archive hash mismatch')
    with zipfile.ZipFile(original) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != ORIGINAL_FILES:
            raise ValueError('Unexpected archive names or duplicate entries')
        if sum(i.file_size for i in archive.infolist()) > 5 * 1024 * 1024:
            raise ValueError('Expanded archive exceeds expected limit')
        if archive.testzip() is not None:
            raise ValueError('Corrupt original archive')
        payload = {name: archive.read(name) for name in names}
    manifest = json.loads(payload['MANIFEST.json'])
    if manifest.get('source_commit') != CODE or manifest.get('signed') is not False:
        raise ValueError('Original manifest does not identify the tested preview')
    expected = ORIGINAL_FILES - {'MANIFEST.json', 'README-FIRST.txt'}
    if set(manifest['files']) != expected:
        raise ValueError('Original manifest coverage mismatch')
    for name, metadata in manifest['files'].items():
        if digest(payload[name]) != metadata['sha256'] or len(payload[name]) != metadata['bytes']:
            raise ValueError('Original file verification failed: ' + name)
    if digest(payload['qbrain.exe']) != EXE_SHA:
        raise ValueError('Wrong native executable')
    corrected = document.read_bytes()
    corrected.decode('utf-8', errors='strict')
    if hashlib.sha1(b'blob ' + str(len(corrected)).encode() + b'\0' + corrected).hexdigest() != DOC_GIT_SHA:
        raise ValueError('Documentation does not match the reviewed Git blob')
    if not (500 <= len(corrected) <= 20000) or b'60,000 ms timeout' not in corrected:
        raise ValueError('Expected bounded documentation correction is missing')
    result_bytes = evidence.read_bytes()
    result = json.loads(result_bytes)
    result_bytes = (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)+'\n').encode()
    if digest(result_bytes) != EVIDENCE_SHA:
        raise ValueError('Evidence content does not match the reviewed canonical JSON')
    if (result.get('tested_source_commit') != CODE or result.get('workflow_run') != RUN
            or result.get('native_result') != 'PASS' or result['binary']['sha256'] != EXE_SHA):
        raise ValueError('Evidence does not correspond to the verified binary')
    original_manifest = payload.pop('MANIFEST.json')
    payload['verification/original-manifest.json'] = original_manifest
    payload['verification/RESULT.json'] = result_bytes
    payload[DOC_NAME] = corrected
    payload['README-FIRST.txt'] = README
    provenance = {
        'format_version': 1, 'repository': 'youq616/qbrain',
        'tested_source_commit': CODE, 'documentation_commit': DOCS,
        'workflow_run': RUN, 'original_ci_zip_sha256': ORIGINAL_ZIP_SHA,
        'executable_sha256': EXE_SHA,
        'changed_original_members': [DOC_NAME, 'README-FIRST.txt', 'MANIFEST.json'],
        'executable_and_scripts_unchanged': True, 'documentation_only_repack': True,
        'signed': False, 'live_host_model_consumption_verified': False,
    }
    payload['verification/PROVENANCE.json'] = (json.dumps(provenance, ensure_ascii=False, indent=2)+'\n').encode()
    new_manifest = {**provenance, 'files': {
        name: {'bytes': len(content), 'sha256': digest(content)}
        for name, content in sorted(payload.items())}}
    payload['MANIFEST.json'] = (json.dumps(new_manifest, ensure_ascii=False, indent=2)+'\n').encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Fixed member order, timestamps and attributes allow byte-identical replay.
    try:
        with output.open('xb') as stream, zipfile.ZipFile(stream, 'w') as archive:
            for name, content in sorted(payload.items()):
                info = zipfile.ZipInfo(name, date_time=(2026, 9, 11, 15, 44, 34))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, content, compresslevel=9)
        with zipfile.ZipFile(output) as archive:
            if archive.testzip() is not None or set(archive.namelist()) != set(payload):
                raise ValueError('Repacked archive verification failed')
            for name, content in payload.items():
                if archive.read(name) != content:
                    raise ValueError('Repacked member changed: ' + name)
            with zipfile.ZipFile(original) as original_archive:
                for name in ORIGINAL_FILES - set(provenance['changed_original_members']):
                    if archive.read(name) != original_archive.read(name):
                        raise ValueError('Unexpected product change: ' + name)
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return {'file': output.name, 'bytes': output.stat().st_size,
            'sha256': digest(output.read_bytes()), 'binary_sha256': EXE_SHA,
            'native_run': RUN, 'source_commit': CODE, 'documentation_commit': DOCS}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--document', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(repack(args.original, args.document, args.evidence, args.output), indent=2))

if __name__ == '__main__':
    main()
