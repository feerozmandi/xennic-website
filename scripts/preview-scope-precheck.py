#!/usr/bin/env python3
"""Read-only pre-check for the reviewed gateway scope update.

Run as root on the deployed preview server before
`install-preview-sftp-helper.py --upgrade-scope`. It reads only; it never
writes, restarts or deploys anything, and prints no secret values. A non-zero
exit means the update must not run.
"""
import hashlib
import os
from pathlib import Path
import stat
import sys
import tomllib

sys.dont_write_bytecode = True
ROOT = Path('/srv/xennic-preview')
SOURCE = Path('/root/xennic-preview-install')
TARGET = Path('/usr/local/libexec/xennic-preview')
PARENT = Path('/usr/local/libexec')
CURRENT_MANIFEST = 'c141100bd456b0f2ade106c4814ecf88dbc89b86257a2167e0a94e9637f68170'
SCOPE_MANIFEST = 'de2a97a75819407576a0292900096d8e170878d83ef6c3e09175caa4e0097854'
APEX_CADDYFILE = '462370b17bf40923bb92d05e39a522acd34ccc08694f2f3b660e273e18d062f2'
PREVIEW_CADDYFILE = 'c52da3f16ff668cd3ad068c6f059cb8cfbad4e8eecbeec9d6bf39fd3fe2bc0d7'
SCOPE_OLD = 'user:email'
SCOPE_NEW = 'user:email read:org'
AUTHORITIES = {APEX_CADDYFILE: 'xennic.ir', PREVIEW_CADDYFILE: 'preview.xennic.ir'}
FILES = ('preview-backup-sftp.py', 'preview-backup-operation.py', 'preview-pull-image.py',
         'preview-age-backup.py', 'preview-deploy-readiness.py', 'preview-deploy-state.py',
         'preview-deploy-manifest.py', 'preview-deploy-backend.py', 'preview-deploy-transaction.py',
         'preview-deploy-lock.py', 'preview-internal-health.py', 'preview-compose-operations.py',
         'preview-release-verifier.py', 'preview-fixed-operations.py', 'preview-deploy-receiver.py')
ALIASES = {'preview-backup-sftp.py': ('sftp-transfer',),
           'preview-backup-operation.py': ('backup-verify', 'preview-backup-operation.py'),
           'preview-pull-image.py': ('pull-image',),
           'preview-fixed-operations.py': ('release-check', 'current-check', 'migrate', 'activate',
                                           'health', 'rollback'),
           'preview-deploy-receiver.py': ('deploy-receiver',)}
BACKUP_SCOPE = PARENT / '.xennic-preview-before-scope'
NEW_DIR = PARENT / '.xennic-preview-update'
problems = []


def digest(path):
    with open(path, 'rb') as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def private(path, mode):
    try:
        info = os.lstat(path)
    except OSError:
        return False
    return (stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1 and
            stat.S_IMODE(info.st_mode) == mode)


def report(label, values):
    print(label + '=' + ' '.join(f'{key}:{value}' for key, value in values))


def toml_value(value):
    if type(value) is bool:
        return 'true' if value else 'false'
    if type(value) is int:
        return str(value)
    if isinstance(value, str):
        return '"' + value + '"'
    if isinstance(value, list) and value and all(isinstance(item, str) for item in value):
        return '[' + ', '.join(toml_value(item) for item in value) + ']'
    raise ValueError('unsupported gateway value')


def canonical(config):
    return ''.join(f'{key} = {toml_value(config[key])}\n' for key in sorted(config))


def helper_manifest(directory):
    data = {}
    for name in FILES:
        for installed in ALIASES.get(name, (name,)):
            raw = Path(directory, installed).read_bytes()
            if name in data and data[name] != raw:
                raise ValueError('alias differs')
            data[name] = raw
    lines = ''.join(f'{hashlib.sha256(data[name]).hexdigest()}  scripts/{name}\n' for name in FILES)
    return hashlib.sha256(lines.encode('ascii')).hexdigest()


