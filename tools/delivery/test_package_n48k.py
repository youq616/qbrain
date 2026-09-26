"""Package integrity fixtures are not native build or publication evidence."""
import copy
import io
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile
from unittest.mock import patch
import package_n48k as p


def inputs():
    raw = bytearray(512); raw[:2] = b'MZ'; struct.pack_into('<I', raw, 60, 128)
    raw[128:132] = b'PE\0\0'; struct.pack_into('<H', raw, 132, 0x8664); struct.pack_into('<H', raw, 152, 0x20b)
    binary = bytes(raw)
    files = {name: ('fixture '+name+'\n').encode() for name in p.FILES}
    receipt = {'schema':'qbrain-n48k-build-v1','source_commit':p.SOURCE,'source_tree':p.TREE,
               'binary_sha256':p.z.sha(binary),'native_groups':['group_'+str(i) for i in range(60)],
               'native_log_sha256':'a'*64, 'live_pg_skipped':True, 'compiler_output_reproducible':False}
    return binary, files, b'fixture guide\n', receipt


class Package(unittest.TestCase):
    def setUp(self): self.args = inputs(); self.wanted = p.expected(*self.args)
    def test_compiler_profile_and_runtime_isolation_are_separate(self):
        from check_n48k_bundle import environments
        roots = dict(HOME='real-home', USERPROFILE='real-profile', APPDATA='real-roaming', LOCALAPPDATA='real-local')
        original = {**roots, 'PATH':'native-tools', 'QBRAIN_EVAL_KEY':'secret', 'OPENAI_API_KEY':'secret', 'GITHUB_TOKEN':'secret'}
        saved = original.copy()
        toolchain, runtime = environments(original,'isolated-temp')
        self.assertEqual(original,saved)
        for name,value in roots.items():
            self.assertEqual(toolchain[name],value)
            self.assertEqual(runtime[name],'isolated-temp')
        for mapping in (toolchain,runtime):
            self.assertEqual(mapping['PATH'],'native-tools')
            self.assertEqual(mapping['PYTHONDONTWRITEBYTECODE'],'1')
            self.assertFalse(any(key.endswith('KEY') or key=='GITHUB_TOKEN' for key in mapping))
        runtime['PATH']='changed'
        self.assertEqual(toolchain['PATH'],'native-tools')

    def test_deterministic_complete_membership(self):
        raw = p.z.make_zip(self.wanted)
        self.assertEqual(raw, p.z.make_zip(dict(reversed(list(self.wanted.items())))))
        r = p.verify(raw, self.wanted)
        self.assertEqual(r['members'], len(p.FILES)+4)
        self.assertFalse(r['new_product_execution'])
    def test_tampered_components_with_forged_inventory(self):
        for name in ('qbrain.exe','scripts/Install-QbrainMemory.ps1','scripts/Invoke-QbrainJson.ps1',
                     'tools/acceptance/model_ab.py','START-HERE.zh-CN.md'):
            with self.subTest(name=name):
                files = dict(self.wanted); files[name] += b'altered'
                m = p.z.obj(files['MANIFEST.json']); m['files'] = p.z.inventory({k:v for k,v in files.items() if k != 'MANIFEST.json'})
                files['MANIFEST.json'] = p.z.encoded(m)
                with self.assertRaises(ValueError): p.verify(p.z.make_zip(files), self.wanted)
    def test_forged_acceptance_and_source(self):
        for key, val in (('product_source','f'*40),('native_bundle_tests','PASS'),('signed',True),('stable_v1',True)):
            files = dict(self.wanted); m=p.z.obj(files['MANIFEST.json']);m[key]=val;files['MANIFEST.json']=p.z.encoded(m)
            with self.assertRaises(ValueError):p.verify(p.z.make_zip(files),self.wanted)
    def test_missing_and_extra_members(self):
        for extra in (True,False):
            f=dict(self.wanted)
            if extra:f['secret.txt']=b'not permitted'
            else:del f['tools/acceptance/model_ab.py']
            with self.assertRaises(ValueError):p.verify(p.z.make_zip(f),self.wanted)
    def test_noncanonical_zip(self):
        stream=io.BytesIO(p.z.make_zip(self.wanted))
        with zipfile.ZipFile(stream,'a') as z:z.comment=b'changed'
        with self.assertRaises(ValueError):p.verify(stream.getvalue(),self.wanted)
    def test_windows_unsafe_paths(self):
        for name in ('../escape','C:/file','name:stream','CON.txt','a\\b','file.','a/../b'):
            with self.assertRaises(ValueError):p.z.windows_path(name)
    def test_case_collisions_and_file_parent(self):
        for names in (('A','a'),('scripts','scripts/file')):
            buf=io.BytesIO()
            with zipfile.ZipFile(buf,'w') as z:
                for name in names:z.writestr(name,b'x')
            with self.assertRaises(ValueError):p.z.archive_files(buf.getvalue())
    def test_wrong_binary_or_receipt(self):
        for index,value in ((0,b'old file'),(3,{**self.args[3],'binary_sha256':'0'*64}),
                            (3,{**self.args[3],'source_commit':'0'*40}),
                            (3,{**self.args[3],'native_groups':['duplicate']*60})):
            args=list(self.args);args[index]=value
            with self.assertRaises(ValueError):p.expected(*args)
    def test_wrong_pe_architecture(self):
        b=bytearray(self.args[0]);struct.pack_into('<H',b,132,0x14c)
        with self.assertRaises(ValueError):p.pe64(bytes(b))
    def test_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'result';first=p.save(out,self.wanted);raw=(out/p.PRODUCT).read_bytes()
            with self.assertRaises(FileExistsError):p.save(out,self.wanted)
            self.assertEqual(raw,(out/p.PRODUCT).read_bytes())
            self.assertEqual(first['sha256'],p.z.sha(raw))
    def test_dirty_or_wrong_source_before_materialization(self):
        with patch.object(p,'regular'), patch.object(p,'git',side_effect=[(p.SOURCE+'\n').encode(),(p.TREE+'\n').encode(),b'src/changed.cpp']):
            with self.assertRaises(ValueError):p.source_files(Path('.'))
        with patch.object(p,'regular'), patch.object(p,'git',return_value=b'wrong'):
            with self.assertRaises(ValueError):p.source_files(Path('.'))
    def test_source_canonical_script_newlines(self):
        def git(root,*args):
            if args == ('rev-parse','HEAD'):return p.SOURCE.encode()
            if args == ('rev-parse','HEAD^{tree}'):return p.TREE.encode()
            if args[0]=='diff':return b''
            return b'fixture\nline\n'
        with patch.object(p,'regular'), patch.object(p,'read',return_value=b'fixture\nline\n'), patch.object(p,'git',side_effect=git):
            files=p.source_files(Path('.'))
            self.assertEqual(files['scripts/Invoke-QbrainJson.ps1'],b'fixture\r\nline\r\n')
            self.assertEqual(files['tools/acceptance/model_ab.py'],b'fixture\nline\n')




    def test_all_current_tool_dependencies_and_examples_present(self):
        for name in ('model_cost', 'model_ab', 'memory_task_contract', 'run_memory_tasks', 'test_model_cost', 'test_memory_tasks'):
            self.assertIn('tools/acceptance/'+name+'.py', self.wanted)
        self.assertIn('examples/cost/compare-basic.json', self.wanted)
        self.assertIn('examples/cost/stream-openai_chat.json', self.wanted)
        self.assertEqual(len(p.FILES),len(set(p.FILES)))
        self.assertEqual(len(self.wanted),51)
    def test_no_sensitive_or_build_members(self):
        self.assertTrue(all(not any(word in s.lower() for word in ('.env','secret','brain.db','build/','.ci/')) for s in p.FILES))
    def test_build_receipt_types_and_no_self_acceptance(self):
        for key,value in (('native_groups',[True]*60),('live_pg_skipped',0),('compiler_output_reproducible',0),
                          ('native_log_sha256','bad'),('native_log_sha256',False),('native_groups',['a']*60),('extra','test')):
            args=list(self.args); args[3]={**args[3],key:value}
            with self.subTest(key=key):
                with self.assertRaises(ValueError):p.expected(*args)
    def test_guide_limits_and_utf8(self):
        for guide in (b'',b'x'*32769,b'\xff'):
            with self.assertRaises(ValueError):p.expected(*self.args[:2],guide,self.args[3])
    def test_each_payload_missing_or_changed(self):
        for name in p.FILES:
            with self.subTest(name=name):
                files=dict(self.wanted);files.pop(name)
                with self.assertRaises(ValueError):p.verify(p.z.make_zip(files),self.wanted)
    def test_duplicate_and_symlink_zip(self):
        for kind in ('duplicate','link','directory'):
            buf=io.BytesIO()
            with zipfile.ZipFile(buf,'w') as archive:
                info=zipfile.ZipInfo('entry')
                info.create_system=3
                info.external_attr=(0o120777 if kind=='link' else 0o100644)<<16
                if kind=='directory':info.filename='entry/'
                archive.writestr(info,b'x')
                if kind=='duplicate':
                    with self.assertWarns(UserWarning):archive.writestr(info,b'x')
            with self.assertRaises(ValueError):p.verify(buf.getvalue(),self.wanted)
    def test_prefix_suffix_crc_and_metadata(self):
        raw=p.z.make_zip(self.wanted)
        for forged in (b'prefix'+raw,raw+b'trailing',raw[:-1]):
            with self.assertRaises((ValueError,zipfile.BadZipFile)):p.verify(forged,self.wanted)
        files=dict(self.wanted);files['MANIFEST.json']=b'{"files":{},"files":{}}'
        with self.assertRaises(ValueError):p.verify(p.z.make_zip(files),self.wanted)
    def test_archive_and_member_limits(self):
        with self.assertRaises(ValueError):p.z.archive_files(b' '* (p.z.MAX_ARCHIVE+1))
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as archive:
            for i in range(p.z.MAX_MEMBERS+1):archive.writestr(str(i),b'')
        with self.assertRaises(ValueError):p.z.archive_files(buf.getvalue())
    def test_filesystem_link_and_nonregular(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);file=root/'file';file.write_bytes(b'x')
            self.assertEqual(p.read(file),b'x')
            with self.assertRaises(ValueError):p.read(root)
            link=root/'alias'
            try:link.symlink_to(file)
            except OSError:self.skipTest('Symlink unavailable on this runner')
            with self.assertRaises(ValueError):p.read(link)
            parent=root/'parent';parent.symlink_to(root,target_is_directory=True)
            with self.assertRaises(ValueError):p.read(parent/'file')
    def test_corrupt_worktree_fails_even_with_clean_git_claim(self):
        def git(root,*args):
            if args==('rev-parse','HEAD'):return p.SOURCE.encode()
            if args==('rev-parse','HEAD^{tree}'):return p.TREE.encode()
            if args[0]=='diff':return b''
            return b'valid\n'
        with patch.object(p,'regular'),patch.object(p,'git',side_effect=git),patch.object(p,'read',return_value=b'changed\n'):
            with self.assertRaises(ValueError):p.source_files(Path('.'))
    def test_synthetic_pe_is_not_execution_evidence(self):
        check=p.verify(p.z.make_zip(self.wanted),self.wanted)
        self.assertFalse(check['new_product_execution'])
        manifest=p.z.obj(self.wanted['MANIFEST.json'])
        self.assertEqual(manifest['status'],'BUILT_NOT_YET_ACCEPTED')
        self.assertFalse(manifest['signed']);self.assertFalse(manifest['stable_v1'])

if __name__=='__main__':unittest.main(verbosity=2)
