#!/usr/bin/python3
"""Root-only pull of the approved immutable GHCR reference; no deploy or SSH.

Only a validated release and short-lived token are read from stdin. Runtime
credentials are confined to a private temporary directory under /run and never
placed in argv or environment. Release provenance must be checked separately.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('pull_manifest', Path(__file__).with_name('preview-deploy-manifest.py'))
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)

DOCKER = '/usr/bin/docker'
RUNTIME = Path('/run/xennic-preview')


class PullFailed(RuntimeError):
    pass


def private_runtime():
    info = os.lstat('/run')
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise PullFailed('unsafe runtime parent')
    try:
        RUNTIME.mkdir(mode=0o700)
    except FileExistsError:
        pass
    info = os.lstat(RUNTIME)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
        raise PullFailed('unsafe runtime directory')


def run(args, env, data=None, capture=False):
    try:
        result = subprocess.run(args, input=data, stdin=subprocess.DEVNULL if data is None else None,
                                stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, env=env, timeout=600, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PullFailed('registry operation unavailable') from exc
    if result.returncode != 0:
        raise PullFailed('registry operation failed')
    if capture:
        if len(result.stdout) > 65536:
            raise PullFailed('invalid image inspection')
        return result.stdout
    return b''


def pull(raw, token):
    if os.geteuid() != 0:
        raise PullFailed('root required')
    release = manifest.validate_manifest(raw)
    if not isinstance(token, bytes) or not re.fullmatch(rb'[!-~]{1,4096}', token):
        raise PullFailed('invalid registry token')
    reference = 'ghcr.io/' + manifest.REPOSITORY + '@' + release['digest']
    private_runtime()
    with tempfile.TemporaryDirectory(prefix='ghcr-', dir=RUNTIME) as temporary:
        env = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'LANG': 'C', 'DOCKER_CONFIG': temporary}
        run([DOCKER, 'login', 'ghcr.io', '--username', 'feerozmandi', '--password-stdin'], env, token + b'\n')
        run([DOCKER, 'pull', '--platform', 'linux/amd64', reference], env)
        try:
            details = json.loads(run([DOCKER, 'image', 'inspect', reference], env, capture=True))
            if not isinstance(details, list) or len(details) != 1:
                raise PullFailed('invalid image inspection')
            image = details[0]
            image_id = image.get('Id', '')
            if (image.get('Os') != 'linux' or image.get('Architecture') != 'amd64' or
                    not re.fullmatch(r'sha256:[0-9a-f]{64}', image_id) or
                    reference not in (image.get('RepoDigests') or [])):
                raise PullFailed('pulled image identity or architecture mismatch')
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise PullFailed('invalid image inspection') from exc
    return image_id


def main():
    if len(sys.argv) != 1:
        print('Invalid fixed image operation', file=sys.stderr)
        return 1
    os.umask(0o077)
    try:
        raw = sys.stdin.buffer.readline(manifest.MAX_MANIFEST_BYTES + 2)
        token = sys.stdin.buffer.readline(4098)
        if not raw.endswith(b'\n') or not token.endswith(b'\n') or sys.stdin.buffer.read(1):
            raise PullFailed('invalid image request')
        pull(raw[:-1], token[:-1])
    except (OSError, ValueError, RuntimeError):
        print('GHCR pull or immutable image verification failed; no maintenance started', file=sys.stderr)
        return 1
    print('Approved GHCR digest pulled for linux/amd64; provenance must also be verified')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
