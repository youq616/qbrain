"""Publisher state-machine/negative tests; no GitHub writes or model calls."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('delivery', Path(__file__).with_name('publish_reviewed_n47o.py'))
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)


class FakeGitHub:
    def __init__(self, fault=None):
        self.fault = fault; self.calls = []; self.tag = None; self.release = None
        self.next_id = 100; self.bytes = {}; self.downloads = 0; self.patches = 0

    def api(self, endpoint, method='GET', body=None, **kwargs):
        self.calls.append((method, endpoint, copy.deepcopy(body)))
        if endpoint.startswith('releases?'):
            if self.fault == 'existing': return [{'tag_name': p.TAG}]
            if self.fault == 'draft-page-two':
                return [{'tag_name': str(x)} for x in range(100)] if 'page=1' in endpoint else [{'tag_name': p.TAG, 'draft': True}]
            if self.fault == 'listing-error': raise RuntimeError('network unavailable')
            return []
        if endpoint.startswith('git/ref/tags/'):
            if self.fault == 'wrong-tag': return {'ref': 'refs/tags/' + p.TAG, 'object': {'type': 'commit', 'sha': 'wrong'}}
            return copy.deepcopy(self.tag)
        if endpoint == 'git/refs':
            self.tag = {'ref': body['ref'], 'object': {'sha': body['sha'], 'type': 'commit'}}
            return copy.deepcopy(self.tag)
        if endpoint == 'releases' and method == 'POST':
            self.release = {**body, 'id': 999, 'assets': []}
            if self.fault == 'bad-draft': self.release['prerelease'] = False
            return copy.deepcopy(self.release)
        if endpoint == 'releases/latest':
            return {'id': 999} if self.fault == 'latest' else None
        if endpoint.startswith('releases/'):
            if method == 'PATCH':
                self.patches += 1; self.release.update(body)
                if self.fault == 'wrong-public': self.release['target_commitish'] = 'wrong'
            return copy.deepcopy(self.release)
        raise AssertionError(endpoint)

    def upload(self, ident, path):
        self.calls.append(('POST', 'upload', path.name)); raw = path.read_bytes()
        self.next_id += 1
        row = {'id': self.next_id, 'name': path.name, 'size': len(raw), 'state': 'uploaded', 'digest': 'sha256:' + p.sha(raw)}
        if self.fault == 'no-digest': row.pop('digest')
        if self.fault == 'wrong-size': row['size'] += 1
        if self.fault == 'not-uploaded': row['state'] = 'new'
        if self.fault == 'duplicate-id': row['id'] = 101
        self.release['assets'].append(row); self.bytes[row['id']] = raw
        if self.fault == 'extra-asset': self.release['assets'].append({**row, 'id': 200, 'name': 'extra'})
        if self.fault == 'upload-interrupted': raise RuntimeError('upload failed')
        return copy.deepcopy(row)

    def raw(self, endpoint, **kwargs):
        self.downloads += 1
        raw = self.bytes[int(endpoint.split('/')[-1])]
        if self.fault == 'bad-bytes': return b'X' + raw[1:]
        if self.fault == 'replace-after-download' and self.patches == 0:
            self.release['assets'][0]['id'] += 1000
        if self.fault == 'replace-public' and self.patches:
            self.release['assets'][0]['id'] += 1000
        if self.fault == 'tag-change' and self.patches == 0:
            self.tag['object']['sha'] = 'wrong'
        return raw


def run_fixture(label):
    ident, path, names = p.RUNS[label]
    live = {'id': ident, 'path': path, 'head_sha': p.SOURCE, 'event': 'push', 'run_attempt': 1,
            'status': 'completed', 'conclusion': 'success', 'html_url': f'https://github.com/{p.REPO}/actions/runs/{ident}',
            'repository': {'full_name': p.REPO}, 'head_repository': {'full_name': p.REPO}}
    jobs = []
    extra = {'publish-cjk-preview', 'publish-fact-preview'} if label == 'n44' else set()
    for i, name in enumerate(sorted(names | extra)):
        jobs.append({'id': i + 1, 'name': name, 'run_id': ident, 'head_sha': p.SOURCE, 'run_attempt': 1,
                     'status': 'completed', 'conclusion': 'skipped' if name in extra else 'success',
                     'steps': [] if name in extra else [{'number': 1, 'name': 'actual', 'status': 'completed', 'conclusion': 'success'}]})
    return live, {'total_count': len(jobs), 'jobs': jobs}


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name); self.assets = {'product.zip': b'product-content', 'guide.md': b'guide-content'}
        for name, raw in self.assets.items(): (self.out / name).write_bytes(raw)

    def test_publishes_same_draft_id_and_downloads_twice(self):
        api = FakeGitHub(); receipt = p.publish(api, self.assets, self.out)
        self.assertEqual(receipt['result'], 'PUBLISHED'); self.assertEqual(api.downloads, 4)
        self.assertEqual(api.patches, 1)
        changes = [x for x in api.calls if x[0] == 'PATCH']
        self.assertEqual(changes, [('PATCH', 'releases/999', {'draft': False, 'prerelease': True, 'make_latest': 'false'})])
        self.assertFalse(any('tags/' in e for m, e, _ in api.calls if m == 'PATCH'))

    def test_refuses_existing_drafts_pagination_errors_and_tags(self):
        for fault in ('existing', 'draft-page-two', 'listing-error', 'wrong-tag'):
            with self.subTest(fault=fault):
                api = FakeGitHub(fault)
                with self.assertRaises((ValueError, RuntimeError)): p.publish(api, self.assets, self.out)
                self.assertFalse(any(m != 'GET' for m, _, _ in api.calls))

    def test_orphan_correct_tag_is_reused_not_moved(self):
        api = FakeGitHub(); api.tag = {'ref': 'refs/tags/' + p.TAG, 'object': {'type': 'commit', 'sha': p.SOURCE}}
        p.publish(api, self.assets, self.out)
        self.assertFalse(any(e == 'git/refs' for _, e, _ in api.calls))

    def test_bad_assets_never_go_public(self):
        for fault in ('no-digest', 'wrong-size', 'not-uploaded', 'duplicate-id', 'extra-asset', 'bad-bytes',
                      'replace-after-download', 'tag-change', 'upload-interrupted', 'bad-draft'):
            with self.subTest(fault=fault):
                api = FakeGitHub(fault)
                with self.assertRaises((ValueError, RuntimeError)): p.publish(api, self.assets, self.out)
                self.assertEqual(api.patches, 0)
                self.assertFalse(any(m == 'DELETE' for m, _, _ in api.calls))

    def test_public_state_still_verified(self):
        for fault in ('replace-public', 'wrong-public', 'latest'):
            with self.subTest(fault=fault):
                api = FakeGitHub(fault)
                with self.assertRaises(ValueError): p.publish(api, self.assets, self.out)
                self.assertEqual(api.patches, 1)

    def test_local_bytes_changed_after_validation_rejected(self):
        (self.out / 'product.zip').write_bytes(b'changed')
        api = FakeGitHub()
        with self.assertRaises(ValueError): p.publish(api, self.assets, self.out)
        self.assertEqual(api.patches, 0)

    def test_valid_fixed_run_shapes(self):
        for label in p.RUNS:
            with self.subTest(label=label): p.validate_run(label, *run_fixture(label))

    def test_wrong_run_fields_rejected(self):
        for key, value in (('head_sha', 'wrong'), ('event', 'pull_request'), ('run_attempt', 2),
                           ('run_attempt', True), ('status', 'in_progress'), ('conclusion', 'failure'),
                           ('id', 7), ('path', 'wrong'), ('repository', {'full_name': 'someone/else'})):
            with self.subTest(key=key, value=value):
                live, listing = run_fixture('n42'); live[key] = value
                with self.assertRaises(ValueError): p.validate_run('n42', live, listing)

    def test_incomplete_duplicated_or_wrong_jobs_rejected(self):
        for fault in ('truncate', 'duplicate', 'wrong-source', 'wrong-attempt', 'failed', 'missing-steps', 'failed-step', 'duplicate-step'):
            with self.subTest(fault=fault):
                live, listing = run_fixture('n42'); job = listing['jobs'][0]
                if fault == 'truncate': listing['jobs'].pop()
                if fault == 'duplicate': listing['jobs'][-1] = copy.deepcopy(job)
                if fault == 'wrong-source': job['head_sha'] = 'wrong'
                if fault == 'wrong-attempt': job['run_attempt'] = 2
                if fault == 'failed': job['conclusion'] = 'failure'
                if fault == 'missing-steps': job['steps'] = []
                if fault == 'failed-step': job['steps'][0]['conclusion'] = 'failure'
                if fault == 'duplicate-step': job['steps'].append(copy.deepcopy(job['steps'][0]))
                with self.assertRaises(ValueError): p.validate_run('n42', live, listing)

    def test_unexpected_publisher_job_rejected(self):
        live, listing = run_fixture('n44')
        for job in listing['jobs']:
            if job['name'].startswith('publish-'): job['conclusion'] = 'success'
        with self.assertRaises(ValueError): p.validate_run('n44', live, listing)

    def test_duplicate_json_and_nonfinite_rejected(self):
        for raw in (b'{"a":1,"a":2}', b'{"x":NaN}', b'{"x":Infinity}'):
            with self.assertRaises(ValueError): p.decode(raw)

    def test_only_confirmed_rest_404_means_absent(self):
        for code, message, stderr, absent in [('404', 'Not Found', b'gh: (HTTP 404)', True),
                 ('404', 'Not Found', b'network failure', False), ('403', 'Forbidden', b'(HTTP 403)', False),
                 ('500', 'Internal Error', b'(HTTP 500)', False)]:
            with self.subTest(code=code, stderr=stderr):
                def call(*_, **kw):
                    kw['stdout'].write(json.dumps({'status': code, 'message': message}).encode())
                    return subprocess.CompletedProcess([], 1, stderr=stderr)
                with patch.object(p.subprocess, 'run', side_effect=call):
                    if absent: self.assertIsNone(p.GitHub().api('releases/latest', optional=True))
                    else:
                        with self.assertRaises(RuntimeError): p.GitHub().api('releases/latest', optional=True)

    def test_regular_file_and_cap(self):
        with self.assertRaises(ValueError): p.read(self.out)
        with patch.object(p, 'CAP', 2):
            with self.assertRaises(ValueError): p.read(self.out / 'guide.md')

    def test_fixed_pins_are_unique(self):
        self.assertEqual(len(p.ARTIFACTS), 11)
        self.assertEqual(len({x[2] for x in p.ARTIFACTS}), 11)
        self.assertEqual(len({x[0] for x in p.ARTIFACTS}), 11)
        for label, run, ident, name, size, digest in p.ARTIFACTS:
            self.assertIn(run, p.RUNS); self.assertGreater(size, 0)
            self.assertRegex(digest, r'^[0-9a-f]{64}$')


if __name__ == '__main__': unittest.main(verbosity=2)
