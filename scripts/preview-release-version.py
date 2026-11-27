#!/usr/bin/env python3
"""Name one release: the semantic version of a commit.

The name of a release is decided here, in CI, before the image is published.
The repository's own release tags say which release came before, and the
commit messages between them say how far the version moves: a breaking
change moves the major number, a feature moves the minor number, and
everything else moves the patch number.

The name is a Git tag on the released commit, and the published image carries
the same name as a second tag. The host does not invent a version: it reads
the tag that names the release it is about to install, from the same public
API the release verifier reads.

Nothing here reads a secret or talks to the network. The repository is read
with git, and the answer is one line of text.
"""
import argparse
import re
import subprocess
import sys

sys.dont_write_bytecode = True

# The shape of one release version: a major, a minor and a patch number, in
# that order, with a `v` in front.
VERSION = re.compile(r'v(\d{1,6})\.(\d{1,6})\.(\d{1,6})')
# A conventional commit header: a type, an optional scope, an optional `!`
# for a breaking change, and a subject.
CONVENTIONAL = re.compile(r'^(?P<type>[A-Za-z]+)(?:\([^()]{1,100}\))?(?P<breaking>!)?: ')
# The first release of a line is the first version of that line.
FIRST = (1, 0, 0)
# How many names may be tried before the answer is that there is none.
LIMIT = 1000


class Unnamed(RuntimeError):
    """The commit cannot be named."""


def parse_version(value):
    """The three numbers of a release version, or a refusal."""
    match = VERSION.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise Unnamed('not a release version')
    return tuple(int(part) for part in match.groups())


def format_version(version):
    return 'v{}.{}.{}'.format(*version)


def commit_kind(messages):
    """major, minor or patch, from the conventional commits in the range."""
    kind = 'patch'
    for message in messages:
        header, _, body = message.partition('\n')
        match = CONVENTIONAL.match(header)
        if match and match.group('breaking'):
            return 'major'
        if 'BREAKING CHANGE:' in body:
            return 'major'
        if match and match.group('type').lower() == 'feat':
            kind = 'minor'
    return kind


def bump(base, kind):
    """The next version after `base`, moved by the kind of the change."""
    if kind == 'major':
        return (base[0] + 1, 0, 0)
    if kind == 'minor':
        return (base[0], base[1] + 1, 0)
    return (base[0], base[1], base[2] + 1)


def _run(repository, arguments):
    """One git command; the exit status and the output as text."""
    try:
        result = subprocess.run(
            ['git', '-c', 'safe.directory=*', '-C', str(repository), *arguments],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
            timeout=60, check=False,
            env={'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'LANG': 'C',
                 'GIT_TERMINAL_PROMPT': '0', 'GIT_CONFIG_NOSYSTEM': '1'})
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Unnamed('git is unavailable') from exc
    return result.returncode, result.stdout.decode('utf-8', 'replace')


def git(repository, *arguments):
    """One git command; its output as text, or a refusal."""
    status, output = _run(repository, arguments)
    if status:
        raise Unnamed('git failed')
    return output


def commit_of(repository, revision):
    """The commit a revision names, whatever it is."""
    return git(repository, 'rev-parse', '--verify', revision + '^{commit}').strip()


def release_tags(repository):
    """Every release tag in the repository: its name and the commit it names."""
    tags = {}
    for line in git(repository, 'tag', '--list', 'v*').splitlines():
        name = line.strip()
        if not name or not VERSION.fullmatch(name):
            continue
        try:
            tags[name] = commit_of(repository, name)
        except Unnamed:
            continue
    return tags


def is_ancestor(repository, ancestor, descendant):
    """Is one commit an ancestor of the other?"""
    status, _ = _run(repository, ['merge-base', '--is-ancestor', ancestor, descendant])
    return status == 0


def messages(repository, start, commit):
    """The commit messages between two commits, oldest first."""
    if start:
        raw = git(repository, 'log', '-z', '--format=%B', start + '..' + commit)
    else:
        raw = git(repository, 'log', '-z', '--format=%B', commit)
    return [item for item in raw.split('\0') if item.strip()]


def name(repository='.', commit=None):
    """The release version of a commit, and nothing else.

    The base is the highest release version among the tags that are already
    on this commit's history: a tag that names another branch says nothing
    about this release. The first release of a line is `v1.0.0`.

    A name that another commit already carries is not reused, because two
    releases with one name cannot be told apart afterwards.
    """
    commit = commit_of(repository, commit or 'HEAD')
    tags = release_tags(repository)
    own = sorted(tag for tag, sha in tags.items() if sha == commit)
    if own:
        # The commit is already named. Naming it again must give the same
        # name, or a re-run of the same release would look like a new one.
        if len(own) > 1:
            raise Unnamed('the commit carries more than one release name')
        return own[0]
    base_tag = None
    base_version = None
    for tag, sha in sorted(tags.items()):
        if not is_ancestor(repository, sha, commit):
            continue
        version = parse_version(tag)
        if base_version is None or version > base_version:
            base_version, base_tag = version, tag
    if base_version is None:
        return format_version(FIRST)
    version = bump(base_version, commit_kind(messages(repository, base_tag, commit)))
    for _ in range(LIMIT):
        candidate = format_version(version)
        if candidate not in tags or tags[candidate] == commit:
            return candidate
        version = (version[0], version[1], version[2] + 1)
    raise Unnamed('no free release version')


def main(argv):
    parser = argparse.ArgumentParser(description='Name one release.')
    parser.add_argument('--repository', default='.', help='the repository to read')
    parser.add_argument('--commit', default=None, help='the commit to name (default: HEAD)')
    parser.add_argument('--check', default=None, help='check one version instead of naming a commit')
    arguments = parser.parse_args(argv[1:])
    try:
        if arguments.check is not None:
            version = format_version(parse_version(arguments.check))
        else:
            version = name(arguments.repository, arguments.commit)
    except Unnamed:
        print('Cannot name this release', file=sys.stderr)
        return 1
    print(version)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
