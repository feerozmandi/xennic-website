#!/usr/bin/python3 -I
"""Root-only fixed-command receiver for the existing two-line protocol.

It is not an SSH or sudo provisioner. The account and fixed forced command
must be separately restricted; no arguments or shell commands are accepted.
"""
import importlib.util
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location(
    "preview_deploy_manifest", Path(__file__).with_name("preview-deploy-manifest.py")
)
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)
backend_spec = importlib.util.spec_from_file_location(
    "preview_deploy_backend_receiver", Path(__file__).with_name("preview-deploy-backend.py")
)
backend = importlib.util.module_from_spec(backend_spec)
backend_spec.loader.exec_module(backend)

COMMAND = "xennic-preview-deploy"
MAX_TOKEN_BYTES = 4096
MAX_INPUT_BYTES = manifest.MAX_MANIFEST_BYTES + MAX_TOKEN_BYTES + 2


class InvalidRequest(ValueError):
    pass


def parse_request(original_command, raw):
    if original_command != COMMAND:
        raise InvalidRequest("invalid original command")
    if not isinstance(raw, bytes) or len(raw) > MAX_INPUT_BYTES:
        raise InvalidRequest("invalid request size")
    lines = raw.split(b"\n")
    if len(lines) != 3 or lines[2] != b"":
        raise InvalidRequest("invalid request structure")
    raw_manifest, token = lines[:2]
    try:
        data = manifest.validate_manifest(raw_manifest)
    except manifest.InvalidManifest as exc:
        raise InvalidRequest("invalid manifest") from exc
    if not re.fullmatch(rb"[!-~]{1,4096}", token):
        raise InvalidRequest("invalid token")
    return data, token


def dispatch(original_command, raw):
    parse_request(original_command, raw)
    # The backend independently validates the request and calls run_checked;
    # it alone owns the lock, provenance checks, backup, health and rollback.
    return backend.run_request(raw)


def main():
    if os.geteuid() != 0 or len(sys.argv) != 1:
        print("Invalid preview receiver invocation.", file=sys.stderr)
        return 1
    os.umask(0o077)
    try:
        dispatch(os.environ.get("SSH_ORIGINAL_COMMAND", ""), sys.stdin.buffer.read(MAX_INPUT_BYTES + 1))
    except InvalidRequest:
        print("Invalid preview deployment request.", file=sys.stderr)
        return 2
    except (ValueError, RuntimeError, OSError):
        print("Preview deployment blocked or failed; review server state.", file=sys.stderr)
        return 1
    print("Preview deployment completed; verify release status.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
