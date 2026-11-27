#!/usr/bin/python3
"""Verify one release against the approved GitHub workflow run and its artifact.

Only api.github.com and GitHub's signed artifact storage are contacted. No
metadata inside an image is treated as evidence of a successful publication.

A release also has to be named: the commit it releases carries exactly one
release tag, and that tag is the version the host records.
"""
import io
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile

BASE = 'https://api.github.com/repos/feerozmandi/xennic-website'
MAX_JSON = 2 * 1024 * 1024
MAX_ZIP = 1024 * 1024
# The shape of one release name: a major, a minor and a patch number, in that
# order, with a `v` in front.
VERSION = re.compile(r'v\d{1,6}\.\d{1,6}\.\d{1,6}')
# How many pages of release tags are read. A thousand names is far more than
# this repository has, and the walk stops at the first empty page.
MAX_TAG_PAGES = 10


class Unverified(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def request(url, token=None, maximum=MAX_JSON):
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or '').lower()
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise Unverified('invalid evidence endpoint')
    if token is not None:
        if host != 'api.github.com' or not url.startswith(BASE + '/'):
            raise Unverified('invalid GitHub endpoint')
    elif not (host.endswith('.blob.core.windows.net') or host.endswith('.actions.githubusercontent.com')):
        raise Unverified('invalid artifact storage endpoint')
    headers = {'User-Agent': 'xennic-preview-release-check', 'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28'}
    if token is not None:
        headers['Authorization'] = 'Bearer ' + token.decode('ascii')
    req = urllib.request.Request(url, headers=headers, method='GET')
    try:
        with OPENER.open(req, timeout=20) as res:
            data = res.read(maximum + 1)
            if len(data) > maximum:
                raise Unverified('evidence too large')
            return data
    except urllib.error.HTTPError as exc:
        if exc.code in (301, 302, 303, 307, 308) and token is not None:
            location = exc.headers.get('Location', '')
            # Never forward the GitHub bearer token to the storage endpoint.
            return request(location, None, maximum)
        raise Unverified('GitHub evidence unavailable') from exc
    except (OSError, ValueError) as exc:
        raise Unverified('GitHub evidence unavailable') from exc


def get_json(path, token):
    try:
        return json.loads(request(BASE + path, token))
    except (UnicodeError, ValueError) as exc:
        raise Unverified('invalid GitHub evidence') from exc


def assert_current(release, token):
    current = get_json('/commits/dev', token)
    if not isinstance(current, dict) or current.get('sha') != release['commit']:
        raise Unverified('dev no longer points to this commit')


def release_tags(token):
    """Every release tag in the repository, read from the same API."""
    tags = []
    for page in range(1, MAX_TAG_PAGES + 1):
        data = get_json(f'/tags?per_page=100&page={page}', token)
        if not isinstance(data, list):
            raise Unverified('invalid release tags')
        if not data:
            break
        tags.extend(item for item in data if isinstance(item, dict))
        if len(data) < 100:
            break
    return tags


def release_version(commit, token):
    """The one release name that belongs to this commit.

    A release is named by a Git tag on the commit it releases, and a commit
    that carries no name of its own, or more than one, cannot be told apart
    from another commit later. The name is therefore part of what makes a
    release a release, not a decoration of it.
    """
    if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise Unverified('invalid release commit')
    found = []
    for tag in release_tags(token):
        name = tag.get('name')
        target = tag.get('commit')
        sha = target.get('sha') if isinstance(target, dict) else None
        if isinstance(name, str) and VERSION.fullmatch(name) and sha == commit:
            found.append(name)
    if len(found) != 1:
        raise Unverified('release is not named')
    return found[0]


def verify(release, token):
    if not isinstance(token, bytes) or not re.fullmatch(rb'[!-~]{1,4096}', token):
        raise Unverified('missing GitHub token')
    runs = get_json('/actions/workflows/ci.yml/runs?branch=dev&event=push&per_page=100', token)
    if not isinstance(runs, dict) or not isinstance(runs.get('workflow_runs'), list):
        raise Unverified('invalid workflow runs')
    matches = [r for r in runs['workflow_runs'] if isinstance(r, dict) and type(r.get('run_number')) is int and
               r['run_number'] == release['run_number']]
    if len(matches) != 1:
        raise Unverified('release run unavailable')
    run = matches[0]
    run_id, attempt = run.get('id'), run.get('run_attempt')
    if (type(run_id) is not int or run_id < 1 or type(attempt) is not int or attempt < 1 or
            run.get('head_sha') != release['commit'] or run.get('head_branch') != 'dev' or
            run.get('event') != 'push' or run.get('status') != 'completed' or run.get('conclusion') != 'success'):
        raise Unverified('release workflow did not succeed for this commit')
    artifacts = get_json(f'/actions/runs/{run_id}/artifacts?per_page=100', token)
    if not isinstance(artifacts, dict) or not isinstance(artifacts.get('artifacts'), list):
        raise Unverified('release artifacts unavailable')
    matching = [a for a in artifacts['artifacts'] if isinstance(a, dict) and
                a.get('name') == f'xennic-preview-release-{attempt}' and a.get('expired') is False]
    if len(matching) != 1 or type(matching[0].get('id')) is not int or matching[0]['id'] < 1:
        raise Unverified('release evidence artifact unavailable')
    raw = request(BASE + f"/actions/artifacts/{matching[0]['id']}/zip", token, MAX_ZIP)
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            files = archive.infolist()
            if (len(files) != 1 or files[0].filename != 'xennic-preview-release.json' or
                    files[0].file_size > 16384 or files[0].is_dir()):
                raise Unverified('invalid release artifact')
            evidence = json.loads(archive.read(files[0]))
    except (ValueError, UnicodeError, zipfile.BadZipFile, RuntimeError) as exc:
        raise Unverified('invalid release artifact') from exc
    if evidence != {'version': 1, 'run_id': run_id, 'run_attempt': attempt, 'release': release}:
        raise Unverified('release artifact does not match')
    release_version(release['commit'], token)
    return run_id
