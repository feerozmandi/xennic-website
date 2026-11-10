#!/usr/bin/env python3
"""Read-only pre-check for the reviewed preview -> apex edge switch.

Run as root on the preview server before `install-preview-sftp-helper.py
--upgrade-apex`. It reads only; it never writes, starts or stops anything, and
it prints no secret values. A non-zero exit means the switch must not run.
"""
import hashlib
import os
from pathlib import Path
import stat
import sys

sys.dont_write_bytecode = True
ROOT = Path('/srv/xennic-preview')
SOURCE = Path('/root/xennic-preview-install')
TARGET = Path('/usr/local/libexec/xennic-preview')
APEX_MANIFEST = 'c141100bd456b0f2ade106c4814ecf88dbc89b86257a2167e0a94e9637f68170'
# The installed preview release (dev commit 09a9d00): routes predate the
# public apex allowlist, so the switch installs the reviewed routes as well.
PREVIEW = {
    'Caddyfile': 'c52da3f16ff668cd3ad068c6f059cb8cfbad4e8eecbeec9d6bf39fd3fe2bc0d7',
    'gateway.yml': 'a6a84eb7d5c0be188d301ecf9ec38c2b5e9e6189dd66d3ac12d2f1966a0e363b',
    'routes.caddy': 'd089cbb65414cd01600383df1bfbea10c0ab6c8e423ad4701324cb368e902033',
    'oauth-gateway.caddy': '34220eb12245d54b8f4231527daad495a11bb559436148a0317e0b9837eaa195',
    'upstream.caddy': '59bdf04300141b80d114a96621165c5cf3a7e4f673554de2204cf70c928e40a8'}
APEX = {
    'apex-Caddyfile': '462370b17bf40923bb92d05e39a522acd34ccc08694f2f3b660e273e18d062f2',
    'apex-gateway-compose.yml': '1444baea48b7aedf2747b7e596872d8b7828bba7544be8dbe05e7720503833ed',
    'routes.caddy': 'a4d844df988812c4cd1922e7ca9a18c34281518bad27f5621be4d57bb8124029'}
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


def main():
    state, work = list((ROOT / 'state').iterdir()), list((ROOT / 'work').iterdir())
    journal = os.path.lexists(ROOT / 'state/release-state.json')
    print('STATE=%s WORK=%s JOURNAL=%s' % ('EMPTY' if not state else 'NOT_EMPTY',
                                           'EMPTY' if not work else 'NOT_EMPTY',
                                           'PRESENT' if journal else 'ABSENT'))
    if state or work or journal:
        problems.append('deployment state is not pristine')
    edge = []
    for name, expected in PREVIEW.items():
        try:
            ok = digest(ROOT / 'config' / name) == expected
        except OSError:
            ok = False
        edge.append((name, 'PASS' if ok else 'FAIL'))
        if not ok:
            problems.append(f'installed {name} is not the reviewed release')
    report('EDGE', edge)
    for name in ('oauth2-proxy.cfg', 'preview.env'):
        ok = private(ROOT / 'secrets' / name, 0o600)
        print(f'SECRET={name}:{"PASS" if ok else "FAIL"}')
        if not ok:
            problems.append(f'secret {name} is missing or unsafe')
    expected_names = {name for source in FILES for name in ALIASES.get(source, (source,))}
    present = {path.name for path in TARGET.iterdir()} if TARGET.is_dir() else set()
    target_ok = present == expected_names
    if not target_ok:
        problems.append('installed helper set is unexpected')
    alias_ok = len({digest(TARGET / name) for name in ALIASES['preview-fixed-operations.py']
                    if (TARGET / name).exists()}) == 1
    if not alias_ok:
        problems.append('installed guard aliases differ')
    report('HELPERS', [('TARGET', 'PASS' if target_ok else 'FAIL'),
                       ('ALIASES', 'PASS' if alias_ok else 'FAIL')])
    incoming = SOURCE / 'incoming-apex'
    modes = all(private(incoming / name, 0o600) for name in FILES)
    if not modes:
        problems.append('staged helper modes are wrong')
    try:
        lines = ''.join(f'{digest(incoming / name)}  scripts/{name}\n' for name in FILES)
        manifest = hashlib.sha256(lines.encode()).hexdigest() == APEX_MANIFEST
    except OSError:
        manifest = False
    if not manifest:
        problems.append('staged helpers are not the reviewed release')
    try:
        apex_ok = all(digest(incoming / name) == expected for name, expected in APEX.items())
    except OSError:
        apex_ok = False
    if not apex_ok:
        problems.append('staged edge files are not the reviewed ones')
    report('STAGED', [('MANIFEST', 'PASS' if manifest else 'FAIL'),
                      ('APEX_FILES', 'PASS' if apex_ok else 'FAIL')])
    prior = [('APEX_STATE', os.path.lexists(ROOT / 'config/.apex-before')),
             ('BACKUP_APEX', os.path.lexists('/usr/local/libexec/.xennic-preview-before-apex'))]
    report('PRIOR', [(name, 'PRESENT' if value else 'ABSENT') for name, value in prior])
    if any(value for _, value in prior):
        problems.append('a previous apex switch already exists; review it first')
    report('STAGING', [(p.name, 'dir' if p.is_dir() else 'file') for p in sorted(SOURCE.iterdir())])
    if problems:
        print('READY=STOP ' + '; '.join(sorted(set(problems))))
        return 1
    print('READY=PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
