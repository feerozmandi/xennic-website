#!/usr/bin/env python3
"""Shared host-side lock primitive; no deployment or state changes are performed."""
import contextlib
import fcntl
import os
from pathlib import Path
import stat

LOCK_PATH = Path("/run/lock/xennic-preview-deploy.lock")


class UnsafeLock(RuntimeError):
    pass


@contextlib.contextmanager
def acquire_lock(path=LOCK_PATH, *, owner_uid=0, nonblocking=False):
    """Hold an exclusive advisory lock until the entire caller transaction exits.

    Production callers must use the default fixed path and root owner. Both CI
    and any manual/rollback operation must call the same primitive; this helper
    alone does not guarantee that a future caller actually uses it correctly.
    """
    path = Path(path)
    if not path.is_absolute():
        raise UnsafeLock("lock path must be absolute")
    try:
        parent = os.lstat(path.parent)
        # A root-owned sticky directory, e.g. /run/lock, protects root-owned
        # entries against removal by other users. Reject writable non-sticky dirs.
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != owner_uid or
                ((parent.st_mode & 0o022) and not (parent.st_mode & stat.S_ISVTX))):
            raise UnsafeLock("unsafe lock parent")
        flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise UnsafeLock("cannot open lock safely") from exc
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != owner_uid or
                info.st_nlink != 1 or info.st_mode & 0o077):
            raise UnsafeLock("unsafe lock file")
        fcntl.flock(fd, fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0))
        # Validate the name still refers to the file locked; no path replacement.
        named = os.lstat(path)
        if (named.st_dev, named.st_ino) != (info.st_dev, info.st_ino):
            raise UnsafeLock("lock path changed")
        yield
    finally:
        os.close(fd)
