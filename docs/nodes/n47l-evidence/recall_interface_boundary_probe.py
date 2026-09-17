"""Independent Linux CLI/MCP error and brain-selection probes; synthetic roots."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile


def isolated_env(root):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(('QBRAIN', 'OPENAI', 'ANTHROPIC'))}
    env.update(HOME=root, USERPROFILE=root, LOCALAPPDATA=root, APPDATA=root, TEMP=root, TMP=root)
    return env


def run(binary, checks):
    def check(name, ok, detail=None):
        checks.append({'name': name, 'status': 'PASS' if ok else 'FAIL', 'detail': detail})
        if not ok:
            raise AssertionError(name)

    with tempfile.TemporaryDirectory(prefix='qbrain-independent-mcp-errors-') as root:
        env = isolated_env(root)
        def invoke(args, raw=b''):
            return subprocess.run([str(binary), *args, '--brain', 'probe'], input=raw,
                                  cwd=root, env=env, capture_output=True, timeout=30)
        if invoke(['init']).returncode:
            raise RuntimeError('MCP fixture initialization failed')
        dbpath = Path(root) / '.local/share/Qbrain/brains/probe/brain.db'
        with closing(sqlite3.connect(dbpath)) as db:
            db.execute("INSERT INTO sources(id,name) VALUES('alpha','alpha')")
            db.execute("INSERT INTO config(key,value) VALUES('mcp.allowed_sources','alpha')")
            db.commit()

        def rpc_error(name, args):
            request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                       'params': {'name': name, 'arguments': args}}
            output = invoke(['serve', '--tool-profile', 'memory', '--allow-write'],
                            json.dumps(request).encode() + b'\n')
            if output.returncode:
                raise RuntimeError(output.stderr.decode(errors='replace'))
            response = json.loads(output.stdout)['result']
            if response.get('isError') is not True:
                raise AssertionError('expected a tool error')
            return json.loads(response['content'][-1]['text'])['error']

        modes = [None, True, False, 0, 1.5, [], {}, '', 'LITERAL', 'literal_substring', 'all_terms ', '\0literal']
        for i, mode in enumerate(modes):
            error = rpc_error('memory_read', {'source_id': 'alpha', 'view': 'recall', 'query': 'red', 'match': mode})
            expected = 'fact_invalid_match' if isinstance(mode, str) else 'invalid_argument'
            check('mode_type_enum_' + str(i), error['code'] == expected and
                  (expected != 'invalid_argument' or error.get('field') == 'match'),
                  {'mode': mode, 'error': error})
        for view in [None, 'memories', 'facts', 'conflicts', 'lifecycle', 'lifecycle_candidates', 'lifecycle_batch', 'unknown', '']:
            args = {'source_id': 'alpha', 'match': 'literal'}
            if view is not None:
                args['view'] = view
            error = rpc_error('memory_read', args)
            check('wrong_read_view_' + str(view), error['code'] == 'fact_unexpected_argument', error)
        for action in ['capture', 'extract', 'forget', 'fact_create', 'fact_archive', 'fact_lifecycle_batch', 'fact_promote']:
            error = rpc_error('memory_write', {'source_id': 'alpha', 'action': action, 'match': 'all_terms'})
            check('wrong_write_view_' + action,
                  error['code'] == 'invalid_argument' and error.get('field') == 'match', error)
        for mode in ['literal', 'all_terms', 'any_terms']:
            queries = [None, '', ' \t\n\r', 'a\0b', 'a ' * 9 if mode != 'literal' else 'x' * 1025,
                       'x' * 1025, '界' * 342, 'Bearer harmlessFixture']
            for i, query in enumerate(queries):
                args = {'source_id': 'alpha', 'view': 'recall', 'match': mode}
                if query is not None:
                    args['query'] = query
                error = rpc_error('memory_read', args)
                expected = 'sensitive_material_rejected' if query == 'Bearer harmlessFixture' else 'fact_invalid_query'
                check('query_rejection_' + mode + '_' + str(i), error['code'] == expected, error)

    with tempfile.TemporaryDirectory(prefix='qbrain-independent-brain-selection-') as root:
        env = isolated_env(root)
        def invoke(args, extra=None):
            return subprocess.run([str(binary), *args], cwd=root, env={**env, **(extra or {})},
                                  capture_output=True, timeout=30)
        def create(brain, source):
            result = invoke(['init', '--brain', brain])
            if result.returncode:
                raise RuntimeError(result.stderr.decode(errors='replace'))
            dbpath = Path(root) / '.local/share/Qbrain/brains' / brain / 'brain.db'
            with closing(sqlite3.connect(dbpath)) as db:
                db.execute('INSERT INTO sources(id,name) VALUES(?,?)', (source, source))
                db.commit()
        create('environment', 'env-only')
        create('configured', 'config-only')
        positives = [
            ('config_fallback', ['fact', 'recall', '--query', '--brain', '--source', 'config-only'], None, 'config-only'),
            ('environment_precedes_config', ['fact', 'recall', '--query', '--brain', '--source', 'env-only'], {'QBRAIN_BRAIN': 'environment'}, 'env-only'),
            ('explicit_precedes_environment', ['fact', 'recall', '--query', '--brain', '--source', 'config-only', '--brain', 'configured'], {'QBRAIN_BRAIN': 'environment'}, 'config-only'),
            ('empty_env_uses_config', ['fact', 'recall', '--query', '--brain', '--source', 'config-only'], {'QBRAIN_BRAIN': ''}, 'config-only'),
        ]
        for label, args, extra, source in positives:
            result = invoke(args, extra)
            check(label, result.returncode == 0 and json.loads(result.stdout)['source_id'] == source)
        negatives = [
            ('empty_brain', ['fact', 'recall', '--query', 'red', '--brain', '']),
            ('missing_match', ['fact', 'recall', '--query', 'red', '--match']),
            ('missing_query', ['fact', 'recall', '--match', 'literal']),
            ('duplicate_match', ['fact', 'recall', '--query', 'red', '--match', 'literal', '--match', 'literal']),
            ('duplicate_brain', ['fact', 'recall', '--query', 'red', '--brain', 'configured', '--brain', 'configured']),
            ('duplicate_query', ['fact', 'recall', '--query', 'red', '--query', 'blue']),
        ]
        for label, args in negatives:
            result = invoke(args)
            check(label, result.returncode != 0, {'exit_code': result.returncode,
                  'stdout': result.stdout.decode(errors='replace'), 'stderr': result.stderr.decode(errors='replace')})
        brain_root = Path(root) / '.local/share/Qbrain/brains'
        check('query_not_used_as_brain', {p.name for p in brain_root.iterdir()} == {'environment', 'configured'})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    checks = []
    report = {'result': 'FAIL', 'checks': checks, 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
              'scope': 'Independent Linux synthetic CLI/MCP boundary tests; not native Windows acceptance'}
    try:
        run(binary, checks)
        if len(checks) != 63:
            raise AssertionError('incomplete boundary probe schedule')
        report['result'] = 'PASS'
    except Exception as error:
        report.update(error_type=type(error).__name__, error=str(error))
    report['check_count'] = len(checks)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ['result', 'check_count', 'binary_sha256']}))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
