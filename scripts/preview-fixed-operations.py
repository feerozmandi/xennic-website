#!/usr/bin/python3
"""Fixed privileged phases for the preview transaction; no arbitrary arguments.

Install identical copies under the fixed phase names. Entry is root-only and
requires a validated manifest on stdin. SSH/automatic deployment remains disabled.
"""
import base64
import binascii
import hashlib
import http.client
import importlib.util
import ipaddress
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tarfile
import time
import tomllib
from urllib.parse import unquote, urlsplit

sys.dont_write_bytecode = True
ROOT = Path('/srv/xennic-preview')
DOCKER = '/usr/bin/docker'
COMPOSE = [DOCKER, 'compose', '--project-name', 'xennic-preview', '--env-file',
           '/srv/xennic-preview/secrets/preview.env', '-f', '/srv/xennic-preview/config/compose.yml']
SAFE = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'LANG': 'C'}
GATEWAY_COMPOSE = [DOCKER, 'compose', '--project-name', 'xennic-preview-gateway', '--env-file',
                   '/srv/xennic-preview/secrets/preview.env', '-f', '/srv/xennic-preview/config/gateway.yml']
GATEWAY_IMAGES = {
    'caddy': 'caddy:2.11.7@sha256:36c24ad91a7ff7bc4c87fe22bfa8df3c4b18da0773d73fc12ee2c52b98c0bb7e',
    'gate': 'quay.io/oauth2-proxy/oauth2-proxy:v7.15.5@sha256:8498b0d0ef0a7b29686414000a08aee467f02d0299c9ed1e006a8f33fc017916',
}
GATEWAY_FILES = {
    'config/gateway.yml': 'a6a84eb7d5c0be188d301ecf9ec38c2b5e9e6189dd66d3ac12d2f1966a0e363b',
    'config/Caddyfile': 'c52da3f16ff668cd3ad068c6f059cb8cfbad4e8eecbeec9d6bf39fd3fe2bc0d7',
    'config/routes.caddy': 'd089cbb65414cd01600383df1bfbea10c0ab6c8e423ad4701324cb368e902033',
    'config/oauth-gateway.caddy': '34220eb12245d54b8f4231527daad495a11bb559436148a0317e0b9837eaa195',
    'config/upstream.caddy': '59bdf04300141b80d114a96621165c5cf3a7e4f673554de2204cf70c928e40a8',
}
PHASES = frozenset({'release-check', 'current-check', 'migrate', 'activate', 'health', 'rollback'})

# Probe from the trusted host helper, not from a candidate app image. The
# address is taken only from the independently verified Caddy container.
INGRESS_CASES = (('GET', '/', 302), ('GET', '/admin', 302),
                 ('GET', '/api/pages', 401), ('POST', '/api/graphql', 401),
                 ('GET', '/media/missing.png', 302), ('GET', '/health', 302))


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


