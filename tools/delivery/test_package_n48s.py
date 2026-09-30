"""Synthetic parser/assembly tests; do not equate fixtures with native acceptance."""
import copy
import io
from pathlib import Path
import struct
import unittest
import zipfile
import package_n48s as p

def image():
    raw=bytearray(2048)
    raw[:2]=b"MZ";struct.pack_into("<I",raw,0x3c,0x80)
    raw[0x80:0x84]=b"PE\0\0"
    struct.pack_into("<HHIIIHH",raw,0x84,0x8664,1,0,0,0,240,0x22)
    opt=0x98;struct.pack_into("<H",raw,opt,0x20b)
    struct.pack_into("<I",raw,opt+108,16)
    struct.pack_into("<II",raw,opt+112+8,0x1000,40)
    struct.pack_into("<II",raw,opt+112+13*8,0x1080,64)
    sec=opt+240;raw[sec:sec+8]=b".rdata\0\0"
    struct.pack_into("<IIII",raw,sec+8,1536,0x1000,1536,512)
    struct.pack_into("<IIIII",raw,512,1,0,0,0x1200,1)
    raw[1024:1037]=b"kernel32.dll\0"
    struct.pack_into("<IIIIIIII",raw,640,1,0x1240,1,1,1,0,0,0)
    raw[1088:1098]=b"libpq.dll\0"
    return raw

