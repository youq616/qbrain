"""Adversarial tests of the independent N48S reader against original evidence.
No native execution. Mutations are in-memory overlays; input artifacts stay intact.
"""
from __future__ import annotations
import argparse
import copy
import io
import json
from pathlib import Path
import sys
import unittest
import warnings
import zipfile
import review_n48s_outcome as r

EVIDENCE = None
SOURCE = None
RESULT = None
MUTATIONS = []

class OutcomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reader = r.Reader(EVIDENCE)
        cls.source = SOURCE.read_bytes()
        cls.valid = r.review(cls.reader,cls.source)

    def test_full_original_evidence(self):
        self.assertEqual(self.valid['qualification_stages'],27)
        self.assertEqual(self.valid['result'],'PASS_FIXED_ARTIFACT_TOP_LEVEL_READBACK')
        self.assertEqual(self.valid['qualification_command_binding'],'all_27_top_level_stage_commands_only')
        self.assertIs(self.valid['nested_command_binding_verified'],False)
        self.assertIs(self.valid['descendant_execution_verified'],False)
        self.assertEqual(self.valid['retained_driver_steps'],55)
        self.assertEqual(self.valid['complete_preservation_snapshots'],24)
        self.assertIs(self.valid['new_windows_execution'],False)
        self.assertIs(self.valid['full_project_complete'],False)

    def test_json_types_and_strictness(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e999}',b'{"x":"\\ud800"}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError): r.decode(raw)
        for a,b in [(False,0),(True,1),(1,1.0),({'x':False},{'x':0})]:
            with self.assertRaises(ValueError):r.same(a,b,'type_identity')

    def test_git_tree_not_just_labels(self):
        a={'a':b'hello','dir/b':b'world'};m=dict.fromkeys(a,'100644')
        original=r.git_tree(a,m)
        for files,modes in [({'a':b'HELLO','dir/b':b'world'},m),({'a':b'hello'}, {'a':'100644'}),
                            (a, {'a':'100755','dir/b':'100644'})]:
            self.assertNotEqual(r.git_tree(files,modes),original)

    def test_zip_alias_and_duplicate(self):
        for names in [['../evil'],['a','a'],['/absolute'],['a\\b']]:
            b=io.BytesIO()
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',UserWarning)
                with zipfile.ZipFile(b,'w') as z:
                    for name in names:z.writestr(name,b'x')
            with self.assertRaises(ValueError):r.archive(b.getvalue())

    def test_raw_hash_not_semantic_guarantee(self):
        # A changed money amount rehashed in its stage record must still fail.
        view=r.Reader(EVIDENCE);view.cache=self.reader.cache
        driver=copy.deepcopy(view.obj('qualification/driver.json'))
        report=copy.deepcopy(view.obj('qualification/logs/system-only-cost.stdout'))
        report['change']['candidate_minus_baseline']='-999.000000000000'
        forged=r.canonical(report)
        driver['steps'][1]['stdout_sha256']=r.sha(forged)
        view.overrides['qualification/driver.json']=r.canonical(driver)
        view.overrides['qualification/logs/system-only-cost.stdout']=forged
        with self.assertRaisesRegex(r.Rejected,'cost_output'):r.review(view,self.source)
        MUTATIONS.append('rehashed_forged_cost')

    def test_all_snapshots_rewritten_cannot_replace_raw_receipts(self):
        view=r.Reader(EVIDENCE);view.cache=self.reader.cache
        for phase in ('before','upgrade','rollback','reupgrade','uninstall','after-duplicate'):
            path='qualification/existing-receipts-powershell/Claude-'+phase+'.json'
            snapshot=copy.deepcopy(view.obj(path));snapshot['fact']['items'][0]['object']='FORGED_SNAPSHOT_ONLY'
            view.overrides[path]=r.canonical(snapshot)
        with self.assertRaisesRegex(r.Rejected,'snapshot_raw_binding'):r.review(view,self.source)
        MUTATIONS.append('all_six_snapshots_changed_without_raw_receipts')

    def test_required_inputs_refuse_mutations(self):
        A='qualification/ACCEPTANCE.json';D='qualification/driver.json';R='qualification/retained/driver.json'
        P='qualification/existing-receipts-powershell/RESULT.json'
        def setkey(k,v):return lambda x:x.__setitem__(k,v)
        cases=[
            ('stable_claim',A,setkey('stable_release',True)),
            ('host_claim',A,setkey('real_client_consumption_verified',True)),
            ('integer_false',A,setkey('signed',0)),
            ('boolean_count',A,setkey('stages',True)),
            ('missing_pg',A,setkey('postgres_tests_executed',False)),
            ('unknown_acceptance_field',A,setkey('extra','not validated')),
            ('wrong_tree',A,setkey('product_tree','0'*40)),
            ('missing_stage',D,lambda x:x['steps'].pop()),
            ('reordered_stage',D,lambda x:x['steps'].reverse()),
            ('pending_stage',D,lambda x:x['steps'][0].update(status='started')),
            ('boolean_stage_exit',D,lambda x:x['steps'][0].update(exit=False)),
            ('wrong_binary',D,lambda x:x['steps'][2]['argv'].__setitem__(3,'elsewhere.exe')),
            ('wrong_test_entrypoint',D,lambda x:x['steps'][2]['argv'].__setitem__(1,'another_test.py')),
            ('replay_instead_of_execute',D,lambda x:x['steps'][5]['argv'].append('--verify')),
            ('wrong_python_mode',D,lambda x:x['steps'][2]['argv'].insert(1,'-O')),
            ('installer_failed','qualification/test_installer_snapshot-powershell.json',lambda x:x['cases'][0].update(passed=False)),
            ('installer_bool_failed','qualification/test_installer_recovery-pwsh.json',setkey('failed',False)),
            ('upgrade_wrong_archive','qualification/upgrade-powershell.json',setkey('new_zip_sha256','0'*64)),
            ('preservation_wrong_version',P,setkey('shell_major',7)),
            ('preservation_wrong_script',P,setkey('script_sha256','0'*64)),
            ('preservation_failed',P,lambda x:x['checks'][0].update(passed=False)),
            ('missing_retained_stage',R,lambda x:x['steps'].pop()),
            ('reordered_retained_stage',R,lambda x:x['steps'].reverse()),
            ('boolean_retained_exit',R,lambda x:x['steps'][0].update(exit=False)),
            ('wrong_retained_log',R,lambda x:x['steps'][0].update(log_sha256='0'*64)),
            ('wrong_process_script','qualification/sqlite_check-normal/RESULT.json',setkey('script_sha256','0'*64)),
            ('process_skipped','qualification/sqlite_backup-normal/report.json',setkey('skipped',['not tested'])),
            ('pg_relabelled','qualification/postgres-hooks-normal/RESULT.json',setkey('postgres_executed',False)),
        ]
        for name,path,change in cases:
            with self.subTest(name=name):
                view=r.Reader(EVIDENCE);view.cache=self.reader.cache
                value=copy.deepcopy(view.obj(path));change(value);view.overrides[path]=r.canonical(value)
                with self.assertRaises((ValueError,KeyError,TypeError,IndexError)):
                    r.review(view,self.source)
                MUTATIONS.append(name)

    def test_every_stage_command_is_bound(self):
        driver_path = 'qualification/driver.json'
        original = self.reader.obj(driver_path)
        cases = []
        for index, row in enumerate(original['steps']):
            cases.append(('replaced_command_'+row['name'], index,
                          lambda args: ['echo', 'skipped-real-test']))
            if row['argv'][0].endswith('python.exe'):
                cases.append(('replaced_interpreter_'+row['name'], index,
                              lambda args: ['echo', *args[1:]]))
        def replace_at(index, value):
            def change(args):
                args[index] = value
                return args
            return change
        subtle = [
            ('script_outside_bundle', 'evaluation-normal',
             replace_at(1, r'D:\untrusted\test_model_evaluation.py')),
            ('duplicate_optimized_flag', 'evaluation-optimized',
             lambda args: [args[0], '-O', *args[1:]]),
            ('wrong_unittest_module', 'old-acceptance-normal', replace_at(2, 'fake_unittest')),
            ('wrong_powershell_version', 'upgrade-powershell', replace_at(0, 'pwsh')),
            ('wrong_installer_path', 'test_installer_snapshot-powershell',
             replace_at(10, r'D:\untrusted\Install-QbrainMemory.ps1')),
            ('changed_python_payload', 'existing-receipts-pwsh', replace_at(2, 'print("PASS")')),
            ('wrong_retained_baseline', 'retained55', replace_at(5, r'D:\untrusted\qbrain.exe')),
        ]
        positions = {row['name']: index for index, row in enumerate(original['steps'])}
        cases.extend((name, positions[stage], change) for name, stage, change in subtle)
        self.assertEqual(len(cases), 53)
        for name, index, change in cases:
            with self.subTest(name=name):
                view = r.Reader(EVIDENCE); view.cache = self.reader.cache
                driver = copy.deepcopy(original)
                driver['steps'][index]['argv'] = change(driver['steps'][index]['argv'])
                view.overrides[driver_path] = r.canonical(driver)
                with self.assertRaisesRegex(r.Rejected, 'stage_command_binding:'):
                    r.review(view, self.source)
                MUTATIONS.append(name)

    def test_corrupt_bytes(self):
        cases=[('appended_package','one/'+r.PACKAGE,self.reader.raw('one/'+r.PACKAGE)+b'X'),
               ('different_second_package','two/'+r.PACKAGE,b'not the first archive'),
               ('invalid_source_archive','source.zip',b'not a zip'),
               ('duplicate_acceptance','qualification/ACCEPTANCE.json',b'{"result":0,'+self.reader.raw('qualification/ACCEPTANCE.json')[1:]),
               ('wrong_raw_stream','qualification/sqlite_backup-normal/raw/000.stdout',b'{}'),
               ('edited_upgrade_assertions','qualification/test_n48s_upgrade.ps1',b'Write-Output "fake success"')]
        for name,path,raw in cases:
            with self.subTest(name=name):
                view=r.Reader(EVIDENCE);view.cache=self.reader.cache;view.overrides[path]=raw
                with self.assertRaises((ValueError,KeyError,zipfile.BadZipFile)):
                    r.review(view,self.source)
                MUTATIONS.append(name)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--canonical-source',type=Path,required=True);p.add_argument('--result',type=Path,required=True)
    a,rest=p.parse_known_args();EVIDENCE=a.evidence;SOURCE=a.canonical_source
    program=unittest.main(argv=[sys.argv[0],*rest],verbosity=2,exit=False)
    result=dict(schema='qbrain-n48s-independent-tests-v1',tests_run=program.result.testsRun,
                passed=program.result.wasSuccessful(),failures=len(program.result.failures),errors=len(program.result.errors),
                skipped=len(program.result.skipped),optimized=not __debug__,
                rejected_mutations=MUTATIONS,mutation_count=len(MUTATIONS),
                reviewer_sha256=r.sha(Path(r.__file__).read_bytes()),test_sha256=r.sha(Path(__file__).read_bytes()),
                product_executed=False)
    with a.result.open('xb') as f:f.write(r.canonical(result)+b'\n')
    raise SystemExit(0 if program.result.wasSuccessful() else 1)
