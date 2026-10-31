#!/usr/bin/env python3
"""Fail-closed release transaction logic. This module does not deploy by itself.

A future root-owned backend must implement the operations below, use the fixed
host lock, and independently verify source, artifact, configuration and backup.
Never wire this module into an SSH receiver until that backend is reviewed.
"""
import importlib.util
from pathlib import Path
import sys

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location(
    "preview_deploy_manifest", Path(__file__).with_name("preview-deploy-manifest.py")
)
manifest_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest_module)


class DeploymentRejected(RuntimeError):
    pass


class DeploymentFailed(RuntimeError):
    pass


def deploy(raw_manifest, ops):
    """Run one transaction while the trusted backend holds the shared host lock.

    Required backend operations: lock(), read_state(), preflight(manifest),
    pull_image(manifest), backup_and_verify(manifest), assert_current(manifest), mark_inflight(manifest),
    migrate(manifest), activate(manifest), verify_health(manifest), mark_healthy(manifest),
    ensure_blocked(manifest), rollback_previous(), verify_previous_health(). preflight returns a dict with
    boolean initial and rollback_safe fields, based on trusted server state.
    mark_inflight must durably block later releases before migration begins;
    mark_healthy must atomically record success and clear that block. A backend
    must never use values supplied by the request to decide rollback safety.
    """
    try:
        release = manifest_module.validate_manifest(raw_manifest)
    except manifest_module.InvalidManifest as exc:
        raise DeploymentRejected("invalid release manifest") from exc
    with ops.lock():
        state = ops.read_state()
        if (not isinstance(state, dict) or type(state.get("blocked")) is not bool or
                type(state.get("last_run")) is not int or state["last_run"] < 0):
            raise DeploymentRejected("invalid release state")
        if state["blocked"] or release["run_number"] <= state["last_run"]:
            raise DeploymentRejected("release blocked or superseded")
        # These are trusted backend checks, not claims from the incoming manifest.
        readiness = ops.preflight(release)
        if (not isinstance(readiness, dict) or set(readiness) != {"initial", "rollback_safe"} or
                type(readiness["initial"]) is not bool or type(readiness["rollback_safe"]) is not bool or
                (not readiness["initial"] and not readiness["rollback_safe"]) or
                (readiness["initial"] and readiness["rollback_safe"])):
            raise DeploymentRejected("release or rollback compatibility not established")
        rollback_safe = readiness["rollback_safe"]
        # Pull while the previous app is still running. A network failure must
        # neither enter maintenance nor change the journal.
        ops.assert_current(release)
        ops.pull_image(release)
        # Dev can advance during a lengthy pull; check again before blocking.
        ops.assert_current(release)
        # Block durably before maintenance can stop app writers.
        ops.mark_inflight(release)
        switch_attempted = False
        try:
            ops.backup_and_verify(release)
            ops.assert_current(release)
            ops.migrate(release)
            # An old run must not switch traffic if dev advanced during migration.
            # The durable block stays in place if this check fails.
            ops.assert_current(release)
            # A failed activation can still have partially switched the service.
            switch_attempted = True
            ops.activate(release)
            ops.verify_health(release)
            ops.mark_healthy(release)
        except Exception:
            # A failed durable success write can have partially committed. Ensure
            # a durable blocked state before any rollback or subsequent release.
            try:
                ops.ensure_blocked(release)
            except Exception:
                raise DeploymentFailed("release state uncertain; stop and review") from None
            rollback_ok = False
            if switch_attempted and rollback_safe:
                try:
                    ops.rollback_previous()
                    ops.verify_previous_health()
                    rollback_ok = True
                except Exception:
                    pass
            # The durable inflight block remains; a later run must not proceed
            # until an operator has reviewed and resolved the failure.
            if rollback_ok:
                raise DeploymentFailed("release failed; previous image restored, review required") from None
            raise DeploymentFailed("release failed; blocked, review required") from None
        return release
