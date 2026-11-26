#!/usr/bin/env python3
"""Tests for the CI gateway's pure validation, without touching a real host.

The docker/SSH-driving parts are deliberately not exercised here (CI has no
production host); everything that decides whether a command or a transition row
is acceptable is pure and is covered below.
"""
import base64
import contextlib
import importlib.util
import io
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

p = Path(__file__).resolve().parents[1] / 'scripts/preview-ci-gateway.py'
spec = importlib.util.spec_from_file_location('preview_ci_gateway', p)
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)

FROM = 'b5838e507edaedd3278dfa140cdcb6fe805cc684'
TO = '42950e6035377b84bf271b1b7986e5895d53561d'
HASH = '9f66a5faa171cd9a959a400b117d96d8a0832cfa69c27e9ba8cd76922632e69d'


def row(**changes):
    data = {'from_commit': FROM, 'to_commit': TO, 'migration_sha256': HASH,
            'previous_migrations': ['20261030_163225_baseline'], 'rollback_safe': True}
    data.update(changes)
    return data


def store(*rows):
    return {'version': 1, 'transitions': list(rows)}


class CommandTest(unittest.TestCase):
    def test_known_commands(self):
        self.assertEqual(gateway.parse_command(['ci-gateway', 'preflight']), ('preflight', []))
        for name in ('release-check', 'deploy'):
            self.assertEqual(gateway.parse_command(['ci-gateway', name])[0], name)

    def test_unknown_command_is_rejected(self):
        for argv in (['ci-gateway'], ['ci-gateway', 'shell'], ['ci-gateway', 'deploy', 'x'],
                     ['ci-gateway', 'approve'], ['ci-gateway', 'approve', 'short', '[]']):
            with self.assertRaises(gateway.Rejected):
                gateway.parse_command(argv)

    def test_approve_needs_hash_and_migrations(self):
        command, extras = gateway.parse_command(
            ['ci-gateway', 'approve', HASH, '["20261030_163225_baseline"]'])
        self.assertEqual(command, 'approve')
        self.assertEqual(extras[0], HASH)


class MigrationsTest(unittest.TestCase):
    def test_valid_list(self):
        self.assertEqual(gateway.parse_previous_migrations('["a","b_1"]'), ['a', 'b_1'])

    def test_the_base64_form_means_the_same_thing(self):
        # The SSH wrapper, the diagnostic and the reviewer all carry the list
        # in base64; the gateway is also called directly with plain JSON. Both
        # encodings must be accepted and must mean the same thing.
        encoded = base64.b64encode(b'["20261030_163225_baseline"]').decode('ascii')
        self.assertEqual(gateway.parse_previous_migrations(encoded), ['20261030_163225_baseline'])
        self.assertEqual(gateway.parse_previous_migrations('["20261030_163225_baseline"]'),
                         ['20261030_163225_baseline'])

    def test_invalid_lists(self):
        for raw in ('', '{}', '[]', '["a","a"]', '[1]', '["a b"]', '["' + 'x' * 201 + '"]'):
            with self.assertRaises(gateway.Rejected):
                gateway.parse_previous_migrations(raw)

    def test_base64_that_is_not_a_json_array_is_rejected(self):
        for raw in (base64.b64encode(b'{}').decode('ascii'),
                    base64.b64encode(b'not json').decode('ascii'),
                    base64.b64encode(b'[]').decode('ascii'),
                    base64.b64encode(b'["a","a"]').decode('ascii')):
            with self.assertRaises(gateway.Rejected):
                gateway.parse_previous_migrations(raw)


class StoreTest(unittest.TestCase):
    def test_accepts_the_reviewed_shape(self):
        gateway.validate_store(store(row()))

    def test_rejects_extra_or_missing_fields(self):
        for item in (dict(row(), extra=1), {k: v for k, v in row().items() if k != 'rollback_safe'}):
            with self.assertRaises(gateway.Rejected):
                gateway.validate_store(store(item))

    def test_rejects_unsafe_rows(self):
        for item in (row(rollback_safe=False), row(rollback_safe='true'), row(from_commit='abc'),
                     row(migration_sha256=HASH.upper()), row(previous_migrations=[]),
                     row(previous_migrations=['a', 'a'])):
            with self.assertRaises(gateway.Rejected):
                gateway.validate_store(store(item))

    def test_rejects_wrong_envelope(self):
        for data in ({}, {'version': 2, 'transitions': []}, {'version': 1},
                     {'version': 1, 'transitions': [], 'extra': 1},
                     {'version': 1, 'transitions': 'nope'}):
            with self.assertRaises(gateway.Rejected):
                gateway.validate_store(data)


