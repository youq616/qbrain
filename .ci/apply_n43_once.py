"""One-use import of the owner's locally tested source patch; removed on success."""
import base64
import hashlib
import json
import lzma
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path.cwd()
BRANCH = 'optimization/n43-memory-cycle'
BASE = '258698aba8f3f53f4243d09fc19cb084a3ec2d3a'

def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

assert os.environ['GITHUB_REPOSITORY'] == 'youq616/qbrain'
assert os.environ['GITHUB_REF'] == 'refs/heads/' + BRANCH
assert git('rev-parse', 'HEAD') == os.environ['GITHUB_SHA']
assert git('rev-parse', 'HEAD^') == BASE
parts = [ROOT / '.ci/n43-import' / p for p in ['00.b64', '01.b64', '02.b64', '04.b64', '06.b64']]
encoded = ''.join(p.read_text(encoding='ascii') for p in parts)
assert len(encoded) == 46592
compressed = base64.b64decode(encoded, validate=True)
assert hashlib.sha256(compressed).hexdigest() == '74415f4c5409afe49174f3f20ef8fb1b07a388e70f618b024cf0105844c5be80'
decoder = lzma.LZMADecompressor(memlimit=268435456)
raw = decoder.decompress(compressed, max_length=127906)
assert decoder.eof and not decoder.unused_data and len(raw) == 127905
bundle = json.loads(raw)
allowed = set('''.ci/test_memory_cycle.py
.ci/test_windows_transport.ps1
.github/workflows/n43-validation.yml
CMakeLists.txt
docs/nodes/N43-PLAN-AUDIT.md
docs/nodes/N43-PLAN.md
docs/nodes/N43-USAGE.md
docs/nodes/N44A-PLAN-AUDIT.md
docs/nodes/N44A-PLAN.md
include/qbrain/ai/chat.hpp
include/qbrain/memory/session_memory.hpp
include/qbrain/ops/memory_ops.hpp
include/qbrain/util/paths.hpp
scripts/Invoke-QbrainJson.ps1
scripts/build-cl.ps1
scripts/build-tests-cl.ps1
src/qbrain/ai/chat.cpp
src/qbrain/cli/commands.cpp
src/qbrain/main.cpp
src/qbrain/mcp/server.cpp
src/qbrain/memory/session_memory.cpp
src/qbrain/ops/handlers.cpp
src/qbrain/ops/memory_ops.cpp
src/qbrain/util/hash.cpp
src/qbrain/util/paths.cpp
tests/test_main.cpp
tests/test_n31.cpp
tests/test_n43.cpp'''.splitlines())
assert set(bundle) == {'patch', 'files'} and set(bundle['files']) == allowed
for name, hashes in bundle['files'].items():
    path = ROOT / name
    assert not path.is_symlink() and path.resolve().is_relative_to(ROOT)
    assert not path.exists() if hashes['before'] is None else digest(path) == hashes['before'], name
with tempfile.TemporaryDirectory() as tmp:
    patch = Path(tmp) / 'source.patch'
    patch.write_bytes(bundle['patch'].encode('utf-8'))
    assert patch.stat().st_size == 118412
    subprocess.run(['git', 'apply', '--check', str(patch)], check=True)
    subprocess.run(['git', 'apply', str(patch)], check=True)
for name, hashes in bundle['files'].items():
    assert digest(ROOT / name) == hashes['after'], name
for path in parts:
    path.unlink()
(ROOT / '.ci/apply_n43_once.py').unlink()
(ROOT / '.github/workflows/apply-n43-once.yml').unlink()
git('config', 'user.name', 'github-actions[bot]')
git('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
git('add', '--all')
git('commit', '-m', 'feat(memory): add grounded session cycle and native Unicode transport')
remote = git('ls-remote', 'origin', 'refs/heads/' + BRANCH).split()[0]
assert remote == os.environ['GITHUB_SHA'], 'Branch changed; refusing to overwrite concurrent work'
git('push', 'origin', 'HEAD:refs/heads/' + BRANCH)
print('Applied and verified 28 source files; temporary importer removed; commit', git('rev-parse', 'HEAD'))
