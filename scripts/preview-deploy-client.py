#!/usr/bin/env python3
"""Send a validated preview manifest and short-lived registry token over pinned SSH.

This client does not provision the server, configure trust, or enable deployment.
The receiving forced-command wrapper must validate all input independently.
"""
import base64
import binascii
import hashlib
import hmac
import importlib.util
import json
import struct
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


def verify_known_host(path, expected):
    # The expected fingerprint must be supplied only after independent validation;
    # a fingerprint merely observed through SSH is not a trust decision.
    if not re.fullmatch(r"SHA256:[A-Za-z0-9+/]{43}", expected):
        raise ClientError("independently confirmed host fingerprint is missing or invalid")
    try:
        raw = Path(path).read_bytes()
        if len(raw) > 1024:
            raise ValueError
        fields = raw.decode("ascii").strip().split()
        if len(fields) != 3 or fields[:2] != [f"[{HOST}]:{PORT}", "ssh-ed25519"]:
            raise ValueError
        blob = base64.b64decode(fields[2], validate=True)
        algorithm = b"ssh-ed25519"
        if (len(blob) != 4 + len(algorithm) + 4 + 32 or
                blob[:4] != struct.pack(">I", len(algorithm)) or
                blob[4:4 + len(algorithm)] != algorithm or
                blob[4 + len(algorithm):8 + len(algorithm)] != struct.pack(">I", 32)):
            raise ValueError
        actual = "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode("ascii").rstrip("=")
    except (OSError, ValueError, UnicodeError, binascii.Error) as exc:
        raise ClientError("known_hosts must contain the exact pinned ED25519 host key") from exc
    if not hmac.compare_digest(actual, expected):
        raise ClientError("known_hosts does not match the independently confirmed fingerprint")


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
    try:
        private_key = Path(key).read_bytes()
        if (len(private_key) > 16384 or
                not private_key.startswith(b"-----BEGIN OPENSSH PRIVATE KEY-----\n") or
                not private_key.rstrip().endswith(b"-----END OPENSSH PRIVATE KEY-----")):
            raise ClientError("SSH deploy identity is missing or invalid")
    except OSError as exc:
        raise ClientError("SSH deploy identity is missing or invalid") from exc
    verify_known_host(known_hosts, env.get("PREVIEW_CONFIRMED_HOST_FINGERPRINT", ""))
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
    except ClientError as exc:
        print(f"Preview deployment blocked: {exc}.", file=sys.stderr)
        return 1
    except (UnicodeError, OSError):
        print("Preview deployment transport failed; no sensitive output is shown.", file=sys.stderr)
        return 1
    if result.returncode:
        print("Preview deployment failed; inspect redacted server-side status.", file=sys.stderr)
        return 1
    print("Preview deploy command completed successfully; verify server-side release status.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
