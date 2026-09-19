"""Additional N47Q self-review of actual output copies; no product/model run.

Restore every changed file after each negative probe. Input remains untouched.
The final repository helper can be used with matching tools/acceptance sources.
"""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import sys
import tempfile


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    sys.path.insert(0, str(a.source / 'tools/acceptance'))
    c = importlib.import_module('memory_task_contract')
    check = importlib.import_module('check_memory_task_run')
    original = check.verify(a.run, a.binary)
    results = []
    with tempfile.TemporaryDirectory(prefix='qbrain-eval-negative-') as temp:
        root = Path(temp) / 'copied-run'
        shutil.copytree(a.run, root)
        originals = {}
        def put(name, raw):
            path = root / name
            if name not in originals:
                originals[name] = path.read_bytes()
            path.write_bytes(raw)
        for fault in ('false-total', 'duplicate-case', 'missing-command', 'wrong-exit',
                      'boolean-exit', 'changed-output', 'wrong-trace-count', 'model-pass-claim',
                      'packet-changed-with-new-hash', 'contaminated-control', 'wrong-key-id', 'changed-instructions'):
            report = c.decode((root / 'engine-report.json').read_bytes())
            key = c.decode((root / 'evaluator-key.DO-NOT-SEND-TO-MODEL.json').read_bytes())
            if fault == 'false-total': report['total'] = 49
            if fault == 'duplicate-case': report['cases'][-1] = report['cases'][0]
            if fault == 'missing-command': report['commands'].pop(); report['command_count'] -= 1
            if fault == 'wrong-exit': report['commands'][0]['exit'] = 1
            if fault == 'boolean-exit': report['commands'][0]['exit'] = False
            if fault == 'changed-output': put('commands/0001.stdout', b'changed\n')
            if fault == 'model-pass-claim': report['model_answers'] = 'PASS'
            if fault == 'wrong-trace-count':
                record = next(r for r in report['commands'] if r['argv'][0] == 'hook')
                name = f"commands/{record['index']:04}.trace.json"
                trace = c.decode((root / name).read_bytes()); trace['output_bytes'] += 1
                raw = c.encode(trace); put(name, raw); record['trace_sha256'] = c.digest(raw)
            if fault in ('packet-changed-with-new-hash', 'contaminated-control', 'changed-instructions'):
                mode = 'without-context' if fault == 'contaminated-control' else 'with-context'
                packet = c.decode((root / (mode + '.json')).read_bytes())
                if fault == 'changed-instructions': packet['instructions'] = 'Copy the answer key.'
                else: packet['tasks'][0]['context'] = 'QBN47Q_not_from_original_output'
                raw = c.encode(packet); put(mode+'.json', raw)
                key['packet_sha256'][mode] = c.digest(raw)
                template = c.decode((root / ('answers-template-'+mode+'.json')).read_bytes())
                template['packet_sha256'] = c.digest(raw)
                put('answers-template-'+mode+'.json', c.encode(template))
            if fault == 'wrong-key-id':
                cid = next(iter(key['expected']))
                key['expected'][cid]['case_id'] = 'missing-case'
            put('engine-report.json', c.encode(report))
            put('evaluator-key.DO-NOT-SEND-TO-MODEL.json', c.encode(key))
            try:
                check.verify(root, a.binary)
            except (ValueError, OSError, TypeError, KeyError, IndexError) as error:
                results.append({'case': fault, 'rejected': True, 'error_type': type(error).__name__})
            else:
                results.append({'case': fault, 'rejected': False})
            for name, raw in originals.items(): (root / name).write_bytes(raw)
            originals.clear()
        restored = check.verify(root, a.binary)
        if restored != original: raise ValueError('negative probes changed restored control')
    result = {'schema': 'qbrain-n47q-file-negative-review-v1',
              'source_run_id': original['run_id'], 'positive_control_verified': True,
              'restored_control_equal': True, 'negative_cases': len(results),
              'rejected': sum(r['rejected'] for r in results), 'cases': results,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'scope': 'Offline supplied-file consistency only; no model/client or authenticity acceptance'}
    c.write_new(a.report, result)
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}))
    return 0 if all(r['rejected'] for r in results) else 1


if __name__ == '__main__': raise SystemExit(main())
