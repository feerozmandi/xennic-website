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
import os
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


class LeftoverMessageTest(unittest.TestCase):
    """A refusal has to name what is in the way, and where it is.

    An operator on the host was told "previous or incomplete helper
    refresh exists" and could not act on it: the message named no path,
    so it did not say which directory to look at or what removing it
    would mean. The message now carries the path and says what the
    directory holds.
    """

    def test_the_message_names_the_directory_that_is_in_the_way(self):
        real = os.path.lexists
        try:
            os.path.lexists = lambda p: True if str(p) == str(installer.REFRESH_BACKUP) else real(p)
            message = installer.leftover_message(installer.NEW_DIR, installer.REFRESH_BACKUP,
                                                 "helper refresh")
        finally:
            os.path.lexists = real
        self.assertIn(str(installer.REFRESH_BACKUP), message)
        self.assertIn("helper refresh", message)

    def test_the_message_names_every_leftover_that_is_there(self):
        real = os.path.lexists
        try:
            os.path.lexists = lambda p: True if str(p) in (str(installer.NEW_DIR),
                                                           str(installer.REFRESH_BACKUP)) else real(p)
            message = installer.leftover_message(installer.NEW_DIR, installer.REFRESH_BACKUP,
                                                 "helper refresh")
        finally:
            os.path.lexists = real
        self.assertIn(str(installer.NEW_DIR), message)
        self.assertIn(str(installer.REFRESH_BACKUP), message)

    def test_the_message_says_what_removing_it_means(self):
        real = os.path.lexists
        try:
            os.path.lexists = lambda p: True if str(p) == str(installer.REFRESH_BACKUP) else real(p)
            message = installer.leftover_message(installer.NEW_DIR, installer.REFRESH_BACKUP,
                                                 "helper refresh")
        finally:
            os.path.lexists = real
        self.assertIn("keeps the set from before the last one", message)
        self.assertIn("removed", message)

    def test_the_refresh_refuses_with_that_message(self):
        source = inspect.getsource(installer.refresh)
        self.assertIn("leftover_message(NEW_DIR, REFRESH_BACKUP", source)

    def test_the_update_refuses_with_that_message(self):
        source = inspect.getsource(installer.upgrade)
        self.assertIn("leftover_message(NEW_DIR, BACKUP", source)


if __name__ == "__main__":
    unittest.main()
