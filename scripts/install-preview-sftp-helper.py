#!/usr/bin/python3
"""Install all fixed preview helpers and trusted modules; deployment remains disabled.

A root administrator stages these exact files under the fixed private
/root/xennic-preview-install directory. The no-argument path remains initial
installation only. The explicitly bounded --upgrade path verifies both fixed
versions, preserves the previous directory, and refuses uncertain state.
Neither path installs sudoers, SSH access, or deploys the application.
"""
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

sys.dont_write_bytecode = True

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

# Specifically reviewed transition: installed 449a helpers to merged dev f18b
# helpers. These are SHA-256 of the ordered sha256sum lines for FILES using the
# path scripts/<name>. A different version is not automatically trusted.
OLD_MANIFEST = '105cde2ecdac77c14b70cdb9d1f1c22fe9bd9f93bad466a93bb3c1e476f72f7a'
NEW_MANIFEST = 'ec0ea6d51210c23b85e94a7f4aac902d39a86f247f1eb80c618265f4b5fd55fa'
INCOMING = SOURCE / 'incoming'
NEW_DIR = PARENT / '.xennic-preview-update'
BACKUP = PARENT / '.xennic-preview-previous'
ROOT = Path('/srv/xennic-preview')
# Reviewed pre-first-deployment transition from the installed f18b helpers and
# exact loopback Compose file to this release's isolated-network topology.
NETWORK_MANIFEST = '4648e1d3c73c1ec61b2fe1eefcdd9e155abdb02d499d68838b059185a74f9366'
OLD_COMPOSE = '18a97bc2c21a6d623a54c81d07a49e44f6468cd225f0ce34a73f3760d3d0a373'
NETWORK_COMPOSE = '44639d7d7f3678c8cb772d02768a8c51320ae4f71e7ccd3829b3d9d5126f2b7c'
INCOMING_NETWORK = SOURCE / 'incoming-network'
BACKUP_NETWORK = PARENT / '.xennic-preview-before-network'
COMPOSE = ROOT / 'config/compose.yml'
COMPOSE_BACKUP = ROOT / 'config/.compose-before-network.yml'
COMPOSE_NEW = ROOT / 'config/.compose-network-update.yml'
COMPOSE_ROLLBACK = ROOT / 'config/.compose-network-rollback.yml'


def check_dir(path):
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise RuntimeError('unsafe installation directory')


def read_private(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1 or
                info.st_mode & 0o077 or info.st_size > 2_000_000):
            raise RuntimeError('unsafe helper file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            return stream.read()
    finally:
        os.close(fd)


def private_dir(path):
    check_dir(path)
    if os.lstat(path).st_mode & 0o077:
        raise RuntimeError('directory is not private')


def verified_sources(directory, expected):
    private_dir(directory)
    data = {name: read_private(directory / name) for name in FILES}
    lines = ''.join(f'{hashlib.sha256(data[name]).hexdigest()}  scripts/{name}\n' for name in FILES)
    if hashlib.sha256(lines.encode('ascii')).hexdigest() != expected:
        raise RuntimeError('helper version is not approved')
    return data


def installed_matches(directory, data):
    private_dir(directory)
    expected = {installed for name in FILES for installed in EXECUTABLES.get(name, (name,))}
    if {p.name for p in directory.iterdir()} != expected:
        raise RuntimeError('unexpected installed helper')
    for name in FILES:
        for installed in EXECUTABLES.get(name, (name,)):
            path = directory / installed
            if read_private(path) != data[name]:
                raise RuntimeError('installed helper differs from approved version')
            mode = stat.S_IMODE(os.lstat(path).st_mode)
            if mode != (0o700 if name in EXECUTABLES else 0o600):
                raise RuntimeError('installed helper mode differs')


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def verify_backend():
    module(TARGET / 'preview-deploy-backend.py', 'installer_backend').FixedRunner().verify_helpers()


def assert_pristine():
    # This update is deliberately limited to the verified pre-first-install
    # state. Unknown journal, data, project resources or work files fail closed.
    for path in (ROOT, ROOT / 'config', ROOT / 'secrets', ROOT / 'state', ROOT / 'work'):
        private_dir(path)
    if {p.name for p in ROOT.iterdir()} != {'config', 'secrets', 'state', 'work'}:
        raise RuntimeError('unexpected preview root contents')
    if any((ROOT / 'state').iterdir()) or any((ROOT / 'work').iterdir()):
        raise RuntimeError('preview state or work is not empty')
    env = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'LANG': 'C'}
    for args in (
        ['ps', '-aq', '--filter', 'label=com.docker.compose.project=xennic-preview'],
        ['volume', 'ls', '-q', '--filter', 'label=com.docker.compose.project=xennic-preview'],
        ['network', 'ls', '-q', '--filter', 'label=com.docker.compose.project=xennic-preview'],
    ):
        result = subprocess.run(['/usr/bin/docker', *args], env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30, check=True)
        if result.stdout.strip(): raise RuntimeError('existing preview resources')
    for args in (['ps', '-a', '--format', '{{.Names}}'], ['volume', 'ls', '--format', '{{.Name}}'],
                 ['network', 'ls', '--format', '{{.Name}}']):
        result = subprocess.run(['/usr/bin/docker', *args], env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30, check=True)
        if len(result.stdout) > 16_000_000: raise RuntimeError('resource inventory too large')
        if any(x.startswith(('xennic-preview_', 'xennic-preview-')) for x in result.stdout.decode('utf-8').splitlines()):
            raise RuntimeError('existing named preview resource')


