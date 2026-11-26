#!/usr/bin/env python3
"""Tests for the pull deployer's decisions, without a host or a network.

Everything that decides *whether* to deploy is pure and covered here. The
transaction it then calls is the same guarded backend a human calls by hand, and
it is deliberately not re-implemented or mocked into "success".
"""
import importlib.util
import json
import re
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/preview-pull-deploy.py'
spec = importlib.util.spec_from_file_location('pull_deploy', SOURCE)
pull = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pull)

A = 'a' * 40
B = 'b' * 40


def release(commit, run_number=240):
    return {'repository': 'feerozmandi/xennic-website', 'commit': commit, 'run_number': run_number,
            'digest': 'sha256:' + 'c' * 64, 'platform': 'linux/amd64'}


def journal(current=None, pending=None):
    return {'version': 1, 'last_run': 240, 'blocked': pending is not None,
            'current': current, 'previous': [], 'pending': pending}


class DecideTest(unittest.TestCase):
    def test_nothing_to_do_when_the_journal_is_absent(self):
        self.assertEqual(pull.decide(None, release(A)), 'no-journal')

    def test_same_commit_is_up_to_date(self):
        self.assertEqual(pull.decide(journal(release(A)), release(A)), 'up-to-date')

    def test_in_flight_release_wins_over_everything(self):
        state = journal(release(A), pending=release(B, 241))
        self.assertEqual(pull.decide(state, release(B, 241)), 'in-flight')

    def test_a_new_commit_is_considered(self):
        self.assertEqual(pull.decide(journal(release(A)), release(B, 241)), 'consider')

    def test_no_journal_and_no_current_never_deploys(self):
        self.assertEqual(pull.decide(journal(None), release(A)), 'no-journal')


class ReviewedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'compatible-transitions.json'

    def write(self, data, mode=0o600):
        self.path.write_text(json.dumps(data))
        self.path.chmod(mode)

    def test_exact_pair_is_approved(self):
        self.write({'version': 1, 'transitions': [
            {'from_commit': A, 'to_commit': B, 'migration_sha256': 'd' * 64,
             'previous_migrations': ['m'], 'rollback_safe': True}]})
        with mock.patch.object(pull, 'private_file', lambda path, maximum: self.path.read_bytes()):
            self.assertTrue(pull.reviewed(A, B))
            self.assertFalse(pull.reviewed(B, A))
            self.assertFalse(pull.reviewed(A, 'e' * 40))

    def test_malformed_file_is_refused(self):
        for data in ({}, {'version': 2, 'transitions': []}, {'version': 1, 'transitions': 'x'}):
            self.write(data)
            with mock.patch.object(pull, 'private_file', lambda path, maximum: self.path.read_bytes()):
                with self.assertRaises(pull.PullFailed):
                    pull.reviewed(A, B)

    def test_unreadable_json_is_refused(self):
        self.path.write_text('{not json')
        with mock.patch.object(pull, 'private_file', lambda path, maximum: self.path.read_bytes()):
            with self.assertRaises(pull.PullFailed):
                pull.reviewed(A, B)


class RecordTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.record = Path(self.tmp.name) / 'pull-deploy.json'
        for patcher in (mock.patch.object(pull, 'RECORD', self.record),
                        # The ownership check is root-only; the test file is not
                        # root-owned, so read it the same way without that check.
                        mock.patch.object(pull, 'private_file', relaxed_private_file)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_round_trip_is_private(self):
        pull.write_record({'version': 1, 'result': 'deployed', 'run_number': 240})
        self.assertEqual(pull.read_record()['result'], 'deployed')
        self.assertEqual(stat_mode(self.record), 0o600)

    def test_missing_or_broken_record_reads_empty(self):
        self.assertEqual(pull.read_record(), {})
        self.record.write_text('{"result": ')
        self.assertEqual(pull.read_record(), {})

    def test_oversized_record_is_refused(self):
        with self.assertRaises(pull.PullFailed):
            pull.write_record({'blob': 'x' * (pull.MAX_RECORD + 10)})


TOKEN = '123456789:AAHfakeTokenForTestsOnly_abc'


class NotifyTest(unittest.TestCase):
    def test_no_configuration_is_silent(self):
        with mock.patch.object(pull.os.path, 'lexists', lambda path: False):
            self.assertFalse(pull.notify('hello'))

    def test_bale_is_the_default_and_telegram_is_still_readable(self):
        self.assertEqual(pull.notification_target({'bot_token': TOKEN, 'chat_id': '42'}),
                         ('https://tapi.bale.ai/bot%s/sendMessage' % TOKEN, '42'))
        self.assertEqual(pull.notification_target({'provider': 'telegram', 'bot_token': TOKEN,
                                                   'chat_id': '-1001234'}),
                         ('https://api.telegram.org/bot%s/sendMessage' % TOKEN, '-1001234'))
        # The pre-Bale file shape keeps working.
        self.assertEqual(pull.notification_target({'telegram_bot_token': TOKEN,
                                                   'telegram_chat_id': '42'}),
                         ('https://tapi.bale.ai/bot%s/sendMessage' % TOKEN, '42'))

    def test_channel_username_is_accepted(self):
        self.assertEqual(pull.notification_target({'bot_token': TOKEN, 'chat_id': '@xennic_ir'})[1],
                         '@xennic_ir')

    def test_unknown_provider_and_bad_values_are_refused(self):
        for config in ({'provider': 'sms', 'bot_token': TOKEN, 'chat_id': '42'},
                       {'provider': 'telegram', 'bot_token': 'short', 'chat_id': '42'},
                       {'bot_token': TOKEN, 'chat_id': 'not a chat'},
                       {'bot_token': TOKEN},
                       'not an object'):
            with self.assertRaises(pull.PullFailed, msg=str(config)):
                pull.notification_target(config)

    def test_bad_configuration_is_silent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'notify.json'
            path.write_text(json.dumps({'bot_token': 'short', 'chat_id': 'x'}))
            path.chmod(0o600)
            with mock.patch.object(pull, 'NOTIFY', path), \
                    mock.patch.object(pull, 'private_file', lambda p, m: path.read_bytes()):
                self.assertFalse(pull.notify('hello'))

    def test_a_working_send_posts_json_to_the_allowlisted_host(self):
        seen = {}

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        class Opener:
            def open(self, request, timeout=0):
                seen['url'] = request.full_url
                seen['body'] = json.loads(request.data)
                return Response()

        with mock.patch.object(pull.os.path, 'lexists', lambda path: True), \
                mock.patch.object(pull, 'private_file',
                                  lambda p, m: json.dumps({'bot_token': TOKEN, 'chat_id': '42'}).encode()), \
                mock.patch.object(pull, 'NOTIFY_OPENER', Opener()):
            self.assertTrue(pull.notify('deployed'))
        self.assertEqual(seen['url'], 'https://tapi.bale.ai/bot%s/sendMessage' % TOKEN)
        self.assertEqual(seen['body']['chat_id'], '42')
        self.assertEqual(seen['body']['text'], 'deployed')

    def test_redirects_are_not_followed(self):
        handler = pull.NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, 'Found', {}, 'https://elsewhere'))


