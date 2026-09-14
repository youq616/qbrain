"""Readback-tool tests, not product or independent-agent acceptance."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('readback', ROOT/'tools/delivery/readback_n47a_candidate.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
from test_fact_process import EXPECTED_CHECKS, EXPECTED_COMMAND_COUNT


def encode(value):
    return json.dumps(value, separators=(',', ':')).encode('utf-8')


def fixture():
    names = ['case-'+str(i) for i in range(15)]
    test = '\n'.join('scenario("'+name+'", []{});' for name in names).encode()
    script = b'# synthetic standalone process fixture\n'
    source = {'tests/test_n47a.cpp':test, '.ci/test_fact_process.py':script}
    unit = dict(result='PASS',source_commit=m.SOURCE,tracked_tree_clean=True,native_windows=True,
        binary_sha256='1'*64,test_sha256=m.sha(test),exit_code=0,provider_calls=False,
        scenario_count=15,checks=380,scenarios=[dict(name=n,status='PASS',assertions=26) for n in names])
    unit['scenarios'][-1]['assertions']=16
    process = dict(result='PASS',source_commit=m.SOURCE,source_tree=m.TREE,tracked_tree_clean=True,
        native_windows=True,binary_sha256=m.sha(b'fake-exe-never-run'),script_sha256=m.sha(script),
        checks=[dict(name=n,status='PASS') for n in sorted(EXPECTED_CHECKS)],
        check_count=len(EXPECTED_CHECKS),counts=dict(total=len(EXPECTED_CHECKS),pass_=len(EXPECTED_CHECKS)))
    process['counts']={'total':len(EXPECTED_CHECKS),'pass':len(EXPECTED_CHECKS),'fail':0}
    process['commands']=[{'exit_code':0,'expected_exit':0} for _ in range(EXPECTED_COMMAND_COUNT)]
    process['commands'][-1]={'exit_code':1,'expected_exit':1}
    files={'qbrain.exe':b'fake-exe-never-run','verification/test_fact_process.py':script,
           'verification/fact-unit.json':encode(unit),'verification/fact-process.json':encode(process)}
    logs={'fact-unit.json':encode(unit),'fact-process.json':encode(process)}
    return files,source,logs


def mutate_report(files, logs, name, edit):
    value=json.loads(files['verification/'+name])
    edit(value)
    files['verification/'+name]=encode(value)
    logs[name]=encode(value)  # Make the equality check pass; semantic gates must still reject.


class CandidateReadbackTests(unittest.TestCase):
    def test_complete_fact_evidence(self):
        result=m.verify_fact_evidence(*fixture())
        self.assertEqual(result['unit'],{'scenarios':15,'assertions':380})
        self.assertEqual(result['process'],{'named_checks':34,'commands':118})
        self.assertFalse(result['probe_binary_independently_downloaded'])

    def test_missing_unit_cannot_pass(self):
        f,s,l=fixture();del f['verification/fact-unit.json']
        with self.assertRaises(KeyError):m.verify_fact_evidence(f,s,l)

    def test_unit_failure_not_hidden_by_other_pass_reports(self):
        for edit in [lambda x:x.update(result='FAIL'),lambda x:x.update(exit_code=1),
                     lambda x:x.update(exit_code=False),lambda x:x.update(tracked_tree_clean=False),
                     lambda x:x.update(native_windows=False),lambda x:x.update(error_type='Exception'),
                     lambda x:x.update(provider_calls=True),lambda x:x.update(source_commit='b'*40)]:
            f,s,l=fixture();mutate_report(f,l,'fact-unit.json',edit)
            with self.subTest(edit=edit),self.assertRaises(ValueError):m.verify_fact_evidence(f,s,l)

    def test_unit_partial_duplicate_and_reordered_cases(self):
        edits=[lambda x:x['scenarios'].clear(),lambda x:x['scenarios'].pop(),
               lambda x:x['scenarios'].reverse(),
               lambda x:x['scenarios'].__setitem__(-1,copy.deepcopy(x['scenarios'][0]))]
        for edit in edits:
            f,s,l=fixture();mutate_report(f,l,'fact-unit.json',edit)
            with self.subTest(edit=edit),self.assertRaises(ValueError):m.verify_fact_evidence(f,s,l)

    def test_wrong_assertion_or_scenario_totals(self):
        for edit in [lambda x:x.update(checks=381),lambda x:x.update(scenario_count=14),
                     lambda x:x['scenarios'][0].update(assertions=0),
                     lambda x:x['scenarios'][0].update(assertions=True),
                     lambda x:x['scenarios'][0].update(status='FAIL')]:
            f,s,l=fixture();mutate_report(f,l,'fact-unit.json',edit)
            with self.subTest(edit=edit),self.assertRaises(ValueError):m.verify_fact_evidence(f,s,l)

    def test_original_log_equality_required(self):
        f,s,l=fixture();l['fact-unit.json']=encode({'result':'PASS'})
        with self.assertRaises(ValueError):m.verify_fact_evidence(f,s,l)

    def test_source_and_product_bytes_bound(self):
        for path in ['qbrain.exe','verification/test_fact_process.py']:
            f,s,l=fixture();f[path]+=b'x'
            with self.subTest(path=path),self.assertRaises(ValueError):m.verify_fact_evidence(f,s,l)
        f,s,l=fixture();s['tests/test_n47a.cpp']+=b'// changed'
        with self.assertRaises(ValueError):m.verify_fact_evidence(f,s,l)

    def test_only_exact_checkout_conversion(self):
        raw=b'a\nb\n'
        self.assertEqual(m.checkout_bytes(raw,m.sha(b'a\r\nb\r\n')),b'a\r\nb\r\n')
        with self.assertRaises(ValueError):m.checkout_bytes(raw,m.sha(b'a \nb\n'))

    def test_process_count_and_expected_negative_exits(self):
        for edit in [lambda x:x['commands'].pop(),lambda x:x['commands'][-1].update(exit_code=0),
                     lambda x:x['commands'][0].update(exit_code=2),
                     lambda x:x.update(source_tree='0'*40),lambda x:x['counts'].update(fail=1)]:
            f,s,l=fixture();mutate_report(f,l,'fact-process.json',edit)
            with self.subTest(edit=edit),self.assertRaises(ValueError):m.verify_fact_evidence(f,s,l)

    def test_strict_json(self):
        for raw in [b'[]',b'{"a":1,"a":1}',b'{"n":NaN}',b'{"n":Infinity}',b'\xff']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):m.json_object(raw)
        self.assertEqual(m.json_object(b'\xef\xbb\xbf{"n":1}'),{'n':1})

    def test_inventory_no_unlisted_file_or_wrong_size(self):
        f={'a':b'abc','README-FIRST.txt':b'hello'}
        manifest={'files':{'a':{'bytes':3,'sha256':m.sha(b'abc')}}}
        f['MANIFEST.json']=encode(manifest)
        self.assertEqual(m.verify_inventory(f),manifest)
        f['extra']=b'x'
        with self.assertRaises(ValueError):m.verify_inventory(f)
        del f['extra'];manifest['files']['a']['bytes']=True;f['MANIFEST.json']=encode(manifest)
        with self.assertRaises(ValueError):m.verify_inventory(f)

    def test_wrong_artifact_hash_refused_before_parse(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'artifact';p.write_bytes(b'not even a zip')
            with patch.object(m,'unzip',side_effect=AssertionError('must not parse')):
                with self.assertRaisesRegex(ValueError,'Wrong artifact'):m.pinned(p,'source')

    def test_memory_only_archives_and_path_rejection(self):
        for name in ['../outside','/absolute','a/../b','a\\b','x:stream','a\x00b']:
            # ZipInfo normalizes Windows separators when constructing a fixture.
            # Patch both serialized name fields, not the already-normalized object.
            raw=io.BytesIO();encoded=name.encode('ascii');placeholder=b'Q'*len(encoded)
            with zipfile.ZipFile(raw,'w') as z:z.writestr(placeholder.decode('ascii'),b'x')
            data=raw.getvalue()
            self.assertEqual(data.count(placeholder),2)
            data=data.replace(placeholder,encoded)
            with self.subTest(name=name),self.assertRaises(ValueError):m.unzip(data)
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,'w') as z:
            entry=zipfile.ZipInfo('link');entry.create_system=3
            entry.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(entry,b'target')
        with self.assertRaises(ValueError):m.unzip(raw.getvalue())

    def test_member_and_expansion_caps(self):
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('zeros',b'0'*4000)
        with patch.object(m,'CAP',1000),self.assertRaises(ValueError):m.unzip(raw.getvalue())

    def test_git_tree_reconstruction(self):
        self.assertEqual(m.git_tree({}),'4b825dc642cb6eb9a060e54bf8d69288fbee4904')
        files={'z.txt':b'hello\n','a/x.txt':b'x','a.c':b'y','a-b':b'z','unicode/中文':b'abc'}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            subprocess.run(['git','init','-q',str(root)],check=True)
            for name,data in files.items():
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            subprocess.run(['git','-C',d,'-c','core.autocrlf=false','-c','core.filemode=false','add','-f','--all'],check=True)
            expected=subprocess.check_output(['git','-C',d,'write-tree'],text=True).strip()
        self.assertEqual(m.git_tree(files),expected)

    def test_no_native_execution_or_publication_flag_in_fixture(self):
        r=m.verify_fact_evidence(*fixture())
        self.assertFalse(r['probe_binary_independently_downloaded'])
        self.assertNotIn('independent_review',r)


if __name__=='__main__':unittest.main(verbosity=2)
