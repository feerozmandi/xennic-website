#!/usr/bin/python3
"""Disposable CI: exact installed backend/helpers; GitHub/GHCR endpoints are fixtures."""
import base64
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import lz4.frame
import msgpack
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

sys.dont_write_bytecode = True
ROOT = Path('/srv/xennic-preview')
LIBEXEC = Path('/usr/local/libexec/xennic-preview')
fixture_path = ROOT / 'config/ci-github-fixture.json'
spec = importlib.util.spec_from_file_location('installed_backend_ci', LIBEXEC / 'preview-deploy-backend.py')
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)

fixture = json.loads(fixture_path.read_text())
previous = fixture['releases']['previous']
first = fixture['releases']['first']
second = fixture['releases']['second']

def select(name):
    fixture['current'] = name
    fixture_path.write_text(json.dumps(fixture))
    fixture_path.chmod(0o600)


def run_sql():
    # Fixed project and synthetic fixture only; no SQL comes from a request.
    env = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'PREVIEW_IMAGE': 'ghcr.io/feerozmandi/xennic-website@' + first['digest']}
    command = ['/usr/bin/docker', 'compose', '-p', 'xennic-preview', '--env-file', str(ROOT / 'secrets/preview.env'),
               '-f', str(ROOT / 'config/compose.yml'), 'exec', '-T', 'postgres', 'psql', '-U', 'preview_ci',
               '-d', 'preview_ci', '-tAc', "SELECT count(*) FROM shared.customers WHERE name='CI snapshot fixture'"]
    return subprocess.check_output(command, env=env, text=True).strip()


def run_migration_check():
    env = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'PREVIEW_IMAGE': 'ghcr.io/feerozmandi/xennic-website@' + first['digest']}
    query = "SELECT to_regclass('website.ci_compatibility_probe') IS NOT NULL AND EXISTS (SELECT 1 FROM website.payload_migrations WHERE name='20261031_000000_ci_additive' AND batch >= 0)"
    command = ['/usr/bin/docker', 'compose', '-p', 'xennic-preview', '--env-file', str(ROOT / 'secrets/preview.env'),
               '-f', str(ROOT / 'config/compose.yml'), 'exec', '-T', 'postgres', 'psql', '-U', 'preview_ci',
               '-d', 'preview_ci', '-tAc', query]
    return subprocess.check_output(command, env=env, text=True).strip()


def run_media():
    env = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'PREVIEW_IMAGE': 'ghcr.io/feerozmandi/xennic-website@' + first['digest']}
    command = ['/usr/bin/docker', 'compose', '-p', 'xennic-preview', '--env-file', str(ROOT / 'secrets/preview.env'),
               '-f', str(ROOT / 'config/compose.yml'), 'exec', '-T', 'app', 'cat', '/app/media/ci-snapshot.txt']
    return subprocess.check_output(command, env=env, text=True)


# The actual root-owned FixedRunner checks all installed helper files. No
# injection or test adapter is supplied to Backend.
runner = backend.FixedRunner()
runner.verify_helpers()
# Exercise the explicit temporary staging-only local-backup policy on the
# successful release; the second release still exercises the original SFTP.
config_path = ROOT / 'config/backup.json'
sftp_config = json.loads(config_path.read_text())
local_config = {'approved': True, 'transport': 'manual-local', 'environment': 'preview-staging-only',
                'no_real_customer_data': True, 'age_recipient': sftp_config['age_recipient']}
config_path.write_text(json.dumps(local_config)); config_path.chmod(0o600)

# This entire script is executed only by the guarded disposable CI fixture.
# An unlabelled reserved volume must not be mistaken for an empty first install.
subprocess.check_call(['/usr/bin/docker', 'volume', 'create', 'xennic-preview_preview_db'], stdout=subprocess.DEVNULL)
try:
    select('previous')
    try:
        backend.run_checked(json.dumps(previous).encode(), b'synthetic-token', backend.Backend(b'synthetic-token'))
        raise AssertionError('pre-existing volume was accepted without a journal')
    except backend.BackendError:
        pass
    if (ROOT / 'state/release-state.json').exists():
        raise AssertionError('rejected environment created a journal')
finally:
    subprocess.check_call(['/usr/bin/docker', 'volume', 'rm', 'xennic-preview_preview_db'], stdout=subprocess.DEVNULL)

