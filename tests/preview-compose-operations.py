#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

sys.dont_write_bytecode = True
path = Path(__file__).resolve().parents[1] / 'scripts/preview-compose-operations.py'
spec = importlib.util.spec_from_file_location('preview_compose_ops', path)
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)


def release():
    return {'repository': 'feerozmandi/xennic-website', 'commit': 'a' * 40,
            'digest': 'sha256:' + 'b' * 64, 'platform': 'linux/amd64', 'run_number': 1}


class OperationsTest(unittest.TestCase):
    @mock.patch.object(ops.subprocess, 'run')
    def test_fixed_compose_operation_and_pinned_image(self, run):
        run.return_value = subprocess.CompletedProcess([], 0)
        ops.replace_app(release())
        args, kwargs = run.call_args.args, run.call_args.kwargs
        self.assertEqual(args[0], ops.COMPOSE + ['up', '-d', '--no-deps', '--no-build', '--force-recreate', '--wait', 'app'])
        self.assertEqual(kwargs['env']['PREVIEW_IMAGE'], 'ghcr.io/feerozmandi/xennic-website@' + release()['digest'])
        self.assertNotIn('DATABASE_URL', kwargs['env'])
        self.assertEqual(kwargs['stderr'], subprocess.DEVNULL)

    @mock.patch.object(ops.subprocess, 'run')
    def test_wrong_repo_or_digest_never_executes(self, run):
        for key, value in [('repository', 'evil/repo'), ('digest', 'latest'), ('commit', 'a' * 40 + ';id')]:
            r = release(); r[key] = value
            with self.assertRaises(ops.OperationFailed): ops.replace_app(r)
        run.assert_not_called()

    @mock.patch.object(ops.subprocess, 'run')
    def test_failure_is_redacted(self, run):
        run.return_value = subprocess.CompletedProcess([], 1)
        with self.assertRaises(ops.OperationFailed): ops.replace_app(release())


if __name__ == '__main__':
    unittest.main()
