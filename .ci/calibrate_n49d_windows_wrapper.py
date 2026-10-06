"""One fixed NONQUALIFYING wrapper calibration; never a qualification consumer.

Only the coordinator and its two serial workers run. The unchanged qualifier
owns every child. No fixture observer, retry, Git process or version probe runs.
Complete D/tree/parent/delta provenance is verified externally before activation.
"""
from __future__ import annotations

import argparse
import ast
import ctypes
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid
import zipfile

MIB = 1024 * 1024
SOURCE_COMMIT = '5a387bda0a5114de37ce024093d8bedb4b696453'
SOURCE_TREE = 'f83c9cf6cde92f19ac7782fcc97f5c8e00156692'
HELPER = '.ci/calibrate_n49d_windows_wrapper.py'
WORKFLOW = '.github/workflows/n49d-windows-wrapper-calibration.yml'
PINS = {
    '.ci/test_n49d_source_contract.py': '42923fe3b7a45d90cdf91a2bb71a95eab594bc74eb7e5065a00272e489466cf7',
    '.ci/run_n49d_qualification.py': 'ce9b8408d98ceb38499e6211abbf913d0ff7dd552f55c8dc9191808cb4088b9b',
    '.ci/check_n49d_sources.py': 'd275566a5d10ac431f76ef6d5824d7c59f31ff1949f8de8b1b99fb67af827601',
    'scripts/build-tests-cl.ps1': '670d1948220528333584ccff2f7073e2227da9bdb640989bdd32bfcf39125607',
    'scripts/build-cl.ps1': '7efc7579d82cbba24ecf2fd5165007040371d3d58b7733ec7487ad0721bce3f0',
    '.github/workflows/n49d-mcp-directory-search.yml': '5a8dc5530721ca8aa150abd59aa9043edbeaf9535e62249aab60ffb3b0f0b742',
}
SCRIPT_SHA = '21f0c949c12198d5d50e6fa6a9129d4656c8068ecd89d0baf1e938396fe75e6a'
MODES = ('normal', 'optimized')
JOBS = ('windows-msvc', 'windows-cmake')
STREAM_CAP = 65536
RECORD_CAP = 65536
MANIFEST_CAP = 8192
INNER_SECONDS = 60
OUTER_SECONDS = 120
RUNNER_HEADROOM = 150 * MIB
SAMPLE_FILES = ('wrapper-controls.ps1', 'inner-stdout.bin', 'inner-stderr.bin',
                'outer-stdout.bin', 'outer-stderr.bin', 'sample.json')
WORKER_KEYS = frozenset(('schema', 'acceptance', 'mode', 'first_failure', 'owner', 'argv',
    'inner_owner_start_offset', 'worker_origin', 'runtime_before', 'runtime_after',
    'temp_empty', 'streams', 'terminal_token', 'capture'))


def need(ok, code):
    if not ok:
        raise ValueError(code)


def remaining(deadline):
    need(math.isfinite(deadline) and time.monotonic() < deadline, 'outer-deadline')


