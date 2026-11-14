#!/usr/bin/python3
"""Single entry point the CI deploy job is allowed to run on the VPS.

Installed as `/usr/local/libexec/xennic-preview/ci-gateway`, owned by root with
mode 0755, and reachable only through a forced command in the deploy user's
`authorized_keys`. It exists so the GitHub workflow can drive the *existing*
guarded release path without an interactive shell and without copying long
command lines around.

Four subcommands, nothing else:

  preflight      read-only report: current release, whether the reviewed
                 migration transition for the candidate exists, whether the
                 candidate image is already present. Never changes anything.
  release-check  the existing read-only phase of the release transaction.
  deploy         the existing privileged backend with the candidate manifest.
  approve        write *one* reviewed migration transition row after proving
                 the row against the live system (migration hash computed from
                 the candidate image, ledger read from the running database),
                 then stop. Deployment stays a separate `deploy` call.

`approve` is deliberately not a bypass: it recomputes the migration tree hash
from the pulled image and refuses when the caller's value differs, and it
refuses to write a row whose `previous_migrations` differ from the ledger that
is actually in the database. A human still has to approve the workflow run that
invokes it, and the repository variable `DEPLOY_AUTOMATION` has to be enabled.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

sys.dont_write_bytecode = True

ROOT = Path('/srv/xennic-preview')
HELPERS = Path(__file__).resolve().parent
BACKEND = HELPERS / 'preview-deploy-backend.py'
TRANSITIONS = ROOT / 'config/compatible-transitions.json'
TOKEN = Path('/root/.xennic-release-token')
MAX_INPUT = 8192
COMMANDS = ('preflight', 'release-check', 'deploy', 'approve')
HEX = re.compile(r'[0-9a-f]{64}')
COMMIT = re.compile(r'[0-9a-f]{40}')
ROW_KEYS = {'from_commit', 'to_commit', 'migration_sha256', 'previous_migrations', 'rollback_safe'}


class Rejected(RuntimeError):
    """A check failed; the message is safe to show in a workflow log."""


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HELPERS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_command(argv):
    """Map argv to (command, extras). Unknown shapes are rejected, not ignored."""
    if len(argv) < 2 or argv[1] not in COMMANDS:
        raise Rejected('unknown ci-gateway command')
    command = argv[1]
    extras = argv[2:]
    if command != 'approve' and extras:
        raise Rejected('unexpected arguments')
    if command == 'approve':
        # <expected migration sha256> <previous migrations JSON array>
        if len(extras) != 2 or not HEX.fullmatch(extras[0]):
            raise Rejected('approve needs a 64-character lowercase hex hash')
        parse_previous_migrations(extras[1])
    return command, extras


def parse_previous_migrations(raw):
    """The list of migration names the reviewer believes is already applied."""
    try:
        names = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise Rejected('previous migrations must be a JSON array') from exc
    if (not isinstance(names, list) or not names or len(names) > 200 or
            any(not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', name) for name in names) or
            len(set(names)) != len(names)):
        raise Rejected('previous migrations must be unique migration names')
    return names


def read_manifest():
    """One JSON object on stdin, bounded and validated by the shared module."""
    manifest = load('ci_gateway_manifest', 'preview-deploy-manifest.py')
    raw = sys.stdin.buffer.readline(manifest.MAX_MANIFEST_BYTES + 2)
    if not raw.endswith(b'\n') or sys.stdin.buffer.read(1):
        raise Rejected('expected exactly one manifest line')
    try:
        return manifest.validate_manifest(raw[:-1])
    except manifest.InvalidManifest as exc:
        raise Rejected('invalid release manifest') from exc


def manifest_line(release):
    return json.dumps(release, separators=(',', ':'), sort_keys=True).encode() + b'\n'


def read_token():
    try:
        info = os.lstat(TOKEN)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
            raise Rejected('release token file is not private')
        data = TOKEN.read_bytes()
    except OSError as exc:
        raise Rejected('release token is unavailable') from exc
    if not re.fullmatch(rb'[!-~]{1,4096}', data):
        raise Rejected('release token is malformed')
    return data


def run_helper(executable, payload, timeout):
    """Run one installed fixed phase; the payload is the exact stdin protocol."""
    path = HELPERS / executable
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise Rejected(f'{executable} is not installed') from exc
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise Rejected(f'{executable} has an unsafe owner or mode')
    completed = subprocess.run([str(path)], input=payload, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=timeout, cwd='/')
    if completed.returncode != 0:
        raise Rejected(f'{executable} failed with exit {completed.returncode}')
    return completed.stdout


def journal():
    state = load('ci_gateway_state', 'preview-deploy-state.py')
    data = state.Journal().read()
    return data


def read_transitions():
    try:
        info = os.lstat(TRANSITIONS)
    except OSError as exc:
        raise Rejected('reviewed transition file is missing') from exc
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
        raise Rejected('reviewed transition file is not private to root')
    try:
        data = json.loads(TRANSITIONS.read_text('utf-8'))
    except (OSError, ValueError, UnicodeError) as exc:
        raise Rejected('reviewed transition file is unreadable') from exc
    validate_store(data)
    return data


def validate_store(data):
    """Exactly the shape the installed guard accepts — no extra fields."""
    if not isinstance(data, dict) or set(data) != {'version', 'transitions'}:
        raise Rejected('reviewed transition file has unexpected fields')
    if data['version'] != 1 or not isinstance(data['transitions'], list) or len(data['transitions']) > 500:
        raise Rejected('reviewed transition file has an unsupported version')
    for item in data['transitions']:
        if not isinstance(item, dict) or set(item) != ROW_KEYS:
            raise Rejected('reviewed transition row has unexpected fields')
        if not COMMIT.fullmatch(item['from_commit']) or not COMMIT.fullmatch(item['to_commit']):
            raise Rejected('reviewed transition row has an invalid commit')
        if not isinstance(item['migration_sha256'], str) or not HEX.fullmatch(item['migration_sha256']):
            raise Rejected('reviewed transition row has an invalid hash')
        if item['rollback_safe'] is not True:
            raise Rejected('reviewed transition row is not rollback safe')
        names = item['previous_migrations']
        if (not isinstance(names, list) or not names or
                any(not isinstance(n, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', n) for n in names) or
                len(set(names)) != len(names)):
            raise Rejected('reviewed transition row has invalid migrations')
    return data


def next_store(data, previous_commit, candidate_commit, migration_sha256, previous_migrations):
    """Append one row; refuse a second row for the same pair or the same target."""
    if any(item['from_commit'] == previous_commit and item['to_commit'] == candidate_commit
           for item in data['transitions']):
        raise Rejected('this transition is already approved')
    if any(item['to_commit'] == candidate_commit for item in data['transitions']):
        raise Rejected('another transition already targets this commit')
    row = {'from_commit': previous_commit, 'to_commit': candidate_commit,
           'migration_sha256': migration_sha256, 'previous_migrations': list(previous_migrations),
           'rollback_safe': True}
    return {'version': 1, 'transitions': list(data['transitions']) + [row]}, row


def write_store(data, run_number):
    """Back up the reviewed file to /root and replace it atomically, root-only."""
    if type(run_number) is not int or run_number < 1:
        raise Rejected('invalid run number for the backup name')
    backup = Path(f'/root/compatible-transitions.before-{run_number}.json')
    if backup.exists() or os.path.lexists(backup):
        raise Rejected('backup for this run already exists; review it by hand')
    payload = (json.dumps(data, separators=(',', ':'), sort_keys=True) + '\n').encode()
    staged = TRANSITIONS.with_name('.compatible-transitions.staged')
    for path in (staged,):
        if os.path.lexists(path):
            raise Rejected('staged file already exists')
    original = TRANSITIONS.read_bytes()
    os.close(os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600))
    backup.write_bytes(original)
    os.chmod(backup, 0o600)
    fd = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(staged, TRANSITIONS)
    finally:
        if os.path.lexists(staged):
            os.unlink(staged)
    os.chmod(TRANSITIONS, 0o600)
    return backup


def preview_report(release):
    data = journal()
    current = data.get('current')
    if current is None:
        raise Rejected('no healthy release is recorded yet')
    transitions = read_transitions()
    approved = any(item['from_commit'] == current['commit'] and item['to_commit'] == release['commit']
                   for item in transitions['transitions'])
    return {'current_run_number': current['run_number'], 'current_commit': current['commit'],
            'candidate_run_number': release['run_number'], 'candidate_commit': release['commit'],
            'transition_approved': approved, 'blocked': bool(data.get('blocked'))}


def live_ledger(release):
    """Read the applied migration names from the running database, read-only."""
    ops = load('ci_gateway_ops', 'release-check')
    snapshot = load('ci_gateway_snapshot', 'preview-backup-operation.py')
    snapshot.ENV = dict(ops.SAFE, PREVIEW_IMAGE=ops.reference(release))
    _app, database, _volume = snapshot.single_app_and_database()
    user, database_name = snapshot.pg_settings(database)
    rows = json.loads(snapshot.sql(
        database, user, database_name,
        "SELECT COALESCE(json_agg(json_build_object('name',name,'batch',batch) ORDER BY name),'[]'::json)::text "
        "FROM website.payload_migrations"))
    if not isinstance(rows, list) or any(not isinstance(row, dict) or set(row) != {'name', 'batch'} for row in rows):
        raise Rejected('database migration ledger is unreadable')
    return sorted(row['name'] for row in rows)


def command_preflight(release):
    print(json.dumps(preview_report(release), separators=(',', ':'), sort_keys=True))


def command_release_check(release):
    output = run_helper('release-check', manifest_line(release) + read_token() + b'\n', timeout=1800)
    sys.stdout.write(output.decode('utf-8', 'replace'))


def command_deploy(release):
    output = run_helper('preview-deploy-backend.py', manifest_line(release) + read_token() + b'\n', timeout=3600)
    sys.stdout.write(output.decode('utf-8', 'replace'))


def command_approve(release, expected_sha256, previous_migrations):
    report = preview_report(release)
    if report['transition_approved']:
        raise Rejected('this transition is already approved; run deploy instead')
    if report['blocked']:
        raise Rejected('the release journal is blocked; clear it before approving')
    # The candidate image has to be local for any of this to mean anything.
    run_helper('pull-image', manifest_line(release), timeout=1800)
    # `preview-fixed-operations.py` is installed under its phase names only, so
    # load the copy that is certainly on the host rather than the source name.
    ops = load('ci_gateway_ops_hash', 'release-check')
    computed = ops.migration_tree_hash(release)
    if computed != expected_sha256:
        raise Rejected(f'migration hash mismatch: image gives {computed}')
    ledger = live_ledger(release)
    if sorted(previous_migrations) != ledger:
        raise Rejected('previous migrations do not match the database ledger')
    store, row = next_store(read_transitions(), report['current_commit'], release['commit'],
                            computed, previous_migrations)
    backup = write_store(store, release['run_number'])
    print(json.dumps({'approved': True, 'backup': str(backup), 'row': row},
                     separators=(',', ':'), sort_keys=True))


def main():
    if os.geteuid() != 0 or len(sys.argv) < 2:
        print('ci-gateway requires root and an explicit command', file=sys.stderr)
        return 1
    os.umask(0o077)
    try:
        command, extras = parse_command(sys.argv)
        release = read_manifest()
        if command == 'preflight':
            command_preflight(release)
        elif command == 'release-check':
            command_release_check(release)
        elif command == 'deploy':
            command_deploy(release)
        else:
            command_approve(release, extras[0], parse_previous_migrations(extras[1]))
    except Rejected as exc:
        print(f'ci-gateway rejected: {exc}', file=sys.stderr)
        return 78
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f'ci-gateway failed: {type(exc).__name__}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
