#!/usr/bin/env bash
# Refresh the pull deployer on the preview host and then diagnose it.
#
# The deployer is host-side tooling: it is installed from the repository source
# and is not part of the published image. This script fetches the deployer,
# the evidence module, the reviewed installer and the diagnosis from one
# commit, installs them, and then runs the diagnosis.
#
#   ./scripts/refresh-preview-pull-deploy.sh <commit-ish>
#
# Root only. It never approves a transition and never deploys anything: the
# timer does that, five minutes later, and only if a reviewed transition for
# the candidate commit already exists.
set -euo pipefail

REF="${1:-}"
if [ -z "$REF" ]; then
  echo "usage: refresh-preview-pull-deploy.sh <commit-ish>" >&2
  exit 2
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "this must run as root" >&2
  exit 2
fi

BASE="https://raw.githubusercontent.com/feerozmandi/xennic-website"
SRC="/root/xennic-preview-pull-deploy"
FILES="preview-pull-deploy.py preview-ci-evidence.py install-preview-pull-deploy.py diagnose-preview-pull-deploy.py"

mkdir -p "$SRC"
chmod 700 "$SRC"
cd "$SRC"

for name in $FILES; do
  curl -fsSL -o "$name" "$BASE/$REF/scripts/$name"
  echo "fetched $name"
done
sha256sum preview-pull-deploy.py preview-ci-evidence.py

# The reviewed installer: it writes the deployer, the evidence module and the
# systemd unit, all root-owned, and it re-enables the timer.
python3 install-preview-pull-deploy.py

echo
# Read-only: it asks GitHub for the same things the deployer asks for and
# prints the real answer for each. It prints no token. The one file it writes
# is the validated candidate manifest, and only when the read succeeded; that
# file is what the approval is given with, so nothing has to be retyped.
python3 diagnose-preview-pull-deploy.py --write-manifest
