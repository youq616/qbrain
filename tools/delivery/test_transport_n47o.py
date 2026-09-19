"""Transport regressions for N47O; no live network or publication."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('delivery', Path(__file__).with_name('publish_reviewed_n47o.py'))
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)


class TransportTests(unittest.TestCase):
    def test_artifact_and_release_binary_accept_headers(self):
        for endpoint, wants_header in [('actions/artifacts/123/zip', False), ('releases/assets/123', True)]:
            with self.subTest(endpoint=endpoint):
                def call(argv, **kw):
                    self.assertEqual('Accept: application/octet-stream' in argv, wants_header)
                    kw['stdout'].write(b'PK\x03\x04binary')
                    return subprocess.CompletedProcess(argv, 0, stderr=b'')
                with patch.object(p.subprocess, 'run', side_effect=call):
                    self.assertEqual(p.GitHub().raw(endpoint, binary=True), b'PK\x03\x04binary')

    def test_error_has_http_code_without_credentials_or_signed_url(self):
        def call(argv, **kw):
            kw['stdout'].write(b'{}')
            return subprocess.CompletedProcess(argv, 1, stderr=b'secret-token signed-url (HTTP 415)')
        with patch.object(p.subprocess, 'run', side_effect=call):
            with self.assertRaisesRegex(RuntimeError, 'HTTP 415') as error:
                p.GitHub().raw('actions/artifacts/123/zip', binary=True)
            self.assertNotIn('secret-token', str(error.exception))
            self.assertNotIn('signed-url', str(error.exception))


if __name__ == '__main__': unittest.main(verbosity=2)
