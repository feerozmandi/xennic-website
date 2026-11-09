#!/usr/bin/env bash
# Disposable GitHub runner only; never run against an existing installation.
set -euo pipefail
[[ ${CI:-} == true && ${GITHUB_ACTIONS:-} == true && -n ${RUNNER_TEMP:-} ]] || exit 1
for p in /srv/xennic-preview /root/xennic-preview-install /usr/local/libexec/xennic-preview \
  /usr/local/libexec/.xennic-preview-update /usr/local/libexec/.xennic-preview-previous \
  /usr/local/libexec/.xennic-preview-before-network; do
  if sudo test -e "$p" || sudo test -L "$p"; then echo "Fixture path already exists: $p" >&2; exit 1; fi
done
if sudo docker volume inspect xennic-preview_preview_db >/dev/null 2>&1; then
  echo 'Fixture volume already exists' >&2; exit 1
fi
scratch=$(mktemp -d "$RUNNER_TEMP/xennic-upgrade.XXXXXX")
cleanup() {
  sudo docker volume rm xennic-preview_preview_db >/dev/null 2>&1 || true
  sudo rm -rf /srv/xennic-preview /root/xennic-preview-install /usr/local/libexec/xennic-preview \
    /usr/local/libexec/.xennic-preview-update /usr/local/libexec/.xennic-preview-previous \
    /usr/local/libexec/.xennic-preview-before-network
  rm -rf "$scratch"
}
trap cleanup EXIT
old=449a135c3c4b3bd7b0e03163e63258b1396329a0
git cat-file -e "$old^{commit}"
files=(preview-backup-sftp.py preview-backup-operation.py preview-pull-image.py preview-age-backup.py
  preview-deploy-readiness.py preview-deploy-state.py preview-deploy-manifest.py preview-deploy-backend.py
  preview-deploy-transaction.py preview-deploy-lock.py preview-internal-health.py preview-compose-operations.py
  preview-release-verifier.py preview-fixed-operations.py)
sudo install -d -m 0700 /root/xennic-preview-install /root/xennic-preview-install/incoming \
  /srv/xennic-preview /srv/xennic-preview/config /srv/xennic-preview/secrets \
  /srv/xennic-preview/state /srv/xennic-preview/work
sudo install -d -m 0755 /usr/local/libexec
for f in "${files[@]}" install-preview-sftp-helper.py; do
  git show "$old:scripts/$f" > "$scratch/$f"
  sudo install -o root -g root -m 0600 "$scratch/$f" "/root/xennic-preview-install/$f"
  if [[ $f == install-preview-sftp-helper.py ]]; then
    sudo install -o root -g root -m 0600 "scripts/$f" "/root/xennic-preview-install/incoming/$f"
  else
    git show "f18b3158cd23786da3e4ee4ff3eae70577dcdc97:scripts/$f" > "$scratch/new-$f"
    sudo install -o root -g root -m 0600 "$scratch/new-$f" "/root/xennic-preview-install/incoming/$f"
  fi
done
sudo chmod 0700 /root/xennic-preview-install/install-preview-sftp-helper.py \
  /root/xennic-preview-install/incoming/install-preview-sftp-helper.py
sudo /usr/bin/python3 /root/xennic-preview-install/install-preview-sftp-helper.py
printf 'synthetic secret; never print\n' | sudo tee /srv/xennic-preview/secrets/ci-private >/dev/null
sudo chmod 0600 /srv/xennic-preview/secrets/ci-private
printf 'synthetic configuration\n' | sudo tee /srv/xennic-preview/config/ci-config >/dev/null
sudo chmod 0600 /srv/xennic-preview/config/ci-config
before=$(sudo sha256sum /srv/xennic-preview/secrets/ci-private /srv/xennic-preview/config/ci-config | sha256sum)
installer=/root/xennic-preview-install/incoming/install-preview-sftp-helper.py

