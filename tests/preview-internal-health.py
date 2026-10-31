#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

sys.dont_write_bytecode = True
p = Path(__file__).resolve().parents[1] / "scripts/preview-internal-health.py"
spec = importlib.util.spec_from_file_location("preview_health", p)
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


class HealthTest(unittest.TestCase):
    def test_healthy_checks_database_and_app_inside_fixed_project(self):
        responses = iter(["a" * 64, "healthy", "b" * 64, "healthy", "1", ""])
        commands = []
        def fake_run(command):
            commands.append(command)
            return next(responses)
        with mock.patch.object(health, "run", side_effect=fake_run):
            health.check_once()
        self.assertEqual(commands[0][-3:], ["ps", "-q", "postgres"])
        self.assertEqual(commands[2][-3:], ["ps", "-q", "app"])
        self.assertIn("SELECT 1", commands[4][-1])
        self.assertEqual(commands[5][-3:-1], ["node", "-e"])
        self.assertIn("/health", commands[5][-1])
        self.assertIn("xennic-preview", commands[0])

    def test_bad_containers_and_database_fail(self):
        for responses in (["bad-id"], ["a" * 64, "unhealthy"],
                          ["a" * 64, "healthy", "b" * 64, "healthy", "2"]):
            with self.subTest(responses=responses), mock.patch.object(health, "run", side_effect=iter(responses)):
                with self.assertRaises(health.Unhealthy): health.check_once()

    def test_app_failure_not_treated_as_success(self):
        responses = ["a" * 64, "healthy", "b" * 64, "healthy", "1", health.Unhealthy("app down")]
        with mock.patch.object(health, "run", side_effect=responses):
            with self.assertRaises(health.Unhealthy): health.check_once()

    @mock.patch.object(health.subprocess, "run")
    def test_run_has_sanitized_environment_and_no_stderr(self, proc):
        proc.return_value = subprocess.CompletedProcess([], 0, stdout=b"healthy\n")
        self.assertEqual(health.run(["/usr/bin/docker", "inspect"]), "healthy")
        self.assertEqual(proc.call_args.kwargs["env"], health.ENV)
        self.assertEqual(proc.call_args.kwargs["stderr"], subprocess.DEVNULL)
        self.assertEqual(proc.call_args.kwargs["stdin"], subprocess.DEVNULL)
        proc.return_value = subprocess.CompletedProcess([], 1, stdout=b"sensitive output")
        with self.assertRaises(health.Unhealthy) as exc: health.run(["ignored"])
        self.assertNotIn("sensitive", str(exc.exception))

    def test_retries_fail_closed(self):
        with mock.patch.object(health, "check_once", side_effect=health.Unhealthy("down")) as check, \
             mock.patch.object(health.time, "sleep") as sleep, \
             mock.patch.object(health.sys, "stderr"):
            self.assertEqual(health.main(), 1)
            self.assertEqual(check.call_count, 12)
            self.assertEqual(sleep.call_count, 11)


if __name__ == "__main__":
    unittest.main()
