#!/usr/bin/env python3
"""Bind a release artifact to the workflow run that is about to deploy it.

The deploy job never trusts the run number, commit or digest it was triggered
with: it reads them from the evidence artifact that the publishing job produced
*after* the published image passed its own tests, then proves the artifact's run
identity against the current run. A mismatch stops the deployment before
anything reaches the host.

Reads the evidence JSON on stdin, writes the validated manifest line on stdout.
"""
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location('ci_evidence_manifest', Path(__file__).with_name('preview-deploy-manifest.py'))
manifest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manifest)


class EvidenceError(ValueError):
    """The artifact does not belong to this run or is malformed."""


def check(evidence, run_id, commit, run_number):
    if not isinstance(evidence, dict) or set(evidence) != {'version', 'run_id', 'run_attempt', 'release'}:
        raise EvidenceError('unexpected evidence fields')
    if evidence['version'] != 1:
        raise EvidenceError('unsupported evidence version')
    if type(evidence['run_id']) is not int or evidence['run_id'] != run_id:
        raise EvidenceError('evidence belongs to another workflow run')
    if type(evidence['run_attempt']) is not int or not 1 <= evidence['run_attempt'] <= 2**31 - 1:
        raise EvidenceError('invalid run attempt')
    try:
        release = manifest.validate_manifest(json.dumps(evidence['release']).encode())
    except manifest.InvalidManifest as exc:
        raise EvidenceError('invalid release in evidence') from exc
    if release['commit'] != commit:
        raise EvidenceError('evidence describes another commit')
    if release['run_number'] != run_number:
        raise EvidenceError('evidence describes another run number')
    return release


def manifest_line(release):
    return json.dumps(release, separators=(',', ':'), sort_keys=True)


def main(argv):
    args = {'--run-id': None, '--commit': None, '--run-number': None}
    if len(argv) != 7 or argv[1::2].count('--run-id') != 1 or set(argv[1::2]) != set(args):
        print('usage: preview-ci-evidence.py --run-id N --commit SHA --run-number N < evidence.json', file=sys.stderr)
        return 2
    for name, value in zip(argv[1::2], argv[2::2]):
        args[name] = value
    try:
        run_id, run_number = int(args['--run-id']), int(args['--run-number'])
        raw = sys.stdin.buffer.read(64 * 1024)
        release = check(json.loads(raw.decode('utf-8')), run_id, args['--commit'], run_number)
    except (ValueError, UnicodeError, TypeError):
        print('invalid release evidence', file=sys.stderr)
        return 2
    sys.stdout.write(manifest_line(release) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
