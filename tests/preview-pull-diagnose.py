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
import zipfile

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/diagnose-preview-pull-deploy.py'
spec = importlib.util.spec_from_file_location('pull_diagnose', SOURCE)
diagnose = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnose)

FAKE_TOKEN = 'github_pat_fake_token_for_tests_only'


def evidence_zip(release, run_id=46010745224, attempt=1):
    """The release artifact as the publishing job leaves it."""
    buffer = io.BytesIO()
    envelope = {'version': 1, 'run_id': run_id, 'run_attempt': attempt, 'release': release}
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('xennic-preview-release.json', json.dumps(envelope))
    return buffer.getvalue()


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


class StorageHostTest(unittest.TestCase):
    """The artifact lives in GitHub's storage, where the signed URL carries its
    own authorisation. The API token must not travel there."""

    def test_only_github_storage_hosts_are_accepted(self):
        self.assertEqual(diagnose.storage_host('https://productionresultssa7.blob.core.windows.net/x?sig=a'),
                         'productionresultssa7.blob.core.windows.net')
        self.assertEqual(diagnose.storage_host('https://pipelines.actions.githubusercontent.com/x'),
                         'pipelines.actions.githubusercontent.com')

    def test_any_other_host_is_refused(self):
        for url in ('https://evil.example.com/x', 'https://blob.core.windows.net.evil.example/x',
                    'https://notblob.core.windows.net/x', 'http://x.blob.core.windows.net/y',
                    'https://user:pass@x.blob.core.windows.net/y',
                    'https://x.blob.core.windows.net:8443/y'):
            self.assertEqual(diagnose.storage_host(url), '')

    def test_the_token_is_not_sent_to_the_storage_host(self):
        import http.server
        import threading

        seen = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append((self.path, self.headers.get('Authorization')))
                if self.path.endswith('/zip'):
                    self.send_response(302)
                    self.send_header('Location', 'http://127.0.0.1:%d/blob' % server.server_port)
                    self.end_headers()
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'zip-bytes')

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        with mock.patch.object(diagnose, 'BASE', 'http://127.0.0.1:%d' % server.server_port), \
                mock.patch.object(diagnose, 'storage_host',
                                  lambda location: '127.0.0.1' if location.startswith('http://127.0.0.1') else ''):
            hops, result = diagnose.download_artifact(7, b'secret-token')
        self.assertEqual(len(hops), 1)
        self.assertEqual(result, b'zip-bytes')
        # The API call carries the token; the storage call must not.
        self.assertEqual(seen[0][1], 'Bearer secret-token')
        self.assertEqual(seen[1][1], None)


