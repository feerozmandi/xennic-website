#!/usr/bin/python3
"""Fixed stopped-app backup operation. Not an enabled deployment entry point.

Only the root-owned fixed Compose project is inspected or stopped. The caller
must hold the shared deployment lock and durably mark the release blocked first.
"""
import gzip
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
ROOT = Path('/srv/xennic-preview')
WORK = ROOT / 'work'
HELPERS = Path('/usr/local/libexec/xennic-preview')
COMPOSE = ['/usr/bin/docker', 'compose', '--project-name', 'xennic-preview',
           '--env-file', '/srv/xennic-preview/secrets/preview.env', '-f', '/srv/xennic-preview/config/compose.yml']
ENV = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'LANG': 'C'}
DOCKER = '/usr/bin/docker'


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

manifest = load('snapshot_manifest', 'preview-deploy-manifest.py')
states = load('snapshot_state', 'preview-deploy-state.py')
readiness = load('snapshot_readiness', 'preview-deploy-readiness.py')
age = load('snapshot_age', 'preview-age-backup.py')


class BackupFailed(RuntimeError):
    pass


def run(args, *, data=None, output=None, timeout=120):
    try:
        result = subprocess.run(args, input=data, stdin=subprocess.DEVNULL if data is None else None,
                                stdout=subprocess.PIPE if output is None else output,
                                stderr=subprocess.DEVNULL, env=ENV, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BackupFailed('backup command unavailable') from exc
    if result.returncode:
        raise BackupFailed('backup command failed')
    if output is None:
        if len(result.stdout) > 1024 * 1024:
            raise BackupFailed('backup command output too large')
        return result.stdout
    return b''


def container_id(service):
    raw = run(COMPOSE + ['ps', '--all', '-q', service]).decode('ascii').strip().splitlines()
    if len(raw) != 1 or not re.fullmatch('[0-9a-f]{12,64}', raw[0]):
        raise BackupFailed('ambiguous preview container')
    return raw[0]


def inspect(container):
    raw = json.loads(run([DOCKER, 'inspect', container]))
    if not isinstance(raw, list) or len(raw) != 1:
        raise BackupFailed('invalid container inspection')
    return raw[0]


def safe_directory(path):
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
        raise BackupFailed('unsafe snapshot directory')


def single_app_and_database():
    services = set(run(COMPOSE + ['config', '--services']).decode('ascii').split())
    if services != {'app', 'postgres'}:
        raise BackupFailed('unexpected preview services; writer isolation not established')
    app, database = container_id('app'), container_id('postgres')
    pg = inspect(database)
    if not pg.get('State', {}).get('Running') or pg.get('HostConfig', {}).get('NetworkMode') == 'host':
        raise BackupFailed('database is not safely isolated')
    ports = pg.get('NetworkSettings', {}).get('Ports') or {}
    if any(value for value in ports.values()):
        raise BackupFailed('database has published ports')
    mounts = [m for m in inspect(app).get('Mounts', []) if m.get('Destination') == '/app/media' and m.get('Type') == 'volume']
    if len(mounts) != 1 or not mounts[0].get('Name'):
        raise BackupFailed('media volume not identified')
    return app, database, mounts[0]['Name']


def assert_writers_stopped(app, database, media_volume):
    if inspect(app).get('State', {}).get('Running'):
        raise BackupFailed('application did not stop')
    db = inspect(database)
    database_id = db['Id']
    running = run([DOCKER, 'ps', '--no-trunc', '-q', '--filter', 'label=com.docker.compose.project=xennic-preview']).decode('ascii').split()
    if set(running) != {database_id}:
        raise BackupFailed('another preview service or one-off writer is running')
    networks = db.get('NetworkSettings', {}).get('Networks') or {}
    if not networks:
        raise BackupFailed('database network cannot be verified')
    for network in networks.values():
        net_id = network.get('NetworkID', '')
        if not re.fullmatch('[0-9a-f]{12,64}', net_id):
            raise BackupFailed('database network is ambiguous')
        inspected = json.loads(run([DOCKER, 'network', 'inspect', net_id]))
        if len(inspected) != 1 or set((inspected[0].get('Containers') or {}).keys()) != {database_id}:
            raise BackupFailed('another container has access to the database network')
    # Reject every running container mounting the media volume, even outside the project.
    other = run([DOCKER, 'ps', '-q', '--filter', f'volume={media_volume}']).decode('ascii').split()
    if other:
        raise BackupFailed('media volume is mounted by a running container')


def pg_settings(database):
    info = inspect(database)
    values = {}
    for item in info.get('Config', {}).get('Env', []):
        key, sep, val = item.partition('=')
        if sep and key in ('POSTGRES_USER', 'POSTGRES_DB'):
            if key in values or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,62}', val):
                raise BackupFailed('invalid database identity')
            values[key] = val
    if set(values) != {'POSTGRES_USER', 'POSTGRES_DB'}:
        raise BackupFailed('database identity missing')
    return values['POSTGRES_USER'], values['POSTGRES_DB']


