"""N47N real CLI/MCP tests. Synthetic SQLite; no actual provider or client.

--baseline enables ordinary-input byte comparisons. Run this same script with
an old --binary to demonstrate rejection of the old parser. Python is test-only.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import tempfile


def require(ok: bool, message: str) -> None:
    if not ok:
        raise AssertionError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--source-commit')
    a = parser.parse_args()
    exe = a.binary.resolve(strict=True)
    baseline = a.baseline.resolve(strict=True) if a.baseline else None
    checks, commands = [], []
    sha = lambda b: hashlib.sha256(b).hexdigest()

    def case(name, fn):
        start = len(commands)
        try:
            fn()
            checks.append({'name': name, 'passed': True, 'commands': [start, len(commands)]})
        except Exception as e:
            checks.append({'name': name, 'passed': False, 'error': str(e), 'commands': [start, len(commands)]})
        print(('PASS ' if checks[-1]['passed'] else 'FAIL ') + name, flush=True)

    with tempfile.TemporaryDirectory(prefix='qbrain-n47n-') as td:
        root = Path(td) / '中文 search 😀'; root.mkdir()
        env = {k: v for k, v in os.environ.items()
               if not k.upper().startswith(('QBRAIN', 'OPENAI', 'ANTHROPIC'))
               and k.upper() not in {'HOME', 'USERPROFILE', 'LOCALAPPDATA', 'APPDATA'}}
        env.update({k: str(root) for k in ('HOME', 'USERPROFILE', 'LOCALAPPDATA', 'APPDATA')})
        data = (root if os.name == 'nt' else root / '.local/share') / 'Qbrain'
        brain_names = {'intended', 'environment', 'configured', 'default', '--json'}

        def run(argv, *, payload=None, extra=None, expected=0, binary=None):
            raw = payload if isinstance(payload, bytes) else (json.dumps(payload, ensure_ascii=False).encode() if payload is not None else b'')
            b = binary or exe
            r = subprocess.run([str(b), *argv], input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               cwd=root, env={**env, **(extra or {})}, timeout=30)
            commands.append({'binary': 'baseline' if b == baseline else 'candidate', 'argv': argv,
                             'stdin': raw.decode(), 'expected_exit': expected, 'exit': r.returncode,
                             'stdout': r.stdout.decode('utf-8', errors='replace'),
                             'stderr': r.stderr.decode('utf-8', errors='replace'),
                             'stdout_sha256': sha(r.stdout), 'stderr_sha256': sha(r.stderr),
                             'environment_overrides': extra or {}})
            require(r.returncode == expected, f'exit {r.returncode} != {expected}: {argv}: {(r.stdout+r.stderr)[:300]!r}')
            return r

        def obj(argv, **kw):
            return json.loads(run(argv, **kw).stdout)

        def snapshot(brain):
            with closing(sqlite3.connect(data / 'brains' / brain / 'brain.db')) as db:
                names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
                return sha(repr({t: sorted(db.execute('SELECT * FROM "' + t + '"').fetchall(), key=repr) for t in names}).encode())

        needles = ['--brain sentinelneedle', '--json sentinelneedle', '--limit sentinelneedle',
                   '--no-vector sentinelneedle', '--mode tokenmax sentinelneedle',
                   '--rerank sentinelneedle', '--rerank-llm sentinelneedle',
                   '--source sentinelneedle', '--query sentinelneedle', '--unknown=value sentinelneedle',
                   '中文日志前缀', '-single sentinelneedle']
        for brain in sorted(brain_names):
            run(['init', '--brain', brain, '--no-default'])
            for n in range(2):
                body = root / 'body.md'
                body.write_text(f'{brain} page {n}\n' + '\n'.join(needles), encoding='utf-8')
                run(['put', '--brain', brain, '--slug', brain.strip('-') + '/' + str(n),
                     '--title', 'Named query fixture', '--file', str(body), '--json'])

        def mcp(query, brain='intended'):
            message = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                       'params': {'name': 'search', 'arguments': {'query': query, 'no_vector': True,
                                  'source_id': 'default', 'limit': 10, 'mode': 'conservative'}}}
            r = obj(['serve', '--brain', brain], payload=json.dumps(message, ensure_ascii=False).encode() + b'\n')['result']
            require(not r.get('isError'), 'MCP search denied')
            return json.loads(r['content'][-1]['text'])

        expected_results = {}
        for needle in needles:
            expected_results[needle] = mcp(needle)
            require(expected_results[needle], 'fixture/MCP must yield nonempty hits: ' + needle)

        fixed_opts = ['--brain', 'intended', '--json', '--no-vector', '--mode', 'conservative']
        before_reads = {b: snapshot(b) for b in brain_names}
        for needle in needles:
            for form in ('separated', 'attached', 'delimiter'):
                if form == 'separated': tail = ['--query', needle]
                elif form == 'attached': tail = ['--query=' + needle]
                else: tail = ['--', needle]
                def parity(tail=tail, needle=needle):
                    actual = obj(['search', *fixed_opts, *tail])
                    require(actual == expected_results[needle], 'CLI/MCP result mismatch')
                    require(all(h['source_id'] == 'default' and h['slug'].startswith('intended/') for h in actual), 'wrong brain/source')
                case(form + '/' + needle, parity)

        # Every permutation keeps query data separate from flags and real values.
        groups = [('--query', '--brain sentinelneedle'), ('--brain', 'intended'),
                  ('--json',), ('--no-vector',), ('--mode', 'conservative')]
        for i, order in enumerate(itertools.permutations(groups)):
            argv = ['search', *[word for group in order for word in group]]
            case('option-order/' + str(i), lambda argv=argv: require(obj(argv) == expected_results[needles[0]], 'permuted result changed'))

        def delimiter_tokens():
            query = '--brain sentinelneedle'
            r = obj(['search', *fixed_opts, '--', '--brain', 'sentinelneedle'])
            require(r == expected_results[query], 'delimiter token joining changed')
        case('delimiter/multiple-tokens', delimiter_tokens)

        def text_not_json():
            r = run(['search', '--brain', 'intended', '--no-vector', '--mode', 'conservative', '--', '--json', 'sentinelneedle'])
            require(r.stdout.startswith(b'1. intended/'), 'literal --json toggled JSON output')
        case('literal-json-does-not-toggle-format', text_not_json)

        def attached_brain():
            r = obj(['search', '--brain=--json', '--json', '--no-vector', '--mode=conservative', '--limit=1', '--query=sentinelneedle'])
            require(len(r) == 1 and r[0]['slug'].startswith('json/'), 'option-shaped brain lost')
        case('attached-brain-and-limit', attached_brain)
        for label, config_brain, extra, explicit, chosen in (
            ('default', None, {}, [], 'default'),
            ('file', 'configured', {}, [], 'configured'),
            ('env', 'configured', {'QBRAIN_BRAIN': 'environment'}, [], 'environment'),
            ('empty-env', 'configured', {'QBRAIN_BRAIN': ''}, [], 'configured'),
            ('explicit', 'configured', {'QBRAIN_BRAIN': 'environment'}, ['--brain', 'intended'], 'intended'),
        ):
            config = data / 'config.json'
            if config_brain is None: config.unlink(missing_ok=True)
            else: config.write_text(json.dumps({'brain_id': config_brain}), encoding='utf-8')
            def precedence(extra=extra, explicit=explicit, chosen=chosen):
                hits = obj(['search', '--query', '--brain sentinelneedle', '--no-vector', '--json', '--mode', 'conservative', *explicit], extra=extra)
                require(hits and all(h['slug'].startswith(chosen + '/') for h in hits), 'brain precedence changed')
            case('brain-precedence/' + label, precedence)
        # Restore configuration before checking DB snapshots (file isn't in DB).
        (data / 'config.json').write_text(json.dumps({'brain_id': 'intended'}), encoding='utf-8')
        case('search-reads-preserve-all-database-rows', lambda: require(before_reads == {b: snapshot(b) for b in brain_names}, 'read mutated data'))

        invalid = [
            (['--brain', '--no-vector', 'needle'], 'search_option_value_required'),
            (['--limit', '--', 'needle'], 'search_option_value_required'),
            (['--mode'], 'search_option_value_required'),
            (['--query'], 'search_option_value_required'),
            (['--bad', 'needle'], 'unknown_search_option'),
            (['--source', 'alpha', 'needle'], 'unknown_search_option'),
            (['--brain sentinelneedle'], 'unknown_search_option'),
            (['--json=true', 'needle'], 'search_flag_has_value'),
            (['--query=x', '--query', 'y'], 'duplicate_search_option'),
            (['--brain=x', '--brain', 'y', 'needle'], 'duplicate_search_option'),
            (['--no-vector', '--no-vector', 'needle'], 'duplicate_search_option'),
            (['--query=x', 'word'], 'mixed_search_query_forms'),
            (['--query=x', '--', 'word'], 'mixed_search_query_forms'),
        ]
        before_invalid = {b: snapshot(b) for b in brain_names}
        for argv, error in invalid:
            def rejected(argv=argv, error=error):
                r = run(['search', *argv], expected=2, extra={'QBRAIN_BRAIN': 'must-not-exist'})
                require(error.encode() in r.stderr and not r.stdout, 'wrong parse error contract')
                require(not (data / 'brains' / 'must-not-exist').exists(), 'invalid query opened a brain')
            case('reject/' + repr(argv), rejected)
        for argv in ([], ['--'], ['--query='], ['--query', ' \t\r\n '], ['--json']):
            def empty(argv=argv):
                r = run(['search', *argv], expected=1, extra={'QBRAIN_BRAIN': 'must-not-exist'})
                require(r.stdout == (b'' if '--json' in argv else b'query required'), 'empty-query contract changed')
                require(not (data / 'brains' / 'must-not-exist').exists(), 'empty query opened a brain')
            case('empty/' + repr(argv), empty)
        case('invalid-input-preserves-all-database-rows', lambda: require(before_invalid == {b: snapshot(b) for b in brain_names}, 'rejected input mutated data'))

        if baseline:
            for query in ('sentinelneedle', '中文日志前缀', 'absent-needle'):
                for mode in ('balanced', 'conservative', 'tokenmax'):
                    for json_flag in ([], ['--json']):
                        argv = ['search', query, '--brain', 'intended', '--no-vector', '--mode', mode, '--limit', '1', *json_flag]
                        def same(argv=argv):
                            fixed, old = run(argv), run(argv, binary=baseline)
                            require((fixed.returncode, fixed.stdout, fixed.stderr) == (old.returncode, old.stdout, old.stderr), 'ordinary command byte mismatch')
                        case('baseline-bytes/' + repr(argv), same)
            for flags in (['--rerank'], ['--rerank', '--rerank-llm']):
                argv = ['search', 'sentinelneedle', '--brain', 'intended', '--json', '--no-vector', *flags]
                def same_rerank(argv=argv):
                    fixed, old = run(argv), run(argv, binary=baseline)
                    require((fixed.returncode, fixed.stdout, fixed.stderr) == (old.returncode, old.stdout, old.stderr), 'rerank byte mismatch')
                case('baseline-rerank/' + repr(flags), same_rerank)
        case('no-unexpected-brain-directories', lambda: require({p.name for p in (data / 'brains').iterdir()} == brain_names, 'extra brain directory'))

    report = {'schema': 'qbrain-search-arguments-v1', 'source_commit': a.source_commit,
              'platform': platform.platform(), 'native_windows': os.name == 'nt',
              'binary_sha256': sha(exe.read_bytes()), 'baseline_sha256': sha(baseline.read_bytes()) if baseline else None,
              'script_sha256': sha(Path(__file__).read_bytes()), 'checks': checks, 'commands': commands,
              'passed': sum(c['passed'] for c in checks), 'failed': sum(not c['passed'] for c in checks),
              'command_count': len(commands), 'limits': ['synthetic SQLite', 'no live provider/client/PostgreSQL', 'not an independent subagent review']}
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"SEARCH_PROCESS passed={report['passed']} failed={report['failed']} commands={len(commands)}")
    raise SystemExit(1 if report['failed'] else 0)


if __name__ == '__main__':
    main()
