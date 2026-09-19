"""Actual Qbrain -> packet -> HTTP executor -> scorer, with a LOOPBACK FIXTURE.

Deliberately NOT a real provider/model evaluation. CI needs no key or account.
"""
import argparse
from pathlib import Path
import subprocess
import sys

import memory_task_contract as c
import run_memory_tasks
import check_memory_task_run
import model_ab
from test_model_ab import server


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); binary = a.binary.resolve(strict=True)
    a.output.mkdir(parents=True, exist_ok=False)
    packets = a.output / 'engine'
    engine = run_memory_tasks.run(binary, packets, 'claude')
    c.require(engine['result'] == 'ENGINE_PASS', 'engine_failed')
    checked = check_memory_task_run.verify(packets, binary)
    c.write_new(a.output / 'engine-readback.json', checked)
    with server() as (url, calls):
        plan = model_ab.prepare(packets, url, 'loopback-fixture-not-a-model', test=True)
        raw = c.encode(plan); path = a.output / 'plan.json'; path.write_bytes(raw)
        # The child execution process has only a plan. No key filename/answers.
        result = subprocess.run([sys.executable, str(Path(model_ab.__file__)), 'execute', '--plan', str(path),
                  '--approve-sha256', c.digest(raw), '--approve-endpoint', url, '--approve-requests', '100',
                  '--output', str(a.output / 'http-run')], capture_output=True, timeout=120)
        (a.output / 'execute.stdout').write_bytes(result.stdout)
        (a.output / 'execute.stderr').write_bytes(result.stderr)
        c.require(result.returncode == 0 and len(calls) == 100, 'transport_execution_failed')
    comparison = model_ab.score_run(a.output / 'http-run', packets / 'evaluator-key.DO-NOT-SEND-TO-MODEL.json')
    c.require(comparison['execution_kind'] == 'LOOPBACK_TEST' and comparison['complete_pair'], 'fixture_scope')
    c.write_new(a.output / 'comparison.json', comparison)
    receipt = {'schema': 'qbrain-n47s-loopback-pipeline-v1', 'result': 'PASS',
               'engine_tasks': 50, 'engine_commands': engine['command_count'], 'http_requests': len(calls),
               'source_commit': engine['provenance']['source_commit'], 'binary_sha256': engine['binary_sha256'],
               'plan_sha256': c.digest(raw), 'comparison_sha256': c.digest(c.encode(comparison)),
               'execution_kind': 'LOOPBACK_TEST', 'real_model_answers': 'NOT_RUN',
               'real_client_consumption': 'NOT_RUN', 'provider_cost_usd': None}
    c.write_new(a.output / 'pipeline.json', receipt)
    print(c.encode(receipt).decode())


if __name__ == '__main__': main()