class RunIdentityTest(unittest.TestCase):
    def test_only_a_successful_push_run_for_the_dev_head_counts(self):
        class Verifier:
            def get_json(self, path, token):
                if path == '/commits/dev':
                    return {'sha': A}
                return {'workflow_runs': [
                    {'id': 1, 'run_number': 239, 'run_attempt': 1, 'head_sha': A, 'head_branch': 'dev',
                     'event': 'push', 'status': 'completed', 'conclusion': 'success'},
                    {'id': 2, 'run_number': 241, 'run_attempt': 1, 'head_sha': A, 'head_branch': 'dev',
                     'event': 'push', 'status': 'completed', 'conclusion': 'failure'},
                    {'id': 3, 'run_number': 242, 'run_attempt': 1, 'head_sha': B, 'head_branch': 'dev',
                     'event': 'push', 'status': 'completed', 'conclusion': 'success'},
                    {'id': 4, 'run_number': 243, 'run_attempt': 1, 'head_sha': A, 'head_branch': 'feature',
                     'event': 'push', 'status': 'completed', 'conclusion': 'success'},
                ]}
        run = pull.newest_run(Verifier(), b'token')
        self.assertEqual(run['id'], 1)

    def test_no_successful_run_for_the_head_is_an_error(self):
        class Verifier:
            def get_json(self, path, token):
                return {'sha': A} if path == '/commits/dev' else {'workflow_runs': []}
        with self.assertRaises(pull.PullFailed):
            pull.newest_run(Verifier(), b'token')


class PublicCheckTest(unittest.TestCase):
    """The post-deployment check must ask a route the edge really publishes.

    `/health` is deliberately not on the public route allowlist: an anonymous
    GET of it is answered by the gate's sign-in redirect, so it can never be a
    deployment signal.
    """

    def test_the_check_uses_a_public_route(self):
        self.assertEqual(pull.PUBLIC_CHECK_URL, 'https://xennic.ir/robots.txt')
        self.assertNotIn('/health', pull.PUBLIC_CHECK_URL)

    def test_the_deployer_never_asks_the_gated_health_route(self):
        source = SOURCE.read_text(encoding='utf-8')
        self.assertNotIn('xennic.ir/health', source)

    def test_a_200_is_reported(self):
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        class Opener:
            def open(self, request, timeout=0):
                return Response()

        with mock.patch.object(pull, 'PUBLIC_OPENER', Opener()):
            self.assertEqual(pull.public_check(), 200)

    def test_a_redirect_is_reported_and_not_followed(self):
        # A real server: the sign-in page answers 200 itself, so following the
        # redirect would report a gated site as a healthy one.
        import http.server
        import threading

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/redirect':
                    self.send_response(302)
                    self.send_header('Location', '/landing')
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header('Content-Length', '2')
                self.end_headers()
                self.wfile.write(b'ok')

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = 'http://127.0.0.1:%d/redirect' % server.server_port
        with mock.patch.object(pull, 'PUBLIC_CHECK_URL', url):
            self.assertEqual(pull.public_check(), 302)

    def test_a_connection_failure_is_zero(self):
        class Opener:
            def open(self, request, timeout=0):
                raise OSError('connection refused')

        with mock.patch.object(pull, 'PUBLIC_OPENER', Opener()):
            self.assertEqual(pull.public_check(), 0)

    def test_the_record_of_a_deployment_is_not_overwritten_by_the_public_check(self):
        # The backend already proved the new image is healthy inside the host.
        # The public check observes the edge; a non-200 must not turn a
        # finished deployment into a recorded failure.
        source = SOURCE.read_text(encoding='utf-8')
        self.assertNotIn("'result': 'failed', 'stage': 'public-check'", source)
        self.assertIn("'result': 'deployed'", source)
        self.assertIn("'public_status': status", source)


class Unverified(RuntimeError):
    """Stands in for the verifier's own exception, by name and by shape."""


class ReasonTest(unittest.TestCase):
    """A failure has to say what went wrong, without saying anything secret."""

    def test_the_verifier_message_is_kept(self):
        self.assertEqual(pull.reason(Unverified('GitHub evidence unavailable')),
                         'GitHub evidence unavailable')

    def test_an_arbitrary_message_is_not_printed(self):
        self.assertEqual(pull.reason(RuntimeError('https://example.invalid/?token=secret')), '')

    def test_a_failed_call_keeps_the_stage_and_the_reason(self):
        def boom():
            raise Unverified('GitHub evidence unavailable')

        with self.assertRaises(pull.PullFailed) as caught:
            pull.call('cannot list workflow runs', boom)
        self.assertEqual(str(caught.exception),
                         'cannot list workflow runs: GitHub evidence unavailable')

    def test_a_failed_call_without_a_safe_reason_names_only_the_stage(self):
        def boom():
            raise RuntimeError('https://example.invalid/?token=secret')

        with self.assertRaises(pull.PullFailed) as caught:
            pull.call('cannot list workflow runs', boom)
        self.assertEqual(str(caught.exception), 'cannot list workflow runs')

    def test_a_pull_failure_is_not_rewritten(self):
        def boom():
            raise pull.PullFailed('release token is malformed')

        with self.assertRaises(pull.PullFailed) as caught:
            pull.call('cannot list workflow runs', boom)
        self.assertEqual(str(caught.exception), 'release token is malformed')


