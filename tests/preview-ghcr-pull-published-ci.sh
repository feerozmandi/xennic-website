#!/usr/bin/env bash
# Trusted push-to-dev publication job only; never used by a PR job.
set -euo pipefail
if [[ "${CI:-}" != true || "${GITHUB_ACTIONS:-}" != true || "${GITHUB_EVENT_NAME:-}" != push || "${GITHUB_REF:-}" != refs/heads/dev || "${GITHUB_REPOSITORY:-}" != feerozmandi/xennic-website || -z "${GHCR_TOKEN:-}" ]]; then
  echo 'Refusing outside trusted dev publication' >&2; exit 1
fi
umask 077
for p in /root/xennic-preview-install /usr/local/libexec/xennic-preview; do
  if sudo test -e "$p"; then echo 'Refusing existing fixed installation path' >&2; exit 1; fi
done
scratch=$(mktemp -d "$RUNNER_TEMP/xennic-ghcr-pull.XXXXXX")
cleanup() {
  sudo rm -rf /root/xennic-preview-install /usr/local/libexec/xennic-preview
  rm -rf "$scratch"
}
trap cleanup EXIT
sudo install -d -o root -g root -m 0700 /root/xennic-preview-install
sudo install -d -o root -g root -m 0755 /usr/local/libexec
for f in preview-backup-sftp.py preview-backup-operation.py preview-pull-image.py preview-age-backup.py preview-deploy-readiness.py preview-deploy-state.py preview-deploy-manifest.py preview-deploy-backend.py preview-deploy-transaction.py preview-deploy-lock.py preview-internal-health.py preview-compose-operations.py preview-release-verifier.py preview-fixed-operations.py; do
  sudo install -o root -g root -m 0600 "scripts/$f" "/root/xennic-preview-install/$f"
done
sudo install -o root -g root -m 0700 scripts/install-preview-sftp-helper.py /root/xennic-preview-install/install-preview-sftp-helper.py
sudo /usr/bin/python3 /root/xennic-preview-install/install-preview-sftp-helper.py
python3 - <<'PY' > "$scratch/release.json"
import json, os
print(json.dumps({'repository': 'feerozmandi/xennic-website', 'commit': os.environ['GITHUB_SHA'],
                  'run_number': int(os.environ['GITHUB_RUN_NUMBER']), 'digest': os.environ['IMAGE_DIGEST'],
                  'platform': 'linux/amd64'}, separators=(',', ':')))
PY
# The short-lived job token is passed only via stdin; no PR job receives it.
{ cat "$scratch/release.json"; printf '%s\n' "$GHCR_TOKEN"; } | sudo /usr/local/libexec/xennic-preview/pull-image
printf 'PASS: installed pull helper retrieved and inspected the published GHCR digest\n'
