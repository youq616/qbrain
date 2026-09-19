"""Verify fixed N47R native evidence, then optionally publish the tested bytes.

The default is read-only. No rebuilding, overwriting releases, moving tags,
auto-deletion or model requests. The older state-machine helpers are hash-pinned.
"""
from __future__ import annotations
import argparse
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
from urllib.request import urlopen
import zipfile

import verify_n47r_evidence as v

REPO = 'youq616/qbrain'
BRANCH = 'delivery/n47r-integrated-preview'
TAG = 'windows-integrated-preview-9e9a92b0'
TITLE = 'Qbrain N47R — integrated Windows preview with installer recovery'
PRODUCT = 'qbrain-windows-x64-n47r-preview.zip'
BASE_SHA = 'ec681a4599bf1b2a90f3848f5bf65b6d6a32e37254f32392d0709c43080b356c'
LEGACY_SHA = 'c01890e7b941cb25718e479d8f5ded0576210df709ad3b5fcdd96b713a6f263a'
RUNS = {
    'native': (v.RUN, v.SOURCE, '.github/workflows/n47r-validation.yml',
               {'full-native': 105859910076, 'bundle (ubuntu-latest)': 105859910257,
                'bundle (windows-latest)': 105859910461}),
    'upgrade': (v.UPGRADE_RUN, v.UPGRADE_SOURCE, '.github/workflows/n47r-upgrade-validation.yml',
                {'upgrade (powershell)': 105860856957, 'upgrade (pwsh)': 105860856792}),
}
ARTIFACTS = (
    ('windows', 'native', 10579886985, 'qbrain-n47r-windows-latest', 17338465, '90ce92026b23c7b37edbc8ad3f47e7a6e891905a8916596221fbad02a2f91c35'),
    ('linux', 'native', 10579304715, 'qbrain-n47r-ubuntu-latest', 16223888, '2799de41e488d75186015e591afaef4ffd19ba883a239378a669150a73c7418f'),
    ('native', 'native', 10580126897, 'qbrain-n47r-full-native', 29624, '4ad5839d0aa048a496bd13cfa3a841f3f89e7f5d4cce25909e12d74b9acbcc1c'),
    ('upgrade5', 'upgrade', 10579509829, 'qbrain-n47r-upgrade-powershell', 14123173, '1cf15ce7751ccb47216363c0ed1e78fc7525370dc4cd7065c339a8e9451645ba'),
    ('upgrade7', 'upgrade', 10580057003, 'qbrain-n47r-upgrade-pwsh', 14123144, 'eddfc42d2cca2858b06f25ccc3ee9af8ec6dfa84bc7d141b09d000f444d6ead2'),
)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')


