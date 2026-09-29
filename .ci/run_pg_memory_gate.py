"""N48O integrated evidence gate with pre-execution, externally pinned identities.

Compose the independent readers without relaxing their old frozen CLI profiles.
The pin command runs BEFORE tests. Verify requires its separately retained hash;
report-supplied executable identities cannot set the expected values. No SQL runs.
Hashes bind this test evidence, not server provenance or real client consumption.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
import re
import sqlite3
from pathlib import Path
import zipfile

import check_pg_memory_evidence as memory
import check_pg_scope_evidence as scope
import check_session_lifecycle_evidence as session
import check_source_archive as source_archive

FILES = ('.ci/test_pg_memory.py', 'tests/test_pg_memory.cpp',
         'tests/test_pg_memory_scope.cpp', '.ci/check_pg_memory_evidence.py',
         '.ci/check_pg_scope_evidence.py', '.ci/review_session_lifecycle.py',
         '.ci/run_pg_memory_gate.py', '.ci/check_session_lifecycle_evidence.py',
         '.ci/check_source_archive.py')
ROOT = Path(__file__).resolve().parents[1]
CAP = 128 * 1024 * 1024


def need(ok, label):
    if not ok:
        raise ValueError(label)


def read(path, cap=CAP):
    info = path.lstat()
    need(path.is_file() and not path.is_symlink() and
         not (getattr(info, 'st_file_attributes', 0) & 0x400), 'regular input required')
    need(info.st_size <= cap, 'input byte limit')
    with path.open('rb') as stream:
        raw = stream.read(cap + 1)
    need(len(raw) == info.st_size and len(raw) <= cap, 'input changed/limit')
    return raw


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return memory.encode(value) + b'\n'


def pin(artifact, binary, commit, platform, tree):
    need(re.fullmatch('[0-9a-f]{40}', commit) is not None, 'commit identity')
    source = read(artifact / 'source.zip')
    tree_manifest = source_archive.read_file(artifact / 'source-tree.bin', source_archive.MANIFEST_CAP)
    full_source = source_archive.verify_bytes(source, tree_manifest, commit, tree, platform)
    with zipfile.ZipFile(artifact / 'source.zip') as archive:
        need(archive.comment == commit.encode(), 'archive commit')
        need(len(archive.namelist()) == len(set(archive.namelist())), 'duplicate archive member')
        components = {}
        for name in FILES:
            raw = read(ROOT / name)
            need(raw == archive.read(name), 'worktree/archive disagreement: ' + name)
            components[name] = sha(raw)
    suffix = '.exe' if platform == 'windows' else ''
    programs = {'qbrain': binary,
                'pg-memory-tests': binary.with_name('qbrain_pg_memory_tests' + suffix),
                'pg-scope-tests': binary.with_name('qbrain_pg_memory_scope_tests' + suffix)}
    identity = dict(schema='qbrain-n48o-pretest-pins-v2', commit=commit, platform=platform,
                    source_tree=tree, source_manifest_sha256=sha(tree_manifest),
                    source_files=full_source['source_files'],
                    source_sha256=sha(source), components=components,
                    programs={k: sha(read(v)) for k, v in programs.items()})
    raw = encode(identity)
    with (artifact / 'review-pins.json').open('xb') as stream:
        stream.write(raw)
    return sha(raw)


def identity(artifact, pin_sha256):
    need(re.fullmatch('[0-9a-f]{64}', pin_sha256) is not None, 'external pin format')
    raw = read(artifact / 'review-pins.json', 65536)
    need(sha(raw) == pin_sha256, 'external pretest pin mismatch')
    p = memory.decode(raw)
    need(set(p) == {'schema', 'commit', 'platform', 'source_sha256', 'components', 'programs',
                    'source_tree', 'source_manifest_sha256', 'source_files'}, 'pin fields')
    need(p['schema'] == 'qbrain-n48o-pretest-pins-v2' and p['platform'] in ('linux', 'windows'), 'pin schema/platform')
    need(re.fullmatch('[0-9a-f]{40}', p['commit']) is not None, 'pin commit')
    need(set(p['components']) == set(FILES) and set(p['programs']) == {'qbrain', 'pg-memory-tests', 'pg-scope-tests'}, 'pin inventory')
    source = read(artifact / 'source.zip')
    need(sha(source) == p['source_sha256'], 'source archive hash')
    tree_manifest = source_archive.read_file(artifact / 'source-tree.bin', source_archive.MANIFEST_CAP)
    need(sha(tree_manifest) == p['source_manifest_sha256'], 'source tree manifest hash')
    full_source = source_archive.verify_bytes(source, tree_manifest, p['commit'], p['source_tree'], p['platform'])
    need(type(p['source_files']) is int and p['source_files'] == full_source['source_files'], 'source file coverage')
    with zipfile.ZipFile(artifact / 'source.zip') as archive:
        need(archive.comment.decode() == p['commit'], 'source commit')
        need(len(archive.namelist()) == len(set(archive.namelist())), 'duplicate archive member')
        for name, digest in p['components'].items():
            need(sha(read(ROOT / name)) == digest == sha(archive.read(name)), 'review/producer source identity')
    suffix = '.exe' if p['platform'] == 'windows' else ''
    for name, digest in p['programs'].items():
        need(sha(read(artifact / (name + suffix))) == digest, 'native program identity')
    return p


def lifecycle(directory, pins, mode):
    r = memory.decode(read(directory / 'RESULT.json', 4*1024*1024))
    need(set(r) == {'synthetic_snapshot_sha256','passed','schema','backend','optimized','binary_sha256','reviewer_sha256','commands','checks','command_count','check_count','native_retries','model_requests_sent','real_client_consumption_verified','postgres_execution'}, 'lifecycle report fields')
    need(r['schema'] == 'qbrain-independent-session-review-v1' and r['passed'] is True and 'error' not in r, 'lifecycle completed')
    need(r['backend'] == 'sqlite' and r['optimized'] is (mode == 'optimized'), 'lifecycle mode')
    need(r['binary_sha256'] == pins['programs']['qbrain'] and
         r['reviewer_sha256'] == pins['components']['.ci/review_session_lifecycle.py'], 'lifecycle identities')
    for key, expected in [('command_count', 42), ('check_count', 110), ('native_retries', 0), ('model_requests_sent', 0)]:
        need(type(r[key]) is int and r[key] == expected, 'lifecycle integer: ' + key)
    need(r['postgres_execution'] is False and r['real_client_consumption_verified'] is False, 'lifecycle scope')
    need(len(r['commands']) == 42 and len(r['checks']) == 110 and all(c['passed'] is True for c in r['checks']), 'lifecycle coverage')
    need({p.name for p in (directory/'raw').iterdir()} == {f'{i:03d}.{ext}' for i in range(42) for ext in ('stdin','stdout','stderr')}, 'lifecycle raw inventory')
    streams = []
    for i, row in enumerate(r['commands']):
        current = {}
        need(type(row['exit']) is int and row['exit'] == (1 if i in (9, 18, 20, 23, 30, 32, 33) else 0), 'lifecycle exact exit')
        for ext in ('stdin', 'stdout', 'stderr'):
            data = read(directory/'raw'/f'{i:03d}.{ext}', memory.CAP)
            current[ext] = data
            need(sha(data) == row['hashes'][ext], 'lifecycle raw digest')
            if ext == 'stderr':
                need(not data, 'lifecycle stderr')
        streams.append(current)
    session.validate(r['commands'], streams)
    dbfile = directory/'synthetic-final.db'
    need(sha(read(dbfile)) == r['synthetic_snapshot_sha256'], 'lifecycle snapshot identity')
    # Read a closed synthetic snapshot, never a live user DB; do not import its SQL.
    with closing(sqlite3.connect(dbfile.resolve().as_uri()+'?mode=ro&immutable=1', uri=True)) as db:
        need(db.execute('PRAGMA integrity_check').fetchall() == [('ok',)], 'lifecycle integrity')
        need(db.execute("SELECT count(*) FROM memory_events WHERE status='forgotten'").fetchone() == (3,), 'all tombstones retained')
        need(db.execute("SELECT count(*) FROM memory_events WHERE source_id='beta'").fetchone() == (1,), 'concurrent creator count')
        need(db.execute("SELECT count(*) FROM memory_items m JOIN memory_events e ON m.event_id=e.event_id WHERE e.status='forgotten'").fetchone() == (0,), 'forgotten items absent')
    return dict(commands=42, checks=110, retries=0, postgres_execution=False)


def verify(artifact, pin_sha256, output):
    need(not output.exists(), 'refuse output overwrite')
    p = identity(artifact, pin_sha256)
    # Parameterize pure semantic functions with PRETEST identities, not report claims.
    # The historical readers' CLI profiles and source files remain unchanged.
    previous = memory.PIN
    memory.PIN = {p['platform']: (p['programs']['qbrain'], p['components']['.ci/test_pg_memory.py'])}
    try:
        native = memory.decode(read(artifact/'native-result.json', memory.CAP))
        need(native['schema'] == 'qbrain-n48o-native-v1' and native['passed'] is True and native['real_server'] is True, 'native PG result')
        need(type(native['count']) is int and native['count'] == len(native['checks']) == 122 and
             all(c['passed'] is True for c in native['checks']), 'native PG checks')
        scope_raw = read(artifact/'scope-result.json', scope.CAP)
        scope_result = scope.verify(scope_raw)
        parent = artifact/'parent-scope-result.json'
        parent_raw = read(parent, scope.CAP) if parent.exists() else None
        rejected_scope = scope.negatives(scope_raw, parent_raw)
        dump = read(artifact/'synthetic-process.sql', memory.CAP)
        final_db = memory.verify_dump(dump)
        modes = {}
        for mode in ('normal', 'optimized'):
            r, streams = memory.load(artifact/('process-'+mode))
            modes[mode] = memory.verify_memory(r, streams, p['platform'], mode)
            modes[mode]['rejected_mutations'] = memory.negatives(r, streams, p['platform'], mode, dump)
            modes[mode]['sqlite_lifecycle'] = lifecycle(artifact/'integrated'/('lifecycle-'+mode), p, mode)
        identity(artifact, pin_sha256)
        result = dict(schema='qbrain-n48o-integrated-gate-v2', passed=True, commit=p['commit'], platform=p['platform'],
                      pretest_pin_sha256=pin_sha256, source_tree=p['source_tree'],
                      source_files=p['source_files'], source_archive_sha256=p['source_sha256'], native_checks=122, scope_checks=len(scope_result['checks']),
                      rejected_scope_mutations=rejected_scope, modes=modes, final_database=final_db,
                      provenance_authenticated=False, real_client_consumption_verified=False, new_postgresql_execution=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('xb') as stream:
            stream.write(encode(result))
        return result
    finally:
        memory.PIN = previous


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('pin','verify'))
    parser.add_argument('--artifact', type=Path, required=True)
    parser.add_argument('--binary', type=Path)
    parser.add_argument('--commit')
    parser.add_argument('--tree')
    parser.add_argument('--platform', choices=('linux','windows'))
    parser.add_argument('--pin-sha256')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'pin':
            need(all((args.binary, args.commit, args.platform, args.tree)), 'pin arguments')
            print(pin(args.artifact, args.binary.resolve(strict=True), args.commit, args.platform, args.tree))
        else:
            need(args.pin_sha256 is not None and args.output is not None, 'verify arguments')
            print(json.dumps(verify(args.artifact, args.pin_sha256, args.output), ensure_ascii=False))
    except (ValueError, TypeError, KeyError, IndexError, OSError, zipfile.BadZipFile, RecursionError, sqlite3.Error) as error:
        print(json.dumps({'passed': False, 'error': type(error).__name__, 'detail': str(error)}))
        raise SystemExit(1)
