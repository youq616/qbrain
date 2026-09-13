"""Publish only the same-run, fully gated native evidence-fact package; no rebuild/repack."""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".ci"))
from validate_cjk_report import validate_report
from validate_fact_report import validate_report as validate_facts

REPO = 'youq616/qbrain'
BRANCH = 'optimization/n47a-evidence-facts'
CAP = 64 * 1024 * 1024


def gh(*args, output=None):
    return subprocess.run(['gh', *args], check=True, stdout=output or subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=120).stdout


def api(path):
    return json.loads(gh('api', f'repos/{REPO}/{path}'))


def unpack(raw):
    if len(raw) > CAP:
        raise ValueError('archive byte cap')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        items = z.infolist()
        if len(items) > 128 or sum(i.file_size for i in items) > CAP:
            raise ValueError('unpacked byte/member cap')
        if len({i.filename for i in items}) != len(items):
            raise ValueError('duplicate member')
        # Return bytes only; never extract untrusted paths.
        return {i.filename: z.read(i) for i in items}


def verify_product(raw, source):
    files = unpack(raw)
    manifest = json.loads(files['MANIFEST.json'])
    validation = json.loads(files['verification/validation.json'])
    cjk = json.loads(files['verification/cjk-recall.json'])
    assert manifest['source_commit'] == validation['source_commit'] == cjk['source_commit'] == source
    assert manifest['result'] == validation['result'] == cjk['result'] == 'PASS'
    assert validation['registered_groups'] == 49
    assert cjk['native_windows'] is True
    validate_report(cjk, source_commit=source, binary_sha256=hashlib.sha256(files['qbrain.exe']).hexdigest(),
                    script_sha256=hashlib.sha256(files['verification/test_cjk_recall.py']).hexdigest())
    assert cjk['real_agent_verified'] is False and cjk['live_provider_verified'] is False
    assert set(files) == set(manifest['files']) | {'MANIFEST.json', 'README-FIRST.txt'}
    for name, metadata in manifest['files'].items():
        assert metadata['bytes'] == len(files[name])
        assert metadata['sha256'] == hashlib.sha256(files[name]).hexdigest()
    facts=json.loads(files['verification/fact-process.json'])
    validate_facts(facts,source_commit=source,binary_sha256=hashlib.sha256(files['qbrain.exe']).hexdigest(),
                   script_sha256=hashlib.sha256(files['verification/test_fact_process.py']).hexdigest())
    assert 'EVIDENCE-FACTS.zh-CN.md' in files
    exe = hashlib.sha256(files['qbrain.exe']).hexdigest()
    assert manifest['binary_sha256'] == validation['binary_sha256'] == cjk['binary_sha256'] == exe
    assert 'verification/test_cjk_recall.py' in files and 'CJK-RECALL.zh-CN.md' in files
    return {'source_commit': source, 'binary_sha256': exe,
            'package_sha256': hashlib.sha256(raw).hexdigest(), 'package_bytes': len(raw),
            'registered_groups': 49, 'cjk_process_checks': cjk['check_count'], 'fact_process_checks': facts['check_count'],
            'signed': False, 'real_agent_verified': False, 'live_provider_verified': False}


def main():
    source = os.environ['GITHUB_SHA']
    run_id = os.environ['GITHUB_RUN_ID']
    assert os.environ.get('GITHUB_REPOSITORY') == REPO
    assert os.environ.get('GITHUB_REF') == 'refs/heads/' + BRANCH
    assert re.fullmatch('[0-9a-f]{40}', source) and run_id.isdecimal()
    run = api('actions/runs/' + run_id)
    assert run['head_sha'] == source and run['head_branch'] == BRANCH and run['event'] == 'push'
    jobs = api(f'actions/runs/{run_id}/jobs?per_page=100')['jobs']
    for name in ('source', 'portable', 'windows', 'windows-http-2022'):
        matching = [j for j in jobs if j['name'] == name]
        assert len(matching) == 1 and matching[0]['conclusion'] == 'success'
    artifacts = api(f'actions/runs/{run_id}/artifacts?per_page=100')['artifacts']
    matching = [x for x in artifacts if x['name'] == 'qbrain-n44-windows-development-package']
    assert len(matching) == 1
    item = matching[0]
    assert not item['expired'] and item['size_in_bytes'] <= CAP
    root = Path(os.environ['RUNNER_TEMP']) / ('qbrain-fact-publish-' + run_id)
    root.mkdir(exist_ok=False)
    outer = root / 'artifact.zip'
    with outer.open('xb') as stream:
        gh('api', f'repos/{REPO}/actions/artifacts/{item["id"]}/zip', output=stream)
    data = outer.read_bytes()
    assert 'sha256:' + hashlib.sha256(data).hexdigest() == item['digest']
    members = unpack(data)
    assert set(members) == {'qbrain-windows-x64-development.zip', 'SHA256SUMS.txt'}
    raw = members['qbrain-windows-x64-development.zip']
    assert members['SHA256SUMS.txt'].decode().split()[0] == hashlib.sha256(raw).hexdigest()
    provenance = verify_product(raw, source)
    provenance.update(repository=REPO, workflow_run_id=int(run_id), artifact_id=item['id'],
                      scope='Explicit evidence-backed fact versions; no semantic inference or automatic recall; first write makes additive schema and local backup')
    out = root / 'release'
    out.mkdir()
    product = out / 'qbrain-windows-x64-facts.zip'
    product.write_bytes(raw)  # exact tested inner ZIP, never repacked
    (out / 'SHA256SUMS.txt').write_text(provenance['package_sha256'] + '  ' + product.name + '\n')
    (out / 'PROVENANCE.json').write_text(json.dumps(provenance, indent=2) + '\n')
    tag = 'fact-preview-' + source[:8]
    names = ['qbrain-windows-x64-facts.zip', 'SHA256SUMS.txt', 'PROVENANCE.json']
    notes = ('Unsigned Windows development preview. Same-source native gates passed. '
             'Read EVIDENCE-FACTS.zh-CN.md before use: the first explicit fact write adds '
             'an optional SQLite module after a backup. Complete extracted user quotes only; '
             'no semantic truth/confidence inference, automatic recall, new provider consent '
             'or live user-host acceptance. ZIP SHA256: ' + provenance['package_sha256'])
    gh('release', 'create', tag, *(str(out/n) for n in names), '--repo', REPO,
       '--target', source, '--draft', '--prerelease', '--latest=false',
       '--title', 'Qbrain evidence-backed facts preview (' + source[:8] + ')', '--notes', notes)
    readback = root / 'readback'
    gh('release', 'download', tag, '--repo', REPO, '--dir', str(readback))
    assert {p.name for p in readback.iterdir()} == set(names)
    for name in names:
        assert (out/name).read_bytes() == (readback/name).read_bytes()
    gh('release', 'edit', tag, '--repo', REPO, '--draft=false', '--prerelease', '--latest=false')
    print(json.dumps({'tag': tag, **provenance}))


if __name__ == '__main__':
    main()
