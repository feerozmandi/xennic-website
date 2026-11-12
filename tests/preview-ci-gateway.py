#!/usr/bin/env python3
"""Tests for the CI gateway's pure validation, without touching a real host.

The docker/SSH-driving parts are deliberately not exercised here (CI has no
production host); everything that decides whether a command or a transition row
is acceptable is pure and is covered below.
"""
import importlib.util
import json
from pathlib import Path
import unittest

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

    def test_invalid_lists(self):
        for raw in ('', '{}', '[]', '["a","a"]', '[1]', '["a b"]', '["' + 'x' * 201 + '"]'):
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
