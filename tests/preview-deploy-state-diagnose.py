#!/usr/bin/env python3
"""The journal the deployer writes is the journal the diagnosis reads.

The proof that the live release is the release the repository names has
two halves, and until now they were tested apart:

- the deployer's half: `mark_healthy` records the release and the
  version it read from the repository, and
- the diagnosis's half: it reads the journal, takes the commit out of
  `current` and the version out of `release_version`, and compares the
  version with the name the repository gives that commit.

A change to either half alone, or a change to the shape they agree on,
would leave each of them passing its own tests while the proof stopped
holding on the host. This test runs both halves against the same journal:
the one the deployer writes, read back by the diagnosis.

    python3 tests/preview-deploy-state-diagnose.py
"""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


state = load('preview_state', ROOT / 'scripts/preview-deploy-state.py')
diagnose = load('preview_diagnose', ROOT / 'scripts/diagnose-preview-pull-deploy.py')

FAKE_TOKEN = 'token-that-is-never-printed'
COMMIT = 'a' * 40


def evidence_zip(release, run_id=46115834603, attempt=1):
    """The release artifact as the publishing job leaves it."""
    buffer = io.BytesIO()
    envelope = {'version': 1, 'run_id': run_id, 'run_attempt': attempt, 'release': release}
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('xennic-preview-release.json', json.dumps(envelope))
    return buffer.getvalue()


def release(run):
    return {"repository": "feerozmandi/xennic-website", "commit": f"{run:040x}",
            "run_number": run, "digest": "sha256:" + f"{run:064x}", "platform": "linux/amd64"}