# Unknown data/journal and files or unsafe modes fail before replacing anything.
printf 'synthetic journal\n' | sudo tee /srv/xennic-preview/state/release-state.json >/dev/null
if sudo /usr/bin/python3 "$installer" --upgrade; then echo 'Existing journal accepted' >&2; exit 1; fi
sudo test -f /srv/xennic-preview/state/release-state.json
sudo rm /srv/xennic-preview/state/release-state.json # disposable fixture only
sudo docker volume create xennic-preview_preview_db >/dev/null
if sudo /usr/bin/python3 "$installer" --upgrade; then echo 'Existing volume accepted' >&2; exit 1; fi
sudo docker volume inspect xennic-preview_preview_db >/dev/null
sudo docker volume rm xennic-preview_preview_db >/dev/null # disposable fixture only
sudo touch /usr/local/libexec/xennic-preview/unknown-fixture
if sudo /usr/bin/python3 "$installer" --upgrade; then echo 'Unknown helper accepted' >&2; exit 1; fi
sudo test -f /usr/local/libexec/xennic-preview/unknown-fixture
sudo rm /usr/local/libexec/xennic-preview/unknown-fixture # disposable fixture only
sudo chmod 0644 /usr/local/libexec/xennic-preview/release-check
if sudo /usr/bin/python3 "$installer" --upgrade; then echo 'Unsafe helper mode accepted' >&2; exit 1; fi
sudo chmod 0700 /usr/local/libexec/xennic-preview/release-check
sudo chown "$(id -u):$(id -g)" /usr/local/libexec/xennic-preview/release-check
if sudo /usr/bin/python3 "$installer" --upgrade; then echo 'Unsafe helper owner accepted' >&2; exit 1; fi
sudo chown root:root /usr/local/libexec/xennic-preview/release-check
printf 'unknown version\n' | sudo tee /usr/local/libexec/xennic-preview/release-check >/dev/null
if sudo /usr/bin/python3 "$installer" --upgrade; then echo 'Modified alias accepted' >&2; exit 1; fi
sudo install -o root -g root -m 0700 /root/xennic-preview-install/preview-fixed-operations.py /usr/local/libexec/xennic-preview/release-check
printf 'unknown version\n' | sudo tee /root/xennic-preview-install/incoming/preview-deploy-state.py >/dev/null
if sudo /usr/bin/python3 "$installer" --upgrade; then echo 'Unknown new version accepted' >&2; exit 1; fi
sudo install -o root -g root -m 0600 "$scratch/new-preview-deploy-state.py" /root/xennic-preview-install/incoming/preview-deploy-state.py
sudo /usr/bin/python3 - "$installer" <<'PY'
import importlib.util, subprocess, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('ci_lock', '/usr/local/libexec/xennic-preview/preview-deploy-lock.py')
lock = importlib.util.module_from_spec(spec); spec.loader.exec_module(lock)
with lock.acquire_lock(nonblocking=True):
    result = subprocess.run(['/usr/bin/python3', sys.argv[1], '--upgrade'], check=False)
    if result.returncode == 0: raise AssertionError('update ignored deployment lock')
print('PASS: shared deployment lock rejects concurrent upgrade')
PY

