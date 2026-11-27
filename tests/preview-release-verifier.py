#!/usr/bin/env python3
"""Synthetic API responses test fail-closed evidence matching, not real GHCR."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock
import zipfile

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('verifier_tests', Path(__file__).resolve().parents[1] / 'scripts/preview-release-verifier.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.release = {'repository': 'feerozmandi/xennic-website', 'commit': 'a' * 40, 'digest': 'sha256:' + 'b' * 64, 'platform': 'linux/amd64', 'run_number': 4}
        self.run = {'id': 11, 'run_attempt': 1, 'run_number': 4, 'head_sha': 'a' * 40, 'head_branch': 'dev', 'event': 'push', 'status': 'completed', 'conclusion': 'success'}
        self.artifact = {'id': 22, 'name': 'xennic-preview-release-1', 'expired': False}
        self.evidence = {'version': 1, 'run_id': 11, 'run_attempt': 1, 'release': self.release}
        self.tags = [{'name': 'v1.2.3', 'commit': {'sha': 'a' * 40}}]

    def zip(self, evidence, filename='xennic-preview-release.json'):
        result = io.BytesIO()
        with zipfile.ZipFile(result, 'w') as z: z.writestr(filename, json.dumps(evidence))
        return result.getvalue()

    def api(self, path, actual):
        self.assertEqual(actual, b'synthetic-token')
        if '/workflows/' in path:
            return {'workflow_runs': [self.run]}
        if path.startswith('/tags'):
            return list(self.tags)
        return {'artifacts': [self.artifact]}

    def verify(self, token=b'synthetic-token'):
        with mock.patch.object(v, 'get_json', side_effect=self.api), mock.patch.object(v, 'request', return_value=self.zip(self.evidence)):
            return v.verify(self.release, token)

    def test_successful_matching_evidence(self):
        self.assertEqual(self.verify(), 11)

    def test_a_release_without_a_name_is_refused(self):
        self.tags = []
        with self.assertRaises(v.Unverified):
            self.verify()

    def test_a_release_with_two_names_is_refused(self):
        self.tags = [{'name': 'v1.2.3', 'commit': {'sha': 'a' * 40}},
                     {'name': 'v1.2.4', 'commit': {'sha': 'a' * 40}}]
        with self.assertRaises(v.Unverified):
            self.verify()

    def test_a_name_that_is_not_a_version_does_not_name_a_release(self):
        self.tags = [{'name': 'release-1', 'commit': {'sha': 'a' * 40}}]
        with self.assertRaises(v.Unverified):
            self.verify()

    def test_the_name_of_a_release_is_the_tag_that_carries_its_commit(self):
        with mock.patch.object(v, 'get_json', side_effect=self.api):
            self.assertEqual(v.release_version('a' * 40, b'synthetic-token'), 'v1.2.3')
            with self.assertRaises(v.Unverified):
                v.release_version('c' * 40, b'synthetic-token')

    def test_request_never_leaks_credentials(self):
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{}'
        with mock.patch.object(v.OPENER, 'open', return_value=response) as send:
            v.request(v.BASE + '/commits/dev', b'synthetic-token')
            self.assertEqual(send.call_args.args[0].get_header('Authorization'), 'Bearer synthetic-token')
        with self.assertRaises(v.Unverified): v.request('https://attacker.example/a', b'synthetic-token')
        with self.assertRaises(v.Unverified): v.request(v.BASE + '/commits/dev', None)

    def test_invalid_auth_has_no_anonymous_fallback(self):
        err = v.urllib.error.HTTPError(v.BASE + '/commits/dev', 401, 'denied', {}, None)
        with mock.patch.object(v.OPENER, 'open', side_effect=err) as send:
            with self.assertRaises(v.Unverified): v.request(v.BASE + '/commits/dev', b'invalid')
            send.assert_called_once()

    def test_artifact_redirect_never_forwards_credentials(self):
        artifact = v.BASE + '/actions/artifacts/22/zip'
        target = 'https://ci.blob.core.windows.net/artifact'
        redirect = v.urllib.error.HTTPError(artifact, 302, 'redirect', {'Location': target}, None)
        response = mock.MagicMock(); response.__enter__.return_value.read.return_value = b'zip'
        for token in (b'synthetic-token',):
            with self.subTest(token=token), mock.patch.object(v.OPENER, 'open', side_effect=[redirect, response]) as send:
                self.assertEqual(v.request(artifact, token), b'zip')
                self.assertIsNone(send.call_args_list[1].args[0].get_header('Authorization'))
        redirect = v.urllib.error.HTTPError(artifact, 302, 'redirect', {'Location': 'https://evil.example/'}, None)
        with mock.patch.object(v.OPENER, 'open', side_effect=redirect):
            with self.assertRaises(v.Unverified): v.request(artifact, b'synthetic-token')

    def test_unsuccessful_or_wrong_run_is_rejected(self):
        for key, value in [('conclusion', 'failure'), ('status', 'in_progress'), ('event', 'pull_request'),
                           ('head_branch', 'main'), ('head_sha', 'c' * 40), ('run_number', True)]:
            with self.subTest(key=key):
                original = self.run[key]; self.run[key] = value
                with self.assertRaises(v.Unverified): self.verify()
                self.run[key] = original

    def test_wrong_digest_and_expired_artifact_rejected(self):
        self.evidence = dict(self.evidence, release=dict(self.release, digest='sha256:' + 'c' * 64))
        with self.assertRaises(v.Unverified): self.verify()
        self.evidence = {'version': 1, 'run_id': 11, 'run_attempt': 1, 'release': self.release}
        self.artifact['expired'] = True
        with self.assertRaises(v.Unverified): self.verify()

    def test_wrong_artifact_filename_rejected(self):
        with mock.patch.object(v, 'get_json', side_effect=[{'workflow_runs': [self.run]}, {'artifacts': [self.artifact]}]), \
             mock.patch.object(v, 'request', return_value=self.zip(self.evidence, '../xennic-preview-release.json')):
            with self.assertRaises(v.Unverified): v.verify(self.release, b'synthetic-token')


if __name__ == '__main__': unittest.main()
