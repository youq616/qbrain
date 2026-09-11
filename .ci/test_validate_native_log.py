import unittest
from pathlib import Path
import re
from validate_native_log import verified_groups


class NativeEvidenceTests(unittest.TestCase):
    registry = '{"one", test_one}, {"two", test_two}'

    def test_exact_groups_and_verbose_nested_assertions(self):
        log = '[PASS] legacy RRF\r\n[PASS] Chinese and emoji boundaries\r\n[PASS] one\r\n[PASS] two\r\n'
        self.assertEqual(verified_groups(self.registry, log, 2), ['one', 'two'])

    def test_missing_group(self):
        with self.assertRaises(ValueError):
            verified_groups(self.registry, '[PASS] one\n', 2)

    def test_repeated_group(self):
        with self.assertRaises(ValueError):
            verified_groups(self.registry, '[PASS] one\n[PASS] two\n[PASS] one\n', 2)

    def test_failure_even_with_all_success_lines(self):
        with self.assertRaises(ValueError):
            verified_groups(self.registry, '[PASS] one\n[PASS] two\n[FAIL] assertion\n', 2)

    def test_registry_change_requires_explicit_gate_update(self):
        with self.assertRaises(ValueError):
            verified_groups(self.registry, '[PASS] one\n[PASS] two\n', 3)


    def test_n46b_exact_registry(self):
        source = (Path(__file__).resolve().parents[1] / 'tests/test_main.cpp').read_text(encoding='utf-8')
        names = re.findall(r'\{"([^"\r\n]+)",\s*test_\w+\}', source)
        self.assertEqual(len(names), 45)
        self.assertIn('n46b_http', names)
        log = ''.join('[PASS] ' + name + '\n' for name in names)
        self.assertEqual(verified_groups(source, log, 45), names)
        with self.assertRaises(ValueError):
            verified_groups(source, log)  # Old default of 44 must not certify 45.

    def test_n46b_cannot_reuse_old_log(self):
        source = (Path(__file__).resolve().parents[1] / 'tests/test_main.cpp').read_text(encoding='utf-8')
        names = re.findall(r'\{"([^"\r\n]+)",\s*test_\w+\}', source)
        log = ''.join('[PASS] ' + name + '\n' for name in names if name != 'n46b_http')
        with self.assertRaises(ValueError):
            verified_groups(source, log, 45)


if __name__ == '__main__':
    unittest.main()
