#!/usr/bin/env python3
"""Offline checks only; no Docker, OAuth credentials or network required."""
import base64
import importlib.util
import os
import pty
import select
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import tomllib
import unittest

path = Path(__file__).resolve().parents[1] / 'scripts' / 'real-oauth-lab-config.py'
spec = importlib.util.spec_from_file_location('oauth_lab_config', path)
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


class OAuthConfigTest(unittest.TestCase):
    def setUp(self):
        self.key = base64.urlsafe_b64encode(b'x' * 32).decode('ascii')

    def test_render_roundtrip_and_policy(self):
        data = tomllib.loads(config.render_config('example-client', 'quote"\\test', '172.28.0.9', self.key))
        self.assertEqual(data['client_secret'], 'quote"\\test')
        self.assertEqual(data['scope'], 'user:email')
        self.assertEqual(data['github_users'], ['feerozmandi'])
        self.assertEqual(data['trusted_proxy_ips'], ['172.28.0.9/32'])
        self.assertEqual(data['redirect_url'], 'https://preview.xennic.ir/oauth2/callback')
        self.assertEqual(data['cookie_name'], '__Host-preview_gate')
        self.assertTrue(data['cookie_secure'])
        self.assertTrue(data['cookie_httponly'])
        self.assertFalse(data['skip_jwt_bearer_tokens'])
        self.assertFalse(data['request_logging'])
        self.assertFalse(data['auth_logging'])

    def test_reject_invalid_values(self):
        for cid, secret, ip in [('', 's', '172.28.0.9'), ('id', 'x\ny', '172.28.0.9'),
                                ('id', 's', '8.8.8.8'), ('id', 's', 'not-an-ip')]:
            with self.subTest(cid=cid, secret=secret, ip=ip):
                with self.assertRaises(ValueError):
                    config.render_config(cid, secret, ip, self.key)


class PromptTest(unittest.TestCase):
    def test_private_prompt_on_real_pty_does_not_echo(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'config.toml'
            pid, master = pty.fork()
            if pid == 0:
                os.execv(sys.executable, [sys.executable, str(path), str(target), '172.28.0.9'])
            output = bytearray()
            pending = [(b'Client ID (hidden): ', b'synthetic-client-id\n'),
                       (b'Client Secret (hidden): ', b'synthetic-client-secret\n')]
            deadline = time.monotonic() + 10
            status = None
            try:
                while time.monotonic() < deadline:
                    ready, _, _ = select.select([master], [], [], 0.1)
                    if ready:
                        try:
                            chunk = os.read(master, 8192)
                        except OSError:
                            chunk = b''
                        output.extend(chunk)
                        if pending and pending[0][0] in output:
                            _, reply = pending.pop(0)
                            os.write(master, reply)
                    done, wait_status = os.waitpid(pid, os.WNOHANG)
                    if done:
                        status = wait_status
                        while select.select([master], [], [], 0)[0]:
                            try:
                                output.extend(os.read(master, 8192))
                            except OSError:
                                break
                        break
                else:
                    self.fail('prompt test timed out')
                self.assertTrue(os.WIFEXITED(status))
                self.assertEqual(os.WEXITSTATUS(status), 0)
                self.assertFalse(pending)
                self.assertNotIn(b'synthetic-client-id', output)
                self.assertNotIn(b'synthetic-client-secret', output)
                self.assertIn(b'PASS: private OAuth configuration', output)
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)
                contents = tomllib.loads(target.read_text())
                self.assertEqual(contents['client_id'], 'synthetic-client-id')
                self.assertEqual(contents['client_secret'], 'synthetic-client-secret')
            finally:
                if status is None:
                    try:
                        os.kill(pid, signal.SIGKILL)
                        os.waitpid(pid, 0)
                    except (ChildProcessError, ProcessLookupError):
                        pass
                os.close(master)

    def test_no_controlling_terminal_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'config.toml'
            result = subprocess.run([sys.executable, str(path), str(target), '172.28.0.9'],
                                    stdin=subprocess.DEVNULL, capture_output=True,
                                    start_new_session=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(target.exists())
            self.assertIn(b'STOP:', result.stderr)


if __name__ == '__main__':
    unittest.main()
