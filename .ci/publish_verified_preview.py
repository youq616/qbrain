"""Publish only the pinned, verified unsigned preview; never overwrite a release."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
from repack_verified_preview import repack, CODE, DOCS, RUN, EXE_SHA

REPO = 'youq616/qbrain'
TAG = 'memory-preview-5ee79dfd'
LOG_ARTIFACT = 10270422765
LOG_SHA = 'aa73772d02792c2a1b194912b5b92414139f221f9a3d9c82fec2a79b62651624'

def gh(*args: str) -> bytes:
    return subprocess.check_output(['gh', *args], timeout=120)

def api(path: str):
    return json.loads(gh('api', path))

def main() -> None:
    if os.environ.get('GITHUB_REPOSITORY') != REPO or os.environ.get('GITHUB_REF') != 'refs/heads/delivery/memory-preview-5ee79dfd':
        raise RuntimeError('Not the explicitly authorized publication branch')
    run = api(f'repos/{REPO}/actions/runs/{RUN}')
    if (run.get('conclusion') != 'success' or run.get('head_sha') != CODE
            or run.get('head_repository', {}).get('full_name') != REPO
            or run.get('event') != 'push'):
        raise RuntimeError('Expected native validation did not pass for the pinned source')
    comparison=api(f'repos/{REPO}/compare/{CODE}...{DOCS}')
    if comparison.get('status') != 'ahead' or comparison.get('ahead_by') != 1:
        raise RuntimeError('Unexpected documentation lineage')
    changes=comparison.get('files',[])
    if not changes or any(f['filename']!='README.md' and not f['filename'].startswith('docs/') for f in changes):
        raise RuntimeError('Documentation revision contains code changes')
    artifacts=api(f'repos/{REPO}/actions/runs/{RUN}/artifacts')['artifacts']
    wanted={10271347236:'1a9e6b4e297d1a6495170f33bc22850acdda58ddbae766833d2b4cb290e820a9',LOG_ARTIFACT:LOG_SHA}
    for artifact_id, digest in wanted.items():
        matching=[a for a in artifacts if a['id']==artifact_id]
        if len(matching)!=1 or matching[0]['expired'] or matching[0]['digest']!='sha256:'+digest:
            raise RuntimeError('Artifact identity mismatch or expiry')
    existing = subprocess.run(['gh','api',f'repos/{REPO}/releases/tags/{TAG}'],capture_output=True,timeout=30)
    if existing.returncode == 0:
        raise RuntimeError('Release exists; refusing to modify or overwrite it')
    if b'HTTP 404' not in existing.stderr:
        raise RuntimeError('Could not verify release absence')
    work=Path('preview-work');work.mkdir(exist_ok=False)
    output=work/'out';output.mkdir()
    gh('run','download',str(RUN),'--repo',REPO,'--name','qbrain-n44-windows-development-package','--dir',str(work/'artifact'))
    def git_file(path: str, destination: Path) -> None:
        destination.write_bytes(subprocess.check_output(['git','show',DOCS+':'+path],timeout=30))
    git_file('docs/integration/WINDOWS-MEMORY.md',work/'corrected.md')
    git_file('docs/nodes/n44-evidence/RESULT.json',work/'result.json')
    subprocess.run(['python3','.ci/test_repack_preview.py',str(work)],check=True,timeout=30)
    report=repack(work/'artifact/qbrain-windows-x64-development.zip',work/'corrected.md',work/'result.json',output/'qbrain-windows-x64-memory-preview.zip')
    (output/'PROVENANCE.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    logs=gh('api',f'repos/{REPO}/actions/artifacts/{LOG_ARTIFACT}/zip')
    if hashlib.sha256(logs).hexdigest()!=LOG_SHA:
        raise RuntimeError('Original native logs hash mismatch')
    (output/'qbrain-verified-native-logs.zip').write_bytes(logs)
    names=sorted(output.iterdir())
    (output/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in names),encoding='utf-8')
    notes=f'''## Qbrain Windows memory preview — unsigned development build

Native-tested source: `{CODE}`. Documentation-only revision: `{DOCS}`.
Validation: https://github.com/{REPO}/actions/runs/{RUN}

Download **qbrain-windows-x64-memory-preview.zip**, extract the entire archive, and read **QUICKSTART.zh-CN.md**. It contains the actual tested EXE, PowerShell 5.1/7 project installer, provenance and licenses. Historical dist installers are not this build. Do not move the EXE/scripts after installation.

已加入 Claude/Codex 项目自动记忆适配、可撤销安装、分层上下文与精简 MCP。安装默认只召回，`-EnableCapture` 才启用本地采集；不会自动启用模型外发和 MCP 写入。客户端项目/Hook 信任仍须审核。已有脑库先备份。

Native gates: 44 registered regression groups; memory 44; MCP 17; Hooks 69; context 65; project config 6. Each PowerShell version: installer 69, consent/path 16, transport 8. Real PostgreSQL DSN integration was explicitly skipped.

EXE SHA-256: `{EXE_SHA}`. ZIP SHA-256: `{report['sha256']}`.

The package corrects documentation only; executable and script bytes are unchanged from CI. The original manifest is retained. Default L0/L1 is extractive, not a semantic summary. Provider model extraction's 60,000 ms transport parameter is not a strict total wall-clock deadline.

**Not full project completion:** no real logged-in host/model acceptance, no actual Win11 user environment, no online quality/billing benchmark, no new PostgreSQL memory/context backend, no Cursor automatic installer, no full gbrain parity or ANN. This preview is unsigned and does not guarantee token savings. Internal upstream version metadata is retained; use source SHA/manifest to identify it.
'''
    (work/'notes.md').write_text(notes,encoding='utf-8')
    assets=sorted(output.iterdir())
    # Pin a real lightweight tag before drafting; never move an existing tag.
    tag_probe=subprocess.run(['gh','api',f'repos/{REPO}/git/ref/tags/{TAG}'],capture_output=True,timeout=30)
    if tag_probe.returncode == 0:
        tag_ref=json.loads(tag_probe.stdout)
    elif b'HTTP 404' in tag_probe.stderr:
        tag_ref=json.loads(gh('api',f'repos/{REPO}/git/refs','--method','POST','-f','ref=refs/tags/'+TAG,'-f','sha='+CODE))
    else:
        raise RuntimeError('Could not verify tag absence')
    if tag_ref['object']['type']!='commit' or tag_ref['object']['sha']!=CODE:
        raise RuntimeError('Existing tag is not the tested commit')
    # Upload privately first. Publish only after GitHub confirms all asset hashes.
    gh('release','create',TAG,*map(str,assets),'--repo',REPO,'--verify-tag','--title','Qbrain Windows memory preview (5ee79dfd)','--draft','--prerelease','--latest=false','--notes-file',str(work/'notes.md'))
    matches=[r for r in api(f'repos/{REPO}/releases?per_page=100') if r['tag_name']==TAG]
    if len(matches)!=1:
        raise RuntimeError('Could not identify the draft release')
    release=matches[0]
    if not release['draft'] or not release['prerelease']:
        raise RuntimeError('Release is not the expected private draft preview')
    remote={a['name']:a for a in release['assets']}
    if set(remote)!={p.name for p in assets}:
        raise RuntimeError('Unexpected release assets; retaining draft')
    for p in assets:
        asset=remote[p.name]
        if asset['size']!=p.stat().st_size or asset.get('digest')!='sha256:'+hashlib.sha256(p.read_bytes()).hexdigest():
            raise RuntimeError('Uploaded asset mismatch; retaining draft')
    ref=api(f'repos/{REPO}/git/ref/tags/{TAG}')
    if ref['object']['type']!='commit' or ref['object']['sha']!=CODE:
        raise RuntimeError('Tag target differs from tested source; retaining draft')
    gh('release','edit',TAG,'--repo',REPO,'--draft=false','--prerelease','--latest=false')
    published=api(f'repos/{REPO}/releases/tags/{TAG}')
    if published['draft'] or not published['prerelease']:
        raise RuntimeError('Publication verification failed')
    print(json.dumps({'release':published['html_url'],'published':True,'report':report},indent=2))

if __name__=='__main__':
    main()
