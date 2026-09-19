"""Adversarial tests of the local N47R builder and independently pinned contents."""
from __future__ import annotations
import argparse
import copy
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import warnings
import zipfile

import build_integrated_n47r as b


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = b.expected_files(ARGS.base, ARGS.source, ARGS.support)
        cls.raw = b.make_zip(cls.expected)
        cls.old = b.archive_files(ARGS.base.read_bytes())

    def mutated(self, name, value, recompute=False):
        files = dict(self.expected)
        files[name] = value
        if recompute:
            manifest = b.obj(files['MANIFEST.json'])
            manifest['files'] = b.inventory({k: v for k, v in files.items() if k != 'MANIFEST.json'})
            files['MANIFEST.json'] = b.encoded(manifest)
        return b.make_zip(files)

    def test_positive_deterministic_and_flags(self):
        report = b.verify(self.raw, self.expected)
        self.assertEqual(self.raw, b.make_zip(dict(reversed(list(self.expected.items())))))
        self.assertEqual(report['members'], 85)
        self.assertEqual(report['manifest_members'], 84)
        self.assertEqual(report['native_bundle_tests'], 'NOT_RUN')
        self.assertIs(report['published'], False)
        self.assertIs(report['repackaged'], True)
        self.assertIs(report['exe_recompiled'], False)

    def test_retained_members_equal_original(self):
        for name, raw in self.old.items():
            if name not in ('scripts/Install-QbrainMemory.ps1', 'MANIFEST.json', 'README-FIRST.txt'):
                self.assertEqual(self.expected[name], raw, name)
        self.assertEqual(self.expected['provenance/N47O-MANIFEST.json'], self.old['MANIFEST.json'])
        self.assertEqual(self.expected['provenance/N47O-README-FIRST.txt'], self.old['README-FIRST.txt'])

    def test_new_installer_is_exact_windows_tested_bytes(self):
        raw = self.expected['scripts/Install-QbrainMemory.ps1']
        self.assertEqual(b.sha(raw), b.INSTALLER_CRLF)
        self.assertEqual(b.sha(raw.replace(b'\r\n', b'\n')), b.INSTALLER_LF)
        self.assertNotEqual(raw, self.old['scripts/Install-QbrainMemory.ps1'])
        self.assertEqual(b.sha(self.expected['qbrain.exe']), b.EXE_SHA)

    def test_old_bundle_not_accepted_as_new(self):
        with self.assertRaises(ValueError): b.verify(ARGS.base.read_bytes(), self.expected)

    def test_tampering_rejected_even_with_recomputed_manifest(self):
        for name in ('qbrain.exe', 'scripts/Install-QbrainMemory.ps1',
                     'scripts/Invoke-QbrainJson.ps1', 'START-HERE.zh-CN.md',
                     'tools/acceptance/memory_task_contract.py'):
            for recompute in (False, True):
                with self.subTest(name=name, recompute=recompute):
                    old = self.expected[name]
                    raw = bytes([old[0] ^ 1]) + old[1:]
                    with self.assertRaises(ValueError):
                        b.verify(self.mutated(name, raw, recompute), self.expected)

    def test_old_installer_substitution_rejected(self):
        raw = self.mutated('scripts/Install-QbrainMemory.ps1', self.old['scripts/Install-QbrainMemory.ps1'], True)
        with self.assertRaises(ValueError): b.verify(raw, self.expected)

    def test_manifest_status_provenance_forgery_rejected(self):
        for field, value in (('native_bundle_tests', 'PASS'), ('published', True),
                             ('signed', True), ('repackaged', False), ('exe_recompiled', True)):
            with self.subTest(field=field):
                manifest = b.obj(self.expected['MANIFEST.json']); manifest[field] = value
                with self.assertRaises(ValueError):
                    b.verify(self.mutated('MANIFEST.json', b.encoded(manifest)), self.expected)
        manifest = b.obj(self.expected['MANIFEST.json']); manifest['components']['installer'] = 'a'*40
        with self.assertRaises(ValueError):
            b.verify(self.mutated('MANIFEST.json', b.encoded(manifest)), self.expected)

    def test_missing_and_extra_member_rejected(self):
        for kind in ('missing', 'extra'):
            files = dict(self.expected)
            if kind == 'missing': files.pop('LICENSE')
            else: files['tools/extra.py'] = b'print(1)'
            with self.assertRaises(ValueError): b.verify(b.make_zip(files), self.expected)

    def test_noncanonical_zip_comment_rejected(self):
        stream = io.BytesIO(self.raw)
        with zipfile.ZipFile(stream, 'a') as z: z.comment = b'changed metadata'
        with self.assertRaises(ValueError): b.verify(stream.getvalue(), self.expected)

    def test_bad_paths_rejected(self):
        bad = ('/root', '../escape', 'folder/../escape', './file', 'a//b', 'a\\b',
               'C:/drive', 'file:ads', 'a.', 'a ', 'NUL', 'CON.txt', 'com1.exe',
               'LPT9.doc', 'folder/', 'file\x00suffix', 'bad\x01file', 'dir/PRN',
               'a?b', 'a*b', 'a<b', 'a|b', '中文.txt')
        for name in bad:
            with self.subTest(name=name):
                with self.assertRaises(ValueError): b.windows_path(name)

    def test_safe_path_names(self):
        for name in ('scripts/Install-QbrainMemory.ps1', 'tools/acceptance/run_memory_tasks.py',
                     'START-HERE.zh-CN.md', 'provenance/N47O-MANIFEST.json', 'COM10.txt'):
            b.windows_path(name)

    def archive(self, entries):
        stream = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(stream, 'w') as z:
                for entry, body in entries: z.writestr(entry, body)
        return stream.getvalue()

    def test_duplicate_case_and_parent_collisions_rejected(self):
        for names in (('a', 'a'), ('LICENSE', 'license'), ('scripts', 'scripts/a.ps1'),
                      ('SCRIPTS', 'scripts/a.ps1')):
            with self.subTest(names=names):
                with self.assertRaises(ValueError):
                    b.archive_files(self.archive([(name, b'x') for name in names]))

    def test_symlink_and_directory_archive_entries_rejected(self):
        for mode in (0o120777, 0o040755):
            info = zipfile.ZipInfo('somefile'); info.create_system = 3; info.external_attr = mode << 16
            with self.assertRaises(ValueError): b.archive_files(self.archive([(info, b'target')]))
        with self.assertRaises(ValueError): b.archive_files(self.archive([('dir/', b'')]))

    def test_archive_caps_and_crc_rejected(self):
        many = self.archive([(f'file{i}', b'') for i in range(b.MAX_MEMBERS+1)])
        with self.assertRaises(ValueError): b.archive_files(many)
        raw = bytearray(self.archive([('one', b'UNIQUE_DATA_MARKER')]))
        raw[raw.index(b'UNIQUE_DATA_MARKER')] ^= 1
        with self.assertRaises(zipfile.BadZipFile): b.archive_files(bytes(raw))
        with self.assertRaises(ValueError): b.archive_files(b'0' * (b.MAX_ARCHIVE+1))

    def test_strict_json_rejects_duplicate_nonfinite_and_wrong_root(self):
        for raw in (b'{"files":1,"files":2}', b'{"x":NaN}', b'[]', b'null', b'\xff'):
            with self.subTest(raw=raw):
                with self.assertRaises((ValueError, UnicodeError)): b.obj(raw)

    def test_all_components_accept_exact_lf_crlf_only(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'file'
            for name, pin in b.PINS.items():
                raw = (ARGS.source/name).read_bytes().replace(b'\r\n', b'\n')
                path.write_bytes(raw); self.assertEqual(b.pinned_lf(path,pin),raw)
                path.write_bytes(raw.replace(b'\n',b'\r\n')); self.assertEqual(b.pinned_lf(path,pin),raw)
                path.write_bytes(raw.replace(b'\n',b'\r\n',1))
                with self.assertRaises(ValueError): b.pinned_lf(path,pin)
                path.write_bytes(b'\xef\xbb\xbf'+raw)
                with self.assertRaises(ValueError): b.pinned_lf(path,pin)

    def test_wrong_source_inputs_rejected_before_output_created(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in ('scripts/Install-QbrainMemory.ps1', *b.PINS):
                target=root/name; target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes((ARGS.source/name).read_bytes())
            target=root/'scripts/Install-QbrainMemory.ps1'
            target.write_bytes(self.old['scripts/Install-QbrainMemory.ps1'])
            with self.assertRaises(ValueError): b.build(ARGS.base,root,ARGS.support,root/'out')
            self.assertFalse((root/'out').exists())

    def test_wrong_base_and_support_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); base=root/'base.zip'; base.write_bytes(ARGS.base.read_bytes()+b'X')
            with self.assertRaises(ValueError): b.build(base,ARGS.source,ARGS.support,root/'out')
            guide=root/b.GUIDE_PATH;guide.parent.mkdir(parents=True);guide.write_bytes(b'fake')
            with self.assertRaises(ValueError): b.build(ARGS.base,ARGS.source,root,root/'out')
            self.assertFalse((root/'out').exists())

    def test_overwrite_refused_and_existing_bytes_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'out';root.mkdir();(root/'keep.txt').write_bytes(b'KEEP')
            with self.assertRaises(FileExistsError): b.build(ARGS.base,ARGS.source,ARGS.support,root)
            self.assertEqual((root/'keep.txt').read_bytes(),b'KEEP')
            self.assertEqual(set(p.name for p in root.iterdir()),{'keep.txt'})

    def test_entire_crlf_input_tree_produces_identical_archive(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in ('scripts/Install-QbrainMemory.ps1', *b.PINS):
                raw = (ARGS.source / name).read_bytes().replace(b'\r\n', b'\n')
                path = root / 'source' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw.replace(b'\n', b'\r\n'))
            path = root / 'support' / b.GUIDE_PATH
            path.parent.mkdir(parents=True)
            raw = (ARGS.support / b.GUIDE_PATH).read_bytes().replace(b'\r\n', b'\n')
            path.write_bytes(raw.replace(b'\n', b'\r\n'))
            expected = b.expected_files(ARGS.base, root/'source', root/'support')
            self.assertEqual(b.make_zip(expected), self.raw)

    def test_cli_returns_rejection_without_overwriting_output(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); out = root/'out'; out.mkdir()
            (out/'keep').write_bytes(b'KEEP')
            args = [sys.executable, str(Path(b.__file__)), '--base', str(ARGS.base),
                    '--source', str(ARGS.source), '--support', str(ARGS.support),
                    '--output', str(out)]
            result = subprocess.run(args, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)['result'], 'REJECTED')
            self.assertEqual((out/'keep').read_bytes(), b'KEEP')
            self.assertEqual(len(list(out.iterdir())), 1)

    def test_build_twice_and_verify_disk_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            first=b.build(ARGS.base,ARGS.source,ARGS.support,root/'one')
            second=b.build(ARGS.base,ARGS.source,ARGS.support,root/'two')
            self.assertEqual(first,second)
            self.assertEqual((root/'one'/b.NAME).read_bytes(),(root/'two'/b.NAME).read_bytes())
            self.assertEqual(b.verify((root/'one'/b.NAME).read_bytes(),self.expected),first)
            self.assertEqual((root/'one'/'SHA256SUMS.txt').read_text(), first['sha256']+'  '+b.NAME+'\n')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('base','source','support'): parser.add_argument('--'+name,type=Path,required=True)
    ARGS=parser.parse_args()
    unittest.main(argv=[sys.argv[0]],verbosity=2)
