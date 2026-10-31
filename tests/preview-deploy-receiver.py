#!/usr/bin/env python3
import base64
import hashlib
import importlib.util
import struct
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


receiver = load("preview_receiver", ROOT / "scripts/preview-deploy-receiver.py")
client = load("preview_client", ROOT / "scripts/preview-deploy-client.py")


def data():
    return {
        "repository": "feerozmandi/xennic-website", "commit": "a" * 40,
        "run_number": 42, "digest": "sha256:" + "b" * 64,
        "platform": "linux/amd64",
    }


def request(d=None, token=b"synthetic-only-token"):
    return json.dumps(d or data()).encode() + b"\n" + token + b"\n"


class ReceiverTest(unittest.TestCase):
    def test_roundtrip_with_real_client_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            key, hosts = Path(directory) / "key", Path(directory) / "known_hosts"
            key.touch(mode=0o600)
            hosts.touch(mode=0o600)
            algorithm = b"ssh-ed25519"
            blob = struct.pack(">I", len(algorithm)) + algorithm + struct.pack(">I", 32) + b"x" * 32
            fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")
            hosts.write_text(f"[{client.HOST}]:{client.PORT} ssh-ed25519 {base64.b64encode(blob).decode()}\n")
            env = {
                "GITHUB_REPOSITORY": data()["repository"], "GITHUB_SHA": data()["commit"],
                "GITHUB_RUN_NUMBER": str(data()["run_number"]), "PREVIEW_IMAGE_DIGEST": data()["digest"],
                "PREVIEW_GHCR_TOKEN": "synthetic-only-token", "PREVIEW_SSH_KEY_FILE": str(key),
                "PREVIEW_KNOWN_HOSTS_FILE": str(hosts), "PREVIEW_CONFIRMED_HOST_FINGERPRINT": fingerprint,
            }
            command, payload = client.prepare(env)
            parsed, token = receiver.parse_request(command[-1], payload)
            self.assertEqual(parsed, data())
            self.assertEqual(token, b"synthetic-only-token")

    def test_wrong_command_and_malformed_requests_fail_closed(self):
        bad_inputs = [
            ("", request()), ("xennic-preview-deploy;id", request()),
            (receiver.COMMAND, b""), (receiver.COMMAND, request()[:-1]),
            (receiver.COMMAND, request() + b"extra\n"),
            (receiver.COMMAND, request(token=b"")),
            (receiver.COMMAND, request(token=b"secret\ninjected")),
            (receiver.COMMAND, request(token=b"secret\r")),
            (receiver.COMMAND, request(token=b"x" * 4097)),
            (receiver.COMMAND, b"x" * (receiver.MAX_INPUT_BYTES + 1)),
            (receiver.COMMAND, request(dict(data(), platform="linux/arm64"))),
            (receiver.COMMAND, request(dict(data(), repository="other/repository"))),
        ]
        for command, raw in bad_inputs:
            with self.subTest(command=command, length=len(raw)):
                with self.assertRaises(receiver.InvalidRequest):
                    receiver.parse_request(command, raw)

    def test_receiver_cannot_deploy_and_does_not_echo_token(self):
        env = dict(os.environ, SSH_ORIGINAL_COMMAND=receiver.COMMAND)
        script = str(ROOT / "scripts/preview-deploy-receiver.py")
        proc = subprocess.run([sys.executable, script], input=request(), env=env, capture_output=True)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, b"")
        self.assertNotIn(b"synthetic-only-token", proc.stderr)
        self.assertIn(b"not enabled", proc.stderr)
        proc = subprocess.run([sys.executable, script], input=request(token=b"bad token"), env=env, capture_output=True)
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn(b"bad token", proc.stderr)


if __name__ == "__main__":
    unittest.main()
