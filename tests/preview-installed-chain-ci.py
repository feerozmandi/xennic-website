#!/usr/bin/python3
"""Disposable CI: exact installed backend/helpers; GitHub/GHCR endpoints are fixtures."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path('/srv/xennic-preview')
LIBEXEC = Path('/usr/local/libexec/xennic-preview')
fixture_path = ROOT / 'config/ci-github-fixture.json'
spec = importlib.util.spec_from_file_location('installed_backend_ci', LIBEXEC / 'preview-deploy-backend.py')
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)

fixture = json.loads(fixture_path.read_text())
first = fixture['releases']['first']
second = fixture['releases']['second']

def select(name):
    fixture['current'] = name
    fixture_path.write_text(json.dumps(fixture))
    fixture_path.chmod(0o600)


def run_sql():
    # Fixed project and synthetic fixture only; no SQL comes from a request.
    env = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'PREVIEW_IMAGE': 'ghcr.io/feerozmandi/xennic-website@' + first['digest']}
    command = ['/usr/bin/docker', 'compose', '-p', 'xennic-preview', '--env-file', str(ROOT / 'secrets/preview.env'),
               '-f', str(ROOT / 'config/compose.yml'), 'exec', '-T', 'postgres', 'psql', '-U', 'preview_ci',
               '-d', 'preview_ci', '-tAc', "SELECT count(*) FROM shared.customers WHERE name='CI snapshot fixture'"]
    return subprocess.check_output(command, env=env, text=True).strip()


def run_migration_check():
    env = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'PREVIEW_IMAGE': 'ghcr.io/feerozmandi/xennic-website@' + first['digest']}
    query = "SELECT to_regclass('website.ci_compatibility_probe') IS NOT NULL AND EXISTS (SELECT 1 FROM website.payload_migrations WHERE name='20261031_000000_ci_additive' AND batch >= 0)"
    command = ['/usr/bin/docker', 'compose', '-p', 'xennic-preview', '--env-file', str(ROOT / 'secrets/preview.env'),
               '-f', str(ROOT / 'config/compose.yml'), 'exec', '-T', 'postgres', 'psql', '-U', 'preview_ci',
               '-d', 'preview_ci', '-tAc', query]
    return subprocess.check_output(command, env=env, text=True).strip()


def run_media():
    env = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'PREVIEW_IMAGE': 'ghcr.io/feerozmandi/xennic-website@' + first['digest']}
    command = ['/usr/bin/docker', 'compose', '-p', 'xennic-preview', '--env-file', str(ROOT / 'secrets/preview.env'),
               '-f', str(ROOT / 'config/compose.yml'), 'exec', '-T', 'app', 'cat', '/app/media/ci-snapshot.txt']
    return subprocess.check_output(command, env=env, text=True)


# The actual root-owned FixedRunner checks all installed helper files. No
# injection or test adapter is supplied to Backend.
runner = backend.FixedRunner()
runner.verify_helpers()
select('first')
first_result = backend.run_checked(json.dumps(first).encode(), b'synthetic-token', backend.Backend(b'synthetic-token'))
if first_result != first:
    raise AssertionError('successful release mismatch')
journal = backend.states.Journal().read()
if journal['blocked'] or journal['current'] != first or run_sql() != '1' or run_media() != 'synthetic-media' or run_migration_check() != 't':
    raise AssertionError('successful release or data mismatch')
select('second')
try:
    backend.run_checked(json.dumps(second).encode(), b'synthetic-token', backend.Backend(b'synthetic-token'))
    raise AssertionError('deliberately bad post-activation health must fail')
except backend.transaction.DeploymentFailed as exc:
    if str(exc) != 'release failed; previous image restored, review required': raise
journal = backend.states.Journal().read()
marker = ROOT / 'state' / f"activation-{second['run_number']}.json"
if not marker.is_file() or json.loads(marker.read_text()) != second:
    raise AssertionError('failure was not after a verified activation')
if not journal['blocked'] or journal['current'] != first or journal['pending'] != second or run_sql() != '1' or run_media() != 'synthetic-media' or run_migration_check() != 't':
    raise AssertionError('rollback journal or data mismatch')
print('PASS: installed controller and helpers: success, post-activation health failure, compatible rollback, synthetic data preserved')
