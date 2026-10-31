#!/usr/bin/env python3
"""Offline synthetic fixtures for resume verification; never uses the owner's data."""
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

path = Path(__file__).resolve().parents[1] / 'scripts' / 'verify-real-oauth-resume.py'
spec = importlib.util.spec_from_file_location('verify_oauth_resume', path)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class ResumeVerificationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.root = base / 'lab'
        self.root.mkdir(mode=0o700)
        self.original = base / 'original.sh'
        old = '''CADDY='caddy:verified'
GATE='gate:verified'
POSTGRES='pg:verified'
cat > "$ROOT/compose.yml" <<EOF
services:
  app:
    image: \\${APP_IMAGE:?required}
  gate: {image: $GATE}
  postgres: {image: $POSTGRES}
  caddy: {image: $CADDY}
EOF
step='start app and Caddy on loopback'
echo continuation
'''
        self.original.write_text(old)
        self.compose = '''services:
  app:
    image: ${APP_IMAGE:?required}
  gate: {image: gate:verified}
  postgres: {image: pg:verified}
  caddy: {image: caddy:verified}
'''
        (self.root / 'compose.yml').write_text(self.compose)
        self.bundle = base / 'bundle.zip'
        with zipfile.ZipFile(self.bundle, 'w') as z:
            for name in ('Caddyfile.payload.lab', 'routes.caddy', 'oauth-gateway.caddy', 'upstream.caddy'):
                value = f'synthetic {name}\n'
                (self.root / name).write_text(value)
                z.writestr(verifier.BUNDLE + '/' + name, value)
        self.image = 'sha256:' + 'a' * 64
        password = 'b' * 64
        self.env = self.root / 'lab.env'
        self.env.write_text(f'APP_IMAGE={self.image}\nLAB_UID={os.getuid()}\nLAB_GID={os.getgid()}\n'
                            f'DB_PASSWORD={password}\nDATABASE_URL=postgresql://xennic_lab:{password}@postgres:5432/xennic_lab\n'
                            f'PAYLOAD_SECRET={"c" * 64}\n')
        self.env.chmod(0o600)
        self.continuation = self.root / 'tail'
        self.continuation.touch(mode=0o600)
        self.patches = [patch.object(verifier, 'OLD_SCRIPT_SHA', hashlib.sha256(old.encode()).hexdigest()),
                        patch.object(verifier, 'BUNDLE_SHA', hashlib.sha256(self.bundle.read_bytes()).hexdigest())]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.temp.cleanup()

    def check(self):
        verifier.verify(self.root, self.original, self.bundle, self.continuation, self.image)

    def test_valid_retained_lab_extracts_only_continuation(self):
        self.check()
        self.assertEqual(self.continuation.read_text(), "step='start app and Caddy on loopback'\necho continuation\n")

    def test_refuses_changed_database_target(self):
        self.env.write_text(self.env.read_text().replace('@postgres:5432/', '@external:5432/'))
        with self.assertRaises(ValueError):
            self.check()
        self.assertEqual(self.continuation.read_text(), '')

    def test_refuses_modified_compose_and_caddy(self):
        (self.root / 'compose.yml').write_text(self.compose + '# changed\n')
        with self.assertRaises(ValueError):
            self.check()
        (self.root / 'compose.yml').write_text(self.compose)
        (self.root / 'routes.caddy').write_text('changed')
        with self.assertRaises(ValueError):
            self.check()

    def test_refuses_existing_oauth_file_and_nonprivate_env(self):
        (self.root / 'oauth.toml').write_text('already exists')
        with self.assertRaises(ValueError):
            self.check()
        (self.root / 'oauth.toml').unlink()
        self.env.chmod(0o644)
        with self.assertRaises(ValueError):
            self.check()

    def test_refuses_wrong_image_or_changed_original(self):
        with self.assertRaises(ValueError):
            verifier.verify(self.root, self.original, self.bundle, self.continuation, 'sha256:' + 'f' * 64)
        self.original.write_text(self.original.read_text() + '# changed\n')
        with self.assertRaises(ValueError):
            self.check()


if __name__ == '__main__':
    unittest.main()
