"""N49D-only, fail-closed source identity and reviewed delta boundary."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

BASE = 'cfe1ef58e244b51092c2248804b663b6c28913d7'
BASE_TREE = '75b69ad389630e51528ddb5536a27255203470df'
CORRECTION_PARENT = '610bf498d4b2b5cd45921d5f53d71bfacb5b3f4d'
CORRECTION_PARENT_TREE = '181ef0d4e867b669c8a9429f7f9f56ad5a6fdc72'
FIXTURE_PARENT = '7d6aa8dbb62b7d44af9629b5bdbd7ffcd54d6185'
FIXTURE_PARENT_TREE = 'd8c451ae5421abcf709f5f709c243f3f97934a05'
PHASE_PARENT = '652849684fbb0758b861812dd13e68a0df819578'
PHASE_PARENT_TREE = '417b0f186646d6dd7906ed75a5d331cb64937333'
PRE_PHASE_PARENT = 'a6c01c581eb77887ae33090b543a98bbd67477af'
PRE_PHASE_PARENT_TREE = 'fe1250f174afa4eeb8241f4262d855487e1a6045'
LAST_CORRECTION_PARENT = 'a62e648744ddeb23ca20b05421c70aab5c70ea95'
LAST_CORRECTION_PARENT_TREE = '194cbd3f6d486e72f10472234a907e3bf5c1f97e'
PRIOR_CORRECTION_PARENT = 'f64b2eff3c46324f5a8d100748ec6b92ccd4981d'
PRIOR_CORRECTION_PARENT_TREE = 'a37b9b96b50b876f0036ee15cebc6002a242775d'
INTERMEDIATE_PARENT = 'e44de25cc16f3a4154822d3147f20b21b1c69136'
INTERMEDIATE_PARENT_TREE = '2de51cfb37eb7199a1acc5a1a6cd31bb9563efd3'
PREVIOUS_PARENT = 'adf7adfe5ef7cb2a7686161fffd8f00d1d6547c2'
PREVIOUS_PARENT_TREE = '3f166c44c1267c64b1f890617e7062117a9790f5'
EARLIER_PARENT = 'ff61dde8150f30eec699a4e5c01554175ff37f98'
EARLIER_PARENT_TREE = 'd8895a9792cab41cc15d71f7c248fef794829787'
ORIGINAL_PARENT = '0c99f74436682500caeaf0bf68a7bc42310d6a50'
ORIGINAL_PARENT_TREE = 'd91c1f258a704eed9fe899c1193df8d080ff2f56'
CORRECTION_PATHS = frozenset(['.ci/check_n49d_sources.py', '.ci/test_n49d_source_contract.py', '.github/workflows/n49d-mcp-directory-search.yml'])

HANDLERS = 'src/qbrain/ops/handlers.cpp'
SERVER = 'src/qbrain/mcp/server.cpp'
LEDGER = 'docs/OPS-PARITY-LEDGER.md'
NEW = frozenset('''tests/test_mcp_directory_search.cpp
.ci/mcp_directory_search_targets.cmake
.ci/test_mcp_directory_search.py
.ci/check_n49d_sources.py
.ci/test_n49d_source_contract.py
.ci/run_n49d_qualification.py
.github/workflows/n49d-mcp-directory-search.yml
docs/nodes/N49D-PLAN.md
docs/nodes/N49D-PLAN-AUDIT.md
docs/nodes/N49D-HARD-AUDIT.md
docs/integration/MCP-DIRECTORY-SEARCH.md
docs/nodes/n49d-evidence/RESULT.json
docs/nodes/n49d-evidence/SOURCE-MANIFEST.json'''.splitlines())
WRAPPERS = {'scripts/build-cl.ps1': '0d70d018ccfd206aa09d6a8dd52f2f21be0ee5d1', 'scripts/build-tests-cl.ps1': 'fd674ec09cc9f3b2432290a5d66c98e6d92e4411'}
WRAPPER_BASE = {'scripts/build-cl.ps1':'bc9aae3592cefe727b78c2649802e35ee4e94b6c','scripts/build-tests-cl.ps1':'375e7f8f80524dfe94e3f0275b8350fec003436c'}
INHERITED = {HANDLERS, SERVER, LEDGER} | set(WRAPPERS)
ALLOW = NEW | INHERITED
ROOT = Path(__file__).resolve().parents[1]


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, timeout=60, env=dict(os.environ,GIT_NO_LAZY_FETCH='1',GIT_ALLOW_PROTOCOL=''))


def generic_tree_reader(root):
    """Load only unchanged generic tree primitives, never another qualifier."""
    path = Path(root) / '.ci/check_source_archive.py'
    checkout_bytes(path.read_bytes(), '8a573bf1e8673b767b8a6f7ebafa5685f241a86d', os.name == 'nt')
    names = {'Rejected', 'need', 'object_id', 'safe_name', 'tree_from_manifest'}
    nodes = [n for n in ast.parse(path.read_text(encoding='utf-8')).body
             if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    need({n.name for n in nodes} == names, 'generic tree primitive inventory')
    ns = dict(hashlib=hashlib, re=re, MANIFEST_CAP=2*1024*1024, FILE_CAP=5000, PATH_CAP=4096)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), ns)
    return ns['tree_from_manifest']


def checkout_bytes(raw, oid, windows=False):
    """Accept exact Git bytes, or one verified whole-file LF-to-CRLF form."""
    if blob(raw) == oid:
        return raw
    need(windows and b'\0' not in raw, 'checkout blob mismatch')
    canonical = raw.replace(b'\r\n', b'\n')
    need(b'\r' not in canonical and raw == canonical.replace(b'\n', b'\r\n') and
         blob(canonical) == oid, 'checkout newline representation mismatch')
    return canonical


def one_split(raw, anchor):
    need(raw.count(anchor) == 1, 'production anchor ambiguous')
    return raw.split(anchor, 1)


def approved_regions(path, before, after):
    if path in WRAPPERS:
        need(blob(before)==WRAPPER_BASE[path] and blob(after)==WRAPPERS[path],'reviewed wrapper identity mismatch')
    elif path == HANDLERS:
        header = b'#include "qbrain/search/hybrid.hpp"\n'
        added = b'#include "qbrain/search/directory.hpp"\n'
        need(after.count(added) == 1 and header + added in after, 'directory header location')
        stripped = after.replace(header + added, header, 1)
        start = b'void register_search_ops() {\n'
        end = b'  register_one(\n      "think", Scope::Read, [](OpContext& ctx) {'
        bp, bt = one_split(before, start); ap, at = one_split(stripped, start)
        body, bs = one_split(bt, end); changed, ass = one_split(at, end)
        need(bp == ap and bs == ass and body != changed, 'outside search registration changed')
        need(changed.startswith(b'  register_one(\n      "search", Scope::Read, [](OpContext& ctx) {'),
             'search registration start')
    elif path == SERVER:
        anchor = b'    json arguments = params.contains("arguments") ? params["arguments"] : json::object();\n'
        bp, bs = one_split(before, anchor); ap, rest = one_split(after, anchor)
        need(bp == ap and rest.endswith(bs), 'outside search.uri validation changed')
        insertion = rest[:-len(bs)] if bs else rest
        expected = (b'    if (name == "search" && arguments.is_object() && arguments.contains("uri") &&\n'
                    b'        !arguments["uri"].is_string()) {\n'
                    b'      return make_tool_argument_error(id, "uri", "string value required");\n'
                    b'    }\n')
        need(insertion == expected, 'non-narrow search.uri insertion')
    elif path == LEDGER:
        old = before.splitlines(keepends=True); new = after.splitlines(keepends=True)
        need(len(old) == len(new), 'ledger structure changed')
        differences = [(a,b) for a,b in zip(old,new) if a != b]
        need(len(differences) == 1, 'ledger change count')
        a,b = differences[0]
        need(a.startswith(b'|') and b.startswith(b'|') and a.split(b'|')[1].strip() == b'search' and b.split(b'|')[1].strip() == b'search',
             'non-search ledger row changed')
    else:
        raise ValueError('unreviewed inherited delta')


def validate_delta(base, candidate, read_before, read_after, base_commit=BASE, base_tree=BASE_TREE,
                   require_complete=True):
    need(base_commit == BASE and base_tree == BASE_TREE, 'wrong approved base/tree')
    need(set(base) <= set(candidate), 'inherited file deleted')
    new = set(candidate) - set(base)
    need(new <= NEW, 'unreviewed added file')
    if require_complete:
        need(new == NEW, 'required new file missing')
    changed = sorted(p for p in set(base) & set(candidate) if base[p] != candidate[p])
    need(set(changed) <= INHERITED, 'inherited file identity changed')
    if require_complete:
        need(set(changed) == INHERITED, 'required production/ledger delta missing')
    for path in changed:
        need(base[path][0] == candidate[path][0] == '100644', 'inherited mode changed')
        approved_regions(path, read_before(path), read_after(path))
    for path in new:
        need(candidate[path][0] == '100644', 'new file mode unsupported')
    return sorted(new | set(changed))


def stage_zero_index(raw):
    """Keep staged additions/modes visible and reject unresolved index entries."""
    rows={}
    for record in raw.split(b'\0'):
        if not record:continue
        match=re.fullmatch(rb'(100644|100755|120000|160000) ([0-9a-f]{40}) ([0-3])\t([^\0]+)',record)
        need(match is not None, 'invalid index record')
        mode,oid,stage,path=match.groups()
        need(stage==b'0', 'unmerged index entry')
        name=path.decode('utf-8')
        need(name not in rows, 'duplicate index path')
        need(mode in (b'100644',b'100755'), 'nonregular index mode')
        rows[name]=(mode.decode(),oid.decode())
    need(rows, 'empty index inventory')
    return rows


def precommit_index(base, index, untracked):
    need(set(base)<=set(index), 'staged inherited file deleted')
    need((set(index)-set(base))<=NEW and set(untracked)<=NEW, 'unreviewed staged/untracked added file')
    for path,value in index.items():
        if path in base:
            need(value[0]==base[path][0], 'staged inherited mode changed')
            need(value==base[path] or path in INHERITED, 'staged inherited identity changed')
        else:
            need(value[0]=='100644', 'staged new file mode unsupported')
    return dict(index)


def check_ancestry(root, commit=None, tree=None, precommit=False):
    """Only the fixed reviewed lineage edges; no ancestor walk or fetch fallback."""
    head = git(root, 'rev-parse', 'HEAD').decode().strip()
    head_tree = git(root, 'rev-parse', 'HEAD^{tree}').decode().strip()
    need(git(root, 'rev-parse', BASE + '^{tree}').decode().strip() == BASE_TREE, 'base object mismatch')
    need(git(root, 'rev-parse', CORRECTION_PARENT + '^{tree}').decode().strip() == CORRECTION_PARENT_TREE,
         'correction parent tree mismatch')
    need(git(root, 'show', '-s', '--format=%P', CORRECTION_PARENT).decode().strip() == FIXTURE_PARENT,
         'correction parent ancestry mismatch')
    need(git(root, 'rev-parse', FIXTURE_PARENT + '^{tree}').decode().strip() == FIXTURE_PARENT_TREE,
         'fixture parent tree mismatch')
    need(git(root, 'show', '-s', '--format=%P', FIXTURE_PARENT).decode().strip() == PHASE_PARENT,
         'fixture parent ancestry mismatch')
    need(git(root, 'rev-parse', PHASE_PARENT + '^{tree}').decode().strip() == PHASE_PARENT_TREE,
         'phase parent tree mismatch')
    need(git(root, 'show', '-s', '--format=%P', PHASE_PARENT).decode().strip() == PRE_PHASE_PARENT,
         'phase parent ancestry mismatch')
    need(git(root, 'rev-parse', PRE_PHASE_PARENT + '^{tree}').decode().strip() == PRE_PHASE_PARENT_TREE,
         'pre-phase parent tree mismatch')
    need(git(root, 'show', '-s', '--format=%P', PRE_PHASE_PARENT).decode().strip() == LAST_CORRECTION_PARENT,
         'pre-phase parent ancestry mismatch')
    need(git(root, 'rev-parse', LAST_CORRECTION_PARENT + '^{tree}').decode().strip() == LAST_CORRECTION_PARENT_TREE,
         'last correction parent tree mismatch')
    need(git(root, 'show', '-s', '--format=%P', LAST_CORRECTION_PARENT).decode().strip() == PRIOR_CORRECTION_PARENT,
         'last correction parent ancestry mismatch')
    need(git(root, 'rev-parse', PRIOR_CORRECTION_PARENT + '^{tree}').decode().strip() == PRIOR_CORRECTION_PARENT_TREE,
         'prior correction parent tree mismatch')
    need(git(root, 'show', '-s', '--format=%P', PRIOR_CORRECTION_PARENT).decode().strip() == INTERMEDIATE_PARENT,
         'prior correction parent ancestry mismatch')
    need(git(root, 'rev-parse', INTERMEDIATE_PARENT + '^{tree}').decode().strip() == INTERMEDIATE_PARENT_TREE,
         'intermediate parent tree mismatch')
    need(git(root, 'show', '-s', '--format=%P', INTERMEDIATE_PARENT).decode().strip() == PREVIOUS_PARENT,
         'intermediate parent ancestry mismatch')
    need(git(root, 'rev-parse', PREVIOUS_PARENT + '^{tree}').decode().strip() == PREVIOUS_PARENT_TREE,
         'previous parent tree mismatch')
    need(git(root, 'show', '-s', '--format=%P', PREVIOUS_PARENT).decode().strip() == EARLIER_PARENT,
         'previous parent ancestry mismatch')
    need(git(root, 'rev-parse', EARLIER_PARENT + '^{tree}').decode().strip() == EARLIER_PARENT_TREE,
         'earlier parent tree mismatch')
    need(git(root, 'show', '-s', '--format=%P', EARLIER_PARENT).decode().strip() == ORIGINAL_PARENT,
         'earlier parent ancestry mismatch')
    need(git(root, 'rev-parse', ORIGINAL_PARENT + '^{tree}').decode().strip() == ORIGINAL_PARENT_TREE,
         'original parent tree mismatch')
    need(git(root, 'show', '-s', '--format=%P', ORIGINAL_PARENT).decode().strip() == BASE,
         'original parent ancestry mismatch')
    if precommit:
        need(head == CORRECTION_PARENT and head_tree == CORRECTION_PARENT_TREE,
             'precommit requires exact correction parent/tree')
        return head,head_tree,FIXTURE_PARENT,FIXTURE_PARENT_TREE
    need(commit == head and tree == head_tree and head not in (BASE,ORIGINAL_PARENT,EARLIER_PARENT,PREVIOUS_PARENT,INTERMEDIATE_PARENT,PRIOR_CORRECTION_PARENT,LAST_CORRECTION_PARENT,PRE_PHASE_PARENT,PHASE_PARENT,FIXTURE_PARENT,CORRECTION_PARENT), 'candidate pin mismatch')
    need(git(root, 'show', '-s', '--format=%P', head).decode().strip() == CORRECTION_PARENT, 'candidate parent mismatch')
    return head,head_tree,CORRECTION_PARENT,CORRECTION_PARENT_TREE


def validate_correction(parent, candidate, require_complete=True):
    need(set(parent)==set(candidate),'correction added/deleted path')
    need(all(parent[p][0]==candidate[p][0] for p in parent),'correction mode changed')
    changed=sorted(p for p in parent if parent[p]!=candidate[p])
    need(set(changed)<=CORRECTION_PATHS,'unreviewed correction path')
    if require_complete:need(set(changed)==CORRECTION_PATHS,'required correction path missing')
    return changed


def check_source(root, commit=None, tree=None, precommit=False):
    root = Path(root).resolve(strict=True)
    head,head_tree,parent,parent_tree=check_ancestry(root,commit,tree,precommit)
    parse = generic_tree_reader(root)
    base_raw = git(root, 'ls-tree', '-r', '--full-tree', '-z', BASE)
    base = parse(base_raw, BASE_TREE)
    parent_raw = git(root, 'ls-tree', '-r', '--full-tree', '-z', CORRECTION_PARENT)
    correction_parent = parse(parent_raw, CORRECTION_PARENT_TREE)
    raw = git(root, 'ls-tree', '-r', '--full-tree', '-z', head)
    candidate = parse(raw, head_tree)
    sparse = {v[2:].decode() for v in git(root, 'ls-files', '-t', '-z').split(b'\0') if v.startswith(b'S ')}
    untracked = {v.decode() for v in git(root, 'ls-files', '--others', '--exclude-standard', '-z').split(b'\0') if v}
    need(untracked <= NEW if precommit else not untracked, 'unexpected untracked source')
    index_raw=None
    if precommit:
        index_raw=git(root,'ls-files','--stage','-z')
        candidate=precommit_index(base,stage_zero_index(index_raw),untracked)
        validate_correction(correction_parent,candidate,require_complete=False)
        # A staged illegal production edit cannot hide behind a reverted worktree.
        validate_delta(base,candidate,lambda p:git(root,'show',BASE+':'+p),
                       lambda p:git(root,'cat-file','blob',candidate[p][1]),require_complete=False)
    source_hashes = {}
    def read_work(path):
        p = root / path
        need(p.is_file() and not p.is_symlink(), 'source type or absence')
        raw_file = p.read_bytes()
        if precommit:
            if os.name == 'nt' and b'\0' not in raw_file and b'\r\n' in raw_file:
                normalized = raw_file.replace(b'\r\n', b'\n')
                need(b'\r' not in normalized and raw_file == normalized.replace(b'\n', b'\r\n'),
                     'mixed working newline representation')
                raw_file = normalized
            return raw_file
        return checkout_bytes(raw_file, candidate[path][1], os.name == 'nt')
    for path in sorted(set(candidate) | untracked):
        p = root / path
        if not p.exists() and path in sparse:
            continue
        data = read_work(path)
        if precommit:
            indexed_mode=candidate[path][0] if path in candidate else '100644'
            actual_mode=('100755' if p.stat().st_mode & 0o111 else '100644') if os.name!='nt' else indexed_mode
            need(actual_mode==indexed_mode, 'working file mode differs from index')
            candidate[path] = (actual_mode, blob(data))
        source_hashes[path] = sha(data)
    if precommit:
        missing = {p for p in base if not (root / p).exists() and p not in sparse}
        need(not missing, 'working inherited file deleted')
    changed = validate_delta(base, candidate, lambda p: git(root, 'show', BASE + ':' + p),
                             read_work, require_complete=not precommit)
    correction_changed=validate_correction(correction_parent,candidate,require_complete=not precommit)
    return dict(schema='qbrain-n49d-source-v1', passed=True, base=BASE, base_tree=BASE_TREE,
                commit=head, tree=head_tree, parent=parent, parent_tree=parent_tree,
                precommit=precommit, changed=changed, correction_changed=correction_changed,
                changed_files={p:dict(mode=candidate[p][0],blob=candidate[p][1],sha256=sha(read_work(p))) for p in changed},
                checkout_sha256=source_hashes, inventory_sha256=sha(raw),
                index_inventory_sha256=sha(index_raw) if index_raw is not None else None,
                dependency_sha256={p:h for p,h in source_hashes.items() if p.startswith('third_party/')})


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, default=ROOT)
    p.add_argument('--commit'); p.add_argument('--tree'); p.add_argument('--precommit', action='store_true')
    p.add_argument('--report', type=Path)
    args = p.parse_args(argv)
    try:
        result = check_source(args.source, args.commit, args.tree, args.precommit)
        code = 0
    except (ValueError, OSError, subprocess.SubprocessError) as e:
        result = dict(passed=False, error=str(e)); code = 1
    output = json.dumps(result, sort_keys=True, indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True); args.report.write_text(output, encoding='utf-8')
    print(output, end='')
    return code


if __name__ == '__main__':
    sys.exit(main())
