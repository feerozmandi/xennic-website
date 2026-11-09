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
import ipaddress
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
ACTIVATION_FILES = FILES + ('preview-deploy-receiver.py',)
EXECUTABLES = {'preview-deploy-receiver.py': ('deploy-receiver',),
               'preview-backup-sftp.py': ('sftp-transfer',), 'preview-backup-operation.py': ('backup-verify', 'preview-backup-operation.py'),
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
NETWORK_MANIFEST = 'fc2ae67bb9c24aebf936c05b0fe698b4465b3911e01d3884311fa3435836930b'
ACTIVATION_MANIFEST = 'c141100bd456b0f2ade106c4814ecf88dbc89b86257a2167e0a94e9637f68170'
INCOMING_ACTIVATION = SOURCE / 'incoming-activation'
BACKUP_ACTIVATION = PARENT / '.xennic-preview-before-activation'
ACTIVATION_ROUTE_HASH = 'a4d844df988812c4cd1922e7ca9a18c34281518bad27f5621be4d57bb8124029'
ROUTES = ROOT / 'config/routes.caddy'
ROUTES_BACKUP = ROOT / 'config/.routes-before-activation.caddy'
ROUTES_NEW = ROOT / 'config/.routes-activation-update.caddy'
ROUTES_ROLLBACK = ROOT / 'config/.routes-activation-rollback.caddy'
OLD_COMPOSE = '18a97bc2c21a6d623a54c81d07a49e44f6468cd225f0ce34a73f3760d3d0a373'
NETWORK_COMPOSE = '44639d7d7f3678c8cb772d02768a8c51320ae4f71e7ccd3829b3d9d5126f2b7c'
INCOMING_NETWORK = SOURCE / 'incoming-network'
BACKUP_NETWORK = PARENT / '.xennic-preview-before-network'
COMPOSE = ROOT / 'config/compose.yml'
COMPOSE_BACKUP = ROOT / 'config/.compose-before-network.yml'
COMPOSE_NEW = ROOT / 'config/.compose-network-update.yml'
COMPOSE_ROLLBACK = ROOT / 'config/.compose-network-rollback.yml'
GATEWAY_FILES = {
    'gateway.yml': ('preview-gateway-compose.yml', 'a6a84eb7d5c0be188d301ecf9ec38c2b5e9e6189dd66d3ac12d2f1966a0e363b'),
    'Caddyfile': ('preview-Caddyfile', 'c52da3f16ff668cd3ad068c6f059cb8cfbad4e8eecbeec9d6bf39fd3fe2bc0d7'),
    'routes.caddy': ('routes.caddy', 'd089cbb65414cd01600383df1bfbea10c0ab6c8e423ad4701324cb368e902033'),
    'oauth-gateway.caddy': ('oauth-gateway.caddy', '34220eb12245d54b8f4231527daad495a11bb559436148a0317e0b9837eaa195'),
    'upstream.caddy': ('upstream.caddy', '59bdf04300141b80d114a96621165c5cf3a7e4f673554de2204cf70c928e40a8'),
}


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


def verified_sources(directory, expected, files=FILES):
    private_dir(directory)
    data = {name: read_private(directory / name) for name in files}
    lines = ''.join(f'{hashlib.sha256(data[name]).hexdigest()}  scripts/{name}\n' for name in files)
    if hashlib.sha256(lines.encode('ascii')).hexdigest() != expected:
        raise RuntimeError('helper version is not approved')
    return data


def installed_matches(directory, data):
    private_dir(directory)
    expected = {installed for name in data for installed in EXECUTABLES.get(name, (name,))}
    if {p.name for p in directory.iterdir()} != expected:
        raise RuntimeError('unexpected installed helper')
    for name in data:
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
    if {p.name for p in INCOMING_NETWORK.iterdir()} != set(FILES) | {'install-preview-sftp-helper.py', 'preview-compose.yml'} | {source for source, _ in GATEWAY_FILES.values()}:
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
    gateway = {}
    for destination, (source, expected) in GATEWAY_FILES.items():
        data = read_private(INCOMING_NETWORK / source)
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError('gateway version is not approved')
        if os.path.lexists(ROOT / 'config' / destination):
            raise RuntimeError('existing gateway configuration requires review')
        gateway[destination] = data
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
        created_gateway = {}
        try:
            os.rename(TARGET, BACKUP_NETWORK); renamed_old = True; sync_parent()
            os.rename(NEW_DIR, TARGET); renamed_new = True; sync_parent()
            os.replace(COMPOSE_NEW, COMPOSE); replaced_compose = True; sync_dir(COMPOSE.parent)
            for name, data in gateway.items():
                path = ROOT / 'config' / name
                write_exclusive(path, data)
                created_gateway[path] = (os.lstat(path).st_ino, data)
            sync_dir(COMPOSE.parent)
            installed_matches(TARGET, candidate)
            if read_private(COMPOSE) != new_compose: raise RuntimeError('new compose verification failed')
            for path, (_, data) in created_gateway.items():
                if read_private(path) != data: raise RuntimeError('gateway verification failed')
            verify_backend()
        except BaseException:
            # Only remove files this attempt created and which are still exact.
            # Any changed or partially written file remains for manual review.
            for path, (inode, data) in created_gateway.items():
                try:
                    if os.lstat(path).st_ino == inode and read_private(path) == data:
                        path.unlink()
                except (OSError, RuntimeError):
                    pass
            sync_dir(COMPOSE.parent)
            if replaced_compose:
                write_exclusive(COMPOSE_ROLLBACK, old_compose)
                os.replace(COMPOSE_ROLLBACK, COMPOSE); sync_dir(COMPOSE.parent)
            if renamed_new: os.rename(TARGET, NEW_DIR)
            if renamed_old: os.rename(BACKUP_NETWORK, TARGET)
            sync_parent()
            raise
    print('Fixed preview helpers and Compose upgraded; both previous versions preserved; no deployment started.')


# Reviewed pre-first-deployment switch of the public edge from the private
# preview host to the approved apex. Helpers, files and secrets change together
# or not at all; both the previous helpers and originals are preserved.
APEX_MANIFEST = ACTIVATION_MANIFEST
INCOMING_APEX = SOURCE / 'incoming-apex'
BACKUP_APEX = PARENT / '.xennic-preview-before-apex'
APEX_STATE = ROOT / 'config/.apex-before'
EDGE_PREVIEW = {'Caddyfile': 'c52da3f16ff668cd3ad068c6f059cb8cfbad4e8eecbeec9d6bf39fd3fe2bc0d7',
                'gateway.yml': 'a6a84eb7d5c0be188d301ecf9ec38c2b5e9e6189dd66d3ac12d2f1966a0e363b'}
APEX_SOURCES = {'apex-Caddyfile': ('Caddyfile', '462370b17bf40923bb92d05e39a522acd34ccc08694f2f3b660e273e18d062f2'),
                'apex-gateway-compose.yml': ('gateway.yml', '1444baea48b7aedf2747b7e596872d8b7828bba7544be8dbe05e7720503833ed')}
APEX_ORIGIN = ('https://preview.xennic.ir', 'https://xennic.ir')


def _toml_value(value):
    if type(value) is bool:
        return 'true' if value else 'false'
    if type(value) is int:
        return str(value)
    if isinstance(value, str):
        if any(ord(ch) < 33 or ord(ch) > 126 for ch in value):
            raise RuntimeError('unsupported gateway value')
        return '"' + value + '"'
    if isinstance(value, list) and value and all(isinstance(item, str) for item in value):
        return '[' + ', '.join(_toml_value(item) for item in value) + ']'
    raise RuntimeError('unsupported gateway value')


def _canonical_toml(config):
    # Fixed key order is not required for TOML; deterministic output is.
    return ''.join(f'{key} = {_toml_value(config[key])}\n' for key in sorted(config)).encode('ascii')


def _exact_replace(raw, old, new, label):
    # Whole-line replacement only: a suffixed or embedded look-alike (for
    # example https://preview.xennic.ir.evil) must never be accepted.
    lines = raw.split(b'\n')
    if lines.count(old) != 1:
        raise RuntimeError(f'{label} is not in the expected state')
    return b'\n'.join(new if line == old else line for line in lines)


def upgrade_apex():
    """Switch the reviewed edge to the approved apex; no deployment started."""
    for path in (Path('/root'), SOURCE, Path('/usr'), Path('/usr/local'), PARENT, ROOT):
        check_dir(path)
    private_dir(SOURCE)
    private_dir(ROOT / 'config')
    private_dir(ROOT / 'secrets')
    private_dir(INCOMING_APEX)
    if {p.name for p in SOURCE.iterdir()} != set(ACTIVATION_FILES) | {
            'install-preview-sftp-helper.py', 'incoming-apex'}:
        raise RuntimeError('unexpected staging contents')
    if {p.name for p in INCOMING_APEX.iterdir()} != set(ACTIVATION_FILES) | {
            'install-preview-sftp-helper.py'} | set(APEX_SOURCES):
        raise RuntimeError('unexpected apex staging contents')
    for path in (APEX_STATE, BACKUP_APEX):
        if os.path.lexists(path):
            raise RuntimeError('previous apex switch exists; review it first')
    candidate = verified_sources(INCOMING_APEX, APEX_MANIFEST, ACTIVATION_FILES)
    for source, (_, expected) in APEX_SOURCES.items():
        if hashlib.sha256(read_private(INCOMING_APEX / source)).hexdigest() != expected:
            raise RuntimeError('edge file is not approved')
    # This switch is only for the reviewed pre-deployment installation.
    if os.path.lexists(ROOT / 'state/release-state.json') or any((ROOT / 'state').iterdir()) \
            or any((ROOT / 'work').iterdir()):
        raise RuntimeError('deployment state exists; apex switch requires a pristine install')
    for name, expected in EDGE_PREVIEW.items():
        if hashlib.sha256(read_private(ROOT / 'config' / name)).hexdigest() != expected:
            raise RuntimeError('installed edge differs from approved preview version')
    for name, expected in (('routes.caddy', ACTIVATION_ROUTE_HASH),):
        if hashlib.sha256(read_private(ROOT / 'config' / name)).hexdigest() != expected:
            raise RuntimeError('installed routes are not approved')
    if not os.path.isdir(TARGET):
        raise RuntimeError('helper directory is missing')
    locks = module(TARGET / 'preview-deploy-lock.py', 'installer_apex_lock')
    with locks.acquire_lock(nonblocking=True):
        # Previous helper install must be one of the reviewed versions before
        # its directory is replaced; aliases must still be identical copies.
        aliases = EXECUTABLES['preview-fixed-operations.py']
        contents = {read_private(TARGET / name) for name in aliases}
        if len(contents) != 1:
            raise RuntimeError('installed guard aliases differ')
        for name in candidate:
            if name == 'preview-fixed-operations.py':
                continue
            for installed in EXECUTABLES.get(name, (name,)):
                if read_private(TARGET / installed) != candidate[name]:
                    raise RuntimeError('installed helper differs from approved version')
        oauth_path, env_path = ROOT / 'secrets/oauth2-proxy.cfg', ROOT / 'secrets/preview.env'
        oauth_raw, env_raw = read_private(oauth_path), read_private(env_path)
        # The guard is installed only under its fixed executable aliases.
        fixed = module(TARGET / 'release-check', 'installer_apex_guard')
        try:
            existing = __import__('tomllib').loads(oauth_raw.decode('utf-8'))
            fixed.validate_gateway_oauth(oauth_raw, str(ipaddress.ip_address(
                existing['trusted_proxy_ips'][0].split('/')[0])))
        except (ValueError, KeyError, IndexError, UnicodeError) as exc:
            raise RuntimeError('installed gateway policy is not the approved preview version') from exc
        updated = dict(existing)
        updated['redirect_url'] = 'https://xennic.ir/oauth2/callback'
        updated['whitelist_domains'] = ['xennic.ir']
        oauth_new = _canonical_toml(updated)
        fixed.validate_gateway_oauth(oauth_new, str(ipaddress.ip_address(
            updated['trusted_proxy_ips'][0].split('/')[0])), authority='xennic.ir')
        env_new = _exact_replace(env_raw, f'PREVIEW_ORIGIN={APEX_ORIGIN[0]}'.encode('ascii'),
                                 f'PREVIEW_ORIGIN={APEX_ORIGIN[1]}'.encode('ascii'), 'staging origin')
        readiness = module(TARGET / 'preview-deploy-readiness.py', 'installer_apex_env')
        parsed_env = readiness._env(env_new)
        if parsed_env.get('PREVIEW_ORIGIN') != APEX_ORIGIN[1]:
            raise RuntimeError('staging origin was not switched exactly')
        APEX_STATE.mkdir(mode=0o700)
        for name, raw in (('Caddyfile', read_private(ROOT / 'config/Caddyfile')),
                          ('gateway.yml', read_private(ROOT / 'config/gateway.yml')),
                          ('oauth2-proxy.cfg', oauth_raw), ('preview.env', env_raw)):
            write_exclusive(APEX_STATE / name, raw)
        sync_dir(APEX_STATE)
        NEW_DIR.mkdir(mode=0o700)
        for name in ACTIVATION_FILES:
            for installed in EXECUTABLES.get(name, (name,)):
                write_exclusive(NEW_DIR / installed, candidate[name], 0o700 if name in EXECUTABLES else 0o600)
        sync_dir(NEW_DIR)
        installed_matches(NEW_DIR, candidate)
        staged = {}
        for source, (destination, _) in APEX_SOURCES.items():
            staged[destination] = read_private(INCOMING_APEX / source)
        staged['oauth2-proxy.cfg'], staged['preview.env'] = oauth_new, env_new
        temps = {}
        for name, raw in staged.items():
            target = ROOT / ('config' if name in ('Caddyfile', 'gateway.yml') else 'secrets') / name
            temp = target.with_name('.' + name + '.apex-update')
            if os.path.lexists(temp): raise RuntimeError('incomplete apex update exists')
            write_exclusive(temp, raw)
            temps[name] = (temp, target)
        renamed_old = renamed_new = False
        try:
            os.rename(TARGET, BACKUP_APEX); renamed_old = True; sync_parent()
            os.rename(NEW_DIR, TARGET); renamed_new = True; sync_parent()
            for temp, target in temps.values():
                os.replace(temp, target)
            sync_dir(ROOT / 'config'); sync_dir(ROOT / 'secrets')
            verify_backend()
            if hashlib.sha256(read_private(ROOT / 'config/Caddyfile')).hexdigest() != \
                    APEX_SOURCES['apex-Caddyfile'][1]:
                raise RuntimeError('installed edge verification failed')
        except BaseException:
            for temp, _ in temps.values():
                if os.path.lexists(temp): os.unlink(temp)
            for name, raw in (('Caddyfile', APEX_STATE / 'Caddyfile'), ('gateway.yml', APEX_STATE / 'gateway.yml')):
                restore = ROOT / 'config' / name
                if os.path.lexists(restore): os.unlink(restore)
                write_exclusive(restore, read_private(raw))
            for name, raw in (('oauth2-proxy.cfg', APEX_STATE / 'oauth2-proxy.cfg'),
                              ('preview.env', APEX_STATE / 'preview.env')):
                restore = ROOT / 'secrets' / name
                if os.path.lexists(restore): os.unlink(restore)
                write_exclusive(restore, read_private(raw))
            sync_dir(ROOT / 'config'); sync_dir(ROOT / 'secrets')
            if renamed_new: os.rename(TARGET, NEW_DIR)
            if renamed_old: os.rename(BACKUP_APEX, TARGET)
            sync_parent()
            raise
    print('Public edge switched to the approved apex; originals preserved; no deployment started.')


def rollback_apex():
    """Restore the reviewed preview edge and previous helpers from the switch."""
    for path in (Path('/root'), PARENT, ROOT):
        check_dir(path)
    if not os.path.lexists(APEX_STATE) or not os.path.lexists(BACKUP_APEX):
        raise RuntimeError('no completed apex switch to roll back')
    private_dir(APEX_STATE)
    locks = module(TARGET / 'preview-deploy-lock.py', 'installer_apex_rollback_lock')
    with locks.acquire_lock(nonblocking=True):
        if os.path.lexists(ROOT / 'state/release-state.json') or any((ROOT / 'work').iterdir()):
            raise RuntimeError('deployment state exists; review before rollback')
        for name in ('Caddyfile', 'gateway.yml'):
            original = read_private(APEX_STATE / name)
            current = ROOT / 'config' / name
            if os.path.lexists(current): os.unlink(current)
            write_exclusive(current, original)
        for name in ('oauth2-proxy.cfg', 'preview.env'):
            original = read_private(APEX_STATE / name)
            current = ROOT / 'secrets' / name
            if os.path.lexists(current): os.unlink(current)
            write_exclusive(current, original)
        sync_dir(ROOT / 'config'); sync_dir(ROOT / 'secrets')
        os.rename(TARGET, PARENT / '.xennic-preview-apex-rejected')
        os.rename(BACKUP_APEX, TARGET)
        sync_parent()
        verify_backend()
    print('Rolled back to the reviewed preview edge; rejected apex helpers preserved.')


def upgrade_activation():
    """Only the verified network install before first deployment; no configuration changes."""
    for path in (Path('/root'), SOURCE, Path('/usr'), Path('/usr/local'), PARENT):
        check_dir(path)
    for path in (SOURCE, INCOMING, INCOMING_NETWORK, INCOMING_ACTIVATION):
        private_dir(path)
    if {p.name for p in SOURCE.iterdir()} != set(FILES) | {'install-preview-sftp-helper.py', 'incoming', 'incoming-network', 'incoming-activation'}:
        raise RuntimeError('unexpected staging contents')
    if {p.name for p in INCOMING.iterdir()} != set(FILES) | {'install-preview-sftp-helper.py'}:
        raise RuntimeError('unexpected current staging contents')
    if {p.name for p in INCOMING_NETWORK.iterdir()} != set(FILES) | {'install-preview-sftp-helper.py', 'preview-compose.yml'} | {source for source, _ in GATEWAY_FILES.values()}:
        raise RuntimeError('unexpected network staging contents')
    if {p.name for p in INCOMING_ACTIVATION.iterdir()} != set(ACTIVATION_FILES) | {'install-preview-sftp-helper.py', 'routes.caddy'}:
        raise RuntimeError('unexpected activation staging contents')
    for path in (NEW_DIR, BACKUP_ACTIVATION, ROUTES_BACKUP, ROUTES_NEW, ROUTES_ROLLBACK):
        if os.path.lexists(path): raise RuntimeError('previous or incomplete activation update exists')
    previous = verified_sources(SOURCE, OLD_MANIFEST)
    intermediate = verified_sources(INCOMING, NEW_MANIFEST)
    current = verified_sources(INCOMING_NETWORK, NETWORK_MANIFEST)
    candidate = verified_sources(INCOMING_ACTIVATION, ACTIVATION_MANIFEST, ACTIVATION_FILES)
    new_routes = read_private(INCOMING_ACTIVATION / 'routes.caddy')
    if hashlib.sha256(new_routes).hexdigest() != ACTIVATION_ROUTE_HASH:
        raise RuntimeError('activation routes are not approved')
    installed_matches(BACKUP, previous)
    installed_matches(BACKUP_NETWORK, intermediate)
    installed_matches(TARGET, current)
    verify_backend()
    locks = module(TARGET / 'preview-deploy-lock.py', 'installer_activation_lock')
    with locks.acquire_lock(nonblocking=True):
        installed_matches(BACKUP, previous); installed_matches(BACKUP_NETWORK, intermediate)
        installed_matches(TARGET, current)
        assert_pristine()
        if hashlib.sha256(read_private(COMPOSE)).hexdigest() != NETWORK_COMPOSE:
            raise RuntimeError('installed compose differs from approved version')
        for destination, (_, expected) in GATEWAY_FILES.items():
            if hashlib.sha256(read_private(ROOT / 'config' / destination)).hexdigest() != expected:
                raise RuntimeError('installed gateway differs from approved version')
        old_routes = read_private(ROUTES)
        NEW_DIR.mkdir(mode=0o700)
        for name in ACTIVATION_FILES:
            for installed in EXECUTABLES.get(name, (name,)):
                write_exclusive(NEW_DIR / installed, candidate[name], 0o700 if name in EXECUTABLES else 0o600)
        sync_dir(NEW_DIR)
        installed_matches(NEW_DIR, candidate)
        write_exclusive(ROUTES_BACKUP, old_routes)
        write_exclusive(ROUTES_NEW, new_routes)
        sync_dir(ROUTES.parent)
        renamed_old = renamed_new = replaced_routes = False
        try:
            os.rename(TARGET, BACKUP_ACTIVATION); renamed_old = True; sync_parent()
            os.rename(NEW_DIR, TARGET); renamed_new = True; sync_parent()
            os.replace(ROUTES_NEW, ROUTES); replaced_routes = True; sync_dir(ROUTES.parent)
            installed_matches(TARGET, candidate)
            if read_private(ROUTES) != new_routes: raise RuntimeError('new routes verification failed')
            verify_backend()
        except BaseException:
            if replaced_routes:
                write_exclusive(ROUTES_ROLLBACK, old_routes)
                os.replace(ROUTES_ROLLBACK, ROUTES); sync_dir(ROUTES.parent)
            if renamed_new: os.rename(TARGET, NEW_DIR)
            if renamed_old: os.rename(BACKUP_ACTIVATION, TARGET)
            sync_parent()
            raise
    print('Fixed helpers and routes upgraded; previous versions preserved; no deployment or SSH setup started.')


def main():
    if os.geteuid() != 0:
        raise RuntimeError('root required')
    if sys.argv[1:] == ['--upgrade-apex']:
        return upgrade_apex()
    if sys.argv[1:] == ['--rollback-apex']:
        return rollback_apex()
    if sys.argv[1:] == ['--upgrade']:
        if os.path.lexists(INCOMING_ACTIVATION): return upgrade_activation()
        return upgrade_network() if os.path.lexists(INCOMING_NETWORK) else upgrade()
    if len(sys.argv) != 1:
        raise RuntimeError('invalid arguments')
    for path in (Path('/root'), SOURCE, Path('/usr'), Path('/usr/local'), PARENT):
        check_dir(path)
    if os.path.lexists(TARGET):
        raise RuntimeError('target already exists; no update performed')
    staged = []
    try:
        for name in ACTIVATION_FILES:
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
