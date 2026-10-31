#!/usr/bin/env python3
"""Run the actual internal health checks against the disposable CI stack only."""
import importlib.util
import os
from pathlib import Path
import tempfile
import sys

sys.dont_write_bytecode = True
if os.environ.get("CI") != "true" or os.environ.get("COMPOSE_PROJECT_NAME") != "xennic-preview-ci":
    raise SystemExit("Refusing: requires the disposable CI preview project")
root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("preview_internal_health", root / "scripts/preview-internal-health.py")
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)
keys = ("PREVIEW_POSTGRES_DB", "PREVIEW_POSTGRES_USER", "PREVIEW_POSTGRES_PASSWORD",
        "PREVIEW_DATABASE_URL", "PREVIEW_PAYLOAD_SECRET", "PREVIEW_ORIGIN", "PREVIEW_PORT")
values = {key: os.environ.get(key, "") for key in keys}
if any(not value or "\n" in value or "\r" in value for value in values.values()):
    raise SystemExit("Missing CI-only preview configuration")
with tempfile.TemporaryDirectory(prefix="preview-health-ci-", dir=os.environ.get("RUNNER_TEMP")) as directory:
    env_file = Path(directory) / "env"
    fd = os.open(env_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for key, value in values.items():
            f.write(f"{key}={value}\n")
    # The production script has fixed paths. This process overrides them only
    # for the disposable runner's existing stack; no service is created here.
    health.COMPOSE = ["/usr/bin/docker", "compose", "--project-name", "xennic-preview-ci",
                      "--env-file", str(env_file), "-f", str(root / "compose.preview.yml")]
    health.check_once()
print("PASS: production internal health checks against disposable CI stack")
