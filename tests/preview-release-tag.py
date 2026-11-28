#!/usr/bin/env python3
"""Checks for the release namer: the tag that names a release, and its proof.

The namer talks to the GitHub API through `gh`, so these checks give it a
`gh` of their own: a small program that answers like the API does, including
the ways the API refuses. Every answer the real API can give is here, so the
refusals of this repository are written down and cannot drift.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_tag_tests',
                                              ROOT / 'scripts/preview-release-tag.py')
tag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tag)

OWNER = 'feerozmandi/xennic-website'
COMMIT = 'e9169626c1e071cbe0fe652dd758c78b3fed424f'
OTHER = 'fd7d11a205c69035469aec24bcd518f9ee3acaf3'
VERSION = 'v1.2.6'

# The `gh` these checks use. It answers like the API does: the body of a
# refusal on the standard output, the message and the status on the error.
FAKE = '''#!/usr/bin/env python3
import json, os, sys
state = json.loads(open(os.environ['FAKE_GH_STATE']).read())
path = [a for a in sys.argv if a.startswith('repos/')][0]
method = 'GET'
fields = {}
arguments = sys.argv[1:]
for index, argument in enumerate(arguments):
    if argument == '--method':
        method = arguments[index + 1]
    if argument == '-f':
        key, _, value = arguments[index + 1].partition('=')
        fields[key] = value
state['calls'] = state.get('calls', 0) + 1
def save():
    open(os.environ['FAKE_GH_STATE'], 'w').write(json.dumps(state))
def refuse(status, message, body=None):
    save()
    sys.stdout.write(json.dumps(body if body is not None else {'message': message, 'status': str(status)}))
    sys.stderr.write('gh: %s (HTTP %d)\\n' % (message, status))
    sys.exit(1)
if method == 'GET' and '/git/ref/tags/' in path:
    name = path.split('/git/ref/tags/')[1]
    if state['scenario'] == 'forbidden-read':
        refuse(403, 'Resource not accessible by integration')
    if name in state['refs']:
        save()
        sys.stdout.write(json.dumps(state['refs'][name]))
        sys.exit(0)
    refuse(404, 'Not Found')
if method == 'GET' and '/git/tags/' in path:
    save()
    sys.stdout.write(json.dumps(state['tag_objects'][path.split('/git/tags/')[1]]))
    sys.exit(0)
if method == 'POST' and path.endswith('/git/refs'):
    scenario = state['scenario']
    name = fields['ref'].split('/')[-1]
    if scenario == 'forbidden':
        refuse(403, 'Resource not accessible by integration')
    if scenario == 'unknown-sha':
        refuse(422, 'No commit found for SHA: %s' % fields['sha'])
    if scenario == 'transient' and state['calls'] <= state.get('fail_times', 2):
        refuse(500, 'Server Error')
    if scenario == 'raced':
        state['refs'][name] = {'object': {'sha': fields['sha'], 'type': 'commit'}}
        refuse(422, 'Reference already exists')
    if scenario == 'raced-other':
        state['refs'][name] = {'object': {'sha': state['other'], 'type': 'commit'}}
        refuse(422, 'Reference already exists')
    state['refs'][name] = {'object': {'sha': fields['sha'], 'type': 'commit'}}
    save()
    sys.stdout.write(json.dumps(state['refs'][name]))
    sys.exit(0)
refuse(404, 'Not Found')
'''


class ReleaseTagTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.home = Path(self.directory.name)
        self.state = self.home / 'state.json'
        self.state.write_text(json.dumps({
            'refs': {}, 'tag_objects': {}, 'scenario': 'free', 'calls': 0,
            'other': OTHER, 'fail_times': 2}))
        fake = self.home / 'gh'
        fake.write_text(FAKE)
        fake.chmod(0o755)
        self.environment = dict(os.environ)
        self.environment['PATH'] = str(self.home) + os.pathsep + self.environment['PATH']
        self.environment['FAKE_GH_STATE'] = str(self.state)
        self.summary = self.home / 'summary.md'

    def tearDown(self):
        self.directory.cleanup()

    def scenario(self, name, **extra):
        state = json.loads(self.state.read_text())
        state['scenario'] = name
        state.update(extra)
        self.state.write_text(json.dumps(state))

    def run_namer(self, version=VERSION, commit=COMMIT):
        return subprocess.run(
            [sys.executable, str(ROOT / 'scripts/preview-release-tag.py'),
             '--repository', OWNER, '--version', version, '--commit', commit,
             '--summary', str(self.summary)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.environment, check=False)

    def test_a_free_name_is_written_and_read_back(self):
        result = self.run_namer()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        state = json.loads(self.state.read_text())
        self.assertEqual(state['refs'][VERSION]['object']['sha'], COMMIT)
        self.assertIn('- Release tag: `v1.2.6` → `e916962`', self.summary.read_text())

    def test_the_error_page_of_a_free_name_is_not_a_name(self):
        # The API answers 404 with an error page on the standard output. An
        # answer that is not a commit means the name is free.
        result = self.run_namer()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(json.loads(self.state.read_text())['refs'][VERSION]['object']['sha'], COMMIT)

    def test_a_name_that_already_names_this_commit_is_a_success(self):
        self.scenario('free')
        state = json.loads(self.state.read_text())
        state['refs'][VERSION] = {'object': {'sha': COMMIT, 'type': 'commit'}}
        self.state.write_text(json.dumps(state))
        result = self.run_namer()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn('already', self.summary.read_text())

    def test_a_name_that_names_another_commit_is_refused(self):
        state = json.loads(self.state.read_text())
        state['refs'][VERSION] = {'object': {'sha': OTHER, 'type': 'commit'}}
        self.state.write_text(json.dumps(state))
        result = self.run_namer()
        self.assertEqual(result.returncode, 1)
        answer = result.stdout.decode()
        self.assertIn('::error::', answer)
        self.assertIn(OTHER, answer)
        self.assertIn(VERSION, answer)

    def test_a_write_that_raced_with_the_same_commit_is_a_success(self):
        self.scenario('raced')
        result = self.run_namer()
        self.assertEqual(result.returncode, 0, result.stdout.decode() + result.stderr.decode())
        self.assertIn('raced', self.summary.read_text())

    def test_a_write_that_raced_with_another_commit_is_refused(self):
        self.scenario('raced-other')
        result = self.run_namer()
        self.assertEqual(result.returncode, 1)
        answer = result.stdout.decode()
        self.assertIn('::error::', answer)
        self.assertIn(OTHER, answer)

    def test_a_transient_answer_is_retried(self):
        self.scenario('transient', fail_times=2)
        result = self.run_namer()
        self.assertEqual(result.returncode, 0, result.stdout.decode() + result.stderr.decode())
        self.assertEqual(json.loads(self.state.read_text())['refs'][VERSION]['object']['sha'], COMMIT)

    def test_a_refused_write_names_the_reason_of_the_api(self):
        # A refusal has to say why, in a line the run shows next to the
        # failed step, so it can be read without the run log.
        self.scenario('forbidden')
        result = self.run_namer()
        self.assertEqual(result.returncode, 1)
        answer = result.stdout.decode()
        self.assertIn('::error::', answer)
        self.assertIn('403', answer)
        self.assertIn('Resource not accessible by integration', answer)

    def test_a_write_of_an_unknown_commit_is_refused(self):
        self.scenario('unknown-sha')
        result = self.run_namer()
        self.assertEqual(result.returncode, 1)
        self.assertIn('::error::', result.stdout.decode())

    def test_an_annotated_name_is_read_as_the_commit_inside_it(self):
        state = json.loads(self.state.read_text())
        state['refs'][VERSION] = {'object': {'sha': 'a' * 40, 'type': 'tag'}}
        state['tag_objects']['a' * 40] = {'object': {'sha': COMMIT, 'type': 'commit'}}
        self.state.write_text(json.dumps(state))
        result = self.run_namer()
        self.assertEqual(result.returncode, 0, result.stdout.decode() + result.stderr.decode())

    def test_a_name_that_cannot_be_read_is_a_refusal(self):
        # The run does not get to decide a name is free because it could not
        # read the repository.
        state = json.loads(self.state.read_text())
        state['scenario'] = 'forbidden-read'
        self.state.write_text(json.dumps(state))
        result = self.run_namer()
        self.assertEqual(result.returncode, 1)
        self.assertIn('::error::', result.stdout.decode())

    def test_a_commit_that_is_not_a_commit_is_refused(self):
        result = self.run_namer(commit='not-a-commit')
        self.assertEqual(result.returncode, 1)
        self.assertIn('::error::', result.stdout.decode())


if __name__ == '__main__':
    unittest.main()