class JournalToDiagnosisTest(unittest.TestCase):
    """The two halves of the proof, on one journal."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.journal = state.Journal(self.dir, owner_uid=os.geteuid())
        # The journal starts as a host that has never deployed: the same
        # state the first-install path leaves behind.
        path = self.dir / state.STATE_FILE
        path.write_text(json.dumps({"version": 1, "last_run": 0, "blocked": False,
                                    "current": None, "previous": [], "pending": None}))
        path.chmod(0o600)

    def diagnose(self, name_for_commit):
        """Run the diagnosis against the journal the deployer wrote."""
        sha = COMMIT
        release_manifest = {
            'repository': 'feerozmandi/xennic-website', 'platform': 'linux/amd64',
            'commit': sha, 'run_number': 315,
            'digest': 'sha256:' + '0' * 64,
        }
        evidence_module = mock.Mock()
        evidence_module.check.return_value = release_manifest

        def fake_api(path, token):
            if path.startswith('/commits/'):
                return 200, json.dumps({'sha': sha}).encode()
            if '/actions/workflows/' in path:
                run = {'id': 46115834603, 'run_number': 315, 'run_attempt': 1,
                       'head_sha': sha, 'head_branch': 'dev', 'event': 'push',
                       'status': 'completed', 'conclusion': 'success'}
                return 200, json.dumps({'workflow_runs': [run]}).encode()
            if '/actions/runs/' in path and 'artifacts' in path:
                artifact = {'id': 1, 'name': 'xennic-preview-release-1', 'expired': False,
                            'size_in_bytes': 377}
                return 200, json.dumps({'artifacts': [artifact]}).encode()
            return 404, b'{}'

        def fake_load(name, filename):
            # The journal the diagnosis reads is the one the deployer
            # wrote: the same directory, the same file.
            if 'evidence' in name:
                return evidence_module
            return mock.Mock(Journal=lambda *a, **k: self.journal)

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            with mock.patch.object(diagnose, 'read_token', lambda: FAKE_TOKEN.encode()), \
                    mock.patch.object(diagnose, 'api', side_effect=fake_api), \
                    mock.patch.object(diagnose, 'download_artifact',
                                      return_value=([], evidence_zip(release_manifest))), \
                    mock.patch.object(diagnose, 'public_status', return_value=200), \
                    mock.patch.object(diagnose, 'load', side_effect=fake_load), \
                    mock.patch.object(diagnose, 'release_name_for', return_value=name_for_commit):
                diagnose.failures.clear()
                diagnose.anomalies.clear()
                status = diagnose.main()
        return status, buffer.getvalue()

    def test_the_deployed_release_is_proved_against_the_repository_name(self):
        # The deployer writes the journal: the release goes in flight, then
        # it is marked healthy with the version the repository gave it.
        manifest = release(315)
        manifest['commit'] = COMMIT
        self.journal.mark_inflight(manifest)
        self.journal.mark_healthy(manifest, 'v1.2.4')

        # The diagnosis reads that same journal and compares the version in
        # it with the name the repository gives the commit in it.
        status, output = self.diagnose('v1.2.4')
        self.assertEqual(status, 0, output)
        self.assertIn('the live version is v1.2.4', output)
        self.assertIn('the repository names the live commit the same', output)
        self.assertNotIn('ANOMALY', output)

    def test_a_journal_that_claims_another_name_is_an_anomaly(self):
        manifest = release(315)
        manifest['commit'] = COMMIT
        self.journal.mark_inflight(manifest)
        self.journal.mark_healthy(manifest, 'v9.9.9')

        status, output = self.diagnose('v1.2.4')
        self.assertEqual(status, 1)
        self.assertIn('ANOMALY', output)
        self.assertIn('v9.9.9', output)
        self.assertIn('v1.2.4', output)
        # It is not a deployment failure: nothing stopped.
        self.assertNotIn('FAILED', output)

    def test_the_diagnosis_reads_the_version_the_deployer_recorded(self):
        # The version in the journal is the one the deployer wrote, not one
        # the diagnosis makes up: a different version in the journal must
        # reach the comparison.
        manifest = release(315)
        manifest['commit'] = COMMIT
        self.journal.mark_inflight(manifest)
        self.journal.mark_healthy(manifest, 'v1.2.4')
        self.assertEqual(self.journal.read()['release_version'], 'v1.2.4')

        status, output = self.diagnose('v1.2.4')
        self.assertEqual(status, 0, output)
        self.assertIn('v1.2.4', output)

    def test_a_release_before_naming_is_neither_a_failure_nor_an_anomaly(self):
        # The state the host was in before the new release was deployed: the
        # live commit predates naming, so it carries no tag and the journal
        # has no version. That is not a broken proof, it is a host that has
        # not been redeployed yet, and the diagnosis has to say so plainly
        # instead of raising an anomaly.
        manifest = release(260)
        manifest['commit'] = COMMIT
        self.journal.mark_inflight(manifest)
        self.journal.mark_healthy(manifest, 'v1.0.0')
        # A journal written before naming has no version at all.
        raw = json.loads((self.dir / state.STATE_FILE).read_text())
        raw.pop('release_version', None)
        (self.dir / state.STATE_FILE).write_text(json.dumps(raw))
        (self.dir / state.STATE_FILE).chmod(0o600)

        status, output = self.diagnose(None)
        self.assertEqual(status, 0, output)
        self.assertIn('the repository names no release for the live commit', output)
        self.assertNotIn('ANOMALY', output)
        self.assertNotIn('FAILED', output)

    def test_a_named_commit_with_an_unversioned_journal_says_so(self):
        # The other half of the same state: the repository names the live
        # commit, but the journal has no version because the release was
        # deployed before names existed.
        manifest = release(260)
        manifest['commit'] = COMMIT
        self.journal.mark_inflight(manifest)
        self.journal.mark_healthy(manifest, 'v1.0.0')
        raw = json.loads((self.dir / state.STATE_FILE).read_text())
        raw.pop('release_version', None)
        (self.dir / state.STATE_FILE).write_text(json.dumps(raw))
        (self.dir / state.STATE_FILE).chmod(0o600)

        status, output = self.diagnose('v1.0.0')
        self.assertEqual(status, 0, output)
        self.assertIn('the journal records no version', output)
        self.assertNotIn('ANOMALY', output)


if __name__ == '__main__':
    unittest.main(verbosity=2)