def validate_gateway_oauth(raw, caddy_ip):
    """Validate one effective OAuth config; does not itself establish identity.

    This deliberately rejects extra options, including alternate auth routes and
    provider endpoints. The caller must independently verify the exact running
    Caddy peer and supply its inspected IP, not an address from the config.
    This validator is not yet wired into activation; the gateway remains blocked.
    """
    try:
        config = tomllib.loads(raw.decode('utf-8'))
        address = ipaddress.ip_address(caddy_ip)
    except (ValueError, TypeError, UnicodeError, AttributeError) as exc:
        raise Rejected('invalid gateway configuration') from exc
    private_ranges = (ipaddress.ip_network('10.0.0.0/8'), ipaddress.ip_network('172.16.0.0/12'),
                      ipaddress.ip_network('192.168.0.0/16'))
    if address.version != 4 or not any(address in network for network in private_ranges):
        raise Rejected('invalid Caddy peer address')
    fixed = {
        'provider': 'github', 'email_domains': ['*'], 'scope': 'user:email',
        'reverse_proxy': True, 'trusted_proxy_ips': [str(address) + '/32'],
        'http_address': '0.0.0.0:4180',
        'redirect_url': 'https://preview.xennic.ir/oauth2/callback',
        'upstreams': ['static://202'], 'whitelist_domains': ['preview.xennic.ir'],
        'cookie_name': '__Host-preview_gate', 'cookie_secure': True,
        'cookie_httponly': True, 'cookie_samesite': 'lax',
        'cookie_expire': '8h', 'cookie_refresh': '0',
        'skip_jwt_bearer_tokens': False, 'skip_auth_preflight': False,
        'pass_basic_auth': False, 'pass_authorization_header': False,
        'set_authorization_header': False, 'pass_access_token': False,
        'set_xauthrequest': False, 'request_logging': False, 'auth_logging': False,
    }
    keys = set(fixed) | {'github_users', 'client_id', 'client_secret', 'cookie_secret'}
    if set(config) != keys:
        raise Rejected('gateway options are missing or unexpected')
    for key, expected in fixed.items():
        if type(config[key]) is not type(expected) or config[key] != expected:
            raise Rejected('gateway option differs from reviewed policy')
    users = config['github_users']
    if (not isinstance(users, list) or not users or
            any(not isinstance(user, str) or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?', user)
                or '--' in user for user in users) or
            len({user.lower() for user in users}) != len(users)):
        raise Rejected('gateway user allowlist is invalid')
    for key in ('client_id', 'client_secret'):
        value = config[key]
        if not isinstance(value, str) or not 1 <= len(value) <= 1024 or any(ord(ch) < 33 or ord(ch) > 126 for ch in value):
            raise Rejected('gateway credentials are invalid')
    try:
        secret = config['cookie_secret']
        if not isinstance(secret, str) or len(base64.b64decode(secret, altchars=b'-_', validate=True)) != 32:
            raise ValueError('invalid cookie key')
    except (ValueError, binascii.Error, UnicodeError) as exc:
        raise Rejected('gateway cookie key is invalid') from exc


def config_for(release):
    for path in ('config/compose.yml', 'secrets/preview.env'):
        ready._read(ROOT, path, 0)
    image = reference(release)
    try:
        obj = json.loads(run(COMPOSE + ['config', '--format', 'json'], image=image, output=True))
        services = obj['services']
        if set(services) != {'app', 'postgres'} or services['app']['image'] != image:
            raise Rejected('Compose image or services mismatch')
        validate_topology(obj)
    except (ValueError, KeyError, TypeError) as exc:
        raise Rejected('invalid Compose configuration') from exc
    return image


def validate_topology(obj):
    """Require the fixed isolated database and gateway networks on every release."""
    services, volumes, networks = obj['services'], obj['volumes'], obj['networks']
    if (set(services) != {'app', 'postgres'} or set(volumes) != {'preview_db', 'preview_media'} or
            set(networks) != {'default', 'gateway'} or
            any(volumes[k].get('external') or volumes[k].get('driver_opts') or
                volumes[k].get('driver') not in (None, 'local') or
                volumes[k].get('name') != 'xennic-preview_' + k for k in volumes) or
            any(networks[k].get('external') or networks[k].get('driver_opts') or
                networks[k].get('driver') not in (None, 'bridge') or
                networks[k].get('internal') is not True or
                networks[k].get('name') != 'xennic-preview_' + k for k in networks)):
        raise Rejected('preview volumes or networks are not isolated')
    for service, volume, destination, nets in (
            ('postgres', 'preview_db', '/var/lib/postgresql/data', {'default'}),
            ('app', 'preview_media', '/app/media', {'default', 'gateway'})):
        item = services[service]
        mounts = item.get('volumes') or []
        if (len(mounts) != 1 or mounts[0].get('type') != 'volume' or
                mounts[0].get('source') != volume or mounts[0].get('target') != destination or
                set(item.get('networks') or {}) != nets or item.get('network_mode') or
                item.get('ports') or item.get('privileged') or item.get('devices') or
                item.get('pid') or item.get('ipc')):
            raise Rejected('preview service or published ports are unsafe')
    app = services['app']
    if (app.get('build') or app.get('pull_policy') != 'never' or
            services['postgres'].get('image') != 'postgres:16.14-bookworm'):
        raise Rejected('preview application or database image is unsafe')


