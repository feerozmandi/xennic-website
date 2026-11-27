#!/usr/bin/env python3
"""The refresh path of the reviewed helper installer.

The refresh path is the one that runs on a host that is already deployed: it
replaces the helper files and nothing else. The first-install paths refuse a
host that holds a journal or any running preview resource, because there the
preview data must not be touched at all; this path is the opposite, and it
runs on exactly that host.

These tests check its shape without a host. The disposable runner in
tests/preview-installer-upgrade-ci.sh is where the swap itself is exercised.
"""
import hashlib
import importlib.util
import inspect
from pathlib import Path
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("installer_refresh", SCRIPTS / "install-preview-sftp-helper.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class RefreshPathTest(unittest.TestCase):
    def test_the_refresh_path_is_reachable_and_named(self):
        self.assertTrue(callable(installer.refresh))
        self.assertIn("'--refresh'", inspect.getsource(installer.main))

    def test_the_refresh_path_installs_the_reviewed_set_of_this_release(self):
        source = inspect.getsource(installer.refresh)
        self.assertIn("REFRESH_MANIFEST", source)
        self.assertIn("ACTIVATION_FILES", source)

    def test_the_refresh_path_never_requires_a_pristine_host(self):
        self.assertNotIn("assert_pristine", inspect.getsource(installer.refresh))

    def test_the_refresh_path_holds_the_deployment_lock_and_keeps_the_old_set(self):
        source = inspect.getsource(installer.refresh)
        self.assertIn("acquire_lock", source)
        self.assertIn("REFRESH_BACKUP", source)

    def test_the_refresh_digest_is_the_digest_of_this_repository_helper_set(self):
        data = {name: (SCRIPTS / name).read_bytes() for name in installer.ACTIVATION_FILES}
        lines = "".join(f"{hashlib.sha256(data[name]).hexdigest()}  scripts/{name}\n"
                        for name in installer.ACTIVATION_FILES)
        self.assertEqual(hashlib.sha256(lines.encode("ascii")).hexdigest(), installer.REFRESH_MANIFEST)

    def test_the_refresh_staging_directory_is_its_own(self):
        self.assertNotEqual(installer.REFRESH_SOURCE, installer.SOURCE)
        self.assertNotEqual(installer.REFRESH_BACKUP, installer.BACKUP)


if __name__ == "__main__":
    unittest.main()