def sql(database, user, db, query):
    return run([DOCKER, 'exec', '-i', database, 'psql', '-X', '-w', '-v', 'ON_ERROR_STOP=1',
                '-U', user, '-d', db, '-tAc', query]).decode('utf-8').strip()


def no_other_database_clients(database, user, db):
    count = sql(database, user, db, "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND backend_type='client backend'")
    if count != '0':
        raise BackupFailed('other database clients still connected')


def copy_media(app, path):
    try:
        proc = subprocess.Popen([DOCKER, 'cp', f'{app}:/app/media/.', '-'], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, env=ENV)
        with open(path, 'xb') as out, gzip.GzipFile(fileobj=out, mode='wb') as zipped:
            os.fchmod(out.fileno(), 0o600)
            shutil.copyfileobj(proc.stdout, zipped, 1024 * 1024)
        proc.stdout.close()
        if proc.wait(timeout=120):
            raise BackupFailed('media snapshot failed')
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BackupFailed('media snapshot failed') from exc


def verify_restored_database(image_id, dump, expected_migrations):
    if not re.fullmatch('sha256:[0-9a-f]{64}', image_id):
        raise BackupFailed('unexpected PostgreSQL image')
    name = 'xennic-preview-restore-' + secrets.token_hex(12)
    started = True  # cleanup even if Docker fails after creating the disposable container
    try:
        run([DOCKER, 'run', '--rm', '-d', '--name', name, '--network', 'none', '--memory', '384m',
             '--tmpfs', '/var/lib/postgresql/data:rw,noexec,nosuid,size=1024m',
             '-e', 'POSTGRES_USER=restore_ci', '-e', 'POSTGRES_DB=restore_ci',
             '-e', 'POSTGRES_PASSWORD=disposable-only', image_id], timeout=120)
        started = True
        for _ in range(40):
            try:
                run([DOCKER, 'exec', name, 'pg_isready', '-U', 'restore_ci', '-d', 'restore_ci'], timeout=5)
                break
            except BackupFailed:
                time.sleep(1)
        else:
            raise BackupFailed('restore database not ready')
        with open(dump, 'rb') as src:
            result = subprocess.run([DOCKER, 'exec', '-i', name, 'pg_restore', '-U', 'restore_ci', '-d', 'restore_ci',
                                     '--exit-on-error', '--no-owner', '--no-privileges'], stdin=src,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=ENV, timeout=300, check=False)
        if result.returncode:
            raise BackupFailed('independent database restore failed')
        actual = json.loads(sql(name, 'restore_ci', 'restore_ci', "SELECT COALESCE(json_agg(json_build_object('name',name,'batch',batch) ORDER BY name),'[]'::json)::text FROM website.payload_migrations"))
        if actual != expected_migrations:
            raise BackupFailed('restored migration ledger differs')
    finally:
        if started:
            # Cleanup failure is itself a failed backup: never proceed to migration
            # with a disposable restore container left in an uncertain state.
            run([DOCKER, 'rm', '-f', name], timeout=60)


