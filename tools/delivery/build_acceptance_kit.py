"""Build a deterministic handoff kit around the exact tested EXE; no downloads."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
TAG = 'local-acceptance-n46e-v1'
HELPER_PINS = {
    'scripts/prebuilt_acceptance.py': 'ed2839531abc3702682d117e0fdd41c2ae7e1d3e82c093b112e7b2ce56adc876',
    'scripts/Start-QbrainPrebuiltAcceptance.ps1': '22e5fa7ae4091bbdddcd864cbcf0811159e93e95952407b92ff59061198c8a36',
    'tests/test_prebuilt_acceptance.py': 'a95700c6fd598669de0044a06b41e0c6a8c159927a8e425a03d51d1bab6eeda3',
}

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def build(product: Path, destination: Path) -> dict:
    files = {}
    for name, expected in HELPER_PINS.items():
        data = (ROOT / name).read_bytes()
        if sha(data) != expected:
            raise ValueError('Tested helper bytes changed: ' + name)
        files[name] = data
    spec = importlib.util.spec_from_file_location('pinned_prebuilt', ROOT / 'scripts/prebuilt_acceptance.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with product.open('rb') as stream:
        original = stream.read(module.MAX_BYTES + 1)
    module.verify_bytes(original)
    files['packages/qbrain-windows-x64-n46d-queuefix-464045e2.zip'] = original
    files['RUNBOOK.zh-CN.md'] = (ROOT / 'docs/integration/LOCAL-AGENT-RUNBOOK.zh-CN.md').read_bytes()
    metadata = {
        'repository': 'youq616/qbrain', 'release_tag': TAG,
        'helper_tested_commit': 'd1e1a4937489f25305765725f7a071fee90a47d6',
        'helper_workflow_run': 34749654838,
        'product_workflow_run': 34682889565,
        'product_source_commit': module.PIN['source_commit'],
        'product_archive_sha256': sha(original),
        'product_exe_sha256': module.PIN['binary_sha256'],
        'product_recompiled': False, 'local_agent_verified': False,
        'authenticode_signed': False,
        'files': {name: {'bytes': len(data), 'sha256': sha(data)} for name, data in files.items()},
    }
    provenance = (json.dumps(metadata, indent=2, sort_keys=True) + '\n').encode()
    files['PROVENANCE.json'] = provenance
    # Exclusive output. Fixed metadata + stored members are byte-deterministic
    # across platforms and zlib versions; no original executable is repacked.
    destination.mkdir(parents=True, exist_ok=False)
    archive = destination / 'qbrain-local-acceptance-kit.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            z.writestr(info, files[name])
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None or set(z.namelist()) != set(files):
            raise ValueError('Kit integrity failed')
        for name, data in files.items():
            if z.read(name) != data:
                raise ValueError('Kit readback mismatch')
    (destination / 'PROVENANCE.json').write_bytes(provenance)
    digest = sha(archive.read_bytes())
    (destination / 'SHA256SUMS.txt').write_text(digest + '  ' + archive.name + '\n', encoding='ascii')
    return {'sha256': digest, 'bytes': archive.stat().st_size, 'members': len(files)}

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--product', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    print(json.dumps(build(args.product, args.output)))
