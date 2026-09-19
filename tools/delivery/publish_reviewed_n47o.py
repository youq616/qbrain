"""Fixed N47O release delivery. Verification is read-only; publication is explicit.

Never rebuild/repack the application, overwrite assets, move tags, or delete a
release. Errors retain the current state for an inspected, separate recovery.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import io
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import quote
import zipfile

REPO = 'youq616/qbrain'
BRANCH = 'delivery/n47o-reviewed-c26'
SOURCE = 'c26ec5e512d9ba960b86c9ced5b9b4976b031f2c'
TREE = '2beda65c13421a995826c147aad606ea48d7f694'
REVIEW = '65b118542187f2c61895a62f3753d268fab423bf'
REVIEW_TREE = 'd4d4e419474742abb7879afc39a9373416151f5e'
MERGE = 'b099c7fb7c8bcd29b5ad40e78a113bbbe82d920a'
SUMMARY_BLOB = 'fd273fdd17395caed9839f9914331738c584fcbf'
VERIFIER_SHA = '5a8f793b4f0054d55ffff0a134b013c770f3c686974c47dd46d57fd951ee80c6'
PACKAGE_SHA = 'ec681a4599bf1b2a90f3848f5bf65b6d6a32e37254f32392d0709c43080b356c'
EXE_SHA = 'c35fadde8c8356b7243bf0b34cfd5c836bda27bb46da87eddcc79c1031bf05b5'
TAG = 'windows-preview-c26ec5e5'
PRODUCT = 'qbrain-windows-x64-reviewed.zip'
TITLE = 'Qbrain Windows preview — N47M/N47N fixes (c26ec5e5)'
CAP = 128 * 1024 * 1024
RUNS = {
    'n44': (35368994091, '.github/workflows/n44-validation.yml',
            {'source', 'windows', 'windows-http-2022', 'portable', 'batch-sanitized'}),
    'n42': (35368994139, '.github/workflows/n42-validation.yml', {'source', 'windows', 'portable'}),
    'n47n': (35368994138, '.github/workflows/n47n-validation.yml', {'windows', 'portable'}),
    'ledger': (35368994105, '.github/workflows/ops-ledger-validation.yml',
               {'ledger (ubuntu-latest)', 'ledger (windows-latest)'}),
}
# Normalized verifier labels, source run labels, exact artifact IDs/names/bytes/digests.
ARTIFACTS = (
    ('source', 'n44', 10557946121, 'qbrain-n44-source', 11781388, '80894252ec7debec8c221978bbe6160842350ed6977a76fc43e3b4b142e16d4c'),
    ('windows', 'n44', 10558518896, 'qbrain-n44-windows-logs', 120350, '68aaf22e564f10c45408d99221eaf66cf9315efcc4284eb59727f828e7fcb7e2'),
    ('package', 'n44', 10558169282, 'qbrain-n44-windows-development-package', 2111161, 'c974cff396bfaa4e42fbd106f75ee849428b6b0f05a677ab69ad91391a21064d'),
    ('server2022', 'n44', 10558031058, 'qbrain-n46f-server2022-http-evidence', 20941, '133e78fdc8cf7b0ec9ce2aaa82e4d330fd6639483cbb428db79f5d65558a10ef'),
    ('portable', 'n44', 10557671998, 'qbrain-n44-portable-logs', 73029, '06f0131e5de765a511837e38ad7c9247f568fdf3cce305cce843efd6d772b767'),
    ('sanitizer', 'n44', 10557856756, 'qbrain-n47g-sanitizer-evidence', 26395, '36e7004301851e9f8d50c3b57fcc970ceeab521d4c176db186de05d97bb0a793'),
    ('n42-windows', 'n42', 10557791572, 'qbrain-n42-windows-logs', 30624, '8b885b794b376431204ad3c1170050b05d9590646530d458cbadf7d2b426a359'),
    ('n47n-windows', 'n47n', 10558381236, 'qbrain-n47n-windows-evidence', 68943, '163ef394253a1b7813c7d885d4aac0df17df2c7a8d5c1932f0350d1084fb3a44'),
    ('n47n-portable', 'n47n', 10558340535, 'qbrain-n47n-portable-evidence', 40468, '437f58bffa3f1d2915fffcc1e9a77d32327288588230f08f885018b6faae7d03'),
    ('ledger-windows', 'ledger', 10558140225, 'qbrain-ledger-windows-latest', 1180, '1eb4087fbe4f3edaa65aa7e63ef1aef111187458de373efeadbdef52a65bb9c9'),
    ('ledger-ubuntu', 'ledger', 10558295851, 'qbrain-ledger-ubuntu-latest', 1172, '9c44fb5d116eae26ed527b829527ec4a1fd18cc277f118e3760c875e185ce227'),
)


def need(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def decode(raw: bytes):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def encode(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def read(path: Path) -> bytes:
    need(path.is_file() and not path.is_symlink(), 'regular file required: ' + str(path))
    with path.open('rb') as f:
        raw = f.read(CAP + 1)
    need(len(raw) <= CAP, 'byte cap exceeded')
    return raw


class GitHub:
    """gh owns authentication and authenticated redirect handling; never log tokens."""
    def raw(self, endpoint, *, method='GET', body=None, binary=False, optional=False, upload=None):
        target = endpoint if endpoint.startswith('https://uploads.github.com/') else f'repos/{REPO}/{endpoint}'
        args = ['gh', 'api', target, '--method', method]
        # Actions ZIP endpoints negotiate a redirect with the normal REST accept.
        # Only release assets select their binary representation via this header.
        if binary and endpoint.startswith('releases/assets/'):
            args += ['-H', 'Accept: application/octet-stream']
        if upload is not None:
            args += ['-H', 'Content-Type: application/octet-stream', '--input', str(upload)]
        elif body is not None:
            args += ['--input', '-']
        with tempfile.TemporaryFile() as output:
            r = subprocess.run(args, input=encode(body) if body is not None else None,
                               stdout=output, stderr=subprocess.PIPE, timeout=180)
            output.seek(0); raw = output.read(CAP + 1)
        need(len(raw) <= CAP, 'GitHub response exceeds cap')
        if r.returncode == 0:
            return raw
        # Only a confirmed REST 404 means absence, not network/auth/rate errors.
        if optional and method == 'GET':
            try:
                error = decode(raw)
            except (ValueError, UnicodeError):
                error = {}
            if (isinstance(error, dict) and str(error.get('status')) == '404'
                    and error.get('message') == 'Not Found' and b'(HTTP 404)' in r.stderr):
                return None
        status = re.search(rb'\(HTTP ([0-9]{3})\)', r.stderr)
        code = status.group(1).decode('ascii') if status else 'unknown'
        raise RuntimeError('GitHub request failed (HTTP ' + code + '): ' + endpoint)

    def api(self, endpoint, **kwargs):
        raw = self.raw(endpoint, **kwargs)
        return None if raw is None else decode(raw)

    def upload(self, ident: int, path: Path):
        endpoint = f'https://uploads.github.com/repos/{REPO}/releases/{ident}/assets?name={quote(path.name, safe="")}'
        return self.api(endpoint, method='POST', upload=path)


def git(path: Path, *args) -> bytes:
    return subprocess.check_output(['git', '-C', str(path), *args], stderr=subprocess.PIPE, timeout=60)


def checkout(path: Path, commit: str, tree: str):
    need(git(path, 'rev-parse', 'HEAD').decode().strip() == commit, 'wrong checkout commit')
    need(git(path, 'rev-parse', 'HEAD^{tree}').decode().strip() == tree, 'wrong checkout tree')
    need(git(path, 'status', '--porcelain') == b'', 'dirty fixed checkout')


def validate_run(label, live, listing):
    ident, workflow, mandatory = RUNS[label]
    need(live.get('id') == ident and live.get('path') == workflow and live.get('head_sha') == SOURCE
         and live.get('event') == 'push' and type(live.get('run_attempt')) is int and live['run_attempt'] == 1
         and live.get('status') == 'completed' and live.get('conclusion') == 'success'
         and live.get('repository', {}).get('full_name') == REPO
         and live.get('head_repository', {}).get('full_name') == REPO, 'wrong/failed run: ' + label)
    jobs = listing.get('jobs', [])
    need(type(listing.get('total_count')) is int and listing['total_count'] == len(jobs)
         and len({j.get('name') for j in jobs}) == len(jobs)
         and len({j.get('id') for j in jobs}) == len(jobs), 'incomplete/duplicate jobs: ' + label)
    extras = {'publish-cjk-preview', 'publish-fact-preview'} if label == 'n44' else set()
    need({j.get('name') for j in jobs} == mandatory | extras, 'job identity mismatch: ' + label)
    for j in jobs:
        need(type(j.get('id')) is int and j['id'] > 0 and j.get('run_id') == ident
             and j.get('head_sha') == SOURCE and type(j.get('run_attempt')) is int and j['run_attempt'] == 1
             and j.get('status') == 'completed', 'job source/attempt mismatch')
        if j['name'] in extras:
            need(j.get('conclusion') == 'skipped', 'unexpected publisher execution')
        else:
            steps = j.get('steps')
            need(j.get('conclusion') == 'success' and isinstance(steps, list) and bool(steps)
                 and len({s.get('number') for s in steps}) == len(steps)
                 and all(s.get('status') == 'completed' and s.get('conclusion') == 'success' for s in steps),
                 'failed/missing required job step')
    return {**{k: live[k] for k in ('id', 'path', 'head_sha', 'event', 'run_attempt', 'status', 'conclusion', 'html_url')},
            'repository': REPO, 'head_repository': REPO, 'jobs_total_count': len(jobs), 'jobs': jobs}


def asset_identity(row, name, raw):
    need(row.get('name') == name and type(row.get('id')) is int and row['id'] > 0
         and row.get('state') == 'uploaded' and type(row.get('size')) is int and row['size'] == len(raw)
         and row.get('digest') == 'sha256:' + sha(raw), 'asset identity/digest mismatch: ' + name)
    return {k: row[k] for k in ('id', 'size', 'digest')}


def release_state(release, ident, assets, pins, draft):
    need(release.get('id') == ident and release.get('tag_name') == TAG
         and release.get('target_commitish') == SOURCE and release.get('name') == TITLE
         and release.get('draft') is draft and release.get('prerelease') is True, 'wrong release metadata')
    rows = release.get('assets', [])
    need(len(rows) == len(assets) and len({r.get('name') for r in rows}) == len(rows)
         and {r.get('name') for r in rows} == set(assets), 'missing/duplicate/extra release assets')
    current = {r['name']: asset_identity(r, r['name'], assets[r['name']]) for r in rows}
    need(len({p['id'] for p in current.values()}) == len(current) and current == pins,
         'release assets replaced after upload')


def tag_state(api, *, optional=False):
    row = api.api('git/ref/tags/' + TAG, optional=optional)
    if row is None:
        return False
    need(row.get('ref') == 'refs/tags/' + TAG and row.get('object', {}).get('type') == 'commit'
         and row['object'].get('sha') == SOURCE, 'tag target mismatch; never move it')
    return True


def ensure_absent(api):
    # The list endpoint includes private drafts for the authorized publisher.
    for page in range(1, 101):
        rows = api.api(f'releases?per_page=100&page={page}')
        need(isinstance(rows, list) and not any(r.get('tag_name') == TAG for r in rows),
             'release/draft already exists; refusing overwrite')
        if len(rows) < 100:
            return
    raise ValueError('release listing not complete')


def publish(api, assets, out):
    ensure_absent(api)
    if not tag_state(api, optional=True):
        api.api('git/refs', method='POST', body={'ref': 'refs/tags/' + TAG, 'sha': SOURCE})
    tag_state(api)
    # Creation returns the exact draft ID. Never fetch a draft through by-tag.
    draft = api.api('releases', method='POST', body={
        'tag_name': TAG, 'target_commitish': SOURCE, 'name': TITLE,
        'body': 'Windows 原生开发预览，含 N47M/N47N 修复。先读 START-HERE.zh-CN.md。'
                ' 原始 CI ZIP/EXE/安装脚本未改字节；未签名、非 latest。不是全项目完成，PG/模型/真实客户端验收仍有边界。'
                '\nZIP SHA-256: ' + PACKAGE_SHA,
        'draft': True, 'prerelease': True, 'make_latest': 'false'})
    ident = draft.get('id')
    need(type(ident) is int and ident > 0, 'missing new draft ID')
    release_state(draft, ident, {}, {}, True)
    (out / 'draft.json').write_bytes(encode(draft))
    pins = {}
    for name, raw in assets.items():
        path = out / name
        need(read(path) == raw, 'local asset changed before upload')
        row = api.upload(ident, path)
        pins[name] = asset_identity(row, name, raw)
        (out / 'asset-pins.json').write_bytes(encode(pins))
    for is_draft in (True, False):
        state = api.api(f'releases/{ident}') if is_draft else api.api('releases/tags/' + TAG)
        release_state(state, ident, assets, pins, is_draft)
        tag_state(api)
        for name, pin in pins.items():
            downloaded = api.raw(f'releases/assets/{pin["id"]}', binary=True)
            need(downloaded == assets[name], 'download byte mismatch: ' + name)
        # Recheck IDs *after* downloads too, closing same-size replacement races.
        release_state(api.api(f'releases/{ident}'), ident, assets, pins, is_draft)
        tag_state(api)
        if is_draft:
            api.api(f'releases/{ident}', method='PATCH', body={'draft': False, 'prerelease': True, 'make_latest': 'false'})
    latest = api.api('releases/latest', optional=True)
    need(latest is None or latest.get('id') != ident, 'prerelease became latest')
    receipt = {'result': 'PUBLISHED', 'release_id': ident, 'tag': TAG,
               'url': f'https://github.com/{REPO}/releases/tag/{TAG}', 'source_commit': SOURCE,
               'asset_pins': pins, 'downloaded_before_and_after_publication': True,
               'new_product_build': False, 'signed': False, 'whole_project_complete': False}
    (out / 'publication.json').write_bytes(encode(receipt))
    return receipt


def verify(api, workspace, out):
    source = workspace / 'candidate'; review = workspace / 'review'; merged = workspace / 'merged'
    checkout(source, SOURCE, TREE); checkout(review, REVIEW, REVIEW_TREE); checkout(merged, MERGE, REVIEW_TREE)
    git(review, 'merge-base', '--is-ancestor', SOURCE, REVIEW)
    changed = [x.decode() for x in git(review, 'diff', '--name-only', '--no-renames', '-z', SOURCE, REVIEW).split(b'\0') if x]
    need(changed and all(x.startswith('docs/') or x in ('README.md', 'CURRENT-STATUS.md') for x in changed), 'unreviewed product diff')
    git(review, 'diff', '--exit-code', SOURCE, REVIEW, '--', 'docs/OPS-PARITY-LEDGER.md', 'docs/nodes/n31-evidence/OPS-INVENTORY.json')
    summary_path = review / 'docs/nodes/n47n-evidence/FINAL-SUMMARY.json'
    summary_raw = read(summary_path)
    need(git(review, 'hash-object', str(summary_path)).decode().strip() == SUMMARY_BLOB, 'wrong reviewed summary')
    summary = decode(summary_raw)
    need(summary['verdict'] == 'PASS-scoped-source-and-closure-repair'
         and summary['accepted_candidate'] == SOURCE and summary['accepted_tree'] == TREE, 'review scope mismatch')
    pr = api.api('pulls/31')
    need(pr.get('merged') is True and pr.get('state') == 'closed' and pr.get('merge_commit_sha') == MERGE
         and pr['head']['sha'] == REVIEW and pr['head']['repo']['full_name'] == REPO
         and pr['base']['ref'] == 'main' and pr['base']['repo']['full_name'] == REPO, 'reviewed PR mismatch')
    metadata = {'schema_version': 1, 'repository': REPO, 'source_commit': SOURCE, 'source_tree': TREE,
                'runs': {}, 'artifacts': {}}
    all_runs = {}
    for label, (ident, _, _) in RUNS.items():
        live = api.api(f'actions/runs/{ident}')
        jobs = api.api(f'actions/runs/{ident}/attempts/1/jobs?per_page=100')
        all_runs[label] = validate_run(label, live, jobs)
        if label in ('n42', 'n44'):
            metadata['runs'][label] = all_runs[label]
    (out / 'live-runs.json').write_bytes(encode(all_runs))
    artifacts = out / 'artifacts'; artifacts.mkdir()
    for i, (label, run, ident, name, size, digest) in enumerate(ARTIFACTS):
        row = api.api(f'actions/artifacts/{ident}')
        need(row.get('id') == ident and row.get('name') == name and row.get('expired') is False
             and row.get('size_in_bytes') == size and row.get('digest') == 'sha256:' + digest
             and row.get('workflow_run', {}).get('id') == RUNS[run][0]
             and row['workflow_run'].get('head_sha') == SOURCE, 'original artifact mismatch: ' + label)
        raw = api.raw(f'actions/artifacts/{ident}/zip', binary=True)
        need(len(raw) == size and sha(raw) == digest, 'original artifact bytes mismatch: ' + label)
        (artifacts / (label + '.zip')).write_bytes(raw)
        if i < 7:
            metadata['artifacts'][label] = {'id': ident, 'name': name, 'run_id': RUNS[run][0], 'head_sha': SOURCE,
                                           'expired': False, 'size_in_bytes': size, 'sha256': digest, 'file': label + '.zip'}
    metadata_path = out / 'CI-METADATA.json'; metadata_path.write_bytes(encode(metadata))
    verifier = source / 'docs/nodes/n47l-evidence/verify_candidate.py'
    need(sha(read(verifier)) == VERIFIER_SHA, 'original verifier changed')
    report = out / 'READBACK.json'
    subprocess.run([sys.executable, str(verifier), '--source', str(source), '--artifacts', str(artifacts),
                    '--metadata', str(metadata_path), '--metadata-sha256', sha(read(metadata_path)),
                    '--source-sha', SOURCE, '--source-tree', TREE, '--n44-run', str(RUNS['n44'][0]),
                    '--n42-run', str(RUNS['n42'][0]), '--report', str(report)], check=True, timeout=180)
    result = decode(read(report))
    need(result['result'] == 'PASS' and result['check_count'] == 1216 and result['source_commit'] == SOURCE
         and result['source_tree'] == TREE and result['package'] == {'bytes': 2117939, 'sha256': PACKAGE_SHA, 'manifest_files': 73}
         and result['exe'] == {'bytes': 4077568, 'sha256': EXE_SHA}, 'original readback mismatch')
    # Authenticate both original N47N reports; compare native/portable semantic schedules.
    spec = importlib.util.spec_from_file_location('n47n_check', source / 'docs/nodes/n47n-evidence/check_process_report.py')
    checker = importlib.util.module_from_spec(spec); spec.loader.exec_module(checker)
    process = []
    for label, native in (('n47n-windows', True), ('n47n-portable', False)):
        with zipfile.ZipFile(artifacts / (label + '.zip')) as z:
            need(z.read('source.txt').decode('utf-8-sig').strip() == SOURCE, 'N47N source mismatch')
            process.append(decode(z.read('search-process.json')))
    for label in ('ledger-windows', 'ledger-ubuntu'):
        with zipfile.ZipFile(artifacts / (label + '.zip')) as z:
            need(z.read('source.txt').decode('utf-8-sig').strip() == SOURCE, 'ledger source mismatch')
            for name in ('ledger.log', 'optimized.log'):
                value = decode(z.read(name))
                need(value.get('status') == 'PASS' and value.get('upstream') == 104
                     and value.get('extension') == 4, 'ledger result mismatch')
            log = z.read('tests.log').decode('utf-8-sig')
            need('Ran 19 tests' in log and '\nOK' in log, 'ledger negative suite missing')
    reports = [checker.validate(process[0], process[1], read(source / '.ci/test_search_arguments.py'), True),
               checker.validate(process[1], process[0], read(source / '.ci/test_search_arguments.py'), False)]
    (out / 'SEARCH-READBACK.json').write_bytes(encode({'reports': reports,
        'scope': 'Authenticated original native and portable schedules cross-compared; no new product execution.'}))
    with zipfile.ZipFile(artifacts / 'package.zip') as z:
        package = z.read('qbrain-windows-x64-development.zip')
    need(len(package) == 2117939 and sha(package) == PACKAGE_SHA, 'inner package changed')
    provenance = {'schema': 'qbrain-n47o-delivery-v1', 'repository': REPO, 'source_commit': SOURCE, 'source_tree': TREE,
                  'review_commit': REVIEW, 'review_tree': REVIEW_TREE, 'merge_commit': MERGE,
                  'reviewed_pr': 31, 'original_ci_runs': {k: v[0] for k, v in RUNS.items()},
                  'artifact_ids': {a[0]: a[2] for a in ARTIFACTS}, 'original_readback_checks': result['check_count'],
                  'delivery_commit': os.environ['GITHUB_SHA'], 'delivery_run': int(os.environ['GITHUB_RUN_ID']),
                  'delivery_attempt': int(os.environ['GITHUB_RUN_ATTEMPT']), 'package_bytes': len(package),
                  'package_sha256': PACKAGE_SHA, 'exe_sha256': EXE_SHA, 'release_asset': PRODUCT,
                  'rebuilt_or_repacked': False, 'signed': False, 'postgres_integration_verified': False,
                  'new_live_host_acceptance': False, 'new_provider_egress_verified': False, 'whole_project_complete': False,
                  'review_type': 'Owner-authorized coordinator separate self-review, not independent subagent or third party',
                  'metadata_sha256': sha(read(metadata_path)), 'readback_sha256': sha(read(report))}
    assets = {PRODUCT: package, 'PROVENANCE.json': encode(provenance),
              'START-HERE.zh-CN.md': read(workspace / 'delivery/docs/integration/REVIEWED-PREVIEW.zh-CN.md'),
              'SEARCH-ARGUMENTS.zh-CN.md': read(source / 'docs/integration/SEARCH-ARGUMENTS.zh-CN.md')}
    # Retain original logs beyond Actions' expiration, without repacking the product.
    evidence = io.BytesIO()
    with zipfile.ZipFile(evidence, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name in ('live-runs.json', 'CI-METADATA.json', 'READBACK.json', 'SEARCH-READBACK.json'):
            z.writestr(name, read(out / name))
        for label, *_ in ARTIFACTS:
            if label not in ('source', 'package'):
                z.writestr('original-artifacts/' + label + '.zip', read(artifacts / (label + '.zip')))
    assets['VALIDATION-EVIDENCE.zip'] = evidence.getvalue()
    assets['SHA256SUMS.txt'] = ''.join(sha(raw) + '  ' + name + '\n' for name, raw in assets.items()).encode('utf-8')
    for name, raw in assets.items():
        (out / name).write_bytes(raw)
    (out / 'verification.json').write_bytes(encode({'result': 'VERIFIED', 'source_commit': SOURCE,
        'reviewed_merge': MERGE, 'original_artifact_count': len(ARTIFACTS), 'readback_checks': result['check_count'],
        'assets': {n: {'bytes': len(b), 'sha256': sha(b)} for n, b in assets.items()}, 'published': False}))
    return assets


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--publish', action='store_true'); p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    need(os.environ.get('GITHUB_REPOSITORY') == REPO and os.environ.get('GITHUB_REF') == 'refs/heads/' + BRANCH,
         'wrong delivery context')
    need(not a.output.exists(), 'output must be new'); a.output.mkdir(parents=True)
    api = GitHub(); assets = verify(api, a.workspace.resolve(), a.output)
    if a.publish:
        print(json.dumps(publish(api, assets, a.output)))
    else:
        print(json.dumps({'result': 'VERIFIED', 'published': False}))


if __name__ == '__main__':
    main()