def assert_initial_pristine(release, journal_exists=False):
    """Refuse all pre-existing preview data/resources, including unlabelled names."""
    image = config_for(release)
    try:
        obj = json.loads(run(COMPOSE + ['config', '--format', 'json'], image=image, output=True))
        validate_topology(obj)
        services = obj['services']
        app = services['app']
        env = ready._env(ready._read(ROOT, 'secrets/preview.env', 0))
        url = urlsplit(env['PREVIEW_DATABASE_URL'])
        if (url.scheme not in ('postgres', 'postgresql') or url.hostname != 'postgres' or
                url.port not in (None, 5432) or url.query or url.fragment or
                unquote(url.username or '') != env['PREVIEW_POSTGRES_USER'] or
                unquote(url.password or '') != env['PREVIEW_POSTGRES_PASSWORD'] or
                unquote(url.path.removeprefix('/')) != env['PREVIEW_POSTGRES_DB'] or
                app.get('environment', {}).get('DATABASE_URL') != env['PREVIEW_DATABASE_URL'] or
                services['postgres'].get('environment', {}).get('POSTGRES_DB') != env['PREVIEW_POSTGRES_DB'] or
                services['postgres'].get('environment', {}).get('POSTGRES_USER') != env['PREVIEW_POSTGRES_USER'] or
                services['postgres'].get('environment', {}).get('POSTGRES_PASSWORD') != env['PREVIEW_POSTGRES_PASSWORD']):
            raise Rejected('initial database is not the isolated Compose database')
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise Rejected('initial Compose configuration invalid') from exc
    for directory in (ROOT, ROOT / 'state', ROOT / 'work'):
        snapshot.safe_directory(directory)
    if {p.name for p in ROOT.iterdir()} != {'config', 'secrets', 'state', 'work'}:
        raise Rejected('initial preview root has unexpected resources')
    expected = {'release-state.json'} if journal_exists else set()
    if {p.name for p in (ROOT / 'state').iterdir()} != expected or any((ROOT / 'work').iterdir()):
        raise Rejected('initial state or work directory is not empty')
    if run([DOCKER, 'ps', '-aq', '--filter', 'label=com.docker.compose.project=xennic-preview'], output=True).strip():
        raise Rejected('initial project has existing containers')
    for command in ([DOCKER, 'ps', '-a', '--format', '{{.Names}}'],
                    [DOCKER, 'volume', 'ls', '--format', '{{.Name}}'],
                    [DOCKER, 'network', 'ls', '--format', '{{.Name}}']):
        names = run(command, output=True).decode('utf-8').splitlines()
        if any(name.startswith(('xennic-preview_', 'xennic-preview-')) for name in names):
            raise Rejected('initial project has existing named resources')
    for kind in ('volume', 'network'):
        if run([DOCKER, kind, 'ls', '-q', '--filter', 'label=com.docker.compose.project=xennic-preview'], output=True).strip():
            raise Rejected('initial project has existing labelled resources')
    return image


def assert_initial_database(image):
    snapshot.ENV = dict(SAFE, PREVIEW_IMAGE=image)
    database = snapshot.container_id('postgres')
    info = snapshot.inspect(database)
    ports = info.get('NetworkSettings', {}).get('Ports') or {}
    mounts = [m for m in info.get('Mounts', []) if m.get('Destination') == '/var/lib/postgresql/data']
    if (not info.get('State', {}).get('Running') or info.get('HostConfig', {}).get('NetworkMode') == 'host' or
            any(ports.values()) or len(mounts) != 1 or mounts[0].get('Type') != 'volume' or
            mounts[0].get('Name') != 'xennic-preview_preview_db'):
        raise Rejected('initial database is not isolated')
    networks = info.get('NetworkSettings', {}).get('Networks') or {}
    if set(networks) != {'xennic-preview_default'}:
        raise Rejected('initial database network is unexpected')
    network_id = networks['xennic-preview_default'].get('NetworkID', '')
    if not re.fullmatch('[0-9a-f]{12,64}', network_id): raise Rejected('initial network is invalid')
    entries = json.loads(run([DOCKER, 'network', 'inspect', network_id], output=True))
    if len(entries) != 1 or set((entries[0].get('Containers') or {}).keys()) != {info['Id']}:
        raise Rejected('unknown initial database network writer')
    user, database_name = snapshot.pg_settings(database)
    snapshot.no_other_database_clients(database, user, database_name)


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
    app = items[0]
    host = app.get('HostConfig', {})
    net = app.get('NetworkSettings', {})
    if (host.get('NetworkMode') == 'host' or host.get('PublishAllPorts') or host.get('PortBindings') or
            any((net.get('Ports') or {}).values()) or
            set(net.get('Networks') or {}) != {'xennic-preview_default', 'xennic-preview_gateway'}):
        raise Rejected('running app network or published ports are unsafe')
    require_verified_gateway(app['Id'])
    return app['Id']


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
    if not data['blocked'] or data['pending'] != release or 'failure' in data:
        raise Rejected('release is not pending or requires failure review')
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