def backup(raw):
    global ENV
    if os.geteuid() != 0:
        raise BackupFailed('root required')
    release = manifest.validate_manifest(raw)
    for path in (ROOT, WORK, ROOT / 'state'): safe_directory(path)
    state = states.Journal().read()
    if not state['blocked'] or state['pending'] != release or state['current'] is None:
        raise BackupFailed('a prior healthy release and blocked pending release are required')
    # Compose may interpolate the currently running pinned image. The value is
    # derived only from the root-owned journal, never from the caller's env.
    ENV = dict(ENV, PREVIEW_IMAGE=f"ghcr.io/{manifest.REPOSITORY}@{state['current']['digest']}")
    for relative in ('config/compose.yml', 'secrets/preview.env'):
        readiness._read(ROOT, relative, 0)
    config = readiness.backup_config(ROOT, 0)
    encrypted = WORK / 'backup.age'
    if os.path.lexists(encrypted):
        # Preserve (never delete) the last verified ciphertext for repeat releases.
        # A crash between link/unlink causes a fail-closed nlink check next time.
        try:
            record = json.loads(readiness._read(ROOT, f"state/backup-{state['current']['run_number']}.json", 0))
            st = os.lstat(encrypted)
            if (not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_nlink != 1 or st.st_mode & 0o077 or
                    record.get('release') != state['current']):
                raise BackupFailed('previous backup cannot be safely preserved')
            import hashlib
            h = hashlib.sha256()
            with open(encrypted, 'rb') as old:
                for chunk in iter(lambda: old.read(1024 * 1024), b''): h.update(chunk)
            if h.hexdigest() != record.get('sha256'):
                raise BackupFailed('previous backup does not match record')
            archive = WORK / 'retained'
            try: archive.mkdir(mode=0o700)
            except FileExistsError: pass
            safe_directory(archive)
            retained = archive / f"backup-{state['current']['run_number']}-{secrets.token_hex(12)}.age"
            os.link(encrypted, retained, follow_symlinks=False)
            os.unlink(encrypted)
        except (OSError, ValueError, readiness.NotReady) as exc:
            raise BackupFailed('previous backup cannot be safely preserved') from exc
    app, database, volume = single_app_and_database()
    run(COMPOSE + ['stop', '-t', '30', 'app'], timeout=60)
    # Never restart automatically on any failure: the durable journal remains blocked.
    assert_writers_stopped(app, database, volume)
    user, db = pg_settings(database)
    no_other_database_clients(database, user, db)
    migrations = json.loads(sql(database, user, db, "SELECT COALESCE(json_agg(json_build_object('name',name,'batch',batch) ORDER BY name),'[]'::json)::text FROM website.payload_migrations"))
    if not migrations:
        raise BackupFailed('migration ledger missing')
    with tempfile.TemporaryDirectory(prefix='.snapshot-', dir=WORK) as tmp:
        tmp = Path(tmp)
        dump, media = tmp / 'database.dump', tmp / 'media.tar.gz'
        with open(dump, 'xb') as output:
            os.fchmod(output.fileno(), 0o600)
            run([DOCKER, 'exec', '-i', database, 'pg_dump', '-U', user, '-d', db,
                 '--format=custom', '--no-owner', '--no-privileges'], output=output, timeout=300)
        copy_media(app, media)
        no_other_database_clients(database, user, db)
        assert_writers_stopped(app, database, volume)
        expected = age.create_bundle(dump, media, encrypted, config['age_recipient'], state['current']['commit'], migrations)
        helper = HELPERS / 'sftp-transfer'
        h = os.lstat(helper)
        if not stat.S_ISREG(h.st_mode) or h.st_uid != 0 or h.st_nlink != 1 or h.st_mode & 0o077 or not h.st_mode & stat.S_IXUSR:
            raise BackupFailed('SFTP helper is unsafe')
        run([str(helper)], data=raw + b'\n', timeout=360)
        restored = tmp / 'restored'
        restored.mkdir(mode=0o700)
        actual = age.restore_bundle(encrypted, ROOT / 'secrets/backup-identity', restored)
        if actual != expected:
            raise BackupFailed('restored backup metadata differs')
        verify_restored_database(inspect(database)['Image'], restored / 'db.restored', migrations)
    # The app remains stopped for migration / activation by the controller.


def main():
    if len(sys.argv) != 1:
        print('Invalid fixed backup operation', file=sys.stderr)
        return 1
    os.umask(0o077)
    try:
        backup(sys.stdin.buffer.read(manifest.MAX_MANIFEST_BYTES + 1).strip())
    except BackupFailed as exc:
        print(f'Preview backup failed: {exc}; release blocked; inspect app status', file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, KeyError) as exc:
        print(f'Preview backup failed ({type(exc).__name__}); release blocked; inspect app status', file=sys.stderr)
        return 1
    print('Stopped-app encrypted backup, SFTP readback and isolated DB restore passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