class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.binary=bytes(image())
        self.files={name:b"Synthetic source.\n" for name in p.FILES}
        self.guide=b"Synthetic guide, not accepted.\n"
        self.build=dict(schema="qbrain-n48s-build-v1",product_source=p.SOURCE,product_tree=p.TREE,
            binary_sha256=p.z.sha(self.binary),native_log_sha256="a"*64,
            native_groups=["group"+str(i) for i in range(60)],
            dependencies=p.dependencies(self.binary),compiler_reproducibility_verified=False)
    def expected(self):
        return p.expected(self.binary,self.files,self.guide,self.build)
    def test_boolean_metadata_and_section_overlay(self):
        self.build["dependencies"]["postgres_dependencies_bundled"]=0
        with self.assertRaises(ValueError):self.expected()
        raw=image();section=0x98+240
        struct.pack_into("<H",raw,0x86,2)
        raw[section+40:section+48]=b".bss\0\0\0\0"
        struct.pack_into("<IIII",raw,section+48,512,0x1000,0,0)
        with self.assertRaises(ValueError):p.dependencies(bytes(raw))
        # Disjoint virtual addresses do not permit aliasing raw section bytes.
        raw=image();struct.pack_into("<H",raw,0x86,2)
        raw[section+40:section+80]=raw[section:section+40]
        struct.pack_into("<I",raw,section+40+12,0x3000)
        with self.assertRaises(ValueError):p.dependencies(bytes(raw))
    def test_valid_dependencies(self):
        self.assertEqual(p.dependencies(self.binary)["eager"],["kernel32.dll"])
        self.assertEqual(p.dependencies(self.binary)["delayed"],["libpq.dll"])
    def test_pe_header_rejections(self):
        cases=[(0,b"NO"),(0x80,b"NOPE"),(0x84,struct.pack("<H",0x14c)),
               (0x86,struct.pack("<H",0)),(0x96,struct.pack("<H",0x2022)),
               (0x98,struct.pack("<H",0x10b)),(0x98+108,struct.pack("<I",13))]
        for pos,value in cases:
            raw=image();raw[pos:pos+len(value)]=value
            with self.subTest(pos=pos):
                with self.assertRaises((ValueError,struct.error)):p.dependencies(bytes(raw))
        for length in (0,255,511,1000):
            with self.subTest(length=length):
                with self.assertRaises(ValueError):p.dependencies(self.binary[:length])
    def test_ordinary_dependency_policy(self):
        for name in (b"libpq.dll",b"msvcp140.dll",b"vcruntime140.dll",b"mystery.dll",b"../evil.dll",b"C:\\evil.dll"):
            raw=image();raw[1024:1056]=name+b"\0"*(32-len(name))
            with self.subTest(name=name):
                with self.assertRaises(ValueError):p.dependencies(bytes(raw))
    def test_required_delay(self):
        for pos,value in [(0x98+112+13*8,b"\0"*8),(640,b"\0"*4),
                          (1088,b"other.dll\0")]:
            raw=image();raw[pos:pos+len(value)]=value
            with self.subTest(pos=pos):
                with self.assertRaises(ValueError):p.dependencies(bytes(raw))
    def test_unmapped_and_ambiguous_RVA(self):
        for address in (0,0x200,0x99999999,0x1600):
            raw=image();struct.pack_into("<I",raw,512+12,address)
            with self.subTest(address=address):
                with self.assertRaises(ValueError):p.dependencies(bytes(raw))
        raw=image();struct.pack_into("<H",raw,0x86,2)
        section=0x98+240
        raw[section+40:section+80]=raw[section:section+40]
        with self.assertRaises(ValueError):p.dependencies(bytes(raw))
    def test_table_count_and_terminator(self):
        for size in (1,20,21,20*129):
            raw=image();struct.pack_into("<I",raw,0x98+112+8+4,size)
            with self.subTest(size=size):
                with self.assertRaises(ValueError):p.dependencies(bytes(raw))
        raw=image();struct.pack_into("<I",raw,512+20,1)
        with self.assertRaises(ValueError):p.dependencies(bytes(raw))
    def test_name_requires_bounded_null(self):
        raw=image();raw[1024:1152]=b"x"*128
        with self.assertRaises(ValueError):p.dependencies(bytes(raw))
    def test_payload_and_build_rejection(self):
        original=copy.deepcopy(self.build)
        for key,value in (("product_source","b"*40),("product_tree","c"*40),
                          ("binary_sha256","0"*64),("native_log_sha256","x"),
                          ("native_groups",["same"]*60),("compiler_reproducibility_verified",True)):
            self.build=copy.deepcopy(original);self.build[key]=value
            with self.subTest(key=key):
                with self.assertRaises(ValueError):self.expected()
        self.build=original; self.files.pop(next(iter(self.files)))
        with self.assertRaises(ValueError):self.expected()
    def test_canonical_roundtrip(self):
        wanted=self.expected();raw=p.z.make_zip(wanted)
        self.assertEqual(p.verify(raw,wanted)["members"],len(p.FILES)+4)
        self.assertEqual(raw,p.z.make_zip(wanted))
        manifest=p.z.obj(wanted["MANIFEST.json"])
        self.assertEqual(manifest["status"],"BUILT_NOT_YET_ACCEPTED")
        self.assertIs(manifest["stable"],False)
    def test_payload_changed_and_rehashed(self):
        wanted=self.expected();modified=dict(wanted)
        modified["qbrain.exe"]=wanted["qbrain.exe"]+b"x"
        m=p.z.obj(modified["MANIFEST.json"])
        m["files"]=p.z.inventory({k:v for k,v in modified.items() if k!="MANIFEST.json"})
        modified["MANIFEST.json"]=p.z.encoded(m)
        with self.assertRaises(ValueError):p.verify(p.z.make_zip(modified),wanted)
    def test_noncanonical_container(self):
        wanted=self.expected();raw=p.z.make_zip(wanted)
        with self.assertRaises(ValueError):p.verify(raw+b"untrusted suffix",wanted)
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,"w") as archive:
            for name,value in wanted.items():archive.writestr(name,value)
        with self.assertRaises(ValueError):p.verify(buf.getvalue(),wanted)
    def test_extra_and_case_collision(self):
        wanted=self.expected()
        for name in ("UNEXPECTED.txt","QBRAIN.EXE"):
            changed={**wanted,name:b"extra"}
            with self.subTest(name=name):
                with self.assertRaises(ValueError):p.verify(p.z.make_zip(changed),wanted)

if __name__=="__main__":
    unittest.main(verbosity=2)
