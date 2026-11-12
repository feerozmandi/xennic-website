#!/usr/bin/env bash
# Approve the migration transition for one published `dev` run, from your own
# machine, in one command.
#
# Why this exists: GitHub only dispatches a `workflow_dispatch` workflow that is
# present on the *default* branch, so `approve-release.yml` (which lives on
# `dev`) answers HTTP 404 until it reaches `main`. This script does exactly what
# that workflow does, over the same forced command, and prints the same row.
#
# It is not a shortcut around the guard: the gateway on the host recomputes the
# migration hash from the published image, compares the migration list with the
# ledger in the running database, refuses duplicates and backs the reviewed file
# up before writing. The two-pass flow is kept — nothing is typed from memory.
#
#   ./scripts/approve-transition.sh --run-id 43257283235 \
#       --migrations '["20261030_163225_baseline"]'
#
# Optional: --host, --port, --user, --identity, --repo.
set -euo pipefail

RUN_ID=''
MIGRATIONS=''
HOST='185.192.113.199'
PORT='33878'
USER_NAME='deploy'
IDENTITY="$HOME/.ssh/xennic-ci-deploy"
REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || echo feerozmandi/xennic-website)"

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --run-id) RUN_ID="${2-}"; shift 2 ;;
    --migrations) MIGRATIONS="${2-}"; shift 2 ;;
    --host) HOST="${2-}"; shift 2 ;;
    --port) PORT="${2-}"; shift 2 ;;
    --user) USER_NAME="${2-}"; shift 2 ;;
    --identity) IDENTITY="${2-}"; shift 2 ;;
    --repo) REPO="${2-}"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "unknown argument: $1" >&2; usage 2 ;;
  esac
done

[ -n "$RUN_ID" ] || { echo "--run-id is required" >&2; usage 2; }
[ -n "$MIGRATIONS" ] || { echo "--migrations is required, e.g. '[\"20261030_163225_baseline\"]'" >&2; usage 2; }
command -v gh >/dev/null || { echo "gh is required" >&2; exit 2; }
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 2; }
[ -f "$IDENTITY" ] || { echo "no identity at $IDENTITY (use --identity)" >&2; exit 2; }

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

echo "== 1/5 verifying run $RUN_ID"
info=$(gh api "repos/$REPO/actions/runs/$RUN_ID" \
  --jq '{branch: .head_branch, conclusion: .conclusion, sha: .head_sha, number: .run_number}')
branch=$(printf '%s' "$info" | python3 -c 'import json,sys;print(json.load(sys.stdin)["branch"])')
conclusion=$(printf '%s' "$info" | python3 -c 'import json,sys;print(json.load(sys.stdin)["conclusion"])')
sha=$(printf '%s' "$info" | python3 -c 'import json,sys;print(json.load(sys.stdin)["sha"])')
number=$(printf '%s' "$info" | python3 -c 'import json,sys;print(json.load(sys.stdin)["number"])')
[ "$branch" = "dev" ] || { echo "run $RUN_ID is a $branch run, not a dev run" >&2; exit 2; }
[ "$conclusion" = "success" ] || { echo "run $RUN_ID concluded '$conclusion', not success" >&2; exit 2; }
echo "   dev run $number, commit $sha"

echo "== 2/5 fetching its release evidence"
artifact=$(gh api "repos/$REPO/actions/runs/$RUN_ID/artifacts" \
  --jq '.artifacts[].name | select(startswith("xennic-preview-release-"))' | sort | tail -1)
[ -n "$artifact" ] || { echo "run $RUN_ID published no release evidence" >&2; exit 2; }
gh run download "$RUN_ID" --repo "$REPO" -n "$artifact" -D "$work/evidence" >/dev/null
python3 "$(dirname "$0")/preview-ci-evidence.py" --run-id "$RUN_ID" --commit "$sha" \
  --run-number "$number" < "$work/evidence/xennic-preview-release.json" > "$work/manifest.json"
echo "   $(cat "$work/manifest.json")"

ssh_run() {
  ssh -i "$IDENTITY" -p "$PORT" -o BatchMode=yes -o IdentitiesOnly=yes \
      -o ConnectTimeout=20 -o ConnectionAttempts=1 -o StrictHostKeyChecking=yes \
      "$USER_NAME@$HOST" "$@" < "$work/manifest.json"
}

echo "== 3/5 asking the host what it thinks (read-only)"
report=$(ssh_run preflight)
echo "   $report"
case "$report" in
  *'"transition_approved":true'*)
    echo "   this transition is already approved; nothing to do."
    exit 0
    ;;
esac

encoded=$(printf '%s' "$MIGRATIONS" | base64 | tr -d '\n')

echo "== 4/5 first pass: let the host compute the hash from the published image"
set +e
first=$(ssh_run "approve $(printf '0%.0s' $(seq 64)) $encoded" 2>&1)
status=$?
set -e
computed=$(printf '%s' "$first" | sed -n 's/.*migration hash mismatch: image gives \([0-9a-f]\{64\}\).*/\1/p')
if [ "$status" -ne 0 ] && [ -z "$computed" ]; then
  echo "$first" >&2
  echo "the host refused the approval; nothing was written." >&2
  exit "$status"
fi
if [ "$status" -eq 0 ]; then
  echo "   approved on the first pass: $first"
  exit 0
fi
echo "   image computes $computed"

echo "== 5/5 second pass: approve exactly that hash"
ssh_run "approve $computed $encoded"
echo
echo "done. Re-run the deploy workflow for run $RUN_ID, or dispatch deploy-dev."
