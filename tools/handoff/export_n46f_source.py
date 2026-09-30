"""Export only the two owner-reported N46F commits, without GitHub credentials.

This is an offline source handoff, not a build, upload, or product acceptance.
Requires Python 3.10+ and Git. The original worktree and branch are not changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

BASE = '48a498bbf2ea14b39f1023cd1d67e30fb98848f9'
COMMITS = (
    'a0adf373c686d1bbc1845d58d84fb6d1b0da372c',
    '9426692fe40ba41880f9312534f02fde0459cfad',
)
BRANCH = 'refs/heads/optimization/n46f-cjk-recall'
ALLOWED_PATHS = frozenset({
    'docs/nodes/N46F-PLAN.md', 'docs/nodes/N46F-PLAN-REVIEW.md',
    'include/qbrain/search/detail/cjk_literal.hpp',
    'src/qbrain/search/hybrid.cpp', 'src/qbrain/ops/memory_ops.cpp',
    'tests/test_n46f.cpp', 'tests/test_main.cpp', 'CMakeLists.txt',
    'scripts/build-tests-cl.ps1', '.ci/test_cjk_recall.py',
    '.ci/package_n44_development.py', '.github/workflows/n44-validation.yml',
})
MAX_SOURCE_BYTES = 4 * 1024 * 1024
MAX_BUNDLE_BYTES = 16 * 1024 * 1024
SECRET_PATTERNS = (
    re.compile(rb'-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----'),
    re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})'),
    re.compile(rb'\bsk-[A-Za-z0-9_-]{24,}'),
)


class HandoffError(ValueError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise HandoffError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *arguments: str) -> bytes:
    # No command here needs credentials or a network. Ignore inherited Git
    # overrides so this command cannot target another worktree/index/object DB.
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith('GIT_')}
    env.update(GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never',
               GIT_OPTIONAL_LOCKS='0', GIT_NO_REPLACE_OBJECTS='1')
    result = subprocess.run(
        ['git', '-c', 'core.fsmonitor=false', '-c', 'core.pager=cat',
         '-C', str(repo), *arguments], env=env, capture_output=True, timeout=90,
        check=False,
    )
    require(result.returncode == 0, 'Git operation failed: ' + arguments[0] +
            '; no credentials, branch changes or retries were attempted')
    return result.stdout


def check_content(data: bytes) -> None:
    require(len(data) <= MAX_SOURCE_BYTES, 'Source object exceeds handoff limit')
    try:
        data.decode('utf-8')
    except UnicodeDecodeError as error:
        raise HandoffError('Expected UTF-8 source only; refusing binary/private files') from error
    require(b'\x00' not in data, 'NUL in source content')
    require(not any(pattern.search(data) for pattern in SECRET_PATTERNS),
            'Possible credential/private key detected; no content printed or exported')


def export_source(repo: Path, output: Path, *, base: str = BASE,
                  commits: tuple[str, ...] = COMMITS, branch: str = BRANCH) -> dict:
    """Keyword overrides are used only by synthetic tests, not exposed in CLI."""
    require(bool(commits), 'No commits to export')
    for value in (base, *commits):
        require(bool(re.fullmatch(r'[0-9a-f]{40}', value)), 'Invalid pinned commit')
    require(branch.startswith('refs/heads/'), 'Expected a local branch reference')
    repo = Path(git(repo, 'rev-parse', '--show-toplevel').decode('utf-8').strip()).resolve()
    output = output.expanduser().absolute()
    require(not output.exists(), 'Output already exists; choose a new directory')
    require(not output.resolve().is_relative_to(repo), 'Write the handoff outside the worktree')
    origin = git(repo, 'config', '--get', 'remote.origin.url').decode('utf-8').strip()
    require(origin in {'https://github.com/youq616/qbrain.git',
                       'https://github.com/youq616/qbrain',
                       'git@github.com:youq616/qbrain.git',
                       'ssh://git@github.com/youq616/qbrain.git'},
            'Origin is not the expected Qbrain repository; remote value not printed')
    status_before = git(repo, 'status', '--porcelain=v1', '-z', '--untracked-files=all')
    require(not status_before, 'Worktree has uncommitted/untracked files; leave them unchanged')
    head_before = git(repo, 'rev-parse', 'HEAD').decode().strip()
    tip = git(repo, 'rev-parse', '--verify', branch + '^{commit}').decode().strip()
    require(tip == commits[-1], 'Local branch differs from pinned N46F tip; do not reset it')
    observed = git(repo, 'rev-list', '--reverse', base + '..' + branch).decode().splitlines()
    require(observed == list(commits), 'Commit range differs from the two reported commits')
    previous = base
    records = []
    all_paths: set[str] = set()
    for commit in commits:
        parents = git(repo, 'show', '-s', '--format=%P', commit).decode().split()
        require(parents == [previous], 'Unexpected parent/merge in the pinned range')
        check_content(git(repo, 'cat-file', 'commit', commit))
        paths = [p.decode('utf-8') for p in git(repo, 'diff-tree', '--no-commit-id',
                  '--name-only', '--no-renames', '-r', '-z', previous, commit).split(b'\x00') if p]
        require(bool(paths) and set(paths) <= ALLOWED_PATHS,
                'Unexpected changed path; refusing to export unrelated files')
        for revision in (previous, commit):
            for path in paths:
                entry = git(repo, 'ls-tree', '-z', revision, '--', path)
                if not entry:
                    continue  # Addition or deletion; the patch records it.
                header = entry.split(b'\t', 1)[0].split()
                require(len(header) == 3 and header[0] in (b'100644', b'100755')
                        and header[1] == b'blob', 'Non-regular source entry')
                size = int(git(repo, 'cat-file', '-s', header[2].decode()).strip())
                require(0 <= size <= MAX_SOURCE_BYTES, 'Source object exceeds limit')
                check_content(git(repo, 'cat-file', 'blob', header[2].decode()))
        all_paths.update(paths)
        records.append({'commit': commit, 'parent': previous,
                        'tree': git(repo, 'rev-parse', commit + '^{tree}').decode().strip(),
                        'changed_paths': sorted(paths)})
        previous = commit
    with tempfile.TemporaryDirectory(prefix='qbrain-n46f-export-') as temporary:
        staging = Path(temporary)
        bundle = staging / 'n46f.bundle'
        git(repo, 'bundle', 'create', str(bundle), base + '..' + branch)
        require(bundle.stat().st_size <= MAX_BUNDLE_BYTES, 'Bundle exceeds limit')
        git(repo, 'bundle', 'verify', str(bundle))
        advertised = git(repo, 'bundle', 'list-heads', str(bundle)).decode().strip()
        require(advertised == tip + ' ' + branch, 'Bundle advertises unexpected refs')
        patch = git(repo, '-c', 'format.signature=', '-c', 'format.headers=',
                    'format-patch', '--stdout', '--no-cover-letter', '--no-signature',
                    '--no-notes', '--no-ext-diff', '--no-textconv', '--binary',
                    '--full-index', '--no-renames', base + '..' + branch)
        check_content(patch)
        require(git(repo, 'rev-parse', branch).decode().strip() == tip
                and git(repo, 'rev-parse', 'HEAD').decode().strip() == head_before
                and git(repo, 'status', '--porcelain=v1', '-z', '--untracked-files=all') == status_before,
                'Repository changed during export; retry only after review')
        files = {'n46f.bundle': bundle.read_bytes(), 'n46f.patch': patch}
        manifest = {'purpose': 'offline source transfer only; not a build/test PASS',
                    'repository': 'youq616/qbrain', 'base_commit': base,
                    'tip_commit': tip, 'branch': branch, 'commits': records,
                    'changed_paths': sorted(all_paths), 'requires_base_repository': True,
                    'worktree_unchanged': True,
                    'security_scope': 'Allowlisted committed UTF-8 sources and pattern checks; not full DLP',
                    'files': {name: {'bytes': len(data), 'sha256': sha256(data)}
                              for name, data in files.items()}}
        files['manifest.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()
        files['README.txt'] = (
            'Offline N46F source handoff. Includes only the two reported commits,\n'
            'their source changes and ordinary Git author/committer metadata.\n'
            'The bundle requires the base commit already present in a Qbrain clone.\n'
            'Do not execute source, workflows or scripts before engineering review.\n'
            'No user configuration, databases, logs or full repository was copied.\n'
        ).encode()
        output.mkdir(parents=True, exist_ok=False)
        archive = output / 'qbrain-n46f-source-handoff.zip'
        with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as z:
            for name, data in files.items():
                z.writestr(name, data)
        with zipfile.ZipFile(archive) as z:
            require(z.testzip() is None and set(z.namelist()) == set(files), 'Archive verification failed')
            require(all(z.read(name) == data for name, data in files.items()), 'Archive readback differs')
        result = {'result': 'SOURCE_EXPORTED', 'zip': str(archive),
                  'bytes': archive.stat().st_size, 'sha256': sha256(archive.read_bytes()),
                  'base_commit': base, 'tip_commit': tip, 'commit_count': len(commits),
                  'changed_file_count': len(all_paths), 'worktree_unchanged': True,
                  'uploaded': False, 'compiled': False, 'product_tests_executed': False}
        (output / 'export-summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='New directory outside the worktree')
    args = parser.parse_args()
    try:
        print(json.dumps(export_source(args.repo, args.output), ensure_ascii=False))
        return 0
    except (HandoffError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        message = str(error) if isinstance(error, HandoffError) else 'Offline export failed; preserve source unchanged'
        print(json.dumps({'result': 'BLOCKED', 'message': message}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
