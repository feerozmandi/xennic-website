#!/usr/bin/env python3
"""Check internal preview DB and app health. Never a substitute for Gate/TLS checks."""
import re
import subprocess
import sys
import time

COMPOSE = [
    "/usr/bin/docker", "compose", "--project-name", "xennic-preview",
    "--env-file", "/srv/xennic-preview/secrets/preview.env",
    "-f", "/srv/xennic-preview/config/compose.yml",
]
ENV = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "LANG": "C"}
APP_CHECK = (
    "fetch('http://127.0.0.1:3000/health',{signal:AbortSignal.timeout(3000)})"
    ".then(async r=>{const x=await r.json();if(!r.ok||x.status!=='ok')process.exit(1)})"
    ".catch(()=>process.exit(1))"
)
DB_CHECK = 'exec psql -X -w -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -tAc "SELECT 1"'


class Unhealthy(RuntimeError):
    pass


def run(command):
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, env=ENV, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Unhealthy("health command unavailable") from exc
    if result.returncode != 0 or len(result.stdout) > 1024:
        raise Unhealthy("health command failed")
    try:
        return result.stdout.decode("ascii").strip()
    except UnicodeError as exc:
        raise Unhealthy("invalid health output") from exc


def check_once():
    for service in ("postgres", "app"):
        container_id = run(COMPOSE + ["ps", "-q", service])
        if not re.fullmatch(r"[0-9a-f]{12,64}", container_id):
            raise Unhealthy("missing or ambiguous container")
        status = run(["/usr/bin/docker", "inspect", "--format",
                      "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}", container_id])
        if status != "healthy":
            raise Unhealthy("container is not healthy")
    database = run(COMPOSE + ["exec", "-T", "postgres", "sh", "-c", DB_CHECK])
    if database != "1":
        raise Unhealthy("database query failed")
    run(COMPOSE + ["exec", "-T", "app", "node", "-e", APP_CHECK])


def main():
    for attempt in range(12):
        try:
            check_once()
            print("Preview internal database and app health passed; Gate/TLS not checked.")
            return 0
        except Unhealthy:
            if attempt < 11:
                time.sleep(5)
    print("Preview internal health failed; inspect locally with redaction.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
