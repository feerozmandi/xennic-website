#!/usr/bin/env bash
# A disposable GitHub runner only: install and execute the exact root helper.
set -euo pipefail
if [[ "${CI:-}" != true || "${GITHUB_ACTIONS:-}" != true || -z "${RUNNER_TEMP:-}" ]]; then
  echo 'Refusing outside disposable GitHub Actions runner' >&2; exit 1
fi
umask 077
for p in /srv/xennic-preview /root/xennic-preview-install /usr/local/libexec/xennic-preview; do
  if sudo test -e "$p"; then echo 'Refusing existing fixed installation path' >&2; exit 1; fi
done
if [[ -n "$(docker ps -aq --filter label=com.docker.compose.project=xennic-preview)" || -n "$(docker volume ls -q --filter label=com.docker.compose.project=xennic-preview)" ]]; then
  echo 'Refusing existing fixed Compose project or volumes' >&2; exit 1
fi
if id xennicbackupci >/dev/null 2>&1; then echo 'Refusing existing fixture user' >&2; exit 1; fi
scratch=$(mktemp -d "$RUNNER_TEMP/xennic-sftp.XXXXXX")
cleanup() {
  if test -f "$scratch/chain-created"; then
    if sudo test -f "$scratch/nginx.pid"; then sudo kill "$(sudo cat "$scratch/nginx.pid")" 2>/dev/null || true; fi
    if sudo test -f "$scratch/github-fixture.pid"; then sudo kill "$(sudo cat "$scratch/github-fixture.pid")" 2>/dev/null || true; fi
    sudo docker rm -f xennic-ci-fixture-registry >/dev/null 2>&1 || true
    if test -f "$scratch/hosts.original"; then sudo cp "$scratch/hosts.original" /etc/hosts; fi
    sudo rm -f /usr/local/share/ca-certificates/xennic-ci-fixture.crt
    sudo rm -rf /etc/docker/certs.d/ghcr.io
    sudo update-ca-certificates >/dev/null 2>&1 || true
  fi
  if sudo test -f /srv/xennic-preview/config/compose.yml && sudo test -f /srv/xennic-preview/secrets/preview.env; then
    sudo env PREVIEW_IMAGE="$(cat "$scratch/old-image" 2>/dev/null || echo fixture-only)" docker compose -p xennic-preview --env-file /srv/xennic-preview/secrets/preview.env -f /srv/xennic-preview/config/compose.yml down --volumes --remove-orphans >/dev/null 2>&1 || true
  fi
  if sudo test -f "$scratch/sshd.pid"; then sudo kill "$(sudo cat "$scratch/sshd.pid")" 2>/dev/null || true; fi
  sudo userdel -r xennicbackupci >/dev/null 2>&1 || true
  sudo rm -rf /srv/xennic-preview /root/xennic-preview-install /usr/local/libexec/xennic-preview
  rm -rf "$scratch"
}
trap cleanup EXIT
sudo useradd --create-home --shell /usr/sbin/nologin xennicbackupci
sudo passwd -d xennicbackupci >/dev/null
sudo install -d -o xennicbackupci -g xennicbackupci -m 0700 /home/xennicbackupci/.ssh /home/xennicbackupci/store
ssh-keygen -q -t ed25519 -N '' -f "$scratch/client"
sudo install -o xennicbackupci -g xennicbackupci -m 0600 "$scratch/client.pub" /home/xennicbackupci/.ssh/authorized_keys
ssh-keygen -q -t ed25519 -N '' -f "$scratch/host"
sudo chown root:root "$scratch/host"
sudo chmod 0600 "$scratch/host"
# Local Docker bridge is reachable only from this disposable runner / bridge.
host=$(docker network inspect bridge --format '{{(index .IPAM.Config 0).Gateway}}')
[[ "$host" =~ ^[0-9.]+$ && "$host" != 127.* ]] || { echo 'No disposable bridge address' >&2; exit 1; }
port=29488
cat > "$scratch/sshd_config" <<EOF
Port $port
ListenAddress $host
HostKey $scratch/host
PidFile $scratch/sshd.pid
AuthorizedKeysFile .ssh/authorized_keys
AllowUsers xennicbackupci
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
UsePAM no
StrictModes yes
Subsystem sftp internal-sftp
EOF
sudo install -d -m 0755 /run/sshd
sudo /usr/sbin/sshd -t -f "$scratch/sshd_config"
sudo /usr/sbin/sshd -f "$scratch/sshd_config"
sudo install -d -o root -g root -m 0700 /root/xennic-preview-install /srv/xennic-preview /srv/xennic-preview/config /srv/xennic-preview/secrets /srv/xennic-preview/work /srv/xennic-preview/state
sudo install -d -o root -g root -m 0755 /usr/local/libexec
for f in preview-backup-sftp.py preview-backup-operation.py preview-pull-image.py preview-age-backup.py preview-deploy-readiness.py preview-deploy-state.py preview-deploy-manifest.py preview-deploy-backend.py preview-deploy-transaction.py preview-deploy-lock.py preview-internal-health.py preview-compose-operations.py preview-release-verifier.py preview-fixed-operations.py; do
  sudo install -o root -g root -m 0600 "scripts/$f" "/root/xennic-preview-install/$f"
