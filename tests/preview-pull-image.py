#!/usr/bin/env python3
"""Unit checks for the fixed pull helper; no Docker or credentials are used."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import sys

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('pull_test', Path(__file__).resolve().parents[1] / 'scripts/preview-pull-image.py')
pull = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pull)

class PullTest(unittest.TestCase):
    def setUp(self):
        self.release = {'repository': 'feerozmandi/xennic-website', 'commit': 'a' * 40,
                        'run_number': 1, 'digest': 'sha256:' + 'b' * 64, 'platform': 'linux/amd64'}
        self.raw = json.dumps(self.release).encode()
        self.reference = 'ghcr.io/feerozmandi/xennic-website@' + self.release['digest']
        self.image = [{'Os': 'linux', 'Architecture': 'amd64', 'Id': 'sha256:' + 'c' * 64,
                       'RepoDigests': [self.reference]}]
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def exercise(self, token, fail_login=False):
        commands = []
        def run(args, env, data=None, capture=False):
            commands.append((args, data))
            if args[1] == 'login' and fail_login: raise pull.PullFailed('denied')
            return json.dumps(self.image).encode() if capture else b''
        with mock.patch.object(pull.os, 'geteuid', return_value=0), \
                mock.patch.object(pull, 'private_runtime'), \
                mock.patch.object(pull, 'RUNTIME', Path(self.temp.name)), \
                mock.patch.object(pull, 'run', side_effect=run):
            if fail_login:
                with self.assertRaises(pull.PullFailed): pull.pull(self.raw, token)
            else:
                self.assertEqual(pull.pull(self.raw, token), 'sha256:' + 'c' * 64)
        return commands

    def test_explicit_public_pull_uses_no_login(self):
        commands = self.exercise(pull.PUBLIC_READ)
        self.assertEqual([c[0][1] for c in commands], ['pull', 'image'])
        self.assertEqual(commands[0][0][-1], self.reference)

    def test_credentials_failure_never_falls_back_to_public(self):
        commands = self.exercise(b'invalid-test-token', fail_login=True)
        self.assertEqual([c[0][1] for c in commands], ['login'])

    def test_authenticated_path_still_logs_in(self):
        commands = self.exercise(b'synthetic-test-token')
        self.assertEqual([c[0][1] for c in commands], ['login', 'pull', 'image'])

if __name__ == '__main__': unittest.main()
