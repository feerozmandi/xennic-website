#!/usr/bin/python3
"""Transfer one pending release's fixed age bundle over pinned-key SFTP.

Root-only operation; reads no command, path, host, or environment from its input.
It does not create snapshots, stop writers, perform restore, or enable deployment.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path('/srv/xennic-preview')
WORK = ROOT / 'work'
SOURCE = WORK / 'backup.age'
DOWNLOADED = WORK / 'verified.age'
STATE = ROOT / 'state'
ENV = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'LANG': 'C'}


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


manifest = load('sftp_manifest', 'preview-deploy-manifest.py')
readiness = load('sftp_readiness', 'preview-deploy-readiness.py')
states = load('sftp_state', 'preview-deploy-state.py')


class TransferFailed(RuntimeError):
    pass


def private_directory(path):
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
        raise TransferFailed('unsafe backup directory')


def digest_file(path):
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1 or info.st_mode & 0o077 or info.st_size == 0:
            raise TransferFailed('unsafe encrypted backup')
        digest = hashlib.sha256()
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()
    finally:
        os.close(fd)


def transfer(raw_release):
    if os.geteuid() != 0:
        raise TransferFailed('root required')
    release = manifest.validate_manifest(raw_release)
    for directory in (ROOT, WORK, STATE): private_directory(directory)
    state = states.Journal().read()
    if not state['blocked'] or state['pending'] != release:
        raise TransferFailed('release is not pending')
    config = readiness.backup_config(ROOT, 0)
    before = digest_file(SOURCE)
    if DOWNLOADED.exists() or DOWNLOADED.is_symlink():
        raise TransferFailed('verification path already exists')
    filename = f"xennic-{release['run_number']}-{secrets.token_hex(16)}.age"
    remote = config['remote_directory'].rstrip('/') + '/' + filename
    # Config validates every host, user and remote directory character; names
    # and paths below are fixed or generated. No shell is involved.
    batch = f'put {SOURCE} {remote}.part\nrename {remote}.part {remote}\nget {remote} {DOWNLOADED}\n'.encode('ascii')
    args = ['/usr/bin/sftp', '-q', '-F', '/dev/null', '-b', '-', '-P', str(config['port']),
            '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'GlobalKnownHostsFile=/dev/null', '-o', f'UserKnownHostsFile={ROOT}/config/backup-known-hosts',
            '-o', f'IdentityFile={ROOT}/secrets/backup-ssh-key', '-o', 'ClearAllForwardings=yes',
            '-o', 'ConnectTimeout=15', '-o', 'ConnectionAttempts=1',
            f"{config['user']}@{config['host']}"]
    try:
        result = subprocess.run(args, input=batch, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                env=ENV, timeout=300, check=False)
        if result.returncode != 0 or digest_file(DOWNLOADED) != before or digest_file(SOURCE) != before:
            raise TransferFailed('backup upload or readback failed')
        # A root-owned local record binds the downloaded ciphertext to the run.
        # It is not an external signature and does not establish offsite location.
        record = {'version': 1, 'release': release, 'remote_path': remote, 'sha256': before}
        path = STATE / f"backup-{release['run_number']}.json"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            with os.fdopen(fd, 'wb', closefd=False) as stream:
                stream.write(json.dumps(record, sort_keys=True, separators=(',', ':')).encode() + b'\n')
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            os.close(fd)
        dirfd = os.open(STATE, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try: os.fsync(dirfd)
        finally: os.close(dirfd)
        return record
    finally:
        DOWNLOADED.unlink(missing_ok=True)


def main():
    if len(sys.argv) != 1:
        print('Invalid fixed backup operation', file=sys.stderr)
        return 1
    os.umask(0o077)
    try:
        raw = sys.stdin.buffer.read(manifest.MAX_MANIFEST_BYTES + 1).strip()
        transfer(raw)
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired):
        print('Backup transfer failed; release remains blocked', file=sys.stderr)
        return 1
    print('Encrypted backup transfer and readback verified')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
