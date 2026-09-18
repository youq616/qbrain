"""Negative fixtures for the fast ledger check; does not replace native N31."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from check_ops_ledger import ContractError, INVENTORY, LEDGER, ROOT, validate


class LedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = (ROOT / LEDGER).read_text(encoding='utf-8')
        cls.inventory = (ROOT / INVENTORY).read_text(encoding='utf-8')
        cls.doc = json.loads(cls.inventory)

    def reject(self, ledger=None, doc=None):
        with self.assertRaises((ContractError, ValueError, TypeError)):
            validate(self.ledger if ledger is None else ledger,
                     self.inventory if doc is None else json.dumps(doc))

    def test_current_contract(self):
        self.assertEqual(validate(self.ledger, self.inventory)['upstream'], 104)

    def test_crlf_and_plain_status(self):
        self.assertEqual(validate(self.ledger.replace('**implemented**', 'implemented').replace('\n', '\r\n'),
                                  self.inventory)['extension'], 4)

    def test_exact_rejected_closure(self):
        rejected = ROOT / 'docs/nodes/n47n-evidence/REJECTED-LEDGER.md'
        self.reject(rejected.read_text(encoding='utf-8'))

    def test_each_missing_and_duplicated_row(self):
        names = {row['name'] for row in self.doc['ops']}
        for line in self.ledger.splitlines(keepends=True):
            cells = line.split('|')
            if len(cells) < 3 or cells[1].strip() not in names:
                continue
            with self.subTest(name=cells[1].strip(), mutation='missing'):
                self.reject(self.ledger.replace(line, '', 1))
            with self.subTest(name=cells[1].strip(), mutation='duplicate'):
                self.reject(self.ledger.replace(line, line + line, 1))

    def test_same_count_wrong_identity(self):
        self.reject(self.ledger.replace('| search |', '| wrong_search |'))

    def test_same_count_wrong_section(self):
        self.reject(self.ledger.replace('| search |', '| placeholder |')
                    .replace('| capture |', '| search |').replace('| placeholder |', '| capture |'))

    def test_incorrect_status(self):
        self.reject(self.ledger.replace('| search | **implemented**', '| search | deferred'))

    def test_heading_loss(self):
        self.reject(self.ledger.replace('| upstream_op |', '| operation |'))
        self.reject(self.ledger.replace('## Qbrain extensions', '## Archived extensions'))

    def test_repeated_heading(self):
        self.reject(self.ledger + '\n| upstream_op | status | notes |\n')

    def test_invalid_name(self):
        self.reject(self.ledger.replace('| search |', '| `search` |'))

    def test_missing_inventory_mapping(self):
        doc = copy.deepcopy(self.doc); doc['ops'][0]['tests'] = []
        self.reject(doc=doc)

    def test_duplicate_or_unsorted_inventory(self):
        doc = copy.deepcopy(self.doc); doc['ops'][1] = copy.deepcopy(doc['ops'][0])
        self.reject(doc=doc)
        doc = copy.deepcopy(self.doc); doc['ops'].reverse()
        self.reject(doc=doc)

    def test_inventory_counts_not_self_approved(self):
        for key in self.doc['counts']:
            for value in (True, self.doc['counts'][key] + 1, str(self.doc['counts'][key])):
                doc = copy.deepcopy(self.doc); doc['counts'][key] = value
                with self.subTest(key=key, value=value):
                    self.reject(doc=doc)
        doc = copy.deepcopy(self.doc); doc['frozen_registry_count'] = 112
        self.reject(doc=doc)

    def test_inventory_invalid_types(self):
        for field in ('ops', 'counts'):
            for value in (None, [], 'bad'):
                doc = copy.deepcopy(self.doc); doc[field] = value
                with self.subTest(field=field, value=value):
                    self.reject(doc=doc)
        self.reject(doc=[])

    def test_inventory_extra_diff(self):
        doc = copy.deepcopy(self.doc); doc['extensions_or_diff'] = [{'name': 'hidden'}]
        self.reject(doc=doc)

    def test_duplicate_inventory_json_keys(self):
        with self.assertRaises(ContractError):
            validate(self.ledger, self.inventory.replace('"node": "N31"', '"node": "N31", "node": "forged"'))

    def test_cli_is_read_only_and_optimized_checks_still_reject(self):
        with tempfile.TemporaryDirectory(prefix='qbrain-ledger-') as folder:
            root = Path(folder)
            for path, text in ((LEDGER, self.ledger), (INVENTORY, self.inventory)):
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                (root / path).write_text(text, encoding='utf-8')
            script = ROOT / '.ci/check_ops_ledger.py'
            for optimized in ([], ['-O']):
                before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
                p = subprocess.run([sys.executable, *optimized, str(script), '--root', str(root)], capture_output=True)
                self.assertEqual(p.returncode, 0, p.stderr)
                after = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
                self.assertEqual(before, after)
            (root / LEDGER).write_text('# replaced by archive link\n', encoding='utf-8')
            for optimized in ([], ['-O']):
                p = subprocess.run([sys.executable, *optimized, str(script), '--root', str(root)], capture_output=True)
                self.assertEqual(p.returncode, 1)
                self.assertEqual(json.loads(p.stderr)['status'], 'FAIL')
            (root / INVENTORY).unlink()
            p = subprocess.run([sys.executable, str(script), '--root', str(root)], capture_output=True)
            self.assertEqual(p.returncode, 1)


if __name__ == '__main__':
    unittest.main()