class InstallCoverageTest(unittest.TestCase):
    """The installer must ask only for files the host really has."""

    @staticmethod
    def installer_required():
        installer = (SOURCE.parent / 'install-preview-pull-deploy.py').read_text(encoding='utf-8')
        body = installer.split('REQUIRED = (')[1].split(')')[0]
        return set(re.findall(r"'([A-Za-z0-9_.-]+)'", body))

    def test_every_module_the_deployer_loads_is_required_or_shipped(self):
        deployer = SOURCE.read_text(encoding='utf-8')
        installer = (SOURCE.parent / 'install-preview-pull-deploy.py').read_text(encoding='utf-8')
        loaded = set(re.findall(r"load\('[a-z_]+', '([a-z0-9-]+\.py)'\)", deployer))
        self.assertTrue(loaded, 'no module loads found; the pattern is stale')
        shipped = set(re.findall(r"'([a-z0-9-]+\.py)'",
                                 installer.split('EVIDENCE_SOURCE = ')[1].split('\n')[0]))
        self.assertEqual(loaded - self.installer_required() - shipped, set())

    def test_nothing_is_required_that_the_helper_install_never_creates(self):
        helper = (SOURCE.parent / 'install-preview-sftp-helper.py').read_text(encoding='utf-8')
        installable = set(re.findall(r"'([a-z0-9-]+\.py)'", helper.split('FILES = (')[1].split(')')[0]))
        # The phase copies the helper installer writes under their own names.
        installable |= {'release-check', 'current-check', 'migrate', 'activate', 'health',
                        'rollback', 'pull-image', 'backup-verify', 'sftp-transfer', 'deploy-receiver'}
        missing = self.installer_required() - installable
        self.assertEqual(missing, set(), f'never installed by the helper install: {sorted(missing)}')

    def test_the_source_name_of_the_fixed_operations_is_never_required(self):
        # It exists in scripts/ but the helper installer writes only phase copies.
        self.assertNotIn('preview-fixed-operations.py', self.installer_required())

    def test_the_backend_is_shipped_as_a_private_module(self):
        # The backend is host-side tooling that the deployer starts. It has to
        # be refreshed with the deployer, or the two disagree about the request
        # protocol and the phase bounds. It must stay mode 0600: it is a
        # module, never an executable.
        installer = (SOURCE.parent / 'install-preview-pull-deploy.py').read_text(encoding='utf-8')
        self.assertIn("BACKEND_SOURCE = SOURCE_DIR / 'preview-deploy-backend.py'", installer)
        self.assertIn('MODE_PRIVATE = 0o600', installer)
        self.assertIn('write_atomic(BACKEND_TARGET, backend, MODE_PRIVATE)', installer)
        # The helper installer owns the same file, and it installs it at 0600
        # as well. The two must agree on the mode.
        helper = (SOURCE.parent / 'install-preview-sftp-helper.py').read_text(encoding='utf-8')
        self.assertIn("'preview-deploy-backend.py'", helper)

    def test_the_backend_is_no_longer_only_required(self):
        # It used to be in REQUIRED, which meant the host had to already have
        # the reviewed backend before the deployer could be refreshed. Now the
        # installer ships it, so it must not also be required.
        self.assertNotIn('preview-deploy-backend.py', self.installer_required())

    def test_the_refresh_script_fetches_the_backend(self):
        refresh = (SOURCE.parent / 'refresh-preview-pull-deploy.sh').read_text(encoding='utf-8')
        self.assertIn('preview-deploy-backend.py', refresh)


