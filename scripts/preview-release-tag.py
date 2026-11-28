#!/usr/bin/env python3
"""Name one release: write the tag that names it, and prove that it does.

The name of a release is a tag on the commit the release publishes. The tag
is written through the GitHub API and read back through the same API, because
a release the repository does not name is not a release: the host reads the
name of the release it is about to install from that same public API.

Reading and writing are both idempotent:

  * a name that already names this commit is a success, not a failure, so a
    re-run of the same release does not look like a new one;
  * a name that names another commit is refused, so two releases can never
    share one name;
  * a write the API refuses is read back once more, because the write may
    have reached the API even when its answer did not reach this run.

Every refusal is written as a GitHub error line, so the reason of a failed
release can be read next to the failed step without opening the run log.

Nothing here reads a secret of its own: the API is called through the `gh`
command, which takes the token from the environment.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True

# How many times a refused write is read back, and how long to wait between
# two writes. A transient answer is answered differently the next time.
ATTEMPTS = 4
WAIT = 2.0
# The shape of one commit: forty hexadecimal characters.
COMMIT = re.compile(r'^[0-9a-f]{40}$')
# The HTTP status `gh` prints next to its own message.
STATUS = re.compile(r'HTTP (\d{3})')


class Refused(RuntimeError):
    """The release cannot be named."""


class Transient(RuntimeError):
    """The API gave an answer that may be different the next time."""


def api(repository, method, path, fields=None):
    """One call to the GitHub API, through `gh`.

    The answer is the exit status, the body, and the status code the API
    gave. `gh` prints the body of a failed call on its standard output, so
    the body is read there and not only where a message would be.
    """
    command = ['gh', 'api', '--method', method, 'repos/{}/{}'.format(repository, path)]
    for key, value in (fields or {}).items():
        command += ['-f', '{}={}'.format(key, value)]
    environment = dict(os.environ)
    environment.setdefault('GH_TOKEN', environment.get('GITHUB_TOKEN', ''))
    result = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL, timeout=120, check=False)
    body = result.stdout.decode('utf-8', 'replace').strip()
    message = result.stderr.decode('utf-8', 'replace').strip()
    status = None
    found = STATUS.search(message)
    if found:
        status = int(found.group(1))
    return result.returncode, body, message, status


def read_ref(repository, version):
    """The commit a name points at, or None when the name is free.

    A name that is free answers 404. Any other refusal is a refusal: the
    run does not get to decide that a name is free because it could not
    read the repository.
    """
    code, body, message, status = api(repository, 'GET', 'git/ref/tags/{}'.format(version))
    if code == 0:
        try:
            answer = json.loads(body)
        except ValueError as exc:
            raise Refused('the answer about the name {} is not readable: {}'.format(version, exc))
        obj = answer.get('object') or {}
        sha = obj.get('sha') or ''
        if obj.get('type') == 'tag':
            # An annotated tag names a tag object; the commit is inside it.
            code, body, message, status = api(repository, 'GET', 'git/tags/{}'.format(sha))
            if code != 0:
                raise Refused('the name {} names a tag that cannot be read: {}'.format(version, message))
            try:
                sha = (json.loads(body).get('object') or {}).get('sha') or ''
            except ValueError as exc:
                raise Refused('the tag of {} is not readable: {}'.format(version, exc))
        if not COMMIT.match(sha):
            raise Refused('the name {} answers with {} instead of a commit.'.format(version, sha))
        return sha
    if status == 404:
        return None
    raise Refused('the name {} cannot be read: {}'.format(version, message or body))


def write_ref(repository, version, commit):
    """Write the name on the commit. The answer says why it was refused."""
    code, body, message, status = api(
        repository, 'POST', 'git/refs',
        {'ref': 'refs/tags/{}'.format(version), 'sha': commit})
    if code == 0:
        return
    if status == 422 and 'already exists' in body:
        # Another run wrote the name first, or a re-run found it there.
        raise Refused('the name {} is already there.'.format(version))
    if status is not None and 500 <= status < 600:
        raise Transient('the API answered {}: {}'.format(status, message or body))
    raise Refused('the name {} cannot be written: {}'.format(
        version, message or body or 'the API gave no reason'))


def name(repository, version, commit):
    """Write the name, and prove that the repository carries it."""
    if not COMMIT.match(commit):
        raise Refused('{} is not a commit.'.format(commit))
    existing = read_ref(repository, version)
    if existing is not None:
        if existing != commit:
            raise Refused('the name {} already names {}, and this run releases {}.'.format(
                version, existing, commit))
        return 'already', existing
    reason = None
    for attempt in range(ATTEMPTS):
        try:
            write_ref(repository, version, commit)
        except Transient as exc:
            reason = str(exc)
        except Refused as exc:
            reason = str(exc)
            # The write may have reached the API even when the answer did
            # not reach this run, so the name is read back once more.
            written = read_ref(repository, version)
            if written is not None:
                if written != commit:
                    raise Refused('the name {} already names {}, and this run releases {}.'.format(
                        version, written, commit))
                return 'raced', written
            break
        else:
            written = read_ref(repository, version)
            if written is None:
                raise Refused('the name {} was written but the repository does not carry it.'.format(version))
            if written != commit:
                raise Refused('the name {} names {}, and this run releases {}.'.format(
                    version, written, commit))
            return 'written', written
        written = read_ref(repository, version)
        if written is not None:
            if written != commit:
                raise Refused('the name {} already names {}, and this run releases {}.'.format(
                    version, written, commit))
            return 'raced', written
        if attempt + 1 < ATTEMPTS:
            time.sleep(WAIT)
    raise Refused(reason or 'the name {} cannot be written.'.format(version))


def main(argv):
    parser = argparse.ArgumentParser(description='Name one release.')
    parser.add_argument('--repository', default=os.environ.get('GITHUB_REPOSITORY', ''),
                        help='the owner and name of the repository')
    parser.add_argument('--version', required=True, help='the name of the release')
    parser.add_argument('--commit', required=True, help='the commit the release publishes')
    parser.add_argument('--summary', default=None, help='the run summary to write to')
    arguments = parser.parse_args(argv[1:])
    if '/' not in arguments.repository:
        print('::error::The repository {} is not an owner and a name.'.format(arguments.repository))
        return 2
    try:
        how, written = name(arguments.repository, arguments.version, arguments.commit)
    except Refused as exc:
        # The reason is written as a GitHub error line, so it can be read
        # next to the failed step without opening the run log.
        print('::error::{}'.format(exc))
        print('Cannot name this release', file=sys.stderr)
        return 1
    line = '- Release tag: `{}` → `{}` ({})'.format(
        arguments.version, arguments.commit[:7], how)
    print(line)
    if arguments.summary:
        with open(arguments.summary, 'a', encoding='utf-8') as handle:
            handle.write(line + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
