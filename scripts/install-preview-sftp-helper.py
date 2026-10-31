#!/usr/bin/python3
"""Install all fixed preview helpers and trusted modules; deployment remains disabled.

A root administrator must stage these exact files under the fixed private
/root/xennic-preview-install directory. This intentionally refuses upgrades and
an already-existing destination; it does not install sudoers or SSH access.
"""
import os
from pathlib import Path
import shutil
import stat
import sys

SOURCE = Path('/root/xennic-preview-install')
PARENT = Path('/usr/local/libexec')
TARGET = PARENT / 'xennic-preview'
FILES = ('preview-backup-sftp.py', 'preview-backup-operation.py', 'preview-pull-image.py', 'preview-age-backup.py',
         'preview-deploy-readiness.py', 'preview-deploy-state.py', 'preview-deploy-manifest.py',
         'preview-deploy-backend.py', 'preview-deploy-transaction.py', 'preview-deploy-lock.py',
         'preview-internal-health.py', 'preview-compose-operations.py', 'preview-release-verifier.py',
         'preview-fixed-operations.py')
EXECUTABLES = {'preview-backup-sftp.py': ('sftp-transfer',), 'preview-backup-operation.py': ('backup-verify', 'preview-backup-operation.py'),
               'preview-pull-image.py': ('pull-image',), 'preview-fixed-operations.py':
               ('release-check', 'current-check', 'migrate', 'activate', 'health', 'rollback')}


def check_dir(path):
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise RuntimeError('unsafe installation directory')


def main():
    if os.geteuid() != 0 or len(sys.argv) != 1:
        raise RuntimeError('root and no arguments required')
    for path in (Path('/root'), SOURCE, Path('/usr'), Path('/usr/local'), PARENT):
        check_dir(path)
    if os.path.lexists(TARGET):
        raise RuntimeError('target already exists; no update performed')
    staged = []
    try:
        for name in FILES:
            fd = os.open(SOURCE / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1 or info.st_mode & 0o022:
                os.close(fd)
                raise RuntimeError('unsafe installation source')
            staged.append((name, fd))
        TARGET.mkdir(mode=0o700)
        try:
            for name, fd in staged:
                for installed in EXECUTABLES.get(name, (name,)):
                    os.lseek(fd, 0, os.SEEK_SET)
                    destination = TARGET / installed
                    out = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o700 if name in EXECUTABLES else 0o600)
                    with os.fdopen(os.dup(fd), 'rb') as src, os.fdopen(out, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                        dst.flush()
                        os.fsync(dst.fileno())
            directory = os.open(TARGET, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            try: os.fsync(directory)
            finally: os.close(directory)
        except Exception:
            # Target is new and root-private, and only our fixed files can exist.
            for path in TARGET.iterdir(): path.unlink()
            TARGET.rmdir()
            raise
    finally:
        for _, fd in staged: os.close(fd)
    print('Fixed preview helpers installed; no deploy or SSH access enabled.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError):
        print('Fixed SFTP helper installation refused or failed.', file=sys.stderr)
        raise SystemExit(1)
