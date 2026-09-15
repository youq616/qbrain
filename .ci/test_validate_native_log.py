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
        self.assertEqual(len(names), 53)
        self.assertIn('n46b_http', names)
        self.assertIn('n46c_retrieval', names)
        self.assertIn('n46d_embedding', names)
        self.assertIn('n46f_cjk', names)
        self.assertIn('n47a_facts', names)
        self.assertIn('n47b_conflicts', names)
        log = ''.join('[PASS] ' + name + '\n' for name in names)
        self.assertEqual(verified_groups(source, log, 53), names)
        with self.assertRaises(ValueError):
            verified_groups(source, log)  # Old default of 44 must not certify 53.

    def test_n46b_cannot_reuse_old_log(self):
        source = (Path(__file__).resolve().parents[1] / 'tests/test_main.cpp').read_text(encoding='utf-8')
        names = re.findall(r'\{"([^"\r\n]+)",\s*test_\w+\}', source)
        log = ''.join('[PASS] ' + name + '\n' for name in names if name != 'n46b_http')
        with self.assertRaises(ValueError):
            verified_groups(source, log, 53)

    def test_n46c_cannot_reuse_45_group_log(self):
        source = (Path(__file__).resolve().parents[1] / 'tests/test_main.cpp').read_text(encoding='utf-8')
        names = re.findall(r'\{"([^"\r\n]+)",\s*test_\w+\}', source)
        log = ''.join('[PASS] ' + name + '\n' for name in names if name != 'n46c_retrieval')
        with self.assertRaises(ValueError):
            verified_groups(source, log, 53)
        with self.assertRaises(ValueError):
            verified_groups(source, log, 45)

    def test_n46d_cannot_reuse_46_group_log(self):
        source = (Path(__file__).resolve().parents[1] / 'tests/test_main.cpp').read_text(encoding='utf-8')
        names = re.findall(r'\{"([^"\r\n]+)",\s*test_\w+\}', source)
        log = ''.join('[PASS] ' + name + '\n' for name in names if name != 'n46d_embedding')
        with self.assertRaises(ValueError):
            verified_groups(source, log, 53)
        with self.assertRaises(ValueError):
            verified_groups(source, log, 46)


    def test_n46f_cannot_reuse_47_group_log(self):
        source = (Path(__file__).resolve().parents[1] / 'tests/test_main.cpp').read_text(encoding='utf-8')
        names = re.findall(r'\{"([^"\r\n]+)",\s*test_\w+\}', source)
        log = ''.join('[PASS] ' + name + '\n' for name in names if name != 'n46f_cjk')
        with self.assertRaises(ValueError):
            verified_groups(source, log, 53)
        with self.assertRaises(ValueError):
            verified_groups(source, log, 47)


    def test_n47a_cannot_reuse_48_group_log(self):
        source = (Path(__file__).resolve().parents[1] / 'tests/test_main.cpp').read_text(encoding='utf-8')
        names = re.findall(r'\{"([^"\r\n]+)",\s*test_\w+\}', source)
        log = ''.join('[PASS] ' + name + '\n' for name in names if name != 'n47a_facts')
        with self.assertRaises(ValueError):
            verified_groups(source, log, 53)
        with self.assertRaises(ValueError):
            verified_groups(source, log, 48)

    def test_n47c_cannot_reuse_50_group_log(self):
        source = (Path(__file__).resolve().parents[1] / 'tests/test_main.cpp').read_text(encoding='utf-8')
        names = re.findall(r'{"([^"\n]+)",\s*test_\w+}', source)
        log = ''.join('[PASS] ' + name + '\n' for name in names if name != 'n47c_recall')
        with self.assertRaises(ValueError):
            verified_groups(source, log, 53)

    def test_n47b_cannot_reuse_49_group_log(self):
        source = (Path(__file__).resolve().parents[1] / 'tests/test_main.cpp').read_text(encoding='utf-8')
        names = re.findall(r'\{"([^"\r\n]+)",\s*test_\w+\}', source)
        log = ''.join('[PASS] ' + name + '\n' for name in names if name != 'n47b_conflicts')
        with self.assertRaises(ValueError):
            verified_groups(source, log, 53)
        with self.assertRaises(ValueError):
            verified_groups(source, log, 49)

    def test_n47d_cannot_reuse_51_group_log(self):
        source=(Path(__file__).resolve().parents[1]/'tests/test_main.cpp').read_text(encoding='utf-8')
        names=re.findall(r'{"([^"\n]+)",\s*test_\w+}',source)
        log=''.join('[PASS] '+name+'\n' for name in names if name!='n47d_hook_facts')
        with self.assertRaises(ValueError):verified_groups(source,log,53)
        with self.assertRaises(ValueError):verified_groups(source,log,51)

    def test_n47e_cannot_reuse_52_group_log(self):
        source=(Path(__file__).resolve().parents[1]/'tests/test_main.cpp').read_text(encoding='utf-8')
        names=re.findall(r'{"([^"\n]+)",\s*test_\w+}',source)
        self.assertIn('n47e_local_fact_promotion',names)
        log=''.join('[PASS] '+name+'\n' for name in names if name!='n47e_local_fact_promotion')
        with self.assertRaises(ValueError):verified_groups(source,log,53)
        with self.assertRaises(ValueError):verified_groups(source,log,52)

if __name__ == '__main__':
    unittest.main()
