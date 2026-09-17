"""Independent interface differential probes, outside the reviewed repository."""
from contextlib import closing
from pathlib import Path
import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    a.baseline = a.baseline.resolve(strict=True)
    a.candidate = a.candidate.resolve(strict=True)
    results = []

    def check(name, ok, detail=None):
        results.append({'name': name, 'status': 'PASS' if ok else 'FAIL', 'detail': detail})

    with tempfile.TemporaryDirectory(prefix='qbrain-independent-literal-') as temp:
        root = Path(temp)
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(('QBRAIN', 'OPENAI', 'ANTHROPIC'))}
        env.update(HOME=temp, USERPROFILE=temp, LOCALAPPDATA=temp, APPDATA=temp, TEMP=temp, TMP=temp)

        def invoke(binary, args, raw=b''):
            return subprocess.run([str(binary), *args, '--brain', 'probe'], input=raw,
                                  cwd=root, env=env, capture_output=True, timeout=30)

        def cli(args, payload=None):
            raw = b'' if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
            r = invoke(a.baseline, args, raw)
            if r.returncode:
                raise RuntimeError((args, r.stdout, r.stderr))
            return json.loads(r.stdout)

        init = invoke(a.baseline, ['init'])
        if init.returncode:
            raise RuntimeError(init.stderr)
        dbpath = root / '.local/share/Qbrain/brains/probe/brain.db'
        with closing(sqlite3.connect(dbpath)) as db:
            db.execute("INSERT INTO sources(id,name) VALUES('alpha','alpha')")
            db.execute("INSERT INTO config(key,value) VALUES('memory.writeback','salient'),('mcp.allowed_sources','alpha')")
            db.commit()

        def sql(statement, args=()):
            with closing(sqlite3.connect(dbpath)) as db:
                values = db.execute(statement, args).fetchall()
                db.commit()
            return values

        seeds = []
        for tag, quote in [
            ('both', 'I prefer red then blue; 命令行 😀 ÉCOLE, not a GUI.'),
            ('counter', 'I prefer a graphical interface.'),
            ('flags', 'I prefer literal --match --source --brain --query --history --predicate --limit --id --event.'),
            ('sql', "I prefer 100% a_b ' OR 1=1 -- path\\name."),
        ]:
            event = cli(['memory', 'capture', '--manual', '--source', 'alpha'],
                        {'session_id': 'independent-review', 'fragment_id': tag,
                         'messages': [{'role': 'user', 'content': quote}]})['event_id']
            cli(['memory', 'extract', '--source', 'alpha', '--event', event])
            item = sql('SELECT item_id FROM memory_items WHERE event_id=?', (event,))[0][0]
            fact = cli(['fact', 'create', '--source', 'alpha'],
                       {'item_id': item, 'predicate': 'preference.editor'})['fact_id']
            seeds.append(fact)
        cli(['fact', 'contradict', '--source', 'alpha'], {'fact_id': seeds[0], 'other_id': seeds[1]})
        cli(['fact', 'archive', '--source', 'alpha'], {'fact_id': seeds[1], 'expected_revision': 2})
        sql('UPDATE memory_facts SET created_at=123456')

        queries = ['red', 'red blue', 'red then blue', 'red then', 'RED THEN', ' blue;', 'blue;',
                   '命令行', '😀', 'ÉCOLE', 'école', 'not a GUI', '100%', 'a_b', "' OR 1=1", '--',
                   'path\\name', 'absent', ' red', 'red ', 'red\tblue', 'red\u00a0blue', '--match']
        errors = ['', ' \t\r\n', 'x' * 1025, '界' * 342, 'Bearer harmlessFixture', 'api key = harmlessFixture']
        for query in queries + errors:
            baseargs = ['fact', 'recall', '--query', query, '--source', 'alpha', '--limit', '50', '--max-bytes', '32768']
            legacy = invoke(a.baseline, baseargs)
            for label, addition in [('default', []), ('literal', ['--match', 'literal'])]:
                current = invoke(a.candidate, [*baseargs, *addition])
                check('baseline_stdout_bytes_' + label,
                      (legacy.returncode, legacy.stdout) == (current.returncode, current.stdout),
                      {'query': query[:80], 'query_bytes': len(query.encode('utf-8')),
                       'old_exit': legacy.returncode, 'new_exit': current.returncode,
                       'old_sha256': hashlib.sha256(legacy.stdout).hexdigest(),
                       'new_sha256': hashlib.sha256(current.stdout).hexdigest()})

        def rpc(binary, args):
            req = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                   'params': {'name': 'memory_read', 'arguments': args}}
            r = invoke(binary, ['serve', '--tool-profile', 'memory'],
                       json.dumps(req, ensure_ascii=False).encode('utf-8') + b'\n')
            if r.returncode:
                raise RuntimeError(r.stderr)
            return r.stdout

        for query in queries + errors:
            args = {'source_id': 'alpha', 'view': 'recall', 'query': query, 'limit': 50, 'max_bytes': 32768}
            legacy = rpc(a.baseline, args)
            for label, mode in [('default', {}), ('literal', {'match': 'literal'})]:
                current = rpc(a.candidate, {**args, **mode})
                check('baseline_rpc_stdout_bytes_' + label, legacy == current,
                      {'query': query[:80], 'query_bytes': len(query.encode('utf-8'))})

        for query in ['--match', '--source', '--brain', '--query', '--history', '--predicate', '--limit', '--id', '--event']:
            for mode in ['literal', 'all_terms', 'any_terms']:
                request = {'source_id': 'alpha', 'view': 'recall', 'query': query, 'match': mode,
                           'limit': 50, 'max_bytes': 32768}
                expected = json.loads(rpc(a.candidate, request))['result']['content'][0]['text'].encode() + b'\n'
                for reverse in [False, True]:
                    before = ['--source', 'alpha', '--limit', '50', '--max-bytes', '32768', '--match', mode]
                    query_arg = ['--query', query]
                    args = ['fact', 'recall', *(before + query_arg if reverse else query_arg + before)]
                    observed = invoke(a.candidate, args)
                    check('option_shaped_query_cli_rpc_bytes', observed.returncode == 0 and observed.stdout == expected,
                          {'query': query, 'mode': mode, 'options_before_query': reverse,
                           'exit': observed.returncode, 'response': observed.stdout.decode('utf-8', errors='replace')[:120]})

    report = {'result': 'PASS' if all(r['status'] == 'PASS' for r in results) else 'FAIL',
              'baseline': str(a.baseline), 'baseline_sha256': hashlib.sha256(a.baseline.read_bytes()).hexdigest(),
              'candidate': str(a.candidate), 'candidate_sha256': hashlib.sha256(a.candidate.read_bytes()).hexdigest(),
              'scope': 'Independent Linux CLI/MCP read-only interface probes; no native Windows claim',
              'check_count': len(results), 'fail_count': sum(r['status'] != 'PASS' for r in results), 'checks': results}
    a.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('result', 'check_count', 'fail_count')}))
    for row in results:
        if row['status'] != 'PASS':
            print(json.dumps(row, ensure_ascii=False))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