def sync_parent():
    fd = os.open(PARENT, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try: os.fsync(fd)
    finally: os.close(fd)


def upgrade():
    for path in (Path('/root'), SOURCE, Path('/usr'), Path('/usr/local'), PARENT):
        check_dir(path)
    private_dir(SOURCE)
    private_dir(INCOMING)
    if {p.name for p in SOURCE.iterdir()} != set(FILES) | {'install-preview-sftp-helper.py', 'incoming'}:
        raise RuntimeError('unexpected staging contents')
    if {p.name for p in INCOMING.iterdir()} != set(FILES) | {'install-preview-sftp-helper.py'}:
        raise RuntimeError('unexpected incoming staging contents')
    if os.path.lexists(NEW_DIR) or os.path.lexists(BACKUP):
        raise RuntimeError('previous or incomplete helper update exists')
    old = verified_sources(SOURCE, OLD_MANIFEST)
    new = verified_sources(INCOMING, NEW_MANIFEST)
    installed_matches(TARGET, old)
    verify_backend()
    locks = module(TARGET / 'preview-deploy-lock.py', 'installer_lock')
    with locks.acquire_lock(nonblocking=True):
        # Recheck after acquiring the exact deployment lock.
        installed_matches(TARGET, old)
        assert_pristine()
        NEW_DIR.mkdir(mode=0o700)
        for name in FILES:
            for installed in EXECUTABLES.get(name, (name,)):
                mode = 0o700 if name in EXECUTABLES else 0o600
                fd = os.open(NEW_DIR / installed, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, mode)
                try:
                    with os.fdopen(fd, 'wb', closefd=False) as stream:
                        stream.write(new[name]); stream.flush(); os.fsync(stream.fileno())
                finally: os.close(fd)
        fd = os.open(NEW_DIR, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try: os.fsync(fd)
        finally: os.close(fd)
        installed_matches(NEW_DIR, new)
        renamed_old = renamed_new = False
        try:
            os.rename(TARGET, BACKUP); renamed_old = True; sync_parent()
            os.rename(NEW_DIR, TARGET); renamed_new = True; sync_parent()
            installed_matches(TARGET, new)
            verify_backend()
        except BaseException:
            # Preserve both directories; restore original on a recoverable error.
            if renamed_new: os.rename(TARGET, NEW_DIR)
            if renamed_old: os.rename(BACKUP, TARGET)
            sync_parent()
            raise
    print('Fixed preview helpers upgraded; previous helpers preserved; no deployment started.')


def write_exclusive(path, data, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, mode)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
    finally: os.close(fd)


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try: os.fsync(fd)
    finally: os.close(fd)


def upgrade_network():
    """Upgrade only the known pre-deployment installation, preserving both backups."""
    for path in (Path('/root'), SOURCE, Path('/usr'), Path('/usr/local'), PARENT):
        check_dir(path)
    private_dir(SOURCE); private_dir(INCOMING); private_dir(INCOMING_NETWORK)
    if {p.name for p in SOURCE.iterdir()} != set(FILES) | {'install-preview-sftp-helper.py', 'incoming', 'incoming-network'}:
        raise RuntimeError('unexpected staging contents')
    if {p.name for p in INCOMING.iterdir()} != set(FILES) | {'install-preview-sftp-helper.py'}:
        raise RuntimeError('unexpected current staging contents')
    if {p.name for p in INCOMING_NETWORK.iterdir()} != set(FILES) | {'install-preview-sftp-helper.py', 'preview-compose.yml'}:
        raise RuntimeError('unexpected network staging contents')
    for path in (NEW_DIR, BACKUP_NETWORK, COMPOSE_BACKUP, COMPOSE_NEW, COMPOSE_ROLLBACK):
        if os.path.lexists(path): raise RuntimeError('previous or incomplete network update exists')
    previous = verified_sources(SOURCE, OLD_MANIFEST)
    current = verified_sources(INCOMING, NEW_MANIFEST)
    candidate = verified_sources(INCOMING_NETWORK, NETWORK_MANIFEST)
    installed_matches(BACKUP, previous)
    installed_matches(TARGET, current)
    verify_backend()
    old_compose = read_private(COMPOSE)
    new_compose = read_private(INCOMING_NETWORK / 'preview-compose.yml')
    if (hashlib.sha256(old_compose).hexdigest() != OLD_COMPOSE or
            hashlib.sha256(new_compose).hexdigest() != NETWORK_COMPOSE):
        raise RuntimeError('compose version is not approved')
    locks = module(TARGET / 'preview-deploy-lock.py', 'installer_network_lock')
    with locks.acquire_lock(nonblocking=True):
        installed_matches(BACKUP, previous); installed_matches(TARGET, current)
        assert_pristine()
        if read_private(COMPOSE) != old_compose:
            raise RuntimeError('compose changed before update')
        NEW_DIR.mkdir(mode=0o700)
        for name in FILES:
            for installed in EXECUTABLES.get(name, (name,)):
                write_exclusive(NEW_DIR / installed, candidate[name], 0o700 if name in EXECUTABLES else 0o600)
        sync_dir(NEW_DIR)
        installed_matches(NEW_DIR, candidate)
        write_exclusive(COMPOSE_BACKUP, old_compose)
        write_exclusive(COMPOSE_NEW, new_compose)
        sync_dir(COMPOSE.parent)
        renamed_old = renamed_new = replaced_compose = False
        try:
            os.rename(TARGET, BACKUP_NETWORK); renamed_old = True; sync_parent()
            os.rename(NEW_DIR, TARGET); renamed_new = True; sync_parent()
            os.replace(COMPOSE_NEW, COMPOSE); replaced_compose = True; sync_dir(COMPOSE.parent)
            installed_matches(TARGET, candidate)
            if read_private(COMPOSE) != new_compose: raise RuntimeError('new compose verification failed')
            verify_backend()
        except BaseException:
            if replaced_compose:
                write_exclusive(COMPOSE_ROLLBACK, old_compose)
                os.replace(COMPOSE_ROLLBACK, COMPOSE); sync_dir(COMPOSE.parent)
            if renamed_new: os.rename(TARGET, NEW_DIR)
            if renamed_old: os.rename(BACKUP_NETWORK, TARGET)
            sync_parent()
            raise
    print('Fixed preview helpers and Compose upgraded; both previous versions preserved; no deployment started.')


def main():
    if os.geteuid() != 0:
        raise RuntimeError('root required')
    if sys.argv[1:] == ['--upgrade']:
        return upgrade_network() if os.path.lexists(INCOMING_NETWORK) else upgrade()
    if len(sys.argv) != 1:
        raise RuntimeError('invalid arguments')
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
    except RuntimeError as exc:
        print(f'Fixed preview helper installation refused: {exc}', file=sys.stderr)
        raise SystemExit(1)
    except (OSError, subprocess.SubprocessError, UnicodeError):
        print('Fixed preview helper installation failed (filesystem, lock or Docker check).', file=sys.stderr)
        raise SystemExit(1)
