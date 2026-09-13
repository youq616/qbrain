"""Acceptance tooling tests; never substitute these for Qbrain runtime tests."""
from __future__ import annotations
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prebuilt', ROOT / 'scripts/prebuilt_acceptance.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def encode(value):
    return json.dumps(value, sort_keys=True).encode()


def fixture(modifier=None, extra=(), duplicate=False, symlink=False):
    source = 'a' * 40
    binary = b'test bytes, not an executable'
    files = {'qbrain.exe': binary, 'scripts/Install-QbrainMemory.ps1': b'# synthetic',
             'scripts/Invoke-QbrainJson.ps1': b'# synthetic',
             'verification/validation.json': encode({'source_commit': source, 'result': 'PASS',
                                                      'binary_sha256': m.digest(binary)})}
    manifest = {'source_commit': source, 'result': 'PASS', 'binary_sha256': m.digest(binary),
                'files': {name: {'bytes': len(data), 'sha256': m.digest(data)} for name, data in files.items()}}
    if modifier:
        modifier(manifest, files)
    raw_manifest = encode(manifest)
    if duplicate:
        raw_manifest = b'{"result":"PASS",' + raw_manifest[1:]
    files.update({'MANIFEST.json': raw_manifest, 'README-FIRST.txt': b'test fixture'})
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            if symlink and name == 'qbrain.exe':
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                z.writestr(info, data)
            else:
                z.writestr(name, data)
        for name, data in extra:
            z.writestr(name, data)
    raw = out.getvalue()
    pin = {'source_commit': source, 'binary_sha256': m.digest(binary), 'archive_sha256': m.digest(raw)}
    return raw, pin, files


