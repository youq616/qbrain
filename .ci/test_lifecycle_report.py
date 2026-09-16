import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_lifecycle_process as suite
from validate_fact_lifecycle_report import validate_process, validate_unit, UNIT_SCENARIOS

class LifecycleReportTests(unittest.TestCase):
    def fixture(self):
        n=len(suite.EXPECTED_CHECKS)
        return dict(result='PASS',source_commit='source',tracked_tree_clean=True,native_windows=True,
            binary_sha256='binary',script_sha256='script',real_host_consumption_verified=False,
            checks=[dict(name=k,status='PASS') for k in sorted(suite.EXPECTED_CHECKS)],
            check_count=n,counts={'total':n,'pass':n,'fail':0},
            commands=[dict(exit_code=0,expected_exit=0) for _ in range(suite.EXPECTED_COMMAND_COUNT)])
    def validate(self,r):return validate_process(r,source_commit='source',binary_sha256='binary',script_sha256='script')
    def test_complete(self):
        self.assertEqual(self.validate(self.fixture())['checks'],len(suite.EXPECTED_CHECKS))
    def test_missing_and_duplicate_checks(self):
        for mode in ('missing','duplicate','empty'):
            r=self.fixture()
            if mode=='missing':r['checks'].pop()
            elif mode=='empty':r['checks']=[]
            else:r['checks'][-1]=r['checks'][0]
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.validate(r)
    def test_failed_check_and_bad_totals(self):
        for edit in [lambda r:r['checks'][0].update(status='FAIL'),lambda r:r['counts'].update(fail=True),lambda r:r.update(check_count=True),lambda r:r['counts'].update(total=999)]:
            r=self.fixture();edit(r)
            with self.assertRaises(ValueError):self.validate(r)
    def test_identity(self):
        for k,v in [('source_commit','old'),('binary_sha256','old'),('script_sha256','old'),('native_windows',False),('tracked_tree_clean',False),('real_host_consumption_verified',True)]:
            r=self.fixture();r[k]=v
            with self.subTest(field=k),self.assertRaises(ValueError):self.validate(r)
    def test_unexpected_or_missing_commands(self):
        for edit in [lambda r:r['commands'].pop(),lambda r:r['commands'][0].update(exit_code=2),lambda r:r['commands'][0].update(exit_code=False),lambda r:r['commands'][0].update(timed_out=True)]:
            r=self.fixture();edit(r)
            with self.assertRaises(ValueError):self.validate(r)
    def test_expected_negative_is_required(self):
        r=self.fixture();r['commands'][-1]={'exit_code':1,'expected_exit':1};self.validate(r)
        r['commands'][-1]['exit_code']=0
        with self.assertRaises(ValueError):self.validate(r)
    def test_exception_metadata_not_pass(self):
        for k in ('error','error_type'):
            r=self.fixture();r[k]='failed'
            with self.assertRaises(ValueError):self.validate(r)
    def unit(self):
        return dict(result='PASS',source_commit='source',tracked_tree_clean=True,native_windows=True,
            binary_sha256='binary',script_sha256='script',test_sha256='test',exit_code=0,
            scenarios=[dict(name=n,status='PASS',assertions=20) for n in UNIT_SCENARIOS],
            scenario_count=len(UNIT_SCENARIOS),checks=20*len(UNIT_SCENARIOS))
    def validate_unit(self,r):return validate_unit(r,source_commit='source',binary_sha256='binary',script_sha256='script',test_sha256='test')
    def test_unit_complete(self):self.validate_unit(self.unit())
    def test_unit_order_missing_and_duplicate(self):
        for edit in [lambda r:r['scenarios'].pop(),lambda r:r['scenarios'].reverse(),lambda r:r['scenarios'].__setitem__(-1,copy.deepcopy(r['scenarios'][0]))]:
            r=self.unit();edit(r)
            with self.assertRaises(ValueError):self.validate_unit(r)
    def test_unit_count_and_bool(self):
        for edit in [lambda r:r.update(checks=True),lambda r:r.update(checks=1),lambda r:r['scenarios'][0].update(assertions=True),lambda r:r['scenarios'][0].update(assertions=0),lambda r:r['scenarios'][0].update(status='FAIL')]:
            r=self.unit();edit(r)
            with self.assertRaises(ValueError):self.validate_unit(r)
    def test_unit_hash_and_exit(self):
        for k,v in [('test_sha256','wrong'),('exit_code',1),('exit_code',False)]:
            r=self.unit();r[k]=v
            with self.assertRaises(ValueError):self.validate_unit(r)
    def test_interrupted_process_retains_failure(self):
        with tempfile.TemporaryDirectory() as d:
            binary=Path(d)/'not-an-exe';binary.write_bytes(b'not executed');report=Path(d)/'report.json'
            def fail(binary,checks,commands):
                checks.append(dict(name='earlier',status='PASS'));commands.append(dict(exit_code=2,expected_exit=0));raise RuntimeError('synthetic interruption')
            with patch.object(suite,'run',side_effect=fail),patch('sys.argv',['test','--binary',str(binary),'--report',str(report)]):
                self.assertEqual(suite.main(),1)
            r=json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(r['counts'],{'total':2,'pass':1,'fail':1});self.assertEqual(r['commands'][0]['exit_code'],2)
    def test_failed_check_preserved_without_double_count(self):
        with tempfile.TemporaryDirectory() as d:
            binary=Path(d)/'fake';binary.write_bytes(b'not executed');report=Path(d)/'report.json'
            def fail(binary,checks,commands):
                checks.append(dict(name='failed',status='FAIL'));raise AssertionError('synthetic')
            with patch.object(suite,'run',side_effect=fail),patch('sys.argv',['test','--binary',str(binary),'--report',str(report)]):
                self.assertEqual(suite.main(),1)
            self.assertEqual(json.loads(report.read_text(encoding='utf-8'))['counts'],{'total':1,'pass':0,'fail':1})

if __name__=='__main__':unittest.main(verbosity=2)
