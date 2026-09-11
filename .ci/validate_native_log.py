"""Distinguish registered native test groups from verbose nested assertion names."""
from collections import Counter
import re


def verified_groups(registry: str, log: str, expected_count: int = 44) -> list[str]:
    expected = re.findall(r'\{"([^"\r\n]+)",\s*test_\w+\}', registry)
    # Native runner group names are single identifiers on complete lines.
    # Nested N42 assertions print descriptive labels such as 'legacy RRF'.
    passed = re.findall(r'^\[PASS\] (\w+)\s*$', log, re.MULTILINE)
    if len(expected) != expected_count or len(set(expected)) != len(expected):
        raise ValueError('Unexpected or duplicated native test registry')
    if '[FAIL]' in log or Counter(passed) != Counter(expected):
        raise ValueError('Native group evidence is missing, duplicated or failed')
    return expected
