#!/usr/bin/env bash
# Resume only the synthetic lab stopped before Staff bootstrap on Docker 29.
# No rebuild, migration, real OAuth, host port, VPS, DNS or real credentials.
set -Eeuo pipefail
umask 077

PROJECT=${2:-}
ROOT=${1:-}
EXPECTED_PROJECT=xennic-gate-lab-9eb37be47536
BUNDLE_NAME=xennic-preview-gate-delivery-2026-10-31-v1.1.2
BASELINE=418de2b5b3a272e79a824ccde5411dc25f1002cc
NODE='node:22.22.3-bookworm-slim@sha256:e21fc383b50d5347dc7a9f1cae45b8f4e2f0d39f7ade28e4eef7d2934522b752'
step='validate retained disposable lab'
STARTED=0
TEMP_OVERLAY=''
CONFIG=''
compose() {
  LAB_DIR="$BUNDLE" docker compose --project-directory "$SITE" --env-file "$ENVFILE" \
    -p "$PROJECT" -f "$SITE/compose.preview.yml" \
    -f "$BUNDLE/compose.payload-lab.override.yml" -f "$PINS" -f "$TEMP_OVERLAY" "$@"
}
cleanup() {
  local status=$?
  trap - EXIT
  if (( STARTED )); then
    echo 'Stopping only this lab project; all named volumes are retained.'
    if ! compose down >/dev/null 2>&1; then echo 'STOP: lab shutdown failed; inspect this project.'; status=1; fi
  fi
  [[ -z "$CONFIG" ]] || rm -f "$CONFIG"
  [[ -z "$TEMP_OVERLAY" ]] || rm -f "$TEMP_OVERLAY"
  if (( status )); then echo "STOP: $step failed (exit $status). No subsequent step was run."
  else echo 'PASS: synthetic internal-network integration and seed completed. No real OAuth or browser tested.'; fi
  exit "$status"
}
trap cleanup EXIT
[[ "$PROJECT" == "$EXPECTED_PROJECT" ]] || { echo 'STOP: unexpected project; no resources changed.'; exit 1; }
[[ -d "$ROOT" && ! -L "$ROOT" ]] || { echo 'STOP: lab directory not found or is a symlink.'; exit 1; }
ROOT=$(cd "$ROOT" && pwd -P)
SITE="$ROOT/website"
BUNDLE="$ROOT/$BUNDLE_NAME"
ENVFILE="$ROOT/lab.env"
PINS="$ROOT/verified-images.yml"
ZIP="$ROOT/xennic-preview-gate-delivery-2026-10-31-v1.1.2.zip"
[[ -f "$ENVFILE" && -f "$PINS" && -f "$SITE/compose.preview.yml" && -f "$BUNDLE/SHA256SUMS" && -f "$ZIP" ]] || { echo 'STOP: missing lab files.'; exit 1; }
[[ $(git -C "$SITE" rev-parse HEAD) == "$BASELINE" ]] || { echo 'STOP: unexpected app commit.'; exit 1; }
[[ $(sha256sum "$ZIP" | cut -d' ' -f1) == 63f6f07ae46ed05494d8caff10f84e2b4755fd901bdf30d1c648fcda3e6d760c ]] || { echo 'STOP: bundle ZIP hash mismatch.'; exit 1; }
python3 - "$ZIP" "$BUNDLE/SHA256SUMS" "$BUNDLE_NAME" <<'PY'
import sys, zipfile
from pathlib import Path
with zipfile.ZipFile(sys.argv[1]) as z:
    assert z.read(sys.argv[3]+'/SHA256SUMS') == Path(sys.argv[2]).read_bytes(), 'Unexpected bundle checksum file'
PY
(cd "$BUNDLE" && sha256sum -c SHA256SUMS >/dev/null)
[[ $(sha256sum "$SITE/compose.preview.yml" | cut -d' ' -f1) == e00963aed6cd1b6d87a27af55b71f662304097a338e519d7f286dcbc3c40918c ]] || { echo 'STOP: unexpected base Compose.'; exit 1; }
# Verify the original handoff's only expected checkout modification and image pins.
python3 - "$SITE/Dockerfile.preview" "$PINS" "$NODE" <<'PY'
import subprocess, sys
from pathlib import Path
p=Path(sys.argv[1]); original=subprocess.check_output(['git','-C',str(p.parent),'show','HEAD:Dockerfile.preview'],text=True)
expected=original.replace('FROM node:22.22.3-bookworm-slim AS ', 'FROM '+sys.argv[3]+' AS ')
assert original.count('FROM node:22.22.3-bookworm-slim AS ') == 2 and p.read_text() == expected, 'Unexpected Dockerfile; stop'
pins='services:\n  postgres:\n    image: postgres:16.14-bookworm@sha256:64154d0babcb1741988719e703419af0382b19953706149f9872fbd0f438efa8\n'
assert Path(sys.argv[2]).read_text() == pins, 'Unexpected image pins; stop'
PY
for volume in preview_db preview_media payload_caddy_data; do
  docker volume inspect "${PROJECT}_${volume}" --format '{{index .Labels "com.docker.compose.project"}} {{index .Labels "com.docker.compose.volume"}}' | \
    grep -Fx "$PROJECT $volume" >/dev/null || { echo 'STOP: expected isolated volume missing or mislabeled.'; exit 1; }
done
docker image inspect "${PROJECT}-app" >/dev/null || { echo 'STOP: original app image is absent; no rebuild performed.'; exit 1; }
if ! docker image inspect "$NODE" >/dev/null 2>&1; then
  echo 'Fetching the previously verified Node image for the isolated test client.'
  docker pull --platform linux/amd64 "$NODE" >/dev/null
