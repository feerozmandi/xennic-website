#!/usr/bin/python3
"""Install the CI gateway on the preview host; root only, no arguments.

The gateway is the *only* thing the deploy key in GitHub is allowed to run, so
this installer keeps that surface as small as the rest of the privileged
helpers: the source must be committed at a fixed path, the installed copy is
root-owned and not writable by group or other, the phase scripts it drives must
already be installed and equally clean, and the installer prints the SHA-256 of
what it installed so the release report can pin it.

It does not create users, keys, sudoers rules or SSH configuration, and it does
not deploy anything. Those stay manual, one-time steps in the runbook.
"""
import hashlib
import os
from pathlib import Path
import stat
import sys

sys.dont_write_bytecode = True

SOURCE = Path('/root/xennic-preview-ci-gateway/preview-ci-gateway.py')
WRAPPER = Path('/root/xennic-preview-ci-gateway/preview-ci-gateway-ssh')
TARGET = Path('/usr/local/libexec/xennic-preview/ci-gateway')
TARGET_WRAPPER = TARGET.with_name('ci-gateway-ssh')
HELPERS = TARGET.parent
# The gateway drives these installed files; without them it can only fail.
REQUIRED = ('release-check', 'pull-image', 'preview-deploy-backend.py',
            'preview-deploy-manifest.py', 'preview-deploy-state.py',
            'preview-fixed-operations.py', 'preview-backup-operation.py')
MODE = 0o755
MAX_BYTES = 200 * 1024


def clean_regular(path):
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode):
        raise RuntimeError(f'{path} is not a regular file')
    if info.st_uid != 0 or info.st_mode & 0o022:
        raise RuntimeError(f'{path} has an unsafe owner or mode')


def main():
    if os.geteuid() != 0 or len(sys.argv) != 1:
        print('CI gateway install requires root and no arguments.', file=sys.stderr)
        return 1
    os.umask(0o077)
    try:
        if HELPERS.resolve() != Path('/usr/local/libexec/xennic-preview'):
            raise RuntimeError('unexpected installation directory')
        info = os.lstat(HELPERS)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise RuntimeError('unsafe installation directory')
        clean_regular(SOURCE)
        if SOURCE.stat().st_size > MAX_BYTES:
            raise RuntimeError('gateway source is too large')
        data = SOURCE.read_bytes()
        if not data.startswith(b'#!/usr/bin/python3'):
            raise RuntimeError('gateway source has an unexpected interpreter')
        clean_regular(WRAPPER)
        wrapper = WRAPPER.read_bytes()
        if not wrapper.startswith(b'#!/bin/bash'):
            raise RuntimeError('wrapper has an unexpected interpreter')
        for name in REQUIRED:
            clean_regular(HELPERS / name)
        for path in (TARGET, TARGET_WRAPPER):
            if os.path.lexists(path):
                clean_regular(path)
        staged = HELPERS / '.ci-gateway.staged'
        if os.path.lexists(staged):
            raise RuntimeError('staged file already exists')
        fd = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(staged, MODE)
        os.replace(staged, TARGET)
        installed = TARGET.read_bytes()
        if installed != data:
            raise RuntimeError('installed gateway differs from the source')
        staged_wrapper = HELPERS / '.ci-gateway-ssh.staged'
        if os.path.lexists(staged_wrapper):
            raise RuntimeError('staged wrapper already exists')
        fd = os.open(staged_wrapper, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(wrapper)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(staged_wrapper, MODE)
        os.replace(staged_wrapper, TARGET_WRAPPER)
        if TARGET_WRAPPER.read_bytes() != wrapper:
            raise RuntimeError('installed wrapper differs from the source')
        print(f'CI gateway installed: {hashlib.sha256(installed).hexdigest()} ({len(installed)} bytes)')
        print(f'CI gateway wrapper installed: {hashlib.sha256(wrapper).hexdigest()} ({len(wrapper)} bytes)')
    except (OSError, RuntimeError) as exc:
        print(f'CI gateway install failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
