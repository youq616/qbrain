"""Offline trust-boundary regressions using explicitly supplied real CI fixtures."""
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
import zipfile

import verify_candidate as v


def zipped(files):
    result = io.BytesIO()
    with zipfile.ZipFile(result, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
    return result.getvalue()


class ParsingTests(unittest.TestCase):
    def test_json_ambiguity_and_nonfinite_rejected(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}',
                    b'{"x":-Infinity}', b'{"x":1e999}', b'{"x":-1e999}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                v.obj(raw)

    def test_zip_path_escape_and_collisions_rejected(self):
        for names in (('../outside',), ('/absolute',), ('x\\y',), ('C:x',), ('x/./y',),
                      ('x', 'x/y'), ('x', 'x/'), ('A.py', 'a.py')):
            with self.subTest(names=names), self.assertRaises(ValueError):
                v.unzip(zipped({name: b'bytes' for name in names}))

    def test_duplicate_and_symlink_zip_members_rejected(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w') as archive:
            archive.writestr('x', b'first')
            archive.writestr('x', b'second')
        with self.assertRaisesRegex(ValueError, 'duplicate archive'):
            v.unzip(out.getvalue())
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w') as archive:
            info = zipfile.ZipInfo('symlink'); info.external_attr = 0o120777 << 16
            archive.writestr(info, b'target')
        with self.assertRaisesRegex(ValueError, 'nonregular'):
            v.unzip(out.getvalue())

    def test_source_mode_changes_tree_identity(self):
        files = {'file': b'hello\n', 'nested/a': b'world\n'}
        normal = {'file': '100644', 'nested/a': '100644'}
        changed = dict(normal, file='100755')
        self.assertNotEqual(v.source_tree(files, normal), v.source_tree(files, changed))

    def test_package_mapping_is_literal_and_dynamic(self):
        raw = b"files={'qbrain.exe':binary,'new.py':root/'.ci/new.py'}\n"
        self.assertEqual(v.package_mapping(raw), {'qbrain.exe': ('binary', ''), 'new.py': ('source', '.ci/new.py')})
        for raw in (b"files={'qbrain.exe':binary,'qbrain.exe':binary}",
                    b"files={'qbrain.exe':__import__('os').system('bad')}"):
            with self.assertRaises(ValueError):
                v.package_mapping(raw)


class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = v.obj(v.read_file(ARGS.metadata))
        cls.source_sha = cls.original['source_commit']
        cls.tree = cls.original['source_tree']
        cls.runs = {key: row['id'] for key, row in cls.original['runs'].items()}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='qbrain-evidence-negative-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.artifacts = self.root/'artifacts'; self.artifacts.mkdir()
        self.meta = copy.deepcopy(self.original)
        self.meta_path = self.root/'metadata.json'

    def metadata(self):
        self.meta_path.write_text(json.dumps(self.meta), encoding='utf-8')
        return v.sha(self.meta_path.read_bytes())

    def validate_metadata(self):
        v.metadata_check(self.meta, self.source_sha, self.tree, self.runs)

    def copy_artifacts(self):
        for key in v.ARTIFACTS:
            shutil.copyfile(ARGS.artifacts/(key+'.zip'), self.artifacts/(key+'.zip'))

    def put_artifact(self, key, raw):
        (self.artifacts/(key+'.zip')).write_bytes(raw)
        self.meta['artifacts'][key].update(sha256=v.sha(raw), size_in_bytes=len(raw))

    def run_verify(self):
        return v.verify(ARGS.source, self.artifacts, self.meta_path, self.metadata(),
                        self.source_sha, self.tree, self.runs)

    def change_package(self, mutation):
        outer = v.unzip((self.artifacts/'package.zip').read_bytes())[0]
        files = v.unzip(outer['qbrain-windows-x64-development.zip'])[0]
        manifest = v.obj(files['MANIFEST.json']); mutation(files, manifest)
        files['MANIFEST.json'] = json.dumps(manifest).encode()
        raw = zipped(files)
        outer['qbrain-windows-x64-development.zip'] = raw
        outer['SHA256SUMS.txt'] = (v.sha(raw)+'  qbrain-windows-x64-development.zip\n').encode()
        self.put_artifact('package', zipped(outer))

    def test_authentic_fixture_passes(self):
        result = v.verify(ARGS.source, ARGS.artifacts, ARGS.metadata, v.sha(v.read_file(ARGS.metadata)),
                          self.source_sha, self.tree, self.runs)
        self.assertEqual(result['result'], 'PASS')
        self.assertEqual(set(result['native_groups']), {'n44', 'n42'})
        self.assertTrue(all(len(groups) == 60 for groups in result['native_groups'].values()))

    def test_run_source_repository_and_attempt_rejected(self):
        for path, key, value in (
                (('n44',), 'head_sha', '0'*40), (('n42',), 'repository', 'other/repo'),
                (('n44', 'jobs', 0), 'run_attempt', 99)):
            with self.subTest(path=path, key=key):
                self.meta = copy.deepcopy(self.original); node = self.meta['runs']
                for item in path:
                    node = node[item]
                node[key] = value
                with self.assertRaises(ValueError):
                    self.validate_metadata()

    def test_missing_job_and_artifact_wrong_run_rejected(self):
        self.meta['runs']['n44']['jobs'].pop(0)
        with self.assertRaises(ValueError): self.validate_metadata()
        self.meta = copy.deepcopy(self.original)
        self.meta['artifacts']['package']['run_id'] = self.runs['n42']
        with self.assertRaises(ValueError): self.validate_metadata()

    def test_fixed_metadata_and_external_digest_rejected(self):
        self.copy_artifacts(); self.metadata()
        with self.assertRaisesRegex(ValueError, 'metadata SHA'):
            v.verify(ARGS.source, self.artifacts, self.meta_path, '0'*64,
                     self.source_sha, self.tree, self.runs)
        with (self.artifacts/'source.zip').open('ab') as stream: stream.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'external artifact bytes'):
            self.run_verify()

    def test_wrong_source_tree_rejected(self):
        self.copy_artifacts(); self.meta['source_tree'] = '0'*40
        with self.assertRaisesRegex(ValueError, 'reconstructed Git tree'):
            v.verify(ARGS.source, self.artifacts, self.meta_path, self.metadata(),
                     self.source_sha, '0'*40, self.runs)

    def test_package_and_manifest_cannot_drop_same_member(self):
        self.copy_artifacts()
        def drop(files, manifest):
            name = 'verification/test_multiterm_process.py'
            del files[name]; del manifest['files'][name]
        self.change_package(drop)
        with self.assertRaisesRegex(ValueError, 'source-defined manifest'):
            self.run_verify()

    def test_package_report_must_match_windows_original_bytes(self):
        self.copy_artifacts()
        def change(files, manifest):
            name = 'verification/multiterm-process.json'
            files[name] += b'\n'
            manifest['files'][name] = {'bytes': len(files[name]), 'sha256': v.sha(files[name])}
        self.change_package(change)
        with self.assertRaisesRegex(ValueError, 'original Windows evidence bytes'):
            self.run_verify()

    def test_registered_group_missing_rejected(self):
        self.copy_artifacts()
        files = v.unzip((self.artifacts/'n42-windows.zip').read_bytes())[0]
        raw = files['windows-tests.log']; needle = b'[PASS] n47l_multiterm_recall'
        self.assertIn(needle, raw)
        files['windows-tests.log'] = raw.replace(needle, b'[OMITTED] n47l_multiterm_recall', 1)
        self.put_artifact('n42-windows', zipped(files))
        with self.assertRaisesRegex(ValueError, 'Native group evidence'):
            self.run_verify()

    def test_same_platform_process_binary_must_match(self):
        self.copy_artifacts()
        files = v.unzip((self.artifacts/'portable.zip').read_bytes())[0]
        process = v.obj(files['recall-process.json']); process['binary_sha256'] = '0'*64
        files['recall-process.json'] = json.dumps(process).encode()
        self.put_artifact('portable', zipped(files))
        with self.assertRaisesRegex(ValueError, 'wrong binary/script'):
            self.run_verify()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, required=True)
    ARGS, remaining = parser.parse_known_args()
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
