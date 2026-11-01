#!/usr/bin/python3
"""Fixed privileged phases for the preview transaction; no arbitrary arguments.

Install identical copies under the fixed phase names. Entry is root-only and
requires a validated manifest on stdin. SSH/automatic deployment remains disabled.
"""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
ROOT = Path('/srv/xennic-preview')
DOCKER = '/usr/bin/docker'
COMPOSE = [DOCKER, 'compose', '--project-name', 'xennic-preview', '--env-file',
           '/srv/xennic-preview/secrets/preview.env', '-f', '/srv/xennic-preview/config/compose.yml']
SAFE = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'LANG': 'C'}
PHASES = frozenset({'release-check', 'current-check', 'migrate', 'activate', 'health', 'rollback'})


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

manifest = load('fixed_manifest', 'preview-deploy-manifest.py')
states = load('fixed_state', 'preview-deploy-state.py')
ready = load('fixed_readiness', 'preview-deploy-readiness.py')
verifier = load('fixed_verifier', 'preview-release-verifier.py')
healthcheck = load('fixed_health', 'preview-internal-health.py')
snapshot = load('fixed_snapshot_checks', 'preview-backup-operation.py')


class Rejected(RuntimeError):
    pass


def run(args, *, image=None, data=None, timeout=180, output=False):
    env = dict(SAFE)
    if image is not None: env['PREVIEW_IMAGE'] = image
    try:
        result = subprocess.run(args, input=data, stdin=subprocess.DEVNULL if data is None else None,
                                stdout=subprocess.PIPE if output else subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, env=env, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Rejected('fixed operation unavailable') from exc
    if result.returncode:
        raise Rejected('fixed operation failed')
    if output:
        if len(result.stdout) > 16 * 1024 * 1024: raise Rejected('operation output too large')
        return result.stdout
    return b''


def reference(release):
    return f"ghcr.io/{manifest.REPOSITORY}@{release['digest']}"


def state():
    return states.Journal().read()


def approval(previous, candidate):
    try:
        obj = json.loads(ready._read(ROOT, 'config/compatible-transitions.json', 0), object_pairs_hook=ready._object_pairs)
    except (ValueError, UnicodeError, ready.NotReady) as exc:
        raise Rejected('reviewed migration transition missing') from exc
    if not isinstance(obj, dict) or set(obj) != {'version', 'transitions'} or obj['version'] != 1 or not isinstance(obj['transitions'], list):
        raise Rejected('reviewed migration transition invalid')
    matches = [item for item in obj['transitions'] if isinstance(item, dict) and
               item.get('from_commit') == previous['commit'] and item.get('to_commit') == candidate['commit']]
    if len(matches) != 1:
        raise Rejected('migration transition not reviewed')
    item = matches[0]
    if (set(item) != {'from_commit', 'to_commit', 'migration_sha256', 'previous_migrations', 'rollback_safe'} or
            item['rollback_safe'] is not True or not isinstance(item['migration_sha256'], str) or
            not re.fullmatch('[0-9a-f]{64}', item['migration_sha256']) or
            not isinstance(item['previous_migrations'], list) or not item['previous_migrations'] or
            any(not isinstance(name, str) or not re.fullmatch('[A-Za-z0-9_-]{1,200}', name) for name in item['previous_migrations']) or
            len(set(item['previous_migrations'])) != len(item['previous_migrations'])):
        raise Rejected('migration transition not approved for rollback')
    return item


def config_for(release):
    for path in ('config/compose.yml', 'secrets/preview.env'):
        ready._read(ROOT, path, 0)
    image = reference(release)
    try:
        obj = json.loads(run(COMPOSE + ['config', '--format', 'json'], image=image, output=True))
        services = obj['services']
        if set(services) != {'app', 'postgres'} or services['app']['image'] != image:
            raise Rejected('Compose image or services mismatch')
    except (ValueError, KeyError, TypeError) as exc:
        raise Rejected('invalid Compose configuration') from exc
    return image


def image_id(release):
    image = reference(release)
    try:
        items = json.loads(run([DOCKER, 'image', 'inspect', image], output=True))
        if (not isinstance(items, list) or len(items) != 1 or items[0].get('Os') != 'linux' or
            items[0].get('Architecture') != 'amd64' or image not in (items[0].get('RepoDigests') or []) or
            not re.fullmatch(r'sha256:[0-9a-f]{64}', items[0].get('Id', ''))):
            raise Rejected('local image identity mismatch')
        return items[0]['Id']
    except (ValueError, TypeError, KeyError) as exc:
        raise Rejected('invalid local image identity') from exc


def running_app_id(release):
    image = config_for(release)
    ids = run(COMPOSE + ['ps', '-q', 'app'], image=image, output=True).decode('ascii').split()
    if len(ids) != 1 or not re.fullmatch('[0-9a-f]{12,64}', ids[0]):
        raise Rejected('running app unavailable')
    items = json.loads(run([DOCKER, 'inspect', ids[0]], output=True))
    if len(items) != 1 or not items[0].get('State', {}).get('Running') or items[0].get('Image') != image_id(release):
        raise Rejected('running image does not match previous release')
    return ids[0]


def assert_current_host(previous):
    app = running_app_id(previous)
    image = reference(previous)
    dbids = run(COMPOSE + ['ps', '-q', 'postgres'], image=image, output=True).decode('ascii').split()
    if len(dbids) != 1 or not re.fullmatch('[0-9a-f]{12,64}', dbids[0]):
        raise Rejected('database unavailable')
    appinfo = json.loads(run([DOCKER, 'inspect', app], output=True))[0]
    dbinfo = json.loads(run([DOCKER, 'inspect', dbids[0]], output=True))[0]
    if dbinfo.get('HostConfig', {}).get('NetworkMode') == 'host' or any((dbinfo.get('NetworkSettings', {}).get('Ports') or {}).values()):
        raise Rejected('database is exposed')
    app_id, db_id = appinfo['Id'], dbinfo['Id']
    allowed_addresses = set()
    dbnetworks = dbinfo.get('NetworkSettings', {}).get('Networks') or {}
    appnetworks = appinfo.get('NetworkSettings', {}).get('Networks') or {}
    if not dbnetworks: raise Rejected('database network unavailable')
    for name, net in dbnetworks.items():
        net_id = net.get('NetworkID', '')
        if not re.fullmatch('[0-9a-f]{12,64}', net_id): raise Rejected('database network invalid')
        entries = json.loads(run([DOCKER, 'network', 'inspect', net_id], output=True))
        attached = set((entries[0].get('Containers') or {}).keys())
        if not attached <= {app_id, db_id} or db_id not in attached:
            raise Rejected('unknown database network writer')
        if name in appnetworks and app_id in attached:
            addr = appnetworks[name].get('IPAddress', '')
            if addr: allowed_addresses.add(addr)
    # Existing outside-Docker DB sessions are not silently treated as app writers.
    env = {k: v for k, _, v in (x.partition('=') for x in dbinfo.get('Config', {}).get('Env', [])) if k in ('POSTGRES_USER', 'POSTGRES_DB')}
    if set(env) != {'POSTGRES_USER', 'POSTGRES_DB'} or any(not re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,62}', v) for v in env.values()):
        raise Rejected('database identity invalid')
    query = "SELECT COALESCE(host(client_addr),'local') FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND backend_type='client backend'"
    clients = run([DOCKER, 'exec', '-i', dbids[0], 'psql', '-X', '-w', '-v', 'ON_ERROR_STOP=1',
                   '-U', env['POSTGRES_USER'], '-d', env['POSTGRES_DB'], '-tAc', query], output=True).decode('ascii').splitlines()
    if any(client.strip() not in allowed_addresses for client in clients if client.strip()):
        raise Rejected('unknown database client')


def migration_tree_hash(release):
    image = reference(release)
    created = run([DOCKER, 'create', '--network', 'none', '--entrypoint', '/bin/true', image], output=True).decode('ascii').strip()
    if not re.fullmatch('[0-9a-f]{12,64}', created): raise Rejected('migration inspection container invalid')
    try:
        data = run([DOCKER, 'cp', f'{created}:/app/migrations/.', '-'], output=True)
    finally:
        run([DOCKER, 'rm', '-f', created])
    result = []
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
            seen = set()
            for member in archive:
                path = PurePosixPath(member.name)
                name = str(path)
                if member.name.startswith('/') or '..' in path.parts or name in seen:
                    raise Rejected('unsafe migration archive')
                seen.add(name)
                if member.isdir(): continue
                if not member.isfile() or member.size > 8 * 1024 * 1024 or len(result) >= 1000:
                    raise Rejected('invalid migration file')
                with archive.extractfile(member) as source:
                    result.append((name, source.read()))
    except (tarfile.TarError, OSError, AttributeError) as exc:
        raise Rejected('migration inspection failed') from exc
    if not result: raise Rejected('migration files missing')
    digest = hashlib.sha256()
    for name, contents in sorted(result):
        digest.update(name.encode('utf-8') + b'\0' + str(len(contents)).encode('ascii') + b'\0' + contents)
    return digest.hexdigest()


def pending(release):
    data = state()
    if not data['blocked'] or data['pending'] != release or data['current'] is None:
        raise Rejected('release is not pending')
    return data


def verify_backup(release):
    path = f"state/backup-{release['run_number']}.json"
    try:
        backup = json.loads(ready._read(ROOT, path, 0), object_pairs_hook=ready._object_pairs)
        if not isinstance(backup, dict) or set(backup) != {'version', 'release', 'remote_path', 'sha256'} or backup['version'] != 1 or backup['release'] != release:
            raise Rejected('verified backup record missing')
        policy = ready.backup_config(ROOT, 0)
        remote = backup['remote_path']
        if policy['transport'] == 'manual-local':
            if remote != 'manual-offsite-pending': raise Rejected('local-only backup record mismatch')
        elif not isinstance(remote, str) or not re.fullmatch(
                re.escape(policy['remote_directory'].rstrip('/')) + r'/xennic-' + str(release['run_number']) + r'-[0-9a-f]{32}\.age', remote):
            raise Rejected('offsite backup record mismatch')
        fd = os.open(ROOT / 'work/backup.age', os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1 or info.st_mode & 0o077:
                raise Rejected('unsafe backup file')
            h = hashlib.sha256()
            with os.fdopen(fd, 'rb', closefd=False) as f:
                for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
        finally: os.close(fd)
        if h.hexdigest() != backup['sha256']: raise Rejected('backup changed')
    except (OSError, ValueError, ready.NotReady) as exc:
        raise Rejected('verified backup record missing') from exc


def check_health(release):
    config_for(release)
    running_app_id(release)
    healthcheck.ENV = dict(SAFE, PREVIEW_IMAGE=reference(release))
    healthcheck.check_once()


def execute(phase, release, token):
    if phase == 'release-check':
        previous = state()['current']
        if previous is None: raise Rejected('initial installation needs separate review')
        verifier.verify(release, token)
        assert_current_host(previous)
        check_health(previous)
        approval(previous, release)
        return {'initial': False, 'rollback_safe': True, 'verified_commit': release['commit'],
                'verified_digest': release['digest'], 'verified_run_number': release['run_number']}
    if phase == 'current-check':
        verifier.assert_current(release, token)
        return None
    if phase == 'migrate':
        current = pending(release)['current']
        policy = approval(current, release)
        verify_backup(release)
        image = config_for(release)
        image_id(release)
        snapshot.ENV = dict(SAFE, PREVIEW_IMAGE=image)
        app, database, volume = snapshot.single_app_and_database()
        snapshot.assert_writers_stopped(app, database, volume)
        user, database_name = snapshot.pg_settings(database)
        snapshot.no_other_database_clients(database, user, database_name)
        ledger = json.loads(snapshot.sql(database, user, database_name, "SELECT COALESCE(json_agg(json_build_object('name',name,'batch',batch) ORDER BY name),'[]'::json)::text FROM website.payload_migrations"))
        if (not isinstance(ledger, list) or any(not isinstance(row, dict) or set(row) != {'name', 'batch'} or
                not isinstance(row['name'], str) or type(row['batch']) is not int or row['batch'] < 0 for row in ledger) or
                sorted(row['name'] for row in ledger) != sorted(policy['previous_migrations'])):
            raise Rejected('database migration ledger was not reviewed')
        if migration_tree_hash(release) != policy['migration_sha256']:
            raise Rejected('migration files differ from reviewed transition')
        run(COMPOSE + ['run', '--rm', '--no-deps', '-T', 'app', 'npm', 'run', 'preview:migrate'], image=image, timeout=600)
        return None
    if phase == 'activate':
        pending(release)
        verify_backup(release)
        image = config_for(release)
        image_id(release)
        run(COMPOSE + ['up', '-d', '--no-deps', '--no-build', '--force-recreate', '--wait', 'app'], image=image, timeout=180)
        running_app_id(release)
        marker = ROOT / 'state' / f"activation-{release['run_number']}.json"
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            with os.fdopen(fd, 'wb', closefd=False) as stream:
                stream.write(json.dumps(release, separators=(',', ':'), sort_keys=True).encode() + b'\n')
                stream.flush(); os.fsync(stream.fileno())
        finally: os.close(fd)
        directory = os.open(ROOT / 'state', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try: os.fsync(directory)
        finally: os.close(directory)
        return None
    if phase == 'health':
        data = state()
        if not data['blocked'] or release not in (data['current'], data['pending']):
            raise Rejected('health release is not current or pending')
        check_health(release)
        return None
    if phase == 'rollback':
        data = state()
        if not data['blocked'] or data['current'] != release or data['pending'] is None:
            raise Rejected('rollback release is not previous')
        approval(release, data['pending'])
        image = config_for(release)
        image_id(release)
        run(COMPOSE + ['up', '-d', '--no-deps', '--no-build', '--force-recreate', '--wait', 'app'], image=image, timeout=180)
        return None
    raise Rejected('unknown operation')


def main():
    phase = Path(sys.argv[0]).name
    if os.geteuid() != 0 or len(sys.argv) != 1 or phase not in PHASES:
        print('Invalid fixed operation', file=sys.stderr); return 1
    try:
        raw = sys.stdin.buffer.readline(manifest.MAX_MANIFEST_BYTES + 2)
        if not raw.endswith(b'\n'): raise Rejected('invalid input')
        release = manifest.validate_manifest(raw[:-1])
        token = None
        if phase in ('release-check', 'current-check'):
            token = sys.stdin.buffer.readline(4098)
            if not token.endswith(b'\n'): raise Rejected('invalid token')
            token = token[:-1]
            if not re.fullmatch(rb'[!-~]{1,4096}', token): raise Rejected('invalid token')
        if sys.stdin.buffer.read(1): raise Rejected('extra input')
        result = execute(phase, release, token)
        if result is not None: print(json.dumps(result, separators=(',', ':')))
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, UnicodeError):
        print('Fixed preview operation failed; inspect locally with redaction', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
