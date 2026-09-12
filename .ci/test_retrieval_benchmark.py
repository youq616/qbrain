"""Run the real C++ selector/SQLite tests and label synthetic timing honestly."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile

p = argparse.ArgumentParser()
p.add_argument('--binary', required=True, type=Path)
p.add_argument('--report', required=True, type=Path)
p.add_argument('--require-windows', action='store_true')
a = p.parse_args()
if a.require_windows and os.name != 'nt':
    raise SystemExit('Windows acceptance cannot be substituted with a portable run')
binary = a.binary.resolve()
env = {k: v for k, v in os.environ.items() if not k.upper().startswith(('QBRAIN', 'OPENAI', 'ANTHROPIC'))}
unit = subprocess.run([str(binary)], env=env, capture_output=True, text=True, encoding='utf-8', timeout=90)
print(unit.stdout, end='')
if unit.returncode:
    raise SystemExit(unit.stderr or 'Native retrieval tests failed')
match = re.search(r'^N46C exact retrieval: (\d+) checks passed$', unit.stdout, re.MULTILINE)
assert match and int(match[1]) > 100000, 'Missing complete differential/retention checks'
with tempfile.TemporaryDirectory(prefix='qbrain-retrieval-bench-') as t:
    raw = Path(t) / 'report.json'
    subprocess.run([str(binary), '--benchmark', str(raw)], env=env, check=True, timeout=90)
    report = json.loads(raw.read_text(encoding='utf-8'))
assert report['result'] == 'PASS' and report['results_equal'] is True
assert report['hybrid_results_equal'] is True
assert report['baseline_backlink_queries'] == report['backlink_candidates']
assert report['optimized_backlink_queries'] == (report['backlink_candidates'] + 99) // 100
assert report['chunks'] == report['chunks_scanned'] == 16000
assert report['limit'] == 50 and 0 < report['peak_retained_pages'] <= 50
assert len(report['baseline_samples_ms']) == len(report['optimized_samples_ms']) == 7
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
clean = subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--']).returncode == 0
report.update(source_commit=head if clean else None, head_commit=head, tracked_tree_clean=clean,
              source_tree=subprocess.check_output(['git', 'write-tree'], text=True).strip(),
              native_windows=os.name == 'nt', platform=platform.platform(),
              native_test_checks=int(match[1]), probe_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
a.report.parent.mkdir(parents=True, exist_ok=True)
a.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: report[k] for k in ('result', 'chunks_scanned', 'peak_retained_pages',
                                      'baseline_median_ms', 'optimized_median_ms', 'native_windows')}))
