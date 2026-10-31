#!/usr/bin/env python3
"""Offline tests: synthetic data only, no Docker, credentials or network."""
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'scripts' / 'diagnose-real-oauth-callback.py'
spec = importlib.util.spec_from_file_location('diagnose_oauth', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ClassificationTest(unittest.TestCase):
    def test_known_classes_are_fixed_and_do_not_echo_input(self):
        cases = [
            (b'Error while parsing OAuth2 callback: secret', 'CALLBACK_PARSE_OR_PROVIDER_ERROR'),
            (b'Error while parsing OAuth2 state: secret', 'STATE_ERROR'),
            (b'Error redeeming code during OAuth2 callback: secret', 'CODE_REDEMPTION_ERROR'),
            (b'Error creating session during OAuth2 callback: unexpected status "403": secret',
             'SESSION_ENRICHMENT_ERROR UPSTREAM_HTTP_403'),
            (b'Error creating session during OAuth2 callback: missing github user',
             'SESSION_ENRICHMENT_ERROR ACCOUNT_NOT_ALLOWED'),
            (b'Error saving session state for secret: secret', 'SESSION_SAVE_ERROR'),
            (b'Error with authorization: secret', 'AUTHORIZATION_ERROR'),
        ]
        for line, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(module.classify(line), 'DIAGNOSIS: ' + expected)
                self.assertNotIn('secret', module.classify(line))

    def test_unknown_and_untrusted_status_are_not_reflected(self):
        self.assertIsNone(module.classify(b'access token or callback URL secret'))
        result = module.classify(b'Error creating session during OAuth2 callback: secret unexpected status "403": secret')
        self.assertEqual(result, 'DIAGNOSIS: SESSION_ENRICHMENT_ERROR')
        self.assertNotIn('secret', result)


class SyntheticStreamTest(unittest.TestCase):
    def test_stream_never_exposes_raw_synthetic_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / 'docker'
            fake.write_text("""#!/usr/bin/python3
import sys, time
args = sys.argv[1:]
if args[0] == 'ps':
    print('123456789abc')
elif args[0] == 'inspect':
    print('true xennic-real-oauth-73c028764aa6 gate none quay.io/oauth2-proxy/oauth2-proxy:v7.15.5@sha256:8498b0d0ef0a7b29686414000a08aee467f02d0299c9ed1e006a8f33fc017916')
elif args[0] == 'attach':
    assert args[1:] == ['--no-stdin', '--sig-proxy=false', '123456789abc']
    print('unclassified synthetic-private-token', flush=True)
    print('Error creating session during OAuth2 callback: unexpected status "403": synthetic-private-body', flush=True)
    time.sleep(20)
else:
    raise SystemExit(1)
""")
            fake.chmod(0o700)
            env = dict(os.environ, PATH=directory + ':' + os.environ['PATH'], DOCKER_HOST='unix:///synthetic')
            env.pop('DOCKER_CONTEXT', None)
            result = subprocess.run([sys.executable, str(path)], env=env, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            self.assertEqual(result.returncode, 0)
            self.assertIn(b'DIAGNOSIS: SESSION_ENRICHMENT_ERROR UPSTREAM_HTTP_403', result.stdout)
            self.assertNotIn(b'synthetic-private', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
