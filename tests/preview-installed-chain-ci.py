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
previous = fixture['releases']['previous']
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
# Exercise the explicit temporary staging-only local-backup policy on the
# successful release; the second release still exercises the original SFTP.
config_path = ROOT / 'config/backup.json'
sftp_config = json.loads(config_path.read_text())
local_config = {'approved': True, 'transport': 'manual-local', 'environment': 'preview-staging-only',
                'no_real_customer_data': True, 'age_recipient': sftp_config['age_recipient']}
config_path.write_text(json.dumps(local_config)); config_path.chmod(0o600)

# This entire script is executed only by the guarded disposable CI fixture.
# An unlabelled reserved volume must not be mistaken for an empty first install.
subprocess.check_call(['/usr/bin/docker', 'volume', 'create', 'xennic-preview_preview_db'], stdout=subprocess.DEVNULL)
try:
    select('previous')
    try:
        backend.run_checked(json.dumps(previous).encode(), b'synthetic-token', backend.Backend(b'synthetic-token'))
        raise AssertionError('pre-existing volume was accepted without a journal')
    except backend.BackendError:
        pass
    if (ROOT / 'state/release-state.json').exists():
        raise AssertionError('rejected environment created a journal')
finally:
    subprocess.check_call(['/usr/bin/docker', 'volume', 'rm', 'xennic-preview_preview_db'], stdout=subprocess.DEVNULL)

# Fail only after the bad image was activated. The same installed helpers must
# close the app, keep both volumes and data, and record no healthy release.
select('second')
try:
    backend.run_checked(json.dumps(second).encode(), b'synthetic-token', backend.Backend(b'synthetic-token'))
    raise AssertionError('bad initial health was accepted')
except backend.transaction.DeploymentFailed:
    pass
journal = backend.states.Journal().read()
if (not journal['blocked'] or journal['current'] is not None or journal['pending'] != second or
        journal.get('failure') != 'initial-deployment-failed'):
    raise AssertionError('failed initial install did not record a blocked failure')
marker = ROOT / 'state' / f"activation-{second['run_number']}.json"
if not marker.is_file(): raise AssertionError('initial failure did not reach activation')
initial_env = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent',
               'PREVIEW_IMAGE': 'ghcr.io/feerozmandi/xennic-website@' + second['digest']}
compose = ['/usr/bin/docker', 'compose', '-p', 'xennic-preview', '--env-file', str(ROOT / 'secrets/preview.env'),
           '-f', str(ROOT / 'config/compose.yml')]
app = subprocess.check_output(compose + ['ps', '--all', '-q', 'app'], env=initial_env, text=True).strip()
if subprocess.check_output(['/usr/bin/docker', 'inspect', '-f', '{{.State.Running}}', app], text=True).strip() != 'false':
    raise AssertionError('failed initial app was not stopped')
for volume in ('xennic-preview_preview_db', 'xennic-preview_preview_media'):
    subprocess.check_call(['/usr/bin/docker', 'volume', 'inspect', volume], stdout=subprocess.DEVNULL)
# A damaged journal must not prevent the installed fixed closure from stopping
# this exact initial image. This is confined to the disposable CI project.
subprocess.check_call(compose + ['up', '-d', '--no-deps', '--no-build', 'app'], env=initial_env, stdout=subprocess.DEVNULL)
state_path = ROOT / 'state/release-state.json'
state_path.write_text('invalid-ci-journal'); state_path.chmod(0o600)
runner.close_initial(second)
if subprocess.check_output(['/usr/bin/docker', 'inspect', '-f', '{{.State.Running}}', app], text=True).strip() != 'false':
    raise AssertionError('initial closure relied on a readable journal')
state_path.write_text(json.dumps(journal)); state_path.chmod(0o600)
query = "SELECT count(*) FROM website.payload_migrations WHERE name='20261030_163225_baseline'"
count = subprocess.check_output(compose + ['exec', '-T', 'postgres', 'psql', '-U', 'preview_ci', '-d', 'preview_ci', '-tAc', query], env=initial_env, text=True).strip()
if count != '1': raise AssertionError('failed initial database was not preserved')

# Reset only this disposable CI fixture; actual VPS data must never be removed.
subprocess.check_call(compose + ['down', '--volumes', '--remove-orphans'], env=initial_env, stdout=subprocess.DEVNULL)
for directory in (ROOT / 'state', ROOT / 'work'):
    for path in directory.iterdir():
        if not path.is_file() or path.is_symlink(): raise AssertionError('unexpected disposable fixture')
        path.unlink()

# Successful first install performs migration, seed, health, encrypted backup,
# isolated restore, a second health check, then records the real first release.
select('previous')
result = backend.run_checked(json.dumps(previous).encode(), b'synthetic-token', backend.Backend(b'synthetic-token'))
journal = backend.states.Journal().read()
record = json.loads((ROOT / 'state' / f"backup-{previous['run_number']}.json").read_text())
if result != previous or journal['blocked'] or journal['current'] != previous or journal['previous']:
    raise AssertionError('first healthy release was not recorded correctly')
if record.get('remote_path') != 'manual-offsite-pending' or not (ROOT / 'work/backup.age').is_file():
    raise AssertionError('first encrypted local backup not verified')
# Add synthetic upgrade data only after a genuine first release exists.
subprocess.check_call(compose + ['exec', '-T', 'postgres', 'psql', '-U', 'preview_ci', '-d', 'preview_ci', '-v', 'ON_ERROR_STOP=1', '-c',
                                "INSERT INTO shared.customers (name, source) VALUES ('CI snapshot fixture', 'ci-only')"], env=initial_env, stdout=subprocess.DEVNULL)
subprocess.check_call(compose + ['exec', '-T', 'app', 'sh', '-c', 'printf synthetic-media > /app/media/ci-snapshot.txt'], env=initial_env)
print('PASS: installed helper rejected orphan volume; first-install failure preserved data and closed app; first install and local encrypted restore succeeded')

select('first')
first_result = backend.run_checked(json.dumps(first).encode(), b'synthetic-token', backend.Backend(b'synthetic-token'))
if first_result != first:
    raise AssertionError('successful release mismatch')
journal = backend.states.Journal().read()
if journal['blocked'] or journal['current'] != first or run_sql() != '1' or run_media() != 'synthetic-media' or run_migration_check() != 't':
    raise AssertionError('successful release or data mismatch')
local_record = json.loads((ROOT / 'state' / f"backup-{first['run_number']}.json").read_text())
if local_record.get('remote_path') != 'manual-offsite-pending':
    raise AssertionError('local backup must not claim offsite transfer')
config_path.write_text(json.dumps(sftp_config)); config_path.chmod(0o600)
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