def check_ingress_protection(caddy_ip):
    """Probe fixed routes directly from the trusted host, not the candidate app.

    A denial probe is not proof of OAuth or gateway identity: the caller must
    verify the gateway and obtain this address from its inspected container.
    """
    try:
        addr = ipaddress.ip_address(caddy_ip)
        if addr.version != 4 or not addr.is_private or addr.is_loopback:
            raise ValueError('invalid peer')
    except (ValueError, TypeError) as exc:
        raise Rejected('invalid Caddy probe address') from exc
    headers = {'Host': 'preview.xennic.ir', 'Authorization': 'Bearer invalid-probe',
               'X-Forwarded-User': 'untrusted-probe', 'X-Auth-Request-User': 'untrusted-probe'}
    for attempt in range(12):
        try:
            for method, path, expected in INGRESS_CASES:
                conn = http.client.HTTPConnection(str(addr), 8080, timeout=4)
                try:
                    conn.request(method, path, headers=headers)
                    response = conn.getresponse()
                    if (response.status != expected or
                            (expected == 302 and response.getheader('Location') != '/oauth2/sign_in')):
                        raise Rejected('entry protection check failed')
                finally:
                    conn.close()
            return
        except (OSError, http.client.HTTPException, Rejected) as exc:
            if attempt == 11: raise Rejected('entry protection check failed') from exc
            time.sleep(1)


def gateway_configuration():
    """Accept only the reviewed fixed files and fixed private OAuth policy."""
    try:
        for path, expected in GATEWAY_FILES.items():
            if hashlib.sha256(ready._read(ROOT, path, 0)).hexdigest() != expected:
                raise Rejected('gateway configuration differs from reviewed files')
        env = ready._env(ready._read(ROOT, 'secrets/preview.env', 0))
        edge = env.get('PREVIEW_EDGE_IP')
        ports = (env.get('PREVIEW_EDGE_HTTP'), env.get('PREVIEW_EDGE_HTTPS'))
        # A loopback-only fixture must not collide with the runner's registry.
        # The public edge accepts only standard HTTP/HTTPS host ports.
        if (edge, ports) not in (('0.0.0.0', ('80', '443')), ('127.0.0.2', ('18080', '18443'))):
            raise Rejected('edge bind address or ports not approved')
        validate_gateway_oauth(ready._read(ROOT, 'secrets/oauth2-proxy.cfg', 0), '172.28.190.2')
        return edge, ports
    except ready.NotReady as exc:
        raise Rejected('gateway files are missing or unsafe') from exc


def gateway_image_ids():
    identities = {}
    for service, reference in GATEWAY_IMAGES.items():
        items = json.loads(run([DOCKER, 'image', 'inspect', reference], output=True))
        tagged, digest = reference.split('@', 1)
        repo = tagged.rsplit(':', 1)[0]
        acceptable = {reference, repo + '@' + digest}
        if repo == 'caddy': acceptable.add('docker.io/library/caddy@' + digest)
        if (not isinstance(items, list) or len(items) != 1 or items[0].get('Os') != 'linux' or
                items[0].get('Architecture') != 'amd64' or not acceptable.intersection(items[0].get('RepoDigests') or []) or
                not re.fullmatch(r'sha256:[0-9a-f]{64}', items[0].get('Id', ''))):
            raise Rejected('gateway image identity mismatch')
        identities[service] = items[0]['Id']
    return identities