# Force a failure after replacement, exercising the real installer rollback.
sudo /usr/bin/python3 - "$PWD/scripts/install-preview-sftp-helper.py" <<'PY'
import importlib.util, os, sys
from pathlib import Path
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('ci_installer', sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
original = m.verify_backend
calls = 0
def fail_after_replace():
    global calls
    calls += 1
    if calls == 2: raise RuntimeError('intentional CI failure after swap')
    original()
m.verify_backend = fail_after_replace
try:
    m.upgrade()
    raise AssertionError('injected failure accepted')
except RuntimeError as exc:
    if str(exc) != 'intentional CI failure after swap': raise
old = m.verified_sources(m.SOURCE, m.OLD_MANIFEST)
m.installed_matches(m.TARGET, old)
if m.BACKUP.exists() or not m.NEW_DIR.exists(): raise AssertionError('rollback did not restore old helpers')
print('PASS: post-swap failure restored old helpers')
PY
sudo rm -rf /usr/local/libexec/.xennic-preview-update # only the disposable CI attempt
sudo /usr/bin/python3 "$installer" --upgrade
sudo /usr/bin/python3 - "$PWD/scripts/install-preview-sftp-helper.py" <<'PY'
import importlib.util, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('ci_installer_verify', sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.installed_matches(m.TARGET, m.verified_sources(m.INCOMING, m.NEW_MANIFEST))
m.installed_matches(m.BACKUP, m.verified_sources(m.SOURCE, m.OLD_MANIFEST))
m.verify_backend()
print('PASS: installed new helpers, preserved exact prior helpers, permissions verified')
PY
if sudo /usr/bin/python3 "$installer" --upgrade; then echo 'Repeated update unexpectedly succeeded' >&2; exit 1; fi
after=$(sudo sha256sum /srv/xennic-preview/secrets/ci-private /srv/xennic-preview/config/ci-config | sha256sum)
[[ "$before" == "$after" ]] || { echo 'Protected fixture changed' >&2; exit 1; }
echo 'PASS: refusal, rollback, backup and protected-file preservation'

# Reproduce the VPS after its first bounded upgrade, including the exact old
# loopback Compose and retained 449a backup. Only disposable fixture files are
# removed between the deliberately failed attempt and the success attempt.
python3 - <<'PY' > "$scratch/old-compose.yml"
from pathlib import Path
s = Path('compose.preview.yml').read_text()
old = '    build:\n      context: .\n      dockerfile: Dockerfile.preview\n'
assert s.count(old) == 1
print(s.replace(old, '    image: ${PREVIEW_IMAGE:?required}\n    pull_policy: never\n'), end='')
PY
sudo install -o root -g root -m 0600 "$scratch/old-compose.yml" /srv/xennic-preview/config/compose.yml
sudo install -d -o root -g root -m 0700 /root/xennic-preview-install/incoming-network
for f in "${files[@]}" install-preview-sftp-helper.py; do
  sudo install -o root -g root -m 0600 "scripts/$f" "/root/xennic-preview-install/incoming-network/$f"
done
sudo install -o root -g root -m 0600 config/preview-compose.yml /root/xennic-preview-install/incoming-network/preview-compose.yml
for f in preview-gateway-compose.yml preview-Caddyfile routes.caddy oauth-gateway.caddy upstream.caddy; do
  sudo install -o root -g root -m 0600 "config/$f" "/root/xennic-preview-install/incoming-network/$f"
done
new_installer=/root/xennic-preview-install/incoming-network/install-preview-sftp-helper.py
printf 'unknown gateway\n' | sudo tee /srv/xennic-preview/config/Caddyfile >/dev/null
sudo chmod 0600 /srv/xennic-preview/config/Caddyfile
if sudo /usr/bin/python3 "$new_installer" --upgrade; then echo 'Existing gateway accepted' >&2; exit 1; fi
sudo grep -qx 'unknown gateway' /srv/xennic-preview/config/Caddyfile
sudo rm /srv/xennic-preview/config/Caddyfile # disposable fixture only
printf 'unknown gateway version\n' | sudo tee /root/xennic-preview-install/incoming-network/routes.caddy >/dev/null
if sudo /usr/bin/python3 "$new_installer" --upgrade; then echo 'Unknown gateway source accepted' >&2; exit 1; fi
sudo install -o root -g root -m 0600 config/routes.caddy /root/xennic-preview-install/incoming-network/routes.caddy
printf 'unknown compose\n' | sudo tee /srv/xennic-preview/config/compose.yml >/dev/null
if sudo /usr/bin/python3 "$new_installer" --upgrade; then echo 'Unknown previous compose accepted' >&2; exit 1; fi
sudo install -o root -g root -m 0600 "$scratch/old-compose.yml" /srv/xennic-preview/config/compose.yml
printf 'synthetic journal\n' | sudo tee /srv/xennic-preview/state/release-state.json >/dev/null
if sudo /usr/bin/python3 "$new_installer" --upgrade; then echo 'Network upgrade accepted journal' >&2; exit 1; fi
sudo test -f /srv/xennic-preview/state/release-state.json
sudo rm /srv/xennic-preview/state/release-state.json # disposable fixture only
sudo /usr/bin/python3 - "$PWD/scripts/install-preview-sftp-helper.py" <<'PY'
import importlib.util, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('network_upgrade_ci', sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
original = m.verify_backend
calls = 0
def fail_after_replace():
    global calls
    calls += 1
    if calls == 2: raise RuntimeError('injected after both replacements')
    original()
m.verify_backend = fail_after_replace
try:
    m.upgrade_network()
    raise AssertionError('injected failure accepted')
except RuntimeError as e:
    if str(e) != 'injected after both replacements': raise
m.installed_matches(m.TARGET, m.verified_sources(m.INCOMING, m.NEW_MANIFEST))
m.installed_matches(m.BACKUP, m.verified_sources(m.SOURCE, m.OLD_MANIFEST))
if m.read_private(m.COMPOSE) != m.read_private(m.COMPOSE_BACKUP): raise AssertionError('old Compose not restored')
if m.BACKUP_NETWORK.exists() or not m.NEW_DIR.exists(): raise AssertionError('old helper directory not restored')
if any((m.ROOT / 'config' / name).exists() for name in m.GATEWAY_FILES): raise AssertionError('created gateway files survived rollback')
print('PASS: network upgrade failure restored previous helper and Compose, removed only created gateway files')
PY
sudo rm -rf /usr/local/libexec/.xennic-preview-update # disposable fixture only
sudo rm /srv/xennic-preview/config/.compose-before-network.yml # disposable fixture only
sudo /usr/bin/python3 "$new_installer" --upgrade
sudo /usr/bin/python3 - "$PWD/scripts/install-preview-sftp-helper.py" <<'PY'
import importlib.util, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('network_upgrade_verify', sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.installed_matches(m.TARGET, m.verified_sources(m.INCOMING_NETWORK, m.NETWORK_MANIFEST))
m.installed_matches(m.BACKUP_NETWORK, m.verified_sources(m.INCOMING, m.NEW_MANIFEST))
m.installed_matches(m.BACKUP, m.verified_sources(m.SOURCE, m.OLD_MANIFEST))
if m.read_private(m.COMPOSE_BACKUP) == m.read_private(m.COMPOSE): raise AssertionError('Compose not upgraded')
import hashlib
for name, (source, expected) in m.GATEWAY_FILES.items():
    if hashlib.sha256(m.read_private(m.ROOT / 'config' / name)).hexdigest() != expected:
        raise AssertionError('gateway file not installed exactly')
m.verify_backend()
print('PASS: isolated-network helpers, Compose and fixed gateway installed; previous helpers and Compose retained')
PY
after=$(sudo sha256sum /srv/xennic-preview/secrets/ci-private /srv/xennic-preview/config/ci-config | sha256sum)
[[ "$before" == "$after" ]] || { echo 'Protected fixture changed' >&2; exit 1; }
