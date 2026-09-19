"""Check fixed-source Windows snapshot-test evidence; not a new product execution."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

KINDS = ('target-existing target-absent mcp-existing mcp-absent owner-existing owner-absent '
         'config-existing config-absent bridge-existing bridge-absent normal-existing normal-absent').split()


def need(ok, message):
    if not ok:
        raise ValueError(message)


def decode(raw):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            need(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique)


def validate(value, installer, test, binary, source, shell, baseline=False):
    need(value.get('schema') == 'qbrain-n47p-input-snapshot-v1', 'schema')
    need(value.get('source_commit') == source and len(source) == 40, 'source identity')
    need(value.get('native_windows') is True and type(value.get('shell_major')) is int
         and value['shell_major'] == shell and shell in (5, 7), 'native shell')
    need(value.get('real_client_tested') is False, 'scope')
    for field, raw in (('installer_sha256', installer), ('test_sha256', test), ('binary_sha256', binary)):
        need(value.get(field) == hashlib.sha256(raw).hexdigest(), field)
    rows = value.get('cases')
    need(isinstance(rows, list) and all(isinstance(r, dict) for r in rows), 'case array')
    expected = [h+'/'+k for h in ('Claude', 'Codex') for k in KINDS]
    need(Counter(r.get('name') for r in rows) == Counter(expected), 'case coverage')
    need(all(type(r.get('passed')) is bool for r in rows), 'case types')
    failed = sum(not r['passed'] for r in rows)
    need(type(value.get('passed')) is int and type(value.get('failed')) is int
         and value['failed'] == failed and value['passed'] == len(rows)-failed, 'counts')
    for row in rows:
        target = (not baseline) or row['name'].split('/')[1].startswith('normal-')
        need(row['passed'] is target, 'unexpected result: '+row['name'])
    return {'verified': True, 'source_commit': source, 'shell_major': shell,
            'passed': len(rows)-failed, 'failed': failed, 'expected_baseline_rejection': baseline}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('report', 'installer', 'test', 'binary'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--source', required=True)
    p.add_argument('--shell', type=int, choices=(5, 7), required=True)
    p.add_argument('--baseline', action='store_true')
    a = p.parse_args()
    print(json.dumps(validate(decode(a.report.read_bytes()), a.installer.read_bytes(), a.test.read_bytes(),
                              a.binary.read_bytes(), a.source, a.shell, a.baseline)))


if __name__ == '__main__':
    main()
