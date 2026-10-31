#!/usr/bin/env python3
"""Disposable CI: exercise transaction and real Compose replacement/rollback.

Test adapters deliberately map synthetic manifests to local images; they are
not evidence of GHCR verification or a working privileged deployment backend.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
if os.environ.get('CI') != 'true' or os.environ.get('COMPOSE_PROJECT_NAME') != 'xennic-preview-ci':
    raise SystemExit('Refusing: CI disposable project required')
run_id, attempt = os.environ.get('GITHUB_RUN_ID', ''), os.environ.get('GITHUB_RUN_ATTEMPT', '')
if not re.fullmatch(r'[0-9]+', run_id) or not re.fullmatch(r'[0-9]+', attempt):
    raise SystemExit('Refusing: invalid CI run identifier')
project = f'xennic-restore-{run_id}-{attempt}'
root = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, root / 'scripts' / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

transaction = load('transaction_ci', 'preview-deploy-transaction.py')
compose = load('compose_ci', 'preview-compose-operations.py')
state = load('state_ci', 'preview-deploy-state.py')
lock = load('lock_ci', 'preview-deploy-lock.py')

def release(n):
    return {'repository': 'feerozmandi/xennic-website', 'commit': f'{n:040x}', 'run_number': n,
            'digest': 'sha256:' + f'{n:064x}', 'platform': 'linux/amd64'}

with tempfile.TemporaryDirectory(prefix='xennic-rollback-', dir=os.environ['RUNNER_TEMP']) as temp:
    directory = Path(temp)
    override = directory / 'compose.yml'
    override.write_text('services:\n  app:\n    image: ${PREVIEW_IMAGE:?required}\n    pull_policy: never\n')
    compose.COMPOSE = ['/usr/bin/docker', 'compose', '-p', project, '-f', str(root / 'compose.preview.yml'), '-f', str(override)]
    compose.SAFE_ENV = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'LANG': 'C',
                        'PREVIEW_POSTGRES_DB': 'restore_ci', 'PREVIEW_POSTGRES_USER': 'restore_ci',
                        'PREVIEW_POSTGRES_PASSWORD': 'restore-ci-only-password',
                        'PREVIEW_DATABASE_URL': 'postgresql://restore_ci:restore-ci-only-password@postgres:5432/restore_ci',
                        'PREVIEW_PAYLOAD_SECRET': 'ci-only-preview-secret-not-for-real-use',
                        'PREVIEW_PORT': '33001', 'PREVIEW_ORIGIN': 'https://preview.xennic.ir'}
    valid_reference = compose.image_reference
    def local_reference(item):
        valid_reference(item)  # validation still runs; synthetic digests have no registry meaning
        if item == release(1): return f'{project}-app'
        if item == release(2): return f'{project}-bad'
        raise ValueError('unexpected CI fixture release')
    compose.image_reference = local_reference
    subprocess.run(['/usr/bin/docker', 'build', '--pull=false', '-t', f'{project}-bad', '-'],
                   input=f'FROM {project}-app\nCMD ["node", "-e", "process.exit(1)"]\n',
                   text=True, check=True, stdout=subprocess.DEVNULL)
    journal = state.Journal(directory, owner_uid=os.geteuid())
    journal._write({'version': 1, 'last_run': 1, 'blocked': False, 'current': release(1), 'previous': [], 'pending': None})

    class FixtureOps:
        # CI-only adapter. Backup/restore were performed by ci-restore.sh immediately
        # before this test; these adapters are not privileged operational helpers.
        def lock(self): return lock.acquire_lock(directory / 'lock', owner_uid=os.geteuid())
        def read_state(self): return journal.read()
        def preflight(self, item): return {'initial': False, 'rollback_safe': True}
        def pull_image(self, item):
            # Local fixture only, not a registry pull or release verifier.
            subprocess.run(['/usr/bin/docker', 'image', 'inspect', f'{project}-bad'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        def backup_and_verify(self, item): pass
        def assert_current(self, item): pass
        def mark_inflight(self, item): journal.mark_inflight(item)
        def migrate(self, item):
            env = dict(compose.SAFE_ENV, PREVIEW_IMAGE=f'{project}-app')
            subprocess.run(compose.COMPOSE + ['run', '--rm', '--no-deps', 'app', 'npm', 'run', 'preview:migrate'],
                           env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        def activate(self, item): compose.replace_app(item)
        def verify_health(self, item): raise AssertionError('broken image must not become healthy')
        def mark_healthy(self, item): journal.mark_healthy(item)
        def ensure_blocked(self, item): journal.ensure_blocked(item)
        def rollback_previous(self): compose.replace_app(release(1))
        def verify_previous_health(self):
            env = dict(compose.SAFE_ENV, PREVIEW_IMAGE=f'{project}-app')
            container = subprocess.check_output(compose.COMPOSE + ['ps', '-q', 'app'], env=env, text=True).strip()
            actual = subprocess.check_output(['/usr/bin/docker', 'inspect', '-f', '{{.Image}} {{.State.Health.Status}}', container], text=True).strip()
            expected = subprocess.check_output(['/usr/bin/docker', 'image', 'inspect', '-f', '{{.Id}}', f'{project}-app'], text=True).strip()
            if actual != expected + ' healthy': raise AssertionError('rollback image or health mismatch')

    try:
        transaction.deploy(json.dumps(release(2)).encode(), FixtureOps())
        raise AssertionError('broken release must not succeed')
    except transaction.DeploymentFailed as exc:
        if str(exc) != 'release failed; previous image restored, review required': raise
    result = journal.read()
    if not result['blocked'] or result['current'] != release(1) or result['pending'] != release(2):
        raise AssertionError('failed release did not remain blocked')
    print('PASS: actual Compose image failure, compatible-image rollback and durable blocked state')
