#!/usr/bin/python3
"""Pull deployment: the host asks GitHub what to run, GitHub never dials in.

The runner in GitHub cannot open a TCP connection to this host (both the deploy
port and port 22 are filtered for its address), so the push model is replaced by
a pull model with the same guard:

    systemd timer (every 5 minutes)
        -> read the newest successful `dev` run and its own release artifact
        -> already running?                       stop, say nothing
        -> same release as the journal?           stop, say nothing
        -> reviewed transition missing?           record it, notify once, stop
        -> otherwise                              run the existing privileged
                                                  backend, exactly as a human
                                                  would, then check a public page

Nothing here decides that a migration is safe: the transition file is still the
only door, and the backend still re-checks it. This program only decides *when*
to knock, and reports what happened.

Run by systemd as root, one shot, no arguments. `--dry-run` prints the decision
without touching anything (still needs the token to read GitHub).
"""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.dont_write_bytecode = True

ROOT = Path('/srv/xennic-preview')
HELPERS = Path(__file__).resolve().parent
TOKEN = Path('/root/.xennic-release-token')
BACKEND = HELPERS / 'preview-deploy-backend.py'
# The deployment lock is the one the backend takes for the whole transaction:
# it is the only writer of the journal, so every deployment, whether a person
# or the timer starts it, is serialised behind it. This program must not hold
# that same lock while the backend runs. A second, independent open of one
# lock file blocks until the first is released, so the backend would wait for
# a lock its own caller already held, and the deploy would sit there until the
# timeout below expired. That is exactly what the host did: every run took
# 3600 seconds, ended with "deployment backend did not finish", and left the
# journal untouched because the backend never got past its first statement.
#
# This program therefore takes its own lock, which only guards "one pull
# deploy at a time", and leaves the deployment lock to the backend alone.
PULL_LOCK = Path('/run/lock/xennic-preview-pull-deploy.lock')
DEPLOY_LOCK = Path('/run/lock/xennic-preview-deploy.lock')
TRANSITIONS = ROOT / 'config/compatible-transitions.json'
RECORD = ROOT / 'state/pull-deploy.json'
NOTIFY = ROOT / 'secrets/notify.json'
# The public site is behind the gate for every path that is not in the route
# allowlist, and /health is deliberately not on that list: an anonymous GET of
# /health is answered by the gate's sign-in redirect, never by the application.
# The post-deployment check therefore asks for a path that IS public and that
# the application itself serves, so a 200 proves the edge reaches the image
# that was just activated. See config/routes.caddy for the allowlist.
PUBLIC_CHECK_URL = 'https://xennic.ir/robots.txt'
SAFE_ENV = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'LANG': 'C'}
# The interpreter that runs this program. The installer pins the shebang of
# the deployed file to /usr/bin/python3, so this is that interpreter on the
# host, and the backend is started with it rather than executed directly.
INTERPRETER = sys.executable or '/usr/bin/python3'
MAX_RECORD = 8192
MAX_NOTIFY = 4096
RESULTS = ('up-to-date', 'waiting-approval', 'deployed', 'failed', 'in-flight', 'no-journal', 'dry-run')
# The phase marker the backend writes on the host. These names are fixed
# constants, so a marker carrying anything else is ignored rather than shown.
PHASE_MARKER = Path('/run/xennic-preview/deploy-phase.json')
KNOWN_PHASES = ('release-check', 'current-check', 'backup-verify', 'pull-image', 'migrate',
                'activate', 'health', 'rollback', 'complete', 'failed')
# A reason that reaches a log and a chat message has to be safe to print: only
# the verifier's own fixed strings are shown, and nothing that could quote a
# URL, a header or a token.
SAFE_MESSAGE = re.compile(r"[A-Za-z0-9 .,'\-]{1,200}")


class PullFailed(RuntimeError):
    """A step failed; the message is safe for a log or a notification."""


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HELPERS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def private_file(path, maximum):
    """Root-owned, not writable by others, not a symlink, not oversized."""
    try:
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
            raise PullFailed(f'{path.name} is not private to root')
        data = path.read_bytes()
    except OSError as exc:
        raise PullFailed(f'{path.name} is unavailable') from exc
    if len(data) > maximum:
        raise PullFailed(f'{path.name} is too large')
    return data


