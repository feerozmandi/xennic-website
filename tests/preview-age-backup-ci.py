#!/usr/bin/env python3
"""Run the shared age bundle implementation against disposable CI DB/media."""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
if os.environ.get('CI') != 'true' or os.environ.get('COMPOSE_PROJECT_NAME') != 'xennic-preview-ci':
    raise SystemExit('Refusing: disposable CI project required')
scratch = Path(sys.argv[1]).resolve()
runner_temp = Path(os.environ['RUNNER_TEMP']).resolve()
if scratch.parent != runner_temp or not scratch.name.startswith('xennic-restore.'):
    raise SystemExit('Refusing: unexpected CI scratch directory')
commit = os.environ.get('GITHUB_SHA', '')
if not re.fullmatch('[0-9a-f]{40}', commit):
    raise SystemExit('Invalid test commit')
spec = importlib.util.spec_from_file_location('age_backup', Path(__file__).resolve().parents[1] / 'scripts/preview-age-backup.py')
age = importlib.util.module_from_spec(spec)
spec.loader.exec_module(age)


def keypair(name):
    identity = scratch / name
    subprocess.run(['/usr/bin/age-keygen', '-o', str(identity)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    identity.chmod(0o600)
    recipient = subprocess.check_output(['/usr/bin/age-keygen', '-y', str(identity)], text=True).strip()
    return identity, recipient

identity, recipient = keypair('test-identity')
wrong_identity, _ = keypair('wrong-identity')
migrations = json.loads((scratch / 'migrations.json').read_text())
expected = age.create_bundle(scratch / 'db.dump', scratch / 'media.tar.gz', scratch / 'backup.age', recipient, commit, migrations)
# A wrong key or modified ciphertext must fail before producing restore files.
for label, file, key in [('wrong-key', scratch / 'backup.age', wrong_identity), ('tampered', scratch / 'tampered.age', identity)]:
    test_dir = scratch / label
    test_dir.mkdir(mode=0o700)
    if label == 'tampered':
        data = bytearray((scratch / 'backup.age').read_bytes())
        data[len(data) // 2] ^= 1
        file.write_bytes(data)
    try:
        age.restore_bundle(file, key, test_dir)
        raise AssertionError('invalid backup was accepted')
    except age.BackupError:
        if list(test_dir.iterdir()): raise AssertionError('failed restore left published plaintext')
result = age.restore_bundle(scratch / 'backup.age', identity, scratch)
if result != expected or not result['migrations'] or not result['media_files']:
    raise AssertionError('missing or changed backup metadata')
print('PASS: age DB/media bundle, migration/file metadata, wrong-key and tamper rejection')
