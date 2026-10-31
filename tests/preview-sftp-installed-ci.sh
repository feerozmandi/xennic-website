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
  if sudo test -f /srv/xennic-preview/config/compose.yml && sudo test -f /srv/xennic-preview/secrets/preview.env; then
    sudo docker compose -p xennic-preview --env-file /srv/xennic-preview/secrets/preview.env -f /srv/xennic-preview/config/compose.yml down --volumes --remove-orphans >/dev/null 2>&1 || true
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
for f in preview-backup-sftp.py preview-backup-operation.py preview-age-backup.py preview-deploy-readiness.py preview-deploy-state.py preview-deploy-manifest.py; do
  sudo install -o root -g root -m 0600 "scripts/$f" "/root/xennic-preview-install/$f"
done
sudo install -o root -g root -m 0700 scripts/install-preview-sftp-helper.py /root/xennic-preview-install/install-preview-sftp-helper.py
sudo /usr/bin/python3 /root/xennic-preview-install/install-preview-sftp-helper.py
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
