"""Separate review: reject incomplete HTTP framing and explicit port zero."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest

import memory_task_contract as c
import model_ab as m
from test_model_ab import Setup, response


class FramingTests(Setup):
    def test_explicit_zero_port_is_not_silently_defaulted(self):
        for url in ('http://127.0.0.1:0/v1/chat/completions', 'https://provider.example:0/v1/chat/completions'):
            with self.subTest(url=url):
                with self.assertRaises(ValueError): m.endpoint(url, url.startswith('http:'))

    def test_incomplete_and_ambiguous_bodies_stop_after_one_attempt(self):
        for fault in ('short_read', 'duplicate_length', 'mixed_framing'):
            calls = []
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *args): pass
                def do_POST(self):
                    raw = self.rfile.read(int(self.headers['Content-Length']))
                    calls.append(raw); data = response(c.decode(raw))
                    self.send_response(200)
                    self.send_header('Content-Length', str(len(data) + (10 if fault == 'short_read' else 0)))
                    if fault == 'duplicate_length': self.send_header('Content-Length', str(len(data)))
                    if fault == 'mixed_framing': self.send_header('Transfer-Encoding', 'chunked')
                    self.end_headers()
                    try: self.wfile.write(data)
                    except (BrokenPipeError, ConnectionResetError): pass
            httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True); thread.start()
            try:
                with self.subTest(fault=fault):
                    url = f'http://127.0.0.1:{httpd.server_port}/v1/chat/completions'
                    result = self.execute(self.plan(url, True), fault)
                    self.assertEqual(result['completed'], 0)
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(result['rows'][0]['status'], 'transport_error')
                    self.assertEqual(result['rows'][1]['status'], 'not_attempted')
            finally:
                httpd.shutdown(); httpd.server_close(); thread.join(timeout=5)


if __name__ == '__main__': unittest.main(verbosity=2)
