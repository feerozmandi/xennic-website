#!/usr/bin/env python3
"""Offline restart tests against the pinned historical handoff; no Docker."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('verify_oauth_resume', root / 'scripts/verify-real-oauth-resume.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class RestartTailTest(unittest.TestCase):
    def setUp(self):
        result = subprocess.run(['git', '-C', str(root), 'show',
                                 'c619bcf550cb58933268f93ed32174289e2f284b:scripts/real-oauth-local-lab.sh'],
                                capture_output=True, text=True)
        if result.returncode:
            self.skipTest('pinned historical handoff is not available in this checkout')
        self.original = result.stdout
        self.tail = verifier.restart_tail(self.original)

    def test_pinned_tail_is_valid_and_does_not_overwrite_ca_or_repeat_seed(self):
        subprocess.run(['bash', '-n'], input=self.tail, text=True, check=True)
        self.assertNotIn('preview:migrate', self.tail)
        self.assertNotIn('preview:seed', self.tail)
        self.assertNotIn('root.crt" "$ROOT/lab-root.crt"', self.tail)
        self.assertIn('cmp -s -- "$ROOT/lab-root.crt" "$CA_CHECK"', self.tail)
        self.assertIn('read -r < /dev/tty', self.tail)
        self.assertNotIn('wait "$FIREFOX_PID"', self.tail)
        self.assertNotIn('rm -rf', (root / 'scripts/restart-real-oauth-local-lab.sh').read_text())

    def test_ca_mismatch_stops_before_credentials_and_keeps_retained_file(self):
        section = self.tail.split("step='verify retained local CA against the Caddy data volume'\n", 1)[1]
        section = section.split("step='create local OAuth config via hidden terminal prompts'\n", 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            ca = Path(directory) / 'lab-root.crt'
            ca.write_text('synthetic trusted CA')
            check = Path(directory) / 'ca-check'
            check.touch()
            shell = 'set -e\ndocker() { printf "%s" "$FAKE_CA" > "$3"; }\n' + section
            for fake_ca, expected in [('synthetic trusted CA', 0), ('different CA', 1)]:
                with self.subTest(expected=expected):
                    env = dict(os.environ, ROOT=directory, CA_CHECK=str(check), caddy_id='fake', FAKE_CA=fake_ca)
                    result = subprocess.run(['bash', '-c', shell], env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, expected)
                    self.assertEqual(ca.read_text(), 'synthetic trusted CA')

    def test_changed_anchor_is_rejected(self):
        altered = self.original.replace("step='create local OAuth config via hidden terminal prompts'",
                                        "step='unexpected'")
        with self.assertRaises(ValueError):
            verifier.restart_tail(altered)


if __name__ == '__main__':
    unittest.main()
