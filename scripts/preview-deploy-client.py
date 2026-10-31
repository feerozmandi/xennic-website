#!/usr/bin/env python3
"""Send a validated preview manifest and short-lived registry token over pinned SSH.

This client does not provision the server, configure trust, or enable deployment.
The receiving forced-command wrapper must validate all input independently.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

_MANIFEST = Path(__file__).with_name("preview-deploy-manifest.py")
spec = importlib.util.spec_from_file_location("preview_deploy_manifest", _MANIFEST)
manifest = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(manifest)

HOST = "185.192.113.199"
PORT = "33878"
USER = "preview-deploy"
REMOTE_COMMAND = "xennic-preview-deploy"


class ClientError(ValueError):
    pass


def prepare(env):
    run_number = env.get("GITHUB_RUN_NUMBER", "")
    if not re.fullmatch(r"[1-9][0-9]{0,18}", run_number):
        raise ClientError("invalid run number")
    data = {
        "repository": env.get("GITHUB_REPOSITORY", ""),
        "commit": env.get("GITHUB_SHA", ""),
        "run_number": int(run_number),
        "digest": env.get("PREVIEW_IMAGE_DIGEST", ""),
        "platform": "linux/amd64",
    }
    raw = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("ascii", "strict")
    try:
        manifest.validate_manifest(raw)
    except manifest.InvalidManifest as exc:
        raise ClientError("invalid manifest") from exc
    token = env.get("PREVIEW_GHCR_TOKEN", "")
    if not re.fullmatch(r"[!-~]{1,4096}", token):
        raise ClientError("invalid registry token")
    key = env.get("PREVIEW_SSH_KEY_FILE", "")
    known_hosts = env.get("PREVIEW_KNOWN_HOSTS_FILE", "")
    for path in (key, known_hosts):
        try:
            info = os.lstat(path)
            if not Path(path).is_absolute() or not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
                raise ClientError("unsafe SSH trust or identity file")
        except (OSError, ValueError) as exc:
            raise ClientError("missing or unsafe SSH trust or identity file") from exc
    command = [
        "/usr/bin/ssh", "-F", "/dev/null", "-T", "-p", PORT,
        "-i", key, "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=yes", "-o", f"UserKnownHostsFile={known_hosts}",
        "-o", "GlobalKnownHostsFile=/dev/null", "-o", "ClearAllForwardings=yes",
        "-o", "ForwardAgent=no", "-o", "ConnectTimeout=30",
        f"{USER}@{HOST}", REMOTE_COMMAND,
    ]
    return command, raw + b"\n" + token.encode("ascii") + b"\n"


def main():
    try:
        command, payload = prepare(os.environ)
        result = subprocess.run(
            command, input=payload, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "LANG": "C"}, check=False,
        )
    except (ClientError, UnicodeError, OSError):
        print("Preview deployment transport failed; no sensitive output is shown.", file=sys.stderr)
        return 1
    if result.returncode:
        print("Preview deployment failed; inspect redacted server-side status.", file=sys.stderr)
        return 1
    print("Preview deploy command completed successfully; verify server-side release status.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
