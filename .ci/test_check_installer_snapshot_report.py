"""Positive/negative report tests, usable in normal and optimized Python."""
import copy
import hashlib
import unittest
import check_installer_snapshot_report as c

RAW = (b'installer', b'test', b'executable')
SOURCE = 'a'*40


def fixture(shell=5, baseline=False):
    rows = [{'name': h+'/'+k, 'passed': (not baseline) or k.startswith('normal-')}
            for h in ('Claude', 'Codex') for k in c.KINDS]
    return {'schema': 'qbrain-n47p-input-snapshot-v1', 'source_commit': SOURCE,
            'native_windows': True, 'shell_major': shell, 'real_client_tested': False,
            **{k: hashlib.sha256(v).hexdigest() for k, v in zip(('installer_sha256', 'test_sha256', 'binary_sha256'), RAW)},
            'cases': rows, 'passed': sum(r['passed'] for r in rows), 'failed': sum(not r['passed'] for r in rows)}


class Reports(unittest.TestCase):
    def test_positive_candidate_and_baseline_both_shells(self):
        for shell in (5, 7):
            for baseline in (False, True):
                with self.subTest(shell=shell, baseline=baseline):
                    self.assertTrue(c.validate(fixture(shell, baseline), *RAW, SOURCE, shell, baseline)['verified'])

    def test_rejects_identity_source_shell_and_scope_changes(self):
        for field, bad in (('source_commit', 'b'*40), ('installer_sha256', '0'*64), ('test_sha256', '0'*64),
                           ('binary_sha256', '0'*64), ('native_windows', False), ('native_windows', 1),
                           ('shell_major', 7), ('shell_major', True), ('real_client_tested', True), ('schema', 'other')):
            with self.subTest(field=field, bad=bad):
                value = fixture(); value[field] = bad
                with self.assertRaises(ValueError): c.validate(value, *RAW, SOURCE, 5)

    def test_rejects_coverage_type_and_count_forgery(self):
        for bad in ('missing', 'duplicate', 'renamed', 'typed-result', 'failed-result', 'boolean-count', 'count-mismatch', 'not-array'):
            with self.subTest(bad=bad):
                value = fixture()
                if bad == 'missing': value['cases'].pop()
                if bad == 'duplicate': value['cases'][-1] = copy.deepcopy(value['cases'][0])
                if bad == 'renamed': value['cases'][0]['name'] = 'other'
                if bad == 'typed-result': value['cases'][0]['passed'] = 1
                if bad == 'failed-result': value['cases'][0]['passed'] = False; value['failed'] = 1; value['passed'] = 23
                if bad == 'boolean-count': value['failed'] = False
                if bad == 'count-mismatch': value['passed'] = 25
                if bad == 'not-array': value['cases'] = {}
                with self.assertRaises(ValueError): c.validate(value, *RAW, SOURCE, 5)

    def test_baseline_must_fail_defects_but_pass_controls(self):
        for index in (0, 10):
            value = fixture(baseline=True); value['cases'][index]['passed'] = not value['cases'][index]['passed']
            value['passed'] = sum(r['passed'] for r in value['cases']); value['failed'] = 24-value['passed']
            with self.assertRaises(ValueError): c.validate(value, *RAW, SOURCE, 5, True)

    def test_duplicate_raw_json_keys_rejected(self):
        with self.assertRaises(ValueError): c.decode(b'{"failed":1,"failed":0}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