class LoadTest(unittest.TestCase):
    """The modules import each other by sibling path, so a partial copy in one
    directory must not abort the diagnosis: the installed set comes first and
    is complete, because the installer writes it as a whole."""

    def test_a_broken_copy_in_the_first_directory_does_not_stop_the_search(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        broken = Path(tmp.name) / 'broken'
        broken.mkdir()
        # A module whose sibling import cannot resolve: exactly what the host
        # hit when the diagnosis loaded the evidence module from the refresh
        # directory, where its manifest sibling had not been fetched.
        (broken / 'sibling-user.py').write_text(
            "import importlib.util\n"
            "from pathlib import Path\n"
            "SPEC = importlib.util.spec_from_file_location('m', Path(__file__).with_name('missing.py'))\n"
            "m = importlib.util.module_from_spec(SPEC)\n"
            "SPEC.loader.exec_module(m)\n", encoding='utf-8')
        good = Path(tmp.name) / 'good'
        good.mkdir()
        (good / 'sibling-user.py').write_text("VALUE = 1\n", encoding='utf-8')

        with mock.patch.object(diagnose, 'HELPER_DIRECTORIES', (broken, good)):
            module = diagnose.load('sibling_user', 'sibling-user.py')
        self.assertEqual(module.VALUE, 1)

    def test_a_module_that_is_nowhere_is_reported_not_raised_raw(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with mock.patch.object(diagnose, 'HELPER_DIRECTORIES', (Path(tmp.name),)):
            with self.assertRaises(RuntimeError):
                diagnose.load('nothing', 'not-here.py')


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
                diagnose.anomalies.clear()
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
            diagnose.anomalies.clear()
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

    def test_it_fetches_the_sibling_the_evidence_module_imports(self):
        # preview-ci-evidence.py imports preview-deploy-manifest.py by sibling
        # path. Without it the diagnosis cannot read the evidence envelope.
        self.assertIn('preview-deploy-manifest.py', self.source)
        files = [line for line in self.source.splitlines() if line.startswith('FILES=')]
        self.assertEqual(len(files), 1)
        for name in ('preview-ci-evidence.py', 'preview-deploy-manifest.py',
                     'diagnose-preview-pull-deploy.py'):
            self.assertIn(name, files[0])


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


class ReleaseNameTest(unittest.TestCase):
    """The name of a release is a tag on the commit it releases, and exactly
    one such tag. The diagnosis has to read the same rule the deployer read."""

    COMMIT = 'a' * 40
    OTHER = 'b' * 40

    def tags(self, *items):
        return json.dumps(list(items)).encode()

    def tag(self, name, commit):
        return {'name': name, 'commit': {'sha': commit}}

    def read(self, body):
        with mock.patch.object(diagnose, 'api', return_value=(200, body)):
            return diagnose.release_name_for(self.COMMIT, b'token')

    def test_the_one_tag_on_the_commit_is_the_name(self):
        body = self.tags(self.tag('v1.0.1', self.COMMIT))
        self.assertEqual(self.read(body), 'v1.0.1')

    def test_a_tag_on_another_commit_is_not_the_name(self):
        body = self.tags(self.tag('v1.0.1', self.OTHER))
        self.assertIsNone(self.read(body))

    def test_a_commit_with_two_names_has_no_single_name(self):
        body = self.tags(self.tag('v1.0.1', self.COMMIT), self.tag('v1.0.2', self.COMMIT))
        self.assertIsNone(self.read(body))

    def test_a_name_that_is_not_a_release_name_is_ignored(self):
        body = self.tags(self.tag('nightly', self.COMMIT))
        self.assertIsNone(self.read(body))

    def test_every_page_is_read(self):
        first = self.tags(*[self.tag('v0.0.%d' % index, self.OTHER) for index in range(100)])
        second = self.tags(self.tag('v1.0.1', self.COMMIT))
        pages = [(200, first), (200, second)]
        with mock.patch.object(diagnose, 'api', side_effect=pages) as called:
            name = diagnose.release_name_for(self.COMMIT, b'token')
        self.assertEqual(name, 'v1.0.1')
        self.assertEqual(called.call_count, 2)

    def test_a_refused_read_is_an_error_and_not_a_name(self):
        with mock.patch.object(diagnose, 'api', return_value=(403, b'{"message":"no"}')):
            with self.assertRaises(RuntimeError):
                diagnose.release_name_for(self.COMMIT, b'token')

    def test_the_rule_is_the_same_one_the_verifier_applies(self):
        # The verifier is the code that named the release in the first place:
        # the diagnosis must not invent a second, weaker rule.
        verifier = Path(__file__).resolve().parents[1] / 'scripts/preview-release-verifier.py'
        spec = importlib.util.spec_from_file_location('diagnose_verifier', verifier)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        body = self.tags(self.tag('v1.0.1', self.COMMIT), self.tag('v1.0.2', self.COMMIT))
        with mock.patch.object(module, 'get_json', return_value=json.loads(body)):
            with self.assertRaises(module.Unverified):
                module.release_version(self.COMMIT, b'token')
        body = self.tags(self.tag('v1.0.1', self.COMMIT), self.tag('v2.0.0', self.OTHER))
        with mock.patch.object(module, 'get_json', return_value=json.loads(body)):
            self.assertEqual(module.release_version(self.COMMIT, b'token'), 'v1.0.1')


class LiveVersionTest(unittest.TestCase):
    """The last proof: the version that is live is the name the repository
    gives the commit that is live. A difference is a failure, not a note."""

    COMMIT = 'a' * 40

    def run_main(self, journal, name='v1.0.1'):
        states = mock.Mock()
        states.Journal.return_value.read.return_value = journal
        sha = 'a' * 40
        release = {'repository': 'feerozmandi/xennic-website', 'commit': sha,
                   'run_number': 299, 'digest': 'sha256:' + '0' * 64,
                   'platform': 'linux/amd64'}
        evidence_module = mock.Mock()
        evidence_module.check.return_value = release

        def fake_api(path, token):
            if path.startswith('/commits/'):
                return 200, json.dumps({'sha': sha}).encode()
            if '/actions/workflows/' in path:
                run = {'id': 46010745224, 'run_number': 299, 'run_attempt': 1,
                       'head_sha': sha, 'head_branch': 'dev', 'event': 'push',
                       'status': 'completed', 'conclusion': 'success'}
                return 200, json.dumps({'workflow_runs': [run]}).encode()
            if '/actions/runs/' in path and 'artifacts' in path:
                artifact = {'id': 1, 'name': 'xennic-preview-release-1', 'expired': False,
                            'size_in_bytes': 377}
                return 200, json.dumps({'artifacts': [artifact]}).encode()
            return 404, b'{}'

        def fake_load(name, filename):
            return evidence_module if 'evidence' in name else states

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            with mock.patch.object(diagnose, 'read_token', lambda: FAKE_TOKEN.encode()), \
                    mock.patch.object(diagnose, 'api', side_effect=fake_api), \
                    mock.patch.object(diagnose, 'download_artifact',
                                      return_value=([], evidence_zip(evidence_module.check.return_value))), \
                    mock.patch.object(diagnose, 'public_status', return_value=200), \
                    mock.patch.object(diagnose, 'load', side_effect=fake_load), \
                    mock.patch.object(diagnose, 'release_name_for', return_value=name):
                diagnose.failures.clear()
                diagnose.anomalies.clear()
                status = diagnose.main()
        return status, buffer.getvalue()

    def journal(self, version=None):
        data = {'version': 1, 'last_run': 300, 'blocked': False,
                'current': {'repository': 'feerozmandi/xennic-website', 'commit': self.COMMIT,
                            'run_number': 299, 'digest': 'sha256:' + '0' * 64,
                            'platform': 'linux/amd64'},
                'previous': [], 'pending': None}
        if version is not None:
            data['release_version'] = version
        return data

    def test_the_same_name_on_both_sides_is_the_proof(self):
        status, output = self.run_main(self.journal('v1.0.1'), name='v1.0.1')
        self.assertEqual(status, 0)
        self.assertIn('v1.0.1', output)
        self.assertIn('the same', output)

    def test_a_different_name_is_an_anomaly(self):
        status, output = self.run_main(self.journal('v1.0.2'), name='v1.0.1')
        self.assertEqual(status, 1)
        self.assertIn('ANOMALY', output)
        self.assertIn('v1.0.1', output)
        self.assertIn('v1.0.2', output)
        # It is not a deployment failure: nothing stopped, and the release
        # read itself worked.
        self.assertNotIn('FAILED', output)

    def test_a_release_without_a_name_is_not_a_failure(self):
        status, output = self.run_main(self.journal(), name='v1.0.1')
        self.assertEqual(status, 0)
        self.assertIn('before naming', output)

    def test_the_token_is_never_printed(self):
        status, output = self.run_main(self.journal('v1.0.1'), name='v1.0.1')
        self.assertNotIn(FAKE_TOKEN, output)


class NoCandidateTest(unittest.TestCase):
    """The proof about the live release does not depend on the candidate.

    When the current head of `dev` has no successful run there is nothing to
    deploy, and the diagnosis says so. But the release that is already live
    can still be proved, and the operator still has to be told: the question
    "is the live version the name the repository gives it?" does not depend
    on there being a new release to put on the host.
    """

    COMMIT = 'a' * 40

    def run_main(self, journal, name='v1.0.1'):
        states = mock.Mock()
        states.Journal.return_value.read.return_value = journal
        sha = 'a' * 40

        def fake_api(path, token):
            if path.startswith('/commits/'):
                return 200, json.dumps({'sha': sha}).encode()
            if '/actions/workflows/' in path:
                # A run that is not a success: the candidate does not exist.
                run = {'id': 46010745224, 'run_number': 299, 'run_attempt': 1,
                       'head_sha': sha, 'head_branch': 'dev', 'event': 'push',
                       'status': 'completed', 'conclusion': 'failure'}
                return 200, json.dumps({'workflow_runs': [run]}).encode()
            return 404, b'{}'

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            with mock.patch.object(diagnose, 'read_token', lambda: FAKE_TOKEN.encode()), \
                    mock.patch.object(diagnose, 'api', side_effect=fake_api), \
                    mock.patch.object(diagnose, 'public_status', return_value=200), \
                    mock.patch.object(diagnose, 'load', return_value=states), \
                    mock.patch.object(diagnose, 'release_name_for', return_value=name):
                diagnose.failures.clear()
                diagnose.anomalies.clear()
                status = diagnose.main()
        return status, buffer.getvalue()

    def journal(self, version):
        return {'version': 1, 'last_run': 300, 'blocked': False,
                'current': {'repository': 'feerozmandi/xennic-website', 'commit': self.COMMIT,
                            'run_number': 299, 'digest': 'sha256:' + '0' * 64,
                            'platform': 'linux/amd64'},
                'previous': [], 'pending': None,
                'release_version': version}

    def test_the_live_release_is_still_proved_without_a_candidate(self):
        status, output = self.run_main(self.journal('v1.0.1'))
        self.assertEqual(status, 1)  # there is nothing to deploy
        self.assertIn('FAILED', output)
        self.assertIn('no successful push run', output)
        self.assertIn('the same', output)
        self.assertIn('The live release is v1.0.1', output)

    def test_the_mismatch_is_still_reported_without_a_candidate(self):
        status, output = self.run_main(self.journal('v9.9.9'))
        self.assertEqual(status, 1)
        self.assertIn('ANOMALY', output)
        self.assertIn('The live release is v9.9.9', output)
        self.assertIn('the repository does not give it that name', output)


if __name__ == '__main__':
    unittest.main(verbosity=2)
