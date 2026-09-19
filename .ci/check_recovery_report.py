"""N47P report identities/coverage; reports are executed tests, not filesystem snapshots."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

CASES = ('top-array version-string version-bool version-float zero-changes scalar-changes duplicate-path '
         'extra-change-field extra-root-field missing-before bad-before bad-after bad-path '
         'unowned-late-path too-many-changes late-temp-directory late-temp-junction external-late-edit '
         'oversized-unicode-image journal-envelope-cap absent-before empty-before text-before already-before '
         'absent-after empty-after large-valid-journal io-failure-remains-retryable '
         'generated-image-overflow-before-init real-interrupted-large-install').split()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def validate(value, installer, binary, baseline=False):
    require(value['schema'] == 'qbrain-n47p-recovery-v1', 'schema')
    require(value['installer_sha256'].lower() == hashlib.sha256(installer).hexdigest(), 'installer identity')
    require(value['binary_sha256'].lower() == hashlib.sha256(binary).hexdigest(), 'executable identity')
    rows = value['cases']
    expected = [h+'/'+c for h in ('Claude', 'Codex') for c in CASES]
    require(Counter(r['name'] for r in rows) == Counter(expected), 'missing/duplicate/unexpected cases')
    require(all(type(r['passed']) is bool for r in rows), 'case types')
    failed = sum(not r['passed'] for r in rows)
    require(type(value['failed']) is int and type(value['passed']) is int and value['failed'] == failed
            and value['passed'] == len(rows)-failed, 'untrusted counts')
    require(value['live_client_tested'] is False, 'scope')
    mapping = {r['name']: r['passed'] for r in rows}
    if baseline:
        for host in ('Claude', 'Codex'):
            for name in ('large-valid-journal', 'real-interrupted-large-install', 'late-temp-directory'):
                require(not mapping[host+'/'+name], 'baseline did not demonstrate '+name)
            for name in ('text-before', 'absent-before', 'empty-before', 'external-late-edit', 'io-failure-remains-retryable'):
                require(mapping[host+'/'+name], 'baseline fixture/control failed '+name)
    else:
        require(failed == 0, 'candidate failed cases')
    return {'verified': True, 'cases': len(rows), 'passed': len(rows)-failed, 'failed': failed,
            'baseline_expected_rejection': baseline, 'powershell': value['powershell']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--installer', type=Path, required=True)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--baseline', action='store_true')
    a = parser.parse_args()
    print(json.dumps(validate(json.loads(a.report.read_text(encoding='utf-8-sig')), a.installer.read_bytes(),
                              a.binary.read_bytes(), a.baseline)))


if __name__ == '__main__':
    main()
