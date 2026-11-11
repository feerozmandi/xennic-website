#!/usr/bin/env python3
"""Unit checks for the bounded preview->apex edge switch; no server changes."""
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


installer = load('installer_apex_test', REPO / 'scripts/install-preview-sftp-helper.py')
fixed = load('fixed_apex_test', REPO / 'scripts/preview-fixed-operations.py')
readiness = load('readiness_apex_test', REPO / 'scripts/preview-deploy-readiness.py')


def oauth_config():
    return {
        'provider': 'github', 'email_domains': ['*'], 'scope': 'user:email read:org',
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


class ModuleLoadTest(unittest.TestCase):
    def test_installed_alias_without_suffix_can_be_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'release-check'
            path.write_text('VALUE = 41\n')
            self.assertEqual(installer.module(path, 'probe_alias').VALUE, 41)
            other = Path(directory) / 'preview-deploy-lock.py'
            other.write_text('VALUE = 7\n')
            self.assertEqual(installer.module(other, 'probe_module').VALUE, 7)

    def test_missing_helper_module_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises((OSError, RuntimeError)):
                installer.module(Path(directory) / 'missing', 'probe_missing')


class ReviewedFileHashTest(unittest.TestCase):
    def test_switch_installs_only_the_pinned_reviewed_files(self):
        for source, (destination, expected) in installer.APEX_SOURCES.items():
            with self.subTest(source=source):
                digest = hashlib.sha256((REPO / 'config' / source).read_bytes()).hexdigest()
                self.assertEqual(digest, expected)
                self.assertEqual(installer.APEX_FILES[destination][1], destination)
                reviewed = fixed.GATEWAY_FILES['xennic.ir']['config/' + destination]
                accepted = (reviewed,) if isinstance(reviewed, str) else reviewed
                self.assertIn(expected, accepted)
                self.assertNotEqual(installer.EDGE_PREVIEW[destination], expected)

    def test_installed_preview_files_match_the_reviewed_previous_version(self):
        # Caddyfile/gateway.yml are unchanged from the installed preview release;
        # routes are the older version without the public apex allowlist.
        for name, source in (('Caddyfile', 'preview-Caddyfile'),
                             ('gateway.yml', 'preview-gateway-compose.yml')):
            with self.subTest(name=name):
                digest = hashlib.sha256((REPO / 'config' / source).read_bytes()).hexdigest()
                self.assertEqual(digest, installer.EDGE_PREVIEW[name])
                self.assertEqual(fixed.GATEWAY_FILES['preview.xennic.ir']['config/' + name], digest)
        self.assertNotEqual(installer.EDGE_PREVIEW['routes.caddy'], installer.ACTIVATION_ROUTE_HASH)
        self.assertEqual(hashlib.sha256((REPO / 'config/routes.caddy').read_bytes()).hexdigest(),
                         installer.ACTIVATION_ROUTE_HASH)

    def test_routes_and_helper_manifests_are_the_installed_versions(self):
        reviewed = fixed.GATEWAY_FILES['xennic.ir']['config/routes.caddy']
        accepted = (reviewed,) if isinstance(reviewed, str) else reviewed
        self.assertIn(installer.ACTIVATION_ROUTE_HASH, accepted)
        self.assertEqual(hashlib.sha256((REPO / 'config/routes.caddy').read_bytes()).hexdigest(),
                         installer.ACTIVATION_ROUTE_HASH)
        # The live edge still runs the previous routes file, so the window keeps
        # accepting it until the replacement is installed and confirmed.
        self.assertEqual(accepted, (fixed.ROUTES_INSTALLED, installer.ACTIVATION_ROUTE_HASH))
        self.assertEqual(installer.APEX_MANIFEST, installer.ACTIVATION_MANIFEST)


class TransitionSimulationTest(unittest.TestCase):
    """Exercise the real switch/rollback logic against a same-owner fake root."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.root = self.base / 'root'
        self.target = self.base / 'libexec'
        self.source = self.base / 'install'
        self.incoming = self.source / 'incoming-apex'
        for directory in (self.root / 'config', self.root / 'secrets', self.root / 'state',
                          self.root / 'work', self.target, self.incoming):
            directory.mkdir(parents=True, exist_ok=True)
        for name in installer.ACTIVATION_FILES:
            (self.incoming / name).write_bytes((REPO / 'scripts' / name).read_bytes())
            (self.source / name).write_bytes((REPO / 'scripts' / name).read_bytes())
        for source in installer.APEX_SOURCES:
            (self.incoming / source).write_bytes((REPO / 'config' / source).read_bytes())
        (self.source / 'install-preview-sftp-helper.py').write_bytes(b'installer')
        (self.incoming / 'install-preview-sftp-helper.py').write_bytes(b'installer')
        self.oauth = installer._canonical_toml(oauth_config())
        self.env = b'A=1\nPREVIEW_ORIGIN=https://preview.xennic.ir\nB=2\n'
        for name, raw in (('Caddyfile', b'preview edge\n'), ('gateway.yml', b'preview gateway\n'),
                          ('routes.caddy', b'preview routes\n')):
            (self.root / 'config' / name).write_bytes(raw)
        (self.root / 'secrets/oauth2-proxy.cfg').write_bytes(self.oauth)
        (self.root / 'secrets/preview.env').write_bytes(self.env)
        self.prior = {}
        for name in installer.ACTIVATION_FILES:
            if name == 'preview-deploy-receiver.py':
                continue
            raw = ('prior-' + name).encode()
            for installed in installer.EXECUTABLES.get(name, (name,)):
                (self.target / installed).write_bytes(raw)
            self.prior[name] = hashlib.sha256(raw).hexdigest()
        self.patches = [
            mock.patch.multiple(installer, ROOT=self.root, TARGET=self.target, SOURCE=self.source,
                                PARENT=self.base, INCOMING_APEX=self.incoming,
                                NEW_DIR=self.base / '.update', BACKUP_APEX=self.base / '.before-apex',
                                APEX_STATE=self.root / 'config/.apex-before',
                                PRIOR_HELPERS={k: self.prior[k] for k in self.prior if k != 'preview-deploy-receiver.py'}),
            mock.patch.object(installer, 'check_dir', lambda path: None),
            mock.patch.object(installer, 'private_dir', lambda path: None),
            mock.patch.object(installer, 'read_private', lambda path: Path(path).read_bytes()),
            mock.patch.object(installer, 'write_exclusive',
                              lambda path, data, mode=0o600: Path(path).write_bytes(data)),
            mock.patch.object(installer, 'sync_dir', lambda path: None),
            mock.patch.object(installer, 'sync_parent', lambda: None),
            mock.patch.object(installer, 'verified_sources',
                              lambda directory, expected, files=installer.FILES: {
                                  name: (Path(directory) / name).read_bytes() for name in files}),
            mock.patch.object(installer, 'installed_matches', lambda directory, data: None),
            mock.patch.object(installer, 'module', self.fake_module),
            mock.patch.object(installer, 'verify_backend', lambda: None),
        ]
        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        # The fake prior differs from the reviewed digests, so the pinned table
        # is aligned per test run; the real table is checked separately above.
        self.prior_expected = {name: digest for name, digest in self.prior.items()
                               if name != 'preview-deploy-receiver.py'}
        for patch in (mock.patch.object(installer, 'PRIOR_HELPERS', self.prior_expected),
                      # Test-only stand-ins; the real reviewed tables are checked
                      # by RecommendedFileHashTest above.
                      mock.patch.object(installer, 'EDGE_PREVIEW', {
                          name: hashlib.sha256(self.root.joinpath('config', name).read_bytes()).hexdigest()
                          for name in ('Caddyfile', 'gateway.yml', 'routes.caddy')})):
            patch.start(); self.addCleanup(patch.stop)

    def fake_module(self, path, name):
        # The switch must validate policies with the staged candidate, never
        # with the guard of the release that is still installed.
        self.module_paths = getattr(self, 'module_paths', [])
        self.module_paths.append((name, Path(path)))
        if 'lock' in name:
            class Lock:
                def acquire_lock(self, nonblocking=True):
                    class Scope:
                        def __enter__(self_inner): return None
                        def __exit__(self_inner, *args): return False
                    return Scope()
            return Lock()
        # The simulated install holds placeholder prior bytes, so the reviewed
        # modules are imported from the repository instead of from TARGET.
        if 'guard' in name: return fixed
        if 'env' in name: return readiness
        raise AssertionError('unexpected module request')

    def read(self, *parts):
        return (self.root.joinpath(*parts)).read_bytes()

    def test_switch_validates_with_the_staged_candidate(self):
        installer.upgrade_apex()
        guard_paths = [path for name, path in self.module_paths if name == 'installer_apex_guard']
        self.assertTrue(guard_paths)
        for path in guard_paths:
            self.assertEqual(path, self.incoming / 'preview-fixed-operations.py')

    def test_switch_installs_every_reviewed_file(self):
        installer.upgrade_apex()
        self.assertEqual(self.read('config/Caddyfile'), (REPO / 'config/apex-Caddyfile').read_bytes())
        self.assertEqual(self.read('config/routes.caddy'), (REPO / 'config/routes.caddy').read_bytes())
        self.assertEqual(self.read('config/gateway.yml'),
                         (REPO / 'config/apex-gateway-compose.yml').read_bytes())
        policy = tomllib.loads(self.read('secrets/oauth2-proxy.cfg').decode())
        self.assertEqual(policy['redirect_url'], 'https://xennic.ir/oauth2/callback')
        self.assertEqual(policy['whitelist_domains'], ['xennic.ir'])
        self.assertIn(b'PREVIEW_ORIGIN=https://xennic.ir', self.read('secrets/preview.env'))
        for name in ('Caddyfile', 'gateway.yml', 'routes.caddy', 'oauth2-proxy.cfg', 'preview.env'):
            self.assertTrue((self.root / 'config/.apex-before' / name).exists())
        self.assertTrue((self.base / '.before-apex').is_dir())
        self.assertEqual((self.target / 'release-check').read_bytes(),
                         (REPO / 'scripts/preview-fixed-operations.py').read_bytes())

    def test_failure_restores_every_original(self):
        with mock.patch.object(installer, 'verify_backend',
                               side_effect=RuntimeError('intentional failure')):
            with self.assertRaises(RuntimeError): installer.upgrade_apex()
        self.assertEqual(self.read('config/Caddyfile'), b'preview edge\n')
        self.assertEqual(self.read('config/gateway.yml'), b'preview gateway\n')
        self.assertEqual(self.read('config/routes.caddy'), b'preview routes\n')
        self.assertEqual(self.read('secrets/oauth2-proxy.cfg'), self.oauth)
        self.assertEqual(self.read('secrets/preview.env'), self.env)
        self.assertFalse((self.base / '.before-apex').exists())
        self.assertEqual((self.target / 'release-check').read_bytes(),
                         b'prior-preview-fixed-operations.py')

    def test_unknown_prior_state_is_refused(self):
        (self.target / 'release-check').write_bytes(b'tampered')
        with self.assertRaises(RuntimeError): installer.upgrade_apex()
        self.assertEqual(self.read('config/Caddyfile'), b'preview edge\n')

    def test_rollback_restores_the_preview_edge(self):
        installer.upgrade_apex()
        installer.rollback_apex()
        self.assertEqual(self.read('config/Caddyfile'), b'preview edge\n')
        self.assertEqual(self.read('config/gateway.yml'), b'preview gateway\n')
        self.assertEqual(self.read('config/routes.caddy'), b'preview routes\n')
        self.assertEqual(self.read('secrets/oauth2-proxy.cfg'), self.oauth)
        self.assertEqual(self.read('secrets/preview.env'), self.env)
        self.assertEqual((self.target / 'release-check').read_bytes(),
                         b'prior-preview-fixed-operations.py')


if __name__ == '__main__':
    unittest.main()