def read_token():
    data = private_file(TOKEN, 4096).strip()
    if not re.fullmatch(rb'[!-~]{1,4096}', data):
        raise PullFailed('release token is malformed')
    return data


def reason(exc):
    """The verifier's own words for a failure, or nothing.

    `Unverified` is raised with fixed strings that were written for an
    operator, so they are safe to print and they say what actually went wrong.
    Any other exception may quote a URL, a header or a body, so it is reduced
    to its type and the stage it happened in is added by the caller.
    """
    if type(exc).__name__ == 'Unverified' and isinstance(exc, RuntimeError):
        text = str(exc).strip()
        if SAFE_MESSAGE.fullmatch(text):
            return text
    return ''


def call(label, action):
    """Run one GitHub call and keep the reason when it fails.

    The verifier hides the underlying HTTP status behind one message; the
    stage is added here so the log says *which* request failed, and the
    verifier's message is carried through unchanged.
    """
    try:
        return action()
    except PullFailed:
        raise
    except Exception as exc:  # noqa: BLE001 - the reason is re-raised as PullFailed
        detail = reason(exc)
        raise PullFailed(f'{label}: {detail}' if detail else label) from exc


def newest_run(verifier, token):
    """The newest successful push run on dev, and the commit it built."""
    head = call('cannot read the dev head', lambda: verifier.get_json('/commits/dev', token))
    if not isinstance(head, dict) or not re.fullmatch(r'[0-9a-f]{40}', str(head.get('sha', ''))):
        raise PullFailed('cannot read the dev head')
    sha = head['sha']
    listing = call('cannot list workflow runs',
                   lambda: verifier.get_json('/actions/workflows/ci.yml/runs?branch=dev&event=push&per_page=30', token))
    if not isinstance(listing, dict) or not isinstance(listing.get('workflow_runs'), list):
        raise PullFailed('cannot list workflow runs')
    candidates = [run for run in listing['workflow_runs']
                  if isinstance(run, dict) and run.get('head_sha') == sha and run.get('head_branch') == 'dev'
                  and run.get('event') == 'push' and run.get('status') == 'completed'
                  and run.get('conclusion') == 'success' and type(run.get('run_number')) is int]
    if not candidates:
        raise PullFailed('no successful run for the current dev head')
    return max(candidates, key=lambda run: run['run_number'])


def release_from_run(verifier, evidence, token, run):
    """Read that run's own evidence artifact and bind it to the run."""
    run_id, attempt, number = run.get('id'), run.get('run_attempt'), run['run_number']
    if type(run_id) is not int or type(attempt) is not int:
        raise PullFailed('workflow run identity is incomplete')
    artifacts = call('cannot list run artifacts',
                     lambda: verifier.get_json(f'/actions/runs/{run_id}/artifacts?per_page=100', token))
    if not isinstance(artifacts, dict) or not isinstance(artifacts.get('artifacts'), list):
        raise PullFailed('cannot list run artifacts')
    wanted = f'xennic-preview-release-{attempt}'
    matches = [a for a in artifacts['artifacts'] if isinstance(a, dict) and a.get('name') == wanted
               and a.get('expired') is False and type(a.get('id')) is int]
    if len(matches) != 1:
        raise PullFailed('release evidence artifact is missing')
    raw = call('cannot read the release evidence artifact',
               lambda: verifier.request(f'{verifier.BASE}/actions/artifacts/{matches[0]["id"]}/zip', token,
                                        verifier.MAX_ZIP))
    import io
    import zipfile
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            files = archive.infolist()
            if len(files) != 1 or files[0].filename != 'xennic-preview-release.json' or files[0].is_dir():
                raise PullFailed('invalid release artifact')
            parsed = json.loads(archive.read(files[0]))
    except PullFailed:
        raise
    except (ValueError, UnicodeError, zipfile.BadZipFile, RuntimeError) as exc:
        raise PullFailed('invalid release artifact') from exc
    try:
        return evidence.check(parsed, run_id, run['head_sha'], number)
    except evidence.EvidenceError as exc:
        raise PullFailed(str(exc)) from exc


