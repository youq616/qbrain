"""Offline, disposable Git repositories; no GitHub authentication/network."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/handoff/export_n46f_source.py'
spec = importlib.util.spec_from_file_location('exporter', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def run(repo, *args):
    p = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, check=True)
    return p.stdout.decode().strip()


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='qbrain-handoff-unit-')
        self.root = Path(self.temporary.name)
        self.repo = self.root / 'source'
        self.repo.mkdir()
        run(self.repo, 'init', '-q')
        run(self.repo, 'config', 'user.name', 'Synthetic fixture')
        run(self.repo, 'config', 'user.email', 'fixture@example.invalid')
        run(self.repo, 'config', 'commit.gpgsign', 'false')
        run(self.repo, 'config', 'core.autocrlf', 'false')
        run(self.repo, 'remote', 'add', 'origin', 'https://github.com/youq616/qbrain.git')
        self.write('src/qbrain/search/hybrid.cpp', 'baseline\n')
        self.base = self.commit('baseline')
        run(self.repo, 'checkout', '-q', '-b', 'optimization/n46f-cjk-recall')
        self.write('docs/nodes/N46F-PLAN.md', 'Synthetic plan only.\n')
        self.plan = self.commit('synthetic plan')
        self.write('src/qbrain/search/hybrid.cpp', 'synthetic change\n')
        self.write('.ci/test_cjk_recall.py', '# synthetic, not product test\n')
        self.tip = self.commit('synthetic implementation')
        self.output = self.root / 'out'

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, path, content):
        p = self.repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8')

    def commit(self, message):
        run(self.repo, 'add', '--all')
        run(self.repo, 'commit', '-qm', message)
        return run(self.repo, 'rev-parse', 'HEAD')

    def export(self):
        return m.export_source(self.repo, self.output, base=self.base,
                               commits=(self.plan, self.tip))

    def test_exact_commits_roundtrip_without_network(self):
        result = self.export()
        self.assertEqual(result['result'], 'SOURCE_EXPORTED')
        self.assertFalse(result['compiled'])
        self.assertFalse(result['uploaded'])
        self.assertEqual(result['commit_count'], 2)
        with zipfile.ZipFile(result['zip']) as z:
            self.assertEqual(set(z.namelist()), {'n46f.bundle', 'n46f.patch', 'manifest.json', 'README.txt'})
            self.assertIn(self.tip.encode(), z.read('n46f.patch'))
            manifest = json.loads(z.read('manifest.json'))
            for name, entry in manifest['files'].items():
                self.assertEqual(m.sha256(z.read(name)), entry['sha256'])
            bundle = self.root / 'import.bundle'
            bundle.write_bytes(z.read('n46f.bundle'))
        receiver = self.root / 'receiver'
        receiver.mkdir()
        run(receiver, 'init', '-q')
        run(receiver, 'fetch', '-q', str(self.repo), self.base)
        run(receiver, 'bundle', 'verify', str(bundle))
        run(receiver, 'fetch', '-q', str(bundle), m.BRANCH + ':refs/heads/imported')
        self.assertEqual(run(receiver, 'rev-parse', 'imported'), self.tip)
        self.assertEqual(run(self.repo, 'rev-parse', 'HEAD'), self.tip)
        self.assertEqual(run(self.repo, 'status', '--porcelain'), '')

    def test_dirty_worktree_preserved(self):
        self.write('note.txt', 'user-owned uncommitted\n')
        with self.assertRaisesRegex(m.HandoffError, 'uncommitted'):
            self.export()
        self.assertEqual((self.repo / 'note.txt').read_text(), 'user-owned uncommitted\n')
        self.assertFalse(self.output.exists())

    def test_changed_branch_not_reset(self):
        self.write('docs/nodes/N46F-PLAN.md', 'new work\n')
        newer = self.commit('extra work')
        with self.assertRaisesRegex(m.HandoffError, 'pinned N46F tip'):
            self.export()
        self.assertEqual(run(self.repo, 'rev-parse', 'HEAD'), newer)
        self.assertFalse(self.output.exists())

    def test_existing_destination_preserved(self):
        self.output.mkdir()
        (self.output / 'keep').write_text('keep')
        with self.assertRaisesRegex(m.HandoffError, 'already exists'):
            self.export()
        self.assertEqual((self.output / 'keep').read_text(), 'keep')

    def test_no_output_inside_worktree(self):
        self.output = self.repo / 'handoff-output'
        with self.assertRaisesRegex(m.HandoffError, 'outside'):
            self.export()
        self.assertFalse(self.output.exists())

    def test_wrong_remote_not_echoed(self):
        secret_url = 'https://synthetic-user:do-not-print@github.com/another/repo.git'
        run(self.repo, 'remote', 'set-url', 'origin', secret_url)
        with self.assertRaises(m.HandoffError) as caught:
            self.export()
        self.assertNotIn('do-not-print', str(caught.exception))
        self.assertFalse(self.output.exists())

    def test_unexpected_path_refused(self):
        self.write('private/auth.json', '{}')
        run(self.repo, 'add', '--all')
        run(self.repo, 'commit', '--amend', '--no-edit', '-q')
        self.tip = run(self.repo, 'rev-parse', 'HEAD')
        with self.assertRaisesRegex(m.HandoffError, 'Unexpected changed path'):
            self.export()
        self.assertFalse(self.output.exists())

    def test_private_key_pattern_refused(self):
        marker = '-----BEGIN ' + 'PRIVATE KEY-----'
        self.write('src/qbrain/search/hybrid.cpp', marker + '\nsynthetic\n')
        run(self.repo, 'add', '--all')
        run(self.repo, 'commit', '--amend', '--no-edit', '-q')
        self.tip = run(self.repo, 'rev-parse', 'HEAD')
        with self.assertRaisesRegex(m.HandoffError, 'credential/private key'):
            self.export()
        self.assertFalse(self.output.exists())

    def test_wrong_commit_range_refused(self):
        with self.assertRaisesRegex(m.HandoffError, 'Commit range'):
            m.export_source(self.repo, self.output, base=self.base, commits=(self.tip,))
        self.assertFalse(self.output.exists())

    def test_invalid_utf8_and_nul_refused(self):
        for data in (b'\xff', b'a\x00b'):
            with self.subTest(data=data), self.assertRaises(m.HandoffError):
                m.check_content(data)

    def test_binary_limit_checked(self):
        with self.assertRaisesRegex(m.HandoffError, 'limit'):
            m.check_content(b'x' * (m.MAX_SOURCE_BYTES + 1))

    def test_missing_commit_is_blocked_without_credentials(self):
        with self.assertRaises(m.HandoffError):
            m.export_source(self.repo, self.output, base='f' * 40,
                            commits=(self.plan, self.tip))
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
