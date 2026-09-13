import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_fact_process as suite
from validate_fact_report import validate_report, validate_unit_report

class FactReportTests(unittest.TestCase):
    def fixture(self):
        names=sorted(suite.EXPECTED_CHECKS)
        return dict(result='PASS',source_commit='source',tracked_tree_clean=True,native_windows=True,
            binary_sha256='binary',script_sha256='script',checks=[dict(name=n,status='PASS') for n in names],
            check_count=len(names),counts={'total':len(names),'pass':len(names),'fail':0},
            commands=[{'exit_code':0,'expected_exit':0}]*55+[{'exit_code':1,'expected_exit':1}])
    def validate(self,r):
        return validate_report(r,source_commit='source',binary_sha256='binary',script_sha256='script')
    def test_complete(self):
        self.assertEqual(self.validate(self.fixture())['named_checks'],33)
    def test_empty_missing_duplicate(self):
        for mode in ('empty','missing','duplicate'):
            r=self.fixture()
            if mode=='empty':r['checks']=[]
            elif mode=='missing':r['checks'].pop()
            else:r['checks'][-1]=r['checks'][0]
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.validate(r)
    def test_wrong_counts_and_status(self):
        for mode in ('fail','count','bool','error'):
            r=self.fixture()
            if mode=='fail':r['checks'][0]['status']='FAIL'
            elif mode=='count':r['counts']['pass']+=1
            elif mode=='bool':r['counts']['fail']=False
            else:r['error']='ignored failure'
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.validate(r)
    def test_wrong_source_binary_script_platform(self):
        for key,value in [('source_commit','old'),('binary_sha256','wrong'),('script_sha256','old'),
                          ('tracked_tree_clean',False),('native_windows',False)]:
            r=self.fixture();r[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate(r)
    def test_expected_failures_must_really_fail(self):
        r=self.fixture();r['commands'][-1]={'exit_code':0,'expected_exit':1}
        with self.assertRaises(ValueError):self.validate(r)
    def test_command_history_fail_closed(self):
        for rows in ([],[{'exit_code':0,'expected_exit':0}],
                     [{'exit_code':False,'expected_exit':0}]*56,[{'exit_code':None,'expected_exit':0}]*56):
            r=self.fixture();r['commands']=rows
            with self.assertRaises(ValueError):self.validate(r)
    def test_failure_record_preserves_previous_checks(self):
        with tempfile.TemporaryDirectory() as d:
            binary=Path(d)/'fake';binary.write_bytes(b'never executed');report=Path(d)/'report.json'
            def fail(_binary,checks,commands):
                checks.extend([{'name':'one','status':'PASS'},{'name':'two','status':'FAIL'}])
                commands.append({'exit_code':1,'expected_exit':0});raise RuntimeError('synthetic fixture')
            with patch.object(suite,'execute',side_effect=fail),patch('sys.argv',['test','--binary',str(binary),'--report',str(report)]):
                self.assertEqual(suite.main(),1)
            r=json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(r['counts'],{'total':2,'pass':1,'fail':1});self.assertEqual(len(r['commands']),1)
    def test_windows_default_encoding_not_used(self):
        original=Path.read_text
        def read_with_windows_default(path,encoding=None,errors=None):
            return original(path,encoding=encoding or 'cp1252',errors=errors)
        with patch.object(Path,'read_text',read_with_windows_default):
            self.test_failure_record_preserves_previous_checks()

    def unit_fixture(self):
        names=['scenario-'+str(i) for i in range(14)]
        rows=[dict(name=n,status='PASS',assertions=26) for n in names]
        rows[-1]['assertions']=28
        return dict(result='PASS',source_commit='source',tracked_tree_clean=True,native_windows=True,
            binary_sha256='binary',test_sha256='test',exit_code=0,provider_calls=False,
            scenarios=rows,scenario_count=14,checks=366),names
    def unit_validate(self,r,names):
        return validate_unit_report(r,source_commit='source',binary_sha256='binary',test_sha256='test',expected_scenarios=names)
    def test_unit_complete(self):
        r,n=self.unit_fixture();self.assertEqual(self.unit_validate(r,n)['assertions'],366)
    def test_unit_rejects_partial_or_failed(self):
        for mode in ('missing','status','assertions','sum','exit','bool','dirty','source','binary','test','native','error'):
            r,n=self.unit_fixture()
            if mode=='missing':r['scenarios'].pop()
            elif mode=='status':r['scenarios'][0]['status']='FAIL'
            elif mode=='assertions':r['scenarios'][0]['assertions']=0
            elif mode=='sum':r['checks']+=1
            elif mode=='exit':r['exit_code']=1
            elif mode=='bool':r['exit_code']=False
            elif mode=='dirty':r['tracked_tree_clean']=False
            elif mode=='source':r['source_commit']='wrong'
            elif mode=='binary':r['binary_sha256']='wrong'
            elif mode=='test':r['test_sha256']='wrong'
            elif mode=='native':r['native_windows']=False
            else:r['error_type']='RuntimeError'
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.unit_validate(r,n)
    def test_unit_duplicate_scenarios_rejected(self):
        r,n=self.unit_fixture();r['scenarios'][-1]['name']=r['scenarios'][0]['name']
        with self.assertRaises(ValueError):self.unit_validate(r,n)

if __name__=='__main__':unittest.main(verbosity=2)
