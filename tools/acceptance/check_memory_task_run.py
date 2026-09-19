"""Read back an N47Q run's exact files; does not authenticate their origin.

Requires the matching evaluation source. Ordinary LF/CRLF checkout differences
are explicitly handled for script identity, never normalized in evidence bytes.
"""
from __future__ import annotations
import argparse
import math
from pathlib import Path
import re
import sys

import memory_task_contract as c
from run_memory_tasks import parse_context

EXPECTED_COMMANDS = 520


def source_matches(raw: bytes, expected: str) -> bool:
    return expected in {c.digest(raw), c.digest(raw.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))}


def verify(directory: Path, binary: Path) -> dict:
    raw_report = c.read(directory / 'engine-report.json')
    report = c.decode(raw_report)
    c.require(isinstance(report, dict) and report.get('schema') == 'qbrain-memory-task-engine-v1', 'report_schema')
    c.require(report.get('result') == 'ENGINE_PASS' and type(report.get('total')) is int and report['total'] == 50
              and type(report.get('passed')) is int and report['passed'] == 50
              and type(report.get('failed')) is int and report['failed'] == 0, 'engine_result')
    c.require(report.get('binary_sha256') == c.digest(binary.read_bytes()), 'binary_identity')
    code = Path(__file__).parent
    prov = report.get('provenance')
    c.require(isinstance(prov, dict) and prov.get('corpus_sha256') == c.digest(c.encode(c.CASES)), 'corpus_identity')
    c.require(source_matches((code / 'run_memory_tasks.py').read_bytes(), prov.get('script_sha256'))
              and source_matches((code / 'memory_task_contract.py').read_bytes(), prov.get('contract_sha256')), 'tool_identity')
    c.require(report.get('model_answers') == 'NOT_RUN' and report.get('host_consumption') == 'NOT_RUN'
              and report.get('provider_tokens') is None and report.get('provider_cost') is None, 'unobserved_model_scope')
    rows = report.get('cases')
    c.require(isinstance(rows, list) and len(rows) == 50, 'case_coverage')
    for row, case in zip(rows, c.CASES):
        c.require(isinstance(row, dict) and row.get('case_id') == case['id'] and row.get('kind') == case['kind']
                  and row.get('passed') is True, 'case_identity_or_result')
        checks = row.get('checks')
        c.require(isinstance(checks, list) and len(checks) > 0
                  and all(x.get('passed') is True for x in checks), 'case_checks')
    commands = report.get('commands')
    c.require(isinstance(commands, list) and len(commands) == EXPECTED_COMMANDS
              and type(report.get('command_count')) is int and report['command_count'] == len(commands), 'command_coverage')
    by_case = {cid: [] for cid in c.CASE_IDS}
    for index, row in enumerate(commands, 1):
        c.require(type(row.get('index')) is int and row['index'] == index and row.get('case_id') in by_case, 'command_identity')
        c.require(type(row.get('exit')) is int and row['exit'] == 0
                  and type(row.get('expected_exit')) is int and row['expected_exit'] == 0
                  and not row.get('timed_out', False), 'command_failed')
        elapsed = row.get('elapsed_ms')
        c.require(type(elapsed) in (int, float) and 0 <= elapsed < 1e8 and math.isfinite(elapsed), 'command_duration')
        values = {}
        for name in ('stdin', 'stdout', 'stderr'):
            raw = c.read(directory / 'commands' / f'{index:04}.{name}')
            c.require(c.digest(raw) == row.get(name + '_sha256'), 'command_' + name + '_hash')
            if name != 'stdin':
                c.require(type(row.get(name + '_bytes')) is int and row[name + '_bytes'] == len(raw), 'command_byte_count')
            values[name] = raw
        c.require(values['stderr'] == b'', 'command_stderr')
        if row['argv'][:1] == ['hook']:
            trace = c.read(directory / 'commands' / f'{index:04}.trace.json')
            c.require(c.digest(trace) == row.get('trace_sha256'), 'trace_hash')
            t = c.decode(trace)
            c.require(t.get('phase') == 'complete' and t.get('host_consumption_confirmed') is False
                      and type(t.get('output_bytes')) is int and t['output_bytes'] + 1 == len(values['stdout']), 'trace_scope_or_bytes')
            values['trace'] = t
        by_case[row['case_id']].append((row, values))
    key = c.decode(c.read(directory / 'evaluator-key.DO-NOT-SEND-TO-MODEL.json'))
    c.require(key.get('run_id') == report.get('run_id'), 'run_identity')
    for mode in ('with-context', 'without-context'):
        packet_raw = c.read(directory / (mode + '.json'))
        template = c.decode(c.read(directory / ('answers-template-' + mode + '.json')))
        result = c.score(key, packet_raw, template)
        c.require(result['answered'] == 0 and result['correct'] == 0 and result['host_consumption_verified'] is False, 'template_not_empty')
        packet = c.decode(packet_raw)
        for task, case_row in zip(packet['tasks'], rows):
            records = by_case[task['case_id']]
            c.require(case_row['commands'] == [records[0][0]['index'], records[-1][0]['index']], 'case_command_range')
            c.require(records[0][0]['argv'][:2] == ['init', '--no-default'], 'fresh_brain_setup')
            final, values = records[-1]
            c.require(final['argv'][:2] == ['hook', '--config'], 'final_hook')
            event = c.decode(values['stdin'])
            prior_hooks = [x for x in records[:-1] if x[0]['argv'][:1] == ['hook']]
            c.require(bool(prior_hooks), 'missing_prior_session')
            prior_event = c.decode(prior_hooks[-1][1]['stdin'])
            c.require(event.get('hook_event_name') == 'SessionStart' and prior_event.get('hook_event_name') == 'SessionEnd'
                      and event.get('session_id') != prior_event.get('session_id'), 'independent_event_sessions')
            text, payload = parse_context(c.decode(values['stdout']))
            if mode == 'with-context':
                c.require(task['context'] == text and task['delivery_truncated'] == values['trace']['context_truncated'], 'packet_not_actual_output')
                fid_to_object = {f['fact_id']: f['object'] for g in payload['fact_groups'] for f in g['facts']}
                expected = key['expected'][task['case_id']]
                markers = set(re.findall(r'QBN47Q_[0-9a-f]{24}', '\n'.join(fid_to_object.values())))
                c.require(set(expected['fact_ids']) == set(fid_to_object) and set(expected['values']) == markers, 'key_not_actual_evidence')
    return {'schema': 'qbrain-memory-task-readback-v1', 'result': 'ENGINE_FILES_VERIFIED',
            'run_id': report['run_id'], 'engine_report_sha256': c.digest(raw_report),
            'binary_sha256': report['binary_sha256'], 'source_commit': prov['source_commit'],
            'tasks': 50, 'commands': len(commands), 'host_event_format': report['host_event_format'],
            'new_product_execution': False, 'host_consumption_verified': False,
            'evidence_authenticity_verified': False,
            'limits': ['Hashes bind local supplied files, not their trusted origin',
                       'Engine replay and packet consistency only, no real model answers']}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory', type=Path, required=True)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    try:
        result = verify(a.directory, a.binary)
        c.write_new(a.report, result)
    except (OSError, ValueError, TypeError, KeyError, IndexError):
        print('Readback REJECTED: inconsistent evidence or report not new.', file=sys.stderr)
        return 2
    print('ENGINE_FILES_VERIFIED: 50 tasks, 520 commands; model/host not certified')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