def reviewed(current_commit, candidate_commit):
    """Does the reviewed transition file allow this exact move?"""
    try:
        data = json.loads(private_file(TRANSITIONS, 65536))
    except (ValueError, UnicodeError) as exc:
        raise PullFailed('reviewed transition file is unreadable') from exc
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('transitions'), list):
        raise PullFailed('reviewed transition file is malformed')
    return any(isinstance(item, dict) and item.get('from_commit') == current_commit
               and item.get('to_commit') == candidate_commit for item in data['transitions'])


def write_record(record):
    """Small operator-facing note; never a source of truth for the transaction."""
    payload = (json.dumps(record, separators=(',', ':'), sort_keys=True) + '\n').encode()
    if len(payload) > MAX_RECORD:
        raise PullFailed('record is too large')
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    staged = RECORD.with_name('.pull-deploy.staged')
    if os.path.lexists(staged):
        os.unlink(staged)
    fd = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(staged, RECORD)
    os.chmod(RECORD, 0o600)


def read_record():
    try:
        data = json.loads(private_file(RECORD, MAX_RECORD))
        return data if isinstance(data, dict) else {}
    except (PullFailed, ValueError, UnicodeError):
        return {}


# Bale is the default: it is the messenger the owner and the company actually
# use, and its Bot API is deliberately shaped like Telegram's. Both endpoints are
# allowlisted by exact host, because the bot token travels inside the URL path —
# a redirect would hand it to whatever host answered.
NOTIFY_ENDPOINTS = {
    'bale': 'https://tapi.bale.ai/bot{token}/sendMessage',
    'telegram': 'https://api.telegram.org/bot{token}/sendMessage',
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects: the token is in the path and must reach one host only."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


NOTIFY_OPENER = urllib.request.build_opener(NoRedirect)

# The public check shares the same rule for a different reason: a redirect to
# the sign-in page is not a healthy site, so it is reported, not followed.
PUBLIC_OPENER = urllib.request.build_opener(NoRedirect)


def notification_target(config):
    """Resolve the endpoint from a root-only config file; None means stay silent."""
    if not isinstance(config, dict):
        raise PullFailed('notification config is not an object')
    provider = config.get('provider', 'bale')
    if provider not in NOTIFY_ENDPOINTS:
        raise PullFailed('unknown notification provider')
    # `bot_token`/`chat_id` is the current shape; the older telegram_* names are
    # still read so an existing file keeps working after an upgrade.
    token = config.get('bot_token', config.get('telegram_bot_token'))
    chat = config.get('chat_id', config.get('telegram_chat_id'))
    if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9:_-]{20,200}', token):
        raise PullFailed('notification token is malformed')
    chat = str(chat) if chat is not None else ''
    if not re.fullmatch(r'-?\d{1,20}|@[A-Za-z][A-Za-z0-9_]{3,31}', chat):
        raise PullFailed('notification chat id is malformed')
    return NOTIFY_ENDPOINTS[provider].format(token=token), chat


def notify(text):
    """Best-effort message; silence when it is not configured, never fatal."""
    if not os.path.lexists(NOTIFY):
        return False
    try:
        url, chat = notification_target(json.loads(private_file(NOTIFY, MAX_NOTIFY)))
        body = json.dumps({'chat_id': chat, 'text': text[:3500],
                           'disable_web_page_preview': True}).encode()
        request = urllib.request.Request(url, data=body, method='POST',
                                         headers={'Content-Type': 'application/json',
                                                  'User-Agent': 'xennic-pull-deploy'})
        with NOTIFY_OPENER.open(request, timeout=15) as response:
            return response.status == 200
    except (OSError, KeyError, TypeError, ValueError, PullFailed, urllib.error.HTTPError):
        return False


