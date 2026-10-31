#!/usr/bin/env bash
# Resume the owner's exact stopped OAuth lab; never rebuild, migrate or seed.
set -Eeuo pipefail
umask 077
PROJECT=xennic-real-oauth-73c028764aa6
ROOT="$HOME/xennic-real-oauth-lab.UJInfVse"
OLD_PROJECT=xennic-gate-lab-9eb37be47536
OLD_ROOT="$HOME/xennic-preview-lab.OcRYuXI8"
ORIGINAL="$HOME/xennic-oauth-runner.i6pS78Or/real-oauth-local-lab.sh"
BUNDLE=xennic-preview-gate-delivery-2026-10-31-v1.1.2
BASELINE=418de2b5b3a272e79a824ccde5411dc25f1002cc
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
STARTED=0
FIREFOX_PID=''
TAIL=''
PLACEHOLDER_CREATED=0
step='verify retained lab'

compose() {
  # Exclude shell overrides: the verified private env file defines all these values.
  env -u APP_IMAGE -u LAB_UID -u LAB_GID -u DB_PASSWORD -u DATABASE_URL -u PAYLOAD_SECRET \
    -u COMPOSE_FILE -u COMPOSE_PROFILES -u COMPOSE_PROJECT_NAME -u COMPOSE_ENV_FILES \
    docker compose --project-directory "$ROOT" --env-file "$ROOT/lab.env" -p "$PROJECT" -f "$ROOT/compose.yml" "$@"
}
cleanup() {
  local status=$?
  trap - EXIT INT TERM
  if [[ -n "$FIREFOX_PID" ]] && kill -0 "$FIREFOX_PID" 2>/dev/null; then
    kill "$FIREFOX_PID" 2>/dev/null || true
    wait "$FIREFOX_PID" 2>/dev/null || true
  fi
  if (( STARTED )); then
    echo 'Stopping only the resumed OAuth lab; its named volumes are retained.'
    if ! compose down >/dev/null 2>&1; then echo 'STOP: lab shutdown failed; inspect only this project.'; status=1; fi
  fi
  [[ -z "$TAIL" ]] || rm -f -- "$TAIL"
  if (( PLACEHOLDER_CREATED )); then
    rm -f -- "$ROOT/oauth.toml" "$ROOT/effective.json"
    if [[ -d "$ROOT/firefox-profile" && ! -L "$ROOT/firefox-profile" ]]; then
      rm -rf -- "$ROOT/firefox-profile"
    fi
  fi
  if (( status )); then echo "STOP: $step (exit $status). Later steps were not run."
  else echo 'Lab stopped. No OAuth or browser result is implied by this message.'; fi
  echo "Lab project: $PROJECT"
  echo "Private lab directory retained: $ROOT"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

for cmd in docker python3 git unzip sha256sum curl firefox; do command -v "$cmd" >/dev/null || { echo "STOP: missing $cmd"; exit 1; }; done
[[ $(uname -s) == Linux && -n ${DISPLAY:-}${WAYLAND_DISPLAY:-} ]] || { echo 'STOP: Linux desktop session required'; exit 1; }
if [[ -n ${DOCKER_HOST:-} ]]; then host=$DOCKER_HOST; else host=$(docker context inspect "$(docker context show)" --format '{{(index .Endpoints "docker").Host}}'); fi
[[ $host == unix://* ]] || { echo 'STOP: a local Docker daemon is required'; exit 1; }
[[ -d "$ROOT" && ! -L "$ROOT" ]] || { echo 'STOP: expected retained lab missing'; exit 1; }
[[ -d "$OLD_ROOT" && ! -L "$OLD_ROOT" ]] || { echo 'STOP: previous image lab missing'; exit 1; }
[[ -f "$ORIGINAL" && ! -L "$ORIGINAL" ]] || { echo 'STOP: original handoff script missing'; exit 1; }
[[ $(git -C "$OLD_ROOT/website" rev-parse HEAD) == "$BASELINE" ]] || { echo 'STOP: unexpected original app baseline'; exit 1; }
IMAGE=$(docker image inspect "${OLD_PROJECT}-app" --format '{{.Id}}')
[[ $IMAGE =~ ^sha256:[0-9a-f]{64}$ ]] || { echo 'STOP: prior app image missing'; exit 1; }
for volume in db media caddy_data; do
  docker volume inspect "${PROJECT}_${volume}" --format '{{index .Labels "com.docker.compose.project"}} {{index .Labels "com.docker.compose.volume"}}' | \
    grep -Fx "$PROJECT $volume" >/dev/null || { echo 'STOP: lab volume missing or mislabeled'; exit 1; }
done
[[ -z $(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT") ]] || { echo 'STOP: lab containers already exist; nothing stopped'; exit 1; }
[[ -z $(docker network ls -q --filter "label=com.docker.compose.project=$PROJECT") ]] || { echo 'STOP: lab networks already exist; nothing stopped'; exit 1; }
TAIL=$(mktemp "$ROOT/resume-tail.XXXXXXXX")
python3 "$SCRIPT_DIR/verify-real-oauth-resume.py" "$ROOT" "$ORIGINAL" "$OLD_ROOT/$BUNDLE.zip" "$TAIL" "$IMAGE"
# Only create files owned by this attempt; no existing file may be overwritten.
( set -o noclobber; : > "$ROOT/oauth.toml" ) || { echo 'STOP: OAuth config already exists'; exit 1; }
PLACEHOLDER_CREATED=1
compose config --quiet
compose config --format json > "$ROOT/effective.json"
python3 - "$ROOT/effective.json" <<'PY'
import json, sys
c=json.load(open(sys.argv[1])); s=c['services']
for name in ('app','postgres','gate'):
    assert not s[name].get('ports'), 'unexpected published port on '+name
for name, expected in {'postgres':{'backend'}, 'app':{'backend'},
                       'caddy':{'frontend','backend','auth'}, 'gate':{'auth','egress'}}.items():
    assert set(s[name].get('networks',{})) == expected, 'unexpected network on '+name
assert c['networks']['backend'].get('internal') and c['networks']['auth'].get('internal')
p=s['caddy'].get('ports',[])
assert len(p)==1 and p[0]['host_ip']=='127.0.0.1' and str(p[0]['published'])=='443' and p[0]['target']==443
assert all(s[n]['logging']['driver']=='none' for n in ('caddy','gate'))
print('PASS: retained Compose isolation and loopback-only Caddy port')
PY
rm -f "$ROOT/effective.json"
step='start retained OAuth lab database and verify state'
STARTED=1
compose up -d --no-build --wait postgres
STATE=$(compose exec -T postgres sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT (to_regclass('\''website.payload_migrations'\'') IS NOT NULL AND to_regclass('\''shared.customers'\'') IS NOT NULL AND EXISTS (SELECT 1 FROM website.payload_migrations WHERE name = '\''20261030_163225_baseline'\'' AND batch >= 0) AND NOT EXISTS (SELECT 1 FROM website.payload_migrations WHERE batch = -1) AND NOT EXISTS (SELECT 1 FROM website.staff) AND (SELECT count(*) FROM website.pages) >= 3 AND EXISTS (SELECT 1 FROM website.pages WHERE slug = '\''track-record-intro'\''));"')
[[ $STATE == t ]] || { echo 'STOP: retained database migration, seed or empty Staff precondition failed'; exit 1; }
echo 'PASS: retained database is migrated and seeded, and Staff is empty; no migration or seed was rerun'
# This continuation is taken byte-for-byte from the original checksum-pinned handoff.
# It uses the fixed helper in SCRIPT_DIR, and the compose function defined above.
source "$TAIL"