done
sudo install -o root -g root -m 0700 scripts/install-preview-sftp-helper.py /root/xennic-preview-install/install-preview-sftp-helper.py
sudo /usr/bin/python3 /root/xennic-preview-install/install-preview-sftp-helper.py
# The same production check must reject both a permissive helper and module.
sudo /usr/bin/python3 - <<'PY'
import importlib.util, os, sys
sys.dont_write_bytecode = True
root = '/usr/local/libexec/xennic-preview'
spec = importlib.util.spec_from_file_location('installed_backend', root + '/preview-deploy-backend.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
runner = module.FixedRunner(); runner.verify_helpers()
for name, safe in [('release-check', 0o700), ('preview-release-verifier.py', 0o600)]:
    path = root + '/' + name
    os.chmod(path, 0o644)
    try:
        try: runner.verify_helpers()
        except module.BackendError: pass
        else: raise RuntimeError('unsafe installed file was accepted')
    finally: os.chmod(path, safe)
runner.verify_helpers()
PY
# Negative parser checks execute the installed pull code without any network.
if printf '%s\n%s\n' '{"repository":"other/repo"}' 'synthetic-token' | sudo /usr/local/libexec/xennic-preview/pull-image >/dev/null 2>&1; then
  echo 'Invalid pull manifest was accepted' >&2; exit 1
fi
if sudo /usr/local/libexec/xennic-preview/pull-image --arbitrary </dev/null >/dev/null 2>&1; then
  echo 'Arbitrary pull argument was accepted' >&2; exit 1
fi
sudo install -o root -g root -m 0600 "$scratch/client" /srv/xennic-preview/secrets/backup-ssh-key
age-keygen -o "$scratch/age-identity" >/dev/null 2>&1
sudo install -o root -g root -m 0600 "$scratch/age-identity" /srv/xennic-preview/secrets/backup-identity
recipient=$(age-keygen -y "$scratch/age-identity")
printf '[%s]:%s %s\n' "$host" "$port" "$(cat "$scratch/host.pub")" | sudo tee /srv/xennic-preview/config/backup-known-hosts >/dev/null
sudo chmod 0600 /srv/xennic-preview/config/backup-known-hosts
python3 - "$host" "$port" "$recipient" <<'PY' | sudo tee /srv/xennic-preview/config/backup.json >/dev/null
import json, sys
print(json.dumps({'approved': True, 'transport': 'sftp', 'host': sys.argv[1], 'port': int(sys.argv[2]), 'user': 'xennicbackupci', 'remote_directory': '/home/xennicbackupci/store', 'age_recipient': sys.argv[3]}))
PY
sudo chmod 0600 /srv/xennic-preview/config/backup.json
printf 'synthetic encrypted snapshot for SFTP CI\n' | age -r "$recipient" | sudo tee /srv/xennic-preview/work/backup.age >/dev/null
sudo chmod 0600 /srv/xennic-preview/work/backup.age
python3 - "$scratch" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
def r(n): return {'repository':'feerozmandi/xennic-website','commit':f'{n:040x}','digest':'sha256:'+f'{n:064x}','platform':'linux/amd64','run_number':n}
(p/'release.json').write_text(json.dumps(r(2)))
(p/'state.json').write_text(json.dumps({'version':1,'last_run':2,'blocked':True,'current':r(1),'previous':[],'pending':r(2)}))
(p/'release-failure.json').write_text(json.dumps(r(3)))
(p/'state-failure.json').write_text(json.dumps({'version':1,'last_run':3,'blocked':True,'current':r(1),'previous':[],'pending':r(3)}))
(p/'release-backup-failure.json').write_text(json.dumps(r(4)))
(p/'state-backup-failure.json').write_text(json.dumps({'version':1,'last_run':4,'blocked':True,'current':r(1),'previous':[],'pending':r(4)}))
PY
sudo install -o root -g root -m 0600 "$scratch/state.json" /srv/xennic-preview/state/release-state.json
# Direct execution of the installed, root-owned helper with only a manifest on stdin.
sudo /usr/local/libexec/xennic-preview/sftp-transfer < "$scratch/release.json"
sudo test -s /srv/xennic-preview/state/backup-2.json
sudo test ! -e /srv/xennic-preview/work/verified.age
if sudo -u nobody test -w /usr/local/libexec/xennic-preview/sftp-transfer; then echo 'Unsafe helper permission' >&2; exit 1; fi
if sudo -u nobody test -r /srv/xennic-preview/secrets/backup-ssh-key; then echo 'Unsafe secret permission' >&2; exit 1; fi
# Exercise the installed backup-verify executable against a real, disposable
# preview project and the same SFTP server. Its previous release metadata is a
# synthetic fixture: GitHub/GHCR verification is NOT part of this test.
sudo rm /srv/xennic-preview/work/backup.age
sudo install -o root -g root -m 0600 compose.preview.yml /srv/xennic-preview/config/compose.yml
cat > "$scratch/preview.env" <<'EOF'
PREVIEW_POSTGRES_DB=preview_ci
PREVIEW_POSTGRES_USER=preview_ci
PREVIEW_POSTGRES_PASSWORD=disposable-ci-password
PREVIEW_DATABASE_URL=postgresql://preview_ci:disposable-ci-password@postgres:5432/preview_ci
PREVIEW_PAYLOAD_SECRET=disposable-ci-secret-not-real
PREVIEW_PORT=33019
PREVIEW_ORIGIN=https://preview.xennic.ir
EOF
sudo install -o root -g root -m 0600 "$scratch/preview.env" /srv/xennic-preview/secrets/preview.env
compose=(sudo docker compose -p xennic-preview --env-file /srv/xennic-preview/secrets/preview.env -f /srv/xennic-preview/config/compose.yml)
sudo docker build -t xennic-preview-app -f Dockerfile.preview . >/dev/null
"${compose[@]}" up -d --wait --no-build postgres
"${compose[@]}" run --rm --no-deps -T app npm run preview:migrate
"${compose[@]}" run --rm --no-deps -T app npm run preview:seed
"${compose[@]}" up -d --wait --no-build app
"${compose[@]}" exec -T postgres psql -U preview_ci -d preview_ci -v ON_ERROR_STOP=1 -c "INSERT INTO shared.customers (name, source) VALUES ('CI snapshot fixture', 'ci-only')" >/dev/null
"${compose[@]}" exec -T app sh -c 'printf synthetic-media > /app/media/ci-snapshot.txt'
sudo install -o root -g root -m 0600 "$scratch/state-failure.json" /srv/xennic-preview/state/release-state.json
if ! result=$(sudo /usr/local/libexec/xennic-preview/backup-verify < "$scratch/release-failure.json" 2>&1); then
  printf '::error::Installed backup helper failed: %s\n' "$result"
  exit 1
fi
printf '%s\n' "$result"
sudo test -s /srv/xennic-preview/state/backup-3.json
sudo test -s /srv/xennic-preview/work/backup.age
app_id=$("${compose[@]}" ps --all -q app)
test "$(sudo docker inspect -f '{{.State.Running}}' "$app_id")" = false
"${compose[@]}" exec -T postgres psql -U preview_ci -d preview_ci -tAc "SELECT count(*) FROM shared.customers WHERE name='CI snapshot fixture'" | grep -qx 1
# Simulate a subsequent transfer failure: do not invoke migration, verify data
# and ciphertext remain and the actual app stays stopped with blocked state.
"${compose[@]}" up -d --wait --no-build app
sudo rm /srv/xennic-preview/work/backup.age
sudo install -o root -g root -m 0600 "$scratch/state-backup-failure.json" /srv/xennic-preview/state/release-state.json
sudo kill "$(sudo cat "$scratch/sshd.pid")"
if sudo /usr/local/libexec/xennic-preview/backup-verify < "$scratch/release-backup-failure.json"; then echo 'Backup transfer failure was accepted' >&2; exit 1; fi
sudo test ! -e /srv/xennic-preview/state/backup-4.json
sudo test -s /srv/xennic-preview/work/backup.age
test "$(sudo docker inspect -f '{{.State.Running}}' "$app_id")" = false
"${compose[@]}" exec -T postgres psql -U preview_ci -d preview_ci -tAc "SELECT count(*) FROM shared.customers WHERE name='CI snapshot fixture'" | grep -qx 1
sudo grep -q '"blocked": true' /srv/xennic-preview/state/release-state.json
printf 'PASS: installed backup helper stopped app, backed up DB/media, transferred and restored; failure stayed blocked\n'

# Full installed transaction, with an isolated *simulated* GHCR and GitHub API.
# The application, PostgreSQL, age, SFTP, Docker pull, installed controller,
# helpers, migration, activation, health and rollback are all real. The
# registry and release-evidence server below are explicitly CI fixtures.
if sudo test -e /etc/docker/certs.d/ghcr.io || sudo test -e /usr/local/share/ca-certificates/xennic-ci-fixture.crt || docker inspect xennic-ci-fixture-registry >/dev/null 2>&1; then
  echo 'Refusing existing registry fixture paths' >&2; exit 1
fi
touch "$scratch/chain-created"
sudo /usr/sbin/sshd -f "$scratch/sshd_config"
sudo docker run -d --rm --name xennic-ci-fixture-registry -p 127.0.0.1:55000:5000 registry:2@sha256:a3d8aaa63ed8681a604f1dea0aa03f100d5895b6a58ace528858a7b332415373 >/dev/null
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj '/CN=CI fixture only' \
  -addext 'subjectAltName=DNS:ghcr.io,DNS:api.github.com' -keyout "$scratch/fixture.key" -out "$scratch/fixture.crt" >/dev/null 2>&1
sudo install -d -m 0755 /etc/docker/certs.d/ghcr.io
sudo install -o root -g root -m 0644 "$scratch/fixture.crt" /etc/docker/certs.d/ghcr.io/ca.crt
sudo install -o root -g root -m 0644 "$scratch/fixture.crt" /usr/local/share/ca-certificates/xennic-ci-fixture.crt
sudo update-ca-certificates >/dev/null
cat > "$scratch/nginx.conf" <<NGINX
worker_processes 1;
pid $scratch/nginx.pid;
error_log $scratch/nginx-error.log;
events { worker_connections 256; }
http {
  client_max_body_size 0;
  server {
    listen 127.0.0.1:443 ssl;
    server_name ghcr.io;
    ssl_certificate $scratch/fixture.crt;
    ssl_certificate_key $scratch/fixture.key;
    location / { proxy_pass http://127.0.0.1:55000; proxy_set_header Host \$host; proxy_set_header X-Forwarded-Proto https; proxy_read_timeout 300; }
  }
  server {
    listen 127.0.0.1:443 ssl;
    server_name api.github.com;
    ssl_certificate $scratch/fixture.crt;
    ssl_certificate_key $scratch/fixture.key;
    location / { proxy_pass http://127.0.0.1:58001; proxy_set_header Host \$host; }
  }
}
NGINX
sudo nginx -t -c "$scratch/nginx.conf"
sudo nginx -c "$scratch/nginx.conf"
sudo install -o root -g root -m 0700 tests/preview-github-fixture-ci.py /root/xennic-preview-install/ci-github-fixture.py
sudo sh -c '/usr/bin/python3 /root/xennic-preview-install/ci-github-fixture.py >/dev/null 2>&1 & echo $! > "$1"' sh "$scratch/github-fixture.pid"
sudo cp /etc/hosts "$scratch/hosts.original"
printf '\n127.0.0.1 ghcr.io # xennic-ci-fixture\n' | sudo tee -a /etc/hosts >/dev/null
cp /etc/hosts "$scratch/namespace-hosts"
printf '\n127.0.0.1 api.github.com # xennic-ci-fixture\n' >> "$scratch/namespace-hosts"
# Allow the Docker daemon's hosts-file cache to refresh; a synthetic login must
# succeed against the anonymous local registry before any push is attempted.
sleep 6
if ! printf 'synthetic-token\n' | docker login ghcr.io --username feerozmandi --password-stdin > "$scratch/fixture-login.log" 2>&1; then
  cat "$scratch/fixture-login.log"
  echo '::error::Disposable GHCR endpoint did not accept the synthetic login; no fixture image pushed'
  exit 1
fi
# Fake GHCR repo: these digests are not evidence of the real registry.
docker tag xennic-preview-app ghcr.io/feerozmandi/xennic-website:ci-old
docker push ghcr.io/feerozmandi/xennic-website:ci-old > "$scratch/old-push.log"
old_digest=$(awk '$2 == "digest:" && $3 ~ /^sha256:/ {print $3}' "$scratch/old-push.log" | tail -1)
oldref="ghcr.io/feerozmandi/xennic-website@$old_digest"
docker pull --platform linux/amd64 "$oldref" >/dev/null
[[ "$oldref" =~ ^ghcr\.io/feerozmandi/xennic-website@sha256:[0-9a-f]{64}$ ]] || { echo 'Invalid local fixture image reference' >&2; exit 1; }
printf '%s\n' "$oldref" > "$scratch/old-image"
cat > "$scratch/Dockerfile.good" <<'DOCKERFILE'
FROM xennic-preview-app
LABEL xennic.ci.release="good"
DOCKERFILE
docker build -t ghcr.io/feerozmandi/xennic-website:ci-good -f "$scratch/Dockerfile.good" . >/dev/null
docker push ghcr.io/feerozmandi/xennic-website:ci-good > "$scratch/good-push.log"
good_digest=$(awk '$2 == "digest:" && $3 ~ /^sha256:/ {print $3}' "$scratch/good-push.log" | tail -1)
goodref="ghcr.io/feerozmandi/xennic-website@$good_digest"
docker pull --platform linux/amd64 "$goodref" >/dev/null
[[ "$goodref" =~ ^ghcr\.io/feerozmandi/xennic-website@sha256:[0-9a-f]{64}$ && "$goodref" != "$oldref" ]] || { echo 'Invalid or unchanged good fixture image reference' >&2; exit 1; }
cat > "$scratch/Dockerfile.bad" <<'DOCKERFILE'
FROM xennic-preview-app
CMD ["node", "-e", "require('http').createServer((req,res)=>{res.writeHead(200,{'content-type':'application/json'});res.end(JSON.stringify({status:'bad'}))}).listen(3000,'0.0.0.0')"]
DOCKERFILE
docker build -t ghcr.io/feerozmandi/xennic-website:ci-bad -f "$scratch/Dockerfile.bad" . >/dev/null
docker push ghcr.io/feerozmandi/xennic-website:ci-bad > "$scratch/bad-push.log"
bad_digest=$(awk '$2 == "digest:" && $3 ~ /^sha256:/ {print $3}' "$scratch/bad-push.log" | tail -1)
badref="ghcr.io/feerozmandi/xennic-website@$bad_digest"
docker pull --platform linux/amd64 "$badref" >/dev/null
[[ "$badref" =~ ^ghcr\.io/feerozmandi/xennic-website@sha256:[0-9a-f]{64}$ ]] || { echo 'Invalid local fixture bad image reference' >&2; exit 1; }
# Compose is root-owned and fixed; only PREVIEW_IMAGE from the journal is used.
python3 - <<'PY' > "$scratch/compose-chain.yml"
from pathlib import Path
s = Path('compose.preview.yml').read_text()
old = '    build:\n      context: .\n      dockerfile: Dockerfile.preview\n'
assert old in s
print(s.replace(old, '    image: ${PREVIEW_IMAGE:?required}\n    pull_policy: never\n'), end='')
PY
sudo install -o root -g root -m 0600 "$scratch/compose-chain.yml" /srv/xennic-preview/config/compose.yml
compose=(sudo env PREVIEW_IMAGE="$oldref" docker compose -p xennic-preview --env-file /srv/xennic-preview/secrets/preview.env -f /srv/xennic-preview/config/compose.yml)
"${compose[@]}" up -d --wait --no-build app
# Only disposable files created by this CI fixture are reset; operational data is untouched.
sudo rm -f /srv/xennic-preview/work/backup.age /srv/xennic-preview/state/backup-2.json /srv/xennic-preview/state/backup-3.json
python3 - "$oldref" "$goodref" "$badref" <<'PY' > "$scratch/fixture-values.json"
import hashlib, json, pathlib, sys
old, good, bad = (x.split('@', 1)[1] for x in sys.argv[1:])
def r(n, digest):
 return {'repository':'feerozmandi/xennic-website','commit':f'{n:040x}','digest':digest,'platform':'linux/amd64','run_number':n}
h = hashlib.sha256()
root = pathlib.Path('migrations')
for path in sorted(p for p in root.rglob('*') if p.is_file()):
 name = path.relative_to(root).as_posix(); data = path.read_bytes()
 h.update(name.encode() + b'\0' + str(len(data)).encode() + b'\0' + data)
print(json.dumps({'previous':r(1,old),'first':r(2,good),'second':r(3,bad),'migration_sha256':h.hexdigest()}))
PY
python3 - "$scratch" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]); v = json.loads((p/'fixture-values.json').read_text())
(p/'chain-state.json').write_text(json.dumps({'version':1,'last_run':1,'blocked':False,'current':v['previous'],'previous':[],'pending':None}))
(p/'chain-github.json').write_text(json.dumps({'current':'first','releases':{'first':v['first'],'second':v['second']}}))
(p/'chain-transitions.json').write_text(json.dumps({'version':1,'transitions':[
 {'from_commit':v['previous']['commit'],'to_commit':v['first']['commit'],'migration_sha256':v['migration_sha256'],'previous_migrations':['20261030_163225_baseline'],'rollback_safe':True},
 {'from_commit':v['first']['commit'],'to_commit':v['second']['commit'],'migration_sha256':v['migration_sha256'],'previous_migrations':['20261030_163225_baseline'],'rollback_safe':True}]}))
PY
sudo install -o root -g root -m 0600 "$scratch/chain-state.json" /srv/xennic-preview/state/release-state.json
sudo install -o root -g root -m 0600 "$scratch/chain-github.json" /srv/xennic-preview/config/ci-github-fixture.json
sudo install -o root -g root -m 0600 "$scratch/chain-transitions.json" /srv/xennic-preview/config/compatible-transitions.json
printf 'SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n' | sudo tee /srv/xennic-preview/config/verified-host-fingerprint >/dev/null
printf 'client_id="ci"\nclient_secret="ci"\ncookie_secret="ci"\n' | sudo tee /srv/xennic-preview/secrets/oauth2-proxy.cfg >/dev/null
sudo chmod 0600 /srv/xennic-preview/config/verified-host-fingerprint /srv/xennic-preview/secrets/oauth2-proxy.cfg
sudo install -o root -g root -m 0700 tests/preview-installed-chain-ci.py /root/xennic-preview-install/ci-installed-chain.py
# Only the test subprocess sees the fake api.github.com hosts file; the runner
# itself keeps its real GitHub API. Docker sees the fake ghcr.io on this VM.
if ! chain_result=$(sudo unshare -m --propagation private /bin/sh -c 'mount --bind "$1" /etc/hosts; exec /usr/bin/python3 "$2"' sh "$scratch/namespace-hosts" /root/xennic-preview-install/ci-installed-chain.py 2>&1); then
  printf '%s\n' "$chain_result"
  printf '::error::Installed chain failed: %s\n' "${chain_result//$'\n'/; }"
  exit 1
fi
printf '%s\n' "$chain_result"
echo '::notice title=Installed preview chain::Root-owned helpers completed release, pull, SFTP backup, migration, activation, health, and an intentional post-activation failure with schema-compatible rollback; all endpoints and data were synthetic.'
