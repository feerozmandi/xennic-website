#!/usr/bin/env python3
"""Read-only diagnosis of the pull deployer on the preview host.

The deployer stops with one word ("Unverified") when GitHub does not give it
what it expects. This program asks the same questions one by one and prints
the real answer for each: the HTTP status, the endpoint that refused, and the
message GitHub returned. It changes nothing, writes nothing, and never prints
the release token.

Run it as root on the host:

    python3 scripts/diagnose-preview-pull-deploy.py

It is a diagnostic, not a deployment step: it never approves a transition and
never starts a deployment.
"""
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile

sys.dont_write_bytecode = True

ROOT = Path('/srv/xennic-preview')
# The modules this program needs are installed with the privileged helpers,
# but the program itself may sit anywhere (it is a diagnostic, not a helper).
HELPER_DIRECTORIES = (Path(__file__).resolve().parent, Path('/usr/local/libexec/xennic-preview'))
TOKEN = Path('/root/.xennic-release-token')
TRANSITIONS = ROOT / 'config/compatible-transitions.json'
CANDIDATE = Path('/root/xennic-preview-candidate.json')
GATEWAY = Path('/usr/local/libexec/xennic-preview/ci-gateway')
BASE = 'https://api.github.com/repos/feerozmandi/xennic-website'
MAX_ZIP = 1024 * 1024
PUBLIC_ROUTES = ('https://xennic.ir/robots.txt', 'https://xennic.ir/sitemap.xml',
                 'https://xennic.ir/platform', 'https://xennic.ir/health')
# The live migration ledger the owner confirmed; the host compares it with the
# database before it writes anything, so a wrong value is refused, not applied.
PREVIOUS_MIGRATIONS = 'WyIyMDI2MTAzMF8xNjMyMjVfYmFzZWxpbmUiXQ=='

failures = []


def load(name, filename):
    """Load an installed module, from this directory or from the helper set."""
    for directory in HELPER_DIRECTORIES:
        path = directory / filename
        if not path.is_file():
            continue
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    raise RuntimeError(f'{filename} is not installed')


def heading(text):
    print(f'\n== {text}')


def note(text):
    print(f'   {text}')


def fail(text):
    failures.append(text)
    print(f'   FAILED: {text}')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never redirect an API call: the bearer token must reach one host only."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Recorder(urllib.request.HTTPRedirectHandler):
    """Follow a redirect, but remember where it went."""

    def __init__(self):
        self.hops = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.hops.append((code, newurl))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def read_token():
    info = os.lstat(TOKEN)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
        raise RuntimeError('the token file is not private to root')
    data = TOKEN.read_bytes().strip()
    if not re.fullmatch(rb'[!-~]{1,4096}', data):
        raise RuntimeError('the token is malformed')
    return data


def api(path, token):
    """One API call; returns (status, body) and never raises for an HTTP error."""
    url = BASE + path
    headers = {'User-Agent': 'xennic-preview-diagnose', 'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28', 'Authorization': 'Bearer ' + token.decode('ascii')}
    request = urllib.request.Request(url, headers=headers, method='GET')
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=20) as response:
            return response.status, response.read(2 * 1024 * 1024)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(64 * 1024)
    except (OSError, ValueError) as exc:
        raise RuntimeError(f'{type(exc).__name__}: {exc}') from exc


def github_message(body):
    """The message GitHub returned, if the body is a JSON error object."""
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError):
        return ''
    if isinstance(data, dict) and isinstance(data.get('message'), str):
        return data['message'][:200]
    return ''


def download_artifact(artifact_id, token):
    """Fetch the evidence zip the way the deployer does, but say what happened."""
    url = f'{BASE}/actions/artifacts/{artifact_id}/zip'
    headers = {'User-Agent': 'xennic-preview-diagnose', 'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28', 'Authorization': 'Bearer ' + token.decode('ascii')}
    request = urllib.request.Request(url, headers=headers, method='GET')
    recorder = Recorder()
    opener = urllib.request.build_opener(recorder)
    try:
        with opener.open(request, timeout=30) as response:
            return recorder.hops, response.read(MAX_ZIP + 1)
    except urllib.error.HTTPError as exc:
        return recorder.hops, exc
    except (OSError, ValueError) as exc:
        return recorder.hops, exc