class AppendTest(unittest.TestCase):
    def test_appends_one_row_and_keeps_history(self):
        first = row(from_commit='0' * 40, to_commit=FROM)
        data, added = gateway.next_store(store(first), FROM, TO, HASH, ['20261030_163225_baseline'])
        self.assertEqual(data['transitions'], [first, added])
        self.assertEqual(added['from_commit'], FROM)
        self.assertEqual(added['to_commit'], TO)
        self.assertIs(added['rollback_safe'], True)
        self.assertEqual(added['previous_migrations'], ['20261030_163225_baseline'])
        gateway.validate_store(data)

    def test_refuses_duplicates_and_second_targets(self):
        existing = row()
        with self.assertRaises(gateway.Rejected):
            gateway.next_store(store(existing), FROM, TO, HASH, ['20261030_163225_baseline'])
        with self.assertRaises(gateway.Rejected):
            gateway.next_store(store(row(from_commit='1' * 40)), FROM, TO, HASH, ['x'])


class ManifestTest(unittest.TestCase):
    def test_manifest_line_is_canonical_and_newline_terminated(self):
        release = {'repository': 'feerozmandi/xennic-website', 'commit': TO, 'run_number': 234,
                   'digest': 'sha256:' + 'a' * 64, 'platform': 'linux/amd64'}
        line = gateway.manifest_line(release)
        self.assertTrue(line.endswith(b'\n'))
        self.assertEqual(json.loads(line), release)
        self.assertEqual(line.count(b'\n'), 1)


class LoadTest(unittest.TestCase):
    """The phase-named helpers are installed without a file extension, and
    `spec_from_file_location` cannot pick a loader for a name it does not
    recognise: it returns None, and the caller then fails on a None loader."""

    def test_an_extensionless_helper_loads(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'release-check').write_text(
                "VALUE = 7\n"
                "def migration_tree_hash(release):\n"
                "    return 'hash-' + release['commit'][:7]\n", encoding='utf-8')
            with mock.patch.object(gateway, 'HELPERS', directory):
                module = gateway.load('ci_gateway_ops_hash', 'release-check')
            self.assertEqual(module.VALUE, 7)
            self.assertEqual(module.migration_tree_hash({'commit': 'c0196235'}), 'hash-c019623')

    def test_a_helper_with_a_py_extension_still_loads(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'preview-deploy-manifest.py').write_text(
                "VALUE = 9\n", encoding='utf-8')
            with mock.patch.object(gateway, 'HELPERS', directory):
                module = gateway.load('ci_gateway_manifest', 'preview-deploy-manifest.py')
            self.assertEqual(module.VALUE, 9)


class HelperProtocolTest(unittest.TestCase):
    """Every helper the gateway calls has a fixed stdin protocol.

    `pull-image` reads the manifest and then the registry access token, both on
    stdin. Sending it only the manifest makes it fail, and the approval then
    stops for a reason that has nothing to do with the migration — so the
    protocol is checked here, against the helper's own source.
    """

    def pull_image_expects(self):
        source = (p.parent / 'preview-pull-image.py').read_text(encoding='utf-8')
        self.assertIn('token = sys.stdin.buffer.readline(4098)', source)
        self.assertIn("not token.endswith(b'\\n')", source)

    def test_the_helper_needs_the_token_line(self):
        self.pull_image_expects()

    def test_the_approval_sends_the_registry_token(self):
        source = p.read_text(encoding='utf-8')
        self.assertIn("run_helper('pull-image', manifest_line(release) + b'public-read\\n'",
                      source)

    def test_every_helper_call_in_the_approval_sends_what_its_helper_reads(self):
        source = p.read_text(encoding='utf-8')
        # release-check and deploy take the manifest and the API token.
        self.assertIn("run_helper('release-check', manifest_line(release) + read_token() + b'\\n'",
                      source)
        self.assertIn("run_backend(manifest_line(release) + read_token() + b'\\n'",
                      source)


class InstallerPrerequisitesTest(unittest.TestCase):
    """The gateway installer must ask only for files the host really has.

    The helper installer writes `preview-fixed-operations.py` under the phase
    names only. A required list that names the source made the installer fail
    on a correctly installed host, and the approval could never be given.
    """

    @staticmethod
    def helper_installer():
        return (p.parent / 'install-preview-sftp-helper.py').read_text(encoding='utf-8')

    @staticmethod
    def installed_names():
        """The names the helper installer actually writes."""
        helper = InstallerPrerequisitesTest.helper_installer()
        block = helper.split('EXECUTABLES = {')[1].split('}')[0]
        mapping = dict(re.findall(r"'([a-z0-9-]+\.py)':\s*\(([^)]*)\)", block))
        files = set(re.findall(r"'([a-z0-9-]+\.py)'", helper.split('FILES = (')[1].split(')')[0]))
        names = set()
        for source, targets in mapping.items():
            names |= set(re.findall(r"'([A-Za-z0-9_.-]+)'", targets))
        names |= {name for name in files if name not in mapping}
        return names

    @staticmethod
    def gateway_required():
        installer = (p.parent / 'install-preview-ci-gateway.py').read_text(encoding='utf-8')
        body = installer.split('REQUIRED = (')[1].split(')')[0]
        return set(re.findall(r"'([A-Za-z0-9_.-]+)'", body))

    def test_nothing_is_required_that_the_helper_install_never_creates(self):
        missing = self.gateway_required() - self.installed_names()
        self.assertEqual(missing, set(),
                         f'never installed by the helper install: {sorted(missing)}')

    def test_the_source_name_of_the_fixed_operations_is_never_required(self):
        self.assertNotIn('preview-fixed-operations.py', self.gateway_required())

    def test_the_pull_deploy_installer_agrees(self):
        installer = (p.parent / 'install-preview-pull-deploy.py').read_text(encoding='utf-8')
        body = installer.split('REQUIRED = (')[1].split(')')[0]
        required = set(re.findall(r"'([A-Za-z0-9_.-]+)'", body))
        missing = required - self.installed_names()
        self.assertEqual(missing, set(),
                         f'never installed by the helper install: {sorted(missing)}')


