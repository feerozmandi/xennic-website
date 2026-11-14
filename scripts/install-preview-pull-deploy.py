#!/usr/bin/python3
"""Install the pull-based deployer and its timer; root only, no arguments.

Installs exactly these, all root-owned:

    /usr/local/libexec/xennic-preview/ci-pull-deploy           0755
    /usr/local/libexec/xennic-preview/preview-ci-evidence.py   0644
    /etc/systemd/system/xennic-pull-deploy.{service,timer}     0644

then reloads systemd and enables the timer. It does not create users, keys,
tokens or notification settings, and it never runs a deployment itself: the
first tick is five minutes later and behaves exactly like every later tick.

The timer is the whole point of the design — the host reaches out to GitHub over
HTTPS, so no inbound port has to be open for a runner that cannot reach it.
"""
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import sys

sys.dont_write_bytecode = True

SOURCE_DIR = Path('/root/xennic-preview-pull-deploy')
SOURCE = SOURCE_DIR / 'preview-pull-deploy.py'
# The deployer binds a release artifact to its run, so it needs this module.
# It is not part of the privileged helper set installed earlier, which is why
# this installer ships it rather than merely requiring it.
EVIDENCE_SOURCE = SOURCE_DIR / 'preview-ci-evidence.py'
HELPERS = Path('/usr/local/libexec/xennic-preview')
TARGET = HELPERS / 'ci-pull-deploy'
EVIDENCE_TARGET = HELPERS / 'preview-ci-evidence.py'
UNITS = Path('/etc/systemd/system')
SERVICE = UNITS / 'xennic-pull-deploy.service'
TIMER = UNITS / 'xennic-pull-deploy.timer'
MODE_FILE = 0o755
MODE_MODULE = 0o644
MODE_UNIT = 0o644
MAX_BYTES = 200 * 1024

SERVICE_BODY = """[Unit]
Description=Xennic pull deployment (asks GitHub, deploys the approved release)
Documentation=https://github.com/feerozmandi/xennic-website/blob/dev/docs/reports/2026-11-12-pull-deploy.md
After=network-online.target docker.service
Wants=network-online.target
ConditionPathExists=/root/.xennic-release-token

[Service]
Type=oneshot
ExecStart=/usr/local/libexec/xennic-preview/ci-pull-deploy
User=root
Group=root
Environment=PYTHONDONTWRITEBYTECODE=1
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=6
TimeoutStartSec=3900
PrivateTmp=yes
"""

TIMER_BODY = """[Unit]
Description=Check GitHub for an approved Xennic release every five minutes

[Timer]
OnBootSec=3min
OnUnitActiveSec=5min
AccuracySec=30s
Persistent=false
Unit=xennic-pull-deploy.service

[Install]
WantedBy=timers.target
"""

# The deployer reads these at runtime; a missing one is a clear error, not a
# silent half-deployment.
# What the deployer and the backend it calls need to already be on the host.
# `preview-fixed-operations.py` is deliberately absent: the helper installer
# never writes that file under its own name — it installs copies under the phase
# names (release-check, migrate, …), which is what the backend executes. Asking
# for the source name made this installer fail on a correctly installed host.
REQUIRED = ('preview-deploy-backend.py', 'preview-deploy-manifest.py', 'preview-deploy-state.py',
            'preview-deploy-lock.py', 'preview-release-verifier.py',
            'preview-backup-operation.py', 'pull-image',
            'release-check', 'current-check', 'migrate', 'activate', 'health', 'rollback')


def clean(path, *, executable=False):
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise RuntimeError(f'{path} is missing; run the earlier helper install first') from exc
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise RuntimeError(f'{path} has an unsafe owner or mode')
    if executable and not info.st_mode & stat.S_IXUSR:
        raise RuntimeError(f'{path} is not executable')


def write_atomic(path, data, mode):
    staged = path.with_name(f'.{path.name}.staged')
    if os.path.lexists(staged):
        raise RuntimeError(f'staged file for {path.name} already exists')
    fd = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(staged, mode)
    os.replace(staged, path)


def main():
    if os.geteuid() != 0 or len(sys.argv) != 1:
        print('pull deploy install requires root and no arguments.', file=sys.stderr)
        return 1
    os.umask(0o077)
    try:
        info = os.lstat(HELPERS)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022
                or str(HELPERS) != '/usr/local/libexec/xennic-preview'):
            raise RuntimeError('unsafe installation directory')
        clean(SOURCE)
        clean(EVIDENCE_SOURCE)
        data = SOURCE.read_bytes()
        if len(data) > MAX_BYTES or not data.startswith(b'#!/usr/bin/python3'):
            raise RuntimeError('deployer source is unexpected')
        evidence = EVIDENCE_SOURCE.read_bytes()
        if len(evidence) > MAX_BYTES or not evidence.startswith(b'#!/usr/bin/env python3'):
            raise RuntimeError('evidence module is unexpected')
        for name in REQUIRED:
            clean(HELPERS / name)
        if os.path.lexists(TARGET):
            clean(TARGET, executable=True)
        if os.path.lexists(EVIDENCE_TARGET):
            clean(EVIDENCE_TARGET)
        write_atomic(TARGET, data, MODE_FILE)
        if TARGET.read_bytes() != data:
            raise RuntimeError('installed deployer differs from the source')
        write_atomic(EVIDENCE_TARGET, evidence, MODE_MODULE)
        if EVIDENCE_TARGET.read_bytes() != evidence:
            raise RuntimeError('installed evidence module differs from the source')
        for path, body in ((SERVICE, SERVICE_BODY), (TIMER, TIMER_BODY)):
            write_atomic(path, body.encode(), MODE_UNIT)
            if path.read_bytes() != body.encode():
                raise RuntimeError(f'{path} was not written correctly')
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        subprocess.run(['systemctl', 'enable', '--now', TIMER.name], check=True)
        status = subprocess.run(['systemctl', 'is-active', TIMER.name], capture_output=True, text=True)
        print(f'pull deployer installed: {hashlib.sha256(data).hexdigest()} ({len(data)} bytes)')
        print(f'evidence module installed: {hashlib.sha256(evidence).hexdigest()} ({len(evidence)} bytes)')
        print(f'timer: {status.stdout.strip() or "unknown"}')
        print('first run: systemctl start xennic-pull-deploy.service   (or wait for the timer)')
        print('dry run : sudo /usr/local/libexec/xennic-preview/ci-pull-deploy --dry-run')
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f'pull deploy install failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
