#!/usr/bin/env python3
"""Independent, offline readback of an explicitly selected N47L recovery run.

Consumes saved GitHub GET responses and the downloaded Actions artifact only.
No networking, product execution, repository mutation, or publication.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

SOURCE = '17e9a435f94e45b3ca22d3da062ba4683c135c4b'
SOURCE_TREE = 'f9d42819772df53dd8c6337c3cb19c8940d7023a'
READBACK_SHA = '016bdd09c7c51d45c067e4e725438a3fe1f0b481da572062910e40639473e2c0'
INITIAL_RUN = 35233247840
INITIAL_COMMIT = '2f254681c31fd493fa9cb5ab14ae089608f8a4ad'
RELEASE_ID = 390787606
TAG = 'multiterm-preview-17e9a435'
TITLE = 'Qbrain N47L explicit multi-term recall (17e9a435)'
PINS = {
    'qbrain-windows-x64-multiterm.zip': {'id': 570420529, 'size': 2114341, 'digest': 'sha256:ed44a43d79e1e76efa768e74872223cd5d867dfb92881fe67aab129789cd4408'},
    'PROVENANCE.json': {'id': 570420531, 'size': 2049, 'digest': 'sha256:6cc243b432dbb444f83f9983f4294d0a4c516edc2ad0180b9a2940cc810cd59a'},
    'SHA256SUMS.txt': {'id': 570420528, 'size': 181, 'digest': 'sha256:5cd993f0e3a1fe73cfb818706f27e353902738ceabb5e01482b120489c0d715b'},
}

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('Duplicate JSON key: ' + key)
        out[key] = value
    return out

def obj(raw):
    return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory', type=Path, required=True)
    p.add_argument('--run-id', type=int, required=True)
    p.add_argument('--commit', required=True)
    p.add_argument('--workflow-sha256', required=True)
    p.add_argument('--recorded-at-utc', required=True)
    args = p.parse_args()
    d = args.directory.resolve()
    checks = []
    def need(condition, label):
        if not condition:
            raise AssertionError(label)
        checks.append(label)
    def read(name):
        return (d / name).read_bytes()
    def release_metadata(release, draft, label):
        need(release['id'] == RELEASE_ID and release['tag_name'] == TAG and release['target_commitish'] == SOURCE, label + ': source and release ID')
        need(release['draft'] is draft and release['prerelease'] is True and release['name'] == TITLE, label + ': visibility and title')
        need(release['published_at'] is None if draft else isinstance(release['published_at'], str), label + ': publication timestamp')
        rows = release['assets']
        need(len(rows) == 3 and len({row['name'] for row in rows}) == 3, label + ': exactly three distinct assets')
        need({row['name'] for row in rows} == set(PINS), label + ': exact asset names')
        for row in rows:
            pin = PINS[row['name']]
            need({key: row[key] for key in ('id', 'size', 'digest')} == pin and row['state'] == 'uploaded', label + ': asset pin ' + row['name'])
    run = obj(read('run-raw.json'))
    need(run['id'] == args.run_id and run['head_sha'] == args.commit and run['run_attempt'] == 1, 'selected recovery run identity')
    need(run['status'] == 'completed' and run['conclusion'] == 'success', 'recovery run completed success')
    need(sha(read('workflow.yml')) == args.workflow_sha256, 'recovery workflow bytes')
    jobs = obj(read('jobs-raw.json'))
    need(jobs['total_count'] == 1 and len(jobs['jobs']) == 1, 'one publication recovery job')
    job = jobs['jobs'][0]
    need(job['run_id'] == args.run_id and job['head_sha'] == args.commit and job['status'] == 'completed' and job['conclusion'] == 'success', 'recovery job identity and success')
    need(all(step['status'] == 'completed' and step['conclusion'] == 'success' for step in job['steps']), 'all recovery job steps succeeded')
    artifacts = obj(read('artifacts-raw.json'))['artifacts']
    need(len(artifacts) == 1, 'one recovery delivery artifact')
    artifact = artifacts[0]
    need(artifact['name'] == 'qbrain-n47l-reviewed-delivery' and artifact['expired'] is False and artifact['workflow_run']['id'] == args.run_id and artifact['workflow_run']['head_sha'] == args.commit, 'delivery artifact source metadata')
    outer = read('delivery.zip')
    need(len(outer) == artifact['size_in_bytes'] and 'sha256:' + sha(outer) == artifact['digest'], 'delivery artifact original bytes and digest')
    with zipfile.ZipFile(io.BytesIO(outer)) as z:
        infos = z.infolist()
        need(len({row.filename for row in infos}) == len(infos) and all(not row.is_dir() for row in infos), 'artifact file names unique and no directory entries')
        need(z.testzip() is None, 'artifact CRC checks')
        need(all(row.file_size <= 16 * 1024 * 1024 and '..' not in Path(row.filename).parts and not row.filename.startswith('/') for row in infos), 'artifact member path and size bounds')
        files = {row.filename: z.read(row.filename) for row in infos}
    required = {'readback.json', 'publication.json', 'draft-before-publication.json', 'release-public.json', 'release-by-tag.json'} | {'release-assets/' + name for name in PINS}
    need(set(files) == required, 'exact recovery artifact inventory')
    baseline = d.parent / 'new-candidate'
    need(files['readback.json'] == (baseline / 'candidate-readback.json').read_bytes() and sha(files['readback.json']) == READBACK_SHA, 'readback byte-identical to independent source candidate')
    report = obj(files['readback.json'])
    need(report['result'] == 'PASS' and report['check_count'] == 1094 and report['source_commit'] == SOURCE and report['source_tree'] == SOURCE_TREE, 'original 1094-check candidate report')
    expected = obj((d.parent / 'failed-delivery/reconstructed-PROVENANCE.json').read_bytes())
    need(sha((d.parent / 'failed-delivery/reconstructed-PROVENANCE.json').read_bytes()) == PINS['PROVENANCE.json']['digest'][7:], 'independent expected provenance original digest')
    receipt = obj(files['publication.json'])
    need(all(key in receipt and receipt[key] == value for key, value in expected.items()), 'publication preserves every original provenance field')
    need(receipt['result'] == 'PUBLISHED' and receipt['publication_mode'] == 'RECOVER_FIXED_DRAFT' and receipt['release_id'] == RELEASE_ID and receipt['tag'] == TAG, 'publication recovery identity')
    need(receipt['initial_delivery_run'] == INITIAL_RUN and receipt['initial_delivery_run_attempt'] == 1 and receipt['initial_delivery_commit'] == INITIAL_COMMIT and receipt['initial_delivery_conclusion'] == 'failure', 'receipt preserves original failed delivery')
    need(receipt['recovery_run'] == args.run_id and receipt['recovery_run_attempt'] == 1 and receipt['recovery_commit'] == args.commit, 'receipt binds exact successful recovery')
    need(receipt['asset_pins'] == PINS and set(receipt['assets_read_back']) == set(PINS) and len(receipt['assets_read_back']) == 3 and receipt['original_assets_replaced'] is False, 'receipt fixes original three asset IDs')
    need(receipt['original_provenance_sha256'] == PINS['PROVENANCE.json']['digest'][7:], 'receipt original provenance digest')
    for name, pin in PINS.items():
        raw = files['release-assets/' + name]
        need(len(raw) == pin['size'] and 'sha256:' + sha(raw) == pin['digest'], 'downloaded original asset bytes: ' + name)
    original_package = baseline / 'artifacts/package.zip'
    with zipfile.ZipFile(original_package) as z:
        inner = z.read('qbrain-windows-x64-development.zip')
    need(files['release-assets/qbrain-windows-x64-multiterm.zip'] == inner, 'release ZIP byte-identical to original CI inner ZIP')
    need(files['release-assets/PROVENANCE.json'] == (d.parent / 'failed-delivery/reconstructed-PROVENANCE.json').read_bytes(), 'original downloaded provenance exact bytes')
    need(files['release-assets/SHA256SUMS.txt'] == (d.parent / 'failed-delivery/reconstructed-SHA256SUMS.txt').read_bytes(), 'original downloaded checksum exact bytes')
    release_metadata(obj(files['draft-before-publication.json']), True, 'artifact draft snapshot')
    release_metadata(obj(files['release-public.json']), False, 'artifact public by ID')
    release_metadata(obj(files['release-by-tag.json']), False, 'artifact public by tag')
    live = obj(read('release-by-id-raw.json'))
    release_metadata(live, False, 'independent live public by ID')
    release_metadata(obj(read('release-by-tag-raw.json')), False, 'independent live public by tag')
    tag = obj(read('tag-raw.json'))
    need(tag['ref'] == 'refs/tags/' + TAG and tag['object']['type'] == 'commit' and tag['object']['sha'] == SOURCE, 'independent live tag exact source')
    latest = obj(read('latest-raw.json'))
    if latest is None:
        error = obj(read('latest-error.json'))
        need(error['error_code'] == 'NOT_FOUND' and error['error_data']['status'] == '404', 'latest absence is explicit API 404')
    need(latest is None or latest['id'] != RELEASE_ID, 'preview is not latest release')
    need(receipt['url'] == live['html_url'] == 'https://github.com/youq616/qbrain/releases/tag/' + TAG, 'public receipt URL')
    direct_downloads = {}
    for name, pin in PINS.items():
        path = d / 'public-downloads' / name
        downloaded = path.is_file()
        if downloaded:
            raw = path.read_bytes()
            need(len(raw) == pin['size'] and 'sha256:' + sha(raw) == pin['digest'] and raw == files['release-assets/' + name], 'independent public download original bytes: ' + name)
        direct_downloads[name] = {'downloaded': downloaded, 'bytes_compared': pin['size'] if downloaded else 0}
    for name, raw in files.items():
        destination = d / 'artifact-contents' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    output = {
        'schema': 'qbrain.n47l.release-readback.v1', 'result': 'PASS',
        'recorded_at_utc': args.recorded_at_utc, 'repository': 'youq616/qbrain',
        'source_commit': SOURCE, 'source_tree': SOURCE_TREE,
        'review_commit': expected['review_commit'], 'review_tree': expected['review_tree'], 'merge_commit': expected['merge_commit'],
        'release_id': RELEASE_ID, 'tag': TAG, 'url': live['html_url'], 'draft': False, 'prerelease': True, 'latest': False,
        'initial_delivery': {'run': INITIAL_RUN, 'attempt': 1, 'commit': INITIAL_COMMIT, 'conclusion': 'failure'},
        'recovery': {'run': args.run_id, 'attempt': 1, 'commit': args.commit, 'conclusion': 'success', 'workflow_sha256': args.workflow_sha256, 'job_id': job['id'], 'url': run['html_url'], 'job_url': job['html_url']},
        'artifact': {'id': artifact['id'], 'bytes': len(outer), 'sha256': sha(outer), 'member_count': len(files)},
        'readback': {'checks': 1094, 'bytes': len(files['readback.json']), 'sha256': sha(files['readback.json']), 'byte_identical_to_candidate': True},
        'publication_receipt': {'bytes': len(files['publication.json']), 'sha256': sha(files['publication.json'])},
        'asset_pins': PINS, 'original_ci_zip_bytes_identical': True, 'original_assets_replaced': False,
        'asset_byte_readback_channel': 'Original assets downloaded by fixed release IDs in recovery workflow, then independently downloaded as the bound Actions artifact; matched independent live release API digests.',
        'all_public_assets_directly_downloaded': all(row['downloaded'] for row in direct_downloads.values()),
        'direct_public_asset_download_count': sum(row['downloaded'] for row in direct_downloads.values()),
        'direct_public_assets': direct_downloads,
        'direct_public_download_attempts_sha256': sha(read('PUBLIC-DOWNLOAD-ATTEMPTS.json')),
        'direct_public_download_limitation': 'PROVENANCE public URL and public asset API GET timed out. Its original bytes were independently verified through the recovery artifact and the live release asset ID/digest.',
        'signed': False, 'postgres_integration_verified': False, 'new_live_host_acceptance': False, 'new_provider_egress_verified': False,
        'auditor_remote_mutations': False, 'auditor_check_count': len(checks),
    }
    (d / 'RELEASE-READBACK.json').write_text(json.dumps(output, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (d / 'auditor-checks.json').write_text(json.dumps(checks, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
