"""Independent Git-plumbing oracle for the source-tree acceptance module.

Fixture tree IDs and manifests come from real Git, not checker implementations.
No downloaded executable, PostgreSQL, network, or real user database is invoked.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from unittest.mock import patch

import check_source_archive as c
COMMIT = 'a' * 40
ARGS = None


def git_snapshot(files, modes=None):
    with tempfile.TemporaryDirectory(prefix='qbrain-source-git-') as tmp:
        def git(*args, data=None):
            env={k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_')}
            env.update(GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_SYSTEM=os.devnull)
            return subprocess.run(['git','-C',tmp,*args],input=data,capture_output=True,check=True,env=env).stdout
        git('init','-q')
        for name,raw in files.items():
            oid=git('hash-object','-w','--stdin',data=raw).decode().strip()
            git('update-index','--add','--cacheinfo',(modes or {}).get(name,'100644'),oid,name)
        tree=git('write-tree').decode().strip()
        return tree,git('ls-tree','--full-tree','-r','-z',tree)


def archive(files, comment=COMMIT, modes=None, extra=None):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        z.comment=comment.encode()
        for name,raw in files.items():
            entry=zipfile.ZipInfo(name)
            entry.external_attr=int((modes or {}).get(name,'100644'),8)<<16
            z.writestr(entry,raw)
        if extra:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',UserWarning)
                z.writestr(*extra)
    return out.getvalue()


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files={'a/file.cpp':b'int main() { return 0; }\n','a.txt':b'hello\n',
          'binary/icon.dat':b'\x89PNG\r\n\x1a\n\0payload',
          'binary/signature.png':b'\x89PNG\r\n\x1a\n',
          'legacy.txt':b'Caf\xe9 legacy\n','text.png':b'not a png\n',
          'src/中文.cpp':'// 中文😀\n'.encode()}
        cls.tree,cls.manifest=git_snapshot(cls.files)
        cls.raw=archive(cls.files)

    def ok(self,raw=None,manifest=None,tree=None,platform='linux',commit=COMMIT):
        return c.verify_bytes(self.raw if raw is None else raw,
                              self.manifest if manifest is None else manifest,
                              commit,self.tree if tree is None else tree,platform)

    def bad(self,**args):
        with self.assertRaises((c.Rejected,zipfile.BadZipFile,UnicodeError,ValueError)):
            self.ok(**args)

    def test_01_exact_tree_from_independent_git(self):
        r=self.ok();self.assertEqual(r['source_files'],7);self.assertEqual(r['byte_exact_files'],7)
        self.assertFalse(r['source_origin_authenticated']);self.assertFalse(r['binary_build_attested'])

    def test_02_windows_text_and_opaque_binary(self):
        files={n:(v.replace(b'\n',b'\r\n') if not n.startswith('binary/') else v) for n,v in self.files.items()}
        r=self.ok(raw=archive(files),platform='windows')
        self.assertEqual(r['exact_crlf_to_lf_files'],5);self.assertEqual(r['byte_exact_files'],2)

    def test_03_linux_cannot_hide_content_behind_crlf(self):
        files=self.files.copy();files['a.txt']=b'hello\r\n';self.bad(raw=archive(files))

    def test_04_binary_crlf_rewriting_rejected(self):
        for name in ('binary/icon.dat','binary/signature.png'):
            files=self.files.copy();files[name]=files[name].replace(b'\n',b'\r\n')
            with self.subTest(file=name):self.bad(raw=archive(files),platform='windows')

    def test_05_missing_runtime_despite_correct_commit(self):
        self.bad(raw=archive({'a.txt':self.files['a.txt']}))

    def test_06_runtime_replaced(self):
        files=self.files.copy();files['a/file.cpp']=b'int main() { return 1; }\n'
        self.bad(raw=archive(files))

    def test_07_coordinated_manifest_and_archive_do_not_override_tree_pin(self):
        files=self.files.copy();files['a/file.cpp']=b'changed runtime\n'
        newtree,newmanifest=git_snapshot(files)
        self.assertNotEqual(newtree,self.tree)
        self.bad(raw=archive(files),manifest=newmanifest)

    def test_08_wrong_commit_or_external_tree(self):
        self.bad(raw=archive(self.files,comment='b'*40));self.bad(tree='0'*40)
        for pin in ('',True,'g'*40,'abc'):
            with self.subTest(pin=pin):self.bad(tree=pin)

    def test_09_archive_extra_file_and_directory(self):
        self.bad(raw=archive(self.files,extra=('extra',b'not in commit')))
        self.bad(raw=archive(self.files,extra=('empty-unknown/',b'')))

    def test_10_duplicate_archive_member(self):
        self.bad(raw=archive(self.files,extra=('a.txt',self.files['a.txt'])))

    def test_11_manifest_duplicate_path(self):
        self.bad(manifest=self.manifest+self.manifest.split(b'\0')[0]+b'\0')

    def test_12_zip_path_tricks(self):
        for name in ('../escape','/absolute','a/../escape','a//x','./file','C:secret',r'a\x'):
            with self.subTest(path=name):self.bad(raw=archive(self.files,extra=(name,b'x')))

    def test_13_symlink_submodule_modes_refused(self):
        for mode in (b'120000',b'160000'):
            with self.subTest(mode=mode):self.bad(manifest=self.manifest.replace(b'100644',mode,1))
        self.bad(raw=archive(self.files,modes={'a.txt':'120777'}))

    def test_14_executable_modes_bound_by_git(self):
        tree,manifest=git_snapshot({'run.sh':b'exit 0\n'},{'run.sh':'100755'})
        self.ok(raw=archive({'run.sh':b'exit 0\n'},modes={'run.sh':'100755'}),manifest=manifest,tree=tree)
        self.bad(raw=archive({'run.sh':b'exit 0\n'}),manifest=manifest,tree=tree)

    def test_15_reordered_manifest_and_archive(self):
        manifest=b'\0'.join(reversed(self.manifest[:-1].split(b'\0')))+b'\0'
        files=dict(reversed(list(self.files.items())))
        self.assertEqual(self.ok(raw=archive(files),manifest=manifest)['tree'],self.tree)

    def test_16_malformed_or_truncated_manifest(self):
        for raw in (b'',self.manifest[:-1],b'garbage\0',self.manifest.replace(b' blob ',b' tree ',1)):
            with self.subTest(input=raw[:20]):self.bad(manifest=raw)

    def test_17_case_collisions_block_windows(self):
        tree,manifest=git_snapshot({'Case.txt':b'a','case.txt':b'b'})
        raw=archive({'Case.txt':b'a','case.txt':b'b'})
        self.ok(raw=raw,manifest=manifest,tree=tree)
        self.bad(raw=raw,manifest=manifest,tree=tree,platform='windows')

    def test_18_bounded_input_member_and_aggregate(self):
        with patch.object(c,'ARCHIVE_CAP',len(self.raw)-1):self.bad()
        with patch.object(c,'MANIFEST_CAP',len(self.manifest)-1):self.bad()
        with patch.object(c,'MEMBER_CAP',1):self.bad()
        with patch.object(c,'UNPACKED_CAP',1):self.bad()
        with patch.object(c,'FILE_CAP',1):self.bad()

    def test_19_external_archive_pin(self):
        c.verify_bytes(self.raw,self.manifest,COMMIT,self.tree,'linux',c.sha256(self.raw))
        with self.assertRaises(c.Rejected):c.verify_bytes(self.raw,self.manifest,COMMIT,self.tree,'linux','0'*64)

    def test_20_crc_or_zip_corruption(self):
        self.bad(raw=b'not a zip')
        raw=bytearray(self.raw);raw[45]^=0xff
        self.bad(raw=bytes(raw))

    def test_21_cli_roundtrip_no_overwrite_no_input_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a=root/'source.zip';m=root/'tree.bin';o=root/'result.json'
            a.write_bytes(self.raw);m.write_bytes(self.manifest)
            args=['--archive',str(a),'--tree-manifest',str(m),'--expected-commit',COMMIT,
                  '--expected-tree',self.tree,'--platform','linux','--output',str(o)]
            def cli(action):
                return subprocess.run([sys.executable,str(Path(c.__file__)),action,*args],capture_output=True,timeout=20)
            p=cli('check');self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            self.assertEqual(cli('verify-report').returncode,0)
            self.assertEqual(cli('check').returncode,2)
            report=json.loads(o.read_bytes());report['binary_build_attested']=True;o.write_bytes(c.encode(report))
            self.assertEqual(cli('verify-report').returncode,2)
            self.assertEqual(a.read_bytes(),self.raw);self.assertEqual(m.read_bytes(),self.manifest)

    def test_22_linked_input_and_parent_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'x';p.write_bytes(b'test')
            if os.name=='nt':
                with patch.object(c.stat,'S_ISLNK',return_value=True):
                    with self.assertRaises(c.Rejected):c.read_file(p,10)
            else:
                link=root/'link';link.symlink_to(p)
                with self.assertRaises(c.Rejected):c.read_file(link,10)
                parent=root/'parent';parent.symlink_to(root,target_is_directory=True)
                with self.assertRaises(c.Rejected):c.read_file(parent/'x',10)

    def test_23_output_error_is_body_free(self):
        with tempfile.TemporaryDirectory(prefix='PRIVATE_PATH_') as tmp:
            root=Path(tmp);a=root/'a';m=root/'m';a.write_bytes(self.raw);m.write_bytes(self.manifest)
            p=subprocess.run([sys.executable,str(Path(c.__file__)),'check','--archive',str(a),
                  '--tree-manifest',str(m),'--expected-commit',COMMIT,'--expected-tree','0'*40,
                  '--platform','linux','--output',str(root/'out')],capture_output=True,timeout=20)
            self.assertEqual(p.returncode,2);self.assertEqual(p.stderr,b'')
            self.assertNotIn(b'PRIVATE_PATH',p.stdout);self.assertFalse((root/'out').exists())

    def test_24_input_mutation_at_recheck_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a=root/'a';m=root/'m';a.write_bytes(self.raw);m.write_bytes(self.manifest)
            original=c.verify_bytes
            def mutate(*args,**kwargs):
                result=original(*args,**kwargs);a.write_bytes(self.raw+b'changed');return result
            with patch.object(c,'verify_bytes',mutate):
                with self.assertRaises(c.Rejected):c.verify_files(a,m,COMMIT,self.tree,'linux')

    def test_25_control_bytes_never_hidden_as_line_endings(self):
        self.assertFalse(c.crlf_text(b'\0\r\n'))
        self.assertFalse(c.crlf_text(b'bare\rcontrol\r\n'))
        self.assertFalse(c.crlf_text(b'\x89PNG\r\n\x1a\n'))
        self.assertTrue(c.crlf_text(b'legacy Caf\xe9\r\n'))


class RealArchiveTests(unittest.TestCase):
    def test_linux_complete_1480_file_tree(self):
        self.verify('linux')
    def test_windows_complete_1480_file_tree(self):
        self.verify('windows')
    def verify(self,platform):
        root=ARGS.reference_root
        r=c.verify_files(root/platform/'source.zip',root/'source-tree.bin',
           'cd4ca9ae35d846b16738f8ed66dde88f1bf841b5',
           'd002f900552ef4ae58556296b28e95de31e17a1f',platform)
        self.assertEqual(r['source_files'],1480)
        self.assertEqual(r['source_files'],r['byte_exact_files']+r['exact_crlf_to_lf_files'])
        if platform=='linux':self.assertEqual(r['exact_crlf_to_lf_files'],0)
        else:self.assertGreater(r['exact_crlf_to_lf_files'],1400)


class RecordingResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.records=[]
    def addSuccess(self,test):super().addSuccess(test);self.records.append({'test':test.id(),'result':'PASS'})
    def addFailure(self,test,err):super().addFailure(test,err);self.records.append({'test':test.id(),'result':'FAIL'})
    def addError(self,test,err):super().addError(test,err);self.records.append({'test':test.id(),'result':'ERROR'})


def main():
    global ARGS
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-root',type=Path)
    parser.add_argument('--report',type=Path,required=True)
    ARGS=parser.parse_args()
    if ARGS.report.exists():raise ValueError('refuse report overwrite')
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ContractTests)
    if ARGS.reference_root:suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(RealArchiveTests))
    result=unittest.TextTestRunner(verbosity=2,resultclass=RecordingResult).run(suite)
    report=dict(schema='qbrain-source-tree-tests-v1',passed=result.wasSuccessful(),tests=result.testsRun,
      failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
      records=result.records,optimized=not __debug__,execution_os=os.name,
      real_archives_checked=2 if ARGS.reference_root else 0,new_postgresql_execution=False,
      checker_sha256=c.sha256(Path(c.__file__).read_bytes()),test_sha256=c.sha256(Path(__file__).read_bytes()))
    with ARGS.report.open('xb') as f:f.write(c.encode(report))
    return int(not result.wasSuccessful())


if __name__=='__main__':raise SystemExit(main())
