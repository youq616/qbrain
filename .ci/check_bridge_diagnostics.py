"""Strict diagnostic metadata/report consistency, not origin authentication."""
import argparse
import hashlib
import json
from pathlib import Path
import re

NAMES = ('default success result has exactly the original three fields', 'nonzero child exit and exact Unicode streams remain successful transport', 'default success matches the exact prior bridge result', 'opt-in diagnostics do not change child output', 'success diagnostic has versioned completed identity', 'success diagnostic preserves default timeout and observed exit', 'success diagnostic reports completed streams', 'all waits consume one decreasing elapsed budget', 'invalid executable does not report success', 'startup failure is distinct from process timeout', 'unstarted process observations remain null and not started', 'startup failure is normalized without native path text', 'blocked input has the original input timeout message', 'blocked input reports actual pre-cleanup input state', 'blocked input does not receive a fresh timeout budget', 'input timeout cleanup terminates the direct test child', 'live child has the original process timeout message', 'process timeout distinguishes finished input from live child', 'process timeout cleanup terminates the direct test child', 'inherited pipe holder has the original output timeout message', 'output timeout distinguishes an exited parent from open streams', 'output fixture records its separately cleaned descendant', 'invalid UTF-8 remains an error not replacement text', 'stream decoder failure is visible without reading fault text', 'a later invocation succeeds after all failure paths', 'bridge source parses in this actual PowerShell version', 'elapsed-budget helper clamps expired and large elapsed values', 'all shareable diagnostics exclude input path argument and output sentinels', 'diagnostics are observations not proof of host consumption')
CODES = ('completed', 'start_failed', 'input_timeout', 'process_timeout', 'output_timeout', 'transport_error')
FIELDS = {'schema','code','phase','timeout_ms','elapsed_ms','stage_ms','wait_budget_ms',
          'process_started','input_closed','process_exited','exit_code','input_state',
          'stdout_state','stderr_state','observation','host_consumption_verified'}


def need(ok, code):
    if not ok: raise ValueError(code)


def digest(raw): return hashlib.sha256(raw).hexdigest()


def decode(raw):
    need(len(raw) <= 262144, 'report_byte_limit')
    def unique(pairs):
        out = {}
        for key,value in pairs:
            need(key not in out, 'duplicate_json_key'); out[key] = value
        return out
    def invalid(_): raise ValueError('nonfinite_json')
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique, parse_constant=invalid)


def diagnostic(d):
    need(isinstance(d,dict) and set(d) == FIELDS, 'diagnostic_fields')
    need(d['schema'] == 'qbrain-transport-diagnostic-v1' and d['code'] in CODES, 'diagnostic_identity')
    expected = {'completed':'complete','start_failed':'start','input_timeout':'input',
                'process_timeout':'process','output_timeout':'output'}
    need(d['phase'] in ('start','input','process','output','complete'), 'phase')
    if d['code'] in expected: need(d['phase'] == expected[d['code']], 'code_phase')
    need(type(d['timeout_ms']) is int and 100 <= d['timeout_ms'] <= 120000, 'timeout')
    need(type(d['elapsed_ms']) is int and 0 <= d['elapsed_ms'] <= 86400000, 'elapsed')
    need(d['observation'] == 'before_cleanup' and d['host_consumption_verified'] is False, 'scope')
    for key in ('process_started','input_closed'): need(type(d[key]) is bool, 'boolean')
    need(d['process_exited'] is None or type(d['process_exited']) is bool, 'exit_observation')
    need(d['exit_code'] is None or (type(d['exit_code']) is int and -(2**31) <= d['exit_code'] < 2**31), 'exit_code')
    for key in ('input_state','stdout_state','stderr_state'):
        need(d[key] in ('not_started','running','completed','faulted','canceled'), 'task_state')
    for key, stages in (('stage_ms',('start','input','process','output')),('wait_budget_ms',('input','process','output'))):
        values = d[key]
        need(isinstance(values,dict) and set(values) == set(stages), 'stage_fields')
        cap = d['elapsed_ms'] if key == 'stage_ms' else d['timeout_ms']
        need(all(x is None or (type(x) is int and 0 <= x <= cap) for x in values.values()), 'stage_value')
    used = [x for x in d['wait_budget_ms'].values() if x is not None]
    # JSON object order is not a trusted semantic ordering.
    used = [d['wait_budget_ms'][k] for k in ('input','process','output') if d['wait_budget_ms'][k] is not None]
    need(used == sorted(used,reverse=True), 'budget_reset')
    if d['wait_budget_ms']['input'] is not None:
        need(d['stage_ms']['start'] is not None and d['wait_budget_ms']['input'] <= max(0,d['timeout_ms']-d['stage_ms']['start']), 'startup_budget_not_consumed')
    if not d['process_started']:
        need(d['process_exited'] is None and d['exit_code'] is None and not d['input_closed'], 'unstarted_observation')
    if d['code'] == 'completed':
        need(d['process_started'] and d['input_closed'] and d['process_exited'] is True and d['exit_code'] == 7, 'success_observation')
        need(all(d[k] == 'completed' for k in ('input_state','stdout_state','stderr_state')), 'success_tasks')
    if d['code'] == 'output_timeout': need(d['process_exited'] is True and d['exit_code'] == 0, 'output_parent')
    need(len(json.dumps(d).encode()) <= 2048, 'diagnostic_byte_limit')


def validate(r, bridge, prior, test, child, source, shell):
    need(isinstance(r,dict) and set(r) == {'schema','result','source_commit','shell_major','bridge_sha256',
        'prior_bridge_sha256','test_sha256','child_sha256','checks','diagnostics','failure','real_client_verified'}, 'report_fields')
    need(r['schema'] == 'qbrain-n47w-bridge-test-v1' and r['result'] == 'PASS' and r['failure'] == '', 'result')
    need(r['source_commit'] == source and re.fullmatch('[0-9a-f]{40}',source), 'source')
    need(type(r['shell_major']) is int and r['shell_major'] == shell and shell in (5,7), 'shell')
    need(r['real_client_verified'] is False, 'real_client')
    for name, raw in (('bridge',bridge),('prior_bridge',prior),('test',test),('child',child)):
        need(r[name+'_sha256'] == digest(raw), 'component_bytes')
    rows = r['checks']
    need(isinstance(rows,list) and len(rows) == len(NAMES), 'coverage')
    need(all(isinstance(row,dict) and set(row) == {'name','passed'} for row in rows), 'check_shape')
    need(tuple(row['name'] for row in rows) == NAMES and all(row['passed'] is True for row in rows), 'check_results')
    values = r['diagnostics']
    need(isinstance(values,list) and len(values) == len(CODES), 'observations')
    for d in values: diagnostic(d)
    need(tuple(d['code'] for d in values) == CODES, 'observation_order')
    return {'result':'BRIDGE_DIAGNOSTICS_VERIFIED','source_commit':source,'shell_major':shell,
            'checks':len(NAMES),'observations':len(values),'bridge_sha256':digest(bridge),
            'new_windows_execution':False,'real_client_verified':False}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('report','bridge','prior','test','child'): p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--source',required=True);p.add_argument('--shell',type=int,required=True)
    a=p.parse_args()
    print(json.dumps(validate(decode(a.report.read_bytes()),a.bridge.read_bytes(),a.prior.read_bytes(),
        a.test.read_bytes(),a.child.read_bytes(),a.source,a.shell)))
