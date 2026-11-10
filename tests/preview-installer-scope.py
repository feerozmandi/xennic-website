#!/usr/bin/env python3
"""Unit checks for the reviewed gateway scope update; no server changes."""
import base64
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from unittest import mock

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


installer = load('installer_scope_test', REPO / 'scripts/install-preview-sftp-helper.py')
fixed = load('fixed_scope_test', REPO / 'scripts/preview-fixed-operations.py')


def policy(scope='user:email', authority='xennic.ir'):
    return {
        'provider': 'github', 'email_domains': ['*'], 'scope': scope,
        'reverse_proxy': True, 'trusted_proxy_ips': ['172.28.190.2/32'],
        'http_address': '0.0.0.0:4180',
        'redirect_url': f'https://{authority}/oauth2/callback',
        'upstreams': ['static://202'], 'whitelist_domains': [authority],
        'cookie_name': '__Host-preview_gate', 'cookie_secure': True,
        'cookie_httponly': True, 'cookie_samesite': 'lax',
        'cookie_expire': '8h', 'cookie_refresh': '0',
        'skip_jwt_bearer_tokens': False, 'skip_auth_preflight': False,
        'pass_basic_auth': False, 'pass_authorization_header': False,
        'set_authorization_header': False, 'pass_access_token': False,
        'set_xauthrequest': False, 'request_logging': False, 'auth_logging': False,
        'github_users': ['operator'], 'client_id': 'client-id-probe',
        'client_secret': 'client-secret-probe',
        'cookie_secret': base64.b64encode(b'k' * 32).decode('ascii'),
    }


class ReviewedPolicyTest(unittest.TestCase):
    def test_only_read_org_is_accepted(self):
        accepted = installer._canonical_toml(policy(scope='user:email read:org'))
        fixed.validate_gateway_oauth(accepted, '172.28.190.2', authority='xennic.ir')
        for scope in ('user:email', 'user:email read:org repo', 'repo'):
            with self.assertRaises(fixed.Rejected):
                fixed.validate_gateway_oauth(
                    installer._canonical_toml(policy(scope=scope)), '172.28.190.2', authority='xennic.ir')

    def test_candidate_manifest_matches_the_repository_helpers(self):
        lines = ''.join(
            f'{hashlib.sha256((REPO / "scripts" / name).read_bytes()).hexdigest()}  scripts/{name}\n'
            for name in installer.ACTIVATION_FILES)
        self.assertEqual(hashlib.sha256(lines.encode('ascii')).hexdigest(), installer.SCOPE_MANIFEST)
        self.assertNotEqual(installer.CURRENT_MANIFEST, installer.SCOPE_MANIFEST)


class ScopeTransitionTest(unittest.TestCase):
    def test_transition_changes_exactly_one_canonical_value(self):
        installed = installer._canonical_toml(policy())
        updated = installer._scope_transition(installed, fixed, 'xennic.ir')
        self.assertEqual(tomllib.loads(updated.decode('ascii'))['scope'], 'user:email read:org')
        self.assertEqual(installer._exact_replace(updated, installer.SCOPE_NEW, installer.SCOPE_OLD,
                                                  'gateway scope'), installed)
        self.assertEqual(updated.count(b'scope = '), 1)
        self.assertEqual(len(updated.split(b'\n')), len(installed.split(b'\n')))
        fixed.validate_gateway_oauth(updated, '172.28.190.2', authority='xennic.ir')

    def test_other_drift_is_rejected(self):
        drifted = policy()
        drifted['cookie_expire'] = '9h'
        with self.assertRaises(RuntimeError):
            installer._scope_transition(installer._canonical_toml(drifted), fixed, 'xennic.ir')

    def test_non_canonical_policy_is_rejected(self):
        raw = b'scope = "user:email"\n' + installer._canonical_toml(
            {key: value for key, value in policy().items() if key != 'scope'})
        with self.assertRaises(RuntimeError):
            installer._scope_transition(raw, fixed, 'xennic.ir')

    def test_already_updated_policy_is_rejected(self):
        with self.assertRaises(RuntimeError):
            installer._scope_transition(installer._canonical_toml(policy(scope='user:email read:org')),
                                        fixed, 'xennic.ir')

    def test_unreadable_policy_is_rejected(self):
        with self.assertRaises(RuntimeError):
            installer._scope_transition(b'not = [toml', fixed, 'xennic.ir')


class EdgeAuthorityTest(unittest.TestCase):
    def edge(self, digest):
        class FakeHash:
            def __init__(self, raw):
                self.raw = raw

            def hexdigest(self):
                return digest

        root = Path(tempfile.mkdtemp())
        (root / 'config').mkdir()
        with mock.patch.object(installer, 'ROOT', root), \
                mock.patch.object(installer, 'read_private', lambda path: b'edge'), \
                mock.patch.object(installer.hashlib, 'sha256', FakeHash):
            return installer._edge_authority()

    def test_both_reviewed_edges_are_mapped(self):
        self.assertEqual(self.edge(installer.APEX_SOURCES['apex-Caddyfile'][1]), 'xennic.ir')
        self.assertEqual(self.edge(installer.GATEWAY_FILES['Caddyfile'][1]), 'preview.xennic.ir')

    def test_unknown_edge_is_refused(self):
        with self.assertRaises(RuntimeError):
            self.edge('0' * 64)


if __name__ == '__main__':
    unittest.main(verbosity=2)
