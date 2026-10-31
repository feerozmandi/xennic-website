#!/usr/bin/env python3
"""Opt in to read:org on the owner's exact isolated lab gate, with rollback.

No OAuth secrets, callback URLs, cookies, or raw subprocess output are printed.
This does not touch any other Compose project, the app DB, VPS, or DNS.
"""
import base64
import binascii
import getpass
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
import warnings

PROJECT = 'xennic-real-oauth-73c028764aa6'
GATE_IMAGE = 'quay.io/oauth2-proxy/oauth2-proxy:v7.15.5@sha256:8498b0d0ef0a7b29686414000a08aee467f02d0299c9ed1e006a8f33fc017916'
CADDY_IMAGE = 'caddy:2.11.7@sha256:36c24ad91a7ff7bc4c87fe22bfa8df3c4b18da0773d73fc12ee2c52b98c0bb7e'
COMPOSE_SHA = '6a6def062d160b4a52636726fc2c6500f0973fd4bf822eaf38a2fe1782116327'
ROOT = Path.home() / 'xennic-real-oauth-lab.UJInfVse'
ENV_KEYS = {'APP_IMAGE', 'LAB_UID', 'LAB_GID', 'DB_PASSWORD', 'DATABASE_URL', 'PAYLOAD_SECRET'}
ENV_UNSET = ENV_KEYS | {'COMPOSE_FILE', 'COMPOSE_PROFILES', 'COMPOSE_PROJECT_NAME', 'COMPOSE_ENV_FILES',
                         'COMPOSE_REMOVE_ORPHANS', 'COMPOSE_IGNORE_ORPHANS'}


class LabError(Exception):
    pass


def run(args, *, env=None, timeout=30):
    result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env, timeout=timeout, check=True)
    return result.stdout.decode('utf-8')


def private_file(path):
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) != 0o600:
        raise LabError('expected a private owned regular file')
    return path.read_text(encoding='utf-8')


def read_env(root):
    text = private_file(root / 'lab.env')
    lines = text.splitlines()
    pairs = [x.split('=', 1) for x in lines]
    if any(len(x) != 2 for x in pairs) or len(lines) != len(ENV_KEYS):
        raise LabError('unexpected private environment format')
    data = dict(pairs)
    if set(data) != ENV_KEYS or data['LAB_UID'] != str(os.getuid()) or data['LAB_GID'] != str(os.getgid()):
        raise LabError('unexpected private environment')
    pwd = data['DB_PASSWORD']
    if (not re.fullmatch(r'[a-f0-9]{64}', pwd)
            or data['DATABASE_URL'] != 'postgresql://xennic_lab:' + pwd + '@postgres:5432/xennic_lab'
            or not re.fullmatch(r'sha256:[a-f0-9]{64}', data['APP_IMAGE'])
            or not re.fullmatch(r'[A-Za-z0-9_-]{64}', data['PAYLOAD_SECRET'])):
        raise LabError('unexpected private environment')
    return data


def validate_config(text, caddy_ip):
    ip = ipaddress.ip_address(caddy_ip)
    if ip.version != 4 or not ip.is_private:
        raise LabError('unexpected Caddy address')
    data = {}
    lines = text.splitlines()
    for line in lines:
        match = re.fullmatch(r'([a-z_]+) = (.+)', line)
        if not match or match.group(1) in data:
            raise LabError('unexpected config format')
        data[match.group(1)] = json.loads(match.group(2))
    expected = {
        'provider': 'github', 'github_users': ['feerozmandi'], 'email_domains': ['*'],
        'scope': 'user:email', 'reverse_proxy': True, 'trusted_proxy_ips': [str(ip) + '/32'],
        'http_address': '0.0.0.0:4180', 'redirect_url': 'https://preview.xennic.ir/oauth2/callback',
        'upstreams': ['static://202'], 'whitelist_domains': ['preview.xennic.ir'],
        'cookie_name': '__Host-preview_gate', 'cookie_secure': True, 'cookie_httponly': True,
        'cookie_samesite': 'lax', 'cookie_expire': '1h', 'cookie_refresh': '0',
        'skip_jwt_bearer_tokens': False, 'skip_auth_preflight': False,
        'pass_basic_auth': False, 'pass_authorization_header': False, 'set_authorization_header': False,
        'pass_access_token': False, 'set_xauthrequest': False, 'request_logging': False, 'auth_logging': False,
    }
    if set(data) != set(expected) | {'client_id', 'client_secret', 'cookie_secret'}:
        raise LabError('unexpected config keys')
    if any(data[k] != value for k, value in expected.items()):
        raise LabError('unexpected gate policy')
    if any(not isinstance(data[k], str) or not data[k] or any(ord(c) < 32 for c in data[k])
           for k in ('client_id', 'client_secret', 'cookie_secret')):
        raise LabError('unexpected private values')
    try:
        if len(base64.urlsafe_b64decode(data['cookie_secret'])) != 32:
            raise LabError('unexpected cookie key')
    except (binascii.Error, ValueError):
        raise LabError('unexpected cookie key') from None
    old = 'scope = "user:email"\n'
    if text.count(old) != 1:
        raise LabError('scope is not the expected baseline')
    return text.replace(old, 'scope = "user:email read:org"\n', 1), data['client_id']


