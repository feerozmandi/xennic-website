#!/usr/bin/env python3
"""Validate the non-secret release manifest; does not perform a deployment."""
import json
import re
import sys

REPOSITORY = "feerozmandi/xennic-website"
FIELDS = frozenset({"repository", "commit", "run_number", "digest", "platform"})
MAX_MANIFEST_BYTES = 1024


class InvalidManifest(ValueError):
    """Reject malformed or out-of-scope input without printing its contents."""


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise InvalidManifest("duplicate field")
        obj[key] = value
    return obj


def validate_manifest(raw):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_MANIFEST_BYTES:
        raise InvalidManifest("invalid input size")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise InvalidManifest("invalid JSON") from exc
    if not isinstance(data, dict) or set(data) != FIELDS:
        raise InvalidManifest("unexpected fields")
    if data["repository"] != REPOSITORY or data["platform"] != "linux/amd64":
        raise InvalidManifest("repository or platform not allowed")
    if not isinstance(data["commit"], str) or not re.fullmatch(r"[0-9a-f]{40}", data["commit"]):
        raise InvalidManifest("invalid commit")
    if not isinstance(data["digest"], str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", data["digest"]):
        raise InvalidManifest("invalid digest")
    if type(data["run_number"]) is not int or not 1 <= data["run_number"] <= 2**63 - 1:
        raise InvalidManifest("invalid run number")
    return data


def main():
    try:
        data = validate_manifest(sys.stdin.buffer.read(MAX_MANIFEST_BYTES + 1))
    except InvalidManifest:
        print("Invalid preview release manifest", file=sys.stderr)
        return 2
    print(json.dumps(data, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
