"""N47N real CLI/MCP grammar checks; synthetic SQLite, no live provider/client.

Python is test-only. --baseline enables ordinary input byte comparisons, not
an alternative expected-result generator for new behavior. Reports keep every
command, expected exit and output bytes (base64); failures are not self-PASSed.
"""
from __future__ import annotations
import argparse
import base64
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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    baseline = args.baseline.resolve(strict=True) if args.baseline else None
    checks: list[dict] = []
    commands: list[dict] = []
    sha = lambda raw: hashlib.sha256(raw).hexdigest()

    def case(name, function):
        start = len(commands)
        try:
            function()
            checks.append({'name': name, 'passed': True, 'command_range': [start, len(commands)]})
        except Exception as error:
            checks.append({'name': name, 'passed': False, 'error': str(error), 'command_range': [start, len(commands)]})
            print('FAIL ' + name + ': ' + str(error), flush=True)

    with tempfile.TemporaryDirectory(prefix='qbrain-n47n-') as temp:
        root = Path(temp) / '中文 search 😀'
        root.mkdir()
        env = {key: value for key, value in os.environ.items()
               if not key.upper().startswith(('QBRAIN', 'OPENAI', 'ANTHROPIC'))}
        env.update({key: str(root) for key in ('HOME', 'USERPROFILE', 'LOCALAPPDATA', 'APPDATA')})
        data = (root if os.name == 'nt' else root / '.local/share') / 'Qbrain'

        def run(argv, *, executable=None, extra=None, stdin=b'', expected=0):
            exe = executable or binary
            result = subprocess.run([str(exe), *argv], input=stdin, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, cwd=root, env={**env, **(extra or {})}, timeout=30)
            commands.append({'binary': 'baseline' if exe == baseline else 'candidate',
                             'argv': list(argv), 'stdin_base64': base64.b64encode(stdin).decode(),
                             'exit': result.returncode, 'expected_exit': expected,
                             'stdout_base64': base64.b64encode(result.stdout).decode(),
                             'stderr_base64': base64.b64encode(result.stderr).decode(),
                             'stdout_sha256': sha(result.stdout), 'stderr_sha256': sha(result.stderr)})
            require(result.returncode == expected,
                    f'{argv}: exit {result.returncode}, expected {expected}: ' + (result.stdout+result.stderr).decode('utf-8', errors='replace')[:500])
            return result

        def obj(argv, **kwargs):
            return json.loads(run(argv, **kwargs).stdout)

        def sql(brain, statement, parameters=()):
            with closing(sqlite3.connect(data/'brains'/brain/'brain.db')) as db:
                result = db.execute(statement, parameters).fetchall()
                db.commit()
                return result

        def snapshot():
            state = {}
            for path in sorted(data.glob('brains/*/brain.db')):
                with closing(sqlite3.connect(path)) as db:
                    tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
                    state[path.parent.name] = {table: sorted(db.execute('SELECT * FROM "'+table.replace('"', '""')+'"').fetchall(), key=repr) for table in tables}
            return sha(repr(state).encode('utf-8'))

        invalid = [
            ([], 'search_query_required'), (['--'], 'search_query_required'),
            (['--query', ''], 'search_query_required'), (['--query=\t'], 'search_query_required'),
            (['\t  '], 'search_query_required'), (['--query'], 'missing_search_value'),
            (['q', '--brain'], 'missing_search_value'), (['q', '--limit'], 'missing_search_value'),
            (['q', '--mode'], 'missing_search_value'),
            (['q', '--brain', '--no-vector'], 'missing_search_value'),
            (['q', '--limit', '--json'], 'missing_search_value'),
            (['q', '--mode', '--brain', 'intended'], 'missing_search_value'),
            (['q', '--bogus'], 'invalid_search_argument'), (['q', '--source', 'default'], 'invalid_search_argument'),
            (['q', '--json=true'], 'invalid_search_argument'),
            (['q', '--json', '--json'], 'duplicate_search_argument'),
            (['q', '--no-vector', '--no-vector'], 'duplicate_search_argument'),
            (['--query', 'q', '--query=x'], 'duplicate_search_argument'),
            (['q', '--limit', '2', '--limit=1'], 'duplicate_search_argument'),
            (['q', '--brain', 'new-one', '--brain', 'new-two'], 'duplicate_search_argument'),
            (['q', '--mode', 'balanced', '--mode=conservative'], 'duplicate_search_argument'),
            (['q', '--rerank', '--rerank'], 'duplicate_search_argument'),
            (['q', '--rerank-llm', '--rerank-llm'], 'duplicate_search_argument'),
            (['q', '--query', 'q'], 'mixed_search_query'),
            (['--query=q', '--', 'q'], 'mixed_search_query'),
            (['q', '--limit', '1tail'], 'invalid_search_limit'),
            (['q', '--limit', '+-1'], 'invalid_search_limit'),
            (['q', '--limit', '2147483648'], 'invalid_search_limit'),
            (['q', '--limit', ' 2'], 'invalid_search_limit'),
            (['q', '--mode', 'invalid'], 'invalid_search_mode'),
            (['q', '--brain', ''], 'invalid brain id'),
            (['q', '--brain', '../escape'], 'invalid brain id'),
        ]
        for number, (argv, code) in enumerate(invalid):
            def reject(argv=argv, code=code):
                result = run(['search', *argv], expected=2)
                require(result.stdout == b'' and code.encode() in result.stderr, 'wrong diagnostic/channel')
                require(not data.exists(), 'malformed invocation created data root')
            case(f'fresh invalid {number}: {code}', reject)
        # Fail early rather than initialize fixture atop stray brains from a buggy binary.
        # Each rejection above still records its actual output before this cleanup.
        if data.exists():
            import shutil
            shutil.rmtree(data)

        brains = ('intended', 'environment', 'configured', 'default', '--json')
        text = 'sentinelneedle alpha beta 中文日志😀 --brain --source --json --limit --mode --rerank --rerank-llm --no-vector --query -- --brain=decoy  x=y '
        for brain in brains:
            run(['init', '--brain', brain, '--no-default'])
            for index in range(3):
                body = root / 'body.md'
                body.write_text(text + f' {brain}/{index}', encoding='utf-8')
                run(['put', '--brain', brain, '--slug', f'{brain}/page-{index}', '--title', f'{brain} {index}', '--file', str(body), '--json'])
            # A non-default limit ensures omission/empty and argv limits differ.
            sql(brain, "INSERT INTO config(key,value) VALUES('search.default_limit','2') ON CONFLICT(key) DO UPDATE SET value='2'")
        (data/'config.json').write_text(json.dumps({'brain_id': 'intended'}), encoding='utf-8')
        before = snapshot()
        normal = ['--brain', 'intended', '--json', '--no-vector']

        def mcp(query, limit=2, mode=None):
            arguments = {'query': query, 'no_vector': True, 'limit': limit, 'source_id': 'default'}
            if mode is not None:
                arguments['mode'] = mode
            request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                       'params': {'name': 'search', 'arguments': arguments}}
            response = obj(['serve', '--brain', 'intended'], stdin=(json.dumps(request, ensure_ascii=False)+'\n').encode())
            require('error' not in response and not response['result'].get('isError', False), 'MCP rejected query')
            return json.loads(response['result']['content'][-1]['text'])

        queries = ('--brain sentinelneedle', '--brain', '--json', '--source', '--limit', '--mode',
                   '--rerank', '--rerank-llm', '--no-vector', '--query', '--', '-- --json', '--brain=decoy',
                   '中文日志😀', 'sentinelneedle', 'x=y', '  sentinelneedle  ')
        for query in queries:
            for form in ('value', 'equals', 'separator'):
                def literal(query=query, form=form):
                    effective = query.strip() if form == 'separator' else query
                    tail = ['--query', query] if form == 'value' else ['--query='+query] if form == 'equals' else ['--', query]
                    found = obj(['search', *normal, *tail])
                    require(found == mcp(effective), 'CLI/MCP response mismatch')
                    if effective == '--':
                        require(found == [], 'punctuation-only query unexpectedly matched')
                    else:
                        require(found and all(row['slug'].startswith('intended/') for row in found), 'wrong brain or empty fixture result')
                case(f'literal/{form}/{query}', literal)

        groups = [('--query', '--brain'), ('--brain', 'intended'), ('--json',), ('--no-vector',), ('--limit', '1')]
        for index, order in enumerate(itertools.permutations(groups)):
            def ordered(order=order):
                found = obj(['search', *(word for group in order for word in group)])
                require(len(found) == 1 and found[0]['slug'].startswith('intended/'), 'wrong brain/limit/result')
            case(f'option order {index}', ordered)

        def delimiters():
            require(obj(['search', *normal, '--', '--', '--json']) == mcp('-- --json'), 'subsequent -- was discarded')
            require(obj(['search', *normal, 'sentinelneedle', '--', '--brain']) == mcp('sentinelneedle --brain'), 'positional+delimiter content lost')
        case('delimiter keeps all subsequent tokens', delimiters)
        for label, config_brain, environment, explicit, chosen in (
            ('default', None, {}, [], 'default'),
            ('file', 'configured', {}, [], 'configured'),
            ('environment', 'configured', {'QBRAIN_BRAIN': 'environment'}, [], 'environment'),
            ('empty environment', 'configured', {'QBRAIN_BRAIN': ''}, [], 'configured'),
            ('explicit', 'configured', {'QBRAIN_BRAIN': 'environment'}, ['--brain', 'intended'], 'intended'),
            ('option-shaped brain', 'configured', {}, ['--brain=--json'], '--json'),
        ):
            if config_brain is None:
                (data/'config.json').unlink(missing_ok=True)
            else:
                (data/'config.json').write_text(json.dumps({'brain_id': config_brain}), encoding='utf-8')
            def selected(explicit=explicit, chosen=chosen, environment=environment):
                found = obj(['search', '--query', '--brain', '--json', '--no-vector', *explicit], extra=environment)
                require(found and all(row['slug'].startswith(chosen+'/') for row in found), 'brain precedence broken')
            case('brain precedence '+label, selected)
        (data/'config.json').write_text(json.dumps({'brain_id': 'intended'}), encoding='utf-8')
        for limit, expected in (('', 2), ('0', 1), ('-1', 1), ('+1', 1), ('1', 1), ('2', 2), ('100', 3), ('101', 3), ('2147483647', 3), ('-2147483648', 1)):
            def limit_check(limit=limit, expected=expected):
                found = obj(['search', *normal, '--query=sentinelneedle', '--limit='+limit])
                require(len(found) == expected, f'limit {limit} expected {expected}, got {len(found)}')
            case('limit '+repr(limit), limit_check)
        for mode in ('', 'balanced', 'conservative', 'tokenmax'):
            def mode_check(mode=mode):
                found = obj(['search', *normal, '--query=sentinelneedle', '--mode='+mode])
                require(found == mcp('sentinelneedle', mode=mode or 'balanced'), 'mode semantics changed')
            case('mode '+repr(mode), mode_check)

        if baseline:
            ordinary = [
                ['search', 'sentinelneedle', *normal],
                ['search', 'alpha', 'beta', *normal],
                ['search', 'alpha', '--json', 'beta', '--brain', 'intended', '--no-vector'],
                ['search', '  alpha ', '', 'beta  ', *normal],
                ['search', '中文日志😀', *normal],
                ['search', 'missingword', *normal],
                ['search', 'sentinelneedle', '--brain', 'intended', '--no-vector'],
            ]
            ordinary += [['search', 'sentinelneedle', *normal, '--limit', value] for value in ('', '0', '-1', '+1', '1', '2', '101', '2147483647', '-2147483648')]
            ordinary += [['search', 'sentinelneedle', *normal, '--mode', value] for value in ('', 'balanced', 'conservative', 'tokenmax')]
            ordinary += [['search', 'sentinelneedle', *normal, flag] for flag in ('--rerank', '--rerank-llm')]
            for index, argv in enumerate(ordinary):
                def compatible(argv=argv):
                    left, right = run(argv), run(argv, executable=baseline)
                    require((left.returncode, left.stdout, left.stderr) == (right.returncode, right.stdout, right.stderr), 'ordinary raw-byte mismatch')
                case(f'baseline bytes {index}', compatible)

        case('read paths did not mutate application rows', lambda: require(snapshot() == before, 'read path mutated data'))
        case('no unexpected brain directories', lambda: require({entry.name for entry in (data/'brains').iterdir()} == set(brains), 'unexpected brain directory'))

    report = {'schema': 'qbrain-search-arguments-v1', 'platform': platform.platform(),
              'native_windows': os.name == 'nt', 'binary_sha256': sha(binary.read_bytes()),
              'baseline_sha256': sha(baseline.read_bytes()) if baseline else None,
              'script_sha256': sha(Path(__file__).read_bytes()),
              'passed': sum(item['passed'] for item in checks), 'failed': sum(not item['passed'] for item in checks),
              'command_count': len(commands), 'checks': checks, 'commands': commands,
              'limits': ['synthetic SQLite', 'no live provider/client/PostgreSQL acceptance', 'not an independent agent review']}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'SEARCH_ARGUMENTS: {report["passed"]}/{len(checks)} passed; commands={len(commands)}; failed={report["failed"]}')
    raise SystemExit(1 if report['failed'] else 0)


if __name__ == '__main__':
    main()