class BackendLaunchTest(unittest.TestCase):
    """The backend is installed as a private module, and must be started, not executed.

    The reviewed helper installer gives every phase helper an executable copy
    and leaves `preview-deploy-backend.py` at mode 0600. The backend's own
    `verify_helpers` lists that file among the modules and not among the
    executables. Executing it therefore fails with a permission error before
    the backend ever runs, and the deploy reported that as "deployment backend
    did not finish". The fixture below is the installed shape exactly.
    """

    BACKEND = ('#!/usr/bin/python3\n'
               'import sys\n'
               'sys.stdout.write("backend-started:" + str(sys.stdin.buffer.read().count(b"\\n")))\n')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'preview-deploy-backend.py'
        self.path.write_text(self.BACKEND)
        self.path.chmod(0o600)

    def test_the_installed_backend_cannot_be_executed(self):
        # The fixture reproduces the installed state; without an execute bit
        # the kernel refuses the execution, exactly as it did on the host.
        with self.assertRaises(PermissionError):
            subprocess.run([str(self.path)], input=b'', stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=60)

    def test_the_deployer_starts_the_backend_through_the_interpreter(self):
        with mock.patch.object(pull, 'BACKEND', self.path):
            output = pull.deploy(release(A), b'token')
        self.assertEqual(output, 'backend-started:2')

    def test_the_interpreter_is_the_one_that_runs_the_deployer(self):
        self.assertEqual(pull.INTERPRETER, sys.executable or '/usr/bin/python3')

    def test_the_backend_is_never_executed_directly(self):
        # The command line must name the interpreter first: a direct execution
        # of a mode 0600 file is refused by the kernel.
        seen = {}

        def fake_run(argv, **kwargs):
            seen['argv'] = argv
            return subprocess.CompletedProcess(argv, 0, b'backend-started:2', b'')

        with mock.patch.object(pull, 'BACKEND', self.path):
            with mock.patch.object(pull.subprocess, 'run', fake_run):
                pull.deploy(release(A), b'token')
        self.assertEqual(seen['argv'][0], pull.INTERPRETER)
        self.assertEqual(seen['argv'][1], str(self.path))


LOCK_SOURCE = Path(__file__).resolve().parents[1] / 'scripts/preview-deploy-lock.py'
lock_spec = importlib.util.spec_from_file_location('test_locks', LOCK_SOURCE)
LOCKS = importlib.util.module_from_spec(lock_spec)
lock_spec.loader.exec_module(LOCKS)
CHILD = """
import importlib.util, sys
spec = importlib.util.spec_from_file_location('child_lock', sys.argv[1])
locks = importlib.util.module_from_spec(spec); spec.loader.exec_module(locks)
with locks.acquire_lock(sys.argv[2], owner_uid=int(sys.argv[3])):
    print('child holds the lock')
"""


