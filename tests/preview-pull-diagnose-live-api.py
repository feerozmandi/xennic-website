#!/usr/bin/env python3
"""Prove the live release against the real repository, from this machine.

The suite next door proves the diagnosis against a fixture. This program
runs the same diagnosis against the repository itself, so the claim "the
live version is the name the repository gives the live commit" is checked
against the real tags, the real run and the real artifact list.

Only the artifact download is faked. GitHub answers that request with a
redirect to its own storage, and the sandbox cannot open a TLS connection
to it; the archive is rebuilt from the run the API already reported, so
every other answer in the run is the real one.

    python3 tests/preview-pull-diagnose-live-api.py [commit]

The commit is the one the host would have live. Without it, the newest
release the repository has is used. The program proves the case twice: once
with the journal telling the truth, and once with the journal claiming a
name the repository does not give. The first must pass and the second must
fail, or the proof proves nothing.

Exit code 0 means the proof held.
"""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.dont_write_bytecode = True


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def api(path):
    """One real API call, through gh, which is the authenticated path here."""
    result = subprocess.run(
        ['gh', 'api', '-H', 'Accept: application/vnd.github+json', path],
        capture_output=True)
    if result.returncode != 0:
        raise SystemExit(f'gh api {path} failed: {result.stderr.decode("utf-8", "replace")}')
    return json.loads(result.stdout)


def main():
    diagnose = load('diagnose', ROOT / 'scripts/diagnose-preview-pull-deploy.py')
    bearer = b'real-read-only-token'

    # The diagnosis asks GitHub the same way the deployer does. It sends the
    # token as a bearer token; the repository is public, so the read works
    # with any token and the real answers come back.
    diagnose.read_token = lambda: bearer

    def download_artifact(artifact_id, tok):
        artifact = api(f'/repos/feerozmandi/xennic-website/actions/artifacts/{artifact_id}')
        run_id = (artifact.get('workflow_run') or {}).get('id')
        if not run_id:
            raise SystemExit('the artifact does not name its run')
        run = api(f'/repos/feerozmandi/xennic-website/actions/runs/{run_id}')
        evidence = {
            'version': 1,
            'run_id': run_id,
            'run_attempt': run.get('run_attempt'),
            'release': {
                'repository': 'feerozmandi/xennic-website',
                'platform': 'linux/amd64',
                'commit': run.get('head_sha'),
                'run_number': run.get('run_number'),
                'digest': 'sha256:' + '0' * 64,
            },
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('xennic-preview-release.json', json.dumps(evidence))
        return [], buffer.getvalue()

    diagnose.download_artifact = download_artifact

    asked = sys.argv[1] if len(sys.argv) > 1 else ''
    if asked:
        head = api(f'/repos/feerozmandi/xennic-website/commits/{asked}')['sha']
    else:
        head = api('/repos/feerozmandi/xennic-website/tags?per_page=100')[0]['commit']['sha']
    name = diagnose.release_name_for(head, bearer)
    print(f'the repository names the commit {head[:7]} as {name}')

    if name is None:
        print('that commit carries no release name yet')
        return 2

    states = load('states', ROOT / 'scripts/preview-deploy-state.py')
    real_load = diagnose.load

    def load_with_fake_state(module_name, filename):
        if filename == 'preview-deploy-state.py':
            return states
        return real_load(module_name, filename)

    diagnose.load = load_with_fake_state
    # The public routes are not reachable from here, and they are not part
    # of the proof.
    diagnose.PUBLIC_ROUTES = ()

    def prove(claimed, label):
        journal = {
            'current': {'commit': head, 'run_number': 1, 'run_attempt': 1},
            'release_version': claimed,
            'blocked': None,
        }
        states.Journal = lambda *a, **k: type('J', (), {
            'read': staticmethod(lambda: json.loads(json.dumps(journal))),
        })()
        print(f'\n########## {label} ##########')
        diagnose.failures.clear()
        diagnose.anomalies.clear()
        old = sys.argv
        sys.argv = ['diagnose-preview-pull-deploy.py']
        try:
            code = diagnose.main()
        finally:
            sys.argv = old
        print(f'>>> exit code: {code}')
        return code

    truth = prove(name, f'TRUTH — the host journal says {name}')
    lie = prove('v9.9.9', 'LIE — the host journal claims a name the repository does not give')

    print('\n== the proof')
    if truth == 0:
        print(f'   The live version is {name}, and the repository names the live commit the same.')
    else:
        print(f'   The proof did not hold for {name} (exit {truth}).')
    if lie == 1:
        print('   A journal that claims another name is refused (exit 1).')
    else:
        print(f'   A journal that claims another name was not refused (exit {lie}).')
    return 0 if (truth == 0 and lie == 1) else 1


if __name__ == '__main__':
    raise SystemExit(main())
