#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "preview-deploy-manifest.py"
spec = importlib.util.spec_from_file_location("preview_deploy_manifest", SCRIPT)
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)


def valid():
    return {
        "repository": "feerozmandi/xennic-website",
        "commit": "a" * 40,
        "run_number": 123,
        "digest": "sha256:" + "b" * 64,
        "platform": "linux/amd64",
    }


def encode(data):
    return json.dumps(data).encode()


class ManifestTest(unittest.TestCase):
    def test_valid_round_trip(self):
        data = valid()
        self.assertEqual(manifest.validate_manifest(encode(data)), data)
        result = subprocess.run([sys.executable, str(SCRIPT)], input=encode(data), capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), data)

    def test_wrong_types_and_values(self):
        for key, value in [
            ("repository", "other/repository"), ("repository", []),
            ("platform", "linux/arm64"), ("commit", "A" * 40),
            ("commit", "a" * 39), ("commit", None),
            ("digest", "sha256:" + "f" * 63), ("digest", "latest"),
            ("run_number", True), ("run_number", 0),
            ("run_number", -1), ("run_number", "123"),
            ("run_number", 2**63),
        ]:
            with self.subTest(key=key, value=value):
                data = valid()
                data[key] = value
                with self.assertRaises(manifest.InvalidManifest):
                    manifest.validate_manifest(encode(data))

    def test_unknown_missing_and_duplicate_fields(self):
        extra = valid()
        extra["token"] = "must-not-appear"
        missing = valid()
        del missing["platform"]
        duplicate = encode(valid())[:-1] + b', "run_number": 124}'
        for raw in (encode(extra), encode(missing), duplicate):
            with self.subTest(raw=raw):
                with self.assertRaises(manifest.InvalidManifest):
                    manifest.validate_manifest(raw)

    def test_malformed_or_oversized_input_and_no_echo(self):
        for raw in (b"", b"[]", b"\xff", b"{" * 1025,
                    b'{"secret":"must-not-appear"}', b"{} trailing"):
            with self.subTest(raw=raw[:40]):
                result = subprocess.run([sys.executable, str(SCRIPT)], input=raw, capture_output=True)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertNotIn(b"must-not-appear", result.stderr)


if __name__ == "__main__":
    unittest.main()