def public_check():
    """One plain GET against a public page; no token, no retries, no redirects.

    The redirect matters: the edge answers every path outside the route
    allowlist with the gate's sign-in redirect, and that page is itself a 200.
    Following it would turn "the gate is in the way" into "the site is healthy",
    so a redirect is reported as the status it is and never followed.
    """
    try:
        request = urllib.request.Request(PUBLIC_CHECK_URL,
                                         headers={'User-Agent': 'xennic-pull-deploy'})
        with PUBLIC_OPENER.open(request, timeout=20) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (OSError, ValueError):
        return 0


def phase_marker(owner_uid=0):
    """The phase the backend recorded on the host, if it recorded one.

    The backend writes this before it starts a helper, so a phase that hung
    or was killed still leaves the host saying where it stopped. The file is
    root-owned and holds a fixed phase name; anything else is ignored, and a
    missing file simply means no phase was recorded.
    """
    try:
        info = os.lstat(PHASE_MARKER)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != owner_uid or info.st_mode & 0o077:
            return None
        data = json.loads(PHASE_MARKER.read_bytes())
    except (OSError, ValueError, UnicodeError):
        return None
    if not isinstance(data, dict) or data.get('phase') not in KNOWN_PHASES:
        return None
    return data['phase']


def deploy(release, token):
    """The same request a human would pipe into the backend, nothing more."""
    manifest = load('pull_manifest', 'preview-deploy-manifest.py')
    try:
        line = json.dumps(manifest.validate_manifest(json.dumps(release).encode()),
                          separators=(',', ':'), sort_keys=True).encode() + b'\n'
    except manifest.InvalidManifest as exc:
        raise PullFailed('candidate release is invalid') from exc
    try:
        # The backend is installed as a private module, not as an executable.
        # The reviewed helper installer gives every phase helper an executable
        # copy and leaves `preview-deploy-backend.py` at mode 0600, and the
        # backend's own `verify_helpers` lists that file among the modules and
        # not among the executables. Executing the file therefore fails with a
        # permission error before the backend ever runs, and the deploy reported
        # that as "deployment backend did not finish". The backend is started
        # through the interpreter instead, exactly the way the deploy receiver
        # loads it: it is still its own root process, with the same two-line
        # request on stdin and the same clean environment.
        completed = subprocess.run([INTERPRETER, str(BACKEND)], input=line + token + b'\n',
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3600,
                                   env=SAFE_ENV, cwd='/')
    except OSError as exc:
        # The backend never started: a missing interpreter, a missing file or a
        # refused execution. This is not the same as a backend that ran and
        # said no, and the operator has to be able to tell them apart.
        raise PullFailed('deployment backend did not start') from exc
    except subprocess.TimeoutExpired as exc:
        raise PullFailed('deployment backend timed out') from exc
    output = completed.stdout.decode('utf-8', 'replace').strip()
    if completed.returncode != 0:
        raise PullFailed(f'deployment backend failed with exit {completed.returncode}')
    return output


def decide(journal, release):
    """Pure decision from the journal and the candidate release."""
    if journal is None:
        return 'no-journal'
    current = journal.get('current')
    if journal.get('pending') is not None:
        return 'in-flight'
    if current is not None and current.get('commit') == release['commit']:
        return 'up-to-date'
    if current is None:
        return 'no-journal'
    return 'consider'


