#!/usr/bin/env python3
"""Offline checks only; no Docker, OAuth credentials or network required."""
import base64
import importlib.util
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


if __name__ == '__main__':
    unittest.main()
