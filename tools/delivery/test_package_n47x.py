"""Package integrity fixtures are not native build or publication evidence."""
import copy
import io
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile
from unittest.mock import patch
import package_n47x as p


def inputs():
    raw = bytearray(512); raw[:2] = b'MZ'; struct.pack_into('<I', raw, 60, 128)
    raw[128:132] = b'PE\0\0'; struct.pack_into('<H', raw, 132, 0x8664); struct.pack_into('<H', raw, 152, 0x20b)
    binary = bytes(raw)
    files = {name: ('fixture '+name+'\n').encode() for name in p.FILES}
    receipt = {'schema':'qbrain-n47x-build-v1','source_commit':p.SOURCE,'source_tree':p.TREE,
               'binary_sha256':p.z.sha(binary),'native_groups':['group_'+str(i) for i in range(60)]}
    return binary, files, b'fixture guide\n', receipt


class Package(unittest.TestCase):
    def setUp(self): self.args = inputs(); self.wanted = p.expected(*self.args)
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
        with patch.object(p,'git',side_effect=[(p.SOURCE+'\n').encode(),(p.TREE+'\n').encode(),b'src/changed.cpp']):
            with self.assertRaises(ValueError):p.source_files(Path('.'))
        with patch.object(p,'git',return_value=b'wrong'):
            with self.assertRaises(ValueError):p.source_files(Path('.'))
    def test_source_canonical_script_newlines(self):
        def git(root,*args):
            if args == ('rev-parse','HEAD'):return p.SOURCE.encode()
            if args == ('rev-parse','HEAD^{tree}'):return p.TREE.encode()
            if args[0]=='diff':return b''
            return b'fixture\nline\n'
        with patch.object(p,'git',side_effect=git):
            files=p.source_files(Path('.'))
            self.assertEqual(files['scripts/Invoke-QbrainJson.ps1'],b'fixture\r\nline\r\n')
            self.assertEqual(files['tools/acceptance/model_ab.py'],b'fixture\nline\n')


if __name__=='__main__':unittest.main(verbosity=2)