def legacy_helpers():
    path = Path(__file__).with_name('publish_reviewed_n47o.py')
    v.need(v.sha(path.read_bytes()) == LEGACY_SHA, 'legacy publication helpers changed')
    spec = importlib.util.spec_from_file_location('n47r_legacy', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    # Only constants used by the reused transport/state helpers are re-bound.
    # The N47O verify/publish functions are not called or edited.
    module.TAG = TAG; module.SOURCE = v.SOURCE; module.TITLE = TITLE
    return module


def validate_live(label, run, listing):
    ident, source, path, jobs = RUNS[label]
    v.need(run.get('id') == ident and run.get('head_sha') == source and run.get('path') == path
           and run.get('event') == 'push' and type(run.get('run_attempt')) is int and run['run_attempt'] == 1
           and run.get('status') == 'completed' and run.get('conclusion') == 'success'
           and run.get('repository', {}).get('full_name') == REPO
           and run.get('head_repository', {}).get('full_name') == REPO, 'live run identity/status')
    rows = listing.get('jobs')
    v.need(isinstance(rows, list) and type(listing.get('total_count')) is int
           and listing['total_count'] == len(rows) == len(jobs), 'incomplete job listing')
    v.need({j.get('name'): j.get('id') for j in rows} == jobs, 'job identity')
    for j in rows:
        v.need(j.get('run_id') == ident and j.get('head_sha') == source
               and type(j.get('run_attempt')) is int and j['run_attempt'] == 1
               and j.get('status') == 'completed' and j.get('conclusion') == 'success', 'job failure/source')
        steps = j.get('steps')
        v.need(isinstance(steps, list) and bool(steps) and len({s.get('number') for s in steps}) == len(steps), 'missing/duplicate steps')
        required = ({'Unchanged full native unit suite'} if j['name'] == 'full-native' else
                    {'Prepare independently pinned packages', 'Actual guide extraction and old-to-new upgrade'}
                    if label == 'upgrade' else {'Fetch only the pinned public baseline',
                    'Test builder and reproduce the exact candidate twice', 'Actual extracted Windows installer and task gates'})
        v.need(required <= {s.get('name') for s in steps}, 'missing required verification step')
        for s in steps:
            expected = 'skipped' if j['name'] == 'bundle (ubuntu-latest)' and s.get('name') == 'Actual extracted Windows installer and task gates' else 'success'
            v.need(s.get('status') == 'completed' and s.get('conclusion') == expected, 'unexpected missing/failed step')
    return {'run': run, 'listing': listing}


def authenticated_pins(api, out):
    native = {'source_commit': v.SOURCE, 'source_tree': v.TREE, 'run_id': v.RUN, 'artifacts': {}}
    upgrade = {'source_commit': v.UPGRADE_SOURCE, 'source_tree': v.UPGRADE_TREE, 'run_id': v.UPGRADE_RUN, 'artifacts': {}}
    runs = {}
    for label, (ident, source, _, _) in RUNS.items():
        run = api.api(f'actions/runs/{ident}')
        listing = api.api(f'actions/runs/{ident}/attempts/1/jobs?per_page=100')
        runs[label] = validate_live(label, run, listing)
        commit = api.api('git/commits/' + source)
        v.need(commit.get('sha') == source and commit.get('tree', {}).get('sha') == (v.TREE if label == 'native' else v.UPGRADE_TREE), 'live source tree')
    (out / 'GITHUB-RUNS.json').write_bytes(encoded(runs))
    artifact_dir = out / 'original-artifacts'; artifact_dir.mkdir()
    for label, group, ident, name, size, digest in ARTIFACTS:
        row = api.api(f'actions/artifacts/{ident}')
        v.need(row.get('id') == ident and row.get('name') == name and row.get('expired') is False
               and row.get('size_in_bytes') == size and row.get('digest') == 'sha256:' + digest
               and row.get('workflow_run', {}).get('id') == RUNS[group][0]
               and row['workflow_run'].get('head_sha') == RUNS[group][1], 'live artifact identity')
        raw = api.raw(f'actions/artifacts/{ident}/zip', binary=True)
        v.need(len(raw) == size and v.sha(raw) == digest, 'downloaded artifact bytes')
        (artifact_dir / (label + '.zip')).write_bytes(raw)
        (native if group == 'native' else upgrade)['artifacts'][label] = {'id': ident, 'file': label + '.zip', 'bytes': size, 'sha256': digest}
    (out / 'ARTIFACT-PINS.json').write_bytes(encoded({'native': native, 'upgrade': upgrade}))
    return artifact_dir, native, upgrade


def assemble_assets(out, artifact_dir, native, upgrade, native_result, upgrade_result):
    w = v.unzip((artifact_dir / 'windows.zip').read_bytes())[0]
    bundle = w['one/' + v.NAME]
    v.need(v.sha(bundle) == v.BUNDLE_SHA and len(bundle) == v.BUNDLE_BYTES, 'product bytes changed')
    members = v.unzip(bundle)[0]
    (out / 'NATIVE-READBACK.json').write_bytes(encoded(native_result))
    (out / 'UPGRADE-READBACK.json').write_bytes(encoded(upgrade_result))
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(artifact_dir.glob('*.zip')):
            z.writestr('original-artifacts/' + path.name, path.read_bytes())
        for name in ('GITHUB-RUNS.json', 'ARTIFACT-PINS.json', 'NATIVE-READBACK.json', 'UPGRADE-READBACK.json'):
            z.writestr(name, (out / name).read_bytes())
    evidence = stream.getvalue()
    v.need(len(evidence) < v.CAP, 'evidence archive too large')
    provenance = {
        'schema': 'qbrain-n47r-release-provenance-v1', 'repository': REPO,
        'integration_source': v.SOURCE, 'integration_tree': v.TREE,
        'upgrade_test_source': v.UPGRADE_SOURCE, 'upgrade_test_tree': v.UPGRADE_TREE,
        'components': v.obj(members['MANIFEST.json'])['components'],
        'native_validation_run': v.RUN, 'upgrade_validation_run': v.UPGRADE_RUN,
        'artifact_pins': {'native': native['artifacts'], 'upgrade': upgrade['artifacts']},
        'delivery_source': os.environ['GITHUB_SHA'], 'delivery_run': int(os.environ['GITHUB_RUN_ID']),
        'delivery_attempt': int(os.environ['GITHUB_RUN_ATTEMPT']),
        'bundle_sha256': v.BUNDLE_SHA, 'bundle_bytes': len(bundle), 'repackaged': True,
        'exe_recompiled': False, 'native_bundle_evidence': 'VERIFIED', 'real_client_acceptance': 'NOT_RUN',
        'model_answers': 'NOT_RUN', 'provider_cost': None, 'signed': False, 'stable_v1': False,
        'evidence_zip_sha256': v.sha(evidence), 'evidence_retention': 'Includes all five exact original artifact ZIPs',
        'manifest_status_scope': 'The immutable internal manifest describes construction time; this external receipt binds later native acceptance to the exact ZIP digest.',
        'reviewer': 'Owner-authorized coordinator separate self-review, not a subagent or third party',
    }
    assets = {PRODUCT: bundle, 'START-HERE.zh-CN.md': members['START-HERE.zh-CN.md'],
              'PROVENANCE.json': encoded(provenance), 'VALIDATION-EVIDENCE.zip': evidence}
    assets['SHA256SUMS.txt'] = ''.join(v.sha(raw) + '  ' + name + '\n' for name, raw in assets.items()).encode()
    for name, raw in assets.items(): (out / name).write_bytes(raw)
    (out / 'verification.json').write_bytes(encoded({'result': 'VERIFIED', 'published': False,
        'assets': {name: {'bytes': len(raw), 'sha256': v.sha(raw)} for name, raw in assets.items()}}))
    return assets


def prepare(api, out):
    artifact_dir, native, upgrade = authenticated_pins(api, out)
    url = f'https://github.com/{REPO}/releases/download/windows-preview-c26ec5e5/qbrain-windows-x64-reviewed.zip'
    with urlopen(url, timeout=90) as response: raw = response.read(32 * 1024 * 1024 + 1)
    v.need(len(raw) == 2117939 and v.sha(raw) == BASE_SHA, 'original public ZIP identity')
    baseline = out / 'baseline.zip'; baseline.write_bytes(raw)
    native_result = v.verify(artifact_dir, native, baseline)
    z = v.unzip((artifact_dir / 'linux.zip').read_bytes())[0]
    source, modes, _ = v.unzip(z['qbrain-source.zip'])
    bundle = z['one/' + v.NAME]
    upgrade_result = v.verify_upgrade(artifact_dir, upgrade, source, modes, bundle)
    return assemble_assets(out, artifact_dir, native, upgrade, native_result, upgrade_result)


def publish(api, assets, out, helpers):
    # Preserve the previously tested ID/digest/readback state machine. The release
    # body is new: this package is repackaged, unlike the immutable old N47O ZIP.
    helpers.ensure_absent(api)
    if not helpers.tag_state(api, optional=True):
        api.api('git/refs', method='POST', body={'ref': 'refs/tags/' + TAG, 'sha': v.SOURCE})
    helpers.tag_state(api)
    draft = api.api('releases', method='POST', body={
        'tag_name': TAG, 'target_commitish': v.SOURCE, 'name': TITLE,
        'body': 'N47R 集成 Windows 开发预览：同一包包含已验收的 N47P 安装恢复修复和 N47Q 评测工具。'
                'EXE 保留 c26 字节，ZIP 重新组装；两版 PowerShell 的整包/旧版升级测试已通过。'
                '先读 START-HERE.zh-CN.md，核对同版本 PROVENANCE 与 SHA256SUMS。'
                '未签名、非 latest；不代表真实客户端/模型效果或稳定 v1 已验收。'
                '\nZIP SHA-256: ' + v.BUNDLE_SHA,
        'draft': True, 'prerelease': True, 'make_latest': 'false'})
    ident = draft.get('id'); v.need(type(ident) is int and ident > 0, 'draft ID missing')
    helpers.release_state(draft, ident, {}, {}, True)
    (out / 'draft.json').write_bytes(encoded(draft))
    pins = {}
    for name, raw in assets.items():
        path = out / name; v.need(path.read_bytes() == raw, 'local asset changed')
        pins[name] = helpers.asset_identity(api.upload(ident, path), name, raw)
        (out / 'asset-pins.json').write_bytes(encoded(pins))
    for is_draft in (True, False):
        state = api.api(f'releases/{ident}') if is_draft else api.api('releases/tags/' + TAG)
        helpers.release_state(state, ident, assets, pins, is_draft); helpers.tag_state(api)
        for name, pin in pins.items():
            v.need(api.raw(f'releases/assets/{pin["id"]}', binary=True) == assets[name], 'release download mismatch')
        helpers.release_state(api.api(f'releases/{ident}'), ident, assets, pins, is_draft); helpers.tag_state(api)
        if is_draft:
            api.api(f'releases/{ident}', method='PATCH', body={'draft': False, 'prerelease': True, 'make_latest': 'false'})
    latest = api.api('releases/latest', optional=True)
    v.need(latest is None or latest.get('id') != ident, 'release became latest')
    receipt = {'result': 'PUBLISHED', 'release_id': ident, 'tag': TAG, 'source_commit': v.SOURCE,
               'asset_pins': pins, 'bundle_sha256': v.BUNDLE_SHA, 'repackaged': True,
               'exe_recompiled': False, 'signed': False, 'stable_v1': False,
               'url': f'https://github.com/{REPO}/releases/tag/{TAG}',
               'before_and_after_publication_byte_readback': True}
    (out / 'publication.json').write_bytes(encoded(receipt))
    return receipt


def anonymous_readback(assets, receipt, out):
    from urllib.parse import quote
    v.need(receipt.get('result') == 'PUBLISHED', 'no publication receipt')
    rows = []
    for name, expected in assets.items():
        url = f'https://github.com/{REPO}/releases/download/{TAG}/' + quote(name, safe='')
        with urlopen(url, timeout=120) as response: raw = response.read(v.CAP + 1)
        v.need(raw == expected, 'anonymous public bytes mismatch')
        rows.append({'name': name, 'bytes': len(raw), 'sha256': v.sha(raw)})
    record = {'result': 'PASS', 'authenticated': False, 'release_id': receipt['release_id'], 'assets': rows}
    (out / 'public-readback.json').write_bytes(encoded(record))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--publish', action='store_true')
    a = parser.parse_args()
    v.need(os.environ.get('GITHUB_REPOSITORY') == REPO and os.environ.get('GITHUB_REF') == 'refs/heads/' + BRANCH,
           'wrong repository/branch context')
    a.output.mkdir(parents=True, exist_ok=False)
    helpers = legacy_helpers(); api = helpers.GitHub(); assets = prepare(api, a.output)
    if a.publish:
        receipt = publish(api, assets, a.output, helpers)
        anonymous_readback(assets, receipt, a.output)
        print(json.dumps(receipt))
    else:
        print(json.dumps({'result': 'VERIFIED', 'published': False}))


if __name__ == '__main__': main()