def descriptor(raw):
    return dict(size=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def regular(path, directory=False):
    value = path.lstat()
    need(not (getattr(value, 'st_file_attributes', 0) & 0x400), 'reparse-path')
    need(stat.S_ISDIR(value.st_mode) if directory else stat.S_ISREG(value.st_mode), 'nonregular-path')
    return value


def no_streams(path):
    """Reject named Windows alternate streams; no executable is launched."""
    if os.name != 'nt':
        return
    from ctypes import wintypes as w
    class Stream(ctypes.Structure):
        _fields_ = [('size', ctypes.c_longlong), ('name', w.WCHAR * 296)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    first = kernel.FindFirstStreamW
    first.argtypes = [w.LPCWSTR, w.DWORD, ctypes.POINTER(Stream), w.DWORD]
    first.restype = w.HANDLE
    nxt = kernel.FindNextStreamW
    nxt.argtypes = [w.HANDLE, ctypes.POINTER(Stream)]
    nxt.restype = w.BOOL
    close = kernel.FindClose
    close.argtypes = [w.HANDLE]
    close.restype = w.BOOL
    data = Stream()
    handle = first(str(path), 0, ctypes.byref(data), 0)
    if handle == ctypes.c_void_p(-1).value:
        need(ctypes.get_last_error() == 38, 'stream-inventory-unavailable')
        return
    try:
        need(data.name == '::$DATA', 'alternate-stream')
        need(not nxt(handle, ctypes.byref(data)) and ctypes.get_last_error() == 38, 'alternate-stream')
    finally:
        need(close(handle), 'stream-handle-close')


def bounded_read(path, cap, deadline=None):
    regular(path)
    if deadline is not None:
        remaining(deadline)
    with path.open('rb') as handle:
        raw = handle.read(cap + 1)
    need(len(raw) <= cap, 'file-cap')
    if deadline is not None:
        remaining(deadline)
    return raw


def inventory(root, cap, entries, depth, deadline):
    """Admission or proven-closure only. Never called on a live fixture."""
    remaining(deadline)
    regular(root, True)
    total = count = 0
    for folder, dirs, files in os.walk(root, followlinks=False):
        remaining(deadline)
        need(len(Path(folder).relative_to(root).parts) <= depth, 'inventory-depth')
        for name in dirs + files:
            remaining(deadline)
            path = Path(folder) / name
            info = regular(path, name in dirs)
            no_streams(path)
            count += 1
            total += info.st_size if name in files else 0
            need(count <= entries and total <= cap, 'inventory-cap')
    remaining(deadline)
    return dict(bytes=total, paths=count)


def safe_windows_path(value, maximum):
    text = str(value)
    path = PureWindowsPath(text)
    need(len(text) <= maximum and re.fullmatch(r'[A-Za-z]:\\[A-Za-z0-9_.\\-]+', text), 'unsafe-path')
    need(str(path) == text and all(p not in ('.', '..') and not p.startswith('.')
         and not p.endswith('.') for p in path.parts[1:]), 'unsafe-path-component')
    for parent in reversed(Path(text).parents):
        regular(parent, True)
    return text


def canonical(raw, expected):
    if descriptor(raw)['sha256'] == expected:
        return raw, 'git-exact'
    value = raw.replace(b'\r\n', b'\n')
    need(b'\0' not in raw and b'\r' not in value and raw == value.replace(b'\n', b'\r\n')
         and descriptor(value)['sha256'] == expected, 'source-pin')
    return value, 'whole-file-crlf'


def extract_script(raw):
    module = ast.parse(raw)
    functions = [n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'windows_wrapper_controls']
    need(len(functions) == 1, 'wrapper-function')
    assignments = [n for n in ast.walk(functions[0]) if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'body' for t in n.targets)]
    need(len(assignments) == 1 and isinstance(assignments[0].value, ast.Constant)
         and isinstance(assignments[0].value.value, str), 'wrapper-literal')
    script = assignments[0].value.value.encode('utf-8-sig')
    need(len(script) == 94020 and descriptor(script)['sha256'] == SCRIPT_SHA, 'script-pin')
    return script


def source_binding(root, commit, helper_sha, deadline):
    need(re.fullmatch('[0-9a-f]{40}', commit) and os.environ.get('GITHUB_SHA') == commit, 'platform-sha')
    head = bounded_read(root / '.git/HEAD', 42, deadline)
    need(head in (commit.encode() + b'\n', commit.encode() + b'\r\n'), 'detached-head')
    need(re.fullmatch('[0-9a-f]{64}', helper_sha), 'helper-pin-argument')
    sources = {}
    script = None
    for name, expected in dict(PINS, **{HELPER: helper_sha}).items():
        raw = bounded_read(root / name, MIB, deadline)
        git, representation = canonical(raw, expected)
        sources[name] = dict(canonical=descriptor(git), checkout=descriptor(raw), representation=representation)
        if name == '.ci/test_n49d_source_contract.py':
            script = extract_script(raw)
    raw = bounded_read(root / WORKFLOW, 32768, deadline)
    workflow = raw.replace(b'\r\n', b'\n')
    need(b'\r' not in workflow and raw in (workflow, workflow.replace(b'\n', b'\r\n')), 'workflow-representation')
    sources[WORKFLOW] = dict(canonical=descriptor(workflow), checkout=descriptor(raw), externally_pinned=True)
    return sources, script


def load_owner(root):
    # source_binding authenticates these bytes before either import. Do not
    # import the full selftest or call any qualifier/guard CLI entrypoint.
    for name in ('check_n49d_sources', 'run_n49d_qualification'):
        path = root / '.ci' / (name + '.py')
        canonical(bounded_read(path, MIB), PINS['.ci/' + name + '.py'])
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    q = sys.modules['run_n49d_qualification']
    q.source_guard.checkout_bytes((root / 'scripts/build-tests-cl.ps1').read_bytes(),
                                  q.source_guard.WRAPPERS['scripts/build-tests-cl.ps1'], True)
    return q


def file_identity(path, deadline):
    from ctypes import wintypes as w
    remaining(deadline)
    regular(path)
    no_streams(path)
    raw = bounded_read(path, 32 * MIB, deadline)
    version = ctypes.WinDLL('version', use_last_error=True)
    size_fn = version.GetFileVersionInfoSizeW
    size_fn.argtypes = [w.LPCWSTR, ctypes.POINTER(w.DWORD)]
    size_fn.restype = w.DWORD
    size = size_fn(str(path), None)
    need(0 < size <= MIB, 'file-version-size')
    buffer = ctypes.create_string_buffer(size)
    get = version.GetFileVersionInfoW
    get.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p]
    get.restype = w.BOOL
    need(get(str(path), 0, size, buffer), 'file-version-read')
    query = version.VerQueryValueW
    query.argtypes = [ctypes.c_void_p, w.LPCWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(w.UINT)]
    query.restype = w.BOOL
    pointer, length = ctypes.c_void_p(), w.UINT()
    need(query(buffer, '\\', ctypes.byref(pointer), ctypes.byref(length)) and length.value >= 52, 'file-version-query')
    words = ctypes.cast(pointer, ctypes.POINTER(w.DWORD))
    need(words[0] == 0xFEEF04BD, 'file-version-signature')
    def numbers(a, b):
        return [a >> 16, a & 65535, b >> 16, b & 65535]
    remaining(deadline)
    return dict(path=str(path), **descriptor(raw), file_version=numbers(words[2], words[3]),
                product_version=numbers(words[4], words[5]))


