#!/usr/bin/env python3
"""Write the non-secret evidence emitted *after* published-image tests succeed.

This does not verify a release or make deployment decisions. The caller must
bind the artifact to the successful GitHub workflow run through the GitHub API.
"""
import importlib.util
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('release_manifest_evidence', Path(__file__).with_name('preview-deploy-manifest.py'))
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)


def record(env):
    if env.get('GITHUB_REPOSITORY') != manifest.REPOSITORY or env.get('GITHUB_REF') != 'refs/heads/dev' or env.get('GITHUB_EVENT_NAME') != 'push':
        raise ValueError('not a dev push for the approved repository')
    try:
        run_number = int(env['GITHUB_RUN_NUMBER'])
        run_id = int(env['GITHUB_RUN_ID'])
        attempt = int(env['GITHUB_RUN_ATTEMPT'])
        candidate = {'repository': manifest.REPOSITORY, 'commit': env['GITHUB_SHA'],
                     'digest': env['IMAGE_DIGEST'], 'platform': 'linux/amd64', 'run_number': run_number}
        checked = manifest.validate_manifest(json.dumps(candidate).encode())
    except (KeyError, ValueError, TypeError, manifest.InvalidManifest) as exc:
        raise ValueError('invalid release evidence') from exc
    if not 1 <= run_id <= 2**63 - 1 or not 1 <= attempt <= 2**31 - 1:
        raise ValueError('invalid run identity')
    return {'version': 1, 'run_id': run_id, 'run_attempt': attempt, 'release': checked}


def main():
    try:
        data = record(os.environ)
        sys.stdout.write(json.dumps(data, separators=(',', ':'), sort_keys=True) + '\n')
    except ValueError:
        print('Cannot record preview release evidence', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
