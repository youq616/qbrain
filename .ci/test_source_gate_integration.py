"""Exercise the real pretest pin/identity functions, isolated by AST.

This boundary test deliberately does not import the PG/SQLite semantic readers.
Fake program files are hashed only, never executed. Git supplies fixture tree IDs.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import types
import unittest
import zipfile

import check_source_archive as checker
from test_source_archive import git_snapshot,archive,RecordingResult


def boundary(source,root):
    tree=ast.parse(source)
    selected=[]
    for node in tree.body:
        if isinstance(node,ast.FunctionDef) and node.name in ('need','read','sha','encode','pin','identity'):
            selected.append(node)
        elif isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('FILES','CAP') for t in node.targets):
            selected.append(node)
    ns=dict(Path=Path,hashlib=hashlib,re=re,zipfile=zipfile,ROOT=root,
      memory=types.SimpleNamespace(encode=lambda v:checker.encode(v)[:-1],decode=json.loads),
      source_archive=checker)
    exec(compile(ast.Module(body=selected,type_ignores=[]),'pin-boundary-only','exec'),ns)
    return ns


class IntegratedTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='qbrain-tree-gate-boundary-')
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.checkout=self.root/'checkout';self.checkout.mkdir()
        source=Path(__file__).with_name('run_pg_memory_gate.py').read_text()
        self.gate=boundary(source,self.checkout)
        self.commit='a'*40
        self.files={n:b'# isolated fixture for '+n.encode()+b'\n' for n in self.gate['FILES']}
        self.files['src/memory_runtime.cpp']=b'void memory_runtime() {}\n'
        for name,data in self.files.items():
            p=self.checkout/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        self.tree,self.index=git_snapshot(self.files)
        self.evidence=self.root/'evidence';self.evidence.mkdir()
        (self.evidence/'source.zip').write_bytes(archive(self.files))
        (self.evidence/'source-tree.bin').write_bytes(self.index)
        self.binary=self.root/'qbrain';self.binary.write_bytes(b'FAKE_PROGRAM_NEVER_EXECUTED')
        for name in ('qbrain_pg_memory_tests','qbrain_pg_memory_scope_tests'):
            (self.root/name).write_bytes(b'FAKE_TEST_NEVER_EXECUTED')
        for name,origin in [('qbrain','qbrain'),('pg-memory-tests','qbrain_pg_memory_tests'),('pg-scope-tests','qbrain_pg_memory_scope_tests')]:
            shutil.copyfile(self.root/origin,self.evidence/name)

    def pin(self):return self.gate['pin'](self.evidence,self.binary,self.commit,'linux',self.tree)
    def reject(self):
        with self.assertRaises(ValueError):self.pin()
        self.assertFalse((self.evidence/'review-pins.json').exists())

    def test_01_complete_pin_and_identity(self):
        pin=self.pin();result=self.gate['identity'](self.evidence,pin)
        self.assertEqual(result['schema'],'qbrain-n48o-pretest-pins-v2')
        self.assertEqual(result['source_tree'],self.tree)
        self.assertEqual(result['source_files'],len(self.files))

    def test_02_required_scripts_only_not_enough(self):
        partial={n:v for n,v in self.files.items() if n in self.gate['FILES']}
        (self.evidence/'source.zip').write_bytes(archive(partial));self.reject()

    def test_03_partial_manifest_cannot_reset_expected_tree(self):
        partial={n:v for n,v in self.files.items() if n in self.gate['FILES']}
        _,index=git_snapshot(partial)
        (self.evidence/'source.zip').write_bytes(archive(partial))
        (self.evidence/'source-tree.bin').write_bytes(index);self.reject()

    def test_04_runtime_change_before_pin(self):
        self.files['src/memory_runtime.cpp']=b'changed code\n'
        (self.evidence/'source.zip').write_bytes(archive(self.files));self.reject()

    def test_05_runtime_change_after_pin_even_rehashed_metadata(self):
        pin=self.pin();self.files['src/memory_runtime.cpp']=b'changed code\n'
        raw=archive(self.files);(self.evidence/'source.zip').write_bytes(raw)
        p=self.evidence/'review-pins.json';value=json.loads(p.read_bytes());value['source_sha256']=checker.sha256(raw)
        p.write_bytes(checker.encode(value))
        with self.assertRaises(ValueError):self.gate['identity'](self.evidence,pin)
        # Even explicitly trusting the rewritten metadata cannot evade the old tree.
        with self.assertRaises(ValueError):self.gate['identity'](self.evidence,checker.sha256(p.read_bytes()))

    def test_06_manifest_modification_after_pin(self):
        pin=self.pin();p=self.evidence/'source-tree.bin';p.write_bytes(self.index[:-1]+b'X')
        with self.assertRaises(ValueError):self.gate['identity'](self.evidence,pin)

    def test_07_v1_must_not_silently_fall_back(self):
        self.pin();p=self.evidence/'review-pins.json';r=json.loads(p.read_bytes());r['schema']='qbrain-n48o-pretest-pins-v1'
        for key in ('source_tree','source_manifest_sha256','source_files'):r.pop(key)
        raw=checker.encode(r);p.write_bytes(raw)
        with self.assertRaises(ValueError):self.gate['identity'](self.evidence,checker.sha256(raw))

    def test_08_boolean_coverage_rejected(self):
        self.pin();p=self.evidence/'review-pins.json';r=json.loads(p.read_bytes());r['source_files']=True
        raw=checker.encode(r);p.write_bytes(raw)
        with self.assertRaises(ValueError):self.gate['identity'](self.evidence,checker.sha256(raw))

    def test_09_binary_changed_since_pin(self):
        pin=self.pin();(self.evidence/'qbrain').write_bytes(b'CHANGED_PROGRAM_NOT_EXECUTED')
        with self.assertRaises(ValueError):self.gate['identity'](self.evidence,pin)

    def test_10_current_reviewer_component_changed(self):
        pin=self.pin();(self.checkout/'.ci/check_source_archive.py').write_bytes(b'changed reviewer')
        with self.assertRaises(ValueError):self.gate['identity'](self.evidence,pin)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,required=True);a=parser.parse_args()
    if a.report.exists():raise ValueError('report exists')
    result=unittest.TextTestRunner(verbosity=2,resultclass=RecordingResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(IntegratedTests))
    report=dict(schema='qbrain-source-gate-integration-tests-v1',passed=result.wasSuccessful(),
      tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
      records=result.records,optimized=not __debug__,native_program_executions=0,
      scope='pretest_pin_and_identity_functions_only',gate_sha256=checker.sha256(Path(__file__).with_name('run_pg_memory_gate.py').read_bytes()))
    with a.report.open('xb') as f:f.write(checker.encode(report))
    return int(not result.wasSuccessful())


if __name__=='__main__':raise SystemExit(main())
