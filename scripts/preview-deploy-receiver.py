#!/usr/bin/env python3
"""Validate the preview SSH protocol. Deployment is intentionally not enabled.

This is not a provisioner, sudo policy, or a deploy implementation. A future
root-owned forced-command wrapper must still enforce its own trust boundary.
"""
import importlib.util
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location(
    "preview_deploy_manifest", Path(__file__).with_name("preview-deploy-manifest.py")
)
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)
ready_spec = importlib.util.spec_from_file_location(
    "preview_deploy_readiness", Path(__file__).with_name("preview-deploy-readiness.py")
)
readiness = importlib.util.module_from_spec(ready_spec)
ready_spec.loader.exec_module(readiness)

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


def main():
    # This parser is intentionally not wired to sudo or a privileged operation.
    # Do not deploy it as the authorized_keys forced-command in its current form.
    import os
    try:
        _, token = parse_request(os.environ.get("SSH_ORIGINAL_COMMAND", ""), sys.stdin.buffer.read(MAX_INPUT_BYTES + 1))
    except InvalidRequest:
        print("Invalid preview deployment request.", file=sys.stderr)
        return 2
    try:
        readiness.check(registry_token=token)
    except readiness.NotReady as exc:
        print(f"Preview deployment blocked: {exc}.", file=sys.stderr)
        return 1
    print("Preview deployment receiver is not enabled.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
