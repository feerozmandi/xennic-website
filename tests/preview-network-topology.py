#!/usr/bin/env python3
"""Read-only topology checks; the real Compose/network path is tested separately in CI."""
import base64
import copy
import importlib.machinery
import json
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

sys.dont_write_bytecode = True
path = Path(__file__).resolve().parents[1] / 'scripts/preview-fixed-operations.py'
spec = importlib.util.spec_from_file_location('fixed_network_test', path)
fixed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixed)


def valid():
    return {'services': {
        'app': {'image': 'ghcr.io/feerozmandi/xennic-website@sha256:' + 'a' * 64,
                'pull_policy': 'never', 'networks': {'default': {}, 'gateway': {}},
                'volumes': [{'type': 'volume', 'source': 'preview_media', 'target': '/app/media'}]},
        'postgres': {'image': 'postgres:16.14-bookworm', 'networks': {'default': {}},
                     'volumes': [{'type': 'volume', 'source': 'preview_db', 'target': '/var/lib/postgresql/data'}]},
    }, 'volumes': {k: {'name': 'xennic-preview_' + k} for k in ('preview_db', 'preview_media')},
        'networks': {k: {'name': 'xennic-preview_' + k, 'internal': True} for k in ('default', 'gateway')}}


class TopologyTest(unittest.TestCase):
    def test_exact_isolated_stack(self):
        fixed.validate_topology(valid())

    def test_exposed_or_unrecognized_resources_rejected(self):
        for mutation in (
            lambda x: x['services']['app'].update(ports=[{'host_ip': '127.0.0.1', 'published': '3000'}]),
            lambda x: x['services']['postgres'].update(ports=[{'published': '5432'}]),
            lambda x: x['services']['postgres']['networks'].update(gateway={}),
            lambda x: x['services']['app']['networks'].update(untrusted={}),
            lambda x: x['services']['app'].update(network_mode='host'),
            lambda x: x['services']['app'].update(privileged=True),
            lambda x: x['services'].update(gate={}),
            lambda x: x['networks']['gateway'].update(internal=False),
            lambda x: x['networks']['default'].update(external=True),
            lambda x: x['networks']['gateway'].update(name='other-project'),
            lambda x: x['volumes']['preview_db'].update(external=True),
        ):
            with self.subTest(mutation=mutation):
                config = valid(); mutation(config)
                with self.assertRaises(fixed.Rejected): fixed.validate_topology(config)


def oauth_config():
    values = {
        'provider': 'github', 'email_domains': ['*'], 'scope': 'user:email',
        'reverse_proxy': True, 'trusted_proxy_ips': ['172.20.0.2/32'],
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
        'github_users': ['Example-User', 'Another1'], 'client_id': 'ci-client',
        'client_secret': 'ci-secret', 'cookie_secret': base64.urlsafe_b64encode(b'x' * 32).decode(),
    }
    return values


def as_toml(values):
    # JSON literals for these simple string/list/bool fields are valid TOML.
    return ''.join(f'{key} = {json.dumps(value)}\n' for key, value in values.items()).encode()


class GatewayOptionsTest(unittest.TestCase):
    def test_reviewed_options_and_expandable_allowlist(self):
        fixed.validate_gateway_oauth(as_toml(oauth_config()), '172.20.0.2')

    def test_reject_unsafe_or_unknown_options(self):
        for key, value in (
            ('cookie_expire', '4h'), ('cookie_secure', False), ('github_users', []),
            ('github_users', ['user', 'USER']), ('github_users', ['bad--name']),
            ('scope', 'user:email read:org'), ('trusted_proxy_ips', ['0.0.0.0/0']),
            ('skip_auth_preflight', True), ('cookie_secret', 'bad'),
            ('upstreams', ['http://app:3000']), ('skip_auth_routes', ['.*']),
            ('client_secret', ''), ('redirect_url', 'http://preview.xennic.ir/oauth2/callback'),
        ):
            with self.subTest(key=key, value=value):
                config = oauth_config(); config[key] = value
                with self.assertRaises(fixed.Rejected):
                    fixed.validate_gateway_oauth(as_toml(config), '172.20.0.2')

    def test_peer_address_cannot_be_selected_by_config(self):
        with self.assertRaises(fixed.Rejected):
            fixed.validate_gateway_oauth(as_toml(oauth_config()), '172.20.0.3')
        with self.assertRaises(fixed.Rejected):
            fixed.validate_gateway_oauth(as_toml(oauth_config()), '127.0.0.1')


class IngressProbeTest(unittest.TestCase):
    def run_probe(self, mode):
        seen = []
        class Response:
            def __init__(self, path):
                self.status = 200 if mode == 'open' else 502 if mode == 'down' else 401 if path.startswith('/api/') else 302
            def getheader(self, name):
                return 'https://evil.example/' if mode == 'bad-redirect' else '/oauth2/sign_in'
        class Connection:
            def __init__(self, host, port, timeout):
                if (host, port, timeout) != ('172.20.0.3', 8080, 4): raise AssertionError('wrong peer')
            def request(self, method, path, headers):
                if headers.get('Host') != 'preview.xennic.ir' or 'Cookie' in headers:
                    raise AssertionError('unsafe probe')
                seen.append((method, path)); self.path = path
            def getresponse(self): return Response(self.path)
            def close(self): pass
        with mock.patch.object(fixed.http.client, 'HTTPConnection', Connection), mock.patch.object(fixed.time, 'sleep'):
            if mode == 'denied':
                fixed.check_ingress_protection('172.20.0.3')
                self.assertEqual(seen, [(method, path) for method, path, _ in fixed.INGRESS_CASES])
            else:
                with self.assertRaises(fixed.Rejected): fixed.check_ingress_protection('172.20.0.3')

    def test_expected_denials_pass(self): self.run_probe('denied')

    def test_unprotected_outage_and_wrong_redirect_fail(self):
        for mode in ('open', 'down', 'bad-redirect'):
            with self.subTest(mode=mode): self.run_probe(mode)

    def test_probe_rejects_invalid_address(self):
        with self.assertRaises(fixed.Rejected): fixed.check_ingress_protection('127.0.0.1')

    def test_internal_health_cannot_substitute_for_gateway_identity(self):
        release = {'digest': 'sha256:' + 'a' * 64}
        with mock.patch.object(fixed, 'config_for'), mock.patch.object(fixed, 'running_app_id', return_value='a' * 64), \
                mock.patch.object(fixed.healthcheck, 'check_once') as internal, \
                mock.patch.object(fixed, 'require_verified_gateway', side_effect=fixed.Rejected('identity')) as identity, \
                mock.patch.object(fixed, 'check_ingress_protection') as ingress:
            with self.assertRaises(fixed.Rejected):
                fixed.check_health(release)
            internal.assert_called_once_with()
            identity.assert_called_once_with('a' * 64)
            ingress.assert_not_called()


if __name__ == '__main__': unittest.main()
