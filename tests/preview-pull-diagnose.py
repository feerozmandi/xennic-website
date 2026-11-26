#!/usr/bin/env python3
"""Tests for the read-only pull-deploy diagnosis on the preview host.

The diagnostic exists because the deployer stops with one word when GitHub
does not give it what it expects. These tests hold it to what it promises: it
reads, it never writes, it never prints the token, and it reports the real
status of every request it makes.
"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/diagnose-preview-pull-deploy.py'
spec = importlib.util.spec_from_file_location('pull_diagnose', SOURCE)
diagnose = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnose)

FAKE_TOKEN = 'github_pat_fake_token_for_tests_only'


class SourceTest(unittest.TestCase):
    """The diagnosis is a diagnosis: it must not change anything."""

    def setUp(self):
        self.source = SOURCE.read_text(encoding='utf-8')

    def test_every_request_is_a_read(self):
        for method in ("'POST'", '"POST"', "'PUT'", '"PUT"', "'DELETE'", '"DELETE"'):
            self.assertNotIn(method, self.source)

    def test_it_writes_nothing(self):
        for forbidden in ('os.write', 'os.remove', 'os.replace', 'os.rename', 'os.chmod',
                          'shutil', 'subprocess', 'open(STAGED'):
            self.assertNotIn(forbidden, self.source)

    def test_the_token_file_is_only_ever_read(self):
        self.assertIn('TOKEN.read_bytes()', self.source)
        self.assertNotIn('TOKEN.write', self.source)


class MessageTest(unittest.TestCase):
    def test_the_github_message_is_extracted(self):
        body = json.dumps({'message': 'Resource not accessible by integration'}).encode()
        self.assertEqual(diagnose.github_message(body), 'Resource not accessible by integration')

    def test_a_body_that_is_not_an_error_object_has_no_message(self):
        self.assertEqual(diagnose.github_message(b'not json'), '')
        self.assertEqual(diagnose.github_message(b'{"sha":"abc"}'), '')


class PublicStatusTest(unittest.TestCase):
    """A redirect is a status, not a page: the gate answers 302 and its own
    sign-in page answers 200, so following it would hide the gate."""

    def test_a_redirect_is_reported_as_a_redirect(self):
        import http.server
        import threading

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header('Location', '/landing')
                self.end_headers()

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = 'http://127.0.0.1:%d/' % server.server_port
        self.assertEqual(diagnose.public_status(url), 302)

    def test_a_dead_host_is_zero(self):
        self.assertEqual(diagnose.public_status('http://127.0.0.1:1/'), 0)


class OutputTest(unittest.TestCase):
    """The token must never reach the output, and the output must say what failed."""

    def run_main(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            with mock.patch.object(diagnose, 'read_token', lambda: FAKE_TOKEN.encode()), \
                    mock.patch.object(diagnose, 'api', return_value=(200, b'{"sha":"' + b'a' * 40 + b'"}')), \
                    mock.patch.object(diagnose, 'download_artifact', return_value=([], b'not a zip')), \
                    mock.patch.object(diagnose, 'public_status', return_value=200), \
                    mock.patch.object(diagnose, 'load', return_value=mock.Mock()):
                diagnose.failures.clear()
                status = diagnose.main()
        return status, buffer.getvalue()

    def test_the_token_is_never_printed(self):
        status, output = self.run_main()
        self.assertNotIn(FAKE_TOKEN, output)
        self.assertEqual(status, 1)
        self.assertIn('FAILED', output)

    def test_a_failure_is_reported_with_its_cause(self):
        with mock.patch.object(diagnose, 'read_token', lambda: FAKE_TOKEN.encode()), \
                mock.patch.object(diagnose, 'api', return_value=(403, b'{"message":"Resource not accessible by integration"}')):
            diagnose.failures.clear()
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                status = diagnose.main()
        output = buffer.getvalue()
        self.assertEqual(status, 1)
        self.assertIn('Resource not accessible by integration', output)
        self.assertNotIn(FAKE_TOKEN, output)


if __name__ == '__main__':
    unittest.main(verbosity=2)