def run(dry_run=False):
    for path in (ROOT, ROOT / 'state', ROOT / 'config', HELPERS):
        info = os.lstat(path)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise PullFailed(f'{path} is unsafe')
    verifier = load('pull_verifier', 'preview-release-verifier.py')
    evidence = load('pull_evidence', 'preview-ci-evidence.py')
    states = load('pull_state', 'preview-deploy-state.py')
    locks = load('pull_lock', 'preview-deploy-lock.py')

    token = read_token()
    release = release_from_run(verifier, evidence, token, newest_run(verifier, token))
    call('the release is no longer the dev head', lambda: verifier.assert_current(release, token))

    with contextlib.ExitStack() as stack:
        try:
            stack.enter_context(locks.acquire_lock(PULL_LOCK, nonblocking=True))
        except BlockingIOError:
            # Another pull deploy already holds this lock. This lock only keeps
            # two pull deploys from deciding at the same time; it is not the
            # deployment lock, which the backend takes for itself. The design
            # says: already running, stop, say nothing.
            return 0
        journal = None if states.Journal().absent() else states.Journal().read()
        action = decide(journal, release)
        stamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        if action in ('up-to-date', 'no-journal'):
            if not dry_run:
                write_record({'version': 1, 'at': stamp, 'result': action,
                              'candidate': release['commit'], 'run_number': release['run_number']})
            print(action)
            return 0
        if action == 'in-flight':
            print('in-flight')
            return 0

        current_commit = journal['current']['commit']
        if not reviewed(current_commit, release['commit']):
            record = {'version': 1, 'at': stamp, 'result': 'waiting-approval',
                      'from_commit': current_commit, 'to_commit': release['commit'],
                      'run_number': release['run_number']}
            if dry_run:
                print('dry-run: waiting-approval')
                return 0
            previous = read_record()
            write_record(record)
            if (previous.get('result'), previous.get('run_number')) != ('waiting-approval', release['run_number']):
                notify(f'Xennic: run {release["run_number"]} is ready but the migration transition '
                       f'{current_commit[:7]} -> {release["commit"][:7]} is not approved yet. '
                       'Nothing was deployed.')
            print('waiting-approval')
            return 0

        if dry_run:
            print('dry-run: would deploy')
            return 0

        try:
            output = deploy(release, token)
        except PullFailed as exc:
            # The phase marker is written by the backend before each helper
            # starts, so it names the phase that stopped even when the backend
            # itself was killed and could not report anything.
            phase = phase_marker()
            record = {'version': 1, 'at': stamp, 'result': 'failed', 'stage': 'backend',
                      'run_number': release['run_number'], 'to_commit': release['commit']}
            if phase is not None:
                record['phase'] = phase
            write_record(record)
            notify(f'Xennic: deployment of run {release["run_number"]} failed: {exc}. '
                   'The host journal and release-state.json hold the exact phase.')
            raise
        status = public_check()
        # The deployment itself is finished and the journal says so: the
        # backend already proved the new image is healthy inside the host. The
        # public check is an observation of the edge, not part of the
        # transaction, so it is recorded as what it is. A non-200 still exits
        # non-zero, because the operator has to look at the edge now.
        record = {'version': 1, 'at': stamp, 'result': 'deployed',
                  'run_number': release['run_number'], 'to_commit': release['commit'],
                  'public_status': status, 'public_url': PUBLIC_CHECK_URL,
                  'backend': output.splitlines()[-1][:200] if output else ''}
        write_record(record)
        if status != 200:
            notify(f'Xennic: run {release["run_number"]} ({release["commit"][:7]}) is deployed '
                   f'and healthy inside the host, but the public check {PUBLIC_CHECK_URL} '
                   f'returned {status}. Look at the edge now.')
            print('deployed')
            return 1
        notify(f'Xennic: run {release["run_number"]} ({release["commit"][:7]}) is live; '
               f'{PUBLIC_CHECK_URL} returned 200.')
        print('deployed')
        return 0


def main(argv):
    if os.geteuid() != 0:
        print('ci-pull-deploy requires root', file=sys.stderr)
        return 1
    if len(argv) > 2 or (len(argv) == 2 and argv[1] != '--dry-run'):
        print('usage: ci-pull-deploy [--dry-run]', file=sys.stderr)
        return 2
    os.umask(0o077)
    try:
        return run(dry_run=len(argv) == 2)
    except PullFailed as exc:
        print(f'pull deploy stopped: {exc}', file=sys.stderr)
        try:
            notify(f'Xennic: pull deployment stopped: {exc}')
        except Exception:  # notification must never mask the real error
            pass
        return 1
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        # An unexpected failure still has to say something useful: the type, and
        # the message when it is one of the verifier's own safe strings.
        detail = reason(exc)
        print(f'pull deploy failed: {type(exc).__name__}{": " + detail if detail else ""}',
              file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
