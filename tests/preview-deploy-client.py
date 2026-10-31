#!/usr/bin/env python3
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import sys
sys.dont_write_bytecode = True
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "preview-deploy-client.py"
spec = importlib.util.spec_from_file_location("preview_deploy_client", SCRIPT)
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class ClientTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.key = Path(self.tmp.name) / "key"
        self.hosts = Path(self.tmp.name) / "known_hosts"
        self.key.touch(mode=0o600)
        self.hosts.touch(mode=0o600)
        self.env = {
            "GITHUB_REPOSITORY": "feerozmandi/xennic-website",
            "GITHUB_SHA": "a" * 40,
            "GITHUB_RUN_NUMBER": "12",
            "PREVIEW_IMAGE_DIGEST": "sha256:" + "b" * 64,
            "PREVIEW_GHCR_TOKEN": "synthetic-only-token",
            "PREVIEW_SSH_KEY_FILE": str(self.key),
            "PREVIEW_KNOWN_HOSTS_FILE": str(self.hosts),
        }

    def test_strict_ssh_and_token_only_on_stdin(self):
        command, payload = client.prepare(self.env)
        self.assertIn("StrictHostKeyChecking=yes", command)
        self.assertIn("IdentitiesOnly=yes", command)
        self.assertIn("BatchMode=yes", command)
        self.assertIn(f"UserKnownHostsFile={self.hosts}", command)
        self.assertIn("ClearAllForwardings=yes", command)
        self.assertEqual(command[-2:], ["preview-deploy@185.192.113.199", "xennic-preview-deploy"])
        self.assertNotIn(self.env["PREVIEW_GHCR_TOKEN"], " ".join(command))
        first, second, empty = payload.split(b"\n")
        self.assertEqual(json.loads(first)["digest"], self.env["PREVIEW_IMAGE_DIGEST"])
        self.assertEqual(second, b"synthetic-only-token")
        self.assertEqual(empty, b"")

    def test_bad_values_rejected(self):
        for key, value in [
            ("GITHUB_REPOSITORY", "attacker/repo"), ("GITHUB_SHA", "wrong"),
            ("GITHUB_RUN_NUMBER", "0"), ("GITHUB_RUN_NUMBER", "1\n2"),
            ("PREVIEW_IMAGE_DIGEST", "latest"), ("PREVIEW_GHCR_TOKEN", "token\ninjection"),
            ("PREVIEW_GHCR_TOKEN", ""), ("PREVIEW_SSH_KEY_FILE", "relative"),
            ("PREVIEW_KNOWN_HOSTS_FILE", "/nonexistent/known_hosts"),
        ]:
            with self.subTest(key=key):
                env = dict(self.env)
                env[key] = value
                with self.assertRaises(client.ClientError):
                    client.prepare(env)

    def test_rejects_publicly_readable_files_and_symlinks(self):
        self.key.chmod(0o644)
        with self.assertRaises(client.ClientError):
            client.prepare(self.env)
        self.key.chmod(0o600)
        link = Path(self.tmp.name) / "link"
        link.symlink_to(self.hosts)
        with self.assertRaises(client.ClientError):
            client.prepare(dict(self.env, PREVIEW_KNOWN_HOSTS_FILE=str(link)))

    @mock.patch.object(client.subprocess, "run")
    def test_secret_not_forwarded_in_environment_or_output(self, run):
        run.return_value.returncode = 1
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, self.env, clear=True), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = client.main()
        self.assertEqual(result, 1)
        kwargs = run.call_args.kwargs
        self.assertNotIn("PREVIEW_GHCR_TOKEN", kwargs["env"])
        self.assertEqual(kwargs["stdout"], client.subprocess.DEVNULL)
        self.assertEqual(kwargs["stderr"], client.subprocess.DEVNULL)
        self.assertNotIn(self.env["PREVIEW_GHCR_TOKEN"], stdout.getvalue() + stderr.getvalue())

    @mock.patch.object(client.subprocess, "run")
    def test_invalid_input_never_starts_ssh(self, run):
        env = dict(self.env, PREVIEW_GHCR_TOKEN="bad\nsecret")
        with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(client.main(), 1)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
