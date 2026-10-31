#!/usr/bin/env python3
"""Verify retained OAuth lab without exposing values; extract reviewed continuation."""
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import zipfile

OLD_SCRIPT_SHA = 'b03eaf36d5ffcb30589516767d4da75950fffc211cc7d319d1e02b36b5ca2f5e'
BUNDLE_SHA = '63f6f07ae46ed05494d8caff10f84e2b4755fd901bdf30d1c648fcda3e6d760c'
BUNDLE = 'xennic-preview-gate-delivery-2026-10-31-v1.1.2'
MARKER = "step='start app and Caddy on loopback'\n"


def verify(root: Path, original: Path, bundle: Path, continuation: Path, image: str) -> None:
    directory = root.lstat()
    if not stat.S_ISDIR(directory.st_mode) or directory.st_uid != os.getuid() or stat.S_IMODE(directory.st_mode) != 0o700:
        raise ValueError('directory is not private and owned')
    raw = original.read_bytes()
    if hashlib.sha256(raw).hexdigest() != OLD_SCRIPT_SHA:
        raise ValueError('original script mismatch')
    old = raw.decode('utf-8')
    if old.count(MARKER) != 1:
        raise ValueError('unexpected continuation marker')
    match = re.search(r'cat > "\$ROOT/compose.yml" <<EOF\n(.*?)\nEOF\n', old, re.S)
    if not match:
        raise ValueError('compose template not found')
    refs = dict(re.findall(r"^(CADDY|GATE|POSTGRES)='([^']+)'$", old, re.M))
    if set(refs) != {'CADDY', 'GATE', 'POSTGRES'}:
        raise ValueError('image references not found')
    expected = match.group(1) + '\n'
    for key, value in refs.items():
        expected = expected.replace('$' + key, value)
    expected = expected.replace('\\${', '${')
    if (root / 'compose.yml').read_text() != expected:
        raise ValueError('compose differs from original handoff')
    envpath = root / 'lab.env'
    info = envpath.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise ValueError('environment is not private and owned')
    lines = envpath.read_text().splitlines()
    pairs = [line.split('=', 1) for line in lines]
    if any(len(pair) != 2 for pair in pairs):
        raise ValueError('invalid environment')
    values = dict(pairs)
    keys = {'APP_IMAGE', 'LAB_UID', 'LAB_GID', 'DB_PASSWORD', 'DATABASE_URL', 'PAYLOAD_SECRET'}
    if len(lines) != len(keys) or set(values) != keys:
        raise ValueError('unexpected environment fields')
    if values['APP_IMAGE'] != image or not re.fullmatch(r'sha256:[a-f0-9]{64}', image):
        raise ValueError('unexpected app image')
    if values['LAB_UID'] != str(os.getuid()) or values['LAB_GID'] != str(os.getgid()):
        raise ValueError('unexpected lab owner')
    password = values['DB_PASSWORD']
    if not re.fullmatch(r'[a-f0-9]{64}', password):
        raise ValueError('unexpected database password format')
    if values['DATABASE_URL'] != 'postgresql://xennic_lab:' + password + '@postgres:5432/xennic_lab':
        raise ValueError('unexpected database target')
    if not re.fullmatch(r'[A-Za-z0-9_-]{64}', values['PAYLOAD_SECRET']):
        raise ValueError('unexpected payload secret format')
    if hashlib.sha256(bundle.read_bytes()).hexdigest() != BUNDLE_SHA:
        raise ValueError('bundle mismatch')
    with zipfile.ZipFile(bundle) as z:
        for name in ('Caddyfile.payload.lab', 'routes.caddy', 'oauth-gateway.caddy', 'upstream.caddy'):
            if (root / name).read_bytes() != z.read(BUNDLE + '/' + name):
                raise ValueError('Caddy file differs from bundle')
    for name in ('oauth.toml', 'firefox-profile', 'effective.json', 'lab-root.crt'):
        if os.path.lexists(root / name):
            raise ValueError('unexpected file from a later lab step')
    out = continuation.lstat()
    if (not stat.S_ISREG(out.st_mode) or out.st_uid != os.getuid()
            or stat.S_IMODE(out.st_mode) != 0o600 or out.st_size != 0):
        raise ValueError('continuation not a new private file')
    fd = os.open(continuation, os.O_WRONLY | os.O_NOFOLLOW | os.O_TRUNC)
    with os.fdopen(fd, 'w') as f:
        f.write(MARKER + old.split(MARKER, 1)[1])


def main():
    if len(sys.argv) != 6:
        print('STOP: expected retained lab, original script, ZIP, new continuation and image', file=sys.stderr)
        return 1
    try:
        verify(*(Path(value) for value in sys.argv[1:5]), sys.argv[5])
    except (OSError, ValueError, UnicodeError, zipfile.BadZipFile, KeyError):
        print('STOP: retained lab verification failed; no values printed', file=sys.stderr)
        return 1
    print('PASS: original script, private settings, app image, bundle and Caddy files verified')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