def runtime_identity(mode, deadline):
    need(os.name == 'nt' and sys.version_info[:2] == (3, 12)
         and ctypes.sizeof(ctypes.c_void_p) == 8, 'runtime-python')
    need(sys.flags.optimize == (0 if mode == 'normal' else 1), 'optimization-mode')
    import winreg
    system = Path(os.environ['SystemRoot']) / 'System32'
    powershell = system / 'WindowsPowerShell/v1.0/powershell.exe'
    command = system / 'cmd.exe'
    need(Path(shutil.which('powershell') or '').resolve() == powershell.resolve(), 'powershell-resolution')
    need(Path(os.environ.get('COMSPEC', '')).resolve() == command.resolve(), 'cmd-resolution')
    key_name = r'SOFTWARE\Microsoft\PowerShell\3\PowerShellEngine'
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_name, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
        engine, kind = winreg.QueryValueEx(key, 'PowerShellVersion')
        base, base_kind = winreg.QueryValueEx(key, 'ApplicationBase')
    need(kind == winreg.REG_SZ and base_kind == winreg.REG_SZ and len(engine) <= 64 and len(base) <= 240,
         'engine-registration-type')
    need(re.fullmatch(r'5\.1(?:\.[0-9]+){0,2}', engine)
         and Path(base).resolve() == powershell.parent.resolve(), 'engine-registration')
    from ctypes import wintypes as w
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    name = kernel.GetModuleFileNameW
    name.argtypes = [w.HMODULE, w.LPWSTR, w.DWORD]
    name.restype = w.DWORD
    buffer = ctypes.create_unicode_buffer(260)
    length = name(sys.dllhandle, buffer, 260)
    need(0 < length < 260, 'python-dll-path')
    python = Path(sys.executable)
    safe_windows_path(python, 200)
    paths = {'python': python, 'python_core': Path(buffer.value), 'powershell': powershell, 'cmd': command}
    for path in paths.values():
        safe_windows_path(path, 240)
    images = {k: os.environ.get(k) for k in ('ImageOS', 'ImageVersion', 'RUNNER_OS', 'RUNNER_ARCH')}
    need(all(isinstance(v, str) and 0 < len(v) <= 128 for v in images.values()), 'runner-image')
    need(len(sys.version) <= 256 and len(sys.getwindowsversion().service_pack) <= 128, 'runtime-text-cap')
    value = dict(files={k: file_identity(p, deadline) for k, p in paths.items()}, runner=images,
                python_version=sys.version, optimization=sys.flags.optimize, os_version=list(sys.getwindowsversion()),
                engine_registration=dict(evidence='installed-engine-registration', view=64, key=key_name,
                                         version=engine, application_base=base, direct_engine_query=False))
    need(len(json.dumps(value, separators=(',', ':'), allow_nan=False).encode()) <= 8192, 'runtime-record-cap')
    return value


