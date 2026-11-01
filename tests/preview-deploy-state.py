#!/usr/bin/env python3
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import sys
import unittest
from unittest import mock

sys.dont_write_bytecode = True
p = Path(__file__).resolve().parents[1] / "scripts/preview-deploy-state.py"
spec = importlib.util.spec_from_file_location("preview_state", p)
state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(state)


def release(run):
    return {"repository": "feerozmandi/xennic-website", "commit": f"{run:040x}",
            "run_number": run, "digest": "sha256:" + f"{run:064x}", "platform": "linux/amd64"}


class StateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.path = self.dir / state.STATE_FILE
        self.journal = state.Journal(self.dir, owner_uid=os.geteuid())
        self.initial = {"version": 1, "last_run": 0, "blocked": False, "current": None, "previous": [], "pending": None}
        self.write(self.initial)

    def write(self, obj):
        self.path.write_text(json.dumps(obj))
        self.path.chmod(0o600)

    def test_begin_initial_requires_absent_journal_and_never_invents_healthy(self):
        self.path.unlink()
        self.assertTrue(self.journal.absent())
        self.journal.begin_initial(release(1))
        result = self.journal.read()
        self.assertEqual(result['pending'], release(1))
        self.assertIsNone(result['current'])
        self.assertTrue(result['blocked'])
        with self.assertRaises(FileExistsError): self.journal.begin_initial(release(2))
        self.assertEqual(self.journal.read(), result)
        self.journal.mark_healthy(release(1))
        self.assertEqual(self.journal.read()['current'], release(1))
        self.journal.ensure_initial_blocked(release(1))
        self.assertIsNone(self.journal.read()['current'])
        self.assertTrue(self.journal.read()['blocked'])
        self.assertEqual(self.journal.read()['failure'], 'initial-deployment-failed')
        with self.assertRaises(state.UnsafeState): self.journal.mark_healthy(release(1))

    def test_block_before_change_and_keep_two_previous(self):
        for run in (1, 2, 3, 4):
            self.journal.mark_inflight(release(run))
            pending = self.journal.read()
            self.assertTrue(pending["blocked"])
            self.assertEqual(pending["pending"], release(run))
            self.journal.mark_healthy(release(run))
        result = self.journal.read()
        self.assertEqual(result["current"], release(4))
        self.assertEqual(result["previous"], [release(3), release(2)])
        self.assertFalse(result["blocked"])
        self.assertIsNone(result["pending"])

    def test_invalid_or_stale_state_fails_closed(self):
        self.journal.mark_inflight(release(2))
        with self.assertRaises(state.UnsafeState): self.journal.mark_inflight(release(3))
        with self.assertRaises(state.UnsafeState): self.journal.mark_healthy(release(3))
        self.journal.mark_healthy(release(2))
        with self.assertRaises(state.UnsafeState): self.journal.mark_inflight(release(2))
        bad = self.journal.read()
        bad["blocked"] = True
        self.write(bad)
        with self.assertRaises(state.UnsafeState): self.journal.read()

    def test_reblock_after_uncertain_success_write(self):
        self.journal.mark_inflight(release(1))
        self.journal.mark_healthy(release(1))
        self.journal.ensure_blocked(release(1))
        self.assertTrue(self.journal.read()["blocked"])
        self.assertEqual(self.journal.read()["pending"], release(1))
        with self.assertRaises(state.UnsafeState): self.journal.ensure_blocked(release(2))

    def test_missing_insecure_symlink_and_bad_json_fail(self):
        self.path.unlink()
        with self.assertRaises(state.UnsafeState): self.journal.read()
        other = self.dir / "other"
        other.write_text("unchanged")
        self.path.symlink_to(other)
        with self.assertRaises(state.UnsafeState): self.journal.read()
        self.assertEqual(other.read_text(), "unchanged")
        self.path.unlink()
        self.write(self.initial)
        self.path.chmod(0o644)
        with self.assertRaises(state.UnsafeState): self.journal.read()
        self.path.chmod(0o600)
        self.path.write_text('{"version":1,"version":1}')
        with self.assertRaises(state.UnsafeState): self.journal.read()

    def test_atomic_failure_before_replace_does_not_start_release(self):
        with mock.patch.object(state.os, "replace", side_effect=OSError("simulated")):
            with self.assertRaises(OSError): self.journal.mark_inflight(release(1))
        self.assertEqual(self.journal.read(), self.initial)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), [state.STATE_FILE])


if __name__ == "__main__":
    unittest.main()