def start_gateway(app_id):
    """Start the one reviewed project; reject pre-existing unknown resources."""
    gateway_configuration()
    gateway_image_ids()
    existing = run([DOCKER, 'ps', '-aq', '--no-trunc', '--filter',
                    'label=com.docker.compose.project=xennic-preview-gateway'], output=True).decode('ascii').split()
    if existing:
        # Never recreate or replace an existing/unknown proxy or gate.
        require_verified_gateway(app_id)
        return
    for kind in ('network', 'volume'):
        if run([DOCKER, kind, 'ls', '-q', '--filter',
                'label=com.docker.compose.project=xennic-preview-gateway'], output=True).strip():
            raise Rejected('unexpected pre-existing gateway resources')
    for kind in ('network', 'volume'):
        names = run([DOCKER, kind, 'ls', '--format', '{{.Name}}'], output=True).decode('utf-8').splitlines()
        if any(name.startswith('xennic-preview-gateway_') for name in names):
            raise Rejected('unlabelled gateway resources exist')
    run(GATEWAY_COMPOSE + ['up', '-d', '--no-build', '--pull', 'never', '--wait'], timeout=180)
    require_verified_gateway(app_id)


def require_verified_gateway(app_id):
    """Require exact container images, configuration and network peers."""
    if not re.fullmatch('[0-9a-f]{12,64}', app_id): raise Rejected('invalid app identity')
    edge, edge_ports = gateway_configuration()
    images = gateway_image_ids()
    ids = {}
    items = {}
    for service in ('caddy', 'gate'):
        value = run(GATEWAY_COMPOSE + ['ps', '-q', service], output=True).decode('ascii').split()
        if len(value) != 1 or not re.fullmatch('[0-9a-f]{12,64}', value[0]):
            raise Rejected('gateway service unavailable or ambiguous')
        inspected = json.loads(run([DOCKER, 'inspect', value[0]], output=True))
        if len(inspected) != 1: raise Rejected('invalid gateway inspection')
        item = inspected[0]; labels = item.get('Config', {}).get('Labels') or {}
        expected_hash = run(GATEWAY_COMPOSE + ['config', '--hash', service], output=True).decode('ascii').split()
        if len(expected_hash) != 2 or expected_hash[0] != service or not re.fullmatch('[0-9a-f]{64}', expected_hash[1]):
            raise Rejected('gateway compose service hash unavailable')
        if (not item.get('State', {}).get('Running') or item.get('Image') != images[service] or
                labels.get('com.docker.compose.project') != 'xennic-preview-gateway' or
                labels.get('com.docker.compose.service') != service or
                labels.get('com.docker.compose.config-hash') != expected_hash[1]):
            raise Rejected('gateway container identity mismatch')
        ids[service] = item['Id']; items[service] = item
    running = run([DOCKER, 'ps', '-aq', '--no-trunc', '--filter',
                   'label=com.docker.compose.project=xennic-preview-gateway'], output=True).decode('ascii').split()
    if set(running) != set(ids.values()): raise Rejected('unknown gateway service')
    caddy, gate = items['caddy'], items['gate']
    caddy_net = caddy['NetworkSettings']['Networks']; gate_net = gate['NetworkSettings']['Networks']
    if (set(caddy_net) != {'xennic-preview_gateway', 'xennic-preview-gateway_auth'} or
            set(gate_net) != {'xennic-preview-gateway_auth'} or
            caddy_net['xennic-preview-gateway_auth'].get('IPAddress') != '172.28.190.2' or
            gate_net['xennic-preview-gateway_auth'].get('IPAddress') != '172.28.190.3' or
            gate_net['xennic-preview-gateway_auth'].get('NetworkID') != caddy_net['xennic-preview-gateway_auth'].get('NetworkID')):
        raise Rejected('gateway network mismatch')
    for network, expected in ((caddy_net['xennic-preview_gateway'], {app_id, ids['caddy']}),
                              (caddy_net['xennic-preview-gateway_auth'], {ids['caddy'], ids['gate']})):
        network_id = network.get('NetworkID', '')
        if not re.fullmatch('[0-9a-f]{12,64}', network_id): raise Rejected('invalid gateway network')
        entries = json.loads(run([DOCKER, 'network', 'inspect', network_id], output=True))
        if len(entries) != 1 or set((entries[0].get('Containers') or {}).keys()) != expected:
            raise Rejected('unknown gateway network peer')
    for service, item in items.items():
        host = item.get('HostConfig') or {}; config = item.get('Config') or {}
        image_info = json.loads(run([DOCKER, 'image', 'inspect', GATEWAY_IMAGES[service]], output=True))[0]
        base = image_info.get('Config') or {}
        if config.get('Entrypoint') != base.get('Entrypoint'):
            raise Rejected('gateway entrypoint mismatch')
        if service == 'caddy' and config.get('Cmd') != base.get('Cmd'):
            raise Rejected('Caddy command mismatch')
        base_env = dict(entry.split('=', 1) for entry in (base.get('Env') or []) if '=' in entry)
        if service == 'caddy':
            base_env.update({'GATE_ADDR': 'gate:4180', 'APP_ADDR': 'app:3000', 'PUBLIC_AUTHORITY': 'preview.xennic.ir'})
        actual_env = config.get('Env') or []
        parsed_env = dict(entry.split('=', 1) for entry in actual_env if '=' in entry)
        if len(parsed_env) != len(actual_env) or parsed_env != base_env:
            raise Rejected('gateway environment mismatch')
        if (host.get('NetworkMode') == 'host' or host.get('PublishAllPorts') or host.get('Privileged') or
                host.get('Devices') or host.get('PidMode') == 'host' or host.get('IpcMode') == 'host' or
                host.get('ExtraHosts') or host.get('CapAdd') or host.get('LogConfig', {}).get('Type') != 'none'):
            raise Rejected('gateway host configuration is unsafe')
        if service == 'gate':
            if (host.get('PortBindings') or any((item['NetworkSettings'].get('Ports') or {}).values()) or
                    config.get('User') != '0:0' or config.get('Cmd') != ['--config=/etc/oauth2-proxy.cfg'] or
                    not host.get('ReadonlyRootfs') or 'ALL' not in (host.get('CapDrop') or []) or
                    any(entry.startswith('OAUTH2_PROXY_') for entry in (config.get('Env') or []))):
                raise Rejected('gate effective configuration is unsafe')
        else:
            bindings = host.get('PortBindings') or {}
            expected_ports = {'80/tcp': edge_ports[0], '443/tcp': edge_ports[1]}
            if set(bindings) != set(expected_ports) or any(
                    bindings[p] != [{'HostIp': edge, 'HostPort': expected_ports[p]}] for p in bindings):
                raise Rejected('Caddy port mapping mismatch')
            env = dict(entry.split('=', 1) for entry in (config.get('Env') or []) if '=' in entry)
            if any(env.get(k) != v for k, v in {'GATE_ADDR': 'gate:4180', 'APP_ADDR': 'app:3000',
                                                 'PUBLIC_AUTHORITY': 'preview.xennic.ir'}.items()) or 'CADDY_SITE' in env:
                raise Rejected('Caddy effective configuration is unsafe')
    expected_mounts = {
        'gate': {'/etc/oauth2-proxy.cfg': str(ROOT / 'secrets/oauth2-proxy.cfg')},
        'caddy': {'/etc/caddy/Caddyfile': str(ROOT / 'config/Caddyfile'),
                  '/etc/caddy/routes.caddy': str(ROOT / 'config/routes.caddy'),
                  '/etc/caddy/oauth-gateway.caddy': str(ROOT / 'config/oauth-gateway.caddy'),
                  '/etc/caddy/upstream.caddy': str(ROOT / 'config/upstream.caddy')},
    }
    for service, mounts in expected_mounts.items():
        actual = {m.get('Destination'): m for m in items[service].get('Mounts', [])}
        allowed = set(mounts) | ({'/data', '/config'} if service == 'caddy' else set())
        if set(actual) != allowed: raise Rejected('gateway mounts are unexpected')
        for dest, source in mounts.items():
            item = actual[dest]
            if item.get('Type') != 'bind' or item.get('Source') != source or item.get('RW') is not False:
                raise Rejected('gateway config mount mismatch')
        if service == 'caddy':
            for dest, name in (('/data', 'xennic-preview-gateway_caddy_data'), ('/config', 'xennic-preview-gateway_caddy_config')):
                if actual[dest].get('Type') != 'volume' or actual[dest].get('Name') != name:
                    raise Rejected('Caddy volume mismatch')
    return caddy_net['xennic-preview_gateway'].get('IPAddress', '')


