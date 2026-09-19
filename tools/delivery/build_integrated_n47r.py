"""Build/verify the fixed N47R *local* integration candidate, without network I/O.

This archive is repackaged, not a new executable build. Independent component
pins (not the archive's own manifest) are the verification authority. Publication
and native bundle acceptance are deliberately NOT claimed by this tool.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import stat
from pathlib import Path
import zipfile

BASE_SHA = 'ec681a4599bf1b2a90f3848f5bf65b6d6a32e37254f32392d0709c43080b356c'
BASE_BYTES = 2117939
EXE_SHA = 'c35fadde8c8356b7243bf0b34cfd5c836bda27bb46da87eddcc79c1031bf05b5'
INSTALLER_LF = 'bde21f5c1aabb7b517a1324f3fb076b482a5652387eaab26a1050bb0feb97dd2'
INSTALLER_CRLF = 'd802c230d2e5b0938b81baa115d5cf5b475aa855fce0df28f0305f00575fcc51'
NAME = 'qbrain-windows-x64-n47r-candidate.zip'
MAX_ARCHIVE = 32 * 1024 * 1024
MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_MEMBERS = 160
COMPONENTS = {
    'runtime': 'c26ec5e512d9ba960b86c9ced5b9b4976b031f2c',
    'installer': '9feed7c74926d53a7b2a7b21391af02275799f51',
    'evaluation': '11c7da219ee65d6aa387acbad6e07c0fb8acf090',
}
# These are Git/LF contents; only explicitly verified LF <-> CRLF is accepted.
PINS = {
    'tools/acceptance/run_memory_tasks.py': 'f8a18fa7a63c7afb4eeb4bb2b05c0c49add7f40ed5399cdbd599592fd56355dc',
    'tools/acceptance/memory_task_contract.py': '7d89bd2843c077a67dcb9651d8336931d3cc3ed5564ae2bc4810ca0fa5f73b63',
    'tools/acceptance/check_memory_task_run.py': 'b0047f21c06078be0558b153fcff9c49b08f95749982f285a18b16f6a0bf7a9e',
    'tools/acceptance/score_memory_tasks.py': 'f55ff1085b54353f57fd514f23a56884fff654224af2da331f6241538279c6a5',
    'tools/acceptance/test_memory_tasks.py': 'ed3916c5748ccb9cea867437f87769a59e1350d596ebe9740053869bf9f23d55',
    'tools/acceptance/test_memory_metrics.py': '9833987b2cb7f62523a22aac50802c478b7bab29861e6e566ca67e4bf54e229a',
    'docs/integration/INSTALLER-RECOVERY.zh-CN.md': 'fa7616c9abbadc471d59213f218dc845576bec559ad7d5b19db74f0cd2dad719',
}
GUIDE_PATH = 'docs/integration/INTEGRATED-PREVIEW.zh-CN.md'
GUIDE_SHA = '7db4673720d68d902555f72bbe778b0da3045c4c3b02cefa3717e3843b9e9b46'


def need(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + '\n').encode('utf-8')


def obj(raw: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError('nonfinite JSON')
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                       parse_constant=nonfinite)
    need(isinstance(value, dict), 'JSON object required')
    return value


def read(path: Path, limit: int = MAX_FILE) -> bytes:
    need(path.is_file() and not path.is_symlink(), 'regular input file required')
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    need(len(raw) <= limit, 'input exceeds byte cap')
    return raw


def windows_path(name: str) -> list[str]:
    need(bool(name) and len(name) <= 240 and name.isascii(), 'noncanonical member name')
    parts = name.split('/')
    for part in parts:
        need(part not in ('', '.', '..') and part == part.rstrip(' .'), 'unsafe path component')
        need(not re.search(r'[\x00-\x1f\x7f\\:"<>|?*]', part), 'unsafe Windows member name')
        need(not re.fullmatch(r'CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]',
                             part.split('.')[0], re.I), 'Windows reserved name')
    return parts


def archive_files(raw: bytes) -> dict[str, bytes]:
    """Inspect all names/types/sizes before reading any member; never extract here."""
    need(len(raw) <= MAX_ARCHIVE, 'archive byte cap')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        need(0 < len(infos) <= MAX_MEMBERS, 'archive member cap')
        names = set()
        all_parts = []
        total = 0
        for info in infos:
            need(info.orig_filename == info.filename, 'truncated member name')
            parts = windows_path(info.filename)
            key = info.filename.casefold()
            need(key not in names, 'duplicate or case-colliding member')
            names.add(key)
            all_parts.append(parts)
            mode = (info.external_attr >> 16) & 0xffff
            need(stat.S_IFMT(mode) in (0, stat.S_IFREG) and not info.is_dir(), 'non-regular archive member')
            need(not (info.flag_bits & 1), 'encrypted member')
            need(info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'unsupported compression')
            need(0 <= info.file_size <= MAX_FILE, 'member size cap')
            total += info.file_size
        need(total <= MAX_TOTAL, 'expanded archive cap')
        for parts in all_parts:
            for end in range(1, len(parts)):
                need('/'.join(parts[:end]).casefold() not in names, 'file-directory collision')
        out = {}
        for info in infos:
            with archive.open(info) as stream:
                body = stream.read(MAX_FILE + 1)
            need(len(body) == info.file_size and len(body) <= MAX_FILE, 'member size mismatch')
            out[info.filename] = body
        return out


def pinned_lf(path: Path, expected: str) -> bytes:
    raw = read(path)
    normalized = raw.replace(b'\r\n', b'\n')
    # Refuse mixed endings, stray CR, BOM, whitespace or other normalization.
    need(raw in (normalized, normalized.replace(b'\n', b'\r\n')), 'mixed text newlines')
    need(sha(normalized) == expected, 'source component hash mismatch: ' + path.name)
    return normalized


def inventory(files: dict[str, bytes]) -> dict:
    return {name: {'bytes': len(raw), 'sha256': sha(raw)} for name, raw in sorted(files.items())}


def expected_files(base: Path, source: Path, support: Path) -> dict[str, bytes]:
    raw = read(base, MAX_ARCHIVE)
    need(len(raw) == BASE_BYTES and sha(raw) == BASE_SHA, 'not the pinned original N47O ZIP')
    files = archive_files(raw)
    original_manifest = obj(files['MANIFEST.json'])
    listed = original_manifest.get('files')
    need(isinstance(listed, dict) and len(listed) == 73, 'original manifest count')
    need(set(files) == set(listed) | {'MANIFEST.json', 'README-FIRST.txt'}, 'original membership')
    need(listed == inventory({k: files[k] for k in listed}), 'original manifest mismatch')
    need(original_manifest.get('source_commit') == COMPONENTS['runtime']
         and original_manifest.get('binary_sha256') == EXE_SHA
         and sha(files['qbrain.exe']) == EXE_SHA, 'original EXE/source identity')
    files['provenance/N47O-MANIFEST.json'] = files.pop('MANIFEST.json')
    files['provenance/N47O-README-FIRST.txt'] = files.pop('README-FIRST.txt')
    installer = pinned_lf(source / 'scripts/Install-QbrainMemory.ps1', INSTALLER_LF).replace(b'\n', b'\r\n')
    need(sha(installer) == INSTALLER_CRLF, 'installer is not the native-tested representation')
    files['scripts/Install-QbrainMemory.ps1'] = installer
    for path, expected in PINS.items():
        dest = Path(path).name if path.startswith('docs/') else path
        need(dest not in files, 'unexpected component collision')
        files[dest] = pinned_lf(source / path, expected)
    guide = pinned_lf(support / GUIDE_PATH, GUIDE_SHA)
    files['START-HERE.zh-CN.md'] = guide
    files['README-FIRST.txt'] = (
        'N47R INTEGRATED WINDOWS DEVELOPMENT PREVIEW CANDIDATE\r\n'
        'Read START-HERE.zh-CN.md; require a matching release/evidence receipt.\r\n'
        'MANIFEST status fields describe construction time, not later acceptance.\r\n'
        'EXE unchanged; installer updated; ZIP repackaged.\r\n'
        'Historical original manifest/README are in provenance/.\r\n'
    ).encode('ascii')
    manifest = {
        'schema': 'qbrain-n47r-integrated-candidate-v1', 'components': COMPONENTS,
        'base_archive_sha256': BASE_SHA, 'exe_sha256': EXE_SHA,
        'installer_sha256': INSTALLER_CRLF, 'repackaged': True,
        'exe_recompiled': False, 'native_bundle_tests': 'NOT_RUN',
        'model_answers': 'NOT_RUN', 'live_client_acceptance': 'NOT_RUN',
        'signed': False, 'published': False, 'status_scope': 'construction-time only; later acceptance requires an external receipt bound to the ZIP digest', 'files': inventory(files),
    }
    files['MANIFEST.json'] = encoded(manifest)
    return files


def make_zip(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, raw in sorted(files.items()):
            windows_path(name)
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, raw)
    return output.getvalue()


def verify(raw: bytes, expected: dict[str, bytes]) -> dict:
    actual = archive_files(raw)
    need(actual == expected, 'candidate differs from independently pinned expected components')
    need(raw == make_zip(expected), 'noncanonical archive bytes or metadata')
    m = obj(actual['MANIFEST.json'])
    need(m['files'] == inventory({k: v for k, v in actual.items() if k != 'MANIFEST.json'}), 'integration manifest mismatch')
    return {
        'result': 'LOCAL_BUNDLE_VERIFIED', 'sha256': sha(raw), 'bytes': len(raw),
        'members': len(actual), 'manifest_members': len(m['files']),
        'components': dict(COMPONENTS), 'exe_sha256': EXE_SHA,
        'installer_sha256': INSTALLER_CRLF, 'native_bundle_tests': 'NOT_RUN',
        'published': False, 'repackaged': True, 'exe_recompiled': False,
    }


def build(base: Path, source: Path, support: Path, output: Path) -> dict:
    # Complete all input validation before creating the output directory.
    expected = expected_files(base, source, support)
    raw = make_zip(expected)
    result = verify(raw, expected)
    output.mkdir(parents=True, exist_ok=False)
    for name, data in ((NAME, raw), ('LOCAL-VERIFICATION.json', encoded(result)),
                       ('SHA256SUMS.txt', (sha(raw) + '  ' + NAME + '\n').encode('ascii'))):
        with (output / name).open('xb') as stream:
            stream.write(data)
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'source', 'support'):
        p.add_argument('--' + name, type=Path, required=True)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--output', type=Path)
    group.add_argument('--verify', type=Path, dest='candidate')
    a = p.parse_args()
    try:
        if a.candidate:
            result = verify(read(a.candidate, MAX_ARCHIVE), expected_files(a.base, a.source, a.support))
        else:
            result = build(a.base, a.source, a.support, a.output)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        print(json.dumps({'result': 'REJECTED', 'error_type': type(error).__name__, 'reason': str(error)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
