"""Separate self-review: compare Python preflight with the exact native ledger reader.

Compiles only n31a_ledger_rows copied verbatim from the selected checkout. This
is a byte-parsing comparison, not a Windows runtime/registry acceptance test.
Uses temporary synthetic inputs. No repository or user configuration is edited.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, subprocess, tempfile
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--cxx', default='g++')
    a = p.parse_args(); root = a.root.resolve(strict=True)
    source = (root / 'tests/test_n31.cpp').read_bytes()
    text = source.decode('utf-8')
    start = text.index('std::set<std::string> n31a_ledger_rows(')
    native_function = text[start:text.index('\n}\n', start) + 3]
    spec = importlib.util.spec_from_file_location('ledger_check', root / '.ci/check_ops_ledger.py')
    checker = importlib.util.module_from_spec(spec); spec.loader.exec_module(checker)
    ledger = (root / 'docs/OPS-PARITY-LEDGER.md').read_bytes().decode('utf-8')
    inventory = (root / 'docs/nodes/n31-evidence/OPS-INVENTORY.json').read_bytes().decode('utf-8')
    expected = {k: sorted(v) for k, v in checker.inventory_names(inventory).items()}
    cases = [('canonical', ledger), ('rejected-closure', (root / 'docs/nodes/n47n-evidence/REJECTED-LEDGER.md').read_text())]
    for separator in ('\n', '\r\n', '\r', '\v', '\f', '\u0085', '\u2028', '\u2029'):
        cases.append(('separator-' + repr(separator), ledger.replace('\n', separator)))
    for prefix in (' ', '\t', '\r', '\v', '\f', '\x00', '\ufeff', '\u0085', '\u2028', '\u2029'):
        for heading in ('| upstream_op |', '## Qbrain extensions'):
            cases.append(('heading-prefix-' + repr(prefix) + heading, ledger.replace(heading, prefix + heading)))
    cases.append(('file-bom', '\ufeff' + ledger))
    cases.append(('header-bom', '\ufeff' + ledger[ledger.index('| upstream_op |'):]))
    all_names = set(expected['upstream'] + expected['extension'])
    for line in ledger.splitlines(keepends=True):
        cells = line.split('|')
        if len(cells) < 3 or cells[1].strip(' ') not in all_names: continue
        name = cells[1].strip(' ')
        cases += [('remove/' + name, ledger.replace(line, '', 1)),
                  ('duplicate/' + name, ledger.replace(line, line + line, 1)),
                  ('rename/' + name, ledger.replace(line, line.replace(name, 'wrong_' + name, 1), 1))]
    with tempfile.TemporaryDirectory(prefix='qbrain-ledger-diff-') as tmp:
        folder = Path(tmp); cpp = folder / 'reader.cpp'; binary = folder / 'reader'
        cpp.write_text('#include <set>\n#include <vector>\n#include <string>\n#include <iostream>\n#include <nlohmann/json.hpp>\n' + native_function + r'''
int main() {
  std::string line;
  while (std::getline(std::cin, line)) {
    const auto input = nlohmann::json::parse(line).get<std::string>();
    std::cout << nlohmann::json({{"upstream", n31a_ledger_rows(input, false)},
                               {"extension", n31a_ledger_rows(input, true)}}).dump() << "\n";
  }
}
''', encoding='utf-8')
        compile_result = subprocess.run([a.cxx, '-std=c++20', '-O2', '-I' + str(root / 'third_party'), str(cpp), '-o', str(binary)], capture_output=True, timeout=120)
        if compile_result.returncode:
            raise RuntimeError(compile_result.stderr.decode(errors='replace'))
        payload = ''.join(json.dumps(value, ensure_ascii=False) + '\n' for _, value in cases).encode('utf-8')
        result = subprocess.run([str(binary)], input=payload, capture_output=True, timeout=120)
        lines = result.stdout.splitlines()
        if result.returncode or len(lines) != len(cases):
            raise RuntimeError('native reader failed or missing responses')
    rows = []
    for (label, value), response in zip(cases, lines):
        native = json.loads(response)
        try: checker.validate(value, inventory); approved = True
        except (ValueError, TypeError): approved = False
        same = native == expected
        rows.append({'case': label, 'input_sha256': hashlib.sha256(value.encode()).hexdigest(),
                     'preflight_pass': approved, 'native_names_match': same,
                     'false_approval': approved and not same})
    false_approvals = sum(row['false_approval'] for row in rows)
    positive = rows[0]['preflight_pass'] and rows[0]['native_names_match']
    rejected = not rows[1]['preflight_pass'] and not rows[1]['native_names_match']
    report = {'schema': 'qbrain-n47n-ledger-differential-v1', 'cases': len(rows),
              'false_approvals': false_approvals, 'canonical_pass': positive, 'rejected_closure_fails_both': rejected,
              'stricter_rejections': sum(not x['preflight_pass'] and x['native_names_match'] for x in rows),
              'native_source_sha256': hashlib.sha256(source).hexdigest(),
              'checker_sha256': hashlib.sha256((root / '.ci/check_ops_ledger.py').read_bytes()).hexdigest(),
              'inventory_sha256': hashlib.sha256(inventory.encode()).hexdigest(),
              'ledger_sha256': hashlib.sha256(ledger.encode()).hexdigest(),
              'native_function_sha256': hashlib.sha256(native_function.encode()).hexdigest(),
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'results': rows,
              'scope': 'Linux byte-parser comparison, same coordinator self-review; not runtime or third-party certification'}
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'results'}))
    raise SystemExit(bool(false_approvals or not positive or not rejected))


if __name__ == '__main__': main()
