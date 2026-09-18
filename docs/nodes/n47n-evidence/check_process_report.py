"""Read back native N47N reports against a pinned, executed local schedule.

Not a CI publisher or a replacement for executing assertions. The caller must
pin the reference report and authenticated source/artifact outside this script.
Only the temporary --file path of fixture put commands is normalized. Argument
order, flags, query bytes, input bytes and exit expectations otherwise match.
"""
from __future__ import annotations
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path


def need(ok, message):
    if not ok:
        raise ValueError(message)


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        need(key not in obj, 'duplicate JSON key')
        obj[key] = value
    return obj


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=unique_object)


def canonical(argv):
    argv = list(argv)
    if argv[:1] == ['put']:
        index = argv.index('--file') + 1
        need(argv[index].replace('\\', '/').endswith('/body.md'), 'unexpected fixture input path')
        argv[index] = '<fixture>/body.md'
    return argv


def validate(report, reference, script_bytes, native):
    sha = lambda b: hashlib.sha256(b).hexdigest()
    count = 0
    def check(ok, message):
        nonlocal count
        need(ok, message); count += 1
    check(report['schema'] == reference['schema'] == 'qbrain-search-arguments-v1', 'schema')
    check(report['native_windows'] is native, 'platform')
    check(report['baseline_sha256'] is None, 'unexpected comparison build')
    script_hashes = {sha(script_bytes), sha(script_bytes.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))}
    check(report['script_sha256'] in script_hashes, 'script source identity')
    check(report['passed'] == 226 and report['failed'] == 0 and len(report['checks']) == 226, 'check count/result')
    check(report['command_count'] == len(report['commands']) == len(reference['commands']) == 302, 'command count')
    check(report['checks'] == reference['checks'], 'case names, outcomes and command ranges')
    outputs = []
    for index, (actual, expected) in enumerate(zip(report['commands'], reference['commands'])):
        check(canonical(actual['argv']) == canonical(expected['argv']), f'argv sequence {index}')
        check(actual['stdin_base64'] == expected['stdin_base64'], f'stdin sequence {index}')
        check(actual['binary'] == 'candidate' and actual['exit'] == actual['expected_exit'] == expected['expected_exit'], f'exit {index}')
        stdout = base64.b64decode(actual['stdout_base64'], validate=True)
        stderr = base64.b64decode(actual['stderr_base64'], validate=True)
        check(sha(stdout) == actual['stdout_sha256'] and sha(stderr) == actual['stderr_sha256'], f'output bytes {index}')
        outputs.append((stdout, stderr))
    for case in report['checks']:
        start, stop = case['command_range']
        check(0 <= start <= stop <= 302 and (start < stop or case['name'] in
              ('read paths did not mutate application rows', 'no unexpected brain directories')), 'case command range')
        name = case['name']
        if name.startswith('literal/'):
            check(stop - start == 2, 'literal must run CLI and MCP')
            cli = json.loads(outputs[start][0])
            rpc = json.loads(outputs[start + 1][0])
            check(not rpc['result'].get('isError'), 'MCP literal error')
            check(cli == json.loads(rpc['result']['content'][-1]['text']), 'literal CLI/MCP evidence')
        elif name.startswith('fresh invalid '):
            check(outputs[start][0] == b'' and name.split(': ', 1)[1].encode() in outputs[start][1], 'error diagnostic')
        elif name.startswith('option order '):
            rows = json.loads(outputs[start][0])
            check(len(rows) == 1 and rows[0]['slug'].startswith('intended/'), 'ordering brain/limit')
    return {'result': 'PASS', 'readback_checks': count, 'product_checks': 226,
            'commands': 302, 'binary_sha256': report['binary_sha256'],
            'limits': ['source/artifact/run authentication is performed separately',
                       'temporary filesystem assertions are trusted executed tests, not independently observed here',
                       'comparison to executed local schedule is not independent-agent review']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--reference-sha256', required=True)
    p.add_argument('--source-script', type=Path, required=True)
    p.add_argument('--native', action='store_true')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--negative-tests', action='store_true')
    a = p.parse_args()
    need(hashlib.sha256(a.reference.read_bytes()).hexdigest() == a.reference_sha256, 'reference pin')
    reference, report = read(a.reference), read(a.report)
    script = a.source_script.read_bytes()
    result = validate(report, reference, script, a.native)
    if a.negative_tests:
        mutants = []
        def mutate(label, function):
            value = copy.deepcopy(report); function(value); mutants.append((label, value))
        mutate('drop command', lambda x: x['commands'].pop())
        mutate('duplicate command', lambda x: x['commands'].__setitem__(100, copy.deepcopy(x['commands'][101])))
        mutate('wrong argv', lambda x: x['commands'][100]['argv'].append('--rerank-llm'))
        mutate('wrong script identity', lambda x: x.__setitem__('script_sha256', '0'*64))
        mutate('wrong exit', lambda x: x['commands'][100].__setitem__('exit', 2))
        mutate('self-reported expected exit', lambda x: x['commands'][100].__setitem__('expected_exit', 2))
        mutate('wrong output digest', lambda x: x['commands'][100].__setitem__('stdout_sha256', '0'*64))
        mutate('duplicate case', lambda x: x['checks'].__setitem__(100, copy.deepcopy(x['checks'][101])))
        rejected = []
        for label, mutant in mutants:
            try:
                validate(mutant, reference, script, a.native)
            except (ValueError, KeyError, TypeError, IndexError):
                rejected.append(label)
            else:
                raise ValueError('mutation accepted: ' + label)
        result['rejected_report_mutations'] = rejected
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
