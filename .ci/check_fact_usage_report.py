"""N47T report content/byte-identity gate, not independent execution proof."""
import argparse
import hashlib
import json
from pathlib import Path
import re

NAMES_SHA = '1c95e30c746c3f5279bb256bca365ce6dd8d7f7c7e5ef15a88213f7bfaf0a6e9'


def need(value, error):
    if not value: raise ValueError(error)


def digest(raw): return hashlib.sha256(raw).hexdigest()


def decode(raw):
    def unique(pairs):
        value = {}
        for k,v in pairs:
            need(k not in value, 'duplicate_json_key'); value[k] = v
        return value
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique)


def validate(report, binary, script):
    need(isinstance(report, dict) and report.get('schema') == 'qbrain-n47t-process-v1', 'schema')
    need(type(report.get('passed')) is int and report['passed'] == 75 and
         type(report.get('failed')) is int and report['failed'] == 0, 'result')
    need(report.get('real_client_tested') is False and type(report.get('provider_calls')) is int
         and report['provider_calls'] == 0, 'scope')
    need(report.get('binary_sha256') == digest(binary) and report.get('test_sha256') == digest(script), 'bytes')
    rows = report.get('checks')
    need(isinstance(rows, list) and len(rows) == 75 and all(isinstance(x,dict) and x.get('passed') is True for x in rows), 'checks')
    names = json.dumps([r.get('name') for r in rows], ensure_ascii=False, separators=(',', ':')).encode()
    need(digest(names) == NAMES_SHA, 'exact_check_coverage')
    commands = report.get('commands')
    need(isinstance(commands,list) and len(commands) == 118 and type(report.get('command_count')) is int
         and report['command_count'] == 118, 'command_coverage')
    for cmd in commands:
        need(isinstance(cmd, dict) and isinstance(cmd.get('argv'),list) and bool(cmd['argv'])
             and all(isinstance(a,str) for a in cmd['argv']) and isinstance(cmd.get('brain'),str), 'argv')
        need(type(cmd.get('exit')) is int and type(cmd.get('expected_exit')) is int
             and cmd['exit'] == cmd['expected_exit'] and cmd['exit'] in (0,1,2), 'command_exit')
        for field in ('stdin_sha256','stdout_sha256','stderr_sha256'):
            need(isinstance(cmd.get(field),str) and re.fullmatch('[0-9a-f]{64}',cmd[field]), 'stream_digest')
    return {'result':'FACT_USAGE_REPORT_VERIFIED','checks':75,'commands':118,
            'binary_sha256':digest(binary),'test_sha256':digest(script),
            'new_product_execution':False,'real_client_tested':False}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('report','binary','test'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(validate(decode(a.report.read_bytes()),a.binary.read_bytes(),a.test.read_bytes())))
