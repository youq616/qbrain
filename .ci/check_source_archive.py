"""Bind a Git source archive to an externally selected commit and complete tree.

No extraction, shell execution, Git invocation, network or database access. The
caller supplies NUL-delimited `git ls-tree --full-tree -r -z HEAD` bytes and the
expected tree from a trusted checkout. A ZIP comment is not source-tree proof.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import zipfile

MANIFEST_CAP = 2 * 1024 * 1024
ARCHIVE_CAP = 128 * 1024 * 1024
UNPACKED_CAP = 128 * 1024 * 1024
MEMBER_CAP = 32 * 1024 * 1024
FILE_CAP = 5000
PATH_CAP = 4096


class Rejected(ValueError):
    """Stable codes; never publish pathnames, file content or raw parser errors."""


def need(ok, code):
    if not ok:
        raise Rejected(code)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def object_id(kind, raw):
    return hashlib.sha1(kind + b' ' + str(len(raw)).encode('ascii') + b'\0' + raw).digest()


def safe_name(name):
    need(isinstance(name, str) and 0 < len(name.encode('utf-8')) <= PATH_CAP, 'source_path')
    need(not any(ord(c) < 32 or ord(c) == 127 for c in name) and
         '\\' not in name and ':' not in name, 'source_path')
    parts = name.split('/')
    need(len(parts) <= 64 and all(p not in ('', '.', '..') for p in parts), 'source_path')
    return parts


def tree_from_manifest(raw, expected_tree):
    need(isinstance(expected_tree, str) and re.fullmatch('[0-9a-f]{40}', expected_tree), 'source_tree_pin')
    need(0 < len(raw) <= MANIFEST_CAP and raw.endswith(b'\0'), 'source_manifest_size')
    records = raw[:-1].split(b'\0')
    need(len(records) <= FILE_CAP, 'source_file_limit')
    files, tree = {}, {}
    for record in records:
        match = re.fullmatch(rb'(100644|100755) blob ([0-9a-f]{40})\t([^\0]+)', record)
        need(match is not None, 'source_manifest_record')
        mode, oid, path = match.groups()
        try:
            name = path.decode('utf-8')
        except UnicodeError as exc:
            raise Rejected('source_path_encoding') from exc
        parts = safe_name(name)
        need(name not in files, 'source_duplicate_path')
        node = tree
        for part in parts[:-1]:
            need(part not in node or isinstance(node[part], dict), 'source_path_conflict')
            node = node.setdefault(part, {})
        need(parts[-1] not in node, 'source_path_conflict')
        node[parts[-1]] = (mode, bytes.fromhex(oid.decode()))
        files[name] = (mode.decode(), oid.decode())

    def build(node):
        # Git compares directories as name + '/', not simply as name.
        entries = []
        for name, value in sorted(node.items(), key=lambda item:
                (item[0] + ('/' if isinstance(item[1], dict) else '')).encode('utf-8')):
            if isinstance(value, dict):
                mode, oid = b'40000', build(value)
            else:
                mode, oid = value
            entries.append(mode + b' ' + name.encode('utf-8') + b'\0' + oid)
        return object_id(b'tree', b''.join(entries))

    need(build(tree).hex() == expected_tree, 'source_tree_mismatch')
    return files


def crlf_text(raw):
    # Text recognition is deliberately separate from cryptographic identity. It
    # tolerates legacy log encodings, but never normalizes NUL or bare-CR data.
    # A complete expected blob match remains mandatory after normalization.
    value = raw.replace(b'\r\n', b'\n')
    if b'\0' in value or b'\r' in value:
        return False
    printable = sum(byte >= 32 and byte != 127 or byte in (8,9,10,11,12,27)
                    for byte in value)
    return len(value)-printable <= printable//128


def verify_bytes(archive_raw, manifest_raw, expected_commit, expected_tree, platform,
                 expected_archive_sha256=None):
    need(platform in ('linux', 'windows'), 'source_platform')
    need(isinstance(expected_commit, str) and re.fullmatch('[0-9a-f]{40}', expected_commit),
         'source_commit_pin')
    need(0 < len(archive_raw) <= ARCHIVE_CAP, 'source_archive_size')
    if expected_archive_sha256 is not None:
        need(isinstance(expected_archive_sha256, str) and
             re.fullmatch('[0-9a-f]{64}', expected_archive_sha256), 'source_archive_pin')
        need(sha256(archive_raw) == expected_archive_sha256, 'source_archive_hash')
    files = tree_from_manifest(manifest_raw, expected_tree)
    allowed_dirs = {'/'.join(name.split('/')[:i])
                    for name in files for i in range(1, len(name.split('/')))}
    exact = normalized = 0
    with zipfile.ZipFile(io.BytesIO(archive_raw)) as archive:
        need(archive.comment == expected_commit.encode('ascii'), 'source_archive_commit')
        members = archive.infolist()
        need(len(members) <= FILE_CAP + len(allowed_dirs), 'source_archive_inventory')
        need(sum(x.file_size for x in members) <= UNPACKED_CAP, 'source_unpacked_limit')
        seen, entries, directory_members = set(), {}, set()
        for member in members:
            name = member.filename
            need(name == member.orig_filename, 'source_member_name')  # ZIP embedded-NUL truncation.
            is_dir = member.is_dir()
            safe_name(name[:-1] if is_dir else name)
            need(name not in seen, 'source_duplicate_member')
            seen.add(name)
            need(not member.flag_bits & 1, 'source_encrypted_member')
            file_type = stat.S_IFMT(member.external_attr >> 16)
            need(file_type in (0, stat.S_IFDIR if is_dir else stat.S_IFREG), 'source_member_type')
            need(member.file_size <= MEMBER_CAP, 'source_member_limit')
            if is_dir:
                need(name[:-1] in allowed_dirs and member.file_size == 0, 'source_directory_inventory')
                directory_members.add(name[:-1])
                continue
            need(name in files, 'source_unexpected_file')
            entries[name] = member
        need(set(entries) == set(files), 'source_missing_file')
        if platform == 'windows':
            paths = set(files) | allowed_dirs
            need(len({p.casefold() for p in paths}) == len(paths), 'source_windows_case_collision')
        for name, (mode, wanted) in files.items():
            member = entries[name]
            # Where a ZIP actually carries executable bits, they may not contradict
            # the trusted manifest. DOS-created archives can omit modes entirely.
            attributes = member.external_attr >> 16
            if attributes:
                need(bool(attributes & 0o111) == (mode == '100755'), 'source_mode_mismatch')
            raw = archive.read(member)
            need(len(raw) == member.file_size, 'source_member_size')
            if object_id(b'blob', raw).hex() == wanted:
                exact += 1
            else:
                need(platform == 'windows' and b'\r\n' in raw and crlf_text(raw) and
                     object_id(b'blob', raw.replace(b'\r\n', b'\n')).hex() == wanted,
                     'source_blob_mismatch')
                normalized += 1
    return dict(schema='qbrain-source-tree-verification-v1', result='PASS',
                commit=expected_commit, tree=expected_tree, platform=platform,
                source_files=len(files), byte_exact_files=exact,
                exact_crlf_to_lf_files=normalized,
                archive_sha256=sha256(archive_raw), tree_manifest_sha256=sha256(manifest_raw),
                archive_external_hash_checked=expected_archive_sha256 is not None,
                source_origin_authenticated=False, binary_build_attested=False,
                new_native_execution=False)


def checked_path(path, directory=False):
    path = Path(os.path.abspath(path))
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        need(not stat.S_ISLNK(info.st_mode) and
             not (getattr(info, 'st_file_attributes', 0) & 0x400), 'source_input_link')
    info = path.stat()
    need(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode), 'source_input_type')
    return path


def read_file(path, cap):
    path = checked_path(path)
    before = path.stat()
    need(before.st_size <= cap, 'source_input_limit')
    with path.open('rb') as f:
        raw = f.read(cap + 1)
        after = os.fstat(f.fileno())
    need(len(raw) <= cap and len(raw) == before.st_size and
         (before.st_size, before.st_mtime_ns, before.st_ino) ==
         (after.st_size, after.st_mtime_ns, after.st_ino), 'source_input_changed')
    return raw


def verify_files(archive, manifest, commit, tree, platform, archive_sha256=None):
    raw = read_file(archive, ARCHIVE_CAP)
    index = read_file(manifest, MANIFEST_CAP)
    result = verify_bytes(raw, index, commit, tree, platform, archive_sha256)
    need(read_file(archive, ARCHIVE_CAP) == raw and read_file(manifest, MANIFEST_CAP) == index,
         'source_input_changed')
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('check', 'verify-report'))
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--tree-manifest', type=Path, required=True)
    p.add_argument('--expected-commit', required=True)
    p.add_argument('--expected-tree', required=True)
    p.add_argument('--platform', choices=('linux', 'windows'), required=True)
    p.add_argument('--expected-archive-sha256')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(argv)
    try:
        output = Path(os.path.abspath(a.output))
        checked_path(output.parent, True)
        if a.action == 'check':
            need(not output.exists() and not output.is_symlink(), 'source_output_exists')
        result = verify_files(a.archive, a.tree_manifest, a.expected_commit, a.expected_tree,
                              a.platform, a.expected_archive_sha256)
        raw = encode(result)
        if a.action == 'check':
            with output.open('xb') as f:
                f.write(raw)
        else:
            need(read_file(output, 65536) == raw, 'source_report_changed')
        print(encode(dict(result='PASS' if a.action=='check' else 'VERIFIED',
                          tree=a.expected_tree, source_files=result['source_files'],
                          new_native_execution=False)).decode(), end='')
        return 0
    except Rejected as exc:
        print(encode({'error': {'code': str(exc)}}).decode(), end='')
    except (OSError, ValueError, KeyError, TypeError, OverflowError, zipfile.BadZipFile,
            RuntimeError, NotImplementedError, RecursionError):
        print('{"error":{"code":"source_invalid_input_or_io"}}')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
