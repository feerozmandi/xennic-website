#!/usr/bin/env python3
"""Unit checks for the bounded preview->apex edge switch; no server changes."""
import base64
import hashlib
import importlib.util
from pathlib import Path
import sys
import tomllib
import unittest

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


installer = load('installer_apex_test', REPO / 'scripts/install-preview-sftp-helper.py')
fixed = load('fixed_apex_test', REPO / 'scripts/preview-fixed-operations.py')


def oauth_config():
    return {
        'provider': 'github', 'email_domains': ['*'], 'scope': 'user:email',
        'reverse_proxy': True, 'trusted_proxy_ips': ['172.28.190.2/32'],
        'http_address': '0.0.0.0:4180',
        'redirect_url': 'https://preview.xennic.ir/oauth2/callback',
        'upstreams': ['static://202'], 'whitelist_domains': ['preview.xennic.ir'],
        'cookie_name': '__Host-preview_gate', 'cookie_secure': True,
        'cookie_httponly': True, 'cookie_samesite': 'lax',
        'cookie_expire': '8h', 'cookie_refresh': '0',
        'skip_jwt_bearer_tokens': False, 'skip_auth_preflight': False,
        'pass_basic_auth': False, 'pass_authorization_header': False,
        'set_authorization_header': False, 'pass_access_token': False,
        'set_xauthrequest': False, 'request_logging': False, 'auth_logging': False,
        'github_users': ['operator'], 'client_id': 'client-id-probe',
        'client_secret': 'client-secret-probe', 'cookie_secret': base64.b64encode(b'k' * 32).decode('ascii'),
    }


class CanonicalGatewayFileTest(unittest.TestCase):
    def test_switched_policy_is_accepted_only_for_the_apex(self):
        switched = oauth_config()
        switched['redirect_url'] = 'https://xennic.ir/oauth2/callback'
        switched['whitelist_domains'] = ['xennic.ir']
        raw = installer._canonical_toml(switched)
        self.assertEqual(tomllib.loads(raw.decode('ascii')), switched)
        fixed.validate_gateway_oauth(raw, '172.28.190.2', authority='xennic.ir')
        with self.assertRaises(fixed.Rejected):
            fixed.validate_gateway_oauth(raw, '172.28.190.2')

    def test_canonical_output_is_deterministic_and_rejects_other_types(self):
        config = oauth_config()
        self.assertEqual(installer._canonical_toml(config), installer._canonical_toml(dict(config)))
        for bad in ({'flag': None}, {'flag': 1.5}, {'flag': ['a', 1]}, {'flag': 'va\nlue'}):
            with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                installer._canonical_toml(bad)


class ExactReplaceTest(unittest.TestCase):
    def test_origin_switch_must_match_exactly_once(self):
        raw = b'A=1\nPREVIEW_ORIGIN=https://preview.xennic.ir\nB=2\n'
        switched = installer._exact_replace(
            raw, b'PREVIEW_ORIGIN=https://preview.xennic.ir', b'PREVIEW_ORIGIN=https://xennic.ir', 'origin')
        self.assertEqual(switched, b'A=1\nPREVIEW_ORIGIN=https://xennic.ir\nB=2\n')
        for bad in (b'A=1\n', raw + raw, b'PREVIEW_ORIGIN=https://preview.xennic.ir.evil\n',
                    b'X=1 PREVIEW_ORIGIN=https://preview.xennic.ir\n'):
            with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                installer._exact_replace(
                    bad, b'PREVIEW_ORIGIN=https://preview.xennic.ir', b'PREVIEW_ORIGIN=https://xennic.ir', 'origin')

    def test_only_the_two_reviewed_origins_are_accepted(self):
        self.assertEqual(installer.APEX_ORIGIN, ('https://preview.xennic.ir', 'https://xennic.ir'))
        for origin in ('https://www.xennic.ir', 'http://xennic.ir', 'https://xennic.ir.evil'):
            with self.subTest(origin=origin), self.assertRaises(fixed.Rejected):
                config = oauth_config()
                config['redirect_url'] = origin + '/oauth2/callback'
                config['whitelist_domains'] = [origin]
                installer._canonical_toml(config)
                fixed.validate_gateway_oauth(installer._canonical_toml(config), '172.28.190.2', authority='xennic.ir')


class ReviewedFileHashTest(unittest.TestCase):
    def test_switch_installs_only_the_pinned_reviewed_files(self):
        for source, (destination, expected) in installer.APEX_SOURCES.items():
            with self.subTest(source=source):
                digest = hashlib.sha256((REPO / 'config' / source).read_bytes()).hexdigest()
                self.assertEqual(digest, expected)
                self.assertIn(destination, ('Caddyfile', 'gateway.yml'))
                self.assertEqual(fixed.GATEWAY_FILES['xennic.ir']['config/' + destination], expected)
                self.assertNotEqual(installer.EDGE_PREVIEW[destination], expected)

    def test_installed_preview_files_match_the_reviewed_previous_version(self):
        for name, expected in installer.EDGE_PREVIEW.items():
            with self.subTest(name=name):
                source = 'preview-Caddyfile' if name == 'Caddyfile' else 'preview-gateway-compose.yml'
                self.assertEqual(hashlib.sha256((REPO / 'config' / source).read_bytes()).hexdigest(), expected)
                self.assertEqual(fixed.GATEWAY_FILES['preview.xennic.ir']['config/' + name], expected)

    def test_routes_and_helper_manifests_are_the_installed_versions(self):
        self.assertEqual(fixed.GATEWAY_FILES['xennic.ir']['config/routes.caddy'], installer.ACTIVATION_ROUTE_HASH)
        self.assertEqual(hashlib.sha256((REPO / 'config/routes.caddy').read_bytes()).hexdigest(),
                         installer.ACTIVATION_ROUTE_HASH)
        self.assertEqual(installer.APEX_MANIFEST, installer.ACTIVATION_MANIFEST)


if __name__ == '__main__':
    unittest.main()
