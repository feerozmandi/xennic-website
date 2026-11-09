#!/usr/bin/env python3
"""Read-only topology checks; the real Compose/network path is tested separately in CI."""
import base64
import copy
import importlib.machinery
import json
import os
import stat
import importlib.util
from pathlib import Path
import sys
import hashlib
import tempfile
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

    def test_apex_requires_exact_callback_and_whitelist(self):
        config = oauth_config()
        config['redirect_url'] = 'https://xennic.ir/oauth2/callback'
        config['whitelist_domains'] = ['xennic.ir']
        fixed.validate_gateway_oauth(as_toml(config), '172.20.0.2', authority='xennic.ir')
        with self.assertRaises(fixed.Rejected):
            fixed.validate_gateway_oauth(as_toml(config), '172.20.0.2')
        for key, value in (
            ('redirect_url', 'https://preview.xennic.ir/oauth2/callback'),
            ('redirect_url', 'http://xennic.ir/oauth2/callback'),
            ('redirect_url', 'https://www.xennic.ir/oauth2/callback'),
            ('whitelist_domains', ['xennic.ir', 'preview.xennic.ir']),
            ('whitelist_domains', ['.xennic.ir']),
            ('cookie_secure', False), ('trusted_proxy_ips', ['0.0.0.0/0']),
            ('skip_auth_preflight', True), ('github_users', []),
        ):
            with self.subTest(key=key, value=value):
                bad = config.copy(); bad[key] = value
                with self.assertRaises(fixed.Rejected):
                    fixed.validate_gateway_oauth(as_toml(bad), '172.20.0.2', authority='xennic.ir')
        for authority in ('www.xennic.ir', 'xennic.ir.evil.example', '', None):
            with self.subTest(authority=authority), self.assertRaises(fixed.Rejected):
                fixed.validate_gateway_oauth(as_toml(config), '172.20.0.2', authority=authority)

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
                expected = fixed.INGRESS_CASES[len(seen) if mode == 'denied' else 0]
                if (method, path) != expected[:2] or headers != {
                    'Host': 'preview.xennic.ir', 'Authorization': 'Bearer invalid-probe',
                    'X-Forwarded-User': 'untrusted-probe', 'X-Auth-Request-User': 'untrusted-probe',
                }:
                    raise AssertionError('unexpected probe request or forged headers')
                seen.append((method, path)); self.path = path
            def getresponse(self): return Response(self.path)
            def close(self): pass
        with mock.patch.object(fixed.http.client, 'HTTPConnection', Connection), mock.patch.object(fixed.time, 'sleep'), \
                mock.patch.object(fixed, 'edge_authority', return_value='preview.xennic.ir'):
            if mode == 'denied':
                fixed.check_ingress_protection('172.20.0.3')
                self.assertEqual(seen, [(method, path) for method, path, _ in fixed.INGRESS_CASES])
            else:
                with self.assertRaises(fixed.Rejected): fixed.check_ingress_protection('172.20.0.3')

    def test_expected_denials_pass(self): self.run_probe('denied')

    def test_unprotected_outage_and_wrong_redirect_fail(self):
        for mode in ('open', 'down', 'bad-redirect'):
            with self.subTest(mode=mode): self.run_probe(mode)

    def test_probe_rejects_invalid_address_and_network_failure(self):
        for ip in ('127.0.0.1', '8.8.8.8', 'arbitrary;command'):
            with self.subTest(ip=ip), self.assertRaises(fixed.Rejected): fixed.check_ingress_protection(ip)
        with mock.patch.object(fixed.http.client, 'HTTPConnection', side_effect=OSError('connection failed')), \
                mock.patch.object(fixed.time, 'sleep'), \
                mock.patch.object(fixed, 'edge_authority', return_value='preview.xennic.ir'), \
                self.assertRaises(fixed.Rejected):
            fixed.check_ingress_protection('172.20.0.3')

    def test_verified_identity_is_used_for_ingress(self):
        release = {'digest': 'sha256:' + 'a' * 64}
        with mock.patch.object(fixed, 'config_for'), mock.patch.object(fixed, 'running_app_id', return_value='a' * 64), \
                mock.patch.object(fixed.healthcheck, 'check_once'), \
                mock.patch.object(fixed, 'require_verified_gateway', return_value='172.20.0.3'), \
                mock.patch.object(fixed, 'check_ingress_protection') as ingress:
            fixed.check_health(release)
            ingress.assert_called_once_with('172.20.0.3')

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


class EdgeAuthorityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'config').mkdir(mode=0o700)
        os.chmod(self.root, 0o700)
        self.addCleanup(self.tmp.cleanup)
        self.original = fixed.ROOT
        fixed.ROOT = self.root
        self.addCleanup(setattr, fixed, 'ROOT', self.original)
        # The strict ownership/mode checks of real staging files are covered by
        # the installed-chain tests; here only the reviewed-hash mapping and
        # the symlink/absence rejection are exercised with a same-owner file.

        def fake_read(root, relative, owner_uid, private=True):
            path = Path(root) / relative
            info = os.lstat(path)
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                raise fixed.ready.NotReady('unsafe test file')
            return path.read_bytes()

        patcher = mock.patch.object(fixed.ready, '_read', fake_read)
        patcher.start()
        self.addCleanup(patcher.stop)

    def install_caddy(self, content):
        path = self.root / 'config/Caddyfile'
        path.write_text(content)
        if path.is_symlink(): return hashlib.sha256(b'').hexdigest()
        os.chmod(path, 0o600)
        return hashlib.sha256(content.encode()).hexdigest()

    def use_reviewed(self, authority):
        content = {'preview.xennic.ir': 'preview edge\n', 'xennic.ir': 'apex edge\n'}[authority]
        digest = self.install_caddy(content)
        patched = {name: dict(files) for name, files in fixed.GATEWAY_FILES.items()}
        patched[authority]['config/Caddyfile'] = digest
        patcher = mock.patch.object(fixed, 'GATEWAY_FILES', patched)
        patcher.start()
        self.addCleanup(patcher.stop)
        return content

    def test_authority_is_derived_only_from_the_installed_file(self):
        for authority in ('preview.xennic.ir', 'xennic.ir'):
            with self.subTest(authority=authority):
                self.use_reviewed(authority)
                self.assertEqual(fixed.edge_authority(), authority)

    def test_unknown_or_unsafe_caddyfile_is_rejected(self):
        for content in ('unknown edge\n', ''):
            with self.subTest(content=content):
                self.install_caddy(content)
                with self.assertRaises(fixed.Rejected): fixed.edge_authority()
        (self.root / 'config/Caddyfile').unlink()
        (self.root / 'config/Caddyfile').symlink_to('/etc/passwd')
        with self.assertRaises(fixed.Rejected): fixed.edge_authority()

    def test_probe_cases_follow_the_installed_edge(self):
        apex = fixed._probe_cases('xennic.ir')
        self.assertEqual(apex, fixed.APEX_INGRESS_CASES)
        self.assertIn(('GET', '/', 'xennic.ir', 200), apex)
        self.assertIn(('GET', '/admin', 'xennic.ir', 302), apex)
        preview = fixed._probe_cases('preview.xennic.ir')
        self.assertEqual(preview, tuple((m, p, 'preview.xennic.ir', e) for m, p, e in fixed.INGRESS_CASES))


class ApexProbeTest(unittest.TestCase):
    def run_probe(self, mode, cases=None, host='172.20.0.3'):
        seen = []
        cases = cases or fixed.APEX_INGRESS_CASES
        class Response:
            def __init__(self, case):
                self.status = case[3]
                if mode == 'private-open' and case[1] == '/admin': self.status = 200
                if mode == 'gate-down' and case[1] == '/api/pages': self.status = 502
                if mode == 'public-down' and case[1] == '/' and case[0] == 'GET' and case[2] == 'xennic.ir': self.status = 503
                if mode == 'foreign-open' and case[2] == 'www.xennic.ir': self.status = 200
            def getheader(self, name):
                if name == 'Location':
                    return 'https://evil.example/' if mode == 'bad-redirect' else '/oauth2/sign_in'
                if name == 'Content-Type':
                    return 'application/json' if mode == 'bad-content' else 'text/html; charset=utf-8'
                return None
        class Connection:
            def __init__(self, peer, port, timeout):
                if (peer, port, timeout) != (host, 8080, 4): raise AssertionError('wrong peer')
            def request(self, method, path, headers):
                case = next(c for c in cases if c[:3] == (method, path, headers.get('Host')))
                if headers != {'Host': case[2], 'Authorization': 'Bearer invalid-probe',
                               'X-Forwarded-User': 'untrusted-probe', 'X-Auth-Request-User': 'untrusted-probe'}:
                    raise AssertionError('unexpected probe headers')
                seen.append(case); self.case = case
            def getresponse(self): return Response(self.case)
            def close(self): pass
        with mock.patch.object(fixed.http.client, 'HTTPConnection', Connection), \
                mock.patch.object(fixed.time, 'sleep'), \
                mock.patch.object(fixed, 'edge_authority', return_value='xennic.ir'), \
                mock.patch.object(fixed, '_probe_cases', return_value=cases):
            if mode == 'valid':
                fixed.check_ingress_protection(host)
                self.assertEqual(seen, list(cases))
            else:
                with self.assertRaises(fixed.Rejected): fixed.check_ingress_protection(host)

    def test_all_fixed_apex_cases(self): self.run_probe('valid')

    def test_public_private_outage_and_spoof_fail_closed(self):
        for mode in ('private-open', 'gate-down', 'public-down', 'foreign-open', 'bad-redirect', 'bad-content'):
            with self.subTest(mode=mode): self.run_probe(mode)

    def test_preview_edge_cases_still_use_the_preview_host(self):
        cases = tuple((m, p, 'preview.xennic.ir', e) for m, p, e in fixed.INGRESS_CASES)
        self.run_probe('valid', cases=cases)

    def test_peer_address_and_network_errors_are_rejected(self):
        for ip in ('127.0.0.1', '8.8.8.8', 'bad;command', None):
            with self.subTest(ip=ip), self.assertRaises(fixed.Rejected):
                fixed.check_ingress_protection(ip)
        with mock.patch.object(fixed.http.client, 'HTTPConnection', side_effect=OSError('offline')), \
                mock.patch.object(fixed.time, 'sleep'), \
                mock.patch.object(fixed, 'edge_authority', return_value='xennic.ir'), \
                mock.patch.object(fixed, '_probe_cases', return_value=fixed.APEX_INGRESS_CASES):
            with self.assertRaises(fixed.Rejected): fixed.check_ingress_protection('172.20.0.3')


if __name__ == '__main__': unittest.main()
