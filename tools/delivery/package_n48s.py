"""N48S unified Windows candidate. Offline assembly; acceptance is a later receipt."""
from __future__ import annotations
import argparse
from pathlib import Path
import re
import struct
import subprocess
import types
import zipfile
import package_n48k as old

z = old.z
SOURCE = "e0a27f829d970c24ed8c566023ada0911c0042b3"
TREE = "534c86deabf43e30d3b2533cd3bf1f0728cf8400"
PRODUCT = "qbrain-windows-x64-n48s-candidate.zip"
EXTRA_GUIDES = ("MODEL-QUALITY-COST", "SQLITE-BACKUP", "SQLITE-CHECK",
                "POSTGRES-SESSION-MEMORY", "POSTGRES-LAYERED-CONTEXT",
                "POSTGRES-STRUCTURED-FACTS", "POSTGRES-HOOKS")
FILES = old.FILES + ("tools/acceptance/model_evaluation.py",
                     "tools/acceptance/test_model_evaluation.py") + tuple(
    "docs/integration/" + n + ".zh-CN.md" for n in EXTRA_GUIDES) + (
    "examples/context/pg-context.synthetic.txt",)
# Only direct imports are classified. PG's transitive dependencies are NOT bundled.
SYSTEM = frozenset(("kernel32.dll", "advapi32.dll", "bcrypt.dll", "shell32.dll",
                    "ole32.dll", "user32.dll", "winhttp.dll", "ws2_32.dll",
                    "ntdll.dll", "gdi32.dll", "secur32.dll", "crypt32.dll",
                    "shlwapi.dll", "comdlg32.dll", "version.dll", "iphlpapi.dll"))