# Fail only after the bad image was activated. The same installed helpers must
# close the app, keep both volumes and data, and record no healthy release.
select('second')
try:
    backend.run_checked(json.dumps(second).encode(), b'synthetic-token', backend.Backend(b'synthetic-token'))
    raise AssertionError('bad initial health was accepted')
except backend.transaction.DeploymentFailed:
    pass
journal = backend.states.Journal().read()
if (not journal['blocked'] or journal['current'] is not None or journal['pending'] != second or
        journal.get('failure') != 'initial-deployment-failed'):
    raise AssertionError('failed initial install did not record a blocked failure')
marker = ROOT / 'state' / f"activation-{second['run_number']}.json"
if not marker.is_file():
    # Disposable-fixture diagnostics only; never print OAuth config or secrets.
    print('CI diagnostic: activation marker absent; inspecting fixed gateway state', flush=True)
    diagnostic = ['/usr/bin/docker', 'compose', '-p', 'xennic-preview-gateway', '--env-file',
                  str(ROOT / 'secrets/preview.env'), '-f', str(ROOT / 'config/gateway.yml')]
    subprocess.run(diagnostic + ['config', '--quiet'], check=False)
    subprocess.run(diagnostic + ['ps', '--all'], check=False)
    for service in ('caddy', 'gate'):
        ids = subprocess.check_output(diagnostic + ['ps', '--all', '-q', service], text=True).split()
        if len(ids) == 1:
            data = json.loads(subprocess.check_output(['/usr/bin/docker', 'inspect', ids[0]]))[0]
            print('CI diagnostic:', service, 'state=', data.get('State', {}).get('Status'),
                  'error=', data.get('State', {}).get('Error'), flush=True)
    import importlib.machinery
    loader = importlib.machinery.SourceFileLoader('installed_fixed_diagnostic', str(LIBEXEC / 'activate'))
    diagnostic_spec = importlib.util.spec_from_loader(loader.name, loader)
    diagnostic_module = importlib.util.module_from_spec(diagnostic_spec); loader.exec_module(diagnostic_module)
    try:
        diagnostic_module.gateway_configuration()
        diagnostic_module.gateway_image_ids()
        print('CI diagnostic: fixed gateway files and images verified', flush=True)
    except (RuntimeError, ValueError, OSError) as exc:
        print('CI diagnostic: fixed gateway preflight failed:', str(exc), flush=True)
    raise AssertionError('initial failure did not reach activation')
initial_env = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent',
               'PREVIEW_IMAGE': 'ghcr.io/feerozmandi/xennic-website@' + second['digest']}
compose = ['/usr/bin/docker', 'compose', '-p', 'xennic-preview', '--env-file', str(ROOT / 'secrets/preview.env'),
           '-f', str(ROOT / 'config/compose.yml')]
app = subprocess.check_output(compose + ['ps', '--all', '-q', 'app'], env=initial_env, text=True).strip()
if subprocess.check_output(['/usr/bin/docker', 'inspect', '-f', '{{.State.Running}}', app], text=True).strip() != 'false':
    raise AssertionError('failed initial app was not stopped')
for volume in ('xennic-preview_preview_db', 'xennic-preview_preview_media'):
    subprocess.check_call(['/usr/bin/docker', 'volume', 'inspect', volume], stdout=subprocess.DEVNULL)
# A damaged journal must not prevent the installed fixed closure from stopping
# this exact initial image. This is confined to the disposable CI project.
subprocess.check_call(compose + ['up', '-d', '--no-deps', '--no-build', 'app'], env=initial_env, stdout=subprocess.DEVNULL)
state_path = ROOT / 'state/release-state.json'
state_path.write_text('invalid-ci-journal'); state_path.chmod(0o600)
runner.close_initial(second)
if subprocess.check_output(['/usr/bin/docker', 'inspect', '-f', '{{.State.Running}}', app], text=True).strip() != 'false':
    raise AssertionError('initial closure relied on a readable journal')
state_path.write_text(json.dumps(journal)); state_path.chmod(0o600)
query = "SELECT count(*) FROM website.payload_migrations WHERE name='20261030_163225_baseline'"
count = subprocess.check_output(compose + ['exec', '-T', 'postgres', 'psql', '-U', 'preview_ci', '-d', 'preview_ci', '-tAc', query], env=initial_env, text=True).strip()
if count != '1': raise AssertionError('failed initial database was not preserved')