def closed(result):
    return isinstance(result, dict) and all(result.get(k) is True for k in
        ('owned_tree_empty', 'cleanup_ok', 'stable', 'readers_done')) and result.get('cleanup_error') is None and 'capture_error' not in result


def strict(result):
    return closed(result) and result.get('classification') == 'passed' and type(result.get('exit')) is int and result['exit'] == 0


def capture_facts(owner):
    # Read only the existing in-memory event/errors after proved finalization.
    # The event also covers drain exceptions, not solely literal byte overflow.
    if not closed(owner.result):
        return None
    return dict(limited=owner.overflow.is_set(), reader_errors=list(owner.errors))


def streams(folder, prefix, result, closure, deadline=None, capture=None):
    values = {}
    for stream in ('stdout', 'stderr'):
        name = prefix + '-' + stream + '.bin'
        if not closure:
            values[name] = dict(available=False, complete=False, stable=False)
            continue
        path = folder / name
        if not path.exists():
            values[name] = dict(available=False, complete=False, stable=False)
            continue
        raw = bounded_read(path, STREAM_CAP, deadline)
        actual = descriptor(raw)
        interrupted = capture['limited'] if isinstance(capture, dict) else None
        complete = closed(result) and result.get(stream) == actual and interrupted is False
        # The event is shared by both readers. It cannot identify which stream
        # overflowed, and drain errors can also set it. Keep truncation unknown.
        truncated = False if interrupted is False else None
        values[name] = dict(available=True, **actual, complete=complete and not truncated,
                            stable=closed(result), snapshot_after_proven_closure=True,
                            capture_incomplete=interrupted, truncated=truncated)
    return values


def encode(value, cap):
    need(value.get('acceptance') is False, 'nonqualification-barrier')
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    need(len(raw) <= cap, 'record-cap')
    return raw


def worker_record(raw, mode):
    value = json.loads(raw)
    need(type(value) is dict and set(value) == WORKER_KEYS
         and value['schema'] == 'qbrain-wrapper-calibration-worker-v1'
         and value['acceptance'] is False and value['mode'] == mode, 'worker-schema')
    need(value['first_failure'] is None or type(value['first_failure']) is str, 'worker-failure-schema')
    need(type(value['streams']) is dict and type(value['terminal_token']) is bool, 'worker-facts-schema')
    need(type(value['worker_origin']) in (float, int) and math.isfinite(value['worker_origin']), 'worker-clock-schema')
    need(value['owner'] is None or type(value['owner']) is dict, 'worker-owner-schema')
    capture = value['capture']
    need(capture is None or (type(capture) is dict and set(capture) == {'limited', 'reader_errors'}
         and type(capture['limited']) is bool and type(capture['reader_errors']) is list
         and all(type(v) is str for v in capture['reader_errors'])), 'worker-capture-schema')
    return value


def publish(path, value, cap, deadline=None):
    """At most one fixed temporary. Success receipt is made only after return."""
    raw = encode(value, cap)
    temp = path.with_name(path.name + '.tmp')
    need(not path.exists(), 'record-exists')
    if deadline is not None:
        remaining(deadline)
    with temp.open('xb') as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    if deadline is not None:
        remaining(deadline)
    temp.rename(path)
    if deadline is not None:
        remaining(deadline)
    return descriptor(raw)