def confirm_test_app_id(expected):
    # The new App must be verified locally; never print either ID or accept an
    # echoing fallback. The old production or lab App is not authorized here.
    warnings.simplefilter('error', getpass.GetPassWarning)
    with open('/dev/tty', 'w', encoding='utf-8') as tty:
        provided = getpass.getpass('Client ID from the NEW independent test App settings (hidden): ', stream=tty).strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise LabError('test app identity mismatch')


def write_atomic(path, text):
    fd, temp = tempfile.mkstemp(prefix='.oauth-scope-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass


def docker(args):
    return run(['docker', *args], timeout=20).strip()


def local_daemon():
    host = os.environ.get('DOCKER_HOST')
    if host and os.environ.get('DOCKER_CONTEXT'):
        raise LabError('ambiguous Docker host')
    if not host:
        context = docker(['context', 'show'])
        host = docker(['context', 'inspect', context, '--format', '{{(index .Endpoints "docker").Host}}'])
    if not host.startswith('unix://'):
        raise LabError('local Docker daemon required')


def service(name):
    ids = docker(['ps', '-q', '--filter', 'label=com.docker.compose.project=' + PROJECT,
                  '--filter', 'label=com.docker.compose.service=' + name]).splitlines()
    if len(ids) != 1 or not re.fullmatch(r'[a-f0-9]{12,64}', ids[0]):
        raise LabError('expected running service unavailable')
    details = json.loads(docker(['inspect', ids[0]]))
    if len(details) != 1:
        raise LabError('unexpected service inspection')
    c = details[0]
    labels = c['Config']['Labels'] or {}
    if not c['State']['Running'] or labels.get('com.docker.compose.project') != PROJECT or labels.get('com.docker.compose.service') != name:
        raise LabError('unexpected service')
    return ids[0], c


def bound(ports):
    return [(port, b) for port, bindings in (ports or {}).items() for b in (bindings or [])]


def validate_gate(gate, root):
    if gate['Config']['Image'] != GATE_IMAGE or gate['HostConfig']['LogConfig']['Type'] != 'none':
        raise LabError('unexpected gate image or logger')
    if set(gate['NetworkSettings']['Networks']) != {PROJECT + '_auth', PROJECT + '_egress'}:
        raise LabError('unexpected gate networks')
    if bound(gate['HostConfig'].get('PortBindings')) or bound(gate['NetworkSettings'].get('Ports')):
        raise LabError('unexpected gate port')
    mounts = [m for m in gate['Mounts'] if m.get('Destination') == '/run/private/oauth.toml']
    if len(mounts) != 1 or mounts[0].get('Source') != str(root / 'oauth.toml') or mounts[0].get('RW') is not False:
        raise LabError('unexpected gate config mount')


def caddy_details(caddy):
    if caddy['Config']['Image'] != CADDY_IMAGE or caddy['HostConfig']['LogConfig']['Type'] != 'none':
        raise LabError('unexpected Caddy image or logger')
    nets = caddy['NetworkSettings']['Networks']
    if set(nets) != {PROJECT + '_frontend', PROJECT + '_backend', PROJECT + '_auth'}:
        raise LabError('unexpected Caddy networks')
    for ports in (caddy['HostConfig'].get('PortBindings'), caddy['NetworkSettings'].get('Ports')):
        b = bound(ports)
        if len(b) != 1 or b[0][0] != '443/tcp' or b[0][1].get('HostIp') != '127.0.0.1' or b[0][1].get('HostPort') != '443':
            raise LabError('unexpected Caddy binding')
    return nets[PROJECT + '_auth']['IPAddress']


def compose_env():
    env = dict(os.environ)
    for key in ENV_UNSET:
        env.pop(key, None)
    env['COMPOSE_IGNORE_ORPHANS'] = '1'
    return env


def recreate_gate(root):
    run(['docker', 'compose', '--project-directory', str(root), '--env-file', str(root / 'lab.env'),
         '-p', PROJECT, '-f', str(root / 'compose.yml'), 'up', '-d', '--no-deps', '--force-recreate',
         '--no-build', '--pull', 'never', 'gate'], env=compose_env(), timeout=90)


def ready(root, old_gate, caddy_id, expected_ip):
    ca = root / 'lab-root.crt'
    if not ca.is_file() or ca.is_symlink():
        raise LabError('retained CA unavailable')
    for _ in range(30):
        try:
            gate_id, gate = service('gate')
            current_caddy_id, caddy = service('caddy')
            validate_gate(gate, root)
            if gate_id == old_gate or current_caddy_id != caddy_id or caddy_details(caddy) != expected_ip:
                raise LabError('unexpected service change')
            result = subprocess.run(['curl', '-q', '--silent', '--max-time', '3', '--noproxy', '*',
                                     '--resolve', 'preview.xennic.ir:443:127.0.0.1', '--cacert', str(ca),
                                     '--output', '/dev/null', '--write-out', '%{http_code}',
                                     'https://preview.xennic.ir/api/staff/me'], stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5)
            if result.returncode == 0 and result.stdout == b'401':
                return
        except (LabError, OSError, KeyError, ValueError, subprocess.SubprocessError):
            pass
        time.sleep(1)
    raise LabError('gate did not become ready')


def apply_change(path, original, changed, recreate_and_check):
    """Apply once and roll back both file and gate on a handled failure."""
    try:
        # Include the atomic write in the rollback guard, including interruptions.
        write_atomic(path, changed)
        recreate_and_check()
    except (Exception, KeyboardInterrupt) as failure:
        try:
            write_atomic(path, original)
            recreate_and_check()
        except (Exception, KeyboardInterrupt):
            raise LabError('rollback incomplete') from None
        raise LabError('rolled back') from failure


def main():
    # Keep an interrupted change recoverable; SIGKILL or power loss cannot be trapped.
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        st = ROOT.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) != 0o700:
            raise LabError('unexpected private lab directory')
        if hashlib.sha256((ROOT / 'compose.yml').read_bytes()).hexdigest() != COMPOSE_SHA:
            raise LabError('unexpected lab Compose')
        read_env(ROOT)
        local_daemon()
        gate_id, gate = service('gate')
        caddy_id, caddy = service('caddy')
        validate_gate(gate, ROOT)
        ip = caddy_details(caddy)
        path = ROOT / 'oauth.toml'
        original = private_file(path)
        changed, expected_client_id = validate_config(original, ip)
        print('PASS: exact active lab gate, policy, local networks and private config verified.', flush=True)
        confirm_test_app_id(expected_client_id)
        print('PASS: local gate Client ID matches the independently confirmed test App.', flush=True)
        print('Applying only the explicitly approved temporary read:org scope to this lab gate.', flush=True)

        def recreate_and_check():
            previous_id, _ = service('gate') if docker(['ps', '-q', '--filter', 'label=com.docker.compose.project=' + PROJECT,
                                                        '--filter', 'label=com.docker.compose.service=gate']) else ('', None)
            recreate_gate(ROOT)
            ready(ROOT, previous_id, caddy_id, ip)

        apply_change(path, original, changed, recreate_and_check)
        print('PASS: lab gate restarted and unauthenticated API still returns 401.', flush=True)
        print('Configured scope: user:email read:org. GitHub authorization and login are NOT yet confirmed.', flush=True)
        print('GitHub grant may remain until the owner revokes it after the test.', flush=True)
        return 0
    except LabError as e:
        if str(e) == 'rolled back':
            print('STOP: change failed; original scope and lab gate were restored.', file=sys.stderr)
        elif str(e) == 'rollback incomplete':
            print('STOP: automatic rollback incomplete; do not retry, inspect only this lab.', file=sys.stderr)
        elif str(e) == 'test app identity mismatch':
            print('STOP: test App Client ID does not match the running lab; nothing changed.', file=sys.stderr)
        else:
            print('STOP: lab precondition or readiness failed; no private values printed.', file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, getpass.GetPassWarning,
            EOFError, subprocess.SubprocessError, KeyboardInterrupt):
        print('STOP: could not verify or update the lab; no private values printed.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