class BackendLaunchTest(unittest.TestCase):
    """The backend is installed as a private module, and must be started, not executed.

    The reviewed helper installer gives every phase helper an executable copy
    and leaves `preview-deploy-backend.py` at mode 0600, and the backend's own
    `verify_helpers` lists that file among the modules and not among the
    executables. Executing it fails with a permission error before the
    backend ever runs. The fixture below is the installed shape exactly.
    """

    BACKEND = ('#!/usr/bin/python3\n'
               'import sys\n'
               'sys.stdout.write("backend-started:" + str(sys.stdin.buffer.read().count(b"\\n")))\n')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.helpers = Path(self.tmp.name)
        self.path = self.helpers / 'preview-deploy-backend.py'
        self.path.write_text(self.BACKEND)
        self.path.chmod(0o600)
        self.lstat = os.lstat

    def root_owned(self):
        """Report the fixture helpers as root-owned, the way the host's are.

        The gateway refuses a helper that is not owned by root, and it always
        runs as root itself. The disposable fixture is written by the test
        user, so only the ownership field is adjusted; the mode, which is what
        these tests are about, is left exactly as it was written.
        """
        real = self.lstat

        def lstat(path, *args, **kwargs):
            info = real(path, *args, **kwargs)
            if str(path).startswith(str(self.helpers)):
                fields = list(info)
                fields[4] = 0
                return os.stat_result(fields)
            return info

        return mock.patch.object(gateway.os, 'lstat', lstat)

    def release(self):
        return {'repository': 'feerozmandi/xennic-website', 'commit': TO, 'run_number': 260,
                'digest': 'sha256:' + 'c' * 64, 'platform': 'linux/amd64'}

    def test_the_installed_backend_cannot_be_executed(self):
        with self.assertRaises(PermissionError):
            subprocess.run([str(self.path)], input=b'', stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=60)

    def test_the_gateway_starts_the_backend_through_the_interpreter(self):
        buffer = io.StringIO()
        with self.root_owned():
            with mock.patch.object(gateway, 'HELPERS', self.helpers):
                with mock.patch.object(gateway, 'read_token', lambda: b'token'):
                    with contextlib.redirect_stdout(buffer):
                        gateway.command_deploy(self.release())
        self.assertEqual(buffer.getvalue(), 'backend-started:2')

    def test_the_backend_is_never_executed_directly(self):
        seen = {}

        def fake_run(argv, **kwargs):
            seen['argv'] = argv
            return subprocess.CompletedProcess(argv, 0, b'backend-started:2', b'')

        with self.root_owned():
            with mock.patch.object(gateway, 'HELPERS', self.helpers):
                with mock.patch.object(gateway, 'read_token', lambda: b'token'):
                    with mock.patch.object(gateway.subprocess, 'run', fake_run):
                        with contextlib.redirect_stdout(io.StringIO()):
                            gateway.command_deploy(self.release())
        self.assertEqual(seen['argv'][0], gateway.INTERPRETER)
        self.assertEqual(seen['argv'][1], str(self.path))

    def test_a_phase_helper_without_an_execute_bit_is_refused(self):
        # The phase helpers are executed directly, so a missing execute bit has
        # to be refused with a clear message instead of a permission error.
        phase = self.helpers / 'release-check'
        phase.write_text('#!/usr/bin/python3\n')
        phase.chmod(0o600)
        with self.root_owned():
            with mock.patch.object(gateway, 'HELPERS', self.helpers):
                with self.assertRaises(gateway.Rejected) as caught:
                    gateway.run_helper('release-check', b'payload\n', 60)
        self.assertEqual(str(caught.exception), 'release-check is not executable')

    def test_a_phase_helper_with_an_execute_bit_is_run(self):
        phase = self.helpers / 'release-check'
        phase.write_text('#!/usr/bin/python3\nimport sys\nsys.stdout.write("ran\\n")\n')
        phase.chmod(0o700)
        with self.root_owned():
            with mock.patch.object(gateway, 'HELPERS', self.helpers):
                output = gateway.run_helper('release-check', b'payload\n', 60)
        self.assertEqual(output, b'ran\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