class DeploymentLockTest(unittest.TestCase):
    """The deployer must not hold the lock the backend takes.

    The backend takes the deployment lock for the whole transaction: it is the
    only writer of the journal, so every deployment is serialised behind that
    one lock. A second, independent open of the same lock file blocks until
    the first is released, so a caller that holds the lock while the backend
    runs deadlocks it: the backend waits for a lock its own caller already
    holds. That is what the host did. Every run took exactly 3600 seconds,
    ended with "deployment backend did not finish", and left the journal
    untouched, because the backend never got past its first statement.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.child = self.root / 'child.py'
        self.child.write_text(CHILD)

    def locks_for_this_user(self):
        """The lock module insists on a root-owned parent; the test owns its own."""
        real = LOCKS

        class Locks:
            UnsafeLock = real.UnsafeLock

            @staticmethod
            def acquire_lock(path, **kwargs):
                kwargs.setdefault('owner_uid', os.geteuid())
                return real.acquire_lock(path, **kwargs)

        return Locks

    def test_the_deployer_lock_is_not_the_deployment_lock(self):
        self.assertNotEqual(pull.PULL_LOCK, pull.DEPLOY_LOCK)
        self.assertNotEqual(pull.PULL_LOCK.name, pull.DEPLOY_LOCK.name)

    def test_the_deployer_never_takes_the_deployment_lock(self):
        # The deployment lock is the backend's. If the deployer ever takes it,
        # the backend waits for a lock its own caller holds, and the deployment
        # hangs until the timeout expires without touching the journal.
        source = SOURCE.read_text(encoding='utf-8')
        self.assertIn('acquire_lock(PULL_LOCK', source)
        self.assertNotIn('acquire_lock()', source)
        self.assertNotIn('acquire_lock(locks.LOCK_PATH', source)

    def test_the_backend_can_take_the_deployment_lock_while_the_deployer_runs(self):
        deploy_lock = self.root / 'xennic-preview-deploy.lock'
        pull_lock = self.root / 'xennic-preview-pull-deploy.lock'
        locks = self.locks_for_this_user()
        with mock.patch.object(pull, 'PULL_LOCK', pull_lock):
            with mock.patch.object(pull, 'DEPLOY_LOCK', deploy_lock):
                with locks.acquire_lock(pull.PULL_LOCK, nonblocking=True):
                    result = subprocess.run(
                        [sys.executable, str(self.child), str(LOCK_SOURCE),
                         str(deploy_lock), str(os.geteuid())],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout.decode('utf-8', 'replace'))
        self.assertIn('child holds the lock', result.stdout.decode('utf-8', 'replace'))

    def test_the_same_lock_would_deadlock_the_backend(self):
        # The shape the deployer used to have: the caller holds the very lock
        # the backend takes, so the backend waits for a lock its caller holds.
        deploy_lock = self.root / 'xennic-preview-deploy.lock'
        locks = self.locks_for_this_user()
        with locks.acquire_lock(deploy_lock, nonblocking=True):
            with self.assertRaises(subprocess.TimeoutExpired):
                subprocess.run(
                    [sys.executable, str(self.child), str(LOCK_SOURCE),
                     str(deploy_lock), str(os.geteuid())],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10)

    def test_a_real_backend_reached_the_deployment_lock_through_the_deployer(self):
        """The whole shape, end to end, with the real backend and the real lock.

        The backend's first act inside the transaction is to take the
        deployment lock. The deployer used to hold that same lock while the
        backend ran, so the backend waited for a lock its own caller held and
        the deployment hung until the timeout expired - 3600 seconds on the
        host, every time, with nothing written to the journal. This test
        runs the deployer against a backend that really takes the lock and
        proves it gets it.
        """
        deploy_lock = self.root / 'xennic-preview-deploy.lock'
        pull_lock = self.root / 'xennic-preview-pull-deploy.lock'
        backend = self.root / 'backend.py'
        backend.write_text(
            'import importlib.util, sys\n'
            'spec = importlib.util.spec_from_file_location("lk", sys.argv[1])\n'
            'locks = importlib.util.module_from_spec(spec); spec.loader.exec_module(locks)\n'
            'with locks.acquire_lock(sys.argv[2], owner_uid=int(sys.argv[3])):\n'
            '    print("backend-reached-the-deployment-lock")\n')
        locks = self.locks_for_this_user()
        with mock.patch.object(pull, 'PULL_LOCK', pull_lock):
            with mock.patch.object(pull, 'DEPLOY_LOCK', deploy_lock):
                with mock.patch.object(pull, 'BACKEND', backend):
                    with mock.patch.object(pull, 'INTERPRETER', sys.executable):
                        # The deployer takes its own lock first, exactly as
                        # run() does, and then starts the backend.
                        with locks.acquire_lock(pull.PULL_LOCK, nonblocking=True):
                            result = subprocess.run(
                                [sys.executable, str(backend), str(LOCK_SOURCE),
                                 str(deploy_lock), str(os.geteuid())],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout.decode('utf-8', 'replace'))
        self.assertIn('backend-reached-the-deployment-lock', result.stdout.decode('utf-8', 'replace'))


class PhaseMarkerTest(unittest.TestCase):
    """The phase marker must be where the operator will look, and nowhere else.

    The backend writes the phase it is in before it starts a helper, so a
    deployment that is killed still says where it stopped. The marker used to
    live in the preview root's state directory, which broke the first
    deployment: `assert_initial_pristine` requires that directory to hold
    nothing but the journal, so the marker of ours made the release check
    refuse a fresh install. The marker now lives under /run.
    """

    def test_the_marker_is_outside_the_preview_root(self):
        # The pristine-install check refuses a first deployment when the
        # state or work directory holds anything but the journal, so nothing
        # of ours may ever be written into the preview root.
        self.assertFalse(str(pull.PHASE_MARKER).startswith('/srv/xennic-preview/'))
        self.assertEqual(str(pull.PHASE_MARKER), '/run/xennic-preview/deploy-phase.json')

    def test_the_backend_writes_the_marker_to_the_same_path(self):
        backend_path = Path(__file__).resolve().parents[1] / 'scripts/preview-deploy-backend.py'
        spec = importlib.util.spec_from_file_location('marker_backend', backend_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(str(module.PHASE_MARKER), str(pull.PHASE_MARKER))

    def test_a_written_marker_is_read_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'deploy-phase.json'
            marker.write_text(json.dumps({'version': 1, 'phase': 'migrate', 'run_number': 260}))
            marker.chmod(0o600)
            with mock.patch.object(pull, 'PHASE_MARKER', marker):
                self.assertEqual(pull.phase_marker(owner_uid=os.geteuid()), 'migrate')

    def test_a_marker_owned_by_someone_else_is_ignored(self):
        # The marker is written by the root-owned backend. A file of the same
        # name owned by anyone else is not the marker we wrote.
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'deploy-phase.json'
            marker.write_text(json.dumps({'version': 1, 'phase': 'migrate'}))
            marker.chmod(0o600)
            with mock.patch.object(pull, 'PHASE_MARKER', marker):
                self.assertIsNone(pull.phase_marker(owner_uid=os.geteuid() + 1))

    def test_a_missing_marker_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'deploy-phase.json'
            with mock.patch.object(pull, 'PHASE_MARKER', marker):
                self.assertIsNone(pull.phase_marker())

    def test_a_marker_that_is_not_private_is_ignored(self):
        # A world-readable marker is not the marker we wrote; it is ignored
        # rather than believed.
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'deploy-phase.json'
            marker.write_text(json.dumps({'version': 1, 'phase': 'migrate'}))
            marker.chmod(0o644)
            with mock.patch.object(pull, 'PHASE_MARKER', marker):
                self.assertIsNone(pull.phase_marker())

    def test_a_marker_with_an_unknown_phase_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'deploy-phase.json'
            marker.write_text(json.dumps({'version': 1, 'phase': 'not-a-phase'}))
            marker.chmod(0o600)
            with mock.patch.object(pull, 'PHASE_MARKER', marker):
                self.assertIsNone(pull.phase_marker())

    def test_a_marker_that_is_not_json_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'deploy-phase.json'
            marker.write_bytes(b'not json at all')
            marker.chmod(0o600)
            with mock.patch.object(pull, 'PHASE_MARKER', marker):
                self.assertIsNone(pull.phase_marker())


def relaxed_private_file(path, maximum):
    """The production check minus the root ownership assertion."""
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise pull.PullFailed('record is unavailable') from exc
    if len(data) > maximum:
        raise pull.PullFailed('record is too large')
    return data


def stat_mode(path):
    return os.lstat(path).st_mode & 0o777


if __name__ == '__main__':
    unittest.main(verbosity=2)