# Reset only this disposable CI fixture; actual VPS data must never be removed.
real_gateway = ['/usr/bin/docker', 'compose', '-p', 'xennic-preview-gateway', '--env-file',
                str(ROOT / 'secrets/preview.env'), '-f', str(ROOT / 'config/gateway.yml')]
subprocess.check_call(real_gateway + ['down', '--volumes', '--remove-orphans'], env=initial_env, stdout=subprocess.DEVNULL)
subprocess.check_call(compose + ['down', '--volumes', '--remove-orphans'], env=initial_env, stdout=subprocess.DEVNULL)
for directory in (ROOT / 'state', ROOT / 'work'):
    for path in directory.iterdir():
        if not path.is_file() or path.is_symlink(): raise AssertionError('unexpected disposable fixture')
        path.unlink()

# Successful first install performs migration, seed, health, encrypted backup,
# isolated restore, a second health check, then records the real first release.
select('previous')
receiver = str(LIBEXEC / 'deploy-receiver')
payload = json.dumps(previous).encode() + b'\nsynthetic-token\n'
receiver_env = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'LANG': 'C',
                'SSH_ORIGINAL_COMMAND': 'xennic-preview-deploy'}
wrong_env = dict(receiver_env, SSH_ORIGINAL_COMMAND='xennic-preview-deploy;id')
rejected = subprocess.run([receiver], input=payload, env=wrong_env, capture_output=True)
if rejected.returncode == 0 or b'synthetic-token' in rejected.stderr or (ROOT / 'state/release-state.json').exists():
    raise AssertionError('installed receiver accepted invalid command')
try:
    received = subprocess.run([receiver], input=payload, env=receiver_env, capture_output=True)
    if received.returncode or b'synthetic-token' in received.stdout + received.stderr:
        raise backend.transaction.DeploymentFailed('installed receiver failed')
    result = previous
except backend.transaction.DeploymentFailed:
    # Keep this test failing: successful first installation is still required.
    # Nevertheless verify the actual installed failure path preserves the data
    # and closes the app while the gateway guard is intentionally in place.
    failed = backend.states.Journal().read()
    if (not failed['blocked'] or failed['current'] is not None or failed['pending'] != previous or
            failed.get('failure') != 'initial-deployment-failed'):
        raise AssertionError('initial failure left an unsafe journal')
    marker = ROOT / 'state' / f"activation-{previous['run_number']}.json"
    if not marker.is_file(): raise AssertionError('initial failure occurred before activation')
    failed_id = subprocess.check_output(compose + ['ps', '--all', '-q', 'app'], env=initial_env, text=True).strip()
    if subprocess.check_output(['/usr/bin/docker', 'inspect', '-f', '{{.State.Running}}', failed_id], text=True).strip() != 'false':
        raise AssertionError('initial failure left the app running')
    for volume in ('xennic-preview_preview_db', 'xennic-preview_preview_media'):
        subprocess.check_call(['/usr/bin/docker', 'volume', 'inspect', volume], stdout=subprocess.DEVNULL)
    print('PASS: failed initial activation remains blocked, app stopped, volumes preserved; success is still required', flush=True)
    raise
journal = backend.states.Journal().read()
record = json.loads((ROOT / 'state' / f"backup-{previous['run_number']}.json").read_text())
if result != previous or journal['blocked'] or journal['current'] != previous or journal['previous']:
    raise AssertionError('first healthy release was not recorded correctly')
if record.get('remote_path') != 'manual-offsite-pending' or not (ROOT / 'work/backup.age').is_file():
    raise AssertionError('first encrypted local backup not verified')

