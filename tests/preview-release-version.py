#!/usr/bin/env python3
"""Checks for the release namer: the version of a commit, and its name."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('release_version_tests',
                                              Path(__file__).resolve().parents[1] / 'scripts/preview-release-version.py')
version = importlib.util.module_from_spec(spec)
spec.loader.exec_module(version)

GIT = ('git', '-c', 'safe.directory=*', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid')


class VersionShapeTest(unittest.TestCase):
    def test_a_version_is_three_numbers_with_a_v(self):
        self.assertEqual(version.parse_version('v1.2.3'), (1, 2, 3))
        self.assertEqual(version.format_version((1, 2, 3)), 'v1.2.3')
        for value in ('1.2.3', 'v1.2', 'v1.2.3.4', 'v1.2.3-rc1', 'vx.y.z', '', None, 'v1.2.3 '):
            with self.subTest(value=value), self.assertRaises(version.Unnamed):
                version.parse_version(value)

    def test_a_breaking_change_moves_the_major_number(self):
        self.assertEqual(version.commit_kind(['fix: mend']), 'patch')
        self.assertEqual(version.commit_kind(['feat: add']), 'minor')
        self.assertEqual(version.commit_kind(['feat(scope): add']), 'minor')
        self.assertEqual(version.commit_kind(['feat!: add']), 'major')
        self.assertEqual(version.commit_kind(['chore: x\n\nBREAKING CHANGE: no']), 'major')
        self.assertEqual(version.commit_kind(['fix: mend', 'feat: add']), 'minor')

    def test_the_version_only_moves_forward(self):
        self.assertEqual(version.bump((1, 2, 3), 'patch'), (1, 2, 4))
        self.assertEqual(version.bump((1, 2, 3), 'minor'), (1, 3, 0))
        self.assertEqual(version.bump((1, 2, 3), 'major'), (2, 0, 0))


class RepositoryTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.repository = Path(self.directory.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')

    def tearDown(self):
        self.directory.cleanup()

    def git(self, *arguments):
        result = subprocess.run([*GIT, '-C', str(self.repository), *arguments],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
        self.assertEqual(result.returncode, 0, f'git {arguments} failed')
        return result

    def commit(self, message):
        self.git('commit', '-q', '--allow-empty', '-m', message)
        return self.git('rev-parse', 'HEAD').stdout.decode('ascii').strip()

    def tag(self, name, revision='HEAD'):
        self.git('tag', name, revision)

    def test_the_first_release_of_a_line_is_the_first_version(self):
        self.commit('feat: the first thing')
        self.assertEqual(version.name(self.repository), 'v1.0.0')

    def test_a_patch_moves_the_patch_number(self):
        self.commit('feat: the first thing')
        self.tag('v1.0.0')
        self.commit('fix: mend it')
        self.assertEqual(version.name(self.repository), 'v1.0.1')

    def test_a_feature_moves_the_minor_number(self):
        self.commit('feat: the first thing')
        self.tag('v1.0.0')
        self.commit('feat: add another thing')
        self.assertEqual(version.name(self.repository), 'v1.1.0')

    def test_a_breaking_change_moves_the_major_number(self):
        self.commit('feat: the first thing')
        self.tag('v1.0.0')
        self.commit('feat!: break the contract')
        self.assertEqual(version.name(self.repository), 'v2.0.0')

    def test_a_tag_on_another_branch_says_nothing_about_this_release(self):
        self.commit('feat: the first thing')
        self.tag('v1.0.0')
        self.git('checkout', '-q', '-b', 'other')
        self.commit('feat: another thing')
        self.tag('v9.9.9')
        self.git('checkout', '-q', '-')
        self.commit('fix: mend it')
        self.assertEqual(version.name(self.repository), 'v1.0.1')

    def test_a_name_that_another_commit_carries_is_not_reused(self):
        first = self.commit('feat: the first thing')
        self.tag('v1.0.0')
        second = self.commit('fix: mend it')
        third = self.commit('fix: mend it again')
        self.tag('v1.0.1', third)
        self.assertEqual(version.name(self.repository, second), 'v1.0.2')
        self.assertEqual(version.name(self.repository, third), 'v1.0.1')
        self.assertEqual(version.name(self.repository, first), 'v1.0.0')

    def test_the_same_commit_keeps_its_own_name(self):
        self.commit('feat: the first thing')
        self.tag('v1.0.0')
        commit = self.commit('fix: mend it')
        self.tag('v1.0.1', commit)
        self.assertEqual(version.name(self.repository, commit), 'v1.0.1')

    def test_a_name_that_is_not_a_version_is_not_a_release_tag(self):
        self.commit('feat: the first thing')
        self.tag('v1.0.0')
        self.tag('vnot-a-version')
        self.commit('fix: mend it')
        self.assertEqual(version.name(self.repository), 'v1.0.1')


if __name__ == '__main__':
    unittest.main()
