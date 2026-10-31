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
if id xennicbackupci >/dev/null 2>&1; then echo 'Refusing existing fixture user' >&2; exit 1; fi
scratch=$(mktemp -d "$RUNNER_TEMP/xennic-sftp.XXXXXX")
cleanup() {
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
for f in preview-backup-sftp.py preview-deploy-readiness.py preview-deploy-state.py preview-deploy-manifest.py; do
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
PY
sudo install -o root -g root -m 0600 "$scratch/state.json" /srv/xennic-preview/state/release-state.json
# Direct execution of the installed, root-owned helper with only a manifest on stdin.
sudo /usr/local/libexec/xennic-preview/sftp-transfer < "$scratch/release.json"
sudo test -s /srv/xennic-preview/state/backup-2.json
sudo test ! -e /srv/xennic-preview/work/verified.age
if sudo -u nobody test -w /usr/local/libexec/xennic-preview/sftp-transfer; then echo 'Unsafe helper permission' >&2; exit 1; fi
if sudo -u nobody test -r /srv/xennic-preview/secrets/backup-ssh-key; then echo 'Unsafe secret permission' >&2; exit 1; fi
before=$(sudo sha256sum /srv/xennic-preview/work/backup.age | cut -d ' ' -f 1)
sudo kill "$(sudo cat "$scratch/sshd.pid")"
sudo install -o root -g root -m 0600 "$scratch/state-failure.json" /srv/xennic-preview/state/release-state.json
if sudo /usr/local/libexec/xennic-preview/sftp-transfer < "$scratch/release-failure.json"; then echo 'Transfer failure was accepted' >&2; exit 1; fi
sudo test ! -e /srv/xennic-preview/state/backup-3.json
test "$before" = "$(sudo sha256sum /srv/xennic-preview/work/backup.age | cut -d ' ' -f 1)"
sudo grep -q '"blocked": true' /srv/xennic-preview/state/release-state.json
printf 'PASS: installed root-only SFTP helper; real encrypted upload/readback and failure stopped\n'
