"""Validate exact native case-path evidence, not an independent Windows run."""
import argparse
import hashlib
import json
from pathlib import Path


def names():
    rows = []
    def reject(name):
        rows.extend([name+' rejected explicitly', name+' preserves all fixture bytes and directories'])
    for host in ('Claude', 'Codex'):
        rows += [host+' actual distinct case-only project directories', host+' old identity algorithm collides',
                 host+' old Status incorrectly reports sibling installed']
        for project in ('Project', 'project'):
            for action in ('Status', 'Install', 'Uninstall'): reject(host+'/'+project+'/'+action)
        rows += [host+' guard never changes case flags']
        for scope in ('self', 'config'):
            for action in ('Install', 'Uninstall', 'Status'): reject(host+'/'+scope+'/'+action)
        reject(host+'/pending-recovery')
        rows += [host+' ordinary legacy ID unchanged', host+' ordinary case alias still resolves installation',
                 host+' ordinary default consent stays off', host+' ordinary reinstall and uninstall succeed']
    reject('sensitive binary parent before owned creation')
    for action in ('Install', 'Uninstall', 'Status'): reject('sensitive appdata/'+action)
    reject('no stale directory flag cache')
    rows += ['metadata-only query works with deny-sharing handle',
             'metadata-only shared query preserves fixture bytes and directories',
             'directory disappearance occurred at the intended metadata boundary',
             'missing metadata handle rejected explicitly',
             'metadata disappearance preserves application state after fixture restoration',
             'metadata query works after external directory restoration']
    return rows


def need(ok, why):
    if not ok: raise ValueError(why)


def decode(raw):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            need(k not in result, 'duplicate key'); result[k] = v
        return result
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique)


def sha(raw): return hashlib.sha256(raw).hexdigest()


def validate(report, installer, prior, script, binary, source, shell, log):
    need(isinstance(report, dict) and report.get('schema') == 'qbrain-n47v-case-paths-v1', 'schema')
    need(report.get('source_commit') == source and len(source) == 40, 'source')
    need(report.get('result') == 'PASS' and report.get('native_windows') is True and
         type(report.get('shell_major')) is int and report['shell_major'] == shell and shell in (5, 7) and
         report.get('real_client_verified') is False, 'result/scope')
    for key, raw in (('installer_sha256', installer), ('baseline_installer_sha256', prior),
                     ('script_sha256', script), ('binary_sha256', binary)):
        need(report.get(key) == sha(raw), 'identity: '+key)
    checks = report.get('checks')
    need(isinstance(checks, list) and len(checks) == len(names()) and all(isinstance(x, dict) for x in checks), 'coverage')
    need([x.get('name') for x in checks] == names() and all(x.get('passed') is True for x in checks), 'checks')
    flags = report.get('flags')
    expected = [1, 0, 0, 1, 1]*2 + [1, 1, 1]
    need(isinstance(flags, list) and len(flags) == len(expected), 'flag coverage')
    need(all(isinstance(x, dict) and type(x.get('flags')) is int and x['flags'] == flag and
             isinstance(x.get('path'), str) and bool(x['path']) and isinstance(x.get('fsutil_output'), str)
             for x, flag in zip(flags, expected)), 'actual flag states')
    lines = log.decode('utf-8-sig').splitlines()
    need([line for line in lines if line.startswith('PASS ')] ==
         ['PASS '+str(i)+' : '+name for i, name in enumerate(names(), 1)], 'log checks')
    return {'result': 'NATIVE_CASE_PATHS_VERIFIED', 'source_commit': source, 'shell_major': shell,
            'checks': len(checks), 'flag_observations': len(flags), 'installer_sha256': sha(installer),
            'binary_sha256': sha(binary), 'new_windows_execution': False, 'real_client_verified': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('report', 'installer', 'prior', 'test', 'binary', 'log'): p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--source', required=True); p.add_argument('--shell', type=int, choices=(5, 7), required=True)
    a = p.parse_args()
    print(json.dumps(validate(decode(a.report.read_bytes()), a.installer.read_bytes(), a.prior.read_bytes(),
                              a.test.read_bytes(), a.binary.read_bytes(), a.source, a.shell, a.log.read_bytes())))
