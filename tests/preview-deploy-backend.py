#!/usr/bin/env python3
"""Synthetic-only end-to-end backend tests; no Docker, network or VPS."""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("preview_backend", ROOT / "scripts/preview-deploy-backend.py")
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)


def release(run):
    return {"repository": "feerozmandi/xennic-website", "commit": f"{run:040x}", "run_number": run,
            "digest": "sha256:" + f"{run:064x}", "platform": "linux/amd64"}


def raw(run):
    return json.dumps(release(run)).encode()


class SyntheticRunner:
    def __init__(self, destination, fail=None):
        if destination not in ("synthetic-a", "synthetic-b"):
            raise ValueError("synthetic destination only")
        self.destination, self.fail = destination, fail
        self.events, self.backups = [], {}
        self.data = {"db": b"synthetic database", "media": b"synthetic media"}
        self.running = release(1)

    def verify_helpers(self):
        self.events.append(("verify_helpers",))

    def call(self, phase, item, token=None):
        item = backend._validated_release(item)
        self.events.append((phase, item["run_number"]))
        failures = {self.fail} if isinstance(self.fail, str) else (self.fail or set())
        if phase == "health" and "health" in failures and item["run_number"] == 2:
            raise backend.BackendError("synthetic failed health")
        if phase in failures and phase != "health":
            raise backend.BackendError("synthetic failure")
        if phase == "release-check":
            return {"initial": False, "rollback_safe": True, "verified_commit": item["commit"],
                    "verified_digest": item["digest"], "verified_run_number": item["run_number"]}
        if phase == "backup-verify":
            # A synthetic remote and restore drill, not real encryption/SFTP.
            self.backups[self.destination] = dict(self.data)
            if "corrupt-backup" in failures:
                self.backups[self.destination]["db"] = b"corrupted synthetic database"
            restored = dict(self.backups[self.destination])
            if restored != self.data:
                raise backend.BackendError("synthetic restore failed")
        if phase == "pull-image" and token != b"synthetic-token":
            raise backend.BackendError("invalid synthetic token")
        if phase in ("activate", "rollback"):
            self.running = item


class BackendTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        directory = Path(self.tmp.name)
        self.journal_dir = directory / "state"
        self.journal_dir.mkdir(mode=0o700)
        state_file = self.journal_dir / backend.states.STATE_FILE
        state_file.write_text(json.dumps({"version": 1, "last_run": 1, "blocked": False,
                                          "current": release(1), "previous": [], "pending": None}))
        state_file.chmod(0o600)
        self.journal = backend.states.Journal(self.journal_dir, owner_uid=os.geteuid())
        self.lock_path = directory / "synthetic.lock"
        self.runner = SyntheticRunner("synthetic-a")
        self.ops = backend.Backend(b"synthetic-token", runner=self.runner, journal=self.journal)
        # Production uses the fixed /run/lock path; override only in this unit test.
        self.ops.lock = lambda: backend.locks.acquire_lock(self.lock_path, owner_uid=os.geteuid())

    def ready(self, **kwargs):
        if kwargs.get("registry_token") != b"synthetic-token":
            raise backend.readiness.NotReady("missing synthetic token")

    def test_success_with_configurable_synthetic_backup(self):
        self.runner.destination = "synthetic-b"
        with mock.patch.object(backend.readiness, "check", side_effect=self.ready):
            result = backend.run_checked(raw(2), b"synthetic-token", self.ops)
        self.assertEqual(result, release(2))
        self.assertEqual(self.runner.backups["synthetic-b"], self.runner.data)
        self.assertEqual(self.runner.running, release(2))
        self.assertEqual(self.journal.read()["current"], release(2))
        self.assertFalse(self.journal.read()["blocked"])
        phases = [x[0] for x in self.runner.events]
        self.assertLess(phases.index("pull-image"), phases.index("backup-verify"))
        self.assertLess(phases.index("backup-verify"), phases.index("migrate"))
        self.assertLess(phases.index("migrate"), phases.index("activate"))

    def test_health_failure_rolls_back_but_stays_blocked(self):
        self.runner.fail = "health"
        with mock.patch.object(backend.readiness, "check", side_effect=self.ready):
            with self.assertRaises(backend.transaction.DeploymentFailed):
                backend.run_checked(raw(2), b"synthetic-token", self.ops)
        self.assertEqual(self.runner.running, release(1))
        self.assertTrue(self.journal.read()["blocked"])
        self.assertIn(("rollback", 1), self.runner.events)
        self.assertIn(("health", 1), self.runner.events)

    def test_missing_prerequisites_stop_before_lock_or_changes(self):
        before = self.journal.read()
        for missing in ("fingerprint", "registry token", "secret", "backup destination"):
            with self.subTest(missing=missing), mock.patch.object(
                backend.readiness, "check", side_effect=backend.readiness.NotReady(missing)
            ):
                with self.assertRaises(backend.BackendError) as exc:
                    backend.run_checked(raw(2), b"synthetic-token", self.ops)
                self.assertIn(missing, str(exc.exception))
                self.assertFalse(self.lock_path.exists())
                self.assertEqual(self.journal.read(), before)
                self.assertEqual(self.runner.events, [])

    def test_pull_failure_does_not_block_or_stop_existing_release(self):
        self.runner.fail = "pull-image"
        with mock.patch.object(backend.readiness, "check", side_effect=self.ready):
            with self.assertRaises(backend.BackendError):
                backend.run_checked(raw(2), b"synthetic-token", self.ops)
        self.assertFalse(self.journal.read()["blocked"])
        self.assertEqual(self.runner.running, release(1))
        self.assertNotIn(("backup-verify", 2), self.runner.events)
        self.assertNotIn(("migrate", 2), self.runner.events)

    def test_backup_failure_never_migrates_or_changes_release(self):
        self.runner.fail = "backup-verify"
        with mock.patch.object(backend.readiness, "check", side_effect=self.ready):
            with self.assertRaises(backend.transaction.DeploymentFailed):
                backend.run_checked(raw(2), b"synthetic-token", self.ops)
        self.assertEqual(self.runner.running, release(1))
        self.assertTrue(self.journal.read()["blocked"])
        self.assertNotIn(("migrate", 2), self.runner.events)

    def test_corrupt_synthetic_backup_stops_before_migration(self):
        self.runner.fail = "corrupt-backup"
        with mock.patch.object(backend.readiness, "check", side_effect=self.ready):
            with self.assertRaises(backend.transaction.DeploymentFailed):
                backend.run_checked(raw(2), b"synthetic-token", self.ops)
        self.assertEqual(self.runner.running, release(1))
        self.assertTrue(self.journal.read()["blocked"])
        self.assertNotIn(("migrate", 2), self.runner.events)

    def test_failed_rollback_keeps_release_blocked(self):
        self.runner.fail = {"health", "rollback"}
        with mock.patch.object(backend.readiness, "check", side_effect=self.ready):
            with self.assertRaises(backend.transaction.DeploymentFailed):
                backend.run_checked(raw(2), b"synthetic-token", self.ops)
        self.assertTrue(self.journal.read()["blocked"])
        self.assertEqual(self.runner.running, release(2))

    def test_migration_failure_keeps_release_blocked_without_switch(self):
        self.runner.fail = "migrate"
        with mock.patch.object(backend.readiness, "check", side_effect=self.ready):
            with self.assertRaises(backend.transaction.DeploymentFailed):
                backend.run_checked(raw(2), b"synthetic-token", self.ops)
        self.assertEqual(self.runner.running, release(1))
        self.assertTrue(self.journal.read()["blocked"])
        self.assertNotIn(("activate", 2), self.runner.events)

    def test_partial_switch_is_rolled_back_if_compatible(self):
        original = self.runner.call
        def partially_failed(phase, item, token=None):
            if phase == "activate":
                self.runner.running = item
                raise backend.BackendError("synthetic partial switch")
            return original(phase, item, token)
        self.runner.call = partially_failed
        with mock.patch.object(backend.readiness, "check", side_effect=self.ready):
            with self.assertRaises(backend.transaction.DeploymentFailed):
                backend.run_checked(raw(2), b"synthetic-token", self.ops)
        self.assertEqual(self.runner.running, release(1))
        self.assertTrue(self.journal.read()["blocked"])
        self.assertIn(("rollback", 1), self.runner.events)

    def test_incompatible_release_stops_before_backup(self):
        original = self.runner.call
        def incompatible(phase, item, token=None):
            if phase == "release-check":
                return {"initial": False, "rollback_safe": False, "verified_commit": item["commit"],
                        "verified_digest": item["digest"], "verified_run_number": item["run_number"]}
            return original(phase, item, token)
        self.runner.call = incompatible
        with mock.patch.object(backend.readiness, "check", side_effect=self.ready):
            with self.assertRaises(backend.transaction.DeploymentRejected):
                backend.run_checked(raw(2), b"synthetic-token", self.ops)
        self.assertFalse(self.journal.read()["blocked"])
        self.assertNotIn(("backup-verify", 2), self.runner.events)

    def test_unverified_digest_cannot_reach_backup_or_change(self):
        original = self.runner.call
        def wrong_evidence(phase, item, token=None):
            if phase == "release-check":
                return {"initial": False, "rollback_safe": True, "verified_commit": item["commit"],
                        "verified_digest": "sha256:" + "f" * 64, "verified_run_number": item["run_number"]}
            return original(phase, item, token)
        self.runner.call = wrong_evidence
        with mock.patch.object(backend.readiness, "check", side_effect=self.ready):
            with self.assertRaises(backend.BackendError):
                backend.run_checked(raw(2), b"synthetic-token", self.ops)
        self.assertNotIn(("backup-verify", 2), self.runner.events)
        self.assertFalse(self.journal.read()["blocked"])

    def test_initial_closure_uses_fixed_helper_and_checks_permissions(self):
        runner = backend.FixedRunner()
        with mock.patch.object(runner, 'verify_helpers') as verify, mock.patch.object(backend.subprocess, 'run') as run:
            run.return_value = subprocess.CompletedProcess([], 0)
            runner.close_initial(release(2))
            verify.assert_called_once()
            self.assertEqual(run.call_args.args[0], [str(backend.PHASES['rollback'])])
            self.assertTrue(run.call_args.kwargs['input'].endswith(b'\ninitial-close\n'))

    def test_cli_is_always_disabled(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/preview-deploy-backend.py")],
                                capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"disabled", result.stderr)

    def test_fixed_runner_rejects_arbitrary_operations_and_paths(self):
        runner = backend.FixedRunner()
        with mock.patch.object(runner, "verify_helpers"), mock.patch.object(backend.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, stdout=b"")
            runner.call("pull-image", release(2), b"synthetic-token")
            args, kwargs = run.call_args.args, run.call_args.kwargs
            self.assertEqual(args[0], [str(backend.PHASES["pull-image"])])
            self.assertNotIn("synthetic-token", repr(args))
            self.assertNotIn("synthetic-token", repr(kwargs["env"]))
            self.assertIn(b"synthetic-token", kwargs["input"])
            with self.assertRaises(backend.BackendError): runner.call("/bin/sh", release(2))
            with self.assertRaises(backend.BackendError): runner.call("activate", dict(release(2), repository="other/repo"))
            with self.assertRaises(backend.BackendError): runner.call("activate", release(2), b"secret")
            self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
