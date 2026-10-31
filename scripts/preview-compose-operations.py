#!/usr/bin/env python3
"""Fixed preview app replacement operation; no SSH or standalone entry point.

A reviewed root-owned Compose configuration and release verification are
required before a backend can use this. No arbitrary command/path is accepted.
"""
import importlib.util
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("preview_manifest_compose", Path(__file__).with_name("preview-deploy-manifest.py"))
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)

COMPOSE = ["/usr/bin/docker", "compose", "--project-name", "xennic-preview",
           "--env-file", "/srv/xennic-preview/secrets/preview.env",
           "-f", "/srv/xennic-preview/config/compose.yml"]
SAFE_ENV = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "LANG": "C"}


class OperationFailed(RuntimeError):
    pass


def image_reference(release):
    import json
    try:
        checked = manifest.validate_manifest(json.dumps(release, separators=(",", ":")).encode())
    except (manifest.InvalidManifest, ValueError, TypeError) as exc:
        raise OperationFailed("invalid release") from exc
    return f"ghcr.io/{manifest.REPOSITORY}@{checked['digest']}"


def replace_app(release):
    # This operation is for both activation and compatible-image rollback.
    # Preflight, verified backup, migration compatibility and the shared lock
    # are the caller's responsibility; this function is not an entry point.
    environment = dict(SAFE_ENV, PREVIEW_IMAGE=image_reference(release))
    try:
        result = subprocess.run(COMPOSE + ["up", "-d", "--no-deps", "--no-build", "--force-recreate", "--wait", "app"],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                env=environment, check=False)
    except OSError as exc:
        raise OperationFailed("preview app replacement failed") from exc
    if result.returncode:
        raise OperationFailed("preview app replacement failed")
