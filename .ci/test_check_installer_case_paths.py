"""Content verifier positive/negative fixtures. Not a filesystem test."""
import copy
import unittest
import check_installer_case_paths as c

RAW = (b'installer', b'prior', b'test', b'exe')
SOURCE = 'a'*40


def fixture():
    r = {'schema': 'qbrain-n47v-case-paths-v1', 'source_commit': SOURCE, 'result': 'PASS',
         'native_windows': True, 'shell_major': 5, 'real_client_verified': False,
         'checks': [{'name': n, 'passed': True} for n in c.names()],
         'flags': [{'path': str(i), 'flags': n, 'fsutil_output': 'fixture'}
                   for i, n in enumerate([1,0,0,1,1]*2+[1,1,1])],
         **{k: c.sha(raw) for k, raw in zip(('installer_sha256','baseline_installer_sha256','script_sha256','binary_sha256'), RAW)}}
    log = ''.join('PASS '+str(i)+' : '+n+'\n' for i,n in enumerate(c.names(),1)).encode()
    return r, log


class Checks(unittest.TestCase):
    def test_exact_coverage(self):
        r, log = fixture()
        self.assertEqual(len(c.names()), 81)
        self.assertEqual(len(set(c.names())), 81)
        self.assertEqual(c.validate(r, *RAW, SOURCE, 5, log)['checks'], 81)
        r['shell_major'] = 7
        self.assertEqual(c.validate(r, *RAW, SOURCE, 7, log)['shell_major'], 7)

    def test_rejects_forged_scope_identity_coverage_flags(self):
        cases = ('source','result','shell','boolean_shell','client','native','installer','baseline','script','binary',
                 'missing','duplicate','typed_pass','bad_pass','flags_missing','flags_false','flags_bool','log')
        for case in cases:
            with self.subTest(case=case):
                r, log = fixture()
                if case=='source': r['source_commit']='b'*40
                if case=='result': r['result']='SKIP'
                if case=='shell': r['shell_major']=7
                if case=='boolean_shell': r['shell_major']=True
                if case=='client': r['real_client_verified']=True
                if case=='native': r['native_windows']=1
                if case in ('installer','baseline','script','binary'):
                    r[{'installer':'installer_sha256','baseline':'baseline_installer_sha256','script':'script_sha256','binary':'binary_sha256'}[case]]='0'*64
                if case=='missing': r['checks'].pop()
                if case=='duplicate': r['checks'][-1]=copy.deepcopy(r['checks'][0])
                if case=='typed_pass': r['checks'][0]['passed']=1
                if case=='bad_pass': r['checks'][0]['passed']=False
                if case=='flags_missing': r['flags'].pop()
                if case=='flags_false': r['flags'][0]['flags']=0
                if case=='flags_bool': r['flags'][0]['flags']=True
                if case=='log': log=log.replace(b'PASS 1 :',b'PASS 2 :')
                with self.assertRaises(ValueError): c.validate(r,*RAW,SOURCE,5,log)

    def test_duplicate_json_is_rejected(self):
        with self.assertRaises(ValueError): c.decode(b'{"result":"FAIL","result":"PASS"}')


if __name__=='__main__': unittest.main(verbosity=2)
