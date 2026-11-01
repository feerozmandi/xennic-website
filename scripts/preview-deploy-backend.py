#!/usr/bin/env python3
"""Restricted preview backend. Not wired to SSH or enabled for live deployment.

The privileged operations are fixed, root-owned programs below. They are NOT
installed or implemented by this module. In particular, a real, independently
reviewed backup/restore driver is a prerequisite, not a successful stub.
"""
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import MappingProxyType

sys.dont_write_bytecode = True


def _module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


manifest = _module("preview_manifest_backend", "preview-deploy-manifest.py")
readiness = _module("preview_readiness_backend", "preview-deploy-readiness.py")
locks = _module("preview_locks_backend", "preview-deploy-lock.py")
states = _module("preview_state_backend", "preview-deploy-state.py")
transaction = _module("preview_transaction_backend", "preview-deploy-transaction.py")

# These are code constants, never configuration, request fields or SSH arguments.
HELPER_DIR = Path("/usr/local/libexec/xennic-preview")
PHASES = MappingProxyType({
    "release-check": HELPER_DIR / "release-check",
    "current-check": HELPER_DIR / "current-check",
    "backup-verify": HELPER_DIR / "backup-verify",
    "pull-image": HELPER_DIR / "pull-image",
    "migrate": HELPER_DIR / "migrate",
    "activate": HELPER_DIR / "activate",
    "health": HELPER_DIR / "health",
    "rollback": HELPER_DIR / "rollback",
})
SAFE_ENV = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "LANG": "C"}


class BackendError(RuntimeError):
    pass


def _validated_release(value):
    try:
        return manifest.validate_manifest(json.dumps(value, separators=(",", ":")).encode("ascii"))
    except (manifest.InvalidManifest, ValueError, TypeError, UnicodeError) as exc:
        raise BackendError("invalid preview release") from exc


