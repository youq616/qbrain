import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_cjk_recall as suite
from validate_cjk_report import EXPECTED_CHECKS, validate_report

class CjkReportTests(unittest.TestCase):
    def fixture(self):
        checks=[{'name':n,'status':'PASS'} for n in sorted(EXPECTED_CHECKS)]
        return dict(result='PASS',checks=checks,check_count=len(checks),counts=suite.status_counts(checks),
                    source_commit='source',binary_sha256='binary',script_sha256='script',tracked_tree_clean=True,
                    commands=[{'exit_code':0} for _ in range(54)])
    def validate(self,r):
        return validate_report(r,source_commit='source',binary_sha256='binary',script_sha256='script')
    def test_valid_complete(self): self.validate(self.fixture())
    def test_failed_count_is_not_pass(self):
        self.assertEqual(suite.status_counts([{'status':'PASS'}]*5+[{'status':'FAIL'}]),{'total':6,'pass':5,'fail':1})
    def test_empty_and_missing(self):
        for n in (0,1,len(EXPECTED_CHECKS)-1):
            r=self.fixture();r['checks']=r['checks'][:n];r['check_count']=n;r['counts']=suite.status_counts(r['checks'])
            with self.assertRaises(ValueError):self.validate(r)
    def test_corrupt_and_duplicate(self):
        for kind in ('duplicate','counts','bool_count','status','dirty'):
            r=self.fixture()
            if kind=='duplicate':r['checks'][0]=r['checks'][1].copy()
            elif kind=='counts':r['counts']['pass']+=1
            elif kind=='bool_count':r['counts']['fail']=False
            elif kind=='dirty':r['tracked_tree_clean']=False
            else:r['checks'][0]['status']='FAIL'
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.validate(r)
    def test_source_and_hashes(self):
        for key in ('source_commit','binary_sha256','script_sha256'):
            r=self.fixture();r[key]='different'
            with self.assertRaises(ValueError):self.validate(r)
    def test_incomplete_command_history(self):
        for commands in ([],[{'exit_code':0}], [{'exit_code':1}]*54,[{'exit_code':None}]*54,[{'exit_code':False}]*54):
            r=self.fixture();r['commands']=commands
            with self.assertRaises(ValueError):self.validate(r)
    def test_exception_keeps_completed_checks(self):
        with tempfile.TemporaryDirectory() as d:
            binary,output=Path(d)/'fake',Path(d)/'report.json';binary.write_bytes(b'not executed')
            def fail(args,checks,commands):
                checks.append({'name':'earlier','status':'PASS','detail':'synthetic'})
                commands.append({'exit_code':7})
                raise suite.CheckFailure('synthetic failure')
            with patch.object(suite,'run',side_effect=fail),patch('sys.argv',['test','--binary',str(binary),'--report',str(output)]):
                self.assertEqual(suite.main(),1)
            r=json.loads(output.read_text());self.assertEqual(r['counts'],{'total':2,'pass':1,'fail':1});self.assertEqual(r['commands'],[{'exit_code':7}])
    def test_non_windows_cannot_be_reported_native(self):
        # Metadata field is generated from the actual interpreter OS, not CLI input.
        import inspect
        self.assertIn('native_windows=os.name == "nt"',inspect.getsource(suite.add_source_provenance))

if __name__=='__main__':unittest.main()