def dependencies(raw: bytes) -> dict:
    """Read bounded PE32+ import descriptors, never load/execute the image."""
    z.need(type(raw) is bytes and 256 <= len(raw) <= z.MAX_FILE, "PE size")
    def unpack(fmt, pos):
        size = struct.calcsize(fmt)
        z.need(type(pos) is int and 0 <= pos <= len(raw)-size, "PE bounds")
        return struct.unpack_from(fmt, raw, pos)
    z.need(raw[:2] == b"MZ", "PE DOS")
    pe, = unpack("<I", 0x3c)
    z.need(pe >= 64 and raw[pe:pe+4] == b"PE\0\0", "PE signature")
    machine, count, _, _, _, opt_size, chars = unpack("<HHIIIHH", pe+4)
    z.need(machine == 0x8664 and 1 <= count <= 96 and chars & 2 and not chars & 0x2000, "PE executable")
    opt = pe+24
    z.need(opt_size >= 240 and opt+opt_size+count*40 <= len(raw), "PE optional size")
    z.need(unpack("<H", opt)[0] == 0x20b, "PE32+ required")
    directory_count, = unpack("<I", opt+108)
    z.need(14 <= directory_count <= 16 and 112+directory_count*8 <= opt_size, "PE directories")
    sections = []
    for i in range(count):
        base = opt+opt_size+i*40
        vs, va, length, offset = unpack("<IIII", base+8)
        z.need(offset+length <= len(raw), "PE section bounds")
        sections.append((va, max(vs, length), length, offset))
    def rva(address, length):
        matches = [off+address-va for va, span, size, off in sections
                   if va <= address and address-va+length <= size]
        z.need(address > 0 and length > 0 and len(matches) == 1, "PE ambiguous/unmapped RVA")
        return matches[0]
    def dll(address):
        begin = rva(address, 1)
        end = raw.find(b"\0", begin, min(begin+128, len(raw)))
        z.need(end > begin and rva(address, end-begin+1) == begin, "PE DLL name")
        value = raw[begin:end].decode("ascii").lower()
        z.need(re.fullmatch(r"[a-z0-9_-]+\.dll", value) is not None, "PE DLL syntax")
        return value
    def table(index, width, name_index, delayed):
        address, size = unpack("<II", opt+112+index*8)
        z.need(bool(address) == bool(size), "PE directory pair")
        if not size:
            return []
        z.need(width <= size <= width*128 and size % width == 0, "PE descriptor count")
        begin = rva(address, size)
        out = []
        for j in range(size//width):
            fields = unpack("<" + "I"*(width//4), begin+j*width)
            if not any(fields):
                z.need(not any(raw[begin+(j+1)*width:begin+size]), "PE trailing descriptors")
                z.need(len(out) == len(set(out)), "PE duplicate DLL")
                return sorted(out)
            if delayed:
                z.need(fields[0] == 1, "PE delay RVA attributes")
            out.append(dll(fields[name_index]))
        raise ValueError("PE missing descriptor terminator")
    eager, delayed = table(1, 20, 3, False), table(13, 32, 1, True)
    z.need(bool(eager) and set(eager) <= SYSTEM, "non-system eager dependency")
    z.need(delayed == ["libpq.dll"], "expected delayed PostgreSQL dependency")
    return dict(machine="AMD64", format="PE32+", eager=eager, delayed=delayed,
                scope="direct_import_tables_only", postgres_dependencies_bundled=False)

def source_files(root: Path) -> dict[str, bytes]:
    old.regular(root, True)
    z.need(old.git(root, "rev-parse", "HEAD").decode().strip() == SOURCE, "product commit")
    z.need(old.git(root, "rev-parse", "HEAD^{tree}").decode().strip() == TREE, "product tree")
    z.need(old.git(root, "diff", "--name-only", "HEAD") == b"", "dirty product source")
    result = {}
    for name in FILES:
        raw = old.git(root, "show", SOURCE+":"+name)
        raw.decode("utf-8")
        working = old.read(root/name)
        # One sample intentionally has CRLF in Git; accept its exact bytes first.
        z.need(working == raw or (b"\r" not in raw and working == raw.replace(b"\n",b"\r\n")),
               "source representation")
        result[name] = raw.replace(b"\n", b"\r\n") if name.endswith(".ps1") else raw
    return result

def build_receipt(root, binary, log):
    validator = types.ModuleType("n48s_fixed_validator")
    exec(compile(old.git(root, "show", SOURCE+":.ci/validate_native_log.py"),
                 "<fixed-native-validator>", "exec"), validator.__dict__)
    groups = validator.verified_groups(
        old.git(root, "show", SOURCE+":tests/test_main.cpp").decode(),
        log.decode("utf-8-sig"), 60)
    z.need("BUILD_OK" in log.decode("utf-8-sig"), "missing native build")
    return dict(schema="qbrain-n48s-build-v1", product_source=SOURCE, product_tree=TREE,
                binary_sha256=z.sha(binary), native_log_sha256=z.sha(log),
                native_groups=groups, dependencies=dependencies(binary),
                compiler_reproducibility_verified=False)

def expected(binary, files, guide, build):
    z.need(set(files) == set(FILES), "payload membership")
    deps = dependencies(binary)
    for name, body in files.items():
        z.windows_path(name)
        z.need(type(body) is bytes and 0 < len(body) <= z.MAX_FILE, "payload bounds")
        body.decode("utf-8")
    z.need(type(guide) is bytes and 0 < len(guide) <= 32768, "guide")
    guide.decode("utf-8")
    z.need(set(build) == {"schema","product_source","product_tree","binary_sha256",
                         "native_log_sha256","native_groups","dependencies",
                         "compiler_reproducibility_verified"}, "build fields")
    z.need(build["schema"] == "qbrain-n48s-build-v1" and build["product_source"] == SOURCE
           and build["product_tree"] == TREE and build["binary_sha256"] == z.sha(binary)
           and build["dependencies"] == deps
           and build["compiler_reproducibility_verified"] is False, "build identity")
    z.need(re.fullmatch("[0-9a-f]{64}", build["native_log_sha256"]) is not None, "native log digest")
    groups = build["native_groups"]
    z.need(type(groups) is list and len(groups) == 60 and len(set(groups)) == 60 and
           all(type(g) is str and re.fullmatch("[a-z0-9_]+",g) for g in groups), "native groups")
    contents = {**files, "qbrain.exe":binary, "START-HERE.zh-CN.md":guide,
                "BUILD-PROVENANCE.json":z.encoded(build)}
    contents["MANIFEST.json"] = z.encoded(dict(
        schema="qbrain-n48s-package-v1", product_source=SOURCE, product_tree=TREE,
        files=z.inventory(contents), binary_sha256=z.sha(binary), dependencies=deps, signed=False, stable=False,
        status="BUILT_NOT_YET_ACCEPTED", real_client_consumption_verified=False,
        full_project_complete=False))
    return contents

def verify(raw, wanted):
    z.need(z.archive_files(raw) == wanted, "archive payload")
    z.need(raw == z.make_zip(wanted), "archive container")
    return dict(schema="qbrain-n48s-package-check-v1", result="FILES_VERIFIED",
                product_source=SOURCE, product_tree=TREE, bytes=len(raw), sha256=z.sha(raw),
                members=len(wanted), binary_sha256=z.sha(wanted["qbrain.exe"]),
                native_bundle_tests="NOT_RUN")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ("source","binary","native-log","guide"):
        p.add_argument("--"+arg,type=Path,required=True)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--output",type=Path);group.add_argument("--verify",type=Path)
    a=p.parse_args()
    try:
        files=source_files(a.source)
        binary,log,guide=old.read(a.binary),old.read(a.native_log),old.read(a.guide,32768)
        wanted=expected(binary,files,guide,build_receipt(a.source,binary,log))
        z.need(source_files(a.source)==files and old.read(a.binary)==binary and
               old.read(a.native_log)==log and old.read(a.guide,32768)==guide, "changed input")
        raw=old.read(a.verify,z.MAX_ARCHIVE) if a.verify else z.make_zip(wanted)
        result=verify(raw,wanted)
        if not a.verify:
            old.regular(a.output.parent,True);a.output.mkdir(exist_ok=False)
            for name,body in ((PRODUCT,raw),("PACKAGE-CHECK.json",z.encoded(result)),
                              ("SHA256SUMS.txt",(result["sha256"]+"  "+PRODUCT+"\n").encode())):
                with (a.output/name).open("xb") as f:f.write(body)
        print(z.encoded(result).decode(),end="")
        return 0
    except (OSError,ValueError,KeyError,TypeError,struct.error,zipfile.BadZipFile,subprocess.SubprocessError):
        print('{"result":"REJECTED","error":"n48s_input_or_io"}')
        return 2

if __name__=="__main__":
    raise SystemExit(main())