# A synthetic session is signed using the disposable CI cookie secret. This
# tests an authorized request through the *installed-helper-started* gateway;
# it is not evidence of a GitHub OAuth login or real-user acceptance.
seed = 'eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHg='
name = '__Host-preview_gate'
packed = msgpack.packb({'u': 'ci-user', 'e': 'ci-user@example.com'}, use_bin_type=True)
compressed = lz4.frame.compress(packed, block_size=lz4.frame.BLOCKSIZE_MAX64KB)
iv = os.urandom(16)
encryptor = Cipher(algorithms.AES(b'x' * 32), modes.CFB(iv)).encryptor()
value = base64.urlsafe_b64encode(iv + encryptor.update(compressed) + encryptor.finalize()).decode('ascii')
timestamp = str(int(time.time()))
signature = base64.urlsafe_b64encode(hmac.new(seed.encode(), (name + value + timestamp).encode(), hashlib.sha256).digest()).decode('ascii')
synthetic_cookie = name + '=' + value + '|' + timestamp + '|' + signature
valid_probe = """(async()=>{const cookie=require('fs').readFileSync(0,'utf8');
const http=require('node:http'); const result=await new Promise((resolve,reject)=>{
 const q=http.request({hostname:'caddy',port:8080,path:'/',headers:{Host:'preview.xennic.ir',Cookie:cookie}},r=>{
  const chunks=[]; r.on('data',x=>chunks.push(x));r.on('end',()=>resolve({status:r.statusCode,body:Buffer.concat(chunks).toString()}));r.on('error',reject)});
 q.setTimeout(5000,()=>q.destroy(new Error('timeout')));q.on('error',reject);q.end()});
if(result.status!==200 || !result.body.includes('<html'))throw Error('synthetic authorized session did not reach app')
})().catch(()=>process.exit(1))"""
subprocess.run(compose + ['exec', '-T', 'app', 'node', '-e', valid_probe], env=initial_env,
               input=synthetic_cookie, text=True, check=True)
print('PASS: synthetic session reached the app through the helper-started gateway; real OAuth not tested', flush=True)

# The operational helper, not CI, has started this real Caddy and OAuth2 Proxy.
# Stop only the disposable gate and verify no unauthenticated path reaches app.
subprocess.check_call(real_gateway + ['stop', 'gate'], env=initial_env)
offline_probe = """(async()=>{const http=require('node:http');
for(const p of ['/','/admin','/api/pages','/api/graphql','/media/missing.png']){
 const status=await new Promise((resolve,reject)=>{const q=http.request({hostname:'caddy',port:8080,path:p,headers:{Host:'preview.xennic.ir'}},
  r=>{r.resume();resolve(r.statusCode)});q.setTimeout(5000,()=>q.destroy(new Error('timeout')));q.on('error',reject);q.end()});
 if(status<500)throw Error('gate outage did not close '+p)} })().catch(()=>process.exit(1))"""
subprocess.check_call(compose + ['exec', '-T', 'app', 'node', '-e', offline_probe], env=initial_env)
select('first')
try:
    runner.call('release-check', first, b'synthetic-token')
    raise AssertionError('missing gate was accepted by installed helper')
except backend.BackendError:
    pass
subprocess.check_call(real_gateway + ['start', 'gate'], env=initial_env)
select('previous')
print('PASS: installed helper gateway outage denied traffic and prevented release preflight', flush=True)

# Negative integration regression: attach a CI-owned Caddy and synthetic gate
# to the exact installed helper's app, probe protected paths and gate outage,
# and require the installed release-check to reject this unapproved peer. This
# is deliberately not final gateway acceptance: CI, not the helper, starts it.
gateway_compose = ['/usr/bin/docker', 'compose', '-p', 'xennic-ci-gateway', '-f',
                   '/root/xennic-preview-install/ci-gateway/compose.yml']
