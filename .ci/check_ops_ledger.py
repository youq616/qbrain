"""Read-only N31 ledger/inventory preflight; native runtime checks stay authoritative."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEDGER = Path('docs/OPS-PARITY-LEDGER.md')
INVENTORY = Path('docs/nodes/n31-evidence/OPS-INVENTORY.json')
COUNTS = {'upstream': 104, 'extension': 4}
TOKEN = re.compile(r'[a-z][a-z0-9_]*\Z')


class ContractError(ValueError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ContractError(message)


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        require(key not in value, 'duplicate inventory JSON key: ' + key)
        value[key] = item
    return value


def inventory_names(text: str) -> dict[str, set[str]]:
    doc = json.loads(text, object_pairs_hook=unique_object)
    require(isinstance(doc, dict), 'inventory must be an object')
    expected = {'registry_ops': 108, 'inventory_rows': 108, 'ledger_upstream': 104,
                'ledger_extension': 4, 'extensions_or_diff': 0,
                'ops_with_tests': 108, 'ops_without_tests': 0}
    require(type(doc.get('frozen_registry_count')) is int and doc['frozen_registry_count'] == 108,
            'frozen registry count changed')
    counts = doc.get('counts')
    require(isinstance(counts, dict), 'inventory counts missing')
    for key, count in expected.items():
        require(type(counts.get(key)) is int and counts[key] == count, 'inventory count changed: ' + key)
    rows = doc.get('ops')
    require(isinstance(rows, list) and len(rows) == 108, 'inventory must have 108 rows')
    names = {key: set() for key in COUNTS}
    previous = ''
    for row in rows:
        require(isinstance(row, dict), 'inventory row must be an object')
        name = row.get('name')
        require(isinstance(name, str) and TOKEN.fullmatch(name) is not None, 'invalid inventory name')
        require(name > previous, 'inventory names must be unique and sorted: ' + name)
        previous = name
        section = row.get('ledger')
        require(isinstance(section, str) and section in names, 'invalid inventory section: ' + name)
        tests = row.get('tests')
        require(isinstance(tests, list) and bool(tests), 'inventory test mapping missing: ' + name)
        for test in tests:
            require(isinstance(test, dict) and isinstance(test.get('file'), str) and bool(test['file'])
                    and '/' not in test['file'] and '\\' not in test['file']
                    and isinstance(test.get('case'), str) and bool(test['case']), 'invalid test mapping: ' + name)
        names[section].add(name)
    for section, count in COUNTS.items():
        require(len(names[section]) == count, 'inventory section count changed: ' + section)
    require(doc.get('extensions_or_diff') == [], 'unexpected inventory diff rows')
    return names


def ledger_names(markdown: str) -> dict[str, set[str]]:
    names = {key: set() for key in COUNTS}
    headings = {key: 0 for key in COUNTS}
    section: str | None = None
    # Match the native test's canonical section boundaries. Additional duplicate
    # and id/status checks fail closed; an archive link is never a substitute.
    for line_number, line in enumerate(markdown.split('\n'), 1):
        if line.startswith('## '):
            section = None
        if line.startswith('| upstream_op |'):
            section = 'upstream'
            headings[section] += 1
        elif line.startswith('## Qbrain extensions'):
            section = 'extension'
            headings[section] += 1
        if section is None or not line.startswith('|'):
            continue
        cells = [cell.strip(' ') for cell in line.split('|')[1:-1]]
        if len(cells) < 2:
            raise ContractError(f'malformed table row at line {line_number}')
        name, status = cells[:2]
        if name in ('upstream_op', 'op') or (name and set(name) <= set('-:')):
            continue
        require(TOKEN.fullmatch(name) is not None, f'invalid ledger name at line {line_number}')
        require(status.startswith(('**implemented**', 'implemented')), 'missing implemented status: ' + name)
        require(name not in names['upstream'] and name not in names['extension'], 'duplicate ledger row: ' + name)
        names[section].add(name)
    for key in COUNTS:
        require(headings[key] == 1, 'canonical table missing or repeated: ' + key)
    return names


def validate(ledger: str, inventory: str) -> dict[str, Any]:
    expected = inventory_names(inventory)
    actual = ledger_names(ledger)
    for key in COUNTS:
        missing, extra = expected[key] - actual[key], actual[key] - expected[key]
        require(not missing and not extra, f'{key}: missing={sorted(missing)}, unexpected={sorted(extra)}')
    return {'status': 'PASS', 'upstream': 104, 'extension': 4,
            'scope': 'static N31 documentation contract; not a runtime or full-parity verdict'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        result = validate((args.root / LEDGER).read_bytes().decode('utf-8-sig'),
                          (args.root / INVENTORY).read_bytes().decode('utf-8-sig'))
    except (OSError, ValueError, TypeError) as error:
        print(json.dumps({'status': 'FAIL', 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