def installed_names():
    expected = {installed for name in FILES for installed in ALIASES.get(name, (name,))}
    present = {path.name for path in TARGET.iterdir()} if TARGET.is_dir() else set()
    return expected, present


def main():
    for name in ('oauth2-proxy.cfg', 'preview.env'):
        ok = private(ROOT / 'secrets' / name, 0o600)
        print(f'SECRET={name}:{"PASS" if ok else "FAIL"}')
        if not ok:
            problems.append(f'secret {name} is missing or unsafe')
    try:
        caddy = digest(ROOT / 'config/Caddyfile')
    except OSError:
        caddy = ''
    authority = AUTHORITIES.get(caddy)
    report('EDGE', [('Caddyfile', 'PASS' if authority else 'FAIL'), ('AUTHORITY', authority or 'UNKNOWN')])
    if authority is None:
        problems.append('installed Caddyfile is not a reviewed edge')
    expected, present = installed_names()
    try:
        manifest = helper_manifest(TARGET)
    except (OSError, ValueError):
        manifest = ''
    target_ok = present == expected and manifest == CURRENT_MANIFEST
    report('HELPERS', [('TARGET', 'PASS' if target_ok else 'FAIL'), ('MANIFEST', manifest[:8] or 'UNKNOWN')])
    if not target_ok:
        problems.append('installed helpers are not the reviewed release')
    policy = None
    try:
        raw = (ROOT / 'secrets' / 'oauth2-proxy.cfg').read_bytes()
        policy = tomllib.loads(raw.decode('utf-8'))
    except (OSError, ValueError, UnicodeError):
        problems.append('installed gateway policy cannot be read')
    if policy is not None:
        scope_old = policy.get('scope') == SCOPE_OLD
        canonical_ok = canonical(policy).encode('ascii') == raw
        updated = dict(policy)
        updated['scope'] = SCOPE_NEW
        only_scope = canonical(updated).encode('ascii').replace(
            f'scope = "{SCOPE_NEW}"\n'.encode('ascii'),
            f'scope = "{SCOPE_OLD}"\n'.encode('ascii')) == raw
        report('POLICY', [('SCOPE', 'OLD' if scope_old else 'OTHER'),
                          ('CANONICAL', 'PASS' if canonical_ok else 'FAIL'),
                          ('ONLY_SCOPE', 'PASS' if only_scope else 'FAIL')])
        if not scope_old:
            problems.append('installed gateway scope is not the reviewed baseline')
        if not canonical_ok:
            problems.append('installed gateway policy is not in canonical form')
        if not only_scope:
            problems.append('installed gateway policy differs beyond the scope')
    incoming = SOURCE / 'incoming-scope'
    modes = all(private(incoming / name, 0o600) for name in FILES) if incoming.is_dir() else False
    try:
        staged = helper_manifest(incoming) if incoming.is_dir() else ''
    except (OSError, ValueError):
        staged = ''
    report('STAGED', [('MODES', 'PASS' if modes else 'FAIL'),
                      ('MANIFEST', 'PASS' if staged == SCOPE_MANIFEST else 'FAIL')])
    if not modes:
        problems.append('staged helper modes are wrong')
    if staged != SCOPE_MANIFEST:
        problems.append('staged helpers are not the reviewed candidate')
    prior = [('BACKUP_SCOPE', os.path.lexists(BACKUP_SCOPE)), ('UPDATE_DIR', os.path.lexists(NEW_DIR))]
    report('PRIOR', [(name, 'PRESENT' if value else 'ABSENT') for name, value in prior])
    if any(value for _, value in prior):
        problems.append('a previous scope update already exists; review it first')
    report('STAGING', [(p.name, 'dir' if p.is_dir() else 'file') for p in sorted(SOURCE.iterdir())]
           if SOURCE.is_dir() else [('SOURCE', 'MISSING')])
    if problems:
        print('READY=STOP ' + '; '.join(sorted(set(problems))))
        return 1
    print('READY=PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
