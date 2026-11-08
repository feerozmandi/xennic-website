#!/usr/bin/env python3
"""Durable fail-closed release journal; callers must hold the shared host lock."""
import importlib.util
import json
import os
from pathlib import Path
import secrets
import stat
import sys

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("preview_manifest", Path(__file__).with_name("preview-deploy-manifest.py"))
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)

STATE_DIR = Path("/srv/xennic-preview/state")
STATE_FILE = "release-state.json"
MAX_BYTES = 16384


class UnsafeState(RuntimeError):
    pass


def _release(value):
    try:
        return manifest.validate_manifest(json.dumps(value, separators=(",", ":")).encode())
    except (manifest.InvalidManifest, TypeError, ValueError) as exc:
        raise UnsafeState("invalid release state") from exc


def _validate(data):
    fields = {"version", "last_run", "blocked", "current", "previous", "pending"}
    if (not isinstance(data, dict) or set(data) not in (fields, fields | {"failure"}) or
            type(data["version"]) is not int or data["version"] != 1):
        raise UnsafeState("invalid release state")
    if "failure" in data and data["failure"] != "initial-deployment-failed":
        raise UnsafeState("invalid failure record")
    if type(data["blocked"]) is not bool or type(data["last_run"]) is not int or data["last_run"] < 0:
        raise UnsafeState("invalid release state")
    if not isinstance(data["previous"], list) or len(data["previous"]) > 2:
        raise UnsafeState("invalid release state")
    for item in [data["current"], *data["previous"], data["pending"]]:
        if item is not None:
            item = _release(item)
            if item["run_number"] > data["last_run"]:
                raise UnsafeState("invalid release sequence")
    if any(item is None for item in data["previous"]):
        raise UnsafeState("invalid release history")
    if (data["blocked"] != (data["pending"] is not None) or
            (data["pending"] is not None and data["pending"]["run_number"] != data["last_run"]) or
            ("failure" in data and (not data["blocked"] or data["current"] is not None or data["previous"]))):
        raise UnsafeState("invalid release state")
    return data


def _unique(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise UnsafeState("duplicate state field")
        obj[key] = value
    return obj


class Journal:
    def __init__(self, directory=STATE_DIR, owner_uid=0):
        self.directory = Path(directory)
        self.owner_uid = owner_uid

    def _open_dir(self):
        if not self.directory.is_absolute():
            raise UnsafeState("invalid state directory")
        try:
            fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        except OSError as exc:
            raise UnsafeState("state directory unavailable") from exc
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != self.owner_uid or info.st_mode & 0o077:
            os.close(fd)
            raise UnsafeState("unsafe state directory")
        return fd

    def absent(self):
        directory = self._open_dir()
        try:
            try:
                os.stat(STATE_FILE, dir_fd=directory, follow_symlinks=False)
                return False
            except FileNotFoundError:
                return True
        finally:
            os.close(directory)

    def begin_initial(self, release):
        # Only the locked backend may call this, after its independent pristine
        # preflight and image pull. A partial write remains invalid and blocks.
        release = _release(release)
        data = _validate({"version": 1, "last_run": release["run_number"], "blocked": True,
                          "current": None, "previous": [], "pending": release})
        raw = json.dumps(data, separators=(",", ":"), sort_keys=True).encode() + b"\n"
        directory = self._open_dir()
        try:
            fd = os.open(STATE_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=directory)
            try:
                with os.fdopen(fd, "wb", closefd=False) as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            finally:
                os.close(fd)
            os.fsync(directory)
        finally:
            os.close(directory)

    def read(self):
        directory = self._open_dir()
        try:
            fd = os.open(STATE_FILE, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_uid != self.owner_uid or info.st_nlink != 1 or info.st_mode & 0o077:
                    raise UnsafeState("unsafe state file")
                with os.fdopen(fd, "rb", closefd=False) as f:
                    raw = f.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise UnsafeState("state file too large")
                try:
                    return _validate(json.loads(raw.decode("utf-8"), object_pairs_hook=_unique))
                except (ValueError, UnicodeError, RecursionError) as exc:
                    raise UnsafeState("invalid state file") from exc
            finally:
                os.close(fd)
        except OSError as exc:
            raise UnsafeState("state file unavailable") from exc
        finally:
            os.close(directory)

    def _write(self, data):
        raw = json.dumps(_validate(data), separators=(",", ":"), sort_keys=True).encode() + b"\n"
        if len(raw) > MAX_BYTES:
            raise UnsafeState("state file too large")
        directory = self._open_dir()
        name = ".release-state-" + secrets.token_hex(12)
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory)
            try:
                with os.fdopen(fd, "wb", closefd=False) as f:
                    f.write(raw)
                    f.flush()
                    os.fsync(f.fileno())
            finally:
                os.close(fd)
            os.replace(name, STATE_FILE, src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
        finally:
            try:
                os.unlink(name, dir_fd=directory)
            except FileNotFoundError:
                pass
            os.close(directory)

    def mark_inflight(self, release):
        release = _release(release)
        state = self.read()
        if state["blocked"] or release["run_number"] <= state["last_run"]:
            raise UnsafeState("release blocked or superseded")
        state.update(blocked=True, last_run=release["run_number"], pending=release)
        self._write(state)

    def ensure_blocked(self, release):
        release = _release(release)
        state = self.read()
        if state["last_run"] != release["run_number"]:
            raise UnsafeState("release sequence changed")
        if state["blocked"] and state["pending"] != release:
            raise UnsafeState("pending release changed")
        if not state["blocked"] and state["current"] != release:
            raise UnsafeState("release state changed")
        state.update(blocked=True, pending=release)
        self._write(state)

    def ensure_initial_blocked(self, release):
        release = _release(release)
        state = self.read()
        if (state["last_run"] != release["run_number"] or state["previous"] or
                state["current"] not in (None, release) or
                state["pending"] not in (None, release)):
            raise UnsafeState("initial release state changed")
        state.update(blocked=True, current=None, pending=release, failure="initial-deployment-failed")
        self._write(state)

    def mark_healthy(self, release):
        release = _release(release)
        state = self.read()
        if not state["blocked"] or state["pending"] != release or "failure" in state:
            raise UnsafeState("release is not pending or requires failure review")
        previous = ([state["current"]] if state["current"] is not None else []) + state["previous"]
        state.update(blocked=False, current=release, previous=previous[:2], pending=None)
        self._write(state)