def worker(args, root, folder, private, deadline):
    origin = time.monotonic()
    record = dict(schema='qbrain-wrapper-calibration-worker-v1', acceptance=False, mode=args.mode,
                  first_failure=None, owner=None, argv=None, inner_owner_start_offset=None,
                  worker_origin=origin, runtime_before=None, runtime_after=None, temp_empty=None,
                  streams={}, terminal_token=False, capture=None)
    owner = None
    try:
        source_binding(root, args.diagnostic_commit, args.helper_sha256, deadline)
        q = load_owner(root)
        need(os.environ.get('TEMP') == str(private) and os.environ.get('TMP') == str(private), 'private-temp-environment')
        safe_windows_path(private, 80)
        need(inventory(private, 8*MIB, 128, 6, deadline)['paths'] == 0, 'private-temp-not-empty')
        record['runtime_before'] = runtime_identity(args.mode, deadline)
        script = folder / 'wrapper-controls.ps1'
        need(descriptor(bounded_read(script, 94020, deadline)) == dict(size=94020, sha256=SCRIPT_SHA), 'written-script-pin')
        wrapper = root / 'scripts/build-tests-cl.ps1'
        for path in (script, wrapper, folder):
            safe_windows_path(path, 240)
        record['argv'] = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script),
                          '-Wrapper', str(wrapper), '-Python', sys.executable]
        remaining(deadline)
        owner = q.OwnedChild(record['argv'], folder, dict(os.environ), subprocess.DEVNULL,
                             folder/'inner-stdout.bin', folder/'inner-stderr.bin', INNER_SECONDS, STREAM_CAP)
        record['inner_owner_start_offset'] = owner.started - origin
        owner.wait()
        record['owner'] = owner.result
        need(strict(record['owner']), 'inner-owner-incomplete')
        # This is the original acceptance rule, including strip/endswith.
        record['terminal_token'] = (folder/'inner-stdout.bin').read_text().strip().endswith('WRAPPER_CONTROLS_OK')
        need(record['terminal_token'], 'terminal-token')
    except Exception as error:
        if hasattr(error, 'owner'):
            owner = error.owner
        record['first_failure'] = ('inner-' + owner.result['classification']) if owner and owner.result and owner.result['classification'] != 'passed' else str(error)
    if owner is not None:
        record['owner'] = owner.result
        record['capture'] = capture_facts(owner)
        record['inner_owner_start_offset'] = owner.started - origin
    try:
        if closed(record['owner']):
            record['streams'] = streams(folder, 'inner', record['owner'], True, deadline, record['capture'])
            record['temp_empty'] = inventory(private, 8*MIB, 128, 6, deadline)['paths'] == 0
            need(record['temp_empty'], 'fixture-cleanup-residue')
            record['runtime_after'] = runtime_identity(args.mode, deadline)
            need(record['runtime_after'] == record['runtime_before'], 'runtime-identity-changed')
        else:
            record['streams'] = streams(folder, 'inner', record['owner'], False)
        remaining(deadline)
    except Exception as error:
        record['first_failure'] = record['first_failure'] or str(error)
    # Outer stdout is the bounded worker handoff; no extra file is produced.
    sys.stdout.buffer.write(encode(record, 32768))
    sys.stdout.buffer.flush()
    remaining(deadline)
    return 0 if record['first_failure'] is None and strict(record['owner']) else 1