fi
TEMP_OVERLAY=$(mktemp "$ROOT/resume-network.XXXXXXXX.yml")
printf 'services:\n  caddy:\n    ports: !reset []\n' > "$TEMP_OVERLAY"
compose config --quiet
[[ -z $(compose ps --all -q) ]] || { echo 'STOP: lab containers already exist; nothing stopped.'; exit 1; }
CONFIG=$(mktemp "$ROOT/resume-config.XXXXXXXX.json")
compose config --format json > "$CONFIG"
python3 - "$CONFIG" <<'PY'
import json,sys
c=json.load(open(sys.argv[1])); services=c['services']
for name in ('app','postgres','gate','caddy'):
    assert not services[name].get('ports'), 'Unexpected published port on '+name
    assert set(services[name].get('networks',{})) == {'preview_gate_lab'}, 'Unexpected network on '+name
assert c['networks']['preview_gate_lab'].get('internal'), 'Network is not internal'
print('PASS: Compose has no published ports; all services use one internal network')
PY
rm -f "$CONFIG"; CONFIG=''

step='start only retained synthetic PostgreSQL'
STARTED=1
compose up -d --no-build --wait postgres
step='verify migration and absence of prior bootstrap or seed'
STATE=$(compose exec -T postgres sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT (to_regclass('\''website.payload_migrations'\'') IS NOT NULL AND to_regclass('\''shared.customers'\'') IS NOT NULL AND EXISTS (SELECT 1 FROM website.payload_migrations WHERE name = '\''20261030_163225_baseline'\'' AND batch >= 0) AND NOT EXISTS (SELECT 1 FROM website.payload_migrations WHERE batch = -1) AND NOT EXISTS (SELECT 1 FROM website.staff) AND NOT EXISTS (SELECT 1 FROM website.pages));"')
[[ "$STATE" == t ]] || { echo 'STOP: migration or empty bootstrap/seed precondition failed.'; exit 1; }
echo 'PASS: existing migration and empty Staff/pages; no migration or seed was rerun'

step='start app, Caddy and synthetic gate without host ports'
compose up -d --no-build --wait app caddy gate
step='verify actual and configured port bindings'
for service in app postgres gate caddy; do
  id=$(compose ps -q "$service")
  [[ -n "$id" ]] || { echo 'STOP: missing lab container.'; exit 1; }
  docker inspect --format '{{json .HostConfig.PortBindings}} {{json .NetworkSettings.Ports}}' "$id" | python3 -c '
import json,sys
service=sys.argv[1]; line=sys.stdin.read(); decoder=json.JSONDecoder()
config,end=decoder.raw_decode(line); actual=json.loads(line[end:].strip())
for ports in (config or {},actual or {}):
    if any(ports.values()): raise SystemExit("STOP: unexpected host port on "+service)
print("PASS: no published ports",service)
' "$service"
done
NETWORK_ID=$(docker network ls -q --filter "label=com.docker.compose.project=$PROJECT" --filter 'label=com.docker.compose.network=preview_gate_lab')
[[ $(printf '%s\n' "$NETWORK_ID" | grep -c .) == 1 ]] || { echo 'STOP: expected exactly one lab network.'; exit 1; }

step='run real Payload with synthetic gate inside internal network'
caddy_id=$(compose ps -q caddy)
CA=$(mktemp "$ROOT/resume-ca.XXXXXXXX.crt")
TEST=$(mktemp "$ROOT/resume-test.XXXXXXXX.mjs")
docker cp "$caddy_id:/data/caddy/pki/authorities/local/root.crt" "$CA"
python3 - "$BUNDLE/test_payload_caddy.mjs" "$TEST" <<'PY'
from pathlib import Path
import sys
source=Path(sys.argv[1]).read_text()
needle="import https from 'node:https'"
assert source.count(needle)==1
source=source.replace(needle, needle+"\nimport dns from 'node:dns'")
old="""      lookup(_host, options, cb) {
        if (options?.all) cb(null, [{address:'127.0.0.1', family:4}])
        else cb(null, '127.0.0.1', 4)
      },"""
assert source.count(old)==1
source=source.replace(old,"      lookup(_host, options, cb) { dns.lookup('caddy', options, cb) },")
needle="  check(r.status === 200 && Boolean(cookieMe.user?.email), 'Payload Cookie session works through Caddy')\n"
assert source.count(needle)==1
extra="""
  r = await request('/api/staff/me', {headers:{Cookie:payloadCookie, 'Sec-Fetch-Site':'same-origin'}})
  check(r.status === 200 && Boolean(jsonBody(r).user?.email), 'origin-less same-origin cookie request authenticates')
  r = await request('/api/staff/me', {headers:{Cookie:payloadCookie}})
  check(r.status === 200 && jsonBody(r).user === null, 'origin-less request without Fetch Metadata is not authenticated')
"""
Path(sys.argv[2]).write_text(source.replace(needle,needle+extra))
PY
echo 'Test-copy diff: internal Caddy DNS and Origin-absent checks; bundle remains unchanged.'
docker run --rm --network "$NETWORK_ID" --user "$(id -u):$(id -g)" \
  -e LAB_CA_FILE=/lab-root.crt -v "$CA:/lab-root.crt:ro" \
  -v "$TEST:/test-payload-local.mjs:ro" --entrypoint node "$NODE" /test-payload-local.mjs
step='seed approved content once after successful integration'
compose run --rm --no-deps app npm run preview:seed
step='complete'
