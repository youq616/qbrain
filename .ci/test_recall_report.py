"""Negative evidence tests for the N47C process/unit gates."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_recall_process as process
from validate_recall_report import UNIT_SCENARIOS, validate_process, validate_unit, validate_unit_payload

class RecallReportTests(unittest.TestCase):
    def common(self):
        return dict(result='PASS',source_commit='source',tracked_tree_clean=True,native_windows=True,
                    binary_sha256='binary',script_sha256='script')
    def process_fixture(self):
        r=self.common();r.update(checks=[dict(name=n,status='PASS') for n in sorted(process.EXPECTED_CHECKS)],
            check_count=44,counts={'total':44,'pass':44,'fail':0},
            commands=[dict(exit_code=0,expected_exit=0) for _ in range(71)])
        r['commands'][-1]=dict(exit_code=1,expected_exit=1);return r
    def unit_fixture(self):
        r=self.common();r.update(test_sha256='test',exit_code=0,scenario_count=len(UNIT_SCENARIOS),checks=27*len(UNIT_SCENARIOS),
            scenarios=[dict(name=n,status='PASS',assertions=27) for n in UNIT_SCENARIOS]);return r
    def vp(self,r):return validate_process(r,source_commit='source',binary_sha256='binary',script_sha256='script')
    def vu(self,r):return validate_unit(r,source_commit='source',binary_sha256='binary',script_sha256='script',test_sha256='test')
    def test_complete(self):
        self.assertEqual(self.vp(self.process_fixture()),{'checks':44,'commands':71})
        self.assertEqual(self.vu(self.unit_fixture()),{'scenarios':len(UNIT_SCENARIOS),'assertions':27*len(UNIT_SCENARIOS)})
    def test_source_platform_and_binary(self):
        for field,value in [('source_commit','wrong'),('tracked_tree_clean',False),('native_windows',False),
                            ('script_sha256','wrong'),('binary_sha256','wrong'),('result','FAIL'),('error','failed')]:
            for fixture,validate in [(self.process_fixture,self.vp),(self.unit_fixture,self.vu)]:
                r=fixture();r[field]=value
                with self.subTest(field=field),self.assertRaises(ValueError):validate(r)
    def test_missing_duplicate_or_failed_names(self):
        for edit in [lambda r:r['checks'].pop(),lambda r:r['checks'].clear(),
                     lambda r:r['checks'].__setitem__(-1,r['checks'][0]),lambda r:r['checks'][0].update(status='FAIL')]:
            r=self.process_fixture();edit(r)
            with self.assertRaises(ValueError):self.vp(r)
    def test_bad_totals(self):
        for field,value in [('total',37),('pass',39),('fail',False)]:
            r=self.process_fixture();r['counts'][field]=value
            with self.assertRaises(ValueError):self.vp(r)
    def test_command_failures_and_partial_history(self):
        for row in [dict(exit_code=0,expected_exit=1),dict(exit_code=2,expected_exit=0),
                    dict(exit_code=None,expected_exit=0),dict(exit_code=False,expected_exit=0),
                    dict(exit_code=0,expected_exit=0,timed_out=True)]:
            r=self.process_fixture();r['commands'][0]=row
            with self.assertRaises(ValueError):self.vp(r)
        r=self.process_fixture();r['commands'].pop()
        with self.assertRaises(ValueError):self.vp(r)
    def test_unit_rows_totals_and_source(self):
        for edit in [lambda r:r['scenarios'].pop(),lambda r:r['scenarios'].reverse(),
                     lambda r:r['scenarios'].__setitem__(-1,r['scenarios'][0]),
                     lambda r:r['scenarios'][0].update(assertions=True),lambda r:r['scenarios'][0].update(status='FAIL'),
                     lambda r:r.update(checks=350),lambda r:r.update(scenario_count=12),
                     lambda r:r.update(test_sha256='wrong'),lambda r:r.update(exit_code=False)]:
            r=self.unit_fixture();edit(r)
            with self.assertRaises(ValueError):self.vu(r)
    def test_payload_checked_without_source_attribution(self):
        r=self.unit_fixture();self.assertEqual(validate_unit_payload(r)['scenarios'],len(UNIT_SCENARIOS))
        r['scenarios']=[]
        with self.assertRaises(ValueError):validate_unit_payload(r)
    def test_exception_preserves_failure_count_and_prior_history(self):
        with tempfile.TemporaryDirectory() as d:
            binary=Path(d)/'fake';binary.write_bytes(b'never run');report=Path(d)/'report.json'
            def failure(_binary,checks,commands):
                checks.append({'name':'earlier','status':'PASS'});commands.append({'exit_code':2,'expected_exit':0})
                raise RuntimeError('synthetic failure')
            with patch.object(process,'run',side_effect=failure),patch('sys.argv',['test','--binary',str(binary),'--report',str(report)]):
                self.assertEqual(process.main(),1)
            r=json.loads(report.read_text(encoding='utf-8'));self.assertEqual(r['counts'],{'total':2,'pass':1,'fail':1})
            self.assertEqual(r['commands'][0]['exit_code'],2)
    def test_standalone_copy_does_not_claim_parent_git_source(self):
        with tempfile.TemporaryDirectory() as d:
            script=Path(d)/'verification'/'test_recall_process.py';script.parent.mkdir();script.write_bytes(b'# fixture')
            self.assertEqual(process.provenance(script),{'source_commit':None,'tracked_tree_clean':False})
    def test_unit_names_match_actual_cpp_registry(self):
        import re
        text=(Path(__file__).resolve().parents[1]/'tests/test_n47c.cpp').read_text(encoding='utf-8')
        self.assertEqual(tuple(re.findall(r'scenario\("([^"\r\n]+)"',text)),UNIT_SCENARIOS)

if __name__=='__main__':unittest.main(verbosity=2)
