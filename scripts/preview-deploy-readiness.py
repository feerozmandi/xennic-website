#!/usr/bin/env python3
"""Read-only local readiness checks. No SSH, Docker, migrations or deployment."""
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import sys
import tomllib

ROOT = Path("/srv/xennic-preview")
MAX_FILE = 32768


class NotReady(RuntimeError):
    pass


def _read(root, relative, uid, private=True):
    parts = Path(relative).parts
    for directory in (root, root / parts[0]):
        try:
            st = os.lstat(directory)
        except OSError as exc:
            raise NotReady("staging configuration directory missing") from exc
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != uid or st.st_mode & 0o022:
            raise NotReady("staging configuration directory is unsafe")
    try:
        fd = os.open(root / relative, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            st = os.fstat(fd)
            if (not stat.S_ISREG(st.st_mode) or st.st_uid != uid or st.st_nlink != 1 or
                    st.st_mode & (0o077 if private else 0o022)):
                raise NotReady("staging configuration file permissions are unsafe")
            with os.fdopen(fd, "rb", closefd=False) as f:
                contents = f.read(MAX_FILE + 1)
        finally:
            os.close(fd)
    except OSError as exc:
        raise NotReady("required staging configuration or secret is missing") from exc
    if not contents or len(contents) > MAX_FILE:
        raise NotReady("required staging configuration or secret is empty or too large")
    return contents


def _env(raw):
    result = {}
    try:
        for line in raw.decode("utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if not sep or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or key in result:
                raise ValueError
            result[key] = value.strip()
    except (UnicodeError, ValueError) as exc:
        raise NotReady("staging environment is invalid") from exc
    return result


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise NotReady("duplicate backup configuration field")
        result[key] = value
    return result


def backup_config(root=ROOT, owner_uid=0):
    try:
        backup_raw = _read(Path(root), "config/backup.json", owner_uid)
        backup = json.loads(backup_raw, object_pairs_hook=_object_pairs)
    except (NotReady, ValueError, UnicodeError) as exc:
        raise NotReady("backup configuration is missing or invalid") from exc
    keys = {"approved", "transport", "host", "port", "user", "remote_directory", "age_recipient"}
    if (not isinstance(backup, dict) or set(backup) != keys or backup.get("approved") is not True or
            backup.get("transport") != "sftp" or
            not isinstance(backup.get("host"), str) or
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}", backup["host"]) or
            backup["host"].lower() in ("localhost", "127.0.0.1", "185.192.113.85", "185.192.113.199") or
            type(backup.get("port")) is not int or not 1 <= backup["port"] <= 65535 or
            not isinstance(backup.get("user"), str) or not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", backup["user"]) or
            not isinstance(backup.get("remote_directory"), str) or
            not re.fullmatch(r"/[A-Za-z0-9_./-]{1,240}", backup["remote_directory"]) or
            ".." in backup["remote_directory"].split("/") or
            not isinstance(backup.get("age_recipient"), str) or
            not re.fullmatch(r"age1[023456789acdefghjklmnpqrstuvwxyz]{58}", backup["age_recipient"])):
        raise NotReady("approved off-site encrypted backup configuration is missing or invalid")
    try:
        address = ipaddress.ip_address(backup["host"])
    except ValueError:
        address = None
    if address is not None and (address.is_loopback or address.is_unspecified or address.is_link_local):
        raise NotReady("backup host must not be local or unspecified")
    for path in ("secrets/backup-ssh-key", "secrets/backup-identity", "config/backup-known-hosts"):
        try:
            _read(Path(root), path, owner_uid)
        except NotReady as exc:
            raise NotReady("backup credentials or pinned backup host key are missing or unsafe") from exc
    return backup


def check(root=ROOT, owner_uid=0, registry_token=b""):
    root = Path(root)
    if not root.is_absolute():
        raise NotReady("staging root must be absolute")
    try:
        fingerprint = _read(root, "config/verified-host-fingerprint", owner_uid).decode("ascii", errors="replace").strip()
    except NotReady as exc:
        raise NotReady("independently verified SSH host fingerprint is missing or unsafe") from exc
    if not re.fullmatch(r"SHA256:[A-Za-z0-9+/]{43}", fingerprint):
        raise NotReady("independently verified SSH host fingerprint is missing")
    if not isinstance(registry_token, bytes) or not re.fullmatch(rb"[!-~]{1,4096}", registry_token):
        raise NotReady("short-lived GHCR token is missing")
    env = _env(_read(root, "secrets/preview.env", owner_uid))
    for key in ("PREVIEW_POSTGRES_USER", "PREVIEW_POSTGRES_DB", "PREVIEW_POSTGRES_PASSWORD", "PREVIEW_DATABASE_URL", "PREVIEW_PAYLOAD_SECRET"):
        if env.get(key, "") in ("", '""', "''"):
            raise NotReady("required preview secret or database setting is missing")
    try:
        oauth = tomllib.loads(_read(root, "secrets/oauth2-proxy.cfg", owner_uid).decode("utf-8"))
    except (UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise NotReady("OAuth configuration is invalid") from exc
    if any(not isinstance(oauth.get(key), str) or not oauth[key] for key in ("client_id", "client_secret", "cookie_secret")):
        raise NotReady("required OAuth secret or client ID is missing")
    backup_config(root, owner_uid)
    # Existence is not proof: the backend must verify endpoint identity, off-site
    # allocation, write/read, encryption and an isolated restore before mutation.


def main():
    token = sys.stdin.buffer.read(4097).rstrip(b"\n")
    try:
        check(registry_token=token)
    except NotReady as exc:
        print(f"Preview deployment blocked: {exc}.", file=sys.stderr)
        return 1
    print("Local configuration checks passed; operational backup and host trust remain to be verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
