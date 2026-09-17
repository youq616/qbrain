"""Negative evidence tests for the N47L process/unit gates."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import test_multiterm_process as process
from validate_multiterm_report import UNIT_SCENARIOS, validate_process, validate_unit, validate_unit_payload

class MultitermReportTests(unittest.TestCase):
    def common(self):
        return dict(result='PASS',source_commit='source',tracked_tree_clean=True,native_windows=True,
                    binary_sha256='binary',script_sha256='script')
    def process_fixture(self):
        def value(pattern):
            if isinstance(pattern,str) and pattern.startswith('<id:') and pattern.endswith('>'):
                return hashlib.sha256(pattern.encode()).hexdigest()
            if pattern=='<group-budget>':return '2048'
            if isinstance(pattern,dict):
                if set(pattern)=={'<json>'}:return json.dumps(value(pattern['<json>']))
                return {k:value(v) for k,v in pattern.items()}
            if isinstance(pattern,list):return [value(v) for v in pattern]
            return pattern
        count=len(process.EXPECTED_CHECKS)
        r=self.common();r.update(checks=[dict(name=n,status='PASS') for n in sorted(process.EXPECTED_CHECKS)],
            check_count=count,counts={'total':count,'pass':count,'fail':0},
            commands=[dict(name=name,args=value(process.COMMAND_ARGUMENTS[name]),
                           stdin_json=value(process.COMMAND_INPUTS[name]),
                           exit_code=1 if name in process.NEGATIVE else 0,
                           expected_exit=1 if name in process.NEGATIVE else 0)
                      for name in process.COMMAND_SCHEDULE])
        return r
    def unit_fixture(self):
        r=self.common();r.update(test_sha256='test',exit_code=0,scenario_count=len(UNIT_SCENARIOS),checks=27*len(UNIT_SCENARIOS),
            scenarios=[dict(name=n,status='PASS',assertions=27) for n in UNIT_SCENARIOS]);return r
    def vp(self,r):return validate_process(r,source_commit='source',binary_sha256='binary',script_sha256='script')
    def vu(self,r):return validate_unit(r,source_commit='source',binary_sha256='binary',script_sha256='script',test_sha256='test')
    def test_complete(self):
        self.assertEqual(self.vp(self.process_fixture()),{'checks':len(process.EXPECTED_CHECKS),'commands':len(process.COMMAND_SCHEDULE)})
        self.assertEqual(len(process.COMMAND_SCHEDULE),len(set(process.COMMAND_SCHEDULE)))
        self.assertEqual(process.EXPECTED_COMMAND_COUNT,len(process.COMMAND_SCHEDULE))
        self.assertLessEqual(process.NEGATIVE,set(process.COMMAND_SCHEDULE))
        self.assertEqual(self.vu(self.unit_fixture()),{'scenarios':len(UNIT_SCENARIOS),'assertions':27*len(UNIT_SCENARIOS)})
    def test_source_platform_and_binary(self):
        for field,value in [('source_commit','wrong'),('tracked_tree_clean',False),('native_windows',False),
                            ('script_sha256','wrong'),('binary_sha256','wrong'),('result','FAIL'),('error','failed'),
                            ('error_type','RuntimeError'),('native_windows',1)]:
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
            r=self.process_fixture();r['commands'][0].update(row)
            with self.assertRaises(ValueError):self.vp(r)
        r=self.process_fixture();r['commands'].pop()
        with self.assertRaises(ValueError):self.vp(r)
    def test_init_padding_cannot_certify_command_coverage(self):
        for preserve_names in (False,True):
            r=self.process_fixture()
            for command in r['commands']:
                command['args']=copy.deepcopy(r['commands'][0]['args'])
                command['stdin_json']=[]
                if not preserve_names:command['name']='init'
            with self.subTest(preserve_names=preserve_names),self.assertRaises(ValueError):self.vp(r)
    def test_required_command_identity_and_input_cannot_be_removed(self):
        for field in ('name','args','stdin_json','expected_exit','exit_code'):
            r=self.process_fixture()
            for command in r['commands']:command.pop(field)
            with self.subTest(field=field),self.assertRaises(ValueError):self.vp(r)
    def test_duplicate_or_swapped_commands_cannot_pass(self):
        r=self.process_fixture();r['commands'][1]=copy.deepcopy(r['commands'][0])
        with self.assertRaises(ValueError):self.vp(r)
        r=self.process_fixture();r['commands'][0],r['commands'][1]=r['commands'][1],r['commands'][0]
        with self.assertRaises(ValueError):self.vp(r)
    def test_recorded_exit_expectations_cannot_redefine_success(self):
        r=self.process_fixture()
        for command in r['commands']:command.update(exit_code=1,expected_exit=1)
        with self.assertRaises(ValueError):self.vp(r)
        r=self.process_fixture();r['commands'][0].update(exit_code=1,expected_exit=1)
        with self.assertRaises(ValueError):self.vp(r)
        r=self.process_fixture();r['commands'][0].update(expected_exit=False)
        with self.assertRaises(ValueError):self.vp(r)
    def test_every_negative_case_has_a_fixed_failure_exit(self):
        for name in process.NEGATIVE:
            r=self.process_fixture()
            next(command for command in r['commands'] if command['name']==name).update(exit_code=0,expected_exit=0)
            with self.subTest(command=name),self.assertRaises(ValueError):self.vp(r)
    def test_argument_shape_values_and_required_options_are_fixed(self):
        for args in (None,{},'init',[],['init'],['init','--brain','wrong-brain']):
            r=self.process_fixture();r['commands'][0]['args']=args
            with self.subTest(args=args),self.assertRaises(ValueError):self.vp(r)
        r=self.process_fixture()
        row=next(command for command in r['commands'] if command['name']=='flag-match-query_first-all_terms')
        row['args'][-1]='any_terms'
        with self.assertRaises(ValueError):self.vp(r)
    def test_rpc_replays_cannot_keep_the_old_semantic_name(self):
        r=self.process_fixture()
        literal=next(command for command in r['commands'] if command['name']=='mcp-literal')
        conjunction=next(command for command in r['commands'] if command['name']=='mcp-all_terms')
        conjunction['stdin_json']=copy.deepcopy(literal['stdin_json'])
        with self.assertRaises(ValueError):self.vp(r)
        r=self.process_fixture()
        row=next(command for command in r['commands'] if command['name']=='strict-match-boolean')
        row['stdin_json'][-1]['params']['arguments']['match']=1
        with self.assertRaises(ValueError):self.vp(r)
    def test_seed_replays_and_changed_dynamic_bindings_are_rejected(self):
        r=self.process_fixture()
        first=next(command for command in r['commands'] if command['name']=='seed-a-capture')
        second=next(command for command in r['commands'] if command['name']=='seed-b-capture')
        second['stdin_json']=copy.deepcopy(first['stdin_json'])
        with self.assertRaises(ValueError):self.vp(r)
        for replacement in ('not-an-id','b'*64):
            r=self.process_fixture()
            row=next(command for command in r['commands'] if command['name']=='forget-a')
            row['args'][5]=replacement
            with self.subTest(replacement=replacement),self.assertRaises(ValueError):self.vp(r)
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
            script=Path(d)/'verification'/'test_multiterm_process.py';script.parent.mkdir();script.write_bytes(b'# fixture')
            self.assertEqual(process.provenance(script),{'source_commit':None,'tracked_tree_clean':False})
    def test_standalone_process_and_validator_have_complete_imports(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);verification=root/'verification';verification.mkdir()
            source=Path(__file__).resolve().parent
            for name in ('test_multiterm_process.py','validate_multiterm_report.py'):
                (verification/name).write_bytes((source/name).read_bytes())
            fixture=root/'commands.json';fixture.write_text(json.dumps(self.process_fixture()['commands']),encoding='utf-8')
            code=('import json, sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); '
                  'import test_multiterm_process as suite; from validate_multiterm_report import validate_commands; '
                  'validate_commands(json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))); '
                  'print(json.dumps(suite.provenance(Path(suite.__file__))))')
            result=subprocess.run([sys.executable,'-I','-c',code,str(verification),str(fixture)],
                                  cwd=root,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout),{'source_commit':None,'tracked_tree_clean':False})
    def test_unit_names_match_actual_cpp_registry(self):
        import re
        text=(Path(__file__).resolve().parents[1]/'tests/test_n47l.cpp').read_text(encoding='utf-8')
        self.assertEqual(tuple(re.findall(r'scenario\("([^"\r\n]+)"',text)),UNIT_SCENARIOS)

    def test_build_and_delivery_wiring(self):
        root=Path(__file__).resolve().parents[1]
        workflow=(root/'.github/workflows/n44-validation.yml').read_text(encoding='utf-8')
        lines=workflow.splitlines()
        build_lines=[line for line in lines if 'cmake --build' in line and '--target' in line]
        self.assertEqual(len(build_lines),4)
        for line in build_lines:self.assertEqual(line.count('qbrain_multiterm_tests'),1)
        for line in lines:
            if 'qbrain_multiterm_tests' in line and 'cmake --build' not in line:
                self.assertIn('test_multiterm_unit.py --binary',line)
        self.assertEqual(sum('test_multiterm_unit.py --binary' in line for line in lines),4)
        self.assertEqual(sum('test_multiterm_process.py --binary' in line for line in lines),3)
        self.assertIn("'optimization/n47l-multi-term-recall'",workflow)
        package=(root/'.ci/package_n44_development.py').read_text(encoding='utf-8')
        for name in ('validate_multiterm_unit(', 'validate_multiterm_process(', "tests/test_n47l.cpp", 'MULTI-TERM-RECALL.zh-CN.md'):
            self.assertIn(name,package)
        self.assertIn('verification/validate_multiterm_report.py',package)

if __name__=='__main__':unittest.main(verbosity=2)