class PrebuiltTests(unittest.TestCase):
    def rejects(self, *args, **kwargs):
        raw, pin, _ = fixture(*args, **kwargs)
        with self.assertRaises((m.AcceptanceError, ValueError)):
            m.verify_bytes(raw, pin)

    def test_exact_fixture(self):
        raw, pin, files = fixture()
        self.assertEqual(m.verify_bytes(raw, pin), files)

    def test_outer_hash_is_trust_anchor(self):
        raw, pin, _ = fixture()
        pin['archive_sha256'] = '0' * 64
        with self.assertRaisesRegex(m.AcceptanceError, 'Archive SHA-256'):
            m.verify_bytes(raw, pin)

    def test_wrong_source(self):
        self.rejects(lambda j, f: j.update(source_commit='b' * 40))

    def test_binary_requires_external_pin(self):
        raw, pin, _ = fixture()
        pin['binary_sha256'] = '0' * 64
        with self.assertRaisesRegex(m.AcceptanceError, 'Executable SHA-256'):
            m.verify_bytes(raw, pin)

    def test_member_tampering(self):
        self.rejects(lambda j, f: f.update({'scripts/Invoke-QbrainJson.ps1': b'changed'}))

    def test_manifest_byte_count(self):
        self.rejects(lambda j, f: j['files']['qbrain.exe'].update(bytes=True))

    def test_manifest_inventory_required(self):
        self.rejects(lambda j, f: j['files'].pop('scripts/Install-QbrainMemory.ps1'))

    def test_extra_file(self):
        self.rejects(extra=[('unexpected.ps1', b'no')])

    def test_duplicate_json_keys(self):
        self.rejects(duplicate=True)

    def test_case_aliases(self):
        self.rejects(extra=[('QBRAIN.EXE', b'no')])

    def test_windows_unsafe_names(self):
        for name in ('../out', '/absolute', 'C:/file', 'x\\file', 'a//b',
                     'a/./b', 'a/../b', 'a/b.', 'a/CON.txt', 'NUL', 'COM1.exe',
                     'x:stream', 'a/space ', 'a\x00b'):
            with self.subTest(name=name), self.assertRaises(m.AcceptanceError):
                m.safe_member(name)

    def test_symlink_archive(self):
        self.rejects(symlink=True)

    def test_bounded_expansion(self):
        raw, pin, _ = fixture(extra=[('padding', b'0' * 20000)])
        self.assertLess(len(raw), 4000)
        with patch.object(m, 'MAX_BYTES', 4000), self.assertRaisesRegex(m.AcceptanceError, 'byte cap'):
            m.verify_bytes(raw, pin)

    def test_wrong_validation_source(self):
        def change(j, f):
            data = m.load_json(f['verification/validation.json'])
            data['source_commit'] = 'c' * 40
            f['verification/validation.json'] = encode(data)
            j['files']['verification/validation.json'] = {'bytes': len(encode(data)), 'sha256': m.digest(encode(data))}
        self.rejects(change)

    def test_wrong_validation_result(self):
        self.rejects(lambda j, f: j.update(result='FAIL'))

    def test_no_writes_on_invalid_package(self):
        with tempfile.TemporaryDirectory() as d:
            archive, output = Path(d) / 'bad.zip', Path(d) / 'out'
            archive.write_bytes(b'not the pinned archive')
            with self.assertRaises(m.AcceptanceError):
                m.prepare(archive, output, False)
            self.assertFalse(output.exists())

    def test_existing_destination_preserved(self):
        raw, _, files = fixture()
        with tempfile.TemporaryDirectory() as d:
            archive, output = Path(d) / 'test.zip', Path(d) / 'out'
            archive.write_bytes(raw)
            output.mkdir()
            (output / 'keep.txt').write_text('preserve')
            with patch.object(m, 'verify_bytes', return_value=files), self.assertRaises(m.AcceptanceError):
                m.prepare(archive, output, False)
            self.assertEqual((output / 'keep.txt').read_text(), 'preserve')

    def test_stage_does_not_claim_native_execution(self):
        raw, _, files = fixture()
        with tempfile.TemporaryDirectory() as d:
            archive, output = Path(d) / 'test.zip', Path(d) / 'out'
            archive.write_bytes(raw)
            with patch.object(m, 'verify_bytes', return_value=files):
                _, report = m.prepare(archive, output, False)
            self.assertEqual(report['counts'], dict(total=5, PASS=1, NOT_RUN=4, FAIL=0, SKIP=0, BLOCKED=0))
            self.assertFalse(report['real_agent_verified'])
            self.assertEqual((output / 'package/qbrain.exe').read_bytes(), files['qbrain.exe'])

    def test_summaries_derive_counts(self):
        records = [{'status': 'PASS'}] * 6 + [{'status': 'BLOCKED'}] * 10
        self.assertEqual(m.summarize(records)['total'], 16)
        with self.assertRaises(m.AcceptanceError):
            m.summarize([{'status': 'SOMETHING'}])

    def test_child_environment_only(self):
        original = {'PATH': 'unchanged', 'OPENAI_API_KEY': 'synthetic-not-real',
                    'qbrain_pg_dsn': 'synthetic', 'Home': 'old', 'LOCALAPPDATA': 'old',
                    'APPDATA': 'old', 'TEMP': 'old'}
        before = original.copy()
        env = m.isolated_environment(Path('/isolated'), original)
        self.assertEqual(original, before)
        self.assertNotIn('OPENAI_API_KEY', env)
        self.assertNotIn('qbrain_pg_dsn', env)
        self.assertNotIn('Home', env)
        self.assertEqual(env['LOCALAPPDATA'], str(Path('/isolated')))
        self.assertEqual(env['PATH'], 'unchanged')

    @unittest.skipIf(os.name == 'nt', 'Portable-only refusal check; native CI runs the actual EXE separately')
    def test_linux_cannot_claim_windows_smoke(self):
        with tempfile.TemporaryDirectory() as d:
            records, ok = m.run_smoke(Path(d) / 'missing.exe', Path(d))
            self.assertFalse(ok)
            self.assertEqual(records[0]['status'], 'BLOCKED')


if __name__ == '__main__':
    unittest.main(verbosity=2)