probe = r"""
(async () => {
  const http = require('node:http');
  const call = (path, cookie) => new Promise((resolve,reject) => {
    const q=http.request({hostname:'caddy-fixture',port:8080,path,headers:{Host:'preview.xennic.ir',
      ...(cookie ? {Cookie:cookie} : {})}},r=>{
      const chunks=[];r.on('data',x=>chunks.push(x));
      r.on('end',()=>resolve({status:r.statusCode,body:Buffer.concat(chunks).toString()}));r.on('error',reject)});
    q.setTimeout(5000,()=>q.destroy(new Error('timeout')));q.on('error',reject);q.end();
  });
  const paths = ['/', '/admin', '/api/pages', '/api/graphql', '/media/missing.png'];
  for (const path of paths) {
    let response;
    for (let i = 0; i < 20; i++) {
      response = await call(path);
      if (process.argv[1] === 'offline' || response.status < 500) break;
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    if (process.argv[1] === 'offline') {
      if (response.status < 500) throw Error('gate outage passed ' + path + ': ' + response.status);
    } else {
      const expected = path.startsWith('/api/') ? 401 : 302;
      if (response.status !== expected) throw Error('missing session passed ' + path + ': ' + response.status);
    }
  }
  if (process.argv[1] !== 'offline') {
    const response = await call('/', '__Host-preview_gate=ci-valid');
    if (response.status !== 200 || !response.body.includes('<html'))
      throw Error('synthetic session did not reach app');
  }
})().catch(error => { console.error(error.message); process.exit(1); });
"""
# Establish the same candidate passes without the additional gateway peer;
# otherwise an unrelated verifier or migration-policy failure could look like
# a successful gateway rejection.
select('first')
runner.call('release-check', first, b'synthetic-token')
try:
    subprocess.check_call(gateway_compose + ['up', '-d', '--wait'])
    for project_compose, service in ((compose, 'app'), (compose, 'postgres'), (gateway_compose, 'gate')):
        cid = subprocess.check_output(project_compose + ['ps', '-q', service], env=initial_env, text=True).strip()
        item = json.loads(subprocess.check_output(['/usr/bin/docker', 'inspect', cid]))[0]
        host = item['HostConfig']; net = item['NetworkSettings']
        if (host.get('NetworkMode') == 'host' or host.get('PublishAllPorts') or host.get('PortBindings') or
                any((net.get('Ports') or {}).values())):
            raise AssertionError(service + ' published a host port')
    subprocess.check_call(compose + ['exec', '-T', 'app', 'node', '-e', probe, 'online'], env=initial_env)
    subprocess.check_call(gateway_compose + ['stop', 'gate'])
    subprocess.check_call(compose + ['exec', '-T', 'app', 'node', '-e', probe, 'offline'], env=initial_env)
    subprocess.check_call(gateway_compose + ['start', 'gate'])
    subprocess.check_call(compose + ['exec', '-T', 'app', 'node', '-e', probe, 'online'], env=initial_env)
    print('PASS: real Caddy/app fixture blocks protected paths and gate outage; auth is synthetic', flush=True)
    select('first')
    try:
        runner.call('release-check', first, b'synthetic-token')
    except backend.BackendError:
        print('PASS: installed release-check rejected unapproved Caddy peer', flush=True)
    else:
        raise AssertionError('unapproved gateway was accepted')
    select('previous')
finally:
    subprocess.run(gateway_compose + ['down', '--remove-orphans'], check=False)
# Add synthetic upgrade data only after a genuine first release exists.
subprocess.check_call(compose + ['exec', '-T', 'postgres', 'psql', '-U', 'preview_ci', '-d', 'preview_ci', '-v', 'ON_ERROR_STOP=1', '-c',
                                "INSERT INTO shared.customers (name, source) VALUES ('CI snapshot fixture', 'ci-only')"], env=initial_env, stdout=subprocess.DEVNULL)
subprocess.check_call(compose + ['exec', '-T', 'app', 'sh', '-c', 'printf synthetic-media > /app/media/ci-snapshot.txt'], env=initial_env)
print('PASS: installed helper rejected orphan volume; first-install failure preserved data and closed app; first install and local encrypted restore succeeded')

select('first')
first_result = backend.run_checked(json.dumps(first).encode(), b'synthetic-token', backend.Backend(b'synthetic-token'))
if first_result != first:
    raise AssertionError('successful release mismatch')
journal = backend.states.Journal().read()
if journal['blocked'] or journal['current'] != first or run_sql() != '1' or run_media() != 'synthetic-media' or run_migration_check() != 't':
    raise AssertionError('successful release or data mismatch')
local_record = json.loads((ROOT / 'state' / f"backup-{first['run_number']}.json").read_text())
if local_record.get('remote_path') != 'manual-offsite-pending':
    raise AssertionError('local backup must not claim offsite transfer')
config_path.write_text(json.dumps(sftp_config)); config_path.chmod(0o600)
select('second')
try:
    backend.run_checked(json.dumps(second).encode(), b'synthetic-token', backend.Backend(b'synthetic-token'))
    raise AssertionError('deliberately bad post-activation health must fail')
except backend.transaction.DeploymentFailed as exc:
    if str(exc) != 'release failed; previous image restored, review required': raise
journal = backend.states.Journal().read()
marker = ROOT / 'state' / f"activation-{second['run_number']}.json"
if not marker.is_file() or json.loads(marker.read_text()) != second:
    raise AssertionError('failure was not after a verified activation')
if not journal['blocked'] or journal['current'] != first or journal['pending'] != second or run_sql() != '1' or run_media() != 'synthetic-media' or run_migration_check() != 't':
    raise AssertionError('rollback journal or data mismatch')
print('PASS: installed controller and helpers: success, post-activation health failure, compatible rollback, synthetic data preserved')