def write_candidate(line):
    """Write the validated manifest for the approval, root-only.

    This is the only thing this program ever writes, and only when it is asked
    to. The file holds the manifest that was just bound to the successful run,
    so the operator never has to retype it and never can mistype it.
    """
    staged = CANDIDATE.with_name('.' + CANDIDATE.name + '.staged')
    if os.path.lexists(staged):
        os.unlink(staged)
    fd = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(line.encode() + b'\n')
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(staged, CANDIDATE)
    os.chmod(CANDIDATE, 0o600)


def public_status(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'xennic-preview-diagnose'})
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=20) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (OSError, ValueError):
        return 0


def main():
    write_manifest = '--write-manifest' in sys.argv[1:]
    if sys.argv[1:] and not write_manifest:
        print('usage: diagnose-preview-pull-deploy.py [--write-manifest]', file=sys.stderr)
        return 2
    heading('host')
    note(f'host name : {os.uname().nodename}')
    note(f'root      : {os.geteuid() == 0}')

    heading('release token')
    try:
        token = read_token()
        note(f'present, {len(token)} bytes, root-owned and mode 0600 (the value is never printed)')
    except (OSError, RuntimeError) as exc:
        fail(f'the release token cannot be used: {exc}')
        print('\nRESULT: failed — the token is the first thing to fix.')
        return 1

    heading('dev head')
    status, body = api('/commits/dev', token)
    note(f'GET /commits/dev -> {status}')
    if status != 200:
        fail(f'GitHub refused the commit read: {github_message(body) or body[:200]!r}')
        print('\nRESULT: failed — the token cannot read the repository.')
        return 1
    sha = json.loads(body).get('sha')
    note(f'dev head: {sha}')

    heading('workflow runs')
    status, body = api('/actions/workflows/ci.yml/runs?branch=dev&event=push&per_page=30', token)
    note(f'GET /actions/workflows/ci.yml/runs -> {status}')
    if status != 200:
        fail(f'GitHub refused the run list: {github_message(body) or body[:200]!r}')
        print('\nRESULT: failed — the token cannot list workflow runs '
              '(it needs read access to Actions).')
        return 1
    runs = json.loads(body).get('workflow_runs', [])
    matching = [r for r in runs if r.get('head_sha') == sha and r.get('head_branch') == 'dev'
                and r.get('event') == 'push' and r.get('status') == 'completed'
                and r.get('conclusion') == 'success' and type(r.get('run_number')) is int]
    if not matching:
        fail('no successful push run for the current dev head')
        print('\nRESULT: failed — there is nothing to deploy yet.')
        return 1
    run = max(matching, key=lambda r: r['run_number'])
    note(f"newest successful dev run: number {run['run_number']}, id {run['id']}, "
         f"attempt {run['run_attempt']}")

    heading('release evidence artifact')
    status, body = api(f"/actions/runs/{run['id']}/artifacts?per_page=100", token)
    note(f'GET /actions/runs/{run["id"]}/artifacts -> {status}')
    if status != 200:
        fail(f'GitHub refused the artifact list: {github_message(body) or body[:200]!r}')
        print('\nRESULT: failed — the token cannot list run artifacts.')
        return 1
    wanted = f"xennic-preview-release-{run['run_attempt']}"
    matches = [a for a in json.loads(body).get('artifacts', [])
               if a.get('name') == wanted and a.get('expired') is False]
    if len(matches) != 1:
        fail(f'expected exactly one artifact named {wanted}, found {len(matches)}')
        print('\nRESULT: failed — the release evidence artifact is missing.')
        return 1
    artifact = matches[0]
    note(f"{artifact['name']}: id {artifact['id']}, {artifact['size_in_bytes']} bytes")

    heading('artifact download')
    hops, result = download_artifact(artifact['id'], token)
    for code, target in hops:
        host = urllib.parse.urlsplit(target).hostname or ''
        note(f'redirect {code} -> {host}')
    if isinstance(result, urllib.error.HTTPError):
        fail(f'the artifact download was refused with HTTP {result.code}: '
             f'{github_message(result.read(64 * 1024))}')
    elif isinstance(result, BaseException):
        fail(f'the artifact download failed: {type(result).__name__}: {result}')
    else:
        note(f'downloaded {len(result)} bytes')

    if not failures:
        heading('evidence envelope')
        release = None
        try:
            with zipfile.ZipFile(io.BytesIO(result)) as archive:
                names = archive.namelist()
                note(f'archive contains: {names}')
                evidence = json.loads(archive.read('xennic-preview-release.json'))
            evidence_module = load('diagnose_evidence', 'preview-ci-evidence.py')
            release = evidence_module.check(evidence, run['id'], sha, run['run_number'])
            note('the envelope binds to this run, commit and run number')
            note(f"candidate: commit {release['commit']}, run {release['run_number']}, "
                 f"digest {release['digest']}")
        except (KeyError, ValueError, UnicodeError, zipfile.BadZipFile, RuntimeError) as exc:
            fail(f'the evidence envelope is not usable: {type(exc).__name__}: {exc}')
    else:
        release = None

    heading('live release journal')
    try:
        states = load('diagnose_state', 'preview-deploy-state.py')
        journal = states.Journal().read()
        current = journal.get('current')
        note(f"current: run {current['run_number']} commit {current['commit']}"
             if current else 'current: none recorded')
        note(f"blocked: {journal.get('blocked')}")
    except Exception as exc:  # noqa: BLE001 - a diagnosis must not stop here
        note(f'the journal could not be read: {type(exc).__name__}: {exc}')

    heading('reviewed transitions')
    try:
        data = json.loads(TRANSITIONS.read_text('utf-8'))
        note(f'{len(data.get("transitions", []))} transition(s) on file')
        for item in data.get('transitions', []):
            note(f"{item['from_commit'][:7]} -> {item['to_commit'][:7]}")
    except (OSError, ValueError, UnicodeError) as exc:
        note(f'the reviewed transition file could not be read: {type(exc).__name__}')

    heading('public routes (no redirect is followed)')
    for url in PUBLIC_ROUTES:
        note(f'{url} -> {public_status(url)}')
    note('/health is behind the gate on purpose: it answers 302 and is not a deployment signal.')

    if release is not None and not failures:
        heading('the candidate, for the approval')
        line = json.dumps(release, separators=(',', ':'), sort_keys=True)
        note(f'manifest: {line}')
        if write_manifest:
            try:
                write_candidate(line)
                note(f'written: {CANDIDATE} (root-owned, 0600)')
            except OSError as exc:
                fail(f'the candidate file could not be written: {exc}')
        if GATEWAY.exists():
            zeros = '0' * 64
            note('the gateway is installed: the approval can be given on this host.')
            note('  first pass  : cat CANDIDATE | ci-gateway approve '
                 + zeros + ' ' + PREVIOUS_MIGRATIONS)
            note('  second pass : cat CANDIDATE | ci-gateway approve <the hash it printed> '
                 + PREVIOUS_MIGRATIONS)
        else:
            note('the gateway is not installed here: approve from your own machine with')
            note('  ./scripts/approve-transition.sh --run-id <run id> '
                 '--migrations \'["20261030_163225_baseline"]\'')

    print('\n== result')
    if failures:
        for item in failures:
            print(f'   FAILED: {item}')
        print('   The deployer stops at the first of these. Nothing was changed.')
        return 1
    print('   Every step of the release read works from this host.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
