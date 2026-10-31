#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('evidence', Path(__file__).resolve().parents[1] / 'scripts/preview-release-evidence.py')
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


class EvidenceTest(unittest.TestCase):
    def setUp(self):
        self.env = {'GITHUB_REPOSITORY': 'feerozmandi/xennic-website', 'GITHUB_REF': 'refs/heads/dev',
                    'GITHUB_EVENT_NAME': 'push', 'GITHUB_RUN_ID': '123', 'GITHUB_RUN_NUMBER': '5',
                    'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_SHA': 'a' * 40, 'IMAGE_DIGEST': 'sha256:' + 'b' * 64}

    def test_record_binds_run_commit_digest_and_architecture(self):
        actual = evidence.record(self.env)
        self.assertEqual(actual['run_id'], 123)
        self.assertEqual(actual['run_attempt'], 1)
        self.assertEqual(actual['release']['run_number'], 5)
        self.assertEqual(actual['release']['commit'], self.env['GITHUB_SHA'])
        self.assertEqual(actual['release']['digest'], self.env['IMAGE_DIGEST'])
        self.assertEqual(actual['release']['platform'], 'linux/amd64')

    def test_untrusted_event_repo_or_digest_rejected(self):
        for field, value in [('GITHUB_REF', 'refs/heads/main'), ('GITHUB_EVENT_NAME', 'pull_request'),
                             ('GITHUB_REPOSITORY', 'other/repo'), ('IMAGE_DIGEST', 'latest'),
                             ('GITHUB_SHA', 'bad'), ('GITHUB_RUN_ID', '0'), ('GITHUB_RUN_ATTEMPT', '-1')]:
            env = dict(self.env, **{field: value})
            with self.subTest(field=field), self.assertRaises(ValueError): evidence.record(env)


if __name__ == '__main__': unittest.main()