def sample(args, root, output, mode):
    origin = time.monotonic()
    deadline = origin + OUTER_SECONDS
    folder = output / mode
    folder.mkdir()
    record = dict(schema='qbrain-wrapper-calibration-sample-v1', acceptance=False, job=args.job, mode=mode,
                  diagnostic_commit=args.diagnostic_commit, fixture_commit=SOURCE_COMMIT, fixture_tree=SOURCE_TREE,
                  provenance='external-preactivation-D-tree-parent-delta-review-required', sources=None,
                  sample_origin=origin, deadline=deadline, outer_owner_start_offset=None, outer_owner=None, outer_capture=None,
                  inner_seconds=INNER_SECONDS, outer_seconds=OUTER_SECONDS, first_failure=None,
                  worker=None, streams={}, private_temp=None, post_outer_temp_empty=None, runtime_admission=None,
                  inner_facts='unavailable', script=None, outer_argv=None,
                  publication='receipt-in-job-manifest; this record cannot attest its own publication',
                  limitations=['No full-tree runtime verification', 'No direct PowerShell engine query',
                               'No pre-checkout transport bound',
                               'Work-marker clock has a separate later origin and 20000ms saturation'])
    owner = None
    private = None
    try:
        record['checkout'] = inventory(root, 16*MIB, 4096, 16, deadline)
        need(shutil.disk_usage(output).free >= 32*MIB + RUNNER_HEADROOM, 'physical-space')
        need(inventory(output, MIB, 32, 3, deadline)['bytes'] <= MIB, 'output-capacity')
        sources, script = source_binding(root, args.diagnostic_commit, args.helper_sha256, deadline)
        record['sources'] = sources
        q = load_owner(root)
        record['runtime_admission'] = runtime_identity('normal', deadline)
        runner_temp = Path(os.environ['RUNNER_TEMP'])
        safe_windows_path(runner_temp, 80)
        regular(runner_temp, True)
        private = runner_temp / ('n49d-' + uuid.uuid4().hex)
        safe_windows_path(private, 80)
        private.mkdir()
        no_streams(private)
        need(inventory(private, 8*MIB, 128, 6, deadline)['paths'] == 0, 'private-temp-not-empty')
        record['private_temp'] = str(private)
        with (folder/'wrapper-controls.ps1').open('xb') as handle:
            handle.write(script)
        record['script'] = descriptor(bounded_read(folder/'wrapper-controls.ps1', 94020, deadline))
        for path in (folder/'wrapper-controls.ps1', root/'scripts/build-tests-cl.ps1', folder):
            safe_windows_path(path, 240)
        env = {k:v for k,v in os.environ.items() if not q.BLOCKED.search(k)}
        env.update(TEMP=str(private), TMP=str(private), PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
        argv = [sys.executable] + (['-O'] if mode == 'optimized' else []) + [str(root/HELPER), '--worker',
            '--job', args.job, '--mode', mode, '--diagnostic-commit', args.diagnostic_commit,
            '--helper-sha256', args.helper_sha256, '--deadline', repr(deadline), '--folder', str(folder),
            '--private-temp', str(private)]
        record['outer_argv'] = argv
        remaining(deadline)
        owner = q.OwnedChild(argv, folder, env, subprocess.DEVNULL,
                             folder/'outer-stdout.bin', folder/'outer-stderr.bin', OUTER_SECONDS, STREAM_CAP,
                             deadline=deadline)
        record['outer_owner_start_offset'] = owner.started-origin
        owner.wait()
        record['outer_owner'] = owner.result
    except Exception as error:
        if hasattr(error, 'owner'):
            owner = error.owner
        record['first_failure'] = ('outer-' + owner.result['classification']) if owner and owner.result else str(error)
    if owner is not None:
        record['outer_owner'] = owner.result
        record['outer_capture'] = capture_facts(owner)
        record['outer_owner_start_offset'] = owner.started-origin
    try:
        if closed(record['outer_owner']):
            # A failed outer deadline cannot be converted to success. After
            # proven closure, retain capped raw bytes even if it has expired.
            capture_deadline = deadline if record['first_failure'] is None else None
            record['streams'].update(streams(folder, 'outer', record['outer_owner'], True, capture_deadline, record['outer_capture']))
            raw = bounded_read(folder/'outer-stdout.bin', STREAM_CAP, capture_deadline)
            try:
                inner = worker_record(raw, mode)
                record['worker'] = inner
                record['inner_facts'] = 'cached-owner' if isinstance(inner.get('owner'), dict) else 'unavailable'
                record['first_failure'] = inner.get('first_failure') or record['first_failure']
            except (ValueError, UnicodeError):
                record['first_failure'] = record['first_failure'] or 'worker-record-incomplete'
            inner = record['worker'] or {}
            record['streams'].update(streams(folder, 'inner', inner.get('owner'), True, capture_deadline, inner.get('capture')))
            record['post_outer_temp_empty'] = inventory(private, 8*MIB, 128, 6, deadline)['paths'] == 0
            need(record['post_outer_temp_empty'], 'fixture-cleanup-residue')
            need(strict(record['outer_owner']) and strict(inner.get('owner')) and inner.get('terminal_token') is True
                 and inner.get('temp_empty') is True and inner.get('runtime_before') is not None
                 and inner.get('runtime_before') == inner.get('runtime_after'), 'strict-sample-incomplete')
            need(all(v['available'] and v['complete'] for v in record['streams'].values()), 'streams-incomplete')
        else:
            record['streams'].update(streams(folder, 'outer', None, False))
            record['streams'].update(streams(folder, 'inner', None, False))
            record['first_failure'] = record['first_failure'] or 'outer-closure-unavailable'
    except Exception as error:
        record['first_failure'] = record['first_failure'] or str(error)
    receipt = dict(mode=mode, acceptance=False, deadline=deadline, completed=False, first_failure=record['first_failure'],
                   record=None, published_elapsed=None)
    try:
        receipt['record'] = publish(folder/'sample.json', record, RECORD_CAP,
                                    deadline if record['first_failure'] is None else None)
        receipt['published_elapsed'] = time.monotonic()-origin
        remaining(deadline)
        receipt['completed'] = record['first_failure'] is None
    except Exception as error:
        receipt['first_failure'] = receipt['first_failure'] or str(error)
    # No recursive cleanup, especially when closure is missing. The runner owns
    # eventual disposal. Empty private parents consume no fixture payload bytes.
    return receipt, record


def package(output, manifest, records):
    allowed = [('job.json', MANIFEST_CAP)]
    for mode, record in records.items():
        for name in SAMPLE_FILES:
            path = output/mode/name
            if name.endswith('.bin'):
                if not record['streams'].get(name, {}).get('available'):
                    continue
                cap = STREAM_CAP
            else:
                cap = 94020 if name.endswith('.ps1') else RECORD_CAP
            if path.exists():
                allowed.append((mode+'/'+name, cap))
    payloads = [(name, bounded_read(output/name, cap)) for name, cap in allowed]
    need(sum(len(raw) for _,raw in payloads) <= MIB, 'job-raw-cap')
    path = output/'payload.zip'
    temporary = output/'payload.zip.tmp'
    with zipfile.ZipFile(temporary, 'x', compression=zipfile.ZIP_STORED) as archive:
        for name, raw in payloads:
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)
    need(regular(temporary).st_size <= 3*MIB//2, 'payload-zip-cap')
    inventory(output, 8*MIB, 40, 3, time.monotonic()+5)
    need(shutil.disk_usage(output).free >= 32*MIB+RUNNER_HEADROOM, 'upload-space')
    temporary.rename(path)
    return path


def run_job(args, root, output):
    output.mkdir(parents=True, exist_ok=False)
    manifest = dict(schema='qbrain-wrapper-calibration-job-v1', acceptance=False, job=args.job,
                    diagnostic_commit=args.diagnostic_commit, fixture_commit=SOURCE_COMMIT, fixture_tree=SOURCE_TREE,
                    first_failure=None, samples=[], not_run=[], all_samples_completed=False)
    records = {}
    for index, mode in enumerate(MODES):
        receipt, record = sample(args, root, output, mode)
        if receipt['completed']:
            try:
                remaining(receipt['deadline'])
            except ValueError:
                receipt.update(completed=False, first_failure='outer-deadline')
        records[mode] = record
        manifest['samples'].append(receipt)
        if not receipt['completed']:
            manifest['first_failure'] = receipt['first_failure'] or 'incomplete-publication'
            manifest['not_run'] = list(MODES[index+1:])
            break
    manifest['all_samples_completed'] = len(manifest['samples']) == 2 and all(v['completed'] for v in manifest['samples'])
    publish(output/'job.json', manifest, MANIFEST_CAP)
    package(output, manifest, records)
    return 0 if manifest['all_samples_completed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', choices=JOBS, required=True)
    parser.add_argument('--diagnostic-commit', required=True)
    parser.add_argument('--helper-sha256', required=True)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--mode', choices=MODES)
    parser.add_argument('--deadline', type=float)
    parser.add_argument('--folder')
    parser.add_argument('--private-temp')
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    root = Path(__file__).resolve().parents[1]
    need(os.name == 'nt', 'Windows diagnostic only')
    need(os.environ.get('GITHUB_EVENT_NAME') == 'push' and os.environ.get('GITHUB_REF') ==
         'refs/heads/diagnostics/n49d-wrapper-budget-5a387bda', 'diagnostic-trigger')
    need(os.environ.get('GITHUB_RUN_ATTEMPT') == '1', 'diagnostic-retry-forbidden')
    if args.worker:
        need(all((args.mode, args.deadline, args.folder, args.private_temp)), 'worker-arguments')
        return worker(args, root, Path(args.folder), Path(args.private_temp), args.deadline)
    need(not any((args.mode, args.deadline, args.folder, args.private_temp)), 'coordinator-arguments')
    return run_job(args, root, Path(os.environ['RUNNER_TEMP'])/'n49d-wrapper-calibration'/args.job)


if __name__ == '__main__':
    raise SystemExit(main())
