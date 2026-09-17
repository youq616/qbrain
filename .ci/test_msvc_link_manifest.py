"""Static default MSVC source/object closure checks; not a C++ compile test."""
from __future__ import annotations
from collections import Counter
from pathlib import Path, PureWindowsPath
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def literal_array(script: str, variable: str) -> list[str]:
    """Understand only the literal array syntax used by our native scripts."""
    rows = re.findall(r'(?m)^\$' + re.escape(variable) + r'\s*=\s*@\((.*?)^\)', script, re.S)
    if len(rows) != 1:
        raise ValueError('missing or repeated literal array: ' + variable)
    body = rows[0]
    # No interpolation, comment interpretation or PowerShell execution here.
    if not re.fullmatch(r'\s*"[A-Za-z0-9_\\/.-]+"(?:\s*,\s*"[A-Za-z0-9_\\/.-]+")*\s*', body):
        raise ValueError('unrecognized literal array: ' + variable)
    return re.findall(r'"([^"\r\n]+)"', body)


def validate_manifest(production: str, tests: str) -> dict[str, int]:
    source = literal_array(production, 'productionSources')
    linked = literal_array(production, 'prodObjNames')
    test_sources = literal_array(tests, 'defaultTestSources')
    test_linked = literal_array(tests, 'prodObjs')
    for paths in (source, test_sources):
        if any(PureWindowsPath(p).is_absolute() or '..' in PureWindowsPath(p).parts or
               PureWindowsPath(p).suffix.casefold() != '.cpp' for p in paths):
            raise ValueError('unexpected source path')
    stems = [PureWindowsPath(p).stem.casefold() for p in source]
    test_stems = [PureWindowsPath(p).stem.casefold() for p in test_sources]
    linked = [p.casefold() for p in linked]
    test_linked = [p.casefold() for p in test_linked]
    for label, values in (('source stems', stems), ('production objects', linked),
                          ('test source stems', test_stems), ('test objects', test_linked)):
        if len(values) != len(set(values)):
            raise ValueError('duplicate ' + label)
    if Counter(linked) != Counter(stems):
        raise ValueError('production object closure mismatch')
    # Native tests replace the application entry points, and link bundled SQLite.
    if not {'main', 'app'}.issubset(stems):
        raise ValueError('application entry points missing')
    expected_test = (set(stems) - {'main', 'app'}) | {'sqlite3'}
    if set(test_linked) != expected_test:
        raise ValueError('test production-object closure mismatch')
    if set(test_stems) & set(test_linked):
        raise ValueError('test and production object collision')
    return {'production_sources': len(source), 'test_sources': len(test_sources)}


class MsvcLinkManifestTests(unittest.TestCase):
    def setUp(self):
        self.prod = '$productionSources = @(\n "src\\app.cpp", "src\\main.cpp", "src\\diagnostics.cpp"\n)\n$prodObjNames = @(\n "app", "main", "diagnostics"\n)'
        self.tests = '$defaultTestSources = @(\n "tests\\test_main.cpp"\n)\n$prodObjs = @(\n "diagnostics", "sqlite3"\n) | ForEach-Object { "unused" }'

    def test_real_default_native_closures(self):
        prod = (ROOT/'scripts/build-cl.ps1').read_text(encoding='utf-8-sig')
        tests = (ROOT/'scripts/build-tests-cl.ps1').read_text(encoding='utf-8-sig')
        result = validate_manifest(prod, tests)
        self.assertGreater(result['production_sources'], 0)
        for text, var in ((prod, 'productionSources'), (tests, 'defaultTestSources')):
            for path in literal_array(text, var):
                self.assertTrue((ROOT/Path(*PureWindowsPath(path).parts)).is_file(), path)

    def test_complete_literal_fixture(self):
        self.assertEqual(validate_manifest(self.prod, self.tests),
                         {'production_sources': 3, 'test_sources': 1})

    def test_missing_production_object_detected(self):
        with self.assertRaisesRegex(ValueError, 'production object closure'):
            validate_manifest(self.prod.replace(', "diagnostics"\n)', '\n)'), self.tests)

    def test_missing_test_object_detected(self):
        with self.assertRaisesRegex(ValueError, 'test production-object'):
            validate_manifest(self.prod, self.tests.replace('"diagnostics", ', ''))

    def test_extra_stale_object_detected(self):
        with self.assertRaises(ValueError):
            validate_manifest(self.prod.replace('"main", "diagnostics"', '"main", "diagnostics", "stale"'), self.tests)

    def test_duplicate_source_stems_detected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate source stems'):
            validate_manifest(self.prod.replace('"src\\diagnostics.cpp"', '"src\\diagnostics.cpp", "other\\DIAGNOSTICS.cpp"'), self.tests)

    def test_duplicate_link_objects_detected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate production objects'):
            validate_manifest(self.prod.replace('"main", "diagnostics"', '"main", "diagnostics", "DIAGNOSTICS"'), self.tests)

    def test_test_production_collision_detected(self):
        with self.assertRaisesRegex(ValueError, 'collision'):
            validate_manifest(self.prod, self.tests.replace('tests\\test_main.cpp', 'tests\\diagnostics.cpp'))

    def test_unknown_or_repeated_array_rejected(self):
        for changed in (self.prod.replace('"app", "main"', '$computed, "main"'),
                        self.prod + '\n$prodObjNames = @(\n "x"\n)',
                        self.prod.replace('$prodObjNames', '$other')):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                validate_manifest(changed, self.tests)

    def test_no_path_escape_or_entrypoint_drop(self):
        for changed in (self.prod.replace('src\\main.cpp', '..\\main.cpp'),
                        self.prod.replace('src\\main.cpp', 'C:\\main.cpp'),
                        self.prod.replace('main', 'notmain')):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                validate_manifest(changed, self.tests)


if __name__ == '__main__':
    unittest.main(verbosity=2)
