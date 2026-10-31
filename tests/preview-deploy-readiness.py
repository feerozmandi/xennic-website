#!/usr/bin/env python3
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
p = Path(__file__).resolve().parents[1] / "scripts/preview-deploy-readiness.py"
spec = importlib.util.spec_from_file_location("preview_readiness", p)
readiness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readiness)


class ReadinessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "config").mkdir(mode=0o700)
        (self.root / "secrets").mkdir(mode=0o700)
        self.uid = os.geteuid()
        self.token = b"synthetic-registry-token"

    def put(self, path, value):
        p = self.root / path
        p.write_text(value)
        p.chmod(0o600)

    def valid(self):
        self.put("config/verified-host-fingerprint", "SHA256:" + "A" * 43)
        self.put("secrets/preview.env", "PREVIEW_POSTGRES_USER=test\nPREVIEW_POSTGRES_DB=test\n"
                 "PREVIEW_POSTGRES_PASSWORD=synthetic\nPREVIEW_DATABASE_URL=synthetic\nPREVIEW_PAYLOAD_SECRET=synthetic\n")
        self.put("secrets/oauth2-proxy.cfg", 'client_id="synthetic"\nclient_secret="synthetic"\ncookie_secret="synthetic"\n')
        self.put("config/backup.json", json.dumps({"approved": True, "transport": "sftp", "host": "backup.example.org",
                 "remote_directory": "/private/preview", "age_recipient": "age1" + "q" * 58}))
        for p in ("secrets/backup-ssh-key", "secrets/backup-identity", "config/backup-known-hosts"):
            self.put(p, "synthetic-only")

    def check(self, token=None):
        return readiness.check(self.root, self.uid, self.token if token is None else token)

    def test_missing_fingerprint_fails_without_creating_files(self):
        before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        with self.assertRaisesRegex(readiness.NotReady, "fingerprint"):
            self.check()
        self.assertEqual(before, sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*")))

    def test_missing_token_secrets_and_backup_fail(self):
        self.valid()
        for path in ("secrets/preview.env", "secrets/oauth2-proxy.cfg", "config/backup.json", "secrets/backup-ssh-key"):
            with self.subTest(path=path):
                p = self.root / path
                content = p.read_text()
                p.unlink()
                with self.assertRaises(readiness.NotReady): self.check()
                self.put(path, content)
        with self.assertRaisesRegex(readiness.NotReady, "GHCR"): self.check(b"")

    def test_invalid_empty_values_unapproved_backup_and_bad_permissions_fail(self):
        self.valid()
        self.put("secrets/preview.env", 'PREVIEW_POSTGRES_USER=test\nPREVIEW_POSTGRES_DB=test\n'
                 'PREVIEW_POSTGRES_PASSWORD=""\nPREVIEW_DATABASE_URL=test\nPREVIEW_PAYLOAD_SECRET=test\n')
        with self.assertRaises(readiness.NotReady): self.check()
        self.valid()
        self.put("config/backup.json", json.dumps({"approved": False, "transport": "sftp", "host": "localhost",
                 "remote_directory": "/backup", "age_recipient": "age1" + "q" * 58}))
        with self.assertRaises(readiness.NotReady): self.check()
        self.valid()
        (self.root / "secrets/preview.env").chmod(0o644)
        with self.assertRaises(readiness.NotReady): self.check()

    def test_local_backup_ip_is_rejected(self):
        self.valid()
        for host in ("127.5.4.3", "0.0.0.0", "169.254.1.2", "185.192.113.85"):
            with self.subTest(host=host):
                self.put("config/backup.json", json.dumps({"approved": True, "transport": "sftp", "host": host,
                         "remote_directory": "/private/preview", "age_recipient": "age1" + "q" * 58}))
                with self.assertRaises(readiness.NotReady): self.check()

    def test_only_local_syntactic_checks_pass_for_complete_synthetic_fixture(self):
        self.valid()
        self.assertIsNone(self.check())

    def test_symlink_secret_fails(self):
        self.valid()
        path = self.root / "secrets/preview.env"
        path.unlink()
        path.symlink_to(self.root / "secrets/oauth2-proxy.cfg")
        with self.assertRaises(readiness.NotReady): self.check()


if __name__ == "__main__":
    unittest.main()
