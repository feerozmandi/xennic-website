#!/usr/bin/env python3
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
SCRIPT = Path(__file__).resolve().parents[1] / "scripts/preview-deploy-lock.py"
spec = importlib.util.spec_from_file_location("preview_lock", SCRIPT)
lock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lock)


class LockTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.path = self.directory / "preview.lock"
        self.uid = os.geteuid()

    def test_exclusive_lock_across_processes_and_release(self):
        code = """
import importlib.util, os, sys
sys.dont_write_bytecode = True
s=importlib.util.spec_from_file_location('testlock', sys.argv[1])
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
try:
    with m.acquire_lock(sys.argv[2], owner_uid=os.geteuid(), nonblocking=True): pass
except BlockingIOError:
    sys.exit(3)
"""
        def attempt():
            return subprocess.run([sys.executable, "-c", code, str(SCRIPT), str(self.path)],
                                  capture_output=True).returncode
        with lock.acquire_lock(self.path, owner_uid=self.uid):
            self.assertEqual(attempt(), 3)
        self.assertEqual(attempt(), 0)

    def test_symlink_and_unsafe_file_are_rejected(self):
        target = self.directory / "target"
        target.write_text("unchanged")
        self.path.symlink_to(target)
        with self.assertRaises(lock.UnsafeLock):
            with lock.acquire_lock(self.path, owner_uid=self.uid):
                pass
        self.assertEqual(target.read_text(), "unchanged")
        self.path.unlink()
        self.path.touch(mode=0o644)
        with self.assertRaises(lock.UnsafeLock):
            with lock.acquire_lock(self.path, owner_uid=self.uid):
                pass

    def test_parent_owner_and_permissions(self):
        self.directory.chmod(0o777)
        with self.assertRaises(lock.UnsafeLock):
            with lock.acquire_lock(self.path, owner_uid=self.uid):
                pass
        self.directory.chmod(0o700)
        with self.assertRaises(lock.UnsafeLock):
            with lock.acquire_lock(self.path, owner_uid=self.uid + 1):
                pass
        with self.assertRaises(lock.UnsafeLock):
            with lock.acquire_lock("relative", owner_uid=self.uid):
                pass

    def test_sticky_parent_allowed(self):
        self.directory.chmod(0o1777)
        with lock.acquire_lock(self.path, owner_uid=self.uid):
            self.assertTrue(self.path.exists())
        self.directory.chmod(0o700)


if __name__ == "__main__":
    unittest.main()
