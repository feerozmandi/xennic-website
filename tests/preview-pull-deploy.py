#!/usr/bin/env python3
"""Tests for the pull deployer's decisions, without a host or a network.

Everything that decides *whether* to deploy is pure and covered here. The
transaction it then calls is the same guarded backend a human calls by hand, and
it is deliberately not re-implemented or mocked into "success".
"""
import importlib.util
import json
import os
from pathlib import Path
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
