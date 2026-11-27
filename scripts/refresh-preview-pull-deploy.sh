#!/usr/bin/env bash
# Refresh the pull deployer, the fixed preview helpers and the approval
# gateway on the preview host, and then diagnose the result.
#
# The deployer is host-side tooling: it is installed from the repository source
# and is not part of the published image. The fixed preview helpers are the
# privileged phases of the deployment, and they are installed by the reviewed
# helper installer, which checks the staged set against the digest this
# release pins. This script fetches all of it from one commit, installs it,
# and then runs the read-only diagnosis.
#
#   ./scripts/refresh-preview-pull-deploy.sh <commit-ish>
#
# Root only. It never approves a transition and never deploys anything: the
# timer does that, five minutes later, and only when the transition for the
# candidate commit is reviewed or the automatic rule can prove it is safe.
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
# `preview-ci-evidence.py` imports its manifest module as a sibling, so that
# module has to travel with it: without it the diagnosis cannot read the
# evidence envelope at all.
#
# `preview-deploy-backend.py` is the privileged module the deployer starts. It
# is host-side tooling and is refreshed with the deployer, so that the two
# always agree on the request protocol and on the per-phase bounds. It is
# installed as a private module, mode 0600: it is never executed directly.
#
# `install-preview-sftp-helper.py` is the reviewed installer of the fixed
# preview helpers. It is fetched, not run, from this directory; the refresh
# path of the helper installer is what actually replaces the helpers.
FILES="preview-pull-deploy.py preview-ci-evidence.py preview-deploy-manifest.py preview-deploy-backend.py install-preview-pull-deploy.py diagnose-preview-pull-deploy.py install-preview-sftp-helper.py"
GATEWAY_SRC="/root/xennic-preview-ci-gateway"
GATEWAY_FILES="preview-ci-gateway.py preview-ci-gateway-ssh install-preview-ci-gateway.py"
GATEWAY_TARGET="/usr/local/libexec/xennic-preview/ci-gateway"
# The fixed preview helpers are staged in their own directory: the
# first-install staging directory belongs to the first-install transition.
HELPER_SRC="/root/xennic-preview-refresh"

mkdir -p "$SRC"
chmod 700 "$SRC"
cd "$SRC"

for name in $FILES; do
  curl -fsSL -o "$name" "$BASE/$REF/scripts/$name"
  echo "fetched $name"
done
sha256sum preview-pull-deploy.py preview-ci-evidence.py preview-deploy-backend.py

echo
echo "refreshing the fixed preview helpers"
# The installer names the files it installs. Asking it is better than
# repeating the list here, where it would quietly drift.
HELPER_FILES=$(python3 - "$SRC/install-preview-sftp-helper.py" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location('xennic_helper_installer', sys.argv[1])
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
print(' '.join(installer.ACTIVATION_FILES))
PY
)
install -d -o root -g root -m 0700 "$HELPER_SRC"
cd "$HELPER_SRC"
for name in $HELPER_FILES; do
  rm -f "$name"
  curl -fsSL -o "$name" "$BASE/$REF/scripts/$name"
  chmod 600 "$name"
done
echo "staged $(echo "$HELPER_FILES" | wc -w) helper files"
python3 "$SRC/install-preview-sftp-helper.py" --refresh
cd "$SRC"

echo
# The reviewed installer: it writes the deployer, the evidence module and the
# systemd unit, all root-owned, and it re-enables the timer.
python3 install-preview-pull-deploy.py

# The gateway is what the approval is given through. It is only refreshed when
# it is already installed here: the installer writes two root-owned files and
# creates no user, key, sudoers rule or SSH configuration, but installing
# something the host never had is the operator's decision, not this script's.
if [ -e "$GATEWAY_TARGET" ]; then
  echo
  echo "refreshing the approval gateway"
  mkdir -p "$GATEWAY_SRC"
  chmod 700 "$GATEWAY_SRC"
  cd "$GATEWAY_SRC"
  for name in $GATEWAY_FILES; do
    curl -fsSL -o "$name" "$BASE/$REF/scripts/$name"
    echo "fetched $name"
  done
  python3 install-preview-ci-gateway.py
  cd "$SRC"
else
  echo
  echo "the approval gateway is not installed on this host."
  echo "to install it (it creates no user, key, sudoers rule or SSH configuration):"
  echo "  mkdir -p $GATEWAY_SRC && cd $GATEWAY_SRC"
  echo "  curl -fsSL -o preview-ci-gateway.py $BASE/$REF/scripts/preview-ci-gateway.py"
  echo "  curl -fsSL -o preview-ci-gateway-ssh $BASE/$REF/scripts/preview-ci-gateway-ssh"
  echo "  curl -fsSL -o install-preview-ci-gateway.py $BASE/$REF/scripts/install-preview-ci-gateway.py"
  echo "  python3 install-preview-ci-gateway.py"
fi

echo
# Read-only: it asks GitHub for the same things the deployer asks for and
# prints the real answer for each. It prints no token. The one file it writes
# is the validated candidate manifest, and only when the read succeeded; that
# file is what the approval is given with, so nothing has to be retyped.
python3 diagnose-preview-pull-deploy.py --write-manifest
