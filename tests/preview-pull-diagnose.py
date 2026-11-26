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
import os
from pathlib import Path
import tempfile
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

    def test_it_writes_nothing_by_itself(self):
        # The only write is the candidate file, and only when it is asked for.
        for forbidden in ('os.write', 'os.remove', 'os.rename', 'shutil', 'subprocess'):
            self.assertNotIn(forbidden, self.source)
        self.assertIn('--write-manifest', self.source)
        self.assertIn("if write_manifest:", self.source)

    def test_the_candidate_file_is_the_only_thing_it_writes(self):
        self.assertEqual(diagnose.CANDIDATE, Path('/root/xennic-preview-candidate.json'))
        self.assertIn('os.replace(staged, CANDIDATE)', self.source)

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


class RefreshScriptTest(unittest.TestCase):
    """The one-line host refresh must install and diagnose, and nothing else."""

    def setUp(self):
        path = Path(__file__).resolve().parents[1] / 'scripts/refresh-preview-pull-deploy.sh'
        self.source = path.read_text(encoding='utf-8')
        # Only the commands matter here; the comments say what it does not do.
        self.commands = '\n'.join(line for line in self.source.splitlines()
                                  if not line.lstrip().startswith('#'))

    def test_it_needs_root_and_fails_early(self):
        self.assertIn('set -euo pipefail', self.source)
        self.assertIn('id -u', self.source)

    def test_it_never_approves_or_starts_a_deployment(self):
        for forbidden in ('ci-gateway approve', 'ci-gateway deploy', 'compatible-transitions',
                          'systemctl start', 'ci-pull-deploy --dry-run'):
            self.assertNotIn(forbidden, self.commands)

    def test_it_refreshes_the_gateway_only_when_it_is_already_there(self):
        self.assertIn('if [ -e "$GATEWAY_TARGET" ]; then', self.commands)
        self.assertIn('install-preview-ci-gateway.py', self.commands)

    def test_it_installs_and_then_diagnoses(self):
        self.assertIn('install-preview-pull-deploy.py', self.source)
        self.assertIn('diagnose-preview-pull-deploy.py', self.source)


class CandidateFileTest(unittest.TestCase):
    """The manifest the operator approves is written once, root-only, intact."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'candidate.json'
        patcher = mock.patch.object(diagnose, 'CANDIDATE', self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_it_is_private_and_holds_exactly_one_line(self):
        diagnose.write_candidate('{"commit":"' + 'a' * 40 + '"}')
        self.assertEqual(self.path.read_text(), '{"commit":"' + 'a' * 40 + '"}\n')
        self.assertEqual(os.lstat(self.path).st_mode & 0o777, 0o600)

    def test_it_replaces_an_earlier_candidate(self):
        diagnose.write_candidate('{"first":1}')
        diagnose.write_candidate('{"second":2}')
        self.assertEqual(self.path.read_text(), '{"second":2}\n')


class ArgumentTest(unittest.TestCase):
    def test_an_unknown_argument_is_refused(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with mock.patch.object(diagnose.sys, 'argv', ['diagnose', '--deploy']):
                self.assertEqual(diagnose.main(), 2)

    def test_the_diagnosis_runs_without_arguments(self):
        with mock.patch.object(diagnose.sys, 'argv', ['diagnose']):
            with mock.patch.object(diagnose, 'read_token',
                                   side_effect=RuntimeError('no token here')):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(diagnose.main(), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