def check_health(release):
    config_for(release)
    app = running_app_id(release)
    healthcheck.ENV = dict(SAFE, PREVIEW_IMAGE=reference(release))
    healthcheck.check_once()
    # Fail closed while gateway identity/startup is incomplete. A healthy
    # internal application alone must never become a healthy release. The
    # existing peer check still rejects every unrecognized gateway.
    caddy_ip = require_verified_gateway(app)
    check_ingress_protection(caddy_ip)


def execute(phase, release, token):
    if phase == 'release-check':
        gateway_configuration()
        gateway_image_ids()
        journal = states.Journal()
        initial = journal.absent()
        previous = None if initial else journal.read()['current']
        if not initial and previous is None:
            raise Rejected('existing journal has no healthy release')
        verifier.verify(release, token)
        if initial:
            assert_initial_pristine(release)
        else:
            assert_current_host(previous)
            check_health(previous)
            approval(previous, release)
        return {'initial': initial, 'rollback_safe': not initial, 'verified_commit': release['commit'],
                'verified_digest': release['digest'], 'verified_run_number': release['run_number']}
    if phase == 'current-check':
        verifier.assert_current(release, token)
        return None
    if phase == 'migrate':
        current = pending(release)['current']
        if current is None:
            image = assert_initial_pristine(release, journal_exists=True)
            image_id(release)
            run(COMPOSE + ['up', '-d', '--no-build', '--wait', 'postgres'], image=image, timeout=180)
            assert_initial_database(image)
            run(COMPOSE + ['run', '--rm', '--no-deps', '-T', 'app', 'npm', 'run', 'preview:migrate'], image=image, timeout=600)
            assert_initial_database(image)
            run(COMPOSE + ['run', '--rm', '--no-deps', '-T', 'app', 'npm', 'run', 'preview:seed'], image=image, timeout=600)
            assert_initial_database(image)
            return None
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
        current = pending(release)['current']
        marker = ROOT / 'state' / f"activation-{release['run_number']}.json"
        reactivation = current is None and os.path.lexists(marker)
        if current is not None or reactivation:
            verify_backup(release)
        if reactivation:
            try:
                recorded = json.loads(ready._read(ROOT, f"state/activation-{release['run_number']}.json", 0))
            except (ValueError, UnicodeError, ready.NotReady) as exc:
                raise Rejected('initial activation marker invalid') from exc
            if recorded != release: raise Rejected('initial activation marker mismatch')
        image = config_for(release)
        image_id(release)
        run(COMPOSE + ['up', '-d', '--no-deps', '--no-build', '--force-recreate', '--wait', 'app'], image=image, timeout=180)
        ids = run(COMPOSE + ['ps', '-q', 'app'], image=image, output=True).decode('ascii').split()
        if len(ids) != 1 or not re.fullmatch('[0-9a-f]{12,64}', ids[0]):
            raise Rejected('activated app is ambiguous')
        inspected = json.loads(run([DOCKER, 'inspect', ids[0]], output=True))
        if len(inspected) != 1 or inspected[0].get('Image') != image_id(release):
            raise Rejected('activated app image mismatch')
        start_gateway(inspected[0]['Id'])
        running_app_id(release)
        if reactivation: return None
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
    if phase == 'close-initial':
        # Fixed failure-only operation. It does not depend on a readable journal:
        # an interrupted state write must not leave this exact app exposed.
        image = config_for(release)
        ids = run(COMPOSE + ['ps', '--all', '-q', 'app'], image=image, output=True).decode('ascii').split()
        if len(ids) > 1 or any(not re.fullmatch('[0-9a-f]{12,64}', item) for item in ids):
            raise Rejected('initial app is ambiguous')
        if ids:
            info = json.loads(run([DOCKER, 'inspect', ids[0]], output=True))[0]
            if info.get('Image') != image_id(release): raise Rejected('initial app image mismatch')
            run(COMPOSE + ['stop', '-t', '30', 'app'], image=image, timeout=60)
            after = json.loads(run([DOCKER, 'inspect', ids[0]], output=True))[0]
            if after.get('State', {}).get('Running'): raise Rejected('initial app still running')
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
        extra = sys.stdin.buffer.read(32)
        if extra:
            if phase != 'rollback' or extra != b'initial-close\n' or sys.stdin.buffer.read(1):
                raise Rejected('extra input')
            phase = 'close-initial'
        result = execute(phase, release, token)
        if result is not None: print(json.dumps(result, separators=(',', ':')))
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, UnicodeError):
        print('Fixed preview operation failed; inspect locally with redaction', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
