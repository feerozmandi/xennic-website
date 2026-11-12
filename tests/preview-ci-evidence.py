#!/usr/bin/env python3
"""Tests for binding a release artifact to the deploying workflow run."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('preview_ci_evidence', ROOT / 'scripts/preview-ci-evidence.py')
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)

COMMIT = '42950e6035377b84bf271b1b7986e5895d53561d'
DIGEST = 'sha256:' + 'a' * 64


def artifact(**changes):
    data = {'version': 1, 'run_id': 43202237982, 'run_attempt': 1,
            'release': {'repository': 'feerozmandi/xennic-website', 'commit': COMMIT, 'run_number': 234,
                        'digest': DIGEST, 'platform': 'linux/amd64'}}
    data.update(changes)
    return data


class EvidenceTest(unittest.TestCase):
    def test_accepts_matching_evidence(self):
        release = evidence.check(artifact(), 43202237982, COMMIT, 234)
        self.assertEqual(release['commit'], COMMIT)
        self.assertEqual(json.loads(evidence.manifest_line(release)), release)
        self.assertEqual(evidence.manifest_line(release).count(' '), 0)

    def test_rejects_foreign_or_malformed_evidence(self):
        cases = [
            (artifact(), 1, COMMIT, 234),
            (artifact(version=2), 43202237982, COMMIT, 234),
            (artifact(run_attempt=0), 43202237982, COMMIT, 234),
            (artifact(run_attempt='1'), 43202237982, COMMIT, 234),
            (artifact(release=dict(artifact()['release'], commit='0' * 40)), 43202237982, COMMIT, 234),
            (artifact(release=dict(artifact()['release'], run_number=235)), 43202237982, COMMIT, 234),
            (artifact(release=dict(artifact()['release'], digest='sha256:abc')), 43202237982, COMMIT, 234),
            (artifact(extra=1), 43202237982, COMMIT, 234),
            ({}, 43202237982, COMMIT, 234),
            ('nope', 43202237982, COMMIT, 234),
        ]
        for data, run_id, commit, run_number in cases:
            with self.assertRaises(evidence.EvidenceError):
                evidence.check(data, run_id, commit, run_number)

    def test_cli_writes_one_manifest_line(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/preview-ci-evidence.py'),
                                 '--run-id', '43202237982', '--commit', COMMIT, '--run-number', '234'],
                                input=json.dumps(artifact()).encode(), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['run_number'], 234)
        self.assertEqual(result.stdout.count(b'\n'), 1)

    def test_cli_refuses_mismatch_and_bad_arguments(self):
        broken = subprocess.run([sys.executable, str(ROOT / 'scripts/preview-ci-evidence.py'),
                                 '--run-id', '1', '--commit', COMMIT, '--run-number', '234'],
                                input=json.dumps(artifact()).encode(), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, check=False)
        self.assertEqual(broken.returncode, 2)
        self.assertEqual(broken.stdout, b'')
        for argv in (['--run-id', '1'], ['--commit', COMMIT, '--run-id', '1', '--run-id', '2', '--run-number', '1']):
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/preview-ci-evidence.py')] + argv,
                                    input=b'{}', stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(result.returncode, 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
