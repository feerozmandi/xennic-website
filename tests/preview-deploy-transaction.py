#!/usr/bin/env python3
import contextlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
p = Path(__file__).resolve().parents[1] / "scripts/preview-deploy-transaction.py"
spec = importlib.util.spec_from_file_location("preview_transaction", p)
tx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tx)


def release(run=6):
    return json.dumps({"repository": "feerozmandi/xennic-website", "commit": "a" * 40,
                       "run_number": run, "digest": "sha256:" + "b" * 64,
                       "platform": "linux/amd64"}).encode()


class Operations:
    def __init__(self, fail="", rollback_safe=True, state=None):
        self.events = []
        self.fail = fail
        self.rollback_safe = rollback_safe
        self.state = state if state is not None else {"blocked": False, "last_run": 5}

    @contextlib.contextmanager
    def lock(self):
        self.events.append("lock")
        try:
            yield
        finally:
            self.events.append("unlock")

    def step(self, name):
        self.events.append(name)
        if self.fail == name:
            raise RuntimeError("synthetic error; must not be echoed")

    def read_state(self):
        self.step("read_state")
        return dict(self.state)

    def preflight(self, r):
        self.step("preflight")
        if self.rollback_safe is None:
            return None
        return {"initial": not self.rollback_safe, "rollback_safe": self.rollback_safe}

    def pull_image(self, r): self.step("pull")
    def backup_and_verify(self, r): self.step("backup")
    def assert_current(self, r): self.step("assert_current")
    def mark_inflight(self, r):
        self.step("mark_inflight")
        self.state["blocked"] = True
        self.state["last_run"] = r["run_number"]
    def migrate(self, r): self.step("migrate")
    def activate(self, r): self.step("activate")
    def verify_health(self, r): self.step("health")
    def mark_healthy(self, r):
        self.step("mark_healthy")
        self.state["blocked"] = False
    def ensure_blocked(self, r):
        self.step("ensure_blocked")
        self.state["blocked"] = True
    def rollback_previous(self): self.step("rollback")
    def verify_previous_health(self): self.step("previous_health")


class TransactionTest(unittest.TestCase):
    def test_success_order_under_lock(self):
        ops = Operations()
        tx.deploy(release(), ops)
        self.assertEqual(ops.events, ["lock", "read_state", "preflight", "assert_current", "pull", "assert_current", "mark_inflight", "backup",
                                      "assert_current", "migrate", "assert_current", "activate", "health", "mark_healthy", "unlock"])
        self.assertEqual(ops.state, {"blocked": False, "last_run": 6})

    def test_bad_state_old_run_and_manifest_fail_before_mutation(self):
        for state, raw in [({"blocked": True, "last_run": 5}, release()),
                           ({"blocked": False, "last_run": 6}, release()),
                           ({"blocked": False, "last_run": True}, release()),
                           ({"blocked": False, "last_run": 5}, b"{}")]:
            with self.subTest(state=state, raw=raw):
                ops = Operations(state=state)
                with self.assertRaises(tx.DeploymentRejected): tx.deploy(raw, ops)
                self.assertNotIn("backup", ops.events)
                self.assertNotIn("migrate", ops.events)

    def test_preflight_backup_and_journal_fail_before_migration(self):
        for failure in ("preflight", "pull", "backup", "assert_current", "mark_inflight"):
            with self.subTest(failure=failure):
                ops = Operations(fail=failure)
                with self.assertRaises(RuntimeError): tx.deploy(release(), ops)
                self.assertNotIn("migrate", ops.events)
                self.assertEqual(ops.events[-1], "unlock")
                self.assertEqual(ops.state["blocked"], failure == "backup")
                if failure == "pull":
                    self.assertNotIn("mark_inflight", ops.events)
                    self.assertNotIn("backup", ops.events)
                if failure == "backup":
                    self.assertLess(ops.events.index("mark_inflight"), ops.events.index("backup"))
                    self.assertIn("ensure_blocked", ops.events)
                    self.assertNotIn("rollback", ops.events)
        ops = Operations(rollback_safe=None)
        with self.assertRaises(tx.DeploymentRejected): tx.deploy(release(), ops)
        self.assertNotIn("backup", ops.events)
        ops = Operations()
        ops.preflight = lambda _: {"initial": False, "rollback_safe": False}
        with self.assertRaises(tx.DeploymentRejected): tx.deploy(release(), ops)
        self.assertNotIn("backup", ops.events)

    def test_migration_failure_blocks_without_automatic_restore(self):
        ops = Operations(fail="migrate")
        with self.assertRaises(tx.DeploymentFailed) as exc: tx.deploy(release(), ops)
        self.assertNotIn("synthetic", str(exc.exception))
        self.assertTrue(ops.state["blocked"])
        self.assertNotIn("activate", ops.events)
        self.assertNotIn("rollback", ops.events)

    def test_superseded_during_migration_never_switches_traffic(self):
        class Superseded(Operations):
            def assert_current(self, r):
                self.step("assert_current")
                if self.state["blocked"]:
                    raise RuntimeError("dev advanced")
        ops = Superseded()
        with self.assertRaises(tx.DeploymentFailed): tx.deploy(release(), ops)
        self.assertTrue(ops.state["blocked"])
        self.assertNotIn("activate", ops.events)
        self.assertNotIn("rollback", ops.events)

    def test_switch_health_or_journal_failure_rolls_back_only_when_safe(self):
        for failure in ("activate", "health", "mark_healthy"):
            for safe in (True, False):
                with self.subTest(failure=failure, safe=safe):
                    ops = Operations(fail=failure, rollback_safe=safe)
                    with self.assertRaises(tx.DeploymentFailed): tx.deploy(release(), ops)
                    self.assertTrue(ops.state["blocked"])
                    self.assertIn("ensure_blocked", ops.events)
                    self.assertEqual("rollback" in ops.events, safe)
                    if safe:
                        self.assertLess(ops.events.index("ensure_blocked"), ops.events.index("rollback"))
                    self.assertEqual("previous_health" in ops.events, safe)
                    self.assertEqual(ops.events[-1], "unlock")

    def test_uncertain_journal_never_attempts_rollback(self):
        class BrokenJournal(Operations):
            def verify_health(self, r): raise RuntimeError("health failed")
            def ensure_blocked(self, r): raise RuntimeError("journal unavailable")
        ops = BrokenJournal()
        with self.assertRaises(tx.DeploymentFailed) as exc: tx.deploy(release(), ops)
        self.assertIn("state uncertain", str(exc.exception))
        self.assertNotIn("rollback", ops.events)

    def test_failed_rollback_stays_blocked(self):
        class BadRollback(Operations):
            def verify_health(self, r): raise RuntimeError("bad")
            def rollback_previous(self): raise RuntimeError("bad rollback")
        ops = BadRollback()
        with self.assertRaises(tx.DeploymentFailed) as exc: tx.deploy(release(), ops)
        self.assertIn("blocked", str(exc.exception))
        self.assertTrue(ops.state["blocked"])


if __name__ == "__main__":
    unittest.main()