class FixedRunner:
    """Run only known root-owned helpers, without shell or caller-selected argv."""

    def verify_helpers(self):
        for directory in (Path("/usr"), Path("/usr/local"), Path("/usr/local/libexec"), HELPER_DIR):
            try:
                info = os.lstat(directory)
            except OSError as exc:
                raise BackendError("required preview helper directory is missing") from exc
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                raise BackendError("preview helper directory is unsafe")
        if os.lstat(HELPER_DIR).st_mode & 0o077:
            raise BackendError("preview helper directory is not private")
        executables = (*PHASES.values(), HELPER_DIR / "sftp-transfer")
        modules = tuple(HELPER_DIR / name for name in (
            "preview-deploy-backend.py", "preview-deploy-transaction.py", "preview-deploy-lock.py",
            "preview-deploy-readiness.py", "preview-deploy-state.py", "preview-deploy-manifest.py",
            "preview-release-verifier.py", "preview-internal-health.py", "preview-compose-operations.py",
            "preview-age-backup.py", "preview-backup-operation.py"))
        for path in (*executables, *modules):
            try:
                info = os.lstat(path)
            except OSError as exc:
                raise BackendError("required preview operation is not installed") from exc
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1 or
                    info.st_mode & 0o077 or (path in executables and not info.st_mode & stat.S_IXUSR)):
                raise BackendError("preview operation is unsafe")

    def close_initial(self, release):
        # A fixed operation, not a caller-controlled path or command. It must
        # still run when a failed initial journal write cannot be read.
        release = _validated_release(release)
        self.verify_helpers()
        payload = json.dumps(release, separators=(",", ":"), sort_keys=True).encode("ascii") + b"\ninitial-close\n"
        try:
            result = subprocess.run([str(PHASES["rollback"])], input=payload,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    env=SAFE_ENV, timeout=180, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BackendError("initial app closure failed") from exc
        if result.returncode:
            raise BackendError("initial app closure failed")

    def call(self, phase, release, token=None):
        token_phases = {"release-check", "current-check", "pull-image"}
        if phase not in PHASES or (token is not None and phase not in token_phases):
            raise BackendError("invalid preview operation")
        release = _validated_release(release)
        payload = json.dumps(release, separators=(",", ":"), sort_keys=True).encode("ascii") + b"\n"
        if phase in token_phases:
            if not isinstance(token, bytes) or not token or len(token) > 4096 or any(x < 33 or x > 126 for x in token):
                raise BackendError("GHCR token is missing")
            payload += token + b"\n"
        # Root-owned operations must be rechecked before every invocation.
        self.verify_helpers()
        try:
            result = subprocess.run([str(PHASES[phase])], input=payload,
                                    stdout=subprocess.PIPE if phase == "release-check" else subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, env=SAFE_ENV, check=False)
        except OSError as exc:
            raise BackendError("preview operation failed") from exc
        if result.returncode != 0:
            # The phase name is a fixed constant; never expose helper stderr.
            raise BackendError(f"preview operation failed: {phase}")
        if phase == "release-check":
            try:
                if len(result.stdout) > 1024:
                    raise ValueError
                result_data = json.loads(result.stdout)
            except (ValueError, UnicodeError, TypeError) as exc:
                raise BackendError("preview release verification failed") from exc
            fields = {"initial", "rollback_safe", "verified_commit", "verified_digest", "verified_run_number"}
            if (not isinstance(result_data, dict) or set(result_data) != fields or
                    type(result_data["initial"]) is not bool or type(result_data["rollback_safe"]) is not bool or
                    type(result_data["verified_run_number"]) is not int or
                    result_data["verified_commit"] != release["commit"] or
                    result_data["verified_digest"] != release["digest"] or
                    result_data["verified_run_number"] != release["run_number"]):
                raise BackendError("preview release verification failed")
            return result_data
        return None


class Backend:
    def __init__(self, token, runner=None, journal=None):
        # Injection is for isolated tests only; request payloads never control it.
        self.token = token
        self.runner = runner if runner is not None else FixedRunner()
        self.journal = journal if journal is not None else states.Journal()
        self.previous = None
        self.active_release = None
        self.initial = False

    def lock(self):
        return locks.acquire_lock()

    def read_state(self):
        self.initial = self.journal.absent()
        if self.initial:
            self.previous = None
            return {"version": 1, "last_run": 0, "blocked": False,
                    "current": None, "previous": [], "pending": None}
        state = self.journal.read()
        self.previous = state["current"]
        if self.previous is None and not state["blocked"]:
            raise BackendError("journal without a healthy release requires review")
        return state

    def preflight(self, release):
        readiness.check(registry_token=self.token)
        self.runner.verify_helpers()
        self.active_release = _validated_release(release)
        decision = self.runner.call("release-check", release, self.token)
        if (decision["initial"] != self.initial or
                decision["verified_commit"] != release["commit"] or
                decision["verified_digest"] != release["digest"] or
                decision["verified_run_number"] != release["run_number"]):
            raise BackendError("release verification does not match local state")
        return {"initial": decision["initial"], "rollback_safe": decision["rollback_safe"]}

    def pull_image(self, release): self.runner.call("pull-image", release, self.token)
    def backup_and_verify(self, release): self.runner.call("backup-verify", release)
    def assert_current(self, release): self.runner.call("current-check", release, self.token)
    def mark_inflight(self, release):
        if self.initial:
            # Revalidate both provenance and pristine resources after the pull.
            decision = self.runner.call("release-check", release, self.token)
            if decision["initial"] is not True or decision["rollback_safe"] is not False:
                raise BackendError("initial preflight changed")
            self.journal.begin_initial(release)
        else:
            self.journal.mark_inflight(release)
    def ensure_blocked(self, release):
        if self.initial:
            self.journal.ensure_initial_blocked(release)
        else:
            self.journal.ensure_blocked(release)
    def close_initial(self, release): self.runner.close_initial(release)

    def migrate(self, release): self.runner.call("migrate", release)

    def activate(self, release): self.runner.call("activate", release)
    def verify_health(self, release): self.runner.call("health", release)
    def mark_healthy(self, release): self.journal.mark_healthy(release)

    def rollback_previous(self):
        if self.previous is None:
            raise BackendError("no previous healthy release")
        self.runner.call("rollback", self.previous)

    def verify_previous_health(self):
        if self.previous is None:
            raise BackendError("no previous healthy release")
        self.runner.call("health", self.previous)


def run_checked(raw_manifest, token, backend):
    # Read-only validation before even creating/acquiring the shared lock.
    try:
        manifest.validate_manifest(raw_manifest)
    except manifest.InvalidManifest:
        raise BackendError("invalid preview release; no deployment started") from None
    try:
        readiness.check(registry_token=token)
    except readiness.NotReady as exc:
        raise BackendError(f"preview deployment blocked: {exc}; no deployment started") from None
    try:
        backend.runner.verify_helpers()
    except BackendError:
        raise BackendError("required fixed preview operations are missing or unsafe; no deployment started") from None
    return transaction.deploy(raw_manifest, backend)


def main():
    # No production entry point until helpers, trusted setup and full integration
    # are independently reviewed. The existing SSH receiver remains disabled.
    print("Preview privileged backend is disabled; no server changes made.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
