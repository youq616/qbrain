import unittest
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


if __name__ == '__main__':
    unittest.main()
